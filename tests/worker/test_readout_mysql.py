"""Real MySQL T1/usage interruptions with real public Readout and offline OCR."""
from contextlib import contextmanager
from dataclasses import replace

import pytest
import sqlalchemy as sa

from daesingo.common.config import DbSettings
from daesingo.common.db import create_worker_engine
from daesingo.common.db.transactions import run_worker_transaction
from daesingo.common.jobs.execution import ExecutionContext
from daesingo.common.jobs.produced import ProducedReader, ProducedConflict, produced_objects
from daesingo.common.jobs.repository import claim_one
from daesingo.common.jobs.schema import job_execution
from daesingo.common.usage.sink import DurableUsageSink
from daesingo.common.usage.schema import usage_record, usage_inflight
from daesingo.common.usage.reconciliation import reconcile_once
from daesingo.common.usage.port import UsagePersistenceError
from daesingo.worker.readout_handlers import ReadoutInput, ReadoutSession, readout_registry
from tests.worker.readout_support import OfflineOcr
from mysql_fault_proxy import CommitResponseProxy
from test_worker_mysql import queue, seed, row, composed  # noqa: F401

pytestmark = pytest.mark.mysql
KINDS = ("PLATE_READ", "OVERLAY_TIME_READ")


def invocation(engine, kind, *, mode="success", sink_failure=None):
    claimed = claim_one(engine, "worker")
    assert claimed.kind == kind
    sink = DurableUsageSink(execution_ref=claimed.execution_id, case_id=claimed.case_id,
        transaction=lambda callback: run_worker_transaction(engine, callback, sleep=lambda _: None))
    provider = OfflineOcr(mode, observe=lambda: (_ for _ in ()).throw(AssertionError("connection held"))
                          if engine.pool.checkedout() else None)
    if sink_failure:
        method = getattr(sink, sink_failure)
        def fail(*args, **kw):
            method(*args, **kw)
            raise UsagePersistenceError()
        setattr(sink, sink_failure, fail)
    context = ExecutionContext(claimed.execution_id, claimed.job_id, claimed.case_id, kind,
        claimed.attempt, claimed.trace_id, usage_sink=sink)
    @contextmanager
    def factory(data): yield ReadoutSession(provider, .7)
    registry = readout_registry(load=lambda ctx: ReadoutInput(ctx.case_id, "candidate", "generation", "clip"),
        provider_factory=factory)
    return registry, context, provider


def ledger(engine):
    with engine.connect() as conn:
        return (list(conn.execute(sa.select(usage_inflight)).mappings()),
                list(conn.execute(sa.select(usage_record)).mappings()))


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("mode", ["success", "failed"])
@pytest.mark.mysql_check("readout", "durable_receipt")
def test_durable_failed_and_successful_run_receipt_and_usage_replay(queue, kind, mode):
    execution, = seed(queue, (kind,))
    registry, context, provider = invocation(queue, kind, mode=mode)
    terminal = registry.dispatch(context)
    worker = composed(queue, {})
    assert worker.record(context, terminal)
    before = row(queue, execution)
    assert worker.record(context, terminal)  # T1 receipt replay, no invocation.
    reconcile_once(queue); reconcile_once(queue)
    assert len(provider.calls) == 1
    assert row(queue, execution) == before
    tracks, finals = ledger(queue)
    assert len(tracks) == len(finals) == 1
    run = terminal.objects[0].payload["readout_run"]
    assert finals[0]["run_ref"] == run["run_id"] and finals[0]["run_ref_reason"] is None
    assert finals[0]["occurred_at"] == tracks[0]["occurred_at"]
    assert finals[0]["latency_ms"] >= 0 and finals[0]["processed_duration_sec"] == .7
    assert tracks[0]["outcome"] == ("FAILED" if mode == "failed" else "SUCCEEDED")
    assert tracks[0]["failure_kind"] == ("READOUT_INFRA" if mode == "failed" else None)
    with queue.connect() as conn:
        payload = ProducedReader()(conn, kind, tuple(before["produced"]))
    assert payload == terminal.objects[0].payload
    # A conflicting receipt fails closed without changing the durable Run.
    changed = terminal.model_copy(update={"objects": (terminal.objects[0].model_copy(update={"payload": {"wrong": True}}),)})
    with pytest.raises(ProducedConflict): worker.record(context, changed)
    assert ledger(queue) == (tracks, finals) and len(provider.calls) == 1
    assert queue.pool.checkedout() == 0


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("fault", ["rollback", "commit_unknown", "reconcile"])
@pytest.mark.mysql_check("readout", "t1_replay")
def test_t1_deadlock_lost_commit_and_reconcile_failure_never_reinvoke(queue, kind, fault, monkeypatch):
    execution, = seed(queue, (kind,))
    with CommitResponseProxy(queue.url.host, queue.url.port) as proxy:
        extra = None
        active = queue
        if fault == "commit_unknown":
            active = extra = create_worker_engine(DbSettings(url=queue.url.set(host="127.0.0.1", port=proxy.port)
                .update_query_dict({"ssl_disabled": "true"}).render_as_string(hide_password=False)))
        registry, context, provider = invocation(active, kind)
        result = registry.dispatch(context)
        injected = []
        def after(conn, cursor, sql, *args):
            if not injected and sql.upper().startswith("INSERT INTO PRODUCED_OBJECTS"):
                injected.append(True)
                if fault == "rollback": raise sa.exc.OperationalError("probe", {}, Exception(1213, "deadlock"))
                if fault == "commit_unknown": proxy.arm()
        sa.event.listen(active, "after_cursor_execute", after)
        original = __import__("daesingo.worker.composition", fromlist=["reconcile_once"]).reconcile_once
        if fault == "reconcile":
            monkeypatch.setattr("daesingo.worker.composition.reconcile_once", lambda *a, **k: (_ for _ in ()).throw(UsagePersistenceError()))
        try:
            worker = composed(active, {})
            assert worker.record(context, result)
            assert injected and len(provider.calls) == 1
            assert proxy.commit_ok_dropped == (1 if fault == "commit_unknown" else 0)
            assert row(active, execution)["status"] == "SUCCEEDED"
            if fault == "reconcile": assert not ledger(active)[1]
            original(active); original(active)
            assert len(ledger(active)[1]) == 1 and len(provider.calls) == 1
            assert active.pool.checkedout() == 0
        finally:
            sa.event.remove(active, "after_cursor_execute", after)
            if extra is not None: extra.dispose()


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("stage", ["begin", "finish", "before_t1", "t1_rollback"])
@pytest.mark.mysql_check("readout", "pre_t1_interruption")
def test_pre_t1_interruption_preserves_observation_and_run_not_produced(queue, kind, stage):
    execution, = seed(queue, (kind,))
    registry, context, provider = invocation(queue, kind, sink_failure=stage if stage in {"begin", "finish"} else None)
    if stage in {"begin", "finish"}:
        with pytest.raises(UsagePersistenceError): registry.dispatch(context)
    else:
        terminal = registry.dispatch(context)
        if stage == "t1_rollback":
            def fail(conn, cursor, sql, *args):
                if sql.upper().startswith("INSERT INTO PRODUCED_OBJECTS"): raise RuntimeError("T1 interrupted")
            sa.event.listen(queue, "after_cursor_execute", fail)
            try:
                with pytest.raises(RuntimeError): composed(queue, {}).record(context, terminal)
            finally: sa.event.remove(queue, "after_cursor_execute", fail)
    assert len(provider.calls) == (0 if stage == "begin" else 1)
    with queue.begin() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(produced_objects)) == 0
        if stage == "t1_rollback":
            conn.execute(job_execution.update().where(job_execution.c.execution_id == execution)
                .values(lease_expires_at=sa.text("NOW(6) - INTERVAL 1 SECOND")))
        else:
            conn.execute(job_execution.update().where(job_execution.c.execution_id == execution).values(status="STALE"))
    if stage == "t1_rollback":
        from daesingo.common.jobs.sweep import sweep_once
        assert len(sweep_once(queue, composed(queue, {}).settings, sleep=lambda _: None)) == 1
    reconcile_once(queue); reconcile_once(queue)
    tracks, finals = ledger(queue)
    assert len(finals) == 1 and finals[0]["run_ref"] is None and finals[0]["run_ref_reason"] == "RUN_NOT_PRODUCED"
    assert (finals[0]["processed_duration_sec"] is None) == (stage == "begin")
    assert tracks[0]["planned_run_ref"].startswith("rr_")
    assert len(provider.calls) == (0 if stage == "begin" else 1)
    if stage == "t1_rollback":
        # A new execution invokes again and gets a fresh Run; usage recovery above does not.
        with queue.begin() as conn:
            conn.execute(job_execution.update().where(job_execution.c.status == "QUEUED").values(available_at=sa.func.now(6)))
        again, next_context, next_provider = invocation(queue, kind)
        next_result = again.dispatch(next_context)
        assert next_context.attempt == 2 and next_result.objects[0].ref != tracks[0]["planned_run_ref"]
        assert composed(queue, {}).record(next_context, next_result)
        assert len(next_provider.calls) == 1 and len(ledger(queue)[1]) == 2
    assert queue.pool.checkedout() == 0
