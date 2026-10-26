"""Runtime consumes an Owner policy; it must never classify its own failures."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from daesingo import search
from daesingo.common.db.errors import (BeforeCommitFailure, CommitOutcomeUnknown,
    TransactionBoundaryError, TransactionRetryExhausted)
from daesingo.common.jobs.cancel import CancellationRequested
from daesingo.common.jobs.execution import HandlerResult, validated_terminal
from daesingo.common.usage.port import UsagePersistenceError
from daesingo.search.intent import IntentFailureKind, IntentHintResult, IntentHintStatus
from daesingo.search.runs import Issue, RunOutcome
from daesingo.worker.search_handlers import SearchInput, search_registry
from test_search_handlers import context, fixtures


class Policy:
    def __init__(self, kind=None):
        self.kind, self.seen = kind, []

    def failure_kind_for_run(self, run):
        self.seen.append(("run", run))
        return self.kind

    def failure_kind_for_intent(self, result):
        self.seen.append(("intent", result))
        return self.kind

    def failure_kind_for_error(self, error):
        self.seen.append(("error", error))
        return self.kind


def compose(ctx, policy, *, result=None, error=None, load_error=None, cancel_after=False,
            resource_error=None, resolve_error=None):
    scope, coarse, fine = fixtures()
    resources = []
    # Fine reads the Case-fixed bound from its input (#407 decision (a)).
    data = SearchInput(description="text", scope=scope, candidate=coarse.candidates[0], max_latency_sec=70)

    def load(_):
        if load_error: raise load_error
        return data

    def capability(*args, **kwargs):
        assert kwargs["usage_sink"] is ctx.usage_sink
        resources.append("called")
        if cancel_after: ctx.cancel_signal.request()
        if error: raise error
        return result or (coarse if ctx.kind == "COARSE_SEARCH" else fine)

    def resolve(_):
        if resolve_error: raise resolve_error
        return (SimpleNamespace(source_ref=fine.analysis_run.input_ref),)

    @contextmanager
    def service(_):
        if resource_error == "enter": raise ValueError("resource enter")
        try:
            yield SimpleNamespace(search_candidates=capability, verify_visual=capability,
                                  resolver=SimpleNamespace(resolve=resolve))
        finally:
            resources.append("closed")
            if resource_error == "exit": raise ValueError("resource exit")

    return search_registry(load=load, intent_factory=lambda: SimpleNamespace(extract=capability),
        service_factory=service, failures=policy), resources


@pytest.mark.parametrize("kind", ["COARSE_SEARCH", "FINE_VERIFY"])
@pytest.mark.parametrize("issue_codes", [[], ["OWNER_CODE"], ["FIRST", "SECOND"]])
def test_failed_run_projects_owner_helper_and_preserves_actual_run_receipt(kind, issue_codes):
    _, coarse, fine = fixtures()
    original = coarse if kind == "COARSE_SEARCH" else fine
    run = original.analysis_run.model_copy(update={"outcome": RunOutcome.FAILED,
        "issues": tuple(Issue(kind="INFRA", code=code) for code in issue_codes)})
    changes = {"analysis_run": run, "candidates": ()} if kind == "COARSE_SEARCH" else {"analysis_run": run}
    result = original.model_copy(update=changes)
    policy = Policy("SEARCH_UNCLASSIFIED")  # Owner-returned sentinel, no local code mapping
    ctx = context(kind, object())
    registry, resources = compose(ctx, policy, result=result)
    terminal = validated_terminal(registry.dispatch(ctx), execution_id=ctx.execution_id)
    assert terminal.status == "FAILED" and terminal.failure_kind == "SEARCH_UNCLASSIFIED"
    assert policy.seen == [("run", run)]
    assert [(r.kind, r.ref) for r in terminal.produced] == [("analysis_run", run.run_id)]
    assert terminal.objects[0].payload["analysis_run"]["outcome"] == "FAILED"
    assert resources == ["called", "closed"]


def test_partial_coarse_is_success_with_candidates_and_owner_issue_payload():
    _, coarse, _ = fixtures()
    run = coarse.analysis_run.model_copy(update={"outcome": RunOutcome.PARTIAL,
        "issues": (Issue(kind="INFRA", code="COARSE_SPAN_OUT_OF_SOURCE"),)})
    policy = Policy()
    ctx = context("COARSE_SEARCH", object())
    registry, _ = compose(ctx, policy,
                          result=coarse.model_copy(update={"analysis_run": run}))
    result = registry.dispatch(ctx)
    assert result.status == "SUCCEEDED" and result.failure_kind is None
    assert result.objects[0].payload["candidate_events"]
    assert policy.seen == [("run", run)]


@pytest.mark.parametrize("status,raw,mapped", [
    (IntentHintStatus.OK, None, None), (IntentHintStatus.ABSTAINED, None, None),
    (IntentHintStatus.FAILED, IntentFailureKind.PROVIDER_ERROR, "SEARCH_PROVIDER_ERROR"),
    (IntentHintStatus.FAILED, IntentFailureKind.RESPONSE_INVALID, "SEARCH_RESPONSE_INVALID"),
    (IntentHintStatus.FAILED, None, "SEARCH_UNCLASSIFIED"),
])
def test_intent_projects_returned_owner_classification_without_interpreting_raw_error(status, raw, mapped):
    policy = Policy(mapped)
    extraction = IntentHintResult(status=status, failure_kind=raw)
    ctx = context(sink=object())
    registry, _ = compose(ctx, policy, result=extraction)
    result = registry.dispatch(ctx)
    assert result.status == ("SUCCEEDED" if mapped is None else "FAILED")
    assert result.failure_kind == mapped and policy.seen == [("intent", extraction)]
    assert result.objects[0].payload["status"] == status
    assert result.produced == ()


@pytest.mark.parametrize("kind", ["HINT_EXTRACT", "COARSE_SEARCH", "FINE_VERIFY"])
def test_only_capability_exception_uses_owner_error_helper(kind):
    error = ValueError("private provider detail")
    policy = Policy("SEARCH_RESPONSE_INVALID")
    ctx = context(kind, object())
    registry, resources = compose(ctx, policy, error=error)
    result = registry.dispatch(ctx)
    assert result == HandlerResult(status="FAILED", failure_kind="SEARCH_RESPONSE_INVALID")
    assert policy.seen == [("error", error)] and resources.count("called") == 1
    if kind != "HINT_EXTRACT": assert resources[-1] == "closed"
    assert "private" not in result.model_dump_json()


@pytest.mark.parametrize("error", [ValueError("input"),
    sa.exc.OperationalError("read", {}, Exception("persistence"))])
def test_input_lookup_and_transaction_failure_never_enter_search_error_helper(error):
    policy = Policy("SEARCH_UNCLASSIFIED")
    ctx = context("COARSE_SEARCH", object())
    registry, resources = compose(ctx, policy, load_error=error)
    assert registry.dispatch(ctx).failure_kind == "RUNTIME_HANDLER_ERROR"
    assert not policy.seen and not resources


@pytest.mark.parametrize("kind", ["HINT_EXTRACT", "COARSE_SEARCH", "FINE_VERIFY"])
def test_checkpoint_and_usage_errors_never_become_search_failures(kind):
    for usage_error in (False, True):
        policy = Policy("SEARCH_UNCLASSIFIED")
        ctx = context(kind, object())
        error = UsagePersistenceError() if usage_error else None
        registry, resources = compose(ctx, policy, error=error, cancel_after=not usage_error)
        with pytest.raises(UsagePersistenceError if usage_error else CancellationRequested):
            registry.dispatch(ctx)
        assert not policy.seen
        if kind != "HINT_EXTRACT": assert resources[-1] == "closed"


@pytest.mark.parametrize("phase", ["enter", "exit"])
def test_resource_factory_errors_are_runtime_failures(phase):
    policy = Policy()
    ctx = context("COARSE_SEARCH", object())
    registry, _ = compose(ctx, policy, resource_error=phase)
    assert registry.dispatch(ctx).failure_kind == "RUNTIME_HANDLER_ERROR"
    assert all(tag != "error" for tag, _ in policy.seen)


def test_missing_public_helpers_leave_kinds_unregistered_without_loading_or_provider(monkeypatch):
    for name in ("failure_kind_for_run", "failure_kind_for_intent", "failure_kind_for_error"):
        monkeypatch.delattr(search, name, raising=False)
    def forbidden(*args): raise AssertionError("missing dependency invoked")
    registry = search_registry(load=forbidden, intent_factory=forbidden, service_factory=forbidden)
    for kind in ("HINT_EXTRACT", "COARSE_SEARCH", "FINE_VERIFY"):
        assert registry.dispatch(context(kind, object())).failure_kind == "RUNTIME_UNREGISTERED_KIND"


@pytest.mark.parametrize("error", [
    sa.exc.OperationalError("read", {}, Exception("db failure")),
    BeforeCommitFailure("disconnect"), CommitOutcomeUnknown(),
    TransactionBoundaryError("caller transaction"),
    TransactionRetryExhausted(3, outcome_unknown=False),
    TransactionRetryExhausted(3, outcome_unknown=True),
])
@pytest.mark.parametrize("path", ["HINT_EXTRACT", "COARSE_SEARCH", "FINE_VERIFY", "resolver"])
def test_persistence_error_propagating_through_search_is_still_runtime_owned(error, path):
    policy = Policy("SEARCH_UNCLASSIFIED")
    ctx = context("FINE_VERIFY" if path == "resolver" else path, object())
    registry, resources = compose(ctx, policy,
        **({"resolve_error": error} if path == "resolver" else {"error": error}))
    assert registry.dispatch(ctx).failure_kind == "RUNTIME_HANDLER_ERROR"
    assert policy.seen == []
    if path != "HINT_EXTRACT": assert resources[-1] == "closed"


def test_actual_worker_retry_exhaustion_inside_capability_bypasses_search_helper():
    from daesingo.common.db import transactions
    attempts = []

    class DisconnectedEngine:
        def connect(self):
            attempts.append("connect")
            raise sa.exc.OperationalError("connect", {}, Exception("disconnect"), connection_invalidated=True)

    policy = Policy("SEARCH_UNCLASSIFIED")
    def capability(*args, **kwargs):
        return transactions.run_worker_transaction(DisconnectedEngine(), lambda _: None, sleep=lambda _: None)

    registry = search_registry(load=lambda _: SearchInput(description="text"),
        intent_factory=lambda: SimpleNamespace(extract=capability), failures=policy)
    assert registry.dispatch(context(sink=object())).failure_kind == "RUNTIME_HANDLER_ERROR"
    assert len(attempts) == 3 and policy.seen == []


def test_default_registry_discovers_installed_public_helpers_without_override(monkeypatch):
    policy = Policy("SEARCH_RESPONSE_INVALID")
    for name in ("failure_kind_for_run", "failure_kind_for_intent", "failure_kind_for_error"):
        monkeypatch.setattr(search, name, getattr(policy, name), raising=False)
    error = ValueError("module response")
    def extract(*args, **kwargs): raise error
    registry = search_registry(load=lambda _: SearchInput(description="text"),
        intent_factory=lambda: SimpleNamespace(extract=extract))
    result = registry.dispatch(context(sink=object()))
    assert result.failure_kind == "SEARCH_RESPONSE_INVALID" and policy.seen == [("error", error)]
