"""`AnalysisScope.budget`이 실행 상한으로 실제 집행되는지 확인한다.

계약 contract-analysis-scope.md §104: `max_latency_sec`는 search가 준수할 실행 마감이다.
#149 A안: 이 값이 유일한 상한이고, 시계는 검색 호출 시점에 시작한다. Fine은 후보를
만든 Coarse scope의 상한을 이어받되 호출마다 새 시계로 센다.
`max_latency_sec`만 다룬다 — `max_cost_krw`는 KRW↔USD 환산 정책이 아직
미결이라(adr-data-contract-call-closure-2026-09-07.md §306, UsageRecord §10
잔여 "통화 KRW 고정") 여기서 임의의 환율을 도입하지 않는다.
"""

from collections.abc import Callable

import pytest

from daesingo.search.config import GeminiSearchConfig
from daesingo.search.errors import UnknownCandidateRunError
from daesingo.search.provider import CoarseRequest, FineRequest, ProviderResult
from daesingo.search.runs import CandidateEvent, ContractRef, FailureKind, RunOutcome
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
)

_SOURCE_REF = ContractRef(kind="analysis_source", ref="clip-budget-1")
_SOURCE = ResolvedAnalysisSource(
    source_ref=_SOURCE_REF,
    duration_sec=10.0,
    timeline_id="clip-budget-1",
    timeline_revision=1,
)


def _scope(max_latency_sec: int) -> AnalysisScope:
    return AnalysisScope(
        scope_id="scope-budget-1",
        time_ranges=(
            TimelineRelativeTimeRange(
                kind=TimeRangeKind.TIMELINE_RELATIVE,
                timeline_ref=TimelineRef(timeline_id="clip-budget-1", revision=1),
                start_ms=0,
                end_ms=10_000,
            ),
        ),
        target_event_types=tuple(VisualEventType),
        hint=SearchHint(vehicle=None, free_text=None),
        budget=SearchBudget(max_cost_krw=1000, max_latency_sec=max_latency_sec),
        contract_version="1.1.0",
    )


class _TimeoutSpy:
    """provider가 받은 per-attempt timeout을 기록한다."""

    timeouts: list[float]
    fine_timeouts: list[float]

    def __init__(self) -> None:
        self.timeouts = []
        self.fine_timeouts = []

    def search_coarse(self, request: CoarseRequest) -> ProviderResult[CoarseResponse]:
        self.timeouts.append(request.timeout_sec)
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
        self.fine_timeouts.append(request.timeout_sec)
        response = FineResponse.model_validate(
            {
                "verification": "UNCERTAIN",
                "visual_event_type": None,
                "target": {
                    "association_status": "AMBIGUOUS",
                    "described_as": None,
                    "match_with_hint": None,
                    "association_confidence": None,
                    "track_ref": None,
                },
                "primitives": [],
                "temporal_facts": [],
                "uncertainties": [],
            }
        )
        return ProviderResult(response, ProviderUsage(10, 2, 0, 12), 15)


def _make_clock() -> tuple[Callable[[], float], Callable[[float], None]]:
    now = [0.0]

    def monotonic() -> float:
        return now[0]

    def advance(seconds: float) -> None:
        now[0] += seconds

    return monotonic, advance


def _service(provider: object, monotonic: Callable[[], float]) -> SearchService:
    resolver = StaticAnalysisSourceResolver(
        {"scope-budget-1": (_SOURCE,)},
        {"clip-budget-1": _SOURCE},
    )
    return SearchService(
        OpenableResolver(resolver),
        provider,
        GeminiSearchConfig(),
        FixtureMediaPreparer(_SOURCE.duration_sec),
        monotonic,
    )


def _only_candidate(service: SearchService, max_latency_sec: int) -> CandidateEvent:
    (candidate,) = service.search_candidates(_scope(max_latency_sec)).candidates
    return candidate


def test_scope_latency_budget_caps_the_provider_timeout() -> None:
    monotonic, _ = _make_clock()
    spy = _TimeoutSpy()

    _ = _service(spy, monotonic).search_candidates(_scope(max_latency_sec=5))

    (timeout,) = spy.timeouts
    assert timeout == 5.0


def test_scope_latency_budget_is_not_capped_by_a_hidden_service_limit() -> None:
    """#149: factory의 60초 하드코딩이 요청서 값을 조용히 자르던 회귀."""
    monotonic, _ = _make_clock()
    spy = _TimeoutSpy()

    _ = _service(spy, monotonic).search_candidates(_scope(max_latency_sec=3600))

    (timeout,) = spy.timeouts
    assert timeout == 3600.0


def test_budget_clock_starts_at_the_search_call_not_service_construction() -> None:
    monotonic, advance = _make_clock()
    spy = _TimeoutSpy()
    service = _service(spy, monotonic)
    advance(100.0)

    result = service.search_candidates(_scope(max_latency_sec=5))

    assert result.analysis_run.outcome is RunOutcome.SUCCEEDED
    assert spy.timeouts == [5.0]


def test_exhausted_scope_latency_budget_records_cost_issue() -> None:
    """scope budget을 넘긴 실행은 provider를 부르지 않고 COST로 기록된다."""
    readings = iter((0.0, 1.5))
    last = [0.0]

    def monotonic() -> float:
        last[0] = next(readings, last[0])
        return last[0]

    spy = _TimeoutSpy()

    result = _service(spy, monotonic).search_candidates(_scope(max_latency_sec=1))

    (issue,) = result.analysis_run.issues
    assert result.analysis_run.outcome is RunOutcome.FAILED
    assert issue.kind is FailureKind.COST
    assert spy.timeouts == []


def test_fine_inherits_the_coarse_scope_budget_with_a_fresh_clock() -> None:
    """후보를 다시 고르는 동안 흐른 시간이 Fine 상한을 깎지 않는다(FINE_VERIFY는 별도 Job)."""
    monotonic, advance = _make_clock()
    spy = _TimeoutSpy()
    service = _service(spy, monotonic)
    candidate = _only_candidate(service, max_latency_sec=5)
    advance(100.0)

    _ = service.verify_visual(_SOURCE_REF, candidate, event_type=VisualEventType.SIGNAL)

    assert spy.fine_timeouts == [5.0]


def test_fine_rejects_a_candidate_from_a_run_this_service_did_not_execute() -> None:
    monotonic, _ = _make_clock()
    spy = _TimeoutSpy()
    candidate = _only_candidate(_service(_TimeoutSpy(), monotonic), max_latency_sec=5)

    with pytest.raises(UnknownCandidateRunError):
        _ = _service(spy, monotonic).verify_visual(
            _SOURCE_REF, candidate, event_type=VisualEventType.SIGNAL
        )

    assert spy.fine_timeouts == []


def test_fine_runs_on_another_service_with_an_explicit_budget() -> None:
    """Coarse와 다른 객체(Worker)에서도 넘겨받은 상한으로 Fine을 실행한다(#226)."""
    monotonic, _ = _make_clock()
    candidate = _only_candidate(_service(_TimeoutSpy(), monotonic), max_latency_sec=5)
    spy = _TimeoutSpy()

    _ = _service(spy, monotonic).verify_visual(
        _SOURCE_REF, candidate, event_type=VisualEventType.SIGNAL, max_latency_sec=70
    )

    assert spy.fine_timeouts == [70.0]
