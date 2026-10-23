"""RT-08(d): existing public Case stop result → caller-owned Runtime cancel."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import multiprocessing
from threading import Barrier

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

import daesingo.case as case_api
from daesingo.api.app import create_app
from daesingo.case import jobs
from daesingo.case.domain import CaseAggregate
from daesingo.common.config import DbSettings
from daesingo.common.jobs.cancel import CancelSignal, CancellationRequested, request_cancel
from daesingo.common.jobs.heartbeat import LeaseConnection, OwnershipFence
from daesingo.common.jobs.redelivery import redeliver_once
from daesingo.common.jobs.repository import claim_one, enqueue, finish
from daesingo.common.jobs.schema import job_execution
from cancel_api_process import interrupted_request
from mysql_fault_proxy import CommitResponseProxy
from redelivery_support import adapter
from test_cases_view_mysql import api_db, store, envelope

pytestmark = pytest.mark.mysql


def parameters(scenario, modes):
    return [pytest.param(p, marks=pytest.mark.mysql_check("api_cancel", scenario, parameter=p)) for p in modes]


def seed(engine, mode="QUEUED"):
    case = CaseAggregate.intake(case_id="case_cancel", hints={}, manifest_summary={})
    case.start_search()
    jobs.issue_coarse_search(case, scope_ref="scope", input_fingerprint="PRIVATE")
    if mode == "multiple":
        jobs.issue_job(case, "HINT_EXTRACT", input_fingerprint="PRIVATE")
        jobs.issue_job(case, "PLATE_READ", input_fingerprint="PRIVATE")
    with engine.begin() as conn:
        store(conn).register(case)
        executions = enqueue(conn, case.job_records, "trace_fixture")
    if mode in ("RUNNING", "STALE", "SUCCEEDED"):
        claim_one(engine, "owner")
        if mode == "SUCCEEDED":
            with engine.begin() as conn:
                assert finish(conn, executions[0], "owner", status=mode) == 1
        elif mode == "STALE":
            # Persist a recovery fixture; Worker finish intentionally forbids
            # STALE, whose transition belongs to the sweeper.
            with engine.begin() as conn:
                conn.execute(job_execution.update().values(status="STALE", ended_at=sa.func.now(6)))
    return {"case_id": case.case_id, "expected_case_rev": case.case_rev,
            "kind": "STOP_ANALYSIS", "payload": {}}


def state(engine):
    with engine.begin() as conn:
        # Plain reads intentionally don't compete with the API's Case lock.
        case = conn.exec_driver_sql("SELECT * FROM cases WHERE case_id='case_cancel'").mappings().one()
        rows = [dict(r) for r in conn.execute(sa.select(job_execution).order_by(
            job_execution.c.job_id, job_execution.c.attempt)).mappings()]
        records = conn.exec_driver_sql("SELECT record FROM job_records ORDER BY seq").scalars().all()
        return case["case_rev"], json.loads(case["state"])["settled_jobs"], records, rows, dict(case)


def assert_private_absent(response, stream):
    for token in ("PRIVATE", "execution_id", "lease_owner", "claim_token", "cancel_requested_at", '"attempt"',
                  "SELECT ", "UPDATE ", "/private/path", "secret"):
        assert token not in response.text and token not in stream.getvalue()


@pytest.mark.parametrize("mode", parameters("atomicity", ("QUEUED", "RUNNING", "STALE", "SUCCEEDED", "multiple")))
def test_stop_commits_case_and_exact_runtime_targets_together(api_db, monkeypatch, mode):
    from daesingo.api import composition
    startup, stream, engine = api_db
    payload = seed(engine, mode)
    before = state(engine)
    results, connections, calls, locks = [], [], [], []
    original = case_api.execute_command
    def execute(*args, **kwargs):
        result = original(*args, **kwargs)
        connections.append(kwargs["store"].conn)
        results.append(result)
        return result
    def cancel(conn, ids):
        assert conn is connections[0] and conn.in_transaction()
        assert ids == results[0].cancelled_job_ids
        assert state(engine) == before  # Independent committed observer.
        with engine.connect() as observer:
            with pytest.raises(sa.exc.OperationalError) as error:
                observer.exec_driver_sql("SELECT case_id FROM cases WHERE case_id='case_cancel' FOR UPDATE NOWAIT")
            assert error.value.orig.args[0] == 3572
        calls.append(list(ids))
        request_cancel(conn, ids)
        assert state(engine) == before
    monkeypatch.setattr(case_api, "execute_command", execute)
    monkeypatch.setattr(composition, "request_cancel", cancel, raising=False)
    app = create_app(startup=startup)
    @sa.event.listens_for(app.state.composition.engine, "before_cursor_execute")
    def observe(conn, cursor, sql, *args):
        if "FOR UPDATE" in sql.upper():
            locks.append(sql.upper())
    with TestClient(app) as client:
        response = client.post("/cases/case_cancel/commands", json=payload)
        assert response.status_code == 200 and response.headers.get("location") is None
        assert response.json() == results[0].response
        view = response.json()["case_view"]
        assert view["stage"] == "SEARCHING"
        assert all(j["kind"] == "PLATE_READ" for j in view["running_jobs"])
        assert next(p for p in view["progress"] if p["step"] == "coarse_search")["state"] == "PARTIAL"
        assert "case.analysis_stopped" in [n["code"] for n in view["notices"]]
        assert client.get("/cases/case_cancel/view").json() == view
    rev, settled, records, rows, _ = state(engine)
    assert rev == before[0] + 1 and records == before[2]
    assert len(calls) == 1 and set(calls[0]) == set(settled)
    assert len(calls[0]) == (2 if mode == "multiple" else 1)
    assert "CASES" in locks[0] and any("JOB_EXECUTION" in sql for sql in locks[1:])
    for row in rows:
        previous = next(r for r in before[3] if r["execution_id"] == row["execution_id"])
        if row["job_id"] not in settled or mode == "SUCCEEDED":
            assert row == previous
            continue
        assert row["cancel_requested_at"] is not None
        assert row["status"] == (mode if mode in ("RUNNING", "STALE") else "CANCELLED")
        if row["status"] == "CANCELLED":
            assert row["produced"] == [] and row["started_at"] is None
            assert row["ended_at"] >= max(row["queued_at"], row["cancel_requested_at"])
        else:
            assert row["ended_at"] == previous["ended_at"]
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM usage_record").scalar_one() == 0
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM usage_inflight").scalar_one() == 0
    assert connections[0].closed
    assert_private_absent(response, stream)


@pytest.mark.parametrize("fault", parameters("rollback", ("before", "after", "disconnect", "sql")))
def test_cancel_fault_rolls_back_both_halves_without_retry_or_disclosure(api_db, monkeypatch, fault):
    from daesingo.api import composition
    startup, stream, engine = api_db
    payload = seed(engine)
    before = state(engine)
    calls = []
    def cancel(conn, ids):
        calls.append(1)
        if fault != "before":
            request_cancel(conn, ids)
        if fault == "disconnect":
            cid = conn.exec_driver_sql("SELECT CONNECTION_ID()").scalar_one()
            with engine.connect() as control:
                control.exec_driver_sql(f"KILL CONNECTION {int(cid)}")
            conn.exec_driver_sql("SELECT 1")
        elif fault == "sql":
            conn.exec_driver_sql("SELECT PRIVATE FROM PRIVATE_missing")
        else:
            raise sa.exc.OperationalError("PRIVATE /private/path secret", {}, Exception(1205, "PRIVATE"))
    monkeypatch.setattr(composition, "request_cancel", cancel, raising=False)
    with TestClient(create_app(startup=startup)) as client:
        response = client.post("/cases/case_cancel/commands", json=payload)
        status = 500 if fault == "sql" else 503
        assert response.status_code == status
        assert response.json() == envelope("http.internal_error" if status == 500 else "http.dependency_unavailable")
    assert calls == [1] and state(engine) == before
    assert_private_absent(response, stream)


@pytest.mark.mysql_check("api_cancel", "commit_unknown", parameter="ack_loss")
def test_cancel_commit_ack_loss_is_500_with_both_halves_durable_and_no_retry(api_db, monkeypatch):
    from daesingo.api import composition
    startup, stream, engine = api_db
    payload = seed(engine, "RUNNING")
    before = state(engine)
    calls = []
    with CommitResponseProxy(engine.url.host, engine.url.port) as proxy:
        url = engine.url.set(host="127.0.0.1", port=proxy.port).update_query_dict({"ssl_disabled": "true"})
        startup = replace(startup, config=replace(startup.config, db=DbSettings(url=url.render_as_string(hide_password=False))))
        def cancel(conn, ids):
            calls.append(1)
            request_cancel(conn, ids)
            proxy.arm()
        monkeypatch.setattr(composition, "request_cancel", cancel, raising=False)
        with TestClient(create_app(startup=startup)) as client:
            response = client.post("/cases/case_cancel/commands", json=payload)
            assert response.status_code == 500 and response.json() == envelope("http.internal_error")
        assert proxy.commit_ok_dropped == 1
    after = state(engine)
    assert calls == [1] and after[0] == before[0] + 1 and after[2] == before[2]
    assert set(after[1].values()) == {"CANCELLED"}
    assert after[3][0]["status"] == "RUNNING" and after[3][0]["cancel_requested_at"] is not None
    assert_private_absent(response, stream)


@pytest.mark.parametrize("mode", parameters("repeat", ("sequential", "concurrent", "current_revision")))
def test_repeated_stop_is_case_owned_and_keeps_first_marker(api_db, monkeypatch, mode):
    from daesingo.api import composition
    startup, _, engine = api_db
    payload = seed(engine, "RUNNING")
    calls = []
    def cancel(conn, ids):
        calls.append(1)
        request_cancel(conn, ids)
    monkeypatch.setattr(composition, "request_cancel", cancel, raising=False)
    with TestClient(create_app(startup=startup)) as client:
        def post():
            return client.post("/cases/case_cancel/commands", json=payload)
        if mode == "concurrent":
            barrier = Barrier(2, timeout=10)
            def racing(_):
                barrier.wait()
                return post()
            with ThreadPoolExecutor(2) as pool:
                responses = list(pool.map(racing, range(2)))
        else:
            responses = [post()]
            committed = state(engine)
            if mode == "current_revision":
                payload["expected_case_rev"] = committed[0]
            responses.append(post())
            assert state(engine) == committed
    assert sorted(r.status_code for r in responses) == [200, 409]
    rejected, = [r for r in responses if r.status_code == 409]
    assert rejected.json()["error"]["code"] == "case.command." + (
        "not_allowed" if mode == "current_revision" else "stale_revision")
    assert calls == [1]


@pytest.mark.parametrize("boundary", parameters("interruption", ("before_cancel", "after_cancel", "after_commit")))
def test_process_interruption_never_leaves_half_cancel_committed(api_db, boundary):
    startup, _, engine = api_db
    payload = seed(engine)
    before = state(engine)
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=interrupted_request, args=(startup.config, payload, boundary, child))
    process.start()
    child.close()
    try:
        assert parent.poll(30), "HTTP process did not reach transaction boundary"
        actual, _ = parent.recv()
        assert actual == boundary
        if boundary != "after_commit":
            assert state(engine) == before
        process.kill()
        process.join(15)
        assert not process.is_alive() and process.exitcode != 0
        # Locking load waits for InnoDB to roll back the disconnected caller.
        with engine.begin() as conn:
            store(conn).load_for_update("case_cancel")
        after = state(engine)
        if boundary == "after_commit":
            assert after[0] == before[0] + 1 and after[2] == before[2]
            assert set(after[1].values()) == {"CANCELLED"}
            assert after[3][0]["status"] == "CANCELLED"
            with TestClient(create_app(startup=startup)) as client:
                assert client.post("/cases/case_cancel/commands", json=payload).status_code == 409
            assert state(engine) == after
        else:
            assert after == before
    finally:
        if process.is_alive():
            process.kill()
        process.join(15)
        parent.close()
        process.close()


@pytest.mark.parametrize("mode", parameters("delivery", ("late_success", "cancelled", "ownership")))
def test_api_marker_preserves_checkpoint_fence_and_idempotent_late_delivery(api_db, mode):
    startup, _, engine = api_db
    payload = seed(engine, "RUNNING")
    execution = state(engine)[3][0]["execution_id"]
    signal, fence = CancelSignal(), OwnershipFence()
    lease = LeaseConnection(engine, execution, "owner", 60, fence=fence, cancel_signal=signal)
    try:
        with TestClient(create_app(startup=startup)) as client:
            response = client.post("/cases/case_cancel/commands", json=payload)
            assert response.status_code == 200 and response.json()["case_view"]["running_jobs"] == []
        assert not signal.requested and not fence.lost
        if mode == "ownership":
            with engine.begin() as conn:
                conn.execute(job_execution.update().values(lease_owner="new_owner"))
            lease.renew()
            assert fence.lost and not signal.requested
            with engine.begin() as conn:
                assert finish(conn, execution, "owner", status="CANCELLED") == 0
            assert state(engine)[3][0]["status"] == "RUNNING"
            return
        lease.renew()
        assert signal.requested and not fence.lost
        if mode == "cancelled":
            with pytest.raises(CancellationRequested):
                signal.checkpoint()
        # A completion after the last checkpoint may win; marker isn't terminal.
        status = "SUCCEEDED" if mode == "late_success" else "CANCELLED"
        with engine.begin() as conn:
            assert finish(conn, execution, "owner", status=status) == 1
        with engine.begin() as conn:
            assert finish(conn, execution, "owner", status="FAILED", failure_kind="TEST") == 0
        before = state(engine)
        delivered = redeliver_once(engine, adapter(), sleep=lambda _: None)
        after = state(engine)
        assert after[:3] == before[:3] and after[4] == before[4]  # No Case write or new intent after stop.
        assert after[3][0]["status"] == status and after[3][0]["produced"] == []
        # Only SUCCEEDED/FAILED are redelivery candidates; CANCELLED remains
        # a Runtime fact and has no Case ExecutionOutcome or receipt.
        assert (after[3][0]["case_applied_at"] is not None) == (mode == "late_success")
        assert len(delivered) == (1 if mode == "late_success" else 0)
        redeliver_once(engine, adapter(), sleep=lambda _: None)
        assert state(engine) == after
        with engine.begin() as conn:
            case = store(conn).get_case("case_cancel")
            # Rejected late outcomes leave Case unchanged; Runtime's receipt
            # makes redelivery idempotent without a new Case write.
            assert case.processed_executions == {}
    finally:
        lease.close()
