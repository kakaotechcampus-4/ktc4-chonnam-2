"""Actual MySQL chunk commands, atomic publish, corruption and compatibility."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import threading

import pytest
import sqlalchemy as sa

from daesingo.recording import (
    ContractRef,
    RecordingService,
    TransactionalRecordingRepository,
    load_recording_fixture,
)
from daesingo.recording.mysql_repository import MySQLRecordingRepository, entries
from test_recording_repository_mysql import db as _db
from test_ownership_reads import MP4, OTHER_MP4, padded_mp4

pytestmark = pytest.mark.mysql
db = _db


def check(parameter):
    return pytest.mark.mysql_check("recording", "chunked_media", parameter=parameter)


def model(content=MP4, kind="analysis_source"):
    fixture = load_recording_fixture("scenario_happy_001")
    original = (
        fixture.analysis_sources
        if kind == "analysis_source"
        else fixture.incident_clips
    )[0]
    return original.model_copy(
        update={"byte_size": len(content), "availability": "AVAILABLE"}
    )


def repo(conn, root, **kwargs):
    return MySQLRecordingRepository(conn, storage_root=root, temp_root=root,
                                    prepared_write_format="chunked", **kwargs)


@check("bounded")
def test_driver_commands_and_result_rows_are_bounded(db, monkeypatch):
    engine, root = db
    content = padded_mp4(1024 * 1024)
    media = model(content)
    commands, rows = [], []
    import pymysql.connections

    original = pymysql.connections.Connection._execute_command

    def observe(connection, command, sql):
        commands.append(
            len(sql.encode(connection.encoding) if isinstance(sql, str) else sql) + 1
        )
        return original(connection, command, sql)

    monkeypatch.setattr(pymysql.connections.Connection, "_execute_command", observe)
    with engine.begin() as conn:
        repo(conn, root, command_budget=64 * 1024).add_prepared_media(
            media, content, case_id="case"
        )
        assert (
            conn.exec_driver_sql(
                "SELECT OCTET_LENGTH(content) FROM recording_entry WHERE kind='analysis_source'"
            ).scalar_one()
            is None
        )
    with engine.begin() as conn:
        for (length,) in conn.exec_driver_sql(
            "SELECT OCTET_LENGTH(content) FROM recording_media_chunk"
        ):
            rows.append(length)
        opened = repo(conn, root).open_analysis_stream(media.analysis_source_ref)
    with opened[0]:
        assert (
            hashlib.file_digest(opened[0], "sha256").digest()
            == hashlib.sha256(content).digest()
        )
    assert max(commands) <= 64 * 1024 < len(content)
    assert len(rows) > 1 and max(rows) < 64 * 1024


@pytest.mark.parametrize(
    "stage",
    [
        pytest.param(stage, marks=check("atomic_" + stage))
        for stage in ("chunk", "manifest", "case_link")
    ],
)
def test_publish_failure_caller_catch_commit_preserves_other_work(db, stage):
    engine, root = db
    content = padded_mp4(800000)
    media = model(content)
    condition = {
        "chunk": "NEW.chunk_index=1",
        "manifest": "NEW.kind='prepared_content'",
        "case_link": "NEW.kind='case_asset'",
    }[stage]
    table = "recording_media_chunk" if stage == "chunk" else "recording_entry"
    with engine.begin() as conn:
        conn.exec_driver_sql(
            f"CREATE TRIGGER reject_chunk_publish BEFORE INSERT ON {table} FOR EACH ROW BEGIN IF {condition} THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='rejected'; END IF; END"
        )
    with engine.begin() as conn:
        conn.execute(
            entries.insert().values(kind="sentinel", entry_key="other", payload={})
        )
        with pytest.raises(sa.exc.DBAPIError):
            repo(conn, root).add_prepared_media(media, content, case_id="case")
        assert conn.in_transaction() and not conn.invalidated
    with engine.connect() as conn:
        assert conn.exec_driver_sql(
            "SELECT kind FROM recording_entry"
        ).scalars().all() == ["sentinel"]
        assert (
            conn.exec_driver_sql(
                "SELECT COUNT(*) FROM recording_media_chunk"
            ).scalar_one()
            == 0
        )


@check("detached")
def test_independent_streams_outlive_service_and_have_no_db_checkout(db):
    engine, root = db
    content = padded_mp4(800000)
    media = model(content)

    def transaction(callback):
        with engine.begin() as conn:
            return callback(conn)

    repository = TransactionalRecordingRepository(
        transaction, storage_root=root, temp_root=root
    )
    repository.add_prepared_media(media, content)
    with RecordingService(repository) as service:
        first = service.open_analysis_source(media.analysis_source_ref)
        second = service.open_analysis_source(media.analysis_source_ref)
        assert engine.pool.checkedout() == 0
    with first.stream, second.stream:
        assert first.stream.read(17) == content[:17]
        assert second.stream.tell() == 0
        assert (
            hashlib.file_digest(second.stream, "sha256").digest()
            == hashlib.sha256(content).digest()
        )
    assert list(root.iterdir()) == []


@pytest.mark.parametrize(
    "damage",
    [
        pytest.param(damage, marks=check("corrupt_" + damage))
        for damage in ("missing", "changed", "extra", "order", "oversize", "manifest")
    ],
)
def test_corrupt_chunks_rejected_and_temp_cleaned(db, damage):
    engine, root = db
    content = padded_mp4(800000)
    media = model(content)
    with engine.begin() as conn:
        repo(conn, root).add_prepared_media(media, content)
    with engine.begin() as conn:
        if damage == "missing":
            conn.exec_driver_sql(
                "DELETE FROM recording_media_chunk WHERE chunk_index=1"
            )
        elif damage == "changed":
            conn.exec_driver_sql(
                "UPDATE recording_media_chunk SET content=CONCAT(X'01',SUBSTRING(content,2)) WHERE chunk_index=0"
            )
        elif damage == "extra":
            conn.exec_driver_sql(
                "INSERT INTO recording_media_chunk SELECT kind,entry_key,99,content FROM recording_media_chunk WHERE chunk_index=0"
            )
        elif damage == "order":
            conn.exec_driver_sql(
                "UPDATE recording_media_chunk SET chunk_index=chunk_index+10 ORDER BY chunk_index DESC"
            )
        elif damage == "oversize":
            conn.exec_driver_sql(
                "UPDATE recording_media_chunk SET content=CONCAT(content,X'01') WHERE chunk_index=0"
            )
        else:
            conn.exec_driver_sql(
                "UPDATE recording_entry SET payload=JSON_SET(payload,'$.version',99) WHERE kind='prepared_content'"
            )
    with engine.begin() as conn:
        with pytest.raises(ValueError):
            repo(conn, root).open_analysis_stream(media.analysis_source_ref)
    assert list(root.iterdir()) == []
    assert engine.pool.checkedout() == 0


@pytest.mark.parametrize(
    "conflict",
    [
        pytest.param(False, marks=check("concurrent_equal")),
        pytest.param(True, marks=check("concurrent_conflict")),
    ],
)
def test_concurrent_immutable_publish_and_case_links(db, conflict):
    engine, root = db
    barrier = threading.Barrier(2)

    def worker(index):
        content = OTHER_MP4 if conflict and index else MP4
        barrier.wait(timeout=10)
        with engine.begin() as conn:
            try:
                repo(conn, root).add_prepared_media(
                    model(content), content, case_id=f"case-{index}"
                )
                return True
            except ValueError:
                return False

    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(worker, (0, 1)))
    assert sum(outcomes) == (1 if conflict else 2)
    with engine.begin() as conn:
        repository = repo(conn, root)
        for index, success in enumerate(outcomes):
            assert bool(repository.get_case_assets(f"case-{index}")) == success


@pytest.mark.parametrize(
    "kind",
    [
        pytest.param(kind, marks=check("legacy_" + kind))
        for kind in ("analysis_source", "incident_clip")
    ],
)
def test_legacy_read_republish_without_blob_transfer_and_upgrade(
    mysql_engine, tmp_path, kind
):
    from alembic import command
    from alembic.config import Config
    from daesingo.common.db.migrate import upgrade_all
    from daesingo.recording.media_content import descriptor
    from test_recording_repository_mysql import ROOT
    from daesingo.recording.mysql_repository import _key

    content = padded_mp4(800000)
    media = model(content, kind)
    ref = getattr(media, kind + "_ref")
    cfg = Config(str(ROOT / "migrations/recording/alembic.ini"))
    with mysql_engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "recording_0001")
        conn.execute(
            entries.insert().values(
                kind=kind,
                entry_key=_key(ref),
                payload=media.model_dump(mode="json"),
                content=content,
            )
        )
        conn.execute(
            entries.insert().values(
                kind="prepared_content",
                entry_key=_key([kind, ref]),
                payload=descriptor(content, "video/mp4"),
            )
        )
    upgrade_all(mysql_engine.url)
    with mysql_engine.begin() as conn:
        repository = repo(conn, tmp_path)
        statements = []

        def observe(c, cursor, statement, parameters, context, many):
            statements.append(statement)

        sa.event.listen(conn, "before_cursor_execute", observe)
        repository.add_prepared_media(media, content, case_id="case")
        assert not any("recording_entry.content \n" in s for s in statements)
        assert (
            conn.exec_driver_sql(
                "SELECT COUNT(*) FROM recording_media_chunk"
            ).scalar_one()
            == 0
        )
        stream, mime = repository.open_prepared_stream(ContractRef(kind=kind, ref=ref))
    with stream:
        assert (
            hashlib.file_digest(stream, "sha256").digest()
            == hashlib.sha256(content).digest()
        )
    assert mime == "video/mp4"
    assert list(tmp_path.iterdir()) == []


@check("duplicate")
def test_chunk_primary_key_rejects_duplicate(db):
    engine, root = db
    with engine.begin() as conn:
        repo(conn, root).add_prepared_media(model(), MP4)
    with engine.begin() as conn:
        with pytest.raises(sa.exc.IntegrityError):
            conn.exec_driver_sql(
                "INSERT INTO recording_media_chunk SELECT * FROM recording_media_chunk"
            )


@check("replay")
def test_equal_replay_no_chunk_retransmit_and_conflict_no_case_link(db):
    engine, root = db
    with engine.begin() as conn:
        repo(conn, root).add_prepared_media(model(), MP4)
    statements = []
    with engine.begin() as conn:
        sa.event.listen(
            conn,
            "before_cursor_execute",
            lambda c, cursor, sql, p, ctx, many: statements.append(sql),
        )
        repository = repo(conn, root)
        repository.add_prepared_media(model(), MP4, case_id="equal")
        with pytest.raises(ValueError):
            repository.add_prepared_media(model(), OTHER_MP4, case_id="conflict")
        assert repository.get_case_assets("conflict") == []
        assert len(repository.get_case_assets("equal")) == 1
    assert not any(
        s.startswith("INSERT INTO recording_media_chunk") for s in statements
    )


@check("metadata")
def test_case_metadata_sql_never_reads_media_chunks_or_blob(db):
    engine, root = db
    with engine.begin() as conn:
        repo(conn, root).add_prepared_media(model(), MP4, case_id="case")
    statements = []
    with engine.begin() as conn:
        sa.event.listen(
            conn,
            "before_cursor_execute",
            lambda c, cursor, sql, p, ctx, many: statements.append(sql),
        )
        with RecordingService(repo(conn, root)) as service:
            (facts,) = service.list_case_asset_facts("case")
        assert facts.byte_size == len(MP4)
    assert not any(
        ".content" in sql or "recording_media_chunk" in sql for sql in statements
    )


@check("commit_unknown")
def test_prepared_commit_ack_loss_is_unknown_and_replay_is_immutable(db):
    from mysql_fault_proxy import CommitResponseProxy
    from daesingo.common.db.transactions import run_api_transaction
    from daesingo.common.db.errors import CommitOutcomeUnknown

    engine, root = db
    with CommitResponseProxy(engine.url.host, engine.url.port or 3306) as proxy:
        proxied = sa.create_engine(
            engine.url.set(host="127.0.0.1", port=proxy.port).update_query_dict(
                {"ssl_disabled": "true"}
            ),
            hide_parameters=True,
        )
        try:

            def operation(conn):
                repo(conn, root).add_prepared_media(model(), MP4, case_id="case")
                proxy.arm()

            with pytest.raises(CommitOutcomeUnknown):
                run_api_transaction(proxied, operation)
            assert proxy.commit_forwarded == proxy.commit_ok_dropped == 1
        finally:
            proxied.dispose()
    with engine.begin() as conn:
        repository = repo(conn, root)
        repository.add_prepared_media(model(), MP4, case_id="case")
        stream, _ = repository.open_analysis_stream(model().analysis_source_ref)
        with stream:
            assert stream.read() == MP4
        assert len(repository.get_case_assets("case")) == 1


@check("search_consumer")
def test_search_consumer_closes_detached_stream_on_exception(db):
    from daesingo import search
    from daesingo.search.sources import RecordingAnalysisSourceResolver, SourceMeta

    engine, root = db

    def transaction(callback):
        with engine.begin() as conn:
            return callback(conn)

    repository = TransactionalRecordingRepository(
        transaction, storage_root=root, temp_root=root
    )
    media = model()
    repository.add_prepared_media(media, MP4)
    ref = search.ContractRef(kind="analysis_source", ref=media.analysis_source_ref)
    with RecordingService(repository) as service:
        resolver = RecordingAnalysisSourceResolver(
            {},
            {
                ref.ref: SourceMeta(
                    media.duration_sec,
                    media.timeline_ref.timeline_id,
                    media.timeline_ref.revision,
                    media.timeline_range.start_sec,
                )
            },
            service,
        )
        with pytest.raises(RuntimeError):
            with resolver.open_source(ref) as opened:
                assert engine.pool.checkedout() == 0
                stream = opened.stream
                assert stream.read(12) == MP4[:12]
                raise RuntimeError("consumer cancelled")
        assert stream.closed
    assert list(root.iterdir()) == []
