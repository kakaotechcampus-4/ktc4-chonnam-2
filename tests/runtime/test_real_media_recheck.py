"""Offline negative controls for the real-media measurement boundary."""
import hashlib
import importlib.util
from io import BytesIO
from pathlib import Path
import socket
import sys
from types import SimpleNamespace

import pytest


def probe():
    scripts = Path(__file__).parents[2] / 'scripts'
    spec = importlib.util.spec_from_file_location('real_recheck', scripts / 'recording_real_media_recheck.py')
    assert spec is not None, 'new integration harness is required'
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(scripts))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def test_bounded_stream_hash_rewinds_and_rejects_wrong_length():
    p = probe()
    raw = BytesIO(b'a' * 180000)
    stream = p.BoundedView(raw)
    p.verify_stream(stream, 180000, hashlib.sha256(raw.getvalue()).hexdigest())
    assert raw.tell() == 0 and stream.max_read <= 65536
    with pytest.raises(ValueError, match='STREAM_IDENTITY'):
        p.verify_stream(stream, 180001, 'incorrect')
    with pytest.raises(ValueError, match='BOUNDED_READ'):
        stream.read()
    with pytest.raises(ValueError, match='BOUNDED_READ'):
        stream.read(1024 * 1024)


def test_metadata_difference_reports_number_type_and_hex_but_redacts_identity():
    p = probe()
    before={'timeline_range':{'end_sec':100.00000033333333},'source_refs':[{'ref':'private-original-id'}]}
    after={'timeline_range':{'end_sec':100.00000033333332},'source_refs':[{'ref':'other-private-id'}]}
    differences=p.metadata_differences(before,after)
    number=next(d for d in differences if d['path']=='timeline_range.end_sec')
    assert number['before_type']==number['after_type']=='float'
    assert number['before']==100.00000033333333 and number['after']==100.00000033333332
    assert number['before_hex']!=number['after_hex']
    assert 'private' not in str(differences)


def test_failed_tool_observation_keeps_partial_size_and_original_error(tmp_path):
    p = probe()
    path = tmp_path / 'private-output.mp4'
    path.write_bytes(b'partial')
    events = []
    with pytest.raises(ValueError, match='original rejection'):
        with p.tool_measure(events, 'encode', path):
            raise ValueError('original rejection')
    assert events[0]['status'] == 'FAIL' and events[0]['output_bytes'] == 7
    assert 'private' not in str(events)


@pytest.mark.parametrize('same_id,checkedout', [(True, 0), (False, 1)])
def test_fresh_connection_requires_distinct_physical_id_and_no_checkout(same_id, checkedout):
    p = probe()
    with pytest.raises(ValueError, match='DETACHED_CONNECTION'):
        p.require_detached(41, [41 if same_id else 42], checkedout)
    p.require_detached(41, [42], 0)


def test_network_fence_blocks_connect_connect_ex_and_restores(monkeypatch):
    p = probe()
    calls = []
    def connect(sock, address):
        calls.append(address)
    monkeypatch.setattr(socket.socket, 'connect', connect)
    monkeypatch.setattr(socket.socket, 'connect_ex', connect)
    original = socket.socket.connect
    with p.egress_fence('172.29.0.2'):
        with socket.socket() as sock:
            sock.connect(('172.29.0.2', 3306))
            for operation in (sock.connect, sock.connect_ex):
                for address in [('172.29.0.3', 3306), ('172.29.0.2', 443), '/socket']:
                    with pytest.raises(RuntimeError, match='EGRESS_BLOCKED'):
                        operation(address)
    assert calls == [('172.29.0.2', 3306)]
    assert socket.socket.connect is original


def test_http_send_is_fail_closed():
    import httpx
    p = probe()
    original = httpx.Client.send
    with p.egress_fence('172.29.0.2'):
        with httpx.Client() as client:
            with pytest.raises(RuntimeError, match='HTTP_SEND_BLOCKED'):
                client.send(httpx.Request('POST', 'https://example.invalid'))
    assert httpx.Client.send is original


def test_async_send_and_create_connection_fail_closed():
    import httpx
    p = probe()
    with p.egress_fence('172.29.0.2'):
        with pytest.raises(RuntimeError, match='EGRESS_BLOCKED'):
            socket.create_connection(('192.0.2.1', 443), timeout=.1)
        # The async send blocker raises before its first await; no event-loop socket is needed.
        coroutine = httpx.AsyncClient.send(None, httpx.Request('POST', 'https://example.invalid'))
        with pytest.raises(RuntimeError, match='HTTP_SEND_BLOCKED'):
            coroutine.send(None)


def test_real_search_materializer_consumes_same_bounded_stream(tmp_path, monkeypatch):
    from daesingo.search import media
    from daesingo.search.execution import RunDeadline
    import time
    p = probe()
    raw = BytesIO(b'media' * 40000)
    stream = p.BoundedView(raw)
    monkeypatch.setattr(media, '_probe', lambda *_: media.MediaProbe('mp4', 'h264', 10, 640, 480))
    dest = tmp_path / 'source.mp4'
    result = media._materialize(media.MediaInput(stream, 'video/mp4', 200000, 10), dest,
                                512 * 1024**2, RunDeadline(time.monotonic, 150000))
    assert result.actual_byte_size == 200000
    assert dest.read_bytes() == raw.getvalue() and stream.max_read == 65536


def test_actual_provider_guard_reaches_sentinel_and_restores_hooks(tmp_path):
    from daesingo.search import provider
    from daesingo.search.config import GeminiSearchConfig
    from daesingo.search.media import PreparedMedia
    from daesingo.search.execution import RunDeadline
    import time
    p = probe()
    path = tmp_path / 'proxy.mp4'
    path.write_bytes(b'bounded media')
    media = PreparedMedia(path, 'video/mp4', 13, 10, 0, 10)
    original = provider._video_data_url
    report = {}
    p.request_boundary(GeminiSearchConfig(), media, SimpleNamespace(
        analysis_source_ref='control', duration_sec=10), 'timeline-control',
        RunDeadline(time.monotonic, 150000), report, [], lambda: None)
    assert report['request_guard'] == 'PASS_STOP_BEFORE_SEND'
    assert report['sdk_entry_count'] == 1 and report['base64_bytes'] == 20
    assert report['guard_json_bytes'] > report['base64_bytes']
    assert provider._video_data_url is original
    with pytest.raises(Exception):
        p.request_boundary(GeminiSearchConfig(max_inline_media_bytes=1), media,
            SimpleNamespace(analysis_source_ref='control', duration_sec=10), 'timeline-control',
            RunDeadline(time.monotonic, 150000), {}, [], lambda: None)
    assert provider._video_data_url is original


def test_temp_measure_counts_unlinked_open_file(tmp_path):
    p = probe()
    path = tmp_path / 'open.bin'
    path.write_bytes(b'a' * 1234)
    # POSIX anonymous file accounting is dynamically checked inside the Linux runner.
    assert p.temp_usage(tmp_path)['named_bytes'] == 1234


@pytest.mark.parametrize('condition', ['memory', 'temp', 'read_error'])
def test_new_sampler_thresholds_and_read_failure_stop_before_next_phase(tmp_path, condition):
    p = probe()
    marker = tmp_path / 'abort'
    sampler = p.Sampler(tmp_path, {'phase':'control', 'samples':[]}, marker)
    def collect():
        if condition == 'read_error':
            raise OSError('private path')
        return {'cgroup_bytes':1100*1024**2 if condition=='memory' else 0,
                'including_open_unlinked_bytes':512*1024**2 if condition=='temp' else 0}
    sampler.collect = collect
    sampler.start()
    sampler.thread.join(2)
    assert not sampler.thread.is_alive() and marker.read_text()=='SAMPLER_OR_RESOURCE_STOP'
    with pytest.raises(RuntimeError, match='SAMPLER_OR_RESOURCE_STOP'):
        sampler.check()
    sampler.close()


def test_request_byte_cap_rejection_never_reaches_sdk_and_restores_hooks(tmp_path):
    from daesingo.search import provider
    from daesingo.search.config import GeminiSearchConfig
    from daesingo.search.provider import RequestSizeError
    from daesingo.search.media import PreparedMedia
    from daesingo.search.execution import RunDeadline
    import time
    p = probe()
    path = tmp_path/'proxy.mp4'
    path.write_bytes(b'media')
    report = {}
    original_url, original_json = provider._video_data_url, provider.json.dumps
    with pytest.raises(RequestSizeError):
        p.request_boundary(GeminiSearchConfig(max_inline_request_bytes=1),
            PreparedMedia(path,'video/mp4',5,10,0,10),
            SimpleNamespace(analysis_source_ref='control',duration_sec=10), 'control',
            RunDeadline(time.monotonic,150000),report,[],lambda:None)
    assert report['sdk_entry_count']==0 and report['request_guard']=='FAIL'
    assert provider._video_data_url is original_url and provider.json.dumps is original_json


def test_search_timeout_reaps_child_without_raw_diagnostic(monkeypatch):
    from daesingo.search import media
    from daesingo.search.execution import RunDeadline, DeadlineExceededError
    import subprocess
    import time
    calls = []
    class Process:
        def communicate(self, timeout=None):
            calls.append(('communicate',timeout))
            if timeout is not None:
                raise subprocess.TimeoutExpired('private argv',timeout)
            return b'',b'private path'
        def kill(self):
            calls.append(('kill',None))
    monkeypatch.setattr(media.subprocess,'Popen',lambda *a,**kw:Process())
    with pytest.raises(DeadlineExceededError):
        media._run_subprocess(['ffmpeg','private input'],RunDeadline(time.monotonic,1))
    assert [c[0] for c in calls]==['communicate','kill','communicate']


def experimental(**changes):
    return dict(experiment_id='p2-0c-240', max_output_bytes=100663296,
                max_duration_ms=240000, run_timeout_sec=900, **changes)


@pytest.mark.parametrize('key,value', [
    ('max_output_bytes', 0), ('max_output_bytes', True), ('max_output_bytes', 268435457),
    ('max_duration_ms', 1200001), ('max_duration_ms', 239999),
    ('run_timeout_sec', 0), ('run_timeout_sec', 3601), ('run_timeout_sec', float('inf')),
    ('experiment_id', '../private'), ('search_cap', 999),
])
def test_experiment_rejects_unsafe_values_and_unrelated_overrides(key, value):
    p = probe()
    values = experimental()
    values[key] = value
    with pytest.raises(ValueError, match='EXPERIMENT'):
        p.Experiment.from_mapping(values)


def test_experiment_rejects_duplicate_json_and_preserves_recording_guard(tmp_path):
    p = probe()
    config = tmp_path / 'experiment.json'
    config.write_text('{"experiment_id":"x","experiment_id":"y"}')
    with pytest.raises(ValueError, match='EXPERIMENT'):
        p.load_experiment(config)
    exp = p.Experiment.from_mapping(experimental())
    from daesingo.recording.factory import RecordingSettings
    from daesingo.recording.analysis_limits import analysis_source_scope, check_output_size
    from daesingo.recording.errors import RecordingCapabilityError
    settings = RecordingSettings.from_mapping(p.recording_config(exp))
    assert settings.analysis_limits.max_bytes == 100663296
    assert settings.analysis_limits.max_duration_ms == 240000
    # 새 상한에서도 제품 실행 중 guard가 유효해야 한다.
    with analysis_source_scope(settings.analysis_limits, lambda: None):
        check_output_size(50331649)
        with pytest.raises(RecordingCapabilityError) as failure:
            check_output_size(100663297)
    assert failure.value.code == 'ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED'


def test_long_requests_require_explicit_config_and_finite_contiguous_selection():
    p = probe()
    exp = p.Experiment.from_mapping({**experimental(), 'max_duration_ms': 480000})
    p.validate_selection(1, 5, 480, exp)
    for first, count, seconds, config in [(1, 5, 480, None), (2, 5, 480, exp),
            (1, 0, 240, exp), (1, 16, 240, exp), (1, 5, 481, exp), (True, 5, 240, exp)]:
        with pytest.raises(ValueError, match='INPUT_PROFILE'):
            p.validate_selection(first, count, seconds, config)
    baseline = p.recording_config(None)
    assert baseline['DAESINGO_RECORDING_ANALYSIS_MAX_BYTES'] == '50331648'
    assert baseline['DAESINGO_RECORDING_ANALYSIS_MAX_DURATION_MS'] == '240000'


@pytest.mark.parametrize('start,end', [(10.1, 20), (9.9, 20), (10, 9)])
def test_logical_coverage_rejects_gap_overlap_or_reversed_boundary(start, end):
    p = probe()
    with pytest.raises(ValueError, match='PLACEMENT'):
        p.logical_coverage([{'start': 0, 'end': 10}, {'start': start, 'end': end}], 20)


def test_logical_coverage_requires_full_requested_range_but_does_not_invent_capture_continuity():
    p = probe()
    result = p.logical_coverage([{'start': 0, 'end': 10}, {'start': 10, 'end': 21}], 20)
    assert result['requested_sec'] == 20 and result['logical_gap_overlap_count'] == 0
    assert result['capture_continuity'] == 'UNKNOWN'
    with pytest.raises(ValueError, match='PLACEMENT'):
        p.logical_coverage([{'start': 0, 'end': 19}], 20)


def test_network_observation_counts_actual_attempts_after_controls():
    import httpx
    p = probe()
    with p.egress_fence('192.0.2.2') as counts:
        assert counts['external_socket_attempts'] == 0 and counts['http_send_attempts'] == 0
        with socket.socket() as sock, pytest.raises(RuntimeError, match='EGRESS_BLOCKED'):
            sock.connect(('192.0.2.3', 443))
        with httpx.Client() as client, pytest.raises(RuntimeError, match='HTTP_SEND_BLOCKED'):
            client.send(httpx.Request('POST', 'https://example.invalid'))
        assert counts['external_socket_attempts'] == 1 and counts['http_send_attempts'] == 1


def test_cli_accepts_explicit_long_request_and_rejects_implicit_override(tmp_path, monkeypatch):
    p = probe()
    path = tmp_path / 'experiment.json'
    path.write_text(__import__('json').dumps({**experimental(), 'max_duration_ms': 480000}))
    common = ['probe', '--manifest', 'protected', '--output', 'result', '--db-host', '192.0.2.2',
              '--schema', 'owned', '--code-sha', 'head', '--image-id', 'fixed',
              '--first', '1', '--count', '5', '--seconds', '480']
    reached = []
    monkeypatch.setattr(p, 'run', lambda args: reached.append(args.seconds) or 0)
    monkeypatch.setattr(sys, 'argv', common)
    with pytest.raises(SystemExit) as failure:
        p.main()
    assert failure.value.code == 2 and reached == []
    monkeypatch.setattr(sys, 'argv', common + ['--experimental-config', str(path)])
    assert p.main() == 0 and reached == [480]


def test_driver_observes_all_result_packets_and_restores_hook(monkeypatch):
    import pymysql.connections
    from pymysql.protocol import MysqlPacket
    p = probe()
    cls = pymysql.connections.Connection
    packet = MysqlPacket(b'x' * 123, 'utf8')
    monkeypatch.setattr(cls, '_read_packet', lambda *a, **kw: packet)
    original = cls._read_packet
    report = {'phase': 'control', 'driver': []}
    with p.command_metrics(report):
        conn = cls(defer_connect=True)
        assert conn._read_packet() is packet
        assert max(d.get('result_packet_bytes', 0) for d in report['driver']) == 123
    assert cls._read_packet is original


def test_search_output_size_survives_real_media_cap_rejection_and_cleanup(tmp_path):
    from daesingo.search.media import _verify_output, MediaTooLargeError
    p = probe()
    output = tmp_path / 'private.mp4'
    events = []
    def encode(source, target, **kwargs):
        target.write_bytes(b'x' * 11)
    try:
        p.measure_search_encode(events, encode, Path('unused'), output)
        with pytest.raises(MediaTooLargeError):
            _verify_output(output, 10)
    finally:
        output.unlink(missing_ok=True)
    assert not output.exists()
    assert events[0]['output_bytes'] == 11 and events[0]['status'] == 'PASS'
    assert 'private' not in str(events)


@pytest.mark.parametrize('values', [None, {}, {'height': 360, 'crf': 28},
    {'height': 270, 'crf': True}, {'height': 270, 'crf': 29},
    {'height': 270, 'crf': 28, 'media_cap': 99}])
def test_coarse_override_rejects_unapproved_settings(values):
    with pytest.raises(ValueError, match='COARSE_EXPERIMENT'):
        probe().CoarseOverride.from_mapping(values)


@pytest.mark.parametrize('fail', [False, True])
def test_coarse_override_changes_actual_encode_argv_only_and_restores(tmp_path, monkeypatch, fail):
    """실제 제품 argv builder를 통과한다. subprocess 실행만 이 control에서 대체한다."""
    import subprocess
    import time
    from daesingo.search import media
    from daesingo.search.execution import RunDeadline
    p = probe()
    seen = []
    def execute(argv, deadline):
        seen.append(argv)
        if fail and argv[-1].endswith('coarse.mp4'):
            raise RuntimeError('encode control failure')
        return subprocess.CompletedProcess(argv, 0, b'', b'crf=28.0')
    monkeypatch.setattr(media, '_run_subprocess', execute)
    original_encode, original_run = media._run_ffmpeg_encode, media._run_subprocess
    settings = p.CoarseOverride.from_mapping({'height': 270, 'crf': 28})
    report = {}
    deadline = RunDeadline(time.monotonic, 150000)
    src = tmp_path / 'source.mp4'
    with p.coarse_encode_override(media, settings, report):
        # Fine도 같은 thread/context 안에서 baseline으로 실행돼야 한다.
        media._run_ffmpeg_encode(src, tmp_path/'fine.mp4', fps=4.0, max_height=360,
                                deadline=deadline, start_sec=2.0, end_sec=5.0)
        media._run_subprocess(['ffmpeg', '-i', 'other', 'other.mp4'], deadline)
        if fail:
            with pytest.raises(RuntimeError, match='encode control failure'):
                media._run_ffmpeg_encode(src, tmp_path/'coarse.mp4', fps=2.0,
                                        max_height=360, deadline=deadline)
        else:
            media._run_ffmpeg_encode(src, tmp_path/'coarse.mp4', fps=2.0,
                                    max_height=360, deadline=deadline)
        assert media._run_subprocess is original_run
    assert media._run_ffmpeg_encode is original_encode and media._run_subprocess is original_run
    assert '-crf' not in seen[0] and seen[0][1:5] == ['-y', '-ss', '2.0', '-t']
    assert "fps=4.0,scale=-2:'min(360,ih)',setpts=(PTS-STARTPTS)*4.0,fps=1" in seen[0]
    assert seen[1] == ['ffmpeg', '-i', 'other', 'other.mp4']
    actual = seen[2]
    assert actual[actual.index('-crf') + 1] == '28'
    assert "fps=2.0,scale=-2:'min(270,ih)',setpts=(PTS-STARTPTS)*2.0,fps=1" in actual
    assert '-an' in actual and actual[actual.index('-c:v')+1] == 'libx264'
    assert report['coarse_override_restored'] is True


def test_coarse_override_context_failure_restores_before_propagation(monkeypatch):
    from daesingo.search import media
    p = probe()
    original_encode, original_run = media._run_ffmpeg_encode, media._run_subprocess
    with pytest.raises(KeyboardInterrupt):
        with p.coarse_encode_override(media, p.CoarseOverride(270, 28), {}):
            raise KeyboardInterrupt()
    assert media._run_ffmpeg_encode is original_encode and media._run_subprocess is original_run


def test_coarse_output_probe_captures_actual_stdout(tmp_path, monkeypatch):
    import json
    import subprocess
    from daesingo.search import media
    p = probe()
    def execute(argv, deadline, *, capture_stdout=False):
        payload = {'streams': [{'codec_type': 'video', 'height': 270, 'time_base': '1/16384'}],
            'format': {'duration': '2'}, 'frames': [
                {'best_effort_timestamp': 0, 'duration': 16384},
                {'best_effort_timestamp': 16384, 'duration': 16384}]}
        return subprocess.CompletedProcess(argv, 0, json.dumps(payload).encode() if capture_stdout else None, b'')
    monkeypatch.setattr(media, '_run_subprocess', execute)
    result = p.inspect_coarse_output(media, SimpleNamespace(path=tmp_path/'coarse.mp4',
        origin_start_sec=0, origin_end_sec=1, playback_speed=.5), object())
    assert result['frames']['frame_count'] == 2 and result['format_duration_sec'] == 2


def test_extended_experiment_requires_shared_profile_and_sampler_uses_it(tmp_path):
    p = probe()
    values = {'experiment_id': 'coarse270-1200', 'max_output_bytes': 402653184,
        'max_duration_ms': 1200000, 'run_timeout_sec': 3000, 'resource_profile': 'coarse-1200-384m'}
    exp = p.Experiment.from_mapping(values)
    budget = p.experiment_budget(exp)
    assert budget.runner_hard_mib == 2176 and budget.runner_soft_mib == 1900 and budget.temp_soft_mib == 896
    assert p.recording_config(exp)['DAESINGO_RECORDING_ANALYSIS_MAX_BYTES'] == '402653184'
    sampler = p.Sampler(tmp_path, {'samples': []}, tmp_path/'abort', budget=budget)
    # 확장 soft 직전은 통과, 실제 확장 soft에서는 중단한다.
    sampler.collect = lambda: {'cgroup_bytes': 1992294399, 'including_open_unlinked_bytes': 939524095}
    original_emit = p.diag.emit
    p.diag.emit = lambda value: sampler.stop.set()
    try:
        sampler.sample()
        assert sampler.error is None
        sampler.stop.clear()
        sampler.collect = lambda: {'cgroup_bytes': 1992294400, 'including_open_unlinked_bytes': 0}
        sampler.sample()
        assert sampler.error == 'RuntimeError' and (tmp_path/'abort').exists()
    finally:
        p.diag.emit = original_emit
    for change in ({'resource_profile': 'legacy'}, {'run_timeout_sec': 1800}, {'max_duration_ms': 720000}):
        with pytest.raises(ValueError, match='EXPERIMENT'):
            p.Experiment.from_mapping({**values, **change})


def test_coarse_override_does_not_change_another_thread_encode(tmp_path, monkeypatch):
    import subprocess
    import threading
    import time
    from daesingo.search import media
    from daesingo.search.execution import RunDeadline
    p = probe()
    seen, errors = [], []
    deadline = RunDeadline(time.monotonic, 150000)
    def other():
        try:
            media._run_ffmpeg_encode(tmp_path/'other-source', tmp_path/'other'/'coarse.mp4',
                fps=2.0, max_height=360, deadline=deadline)
        except BaseException as error:
            errors.append(error)
    def execute(argv, deadline, **options):
        seen.append(argv)
        if '-crf' in argv:
            thread = threading.Thread(target=other)
            thread.start()
            thread.join(2)
            assert not thread.is_alive()
        return subprocess.CompletedProcess(argv, 0, b'', b'')
    monkeypatch.setattr(media, '_run_subprocess', execute)
    with p.coarse_encode_override(media, p.CoarseOverride(270, 28), {}):
        media._run_ffmpeg_encode(tmp_path/'source', tmp_path/'coarse.mp4',
            fps=2.0, max_height=360, deadline=deadline)
    assert not errors and len(seen) == 2
    assert '-crf' in seen[0] and '-crf' not in seen[1]
    assert "fps=2.0,scale=-2:'min(360,ih)',setpts=(PTS-STARTPTS)*2.0,fps=1" in seen[1]


def test_coarse_override_refuses_changed_call_contract(tmp_path):
    from daesingo.search import media
    p = probe()
    original = media._run_ffmpeg_encode
    with pytest.raises(ValueError, match='COARSE_EXPERIMENT_CALL_DRIFT'):
        with p.coarse_encode_override(media, p.CoarseOverride(270, 28), {}):
            media._run_ffmpeg_encode(tmp_path/'source', tmp_path/'coarse.mp4',
                fps=4.0, max_height=360, deadline=object())
    assert media._run_ffmpeg_encode is original
