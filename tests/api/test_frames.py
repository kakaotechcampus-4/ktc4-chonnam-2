"""Frame HTTP contract: transport, typed errors and bounded reads."""
import asyncio
import base64
import json
from threading import Event, Lock

import pytest
from fastapi.testclient import TestClient

from daesingo.api.app import create_app
from daesingo.api.composition import ApiComposition
from daesingo.common.db.errors import BeforeCommitFailure, CommitOutcomeUnknown
from daesingo.recording import FrameImage, RecordingCapabilityError
from daesingo.case.store import CaseNotFound, InvalidCaseId
from test_sources import envelope, scope as upload_scope

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aV1cAAAAASUVORK5CYII=')
PATH = '/cases/case_frame/frames/fr_stored'


def scope(path=PATH):
    value = upload_scope({})
    value.update(method='GET', path=path, raw_path=path.encode())
    return value


async def request(app, *, path=PATH, send=None):
    messages = []
    received = False
    async def receive():
        nonlocal received
        if not received:
            received = True
            return {'type': 'http.request', 'body': b'', 'more_body': False}
        await asyncio.Event().wait()
    async def capture(message):
        messages.append(message)
        if send:
            await send(message)
    await app(scope(path), receive, capture)
    return messages


@pytest.fixture
def frame_app(api_startup, monkeypatch):
    startup, output = api_startup
    monkeypatch.setattr(ApiComposition, 'load_frame', lambda self, case, ref: FrameImage(PNG, 'image/png', 'png'), raising=False)
    app = create_app(startup=startup)
    yield app, output
    app.state.composition.close()


def test_exact_stored_bytes_headers_and_repeat_cache(frame_app):
    app, output = frame_app
    with TestClient(app) as client:
        for _ in range(2):
            result = client.get(PATH, headers={'Range': 'bytes=0-1'})
            assert result.status_code == 200
            assert result.content == PNG
            assert result.headers['content-type'] == 'image/png'
            assert result.headers['content-length'] == str(len(PNG))
            assert result.headers['cache-control'] == 'private, max-age=3600'
            assert 'content-range' not in result.headers
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    for name in ('api.frame.wait_ms', 'api.frame.latency_ms', 'api.frame.request_rate'):
        found = [e for e in events if e['event'] == name]
        assert len(found) == 2
        assert all(e.get('duration_ms', 0) >= 0 and e['trace_id'].startswith('tr_') for e in found)


@pytest.mark.parametrize('failure,status,code', [
    (CaseNotFound('PRIVATE'), 404, 'http.not_found'),
    (InvalidCaseId('PRIVATE'), 404, 'http.not_found'),
    *( (RecordingCapabilityError(c, 'PRIVATE /secret/file.png'), s, h) for c, s, h in (
        ('UNKNOWN_REF', 404, 'http.not_found'),
        ('FRAME_NOT_FOUND', 404, 'http.ref_unavailable'),
        ('STREAM_UNAVAILABLE', 404, 'http.ref_unavailable'),
        ('OUT_OF_RANGE', 404, 'http.ref_unavailable'),
        ('TEMPORARY_FAILURE', 503, 'http.dependency_unavailable'),
        ('OTHER', 500, 'http.internal_error'))),
    (RuntimeError('PRIVATE TEMPORARY_FAILURE /secret/file.png'), 500, 'http.internal_error'),
], ids=['case', 'invalid-case', 'unknown', 'missing-bytes', 'stream', 'range', 'temporary', 'other', 'unexpected'])
def test_typed_mapping_never_parses_or_discloses(frame_app, monkeypatch, failure, status, code):
    app, output = frame_app
    def fail(*args):
        raise failure
    monkeypatch.setattr(ApiComposition, 'load_frame', fail)
    with TestClient(app, raise_server_exceptions=False) as client:
        result = client.get(PATH + '?secret=PRIVATE', headers={'Authorization': 'PRIVATE'})
        assert result.status_code == status
        assert result.json() == envelope(code)
        assert 'cache-control' not in result.headers
    assert not any(s in output.getvalue() + result.text for s in ('PRIVATE', '/secret', 'file.png', 'Traceback'))
    latency = [json.loads(line) for line in output.getvalue().splitlines()
               if json.loads(line)['event'] == 'api.frame.latency_ms']
    assert len(latency) == 1 and latency[0]['status'] == str(status)


@pytest.mark.parametrize('cancel_active', [False, True])
def test_two_active_third_waits_and_cancellation_never_releases_active_read_early(frame_app, monkeypatch, cancel_active):
    app, _ = frame_app
    entered, release, lock = Event(), Event(), Lock()
    active = maximum = calls = 0
    def load(*args):
        nonlocal active, maximum, calls
        with lock:
            active += 1
            calls += 1
            maximum = max(maximum, active)
            if active == 2:
                entered.set()
        try:
            assert release.wait(4)
            return FrameImage(PNG, 'image/png', 'png')
        finally:
            with lock:
                active -= 1
    monkeypatch.setattr(ApiComposition, 'load_frame', load)
    async def run():
        first = [asyncio.create_task(request(app)) for _ in range(2)]
        assert await asyncio.to_thread(entered.wait, 2)
        third = asyncio.create_task(request(app))
        try:
            await asyncio.sleep(.05)
            assert calls == 2 and maximum == 2 and not third.done()
            victim = first[0] if cancel_active else third
            victim.cancel()
            with pytest.raises(asyncio.CancelledError):
                await victim
            await asyncio.sleep(.05)
            assert calls == 2
        finally:
            release.set()
            await asyncio.gather(*first, third, return_exceptions=True)
        results = await asyncio.wait_for(asyncio.gather(*(request(app) for _ in range(3))), 3)
        assert all(r[0]['status'] == 200 for r in results)
        assert maximum == 2
    asyncio.run(run())


def test_failed_reads_return_permits(frame_app, monkeypatch):
    app, _ = frame_app
    attempts = 0
    def load(*args):
        nonlocal attempts
        attempts += 1
        if attempts <= 3:
            raise RuntimeError('PRIVATE')
        return FrameImage(PNG, 'image/png', 'png')
    monkeypatch.setattr(ApiComposition, 'load_frame', load)
    async def run():
        results = await asyncio.wait_for(asyncio.gather(*(request(app) for _ in range(6))), 3)
        assert sorted(r[0]['status'] for r in results) == [200]*3 + [500]*3
    asyncio.run(run())


@pytest.mark.parametrize('ending', ['normal', 'cancel', 'disconnect', 'oserror', 'unexpected'])
@pytest.mark.parametrize('phase', ['body', 'final'])
def test_permit_covers_real_asgi_send_until_every_exit(frame_app, monkeypatch, ending, phase):
    """Moving release to route/Response.__call__ inside BaseHTTP also fails here."""
    from starlette.requests import ClientDisconnect
    app, output = frame_app
    calls = []
    def load(*args):
        calls.append(True)
        return FrameImage(PNG, 'image/png', 'png')
    monkeypatch.setattr(ApiComposition, 'load_frame', load)
    async def run():
        entered = asyncio.Queue()
        releases = [asyncio.Event() for _ in range(4)]
        tasks = []
        async def send(index, message):
            assert app.state.composition.engine.pool.checkedout() == 0
            if message['type'] != 'http.response.body':
                return
            target = bool(message.get('body')) if phase == 'body' else not message.get('more_body', False)
            if target:
                await entered.put(index)
                await releases[index].wait()
                if index == 0:
                    if ending == 'disconnect':
                        raise ClientDisconnect()
                    if ending == 'oserror':
                        raise OSError('PRIVATE send')
                    if ending == 'unexpected':
                        raise RuntimeError('PRIVATE send')
        def start(index):
            task = asyncio.create_task(request(app, send=lambda m: send(index, m)))
            tasks.append(task)
            return task
        try:
            start(0); start(1)
            assert {await asyncio.wait_for(entered.get(), 2) for _ in range(2)} == {0, 1}
            start(2)
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(entered.get(), .1)
            assert len(calls) == 2 and app.state.composition.engine.pool.checkedout() == 0
            await asyncio.to_thread(app.state.composition.readiness.events.queue.join)
            assert not any(json.loads(line)['event'] == 'api.frame.latency_ms' for line in output.getvalue().splitlines())
            if ending == 'cancel':
                tasks[0].cancel()
            else:
                releases[0].set()
            await asyncio.gather(tasks[0], return_exceptions=True)
            assert await asyncio.wait_for(entered.get(), 2) == 2
            # One terminal response frees one slot, never two.
            start(3)
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(entered.get(), .1)
            assert len(calls) == 3
            releases[1].set()
            assert await asyncio.wait_for(entered.get(), 2) == 3
        finally:
            for release in releases:
                release.set()
            await asyncio.gather(*tasks, return_exceptions=True)
        assert (await request(app))[0]['status'] == 200
    asyncio.run(run())
