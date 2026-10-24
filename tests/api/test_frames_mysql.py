"""RT-11(b): real ownership, transaction, restart and send/check-out boundaries."""
import asyncio
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Event, Lock

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from daesingo.api.app import create_app
from daesingo.api.composition import ApiComposition
from daesingo.recording import RecordingService, ContractRef, load_recording_fixture, RecordingCapabilityError
from daesingo.recording.mysql_repository import MySQLRecordingRepository
import daesingo.case as case_api
from test_cases_view_mysql import api_db, store
from test_frames import PNG, request
from test_sources import envelope

pytestmark = pytest.mark.mysql


def seed(conn, root, case_id, content=PNG):
    fixture = load_recording_fixture('scenario_happy_001')
    repo = MySQLRecordingRepository(conn, storage_root=root)
    for source in fixture.source_assets:
        repo.add_source_asset(source)
        repo.associate_case_asset(case_id, ContractRef(kind='source_asset', ref=source.source_asset_ref))
    for stream in fixture.media_streams:
        repo.add_media_stream(stream)
    frame = fixture.frame_refs[0]
    repo.add_frame(frame, content=content)
    return frame.frame_ref


def prepare(api_db, content=PNG):
    startup, output, engine = api_db
    with engine.begin() as conn:
        owner = case_api.create_case(store=store(conn))
        other = case_api.create_case(store=store(conn))
        ref = seed(conn, startup.config.media_root, owner, content)
    app = create_app(startup=startup)
    return app, owner, other, ref, engine, output


def url(case, ref):
    return f'/cases/{case}/frames/{ref}'


@pytest.mark.parametrize('layer,boundary,variant,left,right', [pytest.param(layer, boundary, variant, left, right,
    marks=pytest.mark.mysql_check('api_frame', 'exact_identity', parameter=layer + '_' + boundary + '_' + variant))
    for layer in ('capability', 'http') for boundary in ('stream', 'source', 'frame')
    for variant, left, right in (
        ('trailing', 'ms_padding', 'ms_padding '),
        ('leading', 'ms_padding', ' ms_padding'),
        ('case', 'ms_padding', 'MS_PADDING'),
        ('multiple', 'ms_padding ', 'ms_padding  '),
        ('unicode', '자료_é', '자료_e\u0301'),
        ('unicode_space', '자료_🚗', '자료_🚗 '))])
def test_distinct_valid_identities_never_join_other_cases(api_db, layer, boundary, variant, left, right):
    """A collating join must not merge identities that canonical models distinguish."""
    import struct
    import zlib

    startup, output, engine = api_db
    fixture = load_recording_fixture('scenario_happy_001')
    def changed(model, **updates):
        return type(model).model_validate({**model.model_dump(), **updates})
    def image(label):
        chunk = b'tEXt' + b'case\0' + label
        return PNG[:-12] + struct.pack('>I', len(chunk) - 4) + chunk + struct.pack('>I', zlib.crc32(chunk)) + PNG[-12:]
    contents = [image(b'A'), image(b'B')]
    assert left != right and contents[0] != contents[1]
    frames = []
    with engine.begin() as conn:
        cases = [case_api.create_case(store=store(conn)) for _ in range(2)]
        repo = MySQLRecordingRepository(conn, storage_root=startup.config.media_root)
        for i, value in enumerate((left, right)):
            source_ref = value if boundary == 'source' else 'sa_identity_' + str(i)
            stream_ref = value if boundary == 'stream' else 'ms_identity_' + str(i)
            frame_ref = value if boundary == 'frame' else 'fr_identity_' + str(i)
            source = changed(fixture.source_assets[0], source_asset_ref=source_ref, media_stream_refs=[stream_ref])
            stream = changed(fixture.media_streams[0], media_stream_ref=stream_ref, source_asset_ref=source_ref)
            frame = changed(fixture.frame_refs[0], frame_ref=frame_ref, media_stream_ref=stream_ref)
            repo.add_source_asset(source)
            repo.add_media_stream(stream)
            repo.associate_case_asset(cases[i], ContractRef(kind='source_asset', ref=source_ref))
            repo.add_frame(frame, content=contents[i])
            frames.append(frame)
    with engine.connect() as conn:
        service = RecordingService(MySQLRecordingRepository(conn, storage_root=startup.config.media_root))
        for i in range(2):
            assert service.owns_frame(cases[i], frames[i].frame_ref)
            assert not service.owns_frame(cases[i], frames[1-i].frame_ref)
        if layer == 'http':
            conn.rollback()  # Release fixture reads before exercising HTTP.
            conn.close()
            return _check_identity_http(startup, output, engine, cases, frames, contents, left, right)
        selects = []
        def observe(conn, cursor, statement, *args):
            selects.append(statement)
        sa.event.listen(conn, 'before_cursor_execute', observe)
        try:
            for i in range(2):
                assert service.read_owned_frame_image(cases[i], frames[i].frame_ref).content == contents[i]
                with pytest.raises(RecordingCapabilityError) as foreign:
                    service.read_owned_frame_image(cases[i], frames[1-i].frame_ref)
                assert foreign.value.code == 'UNKNOWN_REF'
            assert len(selects) == 4 and all(s.lstrip().upper().startswith('SELECT') for s in selects)
            assert conn.in_transaction()  # No self-commit/rollback/close.
        finally:
            sa.event.remove(conn, 'before_cursor_execute', observe)
    # Capability evidence above uses exactly one SELECT per read.


def _check_identity_http(startup, output, engine, cases, frames, contents, left, right):
    from urllib.parse import quote
    from daesingo.recording.mysql_repository import entries, _key
    app = create_app(startup=startup)
    def path(i, ref):
        return url(cases[i], quote(ref, safe=''))
    with TestClient(app, raise_server_exceptions=False) as client:
        for i in range(2):
            own = client.get(path(i, frames[i].frame_ref))
            assert own.status_code == 200 and own.content == contents[i]
            assert own.headers['content-length'] == str(len(contents[i]))
            assert own.headers['content-type'] == 'image/png'
            assert own.headers['cache-control'] == 'private, max-age=3600'
            unknown = client.get(path(i, 'fr_missing'))
            foreign = client.get(path(i, frames[1-i].frame_ref))
            assert foreign.status_code == unknown.status_code == 404
            assert foreign.content == unknown.content
        for damage, expected_status, code in (
            ('metadata', 503, 'http.dependency_unavailable'), ('bytes', 404, 'http.ref_unavailable')):
            payload = frames[1].model_dump(mode='json')
            if damage == 'metadata':
                payload['source_offset_sec'] = 'PRIVATE_CORRUPT'
            with engine.begin() as conn:
                conn.execute(sa.update(entries).where(entries.c.kind == 'frame',
                    entries.c.entry_key == _key(frames[1].frame_ref)).values(payload=payload,
                    content=contents[1] if damage == 'metadata' else b'PRIVATE_CORRUPT'))
            unknown = client.get(path(0, 'fr_missing'))
            foreign = client.get(path(0, frames[1].frame_ref))
            assert foreign.status_code == unknown.status_code == 404 and foreign.content == unknown.content
            app.state.composition.readiness.events.queue.join()
            statuses = [e['status'] for e in map(json.loads, output.getvalue().splitlines())
                        if e['event'] == 'api.frame.latency_ms']
            assert statuses[-2:] == ['404', '404']
            own = client.get(path(1, frames[1].frame_ref))
            assert own.status_code == expected_status and own.json() == envelope(code)
    assert not any(raw in output.getvalue() for raw in ('PRIVATE', 'CORRUPT', 'Traceback', left, right))


@pytest.mark.mysql_check('api_frame', 'exact_identity', parameter='case_scope')
def test_case_identity_requires_exact_stored_relationship(api_db):
    from urllib.parse import quote
    app, owner, _, ref, engine, output = prepare(api_db)
    alias = owner + ' '
    with engine.begin() as conn:
        service = RecordingService(MySQLRecordingRepository(conn, storage_root=app.state.composition.startup.config.media_root))
        assert service.read_owned_frame_image(owner, ref).content == PNG
        with pytest.raises(RecordingCapabilityError) as failure:
            service.read_owned_frame_image(alias, ref)
        assert failure.value.code == 'UNKNOWN_REF' and conn.in_transaction()
    with TestClient(app, raise_server_exceptions=False) as client:
        own = client.get(url(owner, ref))
        foreign = client.get(url(quote(alias, safe=''), ref))
        unknown = client.get(url(owner, 'fr_missing'))
        assert own.status_code == 200 and own.content == PNG
        assert foreign.status_code == unknown.status_code == 404 and foreign.content == unknown.content
    assert alias not in output.getvalue() and ref not in output.getvalue()


@pytest.mark.mysql_check('api_frame', 'read', parameter='headers_repeat')
def test_exact_image_repeat_and_no_media_tools(api_db, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('provider/decoder/regeneration must not run')
    monkeypatch.setattr('daesingo.recording.frames.FfmpegFrameExtractor.extract', forbidden)
    monkeypatch.setattr('daesingo.recording.probe.FfprobeMediaProbe.probe', forbidden)
    monkeypatch.setattr(RecordingService, 'resolve_frame', forbidden)
    app, owner, _, ref, _, output = prepare(api_db)
    pool = app.state.composition.engine.pool
    with TestClient(app) as client:
        for _ in range(2):
            response = client.get(url(owner, ref))
            assert response.status_code == 200 and response.content == PNG
            assert response.headers['content-type'] == 'image/png'
            assert response.headers['content-length'] == str(len(PNG))
            assert response.headers['cache-control'] == 'private, max-age=3600'
            assert pool.checkedout() == 0
    assert 'Traceback' not in output.getvalue()


@pytest.mark.mysql_check('api_frame', 'read', parameter='process_restart')
def test_new_process_restores_committed_frame_twice(api_db):
    app, owner, _, ref, _, _ = prepare(api_db)
    startup = app.state.composition.startup
    app.state.composition.close()
    env = dict(os.environ, FRAME_TEST_DB=startup.config.db.url.get_secret_value(),
               FRAME_TEST_ROOT=str(startup.config.media_root), FRAME_TEST_PATH=url(owner, ref))
    for _ in range(2):
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(Path(__file__).with_name('frame_process.py'))],
                                env=env, capture_output=True, timeout=15)
        assert result.returncode == 0, 'frame child failed (raw diagnostics withheld)'
        assert json.loads(result.stdout) == {'status': 200, 'sha256': hashlib.sha256(PNG).hexdigest(),
                                             'content_type': 'image/png', 'length': str(len(PNG))}
        assert result.stderr == b''


@pytest.mark.parametrize('kind', [pytest.param(k, marks=pytest.mark.mysql_check('api_frame', 'isolation', parameter=k))
                                for k in ('missing_case', 'unknown', 'cross_case', 'unavailable', 'bad_format')])
def test_safe_not_found_and_typed_unavailable(api_db, kind):
    app, owner, other, ref, _, output = prepare(api_db, None if kind == 'unavailable' else b'PRIVATE_BAD_FORMAT' if kind == 'bad_format' else PNG)
    case = 'missing' if kind == 'missing_case' else other if kind == 'cross_case' else owner
    target = 'PRIVATE_missing' if kind == 'unknown' else ref
    with TestClient(app) as client:
        response = client.get(url(case, target), headers={'Authorization': 'PRIVATE_SECRET'})
        code = 'http.ref_unavailable' if kind in ('unavailable', 'bad_format') else 'http.not_found'
        assert response.status_code == 404 and response.json() == envelope(code)
        assert 'cache-control' not in response.headers
        # Even an unavailable foreign ref must have the exact safe unknown body.
        cross = client.get(url(other, ref))
        unknown = client.get(url(other, 'missing'))
        assert cross.content == unknown.content and cross.status_code == unknown.status_code == 404
    assert 'PRIVATE' not in output.getvalue() + response.text


@pytest.mark.parametrize('cancel', [pytest.param(k, marks=pytest.mark.mysql_check('api_frame', 'concurrency', parameter=k))
                                  for k in ('none', 'wait', 'active')])
def test_permit_precedes_checkout_and_third_waits_without_connection(api_db, monkeypatch, cancel):
    app, owner, _, ref, _, _ = prepare(api_db)
    composition = app.state.composition
    pool = composition.engine.pool
    real = ApiComposition.load_frame
    entered, release, lock = Event(), Event(), Lock()
    active = calls = maximum = loaded = 0
    checkouts = []
    def checkout(*args):
        assert 0 < active <= 2
        checkouts.append(active)
    sa.event.listen(composition.engine, 'checkout', checkout)
    def load(self, *args):
        nonlocal active, calls, maximum, loaded
        with lock:
            active += 1
            calls += 1
            maximum = max(maximum, active)
        try:
            image = real(self, *args)
            with lock:
                loaded += 1
                if loaded == 2:
                    entered.set()
            assert release.wait(5)
            return image
        finally:
            with lock:
                active -= 1
    monkeypatch.setattr(ApiComposition, 'load_frame', load)
    async def run():
        first = [asyncio.create_task(request(app, path=url(owner, ref))) for _ in range(2)]
        assert await asyncio.to_thread(entered.wait, 3)
        third = asyncio.create_task(request(app, path=url(owner, ref)))
        try:
            await asyncio.sleep(.05)
            assert calls == 2 and len(checkouts) == 2 and pool.checkedout() == 0
            assert not third.done()
            if cancel != 'none':
                victim = third if cancel == 'wait' else first[0]
                victim.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await victim
                await asyncio.sleep(.05)
                assert calls == 2 and pool.checkedout() == 0
        finally:
            release.set()
            await asyncio.gather(*first, third, return_exceptions=True)
        follow = await asyncio.wait_for(asyncio.gather(*(request(app, path=url(owner, ref)) for _ in range(3))), 4)
        assert all(r[0]['status'] == 200 for r in follow)
    try:
        asyncio.run(run())
        assert maximum == 2 and pool.checkedout() == 0
    finally:
        sa.event.remove(composition.engine, 'checkout', checkout)
        composition.close()


@pytest.mark.mysql_check('api_frame', 'connection', parameter='slow_send')
def test_slow_send_never_holds_connection_or_case_lock(api_db):
    app, owner, _, ref, engine, _ = prepare(api_db)
    composition = app.state.composition
    commits = []
    sa.event.listen(composition.engine, 'commit', lambda conn: commits.append(True))
    async def run():
        sending, release = asyncio.Event(), asyncio.Event()
        messages = []
        async def send(message):
            assert commits and composition.engine.pool.checkedout() == 0
            messages.append(message)
            if message['type'] == 'http.response.body' and message.get('body'):
                sending.set()
                await release.wait()
        slow = asyncio.create_task(request(app, path=url(owner, ref), send=send))
        try:
            await asyncio.wait_for(sending.wait(), 3)
            assert composition.engine.pool.checkedout() == 0 and not slow.done()
            # A separate connection can acquire the Case write lock during send.
            with engine.begin() as conn:
                conn.exec_driver_sql('SELECT case_id FROM cases WHERE case_id=%s FOR UPDATE NOWAIT', (owner,))
            fast = await request(app, path=url(owner, ref))
            assert fast[0]['status'] == 200
        finally:
            release.set()
            await slow
        assert b''.join(m.get('body', b'') for m in messages) == PNG
    try:
        asyncio.run(run())
    finally:
        composition.close()


@pytest.mark.parametrize('kind', [pytest.param(k, marks=pytest.mark.mysql_check('api_frame', 'failure', parameter=k))
                                for k in ('pool', 'disconnect', 'unexpected', 'temporary', 'read_failure')])
def test_failures_are_safe_and_do_not_leak_permits_or_connections(api_db, monkeypatch, kind):
    app, owner, _, ref, engine, output = prepare(api_db)
    composition = app.state.composition
    real = RecordingService.read_owned_frame_image
    def fail(self, *args):
        if kind == 'disconnect':
            conn = self._repository._connection
            identity = conn.exec_driver_sql('SELECT CONNECTION_ID()').scalar_one()
            with engine.connect() as other:
                other.exec_driver_sql(f'KILL CONNECTION {identity}')
            return real(self, *args)
        if kind in ('temporary', 'read_failure'):
            raise RecordingCapabilityError('TEMPORARY_FAILURE' if kind == 'temporary' else 'FRAME_NOT_FOUND', 'PRIVATE /secret/file.png')
        raise RuntimeError('TEMPORARY_FAILURE PRIVATE mysql://secret /secret/file.png')
    with TestClient(app, raise_server_exceptions=False) as client:
        with ExitStack() as stack:
            if kind == 'pool':
                for _ in range(3):
                    stack.enter_context(composition.engine.connect())
            else:
                monkeypatch.setattr(RecordingService, 'read_owned_frame_image', fail)
            for _ in range(3):
                response = client.get(url(owner, ref))
                status = 500 if kind == 'unexpected' else 404 if kind == 'read_failure' else 503
                code = 'http.internal_error' if status == 500 else 'http.ref_unavailable' if status == 404 else 'http.dependency_unavailable'
                assert response.status_code == status and response.json() == envelope(code)
        monkeypatch.setattr(RecordingService, 'read_owned_frame_image', real)
        assert client.get(url(owner, ref)).content == PNG
        assert composition.engine.pool.checkedout() == 0
    assert not any(v in output.getvalue() for v in ('PRIVATE', '/secret', 'mysql://', 'Traceback'))


@pytest.mark.mysql_check('api_frame', 'transaction', parameter='caller_rollback')
def test_owned_read_preserves_caller_transaction_and_isolation(api_db):
    startup, _, engine = api_db
    with engine.begin() as conn:
        owner = case_api.create_case(store=store(conn))
    with engine.connect() as conn:
        transaction = conn.begin()
        ref = seed(conn, startup.config.media_root, owner)
        with RecordingService(MySQLRecordingRepository(conn, storage_root=startup.config.media_root)) as service:
            image = service.read_owned_frame_image(owner, ref)
        assert conn.in_transaction() and image.content == PNG
        with engine.connect() as other:
            service = RecordingService(MySQLRecordingRepository(other, storage_root=startup.config.media_root))
            with pytest.raises(RecordingCapabilityError) as error:
                service.read_owned_frame_image(owner, ref)
            assert error.value.code == 'UNKNOWN_REF'
        transaction.rollback()
    with engine.connect() as conn:
        service = RecordingService(MySQLRecordingRepository(conn, storage_root=startup.config.media_root))
        with pytest.raises(RecordingCapabilityError) as error:
            service.read_owned_frame_image(owner, ref)
        assert error.value.code == 'UNKNOWN_REF'


@pytest.mark.parametrize('damage', [pytest.param(k, marks=pytest.mark.mysql_check('api_frame', 'corrupt_scope', parameter=k))
                                  for k in ('frame', 'stream', 'source', 'bytes', 'frame_link', 'frame_identity')])
def test_foreign_corruption_is_indistinguishable_from_unknown(api_db, damage):
    from daesingo.recording.mysql_repository import entries
    app, owner, other, ref, engine, output = prepare(api_db)
    with engine.begin() as conn:
        frame = conn.execute(sa.select(entries.c.payload).where(entries.c.kind == 'frame')).scalar_one()
        kind = {'frame': 'frame', 'stream': 'media_stream', 'source': 'source_asset',
                'bytes': 'frame', 'frame_link': 'frame', 'frame_identity': 'frame'}[damage]
        rows = conn.execute(sa.select(entries.c.entry_key, entries.c.payload).where(entries.c.kind == kind)).all()
        if kind == 'media_stream':
            row = next(r for r in rows if r.payload['media_stream_ref'] == frame['media_stream_ref'])
        elif kind == 'source_asset':
            stream = conn.execute(sa.select(entries.c.payload).where(entries.c.kind == 'media_stream',
                entries.c.payload['media_stream_ref'].as_string() == frame['media_stream_ref'])).scalar_one()
            row = next(r for r in rows if r.payload['source_asset_ref'] == stream['source_asset_ref'])
        else:
            row, = rows
        if damage == 'bytes':
            values = {'content': b'PRIVATE_CORRUPT'}
        else:
            payload = dict(row.payload)
            field, value = {'frame': ('source_offset_sec', 'PRIVATE_CORRUPT'),
                            'stream': ('duration_sec', -1), 'source': ('byte_size', -1),
                            'frame_link': ('media_stream_ref', {'PRIVATE': 'CORRUPT'}),
                            'frame_identity': ('frame_ref', 'PRIVATE_CORRUPT')}[damage]
            payload[field] = value
            values = {'payload': payload}
        conn.execute(sa.update(entries).where(entries.c.kind == kind, entries.c.entry_key == row.entry_key).values(**values))
    with TestClient(app, raise_server_exceptions=False) as client:
        unknown = client.get(url(other, 'missing'))
        foreign = client.get(url(other, ref))
        assert foreign.status_code == unknown.status_code == 404
        assert foreign.content == unknown.content == json.dumps(envelope('http.not_found'), separators=(',', ':')).encode()
        app.state.composition.readiness.events.queue.join()
        events = [json.loads(line) for line in output.getvalue().splitlines()]
        assert [e['status'] for e in events if e['event'] == 'api.frame.latency_ms'] == ['404', '404']
        owned = client.get(url(owner, ref))
        expected = 404 if damage in ('bytes', 'frame_link') else 503
        assert owned.status_code == expected
        code = 'http.ref_unavailable' if damage == 'bytes' else 'http.not_found' if damage == 'frame_link' else 'http.dependency_unavailable'
        assert owned.json() == envelope(code)
    assert not any(raw in output.getvalue() + foreign.text + owned.text for raw in ('PRIVATE', 'CORRUPT', ref, 'Traceback'))


@pytest.mark.mysql_check('api_frame', 'transaction', parameter='relation_snapshot')
def test_relation_and_content_are_one_read_committed_statement(api_db):
    from daesingo.recording.mysql_repository import entries
    app, owner, _, ref, engine, _ = prepare(api_db)
    root = app.state.composition.startup.config.media_root
    app.state.composition.close()
    with engine.connect() as writer, engine.connect() as reader:
        write = writer.begin()
        writer.execute(sa.delete(entries).where(entries.c.kind == 'case_asset',
            entries.c.payload['case_id'].as_string() == owner))
        service = RecordingService(MySQLRecordingRepository(reader, storage_root=root))
        selects = []
        def observe(conn, cursor, statement, *args):
            if statement.lstrip().upper().startswith('SELECT'):
                selects.append(statement)
        sa.event.listen(reader, 'before_cursor_execute', observe)
        try:
            # Uncommitted reassociation/removal is invisible; one statement
            # restores relation, validated metadata and content from one snapshot.
            assert service.read_owned_frame_image(owner, ref).content == PNG
            assert len(selects) == 1 and reader.in_transaction() and writer.in_transaction()
            write.commit()
            with pytest.raises(RecordingCapabilityError) as failure:
                service.read_owned_frame_image(owner, ref)
            assert failure.value.code == 'UNKNOWN_REF' and len(selects) == 2
            assert reader.in_transaction()  # No self-commit/rollback.
        finally:
            sa.event.remove(reader, 'before_cursor_execute', observe)
            if write.is_active:
                write.rollback()


@pytest.mark.parametrize('phase,ending', [pytest.param(phase, ending,
    marks=pytest.mark.mysql_check('api_frame', 'send_lifetime', parameter=phase + '_' + ending))
    for phase in ('body', 'final') for ending in ('normal', 'cancel', 'disconnect', 'oserror', 'unexpected')])
def test_mysql_permits_cover_actual_body_send_and_all_exits(api_db, monkeypatch, phase, ending):
    from starlette.requests import ClientDisconnect
    app, owner, _, ref, _, _ = prepare(api_db)
    composition = app.state.composition
    calls = []
    real = ApiComposition.load_frame
    def load(self, *args):
        calls.append(True)
        return real(self, *args)
    def forbidden(*args, **kwargs):
        raise AssertionError('provider/decoder/regeneration invoked')
    monkeypatch.setattr(ApiComposition, 'load_frame', load)
    monkeypatch.setattr(RecordingService, 'resolve_frame', forbidden)
    monkeypatch.setattr('daesingo.recording.frames.FfmpegFrameExtractor.extract', forbidden)
    monkeypatch.setattr('daesingo.recording.probe.FfprobeMediaProbe.probe', forbidden)
    async def run():
        entered = asyncio.Queue()
        release = [asyncio.Event() for _ in range(4)]
        tasks = []
        async def send(index, message):
            if message['type'] != 'http.response.body':
                return
            target = bool(message.get('body')) if phase == 'body' else not message.get('more_body', False)
            if target:
                await entered.put(index)
                await release[index].wait()
                if index == 0:
                    if ending == 'disconnect': raise ClientDisconnect()
                    if ending == 'oserror': raise OSError('PRIVATE send')
                    if ending == 'unexpected': raise RuntimeError('PRIVATE send')
        def start(index):
            tasks.append(asyncio.create_task(request(app, path=url(owner, ref), send=lambda m: send(index, m))))
        try:
            for index in (0, 1):
                start(index)
                assert await asyncio.wait_for(entered.get(), 3) == index
                assert composition.engine.pool.checkedout() == 0
            start(2)
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(entered.get(), .1)
            assert len(calls) == 2 and composition.engine.pool.checkedout() == 0
            if ending == 'cancel': tasks[0].cancel()
            else: release[0].set()
            await asyncio.gather(tasks[0], return_exceptions=True)
            assert await asyncio.wait_for(entered.get(), 3) == 2
            start(3)
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(entered.get(), .1)
            assert len(calls) == 3 and composition.engine.pool.checkedout() == 0
            release[1].set()
            assert await asyncio.wait_for(entered.get(), 3) == 3
        finally:
            for event in release: event.set()
            await asyncio.gather(*tasks, return_exceptions=True)
        assert (await request(app, path=url(owner, ref)))[0]['status'] == 200
    try:
        asyncio.run(run())
        assert composition.engine.pool.checkedout() == 0
    finally:
        composition.close()
