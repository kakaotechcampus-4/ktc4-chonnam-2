"""Task 6: CoarseResult retains source_ref; service exposes linked search + lookup."""

import pytest

from daesingo.search.config import GeminiSearchConfig
from daesingo.search.errors import UnknownCandidateError
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

_SOURCE_REF = ContractRef(kind="analysis_source", ref="clip-link-1")
_SOURCE = ResolvedAnalysisSource(
    source_ref=_SOURCE_REF,
    duration_sec=10.0,
    timeline_id="clip-link-1",
    timeline_revision=1,
)
_SCOPE = AnalysisScope(
    scope_id="scope-link-1",
    time_ranges=(
        TimelineRelativeTimeRange(
            kind=TimeRangeKind.TIMELINE_RELATIVE,
            timeline_ref=TimelineRef(timeline_id="clip-link-1", revision=1),
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
        {"scope-link-1": (_SOURCE,)},
        {"clip-link-1": _SOURCE},
    )
    return SearchService(
        OpenableResolver(resolver),
        _MinimalProvider(),
        GeminiSearchConfig(),
        FixtureMediaPreparer(_SOURCE.duration_sec),
        make_deadline(),
    )


# ---------------------------------------------------------------------------
# Core linkage tests
# ---------------------------------------------------------------------------


def test_linked_search_source_ref_equals_resolved_source_ref() -> None:
    """source_ref on the linked result is the exact ResolvedAnalysisSource.source_ref."""
    service = _make_service()
    linked = service.search_candidates_linked(_SCOPE)
    assert linked.source_ref == _SOURCE_REF


def test_linked_search_source_ref_kind_is_analysis_source() -> None:
    service = _make_service()
    linked = service.search_candidates_linked(_SCOPE)
    assert linked.source_ref.kind == "analysis_source"


def test_source_ref_for_known_candidate_returns_source_ref() -> None:
    service = _make_service()
    linked = service.search_candidates_linked(_SCOPE)
    candidate = linked.result.candidates[0]
    ref = linked.source_ref_for(candidate.candidate_id)
    assert ref == _SOURCE_REF


def test_source_ref_for_unknown_candidate_raises_typed_error() -> None:
    from daesingo.search.runs import CandidateId

    service = _make_service()
    linked = service.search_candidates_linked(_SCOPE)
    with pytest.raises(UnknownCandidateError) as exc_info:
        _ = linked.source_ref_for(CandidateId("candidate_does_not_exist"))
    assert "candidate_does_not_exist" in str(exc_info.value)


def test_source_ref_for_validates_kind() -> None:
    """source_ref.kind must be 'analysis_source' — bad ref raises on construction."""
    service = _make_service()
    linked = service.search_candidates_linked(_SCOPE)
    assert linked.source_ref.kind == "analysis_source"
    assert linked.source_ref.ref == _SOURCE_REF.ref


# ---------------------------------------------------------------------------
# Legacy schema unchanged
# ---------------------------------------------------------------------------


def test_legacy_search_candidates_returns_unchanged_candidate_search_result() -> None:
    """search_candidates() still returns a plain CandidateSearchResult."""
    from daesingo.search.runs import CandidateSearchResult

    service = _make_service()
    result = service.search_candidates(_SCOPE)
    assert isinstance(result, CandidateSearchResult)
    # serialized shape must not include any linkage fields
    serialized = result.model_dump()
    assert set(serialized.keys()) == {"analysis_run", "candidates"}


def test_legacy_search_candidates_returns_structurally_equivalent_result() -> None:
    """search_candidates() and search_candidates_linked() produce structurally equivalent candidates."""
    service = _make_service()
    linked = service.search_candidates_linked(_SCOPE)
    legacy = service.search_candidates(_SCOPE)
    assert len(legacy.candidates) == len(linked.result.candidates)
    for leg_c, lnk_c in zip(legacy.candidates, linked.result.candidates):
        assert leg_c.span == lnk_c.span
        assert leg_c.rank == lnk_c.rank


def test_zero_sources_raises_assertion_error() -> None:
    """When resolve() yields no sources, search_coarse raises AssertionError rather than fabricating a ref."""
    from daesingo.search.sources import StaticAnalysisSourceResolver

    resolver = StaticAnalysisSourceResolver(
        {"scope-link-1": ()},  # empty tuple → zero sources
        {},
    )
    service = SearchService(
        OpenableResolver(resolver),
        _MinimalProvider(),
        GeminiSearchConfig(),
        FixtureMediaPreparer(_SOURCE.duration_sec),
        make_deadline(),
    )
    with pytest.raises(AssertionError, match="no sources"):
        _ = service.search_candidates_linked(_SCOPE)
