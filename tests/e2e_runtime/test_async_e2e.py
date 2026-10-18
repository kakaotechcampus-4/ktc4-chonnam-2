"""RT-09: HTTP acknowledgement through durable T1/T2 and public polling."""

import json
from threading import get_ident
from time import monotonic, sleep

import pytest
from fastapi.testclient import TestClient

from daesingo.api.app import create_app
from daesingo.common.jobs.read_port import read_executions
from async_e2e_support import AsyncWorker, prepare_retry, snapshot

pytestmark = pytest.mark.mysql


def public(response):
    assert response.status_code in (200, 201, 202)
    body = response.json()
    forbidden = {"execution_id", "attempt", "trace_id", "lease_owner", "claim_token",
                 "lease_expires_at", "heartbeat_at", "available_at", "case_applied_at",
                 "queued_at", "started_at", "ended_at", "cancel_requested_at"}
    def walk(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(body)
    return body


@pytest.mark.mysql_check("async_e2e", "lifecycle", parameter="retry_search")
def test_http_command_worker_t1_t2_and_view_polling(async_db, tmp_path):
    startup, api_stream, engine = async_db
    app = create_app(startup=startup)
    with TestClient(app) as client:
        created = client.post("/cases")
        identity = public(created)["case_id"]
        assert created.status_code == 201
        assert created.headers["location"] == f"/cases/{identity}/view"
        assert created.json()["case_view"]["stage"] == "INTAKE"
        payload = prepare_retry(engine, identity)
        before = snapshot(engine, identity)
        accepted = client.post(f"/cases/{identity}/commands", json=payload)
        body = public(accepted)
        assert accepted.status_code == 202 and body["ok"] is True
        location = accepted.headers["location"]
        assert location == f"/cases/{identity}/view"
        job, = body["case_view"]["running_jobs"]
        assert (job["kind"], job["status"]) == ("COARSE_SEARCH", "PENDING")
        queued = snapshot(engine, identity, job["job_id"])
        assert len(queued["records"]) == len(before["records"]) + 1
        row, = queued["executions"]
        execution_id, trace = row["execution_id"], row["trace_id"]
        assert (row["status"], row["attempt"]) == ("QUEUED", 1)
        assert row["queued_at"] == row["available_at"]
        assert row["started_at"] is row["ended_at"] is row["case_applied_at"] is None
        polls = [public(client.get(location))]
        assert polls[-1]["running_jobs"] == [job]
        with AsyncWorker(engine, tmp_path) as worker:
            assert worker.engine is not engine and worker.engine is not app.state.composition.engine
            assert worker.entered.wait(5), "separate Worker loop never claimed the HTTP-enqueued job"
            assert worker.thread.ident != get_ident() and worker.thread.is_alive()
            running = snapshot(engine, identity, job["job_id"])
            assert running["executions"][0]["status"] == "RUNNING"
            polls.append(public(client.get(location)))
            assert polls[-1]["running_jobs"][0]["status"] == "RUNNING"
            worker.release_handler.set()
            assert worker.t1_ready.wait(5), "Worker never reached durable T1 before T2"
            terminal = snapshot(engine, identity, job["job_id"])
            t1, = terminal["executions"]
            assert t1["status"] == "SUCCEEDED" and t1["case_applied_at"] is None
            assert execution_id not in terminal["case"]["processed_executions"]
            assert terminal["case"]["stage"] == "SEARCHING"
            assert t1["queued_at"] <= t1["started_at"] <= t1["ended_at"]
            polls.append(public(client.get(location)))
            assert polls[-1]["running_jobs"][0]["status"] == "RUNNING"
            worker.release_t2.set()
            deadline = monotonic() + 10
            while True:
                polls.append(public(client.get(location)))
                if not polls[-1]["running_jobs"]:
                    break
                assert monotonic() < deadline, "Case never stopped waiting after T1"
                sleep(.01)
        final = snapshot(engine, identity, job["job_id"])
        stored, = final["executions"]
        view = polls[-1]
        assert view["stage"] == "CANDIDATE_REVIEW" and view["running_jobs"] == []
        assert [c["candidate_id"] for c in view["candidates"]] == ["cand_rt09"]
        assert {p["step"]: p["state"] for p in view["progress"]}["coarse_search"] == "DONE"
        assert {p["step"]: p["state"] for p in view["progress"]}["candidate_review"] == "DONE"
        assert final["case"]["processed_executions"][execution_id] == job["job_id"]
        assert final["case"]["settled_jobs"][job["job_id"]] == "REFLECTED"
        assert stored["ended_at"] <= stored["case_applied_at"]
        assert len(final["records"]) == len(queued["records"])
        with engine.connect() as conn:
            execution, = read_executions(conn, [job["job_id"]])
        assert (execution["attempt"], execution["status"]) == (1, "SUCCEEDED")
        assert execution["usage_refs"] == []
    api_events = [json.loads(line) for line in api_stream.getvalue().splitlines()]
    access, = [e for e in api_events if e["event"] == "api.request.completed" and e["status"] == "202"]
    assert access["trace_id"] == trace and access["case_id"] == identity
    worker_events = [json.loads(line) for line in worker.stream.getvalue().splitlines()]
    events = [e for e in worker_events if e["event"].startswith("runtime.execution.")]
    assert [e["event"] for e in events] == ["runtime.execution.started", "runtime.execution.completed"]
    for event in events:
        assert (event["trace_id"], event["case_id"], event["job_id"], event["execution_id"]) == (
            trace, identity, job["job_id"], execution_id)
    assert len(worker.calls) == 1 and worker.calls[0].trace_id == trace
    assert worker.precommit == [{"case": "SEARCHING", "receipt": None}]
    # T1 locks only the execution. T2 must acquire Case before Runtime receipt.
    case_lock = next(i for i, sql in enumerate(worker.locks) if "FROM CASES" in sql)
    assert "JOB_EXECUTION" in worker.locks[case_lock + 1]
    assert not worker.errors and not worker.thread.is_alive()
    # Local diagnostic output, outside the deliverable; gate evidence is separate.
    (tmp_path / "durable-stages.json").write_text(json.dumps({
        "case_id": identity, "job_id": job["job_id"], "trace_id": trace,
        "queued": queued["executions"], "running": running["executions"],
        "t1": terminal["executions"], "t2": final["executions"],
        "polls": polls, "api_event": access, "worker_events": events,
        "t2_precommit_observer": worker.precommit,
    }, default=str, indent=2), encoding="utf-8")
