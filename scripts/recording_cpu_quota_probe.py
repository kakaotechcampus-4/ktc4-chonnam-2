"""Recording 격리 실험의 계측 부품. 자체적으로 Docker·DB·미디어를 실행하지 않는다.

PhaseObserver의 collect는 runner/DB 실제 leaf cgroup을 각각 읽는 callback이다.
호출자는 상위 cgroup·mount·quota·정확성·자원 gate를 별도로 확인해야 한다.
합성 controls는 실제 성능 결과가 아니다. 이 모듈은 원문 argv를 기록하지 않는다.
"""
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
import time


REQUIRED = {'usage_usec', 'user_usec', 'system_usec', 'nr_periods', 'nr_throttled', 'throttled_usec'}
ARMS = ('A1', 'B', 'A2')


def counters(text):
    result = {}
    for line in text.splitlines():
        key, value = line.split()
        if key in result or not value.isdecimal():
            raise ValueError('CPU_COUNTER_INVALID')
        result[key] = int(value)
    return result


def read_cgroup(root):
    """실제 지원 필드만 수집한다. 경로는 반환하지 않으며 필수 CPU 누락은 실패다."""
    started = time.monotonic()
    root = Path(root)
    identity = root.stat()
    stat = counters((root / 'cpu.stat').read_text())
    if not REQUIRED <= stat.keys():
        raise ValueError('CPU_COUNTER_MISSING')
    result = {'identity': [identity.st_dev, identity.st_ino], 'cpu_stat': stat,
        'cpu_max': (root / 'cpu.max').read_text().strip(),
        'cpuset': (root / 'cpuset.cpus.effective').read_text().strip()}
    for filename, name in [('memory.current', 'memory_current'), ('memory.peak', 'memory_peak')]:
        path = root / filename
        result[name] = int(path.read_text()) if path.exists() else None
    path = root / 'memory.events'
    result['memory_events'] = counters(path.read_text()) if path.exists() else None
    if root.stat().st_ino != identity.st_ino:
        raise ValueError('CPU_SCOPE_CHANGED')
    result['sample_start_monotonic_sec'] = started
    result['sample_end_monotonic_sec'] = time.monotonic()
    return result


def counter_delta(before, after):
    for key in ('identity', 'cpu_max', 'cpuset'):
        if before[key] != after[key]:
            raise ValueError('CPU_SCOPE_CHANGED')
    a, b = before['cpu_stat'], after['cpu_stat']
    if a.keys() != b.keys() or not REQUIRED <= a.keys():
        raise ValueError('CPU_COUNTER_MISSING')
    if any(type(a[k]) is not int or type(b[k]) is not int or min(a[k], b[k]) < 0 or b[k] < a[k] for k in a):
        raise ValueError('CPU_COUNTER_RESET_OR_INVALID')
    return {k: b[k] - a[k] for k in a}


def classify_argv(argv):
    """옵션의 고정 의미만 공개한다. 경로·필터 문자열·원문 argv는 반환하지 않는다."""
    tool = PurePosixPath(argv[0]).name if argv else 'unknown'
    category = 'unknown'
    if tool == 'ffprobe':
        if '-show_frames' in argv and '-show_packets' in argv:
            category = 'frame_packet_probe'
        elif '-show_packets' in argv:
            category = 'packet_probe'
        elif '-show_frames' in argv:
            category = 'source_frame_probe' if PurePosixPath(argv[-1]).is_relative_to('/inputs') else 'output_frame_probe'
        else:
            category = 'metadata_probe'
    elif tool == 'ffmpeg':
        pairs = set(zip(argv, argv[1:]))
        if ('-f', 'concat') in pairs:
            category = 'concat'
        elif '-vf' in argv:
            category = 'encode'
        elif ('-f', 'null') in pairs and '-xerror' in argv:
            category = 'strict_decode'
        elif ('-c:v', 'copy') in pairs or ('-c', 'copy') in pairs:
            category = 'remux'
    return {'tool': tool if tool in ('ffmpeg', 'ffprobe') else 'unknown', 'category': category,
        'strict_errors': '-xerror' in argv, 'stream_copy': 'copy' in argv}


def children_cpu():
    """Linux에서 회수된 자식 누적 rusage만 반환한다. 실행 중 자식 peak의 대용이 아니다."""
    try:
        import resource
    except ImportError:
        return None
    value = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {'user_sec': value.ru_utime, 'system_sec': value.ru_stime}


class PhaseObserver:
    def __init__(self, collect, events, *, children=children_cpu, clock=time.monotonic):
        self.collect, self.events, self.children, self.clock = collect, events, children, clock
        self.stack = []

    def snapshot(self, event):
        start = self.clock()
        try:
            result = self.collect()
            if set(result) != {'runner', 'db'}:
                raise ValueError('CPU_ACTORS_REQUIRED')
            for value in result.values():
                counter_delta(value, value)
            return result
        finally:
            event['collector_wall_sec'] += self.clock() - start

    @contextmanager
    def phase(self, name):
        # 이름은 기존 하네스가 소유하는 고정 phase다. 임의 argv/경로를 넣지 않는다.
        event = {'id': len(self.events), 'phase': name,
            'parent_id': self.stack[-1] if self.stack else None, 'status': 'MEASUREMENT_FAILED',
            'collector_wall_sec': 0.0, 'children_cpu_delta': None}
        self.events.append(event)
        before = self.snapshot(event)
        child_before = self.children()
        start = self.clock()
        event['start_monotonic_sec'] = start
        self.stack.append(event['id'])
        failed = False
        try:
            yield event
        except BaseException:
            failed = True
            raise
        finally:
            event['wall_sec'] = self.clock() - start
            self.stack.pop()
            try:
                child_after = self.children()
                after = self.snapshot(event)
                event['before'], event['after'] = before, after
                event['delta'] = {actor: counter_delta(before[actor], after[actor]) for actor in before}
                if child_before is not None and child_after is not None:
                    event['children_cpu_delta'] = {k: child_after[k]-child_before[k] for k in child_before}
                event['status'] = 'FAIL' if failed else 'PASS'
            except BaseException:
                event['status'] = 'MEASUREMENT_FAILED'
                # 원래 제품 예외를 보존하고 계측 실패를 기록한다.
                if not failed:
                    raise


@contextmanager
def observe_measurements(target, observer):
    """기존 phase 경계를 감싸고 성공·실패·중단 모두 원복한다. 단일 실행 전용이다."""
    original = target.measure
    @contextmanager
    def measured(events, name):
        with observer.phase(name), original(events, name) as event:
            yield event
    target.measure = measured
    try:
        yield
    finally:
        target.measure = original


def arm_cpu_args(arm):
    if arm not in ARMS:
        raise ValueError('CPU_ARM_INVALID')
    return ['--cpus', '2.0' if arm == 'B' else '1.5', '--cpuset-cpus', '0,1']


def run_sequence(execute, cleanup):
    """연결용 유한 순서 control. callback은 새 target 검증/실행과 정리 검증을 담당한다.

    실제 Docker supervisor가 아니며 자원 gate를 우회하지 않는다. 실행·계측·정리
    중 어느 하나라도 True가 아니거나 예외면 다음 arm을 호출하지 않는다.
    """
    for arm in ARMS:
        try:
            if execute(arm, arm_cpu_args(arm)) is not True:
                raise RuntimeError('CPU_ARM_STOP')
        finally:
            if cleanup(arm) is not True:
                raise RuntimeError('CPU_CLEANUP_STOP')


def removable(name, allowed_names, owner, labels, users):
    """삭제 실행이 아닌 선행조건이다. 실제 삭제 직전 다시 조회해야 한다."""
    return (isinstance(owner, str) and bool(owner.strip()) and name in allowed_names
            and 'owner' in labels and labels['owner'] == owner
            and isinstance(users, (list, tuple, set)) and not users)
