"""RT-11(a) transport, streaming bounds and storage before any DB work."""
import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from daesingo.api.app import create_app
from daesingo.api.composition import ApiComposition
from daesingo.recording import RecordingCapabilityError


def multipart(filename='original.mp4', content=b'PRIVATE_PAYLOAD', *, name='file', extra=b''):
    header = f'Content-Disposition: form-data; name="{name}"'
    if filename is not None:
        header += '; filename="' + filename.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return (b'--boundary\r\n' + header.encode() + b'\r\nContent-Type: ignored/format\r\n\r\n'
            + content + b'\r\n' + extra + b'--boundary--\r\n')


MEDIA = {'content-type': 'multipart/form-data; boundary=boundary'}
PATH = '/cases/case_upload/sources'


def envelope(code):
    return {'ok': False, 'error': {'code': code, 'message_key': code}, 'case_view': None}


@pytest.fixture
def upload_app(api_startup, monkeypatch):
    startup, output = api_startup
    calls = []
    def register(self, case_id, path, original_filename):
        calls.append((case_id, Path(path), original_filename, Path(path).read_bytes()))
        return {'case_id': case_id, 'source_asset_ref': 'sa_registered',
                'case_view': {'case_id': case_id, 'manifest_summary': {'file_count': len(calls)}}}
    monkeypatch.setattr(ApiComposition, 'register_source', register, raising=False)
    app = create_app(startup=startup)
    yield app, calls, output
    app.state.composition.close()


@pytest.mark.parametrize('kind', ['media', 'boundary', 'no-file', 'two-files', 'other-field',
                                 'no-filename', 'empty-filename', 'truncated', 'garbage'])
def test_upload_transport_envelope(upload_app, kind):
    app, calls, output = upload_app
    body, headers, status, code = multipart(), MEDIA, 400, 'http.malformed_request'
    if kind == 'media':
        headers, status, code = {'content-type': 'application/octet-stream'}, 415, 'http.unsupported_media_type'
    elif kind == 'boundary':
        headers = {'content-type': 'multipart/form-data'}
    elif kind == 'no-file':
        body = b'--boundary--\r\n'
    elif kind == 'two-files':
        body = multipart()[:-len(b'--boundary--\r\n')] + multipart()
    elif kind == 'other-field':
        body = multipart(name='metadata')
    elif kind == 'no-filename':
        body = multipart(filename=None)
    elif kind == 'empty-filename':
        body = multipart(filename='')
    elif kind == 'truncated':
        body = multipart()[:-10]
    elif kind == 'garbage':
        body = b'PRIVATE_MALFORMED_MULTIPART'
    with TestClient(app) as client:
        response = client.post(PATH, content=body, headers=headers)
    assert response.status_code == status
    assert response.json() == envelope(code)
    assert calls == []
    assert list(app.state.composition.startup.config.media_root.glob('source/*')) == []
    assert 'PRIVATE' not in output.getvalue()


@pytest.mark.parametrize('filename', ['../escape.mp4', '/absolute.mp4', r'C:\private\original.mp4',
    r'folder\nested.mp4', '한글_가_é.mp4', '  original  ', 'UNSUPPORTED_MEDIA.mp4'])
def test_filename_is_opaque_metadata_and_never_a_locator(upload_app, filename):
    app, calls, output = upload_app
    with TestClient(app) as client:
        response = client.post(PATH, content=multipart(filename), headers=MEDIA)
    assert response.status_code == 201
    assert set(response.json()) == {'case_id', 'source_asset_ref', 'case_view'}
    assert 'location' not in response.headers  # §5.2 defines no Location header.
    assert calls[0][2:] == (filename, b'PRIVATE_PAYLOAD')
    stored = calls[0][1]
    assert stored.parent == app.state.composition.startup.config.media_root / 'source'
    assert stored.name != filename and 'original' not in stored.name
    assert filename not in response.text and filename not in output.getvalue()


def scope(headers, *, close=None):
    result = {'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.4'},
        'http_version': '1.1', 'method': 'POST', 'scheme': 'http', 'path': PATH,
        'raw_path': PATH.encode(), 'query_string': b'', 'root_path': '',
        'headers': [(k.encode(), v.encode()) for k, v in headers.items()],
        'server': ('testserver', 80), 'client': ('testclient', 123)}
    if close is not None:
        result['extensions'] = {'daesingo.close': close}
    return result


async def invoke(app, bodies, headers, *, delays=None):
    sent, consumed, closed = [], [], []
    done = asyncio.Event()
    async def receive():
        index = len(consumed)
        if index >= len(bodies):
            await done.wait()
            return {'type': 'http.disconnect'}
        if delays:
            await asyncio.sleep(delays[index])
        chunk = bodies[index]
        consumed.append(index)
        if chunk is None:
            return {'type': 'http.disconnect'}
        return {'type': 'http.request', 'body': chunk, 'more_body': index < len(bodies)-1}
    async def send(message):
        sent.append(message)
        if message['type'] == 'http.response.body' and not message.get('more_body'):
            done.set()
    await app(scope(headers, close=lambda: closed.append(True)), receive, send)
    return sent, consumed, closed


@pytest.mark.parametrize('declared', [False, True])
@pytest.mark.parametrize('extra', [0, 1])
def test_raw_body_limit_includes_overhead_and_stops_receiving(upload_app, declared, extra):
    app, calls, _ = upload_app
    body = multipart()
    config = app.state.composition.startup.config
    object.__setattr__(app.state.composition.startup, 'config',
        replace(config, upload=replace_settings(config.upload, max_bytes=len(body))))
    headers = dict(MEDIA)
    if declared:
        headers['content-length'] = str(len(body)+extra)
    chunks = [body[:40], body[40:]+b'x'*extra, b'SHOULD_NOT_BE_RECEIVED'] if extra else [body[:40], body[40:]]
    sent, consumed, _ = asyncio.run(invoke(app, chunks, headers))
    assert sent[0]['status'] == (413 if extra else 201)
    assert bool(calls) is (not extra)
    if extra:
        assert 2 not in consumed
        assert json.loads(b''.join(m.get('body', b'') for m in sent)) == envelope('http.payload_too_large')
        assert (b'connection', b'close') in sent[0]['headers']


def replace_settings(settings, **values):
    return settings.model_copy(update=values)


@pytest.mark.parametrize('reason', ['idle', 'duration', 'disconnect'])
def test_receive_abort_sends_no_status_and_never_registers(upload_app, reason):
    app, calls, output = upload_app
    startup = app.state.composition.startup
    settings = replace_settings(startup.config.upload, idle_timeout_sec=.04,
        max_duration_sec=.07 if reason == 'duration' else 1)
    object.__setattr__(startup, 'config', replace(startup.config, upload=settings))
    chunks, delays = [b'--bound', None] if reason == 'disconnect' else [b'-']*10, [.0]*2
    if reason == 'idle':
        delays = [.0]+[.09]*9
    elif reason == 'duration':
        delays = [.02]*10
    sent, consumed, closed = asyncio.run(invoke(app, chunks, MEDIA, delays=delays))
    assert sent == [] and calls == []
    assert bool(closed) is (reason != 'disconnect')
    assert list(startup.config.media_root.glob('source/*')) == []
    assert 'PRIVATE' not in output.getvalue()


@pytest.mark.parametrize('error,status,code', [
    (RecordingCapabilityError('UNSUPPORTED_MEDIA', 'PRIVATE /source secret'), 422, 'http.source_rejected'),
    (RecordingCapabilityError('TEMPORARY_FAILURE', 'PRIVATE /source secret'), 503, 'http.dependency_unavailable'),
    (RecordingCapabilityError('UNKNOWN_REF', 'TEMPORARY_FAILURE PRIVATE'), 500, 'http.internal_error'),
    (RuntimeError('UNSUPPORTED_MEDIA PRIVATE secret'), 500, 'http.internal_error'),
])
def test_taxonomy_does_not_inspect_error_messages(upload_app, monkeypatch, error, status, code):
    app, _, output = upload_app
    def fail(*args):
        raise error
    monkeypatch.setattr(ApiComposition, 'register_source', fail, raising=False)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(PATH, content=multipart(), headers=MEDIA)
    assert response.status_code == status and response.json() == envelope(code)
    assert 'PRIVATE' not in output.getvalue() and 'PRIVATE' not in response.text


@pytest.mark.parametrize('fault', ['none', 'fsync', 'device', 'publish'])
def test_fsync_same_device_and_publish_precede_registration(upload_app, monkeypatch, fault):
    app, calls, output = upload_app
    order = []
    fsync, replace_file, stat = os.fsync, os.replace, Path.stat
    def sync(fd):
        order.append('fsync')
        if fault == 'fsync':
            raise OSError('PRIVATE filesystem failure')
        return fsync(fd)
    def rename(source, destination):
        assert 'fsync' in order and calls == []
        assert Path(source).stat().st_dev == Path(destination).parent.stat().st_dev
        order.append('publish')
        if fault == 'publish':
            raise OSError('PRIVATE publish')
        return replace_file(source, destination)
    def device(path, *args, **kwargs):
        result = stat(path, *args, **kwargs)
        if fault == 'device' and path.name == 'source':
            values = list(result)
            values[2] += 1
            return os.stat_result(values)
        return result
    monkeypatch.setattr(os, 'fsync', sync)
    monkeypatch.setattr(os, 'replace', rename)
    monkeypatch.setattr(Path, 'stat', device)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(PATH, content=multipart(), headers=MEDIA)
    assert response.status_code == (201 if fault == 'none' else 503)
    assert bool(calls) is (fault == 'none')
    if fault != 'none':
        assert list(app.state.composition.startup.config.media_root.glob('source/*')) == []
    else:
        assert order.index('fsync') < order.index('publish')
    assert 'PRIVATE' not in output.getvalue()


@pytest.mark.parametrize('declared', [False, True])
def test_default_one_gib_exact_and_next_byte_are_streamed_without_whole_body_buffer(upload_app, monkeypatch, declared):
    app, _, _ = upload_app
    maximum = app.state.composition.startup.config.upload.max_bytes
    assert maximum == 1_073_741_824
    framing = multipart(content=b'')
    prefix, suffix = framing.split(b'\r\n\r\n', 1)[0]+b'\r\n\r\n', b'\r\n--boundary--\r\n'
    payload_size = maximum-len(prefix)-len(suffix)
    results = []
    def registered(self, case_id, path, original_filename):
        assert Path(path).stat().st_size == payload_size
        results.append(path)
        return {'case_id': case_id, 'source_asset_ref': 'sa_big', 'case_view': {}}
    monkeypatch.setattr(ApiComposition, 'register_source', registered)
    async def perform(extra):
        sent = []
        remaining = payload_size
        position = 0
        finished = asyncio.Event()
        async def receive():
            nonlocal remaining, position
            position += 1
            if position == 1:
                return {'type': 'http.request', 'body': prefix, 'more_body': True}
            if remaining:
                size = min(remaining, 1024*1024)
                remaining -= size
                return {'type': 'http.request', 'body': b'\0'*size, 'more_body': True}
            if position == 2+(payload_size+1024*1024-1)//(1024*1024):
                return {'type': 'http.request', 'body': suffix+b'x'*extra, 'more_body': False}
            await finished.wait()
            return {'type': 'http.disconnect'}
        async def send(message):
            sent.append(message)
            if message['type'] == 'http.response.body' and not message.get('more_body'):
                finished.set()
        headers = dict(MEDIA)
        if declared:
            headers['content-length'] = str(maximum+extra)
        await app(scope(headers), receive, send)
        assert sent[0]['status'] == (413 if extra else 201)
    try:
        asyncio.run(perform(0))
        asyncio.run(perform(1))
        assert len(results) == 1
    finally:
        # Only exact artifacts created by this test; do not retain GiB fixtures.
        for directory in ('source', 'staging'):
            for path in app.state.composition.startup.config.media_root.joinpath(directory).glob('*'):
                path.unlink()
