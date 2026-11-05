"""#452 격리 full 세션. 파일 stdio·유한 자식 수명·별도 복구 진입점.

운영 중단은 수행하지 않는다. 검증된 새 owner/승인/서비스 snapshot 이후만 실행한다.
systemd ExecStopPost의 restore도 같은 source manifest와 소유권을 다시 검증한다.
"""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

HOST_TIMEOUT = 4200
RECOVERY_TIMEOUT = 900
UNIT_RUNTIME_MAX = 5200
UNIT_STOP_TIMEOUT = 940
# systemd 기본 terminate 경로: stop TERM/KILL, stop-post, final TERM/KILL.
# v256 상태별 timer 기준의 보수적 점검창. 실제 설치 버전/effective unit 확인 필요.
WINDOW_REQUIRED = UNIT_RUNTIME_MAX + 5*UNIT_STOP_TIMEOUT + 300


def emit(value):
    try:
        print(value, flush=True)
    except (OSError, ValueError):
        # 인터프리터 종료 시 같은 broken stdout을 재flush하며 exit120이 나지 않게 한다.
        sys.stdout = open(os.devnull, 'w')


def record(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())


def stop_child(child):
    signals = {signal.SIGTERM, signal.SIGINT}
    # Linux에서는 두 신호를 한 번에 block한다. wait/reap 뒤 원래 mask를 복원한다.
    mask = signal.pthread_sigmask(getattr(signal, 'SIG_BLOCK', 0), signals) if hasattr(signal, 'pthread_sigmask') else None
    handlers = {} if mask is not None else {sig: signal.getsignal(sig) for sig in signals}
    try:
        for sig in handlers:
            signal.signal(sig, signal.SIG_IGN)
        if child.poll() is None:
            if os.name == 'posix':
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            else:
                child.terminate()
            try:
                child.wait(15)
            except subprocess.TimeoutExpired:
                if os.name == 'posix':
                    os.killpg(child.pid, signal.SIGKILL)
                else:
                    child.kill()
                child.wait(5)
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        if mask is not None:
            signal.pthread_sigmask(getattr(signal, 'SIG_SETMASK', 2), mask)


def file_child(argv, evidence, role, timeout):
    """로그를 열지 못해도 복구를 시도한다. 터미널/PIPE를 자식에게 상속하지 않는다."""
    with ExitStack() as stack:
        def output(suffix):
            try:
                return stack.enter_context((evidence/(role+suffix)).open('xb'))
            except OSError:
                return stack.enter_context(open(os.devnull, 'wb'))
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
            stdout=output('.out'), stderr=output('.err'), start_new_session=os.name == 'posix')
        try:
            if os.name == 'posix' and role == 'session-host':
                # /proc stat의 comm에는 공백/괄호가 가능하므로 마지막 ')' 뒤에서 센다.
                ticks = Path(f'/proc/{child.pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
                record(evidence/'session-host-process.private.json', {'pid': child.pid, 'start_ticks': ticks})
            return child.wait(timeout)
        finally:
            stop_child(child)


def run_commands(host, recovery, evidence, *, host_timeout=HOST_TIMEOUT, recovery_timeout=RECOVERY_TIMEOUT):
    """역할별 자식을 회수한 뒤 반드시 복구 시도. output 기록 실패도 복구 뒤 처리한다."""
    evidence = Path(evidence)
    value = {'status': 'REVIEW_REQUIRED', 'host_passed': False, 'original_recovered': False}
    try:
        value['host_passed'] = file_child(host, evidence, 'session-host', host_timeout) == 0
    except BaseException as error:
        value['host_error_type'] = type(error).__name__
    finally:
        # 첫 TERM/INT가 host 중단을 시작했으면 후속 TERM이 복구 finally를 끊지 않게 한다.
        # SIGKILL/OS 장애는 ExecStopPost/독립 수동 복구로 다룬다.
        handlers = {getattr(signal, name): signal.getsignal(getattr(signal, name)) for name in ('SIGTERM', 'SIGINT')}
        for sig in handlers:
            signal.signal(sig, signal.SIG_IGN)
        try:
            try:
                emit('ORIGINAL_RECOVERY_START')
                value['original_recovered'] = file_child(recovery, evidence, 'session-recovery', recovery_timeout) == 0
            except BaseException as error:
                value['recovery_error_type'] = type(error).__name__
            if value['host_passed'] and value['original_recovered']:
                value['status'] = 'PASS'
            record(evidence/'session-outcome.private.json', value)
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
    return value


def install_handlers():
    def interrupted(*_):
        raise InterruptedError('SESSION_STOP')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)


def recovery_remaining(evidence, manifest_sha256, *, now=None, manual_id=None):
    """inline/ExecStopPost의 누적 복구 예산. 재진입으로 자동 연장하지 않는다."""
    now = time.time() if now is None else now
    if manual_id is not None and re.fullmatch(r'[0-9a-f]{16}', manual_id) is None:
        raise ValueError('EXPLICIT_MANUAL_RECOVERY_ID_REQUIRED')
    name = 'recovery-window' if manual_id is None else 'manual-recovery-'+manual_id+'-window'
    path = Path(evidence)/(name+'.private.json')
    if not path.exists():
        record(path, {'manifest_sha256': manifest_sha256, 'not_after_unix': int(now)+RECOVERY_TIMEOUT})
    value = json.loads(path.read_text())
    if (value.get('manifest_sha256') != manifest_sha256 or type(value.get('not_after_unix')) is not int
            or value['not_after_unix']-now > RECOVERY_TIMEOUT):
        raise ValueError('RECOVERY_WINDOW_BINDING_INVALID')
    remaining = int(value['not_after_unix']-now)
    if remaining <= 0:
        raise TimeoutError('RECOVERY_WINDOW_EXHAUSTED_MANUAL_REVIEW')
    return remaining


def unit_text(home, manifest_sha256, operation_root):
    if (re.fullmatch(r'/var/lib/recording-probe/rec-ec2-[0-9a-f]{16}', home) is None
            or re.fullmatch(r'[0-9a-f]{64}', manifest_sha256) is None
            or re.fullmatch(r'/[a-zA-Z0-9/_-]+', operation_root) is None):
        raise ValueError('UNIT_EXACT_PATH_AND_IDENTITY_REQUIRED')
    command = f'/usr/bin/python3 -B {home}/source/scripts/recording_probe_session.py'
    args = f'--home {home} --manifest-sha256 {manifest_sha256} --operation-root {operation_root}'
    return f'''[Unit]
Description=Owned offline full15 preparation measurement
After=docker.service
[Service]
Type=exec
User=root
UMask=0077
WorkingDirectory={home}
ExecStart={command} run {args}
ExecStopPost={command} restore {args}
StandardInput=null
StandardOutput=append:{home}/evidence/session-unit.out
StandardError=append:{home}/evidence/session-unit.err
KillMode=control-group
TimeoutStopSec={UNIT_STOP_TIMEOUT}
RuntimeMaxSec={UNIT_RUNTIME_MAX}
Restart=no
'''


def bindings(home, manifest_sha256, operation_root):
    from recording_ec2_host import protected_file
    from recording_ec2_package import verify_files
    home, operation_root = Path(home), Path(operation_root)
    if (home.resolve() != home or any(p.is_symlink() for p in (home, home/'source', home/'evidence'))
            or re.fullmatch(r'rec-ec2-[0-9a-f]{16}', home.name) is None
            or home.parent != Path('/var/lib/recording-probe') or not operation_root.is_absolute()):
        raise ValueError('NEW_EXACT_OWNER_HOME_REQUIRED')
    evidence, source = home/'evidence', home/'source'
    manifest_path = source/'manifest.json'
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != manifest_sha256:
        raise ValueError('MANIFEST_HASH_MISMATCH')
    manifest = json.loads(manifest_path.read_text())
    verify_files(source, manifest)
    original = json.loads(protected_file(evidence/'operational-snapshot.private.json').read_text())
    marker = operation_root/'operation.lock/recording-probe-owner.private.json'
    return home, evidence, source, manifest, original, marker


def restore(home, manifest_sha256, operation_root):
    """기존 수동 복구의 exact identity/health/lock 조건을 유지한 재진입 가능 경로."""
    from recording_cpu_quota_supervisor import Supervisor, bounded_capture
    from recording_ec2_host import operational_snapshot, operational_gate, validate_target
    home, evidence, source, manifest, original, marker = bindings(home, manifest_sha256, operation_root)
    owner = home.name
    actor = evidence/'session-host-process.private.json'
    if actor.exists():
        value = json.loads(actor.read_text())
        stat = Path(f'/proc/{int(value["pid"])}/stat')
        if stat.exists() and stat.read_text().rsplit(')', 1)[1].split()[19] == value['start_ticks']:
            raise ValueError('HOST_STILL_RUNNING_NO_RESTORE')

    def capture(*argv):
        result = bounded_capture(['docker', *argv], 15, evidence)
        if result.returncode:
            raise RuntimeError('RECOVERY_DOCKER_QUERY_FAILED')
        return result

    def snapshot(restored):
        policy, current = operational_snapshot(operation_root, capture)
        operational_gate(current, original, manifest['config']['operational_identity'], restored=restored)
        validate_target(owner, policy, [])
        return current

    current = snapshot(None)
    receipt = evidence/'services-restored.private.json'
    if receipt.exists():
        if json.loads(receipt.read_text()) != {'owner': owner, 'manifest_sha256': manifest_sha256, 'status': 'PASS'}:
            raise ValueError('RECOVERY_RECEIPT_MISMATCH')
        snapshot(True)
    else:
        if json.loads(marker.read_text()) != {'owner': owner, 'evidence': str(evidence)}:
            raise ValueError('EXACT_OWNED_LOCK_REQUIRED')
        # 종료한 host의 full 자원만 정리한다. 기존 실패 로그도 덮어쓰지 않는다.
        cleanup = object.__new__(Supervisor)
        cleanup.owner, cleanup.stage_name = owner, 'full'
        cleanup.root = Path(tempfile.mkdtemp(prefix='restore-cleanup-', dir=evidence))
        cleanup.cleanup_deadline, cleanup.created = None, []
        names = cleanup.names('full')
        for kind, role in (('network', 'network'), ('volume', 'data'), ('volume', 'work'),
                           ('container', 'init'), ('container', 'db'), ('container', 'runner')):
            if cleanup.inspect(kind, names[role], check=False) is not None:
                cleanup.owned(kind, names[role])
                cleanup.created.append((kind, names[role]))
        cleanup.cleanup('full')
    # 선행 qualification의 자원이 아직 실행 중이면 원래 서비스를 시작하지 않는다.
    for identity in capture('ps', '-aq', '--filter', 'label=owner='+owner).stdout.decode().split():
        info = json.loads(capture('inspect', identity).stdout)[0]
        if info['Config'].get('Labels', {}).get('owner') != owner or info['State']['Running']:
            raise ValueError('EXPERIMENT_RUNNING_OR_UNKNOWN_NO_RESTORE')
    for service in ('mysql', 'api', 'worker'):
        current = snapshot(None)
        prior = original['services'][service]
        if prior['running'] and not current['services'][service]['running']:
            if bounded_capture(['docker', 'start', prior['id']], 30, evidence).returncode:
                raise RuntimeError('EXACT_SERVICE_START_FAILED')
        if prior['running']:
            deadline = time.monotonic()+120
            while True:
                info = json.loads(capture('inspect', prior['id']).stdout)[0]
                if info['State']['Running'] and (service == 'worker' or info['State'].get('Health', {}).get('Status') == 'healthy'):
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError('RECOVERY_HEALTH_TIMEOUT')
                time.sleep(2)
    if original['services']['worker']['running']:
        deadline = time.monotonic()+120
        while True:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise TimeoutError('WORKER_READY_TIMEOUT')
            result = bounded_capture(['docker', 'exec', original['services']['worker']['id'],
                'python', '/app/docker/runtime.py', 'worker-status'], min(30, remaining), evidence)
            if result.returncode == 0:
                break
            time.sleep(min(2, max(0, deadline-time.monotonic())))
    ready = bounded_capture(['curl', '--connect-timeout', '3', '--max-time', '5', '-sS', '-o', '/dev/null',
        '-w', '%{http_code}', 'http://127.0.0.1:8000/health/ready'], 8, evidence)
    if ready.returncode or ready.stdout.strip() != b'200':
        raise RuntimeError('RECOVERY_API_NOT_READY')
    active = bounded_capture(['systemctl', 'is-active', 'docker', 'caddy', 'srv-daesingo.mount'], 10, evidence)
    if active.returncode or active.stdout.split() != [b'active']*3:
        raise RuntimeError('SYSTEM_SERVICES_CHANGED')
    snapshot(True)
    if not receipt.exists():
        record(receipt, {'owner': owner, 'manifest_sha256': manifest_sha256, 'status': 'PASS'})
    # receipt 직후 crash도 재진입 시 identity를 확인한 뒤 exact lock 해제를 마친다.
    if marker.parent.exists():
        if ({p.name for p in marker.parent.iterdir()} != {marker.name}
                or json.loads(marker.read_text()) != {'owner': owner, 'evidence': str(evidence)}):
            raise ValueError('LOCK_CHANGED_NO_UNLOCK')
        marker.unlink()
        marker.parent.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('run', 'restore', 'unit'))
    parser.add_argument('--home', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--operation-root', default='/opt/daesingo')
    parser.add_argument('--manual-recovery-id', help='자동 복구창 소진 뒤 운영자가 명시한 새 유한 복구창 ID')
    args = parser.parse_args()
    os.umask(0o077)
    if args.manual_recovery_id is not None and args.mode != 'restore':
        raise ValueError('MANUAL_WINDOW_RESTORE_ONLY')
    if args.mode == 'unit':
        print(unit_text(args.home, args.manifest_sha256, args.operation_root), end='')
        return 0
    if args.mode == 'restore':
        # 외부 timeout/수동 실행 모두 유한하다. 실패 시 잠금을 유지한다.
        _, evidence, _, _, _, _ = bindings(args.home, args.manifest_sha256, args.operation_root)
        remaining = recovery_remaining(evidence, args.manifest_sha256, manual_id=args.manual_recovery_id)
        signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('RECOVERY_LIMIT')))
        signal.alarm(max(1, remaining-5))
        restore(args.home, args.manifest_sha256, args.operation_root)
        emit('ORIGINAL_SERVICES_VERIFIED_LOCK_RELEASED')
        return 0
    from recording_ec2_host import approval_gate, previous_stage, protected_file
    home, evidence, source, manifest, original, marker = bindings(args.home, args.manifest_sha256, args.operation_root)
    if (manifest['config'].get('full_search_prepare_budget_ms') != 900000
            or manifest['config'].get('full_probe_mode') != 'coarse_270p_stop_before_send'):
        raise ValueError('EXPLICIT_COARSE_MEASUREMENT_REQUIRED')
    if json.loads(marker.read_text()) != {'owner': home.name, 'evidence': str(evidence)}:
        raise ValueError('EXACT_OWNED_LOCK_REQUIRED')
    approval = json.loads(protected_file(evidence/'maintenance-approved.private.json').read_text())
    approval_gate(approval, home.name, hashlib.sha256((evidence/'operational-snapshot.private.json').read_bytes()).hexdigest())
    if approval['not_after_unix']-time.time() < WINDOW_REQUIRED:
        raise ValueError('FULL_AND_RECOVERY_WINDOW_REQUIRED')
    previous_stage(evidence, 'full')
    if (evidence/'session-outcome.private.json').exists() or (evidence/'full-result.private.json').exists():
        raise ValueError('ATTEMPT_CLOSED_NEW_OWNER_REQUIRED')
    install_handlers()
    common = ['--home', str(home), '--manifest-sha256', args.manifest_sha256,
              '--operation-root', args.operation_root]
    host = [sys.executable, '-B', str(source/'scripts/recording_ec2_host.py'), '--source', str(source),
            '--evidence', str(evidence), '--owner', home.name, '--manifest-sha256', args.manifest_sha256,
            '--ops-root', args.operation_root,
            '--stage', 'full', '--fixture', str(home/'fixture'), '--inputs', str(home/'inputs')]
    recovery = [sys.executable, '-B', str(source/'scripts/recording_probe_session.py'), 'restore', *common]
    result = run_commands(host, recovery, evidence)
    emit(result['status'])
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
