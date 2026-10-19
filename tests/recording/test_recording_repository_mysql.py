"""REC-1(a): real MySQL durability, transaction and storage boundaries.

Breaks caught: lost persisted identity/bytes/association, hidden commit/cache,
partial multi-row writes, escaping locators, broad locks and unsafe DB errors.
"""

import importlib.util
import json
import os
from pathlib import Path
import threading

from alembic import command
from alembic.config import Config
import pytest
import sqlalchemy as sa

from daesingo.common.db.migrate import upgrade_all
from daesingo.common.db.errors import BeforeCommitFailure, CommitOutcomeUnknown
from daesingo.common.db.transactions import run_api_transaction
from daesingo.recording import RecordingService, load_recording_fixture
from daesingo.recording.models import ContractRef
from daesingo.recording.probe import LocalSource, ProbedStream
from mysql_fault_proxy import CommitResponseProxy

pytestmark = pytest.mark.mysql
ROOT = Path(__file__).resolve().parents[2]


def check(scenario, parameter):
    return pytest.mark.mysql_check("recording", scenario, parameter=parameter)


def adapter(conn, root):
    spec = importlib.util.find_spec("daesingo.recording.mysql_repository")
    assert spec is not None, "REC-1(a) caller-Connection MySQL repository is missing"
    from daesingo.recording.mysql_repository import MySQLRecordingRepository
    return MySQLRecordingRepository(conn, storage_root=root)


@pytest.fixture
def db(mysql_engine, tmp_path):
    upgrade_all(mysql_engine.url)
    root = tmp_path / "storage"
    root.mkdir()
    return mysql_engine, root


def seed(repo):
    fixture = load_recording_fixture("scenario_happy_001")
    for asset in fixture.source_assets:
        repo.add_source_asset(asset)
    for stream in fixture.media_streams:
        repo.add_media_stream(stream)
    for frame in fixture.frame_refs:
        repo.add_frame(frame, content=b"durable-image-" + frame.frame_ref.encode())
    for timeline in fixture.recording_timelines:
        repo.add_timeline(timeline)
    for resolution in fixture.span_resolutions:
        repo.add_span_resolution(resolution)
    for asset in fixture.derived_assets:
        RecordingService(repo).register_derived_asset(asset)
    refs = [ContractRef(kind="source_asset", ref=a.source_asset_ref) for a in fixture.source_assets]
    refs += [ContractRef(kind="frame", ref=f.frame_ref) for f in fixture.frame_refs]
    refs += [ContractRef(kind="derived_asset", ref=a.derived_asset_ref) for a in fixture.derived_assets]
    for ref in refs:
        repo.associate_case_asset("case-a", ref)
    return fixture, refs


def local(root):
    path = root / "original.bin"
    path.write_bytes(b"original unchanged")
    return LocalSource(path.resolve(), path.stat().st_size, path.stat().st_mtime_ns,
                       "f" * 64, 10.0, (ProbedStream(0, "VIDEO", 10.0),))


class Probe:
    def __init__(self, source):
        self.source = source

    def probe(self, path):
        assert path == self.source.path
        return self.source


@check("restore", "identities")
def test_new_service_restores_source_frame_derived_and_case_links(db):
    engine, root = db
    with engine.begin() as conn:
        fixture, refs = seed(adapter(conn, root))
    with engine.begin() as conn:
        repo = adapter(conn, root)
        service = RecordingService(repo)
        for asset in fixture.source_assets:
            assert repo.get_source_asset(asset.source_asset_ref) == asset
        for frame in fixture.frame_refs:
            assert repo.get_frame(frame.frame_ref) == frame
            assert service.read_frame(frame.frame_ref) == b"durable-image-" + frame.frame_ref.encode()
        for asset in fixture.derived_assets:
            assert service.get_derived_asset(asset.derived_asset_ref) == asset
        assert repo.get_case_assets("case-a") == refs


@check("restore", "local_source")
def test_local_registration_restores_without_probe_or_reregistration(db):
    engine, root = db
    source = local(root)
    with engine.begin() as conn:
        registered = RecordingService(adapter(conn, root), media_probe=Probe(source)).register_local_source(source.path)
    with engine.begin() as conn:
        repo = adapter(conn, root)
        service = RecordingService(repo)
        assert repo.get_local_source(registered.source_asset.source_asset_ref) == source
        assert repo.get_local_stream_index(registered.media_streams[0].media_stream_ref) == 0
        timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
        assert timeline.source_placements[0].source_asset_ref == registered.source_asset.source_asset_ref


@check("restore", "timeline_span")
def test_revision_and_span_restore_and_defensive_copy(db):
    engine, root = db
    with engine.begin() as conn:
        fixture, _ = seed(adapter(conn, root))
    with engine.begin() as conn:
        service = RecordingService(adapter(conn, root))
        timeline = fixture.recording_timelines[0]
        assert service.get_timeline(timeline.timeline_id, timeline.revision) == timeline
        assert service.get_latest_timeline(timeline.timeline_id) == timeline
        resolution = fixture.span_resolutions[0]
        assert adapter(conn, root).get_span_resolution(resolution.timeline_ref, resolution.requested_range) == resolution
        restored = service.get_latest_timeline(timeline.timeline_id)
        restored.source_placements.clear()
        assert service.get_latest_timeline(timeline.timeline_id) == timeline


@check("transaction", "rollback")
def test_caller_rollback_removes_all_rows_and_frame_bytes(db):
    engine, root = db
    with engine.connect() as conn:
        tx = conn.begin()
        fixture, _ = seed(adapter(conn, root))
        assert conn.in_transaction() and not conn.closed
        tx.rollback()
        repo = adapter(conn, root)
        assert repo.get_source_asset(fixture.source_assets[0].source_asset_ref) is None
        assert repo.get_frame(fixture.frame_refs[0].frame_ref) is None
        assert repo.get_frame_content(fixture.frame_refs[0].frame_ref) is None
        assert repo.get_derived_asset(fixture.derived_assets[0].derived_asset_ref) is None
        assert repo.get_case_assets("case-a") == []
    assert list(root.iterdir()) == []


@check("transaction", "visibility")
def test_independent_connection_cannot_see_uncommitted_registration(db):
    engine, root = db
    with engine.connect() as writer, engine.connect() as observer:
        tx = writer.begin()
        fixture, _ = seed(adapter(writer, root))
        assert adapter(observer, root).get_source_asset(fixture.source_assets[0].source_asset_ref) is None
        tx.commit()
        assert adapter(observer, root).get_source_asset(fixture.source_assets[0].source_asset_ref) == fixture.source_assets[0]


@pytest.mark.parametrize("target", [
    pytest.param("local", marks=check("transaction", "failed_registration")),
    pytest.param("frame", marks=check("transaction", "failed_frame")),
])
def test_failed_statement_has_no_partial_rows_even_if_caller_commits(db, target):
    engine, root = db
    source = local(root)
    before = source.path.read_bytes()
    with engine.begin() as conn:
        repo = adapter(conn, root)
        # Actual server-side failure during the write, not a mocked repository.
        rejected_kind = "source_asset" if target == "local" else "frame_position"
        conn.exec_driver_sql("CREATE TRIGGER recording_reject BEFORE INSERT ON recording_entry FOR EACH ROW BEGIN IF NEW.kind='" + rejected_kind + "' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='private-sql-secret'; END IF; END")
        try:
            with pytest.raises(sa.exc.DBAPIError) as error:
                if target == "local":
                    RecordingService(repo, media_probe=Probe(source)).register_local_source(source.path)
                else:
                    frame = load_recording_fixture("scenario_happy_001").frame_refs[0]
                    repo.add_frame(frame, content=b"image")
            assert "private" not in str(error.value)
            assert conn.exec_driver_sql("SELECT COUNT(*) FROM recording_entry").scalar_one() == 0
        finally:
            conn.exec_driver_sql("DROP TRIGGER recording_reject")
    assert source.path.read_bytes() == before
    assert [p.name for p in root.iterdir()] == ["original.bin"]


@check("ownership", "cross_case")
def test_other_case_does_not_restore_owners_refs(db):
    engine, root = db
    with engine.begin() as conn:
        _, refs = seed(adapter(conn, root))
        other = ContractRef(kind="source_asset", ref="other-case-source")
        adapter(conn, root).associate_case_asset("case-b", other)
    with engine.begin() as conn:
        repo = adapter(conn, root)
        assert repo.get_case_assets("case-a") == refs
        assert repo.get_case_assets("case-b") == [other]
        assert not set((r.kind, r.ref) for r in refs).intersection((r.kind, r.ref) for r in repo.get_case_assets("case-b"))
        assert repo.get_case_assets("missing-case") == []
        assert repo.get_case_assets("CASE-A") == []


@check("ownership", "duplicates")
def test_duplicate_association_and_same_ref_registration_are_idempotent(db):
    engine, root = db
    with engine.begin() as conn:
        fixture, refs = seed(adapter(conn, root))
        repo = adapter(conn, root)
        for _ in range(2):
            for ref in refs:
                repo.associate_case_asset("case-a", ref)
            for frame in fixture.frame_refs:
                repo.add_frame(frame, content=b"durable-image-" + frame.frame_ref.encode())
            for asset in fixture.derived_assets:
                repo.add_derived_asset(asset)
        assert repo.get_case_assets("case-a") == refs


@check("identity", "repeat_registration")
def test_same_file_new_registration_keeps_new_logical_identity(db):
    engine, root = db
    source = local(root)
    with engine.begin() as conn:
        service = RecordingService(adapter(conn, root), media_probe=Probe(source))
        a, b = (service.register_local_source(source.path) for _ in range(2))
        assert a.source_asset.source_asset_ref != b.source_asset.source_asset_ref
        assert a.media_streams[0].media_stream_ref != b.media_streams[0].media_stream_ref


@check("identity", "immutable_conflict")
def test_immutable_revision_and_asset_conflict_preserve_committed_payload(db):
    engine, root = db
    with engine.begin() as conn:
        fixture, _ = seed(adapter(conn, root))
    with engine.begin() as conn:
        repo = adapter(conn, root)
        asset = fixture.derived_assets[0]
        with pytest.raises(ValueError):
            repo.add_derived_asset(asset.model_copy(update={"byte_size": asset.byte_size + 1}))
        timeline = fixture.recording_timelines[0]
        with pytest.raises(ValueError):
            repo.add_timeline(timeline.model_copy(update={"timeline_status": "UNAVAILABLE"}))
        assert repo.get_derived_asset(asset.derived_asset_ref) == asset
        assert repo.get_timeline(fixture.span_resolutions[0].timeline_ref) == timeline


@check("storage", "relative")
def test_database_contains_only_relative_locator_and_no_frame_files(db):
    engine, root = db
    source = local(root)
    with engine.begin() as conn:
        registered = RecordingService(adapter(conn, root), media_probe=Probe(source)).register_local_source(source.path)
        rows = conn.exec_driver_sql("SELECT payload FROM recording_entry").all()
        text = json.dumps([r[0] for r in rows])
        assert str(root) not in text and root.as_posix() not in text
        assert "original.bin" in text
        assert adapter(conn, root).get_local_source(registered.source_asset.source_asset_ref).path == source.path


@check("storage", "outside")
def test_registration_outside_root_rejected_without_rows(db):
    engine, root = db
    source = local(root.parent)
    with engine.begin() as conn:
        with pytest.raises(ValueError) as error:
            RecordingService(adapter(conn, root), media_probe=Probe(source)).register_local_source(source.path)
        assert str(root.parent) not in str(error.value)
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM recording_entry").scalar_one() == 0


@pytest.mark.parametrize("attack", [
    pytest.param("../outside.bin", marks=check("storage", "traversal")),
    pytest.param("/outside.bin", marks=check("storage", "absolute")),
    pytest.param("link/outside.bin", marks=check("storage", "symlink")),
])
def test_tampered_locator_cannot_escape_root(db, attack):
    engine, root = db
    source = local(root)
    if attack.startswith("link"):
        if os.name == "nt":
            import _winapi
            _winapi.CreateJunction(str(root.parent), str(root / "link"))
        else:
            (root / "link").symlink_to(root.parent, target_is_directory=True)
    with engine.begin() as conn:
        registered = RecordingService(adapter(conn, root), media_probe=Probe(source)).register_local_source(source.path)
        conn.exec_driver_sql("UPDATE recording_entry SET payload=JSON_SET(payload, '$.locator', %s) WHERE kind='local_source'", (attack,))
    with engine.begin() as conn:
        with pytest.raises(ValueError) as error:
            adapter(conn, root).get_local_source(registered.source_asset.source_asset_ref)
        assert attack not in str(error.value)


@check("storage", "wrong_root")
def test_different_storage_root_cannot_rebind_original(db):
    engine, root = db
    source = local(root)
    other = root.parent / "other-root"
    other.mkdir()
    local(other)
    with engine.begin() as conn:
        registered = RecordingService(adapter(conn, root), media_probe=Probe(source)).register_local_source(source.path)
    with engine.begin() as conn:
        with pytest.raises(ValueError):
            adapter(conn, other).get_local_source(registered.source_asset.source_asset_ref)


@check("concurrent", "frame")
def test_concurrent_same_position_uses_one_committed_frame_identity(db):
    from daesingo.recording.frames import DecodedFrame
    engine, root = db
    source = local(root)
    with engine.begin() as conn:
        registered = RecordingService(adapter(conn, root), media_probe=Probe(source)).register_local_source(source.path)
    barrier = threading.Barrier(2)
    class Extractor:
        def extract(self, source, index, offset):
            return DecodedFrame(1.0, b"image")
    def worker():
        barrier.wait(timeout=10)
        with engine.begin() as conn:
            return RecordingService(adapter(conn, root), frame_extractor=Extractor()).resolve_frame({
                "kind": "STREAM_POSITION", "media_stream_ref": registered.media_streams[0].media_stream_ref,
                "source_offset_sec": 1.0})
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        frames = [f.result(timeout=15) for f in futures]
    assert frames[0] == frames[1]


@check("concurrent", "lock_scope")
def test_stream_lock_is_local_and_caller_rollback_releases_it(db):
    engine, root = db
    fixture = load_recording_fixture("scenario_happy_001")
    with engine.begin() as conn:
        for stream in fixture.media_streams[:2]:
            adapter(conn, root).add_media_stream(stream)
    first, second = fixture.media_streams[:2]
    with engine.connect() as blocker, engine.connect() as contender:
        tx = blocker.begin()
        adapter(blocker, root).get_media_stream(first.media_stream_ref)
        contender.exec_driver_sql("SET SESSION innodb_lock_wait_timeout=1")
        assert adapter(contender, root).get_media_stream(second.media_stream_ref) == second
        with pytest.raises(sa.exc.DBAPIError) as error:
            adapter(contender, root).get_media_stream(first.media_stream_ref)
        assert error.value.orig.args[0] == 1205
        contender.rollback()
        tx.rollback()
        assert adapter(contender, root).get_media_stream(first.media_stream_ref) == first


@check("failure", "commit_unknown")
def test_lost_real_commit_ack_is_unknown_and_persisted_state_restores(db):
    engine, root = db
    url = engine.url
    with CommitResponseProxy(url.host, url.port or 3306) as proxy:
        proxied = sa.create_engine(url.set(host="127.0.0.1", port=proxy.port).update_query_dict({"ssl_disabled": "true"}), hide_parameters=True)
        try:
            def operation(conn):
                result = seed(adapter(conn, root))
                proxy.arm()
                return result
            with pytest.raises(CommitOutcomeUnknown):
                run_api_transaction(proxied, operation)
            assert proxy.commit_forwarded == proxy.commit_ok_dropped == 1
            with engine.begin() as conn:
                assert RecordingService(adapter(conn, root)).read_frame("fr_h001_thumb") == b"durable-image-fr_h001_thumb"
                assert adapter(conn, root).get_case_assets("case-a")
        finally:
            proxied.dispose()


@pytest.mark.parametrize("fault", [
    pytest.param("disconnect", marks=check("failure", "disconnect")),
    pytest.param("unrelated_sql", marks=check("failure", "unrelated_sql")),
])
def test_db_failure_classification_and_rollback_are_preserved(db, fault):
    engine, root = db
    if fault == "unrelated_sql":
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE TRIGGER recording_reject BEFORE INSERT ON recording_entry FOR EACH ROW BEGIN IF NEW.kind='frame' THEN SIGNAL SQLSTATE '45000' SET MYSQL_ERRNO=1054, MESSAGE_TEXT='private-sql-secret'; END IF; END")
    def operation(conn):
        repo = adapter(conn, root)
        seed(repo)
        if fault == "disconnect":
            ident = conn.exec_driver_sql("SELECT CONNECTION_ID()").scalar_one()
            with engine.connect() as control:
                control.exec_driver_sql(f"KILL CONNECTION {ident}")
        repo.get_frame_content("fr_h001_thumb")
    if fault == "disconnect":
        with pytest.raises(BeforeCommitFailure):
            run_api_transaction(engine, operation)
        with engine.connect() as conn:
            assert adapter(conn, root).get_case_assets("case-a") == []
    else:
        with pytest.raises(sa.exc.DBAPIError) as error:
            run_api_transaction(engine, operation)
        assert error.value.orig.args[0] == 1054
        assert "SELECT" not in str(error.value) and "recording_entry" not in str(error.value)
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT COUNT(*) FROM recording_entry").scalar_one() == 0


@check("migration", "fresh")
def test_fresh_migration_metadata_and_rerun_preserve_data(db):
    from daesingo.recording.mysql_repository import metadata
    engine, root = db
    with engine.begin() as conn:
        seed(adapter(conn, root))
        before = conn.exec_driver_sql("SELECT kind, entry_key, payload, content FROM recording_entry ORDER BY ordinal").all()
        assert conn.exec_driver_sql("SELECT version_num FROM recording_alembic_version").scalar_one() == "recording_0001"
        from alembic.migration import MigrationContext
        from alembic.autogenerate import compare_metadata
        diff = compare_metadata(MigrationContext.configure(conn, opts={"include_name": lambda name, type_, parents: type_ != "table" or name in metadata.tables}), metadata)
        assert diff == []
    upgrade_all(engine.url)
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT kind, entry_key, payload, content FROM recording_entry ORDER BY ordinal").all() == before


@check("migration", "previous")
def test_upgrade_existing_case_runtime_revisions_keeps_their_data(mysql_engine, tmp_path):
    for module in ("case", "runtime"):
        cfg = Config(str(ROOT / f"migrations/{module}/alembic.ini"))
        with mysql_engine.begin() as conn:
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "head")
    with mysql_engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO cases VALUES ('retained', 0, 'INIT', 0, '{}', NOW(6), NOW(6))")
    upgrade_all(mysql_engine.url)
    with mysql_engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT case_id FROM cases").scalar_one() == "retained"
        assert conn.exec_driver_sql("SELECT version_num FROM runtime_alembic_version").scalar_one() == "runtime_0004"
        assert conn.exec_driver_sql("SELECT version_num FROM recording_alembic_version").scalar_one() == "recording_0001"


@check("migration", "failure")
def test_failed_recording_upgrade_and_rejected_downgrade_preserve_existing_data(db, tmp_path):
    from migration_support import copy_production, add_revision, create_table
    from daesingo.common.db.migrate import MigrationFailure
    engine, root = db
    with engine.begin() as conn:
        seed(adapter(conn, root))
    copied = copy_production(tmp_path / "migrations")
    add_revision(copied / "recording", "recording_test_failure", "recording_0001",
                 create_table("recording_partial") + "\n" + create_table("recording_partial"))
    with pytest.raises(MigrationFailure):
        upgrade_all(engine.url, migrations_root=copied)
    cfg = Config(str(ROOT / "migrations/recording/alembic.ini"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        with pytest.raises(NotImplementedError):
            command.downgrade(cfg, "base")
        assert conn.exec_driver_sql("SELECT version_num FROM recording_alembic_version").scalar_one() == "recording_0001"
        assert "recording_partial" in sa.inspect(conn).get_table_names()
        assert RecordingService(adapter(conn, root)).read_frame("fr_h001_thumb") == b"durable-image-fr_h001_thumb"


@check("registration_input", "restore")
def test_registration_original_filename_and_link_restore(db):
    engine, root = db
    source = local(root)
    name = "20260620_141956_EVT_1.avi"
    with engine.begin() as conn:
        result = RecordingService(adapter(conn, root), media_probe=Probe(source)).register_local_source(
            source.path, original_filename=name, case_id="case-a")
    with engine.begin() as conn:
        repo = adapter(conn, root)
        restored = repo.get_local_source(result.source_asset.source_asset_ref)
        assert restored.path == source.path and restored.original_filename == name
        assert repo.get_case_assets("case-a") == [ContractRef(kind="source_asset", ref=result.source_asset.source_asset_ref)]
        assert repo.get_case_assets("case-b") == []
        payload = conn.exec_driver_sql("SELECT payload FROM recording_entry WHERE kind='local_source'").scalar_one()
        payload = json.loads(payload) if isinstance(payload, str) else payload
        assert payload["locator"] == source.path.name and payload["original_filename"] == name
        assert "original_filename" not in result.source_asset.model_dump()


@check("registration_input", "rollback")
def test_registration_input_and_link_follow_caller_rollback(db):
    engine, root = db
    source = local(root)
    with engine.connect() as conn:
        tx = conn.begin()
        RecordingService(adapter(conn, root), media_probe=Probe(source)).register_local_source(
            source.path, original_filename="original.avi", case_id="case-a")
        tx.rollback()
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM recording_entry").scalar_one() == 0
    assert source.path.read_bytes() == b"original unchanged"


@check("registration_input", "atomic_link")
def test_link_write_failure_cannot_leave_registration_if_caller_commits(db):
    engine, root = db
    source = local(root)
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TRIGGER recording_reject BEFORE INSERT ON recording_entry FOR EACH ROW BEGIN IF NEW.kind='case_asset' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='private-sql-secret'; END IF; END")
        try:
            with pytest.raises(sa.exc.DBAPIError) as error:
                RecordingService(adapter(conn, root), media_probe=Probe(source)).register_local_source(
                    source.path, original_filename="original.avi", case_id="case-a")
            assert "private-sql-secret" not in str(error.value)
            assert conn.exec_driver_sql("SELECT COUNT(*) FROM recording_entry").scalar_one() == 0
        finally:
            conn.exec_driver_sql("DROP TRIGGER recording_reject")


@check("registration_input", "legacy")
def test_legacy_json_without_original_filename_restores_without_rewrite(db):
    engine, root = db
    source = local(root)
    with engine.begin() as conn:
        result = RecordingService(adapter(conn, root), media_probe=Probe(source)).register_local_source(source.path)
        conn.exec_driver_sql("UPDATE recording_entry SET payload=JSON_REMOVE(payload, '$.original_filename') WHERE kind='local_source'")
        before = conn.exec_driver_sql("SELECT ordinal, payload FROM recording_entry ORDER BY ordinal").all()
    upgrade_all(engine.url)
    with engine.begin() as conn:
        restored = adapter(conn, root).get_local_source(result.source_asset.source_asset_ref)
        assert restored.original_filename is None and restored.path == source.path
        assert conn.exec_driver_sql("SELECT ordinal, payload FROM recording_entry ORDER BY ordinal").all() == before
        assert conn.exec_driver_sql("SELECT version_num FROM recording_alembic_version").scalar_one() == "recording_0001"


@check("registration_input", "concurrent")
def test_concurrent_registration_has_distinct_assets_and_preserved_names(db):
    from concurrent.futures import ThreadPoolExecutor
    engine, root = db
    source = local(root)
    barrier = threading.Barrier(2)
    def worker():
        barrier.wait(timeout=10)
        with engine.begin() as conn:
            return RecordingService(adapter(conn, root), media_probe=Probe(source)).register_local_source(
                source.path, original_filename="original.avi", case_id="case-a")
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    assert len({r.source_asset.source_asset_ref for r in results}) == 2
    with engine.begin() as conn:
        repo = adapter(conn, root)
        assert {ref.ref for ref in repo.get_case_assets("case-a")} == {r.source_asset.source_asset_ref for r in results}
        for result in results:
            assert repo.get_local_source(result.source_asset.source_asset_ref).original_filename == "original.avi"


@check("registration_input", "commit_unknown")
def test_registration_input_lost_commit_ack_preserves_unknown_outcome(db):
    engine, root = db
    source = local(root)
    with CommitResponseProxy(engine.url.host, engine.url.port or 3306) as proxy:
        proxied = sa.create_engine(engine.url.set(host="127.0.0.1", port=proxy.port).update_query_dict({"ssl_disabled": "true"}), hide_parameters=True)
        refs = []
        try:
            def operation(conn):
                result = RecordingService(adapter(conn, root), media_probe=Probe(source)).register_local_source(
                    source.path, original_filename="original.avi", case_id="case-a")
                refs.append(result.source_asset.source_asset_ref)
                proxy.arm()
            with pytest.raises(CommitOutcomeUnknown):
                run_api_transaction(proxied, operation)
            assert proxy.commit_forwarded == proxy.commit_ok_dropped == 1
            with engine.begin() as conn:
                repo = adapter(conn, root)
                assert repo.get_local_source(refs[0]).original_filename == "original.avi"
                assert repo.get_case_assets("case-a")[0].ref == refs[0]
        finally:
            proxied.dispose()


@pytest.mark.parametrize("name", [
    pytest.param("../private/escape.avi", marks=check("registration_input", "filename_path")),
    pytest.param(" 한글 e\u0301.AVI ", marks=check("registration_input", "filename_unicode")),
    pytest.param("", marks=check("registration_input", "filename_empty")),
    pytest.param("a\x00b", marks=check("registration_input", "filename_nul")),
])
def test_filename_metadata_never_controls_locator(db, name):
    engine, root = db
    source = local(root)
    with engine.begin() as conn:
        result = RecordingService(adapter(conn, root), media_probe=Probe(source)).register_local_source(
            source.path, original_filename=name)
    with engine.begin() as conn:
        restored = adapter(conn, root).get_local_source(result.source_asset.source_asset_ref)
        assert restored.original_filename == name and restored.path == source.path
    assert list(root.iterdir()) == [source.path]


@pytest.mark.parametrize("fault", [
    pytest.param("unsupported", marks=check("registration_taxonomy", "unsupported")),
    pytest.param("tool", marks=check("registration_taxonomy", "tool")),
    pytest.param("read", marks=check("registration_taxonomy", "read")),
])
def test_registration_taxonomy_never_persists_rejected_input(db, fault):
    from daesingo.recording import FfprobeMediaProbe, RecordingCapabilityError
    engine, root = db
    source = local(root)
    probe = FfprobeMediaProbe(executable="missing-rec1b-tool") if fault == "tool" else FfprobeMediaProbe()
    if fault == "read":
        source.path.unlink()
    with engine.begin() as conn:
        with pytest.raises(RecordingCapabilityError) as error:
            RecordingService(adapter(conn, root), media_probe=probe).register_local_source(
                source.path, original_filename="private-secret.avi", case_id="case-a")
        assert error.value.code == ("UNSUPPORTED_MEDIA" if fault == "unsupported" else "TEMPORARY_FAILURE")
        assert "private-secret" not in str(error.value) and str(root) not in str(error.value)
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM recording_entry").scalar_one() == 0


@pytest.mark.parametrize("allowed", [
    pytest.param(True, marks=check("registration_input", "case_accept")),
    pytest.param(False, marks=check("registration_input", "case_reject")),
])
def test_existing_case_public_boundary_shares_registration_transaction(db, allowed):
    import daesingo.case as case_api
    from daesingo.case.domain import CaseAggregate, SourceNotAccepted
    from daesingo.case.store_mysql import MySQLCaseRepository
    engine, root = db
    source = local(root)
    def store(conn):
        return case_api.CaseStore(repository=MySQLCaseRepository(), conn=conn)
    case = CaseAggregate.empty("case-a")
    if not allowed:
        case.start_search()
    with engine.begin() as conn:
        store(conn).register(case)
    def operation(conn):
        cases = store(conn)
        cases.load_for_update("case-a")  # Existing case-first locking rule.
        registered = RecordingService(adapter(conn, root), media_probe=Probe(source)).register_local_source(
            source.path, original_filename="original.avi", case_id="case-a")
        case_api.record_source_registered("case-a", registered.source_asset.model_dump(mode="json"),
            media_streams=[s.model_dump(mode="json") for s in registered.media_streams], store=cases)
        return registered
    if allowed:
        registered = run_api_transaction(engine, operation)
    else:
        with pytest.raises(SourceNotAccepted):
            run_api_transaction(engine, operation)
    with engine.begin() as conn:
        restored = store(conn).get_case("case-a")
        assert restored.manifest_summary["file_count"] == int(allowed)
        assert restored.case_rev == case.case_rev
        refs = adapter(conn, root).get_case_assets("case-a")
        if allowed:
            assert refs == [ContractRef(kind="source_asset", ref=registered.source_asset.source_asset_ref)]
            assert adapter(conn, root).get_local_source(refs[0].ref).original_filename == "original.avi"
        else:
            assert not refs
            assert conn.exec_driver_sql("SELECT COUNT(*) FROM recording_entry").scalar_one() == 0
