"""RT-08(c): real Case commands, caller transaction and queue atomicity."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import replace
import json
from threading import Barrier

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
import daesingo.case as case_api
from daesingo.api.app import create_app
from daesingo.case import jobs
from daesingo.case.domain import CaseAggregate
from daesingo.common.config import DbSettings
from daesingo.common.jobs.repository import claim_one, enqueue, finish
from mysql_fault_proxy import CommitResponseProxy
from test_cases_view_mysql import api_db, store, envelope

pytestmark = pytest.mark.mysql


def seed(engine, *, ready=False, pending=False):
    case = CaseAggregate.intake(case_id="case_commands", hints={}, manifest_summary={})
    if ready:
        case.stage = "READY"
    else:
        case.start_search()
        jobs.issue_coarse_search(case, scope_ref="scope", input_fingerprint="fingerprint")
        if not pending:
            case.record_candidate_search_failure()
    with engine.begin() as conn:
        store(conn).register(case)
        enqueue(conn, case.job_records, "trace_seed")
    if not ready and not pending:
        claimed = claim_one(engine, "worker_seed")
        with engine.begin() as conn:
            finish(conn, claimed.execution_id, "worker_seed", status="FAILED", failure_kind="TEST_FAILURE")
    return case.case_id, case.case_rev


def command(identity, rev, *, ready=False):
    return {"case_id": identity, "expected_case_rev": rev,
            "kind": "MARK_REVIEWED" if ready else "RUN_NOTICE_ACTION",
            "payload": {} if ready else {"notice_code": "search.candidate_search_failed", "action": "RETRY_SEARCH"}}


def snapshot(engine, identity):
    with engine.begin() as conn:
        # Consistent plain reads observe committed state without competing with
        # the caller's exclusive Case lock. Lock order is tested separately.
        row = conn.exec_driver_sql("SELECT case_rev,state FROM cases WHERE case_id=%s", (identity,)).mappings().one()
        records = conn.exec_driver_sql("SELECT record FROM job_records WHERE case_id=%s ORDER BY seq", (identity,)).scalars().all()
        rows = conn.exec_driver_sql("SELECT job_id,attempt,status,trace_id,queued_at,available_at FROM job_execution ORDER BY job_id,attempt").mappings().all()
        return (row["case_rev"], [json.loads(r) for r in records], json.loads(row["state"])["user_reviewed"]), [dict(row) for row in rows]


@pytest.mark.parametrize("ready", [
    pytest.param(False, marks=pytest.mark.mysql_check("api_commands", "success", parameter="append")),
    pytest.param(True, marks=pytest.mark.mysql_check("api_commands", "success", parameter="no_append")),
])
def test_command_result_is_preserved_and_visible_only_after_commit(api_db, monkeypatch, ready):
    from daesingo.api import composition
    startup, stream, engine = api_db
    identity, rev = seed(engine, ready=ready)
    before = snapshot(engine, identity)
    original = case_api.execute_command
    results, connections = [], []
    def execute(payload, *, store):
        result = original(payload, store=store)
        assert snapshot(engine, identity) == before
        results.append(result)
        connections.append(store.conn)
        return result
    monkeypatch.setattr(case_api, "execute_command", execute)
    def append(conn, records, trace):
        assert conn is connections[0] and conn.in_transaction()
        # Case row is locked before Runtime writes.
        with engine.connect() as other:
            with pytest.raises(sa.exc.OperationalError) as error:
                other.exec_driver_sql("SELECT case_id FROM cases WHERE case_id=%s FOR UPDATE NOWAIT", (identity,))
            assert error.value.orig.args[0] == 3572
        return enqueue(conn, records, trace)
    monkeypatch.setattr(composition, "enqueue", append, raising=False)
    with TestClient(create_app(startup=startup)) as client:
        response = client.post(f"/cases/{identity}/commands", json=command(identity, rev, ready=ready), headers={"X-Trace-Id": "PRIVATE"})
        assert response.status_code == (200 if ready else 202)
        assert response.json() == results[0].response
        assert response.headers.get("location") == (None if ready else f"/cases/{identity}/view")
        after, rows = snapshot(engine, identity)
        assert len(after[1]) == len(before[0][1]) + (0 if ready else 1)
        if ready:
            assert after[2] is True and not rows
        else:
            job_id = results[0].appended_job_records[0]["job_id"]
            assert [(j["job_id"], j["status"]) for j in response.json()["case_view"]["running_jobs"]] == [(job_id, "PENDING")]
            row, = [r for r in rows if r["job_id"] == job_id]
            assert row["attempt"] == 1 and row["status"] == "QUEUED"
            assert row["queued_at"] == row["available_at"] and row["trace_id"].startswith("tr_")
    assert connections[0].closed
    access = [json.loads(l) for l in stream.getvalue().splitlines() if '"event":"api.request.completed"' in l]
    assert len(access) == 1 and access[0]["case_id"] == identity
    if not ready:
        assert access[0]["trace_id"] == row["trace_id"]
    for private in ("PRIVATE", "execution_id", "lease_owner", "lease_expires_at", '"attempt"', "fingerprint", "trace_seed"):
        assert private not in response.text and private not in stream.getvalue()


@pytest.mark.parametrize("mode,status", [
    pytest.param("invalid", 422, marks=pytest.mark.mysql_check("api_commands", "domain", parameter="invalid")),
    pytest.param("missing", 404, marks=pytest.mark.mysql_check("api_commands", "domain", parameter="missing")),
    pytest.param("stale", 409, marks=pytest.mark.mysql_check("api_commands", "domain", parameter="stale")),
    pytest.param("target", 409, marks=pytest.mark.mysql_check("api_commands", "domain", parameter="target")),
    pytest.param("not_allowed", 409, marks=pytest.mark.mysql_check("api_commands", "domain", parameter="not_allowed")),
])
def test_domain_rejections_preserve_case_body_and_database(api_db, monkeypatch, mode, status):
    from daesingo.api import composition
    from daesingo.case.store_mysql import MySQLCaseRepository
    startup, stream, engine = api_db
    identity, rev = seed(engine)
    before = snapshot(engine, identity)
    with engine.connect() as conn:
        before_case = conn.exec_driver_sql("SELECT * FROM cases ORDER BY case_id").mappings().all()
    payload = command(identity, rev)
    if mode == "invalid": payload = []
    if mode == "missing":
        identity = "PRIVATE_missing"
        payload["case_id"] = identity
    if mode == "stale": payload["expected_case_rev"] = -1
    if mode == "target": payload["payload"]["notice_code"] = "PRIVATE"
    if mode == "not_allowed": payload.update(kind="MARK_REVIEWED", payload={})
    payloads = [payload]
    if mode == "invalid":
        # P2 / Case PR #374: valid JSON with an unhashable kind must be rejected
        # by Case, rather than escape as TypeError and become HTTP 500.
        payloads += [{**command(identity, rev), "kind": kind, "payload": {}}
                     for kind in ([], {})]
    expected = []
    saves, enqueues, sql_writes = [], [], []
    original_save = MySQLCaseRepository.save
    def save(repository, conn, case):
        saves.append(case.case_id)
        return original_save(repository, conn, case)
    def append(conn, records, trace_id):
        enqueues.append(records)
        return enqueue(conn, records, trace_id)
    monkeypatch.setattr(MySQLCaseRepository, "save", save)
    monkeypatch.setattr(composition, "enqueue", append)
    original = case_api.execute_command
    def execute(*a, **kw):
        result = original(*a, **kw)
        expected.append(result.response)
        assert not result.appended_job_records
        return result
    monkeypatch.setattr(case_api, "execute_command", execute)
    app = create_app(startup=startup)
    @sa.event.listens_for(app.state.composition.engine, "before_cursor_execute")
    def writes(conn, cursor, statement, parameters, context, executemany):
        verb = statement.lstrip().split(None, 1)[0].upper()
        if verb in {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP", "TRUNCATE"}:
            sql_writes.append(verb)
    with TestClient(app) as client:
        for value in payloads:
            response = client.post(f"/cases/{identity}/commands", json=value)
            assert response.status_code == status and response.json() == expected[-1]
            if mode == "invalid":
                assert response.json()["error"] == {"code": "case.command.invalid_payload", "message_key": "command.invalid_payload"}
            assert saves == [] and enqueues == [] and sql_writes == []
    assert snapshot(engine, "case_commands") == before and "PRIVATE" not in stream.getvalue()
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT * FROM cases ORDER BY case_id").mappings().all() == before_case


@pytest.mark.parametrize("fault", [
    pytest.param("enqueue", marks=pytest.mark.mysql_check("api_commands", "rollback", parameter="enqueue")),
    pytest.param("save", marks=pytest.mark.mysql_check("api_commands", "rollback", parameter="save")),
    pytest.param("disconnect", marks=pytest.mark.mysql_check("api_commands", "rollback", parameter="disconnect")),
    pytest.param("sql", marks=pytest.mark.mysql_check("api_commands", "rollback", parameter="unrelated_sql")),
])
def test_fault_rolls_back_case_and_queue_without_retry(api_db, monkeypatch, fault):
    from daesingo.api import composition
    startup, stream, engine = api_db
    identity, rev = seed(engine)
    before = snapshot(engine, identity)
    calls = []
    original = case_api.execute_command
    def execute(*a, **kw):
        calls.append(1)
        result = original(*a, **kw)
        if fault == "save":
            raise sa.exc.OperationalError("PRIVATE", {}, Exception(1213, "PRIVATE"))
        return result
    monkeypatch.setattr(case_api, "execute_command", execute)
    def append(conn, records, trace):
        enqueue(conn, records, trace)
        if fault == "enqueue":
            raise sa.exc.OperationalError("PRIVATE", {}, Exception(1205, "PRIVATE"))
        if fault == "disconnect":
            cid = conn.exec_driver_sql("SELECT CONNECTION_ID()").scalar_one()
            with engine.connect() as killer:
                killer.exec_driver_sql(f"KILL CONNECTION {int(cid)}")
            conn.exec_driver_sql("SELECT 1")
        if fault == "sql": conn.exec_driver_sql("SELECT PRIVATE FROM PRIVATE_missing")
    monkeypatch.setattr(composition, "enqueue", append, raising=False)
    with TestClient(create_app(startup=startup)) as client:
        response = client.post(f"/cases/{identity}/commands", json=command(identity, rev))
        status = 500 if fault == "sql" else 503
        assert response.status_code == status
        assert response.json() == envelope("http.internal_error" if status == 500 else "http.dependency_unavailable")
    assert calls == [1] and snapshot(engine, identity) == before
    assert "PRIVATE" not in stream.getvalue()


@pytest.mark.mysql_check("api_commands", "failure", parameter="pool")
def test_command_pool_exhaustion_is_503(api_db):
    startup, _, engine = api_db
    identity, rev = seed(engine)
    app = create_app(startup=startup)
    before = snapshot(engine, identity)
    with TestClient(app) as client, ExitStack() as stack:
        for _ in range(3): stack.enter_context(app.state.composition.engine.connect())
        response = client.post(f"/cases/{identity}/commands", json=command(identity, rev))
        assert response.status_code == 503 and response.json() == envelope("http.dependency_unavailable")
    assert snapshot(engine, identity) == before


@pytest.mark.mysql_check("api_commands", "failure", parameter="lock_timeout")
def test_command_real_lock_timeout_is_503(api_db):
    startup, _, engine = api_db
    identity, rev = seed(engine)
    before = snapshot(engine, identity)
    app = create_app(startup=startup)
    @sa.event.listens_for(app.state.composition.engine, "connect")
    def short_wait(dbapi, record):
        with dbapi.cursor() as cursor: cursor.execute("SET SESSION innodb_lock_wait_timeout=1")
    with engine.begin() as blocker, TestClient(app) as client:
        blocker.exec_driver_sql("SELECT case_id FROM cases WHERE case_id=%s FOR UPDATE", (identity,))
        response = client.post(f"/cases/{identity}/commands", json=command(identity, rev))
        assert response.status_code == 503 and response.json() == envelope("http.dependency_unavailable")
        assert app.state.composition.engine.pool.checkedout() == 0
    assert snapshot(engine, identity) == before


@pytest.mark.mysql_check("api_commands", "failure", parameter="commit_unknown")
def test_commit_ack_loss_returns_500_without_replaying_or_losing_atomicity(api_db, monkeypatch):
    from daesingo.api import composition
    startup, stream, engine = api_db
    identity, rev = seed(engine)
    calls = []
    with CommitResponseProxy(engine.url.host, engine.url.port) as proxy:
        url = engine.url.set(host="127.0.0.1", port=proxy.port).update_query_dict({"ssl_disabled": "true"})
        startup = replace(startup, config=replace(startup.config, db=DbSettings(url=url.render_as_string(hide_password=False))))
        def append(conn, records, trace):
            calls.append(1)
            result = enqueue(conn, records, trace)
            proxy.arm()
            return result
        monkeypatch.setattr(composition, "enqueue", append, raising=False)
        with TestClient(create_app(startup=startup)) as client:
            response = client.post(f"/cases/{identity}/commands", json=command(identity, rev))
            assert response.status_code == 500 and response.json() == envelope("http.internal_error")
        assert proxy.commit_ok_dropped == 1
    state, rows = snapshot(engine, identity)
    assert len(state[1]) == 2 and len(rows) == 2 and calls == [1]
    assert "secret" not in stream.getvalue()


@pytest.mark.parametrize("concurrent", [
    pytest.param(False, marks=pytest.mark.mysql_check("api_commands", "idempotency", parameter="sequential")),
    pytest.param(True, marks=pytest.mark.mysql_check("api_commands", "idempotency", parameter="concurrent")),
])
def test_case_owns_repeat_submission_and_only_new_jobs_are_enqueued(api_db, concurrent):
    startup, _, engine = api_db
    identity, rev = seed(engine, ready=True)
    # MARK_REVIEWED advances revision. The second stale command must do no work.
    with TestClient(create_app(startup=startup)) as client:
        payload = command(identity, rev, ready=True)
        if concurrent:
            barrier = Barrier(2, timeout=5)
            def post():
                barrier.wait()
                return client.post(f"/cases/{identity}/commands", json=payload)
            with ThreadPoolExecutor(2) as pool:
                responses = list(pool.map(lambda _: post(), range(2)))
        else:
            responses = [client.post(f"/cases/{identity}/commands", json=payload) for _ in range(2)]
        assert sorted(r.status_code for r in responses) == [200, 409]
    state, rows = snapshot(engine, identity)
    assert state[0] == rev + 1 and state[2] is True and not rows


@pytest.mark.mysql_check("api_commands", "boundary", parameter="cancel_deferred")
def test_cancel_result_cannot_partially_commit_before_rt08d(api_db):
    startup, _, engine = api_db
    identity, rev = seed(engine, pending=True)
    before = snapshot(engine, identity)
    payload = {"case_id": identity, "expected_case_rev": rev, "kind": "STOP_ANALYSIS", "payload": {}}
    with TestClient(create_app(startup=startup)) as client:
        response = client.post(f"/cases/{identity}/commands", json=payload)
        assert response.status_code == 500 and response.json() == envelope("http.internal_error")
    assert snapshot(engine, identity) == before
