"""Linux 호스트 전용 Recording 감독기. 운영 서비스 중단/복귀는 runbook의 별도 수동 단계다."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import sys
import time

from recording_cpu_quota_supervisor import Supervisor, require_inspect, write_new, bounded_capture
from recording_probe_budget import ProbeBudget, MIB
from recording_ec2_package import verify_files, sha

STAGES = ('acceptance', 'smoke', 'representative', 'full')


def stage_settings(config, stage):
    profile = config.get('probe_profile', 'legacy')
    if profile not in ('legacy', 'full15-512m') or stage not in STAGES:
        raise ValueError('EXPLICIT_PROBE_PROFILE_REQUIRED')
    from recording_real_media_recheck import search_preparation_budget
    preparation_ms = search_preparation_budget(config, full=profile == 'full15-512m',
        coarse=config.get('full_probe_mode') == 'coarse_270p_stop_before_send')
    if stage == 'full':
        if profile != 'full15-512m':
            raise ValueError('FULL_PROFILE_REQUIRED')
        return {'profile': profile, 'runner_mib': 3072, 'output_bytes': 512*MIB,
                'duration_ms': 1584174, 'timeout_sec': 3600, 'search_prepare_budget_ms': preparation_ms}
    return {'profile': 'legacy', 'runner_mib': 1280, 'output_bytes': 96*MIB,
            'duration_ms': 240000, 'timeout_sec': 900, 'search_prepare_budget_ms': 150000}

PARENT_MEMORY_COMMAND = r'''
p=/sys/fs/cgroup$(cut -d: -f3 /proc/self/cgroup)
p=${p%/*}
while :; do
  stat -c 'identity %d %i' "$p"
  if [ "$p" = /sys/fs/cgroup ]; then echo 'root 1'; else echo 'root 0'; fi
  for f in memory.max memory.high memory.swap.max memory.current; do
    printf '%s ' "$f"
    if [ -r "$p/$f" ]; then cat "$p/$f"; else echo NONE; fi
  done
  if [ -r "$p/memory.events" ]; then sed 's/^/event_/' "$p/memory.events"; else echo noevents; fi
  echo END
  [ "$p" = /sys/fs/cgroup ] && break
  p=${p%/*}
done
'''


def parse_parent_memory(raw):
    values, value = [], {'events': {}}
    mapping = {'memory.max': 'max', 'memory.high': 'high', 'memory.swap.max': 'swap_max', 'memory.current': 'current'}
    for line in raw.splitlines():
        parts = line.split()
        if parts == ['END']:
            if set(value) != {'events', 'identity', 'root', 'max', 'high', 'swap_max', 'current'}:
                raise ValueError('PARENT_MEMORY_CAPTURE_INCOMPLETE')
            values.append(value)
            value = {'events': {}}
        elif parts == ['noevents']:
            value['events'] = None
        elif parts[0] == 'identity':
            value['identity'] = list(map(int, parts[1:]))
        elif parts[0] == 'root':
            value['root'] = bool(int(parts[1]))
        elif parts[0] in mapping:
            key = mapping[parts[0]]
            value[key] = None if parts[1] == 'NONE' else (int(parts[1]) if key == 'current' else parts[1])
        elif parts[0].startswith('event_'):
            value['events'][parts[0][6:]] = int(parts[1])
        else:
            raise ValueError('PARENT_MEMORY_CAPTURE_INVALID')
    if not values or value != {'events': {}}:
        raise ValueError('PARENT_MEMORY_CAPTURE_INCOMPLETE')
    return values


def local_daemon_gate(endpoint, daemon_name, hostname, environment):
    if (endpoint != 'unix:///var/run/docker.sock' or daemon_name != hostname
            or any(environment.get(k) for k in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'))):
        raise ValueError('LOCAL_LINUX_DAEMON_REQUIRED')


def positive(value):
    if type(value) is not int or value <= 0:
        raise ValueError('POSITIVE_POLICY_RESERVE_REQUIRED')
    return value


def resource_gate(policy, available, free, growth, db_data, *, start=True, budget=None, output_cap=96*MIB):
    budget = budget or ProbeBudget.from_profile('legacy')
    reserve = max(700*MIB, positive(policy['memory_reserve_bytes']))
    disk_reserve = max(4096*MIB, positive(policy['disk_reserve_bytes']))
    required = (budget.runner_hard_mib + budget.db_hard_mib + budget.collector_reserve_mib)*MIB + reserve
    if any(type(n) is not int or n < 0 for n in (available, free, growth, db_data)):
        raise ValueError('RESOURCE_OBSERVATION_INVALID')
    # 중단 기준과 시작 기준을 구분하고 정책 reserve는 줄이지 않는다.
    if available < (required if start else reserve):
        raise ValueError('HOST_MEMORY_BUDGET_STOP')
    if free < disk_reserve or growth >= budget.disk_growth_mib*MIB or db_data >= budget.db_data_mib*MIB:
        raise ValueError('HOST_DISK_BUDGET_STOP')
    if start and (free < disk_reserve+budget.disk_growth_mib*MIB
                  or db_data+3*output_cap >= budget.db_data_mib*MIB):
        raise ValueError('HOST_START_DISK_BUDGET_STOP')
    if start and budget.profile == 'full15-512m':
        needed = budget.requirements(output_cap, 64*MIB)
        if (needed['temp_candidate_bytes'] >= budget.temp_soft_mib*MIB
                or needed['runner_candidate_bytes'] >= budget.runner_soft_mib*MIB
                or growth+needed['disk_growth_candidate_bytes'] > budget.disk_growth_mib*MIB):
            raise ValueError('HOST_COORDINATED_BUDGET_STOP')
    return {'start_required_bytes': required, 'host_reserve_bytes': reserve,
            'disk_reserve_bytes': disk_reserve, 'available_bytes': available, 'free_bytes': free}


def validate_target(owner, policy, names):
    if re.fullmatch(r'rec-ec2-[0-9a-f]{16}', owner) is None:
        raise ValueError('UNIQUE_OWNER_REQUIRED')
    protected = [policy.get(k) for k in ('project', 'mysql_volume', 'media_volume')]
    if any(not isinstance(v, str) or not v for v in protected) or len(set(protected)) != 3:
        raise ValueError('OPERATIONAL_IDENTITY_REQUIRED')
    if any(v == owner or v.startswith(owner+'-') or owner.startswith(v+'-') for v in protected):
        raise ValueError('OPERATIONAL_TARGET_COLLISION')
    if any(n.startswith(owner+'-') or n == owner for n in names):
        raise ValueError('EXPERIMENT_NAME_EXISTS')


def image_reference(value, *, local=False):
    registry = re.fullmatch(r'[a-z0-9][a-z0-9.:/_-]*@sha256:[0-9a-f]{64}', value or '')
    local_id = re.fullmatch(r'sha256:[0-9a-f]{64}', value or '')
    if not registry and not (local and local_id):
        raise ValueError('REGISTRY_DIGEST_REQUIRED')
    return value


def previous_stage(root, stage):
    if stage not in STAGES:
        raise ValueError('STAGE_NOT_ALLOWED')
    if stage != 'acceptance':
        path = Path(root)/(STAGES[STAGES.index(stage)-1]+'-result.private.json')
        if not path.is_file():
            raise ValueError('PREVIOUS_STAGE_REQUIRED')
        value = json.loads(path.read_text())
        if value.get('status') != 'PASS' or value.get('cleanup') is not True:
            raise ValueError('PREVIOUS_STAGE_FAILED_OR_UNCLEAN')


def new_credential(path):
    path = Path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump({'username': 'root', 'password': secrets.token_hex(32)}, stream)
    if os.name == 'posix':
        os.chmod(path, 0o400)


def runner_json(path, value):
    write_new(path, value)
    # stage 디렉터리는 uid10001/0700. 파일에는 secret 값이 없다.
    Path(path).chmod(0o444)


def input_gate(directory, manifest, *, full=False):
    directory = Path(directory).resolve(strict=True)
    records = manifest['files']
    ids = [f'input-{n:02}' for n in range(1, 16)] if full else ['input-01', 'input-02']
    if [r['fixture_id'] for r in records] != ids:
        raise ValueError('EXACT_EXPLICIT_INPUTS_REQUIRED')
    if full:
        from recording_full_input import require_full_scope
        scope = manifest['full_scope']
        require_full_scope(scope['placements'], scope['requested_sec'])
        if scope['total_bytes'] != sum(r['bytes'] for r in records) or scope['max_duration_ms'] != 1584174:
            raise ValueError('FULL_INPUT_SCOPE_MISMATCH')
    expected = {n+'.mp4' for n in ids}
    if {p.name for p in directory.iterdir()} != expected:
        raise ValueError('ONLY_MINIMAL_INPUT_FILES_ALLOWED')
    for r in records:
        path = directory/r['filename']
        if r['filename'] != r['fixture_id']+'.mp4' or path.is_symlink() or not path.is_file():
            raise ValueError('EXACT_INPUT_FILE_REQUIRED')
        before = path.stat()
        if (before.st_size != r['bytes'] or before.st_mtime_ns != r['mtime_ns']
                or r['proposed_video_index'] != 0):
            raise ValueError('INPUT_STAT_OR_STREAM_MISMATCH')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != r['sha256']:
                raise ValueError('INPUT_HASH_MISMATCH')
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ValueError('INPUT_CHANGED_DURING_VERIFICATION')


def fixture_gate(directory, expected):
    names = {'manifest.private.json', 'placements.private.json'}
    if (not isinstance(expected, dict) or set(expected) != names
            or any(not re.fullmatch(r'[0-9a-f]{64}', value) for value in expected.values())):
        raise ValueError('APPROVED_INPUT_IDENTITY_REQUIRED')
    directory = Path(directory)
    if {p.name for p in directory.iterdir()} != names:
        raise ValueError('ONLY_APPROVED_FIXTURE_FILES_ALLOWED')
    for name in names:
        path = directory/name
        if path.is_symlink() or not path.is_file() or sha(path.read_bytes()) != expected[name]:
            raise ValueError('APPROVED_FIXTURE_IDENTITY_MISMATCH')


def memory_available():
    values = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    return int(values['MemAvailable'].split()[0])*1024


def separate_paths(operational, candidate):
    operational, candidate = Path(operational).resolve(), Path(candidate).resolve()
    if candidate.is_relative_to(operational) or operational.is_relative_to(candidate):
        raise ValueError('OPERATIONAL_PATH_OVERLAP')


def disk_growth(origin, current):
    if origin.keys() != current.keys():
        raise ValueError('DISK_FILESYSTEM_SCOPE_CHANGED')
    return sum(max(0, origin[k]-current[k]) for k in origin)


def protected_file(path):
    path = Path(path)
    s = path.lstat()
    if path.is_symlink() or not path.is_file() or s.st_uid != 0 or s.st_mode & 0o077:
        raise ValueError('ROOT_PRIVATE_FILE_REQUIRED')
    return path


def approval_gate(value, owner, snapshot_sha256, *, now=None):
    now = time.time() if now is None else now
    if (value.get('owner') != owner or value.get('snapshot_sha256') != snapshot_sha256
            or not isinstance(value.get('recovery_owner'), str) or not value['recovery_owner']
            or type(value.get('not_after_unix')) is not int or value['not_after_unix'] <= now
            or any(value.get(k) is not True for k in
                   ('ingress_controlled', 'writers_paused', 'jobs_zero', 'deployments_paused', 'backups_paused'))):
        raise ValueError('LIVE_MAINTENANCE_APPROVAL_REQUIRED')


def operational_gate(snapshot, original, expected_identity, *, restored=False):
    if (not expected_identity or snapshot['identity'] != expected_identity or original['identity'] != expected_identity
            or snapshot['files'] != original['files'] or snapshot['pointer'] != original['pointer']
            or snapshot['services'].keys() != original['services'].keys()):
        raise ValueError('OPERATIONAL_IDENTITY_OR_FILES_CHANGED')
    for service, state in snapshot['services'].items():
        prior = original['services'][service]
        running_valid = (not state['running'] or prior['running']) if restored is None else (
            state['running'] == (prior['running'] if restored else False))
        if (any(state[k] != prior[k] for k in ('id', 'image', 'mounts', 'host_config', 'networks'))
                or not running_valid):
            raise ValueError('OPERATIONAL_SERVICE_STATE_CHANGED')


def operational_snapshot(root, capture):
    """값/credential은 출력하지 않고 정확한 서비스 ID와 보호 파일 hash만 보존한다."""
    root = Path(root).resolve(strict=True)
    policy = json.loads(protected_file(root/'policy.json').read_text())
    if (root/'dirty.json').exists():
        raise ValueError('DIRTY_DEPLOYMENT_STOP')
    records = {}
    for name in ('current.json', 'previous.json', 'schema.json', 'policy.json', 'release-compose.json'):
        path = root/name
        if not path.is_file() or path.is_symlink():
            raise ValueError('OPERATIONAL_RECORD_REQUIRED')
        records[name] = sha(path.read_bytes())
    for directory in ('configs', 'approvals'):
        if not (root/directory).is_dir():
            raise ValueError('OPERATIONAL_DIRECTORY_REQUIRED')
        for path in sorted((root/directory).rglob('*')):
            if path.is_symlink():
                raise ValueError('OPERATIONAL_SYMLINK_UNKNOWN')
            if path.is_file():
                records[path.relative_to(root).as_posix()] = sha(path.read_bytes())
    pointer = root/'releases/current'
    if not pointer.is_symlink():
        raise ValueError('WEB_POINTER_REQUIRED')
    ids = capture('ps', '-aq', '--filter', 'label=com.docker.compose.project='+policy['project']).stdout.decode().split()
    services = {}
    for identity in ids:
        info = json.loads(capture('inspect', identity).stdout)[0]
        labels = info['Config'].get('Labels', {})
        service = labels.get('com.docker.compose.service')
        if service not in ('api', 'worker', 'mysql', 'migrate') or service in services:
            raise ValueError('OPERATIONAL_SERVICE_AMBIGUOUS')
        services[service] = {'id': info['Id'], 'image': info['Image'], 'running': info['State']['Running'],
            'started_at': info['State']['StartedAt'], 'mounts': info['Mounts'], 'host_config': info['HostConfig'],
            'networks': list(info['NetworkSettings']['Networks'])}
    if not {'api', 'worker', 'mysql'} <= services.keys():
        raise ValueError('OPERATIONAL_SERVICE_MISSING')
    current = json.loads((root/'current.json').read_text())
    previous = json.loads((root/'previous.json').read_text())
    schema = json.loads((root/'schema.json').read_text())
    identity = {name: {k: value[k] for k in ('revision', 'config_id')} for name, value in
                (('current', current), ('previous', previous))}
    identity['schema_revision'] = schema['revision']
    if (schema.get('phase', 'migration_complete') != 'migration_complete'
            or os.readlink(pointer) != current['revision']+'/web'):
        raise ValueError('SCHEMA_OR_POINTER_AMBIGUOUS')
    # 운영 volume·network가 실험의 보호 대상임을 snapshot에서 확정한다.
    mysql_mounts = {m['Name'] for m in services['mysql']['mounts'] if m['Type'] == 'volume'}
    if policy['mysql_volume'] not in mysql_mounts:
        raise ValueError('OPERATIONAL_MYSQL_VOLUME_MISMATCH')
    return policy, {'files': records, 'pointer': os.readlink(pointer), 'services': services, 'identity': identity}


class LinuxSupervisor(Supervisor):
    def __init__(self, source, evidence, owner, policy, config, *, local=False):
        # Windows constructor를 호출하지 않는다. Docker transport·소유 정리만 상속한다.
        self.source, self.root = Path(source).resolve(), Path(evidence).resolve()
        self.owner, self.policy, self.config = owner, policy, config
        self.created, self.stage_name, self.cleanup_deadline = [], None, None
        self.settings = stage_settings(config, 'acceptance')
        self.budget = replace(ProbeBudget.from_profile('legacy'),
                              host_reserve_mib=(max(700*MIB, policy['memory_reserve_bytes'])+MIB-1)//MIB)
        self.runner_image = image_reference(config['runner_image'], local=local)
        self.mysql_image = image_reference(config['mysql_image'], local=local)
        if config.get('local_validation_only') and not local:
            raise ValueError('LOCAL_PACKAGE_FORBIDDEN_ON_EC2')
        if not local:
            expected = config.get('input_identity')
            if (not isinstance(expected, dict) or set(expected) != {'manifest.private.json', 'placements.private.json'}
                    or any(not re.fullmatch(r'[0-9a-f]{64}', value) for value in expected.values())):
                raise ValueError('APPROVED_INPUT_IDENTITY_REQUIRED')
        quota = Fraction(config['runner_quota'])
        cpus = config['cpus']
        if not (0 < quota <= 2 and isinstance(cpus, list) and cpus
                and all(type(n) is int and n >= 0 for n in cpus) and len(set(cpus)) == len(cpus)
                and quota <= len(cpus) and Fraction(config['db_quota']) == Fraction(1, 2)):
            raise ValueError('OBSERVED_CPU_CONFIGURATION_REQUIRED')
        self.quota, self.cpuset = str(quota.numerator/quota.denominator), ','.join(map(str, cpus))

    def host(self, *, start=False, db_data=0):
        if getattr(self, 'operational_guard', None):
            self.operational_guard()
        runner = self.names(self.stage_name)['runner'] if self.stage_name else None
        if ('container', runner) in self.created:
            require_inspect(self.inspect('container', runner), self.owner, self.quota, self.settings['runner_mib'], self.cpuset)
        if self.stage_name and (self.root/self.stage_name/'recording.private.abort').exists():
            raise ValueError('RUNNER_SOFT_RESOURCE_STOP')
        disks = {}
        for path in (self.root, self.source, self.config['docker_root'], *self.config.get('additional_disk_paths', [])):
            key = str(Path(path).stat().st_dev)
            observed_free = shutil.disk_usage(path).free
            disks[key] = min(disks.get(key, observed_free), observed_free)
        free = min(disks.values())
        now = {'utc': datetime.now(timezone.utc).isoformat(), 'monotonic': time.monotonic(),
               'available_ram_bytes': memory_available(), 'disk_free_bytes': free, 'disks': disks,
               'loadavg': Path('/proc/loadavg').read_text().split()[:3],
               'pressure': {n: Path('/proc/pressure', n).read_text() for n in ('cpu', 'memory', 'io')},
               'proc_stat': Path('/proc/stat').read_text().splitlines()[0]}
        origin = self.root/'resource-origin.private.json'
        if not origin.exists():
            write_new(origin, now)
        growth = disk_growth(json.loads(origin.read_text())['disks'], disks)
        self.log('host.private.jsonl', {**now, 'growth_bytes': growth, 'stage': self.stage_name})
        return resource_gate(self.policy, now['available_ram_bytes'], free, growth, db_data, start=start,
                             budget=self.budget, output_cap=self.settings['output_bytes'])

    def db_metrics(self, name):
        result = super().db_metrics(name)
        from recording_ec2_entry import parent_memory_gate
        parents = parse_parent_memory(self.docker('exec', name, 'sh', '-ec', PARENT_MEMORY_COMMAND, timeout=8).stdout.decode())
        parent_memory_gate(parents, self.parent_memory_expected)
        self.log('parent-memory.private.jsonl', {'monotonic': time.monotonic(), 'stage': self.stage_name, 'parents': parents})
        return result

    def ensure_image(self, ref):
        info = json.loads(self.docker('image', 'inspect', ref).stdout)[0]
        if (info['Os'] != 'linux' or info['Architecture'] != 'amd64'
                or ('@' in ref and ref not in info.get('RepoDigests', []))):
            raise ValueError('ACTUAL_IMAGE_DIGEST_OR_PLATFORM_MISMATCH')
        return info['Id']

    def readonly_mount(self, source, target):
        return ['--mount', f'type=bind,source={source},target={target},readonly']

    def stage(self, tag, fixture=None, inputs=None):
        if tag not in STAGES:
            raise ValueError('STAGE_NOT_ALLOWED')
        self.settings = stage_settings(self.config, tag)
        self.budget = replace(ProbeBudget.from_profile(self.settings['profile']),
                              host_reserve_mib=(max(700*MIB, self.policy['memory_reserve_bytes'])+MIB-1)//MIB)
        if self.config.get('full_probe_mode', 'recording_only') not in ('recording_only', 'coarse_270p_stop_before_send'):
            raise ValueError('FULL_OFFLINE_MODE_REQUIRED')
        self.stage_name = tag
        previous_stage(self.root, tag)
        attempt = self.root/(tag+'-stage.private.json')
        write_new(attempt, {'status': 'STARTED'})  # 재시도/덮어쓰기 금지
        manifest = json.loads((self.source/'manifest.json').read_text())
        verify_files(self.source, manifest)
        self.host(start=True)
        runner_id, mysql_id = self.ensure_image(self.runner_image), self.ensure_image(self.mysql_image)
        names = self.names(tag)
        # 생성 전마다 exact 부재·owner를 기존 create()에서 다시 검사한다.
        self.create('network', names['network'], ['network', 'create', '--internal', '--label', 'owner='+self.owner, names['network']])
        for kind in ('data', 'work'):
            self.create('volume', names[kind], ['volume', 'create', '--label', 'owner='+self.owner, names[kind]])
        directory = self.root/tag
        directory.mkdir(mode=0o700)
        os.chown(directory, 10001, 10001)
        credential = self.root/(tag+'-credential.private.json')
        new_credential(credential)
        value = json.loads(credential.read_text())
        password_file = self.root/(tag+'-mysql-password.private')
        with password_file.open('x') as stream:
            stream.write(value['password'])
        password_file.chmod(0o400)
        os.chown(credential, 10001, 10001)
        self.create('container', names['init'], ['create', '--name', names['init'], '--label', 'owner='+self.owner,
            '--network', 'none', '--cgroupns', 'host', '--cpus', '.5', '--memory', '128m', '--memory-swap', '128m', '--pids-limit', '32',
            '--read-only', '--pull=never', '--user', '0:0', '--mount', f'type=volume,source={names["work"]},target=/work',
            *self.readonly_mount(self.source, '/repo'), '-e', 'PYTHONDONTWRITEBYTECODE=1',
            '-e', 'PYTHONPATH=/repo/src:/repo/scripts', '--entrypoint', 'python', self.runner_image, '-B', '-c',
            "import os,json;from pathlib import Path;from recording_cpu_quota_linux import resolve_leaf,require_readonly_cgroup;"
            "from recording_ec2_entry import ancestor_memory,parent_memory_gate;"
            "require_readonly_cgroup(Path('/proc/self/mountinfo').read_text());r=Path('/sys/fs/cgroup');"
            "v=ancestor_memory(resolve_leaf(r,Path('/proc/self/cgroup').read_text()),r);parent_memory_gate(v);"
            "print(json.dumps(v));os.chown('/work',10001,10001);os.chmod('/work',0o700)"])
        self.docker('start', names['init'])
        self.wait(names['init'], time.monotonic()+30)
        parent_memory = json.loads(self.docker('logs', names['init']).stdout)
        self.parent_memory_expected = parent_memory
        write_new(directory/'parent-memory-preflight.private.json', parent_memory)
        self.docker('rm', names['init'])
        self.created.remove(('container', names['init']))
        self.create('container', names['db'], ['create', '--name', names['db'], '--label', 'owner='+self.owner,
            '--network', names['network'], '--cgroupns', 'host', '--cpus', '.5', '--memory', '512m', '--memory-swap', '512m',
            '--pids-limit', '128', '--pull=never', '--restart', 'no', '--log-driver', 'local', '--log-opt', 'max-size=1m',
            '--log-opt', 'max-file=2', '-e', 'MYSQL_ROOT_PASSWORD_FILE=/run/password', '-e', 'MYSQL_ROOT_HOST=%',
            '-e', 'MYSQL_DATABASE=probe', *self.readonly_mount(password_file, '/run/password'),
            '--mount', f'type=volume,source={names["data"]},target=/var/lib/mysql', self.mysql_image,
            '--max-allowed-packet=67108864', '--innodb-buffer-pool-size=33554432', '--innodb-redo-log-capacity=16777216',
            '--max-connections=12', '--performance-schema=OFF', '--skip-log-bin', '--general-log=OFF', '--slow-query-log=OFF'])
        # mysql CLI 보호 defaults 파일: credential을 argv/env 값에 넣지 않는다.
        defaults = self.root/(tag+'-mysql-client.private.cnf')
        with defaults.open('x') as stream:
            stream.write('[client]\nuser=root\npassword='+value['password']+'\nhost=127.0.0.1\nprotocol=TCP\n')
        defaults.chmod(0o400)
        self.docker('start', names['db'])
        self.docker('cp', str(defaults), names['db']+':/tmp/probe-client.cnf')
        deadline = time.monotonic()+120
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError('DB_READINESS_TIMEOUT')
            self.host()
            self.db_metrics(names['db'])
            ready = self.docker('exec', names['db'], 'mysql', '--defaults-extra-file=/tmp/probe-client.cnf', '-N', '-B',
                                '-e', 'SELECT @@session.max_allowed_packet', check=False, timeout=8)
            if ready.returncode == 0 and ready.stdout.strip() == b'67108864':
                break
            time.sleep(1)
        before = self.db_metrics(names['db'])
        self.host(start=True, db_data=before['db_data_bytes'])
        db = self.owned('container', names['db'])
        if db['Image'] != mysql_id or db['HostConfig']['PortBindings']:
            raise ValueError('DB_IMAGE_OR_EXPOSURE_MISMATCH')
        network = self.owned('network', names['network'])
        if not network['Internal']:
            raise ValueError('INTERNAL_NETWORK_REQUIRED')
        ip = db['NetworkSettings']['Networks'][names['network']]['IPAddress']
        cg = self.docker('exec', names['db'], 'cat', '/proc/self/cgroup', timeout=8).stdout.decode()
        runner_json(directory/'connection.private.json', {'tag': tag, 'quota': self.quota, 'cpus': self.config['cpus'],
                    'db_host': ip, 'db_cgroup': cg, 'image_id': runner_id,
                    'resource_profile': self.settings['profile'],
                    'full_probe_mode': self.config.get('full_probe_mode', 'recording_only'),
                    'search_prepare_budget_ms': self.settings['search_prepare_budget_ms'],
                    'preflight_parent_ids': [p['identity'] for p in parent_memory]})
        runner_json(directory/'config.json', {'experiment_id': self.owner, 'max_output_bytes': self.settings['output_bytes'],
                    'max_duration_ms': self.settings['duration_ms'], 'run_timeout_sec': self.settings['timeout_sec'],
                    'resource_profile': self.settings['profile']})
        mounts = [*self.readonly_mount(self.source, '/repo'), *self.readonly_mount(credential, '/credential.json'),
                  '--mount', f'type=bind,source={directory},target=/evidence',
                  '--mount', f'type=volume,source={names["work"]},target=/work']
        if tag != 'acceptance':
            if not fixture or not inputs:
                raise ValueError('MINIMAL_INPUT_FIXTURE_REQUIRED')
            mounts += self.readonly_mount(Path(fixture).resolve(), '/fixture')
            mounts += self.readonly_mount(Path(inputs).resolve(), '/inputs')
        self.create('container', names['runner'], ['create', '--name', names['runner'], '--label', 'owner='+self.owner,
            '--network', names['network'], '--cgroupns', 'host', '--cpus', self.quota, '--cpuset-cpus', self.cpuset,
            '--memory', str(self.settings['runner_mib'])+'m', '--memory-swap', str(self.settings['runner_mib'])+'m',
            '--pids-limit', '128', '--read-only', '--pull=never',
            '--restart', 'no', '--user', '10001:10001', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--log-driver', 'local', '--log-opt', 'max-size=1m', '--log-opt', 'max-file=2',
            '--tmpfs', '/tmp:rw,size=100663296,mode=1777', '--workdir', '/repo',
            '-e', 'REAL_MEDIA_RECHECK_ISOLATED=owned-internal-20261103', '-e', 'PYTHONDONTWRITEBYTECODE=1',
            '-e', 'PYTHONPATH=/repo/src:/repo/scripts', '-e', 'TMPDIR=/work', *mounts,
            '--entrypoint', 'python', self.runner_image, '-B', '/repo/scripts/recording_ec2_entry.py', '/evidence/connection.private.json'])
        actual = self.owned('container', names['runner'])
        require_inspect(actual, self.owner, self.quota, self.settings['runner_mib'], self.cpuset)
        if (actual['Image'] != runner_id or actual['HostConfig']['PortBindings']
                or not actual['HostConfig']['ReadonlyRootfs'] or actual['HostConfig']['CgroupnsMode'] != 'host'
                or any(m['RW'] for m in actual['Mounts'] if m['Destination'] in ('/repo', '/inputs', '/fixture', '/credential.json'))):
            raise ValueError('RUNNER_ISOLATION_MISMATCH')
        write_new(directory/'actual.private.json', {'runner': actual['HostConfig'], 'db': db['HostConfig'],
                    'runner_image_id': runner_id, 'mysql_image_id': mysql_id, 'manifest_sha256': sha((self.source/'manifest.json').read_bytes())})
        self.docker('start', names['runner'])
        self.wait(names['runner'], time.monotonic()+(180 if tag == 'acceptance' else self.budget.host_timeout_sec(
            self.settings['timeout_sec'])), db=names['db'])
        result = json.loads((directory/'cpu.private.json').read_text())
        expected_status = 'PASS_LINUX_ACCEPTANCE' if tag == 'acceptance' else 'PASS_RECORDING_ONLY'
        if tag == 'full' and self.config.get('full_probe_mode') == 'coarse_270p_stop_before_send':
            expected_status = 'PASS_STOP_BEFORE_SEND'
        if result['status'] != expected_status or not result['hooks_restored']:
            raise ValueError('ENTRY_ACCEPTANCE_FAILED')
        if tag != 'acceptance':
            r = result['details']
            if (r['cleanup_errors'] or r['sampler_error'] or r['temp_after']['including_open_unlinked_bytes']
                    or r['live_children_after'] or r['aborted_before'] != r['aborted_after'] or r['provider_calls']):
                raise ValueError('RECORDING_CLEANUP_OR_CORRECTNESS_FAILED')
        self.db_metrics(names['db'])
        verify_files(self.source, manifest)
        if tag != 'acceptance':
            fixture_gate(fixture, self.config['input_identity'])
            input_gate(inputs, json.loads((Path(fixture)/'manifest.private.json').read_text()),
                       full=self.config.get('probe_profile') == 'full15-512m')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--owner', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--stage', choices=STAGES, required=True)
    parser.add_argument('--ops-root', default='/opt/daesingo')
    parser.add_argument('--local-validation', action='store_true')
    parser.add_argument('--policy-fixture')
    parser.add_argument('--fixture')
    parser.add_argument('--inputs')
    args = parser.parse_args()
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise ValueError('LINUX_ROOT_SUPERVISOR_REQUIRED')
    os.umask(0o077)
    root = Path(args.evidence).resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.stat().st_uid != 0 or root.stat().st_mode & 0o077:
        raise ValueError('PROTECTED_EVIDENCE_ROOT_REQUIRED')
    manifest_data = (Path(args.source)/'manifest.json').read_bytes()
    if sha(manifest_data) != args.manifest_sha256:
        raise ValueError('REVIEWED_MANIFEST_IDENTITY_REQUIRED')
    manifest = json.loads(manifest_data)
    config = manifest['config']
    stage_settings(config, args.stage)
    if args.stage != 'acceptance':
        if not args.fixture or not args.inputs:
            raise ValueError('MINIMAL_INPUT_FIXTURE_REQUIRED')
        fixture_gate(args.fixture, config.get('input_identity'))
        input_gate(args.inputs, json.loads((Path(args.fixture)/'manifest.private.json').read_text()),
                   full=config.get('probe_profile') == 'full15-512m')
    def capture(*argv):
        return bounded_capture(['docker', *argv], 15, root)
    lock = None
    if args.local_validation:
        if args.stage != 'acceptance' or not args.policy_fixture:
            raise ValueError('LOCAL_NO_MEDIA_ACCEPTANCE_ONLY')
        policy = json.loads(Path(args.policy_fixture).read_text())
        if capture('ps', '-aq').stdout.strip():
            raise ValueError('LOCAL_OTHER_CONTAINER_PRESENT')
    else:
        if args.policy_fixture:
            raise ValueError('POLICY_FIXTURE_FORBIDDEN_ON_EC2')
        contexts = json.loads(capture('context', 'inspect').stdout)
        daemon_name = capture('info', '--format', '{{.Name}}').stdout.decode().strip()
        if len(contexts) != 1:
            raise ValueError('LOCAL_DOCKER_CONTEXT_AMBIGUOUS')
        local_daemon_gate(contexts[0]['Endpoints']['docker']['Host'], daemon_name, socket.gethostname(), os.environ)
        ops_root = Path(args.ops_root).resolve(strict=True)
        for candidate in (root, args.source, args.inputs, args.fixture):
            if candidate:
                separate_paths(ops_root, candidate)
        if config.get('additional_disk_paths'):
            raise ValueError('LOCAL_DISK_MAPPING_FORBIDDEN_ON_EC2')
        lock = ops_root/'operation.lock'
        # 운영 lock은 runbook의 유지 shell이 보유한다. 이 도구는 탈취/삭제하지 않는다.
        marker = protected_file(lock/'recording-probe-owner.private.json')
        if json.loads(marker.read_text()) != {'owner': args.owner, 'evidence': str(root)}:
            raise ValueError('EXACT_MAINTENANCE_LOCK_REQUIRED')
        policy, snapshot = operational_snapshot(ops_root, capture)
        original = json.loads(protected_file(root/'operational-snapshot.private.json').read_text())
        operational_gate(snapshot, original, config.get('operational_identity'))
        snapshot_sha256 = sha((root/'operational-snapshot.private.json').read_bytes())
        approval_gate(json.loads(protected_file(root/'maintenance-approved.private.json').read_text()),
                      args.owner, snapshot_sha256)
    actual_root = capture('info', '--format', '{{.DockerRootDir}}').stdout.decode().strip()
    if actual_root != config['docker_root'] or not Path(actual_root).is_dir():
        raise ValueError('ACTUAL_DOCKER_DISK_REQUIRED')
    names = []
    for command in (('ps', '-a', '--format', '{{.Names}}'), ('volume', 'ls', '--format', '{{.Name}}'),
                    ('network', 'ls', '--format', '{{.Name}}')):
        names += capture(*command).stdout.decode().splitlines()
    validate_target(args.owner, policy, names)
    supervisor = LinuxSupervisor(args.source, root, args.owner, policy, config, local=args.local_validation)
    if not args.local_validation:
        def guard():
            if json.loads(protected_file(lock/'recording-probe-owner.private.json').read_text()) != {'owner': args.owner, 'evidence': str(root)}:
                raise ValueError('MAINTENANCE_LOCK_CHANGED')
            _, current_snapshot = operational_snapshot(ops_root, supervisor.docker)
            operational_gate(current_snapshot, original, config['operational_identity'])
            approval_gate(json.loads(protected_file(root/'maintenance-approved.private.json').read_text()),
                          args.owner, snapshot_sha256)
        supervisor.operational_guard = guard
    identity = {'owner': args.owner, 'manifest_sha256': sha((Path(args.source)/'manifest.json').read_bytes())}
    frozen = root/'identity.private.json'
    if frozen.exists():
        if json.loads(frozen.read_text()) != identity:
            raise ValueError('FROZEN_IDENTITY_MISMATCH')
    else:
        write_new(frozen, identity)
    marker = root/(args.stage+'-result.private.json')
    if marker.exists():
        raise ValueError('ATTEMPT_CLOSED_NEW_OWNER_REQUIRED')
    result = {'status': 'FAIL', 'stage': args.stage, 'cleanup': False}
    try:
        supervisor.stage(args.stage, args.fixture, args.inputs)
        result['status'] = 'PASS'
    except BaseException as error:
        result['error_type'] = type(error).__name__
    finally:
        try:
            supervisor.cleanup(args.stage)
            result['cleanup'] = True
        except BaseException as error:
            result.update(status='FAIL', cleanup_error_type=type(error).__name__)
        write_new(marker, result)
    print(json.dumps(result))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'status': 'FAIL_CLOSED', 'error_type': type(error).__name__}))
        raise SystemExit(1)
