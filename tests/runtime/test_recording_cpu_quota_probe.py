"""실제 부하 없이 CPU 계측·중단 경계를 확인하는 합성 controls."""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


@pytest.fixture
def cpu():
    path = Path(__file__).parents[2] / 'scripts/recording_cpu_quota_probe.py'
    assert path.is_file(), 'CPU 계측 모듈이 필요합니다'
    spec = importlib.util.spec_from_file_location('cpu_probe_control', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot(n=0, identity=11, maximum='150000 100000'):
    return {'identity': [1, identity], 'cpu_max': maximum, 'cpuset': '0-1',
        'cpu_stat': {k: n for k in ('usage_usec', 'user_usec', 'system_usec',
                                  'nr_periods', 'nr_throttled', 'throttled_usec')}}


def test_deltas_are_per_actor_and_preserve_optional_fields(cpu):
    a, b = snapshot(10), snapshot(17)
    a['cpu_stat']['burst_usec'] = 2
    b['cpu_stat']['burst_usec'] = 5
    assert cpu.counter_delta(a, b)['usage_usec'] == 7
    assert cpu.counter_delta(a, b)['burst_usec'] == 3
    assert cpu.counter_delta(a, b)['throttled_usec'] == 7


@pytest.mark.parametrize('change', ['reset', 'identity', 'missing', 'quota', 'cpuset'])
def test_reset_missing_or_changed_scope_is_rejected(cpu, change):
    a, b = snapshot(10), snapshot(17)
    if change == 'reset':
        b['cpu_stat']['usage_usec'] = 9
    elif change == 'identity':
        b['identity'] = [1, 12]
    elif change == 'missing':
        del b['cpu_stat']['throttled_usec']
    elif change == 'quota':
        b['cpu_max'] = '200000 100000'
    else:
        b['cpuset'] = '1'
    with pytest.raises(ValueError, match='CPU_'):
        cpu.counter_delta(a, b)


def test_cgroup_reader_keeps_real_fields_and_marks_optional_absence(cpu, tmp_path):
    (tmp_path/'cpu.max').write_text('150000 100000\n')
    (tmp_path/'cpuset.cpus.effective').write_text('0-1\n')
    (tmp_path/'cpu.stat').write_text('usage_usec 10\nuser_usec 7\nsystem_usec 3\nnr_periods 2\nnr_throttled 1\nthrottled_usec 5\n')
    (tmp_path/'memory.current').write_text('2048')
    (tmp_path/'memory.events').write_text('oom 0\noom_kill 0')
    value = cpu.read_cgroup(tmp_path)
    assert value['cpu_stat']['user_usec'] == 7
    assert value['memory_current'] == 2048 and value['memory_peak'] is None
    assert str(tmp_path) not in str(value)
    (tmp_path/'cpu.stat').write_text('usage_usec 1\nusage_usec 2')
    with pytest.raises(ValueError, match='CPU_'):
        cpu.read_cgroup(tmp_path)


@pytest.mark.parametrize('argv,kind', [
    (['ffprobe', '-show_frames', '/inputs/private.mp4'], 'source_frame_probe'),
    (['ffprobe', '-show_frames', '/work/private.mp4'], 'output_frame_probe'),
    (['ffprobe', '-show_packets', '/work/private.mp4'], 'packet_probe'),
    (['ffprobe', '-show_frames', '-show_packets', '/inputs/private.mp4'], 'frame_packet_probe'),
    (['ffmpeg', '-vf', 'scale=480', '/work/private.mp4'], 'encode'),
    (['ffmpeg', '-c:v', 'copy', '/work/private.mp4'], 'remux'),
    (['ffmpeg', '-f', 'concat', '-c', 'copy', '/work/private.mp4'], 'concat'),
    (['ffmpeg', '-xerror', '-f', 'null', '-'], 'strict_decode'),
    (['unknown', '/private/name'], 'unknown'),
])
def test_actual_argv_classification_never_exposes_paths(cpu, argv, kind):
    result = cpu.classify_argv(argv)
    assert result['category'] == kind
    assert 'private' not in str(result)


def test_nested_phase_has_parent_and_separate_cpu_windows(cpu):
    values = iter([0, 10, 20, 30])
    events = []
    def collect():
        n = next(values)
        return {'runner': snapshot(n), 'db': snapshot(n*2, identity=21, maximum='50000 100000')}
    observer = cpu.PhaseObserver(collect, events, children=lambda: None)
    with observer.phase('recording_prepare'):
        with observer.phase('db_publish'):
            pass
    parent, child = events
    assert child['parent_id'] == parent['id']
    assert child['delta']['runner']['usage_usec'] == 10
    assert parent['delta']['runner']['usage_usec'] == 30
    assert parent['delta']['db']['usage_usec'] == 60
    assert child['children_cpu_delta'] is None
    assert parent['wall_sec'] >= child['wall_sec'] >= 0
    assert parent['collector_wall_sec'] >= 0


def test_missing_db_snapshot_blocks_body(cpu):
    events = []
    observer = cpu.PhaseObserver(lambda: {'runner': snapshot()}, events, children=lambda: None)
    with pytest.raises(ValueError, match='CPU_ACTORS'):
        with observer.phase('encode'):
            pytest.fail('계측 누락 후 실행하면 안 됩니다')
    assert events[0]['status'] == 'MEASUREMENT_FAILED'


def test_hook_restores_on_body_and_collector_failure(cpu):
    @contextmanager
    def measure(events, name):
        yield {}
    target = SimpleNamespace(measure=measure)
    observer = cpu.PhaseObserver(lambda: {'runner': snapshot(), 'db': snapshot(identity=21)}, [], children=lambda: None)
    with pytest.raises(RuntimeError, match='CONTROL'):
        with cpu.observe_measurements(target, observer):
            with target.measure([], 'encode'):
                raise RuntimeError('CONTROL')
    assert target.measure is measure and observer.events[0]['status'] == 'FAIL'
    bad = cpu.PhaseObserver(lambda: {}, [], children=lambda: None)
    with pytest.raises(ValueError):
        with cpu.observe_measurements(target, bad):
            with target.measure([], 'encode'):
                pass
    assert target.measure is measure


def test_quota_is_only_arm_difference_and_no_update_is_used(cpu):
    a1, b, a2 = [cpu.arm_cpu_args(arm) for arm in ('A1', 'B', 'A2')]
    assert a1 == a2 == ['--cpus', '1.5', '--cpuset-cpus', '0,1']
    assert b == ['--cpus', '2.0', '--cpuset-cpus', '0,1']
    with pytest.raises(ValueError):
        cpu.arm_cpu_args('extra')


@pytest.mark.parametrize('failure', ['execute', 'measurement', 'cleanup', 'false'])
def test_sequence_stops_on_first_failure_and_always_cleans(cpu, failure):
    calls = []
    def execute(arm, args):
        calls.append(('execute', arm, args))
        if failure in ('execute', 'measurement'):
            raise RuntimeError('CONTROL')
        return failure != 'false'
    def cleanup(arm):
        calls.append(('cleanup', arm))
        return failure != 'cleanup'
    with pytest.raises(RuntimeError):
        cpu.run_sequence(execute, cleanup)
    assert [c[:2] for c in calls] == [('execute', 'A1'), ('cleanup', 'A1')]


def test_cleanup_requires_exact_owner_name_and_unused(cpu):
    assert cpu.removable('task-A1', {'task-A1'}, 'task', {'owner': 'task'}, [])
    assert not cpu.removable('task-A1', {'task-A1'}, 'task', {'owner': 'other'}, [])
    assert not cpu.removable('task-other', {'task-A1'}, 'task', {'owner': 'task'}, [])
    assert not cpu.removable('task-A1', {'task-A1'}, 'task', {'owner': 'task'}, ['attached'])


@pytest.mark.parametrize('owner,labels', [(None, {}), ('', {'owner': ''}), (' ', {'owner': ' '})])
def test_cleanup_refuses_missing_or_empty_owner(cpu, owner, labels):
    assert not cpu.removable('task-A1', {'task-A1'}, owner, labels, [])


@pytest.mark.parametrize('users', [None, False, 0, ''])
def test_cleanup_refuses_unknown_usage(cpu, users):
    assert not cpu.removable('task-A1', {'task-A1'}, 'task', {'owner': 'task'}, users)


def test_recording_only_selection_and_search_bypass_are_explicit():
    scripts = Path(__file__).parents[2] / 'scripts'
    sys.path.insert(0, str(scripts))
    try:
        import recording_real_media_recheck as runner
        assert 'recording_only' in runner.validate_selection.__code__.co_varnames
        runner.validate_selection(1, 2, 120, None, recording_only=True)
        runner.validate_selection(2, 1, 10, None, recording_only=True)
        with pytest.raises(ValueError):
            runner.validate_selection(1, 2, 121, None, recording_only=True)
        report = {'recording': 'PASS', 'db_store': 'PASS_COMMITTED', 'db_commit': 'PASS',
            'prepared_rollback': 'PASS_SAME_CONNECTION', 'db_read': 'PASS_HASH_LENGTH_DETACHED',
            'provenance': 'PASS', 'detached_strict_decode': 'PASS'}
        runner.require_recording_result(report)
        for field in report:
            with pytest.raises(ValueError, match='RECORDING_ONLY_INCOMPLETE'):
                runner.require_recording_result({**report, field: 'NOT_RUN'})
    finally:
        sys.path.pop(0)
