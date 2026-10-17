"""RT-08(b): real Case + Runtime MySQL boundaries through the HTTP composition.

Fault hooks wrap public calls; they never replace the DB/transaction/locking.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from threading import Barrier, Event
from time import monotonic
import weakref

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from daesingo.api.app import create_app
from daesingo.case import create_case, get_view, jobs
from daesingo.case.domain import CaseAggregate
from daesingo.case.store import CaseStore
from daesingo.case.store_mysql import MySQLCaseRepository
from daesingo.common.config import DbSettings
from daesingo.common.db import create_api_engine
from daesingo.common.db.migrate import upgrade_all
from daesingo.common.jobs.read_port import read_executions
from daesingo.common.jobs.repository import claim_one, enqueue, finish
from mysql_fault_proxy import CommitResponseProxy

pytestmark = pytest.mark.mysql


def envelope(code):
    return {"ok": False, "error": {"code": code, "message_key": code}, "case_view": None}


def store(conn):
    return CaseStore(repository=MySQLCaseRepository(), conn=conn, executions=read_executions)


@pytest.fixture
def api_db(api_startup, mysql_schema_url):
    startup, stream = api_startup
    upgrade_all(mysql_schema_url)
    settings = DbSettings(url=mysql_schema_url.render_as_string(hide_password=False),
                          pool_size=3, max_overflow=0, pool_timeout_sec=.1)
    startup = replace(startup, config=replace(startup.config, db=settings))
    engine = create_api_engine(settings)
    try:
        yield startup, stream, engine
    finally:
        engine.dispose()


def seed(engine, identity="case_http"):
    case = CaseAggregate.intake(case_id=identity, hints={}, manifest_summary={})
    case.start_search()
    job = jobs.issue_coarse_search(case, scope_ref="scope", input_fingerprint="fingerprint")
    with engine.begin() as conn:
        store(conn).register(case)
        enqueue(conn, case.job_records, "trace_fixture")
    return case.case_id, job["job_id"]


def count(engine):
    with engine.connect() as conn:
        return conn.exec_driver_sql("SELECT COUNT(*) FROM cases").scalar_one()


@pytest.mark.mysql_check("api_cases", "create", parameter="contract")
def test_create_commits_then_returns_public_view_and_location(api_db, monkeypatch):
    import daesingo.case as case_api
    startup, stream, engine = api_db
    original = case_api.get_view
    seen = []
    registries = []
    def created(*, store):
        registries.append(weakref.ref(store.adapters))
        return create_case(store=store)
    monkeypatch.setattr(case_api, "create_case", created)
    def committed_view(case_id, *, store):
        # An independent connection must see the case before response assembly.
        with engine.begin() as other:
            assert get_view(case_id, store=globals()["store"](other))["stage"] == "INTAKE"
        seen.append(case_id)
        return original(case_id, store=store)
    monkeypatch.setattr(case_api, "get_view", committed_view)
    app = create_app(startup=startup)
    with TestClient(app) as client:
        response = client.post("/cases", content=b"PRIVATE {bad json", headers={"content-type": "text/plain"})
        assert response.status_code == 201
        body = response.json()
        assert set(body) == {"case_id", "case_view"}
        identity = body["case_id"]
        assert identity.startswith("case_") and seen == [identity]
        assert response.headers["location"] == f"/cases/{identity}/view"
        view = body["case_view"]
        assert view["case_id"] == identity and view["case_rev"] == 1 and view["stage"] == "INTAKE"
        assert view["running_jobs"] == [] and view["candidates"] == []
        with engine.begin() as conn:
            assert view == get_view(identity, store=store(conn))
        polled = client.get(response.headers["location"])
        assert polled.status_code == 200 and polled.json() == view
        assert "location" not in polled.headers
    assert count(engine) == 1
    assert registries and all(reference() is None for reference in registries)
    assert "PRIVATE" not in stream.getvalue()


@pytest.mark.mysql_check("api_cases", "create", parameter="body_unread")
def test_create_never_receives_request_body(api_db):
    startup, _, engine = api_db
    app = create_app(startup=startup)
    sent = []
    async def invoke():
        async def receive():
            raise AssertionError("POST /cases must not receive the body")
        async def send(message):
            sent.append(message)
        await app({"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
                   "http_version": "1.1", "method": "POST", "scheme": "http", "path": "/cases",
                   "raw_path": b"/cases", "query_string": b"", "root_path": "",
                   "headers": [(b"content-length", b"999999999"), (b"content-type", b"invalid")],
                   "server": ("testserver", 80), "client": ("testclient", 123)}, receive, send)
    try:
        asyncio.run(invoke())
        assert sent[0]["status"] == 201 and count(engine) == 1
    finally:
        app.state.composition.close()


@pytest.mark.mysql_check("api_view", "read", parameter="missing")
def test_missing_case_has_contract_404(api_db):
    startup, stream, _ = api_db
    with TestClient(create_app(startup=startup)) as client:
        response = client.get("/cases/PRIVATE_missing/view?secret=PRIVATE", headers={"x-trace-id": "PRIVATE"})
        assert response.status_code == 404 and response.json() == envelope("http.not_found")
    assert "PRIVATE" not in stream.getvalue()


@pytest.mark.parametrize("state,want", [
    pytest.param("QUEUED", "PENDING", marks=pytest.mark.mysql_check("api_view", "read", parameter="queued")),
    pytest.param("RUNNING", "RUNNING", marks=pytest.mark.mysql_check("api_view", "read", parameter="running")),
    pytest.param("SUCCEEDED", "RUNNING", marks=pytest.mark.mysql_check("api_view", "read", parameter="terminal_gap")),
])
def test_view_uses_runtime_port_and_preserves_case_projection(api_db, state, want):
    startup, stream, engine = api_db
    identity, job_id = seed(engine)
    seed(engine, "case_other")
    if state != "QUEUED":
        claimed = claim_one(engine, "worker_http")
        assert claimed.job_id == job_id
        if state == "SUCCEEDED":
            with engine.begin() as conn:
                assert finish(conn, claimed.execution_id, "worker_http", status="SUCCEEDED") == 1
    with engine.begin() as conn:
        expected = get_view(identity, store=store(conn))
    with TestClient(create_app(startup=startup)) as client:
        response = client.get(f"/cases/{identity}/view")
        assert response.status_code == 200 and response.json() == expected
        assert [(j["job_id"], j["status"]) for j in response.json()["running_jobs"]] == [(job_id, want)]
        for private in ("execution_id", "attempt", "lease_owner", "lease_expires_at", "claim_token", "trace_fixture", "case_other"):
            assert private not in response.text and private not in stream.getvalue()


@pytest.mark.mysql_check("api_view", "transaction", parameter="lock_order")
def test_view_holds_case_share_lock_on_same_connection_before_runtime_read(api_db, monkeypatch):
    from daesingo.api import composition
    startup, _, engine = api_db
    identity, job_id = seed(engine)
    observed = []
    def locked_read(conn, job_ids):
        assert conn.in_transaction() and job_ids == [job_id]
        assert conn.get_isolation_level() == "READ COMMITTED"
        result = read_executions(conn, job_ids)
        with engine.connect() as other:
            # NOWAIT proves an incompatible Case lock is already held.
            with pytest.raises(sa.exc.OperationalError) as error:
                other.exec_driver_sql("SELECT case_id FROM cases WHERE case_id=%s FOR UPDATE NOWAIT", (identity,))
            assert error.value.orig.args[0] == 3572
            # The read port itself does not lock Runtime rows.
            other.exec_driver_sql("SELECT execution_id FROM job_execution FOR UPDATE NOWAIT")
        observed.append(conn)
        return result
    monkeypatch.setattr(composition, "read_executions", locked_read, raising=False)
    with TestClient(create_app(startup=startup)) as client:
        assert client.get(f"/cases/{identity}/view").status_code == 200
    assert len(observed) == 1 and observed[0].closed


@pytest.mark.mysql_check("api_view", "transaction", parameter="uncommitted_scope")
def test_injected_reader_sees_callers_uncommitted_rows_and_rollback(api_db):
    startup, _, engine = api_db
    app = create_app(startup=startup)
    try:
        with engine.connect() as conn:
            transaction = conn.begin()
            caller_store = app.state.composition._store(conn)
            identity = create_case(store=caller_store)
            case = caller_store.load_for_update(identity)
            case.start_search()
            job = jobs.issue_coarse_search(case, scope_ref="scope", input_fingerprint="fp")
            caller_store.save(case)
            execution_ids = enqueue(conn, case.job_records, "trace_uncommitted")
            conn.exec_driver_sql("UPDATE job_execution SET status='RUNNING', started_at=NOW(6) WHERE execution_id=%s",
                                 (execution_ids[0],))
            assert count(engine) == 0
            view = get_view(identity, store=caller_store)
            assert [(j["job_id"], j["status"]) for j in view["running_jobs"]] == [(job["job_id"], "RUNNING")]
            assert conn.in_transaction()
            transaction.rollback()
        assert count(engine) == 0
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT COUNT(*) FROM job_execution").scalar_one() == 0
    finally:
        app.state.composition.close()


@pytest.mark.mysql_check("api_view", "read", parameter="latest_attempt")
def test_http_preserves_cases_latest_attempt_choice(api_db):
    startup, _, engine = api_db
    identity, job_id = seed(engine)
    claimed = claim_one(engine, "worker_old")
    with engine.begin() as conn:
        conn.exec_driver_sql("UPDATE job_execution SET status='STALE', ended_at=NOW(6) WHERE execution_id=%s", (claimed.execution_id,))
        conn.exec_driver_sql("""INSERT INTO job_execution (execution_id,job_id,case_id,kind,attempt,status,queued_at,available_at,trace_id,produced)
            SELECT 'execution_latest',job_id,case_id,kind,2,'QUEUED',NOW(6),NOW(6),'trace_latest',JSON_ARRAY()
            FROM job_execution WHERE execution_id=%s""", (claimed.execution_id,))
    with TestClient(create_app(startup=startup)) as client:
        response = client.get(f"/cases/{identity}/view")
        assert response.status_code == 200
        assert [(j["job_id"], j["status"]) for j in response.json()["running_jobs"]] == [(job_id, "PENDING")]


@pytest.mark.mysql_check("api_cases", "failure", parameter="unrelated_sql")
def test_unrelated_real_sql_error_is_500_and_never_disclosed(api_db, monkeypatch):
    import daesingo.case as case_api
    startup, stream, engine = api_db
    def invalid(*, store):
        create_case(store=store)
        store.conn.exec_driver_sql("SELECT PRIVATE_SQL_secret FROM PRIVATE_missing_table")
    monkeypatch.setattr(case_api, "create_case", invalid)
    with TestClient(create_app(startup=startup)) as client:
        response = client.post("/cases")
        assert response.status_code == 500 and response.json() == envelope("http.internal_error")
    assert count(engine) == 0 and "PRIVATE" not in stream.getvalue()


@pytest.mark.mysql_check("api_cases", "transaction", parameter="rollback")
def test_create_failure_rolls_back_real_case_without_retry(api_db, monkeypatch):
    import daesingo.case as case_api
    startup, stream, engine = api_db
    calls = []
    def fail(*, store):
        calls.append(create_case(store=store))
        assert store.conn.in_transaction()
        raise RuntimeError("PRIVATE SQL /path secret")
    monkeypatch.setattr(case_api, "create_case", fail)
    with TestClient(create_app(startup=startup)) as client:
        response = client.post("/cases")
        assert response.status_code == 500 and response.json() == envelope("http.internal_error")
    assert len(calls) == 1 and count(engine) == 0 and "PRIVATE" not in stream.getvalue()


@pytest.mark.parametrize("method,path", [
    pytest.param("post", "/cases", marks=pytest.mark.mysql_check("api_cases", "failure", parameter="pool_exhausted")),
    pytest.param("get", "/cases/missing/view", marks=pytest.mark.mysql_check("api_view", "failure", parameter="pool_exhausted")),
])
def test_real_pool_exhaustion_is_safe_503(api_db, method, path):
    from contextlib import ExitStack
    startup, stream, engine = api_db
    app = create_app(startup=startup)
    with TestClient(app) as client, ExitStack() as stack:
        for _ in range(3):
            stack.enter_context(app.state.composition.engine.connect())
        response = getattr(client, method)(path)
        assert response.status_code == 503 and response.json() == envelope("http.dependency_unavailable")
    assert count(engine) == 0 and "secret" not in stream.getvalue()


@pytest.mark.mysql_check("api_view", "failure", parameter="lock_timeout")
def test_view_real_1205_has_503_and_releases_transaction(api_db):
    startup, _, engine = api_db
    identity, _ = seed(engine)
    app = create_app(startup=startup)
    @sa.event.listens_for(app.state.composition.engine, "connect")
    def short_wait(dbapi, record):
        with dbapi.cursor() as cursor:
            cursor.execute("SET SESSION innodb_lock_wait_timeout=1")
    with engine.begin() as blocker, TestClient(app) as client:
        blocker.exec_driver_sql("SELECT case_id FROM cases WHERE case_id=%s FOR UPDATE", (identity,))
        response = client.get(f"/cases/{identity}/view")
        assert response.status_code == 503 and response.json() == envelope("http.dependency_unavailable")
        assert app.state.composition.engine.pool.checkedout() == 0


@pytest.mark.parametrize("phase", [
    pytest.param("create", marks=pytest.mark.mysql_check("api_cases", "failure", parameter="disconnect")),
    pytest.param("view", marks=pytest.mark.mysql_check("api_view", "failure", parameter="disconnect")),
    pytest.param("after_create", marks=pytest.mark.mysql_check("api_cases", "failure", parameter="postcommit_read")),
])
def test_real_disconnect_status_respects_already_committed_create(api_db, monkeypatch, phase):
    import daesingo.case as case_api
    startup, stream, engine = api_db
    identity = None
    calls = []
    if phase == "view":
        with engine.begin() as conn:
            identity = create_case(store=store(conn))
    def kill(conn):
        connection_id = conn.exec_driver_sql("SELECT CONNECTION_ID()").scalar_one()
        with engine.connect() as control:
            control.exec_driver_sql(f"KILL CONNECTION {connection_id}")
        conn.exec_driver_sql("SELECT 1")
    def interrupted_create(*, store):
        calls.append(create_case(store=store))
        kill(store.conn)
    def interrupted_view(case_id, *, store):
        calls.append(case_id)
        kill(store.conn)
    monkeypatch.setattr(case_api, "create_case" if phase == "create" else "get_view",
                        interrupted_create if phase == "create" else interrupted_view)
    with TestClient(create_app(startup=startup)) as client:
        response = client.get(f"/cases/{identity}/view") if phase == "view" else client.post("/cases")
        status, code = (500, "http.internal_error") if phase == "after_create" else (503, "http.dependency_unavailable")
        assert response.status_code == status and response.json() == envelope(code)
    assert len(calls) == 1 and count(engine) == (0 if phase == "create" else 1)
    assert "KILL" not in stream.getvalue() and "secret" not in stream.getvalue()


@pytest.mark.parametrize("phase", [
    pytest.param("create", marks=pytest.mark.mysql_check("api_cases", "failure", parameter="commit_unknown")),
    pytest.param("view", marks=pytest.mark.mysql_check("api_view", "failure", parameter="commit_unknown")),
])
def test_actual_commit_ack_loss_is_500_without_replaying_case(api_db, monkeypatch, phase):
    import daesingo.case as case_api
    startup, stream, engine = api_db
    calls = []
    identity = None
    if phase == "view":
        with engine.begin() as conn:
            identity = create_case(store=store(conn))
    with CommitResponseProxy(engine.url.host, engine.url.port) as proxy:
        url = engine.url.set(host="127.0.0.1", port=proxy.port).update_query_dict({"ssl_disabled": "true"})
        startup = replace(startup, config=replace(startup.config, db=DbSettings(
                            url=url.render_as_string(hide_password=False))))
        original = case_api.create_case if phase == "create" else case_api.get_view
        def operation(*args, **kwargs):
            result = original(*args, **kwargs)
            calls.append(result)
            proxy.arm()
            return result
        monkeypatch.setattr(case_api, "create_case" if phase == "create" else "get_view", operation)
        with TestClient(create_app(startup=startup)) as client:
            response = client.post("/cases") if phase == "create" else client.get(f"/cases/{identity}/view")
            assert response.status_code == 500 and response.json() == envelope("http.internal_error")
        assert proxy.commit_ok_dropped == 1
    assert len(calls) == 1 and count(engine) == 1 and "secret" not in stream.getvalue()


@pytest.mark.mysql_check("api_cases", "failure", parameter="deadlock")
def test_real_deadlock_victim_is_503_with_no_api_retry(api_db, monkeypatch):
    import daesingo.case as case_api
    startup, _, engine = api_db
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE http_lock (id INT PRIMARY KEY, value INT) ENGINE=InnoDB")
        conn.exec_driver_sql("INSERT INTO http_lock VALUES (1,0),(2,0)")
    barrier = Barrier(2, timeout=10)
    codes, calls = [], []
    def deadlocked_create(*, store):
        conn = store.conn
        # API has less rollback weight, so InnoDB chooses it as victim.
        conn.exec_driver_sql("UPDATE http_lock SET value=value+1 WHERE id=1")
        barrier.wait()
        try:
            conn.exec_driver_sql("UPDATE http_lock SET value=value+1 WHERE id=2")
        except sa.exc.DBAPIError as error:
            codes.append(error.orig.args[0])
            raise
        return create_case(store=store)
    def blocker():
        with engine.begin() as conn:
            conn.exec_driver_sql("UPDATE http_lock SET value=value+1 WHERE id=2")
            for n in range(3, 30):
                conn.exec_driver_sql("INSERT INTO http_lock VALUES (%s,0)", (n,))
            barrier.wait()
            conn.exec_driver_sql("UPDATE http_lock SET value=value+1 WHERE id=1")
    def counted(*, store):
        calls.append(1)
        return deadlocked_create(store=store)
    monkeypatch.setattr(case_api, "create_case", counted)
    with TestClient(create_app(startup=startup)) as client, ThreadPoolExecutor(1) as pool:
        future = pool.submit(blocker)
        response = client.post("/cases")
        future.result(timeout=15)
        assert response.status_code == 503 and response.json() == envelope("http.dependency_unavailable")
    assert codes == [1213] and calls == [1] and count(engine) == 0


@pytest.mark.mysql_check("api_cases", "logging", parameter="correlation")
def test_case_requests_keep_trace_with_broken_or_slow_sink(api_db):
    startup, stream, engine = api_db
    entered, release = Event(), Event()
    def slow(record):
        entered.set()
        release.wait(5)
        raise RuntimeError("PRIVATE sink")
    startup.logger.addFilter(slow)
    app = create_app(startup=startup)
    try:
        with TestClient(app) as client:
            started = monotonic()
            first = client.post("/cases", headers={"x-trace-id": "PRIVATE"})
            assert first.status_code == 201 and entered.wait(1)
            assert client.get(first.headers["location"]).status_code == 200
            assert monotonic() - started < 2
            release.set()
    finally:
        release.set()
        startup.logger.removeFilter(slow)
    # A fresh app uses the same safe stream and supplies independent traces.
    with TestClient(create_app(startup=startup)) as client:
        response = client.post("/cases")
        assert client.get(response.headers["location"]).status_code == 200
    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    completed = [e for e in events if e["event"] == "api.request.completed"]
    assert len(completed) == 2 and len({e["trace_id"] for e in completed}) == 2
    assert all(e["case_id"] == response.json()["case_id"] for e in completed)
    views = [e for e in events if e["event"] == "api.view.completed"]
    assert len(views) == 2 and all(e["duration_ms"] >= 0 for e in views)
    assert {e["trace_id"] for e in views} == {e["trace_id"] for e in completed}
    assert all(e["trace_id"].startswith("tr_") for e in events)
    assert "PRIVATE" not in stream.getvalue() and count(engine) == 2
