"""AnalysisRun이 `analysis-run-candidate-event/v1.1` 계약대로 기록되는지 확인한다.

계약 §4 `input_ref`는 `CANDIDATE_SEARCH`에서 `kind=ANALYSIS_SCOPE`를 쓴다.
자산 계층 ref(`analysis_source`)의 소문자 규칙과 다른 값 공간이다.
"""

from daesingo.search.config import GeminiSearchConfig
from daesingo.search.execution import RunDeadline
from daesingo.search.provider import CoarseRequest, FineRequest, ProviderResult
from daesingo.search.runs import ContractRef, FailureKind, RunOutcome
from daesingo.search.schemas import CoarseResponse, FineResponse
from daesingo.search.scope import (
    AnalysisScope,
    SearchBudget,
    SearchHint,
    TimelineRef,
    TimelineRelativeTimeRange,
    TimeRangeKind,
    VisualEventType,
)
from daesingo.search.service import SearchService
from daesingo.search.sources import ResolvedAnalysisSource, StaticAnalysisSourceResolver
from daesingo.search.usage import ProviderUsage
from tests.search._search_service_support import (
    FixtureMediaPreparer,
    OpenableResolver,
    make_deadline,
)

_SOURCE_REF = ContractRef(kind="analysis_source", ref="clip-run-1")
_SOURCE = ResolvedAnalysisSource(
    source_ref=_SOURCE_REF,
    duration_sec=10.0,
    timeline_id="clip-run-1",
    timeline_revision=1,
)
_SCOPE = AnalysisScope(
    scope_id="scope-run-1",
    time_ranges=(
        TimelineRelativeTimeRange(
            kind=TimeRangeKind.TIMELINE_RELATIVE,
            timeline_ref=TimelineRef(timeline_id="clip-run-1", revision=1),
            start_ms=0,
            end_ms=10_000,
        ),
    ),
    target_event_types=tuple(VisualEventType),
    hint=SearchHint(vehicle=None, free_text=None),
    budget=SearchBudget(max_cost_krw=1000, max_latency_sec=30),
    contract_version="1.1.0",
)


class _MinimalProvider:
    def search_coarse(self, request: CoarseRequest) -> ProviderResult[CoarseResponse]:
        _ = request
        response = CoarseResponse.model_validate(
            {
                "candidates": [
                    {
                        "event_type": "SIGNAL",
                        "span": {"start_sec": 1, "end_sec": 3},
                        "at_sec": 2,
                        "observed": ["적색 점등"],
                        "score": 0.8,
                    }
                ]
            }
        )
        return ProviderResult(response, ProviderUsage(10, 2, 0, 12), 15)

    def verify_fine(self, request: FineRequest) -> ProviderResult[FineResponse]:
        _ = request
        raise NotImplementedError


def _make_service() -> SearchService:
    resolver = StaticAnalysisSourceResolver(
        {"scope-run-1": (_SOURCE,)},
        {"clip-run-1": _SOURCE},
    )
    return SearchService(
        OpenableResolver(resolver),
        _MinimalProvider(),
        GeminiSearchConfig(),
        FixtureMediaPreparer(_SOURCE.duration_sec),
        make_deadline(),
    )


def test_coarse_run_input_ref_kind_is_uppercase_analysis_scope() -> None:
    result = _make_service().search_candidates(_SCOPE)
    assert result.analysis_run.input_ref.kind == "ANALYSIS_SCOPE"


# ---------------------------------------------------------------------------
# 실패 taxonomy — 계약 §7 Producer "SUCCEEDED / PARTIAL / FAILED를 구분한다"
# stage는 Issue에 별도 필드를 두지 않는다. operation이 COARSE/FINE을 이미 구분한다.
# ---------------------------------------------------------------------------


class _FailingProvider:
    """provider 호출이 실패하는 경우 — taxonomy의 INFRA."""

    def __init__(self, failure: Exception) -> None:
        self._failure = failure

    def search_coarse(self, request: CoarseRequest) -> ProviderResult[CoarseResponse]:
        _ = request
        raise self._failure

    def verify_fine(self, request: FineRequest) -> ProviderResult[FineResponse]:
        _ = request
        raise NotImplementedError


def _service_with(provider: object) -> SearchService:
    resolver = StaticAnalysisSourceResolver(
        {"scope-run-1": (_SOURCE,)},
        {"clip-run-1": _SOURCE},
    )
    return SearchService(
        OpenableResolver(resolver),
        provider,
        GeminiSearchConfig(),
        FixtureMediaPreparer(_SOURCE.duration_sec),
        make_deadline(),
    )


def test_provider_failure_returns_failed_run_instead_of_raising() -> None:
    result = _service_with(
        _FailingProvider(RuntimeError("provider exploded"))
    ).search_candidates(_SCOPE)
    assert result.analysis_run.outcome is RunOutcome.FAILED
    assert result.candidates == ()


def test_provider_failure_records_infra_issue_with_scope_ref() -> None:
    result = _service_with(
        _FailingProvider(RuntimeError("provider exploded"))
    ).search_candidates(_SCOPE)
    (issue,) = result.analysis_run.issues
    assert issue.kind is FailureKind.INFRA
    assert issue.code == "PROVIDER_CALL_FAILED"
    assert issue.scope_ref == "scope-run-1"


def test_exhausted_deadline_records_cost_issue() -> None:
    """taxonomy의 COST = 비용·지연 상한 초과로 중단."""
    resolver = StaticAnalysisSourceResolver(
        {"scope-run-1": (_SOURCE,)},
        {"clip-run-1": _SOURCE},
    )
    service = SearchService(
        OpenableResolver(resolver),
        _MinimalProvider(),
        GeminiSearchConfig(),
        FixtureMediaPreparer(_SOURCE.duration_sec),
        RunDeadline(lambda: 0.0, budget_ms=0),
    )

    result = service.search_candidates(_SCOPE)

    (issue,) = result.analysis_run.issues
    assert result.analysis_run.outcome is RunOutcome.FAILED
    assert issue.kind is FailureKind.COST
    assert issue.code == "RUN_DEADLINE_EXCEEDED"


def test_failed_run_keeps_implementation_metadata() -> None:
    """실패해도 어느 구현이 실패했는지 비교 가능해야 한다 (계약 §7 Producer)."""
    result = _service_with(
        _FailingProvider(RuntimeError("provider exploded"))
    ).search_candidates(_SCOPE)
    assert result.analysis_run.implementation.impl_id == "search:gemini-coarse-p3"
    assert result.analysis_run.input_ref.kind == "ANALYSIS_SCOPE"


def test_failed_run_detail_excludes_raw_provider_payload() -> None:
    """계약 §3-3: detail에 stack trace나 raw provider payload를 넣지 않는다."""
    secret = "RAW_PROVIDER_PAYLOAD_XYZ"
    result = _service_with(_FailingProvider(RuntimeError(secret))).search_candidates(
        _SCOPE
    )
    (issue,) = result.analysis_run.issues
    assert issue.detail is not None
    assert secret not in issue.detail
    assert "Traceback" not in issue.detail
