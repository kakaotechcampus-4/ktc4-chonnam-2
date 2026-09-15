from pathlib import Path
from typing import Final

from .fixtures import FixtureNotFoundError, FixtureSearchService
from .runs import CandidateSearchResult, ContractRef
from .scope import AnalysisScope, SearchHint
from .visual import VisualVerificationResult

_MOCK_DIR: Final = Path(__file__).resolve().parents[3] / "data" / "mock" / "search"
_FIXTURE_SERVICE: Final = FixtureSearchService(_MOCK_DIR)


def search_candidates(scope: AnalysisScope) -> CandidateSearchResult:
    """Return the recorded coarse run and ranked candidates for a scope."""
    return _FIXTURE_SERVICE.search_candidates(scope)


def verify_visual(
    input_ref: ContractRef,
    target_hint: SearchHint | None = None,
) -> VisualVerificationResult:
    """Return the recorded Fine run together with its visual evidence."""
    return _FIXTURE_SERVICE.verify_visual(input_ref, target_hint)


__all__ = [
    "AnalysisScope",
    "CandidateSearchResult",
    "ContractRef",
    "FixtureNotFoundError",
    "SearchHint",
    "VisualVerificationResult",
    "search_candidates",
    "verify_visual",
]
