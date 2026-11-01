"""Search 실패 → JobExecution.failure_kind (#297). 값 원문은 search/decisions/failure-taxonomy.md."""

from datetime import UTC, datetime

import pytest

from daesingo.common.usage.port import UsagePersistenceError
from daesingo.search import (
    IntentFailureKind,
    IntentHintResult,
    IntentHintStatus,
    SearchFailureKind,
    failure_kind_for_error,
    failure_kind_for_intent,
    failure_kind_for_run,
)
from daesingo.search.errors import (
    GeminiBaseUrlRejectionReason,
    UnsafeGeminiBaseUrlError,
)
from daesingo.search.execution import DeadlineExceededError
from daesingo.search.failure_kind import ISSUE_CODE_KIND, provider_issue_code
from daesingo.search.media import FfmpegError
from daesingo.search.provider import RequestSizeError
from daesingo.search.runs import (
    AnalysisRun,
    ContractRef,
    FailureKind,
    Implementation,
    Issue,
    Operation,
    RunId,
    RunOutcome,
    UsageSummary,
)
from daesingo.search.smoke_errors import ProviderApiError, ProviderPayloadError

K = SearchFailureKind


class _StatusError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(str(status_code))
        self.status_code = status_code


def _wrapped(error: Exception, status: int | None) -> Exception:
    """provider는 SDK 예외를 cause로 두고 Provider*Error로 감싼다."""
    if status is not None:
        error.__cause__ = _StatusError(status)
    return error


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (_wrapped(ProviderApiError("x"), 401), K.PROVIDER_CONFIG),
        (_wrapped(ProviderApiError("x"), 404), K.PROVIDER_CONFIG),
        (
            UnsafeGeminiBaseUrlError(GeminiBaseUrlRejectionReason.QUERY),
            K.PROVIDER_CONFIG,
        ),
        (_wrapped(ProviderApiError("x"), 429), K.PROVIDER_ERROR),
        (_wrapped(ProviderApiError("x"), 503), K.PROVIDER_ERROR),
        (_wrapped(ProviderPayloadError("rejected"), 400), K.PROVIDER_ERROR),
        (ProviderPayloadError("no parsed content"), K.RESPONSE_INVALID),
        (DeadlineExceededError(), K.DEADLINE_EXCEEDED),
        (FfmpegError("x"), K.MEDIA_PREPARATION_FAILED),
        (RequestSizeError("x"), K.MEDIA_PREPARATION_FAILED),
        (RuntimeError("bug"), K.UNCLASSIFIED),
    ],
)
def test_error_maps_to_search_failure_kind(
    error: Exception, expected: SearchFailureKind
) -> None:
    assert failure_kind_for_error(error) is expected


def test_usage_error_is_not_a_search_failure() -> None:
    assert failure_kind_for_error(UsagePersistenceError()) is None


def test_every_value_has_search_prefix() -> None:
    assert all(kind.value.startswith("SEARCH_") for kind in SearchFailureKind)


def test_provider_issue_code_round_trips_through_issue_table() -> None:
    for error in (
        _wrapped(ProviderApiError("x"), 401),
        ProviderPayloadError("bad json"),
        _wrapped(ProviderApiError("x"), 429),
        RequestSizeError("x"),
    ):
        assert ISSUE_CODE_KIND[provider_issue_code(error)] is failure_kind_for_error(
            error
        )


def _run(outcome: RunOutcome, *codes: str) -> AnalysisRun:
    now = datetime(2026, 10, 25, tzinfo=UTC)
    return AnalysisRun(
        run_id=RunId("run-1"),
        operation=Operation.CANDIDATE_SEARCH,
        input_ref=ContractRef(kind="ANALYSIS_SCOPE", ref="scope-1"),
        implementation=Implementation(
            impl_id="i", model_ref="m", prompt_version="p", config_version="c"
        ),
        outcome=outcome,
        started_at=now,
        completed_at=now,
        issues=tuple(Issue(kind=FailureKind.INFRA, code=code) for code in codes),
        usage_refs=(),
        usage_summary=UsageSummary(
            processed_duration_ms=None,
            token_usage=None,
            latency_ms=None,
            total_cost=None,
        ),
        contract_version="analysis-run-candidate-event/v1.1",
    )


def test_failed_run_uses_first_issue() -> None:
    run = _run(RunOutcome.FAILED, "RUN_DEADLINE_EXCEEDED", "PROVIDER_CALL_FAILED")
    assert failure_kind_for_run(run) is K.DEADLINE_EXCEEDED


def test_failed_run_without_known_issue_is_unclassified() -> None:
    assert failure_kind_for_run(_run(RunOutcome.FAILED)) is K.UNCLASSIFIED
    assert failure_kind_for_run(_run(RunOutcome.FAILED, "NEW_CODE")) is K.UNCLASSIFIED


def test_partial_and_succeeded_runs_are_not_failures() -> None:
    assert failure_kind_for_run(_run(RunOutcome.SUCCEEDED)) is None
    partial = _run(RunOutcome.PARTIAL, "COARSE_SPAN_OUT_OF_SOURCE")
    assert failure_kind_for_run(partial) is None


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (IntentFailureKind.CONFIG_ERROR, K.PROVIDER_CONFIG),
        (IntentFailureKind.PROVIDER_ERROR, K.PROVIDER_ERROR),
        (IntentFailureKind.DEADLINE_EXCEEDED, K.DEADLINE_EXCEEDED),
        (IntentFailureKind.RESPONSE_INVALID, K.RESPONSE_INVALID),
        (None, K.UNCLASSIFIED),
    ],
)
def test_failed_intent_maps_by_failure_kind(
    kind: IntentFailureKind | None, expected: SearchFailureKind
) -> None:
    result = IntentHintResult(IntentHintStatus.FAILED, failure_kind=kind)
    assert failure_kind_for_intent(result) is expected


def test_ok_and_abstained_intent_are_not_failures() -> None:
    assert failure_kind_for_intent(IntentHintResult(IntentHintStatus.OK)) is None
    assert failure_kind_for_intent(IntentHintResult(IntentHintStatus.ABSTAINED)) is None
