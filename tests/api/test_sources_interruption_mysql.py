"""Process kill windows use real publication, MySQL and a separately polling caller."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
import pytest
from daesingo.api.app import create_app
from fastapi.testclient import TestClient
from test_cases_view_mysql import api_db, store
from test_sources_mysql import prepare, count
from test_sources import multipart, MEDIA
import daesingo.case as case_api

pytestmark = pytest.mark.mysql


@pytest.mark.parametrize('mode', [pytest.param(mode,
    marks=pytest.mark.mysql_check('api_upload', 'interruption', parameter=mode))
    for mode in ('before_publish', 'after_publish', 'before_commit', 'after_commit')])
def test_owned_process_kill_keeps_file_before_row_order(api_db, monkeypatch, tmp_path, mode):
    app, identity, engine, _ = prepare(api_db, monkeypatch)
    startup = app.state.composition.startup
    app.state.composition.close()
    root = startup.config.media_root
    env_file = tmp_path/'runtime.env'
    env_file.write_text('DAESINGO_RUNTIME_DB_URL='+engine.url.render_as_string(hide_password=False)+'\n'
        f'DAESINGO_RUNTIME_MEDIA_ROOT={root}\nDAESINGO_RUNTIME_API_TEMP_ROOT={root}\n', encoding='utf-8')
    marker = tmp_path/'checkpoint'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, DAESINGO_ENV_FILE=str(env_file), UPLOAD_CHECKPOINT=str(marker), UPLOAD_KILL_MODE=mode)
    child = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', str(Path(__file__).with_name('source_process.py')),
        '--revision', 'test', '--host', '127.0.0.1', '--port', str(port)], env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    def request():
        try:
            with httpx.Client(timeout=15) as client:
                return client.post(f'http://127.0.0.1:{port}/cases/{identity}/sources', content=multipart(), headers=MEDIA)
        except httpx.TransportError:
            return None
    try:
        deadline = time.monotonic()+8
        while True:
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.1):
                    break
            except OSError:
                assert child.poll() is None and time.monotonic() < deadline, 'owned API startup failed'
                time.sleep(.02)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(request)
            deadline = time.monotonic()+10
            while not marker.exists():
                assert child.poll() is None and not pending.done() and time.monotonic() < deadline, 'checkpoint not reached'
                time.sleep(.02)
            assert count(engine) > 0 if mode == 'after_commit' else count(engine) == 0
            final_files = list(root.glob('source/*'))
            assert len(final_files) == (0 if mode == 'before_publish' else 1)
            child.kill()
            stdout, stderr = child.communicate(timeout=8)
            assert pending.result(timeout=5) is None
        deadline = time.monotonic()+5
        while True:
            with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
                # Audit only this test schema; exclude the audit connection.
                # A plain transactional COUNT could itself enter innodb_trx.
                clients = conn.exec_driver_sql('SELECT COUNT(*) FROM information_schema.innodb_trx t '
                    'JOIN information_schema.processlist p ON p.ID=t.trx_mysql_thread_id '
                    'WHERE p.DB=DATABASE() AND p.ID<>CONNECTION_ID()').scalar_one()
            if clients == 0:
                break
            assert time.monotonic() < deadline
            time.sleep(.02)
        assert count(engine) > 0 if mode == 'after_commit' else count(engine) == 0
        with engine.begin() as conn:
            n = case_api.get_view(identity, store=store(conn))['manifest_summary']['file_count']
        assert n == (1 if mode == 'after_commit' else 0)
        (tmp_path/'orphan-evidence.json').write_text(json.dumps({'mode': mode,
            'final_files': len(final_files), 'staging_files': len(list(root.glob('staging/*'))),
            'file_count': n, 'child_exited': child.poll() is not None,
            'transactions_after_kill': clients}), encoding='utf-8')
        assert b'PRIVATE' not in stdout+stderr and b'secret' not in stdout+stderr
        # A new request remains a new registration after response loss.
        if mode == 'after_commit':
            with TestClient(create_app(startup=startup)) as client:
                result = client.post(f'/cases/{identity}/sources', content=multipart(), headers=MEDIA)
                assert result.status_code == 201
                assert result.json()['case_view']['manifest_summary']['file_count'] == 2
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=8)
        with socket.socket() as check:
            check.settimeout(.2)
            assert check.connect_ex(('127.0.0.1', port)) != 0
