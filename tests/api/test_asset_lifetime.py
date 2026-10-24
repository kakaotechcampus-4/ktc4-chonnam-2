"""Asset metrics surround the real outer ASGI send, not response creation."""
import asyncio
import json

import pytest
from starlette.requests import ClientDisconnect
from starlette.responses import StreamingResponse

from daesingo.api.composition import ApiComposition
from daesingo.case.store import CaseNotFound
from daesingo.recording import RecordingCapabilityError
from test_assets import PATH, asset_app
from test_frames import PNG, request, scope


def asset_metrics(output):
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    metrics = {name: [e for e in events if e['event'] == 'api.asset.' + name]
               for name in ('bytes', 'download_latency_ms')}
    assert all(len(items) == 1 for items in metrics.values())
    return metrics['bytes'][0], metrics['download_latency_ms'][0]


def test_asset_failed_send_has_terminal_metrics_after_common_completion(asset_app):
    app, output = asset_app
    events = app.state.composition.readiness.events

    def captured():
        return [json.loads(line) for line in output.getvalue().splitlines()]

    async def run():
        entered, release = asyncio.Event(), asyncio.Event()

        async def send(message):
            if message['type'] == 'http.response.body' and message.get('body'):
                entered.set()
                await release.wait()
                raise OSError('PRIVATE send failure')

        pending = asyncio.create_task(request(app, path=PATH, send=send))
        try:
            await asyncio.wait_for(entered.wait(), 2)
            await asyncio.to_thread(events.queue.join)
            # This existing event describes response creation, even when the
            # subsequent body send fails. Keep its other-route meaning intact.
            common = [e for e in captured() if e['event'] == 'api.request.completed']
            assert len(common) == 1 and common[0]['status'] == '200'
            assert not any(e['event'].startswith('api.asset.') for e in captured())
        finally:
            release.set()
            result, = await asyncio.gather(pending, return_exceptions=True)
        assert isinstance(result, OSError)
        await asyncio.to_thread(events.queue.join)

    asyncio.run(run())
    names = [e['event'] for e in captured() if e['event'].startswith('api.asset.')]
    assert sorted(names) == ['api.asset.bytes', 'api.asset.download_latency_ms']
    byte_event, latency = asset_metrics(output)
    assert byte_event['count'] == 0 and byte_event['status'] == latency['status'] == 'FAILED'
    assert 'PRIVATE' not in output.getvalue()


@pytest.mark.parametrize('ending', ['normal', 'oserror', 'unexpected', 'disconnect', 'cancel'])
@pytest.mark.parametrize('phase,failed_count', [('start', 0), ('body', 0), ('second', 3), ('final', len(PNG))])
def test_metrics_cover_outer_send_and_count_only_returned_chunks(asset_app, monkeypatch, ending, phase, failed_count):
    """Pre-counting a chunk or measuring inside BaseHTTP fails this test."""
    app, output = asset_app
    events = app.state.composition.readiness.events
    def chunks(content, **kwargs):
        # A deliberately false declaration must never be the metric's source.
        kwargs['headers']['Content-Length'] = '9999'
        return StreamingResponse(iter((content[:3], content[3:])), **kwargs)
    monkeypatch.setattr('daesingo.api.routes_assets.Response', chunks)

    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        sent, returned = [], []
        body_number = 0
        async def send(message):
            nonlocal body_number
            sent.append(message)
            is_body = message['type'] == 'http.response.body'
            if is_body and message.get('body'):
                body_number += 1
            target = (message['type'] == 'http.response.start' if phase == 'start' else
                      is_body and ((body_number == (1 if phase == 'body' else 2) and bool(message.get('body')))
                                   if phase != 'final' else not message.get('more_body', False)))
            if target:
                entered.set()
                await release.wait()
                if ending == 'oserror': raise OSError('PRIVATE locator mysql://secret')
                if ending == 'unexpected': raise RuntimeError('PRIVATE original.mp4')
                if ending == 'disconnect': raise ClientDisconnect()
            returned.append(message)
        pending = asyncio.create_task(request(app, path=PATH, send=send))
        try:
            await asyncio.wait_for(entered.wait(), 3)
            assert app.state.composition.engine.pool.checkedout() == 0
            await asyncio.to_thread(events.queue.join)
            assert 'api.asset.' not in output.getvalue()
            if ending == 'cancel': pending.cancel()
        finally:
            release.set()
            result, = await asyncio.gather(pending, return_exceptions=True)
        assert (result == sent) if ending == 'normal' else isinstance(result, BaseException)
        assert [m['status'] for m in sent if m['type'] == 'http.response.start'] == [200]
        await asyncio.to_thread(events.queue.join)
        return sum(len(m.get('body', b'')) for m in returned if m['type'] == 'http.response.body')

    returned = asyncio.run(run())
    byte_event, latency = asset_metrics(output)
    expected = '200' if ending == 'normal' else 'CANCELLED' if ending == 'cancel' else 'FAILED'
    assert byte_event['status'] == latency['status'] == expected
    assert byte_event['count'] == returned == (len(PNG) if ending == 'normal' else failed_count)
    assert latency['duration_ms'] >= 0
    assert byte_event['trace_id'] == latency['trace_id']
    for event in (byte_event, latency):
        assert not set(event) & {'case_id', 'asset_ref', 'filename', 'locator'}
    assert not any(value in output.getvalue() for value in ('case_asset', 'opaque', 'PRIVATE', 'mysql://', 'original.mp4'))


@pytest.mark.parametrize('failure,status', [
    (CaseNotFound('PRIVATE'), 404),
    (RecordingCapabilityError('TEMPORARY_FAILURE', 'PRIVATE'), 503),
    (RuntimeError('PRIVATE'), 500),
])
def test_error_response_bytes_keep_actual_http_status(asset_app, monkeypatch, failure, status):
    app, output = asset_app
    def fail(*args): raise failure
    monkeypatch.setattr(ApiComposition, 'load_asset', fail)
    messages = asyncio.run(request(app, path=PATH))
    app.state.composition.readiness.events.queue.join()
    byte_event, latency = asset_metrics(output)
    assert messages[0]['status'] == status
    assert byte_event['status'] == latency['status'] == str(status)
    assert byte_event['count'] == len(b''.join(m.get('body', b'') for m in messages)) > 0
    common = [json.loads(line) for line in output.getvalue().splitlines()
              if json.loads(line)['event'] == 'api.request.completed']
    assert len(common) == 1 and common[0]['status'] == str(status)
    assert common[0]['trace_id'] == byte_event['trace_id']


@pytest.mark.parametrize('ending,status,count,duration', [
    ('final', '206', 3, 20_000), ('incomplete', 'CANCELLED', 2, 10_000),
    ('empty', 'CANCELLED', 0, 10_000), ('cancel', 'CANCELLED', 2, 10_000),
    ('fatal', 'FAILED', 2, 10_000),
])
def test_final_send_is_latency_boundary_and_missing_final_is_cancelled(asset_app, monkeypatch, ending, status, count, duration):
    """Timing through post-send cleanup or treating an incomplete app as 200 breaks this."""
    from daesingo.api.asset_lifetime import AssetLifetimeMiddleware
    app, output = asset_app
    clock = 10
    monkeypatch.setattr('daesingo.api.asset_lifetime.monotonic', lambda: clock)
    class Fatal(BaseException): pass
    async def inner(request_scope, receive, send):
        nonlocal clock
        clock = 20
        if ending == 'empty': return
        await send({'type': 'http.response.start', 'status': 206, 'headers': [(b'content-length', b'9999')]})
        await send({'type': 'http.response.body', 'body': b'ab', 'more_body': True})
        if ending == 'cancel': raise asyncio.CancelledError()
        if ending == 'fatal': raise Fatal()
        if ending == 'incomplete': return
        await send({'type': 'http.response.body', 'body': b'c', 'more_body': False})
        # Cleanup after the final successful send does not extend download time.
        clock = 100
    async def send(message):
        nonlocal clock
        if message['type'] == 'http.response.body' and not message.get('more_body'):
            clock = 30
    async def receive(): return {'type': 'http.disconnect'}
    async def run():
        middleware = AssetLifetimeMiddleware(inner, composition=app.state.composition)
        if ending in ('cancel', 'fatal'):
            with pytest.raises(asyncio.CancelledError if ending == 'cancel' else Fatal):
                await middleware(scope(PATH), receive, send)
        else:
            await middleware(scope(PATH), receive, send)
    asyncio.run(run())
    app.state.composition.readiness.events.queue.join()
    byte_event, latency = asset_metrics(output)
    assert byte_event['status'] == latency['status'] == status
    assert byte_event['count'] == count
    assert latency['duration_ms'] == duration


@pytest.mark.parametrize('method,path,root,matched', [
    ('GET', PATH, '', True), ('GET', '/api'+PATH, '/api', True),
    ('POST', PATH, '', False), ('HEAD', PATH, '', False),
    ('GET', PATH+'/', '', False), ('GET', '/cases//assets/ref', '', False),
    ('GET', '/cases/PRIVATE/frames/PRIVATE', '', False),
])
def test_only_exact_asset_get_lifetime_is_observed(asset_app, method, path, root, matched):
    from daesingo.api.asset_lifetime import AssetLifetimeMiddleware
    app, output = asset_app
    async def inner(request_scope, receive, send):
        await send({'type': 'http.response.start', 'status': 204, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})
    async def send(message): pass
    async def receive(): return {'type': 'http.disconnect'}
    request_scope = scope(path)
    request_scope.update(method=method, root_path=root)
    asyncio.run(AssetLifetimeMiddleware(inner, composition=app.state.composition)(request_scope, receive, send))
    app.state.composition.readiness.events.queue.join()
    if matched:
        byte_event, latency = asset_metrics(output)
        assert byte_event['count'] == 0 and byte_event['status'] == latency['status'] == '204'
    else:
        assert 'api.asset.' not in output.getvalue()
