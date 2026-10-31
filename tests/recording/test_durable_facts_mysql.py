"""Actual InnoDB rows, bytes, rollback, immutable conflict and detached reopening."""
import pytest
import sqlalchemy as sa

from daesingo.recording import RecordingService, RecordingFacts, ContractRef, load_recording_fixture
from daesingo.recording.time_sources import ObservedTimeSources, TimeSourceCandidate
from test_recording_repository_mysql import db, adapter
from test_ownership_reads import MP4, OTHER_MP4

pytestmark = pytest.mark.mysql


@pytest.mark.parametrize("kind", ["analysis_source", "incident_clip"])
@pytest.mark.mysql_check("recording", "durable_prepared_media")
def test_prepared_media_new_connection_and_rollback_are_atomic(db, kind):
    engine, root = db
    fixture = load_recording_fixture("scenario_happy_001")
    model = (fixture.analysis_sources if kind == "analysis_source" else fixture.incident_clips)[0]
    model = model.model_copy(update={"byte_size": len(MP4), "availability": "AVAILABLE"})
    ref = getattr(model, kind + "_ref")
    with engine.connect() as conn:
        adapter(conn, root).add_prepared_media(model, MP4)
        conn.rollback()
    with engine.begin() as conn:
        getter = adapter(conn, root).get_analysis_source if kind == "analysis_source" else adapter(conn, root).get_incident_clip
        assert getter(ref) is None
        adapter(conn, root).add_prepared_media(model, MP4)
    with engine.begin() as conn:
        repo = adapter(conn, root)
        repo.add_prepared_media(model, MP4)
        with pytest.raises(ValueError): repo.add_prepared_media(model, OTHER_MP4)
    with engine.begin() as conn, RecordingService(adapter(conn, root)) as service:
        if kind == "analysis_source":
            opened = service.open_analysis_source(ref)
            with opened.stream: assert opened.stream.read() == MP4
        else:
            assert adapter(conn, root).get_prepared_content(ContractRef(kind=kind, ref=ref)) == (MP4, "video/mp4")
        current = service.get_analysis_source(ref) if kind == "analysis_source" else service.get_incident_clip(ref)
        assert current == model


@pytest.mark.mysql_check("recording", "durable_observations")
def test_time_observation_first_identity_survives_reopen(db):
    engine, root = db
    candidate = TimeSourceCandidate.model_validate_json('''{"candidate_id":"first","source_kind":"FILENAME",
        "source_detail":"explicit","value":"2026-06-20T14:19:56+09:00",
        "applies_to":{"source_asset_ref":"source","source_offset_sec":0},"observation_status":"OK",
        "producer_checks":{"parse_valid":true},"provenance":{"producer":"recording","observed_from":"filename"}}''')
    value = ObservedTimeSources((candidate,), ())
    with engine.begin() as conn:
        assert adapter(conn, root).save_time_sources("source", value) == value
    with engine.begin() as conn:
        other = ObservedTimeSources((candidate.model_copy(update={"candidate_id": "second"}),), ())
        assert adapter(conn, root).save_time_sources("source", other) == value
    with engine.begin() as conn, RecordingService(adapter(conn, root)) as service:
        assert service.get_time_sources("source") == value
        assert service.get_time_source_candidate("first") == candidate
        assert RecordingFacts(adapter(conn, root)).get_time_source_candidates("source")[0]["candidate_id"] == "first"


@pytest.mark.mysql_check("recording", "transactional_query")
def test_recording_transactional_facade_returns_detached_media_without_checkout(db):
    from daesingo.recording import TransactionalRecordingRepository
    engine, root = db
    def transaction(callback):
        with engine.begin() as conn: return callback(conn)
    repo = TransactionalRecordingRepository(transaction, storage_root=root)
    model = load_recording_fixture("scenario_happy_001").analysis_sources[0].model_copy(
        update={"byte_size": len(MP4), "availability": "AVAILABLE"})
    repo.add_prepared_media(model, MP4)
    assert engine.pool.checkedout() == 0
    with RecordingService(repo) as service:
        opened = service.open_analysis_source(model.analysis_source_ref)
        assert engine.pool.checkedout() == 0
        with opened.stream: assert opened.stream.read() == MP4
    assert engine.pool.checkedout() == 0


@pytest.mark.mysql_check("recording", "prepared_atomic_case_link")
def test_prepared_case_link_failure_leaves_no_bytes_even_if_caller_commits(db):
    engine, root = db
    model = load_recording_fixture("scenario_happy_001").analysis_sources[0].model_copy(
        update={"byte_size": len(MP4), "availability": "AVAILABLE"})
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TRIGGER reject_prepared BEFORE INSERT ON recording_entry FOR EACH ROW BEGIN IF NEW.kind='case_asset' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='rejected'; END IF; END")
    with engine.begin() as conn:
        with pytest.raises(sa.exc.DBAPIError): adapter(conn, root).add_prepared_media(model, MP4, case_id="case")
    with engine.begin() as conn:
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM recording_entry").scalar_one() == 0


@pytest.mark.mysql_check("recording", "prepared_case_conflict")
def test_prepared_case_link_conflict_is_atomic(db):
    engine, root = db
    model = load_recording_fixture("scenario_happy_001").analysis_sources[0].model_copy(
        update={"byte_size": len(MP4), "availability": "AVAILABLE"})
    with engine.begin() as conn:
        adapter(conn, root).add_prepared_media(model, MP4, case_id="case-a")
    with engine.begin() as conn:
        with pytest.raises(ValueError): adapter(conn, root).add_prepared_media(model, OTHER_MP4, case_id="case-b")
        assert adapter(conn, root).get_case_assets("case-b") == []
        assert len(adapter(conn, root).get_case_assets("case-a")) == 1
