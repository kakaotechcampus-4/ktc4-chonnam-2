from contextlib import contextmanager
from dataclasses import replace
from importlib import import_module

import pytest
from sqlalchemy.exc import OperationalError

from daesingo import readout
from daesingo.common.jobs.execution import ExecutionContext, validated_terminal
from daesingo.common.jobs.cancel import CancellationRequested
from daesingo.common.usage.port import UsageError
from daesingo.common.db.errors import (BeforeCommitFailure, CommitOutcomeUnknown,
    TransactionBoundaryError, TransactionRetryExhausted)
from daesingo.readout.contracts import ReadoutRun, PlateReadout, OverlayTimeReadout
from tests.worker.readout_support import OfflineOcr, ObservedUsage

KINDS = ("PLATE_READ", "OVERLAY_TIME_READ")


def setup(kind="PLATE_READ", mode="success", *, cancel=None, error=None, usage_failure=None):
    m = import_module("daesingo.worker.readout_handlers")
    events = []
    sink = ObservedUsage(events, usage_failure)
    ctx = ExecutionContext("exec", "job", "case", kind, 1, "trace", usage_sink=sink)
    data = m.ReadoutInput("case", "candidate", "generation", "same-clip")
    def stage(name):
        events.append(name)
        if cancel == name: ctx.cancel_signal.request()
        if error and error[0] == name: raise error[1]
    def load(context): stage("load"); return data
    provider = OfflineOcr(mode, observe=lambda: stage("provider"))
    @contextmanager
    def factory(value):
        assert value == data
        stage("open")
        try: yield m.ReadoutSession(provider, 1.0)
        finally: stage("close")
    return m.readout_registry(load=load, provider_factory=factory), ctx, provider, sink, events


def test_unconfigured_provider_leaves_both_kinds_unregistered():
    m = import_module("daesingo.worker.readout_handlers")
    registry = m.readout_registry(load=lambda ctx: pytest.fail("input read"))
    for kind in KINDS:
        assert registry.dispatch(ExecutionContext("e", "j", "c", kind, 1, "t")).failure_kind == "RUNTIME_UNREGISTERED_KIND"


@pytest.mark.parametrize("kind,mode,status,reason", [
    ("PLATE_READ", "success", "OK", None), ("PLATE_READ", "abstain", "NEEDS_REVIEW", None),
    ("PLATE_READ", "failed", None, None), ("OVERLAY_TIME_READ", "success", "OK", None),
    ("OVERLAY_TIME_READ", "not_present", "NOT_APPLICABLE", "readout.overlay.not_present"),
    ("OVERLAY_TIME_READ", "undetermined", "UNKNOWN", "readout.overlay.presence_undetermined"),
    ("OVERLAY_TIME_READ", "ocr_failed", "UNKNOWN", "readout.overlay.ocr_failed"),
    ("OVERLAY_TIME_READ", "failed", None, None)])
def test_public_once_run_identity_outcome_payload_and_owner_usage(kind, mode, status, reason, monkeypatch):
    registry, ctx, provider, sink, events = setup(kind, mode)
    function = "read_plate" if kind == "PLATE_READ" else "read_overlay_time"
    actual, calls = getattr(readout, function), []
    def call(request, **kw):
        calls.append((request, kw))
        result = actual(request, **kw)
        # Deterministic timestamps prove Run timing is the latency source.
        result[0].started_at = "2026-10-28T01:00:00+00:00"
        result[0].ended_at = "2026-10-28T01:00:02+00:00"
        return result
    monkeypatch.setattr(readout, function, call)
    result = validated_terminal(registry.dispatch(ctx), execution_id=ctx.execution_id)
    assert len(calls) == 1 and provider.calls == [(kind, "same-clip")]
    assert events == ["load", "open", "begin", "provider", "finish", "close"]
    payload = result.objects[0].payload
    key = "plate_readout" if kind == "PLATE_READ" else "overlay_time_readout"
    assert set(payload) == {"readout_run", key}
    run = ReadoutRun.from_dict(payload["readout_run"])
    assert run.run_id.startswith("rr_") and run.run_id != ctx.execution_id
    assert result.produced[0].kind == "readout_run" and result.produced[0].ref == run.run_id
    assert calls[0][1]["run_id"] == run.run_id == sink.begins[0]["run_ref"]["ref"]
    assert sink.begins[0] == dict(operation="READOUT_PLATE" if kind == "PLATE_READ" else "READOUT_OVERLAY_TIME",
        provider_label="ocr-local", pricing_context={"pricing_id": "local-2026-09", "unit": "per_second"},
        run_ref={"kind": "readout_run", "ref": run.run_id})
    assert run.usage_refs == []
    failed = mode == "failed"
    assert result.status == ("FAILED" if failed else "SUCCEEDED")
    assert result.failure_kind == ("READOUT_INFRA" if failed else None)
    assert sink.finishes == [("usage-test", dict(token_usage=None, processed_duration_sec=1.0, latency_ms=2000,
        pricing_context={"pricing_id": "local-2026-09", "unit": "per_second"}, cost={"amount": "0", "currency": "KRW"},
        outcome="FAILED" if failed else "SUCCEEDED", failure_kind="READOUT_INFRA" if failed else None))]
    if failed:
        assert payload[key] is None and run.failure.code == "READOUT_PROVIDER_TIMEOUT"
    else:
        typed = (PlateReadout if kind == "PLATE_READ" else OverlayTimeReadout).from_dict(payload[key])
        assert typed.to_dict() == payload[key] and typed.run_ref.ref == run.run_id
        assert typed.observation.status == status
        if reason: assert typed.observation.reason.code == reason
        if mode == "abstain": assert typed.abstained


@pytest.mark.parametrize("kind", KINDS)
def test_each_new_execution_gets_a_fresh_run(kind):
    registry, ctx, provider, sink, events = setup(kind)
    one = registry.dispatch(ctx)
    two = registry.dispatch(replace(ctx, execution_id="exec-2", attempt=2))
    assert one.objects[0].ref != two.objects[0].ref
    assert len(provider.calls) == len(sink.finishes) == 2


@pytest.mark.parametrize("kind", KINDS)
def test_partial_preserved_and_usage_success(kind, monkeypatch):
    registry, ctx, provider, sink, events = setup(kind)
    function = "read_plate" if kind == "PLATE_READ" else "read_overlay_time"
    actual = getattr(readout, function)
    def partial(*args, **kw):
        from daesingo.readout.contracts import Failure
        run, result = actual(*args, **kw)
        run.outcome, run.failure = "PARTIAL", Failure("INFRA", "READOUT_FRAME_ACCESS_FAILED")
        return run, result
    monkeypatch.setattr(readout, function, partial)
    result = registry.dispatch(ctx)
    assert result.status == "SUCCEEDED" and result.objects[0].payload["readout_run"]["outcome"] == "PARTIAL"
    assert sink.finishes[0][1]["outcome"] == "SUCCEEDED" and sink.finishes[0][1]["failure_kind"] is None


@pytest.mark.parametrize("stage", ["before", "load", "open", "provider", "close"])
def test_cancel_checkpoint_and_close(stage):
    registry, ctx, provider, sink, events = setup(cancel=stage)
    if stage == "before": ctx.cancel_signal.request()
    with pytest.raises(CancellationRequested): registry.dispatch(ctx)
    assert len(provider.calls) == (1 if stage in {"provider", "close"} else 0)
    if "open" in events: assert events[-1] == "close"
    # Observations survive cancellation after the call, before the checkpoint.
    if stage in {"provider", "close"}: assert len(sink.finishes) == 1


@pytest.mark.parametrize("stage", ["begin", "finish"])
def test_usage_errors_propagate_without_readout_retry(stage):
    registry, ctx, provider, sink, events = setup(usage_failure=stage)
    with pytest.raises(UsageError): registry.dispatch(ctx)
    assert len(provider.calls) == (stage == "finish") and events[-1] == "close"


@pytest.mark.parametrize("stage", ["load", "open", "close"])
def test_runtime_errors_outside_capability_are_not_readout_failure(stage):
    registry, ctx, provider, sink, events = setup(error=(stage, OperationalError("private", {}, Exception("db"))))
    assert registry.dispatch(ctx).failure_kind == "RUNTIME_HANDLER_ERROR"


@pytest.mark.parametrize("kind", KINDS)
def test_public_value_error_keeps_runtime_boundary(kind, monkeypatch):
    registry, ctx, provider, sink, events = setup(kind)
    def invalid(*args, **kw): raise ValueError("private input")
    monkeypatch.setattr(readout, "read_plate" if kind == "PLATE_READ" else "read_overlay_time", invalid)
    assert registry.dispatch(ctx).failure_kind == "RUNTIME_HANDLER_ERROR"
    assert not provider.calls and not sink.finishes and events[-1] == "close"


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("error", [OperationalError("private", {}, Exception("db")),
    BeforeCommitFailure("private"), CommitOutcomeUnknown(), TransactionBoundaryError(),
    TransactionRetryExhausted(3, outcome_unknown=True)])
def test_public_runtime_errors_are_never_converted_to_readout_failure(kind, error, monkeypatch):
    registry, ctx, provider, sink, events = setup(kind)
    def broken(*args, **kw): raise error
    monkeypatch.setattr(readout, "read_plate" if kind == "PLATE_READ" else "read_overlay_time", broken)
    result = registry.dispatch(ctx)
    assert result.failure_kind == "RUNTIME_HANDLER_ERROR" and not result.objects
    assert not provider.calls and not sink.finishes and events[-1] == "close"


@pytest.mark.parametrize("where", ["checkpoint", "object"])
def test_checkpoint_and_payload_errors_do_not_become_readout_failures(where, monkeypatch):
    registry, ctx, provider, sink, events = setup()
    if where == "checkpoint":
        original = ExecutionContext.checkpoint
        def checkpoint(context):
            original(context)
            if sink.finishes: raise TransactionBoundaryError()
        monkeypatch.setattr(ExecutionContext, "checkpoint", checkpoint)
    else:
        def invalid_object(**kw): raise ValueError("private payload error")
        monkeypatch.setattr("daesingo.worker.readout_handlers.ProducedObject", invalid_object)
    result = registry.dispatch(ctx)
    assert result.failure_kind == "RUNTIME_HANDLER_ERROR" and not result.objects
    assert len(provider.calls) == len(sink.finishes) == 1 and events[-1] == "close"


def test_unobserved_end_time_remains_null(monkeypatch):
    registry, ctx, provider, sink, events = setup()
    actual = readout.read_plate
    def open_run(*args, **kw):
        run, result = actual(*args, **kw)
        run.ended_at = None
        return run, result
    monkeypatch.setattr(readout, "read_plate", open_run)
    # The composition test already exercises a session with unknown duration;
    # here the Run itself supplies no observed end, never a synthetic zero.
    assert registry.dispatch(ctx).status == "SUCCEEDED"
    assert sink.finishes[0][1]["latency_ms"] is None
