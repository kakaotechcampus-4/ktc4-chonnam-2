"""RT-11(c): public Recording reads, actual MySQL ownership and ASGI lifetime."""
import asyncio
from contextlib import ExitStack
from io import BytesIO
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time
from threading import Event
from urllib.parse import quote

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

import daesingo.case as case_api
from daesingo.api.app import create_app
from daesingo.recording import RecordingService, RecordingCapabilityError, ContractRef, OpenedDerivedAsset
from daesingo.recording.mysql_repository import MySQLRecordingRepository, entries, _key
from test_cases_view_mysql import api_db, store
from test_frames import PNG, request
from test_sources import envelope
from tests.recording.test_ownership_reads import MP4, OTHER_MP4, asset

pytestmark = pytest.mark.mysql


def check(scenario, parameter):
    return pytest.mark.mysql_check('api_asset', scenario, parameter=parameter)


def url(case, ref):
    return f'/cases/{quote(case, safe="")}/assets/{quote(ref, safe="")}'


def seed(conn, root, owner, ref='opaque', content=MP4, content_type='video/mp4'):
    with RecordingService(MySQLRecordingRepository(conn, storage_root=root)) as service:
        value = asset(len(content) if content is not None else 0, derived_asset_ref=ref)
        service.register_derived_asset(value, content=content,
            content_type=content_type if content is not None else None, case_id=owner)
    return ref


def prepare(api_db, content=MP4, content_type='video/mp4'):
    startup, output, engine = api_db
    with engine.begin() as conn:
        owner, other = [case_api.create_case(store=store(conn)) for _ in range(2)]
        ref = seed(conn, startup.config.media_root, owner, content=content, content_type=content_type)
    return create_app(startup=startup), owner, other, ref, engine, output


@pytest.mark.parametrize('content,content_type,filename', [
    pytest.param(MP4, 'video/mp4', 'daesingo_asset.mp4', id='mp4', marks=check('read', 'mp4')),
    pytest.param(PNG, 'image/png', 'daesingo_asset.png', id='png', marks=check('read', 'png')),
])
def test_stored_bytes_real_format_headers_and_no_regeneration(api_db, monkeypatch, content, content_type, filename):
    app, owner, _, ref, _, output = prepare(api_db, content, content_type)
    def forbidden(*args, **kwargs):
        raise AssertionError('provider or generation during download')
    for name in ('register_derived_asset', 'build_incident_clip', 'resolve_frame', 'prepare_analysis_source'):
        monkeypatch.setattr(RecordingService, name, forbidden)
    monkeypatch.setattr('daesingo.recording.probe.FfprobeMediaProbe.probe', forbidden)
    with TestClient(app) as client:
        for _ in range(2):
            response = client.get(url(owner, ref), headers={'Range': 'bytes=0-1'})
            assert response.status_code == 200 and response.content == content
            assert response.headers['content-type'] == content_type
            assert response.headers['content-length'] == str(len(content))
            assert response.headers['content-disposition'] == f'attachment; filename="{filename}"'
            assert response.headers['cache-control'] == 'private, no-store'
            assert 'content-range' not in response.headers
        assert app.state.composition.engine.pool.checkedout() == 0


@check('read', 'safe_filename')
def test_attachment_never_contains_opaque_ref_or_private_filename(api_db):
    startup, output, engine = api_db
    opaque = 'PRIVATE_차량123_"; filename="secret\r\nX-Private: true'
    with engine.begin() as conn:
        owner = case_api.create_case(store=store(conn))
        seed(conn, startup.config.media_root, owner, opaque)
    app = create_app(startup=startup)
    with TestClient(app) as client:
        response = client.get(url(owner, opaque))
        assert response.status_code == 200 and response.content == MP4
        assert response.headers['content-disposition'] == 'attachment; filename="daesingo_asset.mp4"'
        assert response.headers['content-disposition'].isascii() and 'x-private' not in response.headers
    assert not any(s in output.getvalue() for s in ('PRIVATE', '차량123', 'secret'))


@check('transaction', 'headers_after_checkin')
def test_transaction_ends_and_connection_returns_before_header_construction(api_db, monkeypatch):
    import daesingo.api.routes_assets as route
    app, owner, _, ref, _, _ = prepare(api_db)
    composition = app.state.composition
    endings = []
    def commit(*args): endings.append('commit')
    def checkin(*args): endings.append('checkin')
    real = route.Response
    def response(*args, **kwargs):
        assert composition.engine.pool.checkedout() == 0 and endings[-2:] == ['commit', 'checkin']
        endings.append('headers')
        return real(*args, **kwargs)
    sa.event.listen(composition.engine, 'commit', commit)
    sa.event.listen(composition.engine, 'checkin', checkin)
    monkeypatch.setattr(route, 'Response', response)
    try:
        with TestClient(app) as client:
            result = client.get(url(owner, ref))
            assert result.status_code == 200 and result.content == MP4
        assert endings[-1] == 'headers'
    finally:
        sa.event.remove(composition.engine, 'commit', commit)
        sa.event.remove(composition.engine, 'checkin', checkin)


@pytest.mark.parametrize('kind', [pytest.param(k, marks=check('isolation', k)) for k in
    ('missing_case', 'unknown', 'foreign', 'wrong_kind', 'unavailable', 'missing_bytes', 'invalid_bytes')])
def test_not_found_is_private_and_unavailable_is_distinct(api_db, kind):
    app, owner, other, ref, engine, output = prepare(api_db, None if kind == 'missing_bytes' else MP4)
    if kind in ('unavailable', 'invalid_bytes'):
        with engine.begin() as conn:
            if kind == 'unavailable':
                conn.exec_driver_sql("UPDATE recording_entry SET payload=JSON_SET(payload, '$.availability', 'UNAVAILABLE') WHERE kind='derived_asset'")
            else:
                conn.exec_driver_sql("UPDATE recording_entry SET content=%s WHERE kind='derived_asset'", (b'PRIVATE_CORRUPT',))
    if kind == 'wrong_kind':
        with engine.begin() as conn:
            from daesingo.recording import load_recording_fixture
            repo = MySQLRecordingRepository(conn, storage_root=app.state.composition.startup.config.media_root)
            source = load_recording_fixture('scenario_happy_001').source_assets[0]
            repo.add_source_asset(source)
            repo.associate_case_asset(owner, ContractRef(kind='source_asset', ref=source.source_asset_ref))
            ref = source.source_asset_ref
    case = 'missing' if kind == 'missing_case' else other if kind == 'foreign' else owner
    if kind == 'unknown': ref = 'missing'
    unavailable = kind in ('unavailable', 'missing_bytes', 'invalid_bytes')
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(url(case, ref))
        assert response.status_code == 404
        assert response.json() == envelope('http.ref_unavailable' if unavailable else 'http.not_found')
        assert 'content-disposition' not in response.headers
        if unavailable:
            foreign = client.get(url(other, ref))
            unknown = client.get(url(other, 'missing'))
            assert foreign.status_code == unknown.status_code == 404 and foreign.content == unknown.content
    assert not any(s in output.getvalue() + response.text for s in ('PRIVATE', 'Traceback', 'recording_entry'))


PAIRS = (('trailing', 'asset', 'asset '), ('leading', 'asset', ' asset'),
         ('case', 'asset', 'ASSET'), ('multiple', 'asset ', 'asset  '),
         ('unicode', '자료_é', '자료_e\u0301'), ('unicode_space', '자료_🚗', '자료_🚗 '))


@pytest.mark.parametrize('variant,left,right', [pytest.param(*p, marks=check('exact_identity', 'ref_'+p[0])) for p in PAIRS])
def test_exact_refs_and_bidirectional_cross_case_bytes(api_db, variant, left, right):
    startup, output, engine = api_db
    with engine.begin() as conn:
        cases = [case_api.create_case(store=store(conn)) for _ in range(2)]
        for case, ref, content in zip(cases, (left, right), (MP4, OTHER_MP4)):
            seed(conn, startup.config.media_root, case, ref, content)
    app = create_app(startup=startup)
    with TestClient(app) as client:
        for i in range(2):
            ref, other_ref = (left, right) if i == 0 else (right, left)
            response = client.get(url(cases[i], ref))
            assert response.status_code == 200 and response.content == (MP4, OTHER_MP4)[i]
            unknown = client.get(url(cases[i], 'unknown'))
            foreign = client.get(url(cases[i], other_ref))
            assert foreign.status_code == unknown.status_code == 404 and foreign.content == unknown.content


@pytest.mark.parametrize('variant,left,right', [pytest.param(*p, marks=check('exact_identity', 'scope_'+p[0])) for p in PAIRS])
def test_exact_public_scope_then_http_alias_is_not_authorized(api_db, variant, left, right):
    startup, output, engine = api_db
    with engine.begin() as conn:
        for scope, ref in ((left, 'left'), (right, 'right')):
            seed(conn, startup.config.media_root, scope, ref)
        service = RecordingService(MySQLRecordingRepository(conn, storage_root=startup.config.media_root))
        for scope, own, foreign in ((left, 'left', 'right'), (right, 'right', 'left')):
            assert service.owns_asset(scope, ContractRef(kind='derived_asset', ref=own))
            assert not service.owns_asset(scope, ContractRef(kind='derived_asset', ref=foreign))
            with service.open_derived_asset(own).stream as stream:
                assert stream.read() == MP4
        owner = case_api.create_case(store=store(conn))
        seed(conn, startup.config.media_root, owner, 'http')
    alias = {'trailing': owner+' ', 'leading': ' '+owner, 'case': owner.upper(),
             'multiple': owner+'  ', 'unicode': owner+'é', 'unicode_space': owner+'\u00a0'}[variant]
    app = create_app(startup=startup)
    with TestClient(app) as client:
        assert client.get(url(owner, 'http')).status_code == 200
        for case in (alias, 'unknown'):
            response = client.get(url(case, 'http'))
            assert response.status_code == 404 and response.json() == envelope('http.not_found')


@pytest.mark.parametrize('kind,status,code', [
    pytest.param('metadata', 503, 'http.dependency_unavailable', marks=check('corruption', 'metadata')),
    pytest.param('identity', 404, 'http.not_found', marks=check('corruption', 'identity')),
    pytest.param('descriptor', 404, 'http.ref_unavailable', marks=check('corruption', 'descriptor')),
    pytest.param('bytes', 404, 'http.ref_unavailable', marks=check('corruption', 'bytes')),
    pytest.param('relation', 503, 'http.dependency_unavailable', marks=check('corruption', 'relation')),
])
def test_foreign_damaged_metadata_is_never_restored_or_disclosed(api_db, kind, status, code):
    app, owner, other, ref, engine, output = prepare(api_db)
    with engine.begin() as conn:
        field = {'metadata': 'availability', 'identity': 'derived_asset_ref', 'descriptor': 'content_type', 'relation': 'asset_ref'}.get(kind)
        row_kind = {'descriptor': 'derived_content', 'relation': 'case_asset'}.get(kind, 'derived_asset')
        if kind == 'bytes':
            conn.exec_driver_sql("UPDATE recording_entry SET content=%s WHERE kind='derived_asset'", (b'PRIVATE_CORRUPT',))
        else:
            conn.exec_driver_sql("UPDATE recording_entry SET payload=JSON_SET(payload, %s, 'PRIVATE_CORRUPT') WHERE kind=%s", ('$.'+field, row_kind))
    with TestClient(app, raise_server_exceptions=False) as client:
        for scope in (other, owner+' '):
            foreign, unknown = [client.get(url(scope, r)) for r in (ref, 'unknown')]
            assert foreign.status_code == unknown.status_code == 404 and foreign.content == unknown.content
        response = client.get(url(owner, ref))
        assert response.status_code == status and response.json() == envelope(code)
    assert not any(s in output.getvalue() + response.text for s in ('PRIVATE', 'Traceback', 'recording_entry', 'mysql://'))


@check('transaction', 'caller_rollback')
def test_public_capabilities_never_end_caller_transaction(api_db):
    startup, _, engine = api_db
    with engine.connect() as conn:
        tx = conn.begin()
        endings = []
        sa.event.listen(conn, 'commit', lambda c: endings.append('commit'))
        sa.event.listen(conn, 'rollback', lambda c: endings.append('rollback'))
        ref = seed(conn, startup.config.media_root, 'scope')
        with RecordingService(MySQLRecordingRepository(conn, storage_root=startup.config.media_root)) as service:
            assert service.owns_asset('scope', ContractRef(kind='derived_asset', ref=ref))
            opened = service.open_derived_asset(ref)
            with opened.stream:
                assert opened.stream.read() == MP4
        assert conn.in_transaction() and endings == [] and opened.stream.closed
        with engine.connect() as other:
            assert not RecordingService(MySQLRecordingRepository(other, storage_root=startup.config.media_root)).owns_asset('scope', ContractRef(kind='derived_asset', ref=ref))
        tx.rollback()
        assert endings == ['rollback']
    with engine.connect() as conn:
        assert conn.exec_driver_sql('SELECT COUNT(*) FROM recording_entry').scalar_one() == 0


@pytest.mark.parametrize('ending', [pytest.param(e, marks=check('transaction', e)) for e in ('closed_stream', 'read_error', 'length_mismatch')])
def test_stream_closed_before_transaction_returns_even_on_read_failure(api_db, monkeypatch, ending):
    app, owner, _, ref, _, _ = prepare(api_db)
    composition = app.state.composition
    opened_streams = []
    original = RecordingService.open_derived_asset
    class BrokenStream(BytesIO):
        def read(self, *args):
            raise OSError('PRIVATE read')
    def open_asset(self, value):
        opened = original(self, value)
        if ending == 'read_error':
            opened.stream.close()
            opened = OpenedDerivedAsset(BrokenStream(MP4), 'video/mp4', len(MP4))
        if ending == 'length_mismatch':
            opened = OpenedDerivedAsset(opened.stream, opened.content_type, opened.byte_size+1)
        opened_streams.append(opened.stream)
        return opened
    monkeypatch.setattr(RecordingService, 'open_derived_asset', open_asset)
    checked = []
    def checked_in(*args):
        checked.append(True)
        assert opened_streams and all(s.closed for s in opened_streams)
    sa.event.listen(composition.engine, 'checkin', checked_in)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(url(owner, ref))
            assert response.status_code == (200 if ending == 'closed_stream' else 500)
            if ending != 'closed_stream': assert response.json() == envelope('http.internal_error')
        assert checked and all(s.closed for s in opened_streams)
        assert composition.engine.pool.checkedout() == 0
    finally:
        sa.event.remove(composition.engine, 'checkin', checked_in)


@pytest.mark.parametrize('phase,ending', [pytest.param(p, e, marks=check('send', p+'_'+e))
    for p in ('start', 'body', 'final') for e in ('normal', 'cancel', 'disconnect', 'oserror', 'unexpected')])
def test_detached_response_has_zero_checkout_through_all_asgi_exits(api_db, phase, ending):
    # Mutating the loader to return a stream or sending inside its transaction
    # breaks the check at the real outer ASGI boundary, including final send.
    app, owner, _, ref, _, output = prepare(api_db)
    composition = app.state.composition
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        messages = []
        async def send(message):
            messages.append(message)
            assert composition.engine.pool.checkedout() == 0
            target = message['type'] == 'http.response.start' if phase == 'start' else (
                message['type'] == 'http.response.body' and (bool(message.get('body')) if phase == 'body' else not message.get('more_body', False)))
            if target:
                entered.set()
                await release.wait()
                if ending == 'disconnect':
                    from starlette.requests import ClientDisconnect
                    raise ClientDisconnect()
                if ending == 'oserror': raise OSError('PRIVATE send')
                if ending == 'unexpected': raise RuntimeError('PRIVATE send')
        from test_frames import request as invoke
        task = asyncio.create_task(invoke(app, path=url(owner, ref), send=send))
        try:
            await asyncio.wait_for(entered.wait(), 4)
            assert messages[0]['status'] == 200
            if ending == 'cancel': task.cancel()
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
        assert composition.engine.pool.checkedout() == 0
        await asyncio.to_thread(composition.readiness.events.queue.join)
        from test_asset_lifetime import asset_metrics
        byte_event, latency = asset_metrics(output)
        expected = '200' if ending == 'normal' else 'CANCELLED' if ending == 'cancel' else 'FAILED'
        assert byte_event['status'] == latency['status'] == expected
        assert byte_event['count'] == (len(MP4) if ending == 'normal' or phase == 'final' else 0)
        assert (await invoke(app, path=url(owner, ref)))[0]['status'] == 200
    try:
        asyncio.run(run())
    finally:
        composition.close()


@check('send', 'partial_failure')
def test_partial_send_metrics_include_only_returned_chunks_after_checkin(api_db, monkeypatch):
    from starlette.responses import StreamingResponse
    from test_asset_lifetime import asset_metrics
    app, owner, _, ref, _, output = prepare(api_db)
    composition = app.state.composition
    def chunks(content, **kwargs):
        assert composition.engine.pool.checkedout() == 0
        kwargs['headers']['Content-Length'] = str(len(content))
        return StreamingResponse(iter((content[:3], content[3:])), **kwargs)
    monkeypatch.setattr('daesingo.api.routes_assets.Response', chunks)
    async def run():
        bodies = 0
        async def send(message):
            nonlocal bodies
            assert composition.engine.pool.checkedout() == 0
            if message['type'] == 'http.response.body' and message.get('body'):
                bodies += 1
                if bodies == 2: raise OSError('PRIVATE source locator')
        with pytest.raises(OSError):
            await request(app, path=url(owner, ref), send=send)
        await asyncio.to_thread(composition.readiness.events.queue.join)
        byte_event, latency = asset_metrics(output)
        assert byte_event['count'] == 3
        assert byte_event['status'] == latency['status'] == 'FAILED'
        assert (await request(app, path=url(owner, ref)))[0]['status'] == 200
    try:
        asyncio.run(run())
        assert composition.engine.pool.checkedout() == 0 and 'PRIVATE' not in output.getvalue()
    finally:
        composition.close()


@pytest.mark.parametrize('kind', [pytest.param(k, marks=check('failure', k)) for k in
    ('pool', 'disconnect', 'temporary', 'unexpected', 'read_failure', 'validation')])
def test_typed_failures_release_connections_and_allow_next_download(api_db, monkeypatch, kind):
    app, owner, _, ref, engine, output = prepare(api_db)
    composition = app.state.composition
    original = RecordingService.open_derived_asset
    def fail(self, *args):
        if kind == 'disconnect':
            conn = self._repository._connection
            identity = conn.exec_driver_sql('SELECT CONNECTION_ID()').scalar_one()
            with engine.connect() as other:
                other.exec_driver_sql(f'KILL CONNECTION {identity}')
            return original(self, *args)
        if kind in ('temporary', 'read_failure'):
            raise RecordingCapabilityError('TEMPORARY_FAILURE' if kind == 'temporary' else 'UNAVAILABLE', 'PRIVATE')
        if kind == 'validation': raise ValueError('PRIVATE metadata')
        raise RuntimeError('PRIVATE TEMPORARY_FAILURE mysql://secret')
    with TestClient(app, raise_server_exceptions=False) as client:
        with ExitStack() as stack:
            if kind == 'pool':
                for _ in range(3): stack.enter_context(composition.engine.connect())
            else:
                monkeypatch.setattr(RecordingService, 'open_derived_asset', fail)
            response = client.get(url(owner, ref))
            status = 500 if kind in ('unexpected', 'validation') else 404 if kind == 'read_failure' else 503
            code = 'http.internal_error' if status == 500 else 'http.ref_unavailable' if status == 404 else 'http.dependency_unavailable'
            assert response.status_code == status and response.json() == envelope(code)
        monkeypatch.setattr(RecordingService, 'open_derived_asset', original)
        assert client.get(url(owner, ref)).content == MP4
        assert composition.engine.pool.checkedout() == 0
    assert not any(s in output.getvalue() + response.text for s in ('PRIVATE', 'Traceback', 'mysql://'))


@check('transaction', 'cancel_read')
def test_cancelled_read_eventually_closes_stream_transaction_and_connection(api_db, monkeypatch):
    app, owner, _, ref, _, _ = prepare(api_db)
    composition = app.state.composition
    entered, release, checked_in = Event(), Event(), Event()
    streams = []
    original = RecordingService.open_derived_asset
    class Paused(BytesIO):
        def read(self, *args):
            entered.set()
            assert release.wait(5)
            return super().read(*args)
    def opened(self, value):
        result = original(self, value)
        result.stream.close()
        stream = Paused(MP4)
        streams.append(stream)
        return OpenedDerivedAsset(stream, 'video/mp4', len(MP4))
    monkeypatch.setattr(RecordingService, 'open_derived_asset', opened)
    def checkin(*args):
        assert streams and all(s.closed for s in streams)
        checked_in.set()
    sa.event.listen(composition.engine, 'checkin', checkin)
    async def run():
        task = asyncio.create_task(request(app, path=url(owner, ref)))
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            assert composition.engine.pool.checkedout() == 1
            task.cancel()
            await asyncio.sleep(.05)
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(checked_in.wait, 3)
        # Checkin event fires just before QueuePool updates its checkout count.
        for _ in range(100):
            if composition.engine.pool.checkedout() == 0: break
            await asyncio.sleep(.01)
        assert composition.engine.pool.checkedout() == 0 and all(s.closed for s in streams)
    try:
        asyncio.run(run())
    finally:
        release.set()
        sa.event.remove(composition.engine, 'checkin', checkin)
        composition.close()


@check('read', 'restart')
def test_fresh_process_reads_identical_stored_asset(api_db):
    app, owner, _, ref, _, _ = prepare(api_db)
    config = app.state.composition.startup.config
    app.state.composition.close()
    env = dict(os.environ, ASSET_TEST_DB=config.db.url.get_secret_value(),
        ASSET_TEST_ROOT=str(config.media_root), ASSET_TEST_PATH=url(owner, ref))
    for _ in range(2):
        child = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(Path(__file__).with_name('asset_process.py'))],
            env=env, capture_output=True, timeout=20)
        assert child.returncode == 0 and child.stderr == b'', 'asset child failed (diagnostics withheld)'
        assert json.loads(child.stdout) == {'status': 200, 'sha256': hashlib.sha256(MP4).hexdigest(),
            'type': 'video/mp4', 'length': str(len(MP4)), 'disposition': 'attachment; filename="daesingo_asset.mp4"',
            'cache': 'private, no-store'}


@pytest.mark.parametrize('phase', [pytest.param(p, marks=check('interruption', p)) for p in ('read', 'detached')])
def test_process_interruption_releases_db_and_does_not_change_asset(api_db, tmp_path, phase):
    app, owner, _, ref, engine, _ = prepare(api_db)
    config = app.state.composition.startup.config
    app.state.composition.close()
    marker = tmp_path/'asset-child.json'
    env = dict(os.environ, ASSET_TEST_DB=config.db.url.get_secret_value(), ASSET_TEST_ROOT=str(config.media_root),
        ASSET_TEST_PATH=url(owner, ref), ASSET_TEST_PHASE=phase, ASSET_TEST_MARKER=str(marker))
    child = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', str(Path(__file__).with_name('asset_process.py'))],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic()+10
        while not marker.exists() and child.poll() is None and time.monotonic() < deadline: time.sleep(.02)
        assert marker.exists(), 'asset child did not reach interruption boundary'
        evidence = json.loads(marker.read_text())
        assert evidence['checkedout'] == (1 if phase == 'read' else 0)
        child.kill()
        child.wait(timeout=5)
        if phase == 'read':
            deadline = time.monotonic()+5
            while True:
                with engine.connect() as conn:
                    remaining = conn.exec_driver_sql('SELECT COUNT(*) FROM information_schema.processlist WHERE ID=%s',
                        (evidence['connection'],)).scalar_one()
                if remaining == 0: break
                assert time.monotonic() < deadline
                time.sleep(.02)
        with engine.begin() as conn:
            service = RecordingService(MySQLRecordingRepository(conn, storage_root=config.media_root))
            assert service.owns_asset(owner, ContractRef(kind='derived_asset', ref=ref))
            with service.open_derived_asset(ref).stream as stream: assert stream.read() == MP4
    finally:
        if child.poll() is None: child.kill()
        child.wait(timeout=5)
