"""격리 Linux runner 진입점. source/의존성·cgroup·DB/청크/metadata 연결 검증."""
from contextlib import contextmanager
from decimal import Decimal
from fractions import Fraction
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace

import recording_cpu_quota_linux as bridge
from recording_ec2_package import verify_files


def placement_gate(expected, actual, stage):
    if stage not in ('smoke', 'representative', 'full'):
        raise ValueError('EXPLICIT_PLACEMENT_STAGE_REQUIRED')
    ids = [f'input-{n:02}' for n in range(1, 16)] if stage == 'full' else (
        ['input-02'] if stage == 'smoke' else ['input-01', 'input-02'])
    if [p['id'] for p in expected] != ids or actual != expected:
        raise ValueError('EXPLICIT_PLACEMENT_MISMATCH')
    offset = Decimal(0)
    for p in expected:
        if p['video_index'] != 0 or Decimal(str(p['start'])) != offset:
            raise ValueError('EXPLICIT_PLACEMENT_GAP_OR_STREAM')
        offset = Decimal(str(p['end']))
    if stage == 'full':
        from recording_full_input import require_full_scope
        require_full_scope(expected, expected[-1]['end'])
    elif offset < (10 if stage == 'smoke' else 120):
        raise ValueError('EXPLICIT_PLACEMENT_SHORT')


def parent_gate(parents, quota, affinity):
    for value in parents:
        if value['cpu_max'] is not None:
            maximum, period = value['cpu_max'].split()
            if maximum != 'max' and Fraction(int(maximum), int(period)) < Fraction(quota):
                raise ValueError('PARENT_CPU_QUOTA_INSUFFICIENT')
        if not affinity <= bridge.cpu_set(value['cpuset']):
            raise ValueError('PARENT_CPUSET_INSUFFICIENT')


def ancestor_memory(leaf, root):
    values = []
    node = leaf.parent
    while node.is_relative_to(root):
        value = {'identity': [node.stat().st_dev, node.stat().st_ino], 'root': node == root}
        for key, filename in (('max', 'memory.max'), ('high', 'memory.high'),
                              ('swap_max', 'memory.swap.max'), ('current', 'memory.current'), ('events', 'memory.events')):
            path = node/filename
            if not path.exists() and node != root:
                raise ValueError('PARENT_MEMORY_SCOPE_MISSING')
            raw = path.read_text().strip() if path.exists() else None
            value[key] = raw
            if key == 'current':
                value[key] = int(raw) if raw is not None else None
            if key == 'events':
                from recording_cpu_quota_probe import counters
                value[key] = counters(raw) if raw is not None else None
        values.append(value)
        if node == root:
            break
        node = node.parent
    return values


def parent_memory_gate(values, before=None):
    if before is not None:
        def frozen(seq):
            return [{k: v[k] for k in ('identity', 'root', 'max', 'high', 'swap_max')} for v in seq]
        if frozen(values) != frozen(before):
            raise ValueError('PARENT_MEMORY_SCOPE_CHANGED')
    for value in values:
        # host namespace의 hierarchy root는 이 파일을 제공하지 않을 수 있다.
        # 그 경우 null을 보존하고 /proc/meminfo의 별도 host reserve를 적용한다.
        if value['root'] and all(value[k] is None for k in ('max', 'high', 'swap_max', 'current', 'events')):
            continue
        if (value['max'] != 'max' or value['high'] != 'max'
                or value['swap_max'] is None or type(value['current']) is not int or value['current'] < 0
                or value['events'] is None
                or any(value['events'].get(k, 0) for k in ('oom', 'oom_kill', 'oom_group_kill'))):
            # 유한 상위 memory scope의 공유 잔여 예산은 이 adapter가 추정하지 않는다.
            raise ValueError('PARENT_MEMORY_FINITE_OR_UNVERIFIED')


def leaf_scope_gate(value, before):
    if any(value[k] != before[k] for k in
           ('identity', 'cpu_max', 'cpuset', 'memory_max', 'memory_swap_max')):
        raise ValueError('RUNTIME_CGROUP_LIMIT_CHANGED')


def inventory():
    import platform
    return {'python': platform.python_version(),
            'distributions': sorted({(d.metadata['Name'].lower(), d.version) for d in importlib.metadata.distributions()}),
            'tools': {t: hashlib.sha256(Path(shutil.which(t)).read_bytes()).hexdigest() for t in ('ffmpeg', 'ffprobe')}}


def synthetic_content():
    def box(kind, data):
        return (8+len(data)).to_bytes(4, 'big')+kind+data
    return box(b'ftyp', b'isom\x00\x00\x00\x00')+box(b'moov', b'')+box(b'mdat', b'\x00\x01\x02\x03'*150000)


@contextmanager
def authenticated_database(host, path):
    """기존 하네스의 무암호 URL을 정확한 새 DB IP/schema에 한해 인증 URL로 결속한다."""
    import sqlalchemy as sa
    credentials = json.loads(Path(path).read_text())
    original = sa.create_engine
    def create(url, *args, **kwargs):
        if (not isinstance(url, sa.URL) or url.drivername != 'mysql+pymysql'
                or url.host != host or url.database != 'probe' or url.username != 'root' or url.password):
            raise ValueError('EXACT_EXPERIMENT_DB_URL_REQUIRED')
        return original(url.set(password=credentials['password']), *args, **kwargs)
    sa.create_engine = create
    try:
        yield
    finally:
        sa.create_engine = original


def acceptance(host):
    """미디어 없이 실제 migration·청크 저장/새 연결 decoder·rollback·sampler 확인."""
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config
    from daesingo.recording.models import AnalysisSource, ContractRef
    from daesingo.recording.mysql_repository import MySQLRecordingRepository
    import recording_real_media_recheck as runner
    engine = sa.create_engine(sa.URL.create('mysql+pymysql', username='root', host=host, database='probe'),
                              hide_parameters=True, connect_args={'connect_timeout': 5, 'read_timeout': 10, 'write_timeout': 10})
    content = synthetic_content()
    media = AnalysisSource(contract='AnalysisSource', contract_version='analysis-source-derived/v1',
        analysis_source_ref='acceptance-chunks', asset_kind='ANALYSIS_SOURCE',
        source_refs=[ContractRef(kind='source_asset', ref='synthetic')], media_stream_refs=['synthetic-video'],
        byte_size=len(content), availability='AVAILABLE', duration_sec=0.10000000000000002,
        timeline_ref=None, timeline_range=None, profile_ref='synthetic-no-media')
    try:
        with engine.begin() as conn:
            if conn.exec_driver_sql('SHOW TABLES').all():
                raise ValueError('NEW_EMPTY_SCHEMA_REQUIRED')
            config = Config('/repo/migrations/recording/alembic.ini')
            config.attributes['connection'] = conn
            command.upgrade(config, 'head')
            if conn.exec_driver_sql('SELECT version_num FROM recording_alembic_version').scalar_one() != 'recording_0002':
                raise ValueError('LATEST_RECORDING_MIGRATION_REQUIRED')
            repo = MySQLRecordingRepository(conn, storage_root='/work', temp_root='/work')
            repo.add_prepared_media(media, content)
            if conn.exec_driver_sql('SELECT COUNT(*) FROM recording_media_chunk').scalar_one() < 2:
                raise ValueError('CHUNK_WRITER_NOT_USED')
        engine.dispose()  # 새 물리 연결과 metadata decoder를 검증한다.
        with engine.connect() as conn:
            repo = MySQLRecordingRepository(conn, storage_root='/work', temp_root='/work')
            restored = repo.get_analysis_source(media.analysis_source_ref)
            if restored.model_dump() != media.model_dump() or restored.duration_sec.hex() != media.duration_sec.hex():
                raise ValueError('METADATA_EXACT_MISMATCH')
            stream, _ = repo.open_analysis_stream(media.analysis_source_ref)
            with stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != hashlib.sha256(content).hexdigest():
                    raise ValueError('CHUNK_READ_HASH_MISMATCH')
            repo.add_prepared_media(media.model_copy(update={'analysis_source_ref': 'rollback-control'}), content)
            conn.rollback()
            if repo.get_analysis_source('rollback-control') is not None:
                raise ValueError('ROLLBACK_CONTROL_FAILED')
        import tempfile
        report = {'phase': 'acceptance', 'samples': []}
        sampler = runner.Sampler(Path('/work'), report, Path('/evidence/acceptance.abort'))
        with tempfile.TemporaryFile(dir='/work') as sentinel:
            sentinel.write(b'x'*4096)
            sentinel.flush()
            if sampler.collect()['including_open_unlinked_bytes'] < 4096:
                raise ValueError('ANONYMOUS_TEMP_MISSING')
            sampler.start()
            try:
                deadline = time.monotonic()+3
                while len(report['samples']) < 3:
                    sampler.check()
                    if time.monotonic() > deadline:
                        raise ValueError('SAMPLER_TIMEOUT')
                    time.sleep(.05)
            finally:
                sampler.close()
        sampler.check()
        if sampler.cgroup_root != bridge.resolve_leaf('/sys/fs/cgroup', Path('/proc/self/cgroup').read_text()):
            raise ValueError('SAMPLER_SCOPE_MISMATCH')
        if runner.temp_usage(Path('/work'))['including_open_unlinked_bytes']:
            raise ValueError('TEMP_CLEANUP_FAILED')
        return {'migration': 'recording_0002', 'chunks': 'PASS', 'metadata': 'PASS_EXACT',
                'rollback': 'PASS', 'sampler_samples': len(report['samples']), 'media': 'NOT_RUN'}
    finally:
        engine.dispose()


def run(connection):
    import recording_real_media_recheck as runner
    from daesingo.recording import LocalAnalysisMaterializer
    import daesingo.recording
    from daesingo.common.db.migrate import validate_environments
    import daesingo.search.media
    import daesingo.search.config
    import daesingo.search.execution
    import psutil
    from recording_probe_budget import ProbeBudget
    budget = ProbeBudget.from_profile(connection.get('resource_profile', 'legacy'))
    if not psutil.Process().is_running() or not validate_environments():
        raise ValueError('DEPENDENCY_IMPORT_OR_MIGRATION_GRAPH_FAILED')
    if any(os.environ.get(k) for k in ('GEMINI_API_KEY', 'ELICE_ML_API_KEY', 'OPENAI_API_KEY',
                                      'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN')):
        raise ValueError('CREDENTIAL_ENV_FORBIDDEN')
    manifest = json.loads(Path('/repo/manifest.json').read_text())
    verify_files('/repo', manifest)
    if Path(daesingo.recording.__file__).resolve() != Path('/repo/src/daesingo/recording/__init__.py'):
        raise ValueError('PRODUCT_IMPORT_MISMATCH')
    if os.getuid() != 10001:
        raise ValueError('UNPRIVILEGED_RUNNER_REQUIRED')
    bridge.require_readonly_cgroup(Path('/proc/self/mountinfo').read_text())
    observed = inventory()
    if json.loads(json.dumps(observed)) != manifest['config']['runtime_identity']:
        raise ValueError('IMAGE_DEPENDENCY_TOOL_MISMATCH')
    root = Path('/sys/fs/cgroup')
    leaves = {'runner': bridge.resolve_leaf(root, Path('/proc/self/cgroup').read_text()),
              'db': bridge.resolve_leaf(root, connection['db_cgroup'])}
    if leaves['runner'] == leaves['db']:
        raise ValueError('DISTINCT_CGROUPS_REQUIRED')
    affinity = set(connection['cpus'])
    if os.sched_getaffinity(0) != affinity:
        raise ValueError('CPU_AFFINITY_MISMATCH')
    initial = {a: bridge.limits(p) for a, p in leaves.items()}
    for actor, quota, memory in (('runner', connection['quota'], budget.runner_hard_mib), ('db', '.5', 512)):
        bridge.require_limits(initial[actor], quota, memory)
    # hierarchy()의 기존 2.5core 가정 대신 관측한 운영 비교 quota만 요구한다.
    original_parent = bridge.require_parent_limits
    bridge.require_parent_limits = lambda parents: parent_gate(parents, connection['quota'], affinity)
    try:
        parents = {a: bridge.hierarchy(p, root) for a, p in leaves.items()}
        parent_memory = {a: ancestor_memory(p, root) for a, p in leaves.items()}
        for value in parent_memory.values():
            parent_memory_gate(value)
            if [v['identity'] for v in value] != connection['preflight_parent_ids']:
                raise ValueError('PREFLIGHT_MEMORY_PARENT_CHANGED')
        memory_samples = []
        def collect():
            values = {a: bridge.limits(p) for a, p in leaves.items()}
            memory_now = {a: ancestor_memory(p, root) for a, p in leaves.items()}
            memory_samples.append({'monotonic': time.monotonic(), 'actors': memory_now})
            for a, value in values.items():
                parent_memory_gate(memory_now[a], parent_memory[a])
                leaf_scope_gate(value, initial[a])
                if (value['memory_current'] >= (budget.runner_soft_mib if a == 'runner' else 440)*1024**2
                        or (value['memory_peak'] or 0) >= (budget.runner_soft_mib if a == 'runner' else 440)*1024**2
                        or value['memory_events'] is None
                        or any(value['memory_events'].get(k, 0) for k in ('oom', 'oom_kill', 'oom_group_kill'))):
                    raise ValueError('CGROUP_MEMORY_STOP')
                bridge.require_same_hierarchy(parents[a], bridge.hierarchy(leaves[a], root))
            return values
        events = []
        observer = bridge.JournalObserver(collect, events, Path('/evidence/cpu-snapshots.private.jsonl'))
        with authenticated_database(connection['db_host'], '/credential.json'), runner.egress_fence(connection['db_host']) as network_counts:
            with bridge.capture_tools(LocalAnalysisMaterializer, observer, Path('/evidence/argv.private.jsonl')):
                if connection['tag'] == 'acceptance':
                    with observer.phase('linux_connection_acceptance'):
                        details = acceptance(connection['db_host'])
                        LocalAnalysisMaterializer({})._run(['ffprobe', '-version'])
                    status = 'PASS_LINUX_ACCEPTANCE'
                else:
                    full = connection['tag'] == 'full'
                    search = full and connection.get('full_probe_mode') == 'coarse_270p_stop_before_send'
                    scope = json.loads(Path('/fixture/manifest.private.json').read_text()).get('full_scope') if full else None
                    args = SimpleNamespace(manifest='/fixture/manifest.private.json', output='/evidence/recording.private.json',
                        db_host=connection['db_host'], schema='probe', code_sha=manifest['product_revision'],
                        image_id=connection['image_id'], first=2 if connection['tag'] == 'smoke' else 1,
                        count=15 if full else (1 if connection['tag'] == 'smoke' else 2),
                        seconds=float(scope['requested_sec']) if full else (10 if connection['tag'] == 'smoke' else 120),
                        experimental_config='/evidence/config.json', recording_only=not search, coarse_270p_crf28=search,
                        full_input=full,
                        explicit_placement_path='/fixture/placements.private.json')
                    if runner.run(args, cpu_observer=observer):
                        raise ValueError('RECORDING_FAILED')
                    details = json.loads(Path(args.output).read_text())
                    runner.require_recording_result(details)
                    if full and details.get('full_input_scope') != 'PASS_ALL_FIFTEEN_EXACT_ENDPOINT':
                        raise ValueError('FULL_SCOPE_RESULT_REQUIRED')
                    if search:
                        if details.get('status') != 'PASS_STOP_BEFORE_SEND' or details.get('sdk_entry_count') != 1:
                            raise ValueError('FULL_OFFLINE_SEARCH_REQUIRED')
                        status = 'PASS_STOP_BEFORE_SEND'
                    else:
                        status = 'PASS_RECORDING_ONLY'
        if not events or any(e['status'] != 'PASS' for e in events):
            raise ValueError('CPU_PHASE_FAILED')
        collect()
        verify_files('/repo', manifest)
        result = {'status': status, 'events': events, 'details': details, 'parents': parents,
                  'initial': initial, 'runtime_identity': observed, 'hooks_restored': True,
                  'parent_memory': parent_memory, 'parent_memory_samples': memory_samples,
                  'provider_calls': 0, 'network_counts': network_counts}
        bridge.write_new('/evidence/cpu.private.json', result)
        print(json.dumps({'status': status, 'phase_count': len(events)}))
        return 0
    finally:
        bridge.require_parent_limits = original_parent


if __name__ == '__main__':
    try:
        raise SystemExit(run(json.loads(Path(sys.argv[1]).read_text())))
    except Exception as error:
        print(json.dumps({'status': 'FAIL_ENTRY', 'error_type': type(error).__name__}))
        raise SystemExit(1)
