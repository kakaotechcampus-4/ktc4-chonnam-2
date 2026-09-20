from pathlib import Path
from typing import Final

from .errors import MissingCandidateError
from .factory import build_gemini_search_service
from .fixtures import FixtureNotFoundError, FixtureSearchService
from .runs import CandidateEvent, CandidateSearchResult, ContractRef
from .scope import AnalysisScope, SearchHint, VisualEventType
from .service import SearchService
from .sources import AnalysisSourceResolver, CandidateSourceLink, ResolvedAnalysisSource
from .visual import VisualVerificationResult

_MOCK_DIR: Final = Path(__file__).resolve().parents[3] / "data" / "mock" / "search"
_FIXTURE_SERVICE: Final = FixtureSearchService(_MOCK_DIR)


def search_candidates(
    scope: AnalysisScope,
    *,
    service: SearchService | None = None,
) -> CandidateSearchResult:
    """Return the recorded coarse run and ranked candidates for a scope."""
    if service is None:
        return _FIXTURE_SERVICE.search_candidates(scope)
    return service.search_candidates(scope)


def verify_visual(
    input_ref: ContractRef,
    target_hint: SearchHint | None = None,
    *,
    service: SearchService | None = None,
    event_type: str | VisualEventType = VisualEventType.SOLID_LINE_LANE_CHANGE,
    candidate: CandidateEvent | None = None,
) -> VisualVerificationResult:
    """Return the recorded Fine run together with its visual evidence."""
    if service is None:
        return _FIXTURE_SERVICE.verify_visual(input_ref, target_hint)
    if candidate is None:
        raise MissingCandidateError(source_ref=input_ref)
    return service.verify_visual(input_ref, candidate, target_hint, event_type)


__all__ = [
    "AnalysisScope",
    "AnalysisSourceResolver",
    "CandidateSearchResult",
    "CandidateSourceLink",
    "ContractRef",
    "FixtureNotFoundError",
    "ResolvedAnalysisSource",
    "SearchHint",
    "SearchService",
    "VisualEventType",
    "VisualVerificationResult",
    "build_gemini_search_service",
    "search_candidates",
    "verify_visual",
]
