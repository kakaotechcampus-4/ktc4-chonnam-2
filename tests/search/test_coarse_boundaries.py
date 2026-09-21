from dataclasses import dataclass
from math import isnan

import pytest

from daesingo.search.config import GeminiSearchConfig
from daesingo.search.errors import CandidateSourceMismatchError, InvalidCoarseSpanError
from daesingo.search.provider import CoarseRequest, FineRequest, ProviderResult
from daesingo.search.runs import (
    CandidateEvent,
    CandidateId,
    CandidateSpan,
    ContractRef,
    RunId,
)
from daesingo.search.schemas import (
    CoarseCandidate,
    CoarseResponse,
    CoarseSpan,
    FineResponse,
)
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
from daesingo.search.sources import (
    CandidateSourceLink,
    ResolvedAnalysisSource,
    StaticAnalysisSourceResolver,
)
from daesingo.search.usage import ProviderUsage
from tests.search._search_service_support import (
    FixtureMediaPreparer,
    OpenableResolver,
    make_deadline,
)


@dataclass(frozen=True, slots=True)
class _CoarseProvider:
    response: CoarseResponse

    def search_coarse(self, request: CoarseRequest) -> ProviderResult[CoarseResponse]:
        return ProviderResult(
            response=self.response,
            usage=ProviderUsage(10, 2, 0, 12),
            latency_ms=15,
        )

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


def _source(duration_sec: float = 10.0) -> ResolvedAnalysisSource:
    return ResolvedAnalysisSource(
        ContractRef(kind="analysis_source", ref="clip-1"),
        duration_sec,
        "timeline-1",
        4,
    )


def _candidate(start_sec: float, end_sec: float, at_sec: float) -> CoarseCandidate:
    return CoarseCandidate.model_construct(
        event_type=VisualEventType.SIGNAL,
        span=CoarseSpan.model_construct(start_sec=start_sec, end_sec=end_sec),
        at_sec=at_sec,
        observed=("signal visible",),
        score=0.9,
    )


def _service(source: ResolvedAnalysisSource, response: CoarseResponse) -> SearchService:
    resolver = StaticAnalysisSourceResolver({"scope-1": (source,)}, {})
    return SearchService(
        OpenableResolver(resolver),
        _CoarseProvider(response),
        GeminiSearchConfig(),
        FixtureMediaPreparer(source.duration_sec),
        make_deadline(),
    )


def test_search_coarse_preserves_valid_ranked_timeline_spans() -> None:
    # Given
    source = _source()
    response = CoarseResponse.model_validate(
        {
            "candidates": [
                {
                    "event_type": "SIGNAL",
                    "span": {"start_sec": 1.0, "end_sec": 3.0},
                    "at_sec": 2.0,
                    "observed": ["signal visible"],
                    "score": 0.9,
                },
                {
                    "event_type": "SOLID_LINE_LANE_CHANGE",
                    "span": {"start_sec": 6.0, "end_sec": 8.0},
                    "at_sec": 7.0,
                    "observed": ["lane change visible"],
                    "score": 0.3,
                },
            ]
        }
    )
    service = _service(source, response)

    # When
    result = service.search_candidates(_scope())

    # Then
    assert [candidate.rank for candidate in result.candidates] == [1, 2]
    assert result.candidates[0].span.model_dump() == {
        "timeline_id": "timeline-1",
        "timeline_revision": 4,
        "start_ms": 1000,
        "end_ms": 3000,
        "representative_ms": 2000,
    }


@pytest.mark.parametrize(
    ("start_sec", "end_sec", "at_sec"),
    [
        (float("nan"), 2.0, 1.0),
        (0.0, float("inf"), 1.0),
        (-1.0, 2.0, 1.0),
        (4.0, 3.0, 3.5),
        (11.0, 12.0, 11.5),
    ],
)
def test_search_coarse_rejects_invalid_provider_spans(
    start_sec: float, end_sec: float, at_sec: float
) -> None:
    # Given
    response = CoarseResponse.model_construct(
        candidates=(_candidate(start_sec, end_sec, at_sec),)
    )
    service = _service(_source(), response)

    # When / Then
    with pytest.raises(InvalidCoarseSpanError) as captured:
        service.search_candidates(_scope())
    assert captured.value.source_id == "clip-1"
    assert captured.value.duration_sec == 10.0
    if isnan(start_sec):
        assert isnan(captured.value.start_sec)
    else:
        assert captured.value.start_sec == start_sec
    assert captured.value.end_sec == end_sec


@pytest.mark.parametrize(
    ("start_sec", "end_sec", "at_sec", "expected_start_ms", "expected_end_ms"),
    [(8.0, 12.0, 9.0, 8000, 10_000)],
)
def test_search_coarse_clamps_partially_overlapping_provider_spans(
    start_sec: float,
    end_sec: float,
    at_sec: float,
    expected_start_ms: int,
    expected_end_ms: int,
) -> None:
    # Given
    response = CoarseResponse.model_construct(
        candidates=(_candidate(start_sec, end_sec, at_sec),)
    )
    service = _service(_source(), response)

    # When
    result = service.search_candidates(_scope())

    # Then
    candidate = result.candidates[0]
    assert candidate.span.start_ms == expected_start_ms
    assert candidate.span.end_ms == expected_end_ms
    assert candidate.span.representative_ms == 9000


def test_candidate_source_link_validates_matching_resolved_timeline() -> None:
    # Given
    candidate = CandidateEvent(
        candidate_id=CandidateId("candidate-1"),
        run_id=RunId("run-1"),
        span=CandidateSpan(
            timeline_id="timeline-1",
            timeline_revision=4,
            start_ms=1000,
            end_ms=3000,
            representative_ms=2000,
        ),
        rank=1,
        ranking_score=0.9,
        event_type_hint=VisualEventType.SIGNAL,
        summary="signal visible",
        uncertainties=(),
        thumbnail_ref=None,
    )
    link = CandidateSourceLink(
        source_ref=ContractRef(kind="analysis_source", ref="source-1"),
        candidate=candidate,
    )

    # When: validate against a source whose ref, timeline_id, and timeline_revision all match
    matching_source = ResolvedAnalysisSource(
        ContractRef(kind="analysis_source", ref="source-1"),
        duration_sec=10.0,
        timeline_id="timeline-1",
        timeline_revision=4,
    )
    link.validate(matching_source)

    # Then
    assert link.source_ref.ref == "source-1"
    assert link.candidate.candidate_id == CandidateId("candidate-1")


@pytest.mark.parametrize(
    ("timeline_id", "timeline_revision"),
    [("other-timeline", 4), ("timeline-1", 5)],
)
def test_candidate_source_link_rejects_mismatched_resolved_timeline(
    timeline_id: str, timeline_revision: int
) -> None:
    # Given
    candidate = CandidateEvent(
        candidate_id=CandidateId("candidate-1"),
        run_id=RunId("run-1"),
        span=CandidateSpan(
            timeline_id=timeline_id,
            timeline_revision=timeline_revision,
            start_ms=1000,
            end_ms=3000,
            representative_ms=2000,
        ),
        rank=1,
        ranking_score=0.9,
        event_type_hint=VisualEventType.SIGNAL,
        summary="signal visible",
        uncertainties=(),
        thumbnail_ref=None,
    )
    link = CandidateSourceLink(
        source_ref=ContractRef(kind="analysis_source", ref="source-1"),
        candidate=candidate,
    )

    # When / Then
    with pytest.raises(CandidateSourceMismatchError) as captured:
        link.validate(_source())
    assert captured.value.source_ref.ref == "source-1"
    assert captured.value.source_timeline_id == "timeline-1"
    assert captured.value.source_timeline_revision == 4
