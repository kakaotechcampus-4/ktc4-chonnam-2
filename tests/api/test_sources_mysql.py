"""RT-11(a): durable public registration through real MySQL caller transactions."""
from concurrent.futures import ThreadPoolExecutor
import asyncio
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
import daesingo.case as case_api
from daesingo.api.app import create_app
from daesingo.recording import RecordingService
from daesingo.recording import FfprobeMediaProbe
from daesingo.recording.probe import LocalSource, ProbedStream
from daesingo.recording.mysql_repository import MySQLRecordingRepository
from daesingo.recording import RecordingCapabilityError
from daesingo.api.composition import ApiComposition
from mysql_fault_proxy import CommitResponseProxy
from test_cases_view_mysql import api_db, store
from test_sources import multipart, MEDIA, envelope, invoke, scope

pytestmark = pytest.mark.mysql


class Probe:
    def probe(self, path):
        stat = path.stat()
        return LocalSource(path, stat.st_size, stat.st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest(), 1., (ProbedStream(0, 'VIDEO', 1.),))


def prepare(api_db, monkeypatch):
    startup, stream, engine = api_db
    monkeypatch.setattr('daesingo.api.composition.FfprobeMediaProbe', Probe)
    app = create_app(startup=startup)
    with engine.begin() as conn:
        identity = case_api.create_case(store=store(conn))
    return app, identity, engine, stream


def count(engine):
    with engine.connect() as conn:
        return conn.exec_driver_sql('SELECT COUNT(*) FROM recording_entry').scalar_one()


@pytest.mark.mysql_check('api_upload', 'durability', parameter='commit_restore')
def test_201_restores_from_new_service_after_commit(api_db, monkeypatch):
    app, identity, engine, output = prepare(api_db, monkeypatch)
    filename = '../PRIVATE_한글.mp4'
    with TestClient(app) as client:
        response = client.post(f'/cases/{identity}/sources', content=multipart(filename), headers=MEDIA)
        assert response.status_code == 201
        body = response.json()
        assert body['case_view']['manifest_summary']['file_count'] == 1
        assert body['case_view']['case_rev'] == 1
        with engine.begin() as conn:
            service = RecordingService(MySQLRecordingRepository(conn, storage_root=app.state.composition.startup.config.media_root))
            ref = {'kind': 'source_asset', 'ref': body['source_asset_ref']}
            assert service.owns_asset(identity, ref)
            assert service.lookup_asset_facts(ref).byte_size == len(b'PRIVATE_PAYLOAD')
            assert case_api.get_view(identity, store=store(conn)) == body['case_view']
    assert 'PRIVATE' not in output.getvalue()


@pytest.mark.mysql_check('api_upload', 'atomicity', parameter='case_reject')
def test_non_intake_leaves_no_recording_or_case_change(api_db, monkeypatch):
    app, identity, engine, _ = prepare(api_db, monkeypatch)
    with engine.begin() as conn:
        case_store = store(conn)
        case = case_store.load_for_update(identity)
        case.start_search()
        case_store.save(case)
        before = case_api.get_view(identity, store=case_store)
    with TestClient(app) as client:
        response = client.post(f'/cases/{identity}/sources', content=multipart(), headers=MEDIA)
    assert response.status_code == 409 and response.json() == envelope('http.source_not_allowed')
    assert count(engine) == 0
    with engine.begin() as conn:
        assert case_api.get_view(identity, store=store(conn)) == before


@pytest.mark.mysql_check('api_upload', 'atomicity', parameter='case_failure')
def test_case_failure_rolls_back_recording(api_db, monkeypatch):
    app, identity, engine, _ = prepare(api_db, monkeypatch)
    def fail(*args, **kwargs):
        raise RuntimeError('PRIVATE payload secret')
    monkeypatch.setattr(case_api, 'record_source_registered', fail)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(f'/cases/{identity}/sources', content=multipart(), headers=MEDIA)
    assert response.status_code == 500
    assert count(engine) == 0
    with engine.begin() as conn:
        assert case_api.get_view(identity, store=store(conn))['manifest_summary']['file_count'] == 0


@pytest.mark.mysql_check('api_upload', 'concurrency', parameter='same_case')
def test_same_case_concurrent_and_repeat_are_distinct(api_db, monkeypatch):
    app, identity, engine, _ = prepare(api_db, monkeypatch)
    connections = []
    original = RecordingService.register_local_source
    def register(self, *args, **kwargs):
        # First write must follow a Case exclusive lock on the caller connection.
        with engine.connect() as other:
            with pytest.raises(sa.exc.OperationalError) as error:
                other.exec_driver_sql('SELECT case_id FROM cases WHERE case_id=%s FOR UPDATE NOWAIT', (identity,))
            assert error.value.orig.args[0] == 3572
        return original(self, *args, **kwargs)
    monkeypatch.setattr(RecordingService, 'register_local_source', register)
    with TestClient(app) as client:
        def post(_):
            return client.post(f'/cases/{identity}/sources', content=multipart(), headers=MEDIA)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(post, range(2)))
        responses.append(post(2))
        assert [r.status_code for r in responses] == [201]*3
        assert len({r.json()['source_asset_ref'] for r in responses}) == 3
        view = client.get(f'/cases/{identity}/view').json()
        assert view['manifest_summary']['file_count'] == 3 and view['case_rev'] == 1


@pytest.mark.mysql_check('api_upload', 'receive', parameter='zero_checkout')
def test_pool_checkout_zero_until_publish_and_shared_transaction(api_db, monkeypatch):
    import daesingo.api.upload as upload
    app, identity, engine, _ = prepare(api_db, monkeypatch)
    pool = app.state.composition.engine.pool
    checkpoints, connections, snapshots = [], [], []
    real_publish = upload.publish
    real_register = RecordingService.register_local_source
    real_case = case_api.record_source_registered
    def publish(*args):
        assert pool.checkedout() == 0
        checkpoints.append('publish')
        return real_publish(*args)
    def register(self, *args, **kwargs):
        conn = self._repository._connection
        assert checkpoints == ['publish'] and conn.in_transaction()
        connections.append(conn)
        result = real_register(self, *args, **kwargs)
        assert count(engine) == 0  # Separate connection cannot see uncommitted rows.
        return result
    def attach(*args, store, **kwargs):
        assert store.conn is connections[0] and store.conn.in_transaction()
        real_case(*args, store=store, **kwargs)
    monkeypatch.setattr(upload, 'publish', publish)
    monkeypatch.setattr(RecordingService, 'register_local_source', register)
    monkeypatch.setattr(case_api, 'record_source_registered', attach)
    body = multipart()
    async def perform():
        sent, received = [], 0
        done = asyncio.Event()
        async def receive():
            nonlocal received
            assert pool.checkedout() == 0
            if received == len(body):
                await done.wait()
                return {'type': 'http.disconnect'}
            part = body[received:received+7]
            received += len(part)
            snapshots.append(pool.checkedout())
            return {'type': 'http.request', 'body': part, 'more_body': received < len(body)}
        async def send(message):
            sent.append(message)
            if message['type'] == 'http.response.body' and not message.get('more_body'):
                done.set()
        request_scope = scope(MEDIA)
        request_scope['path'] = f'/cases/{identity}/sources'
        request_scope['raw_path'] = request_scope['path'].encode()
        await app(request_scope, receive, send)
        assert sent[0]['status'] == 201
    try:
        asyncio.run(perform())
        assert snapshots and set(snapshots) == {0} and pool.checkedout() == 0
    finally:
        app.state.composition.close()


@pytest.mark.parametrize('kind,status,code', [
    pytest.param('unsupported', 422, 'http.source_rejected', marks=pytest.mark.mysql_check('api_upload', 'taxonomy', parameter='unsupported')),
    pytest.param('tool', 503, 'http.dependency_unavailable', marks=pytest.mark.mysql_check('api_upload', 'taxonomy', parameter='tool')),
    pytest.param('read', 503, 'http.dependency_unavailable', marks=pytest.mark.mysql_check('api_upload', 'taxonomy', parameter='read')),
    pytest.param('unexpected', 500, 'http.internal_error', marks=pytest.mark.mysql_check('api_upload', 'taxonomy', parameter='unexpected')),
])
def test_recording_failure_never_changes_case_or_persists_rows(api_db, monkeypatch, kind, status, code):
    app, identity, engine, output = prepare(api_db, monkeypatch)
    def probe(self, path):
        if kind == 'unexpected':
            raise RuntimeError('UNSUPPORTED_MEDIA PRIVATE payload secret /path')
        raise RecordingCapabilityError('UNSUPPORTED_MEDIA' if kind == 'unsupported' else 'TEMPORARY_FAILURE',
            'PRIVATE opposite UNSUPPORTED_MEDIA TEMPORARY_FAILURE /path')
    monkeypatch.setattr(Probe, 'probe', probe)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(f'/cases/{identity}/sources', content=multipart(), headers=MEDIA)
        assert response.status_code == status and response.json() == envelope(code)
        assert client.get(f'/cases/{identity}/view').json()['manifest_summary']['file_count'] == 0
    assert count(engine) == 0 and 'PRIVATE' not in output.getvalue()


@pytest.mark.parametrize('filename', [
    pytest.param('../PRIVATE.mp4', marks=pytest.mark.mysql_check('api_upload', 'filename', parameter='traversal')),
    pytest.param('/PRIVATE.mp4', marks=pytest.mark.mysql_check('api_upload', 'filename', parameter='absolute')),
    pytest.param(r'C:\PRIVATE\file.mp4', marks=pytest.mark.mysql_check('api_upload', 'filename', parameter='separator')),
    pytest.param('PRIVATE_한글_가.mp4', marks=pytest.mark.mysql_check('api_upload', 'filename', parameter='unicode')),
])
def test_original_filename_restores_exactly_separate_from_locator(api_db, monkeypatch, filename):
    app, identity, engine, output = prepare(api_db, monkeypatch)
    root = app.state.composition.startup.config.media_root
    with TestClient(app) as client:
        response = client.post(f'/cases/{identity}/sources', content=multipart(filename), headers=MEDIA)
        assert response.status_code == 201
        with engine.begin() as conn:
            repository = MySQLRecordingRepository(conn, storage_root=root)
            source = repository.get_local_source(response.json()['source_asset_ref'])
            assert source.original_filename == filename
            assert source.path.parent == root/'source' and source.path.name not in filename
    assert 'PRIVATE' not in response.text+output.getvalue()


@pytest.mark.parametrize('reason', [
    pytest.param('idle', marks=pytest.mark.mysql_check('api_upload', 'abort', parameter='idle')),
    pytest.param('duration', marks=pytest.mark.mysql_check('api_upload', 'abort', parameter='duration')),
    pytest.param('disconnect', marks=pytest.mark.mysql_check('api_upload', 'abort', parameter='disconnect')),
])
def test_aborted_stream_has_zero_checkouts_no_final_or_rows(api_db, monkeypatch, reason):
    app, identity, engine, _ = prepare(api_db, monkeypatch)
    startup = app.state.composition.startup
    object.__setattr__(startup, 'config', replace(startup.config, upload=startup.config.upload.model_copy(
        update={'idle_timeout_sec': .04, 'max_duration_sec': .07 if reason == 'duration' else 1})))
    checkouts = []
    sa.event.listen(app.state.composition.engine, 'checkout', lambda *args: checkouts.append(True))
    body = multipart()
    chunks = [body[:100], None] if reason == 'disconnect' else [body[:100]]+[b'x']*9
    delays = [.0, .0] if reason == 'disconnect' else ([.02]*10 if reason == 'duration' else [.0]+[.09]*9)
    import test_sources
    old = test_sources.PATH
    test_sources.PATH = f'/cases/{identity}/sources'
    try:
        sent, consumed, closed = asyncio.run(invoke(app, chunks, MEDIA, delays=delays))
        assert sent == [] and checkouts == []
        assert count(engine) == 0 and list(startup.config.media_root.glob('source/*')) == []
        assert list(startup.config.media_root.glob('staging/*'))
    finally:
        test_sources.PATH = old
        app.state.composition.close()


@pytest.mark.mysql_check('api_upload', 'failure', parameter='missing_case')
def test_missing_case_has_no_registration(api_db, monkeypatch):
    app, _, engine, _ = prepare(api_db, monkeypatch)
    with TestClient(app) as client:
        response = client.post('/cases/missing/sources', content=multipart(), headers=MEDIA)
    assert response.status_code == 404 and response.json() == envelope('http.not_found')
    assert count(engine) == 0


@pytest.mark.mysql_check('api_upload', 'failure', parameter='postcommit_view')
def test_postcommit_view_failure_is_500_with_durable_count(api_db, monkeypatch):
    app, identity, engine, _ = prepare(api_db, monkeypatch)
    def fail(*args):
        raise RuntimeError('PRIVATE path secret')
    monkeypatch.setattr(ApiComposition, 'get_view', fail)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(f'/cases/{identity}/sources', content=multipart(), headers=MEDIA)
    assert response.status_code == 500 and count(engine) > 0
    with engine.begin() as conn:
        assert case_api.get_view(identity, store=store(conn))['manifest_summary']['file_count'] == 1


@pytest.mark.mysql_check('api_upload', 'failure', parameter='commit_ack_loss')
def test_actual_commit_ack_loss_is_500_and_count_n_plus_one(api_db, monkeypatch):
    startup, _, engine = api_db
    app, identity, engine, _ = prepare(api_db, monkeypatch)
    app.state.composition.close()
    url = engine.url
    with CommitResponseProxy(url.host, url.port) as proxy:
        proxied = url.set(port=proxy.port).update_query_dict({'ssl_disabled': 'true'})
        object.__setattr__(startup, 'config', replace(startup.config,
            db=startup.config.db.model_copy(update={'url': type(startup.config.db.url)(proxied.render_as_string(hide_password=False))})))
        app = create_app(startup=startup)
        original = case_api.record_source_registered
        def attach(*args, **kwargs):
            original(*args, **kwargs)
            proxy.arm()
        monkeypatch.setattr(case_api, 'record_source_registered', attach)
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(f'/cases/{identity}/sources', content=multipart(), headers=MEDIA)
        assert proxy.commit_ok_dropped == 1
    assert response.status_code == 500 and response.json() == envelope('http.internal_error')
    with engine.begin() as conn:
        assert case_api.get_view(identity, store=store(conn))['manifest_summary']['file_count'] == 1


@pytest.mark.mysql_check('api_upload', 'durability', parameter='response_loss')
def test_response_delivery_failure_never_claims_uncommitted(api_db, monkeypatch):
    app, identity, engine, _ = prepare(api_db, monkeypatch)
    body = multipart()
    observed = []
    async def perform():
        supplied = False
        async def receive():
            nonlocal supplied
            if not supplied:
                supplied = True
                return {'type': 'http.request', 'body': body, 'more_body': False}
            await asyncio.Event().wait()
        async def send(message):
            if message['type'] == 'http.response.start':
                observed.append(message['status'])
                raise OSError('synthetic response loss')
        request_scope = scope(MEDIA)
        request_scope['path'] = f'/cases/{identity}/sources'
        request_scope['raw_path'] = request_scope['path'].encode()
        try:
            await app(request_scope, receive, send)
        except OSError:
            pass
    try:
        asyncio.run(perform())
        assert observed == [201]
        with engine.begin() as conn:
            assert case_api.get_view(identity, store=store(conn))['manifest_summary']['file_count'] == 1
    finally:
        app.state.composition.close()


@pytest.mark.parametrize('declared,extra', [pytest.param(declared, extra,
    marks=pytest.mark.mysql_check('api_upload', 'limit',
        parameter=('excess' if extra else 'exact')+('_declared' if declared else '_stream')))
    for declared in (False, True) for extra in (0, 1)])
def test_body_limit_counts_multipart_without_receiving_or_registering_after_excess(api_db, monkeypatch, declared, extra):
    app, identity, engine, _ = prepare(api_db, monkeypatch)
    startup = app.state.composition.startup
    body = multipart()
    object.__setattr__(startup, 'config', replace(startup.config,
        upload=startup.config.upload.model_copy(update={'max_bytes': len(body)})))
    headers = dict(MEDIA)
    if declared:
        headers['content-length'] = str(len(body)+extra)
    async def perform():
        sent, consumed = [], []
        done = asyncio.Event()
        chunks = [body[:90], body[90:]+b'x'*extra]
        async def receive():
            if len(consumed) == 2:
                if extra:
                    raise AssertionError('body consumed after rejection')
                await done.wait()
                return {'type': 'http.disconnect'}
            part = chunks[len(consumed)]
            consumed.append(True)
            return {'type': 'http.request', 'body': part, 'more_body': bool(extra) or len(consumed) < 2}
        async def send(message):
            sent.append(message)
            if message['type'] == 'http.response.body' and not message.get('more_body'):
                done.set()
        request_scope = scope(headers)
        request_scope['path'] = f'/cases/{identity}/sources'
        await app(request_scope, receive, send)
        assert sent[0]['status'] == (413 if extra else 201)
    try:
        asyncio.run(perform())
        assert (count(engine) == 0) is bool(extra)
    finally:
        app.state.composition.close()


@pytest.mark.parametrize('kind', [pytest.param(kind,
    marks=pytest.mark.mysql_check('api_upload', 'transport', parameter=kind))
    for kind in ('media', 'missing', 'multiple', 'filename', 'truncated')])
def test_bad_transport_never_registers_in_mysql(api_db, monkeypatch, kind):
    app, identity, engine, _ = prepare(api_db, monkeypatch)
    body, headers = multipart(), MEDIA
    if kind == 'media':
        headers = {'content-type': 'application/json'}
    elif kind == 'missing':
        body = b'--boundary--\r\n'
    elif kind == 'multiple':
        body = multipart()[:-len(b'--boundary--\r\n')]+multipart()
    elif kind == 'filename':
        body = multipart(filename=None)
    else:
        body = multipart()[:-8]
    with TestClient(app) as client:
        response = client.post(f'/cases/{identity}/sources', content=body, headers=headers)
    assert response.status_code == (415 if kind == 'media' else 400) and count(engine) == 0


@pytest.mark.parametrize('fault', [pytest.param(fault,
    marks=pytest.mark.mysql_check('api_upload', 'storage', parameter=fault))
    for fault in ('fsync', 'device', 'publish')])
def test_storage_failure_leaves_no_db_or_final_file(api_db, monkeypatch, fault):
    import daesingo.api.upload as upload
    app, identity, engine, _ = prepare(api_db, monkeypatch)
    if fault == 'device':
        original = Path.stat
        def stat(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if path.name == 'source':
                values = list(result)
                values[2] += 1
                return os.stat_result(values)
            return result
        monkeypatch.setattr(Path, 'stat', stat)
    else:
        def fail(*args):
            raise OSError('PRIVATE payload secret')
        monkeypatch.setattr(os, 'fsync' if fault == 'fsync' else 'replace', fail)
    with TestClient(app) as client:
        response = client.post(f'/cases/{identity}/sources', content=multipart(), headers=MEDIA)
    assert response.status_code == 503 and count(engine) == 0
    assert list(app.state.composition.startup.config.media_root.glob('source/*')) == []


@pytest.mark.mysql_check('api_upload', 'receive', parameter='probe_before_checkout')
def test_public_media_probe_runs_before_checkout_and_case_lock(api_db, monkeypatch):
    startup, _, engine = api_db
    with engine.begin() as conn:
        identity = case_api.create_case(store=store(conn))
    app = create_app(startup=startup)
    observed = []
    def probe(self, path):
        observed.append(app.state.composition.engine.pool.checkedout())
        assert observed[-1] == 0
        with engine.begin() as conn:
            assert conn.exec_driver_sql('SELECT case_id FROM cases WHERE case_id=%s FOR UPDATE NOWAIT',
                (identity,)).scalar_one() == identity
        return Probe().probe(path)
    monkeypatch.setattr(FfprobeMediaProbe, 'probe', probe)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(f'/cases/{identity}/sources', content=multipart(), headers=MEDIA)
    assert response.status_code == 201 and observed == [0]


@pytest.mark.mysql_check('api_upload', 'receive', parameter='prepared_mutation')
def test_mutation_after_preprobe_is_rejected_without_registration(api_db, monkeypatch):
    from daesingo.case.store import CaseStore
    app, identity, engine, _ = prepare(api_db, monkeypatch)
    original = CaseStore.load_for_update
    def lock(self, case_id):
        case = original(self, case_id)
        path, = app.state.composition.startup.config.media_root.glob('source/*')
        path.write_bytes(path.read_bytes()+b'changed')
        return case
    monkeypatch.setattr(CaseStore, 'load_for_update', lock)
    with TestClient(app) as client:
        response = client.post(f'/cases/{identity}/sources', content=multipart(), headers=MEDIA)
    assert response.status_code == 503 and count(engine) == 0
