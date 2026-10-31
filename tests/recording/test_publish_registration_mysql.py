"""Actual MySQL current reads, open transactions and file/registration races."""
import os
from threading import Event, Thread

import pytest
import sqlalchemy as sa

from daesingo.common.db.migrate import upgrade_all
from daesingo.common.db.transactions import run_api_transaction
from daesingo.common.storage.cleanup import OrphanPublishScanner
from daesingo.recording import RecordingService, PublishRegistration
from daesingo.recording.mysql_repository import MySQLRecordingRepository, entries
from daesingo.recording.probe import LocalSource, ProbedStream

pytestmark = pytest.mark.mysql


@pytest.fixture
def db(mysql_engine, tmp_path):
    upgrade_all(mysql_engine.url)
    (tmp_path/'source').mkdir()
    return mysql_engine, tmp_path


def candidate(root, name='a'*32):
    path = root/'source'/name
    path.write_bytes(b'synthetic')
    os.utime(path, (1, 1))
    return path


def service(conn, root):
    return RecordingService(MySQLRecordingRepository(conn, storage_root=root))


def register(conn, root, path):
    class Probe:
        def probe(self, value):
            assert value == path
            return LocalSource(path, 9, path.stat().st_mtime_ns, 'f'*64,
                               10.0, (ProbedStream(0, 'VIDEO', 10.0),))
    with RecordingService(MySQLRecordingRepository(conn, storage_root=root), media_probe=Probe()) as rec:
        return rec.register_local_source(path)


def reader(engine, root):
    def read(locator):
        verdict = run_api_transaction(engine, lambda conn: service(conn, root).read_publish_registration(locator))
        assert engine.pool.checkedout() == 0
        return {PublishRegistration.REGISTERED: True, PublishRegistration.UNREGISTERED: False,
                PublishRegistration.UNKNOWN: None}[verdict]
    return read


def scanner(engine, root):
    return OrphanPublishScanner(root=root/'source', lease_root=root, age_sec=86400,
                                registration=reader(engine, root))


def test_committed_registration_and_orphan_use_public_capability(db):
    engine, root = db
    saved, orphan = candidate(root), candidate(root, 'b'*32)
    with engine.begin() as conn:
        register(conn, root, saved)
    result = scanner(engine, root).scan()
    assert saved.exists() and not orphan.exists()
    assert (result.count, result.bytes, result.failed) == (1, 9, 0)


def test_current_read_sees_commit_after_repeatable_read_snapshot(db):
    engine, root = db
    path = candidate(root)
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as stale:
        with stale.begin():
            assert stale.execute(sa.select(entries)).first() is None
            with engine.begin() as writer:
                register(writer, root, path)
            # Negative control: normal consistent read is demonstrably stale.
            assert stale.execute(sa.select(entries).where(entries.c.kind == 'local_source')).first() is None
            assert service(stale, root).read_publish_registration('source/'+path.name) is PublishRegistration.REGISTERED
            assert stale.in_transaction()


@pytest.mark.parametrize('outcome', ['commit', 'rollback'])
def test_pending_registration_is_unknown_even_without_live_os_lease(db, outcome):
    engine, root = db
    path = candidate(root)
    cleaner = scanner(engine, root)
    # Model a crashed client whose DB server transaction has not resolved yet.
    with engine.connect() as writer:
        transaction = writer.begin()
        register(writer, root, path)
        result = cleaner.scan()
        assert path.exists()
        assert (result.count, result.bytes, result.failed) == (0, 0, 1)
        getattr(transaction, outcome)()
    after = cleaner.scan()
    assert path.exists() is (outcome == 'commit')
    assert after.count == (outcome == 'rollback')


@pytest.mark.parametrize('outcome', ['commit', 'rollback'])
def test_publish_before_db_and_uncommitted_are_protected_by_writer_lease(db, outcome):
    engine, root = db
    cleaner = scanner(engine, root)
    with cleaner.in_use():
        path = candidate(root)
        assert cleaner.scan().count == 0  # published but no row yet
        with engine.connect() as writer:
            transaction = writer.begin()
            register(writer, root, path)
            assert cleaner.scan().count == 0
            getattr(transaction, outcome)()
        assert path.exists()
    assert cleaner.scan().count == (outcome == 'rollback')


@pytest.mark.parametrize('payload', [{}, {'locator':'source/SHORT~1'}, {'locator':'../outside'},
                                   {'locator':'SOURCE/'+'a'*32}])
def test_uncertain_stored_alias_blocks_absence(db, payload):
    engine, root = db
    path = candidate(root)
    with engine.begin() as conn:
        conn.execute(sa.insert(entries).values(kind='local_source', entry_key='f'*64, payload=payload))
    result = scanner(engine, root).scan()
    assert path.exists() and result.failed == 1 and result.count == 0


def test_lookup_releases_db_before_delete_and_registration_cannot_overtake(db, monkeypatch):
    from daesingo.common.storage import cleanup
    engine, root = db
    path = candidate(root)
    cleaner = scanner(engine, root)
    at_delete, release, writer_started, writer_entered = (Event() for _ in range(4))
    failures, results = [], []
    original = cleanup._delete_file
    def pause(*args):
        assert engine.pool.checkedout() == 0
        at_delete.set()
        assert release.wait(10)
        return original(*args)
    monkeypatch.setattr(cleanup, '_delete_file', pause)
    def scan():
        results.append(cleaner.scan())
    def write():
        try:
            writer_started.set()
            with cleaner.in_use():
                writer_entered.set()
                with engine.begin() as conn:
                    register(conn, root, path)
        except Exception as error:
            failures.append(type(error))
    scan_thread, writer_thread = Thread(target=scan), Thread(target=write)
    try:
        scan_thread.start()
        assert at_delete.wait(10)
        writer_thread.start()
        assert writer_started.wait(10)
        assert not writer_entered.is_set()
    finally:
        release.set()
        scan_thread.join(10)
        if writer_thread.ident is not None:
            writer_thread.join(10)
    assert not scan_thread.is_alive() and not writer_thread.is_alive()
    assert results[0].count == 1 and failures and not path.exists()
    with engine.begin() as conn:
        assert service(conn, root).read_publish_registration('source/'+path.name) is PublishRegistration.UNREGISTERED


def _writer_process(root, url, channel):
    from pathlib import Path
    engine = sa.create_engine(url)
    root = Path(root)
    cleaner = scanner(engine, root)
    try:
        with cleaner.in_use():
            path = candidate(root)
            channel.send('published')
            if channel.recv() == 'crash':
                os._exit(23)
            with engine.connect() as conn:
                tx = conn.begin()
                register(conn, root, path)
                channel.send('uncommitted')
                outcome = channel.recv()
                if outcome == 'crash':
                    os._exit(23)
                getattr(tx, outcome)()
                channel.send('resolved')
                assert channel.recv() == 'exit'
    finally:
        engine.dispose()
        channel.close()


@pytest.mark.parametrize('outcome', ['commit', 'rollback', 'crash_before_db', 'crash_uncommitted'])
def test_actual_process_publish_transaction_and_crash(db, outcome):
    import multiprocessing
    engine, root = db
    ctx = multiprocessing.get_context('spawn')
    parent, child = ctx.Pipe()
    process = ctx.Process(target=_writer_process, args=(str(root), engine.url.render_as_string(hide_password=False), child))
    process.start()
    child.close()
    cleaner = scanner(engine, root)
    try:
        assert parent.poll(15) and parent.recv() == 'published'
        assert cleaner.scan().count == 0 and (root/'source'/('a'*32)).exists()
        parent.send('crash' if outcome == 'crash_before_db' else 'register')
        if outcome != 'crash_before_db':
            assert parent.poll(15) and parent.recv() == 'uncommitted'
            assert cleaner.scan().count == 0
            parent.send('crash' if outcome == 'crash_uncommitted' else outcome)
            if not outcome.startswith('crash'):
                assert parent.poll(15) and parent.recv() == 'resolved'
                assert cleaner.scan().count == 0
                parent.send('exit')
        process.join(15)
        assert process.exitcode == (23 if outcome.startswith('crash') else 0)
        # Explicit server-side lock barrier: no sleep guesses about disconnect
        # rollback. Await the owned dead session's transaction resolution.
        with engine.begin() as conn:
            conn.execute(sa.select(entries.c.payload).where(entries.c.kind == 'local_source').with_for_update()).all()
        result = cleaner.scan()
        assert result.count == (outcome != 'commit') and result.failed == 0
        assert (root/'source'/('a'*32)).exists() is (outcome == 'commit')
    finally:
        if process.is_alive():
            process.kill()
        process.join(15)
        parent.close()
        process.close()


def test_negative_control_consistent_read_deletes_pending_registration(db):
    engine, root = db
    path = candidate(root)
    with engine.connect() as writer:
        tx = writer.begin()
        register(writer, root, path)
        cleaner = scanner(engine, root)
        assert cleaner.scan().failed == 1 and path.exists()
        def unsafe_read(locator):
            with engine.begin() as conn:
                return conn.execute(sa.select(entries.c.ordinal).where(entries.c.kind == 'local_source')).first() is not None
        cleaner.registration = unsafe_read
        assert cleaner.scan().count == 1 and not path.exists()
        tx.rollback()
