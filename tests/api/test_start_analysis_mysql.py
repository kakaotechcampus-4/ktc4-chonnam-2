"""RT-08 follow-up: real Recording timelines and atomic HTTP analysis dispatch."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
from threading import Barrier

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

import daesingo.case as case_api
from daesingo.api.app import create_app
from daesingo.case.analysis_start import InitialSearchBudget
from daesingo.case.domain import CaseAggregate
from daesingo.case.timeline_source import RecordingSequentialTimelineSource, TimelineUnavailable
from daesingo.common.config import DbSettings
from daesingo.common.jobs.repository import enqueue
from daesingo.recording import RecordingCapabilityError, RecordingService
from daesingo.recording.probe import LocalSource, ProbedStream
from mysql_fault_proxy import CommitResponseProxy
from test_cases_view_mysql import api_db, envelope, store
from test_commands_mysql import snapshot

pytestmark = pytest.mark.mysql


@pytest.fixture
def analysis_case(api_db, tmp_path):
    startup, stream, engine = api_db

    class Probe:
        def probe(self, path):
            stat = path.stat()
            return LocalSource(path, stat.st_size, stat.st_mtime_ns,
                               hashlib.sha256(path.read_bytes()).hexdigest(), 10.0,
                               (ProbedStream(0, "VIDEO", 10.0),))

    recording = RecordingService(media_probe=Probe())
    path = tmp_path / "source.mp4"
    path.write_bytes(b"synthetic source; probe fixture supplies metadata")
    registered = recording.register_local_source(path)
    case = CaseAggregate.empty("case_analysis")
    case.record_source_registered(registered.source_asset.model_dump(mode="json"),
                                 [s.model_dump(mode="json") for s in registered.media_streams])
    with engine.begin() as conn:
        store(conn).register(case)
    return startup, stream, engine, recording, case


def command(case, description):
    return {"case_id": case.case_id, "expected_case_rev": case.case_rev,
            "kind": "START_ANALYSIS", "payload": {"description": description}}


def app_for(startup, recording):
    app = create_app(startup=startup)
    # Same service that registered source + VIDEO stream; no /sources or durable
    # Recording repository is introduced by this HTTP composition acceptance.
    object.__setattr__(app.state.composition, "recording", recording)
    return app


BRANCHES = [("vehicle crossed the line", "HINT_EXTRACT"), ("", "COARSE_SEARCH")]


@pytest.mark.parametrize("description,kind", [
    pytest.param(d, k, marks=pytest.mark.mysql_check("api_start_analysis", "atomicity", parameter=k.lower()))
    for d, k in BRANCHES
])
def test_start_analysis_saves_and_enqueues_before_acknowledged_202(analysis_case, monkeypatch, description, kind):
    from daesingo.api import composition
    startup, stream, engine, recording, case = analysis_case
    before = snapshot(engine, case.case_id)
    results, connections, timelines = [], [], []
    original_execute = case_api.execute_command
    original_timeline = RecordingSequentialTimelineSource.timeline_for

    def timeline(source, sources):
        timelines.append(sources)
        assert sources == case.sources
        return original_timeline(source, sources)

    monkeypatch.setattr(RecordingSequentialTimelineSource, "timeline_for", timeline)

    def execute(payload, **kwargs):
        result = original_execute(payload, **kwargs)
        assert snapshot(engine, case.case_id) == before
        results.append(result)
        connections.append(kwargs["store"].conn)
        return result

    monkeypatch.setattr(case_api, "execute_command", execute)

    def append(conn, records, trace):
        assert conn is connections[0] and conn.in_transaction()
        with engine.connect() as other:
            with pytest.raises(sa.exc.OperationalError) as error:
                other.exec_driver_sql("SELECT case_id FROM cases WHERE case_id=%s FOR UPDATE NOWAIT", (case.case_id,))
            assert error.value.orig.args[0] == 3572
        enqueue(conn, records, trace)
        # Both writes are visible on caller connection; neither is committed.
        row = conn.exec_driver_sql("SELECT stage,state FROM cases WHERE case_id=%s", (case.case_id,)).mappings().one()
        assert row["stage"] == "SEARCHING" and json.loads(row["state"])["description"] == description
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM job_records").scalar_one() == 1
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM job_execution").scalar_one() == 1
        assert snapshot(engine, case.case_id) == before

    monkeypatch.setattr(composition, "enqueue", append)
    with TestClient(app_for(startup, recording)) as client:
        response = client.post(f"/cases/{case.case_id}/commands", json=command(case, description))
        assert response.status_code == 202
        assert response.json() == results[0].response
        assert response.headers["location"] == f"/cases/{case.case_id}/view"
        view = response.json()["case_view"]
        assert view["stage"] == "SEARCHING" and view["description"] == description
        job, = results[0].appended_job_records
        assert job["kind"] == kind
        assert [(j["job_id"], j["kind"], j["status"]) for j in view["running_jobs"]] == [(job["job_id"], kind, "PENDING")]
        after, rows = snapshot(engine, case.case_id)
        assert after[0] == case.case_rev and after[1] == [job]
        row, = rows
        assert row["job_id"] == job["job_id"] and row["attempt"] == 1 and row["status"] == "QUEUED"
        assert row["queued_at"] == row["available_at"] and row["trace_id"].startswith("tr_")
        with engine.begin() as conn:
            saved = store(conn).get_case(case.case_id)
            assert saved.stage == "SEARCHING" and saved.description == description
            if kind == "COARSE_SEARCH":
                scope = saved.analysis_scopes[job["scope_ref"]]
                budget = InitialSearchBudget()
                assert scope["budget"]["max_cost_krw"] == budget.max_cost_krw
                assert scope["budget"]["max_latency_sec"] == budget.max_latency_sec
                time_range, = scope["time_ranges"]
                assert time_range["kind"] == "TIMELINE_RELATIVE"
                assert (time_range["start_ms"], time_range["end_ms"]) == (0, 10_000)
                timeline_ref = time_range["timeline_ref"]
                actual = recording.get_timeline(timeline_ref["timeline_id"], timeline_ref["revision"])
                assert [p.source_asset_ref for p in actual.source_placements] == [case.sources[0]["source_asset_ref"]]
            else:
                assert not saved.analysis_scopes
    assert len(timelines) == (kind == "COARSE_SEARCH")
    assert connections[0].closed
    assert '"status":"202"' in stream.getvalue()


@pytest.mark.parametrize("description,kind,fault", [
    pytest.param(d, k, f, marks=pytest.mark.mysql_check("api_start_analysis", "rollback", parameter=k.lower() + "_" + f))
    for d, k in BRANCHES for f in ("save", "enqueue")
])
def test_start_analysis_precommit_failure_rolls_back_without_retry(analysis_case, monkeypatch, description, kind, fault):
    from daesingo.api import composition
    from daesingo.case.store_mysql import MySQLCaseRepository
    startup, stream, engine, recording, case = analysis_case
    before = snapshot(engine, case.case_id)
    calls = []
    original_save = MySQLCaseRepository.save

    def fail():
        calls.append(fault)
        raise sa.exc.OperationalError("PRIVATE", {}, Exception(1205, "PRIVATE"))

    if fault == "save":
        def save(repository, conn, value):
            original_save(repository, conn, value)
            fail()
        monkeypatch.setattr(MySQLCaseRepository, "save", save)
    else:
        def append(conn, records, trace):
            enqueue(conn, records, trace)
            fail()
        monkeypatch.setattr(composition, "enqueue", append)
    with TestClient(app_for(startup, recording)) as client:
        response = client.post(f"/cases/{case.case_id}/commands", json=command(case, description))
    assert response.status_code == 503 and response.json() == envelope("http.dependency_unavailable")
    assert calls == [fault] and snapshot(engine, case.case_id) == before
    with engine.begin() as conn:
        saved = store(conn).get_case(case.case_id)
        assert saved.stage == "INTAKE" and saved.description is None and not saved.analysis_scopes
    assert "PRIVATE" not in response.text and "PRIVATE" not in stream.getvalue()


@pytest.mark.parametrize("fault", [
    pytest.param(f, marks=pytest.mark.mysql_check("api_start_analysis", "dependency", parameter=f))
    for f in ("timeline_unavailable", "unknown_ref")
])
def test_real_timeline_dependency_errors_remain_500_without_case_or_queue_writes(analysis_case, monkeypatch, fault):
    startup, stream, engine, recording, case = analysis_case
    if fault == "timeline_unavailable":
        with engine.begin() as conn:
            saved = store(conn).load_for_update(case.case_id)
            saved.sources[0]["video_stream_ref"] = None
            store(conn).save(saved)
    else:
        # A new process/service has no registered source: REC-1 remains separate.
        recording = RecordingService()
    before = snapshot(engine, case.case_id)
    errors = []
    original = RecordingSequentialTimelineSource.timeline_for

    def timeline(source, sources):
        try:
            return original(source, sources)
        except (TimelineUnavailable, RecordingCapabilityError) as error:
            errors.append(error)
            raise

    monkeypatch.setattr(RecordingSequentialTimelineSource, "timeline_for", timeline)
    with TestClient(app_for(startup, recording)) as client:
        response = client.post(f"/cases/{case.case_id}/commands", json=command(case, ""))
    assert response.status_code == 500 and response.json() == envelope("http.internal_error")
    error, = errors
    if fault == "timeline_unavailable":
        assert isinstance(error, TimelineUnavailable)
    else:
        assert isinstance(error, RecordingCapabilityError) and error.code == "UNKNOWN_REF"
    assert snapshot(engine, case.case_id) == before
    with engine.begin() as conn:
        saved = store(conn).get_case(case.case_id)
        assert saved.stage == "INTAKE" and saved.description is None and not saved.analysis_scopes
    assert case.sources[0]["source_asset_ref"] not in response.text


@pytest.mark.parametrize("description,kind", [
    pytest.param(d, k, marks=pytest.mark.mysql_check("api_start_analysis", "commit_unknown", parameter=k.lower()))
    for d, k in BRANCHES
])
def test_start_analysis_commit_ack_loss_is_500_with_one_atomic_dispatch(analysis_case, monkeypatch, description, kind):
    from daesingo.api import composition
    startup, stream, engine, recording, case = analysis_case
    calls = []
    with CommitResponseProxy(engine.url.host, engine.url.port) as proxy:
        url = engine.url.set(host="127.0.0.1", port=proxy.port).update_query_dict({"ssl_disabled": "true"})
        startup = replace(startup, config=replace(startup.config, db=DbSettings(url=url.render_as_string(hide_password=False))))

        def append(conn, records, trace):
            calls.append(1)
            enqueue(conn, records, trace)
            proxy.arm()

        monkeypatch.setattr(composition, "enqueue", append)
        with TestClient(app_for(startup, recording)) as client:
            response = client.post(f"/cases/{case.case_id}/commands", json=command(case, description))
            assert response.status_code == 500 and response.json() == envelope("http.internal_error")
        assert proxy.commit_ok_dropped == 1
    state, rows = snapshot(engine, case.case_id)
    job, = state[1]
    row, = rows
    assert calls == [1] and job["kind"] == kind and row["job_id"] == job["job_id"]
    assert row["status"] == "QUEUED"
    with engine.begin() as conn:
        saved = store(conn).get_case(case.case_id)
        assert saved.stage == "SEARCHING" and saved.description == description


@pytest.mark.parametrize("description,kind,concurrent", [
    pytest.param(d, k, c, marks=pytest.mark.mysql_check("api_start_analysis", "repeat", parameter=k.lower() + ("_concurrent" if c else "_sequential")))
    for d, k in BRANCHES for c in (False, True)
])
def test_repeated_start_analysis_dispatches_once_even_without_revision_advance(analysis_case, description, kind, concurrent):
    startup, _, engine, recording, case = analysis_case
    with TestClient(app_for(startup, recording)) as client:
        def post():
            return client.post(f"/cases/{case.case_id}/commands", json=command(case, description))
        if concurrent:
            barrier = Barrier(2, timeout=10)

            def racing(_):
                barrier.wait()
                return post()

            with ThreadPoolExecutor(2) as pool:
                responses = list(pool.map(racing, range(2)))
        else:
            responses = [post(), post()]
    assert sorted(r.status_code for r in responses) == [202, 409]
    rejected, = [r for r in responses if r.status_code == 409]
    assert rejected.json()["error"]["code"] == "case.command.not_allowed"
    state, rows = snapshot(engine, case.case_id)
    assert state[0] == case.case_rev and len(state[1]) == len(rows) == 1
    assert state[1][0]["kind"] == kind and rows[0]["job_id"] == state[1][0]["job_id"]


@pytest.mark.parametrize("description,kind", [
    pytest.param(d, k, marks=pytest.mark.mysql_check("api_start_analysis", "response_loss", parameter=k.lower()))
    for d, k in BRANCHES
])
def test_lost_http_response_keeps_committed_dispatch_and_repeat_is_rejected(analysis_case, description, kind):
    startup, _, engine, recording, case = analysis_case
    app = app_for(startup, recording)

    async def lose_response(scope, receive, send):
        async def lost(message):
            if message["type"] == "http.response.start":
                assert message["status"] == 202
                raise RuntimeError("client response lost")
            await send(message)
        await app(scope, receive, lost if scope["type"] == "http" else send)

    with TestClient(lose_response) as client:
        with pytest.raises(RuntimeError, match="client response lost"):
            client.post(f"/cases/{case.case_id}/commands", json=command(case, description))
    committed = snapshot(engine, case.case_id)
    assert len(committed[0][1]) == len(committed[1]) == 1
    assert committed[0][1][0]["kind"] == kind
    with TestClient(app_for(startup, recording)) as client:
        response = client.post(f"/cases/{case.case_id}/commands", json=command(case, description))
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "case.command.not_allowed"
    assert snapshot(engine, case.case_id) == committed
