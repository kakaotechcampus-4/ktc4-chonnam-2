"""Startup redelivery is an admission gate, distinct from best-effort hooks."""

from io import StringIO
import json
from threading import Event

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

from daesingo.common.config import WorkerSettings
from daesingo.common.jobs.sweep import SweepService
from daesingo.common.jobs.worker_loop import WorkerLoop
from daesingo.common.logging import configure_logging
from daesingo.common.logging.catalog import validate_event
from daesingo.common.jobs.redelivery import redeliver_once
from daesingo.common.jobs.reflection import ReflectionResult
from daesingo.common.jobs.schema import job_execution as jobs
from logging_faults import install_logging_fault
from worker_error_support import NAMES, assert_private_absent, private_error


@pytest.mark.parametrize("phase", ["startup", "periodic"])
def test_redelivery_scan_precedes_claim_and_runs_each_period(phase):
    stop, calls = Event(), []
    logger = configure_logging("worker", stream=StringIO())

    def redeliver():
        calls.append("redeliver")
        if phase == "startup" and calls.count("redeliver") == 1:
            raise OperationalError("secret", {}, Exception(2003, "secret"))

    def claim():
        calls.append("claim")
        stop.set()

    runner = SweepService(sweep=lambda: calls.append("sweep"), redeliver=redeliver,
        settings=WorkerSettings(), stop=stop, logger=logger,
        retry_wait=lambda seconds: calls.append("retry"), wait=lambda seconds: stop.wait(10))
    if phase == "startup":
        WorkerLoop(claim=claim, dispatch=lambda c: None, record=lambda c, r: True,
            settings=WorkerSettings(), stop=stop, logger=logger, sweeper=runner).run()
        assert calls == ["sweep", "redeliver", "retry", "sweep", "redeliver", "claim"]
    else:
        def wait(seconds):
            if calls.count("redeliver") == 2:
                stop.set()
                return True
            return False
        runner.wait = wait
        runner.run()
        assert calls == ["sweep", "redeliver"] * 2


@pytest.fixture
def redelivery_engine():
    """Real candidate scans/transactions; SQLite supplies no MySQL lock evidence."""
    from datetime import datetime

    engine = sa.create_engine("sqlite://")

    @sa.event.listens_for(engine, "connect")
    def sqlite_functions(connection, record):
        connection.create_collation("ascii_bin", lambda left, right: (left > right) - (left < right))
        connection.create_function("utc_timestamp", 1, lambda precision: "2026-01-01 00:00:00.000000")

    jobs.create(engine)
    with engine.begin() as conn:
        for identity in ("first", "second"):
            conn.execute(jobs.insert().values(execution_id=identity, job_id=identity,
                case_id="case", trace_id="trace", kind="TEST", attempt=1,
                status="SUCCEEDED", produced=[], queued_at=datetime(2026, 1, 1),
                available_at=datetime(2026, 1, 1)))
    try:
        yield engine
    finally:
        engine.dispose()


def run_redelivery_failure(engine, error, sink="healthy", *, attempts=1):
    stream, calls = StringIO(), []
    logger = configure_logging("worker", stream=stream)

    class Reflector:
        def reflect(self, conn, incoming):
            calls.append(incoming.execution_id)
            if incoming.execution_id == "first":
                raise error
            return ReflectionResult("NOT_APPLIED", "STOPPED_WAITING")

    seen, remove = ([], lambda: None) if sink == "healthy" else install_logging_fault(
        logger, sink, lambda name: name == "runtime.reflect.failed")
    try:
        result = redeliver_once(engine, Reflector(), logger=logger, sleep=lambda seconds: None)
    finally:
        remove()
    assert result == (ReflectionResult("NOT_APPLIED", "STOPPED_WAITING"),)
    assert calls == ["first"] * attempts + ["second"]
    with engine.connect() as conn:
        rows = conn.execute(sa.select(jobs).order_by(jobs.c.execution_id)).mappings().all()
    assert [row["status"] for row in rows] == ["SUCCEEDED", "SUCCEEDED"]
    assert [row["failure_kind"] for row in rows] == [None, None]
    assert [row["case_applied_at"] is not None for row in rows] == [False, True]
    assert_private_absent(stream.getvalue())
    failures = [json.loads(line) for line in stream.getvalue().splitlines() if '"runtime.reflect.failed"' in line]
    return failures, seen


@pytest.mark.parametrize("error,expected,attempts", [
    (private_error(), "_FrameCoverageError", 1),
    (OperationalError("SELECT secret FROM private_jobs", {"payload": "PRIVATE_PROVIDER_PAYLOAD"},
                      Exception(1213, "credential_SENTINEL_464")), "TransactionRetryExhausted", 3),
])
def test_redelivery_error_type_is_outermost(redelivery_engine, error, expected, attempts):
    failures, _ = run_redelivery_failure(redelivery_engine, error, attempts=attempts)
    assert len(failures) == 1
    assert failures[0]["error_type"] == expected


@pytest.mark.parametrize("qualname,expected", NAMES)
def test_redelivery_tokens_and_privacy(redelivery_engine, qualname, expected, capsys):
    failures, _ = run_redelivery_failure(redelivery_engine, private_error(qualname))
    assert len(failures) == 1
    row = failures[0]
    assert row.get("error_type") == expected
    assert ("error_type" in row) == (expected is not None)
    assert row["execution_id"] == "first"
    assert set(row) == {"timestamp", "level", "service", "event", "status", "execution_id"} | ({"error_type"} if expected else set())
    validate_event(row)
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("sink", ["filter", "handler"])
def test_redelivery_error_log_fault_does_not_change_results(redelivery_engine, sink, capsys):
    _, seen = run_redelivery_failure(redelivery_engine, private_error(), sink)
    assert seen == ["runtime.reflect.failed"]
    assert capsys.readouterr().err == ""
