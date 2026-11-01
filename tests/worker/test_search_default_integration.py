"""Merged Search helpers through the default registry, without a policy override."""
import pytest
import sqlalchemy as sa

from daesingo import search
from daesingo.common.db.errors import TransactionRetryExhausted
from daesingo.common.jobs.cancel import CancellationRequested
from daesingo.search import failure_kind_for_error, failure_kind_for_intent, failure_kind_for_run
from daesingo.search.intent import IntentFailureKind, IntentHintResult, IntentHintStatus
from daesingo.search.runs import Issue, RunOutcome
from daesingo.search.smoke_errors import SmokeProviderError
from test_search_failure_boundary import compose
from test_search_handlers import context, fixtures


@pytest.mark.parametrize("kind", ["HINT_EXTRACT", "COARSE_SEARCH", "FINE_VERIFY"])
def test_installed_helpers_classify_each_default_registered_kind(kind):
    _, coarse, _ = fixtures()
    if kind == "HINT_EXTRACT":
        result = IntentHintResult(status=IntentHintStatus.FAILED, failure_kind=IntentFailureKind.CONFIG_ERROR)
        assert failure_kind_for_intent(result) == "SEARCH_PROVIDER_CONFIG"
        options, expected = {"result": result}, "SEARCH_PROVIDER_CONFIG"
    elif kind == "COARSE_SEARCH":
        run = coarse.analysis_run.model_copy(update={"outcome": RunOutcome.FAILED,
            "issues": (Issue(kind="INFRA", code="PROVIDER_CALL_FAILED"),)})
        assert failure_kind_for_run(run) == "SEARCH_PROVIDER_ERROR"
        options, expected = {"result": coarse.model_copy(update={"analysis_run": run, "candidates": ()})}, "SEARCH_PROVIDER_ERROR"
    else:
        error = SmokeProviderError("offline provider")
        assert failure_kind_for_error(error) == "SEARCH_PROVIDER_ERROR"
        options, expected = {"error": error}, "SEARCH_PROVIDER_ERROR"
    ctx = context(kind, object())
    registry, resources = compose(ctx, None, **options)
    terminal = registry.dispatch(ctx)
    assert terminal.status == "FAILED" and terminal.failure_kind == expected
    if kind != "HINT_EXTRACT": assert resources[-1] == "closed"


@pytest.mark.parametrize("kind", ["HINT_EXTRACT", "COARSE_SEARCH", "FINE_VERIFY"])
@pytest.mark.parametrize("fault", ["input", "transaction", "persistence", "checkpoint"])
def test_default_owner_helper_never_absorbs_runtime_faults(monkeypatch, kind, fault):
    seen = []
    real = search.failure_kind_for_error
    def observe(error):
        seen.append(error)
        return real(error)
    monkeypatch.setattr(search, "failure_kind_for_error", observe)
    options = {
        "input": {"load_error": ValueError("Runtime input")},
        "transaction": {"error": TransactionRetryExhausted(3, outcome_unknown=True)},
        "persistence": {"error": sa.exc.OperationalError("read", {}, Exception("Runtime persistence"))},
        "checkpoint": {"cancel_after": True},
    }[fault]
    ctx = context(kind, object())
    registry, resources = compose(ctx, None, **options)
    if fault == "checkpoint":
        with pytest.raises(CancellationRequested): registry.dispatch(ctx)
    else:
        assert registry.dispatch(ctx).failure_kind == "RUNTIME_HANDLER_ERROR"
    assert seen == []
    if kind != "HINT_EXTRACT" and fault != "input": assert resources[-1] == "closed"
