from dataclasses import dataclass, field

from .coarse import search_coarse
from .config import GeminiSearchConfig
from .fine import normalize_event_type, verify_fine
from .ledger import SearchLedger
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
    ledger: SearchLedger = field(default_factory=SearchLedger)

    def search_candidates(self, scope: AnalysisScope) -> CandidateSearchResult:
        return search_coarse(
            scope, self.resolver, self.provider, self.config, self.ledger
        )

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
        )
