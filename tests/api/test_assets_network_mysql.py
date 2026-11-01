"""Actual TCP disconnect during a stored asset download, without DB checkout."""
import asyncio
from concurrent.futures import Future
import socket
from threading import Event, Thread
from time import monotonic

import pytest
import uvicorn
from uvicorn.protocols.http.h11_impl import H11Protocol

from test_cases_view_mysql import api_db
from test_assets_mysql import prepare, url
from tests.recording.test_ownership_reads import padded_mp4

pytestmark = pytest.mark.mysql


def require_pending(snapshot):
    """A completed send before client close is never disconnect evidence."""
    assert snapshot['drain_pending'] and snapshot['write_paused']
    assert snapshot['send_pending'] and not snapshot['lifetime_ended']
    assert snapshot['checkedout'] == 0


@pytest.mark.mysql_check('api_asset', 'send', parameter='network_disconnect')
def test_tcp_disconnect_releases_download_without_holding_db(api_db):
    content = padded_mp4(16*1024*1024)
    app, owner, _, ref, _, output = prepare(api_db, content)
    composition = app.state.composition
    draining, disconnected, ended = Event(), Event(), Event()
    state = {'send_pending': False, 'drain_task': None, 'protocol': None,
             'disconnected_at': None, 'ended_at': None}
    failures = []

    class Protocol(H11Protocol):
        def connection_made(self, transport):
            super().connection_made(transport)
            state['protocol'] = self
            transport.get_extra_info('socket').setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
            transport.set_write_buffer_limits(high=4096, low=1024)
            original = self.flow.drain

            async def observe_drain():
                pending = asyncio.create_task(original())
                state['drain_task'] = pending
                try:
                    # One scheduling turn lets the real Uvicorn drain reach its
                    # writable-event wait. No timer manufactures backpressure.
                    await asyncio.sleep(0)
                    if self.flow.write_paused and not pending.done():
                        draining.set()
                    await pending
                finally:
                    if not pending.done():
                        pending.cancel()
                    await asyncio.gather(pending, return_exceptions=True)
            self.flow.drain = observe_drain

        def connection_lost(self, exc):
            super().connection_lost(exc)
            state['disconnected_at'] = monotonic()
            disconnected.set()

    async def transport(scope, receive, send):
        if scope['type'] != 'http':
            return await app(scope, receive, send)
        async def observe(message):
            assert composition.engine.pool.checkedout() == 0
            body = message.get('body', b'') if message['type'] == 'http.response.body' else b''
            if body:
                state['send_pending'] = True
                try:
                    for offset in range(0, len(body), 65536):
                        piece = body[offset:offset+65536]
                        await send(dict(message, body=piece,
                            more_body=message.get('more_body', False) or offset+len(piece) < len(body)))
                finally:
                    state['send_pending'] = False
            else:
                await send(message)
        try:
            await app(scope, receive, observe)
        finally:
            state['ended_at'] = monotonic()
            ended.set()
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    ready = Event()
    class Server(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets=sockets)
            ready.set()
    server = Server(uvicorn.Config(transport, http=Protocol, log_config=None, access_log=False, lifespan='on'))
    def serve():
        try:
            asyncio.run(server.serve(sockets=[listener]))
        except BaseException as error:
            failures.append(error)
    worker = Thread(target=serve, daemon=True)
    client = socket.socket()
    try:
        worker.start()
        assert ready.wait(4)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        client.settimeout(4)
        client.connect(('127.0.0.1', port))
        client.sendall(f'GET {url(owner, ref)} HTTP/1.1\r\nHost: localhost\r\n\r\n'.encode())
        headers = b''
        while not headers.endswith(b'\r\n\r\n') and len(headers) < 8192:
            value = client.recv(1)
            assert value
            headers += value
        assert headers.startswith(b'HTTP/1.1 200')
        assert f'content-length: {len(content)}'.encode() in headers.lower()
        assert b'cache-control: private, no-store' in headers.lower()
        assert draining.wait(4), 'no actual downstream drain wait observed'
        proof = Future()
        def snapshot():
            protocol, pending = state['protocol'], state['drain_task']
            proof.set_result({'drain_pending': pending is not None and not pending.done(),
                'write_paused': protocol.flow.write_paused,
                'send_pending': state['send_pending'], 'lifetime_ended': ended.is_set(),
                'checkedout': composition.engine.pool.checkedout()})
        state['protocol'].loop.call_soon_threadsafe(snapshot)
        require_pending(proof.result(timeout=2))
        assert not ended.is_set()
        client.shutdown(socket.SHUT_RDWR)
        client.close()
        assert disconnected.wait(4), 'transport did not observe client close'
        assert ended.wait(4), 'request ASGI lifetime survived disconnect'
        assert state['ended_at'] >= state['disconnected_at'], 'ASGI already ended before disconnect'
    finally:
        client.close()
        server.should_exit = True
        if worker.ident is not None: worker.join(5)
        listener.close()
        composition.close()
        assert not worker.is_alive()
    assert composition.engine.pool.checkedout() == 0
    assert not server.server_state.tasks and not server.server_state.connections
    assert not failures
    assert state['drain_task'].done() and not state['send_pending']
    from test_asset_lifetime import asset_metrics
    byte_event, latency = asset_metrics(output)
    # This Uvicorn version returns normally from send after disconnect. The
    # outer downstream adapter therefore accepts the whole body, even though
    # this client deliberately never reads it. These metrics are not TCP ACKs.
    assert byte_event['status'] == latency['status'] == '200'
    assert byte_event['count'] == len(content)
