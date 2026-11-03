"""Finite offline real-media probe: current Recording -> committed chunks -> detached Search.

Only for an owned internal-network Linux container. No authenticated SDK, HTTP,
payload logging, operational schema or original-media writes. Legacy runner helpers
are reused for diagnostics only; its run() and legacy read path are never called.
"""
import argparse
from contextlib import contextmanager, nullcontext
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import re
from types import SimpleNamespace
import threading
import time
import traceback

import recording_capacity_probe as diag
from recording_probe_budget import ProbeBudget


@dataclass(frozen=True)
class Experiment:
    """실험 process에만 주입하는 유한 예산. 운영 config를 읽거나 쓰지 않는다."""
    experiment_id: str
    max_output_bytes: int
    max_duration_ms: int
    run_timeout_sec: int
    resource_profile: str = 'legacy'

    @classmethod
    def from_mapping(cls, values):
        required = set(cls.__dataclass_fields__) - {'resource_profile'}
        if not isinstance(values, dict) or set(values) not in (required, required | {'resource_profile'}):
            raise ValueError('EXPERIMENT_KEYS_REQUIRED')
        name = values['experiment_id']
        if not isinstance(name, str) or re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', name) is None:
            raise ValueError('EXPERIMENT_ID_INVALID')
        try:
            budget = ProbeBudget.from_profile(values.get('resource_profile', 'legacy'))
            budget.validate_experiment(values['max_output_bytes'], values['max_duration_ms'], values['run_timeout_sec'])
        except ValueError:
            raise ValueError('EXPERIMENT_FINITE_BUDGET_REQUIRED') from None
        return cls(**values)


def load_experiment(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('EXPERIMENT_DUPLICATE_KEY')
            result[key] = value
        return result
    return Experiment.from_mapping(json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique))


def validate_selection(first, count, seconds, experiment):
    if any(type(v) is not int for v in (first, count, seconds)):
        raise ValueError('INPUT_PROFILE_INVALID')
    if experiment is None:
        valid = (first, count, seconds) in ((2, 1, 10), (2, 2, 100), (1, 3, 240))
    else:
        valid = first == 1 and 1 <= count <= 15 and 240 <= seconds <= 1200 and seconds * 1000 <= experiment.max_duration_ms
    if not valid:
        raise ValueError('INPUT_PROFILE_REQUIRES_EXPLICIT_FINITE_EXPERIMENT')


def recording_config(experiment):
    return {'DAESINGO_RECORDING_ANALYSIS_PROFILE_REF': 'aws-e2e-v1',
        'DAESINGO_RECORDING_ANALYSIS_HEIGHT': '480', 'DAESINGO_RECORDING_ANALYSIS_PRESET': 'veryfast',
        'DAESINGO_RECORDING_ANALYSIS_CRF': '23',
        'DAESINGO_RECORDING_ANALYSIS_MAX_BYTES': str(experiment.max_output_bytes if experiment else 50331648),
        'DAESINGO_RECORDING_ANALYSIS_MAX_DURATION_MS': str(experiment.max_duration_ms if experiment else 240000)}


def experiment_budget(experiment):
    return ProbeBudget.from_profile(experiment.resource_profile if experiment else 'legacy')


def logical_coverage(placements, seconds):
    offset = Decimal(0)
    for item in placements:
        start, end = Decimal(str(item['start'])), Decimal(str(item['end']))
        if not start.is_finite() or not end.is_finite() or start != offset or end <= start:
            raise ValueError('PLACEMENT_GAP_OVERLAP_OR_ORDER')
        offset = end
    if offset < seconds:
        raise ValueError('PLACEMENT_INSUFFICIENT_COVERAGE')
    return {'requested_sec': seconds, 'placed_end_sec': str(offset), 'logical_gap_overlap_count': 0,
            'capture_continuity': 'UNKNOWN', 'order_basis': 'protected_manifest_explicit_placement'}


def exact_frame_summary(payload):
    summary = diag.frame_summary(payload)
    frames = payload.get('frames', [])
    if frames:
        summary.update(first_pts_ticks=frames[0].get('best_effort_timestamp'),
            last_pts_ticks=frames[-1].get('best_effort_timestamp'),
            last_duration_ticks=frames[-1].get('duration', frames[-1].get('pkt_duration')))
    return summary


@contextmanager
def tool_measure(events, name, output=None):
    with diag.measure(events, name) as event:
        try:
            yield event
        finally:
            if output is not None:
                try:
                    event['output_bytes'] = output.stat().st_size
                except OSError:
                    event['output_size_available'] = False


def measure_search_encode(events, encode, source, output, **kwargs):
    """후속 guard/cleanup이 거부해도 변환 직후 bytes를 복사 없이 보존한다."""
    with tool_measure(events, 'search_reencode', Path(output)):
        return encode(source, output, **kwargs)


@dataclass(frozen=True)
class CoarseOverride:
    """Owner가 요청한 단일 후보만 허용한다. 운영 설정 API가 아니다."""
    height: int
    crf: int

    def __post_init__(self):
        if type(self.height) is not int or type(self.crf) is not int or (self.height, self.crf) != (270, 28):
            raise ValueError('COARSE_EXPERIMENT_270_CRF28_REQUIRED')

    @classmethod
    def from_mapping(cls, value):
        if not isinstance(value, dict) or set(value) != {'height', 'crf'}:
            raise ValueError('COARSE_EXPERIMENT_KEYS_REQUIRED')
        return cls(**value)


@contextmanager
def coarse_encode_override(media_module, setting, report):
    """명시적 Coarse 준비 중 현재 thread의 정확한 encode만 바꾼다.

    제품 argv builder·deadline·seek·필터는 재사용한다. subprocess hook은
    해당 encode 호출 동안만 설치하고 Fine/다른 도구에는 전달하지 않는다.
    """
    CoarseOverride.from_mapping(asdict(setting))
    original_encode = media_module._run_ffmpeg_encode
    original_subprocess = media_module._run_subprocess
    thread_id = threading.get_ident()
    report['coarse_override'] = asdict(setting)
    report['coarse_commands'] = []

    def encode(source, output, **kwargs):
        if (threading.get_ident() != thread_id or Path(output).name != 'coarse.mp4'
                or kwargs.get('start_sec') is not None or kwargs.get('end_sec') is not None):
            return original_encode(source, output, **kwargs)
        if set(kwargs) != {'fps', 'max_height', 'deadline'} or kwargs['fps'] != 2.0 or kwargs['max_height'] != 360:
            raise ValueError('COARSE_EXPERIMENT_CALL_DRIFT')
        original_run = media_module._run_subprocess
        expected_filter = "fps=2.0,scale=-2:'min(270,ih)',setpts=(PTS-STARTPTS)*2.0,fps=1"

        def run(argv, deadline, **options):
            if threading.get_ident() != thread_id or argv[-1] != str(output):
                return original_run(argv, deadline, **options)
            expected = [media_module._ffmpeg_path(), '-y', '-i', str(source), '-vf', expected_filter,
                        '-c:v', 'libx264', '-an', '-movflags', '+faststart', str(output)]
            if argv != expected or deadline is not kwargs['deadline'] or options:
                raise ValueError('COARSE_EXPERIMENT_ARGV_DRIFT')
            actual = [*argv[:-1], '-crf', str(setting.crf), argv[-1]]
            safe = [('<source>' if item == str(source) else '<coarse>' if item == str(output)
                     else Path(item).name if index == 0 else item) for index, item in enumerate(actual)]
            record = {'argv': safe, 'fps_origin': 2.0, 'playback_speed': 0.5}
            report['coarse_commands'].append(record)
            result = original_run(actual, deadline)
            match = re.search(rb'\bcrf=([0-9.]+)', result.stderr or b'')
            record['encoder_reported_crf'] = float(match[1]) if match else 'UNKNOWN'
            return result

        media_module._run_subprocess = run
        try:
            return original_encode(source, output, **{**kwargs, 'max_height': setting.height})
        finally:
            media_module._run_subprocess = original_run

    media_module._run_ffmpeg_encode = encode
    try:
        yield
    finally:
        media_module._run_ffmpeg_encode = original_encode
        report['coarse_override_restored'] = media_module._run_ffmpeg_encode is original_encode
        report['coarse_subprocess_restored'] = media_module._run_subprocess is original_subprocess


def inspect_coarse_output(media_module, media, deadline):
    """식별자/RAW 없이 실제 출력 stream과 frame 시각을 확인한다."""
    result = media_module._run_subprocess([media_module._ffprobe_path(), '-v', 'error',
        '-show_streams', '-show_format', '-show_frames', '-show_entries',
        'stream=codec_type,width,height,time_base,r_frame_rate:format=duration:'
        'frame=best_effort_timestamp,best_effort_timestamp_time,duration,duration_time,pkt_duration,pkt_duration_time',
        '-of', 'json', str(media.path)], deadline, capture_stdout=True)
    if result.returncode:
        raise RuntimeError('COARSE_OUTPUT_PROBE_FAILED')
    payload = json.loads(result.stdout)
    streams = payload['streams']
    return {'streams': streams, 'format_duration_sec': float(payload['format']['duration']),
        'frames': exact_frame_summary(payload), 'origin_start_sec': media.origin_start_sec,
        'origin_end_sec': media.origin_end_sec, 'playback_speed': media.playback_speed}


def metadata_differences(before, after, path=''):
    """Only field paths/types/numbers; never expose IDs, filenames or payload text."""
    if isinstance(before, dict) and isinstance(after, dict):
        return [difference for key in sorted(before.keys() | after.keys())
                for difference in metadata_differences(before.get(key), after.get(key),
                    path + ('.' if path else '') + key)]
    if isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            return [{'path': path, 'before_type': 'list', 'after_type': 'list',
                     'before_length': len(before), 'after_length': len(after)}]
        return [difference for index, (a, b) in enumerate(zip(before, after))
                for difference in metadata_differences(a, b, f'{path}[{index}]')]
    if before == after and type(before) is type(after):
        return []
    result = {'path': path, 'before_type': type(before).__name__, 'after_type': type(after).__name__}
    for name, value in (('before', before), ('after', after)):
        if type(value) in (int, float, bool) or value is None:
            result[name] = value
            if type(value) is float:
                result[name + '_hex'] = value.hex()
        else:
            result[name + '_redacted'] = True
    return [result]


class BoundedView:
    """Same detached file; no whole-stream bytes or replacement BytesIO."""
    def __init__(self, stream):
        self.stream, self.max_read = stream, 0

    def read(self, size=-1):
        if not 0 < size <= 65536:
            raise ValueError('BOUNDED_READ_REQUIRED')
        self.max_read = max(self.max_read, size)
        return self.stream.read(size)

    def __getattr__(self, name):
        return getattr(self.stream, name)


def verify_stream(stream, length, digest):
    h, count = hashlib.sha256(), 0
    stream.seek(0)
    while block := stream.read(65536):
        count += len(block)
        if count > length:
            raise ValueError('STREAM_IDENTITY_MISMATCH')
        h.update(block)
    if count != length or h.hexdigest() != digest:
        raise ValueError('STREAM_IDENTITY_MISMATCH')
    stream.seek(0)


def require_detached(writer, readers, checkedout):
    if not readers or writer in readers or checkedout != 0:
        raise ValueError('DETACHED_CONNECTION_REQUIRED')


@contextmanager
def egress_fence(db_ip):
    import httpx
    connect, connect_ex = socket.socket.connect, socket.socket.connect_ex
    send, async_send = httpx.Client.send, httpx.AsyncClient.send
    counts = {'external_socket_attempts': 0, 'http_send_attempts': 0, 'allowed_db_connections': 0}

    def checked(original):
        def call(sock, address):
            if not isinstance(address, tuple) or address[:2] != (db_ip, 3306):
                counts['external_socket_attempts'] += 1
                raise RuntimeError('EGRESS_BLOCKED')
            counts['allowed_db_connections'] += 1
            return original(sock, address)
        return call

    def blocked(*args, **kwargs):
        counts['http_send_attempts'] += 1
        raise RuntimeError('HTTP_SEND_BLOCKED')

    async def async_blocked(*args, **kwargs):
        counts['http_send_attempts'] += 1
        raise RuntimeError('HTTP_SEND_BLOCKED')

    socket.socket.connect, socket.socket.connect_ex = checked(connect), checked(connect_ex)
    httpx.Client.send, httpx.AsyncClient.send = blocked, async_blocked
    try:
        # Negative controls exercise both C socket entry wrappers without a send.
        with socket.socket() as sock:
            for operation in (sock.connect, sock.connect_ex):
                try:
                    operation(('192.0.2.1', 443))
                except RuntimeError:
                    pass
                else:
                    raise RuntimeError('EGRESS_CONTROL_FAILED')
        try:
            blocked()
        except RuntimeError:
            pass
        counts.update(external_socket_attempts=0, http_send_attempts=0)
        yield counts
    finally:
        socket.socket.connect, socket.socket.connect_ex = connect, connect_ex
        httpx.Client.send, httpx.AsyncClient.send = send, async_send


def temp_usage(root):
    """Logical bytes, including unlinked open files in this process, deduplicated."""
    files = {}
    named = diag.tree_bytes(root)
    for path in root.rglob('*'):
        try:
            if path.is_file():
                s = path.stat()
                files[(s.st_dev, s.st_ino)] = s.st_size
        except FileNotFoundError:
            pass
    fd_root = Path('/proc/self/fd')
    if fd_root.exists():
        for fd in fd_root.iterdir():
            try:
                target = os.readlink(fd)
                if target.startswith(str(root) + '/'):
                    s = fd.stat()
                    files[(s.st_dev, s.st_ino)] = s.st_size
            except FileNotFoundError:
                pass
    return {'named_bytes': named, 'including_open_unlinked_bytes': sum(files.values())}


class Sampler:
    def __init__(self, root, report, marker, budget=None):
        self.root, self.report, self.marker = root, report, marker
        self.budget = budget or ProbeBudget.from_profile('legacy')
        self.stop = threading.Event()
        self.error = None

    def start(self):
        self.thread = threading.Thread(target=self.sample, daemon=True)
        self.thread.start()

    def collect(self):
        import psutil
        process = psutil.Process()
        children = []
        for child in process.children(recursive=True):
            try:
                cpu = child.cpu_times()
                children.append({'pid': child.pid, 'name': child.name(), 'rss_bytes': child.memory_info().rss,
                                 'cpu_sec': cpu.user + cpu.system})
            except psutil.NoSuchProcess:
                pass
        cpu = process.cpu_times()
        return {'monotonic': time.monotonic(), 'phase': self.report['phase'],
            'runner_rss_bytes': process.memory_info().rss, 'runner_cpu_sec': cpu.user + cpu.system,
            'children': children, 'cgroup_bytes': int(Path('/sys/fs/cgroup/memory.current').read_text()),
            **temp_usage(self.root)}

    def sample(self):
        while not self.stop.is_set():
            try:
                sample = self.collect()
                self.report['samples'].append(sample)
                diag.emit({'kind': 'sample', **sample})
                if (sample['cgroup_bytes'] >= self.budget.runner_soft_mib * 1024**2
                        or sample['including_open_unlinked_bytes'] >= self.budget.temp_soft_mib * 1024**2):
                    raise RuntimeError('SOFT_RESOURCE_STOP')
            except BaseException as error:
                self.error = type(error).__name__
                self.marker.write_text('SAMPLER_OR_RESOURCE_STOP')
                return
            self.stop.wait(.2)

    def check(self):
        if self.error:
            raise RuntimeError('SAMPLER_OR_RESOURCE_STOP')

    def close(self):
        self.stop.set()
        self.thread.join(3)
        if self.thread.is_alive():
            raise RuntimeError('SAMPLER_CLOSE_FAILED')


@contextmanager
def command_metrics(report):
    import pymysql.connections
    cls, result_cls = pymysql.connections.Connection, pymysql.connections.MySQLResult
    command, row = cls._execute_command, result_cls._read_row_from_packet
    read_packet = cls._read_packet

    def observed_command(conn, code, sql):
        n = len(sql.encode(conn.encoding) if isinstance(sql, str) else (sql or b'')) + 1
        entry = {'phase': report['phase'], 'command_bytes': n}
        report['driver'].append(entry)
        diag.emit({'kind': 'driver_command', **entry})
        return command(conn, code, sql)

    def observed_row(result, packet):
        entry = {'phase': report['phase'], 'row_packet_bytes': len(packet._data)}
        report['driver'].append(entry)
        diag.emit({'kind': 'row_packet', **entry})
        return row(result, packet)

    def observed_packet(conn, *args, **kwargs):
        packet = read_packet(conn, *args, **kwargs)
        entry = {'phase': report['phase'], 'result_packet_bytes': len(packet._data)}
        report['driver'].append(entry)
        diag.emit({'kind': 'result_packet', **entry})
        return packet

    cls._execute_command, result_cls._read_row_from_packet = observed_command, observed_row
    cls._read_packet = observed_packet
    try:
        yield
    finally:
        cls._execute_command, result_cls._read_row_from_packet = command, row
        cls._read_packet = read_packet


def request_boundary(cfg, media, source, timeline_id, deadline, report, events, check):
    from daesingo.search import provider as provider_module
    from daesingo.search.sources import ResolvedAnalysisSource
    from daesingo.search.runs import ContractRef
    provider = provider_module.GeminiProvider.__new__(provider_module.GeminiProvider)
    provider._config = cfg
    report['sdk_entry_count'] = 0

    def stop(**kwargs):
        report['sdk_entry_count'] += 1
        raise diag.StopBeforeSend()

    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        with_raw_response=SimpleNamespace(parse=stop))))
    original_url, original_dumps = provider_module._video_data_url, provider_module.json.dumps

    def url(*args, **kwargs):
        check()
        with diag.measure(events, 'search_base64'):
            value = original_url(*args, **kwargs)
            report['base64_bytes'] = len(value) - value.index(',') - 1
            report['search_full_media_bytes_read'] = media.byte_size
            return value

    def dumps(*args, **kwargs):
        check()
        with diag.measure(events, 'search_guard_json'):
            value = original_dumps(*args, **kwargs)
            if not kwargs.get('ensure_ascii', True) or not value.isascii():
                raise RuntimeError('EXPECTED_ASCII_GUARD_JSON')
            report['guard_json_bytes'] = len(value)
            return value

    provider_module._video_data_url, provider_module.json.dumps = url, dumps
    try:
        report['request_guard'] = 'FAIL'
        with diag.measure(events, 'search_request_boundary'):
            try:
                provider.search_coarse(provider_module.CoarseRequest(
                    source=ResolvedAnalysisSource(ContractRef(kind='analysis_source', ref=source.analysis_source_ref),
                        source.duration_sec, timeline_id), event_types=(), media=media, deadline=deadline))
            except diag.StopBeforeSend:
                report['request_guard'] = 'PASS_STOP_BEFORE_SEND'
        diag.require_sdk_stop(report)
        if report['sdk_entry_count'] != 1:
            raise RuntimeError('SDK_ENTRY_COUNT_MISMATCH')
    finally:
        provider_module._video_data_url, provider_module.json.dumps = original_url, original_dumps


def run(args):
    experiment = load_experiment(args.experimental_config) if getattr(args, 'experimental_config', None) else None
    validate_selection(args.first, args.count, args.seconds, experiment)
    import resource
    import sqlalchemy as sa
    import daesingo.recording
    from daesingo.recording import RecordingService, LocalAnalysisMaterializer, TransactionalRecordingRepository
    from daesingo.recording.factory import RecordingSettings, build_recording_service
    from daesingo.recording.mysql_repository import MySQLRecordingRepository
    from daesingo.recording.observability import capture_materialization
    from daesingo.search import media as search_media
    from daesingo.search.config import GeminiSearchConfig
    from daesingo.search.execution import RunDeadline
    from alembic import command as migration
    from alembic.config import Config
    import subprocess
    import tempfile

    if os.name != 'posix' or os.environ.get('REAL_MEDIA_RECHECK_ISOLATED') != 'owned-internal-20261103':
        raise RuntimeError('ISOLATED_CONTAINER_REQUIRED')
    if any(os.environ.get(k) for k in ('GEMINI_API_KEY', 'ELICE_ML_API_KEY', 'OPENAI_API_KEY')):
        raise RuntimeError('CREDENTIAL_ENV_FORBIDDEN')
    if not str(Path(daesingo.recording.__file__).resolve()).startswith('/repo/src/'):
        raise RuntimeError('CURRENT_CHECKOUT_REQUIRED')
    output, work = Path(args.output), Path('/work')
    if output.exists():
        raise RuntimeError('EVIDENCE_EXISTS')
    tempfile.tempdir = str(work)
    report = {'schema': 'real-media-recheck/v1', 'utc': datetime.now(timezone.utc).isoformat(),
        'code_sha': args.code_sha, 'image_id': args.image_id, 'phase': 'setup', 'status': 'FAIL',
        'events': [], 'driver': [], 'samples': [], 'frames': [], 'parts': [],
        'recording': 'NOT_REACHED', 'db_store': 'NOT_REACHED', 'db_read': 'NOT_REACHED',
        'search_media': 'NOT_REACHED', 'request_guard': 'NOT_REACHED',
        'sdk_body': 'NOT_RUN', 'HTTP_wire': 'NOT_RUN', 'provider_calls': 0, 'case_web': 'NOT_RUN',
        'requested_sec': args.seconds, 'experiment': asdict(experiment) if experiment else None,
        'tool_timeout_sec': 120, 'runner_timeout_sec': experiment.run_timeout_sec if experiment else 900,
        'provenance': 'NOT_REACHED', 'detached_strict_decode': 'NOT_REACHED',
        'db_commit': 'NOT_REACHED', 'prepared_rollback': 'NOT_REACHED'}
    report['sdk_entry_count'] = 0
    events = report['events']
    diag.JOURNAL = diag.Journal(output.with_suffix('.events.jsonl'))
    budget = experiment_budget(experiment)
    report['resource_budget'] = asdict(budget)
    report['resource_budget_module_sha256'] = hashlib.sha256(Path(__import__('recording_probe_budget').__file__).read_bytes()).hexdigest()
    sampler = Sampler(work, report, output.with_suffix('.abort'), budget=budget)
    engine = conn = service = detached = None
    cleanup_errors = []
    held = {}

    @contextmanager
    def phase(name):
        sampler.check()
        report['phase'] = name
        with diag.measure(events, name) as event:
            yield event

    def clean(name, operation):
        try:
            operation()
        except BaseException as error:
            cleanup_errors.append({'phase': name, 'type': type(error).__name__})

    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('FINITE_RUN_TIMEOUT')))
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(RuntimeError('SUPERVISOR_STOP')))
    signal.alarm(report['runner_timeout_sec'])
    sampler.start()
    records = []
    try:
        manifest = json.loads(Path(args.manifest).read_text(encoding='utf-8-sig'))
        records = manifest['files'][args.first-1:args.first-1+args.count]
        with egress_fence(args.db_host) as network_counts, command_metrics(report):
            report['network_counts'] = network_counts
            if len(records) != args.count:
                raise ValueError('INPUT_SELECTION_MISMATCH')
            report['input_ids'] = [r['fixture_id'] for r in records]
            report['tools'] = {}
            for tool in ('ffmpeg', 'ffprobe'):
                binary = Path(__import__('shutil').which(tool))
                version = subprocess.check_output([str(binary), '-version'], text=True).splitlines()[0]
                if not version.startswith(tool + ' version 8.1 '):
                    raise RuntimeError('EXPECTED_8_1_BUILD_REQUIRED')
                with binary.open('rb') as binary_stream:
                    report['tools'][tool] = {'version': version, 'sha256': hashlib.file_digest(binary_stream, 'sha256').hexdigest()}
            subprocess.run(['python', '/repo/docker/runtime.py', 'media-preflight'], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            # The anonymous stream accounting control must run on Linux, before encode.
            with tempfile.TemporaryFile(dir=work) as control:
                control.write(b'x' * 4096)
                control.flush()
                if temp_usage(work)['including_open_unlinked_bytes'] < 4096:
                    raise RuntimeError('ANONYMOUS_TEMP_ACCOUNTING_FAILED')
            engine = sa.create_engine(sa.URL.create('mysql+pymysql', username='root', host=args.db_host,
                database=args.schema), hide_parameters=True, echo=False, pool_size=1, max_overflow=0,
                connect_args={'connect_timeout': 5, 'read_timeout': 30, 'write_timeout': 30})
            with engine.begin() as migrate_conn:
                config = Config('/repo/migrations/recording/alembic.ini')
                config.attributes['connection'] = migrate_conn
                migration.upgrade(config, 'head')
            conn = engine.connect()
            writer_id = conn.exec_driver_sql('SELECT CONNECTION_ID()').scalar_one()
            report['writer_connection_id'] = writer_id
            report['packet_bytes'] = conn.exec_driver_sql('SELECT @@session.max_allowed_packet').scalar_one()
            if report['packet_bytes'] != 67108864:
                raise ValueError('PACKET_BASELINE_REQUIRED')
            report['aborted_before'] = int(conn.exec_driver_sql("SHOW GLOBAL STATUS LIKE 'Aborted_clients'").one()[1])
            repo = MySQLRecordingRepository(conn, storage_root='/inputs', temp_root=work)
            publish = repo.add_prepared_media

            def observed_publish(media, content, **kwargs):
                report['db_store'] = 'FAIL'
                with diag.measure(events, 'db_publish'):
                    report['publish_model'] = media.model_dump(mode='json')
                    report['expected_sha256'] = hashlib.sha256(content).hexdigest()
                    report['final_bytes'] = len(content)
                    held['content'] = content  # reference to product bytes, no duplicate allocation
                    original_get = repo._get
                    def observed_get(kind, identity, **options):
                        stored = original_get(kind, identity, **options)
                        if kind in ('analysis_source', 'incident_clip') and stored is not None:
                            differences = metadata_differences(media.model_dump(mode='json'), stored['payload'])
                            report.setdefault('metadata_comparisons', []).append({
                                'locked': options.get('lock', False), 'differences': differences,
                                'model_equal': type(media).model_validate(stored['payload']) == media})
                            diag.emit({'kind': 'metadata_comparison', 'differences': differences})
                        return stored
                    repo._get = observed_get
                    try:
                        result = publish(media, content, **kwargs)
                    finally:
                        repo._get = original_get
                report['db_store'] = 'PASS_UNCOMMITTED'
                return result

            repo.add_prepared_media = observed_publish

            class ObservedMaterializer(LocalAnalysisMaterializer):
                def _probe(self, path, index=None):
                    value = super()._probe(path, index)
                    report['frames'].append({'role': 'source' if Path(path).is_relative_to('/inputs') else 'output',
                                             **exact_frame_summary(value)})
                    return value

                def _run(self, argv):
                    kind = 'probe' if Path(argv[0]).name == 'ffprobe' else (
                        'concat' if 'concat' in argv else 'encode' if '-vf' in argv else 'decode')
                    output = Path(argv[-1]) if kind in ('encode', 'concat') else None
                    with tool_measure(events, 'recording_tool_' + kind, output):
                        return super()._run(argv)

                def materialize(self, *a, **kw):
                    with diag.measure(events, 'individual_materialize') as event:
                        result = super().materialize(*a, **kw)
                        event['bytes'] = len(result.content)
                        report['parts'].append(len(result.content))
                        event['cumulative_part_bytes'] = sum(report['parts'])
                        event['exact_duration'] = str(result.frames[-1][0] + result.frames[-1][1])
                        event['timeline_start_sec'] = result.timeline_range.start_sec
                        event['timeline_end_sec'] = result.timeline_range.end_sec
                        return result

                def _materialize_many(self, inputs, profile_ref):
                    with diag.measure(events, 'chain_total'):
                        return super()._materialize_many(inputs, profile_ref)

            config = recording_config(experiment)
            report['recording_config'] = config
            report['config_sha256'] = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
            service = build_recording_service(repo, RecordingSettings.from_mapping(config), temp_root=work,
                materializer_factory=lambda profiles: ObservedMaterializer(profiles, temp_root=work, timeout_sec=120),
                case_id='real-media-recheck', analysis_checkpoint=sampler.check)
            service.__enter__()
            offset, placements = Decimal(0), []
            with phase('registration'):
                for r in records:
                    path = Path('/inputs') / r['filename']
                    diag.verify_stat(path, r)
                    registered = service.register_local_source(path, original_filename=r['fixture_id'], case_id='real-media-recheck')
                    local = repo.get_local_source(registered.source_asset.source_asset_ref)
                    if local.sha256 != r['sha256']:
                        raise ValueError('INPUT_HASH_MISMATCH')
                    stream = next(s for s in registered.media_streams if s.media_type == 'VIDEO')
                    if repo.get_local_stream_index(stream.media_stream_ref) != r['proposed_video_index']:
                        raise ValueError('SELECTED_STREAM_INDEX_MISMATCH')
                    end = offset + Decimal(str(registered.source_asset.duration_sec))
                    placements.append(dict(source_asset_ref=registered.source_asset.source_asset_ref,
                        timeline_start_sec=float(offset), timeline_end_sec=float(end), media_stream_ref=stream.media_stream_ref))
                    offset = end
                report['placements'] = [{'id': r['fixture_id'], 'start': p['timeline_start_sec'],
                    'end': p['timeline_end_sec'], 'video_index': r['proposed_video_index']} for r, p in zip(records, placements)]
                report['timeline_coverage'] = logical_coverage(report['placements'], args.seconds)
                timeline = service.create_relative_timeline_from_placements(placements)
                resolution = service.resolve_span(dict(timeline_id=timeline.timeline_id, revision=timeline.revision),
                    dict(start_sec=0, end_sec=args.seconds), media_stream_refs=[p['media_stream_ref'] for p in placements])
                report['resolution'] = resolution.model_dump(mode='json')
                if resolution.status != 'COMPLETE':
                    raise ValueError('COMPLETE_RESOLUTION_REQUIRED')
                conn.commit()
            report['recording'] = 'FAIL'
            with phase('recording_prepare'), capture_materialization() as traces:
                report['materialization_traces'] = traces
                source = service.prepare_analysis_source_from_resolution(resolution, 'aws-e2e-v1')
            report['recording'] = 'PASS'
            report['source'] = source.model_dump(mode='json')
            if ([r.ref for r in source.source_refs] != [s.source_asset_ref for s in resolution.spans]
                    or source.media_stream_refs != [s.media_stream_ref for s in resolution.spans]
                    or source.timeline_ref != resolution.timeline_ref or source.profile_ref != 'aws-e2e-v1'):
                raise ValueError('PROVENANCE_MISMATCH')
            report['provenance'] = 'PASS'
            report['service_retained_content_bytes'] = sum(len(value[1]) for value in service._local_analysis.values())
            with phase('db_commit'):
                report['db_commit'] = 'FAIL'
                conn.commit()
                report['db_commit'] = 'PASS'
                report['db_store'] = 'PASS_COMMITTED'
                rows = conn.exec_driver_sql('SELECT COUNT(*), SUM(OCTET_LENGTH(content)), MAX(OCTET_LENGTH(content)) FROM recording_media_chunk').one()
                report['chunk_rows'], report['chunk_bytes'], report['max_chunk_bytes'] = int(rows[0]), int(rows[1]), int(rows[2])
                if report['chunk_bytes'] != source.byte_size or report['max_chunk_bytes'] > 262144:
                    raise ValueError('CHUNK_ACCOUNTING_MISMATCH')
                if conn.exec_driver_sql("SELECT COUNT(*) FROM recording_entry WHERE kind='analysis_source' AND content IS NOT NULL").scalar_one():
                    raise ValueError('LEGACY_CONTENT_WRITE_UNEXPECTED')
                conn.commit()
            with phase('normal_prepared_rollback'):
                before_rows = conn.exec_driver_sql('SELECT COUNT(*) FROM recording_media_chunk').scalar_one()
                transient = source.model_copy(update={'analysis_source_ref': source.analysis_source_ref + '-rollback-control'})
                publish(transient, held.pop('content'), case_id='rollback-control')
                conn.rollback()
                if repo.get_analysis_source(transient.analysis_source_ref) is not None:
                    raise ValueError('ROLLBACK_LEFT_MEDIA')
                if conn.exec_driver_sql('SELECT COUNT(*) FROM recording_media_chunk').scalar_one() != before_rows:
                    raise ValueError('ROLLBACK_LEFT_CHUNKS')
                if conn.exec_driver_sql('SELECT CONNECTION_ID()').scalar_one() != writer_id or conn.invalidated:
                    raise ValueError('WRITER_CONNECTION_CHANGED')
                report['prepared_rollback'] = 'PASS_SAME_CONNECTION'
                conn.rollback()
            service.close()
            service = None
            conn.close()
            conn = None
            engine.dispose()
            read_ids = []

            def transaction(callback):
                with engine.begin() as read_conn:
                    read_ids.append(read_conn.exec_driver_sql('SELECT CONNECTION_ID()').scalar_one())
                    if read_conn.exec_driver_sql('SELECT @@session.max_allowed_packet').scalar_one() != 67108864:
                        raise ValueError('READER_PACKET_MISMATCH')
                    return callback(read_conn)

            facade = TransactionalRecordingRepository(transaction, storage_root='/inputs', temp_root=work)
            report['db_read'] = 'FAIL'
            with phase('fresh_physical_connection_read'):
                with RecordingService(facade) as reader:
                    fresh = reader.get_analysis_source(source.analysis_source_ref)
                    report['fresh_read_metadata_differences'] = metadata_differences(
                        source.model_dump(mode='json'), fresh.model_dump(mode='json'))
                    if fresh != source:
                        raise ValueError('FRESH_METADATA_MISMATCH')
                    report['fresh_read_numeric'] = {
                        name: {'before': before, 'after': after, 'before_type': type(before).__name__,
                               'after_type': type(after).__name__, 'before_hex': before.hex(), 'after_hex': after.hex()}
                        for name, before, after in (
                            ('duration_sec', source.duration_sec, fresh.duration_sec),
                            ('timeline_range.end_sec', source.timeline_range.end_sec, fresh.timeline_range.end_sec))}
                    opened = reader.open_analysis_source(source.analysis_source_ref)
                    detached = opened.stream
                    require_detached(writer_id, read_ids, engine.pool.checkedout())
                view = BoundedView(detached)
                verify_stream(view, source.byte_size, report['expected_sha256'])
                report['detached_stream_bytes'] = os.fstat(detached.fileno()).st_size
                report['reader_connection_ids'] = read_ids
                report['checkedout_after_read'] = engine.pool.checkedout()
                report['db_read'] = 'PASS_HASH_LENGTH_DETACHED'
            cfg = GeminiSearchConfig()
            with phase('detached_strict_decode'):
                # Reopen the anonymous file through the parent fd; no whole read or media copy.
                decoder = LocalAnalysisMaterializer({}, temp_root=work, timeout_sec=120)
                decoder._strict_decode(Path(f'/proc/{os.getpid()}/fd/{detached.fileno()}'))
                report['detached_strict_decode'] = 'PASS'
            report['search_config'] = {'source_cap': cfg.max_materialized_source_bytes,
                'media_cap': cfg.max_inline_media_bytes, 'request_cap': cfg.max_inline_request_bytes,
                'fingerprint': cfg.fingerprint, 'budget_ms': 150000}
            deadline = RunDeadline(time.monotonic, 150000)
            original_copy, original_encode = search_media._materialize, search_media._run_ffmpeg_encode

            def copy(*a, **kw):
                with diag.measure(events, 'search_source_copy') as event:
                    result = original_copy(*a, **kw)
                    event['bytes'] = result.actual_byte_size
                    if result.sha256 != report['expected_sha256']:
                        raise ValueError('SEARCH_SOURCE_HASH_MISMATCH')
                    return result

            def encode(*a, **kw):
                return measure_search_encode(events, original_encode, *a, **kw)

            search_media._materialize, search_media._run_ffmpeg_encode = copy, encode
            report['search_media'] = 'FAIL'
            try:
                with phase('search_prepare'), (coarse_encode_override(search_media, CoarseOverride(270, 28), report)
                        if getattr(args, 'coarse_270p_crf28', False) else nullcontext()):
                    with search_media.MediaPreparer(cfg).prepare_coarse(search_media.MediaInput(
                            view, 'video/mp4', source.byte_size, source.duration_sec), deadline) as media:
                        report['search_media'] = 'PASS'
                        report['search_media_bytes'] = media.byte_size
                        report['search_media_duration_sec'] = media.duration_sec
                        report['coarse_output'] = inspect_coarse_output(search_media, media, deadline)
                        with phase('search_request'):
                            request_boundary(cfg, media, source, timeline.timeline_id, deadline, report, events, sampler.check)
            finally:
                search_media._materialize, search_media._run_ffmpeg_encode = original_copy, original_encode
            report['max_stream_read'] = view.max_read
            detached.close()
            report['stream_closed'] = detached.closed
            detached = None
            with phase('db_final_health'):
                with engine.connect() as final_conn:
                    final_id = final_conn.exec_driver_sql('SELECT CONNECTION_ID()').scalar_one()
                    final_conn.rollback()
                    if final_conn.exec_driver_sql('SELECT CONNECTION_ID()').scalar_one() != final_id or final_conn.invalidated:
                        raise ValueError('FINAL_CONNECTION_CHANGED')
                    report['aborted_after'] = int(final_conn.exec_driver_sql("SHOW GLOBAL STATUS LIKE 'Aborted_clients'").one()[1])
                if report['aborted_after'] != report['aborted_before']:
                    raise ValueError('ABORTED_CLIENTS_CHANGED')
            report['status'] = 'PASS_STOP_BEFORE_SEND'
    except BaseException as error:
        report.update(error_type=type(error).__name__, error_code=getattr(error, 'code', None), failure_phase=report['phase'],
            error_frames=[{'file': Path(f.filename).name, 'line': f.lineno, 'function': f.name} for f in traceback.extract_tb(error.__traceback__)])
        if report['error_code'] == 'ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED':
            report['status'] = 'TYPED_REJECTION'
    finally:
        signal.alarm(0)
        if detached is not None:
            clean('stream_close', detached.close)
        if service is not None:
            clean('service_close', service.close)
        held.clear()
        if conn is not None:
            clean('rollback', conn.rollback)
            clean('connection_close', conn.close)
        if engine is not None:
            clean('engine_dispose', engine.dispose)
        clean('sampler_close', sampler.close)
        report['sampler_error'] = sampler.error
        report['temp_after'] = temp_usage(work)
        report['live_children_after'] = [p.name() for p in __import__('psutil').Process().children(recursive=True)]
        report['runner_ru_maxrss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report['cgroup_peak_bytes'] = int(Path('/sys/fs/cgroup/memory.peak').read_text())
        report['cleanup_errors'] = cleanup_errors
        for r in records:
            clean('original_stat_after', lambda r=r: diag.verify_stat(Path('/inputs') / r['filename'], r))
        if cleanup_errors or sampler.error or report['temp_after']['including_open_unlinked_bytes'] or report['live_children_after']:
            report['status'] = 'FAIL'
        output.write_text(diag._json_dumps(report, indent=2), encoding='utf-8')
        diag.emit({'kind': 'final', 'status': report['status']})
        diag.JOURNAL = None
    print(json.dumps({k: report.get(k) for k in ('status', 'failure_phase', 'error_type', 'error_code', 'final_bytes', 'db_read', 'request_guard')}))
    return 0 if report['status'] in ('PASS_STOP_BEFORE_SEND', 'TYPED_REJECTION') else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('manifest', 'output', 'db-host', 'schema', 'code-sha', 'image-id'):
        parser.add_argument('--' + key, required=True)
    parser.add_argument('--first', type=int, required=True)
    parser.add_argument('--count', type=int, required=True)
    parser.add_argument('--seconds', type=int, required=True)
    parser.add_argument('--experimental-config', help='격리 실험 전용 유한 예산 JSON; 운영 설정과 분리')
    parser.add_argument('--coarse-270p-crf28', action='store_true', help='Owner 요청 후보를 Coarse에만 명시 적용')
    args = parser.parse_args()
    try:
        experiment = load_experiment(args.experimental_config) if args.experimental_config else None
        validate_selection(args.first, args.count, args.seconds, experiment)
        if args.coarse_270p_crf28 and experiment is None:
            raise ValueError('COARSE_EXPERIMENT_REQUIRES_EXPLICIT_EXPERIMENT')
        if experiment and experiment.resource_profile != 'legacy' and not args.coarse_270p_crf28:
            raise ValueError('EXPERIMENT_EXTENDED_REQUIRES_COARSE')
    except (ValueError, OSError):
        parser.error('명시적 유한 실험 설정과 허용 입력 범위가 필요합니다')
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
