"""격리 준비 예산과 복구 경계 controls. 실제 영상/운영서비스를 실행하지 않는다."""
from contextlib import contextmanager
import importlib
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]/'scripts'))


def test_preparation_budget_is_explicit_full_coarse_only():
    r = importlib.import_module('recording_real_media_recheck')
    config = {'probe_profile': 'full15-512m', 'full_search_prepare_budget_ms': 900000}
    assert r.search_preparation_budget({}, full=False, coarse=False) == 150000
    assert r.search_preparation_budget(config, full=True, coarse=True) == 900000
    for full, coarse in ((False, True), (True, False), (False, False)):
        with pytest.raises(ValueError):
            r.search_preparation_budget(config, full=full, coarse=coarse)
    for value in (True, 0, 900001, float('inf'), '900000'):
        with pytest.raises(ValueError):
            r.search_preparation_budget({**config, 'full_search_prepare_budget_ms': value}, full=True, coarse=True)
    with pytest.raises(ValueError):
        r.search_preparation_budget({**config, 'probe_profile': 'legacy'}, full=True, coarse=True)


def test_full_preparation_budget_reaches_stage_without_changing_legacy():
    from recording_ec2_host import stage_settings
    config = {'probe_profile': 'full15-512m', 'full_probe_mode': 'coarse_270p_stop_before_send',
              'full_search_prepare_budget_ms': 900000}
    assert stage_settings(config, 'full')['search_prepare_budget_ms'] == 900000
    assert stage_settings(config, 'representative')['search_prepare_budget_ms'] == 150000
    assert stage_settings(config, 'full')['timeout_sec'] == 3600


@pytest.mark.parametrize('budget,ready', [(150000, False), (900000, True)])
def test_same_preparation_over_150_seconds_keeps_request_guard_separate(monkeypatch, tmp_path, budget, ready):
    import recording_real_media_recheck as r
    from daesingo.search import media as m
    from daesingo.search.config import GeminiSearchConfig
    from daesingo.search.execution import DeadlineExceededError

    now, calls = [0.0], []
    path = tmp_path/'coarse.mp4'
    path.write_bytes(b'complete')
    report = {'expected_sha256': 'control'}

    @contextmanager
    def prepare(self, media_input, deadline):
        now[0] += 151
        deadline.check()
        try:
            yield m.PreparedMedia(path, 'video/mp4', 8, 1584.173332, 0, 1584.173332)
        finally:
            calls.append('media_closed')

    @contextmanager
    def phase(name):
        yield {}

    def guard(cfg, media, source, timeline_id, deadline, report, events, check):
        assert cfg == GeminiSearchConfig()
        assert deadline.remaining_ms() == 150000
        calls.append('guard')

    monkeypatch.setattr(m.MediaPreparer, 'prepare_coarse', prepare)
    monkeypatch.setattr(r, 'request_boundary', guard)
    monkeypatch.setattr(r, 'inspect_coarse_output', lambda *a: {'control': 'not_real_probe'})
    original = m._run_ffmpeg_encode

    def execute():
        r.probe_search(m, GeminiSearchConfig(), None, None, 'timeline', report, [], lambda: None,
                       phase, preparation_budget_ms=budget, coarse_270p=True, clock=lambda: now[0])

    if ready:
        execute()
        assert report['search_prepare_wall_sec'] == 151
        assert report['search_media_bytes'] == 8
        assert report['search_media_duration_sec'] == 1584.173332
        assert calls == ['guard', 'media_closed']
    else:
        with pytest.raises(DeadlineExceededError):
            execute()
        assert report['search_prepare_completed'] is False
        assert 'search_media_bytes' not in report
        assert not calls
    assert m._run_ffmpeg_encode is original


@pytest.mark.parametrize('host_mode', ['ok', 'failed', 'timeout'])
@pytest.mark.parametrize('broken_logs', [False, True])
def test_real_child_failure_and_log_open_failure_still_run_recovery(tmp_path, host_mode, broken_logs):
    import recording_probe_session as session
    import json
    if broken_logs:
        (tmp_path/'session-host.out').mkdir()
        (tmp_path/'session-recovery.out').mkdir()
    marker = tmp_path/'recovered'
    host = [sys.executable, '-B', '-c',
            'import time;time.sleep(30)' if host_mode == 'timeout' else
            'raise SystemExit('+('0' if host_mode == 'ok' else '7')+')']
    recovery = [sys.executable, '-B', '-c',
                'from pathlib import Path;import sys;print("recovery");Path(sys.argv[1]).write_text("yes")', str(marker)]
    value = session.run_commands(host, recovery, tmp_path, host_timeout=.2 if host_mode == 'timeout' else 5,
                                 recovery_timeout=5)
    assert marker.read_text() == 'yes'
    assert value['original_recovered'] is True
    assert value['host_passed'] is (host_mode == 'ok')
    assert json.loads((tmp_path/'session-outcome.private.json').read_text()) == value


@pytest.mark.parametrize('mode', ['write', 'flush', 'closed'])
def test_output_failure_does_not_escape_progress_boundary(monkeypatch, mode):
    import recording_probe_session as session
    class Broken:
        def write(self, value):
            if mode == 'write':
                raise BrokenPipeError('control')
        def flush(self):
            raise ValueError('closed') if mode == 'closed' else BrokenPipeError('control')
    monkeypatch.setattr(sys, 'stdout', Broken())
    session.emit('CONTROL')


def test_recovery_failure_never_reports_pass(tmp_path):
    import recording_probe_session as session
    value = session.run_commands([sys.executable, '-c', 'pass'],
                                 [sys.executable, '-c', 'raise SystemExit(2)'], tmp_path,
                                 host_timeout=5, recovery_timeout=5)
    assert value['status'] == 'REVIEW_REQUIRED'
    assert value['original_recovered'] is False


@pytest.mark.parametrize('failure', [None, 'identity', 'ready', 'extra_lock', 'other_stage_running'])
def test_restore_exact_services_and_lock_with_service_doubles(monkeypatch, tmp_path, failure):
    import copy
    import json
    import recording_probe_session as session
    import recording_ec2_host as host
    import recording_cpu_quota_supervisor as transport
    evidence, operation = tmp_path/'evidence', tmp_path/'operation'
    evidence.mkdir()
    lock = operation/'operation.lock'
    lock.mkdir(parents=True)
    marker = lock/'recording-probe-owner.private.json'
    owner, digest = 'rec-ec2-0123456789abcdef', 'f'*64
    marker.write_text(json.dumps({'owner': owner, 'evidence': str(evidence)}))
    if failure == 'extra_lock':
        (lock/'unknown').touch()
    services = {name: dict(id=name+'-exact-id', image='fixed', mounts=[], host_config={}, networks=[], running=True)
                for name in ('mysql', 'api', 'worker')}
    original = {'identity': {'revision': 'fixed'}, 'files': {'current': 'hash'}, 'pointer': 'fixed/web',
                'services': services}
    current = copy.deepcopy(original)
    for service in current['services'].values():
        service['running'] = False
    if failure == 'identity':
        current['services']['api']['id'] = 'other-id'
    calls = []
    monkeypatch.setattr(session, 'bindings', lambda *a: (Path('/var/lib/recording-probe')/owner,
        evidence, tmp_path/'source', {'config': {'operational_identity': original['identity']}}, original, marker))
    policy = {'project': 'production', 'mysql_volume': 'protected-db', 'media_volume': 'protected-media'}
    monkeypatch.setattr(host, 'operational_snapshot', lambda *a: (policy, copy.deepcopy(current)))
    monkeypatch.setattr(transport.Supervisor, 'inspect', lambda *a, **kw: None)

    def capture(argv, *args, **kwargs):
        calls.append(argv)
        stdout = b''
        if argv[:2] == ['docker', 'start']:
            name = argv[2].split('-')[0]
            assert argv[2] == services[name]['id']
            current['services'][name]['running'] = True
        elif argv[:2] == ['docker', 'inspect']:
            stdout = json.dumps([{'Config': {'Labels': {'owner': owner}},
                'State': {'Running': True, 'Health': {'Status': 'healthy'}}}]).encode()
        elif argv[:2] == ['docker', 'ps']:
            stdout = b'other-stage' if failure == 'other_stage_running' else b''
        elif argv[0] == 'curl':
            stdout = b'500' if failure == 'ready' else b'200'
        elif argv[0] == 'systemctl':
            stdout = b'active\nactive\nactive\n'
        else:
            assert argv[:2] == ['docker', 'exec']
        return SimpleNamespace(returncode=0, stdout=stdout, stderr=b'')
    monkeypatch.setattr(transport, 'bounded_capture', capture)
    if failure:
        with pytest.raises((RuntimeError, ValueError)):
            session.restore('ignored', digest, operation)
        assert marker.exists()
        if failure == 'identity':
            assert not calls
    else:
        session.restore('ignored', digest, operation)
        assert not lock.exists()
        assert [c[2] for c in calls if c[:2] == ['docker', 'start']] == [services[s]['id'] for s in services]
        starts = sum(c[:2] == ['docker', 'start'] for c in calls)
        session.restore('ignored', digest, operation)
        assert sum(c[:2] == ['docker', 'start'] for c in calls) == starts
        assert calls[-2][0] == 'curl'  # 재진입 시에도 health/readiness를 확인한다.


def test_inline_and_stop_post_share_one_recovery_window(tmp_path):
    import recording_probe_session as session
    assert session.recovery_remaining(tmp_path, 'a'*64, now=1000) == 900
    assert session.recovery_remaining(tmp_path, 'a'*64, now=1700) == 200
    with pytest.raises(TimeoutError):
        session.recovery_remaining(tmp_path, 'a'*64, now=1900)
    with pytest.raises(ValueError):
        session.recovery_remaining(tmp_path, 'b'*64, now=1700)
    assert session.recovery_remaining(tmp_path, 'a'*64, now=1900, manual_id='0123456789abcdef') == 900
    with pytest.raises(ValueError):
        session.recovery_remaining(tmp_path, 'a'*64, now=1900, manual_id='../unsafe')


def test_unit_is_detached_file_stdio_with_independent_recovery():
    import recording_probe_session as session
    home = '/var/lib/recording-probe/rec-ec2-0123456789abcdef'
    value = session.unit_text(home, 'a'*64, '/opt/daesingo')
    assert 'ExecStopPost=' in value and ' restore ' in value
    assert 'StandardInput=null' in value and 'StandardOutput=append:'+home+'/evidence/' in value
    assert 'Restart=no' in value and 'RuntimeMaxSec=5200' in value
    assert '--pipe' not in value and 'KillMode=control-group' in value
    with pytest.raises(ValueError):
        session.unit_text(home, 'a'*64, '/opt/unsafe%path')


@pytest.mark.parametrize('remaining', [6000, 8000, 11000])
def test_cli_propagates_operation_root_to_host(monkeypatch, tmp_path, remaining):
    import json
    import time
    import recording_probe_session as session
    import recording_ec2_host as host
    owner = 'rec-ec2-0123456789abcdef'
    home = Path('/var/lib/recording-probe')/owner
    marker = tmp_path/'marker'
    marker.write_text(json.dumps({'owner': owner, 'evidence': str(tmp_path)}))
    (tmp_path/'operational-snapshot.private.json').write_text('{}')
    (tmp_path/'maintenance-approved.private.json').write_text(json.dumps({'not_after_unix': int(time.time())+remaining}))
    config = {'full_probe_mode': 'coarse_270p_stop_before_send', 'full_search_prepare_budget_ms': 900000}
    monkeypatch.setattr(session, 'bindings', lambda *a: (home, tmp_path, tmp_path/'source', {'config': config}, {}, marker))
    monkeypatch.setattr(host, 'protected_file', lambda p: p)
    monkeypatch.setattr(host, 'approval_gate', lambda *a: None)
    monkeypatch.setattr(host, 'previous_stage', lambda *a: None)
    monkeypatch.setattr(session, 'install_handlers', lambda: None)
    commands = []
    monkeypatch.setattr(session, 'run_commands', lambda host, *a: commands.append(host) or {'status': 'PASS'})
    monkeypatch.setattr(sys, 'argv', ['session', 'run', '--home', str(home), '--manifest-sha256', 'a'*64,
                                   '--operation-root', '/opt/other-operations'])
    if remaining < 10200:
        with pytest.raises(ValueError, match='FULL_AND_RECOVERY_WINDOW_REQUIRED'):
            session.main()
        assert not commands
    else:
        assert session.main() == 0
        assert commands[0][commands[0].index('--ops-root')+1] == '/opt/other-operations'


def test_repeated_interrupt_is_deferred_until_child_reaped(monkeypatch):
    import signal
    import recording_probe_session as session
    state = {'blocked': False, 'reaped': False}
    def mask(operation, values):
        old = {signal.SIGTERM, signal.SIGINT} if state['blocked'] else set()
        state['blocked'] = operation == getattr(signal, 'SIG_BLOCK', 0)
        return old
    monkeypatch.setattr(signal, 'pthread_sigmask', mask, raising=False)
    monkeypatch.setattr(session.os, 'killpg', lambda *a: None, raising=False)
    class Child:
        pid = 123
        def poll(self):
            return None
        def terminate(self):
            pass
        def wait(self, *a):
            if not state['blocked']:
                raise InterruptedError('second TERM during child stop')
            state['reaped'] = True
    session.stop_child(Child())
    assert state == {'blocked': False, 'reaped': True}


@pytest.mark.skipif(sys.platform != 'linux', reason='실제 Linux pipe/SIGHUP/SIGTERM control')
@pytest.mark.parametrize('mode', ['closed_pipe', 'hup', 'term', 'double_term'])
def test_linux_real_pipe_and_signals_reach_recovery(tmp_path, mode):
    import json
    import os
    import signal
    import subprocess
    import time
    script = tmp_path/'child.py'
    marker, started = tmp_path/'recovered', tmp_path/'host-started'
    script.write_text('''import sys
from pathlib import Path
import recording_probe_session as s
s.install_handlers()
root=Path(sys.argv[1])
s.emit('READY')
host=[sys.executable,'-c','from pathlib import Path;import sys,time,signal;signal.signal(signal.SIGTERM,lambda *_:(time.sleep(.2),sys.exit(0)));Path(sys.argv[1]).touch();time.sleep(30)',str(root/'host-started')]
recovery=[sys.executable,'-c','from pathlib import Path;import sys;Path(sys.argv[1]).touch()',str(root/'recovered')]
s.run_commands(host,recovery,root,host_timeout=2,recovery_timeout=3)
''')
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).parents[2]/'scripts'), 'PYTHONDONTWRITEBYTECODE': '1'}
    child = subprocess.Popen([sys.executable, '-B', str(script), str(tmp_path)],
                             env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        assert child.stdout.readline() == b'READY\n'
        limit = time.monotonic()+3
        while not started.exists():
            assert child.poll() is None and time.monotonic() < limit
            time.sleep(.01)
        if mode == 'closed_pipe':
            child.stdout.close()
        else:
            os.kill(child.pid, signal.SIGHUP if mode == 'hup' else signal.SIGTERM)
            if mode == 'double_term':
                time.sleep(.03)
                os.kill(child.pid, signal.SIGTERM)
        assert child.wait(8) == 0
        assert marker.exists()
        assert json.loads((tmp_path/'session-outcome.private.json').read_text())['original_recovered'] is True
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(3)
        child.stdout.close()
