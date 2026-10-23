"""Real supported API subprocess: receive timeouts close without an HTTP status."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest


@pytest.mark.parametrize('reason', ['idle', 'duration'])
def test_upload_timeout_closes_without_status(tmp_path, reason):
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    env_file = tmp_path / 'runtime.env'
    env_file.write_text('DAESINGO_RUNTIME_DB_URL=mysql+pymysql://test:secret@127.0.0.1:1/test_upload\n'
        f'DAESINGO_RUNTIME_MEDIA_ROOT={tmp_path}\nDAESINGO_RUNTIME_API_TEMP_ROOT={tmp_path}\n'
        'DAESINGO_RUNTIME_API_UPLOAD_IDLE_TIMEOUT_SEC=0.15\n'
        f'DAESINGO_RUNTIME_API_UPLOAD_MAX_DURATION_SEC={.3 if reason == "duration" else 3}\n', encoding='utf-8')
    env = dict(os.environ, DAESINGO_ENV_FILE=str(env_file))
    process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-m', 'daesingo.api',
        '--revision', 'test', '--host', '127.0.0.1', '--port', str(port)], env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic()+8
        while True:
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.1) as health:
                    health.sendall(b'GET /health/live HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
                    assert b'200 OK' in health.recv(4096)
                break
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    pytest.fail('owned API did not become live')
                time.sleep(.02)
        with socket.create_connection(('127.0.0.1', port), timeout=1) as upload:
            upload.sendall(b'POST /cases/case_upload/sources HTTP/1.1\r\nHost: localhost\r\n'
                b'Content-Type: multipart/form-data; boundary=boundary\r\nTransfer-Encoding: chunked\r\n\r\n')
            # Valid partial header: do not let malformed syntax terminate first.
            chunk = b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="PRIVATE.mp4"\r\n\r\n'
            upload.sendall(f'{len(chunk):x}\r\n'.encode()+chunk+b'\r\n')
            if reason == 'duration':
                for _ in range(8):
                    time.sleep(.05)
                    try:
                        upload.sendall(b'1\r\nx\r\n')
                    except OSError:
                        break
            upload.settimeout(2)
            try:
                received = upload.recv(4096)
            except (ConnectionResetError, ConnectionAbortedError):
                received = b''
            assert received == b''
        assert list(tmp_path.glob('source/*')) == []
    finally:
        process.terminate()
        stdout, stderr = process.communicate(timeout=8)
        assert process.poll() is not None
        assert b'PRIVATE' not in stdout+stderr and b'secret' not in stdout+stderr
        with socket.socket() as check:
            check.settimeout(.2)
            assert check.connect_ex(('127.0.0.1', port)) != 0
