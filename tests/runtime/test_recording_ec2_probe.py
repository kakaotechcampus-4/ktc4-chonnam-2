"""패키지 탈출·변조·운영 혼입·예산 부족·단계 건너뛰기를 거부하는 controls."""
import importlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / 'scripts'))


def module(name):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        pytest.fail('요청한 Linux 실행 모듈이 아직 없습니다')


def test_archive_member_allowlist_rejects_private_and_escape():
    m = module('recording_ec2_package')
    for name in ('src/daesingo/recording/service.py', 'migrations/recording/env.py', 'uv.lock'):
        assert m.allowed(name)
    for name in ('../src/x.py', '/src/x.py', 'src/../.env', 'src/a/.env', '.git/config',
                 '.env', '.codex-scratch/private.json', 'data/original.mp4', 'src/a/__pycache__/a.pyc',
                 'src/a/password.txt', 'scripts/unknown.py'):
        assert not m.allowed(name)


def test_directory_verification_detects_tamper_extra_and_symlink(tmp_path):
    m = module('recording_ec2_package')
    p = tmp_path / 'uv.lock'
    p.write_bytes(b'fixed')
    manifest = {'files': {'uv.lock': m.sha(p.read_bytes())}}
    m.verify_files(tmp_path, manifest)
    p.write_bytes(b'changed')
    with pytest.raises(ValueError):
        m.verify_files(tmp_path, manifest)
    p.write_bytes(b'fixed')
    (tmp_path / '.env').write_text('private')
    with pytest.raises(ValueError):
        m.verify_files(tmp_path, manifest)


def test_finite_budget_preserves_policy_and_charges_collector():
    m = module('recording_ec2_host')
    policy = {'memory_reserve_bytes': 900*1024**2, 'disk_reserve_bytes': 5*1024**3}
    with pytest.raises(ValueError):
        m.resource_gate(policy, 1600*1024**2, 38*1024**3, 0, 0)
    result = m.resource_gate(policy, 4000*1024**2, 38*1024**3, 0, 0)
    assert result['start_required_bytes'] == 3204*1024**2
    with pytest.raises(ValueError):
        m.resource_gate(policy, 4000*1024**2, 5*1024**3, 0, 0)
    for invalid in (0, None, True, -1):
        with pytest.raises(ValueError):
            m.resource_gate({**policy, 'memory_reserve_bytes': invalid}, 9*1024**3, 38*1024**3, 0, 0)


def test_target_rejects_operational_names_and_local_image_on_ec2():
    m = module('recording_ec2_host')
    policy = {'project': 'daesingo-runtime', 'mysql_volume': 'prod-db', 'media_volume': 'prod-media'}
    m.validate_target('rec-ec2-0123456789abcdef', policy, [])
    for owner in ('daesingo-runtime', 'rec-ec2-../prod', 'rec-ec2-prod', ''):
        with pytest.raises(ValueError):
            m.validate_target(owner, policy, [])
    with pytest.raises(ValueError):
        m.validate_target('rec-ec2-0123456789abcdef', policy, ['rec-ec2-0123456789abcdef-smoke-db'])
    with pytest.raises(ValueError):
        m.image_reference('sha256:'+'a'*64, local=False)
    assert m.image_reference('registry.example/repo@sha256:'+'a'*64, local=False)


def test_stage_gate_fails_closed_on_failed_or_unclean_predecessor(tmp_path):
    m = module('recording_ec2_host')
    with pytest.raises(ValueError):
        m.previous_stage(tmp_path, 'smoke')
    (tmp_path/'acceptance-result.private.json').write_text(json.dumps({'status': 'PASS', 'cleanup': False}))
    with pytest.raises(ValueError):
        m.previous_stage(tmp_path, 'smoke')
    (tmp_path/'acceptance-result.private.json').write_text(json.dumps({'status': 'PASS', 'cleanup': True}))
    m.previous_stage(tmp_path, 'smoke')
    with pytest.raises(ValueError):
        m.previous_stage(tmp_path, 'A1')


def test_credentials_are_protected_and_never_put_in_argv(tmp_path):
    m = module('recording_ec2_host')
    path = tmp_path / 'credential.private.json'
    m.new_credential(path)
    value = json.loads(path.read_text())
    assert value['username'] == 'root' and len(value['password']) == 64
    with pytest.raises(FileExistsError):
        m.new_credential(path)


def test_explicit_placement_identity_rejects_reordering_and_wrong_stream():
    m = module('recording_ec2_entry')
    expected = [{'id': 'input-01', 'start': 0.0, 'end': 117.933333, 'video_index': 0},
                {'id': 'input-02', 'start': 117.933333, 'end': 206.5, 'video_index': 0}]
    m.placement_gate(expected, expected, 'representative')
    for actual in (list(reversed(expected)), [{**expected[0], 'video_index': 1}, expected[1]],
                   [{**expected[0], 'end': 118}, expected[1]]):
        with pytest.raises(ValueError):
            m.placement_gate(expected, actual, 'representative')


def test_parent_limits_do_not_copy_local_two_point_five_core_assumption():
    m = module('recording_ec2_entry')
    m.parent_gate([{'cpu_max': '200000 100000', 'cpuset': '0-1'}], '2', {0, 1})
    for parents in ([{'cpu_max': '150000 100000', 'cpuset': '0-1'}],
                    [{'cpu_max': 'max 100000', 'cpuset': '1'}]):
        with pytest.raises(ValueError):
            m.parent_gate(parents, '2', {0, 1})


def test_synthetic_acceptance_content_uses_container_signature_without_media():
    from io import BytesIO
    from daesingo.recording.chunked_media import check_mp4
    m = module('recording_ec2_entry')
    content = m.synthetic_content()
    check_mp4(BytesIO(content), len(content))
    assert 524288 < len(content) < 1048576


def test_paths_cannot_mount_or_write_operational_state(tmp_path):
    m = module('recording_ec2_host')
    ops = tmp_path/'ops'
    ops.mkdir()
    for child in (ops, ops/'configs', tmp_path):
        with pytest.raises(ValueError):
            m.separate_paths(ops, child)
    m.separate_paths(ops, tmp_path/'experiment')


def test_runner_connection_files_are_readable_without_host_root(tmp_path):
    import stat
    m = module('recording_ec2_host')
    path = tmp_path/'connection.private.json'
    m.runner_json(path, {'db_host': '192.0.2.2'})
    assert json.loads(path.read_text()) == {'db_host': '192.0.2.2'}
    assert path.stat().st_mode & stat.S_IROTH


def test_minimal_inputs_reject_extra_file_and_symlink(tmp_path):
    import hashlib
    m = module('recording_ec2_host')
    records = []
    for n in ('01', '02'):
        path = tmp_path/('input-'+n+'.mp4')
        path.write_bytes(b'content')
        records.append({'fixture_id': 'input-'+n, 'filename': path.name, 'bytes': 7,
                        'sha256': hashlib.sha256(b'content').hexdigest(), 'mtime_ns': path.stat().st_mtime_ns,
                        'proposed_video_index': 0})
    m.input_gate(tmp_path, {'files': records})
    (tmp_path/'runtime.env').write_bytes(b'private')
    with pytest.raises(ValueError):
        m.input_gate(tmp_path, {'files': records})


def test_operational_gate_rejects_identity_and_mount_changes():
    from copy import deepcopy
    m = module('recording_ec2_host')
    identity = {'current': {'revision': 'a'*40, 'config_id': 'current'},
                'previous': {'revision': 'a'*40, 'config_id': 'previous'}, 'schema_revision': 'a'*40}
    original = {'files': {'current.json': 'hash'}, 'pointer': 'a'*40+'/web', 'identity': identity,
                'services': {'api': {'id': 'api-id', 'image': 'image', 'running': True,
                                    'mounts': ['original'], 'host_config': {}, 'networks': ['original-net']}}}
    stopped = deepcopy(original)
    stopped['services']['api']['running'] = False
    m.operational_gate(stopped, original, identity)
    m.operational_gate(original, original, identity, restored=None)
    m.operational_gate(stopped, original, identity, restored=None)
    for field, bad in (('id', 'other'), ('running', True), ('mounts', ['experiment']), ('image', 'new')):
        changed = deepcopy(stopped)
        changed['services']['api'][field] = bad
        with pytest.raises(ValueError):
            m.operational_gate(changed, original, identity)
    changed = deepcopy(stopped)
    changed['identity']['schema_revision'] = 'b'*40
    with pytest.raises(ValueError):
        m.operational_gate(changed, original, identity)


def test_disk_growth_counts_separate_filesystems_and_detects_scope_change():
    m = module('recording_ec2_host')
    assert m.disk_growth({'1': 1000, '2': 4000}, {'1': 950, '2': 3500}) == 550
    with pytest.raises(ValueError):
        m.disk_growth({'1': 1000}, {'2': 950})


def test_maintenance_approval_expires_and_requires_each_control():
    m = module('recording_ec2_host')
    approval = {k: True for k in ('ingress_controlled', 'writers_paused', 'jobs_zero', 'deployments_paused', 'backups_paused')}
    approval.update(owner='rec-ec2-0123456789abcdef', snapshot_sha256='a'*64, recovery_owner='operator', not_after_unix=2000)
    m.approval_gate(approval, approval['owner'], 'a'*64, now=1000)
    for key in ('ingress_controlled', 'writers_paused', 'jobs_zero', 'deployments_paused', 'backups_paused'):
        with pytest.raises(ValueError):
            m.approval_gate({**approval, key: False}, approval['owner'], 'a'*64, now=1000)
    with pytest.raises(ValueError):
        m.approval_gate(approval, approval['owner'], 'a'*64, now=2000)


def test_parent_memory_never_silently_accepts_hidden_finite_scope():
    from copy import deepcopy
    m = module('recording_ec2_entry')
    parents = [{'identity': [1, 2], 'root': False, 'max': 'max', 'high': 'max', 'swap_max': 'max',
                'current': 100, 'events': {'oom': 0, 'oom_kill': 0}}]
    m.parent_memory_gate(parents)
    for key, bad in (('max', '536870912'), ('high', '1073741824'), ('events', {'oom': 1}), ('current', None)):
        changed = deepcopy(parents)
        changed[0][key] = bad
        with pytest.raises(ValueError):
            m.parent_memory_gate(changed)
    changed = deepcopy(parents)
    changed[0]['swap_max'] = '0'
    with pytest.raises(ValueError):
        m.parent_memory_gate(changed, parents)


def test_database_authentication_scope_blocks_operational_url_and_restores(tmp_path):
    import sqlalchemy as sa
    m = module('recording_ec2_entry')
    path = tmp_path/'credential.private.json'
    path.write_text(json.dumps({'username': 'root', 'password': 'a'*64}))
    before = sa.create_engine
    with m.authenticated_database('192.0.2.2', path):
        for host, database in (('192.0.2.3', 'probe'), ('192.0.2.2', 'production')):
            with pytest.raises(ValueError):
                sa.create_engine(sa.URL.create('mysql+pymysql', username='root', host=host, database=database))
    assert sa.create_engine is before


def test_approved_fixture_hash_cannot_change_after_smoke(tmp_path):
    import hashlib
    m = module('recording_ec2_host')
    for name in ('manifest.private.json', 'placements.private.json'):
        (tmp_path/name).write_bytes(b'fixed')
    approved = {name: hashlib.sha256(b'fixed').hexdigest() for name in ('manifest.private.json', 'placements.private.json')}
    m.fixture_gate(tmp_path, approved)
    (tmp_path/'placements.private.json').write_bytes(b'different')
    with pytest.raises(ValueError):
        m.fixture_gate(tmp_path, approved)


def test_leaf_memory_and_swap_change_is_not_ignored():
    m = module('recording_ec2_entry')
    value = {'identity': [1, 2], 'cpu_max': '200000 100000', 'cpuset': '0-1',
             'memory_max': 1342177280, 'memory_swap_max': 0}
    m.leaf_scope_gate(value, value)
    for key, bad in (('memory_max', 67108864), ('memory_swap_max', 1024)):
        with pytest.raises(ValueError):
            m.leaf_scope_gate({**value, key: bad}, value)


def test_docker_endpoint_must_be_local_on_ec2():
    m = module('recording_ec2_host')
    m.local_daemon_gate('unix:///var/run/docker.sock', 'host', 'host', {})
    for endpoint, daemon, env in (('tcp://remote:2375', 'host', {}),
                                  ('unix:///var/run/docker.sock', 'other', {}),
                                  ('unix:///var/run/docker.sock', 'host', {'DOCKER_HOST': 'remote'})):
        with pytest.raises(ValueError):
            m.local_daemon_gate(endpoint, daemon, 'host', env)
