from dataclasses import dataclass, field

import pytest

from daesingo.search import search_candidates, verify_visual
from daesingo.search.config import GeminiSearchConfig
from daesingo.search.errors import (
    CandidateSourceMismatchError,
    InvalidFineSpanError,
    MissingCandidateError,
)
from daesingo.search.provider import CoarseRequest, FineRequest, ProviderResult
from daesingo.search.runs import (
    CandidateEvent,
    CandidateId,
    CandidateSpan,
    ContractRef,
    RunId,
)
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


def _fine_response() -> FineResponse:
    return FineResponse.model_validate(
        {
            "verification": "UNCERTAIN",
            "visual_event_type": None,
            "target": {
                "association_status": "AMBIGUOUS",
                "described_as": None,
                "match_with_hint": None,
                "association_confidence": None,
                "track_ref": None,
                "evidence_refs": [],
            },
            "primitives": [],
            "temporal_facts": [],
            "uncertainties": [],
        }
    )


@dataclass(slots=True)
class _RecordingProvider:
    fine_requests: list[FineRequest] = field(default_factory=list)
    coarse_response: CoarseResponse | None = None

    def search_coarse(self, request: CoarseRequest) -> ProviderResult[CoarseResponse]:
        del request
        if self.coarse_response is None:
            raise NotImplementedError
        return ProviderResult(self.coarse_response, ProviderUsage(10, 2, 0, 12), 15)

    def verify_fine(self, request: FineRequest) -> ProviderResult[FineResponse]:
        self.fine_requests.append(request)
        return ProviderResult(_fine_response(), ProviderUsage(10, 2, 0, 12), 15)


def _source(duration_sec: float = 10.0) -> ResolvedAnalysisSource:
    return ResolvedAnalysisSource(
        source_ref=ContractRef(kind="analysis_source", ref="source-1"),
        duration_sec=duration_sec,
        timeline_id="timeline-1",
        timeline_revision=4,
    )


def _candidate(
    start_ms: int = 2000,
    end_ms: int = 6000,
    timeline_id: str = "timeline-1",
    timeline_revision: int = 4,
) -> CandidateEvent:
    return CandidateEvent(
        candidate_id=CandidateId("candidate-1"),
        run_id=RunId("run-coarse-1"),
        span=CandidateSpan(
            timeline_id=timeline_id,
            timeline_revision=timeline_revision,
            start_ms=start_ms,
            end_ms=end_ms,
            representative_ms=(start_ms + end_ms) // 2,
        ),
        rank=1,
        ranking_score=0.9,
        event_type_hint=VisualEventType.SIGNAL,
        summary="signal visible",
        uncertainties=(),
        thumbnail_ref=None,
    )


def test_verify_visual_fixture_accepts_omitted_candidate() -> None:
    # Given
    input_ref = ContractRef(kind="analysis_source", ref="as_h001_fine")

    # When
    result = verify_visual(input_ref)

    # Then
    assert result.visual_evidence.input_ref == input_ref


def test_verify_visual_real_service_uses_selected_candidate_and_explicit_event_type() -> (
    None
):
    # Given
    source = _source()
    input_ref = ContractRef(kind="analysis_source", ref="source-1")
    provider = _RecordingProvider()
    service = SearchService(
        StaticAnalysisSourceResolver({}, {input_ref.ref: source}),
        provider,
        GeminiSearchConfig(),
    )

    # When
    result = verify_visual(
        input_ref,
        candidate=_candidate(),
        event_type=VisualEventType.SOLID_LINE_LANE_CHANGE,
        service=service,
    )

    # Then
    assert provider.fine_requests[0].source == source
    assert result.analysis_run.input_ref == input_ref
    assert (
        provider.fine_requests[0].event_type is VisualEventType.SOLID_LINE_LANE_CHANGE
    )
    assert result.visual_evidence.candidate_id == CandidateId("candidate-1")


def test_verify_visual_real_service_rejects_a_missing_candidate_before_provider_call() -> (
    None
):
    # Given
    source = _source()
    input_ref = ContractRef(kind="analysis_source", ref="source-1")
    provider = _RecordingProvider()
    service = SearchService(
        StaticAnalysisSourceResolver({}, {input_ref.ref: source}),
        provider,
        GeminiSearchConfig(),
    )

    # When / Then
    with pytest.raises(MissingCandidateError):
        verify_visual(input_ref, service=service)
    assert provider.fine_requests == []


def test_verify_visual_real_service_pads_selected_candidate_offsets_exactly() -> None:
    # Given
    source = _source()
    input_ref = ContractRef(kind="analysis_source", ref="source-1")
    provider = _RecordingProvider()
    service = SearchService(
        StaticAnalysisSourceResolver({}, {input_ref.ref: source}),
        provider,
        GeminiSearchConfig(fine_padding_sec=1.5),
    )

    # When
    result = verify_visual(input_ref, candidate=_candidate(), service=service)

    # Then
    request = provider.fine_requests[0]
    assert (request.start_sec, request.end_sec) == (0.5, 7.5)
    assert result.analysis_run.input_ref == input_ref
    assert result.visual_evidence.input_ref == input_ref
    assert result.visual_evidence.candidate_id == CandidateId("candidate-1")


@pytest.mark.parametrize(
    ("candidate", "expected_offsets"),
    [
        (_candidate(500, 6000), (0.0, 8.0)),
        (_candidate(2000, 9500), (0.0, 10.0)),
    ],
)
def test_verify_visual_real_service_clamps_padded_offsets(
    candidate: CandidateEvent, expected_offsets: tuple[float, float]
) -> None:
    # Given
    source = _source()
    input_ref = ContractRef(kind="analysis_source", ref="source-1")
    provider = _RecordingProvider()
    service = SearchService(
        StaticAnalysisSourceResolver({}, {input_ref.ref: source}),
        provider,
        GeminiSearchConfig(fine_padding_sec=2.0),
    )

    # When
    verify_visual(input_ref, candidate=candidate, service=service)

    # Then
    request = provider.fine_requests[0]
    assert (request.start_sec, request.end_sec) == expected_offsets


@pytest.mark.parametrize(
    ("timeline_id", "timeline_revision"),
    [("other-timeline", 4), ("timeline-1", 5)],
)
def test_verify_visual_real_service_rejects_candidate_timeline_mismatch(
    timeline_id: str, timeline_revision: int
) -> None:
    # Given
    source = _source()
    input_ref = ContractRef(kind="analysis_source", ref="source-1")
    provider = _RecordingProvider()
    service = SearchService(
        StaticAnalysisSourceResolver({}, {input_ref.ref: source}),
        provider,
        GeminiSearchConfig(),
    )

    # When / Then
    with pytest.raises(CandidateSourceMismatchError):
        verify_visual(
            input_ref,
            candidate=_candidate(
                timeline_id=timeline_id, timeline_revision=timeline_revision
            ),
            service=service,
        )
    assert provider.fine_requests == []


def test_verify_visual_real_service_rejects_a_non_source_reference() -> None:
    # Given
    source = _source()
    input_ref = ContractRef(kind="candidate", ref="source-1")
    provider = _RecordingProvider()
    service = SearchService(
        StaticAnalysisSourceResolver({}, {input_ref.ref: source}),
        provider,
        GeminiSearchConfig(),
    )

    # When / Then
    with pytest.raises(CandidateSourceMismatchError):
        verify_visual(input_ref, candidate=_candidate(), service=service)
    assert provider.fine_requests == []


def test_verify_visual_real_service_rejects_a_degenerate_clamped_span() -> None:
    # Given
    source = _source(duration_sec=0.0)
    input_ref = ContractRef(kind="analysis_source", ref="source-1")
    provider = _RecordingProvider()
    service = SearchService(
        StaticAnalysisSourceResolver({}, {input_ref.ref: source}),
        provider,
        GeminiSearchConfig(),
    )

    # When / Then
    with pytest.raises(InvalidFineSpanError):
        verify_visual(input_ref, candidate=_candidate(), service=service)
    assert provider.fine_requests == []


def test_public_coarse_to_fine_selected_candidate_manual_qa() -> None:
    # Given
    source = _source()
    source_ref = ContractRef(kind="analysis_source", ref="source-1")
    scope = AnalysisScope(
        scope_id="scope-1",
        time_ranges=(
            TimelineRelativeTimeRange(
                kind=TimeRangeKind.TIMELINE_RELATIVE,
                timeline_ref=TimelineRef(timeline_id="timeline-1", revision=4),
                start_ms=0,
                end_ms=10_000,
            ),
        ),
        target_event_types=(VisualEventType.SIGNAL,),
        hint=SearchHint(vehicle=None, free_text=None),
        budget=SearchBudget(max_cost_krw=1000, max_latency_sec=30),
        contract_version="1.1.0",
    )
    provider = _RecordingProvider(
        coarse_response=CoarseResponse.model_validate(
            {
                "candidates": [
                    {
                        "event_type": "SIGNAL",
                        "span": {"start_sec": 1.0, "end_sec": 9.0},
                        "at_sec": 5.0,
                        "observed": ["signal visible"],
                        "score": 0.9,
                    }
                ]
            }
        )
    )
    service = SearchService(
        StaticAnalysisSourceResolver(
            {scope.scope_id: (source,)}, {source_ref.ref: source}
        ),
        provider,
        GeminiSearchConfig(fine_padding_sec=2.0),
    )

    # When
    coarse = search_candidates(scope, service=service)
    selected = max(coarse.candidates, key=lambda candidate: candidate.ranking_score)
    fine = verify_visual(source_ref, candidate=selected, service=service)

    # Then
    request = provider.fine_requests[0]
    print(
        "manual-qa",
        f"selected_id={selected.candidate_id}",
        f"fine_offsets=({request.start_sec}, {request.end_sec})",
        f"evidence_candidate_id={fine.visual_evidence.candidate_id}",
        f"analysis_input_ref={fine.analysis_run.input_ref.ref}",
        f"evidence_input_ref={fine.visual_evidence.input_ref.ref}",
    )
    assert (request.start_sec, request.end_sec) == (0.0, 10.0)
    assert fine.visual_evidence.candidate_id == selected.candidate_id
    assert fine.analysis_run.input_ref == source_ref
    assert fine.visual_evidence.input_ref == source_ref
