"""`AnalysisScope.budget`이 실행 상한으로 실제 집행되는지 확인한다.

계약 contract-analysis-scope.md §103: budget은 scope **전체**의 상한이다.
`max_latency_sec`만 다룬다 — `max_cost_krw`는 KRW↔USD 환산 정책이 아직
미결이라(adr-data-contract-call-closure-2026-09-07.md §306, UsageRecord §10
잔여 "통화 KRW 고정") 여기서 임의의 환율을 도입하지 않는다.
"""

from collections.abc import Callable

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

    def __init__(self) -> None:
        self.timeouts = []

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
        _ = request
        raise NotImplementedError


def _make_clock() -> tuple[Callable[[], float], Callable[[float], None]]:
    now = [0.0]

    def monotonic() -> float:
        return now[0]

    def advance(seconds: float) -> None:
        now[0] += seconds

    return monotonic, advance


def _service(
    provider: object, deadline: RunDeadline
) -> SearchService:
    resolver = StaticAnalysisSourceResolver(
        {"scope-budget-1": (_SOURCE,)},
        {"clip-budget-1": _SOURCE},
    )
    return SearchService(
        OpenableResolver(resolver),
        provider,
        GeminiSearchConfig(),
        FixtureMediaPreparer(_SOURCE.duration_sec),
        deadline,
    )


def test_scope_latency_budget_caps_the_provider_timeout() -> None:
    """주입된 deadline이 더 넉넉해도 scope budget이 상한이 된다."""
    monotonic, _ = _make_clock()
    spy = _TimeoutSpy()

    _ = _service(spy, RunDeadline(monotonic, budget_ms=30_000)).search_candidates(
        _scope(max_latency_sec=5)
    )

    (timeout,) = spy.timeouts
    assert timeout <= 5.0


def test_injected_deadline_still_wins_when_it_is_tighter() -> None:
    """scope budget은 상한을 좁히기만 한다 — 남은 실행 시간을 늘리지 않는다."""
    monotonic, _ = _make_clock()
    spy = _TimeoutSpy()

    _ = _service(spy, RunDeadline(monotonic, budget_ms=2_000)).search_candidates(
        _scope(max_latency_sec=3600)
    )

    (timeout,) = spy.timeouts
    assert timeout <= 2.0


def test_exhausted_scope_latency_budget_records_cost_issue() -> None:
    """scope budget을 넘긴 실행은 provider를 부르지 않고 COST로 기록된다."""
    monotonic, advance = _make_clock()
    spy = _TimeoutSpy()
    service = _service(spy, RunDeadline(monotonic, budget_ms=30_000))
    advance(1.5)

    result = service.search_candidates(_scope(max_latency_sec=1))

    (issue,) = result.analysis_run.issues
    assert result.analysis_run.outcome is RunOutcome.FAILED
    assert issue.kind is FailureKind.COST
    assert spy.timeouts == []
