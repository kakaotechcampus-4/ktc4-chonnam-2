"""AnalysisRun이 `analysis-run-candidate-event/v1.1` 계약대로 기록되는지 확인한다.

계약 §4 `input_ref`는 `CANDIDATE_SEARCH`에서 `kind=ANALYSIS_SCOPE`를 쓴다.
자산 계층 ref(`analysis_source`)의 소문자 규칙과 다른 값 공간이다.
"""

from daesingo.search.config import GeminiSearchConfig
from daesingo.search.provider import CoarseRequest, FineRequest, ProviderResult
from daesingo.search.runs import ContractRef
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
