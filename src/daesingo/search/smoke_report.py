from dataclasses import dataclass
from decimal import Decimal

from .coarse import LinkedCoarseResult
from .config import GeminiSearchConfig
from .execution import RunDeadline
from .ledger import SearchLedger
from .runs import CandidateEvent, ContractRef
from .smoke_models import (
    SmokeCandidateProjection,
    SmokeFailureCode,
    SmokeFailureStage,
    SmokeFineProjection,
    SmokeReport,
    SmokeReportV2,
    SmokeStageMetrics,
    SmokeStatus,
    SmokeUsage,
)
from .visual import PrimitiveState, VisualVerificationResult

_SIX_PLACES = Decimal("0.000001")


def _strip_trailing_zero(d: Decimal) -> Decimal:
    """Remove a single trailing zero if doing so is lossless and exponent < -6."""
    exp = d.as_tuple().exponent
    if isinstance(exp, int) and exp < -6:
        quantized = d.quantize(_SIX_PLACES)
        if quantized == d:
            return quantized
    return d


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
    ledger: SearchLedger

    def usage(self) -> SmokeUsage:
        records = self.ledger.records()
        usage_values = tuple(record.usage for record in records)
        complete_tokens = all(
            usage.input_tokens is not None
            and usage.output_tokens is not None
            and usage.thought_tokens is not None
            and usage.total_tokens is not None
            for usage in usage_values
        )
        costs = tuple(
            record.usage.cost_with_rates(
                self.config.input_usd_per_million,
                self.config.output_usd_per_million,
            )
            for record in records
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
                _strip_trailing_zero(
                    sum((cost or Decimal(0) for cost in costs), start=Decimal(0))
                )
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

    def build_v2(
        self,
        *,
        status: SmokeStatus,
        failure_stage: SmokeFailureStage | None,
        failure_code: SmokeFailureCode | None,
        coarse: LinkedCoarseResult | None,
        selected_source_ref: ContractRef | None,
        selected: CandidateEvent | None,
        fine: VisualVerificationResult | None,
        stages: tuple[SmokeStageMetrics, ...],
        deadline: RunDeadline,
    ) -> SmokeReportV2:
        coarse_candidates = (
            tuple(
                _project_candidate(c, coarse.source_ref)
                for c in coarse.result.candidates
            )
            if coarse is not None
            else ()
        )
        return SmokeReportV2(
            status=status,
            failure_stage=failure_stage,
            failure_code=failure_code,
            model=self.config.model,
            config_fingerprint=self.config.fingerprint,
            input_sha256=self.input_sha256,
            selected_source_ref=selected_source_ref,
            coarse_candidates=coarse_candidates,
            selected_candidate_id=selected.candidate_id if selected is not None else None,
            fine_result=_project_fine(fine) if fine is not None else None,
            stages=stages,
            usage=self.usage(),
            elapsed_ms=round(deadline.elapsed_ms()),
        )


def _project_candidate(
    candidate: CandidateEvent, source_ref: ContractRef
) -> SmokeCandidateProjection:
    return SmokeCandidateProjection(
        candidate_id=candidate.candidate_id,
        source_ref=source_ref,
        timeline_id=candidate.span.timeline_id,
        timeline_revision=candidate.span.timeline_revision,
        start_ms=candidate.span.start_ms,
        end_ms=candidate.span.end_ms,
        representative_ms=candidate.span.representative_ms,
        rank=candidate.rank,
        ranking_score=candidate.ranking_score,
        event_type_hint=candidate.event_type_hint,
    )


def _project_fine(fine: VisualVerificationResult) -> SmokeFineProjection:
    ev = fine.visual_evidence
    primitive_states: dict[PrimitiveState, int] = {}
    for p in ev.primitives:
        primitive_states[p.state] = primitive_states.get(p.state, 0) + 1
    return SmokeFineProjection(
        run_id=str(ev.run_id),
        input_ref=ev.input_ref,
        candidate_id=str(ev.candidate_id),
        verification=ev.verification,
        visual_event_type=ev.visual_event_type,
        target_association_status=ev.target.association_status,
        target_association_confidence=ev.target.association_confidence,
        primitive_states=primitive_states,
        temporal_offsets_ms=tuple(
            f.at_offset_ms for f in ev.temporal_facts if f.at_offset_ms is not None
        ),
        uncertainty_count=len(ev.uncertainties),
    )
