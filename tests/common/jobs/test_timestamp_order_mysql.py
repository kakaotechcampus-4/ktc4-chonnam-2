"""#370: deterministic MySQL session-clock regression, never host clock steps."""

from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from io import StringIO
import json
from threading import Barrier, Event
from types import MappingProxyType

import pytest
from sqlalchemy import event, select

from daesingo.common.config import WorkerSettings
from daesingo.common.config import DbSettings, RuntimeConfig
from daesingo.common.bootstrap import Startup
from daesingo.common.db import create_worker_engine
from daesingo.common.db.migrate import upgrade_all
from daesingo.common.db.transactions import run_worker_transaction
from daesingo.common.jobs.cancel import request_cancel
from daesingo.common.jobs.heartbeat import LeaseConnection, OwnershipFence
from daesingo.common.jobs.read_port import read_executions
from daesingo.common.jobs.repository import _execution_model, claim_one, enqueue, finish
from daesingo.common.jobs.schema import job_execution as jobs
from daesingo.common.jobs.sweep import sweep_once
from daesingo.common.jobs.execution import ExecutionContext, HandlerResult
from daesingo.common.jobs.cancel import CancelledExecution
from daesingo.common.logging import configure_logging
from daesingo.worker.composition import compose_worker
from daesingo.worker.registry import KindRegistry
from mysql_fault_proxy import CommitResponseProxy

pytestmark = pytest.mark.mysql
T = 1792168658  # Synthetic test clock, not an observed event timestamp.
START = datetime(2026, 10, 16, 16, 37, 38)


@contextmanager
def db_clock(engine, timestamp):
    """SET timestamp is session-local. Dispose reset sessions after each scope.

    A dedicated engine/session is required if threads need different clocks.
    Retained heartbeat connections must be closed before this scope exits.
    """
    def set_clock(dbapi, record, proxy):
        with dbapi.cursor() as cursor:
            cursor.execute("SET timestamp = %s", (timestamp() if callable(timestamp) else timestamp,))
    event.listen(engine, "checkout", set_clock)
    try:
        yield
    finally:
        event.remove(engine, "checkout", set_clock)
        engine.dispose()


@pytest.fixture
def queue(mysql_engine, mysql_schema_url):
    upgrade_all(mysql_schema_url)
    return mysql_engine


def seeded(queue, *, running=True, job="clock_job", owner="owner"):
    with db_clock(queue, T - 2), queue.begin() as conn:
        execution, = enqueue(conn, [dict(job_id=job, case_id="case", kind="TEST")], "trace")
    if running:
        with db_clock(queue, T):
            assert claim_one(queue, owner).execution_id == execution
    return execution


def stored(queue, execution):
    with queue.connect() as conn:
        return dict(conn.execute(select(jobs).where(jobs.c.execution_id == execution)).mappings().one())


def valid_projection(queue, execution):
    row = stored(queue, execution)
    assert _execution_model(row).execution_id == execution
    with queue.connect() as conn:
        projected, = read_executions(conn, [row["job_id"]])[:1]
    assert projected["execution_id"] == execution
    return row


def renew(queue, execution, timestamp, duration=60):
    lease = LeaseConnection(queue, execution, "owner", duration, fence=OwnershipFence())
    with db_clock(queue, timestamp):
        try:
            return lease.renew()
        finally:
            lease.close()


@pytest.mark.mysql_check("timestamp_order", "terminal")
@pytest.mark.parametrize("status", [pytest.param(status, marks=pytest.mark.mysql_check(
    "timestamp_order", "terminal", parameter=status))
    for status in ("SUCCEEDED", "FAILED", "CANCELLED", "STALE", "QUEUED_CANCEL")])
def test_terminal_writers_preserve_durable_order_after_backward_step(queue, status):
    execution = seeded(queue, running=status != "QUEUED_CANCEL")
    if status == "STALE":
        # Preserved incident fixture changes heartbeat/lease only, never start/end.
        with queue.begin() as conn:
            conn.exec_driver_sql("UPDATE job_execution SET heartbeat_at=FROM_UNIXTIME(%s), "
                "lease_expires_at=FROM_UNIXTIME(%s) WHERE execution_id=%s", (T-62, T-2, execution))
    timestamp = T - 3.25 if status == "QUEUED_CANCEL" else T - 1.25
    with db_clock(queue, timestamp):
        if status == "STALE":
            assert len(sweep_once(queue, WorkerSettings())) == 1
        else:
            with queue.begin() as conn:
                if status == "QUEUED_CANCEL":
                    request_cancel(conn, ["clock_job"])
                else:
                    assert finish(conn, execution, "owner", status=status,
                        failure_kind="TEST_FAILURE" if status == "FAILED" else None) == 1
    row = valid_projection(queue, execution)
    assert row["status"] == ("CANCELLED" if status == "QUEUED_CANCEL" else status)
    floor = START - timedelta(seconds=2) if status == "QUEUED_CANCEL" else START
    assert row["ended_at"] == floor
    assert row["ended_at"] >= (row["started_at"] or row["queued_at"])


@pytest.mark.mysql_check("timestamp_order", "renewal", parameter="non_regression")
def test_successful_renewal_never_shortens_heartbeat_or_lease(queue):
    execution = seeded(queue)
    assert renew(queue, execution, T - 1.25) == 1
    first = stored(queue, execution)
    assert first["heartbeat_at"] == START
    assert first["lease_expires_at"] == START + timedelta(seconds=60)
    # Matched but unchanged row remains a successful renewal, not ownership loss.
    assert renew(queue, execution, T - 120) == 1
    assert stored(queue, execution) == first
    assert renew(queue, execution, T + 1) == 1
    after = stored(queue, execution)
    assert after["heartbeat_at"] == START + timedelta(seconds=1)
    assert after["lease_expires_at"] == START + timedelta(seconds=61)


@pytest.mark.mysql_check("timestamp_order", "renewal", parameter="sweep_recheck")
def test_regressed_renewal_cannot_make_a_live_execution_stale_without_fixture_edits(queue):
    execution = seeded(queue)
    assert renew(queue, execution, T - 120) == 1
    with db_clock(queue, T - 1.25):
        assert sweep_once(queue, WorkerSettings()) == ()
    assert stored(queue, execution)["status"] == "RUNNING"
    with db_clock(queue, T + 61):
        outcome, = sweep_once(queue, WorkerSettings())
    row = valid_projection(queue, execution)
    assert row["ended_at"] == START + timedelta(seconds=61)
    assert outcome.detect_latency_sec == 61


def expired_fixture(queue, execution):
    with queue.begin() as conn:
        conn.exec_driver_sql("UPDATE job_execution SET heartbeat_at=FROM_UNIXTIME(%s), "
            "lease_expires_at=FROM_UNIXTIME(%s) WHERE execution_id=%s", (T-62, T-2, execution))


def record(engine, execution, status, waits, stream):
    config = RuntimeConfig.from_mapping("worker", {
        "DAESINGO_RUNTIME_DB_URL": engine.url.render_as_string(hide_password=False),
        "DAESINGO_RUNTIME_MEDIA_ROOT": "/private/clock-media",
        "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": "/private/clock-temp",
    })
    startup = Startup(config, MappingProxyType({}), configure_logging("worker", stream=stream))
    worker = compose_worker(engine=engine, startup=startup, registry=KindRegistry({}),
        stop=Event(), worker_id="owner", sleep=waits)
    context = ExecutionContext(execution, "clock_job", "case", "TEST", 1, "trace")
    result = (CancelledExecution() if status == "CANCELLED" else
              HandlerResult(status=status, failure_kind="TEST_FAILED" if status == "FAILED" else None))
    return worker.record(context, result)


@pytest.mark.mysql_check("timestamp_order", "bounds")
@pytest.mark.parametrize("bound", [pytest.param(b, marks=pytest.mark.mysql_check(
    "timestamp_order", "bounds", parameter=b)) for b in ("heartbeat", "cancel", "null")])
def test_terminal_causal_bounds_and_null_metadata_exclude_future_lease(queue, bound):
    execution = seeded(queue)
    with queue.begin() as conn:
        conn.exec_driver_sql("UPDATE job_execution SET heartbeat_at=%s, cancel_requested_at=%s, "
            "lease_expires_at=%s WHERE execution_id=%s", (
                START + timedelta(seconds=3) if bound == "heartbeat" else None,
                START + timedelta(seconds=4) if bound == "cancel" else None,
                START + timedelta(seconds=600), execution))
    with db_clock(queue, T - 1.25), queue.begin() as conn:
        assert finish(conn, execution, "owner", status="SUCCEEDED") == 1
    row = valid_projection(queue, execution)
    assert row["ended_at"] == START + timedelta(seconds={"heartbeat": 3, "cancel": 4, "null": 0}[bound])
    assert row["ended_at"] < row["lease_expires_at"]


@pytest.mark.mysql_check("timestamp_order", "metrics", parameter="duration_detect_backoff")
def test_clamped_duration_detect_latency_and_retry_backoff_use_durable_terminal(queue):
    execution = seeded(queue)
    expired_fixture(queue, execution)
    stream = StringIO()
    with db_clock(queue, T - 1.25):
        outcome, = sweep_once(queue, WorkerSettings(), logger=configure_logging("worker", stream=stream))
    parent = valid_projection(queue, execution)
    child = stored(queue, outcome.retry_execution_id)
    assert parent["ended_at"] - parent["started_at"] == timedelta(0)
    assert outcome.detect_latency_sec == 62
    assert child["queued_at"] == parent["ended_at"] == START
    assert child["available_at"] == START + timedelta(seconds=5)
    event_, = [json.loads(s) for s in stream.getvalue().splitlines()
               if json.loads(s)["event"] == "runtime.stale.detect_latency_s"]
    assert event_["duration_ms"] == 62000
    with db_clock(queue, T + 4.999999):
        assert claim_one(queue, "owner") is None
    with db_clock(queue, T + 5):
        claimed = claim_one(queue, "owner")
    assert claimed.execution_id == outcome.retry_execution_id
    assert claimed.started_at - claimed.queued_at == timedelta(seconds=5)


@pytest.mark.mysql_check("timestamp_order", "retry")
@pytest.mark.parametrize("status,code", [pytest.param(s, code, marks=pytest.mark.mysql_check(
    "timestamp_order", "retry", parameter=f"{s}_{code}"))
    for s in ("SUCCEEDED", "FAILED", "CANCELLED", "STALE") for code in (1205, 1213)])
def test_clock_step_and_server_lock_errors_replay_whole_transaction(queue, status, code):
    execution = seeded(queue)
    if status == "STALE":
        expired_fixture(queue, execution)
    failed, waits, inserts = [], [], []
    def fault(conn, cursor, sql, params, ctx, many):
        target = sql.startswith("INSERT INTO job_execution") if status == "STALE" else sql.startswith("UPDATE job_execution SET status")
        if sql.startswith("INSERT INTO job_execution"):
            inserts.append(params["execution_id"])
        if target and not failed:
            failed.append(code)
            conn.exec_driver_sql(f"SIGNAL SQLSTATE '40001' SET MYSQL_ERRNO={code}, MESSAGE_TEXT='private-clock-test'")
    def retry(seconds):
        waits.append(seconds)
        # The terminal write/child INSERT must both have rolled back.
        assert stored(queue, execution)["status"] == "RUNNING"
        with queue.connect() as conn:
            assert len(conn.execute(select(jobs)).all()) == 1
    event.listen(queue, "before_cursor_execute", fault)
    try:
        with db_clock(queue, T - 1.25):
            if status == "STALE":
                assert len(sweep_once(queue, WorkerSettings(), sleep=retry)) == 1
            else:
                assert record(queue, execution, status, retry, StringIO())
    finally:
        event.remove(queue, "before_cursor_execute", fault)
    assert failed == [code] and waits == [1]
    assert valid_projection(queue, execution)["ended_at"] == START
    if status == "STALE":
        assert len(inserts) == 2 and inserts[0] == inserts[1]


@pytest.mark.mysql_check("timestamp_order", "commit_unknown")
@pytest.mark.parametrize("path", [pytest.param(p, marks=pytest.mark.mysql_check(
    "timestamp_order", "commit_unknown", parameter=p))
    for p in ("claim", "SUCCEEDED", "FAILED", "CANCELLED", "STALE", "QUEUED_CANCEL", "T2")])
def test_clock_step_and_real_commit_ack_loss_preserve_pinned_receipts(queue, path):
    if path == "T2":
        from redelivery_support import seed, adapter, snapshot
        from daesingo.common.jobs.redelivery import redeliver_once
        with db_clock(queue, T):
            case_id, execution = seed(queue)
    else:
        execution = seeded(queue, running=path not in ("claim", "QUEUED_CANCEL"))
    if path == "STALE":
        expired_fixture(queue, execution)
    waits, before_replay, times, stream = [], [], [T if path == "claim" else T-1.25], StringIO()
    with CommitResponseProxy(queue.url.host, queue.url.port) as proxy:
        url = queue.url.set(host="127.0.0.1", port=proxy.port).update_query_dict({"ssl_disabled": "true"})
        engine = create_worker_engine(DbSettings(url=url.render_as_string(hide_password=False)))
        def arm(conn, cursor, sql, params, ctx, many):
            if sql.lstrip().upper().startswith("UPDATE JOB_EXECUTION"):
                proxy.arm()
        def retry(seconds):
            waits.append(seconds)
            before_replay.append(stored(queue, execution))
            times[0] = T - 120  # Recovery must preserve durable receipt, not resample a new terminal.
        event.listen(engine, "after_cursor_execute", arm)
        try:
            with db_clock(engine, lambda: times[0]):
                if path == "claim":
                    from daesingo.common.jobs import repository
                    # Inject only retry waiting; retain the production claim operation.
                    original = repository.run_worker_transaction
                    def runner(engine_, operation, **kwargs):
                        return run_worker_transaction(engine_, operation, sleep=retry, **kwargs)
                    with pytest.MonkeyPatch.context() as mp:
                        mp.setattr(repository, "run_worker_transaction", runner)
                        assert claim_one(engine, "owner").execution_id == execution
                    assert repository.run_worker_transaction is original
                elif path == "STALE":
                    outcome, = sweep_once(engine, WorkerSettings(), sleep=retry)
                    assert outcome.retry_execution_id is not None
                elif path == "QUEUED_CANCEL":
                    run_worker_transaction(engine, lambda conn: request_cancel(conn, ["clock_job"]), sleep=retry)
                elif path == "T2":
                    redeliver_once(engine, adapter(), sleep=retry)
                    assert snapshot(queue, case_id).processed_executions
                else:
                    assert record(engine, execution, path, retry, stream)
            assert proxy.commit_ok_dropped == 1 and waits == [1]
        finally:
            event.remove(engine, "after_cursor_execute", arm)
            engine.dispose()
    after = valid_projection(queue, execution)
    assert after == before_replay[0]
    if path == "STALE":
        with queue.connect() as conn:
            children = conn.execute(select(jobs).where(jobs.c.attempt == 2)).mappings().all()
        assert len(children) == 1 and children[0]["execution_id"] == outcome.retry_execution_id
    assert all(word not in stream.getvalue() for word in ("private-clock", "clock-media", "claim_token", "mysql+pymysql"))


@pytest.mark.mysql_check("timestamp_order", "concurrent")
@pytest.mark.parametrize("first", [pytest.param(p, marks=pytest.mark.mysql_check(
    "timestamp_order", "concurrent", parameter=p)) for p in ("race", "heartbeat", "sweep", "cancel")])
def test_concurrent_heartbeat_sweep_finish_cancel_keep_one_terminal_and_fences(queue, first):
    execution = seeded(queue)
    expired_fixture(queue, execution)
    ready, first_done = Barrier(4, timeout=15), Event()
    def operation(name):
        ready.wait()
        if first != "race" and name != first:
            assert first_done.wait(15)
        try:
            if name == "heartbeat":
                lease = LeaseConnection(queue, execution, "owner", 60, fence=OwnershipFence())
                try:
                    return lease.renew()
                finally:
                    lease.close()
            if name == "sweep":
                return sweep_once(queue, WorkerSettings())
            with queue.begin() as conn:
                if name == "finish":
                    return finish(conn, execution, "owner", status="SUCCEEDED")
                request_cancel(conn, ["clock_job"])
        finally:
            if name == first:
                first_done.set()
    with db_clock(queue, T-1.25), ThreadPoolExecutor(max_workers=4) as pool:
        results = [pool.submit(operation, n) for n in ("heartbeat", "sweep", "finish", "cancel")]
        for result in results:
            result.result(timeout=25)
    row = valid_projection(queue, execution)
    assert row["status"] in ("SUCCEEDED", "STALE")
    assert row["ended_at"] >= row["started_at"]
    with db_clock(queue, T-120), queue.begin() as conn:
        assert finish(conn, execution, "owner", status="FAILED", failure_kind="TEST") == 0
        assert finish(conn, execution, "other", status="SUCCEEDED") == 0
    with queue.connect() as conn:
        assert len(conn.execute(select(jobs)).all()) <= 2
    assert renew(queue, execution, T-120) == 0
    assert stored(queue, execution) == row


@pytest.mark.mysql_check("timestamp_order", "concurrent", parameter="finish_snapshot")
def test_final_finish_update_clamps_against_heartbeat_after_validation_snapshot(queue):
    execution = seeded(queue)
    heartbeat_engine = create_worker_engine(DbSettings(url=queue.url.render_as_string(hide_password=False)))
    completed = []
    def interleave(conn, cursor, sql, params, ctx, many):
        if sql.startswith("UPDATE job_execution SET status") and not completed:
            completed.append(True)
            with ThreadPoolExecutor(max_workers=1) as pool:
                assert pool.submit(renew, heartbeat_engine, execution, T+10).result(timeout=15) == 1
    event.listen(queue, "before_cursor_execute", interleave)
    try:
        with db_clock(queue, T-1.25), queue.begin() as conn:
            assert finish(conn, execution, "owner", status="SUCCEEDED") == 1
    finally:
        event.remove(queue, "before_cursor_execute", interleave)
        heartbeat_engine.dispose()
    row = valid_projection(queue, execution)
    assert row["ended_at"] == row["heartbeat_at"] == START + timedelta(seconds=10)


@pytest.mark.mysql_check("timestamp_order", "renewal")
@pytest.mark.parametrize("mode", [pytest.param(m, marks=pytest.mark.mysql_check(
    "timestamp_order", "renewal", parameter=m)) for m in ("null_metadata", "longer_lease")])
def test_renewal_handles_null_metadata_and_retains_a_longer_existing_lease(queue, mode):
    execution = seeded(queue)
    with queue.begin() as conn:
        conn.exec_driver_sql("UPDATE job_execution SET heartbeat_at=NULL, lease_expires_at=%s "
            "WHERE execution_id=%s", (None if mode == "null_metadata" else START+timedelta(seconds=600), execution))
    assert renew(queue, execution, T-1.25) == 1
    row = stored(queue, execution)
    assert row["heartbeat_at"] == START
    assert row["lease_expires_at"] == START + timedelta(seconds=60 if mode == "null_metadata" else 600)


@pytest.mark.mysql_check("timestamp_order", "retry", parameter="real_1213")
def test_backward_clock_and_actual_innodb_deadlock_retry_keep_order(queue):
    ids = [seeded(queue, job=f"job_{i}") for i in range(2)]
    barrier, attempts, codes = Barrier(2, timeout=15), [0, 0], []
    def observed(ctx):
        if ctx.original_exception.args[0] == 1213:
            codes.append(1213)
    def participant(index):
        first, second = ids if index == 0 else ids[::-1]
        def operation(conn):
            attempts[index] += 1
            changed = finish(conn, first, "owner", status="SUCCEEDED")
            if attempts[index] == 1:
                barrier.wait()
            return changed + finish(conn, second, "owner", status="SUCCEEDED")
        return run_worker_transaction(queue, operation, sleep=lambda _: None)
    event.listen(queue, "handle_error", observed)
    try:
        with db_clock(queue, T-1.25), ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(participant, i) for i in range(2)]
            assert sum(f.result(timeout=25) for f in futures) == 2
    finally:
        event.remove(queue, "handle_error", observed)
    assert codes == [1213] and sorted(attempts) == [1, 2]
    assert all(valid_projection(queue, i)["ended_at"] == START for i in ids)


@pytest.mark.mysql_check("timestamp_order", "retry", parameter="real_1205")
def test_backward_clock_and_actual_innodb_lock_timeout_retry_keep_order(queue):
    execution = seeded(queue)
    waits, attempts = [], []
    with queue.connect() as blocker:
        tx = blocker.begin()
        blocker.execute(select(jobs).where(jobs.c.execution_id == execution).with_for_update()).one()
        def operation(conn):
            attempts.append(True)
            conn.exec_driver_sql("SET SESSION innodb_lock_wait_timeout=1")
            return finish(conn, execution, "owner", status="SUCCEEDED")
        def retry(seconds):
            waits.append(seconds)
            assert stored(queue, execution)["status"] == "RUNNING"
            tx.rollback()
        try:
            with db_clock(queue, T-1.25):
                assert run_worker_transaction(queue, operation, sleep=retry) == 1
        finally:
            if tx.is_active:
                tx.rollback()
    assert attempts == [True, True] and waits == [1]
    assert valid_projection(queue, execution)["ended_at"] == START
