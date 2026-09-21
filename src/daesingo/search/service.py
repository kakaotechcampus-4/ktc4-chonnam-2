from dataclasses import dataclass, field

from .coarse import (
    CoarseExecutionDependencies,
    LinkedCoarseResult,
    search_coarse,
)
from .config import GeminiSearchConfig
from .execution import RunDeadline
from .fine import normalize_event_type, verify_fine
from .ledger import SearchLedger
from .media_contract import CoarseMediaPreparer
from .provider import SearchProvider
from .runs import CandidateEvent, CandidateSearchResult, ContractRef
from .scope import AnalysisScope, SearchHint, VisualEventType
from .sources import AnalysisSourceResolver
from .visual import VisualVerificationResult


@dataclass(slots=True)
class SearchService:
    resolver: AnalysisSourceResolver
    provider: SearchProvider
    config: GeminiSearchConfig
    media_preparer: CoarseMediaPreparer
    deadline: RunDeadline
    ledger: SearchLedger = field(default_factory=SearchLedger)

    def search_candidates_linked(self, scope: AnalysisScope) -> LinkedCoarseResult:
        """Return coarse search result together with source linkage."""
        return search_coarse(
            scope,
            CoarseExecutionDependencies(
                resolver=self.resolver,
                provider=self.provider,
                config=self.config,
                ledger=self.ledger,
                media_preparer=self.media_preparer,
                deadline=self.deadline,
            ),
        )

    def search_candidates(self, scope: AnalysisScope) -> CandidateSearchResult:
        return self.search_candidates_linked(scope).result

    def verify_visual(
        self,
        input_ref: ContractRef,
        candidate: CandidateEvent,
        target_hint: SearchHint | None = None,
        event_type: str | VisualEventType = VisualEventType.SOLID_LINE_LANE_CHANGE,
    ) -> VisualVerificationResult:
        return verify_fine(
            input_ref,
            candidate,
            target_hint,
            normalize_event_type(event_type),
            self.resolver,
            self.provider,
            self.config,
            self.ledger,
            self.media_preparer,
            self.deadline,
        )
