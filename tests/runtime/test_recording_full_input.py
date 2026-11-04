"""전체 입력을 prefix로 바꾸거나 예산 한쪽만 올리지 못하게 하는 로컬 controls."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / 'scripts'))


def full_module():
    try:
        return importlib.import_module('recording_full_input')
    except ModuleNotFoundError:
        pytest.fail('전체 입력 검증 모듈이 없습니다')


def fixture_manifest(tmp_path):
    source = tmp_path/'originals'
    source.mkdir()
    records = []
    for n in range(1, 16):
        path = source/f'private-{n:02}.mp4'
        path.write_bytes(f'original-{n}'.encode())
        records.append({'fixture_id': f'input-{n:02}', 'filename': path.name,
            'bytes': path.stat().st_size, 'mtime_ns': path.stat().st_mtime_ns,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'proposed_video_index': 0,
            'metadata': {'streams': [{'index': 0, 'codec_type': 'video', 'codec_name': 'h264',
                'width': 1920, 'height': 1080, 'avg_frame_rate': '30/1',
                'time_base': '1/30000', 'duration': '1.000001'}],
                'format': {'duration': '1.000001'}}})
    manifest = {'source_folder_private': str(source), 'file_count': 15,
        'total_bytes': sum(r['bytes'] for r in records), 'sum_metadata_duration_sec': '15.000015', 'files': records}
    return manifest, source


def test_plan_requires_all_fifteen_in_manifest_order_and_preserves_fraction(tmp_path):
    m, _ = fixture_manifest(tmp_path)
    result = full_module().full_plan(m)
    assert [r['id'] for r in result['placements']] == [f'input-{n:02}' for n in range(1, 16)]
    assert result['requested_sec'] == '15.000015'
    assert result['max_duration_ms'] == 15001
    assert result['placements'][1]['start'] == 1.000001
    assert result['placements'][-1]['end'] == 15.000015
    assert result['capture_continuity'] == 'UNKNOWN'


@pytest.mark.parametrize('change', ['missing', 'reordered', 'duplicate', 'stream', 'multi_video', 'duration', 'total', 'escape'])
def test_plan_rejects_wrong_set_stream_duration_totals_and_source_escape(tmp_path, change):
    m, _ = fixture_manifest(tmp_path)
    if change == 'missing':
        m['files'].pop()
    elif change == 'reordered':
        m['files'][0], m['files'][1] = m['files'][1], m['files'][0]
    elif change == 'duplicate':
        m['files'][1]['filename'] = m['files'][0]['filename']
    elif change == 'stream':
        m['files'][0]['proposed_video_index'] = 1
    elif change == 'multi_video':
        m['files'][0]['metadata']['streams'].append({**m['files'][0]['metadata']['streams'][0], 'index': 1})
    elif change == 'duration':
        m['files'][0]['metadata']['format']['duration'] = 'NaN'
    elif change == 'total':
        m['total_bytes'] += 1
    else:
        m['files'][0]['filename'] = '../outside.mp4'
    with pytest.raises(ValueError):
        full_module().full_plan(m)


def test_audit_compares_metadata_hash_and_stat_without_modifying_originals(tmp_path):
    m, source = fixture_manifest(tmp_path)
    original = [(p.name, p.read_bytes(), p.stat().st_mtime_ns) for p in source.iterdir()]
    by_name = {r['filename']: r['metadata'] for r in m['files']}
    result = full_module().audit_sources(m, source, probe=lambda p: copy.deepcopy(by_name[p.name]))
    assert result['status'] == 'PASS_INPUT_AUDIT'
    assert result['verified_files'] == 15
    assert [(p.name, p.read_bytes(), p.stat().st_mtime_ns) for p in source.iterdir()] == original
    (source/m['files'][5]['filename']).write_bytes(b'changed')
    with pytest.raises(ValueError, match='INPUT'):
        full_module().audit_sources(m, source, probe=lambda p: by_name[p.name])


def test_metadata_mismatch_and_extra_original_fail_closed(tmp_path):
    m, source = fixture_manifest(tmp_path)
    def wrong(p):
        metadata = copy.deepcopy(m['files'][0]['metadata'])
        metadata['streams'][0]['codec_type'] = 'audio'
        return metadata
    with pytest.raises(ValueError, match='METADATA'):
        full_module().audit_sources(m, source, probe=wrong)
    (source/'extra.mp4').write_bytes(b'extra')
    with pytest.raises(ValueError, match='FILE_SET'):
        full_module().audit_sources(m, source, probe=wrong)


def test_full_scope_rejects_1200_prefix_and_accepts_exact_endpoint():
    placements = [{'id': f'input-{n:02}', 'start': (n-1)*100.0,
        'end': n*100.0 if n < 15 else 1584.173332, 'video_index': 0} for n in range(1, 16)]
    full_module().require_full_scope(placements, 1584.173332)
    for seconds in (1200, 1584, 1585, float('nan'), True):
        with pytest.raises(ValueError):
            full_module().require_full_scope(placements, seconds)


def test_logical_coverage_accepts_exact_full_fraction_through_float_entry():
    from recording_real_media_recheck import logical_coverage
    placements = [{'start': 0.0, 'end': 1584.173332}]
    result = logical_coverage(placements, float('1584.173332'))
    assert result['placed_end_sec'] == '1584.173332'
    with pytest.raises(ValueError, match='INSUFFICIENT'):
        logical_coverage(placements, 1584.173333)


def test_full_budget_is_coordinated_and_rejects_old_1200_profile():
    from recording_probe_budget import ProbeBudget, MIB
    b = ProbeBudget.from_profile('full15-512m')
    b.validate_experiment(512*MIB, 1584174, 3600)
    required = b.requirements(512*MIB, 64*MIB)
    assert required['temp_candidate_bytes'] == 1088*MIB
    assert required['runner_candidate_bytes'] == 2288*MIB
    assert required['db_growth_candidate_bytes'] == 1536*MIB
    assert required['disk_growth_candidate_bytes'] == 2688*MIB
    assert b.host_start_bytes == 4796*MIB
    assert b.host_timeout_sec(3600) == 3630
    b.preflight(available_ram=6*1024**3, c_free=12*1024**3, disk_growth_used=0,
        db_data=128*MIB, output_cap=512*MIB, search_candidate=64*MIB)
    for values in ((384*MIB, 1584174, 3600), (512*MIB, 1200000, 3600), (512*MIB, 1584174, 0)):
        with pytest.raises(ValueError):
            b.validate_experiment(*values)


def test_full_profile_selection_requires_fifteen_and_explicit_profile():
    from recording_real_media_recheck import Experiment, validate_selection
    from recording_probe_budget import MIB
    exp = Experiment.from_mapping({'experiment_id': 'full15-control', 'max_output_bytes': 512*MIB,
        'max_duration_ms': 1584174, 'run_timeout_sec': 3600, 'resource_profile': 'full15-512m'})
    validate_selection(1, 15, 1584.173332, exp, recording_only=True)
    validate_selection(1, 15, 1584.173332, exp, recording_only=False)
    for first, count, seconds in ((1, 14, 1584.173332), (2, 15, 1584.173332), (1, 15, float('inf'))):
        with pytest.raises(ValueError):
            validate_selection(first, count, seconds, exp, recording_only=True)
    with pytest.raises(ValueError):
        validate_selection(1, 15, 1584.173332, None, recording_only=True)


def test_full_stage_cannot_skip_representative_or_use_legacy_budget(tmp_path):
    from recording_ec2_host import previous_stage, stage_settings
    with pytest.raises(ValueError):
        previous_stage(tmp_path, 'full')
    (tmp_path/'representative-result.private.json').write_text(json.dumps({'status': 'PASS', 'cleanup': True}))
    previous_stage(tmp_path, 'full')
    with pytest.raises(ValueError):
        stage_settings({}, 'full')
    value = stage_settings({'probe_profile': 'full15-512m'}, 'full')
    assert value['runner_mib'] == 3072 and value['timeout_sec'] == 3600
    assert stage_settings({'probe_profile': 'full15-512m'}, 'smoke')['runner_mib'] == 1280


def test_full_placement_requires_fifteen_and_exact_endpoint():
    from recording_ec2_entry import placement_gate
    placements = [{'id': f'input-{n:02}', 'start': float(n-1), 'end': float(n), 'video_index': 0}
        for n in range(1, 16)]
    placement_gate(placements, placements, 'full')
    with pytest.raises(ValueError):
        placement_gate(placements, placements[:-1], 'full')


def test_input_artifacts_exclude_original_paths_and_cannot_overwrite(tmp_path):
    m, source = fixture_manifest(tmp_path)
    output = tmp_path/'plan'
    full_module().write_input_plan(m, output)
    safe = (output/'manifest.private.json').read_text()
    assert str(source) not in safe and 'private-01' not in safe
    assert len(json.loads(safe)['files']) == 15
    placements = json.loads((output/'placements.private.json').read_text())
    assert len(placements['full']) == 15 and len(placements['representative']) == 2
    assert 'source_private' in (output/'transfer-plan.private.json').read_text()
    assert len(list(source.iterdir())) == 15
    with pytest.raises(FileExistsError):
        full_module().write_input_plan(m, output)


def test_linux_full_resource_gate_cannot_reuse_120_second_limits():
    from recording_ec2_host import resource_gate
    from recording_probe_budget import ProbeBudget, MIB
    b = ProbeBudget.from_profile('full15-512m')
    policy = {'memory_reserve_bytes': 700*MIB, 'disk_reserve_bytes': 4096*MIB}
    kwargs = dict(budget=b, output_cap=512*MIB)
    assert resource_gate(policy, 4796*MIB, 8192*MIB, 0, 128*MIB, **kwargs)['start_required_bytes'] == 4796*MIB
    for available, free, growth, data in ((4796*MIB-1, 8192*MIB, 0, 0),
            (4796*MIB, 8192*MIB-1, 0, 0), (4796*MIB, 8192*MIB, 1408*MIB+1, 0),
            (4796*MIB, 8192*MIB, 0, 1024*MIB)):
        with pytest.raises(ValueError):
            resource_gate(policy, available, free, growth, data, **kwargs)


def test_full_input_gate_reads_exact_fifteen_and_detects_same_stat_corruption(tmp_path):
    import os
    from recording_ec2_host import input_gate
    m, source = fixture_manifest(tmp_path)
    m['files'][-1]['metadata']['format']['duration'] = '1570.173318'
    m['sum_metadata_duration_sec'] = '1584.173332'
    plan_dir, copies = tmp_path/'plan', tmp_path/'copies'
    full_module().write_input_plan(m, plan_dir)
    copies.mkdir()
    fixture = json.loads((plan_dir/'manifest.private.json').read_text())
    for original, safe in zip(m['files'], fixture['files']):
        p = copies/safe['filename']
        p.write_bytes((source/original['filename']).read_bytes())
        os.utime(p, ns=(safe['mtime_ns'], safe['mtime_ns']))
    input_gate(copies, fixture, full=True)
    with pytest.raises(ValueError):
        input_gate(copies, fixture)
    p = copies/fixture['files'][-1]['filename']
    p.write_bytes(b'x'*p.stat().st_size)
    os.utime(p, ns=(fixture['files'][-1]['mtime_ns'], fixture['files'][-1]['mtime_ns']))
    with pytest.raises(ValueError, match='HASH'):
        input_gate(copies, fixture, full=True)


@pytest.mark.parametrize('request_cap', [56*1024**2, 1])
def test_full_request_boundary_with_cpu_journal_keeps_json_local_and_restores_hooks(tmp_path, request_cap):
    from types import SimpleNamespace
    import time
    import recording_real_media_recheck as runner
    from recording_cpu_quota_linux import JournalObserver
    from recording_cpu_quota_probe import observe_measurements, REQUIRED
    from daesingo.search import provider
    from daesingo.search.config import GeminiSearchConfig
    from daesingo.search.execution import RunDeadline
    from daesingo.search.media import PreparedMedia

    actor = {'identity': [1, 2], 'cpu_max': '200000 100000', 'cpuset': '0-1',
             'cpu_stat': {key: 0 for key in REQUIRED}}
    events, report = [], {}
    journal = tmp_path/'cpu.jsonl'
    observer = JournalObserver(lambda: {'runner': actor, 'db': actor}, events, journal)
    path = tmp_path/'coarse.mp4'
    path.write_bytes(b'media')
    original_json, original_dumps, original_url = provider.json, json.dumps, provider._video_data_url
    with observe_measurements(runner.diag, observer):
        def request():
            runner.request_boundary(GeminiSearchConfig(max_inline_request_bytes=request_cap),
                PreparedMedia(path, 'video/mp4', 5, 10, 0, 10),
                SimpleNamespace(analysis_source_ref='control', duration_sec=10), 'control',
                RunDeadline(time.monotonic, 150000), report, [], lambda: None)
        if request_cap == 1:
            with pytest.raises(provider.RequestSizeError):
                request()
        else:
            request()
    assert provider.json is original_json and json.dumps is original_dumps
    assert provider._video_data_url is original_url
    assert report['sdk_entry_count'] == (0 if request_cap == 1 else 1)
    assert report['request_guard'] == ('FAIL' if request_cap == 1 else 'PASS_STOP_BEFORE_SEND')
    samples = [json.loads(line) for line in journal.read_text().splitlines()]
    assert samples and len(events) < 10
    assert any(e['phase'] == 'search_guard_json' for e in events)


def test_supervisor_cleanup_preserves_runner_and_init_logs_separately(tmp_path):
    from types import SimpleNamespace
    from recording_cpu_quota_supervisor import Supervisor

    supervisor = object.__new__(Supervisor)
    supervisor.owner, supervisor.root = 'cpu-quota-log-control', tmp_path
    supervisor.cleanup_deadline = None
    names = supervisor.names('smoke')
    supervisor.created = [('container', names['init']), ('container', names['runner'])]
    present = {name: {'State': {'Running': False, 'ExitCode': 0}, 'RestartCount': 0}
               for _, name in supervisor.created}
    supervisor.inspect = lambda kind, name, **kwargs: present.get(name)
    supervisor.owned = lambda kind, name: present[name]

    def docker(*args, **kwargs):
        if args[0] == 'logs':
            return SimpleNamespace(stdout=args[1].encode(), stderr=b'')
        assert args[0] == 'rm'
        present.pop(args[1])
        return SimpleNamespace(stdout=b'', stderr=b'')

    supervisor.docker = docker
    supervisor.cleanup('smoke')
    assert not supervisor.created and not present
    assert (tmp_path/'smoke-runner-logs.private.txt').read_text() == names['runner']
    assert (tmp_path/'smoke-init-logs.private.txt').read_text() == names['init']
