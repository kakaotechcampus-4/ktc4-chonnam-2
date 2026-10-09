"""Injected scheduling only; queue/transactions are covered on real MySQL."""

from datetime import datetime, timezone
from dataclasses import replace
from importlib import import_module
from io import StringIO
import json
from threading import Event

import pytest
from sqlalchemy.exc import OperationalError, TimeoutError

from daesingo.common.config import WorkerSettings
from daesingo.common.db.errors import TransactionRetryExhausted
from daesingo.common.jobs.repository import ClaimedExecution, ClaimLostError
from daesingo.common.logging import configure_logging
from logging_faults import install_logging_fault


def claim(job="job"):
    now = datetime.now(timezone.utc)
    return ClaimedExecution("exec_" + job, job, 1, "TEST", "case", "trace", "worker", now, now)


def loop(**overrides):
    module = import_module("daesingo.common.jobs.worker_loop")
    registry = import_module("daesingo.worker.registry")
    args = dict(claim=lambda: None, dispatch=lambda ctx: registry.HandlerResult(),
                record=lambda ctx, result: True, settings=WorkerSettings(),
                stop=Event(), sleep=lambda seconds: None,
                clock=lambda: 1.0)
    if "logger" not in overrides:
        args["logger"] = configure_logging("worker", stream=StringIO())
    args.update(overrides)
    return module.WorkerLoop(**args)


def test_empty_queue_waits_baseline_then_stops():
    stop, waits = Event(), []
    def sleep(seconds):
        waits.append(seconds)
        stop.set()
    loop(stop=stop, sleep=sleep).run()
    assert waits == [2]


def test_success_claims_next_without_sleep_and_signal_does_not_interrupt_handler():
    stop, calls = Event(), []
    def acquire():
        calls.append("claim")
        return claim(str(len(calls)))
    def dispatch(ctx):
        calls.append("handler")
        if calls.count("handler") == 2:
            stop.set()
        return import_module("daesingo.worker.registry").HandlerResult()
    def record(ctx, result):
        calls.append("terminal")
        return True
    loop(stop=stop, claim=acquire, dispatch=dispatch, record=record,
         sleep=lambda seconds: pytest.fail("successful execution must not sleep")).run()
    assert calls == ["claim", "handler", "terminal"] * 2


@pytest.mark.parametrize("error", [
    TimeoutError("secret"), OperationalError("private SQL", {}, Exception(2003, "secret")),
    TransactionRetryExhausted(3, outcome_unknown=True), ClaimLostError("secret"),
])
def test_claim_failure_waits_and_process_recovers(error):
    stop, calls, waits = Event(), [], []
    def acquire():
        calls.append("claim")
        if len(calls) == 1:
            raise error
        stop.set()
        return None
    loop(stop=stop, claim=acquire, sleep=waits.append).run()
    assert calls == ["claim", "claim"] and waits == [5]


def test_terminal_exhaustion_retries_same_result_without_reinvoking_handler_even_after_signal():
    stop, results, waits, dispatched = Event(), [], [], []
    def dispatch(ctx):
        dispatched.append(ctx)
        stop.set()
        return import_module("daesingo.worker.registry").HandlerResult()
    def record(ctx, result):
        results.append(result)
        if len(results) < 3:
            raise TransactionRetryExhausted(3, outcome_unknown=False)
        return True
    loop(stop=stop, claim=claim, dispatch=dispatch, record=record, sleep=waits.append).run()
    assert len(dispatched) == 1 and len(results) == 3
    assert results[0] is results[1] is results[2] and waits == [5, 5]


def test_outside_dispatch_exception_is_safe_runtime_failure_with_correlated_logs():
    stop, recorded, stream = Event(), [], StringIO()
    def dispatch(ctx):
        raise RuntimeError("/private/file password=secret provider/user payload")
    def record(ctx, result):
        recorded.append(result)
        stop.set()
        return True
    times = iter([1.0, 1.25])
    loop(stop=stop, claim=claim, dispatch=dispatch, record=record,
         logger=configure_logging("worker", stream=stream), clock=lambda: next(times)).run()
    assert recorded[0].failure_kind.startswith("RUNTIME_")
    rows = [json.loads(s) for s in stream.getvalue().splitlines()]
    assert [r["event"] for r in rows] == ["runtime.execution.started", "runtime.execution.completed"]
    assert rows[-1]["status"] == "FAILED" and rows[-1]["duration_ms"] == 250
    for row in rows:
        assert (row["trace_id"], row["case_id"], row["job_id"], row["execution_id"]) == ("trace", "case", "job", "exec_job")
    assert all(s not in stream.getvalue() for s in ("private", "secret", "payload", "claim_token"))


def test_rejected_finish_never_logs_successful_completion():
    stop, stream = Event(), StringIO()
    def record(ctx, result):
        stop.set()
        return False
    loop(stop=stop, claim=claim, record=record,
         logger=configure_logging("worker", stream=stream)).run()
    assert "runtime.execution.completed" not in stream.getvalue()
    assert "runtime.execution.finish_rejected" in stream.getvalue()


@pytest.mark.parametrize("unsafe", [False, True])
def test_storage_valid_correlation_cannot_break_dispatch_or_disclose_paths(unsafe):
    stop, stream, called = Event(), StringIO(), []
    raw = "/private/path-secret\nuser payload" if unsafe else "job_" + "a" * 187
    claimed = replace(claim(), job_id=raw)
    def record(ctx, result):
        called.append(ctx)
        stop.set()
        return True
    loop(stop=stop, claim=lambda: claimed, record=record,
         logger=configure_logging("worker", stream=stream)).run()
    assert called[0].job_id == raw
    rows = [json.loads(s) for s in stream.getvalue().splitlines()]
    assert len(rows) == 2 and rows[0]["job_id"] == rows[1]["job_id"]
    if unsafe:
        assert all(word not in stream.getvalue() for word in ("private", "secret", "payload"))
        assert rows[0]["job_id"].startswith("id_")
    else:
        assert rows[0]["job_id"] == raw


@pytest.mark.parametrize("sink", ["filter", "handler"])
@pytest.mark.parametrize("scenario", ["claim_lost", "finish_rejected"])
def test_other_loop_events_do_not_interrupt_recovery(sink, scenario, capsys):
    stop, calls, waits = Event(), [], []
    def acquire():
        calls.append("claim")
        if scenario == "claim_lost":
            if len(calls) == 1:
                raise ClaimLostError("secret /private/claim")
            stop.set()
            return None
        return claim()

    def record(ctx, result):
        calls.append("record")
        stop.set()
        return False

    worker = loop(stop=stop, claim=acquire, record=record, sleep=waits.append)
    seen, remove = install_logging_fault(worker.logger, sink,
                                         lambda name: name == "runtime.execution." + scenario)
    try:
        worker.run()
    finally:
        remove()
    assert seen == ["runtime.execution." + scenario]
    assert calls == (["claim", "claim"] if scenario == "claim_lost" else ["claim", "record"])
    assert waits == ([5] if scenario == "claim_lost" else [])
    assert capsys.readouterr().err == ""
