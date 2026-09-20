from dataclasses import dataclass
from decimal import Decimal

from .config import GeminiSearchConfig
from .runs import CandidateEvent
from .service import SearchService
from .smoke_models import (
    SmokeFailureStage,
    SmokeReport,
    SmokeStatus,
    SmokeUsage,
)
from .visual import VisualVerificationResult


@dataclass(frozen=True, slots=True)
class SmokeOutcome:
    status: SmokeStatus
    failure_stage: SmokeFailureStage | None = None
    candidates: tuple[CandidateEvent, ...] = ()
    selected: CandidateEvent | None = None
    fine: VisualVerificationResult | None = None


@dataclass(frozen=True, slots=True)
class SmokeReportBuilder:
    config: GeminiSearchConfig
    input_sha256: str
    service: SearchService

    def usage(self) -> SmokeUsage:
        records = self.service.ledger.records()
        usage_values = tuple(record.usage for record in records)
        costs = tuple(record.cost_usd for record in records)
        complete_tokens = all(
            usage.input_tokens is not None
            and usage.output_tokens is not None
            and usage.thought_tokens is not None
            and usage.total_tokens is not None
            for usage in usage_values
        )
        complete_cost = all(cost is not None for cost in costs)
        return SmokeUsage(
            latency_ms=sum(record.latency_ms for record in records),
            input_tokens=(
                sum(usage.input_tokens or 0 for usage in usage_values)
                if complete_tokens
                else None
            ),
            output_tokens=(
                sum(usage.output_tokens or 0 for usage in usage_values)
                if complete_tokens
                else None
            ),
            thought_tokens=(
                sum(usage.thought_tokens or 0 for usage in usage_values)
                if complete_tokens
                else None
            ),
            total_tokens=(
                sum(usage.total_tokens or 0 for usage in usage_values)
                if complete_tokens
                else None
            ),
            cost_usd=(
                sum((cost or Decimal(0) for cost in costs), start=Decimal(0))
                if complete_cost
                else None
            ),
        )

    def build(self, outcome: SmokeOutcome) -> SmokeReport:
        return SmokeReport(
            status=outcome.status,
            failure_stage=outcome.failure_stage,
            model=self.config.model,
            config_fingerprint=self.config.fingerprint,
            input_sha256=self.input_sha256,
            coarse_candidates=outcome.candidates,
            selected_candidate=outcome.selected,
            fine_result=outcome.fine,
            usage=self.usage(),
        )
