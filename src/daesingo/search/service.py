import time
from collections.abc import Callable
from dataclasses import dataclass, field

from .coarse import (
    CoarseExecutionDependencies,
    LinkedCoarseResult,
    search_coarse,
)
from .config import GeminiSearchConfig
from .errors import UnknownCandidateRunError
from .execution import RunDeadline
from .fine import normalize_event_type, verify_fine
from .ledger import SearchLedger
from .media_contract import CoarseMediaPreparer
from .provider import SearchProvider
from .runs import CandidateEvent, CandidateSearchResult, ContractRef, RunId
from .scope import AnalysisScope, SearchHint, VisualEventType
from .sources import AnalysisSourceResolver
from .visual import VisualVerificationResult


@dataclass(slots=True)
class SearchService:
    resolver: AnalysisSourceResolver
    provider: SearchProvider
    config: GeminiSearchConfig
    media_preparer: CoarseMediaPreparer
    monotonic: Callable[[], float] = time.monotonic
    ledger: SearchLedger = field(default_factory=SearchLedger)
    # Coarse run_id → 그 run을 만든 scope의 실행 상한(ms). Fine이 같은 상한을 이어받는다.
    _run_budget_ms: dict[RunId, int] = field(
        default_factory=dict, init=False, repr=False
    )

    def search_candidates_linked(self, scope: AnalysisScope) -> LinkedCoarseResult:
        """Return coarse search result together with source linkage.

        실행 상한은 scope.budget.max_latency_sec 하나이고(#149 A안), 시계는 이 호출
        시점에 시작한다.
        """
        budget_ms = scope.budget.max_latency_sec * 1000
        linked = search_coarse(
            scope,
            CoarseExecutionDependencies(
                resolver=self.resolver,
                provider=self.provider,
                config=self.config,
                ledger=self.ledger,
                media_preparer=self.media_preparer,
                deadline=RunDeadline(self.monotonic, budget_ms),
            ),
        )
        self._run_budget_ms[linked.result.analysis_run.run_id] = budget_ms
        return linked

    def search_candidates(self, scope: AnalysisScope) -> CandidateSearchResult:
        return self.search_candidates_linked(scope).result

    def verify_visual(
        self,
        input_ref: ContractRef,
        candidate: CandidateEvent,
        target_hint: SearchHint | None = None,
        event_type: str | VisualEventType = VisualEventType.SOLID_LINE_LANE_CHANGE,
        *,
        max_latency_sec: int | None = None,
    ) -> VisualVerificationResult:
        """Fine 실행 상한을 받아, 호출마다 새 시계로 센다.

        `max_latency_sec`를 넘기면 그 값을 쓴다 — Coarse와 다른 Worker/process에서도
        Fine을 실행할 수 있다(#226). 넘기지 않으면 이 객체가 실행한 Coarse scope의
        상한을 이어받는다. FINE_VERIFY는 COARSE_SEARCH와 다른 Job이라
        (contract-job-record-case-view.md §110) Coarse에서 쓴 시간이 깎이지 않는다.
        """
        # ponytail: 메모리 fallback은 Case/Runtime이 FINE_VERIFY Job에서 값을 넘기기 시작하면 제거.
        if max_latency_sec is not None:
            budget_ms = max_latency_sec * 1000
        else:
            budget_ms = self._run_budget_ms.get(candidate.run_id)
            if budget_ms is None:
                raise UnknownCandidateRunError(candidate.candidate_id, candidate.run_id)
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
            RunDeadline(self.monotonic, budget_ms),
        )
