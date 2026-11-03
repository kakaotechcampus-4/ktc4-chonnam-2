"""전용 Linux 컨테이너에서 실제 Recording과 runner/DB cgroup observer를 연결한다.

호스트 감독기가 생성한 보호 connection 파일만 소비한다. 원문 argv/경로는 /evidence의
private 파일에만 저장하며 stdout에는 고정 상태와 집계만 출력한다.
"""
import argparse
from contextlib import contextmanager
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import time
from types import SimpleNamespace

from recording_cpu_quota_probe import PhaseObserver, classify_argv, read_cgroup


TOOL_HASHES = {
    'ffmpeg': '19e0073f42f3cc0c1880ac9a4a91fc6c42d511bec9497db03872cc527791c91a',
    'ffprobe': 'ec4bde78f8b08c56109d68fffb16e9972ae7543ed62253fd90e699dda4a0f975',
}


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)


def append(path, value):
    with Path(path).open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(value) + '\n')
        stream.flush()


def resolve_leaf(root, text):
    lines = text.strip().splitlines()
    if len(lines) != 1 or not lines[0].startswith('0::/'):
        raise ValueError('CPU_UNIFIED_HOST_NAMESPACE_REQUIRED')
    raw = PurePosixPath(lines[0][3:])
    if '..' in raw.parts:
        raise ValueError('CPU_SCOPE_ESCAPE')
    root = Path(root).resolve()
    try:
        leaf = (root / str(raw).lstrip('/')).resolve(strict=True)
    except OSError:
        raise ValueError('CPU_LEAF_UNAVAILABLE') from None
    if not leaf.is_relative_to(root) or leaf == root:
        raise ValueError('CPU_LEAF_REQUIRED')
    return leaf


def cpu_set(text):
    values = set()
    for part in text.split(','):
        if '-' in part:
            a, b = map(int, part.split('-'))
            values.update(range(a, b+1))
        elif part:
            values.add(int(part))
    return values


def require_limits(value, quota, memory_mib, *, affinity=None):
    maximum, period = value['cpu_max'].split()
    if maximum == 'max' or Fraction(int(maximum), int(period)) != Fraction(quota):
        raise ValueError('CPU_ACTUAL_QUOTA_MISMATCH')
    if value['memory_max'] != memory_mib*1024**2 or value['memory_swap_max'] != 0:
        raise ValueError('CPU_ACTUAL_MEMORY_MISMATCH')
    if affinity is not None and (cpu_set(value['cpuset']) != affinity or affinity != {0, 1}):
        raise ValueError('CPU_ACTUAL_AFFINITY_MISMATCH')


def require_parent_limits(parents):
    for value in parents:
        maximum = value['cpu_max']
        if maximum is not None:
            quota, period = maximum.split()
            if quota != 'max' and Fraction(int(quota), int(period)) < Fraction(5, 2):
                raise ValueError('CPU_PARENT_QUOTA_INSUFFICIENT')
        if not {0, 1} <= cpu_set(value['cpuset']):
            raise ValueError('CPU_PARENT_CPUSET_INSUFFICIENT')


def require_same_hierarchy(before, after):
    if before != after:
        raise ValueError('CPU_PARENT_CHANGED')


def require_readonly_cgroup(mountinfo):
    found=[]
    for line in mountinfo.splitlines():
        left, right=line.split(' - ',1)
        fields=left.split()
        if fields[4]=='/sys/fs/cgroup' and right.split()[0]=='cgroup2':
            found.append('ro' in fields[5].split(','))
    if found != [True]:
        raise ValueError('CPU_CGROUP_READONLY_MOUNT_REQUIRED')
    return True


def hierarchy(leaf, root):
    parents = []
    node = leaf.parent
    while node.is_relative_to(root):
        maximum = node/'cpu.max'
        cpuset = node/'cpuset.cpus.effective'
        if node != root and not maximum.is_file():
            raise ValueError('CPU_PARENT_MAX_MISSING')
        if not cpuset.is_file():
            raise ValueError('CPU_PARENT_CPUSET_MISSING')
        parents.append({'identity':[node.stat().st_dev,node.stat().st_ino],
            'cpu_max':maximum.read_text().strip() if maximum.exists() else None,
            'cpuset':cpuset.read_text().strip()})
        if node == root:
            break
        node = node.parent
    require_parent_limits(parents)
    return parents


def limits(leaf):
    value = read_cgroup(leaf)
    value['memory_max'] = int((leaf/'memory.max').read_text())
    value['memory_swap_max'] = int((leaf/'memory.swap.max').read_text())
    return value


@contextmanager
def capture_tools(cls, observer, private_path):
    original = cls._run
    def observed(instance, argv):
        category = classify_argv(argv)['category']
        with observer.phase('argv_' + category) as event:
            append(private_path, {'event_id':event['id'], 'argv':list(argv),
                'summary':classify_argv(argv), 'monotonic_sec':time.monotonic()})
            return original(instance, argv)
    cls._run = observed
    try:
        yield
    finally:
        cls._run = original


class JournalObserver(PhaseObserver):
    def __init__(self, collect, events, journal):
        super().__init__(collect, events)
        self.journal = journal

    def snapshot(self, event):
        value = super().snapshot(event)
        append(self.journal, {'event_id':event['id'], 'phase':event['phase'], 'snapshot':value})
        return value


def run(connection):
    import shutil
    from daesingo.recording import LocalAnalysisMaterializer
    import daesingo.recording
    import recording_real_media_recheck as runner
    from recording_cpu_quota_probe import observe_measurements
    root = Path('/sys/fs/cgroup').resolve()
    output = Path('/evidence')
    tag = connection['tag']
    events = []
    result = {'status':'FAIL', 'tag':tag, 'events':events, 'provider_calls':0}
    observer = None
    try:
        if not str(Path(daesingo.recording.__file__).resolve()).startswith('/repo/src/'):
            raise ValueError('CURRENT_CHECKOUT_REQUIRED')
        result['cgroup_readonly']=require_readonly_cgroup(Path('/proc/self/mountinfo').read_text())
        runner_leaf = resolve_leaf(root, Path('/proc/self/cgroup').read_text())
        db_leaf = resolve_leaf(root, connection['db_cgroup'])
        if runner_leaf == db_leaf:
            raise ValueError('CPU_DISTINCT_ACTORS_REQUIRED')
        initial = {'runner':limits(runner_leaf), 'db':limits(db_leaf)}
        require_limits(initial['runner'], connection['quota'],1280,affinity=os.sched_getaffinity(0))
        require_limits(initial['db'], '0.5',512)
        parents = {actor:hierarchy(leaf,root) for actor,leaf in [('runner',runner_leaf),('db',db_leaf)]}
        result.update(initial=initial, parents=parents, affinity=sorted(os.sched_getaffinity(0)),
            product_import='/repo/src/daesingo/recording', tool_hashes={})
        for tool, expected in TOOL_HASHES.items():
            binary = Path(shutil.which(tool))
            with binary.open('rb') as stream:
                digest = hashlib.file_digest(stream,'sha256').hexdigest()
            if digest != expected:
                raise ValueError('CPU_TOOL_IDENTITY_MISMATCH')
            result['tool_hashes'][tool] = digest
        def collect():
            values = {'runner':read_cgroup(runner_leaf),'db':read_cgroup(db_leaf)}
            for actor in values:
                if values[actor]['cpu_max'] != initial[actor]['cpu_max'] or values[actor]['cpuset'] != initial[actor]['cpuset']:
                    raise ValueError('CPU_RUNTIME_LIMIT_CHANGED')
                limit=(1100 if actor=='runner' else 440)*1024**2
                if values[actor]['memory_current']>=limit or (values[actor]['memory_peak'] or 0)>=limit:
                    raise ValueError('CPU_MEMORY_SOFT_STOP')
                if values[actor]['memory_events'] is None or any(values[actor]['memory_events'].get(key,0)
                        for key in ('oom','oom_kill','oom_group_kill')):
                    raise ValueError('CPU_MEMORY_EVENTS_STOP')
            for actor,leaf in [('runner',runner_leaf),('db',db_leaf)]:
                require_same_hierarchy(parents[actor],hierarchy(leaf,root))
            return values
        observer = JournalObserver(collect,events,output/(tag+'-cpu-snapshots.private.jsonl'))
        original_measure, original_tool = runner.diag.measure, LocalAnalysisMaterializer._run
        with capture_tools(LocalAnalysisMaterializer, observer, output/(tag+'-argv.private.jsonl')):
            if connection['mode'] == 'acceptance':
                import xml.etree.ElementTree as ET
                sys.path.append('/host-packages')
                import pytest
                controls=pytest.main(['/repo/tests/runtime/test_recording_cpu_quota_probe.py',
                    '/repo/tests/runtime/test_recording_cpu_quota_supervisor.py','-q','-p','no:cacheprovider',
                    '--basetemp=/tmp/cpu-controls','--junitxml=/evidence/linux-controls.private.xml'])
                if controls!=0:
                    raise ValueError('CPU_LINUX_CONTROLS_FAILED')
                suites=ET.parse('/evidence/linux-controls.private.xml').getroot()
                result['linux_control_count']=sum(int(s.attrib.get('tests',0)) for s in suites.iter('testsuite'))
                import sqlalchemy as sa
                with runner.egress_fence(connection['db_host']):
                    engine = sa.create_engine(sa.URL.create('mysql+pymysql',username='root',host=connection['db_host'],database='probe'),
                        hide_parameters=True,connect_args={'connect_timeout':5,'read_timeout':10,'write_timeout':10})
                    try:
                        with observe_measurements(runner.diag,observer), runner.diag.measure([], 'linux_connection_acceptance'):
                            with engine.connect() as conn:
                                if conn.exec_driver_sql('SELECT 1').scalar_one() != 1:
                                    raise ValueError('CPU_DB_ACCEPTANCE_FAILED')
                            LocalAnalysisMaterializer({})._run(['ffprobe','-version'])
                            import tempfile
                            sampler_report={'phase':'linux_acceptance','samples':[]}
                            sampler=runner.Sampler(Path('/work'),sampler_report,output/'acceptance.abort')
                            if sampler.cgroup_root!=runner_leaf:
                                raise ValueError('CPU_SAMPLER_LEAF_MISMATCH')
                            with tempfile.TemporaryFile(dir='/work') as sentinel:
                                sentinel.write(b'x'*4096)
                                sentinel.flush()
                                if sampler.collect()['including_open_unlinked_bytes']<4096:
                                    raise ValueError('CPU_SAMPLER_TEMP_SENTINEL_MISSING')
                                sampler.start()
                                try:
                                    deadline=time.monotonic()+3
                                    while len(sampler_report['samples'])<3:
                                        sampler.check()
                                        if time.monotonic()>deadline:
                                            raise ValueError('CPU_SAMPLER_ACCEPTANCE_TIMEOUT')
                                        time.sleep(.05)
                                finally:
                                    sampler.close()
                            sampler.check()
                            if sampler.thread.is_alive() or runner.temp_usage(Path('/work'))['including_open_unlinked_bytes']:
                                raise ValueError('CPU_SAMPLER_ACCEPTANCE_CLEANUP_FAILED')
                            result['sampler_acceptance']={'sample_count':len(sampler_report['samples']),
                                'samples':sampler_report['samples'],'leaf_verified':True,'temp_after_bytes':0,
                                'peak_bytes':int((sampler.cgroup_root/'memory.peak').read_text()),'thread_closed':True}
                    finally:
                        engine.dispose()
                result['status'] = 'PASS_LINUX_ACCEPTANCE'
            else:
                args = SimpleNamespace(manifest='/fixture/manifest.private.json',output='/evidence/'+tag+'.json',
                    db_host=connection['db_host'],schema='probe',code_sha=connection['code_sha'],image_id=connection['image_id'],
                    first=2 if tag=='smoke' else 1,count=1 if tag=='smoke' else 2,seconds=10 if tag=='smoke' else 120,
                    experimental_config='/evidence/config.json',recording_only=True,coarse_270p_crf28=False)
                if runner.run(args,cpu_observer=observer) != 0:
                    raise ValueError('CPU_RECORDING_RUN_FAILED')
                report = json.loads(Path(args.output).read_text())
                if report['status'] != 'PASS_RECORDING_ONLY':
                    raise ValueError('CPU_RECORDING_NOT_PASS')
                result['status'] = 'PASS_RECORDING_ONLY'
        if runner.diag.measure is not original_measure or LocalAnalysisMaterializer._run is not original_tool:
            raise ValueError('CPU_HOOK_RESTORE_FAILED')
        if not events or any(event['status'] != 'PASS' for event in events):
            raise ValueError('CPU_PHASE_MISSING_OR_FAILED')
        result['hooks_restored'] = True
        result['final'] = collect()
    except BaseException as error:
        result.update(status='FAIL',error_type=type(error).__name__,error_code=str(error) if isinstance(error,ValueError) else None)
    finally:
        write_new(output/(tag+'-cpu.private.json'),result)
    print(json.dumps({'tag':tag,'status':result['status'],'phase_count':len(events)}))
    return 0 if result['status'].startswith('PASS_') else 1


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connection',required=True)
    args=parser.parse_args()
    raise SystemExit(run(json.loads(Path(args.connection).read_text())))
