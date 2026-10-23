"""Actual TCP backpressure/disconnect, with real ASGI sends and MySQL bytes."""
import asyncio
import socket
import struct
from threading import Event, Lock, Thread
import zlib

import pytest
import uvicorn

from daesingo.api.composition import ApiComposition
from daesingo.recording import RecordingService
from test_cases_view_mysql import api_db
from test_frames import PNG
from test_frames_mysql import prepare, url

pytestmark = pytest.mark.mysql


@pytest.mark.mysql_check('api_frame', 'send_lifetime', parameter='network_disconnect')
def test_tcp_disconnect_releases_backpressured_frame_without_db_checkout(api_db, monkeypatch):
    # Valid ancillary PNG chunk: large enough to exercise transport backpressure,
    # without fabricating a new image format or invoking an image decoder.
    padding = b'\0' * (16 * 1024 * 1024)
    chunk = b'npAD' + padding
    content = PNG[:-12] + struct.pack('>I', len(padding)) + chunk + struct.pack('>I', zlib.crc32(chunk)) + PNG[-12:]
    app, owner, _, ref, _, _ = prepare(api_db, content)
    composition = app.state.composition
    calls, clients = [], []
    active = 0
    lock, two_sends = Lock(), Event()
    real = ApiComposition.load_frame
    def load(self, *args):
        calls.append(True)
        return real(self, *args)
    def forbidden(*args, **kwargs):
        raise AssertionError('regeneration/provider/decoder invoked')
    monkeypatch.setattr(ApiComposition, 'load_frame', load)
    monkeypatch.setattr(RecordingService, 'resolve_frame', forbidden)
    monkeypatch.setattr('daesingo.recording.frames.FfmpegFrameExtractor.extract', forbidden)
    monkeypatch.setattr('daesingo.recording.probe.FfprobeMediaProbe.probe', forbidden)
    async def transport(scope, receive, send):
        async def observe(message):
            nonlocal active
            body = message['type'] == 'http.response.body'
            if body:
                with lock:
                    active += 1
                    if active == 2: two_sends.set()
            try:
                payload = message.get('body', b'') if body else b''
                if payload:
                    # Legal server-side fragmentation forces subsequent writes
                    # to observe drain even when an OS accepts the first large
                    # write into its asynchronous transport buffer immediately.
                    # Every await below is a real Uvicorn send, never a test gate.
                    for offset in range(0, len(payload), 65536):
                        piece = payload[offset:offset + 65536]
                        await send(dict(message, body=piece,
                            more_body=message.get('more_body', False) or offset + len(piece) < len(payload)))
                else:
                    await send(message)
            finally:
                if body:
                    with lock: active -= 1
        await app(scope, receive, observe)
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    listener.listen(128)
    ready = Event()
    class Server(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets=sockets)
            ready.set()
    server = Server(uvicorn.Config(transport, log_config=None, access_log=False, lifespan='on'))
    worker = Thread(target=lambda: asyncio.run(server.serve(sockets=[listener])), daemon=True)
    def connect():
        client = socket.socket()
        # Set before handshake so the TCP receive window is bounded on hosts
        # with loopback auto-tuning. Drain can block on payload or final send.
        client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        client.settimeout(3)
        client.connect(('127.0.0.1', port))
        clients.append(client)
        client.sendall(f'GET {url(owner, ref)} HTTP/1.1\r\nHost: localhost\r\n\r\n'.encode())
        return client
    def headers(client):
        data = b''
        while not data.endswith(b'\r\n\r\n') and len(data) < 8192:
            value = client.recv(1)
            assert value
            data += value
        assert data.startswith(b'HTTP/1.1 200')
        assert f'content-length: {len(content)}'.encode() in data.lower()
    try:
        worker.start()
        assert ready.wait(3)
        first = connect(); headers(first)
        second = connect(); headers(second)
        assert two_sends.wait(3), {'active_body_sends': active, 'loads': len(calls)}
        third = connect()
        third.settimeout(.1)
        with pytest.raises(socket.timeout): third.recv(1)
        assert len(calls) == 2 and composition.engine.pool.checkedout() == 0
        first.shutdown(socket.SHUT_RDWR); first.close()
        third.settimeout(3)
        headers(third)
        assert len(calls) == 3
    finally:
        for client in clients:
            client.close()
        server.should_exit = True
        if worker.ident is not None: worker.join(5)
        listener.close()
        composition.close()
        assert not worker.is_alive()
    assert composition.engine.pool.checkedout() == 0
