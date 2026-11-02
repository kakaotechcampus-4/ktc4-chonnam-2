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
