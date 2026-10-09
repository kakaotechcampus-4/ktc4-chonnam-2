"""#168 클립 분할 후속 — `ranking_score` 순서 규칙(contract-analysis-run-candidate-event §6-2 8).

클립 Run 묶음 정렬은 「한 Run 안의 정렬 규칙과 같다」로 정했다: `ranking_score` 내림차순,
동점이면 원본 timeline 기준 시각이 이른 후보가 앞. 클립 분할(여러 Run 묶음)은 아직 구현되지
않았으므로 여기서는 그 규칙의 원형인 단일 Run 정렬을 고정한다. 묶음 정렬은 클립 분할을
도입할 때 이 규칙으로 테스트를 추가한다.
"""

from dataclasses import dataclass

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
    frozen_clock,
)


@dataclass(frozen=True, slots=True)
class _CoarseProvider:
    response: CoarseResponse

    def search_coarse(self, request: CoarseRequest) -> ProviderResult[CoarseResponse]:
        return ProviderResult(response=self.response, usage=ProviderUsage(10, 2, 0, 12), latency_ms=15)

    def verify_fine(self, request: FineRequest) -> ProviderResult[FineResponse]:
        raise NotImplementedError


def _scope() -> AnalysisScope:
    return AnalysisScope(
        scope_id="scope-1",
        time_ranges=(
            TimelineRelativeTimeRange(
                kind=TimeRangeKind.TIMELINE_RELATIVE,
                timeline_ref=TimelineRef(timeline_id="timeline-1", revision=4),
                start_ms=0,
                end_ms=10_000,
            ),
        ),
        target_event_types=tuple(VisualEventType),
        hint=SearchHint(vehicle=None, free_text=None),
        budget=SearchBudget(max_cost_krw=1000, max_latency_sec=30),
        contract_version="1.1.0",
    )


def _run(candidates: list[dict]) -> tuple:
    source = ResolvedAnalysisSource(ContractRef(kind="analysis_source", ref="clip-1"), 10.0, "timeline-1", 4)
    service = SearchService(
        OpenableResolver(StaticAnalysisSourceResolver({"scope-1": (source,)}, {})),
        _CoarseProvider(CoarseResponse.model_validate({"candidates": candidates})),
        GeminiSearchConfig(),
        FixtureMediaPreparer(source.duration_sec),
        frozen_clock,
    )
    return service.search_candidates(_scope()).candidates


def _candidate(at_sec: float, score: float) -> dict:
    return {
        "event_type": "SIGNAL",
        "span": {"start_sec": at_sec - 0.5, "end_sec": at_sec + 0.5},
        "at_sec": at_sec,
        "observed": ["signal visible"],
        "score": score,
    }


def test_rank_follows_ranking_score_descending_then_earlier_time() -> None:
    ranked = _run([_candidate(1.0, 0.5), _candidate(6.0, 0.9), _candidate(3.0, 0.9)])

    assert [(c.rank, c.span.representative_ms, c.ranking_score) for c in ranked] == [
        (1, 3000, 0.9),  # 동점이면 원본 timeline 기준 시각이 이른 후보가 앞
        (2, 6000, 0.9),
        (3, 1000, 0.5),
    ]


def test_ranks_are_unique_and_start_at_one_within_a_run() -> None:
    ranked = _run([_candidate(2.0, 0.2), _candidate(4.0, 0.8), _candidate(8.0, 0.4)])

    assert [c.rank for c in ranked] == [1, 2, 3]


def test_ranking_score_is_passed_through_raw_not_normalized_into_a_probability() -> None:
    # calibrated confidence가 아니므로 search가 확률로 보정·정규화하지 않는다. 합이 1이 아니어도 된다.
    ranked = _run([_candidate(2.0, 0.9), _candidate(5.0, 0.9), _candidate(7.0, 0.9)])

    assert [c.ranking_score for c in ranked] == [0.9, 0.9, 0.9]
