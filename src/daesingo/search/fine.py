from datetime import UTC, datetime
from uuid import uuid4

from .config import GeminiSearchConfig
from .errors import InvalidFineSpanError
from .execution import RunDeadline
from .ledger import SearchLedger, UsageRecord
from .media import PreparedMedia
from .media_contract import CoarseMediaPreparer
from .prompts import FINE_PROMPT, fine_prompt_for
from .provider import FineRequest, SearchProvider
from .runs import (
    AnalysisRun,
    CandidateEvent,
    ContractRef,
    Implementation,
    Operation,
    RunId,
    RunOutcome,
    UsageSummary,
)
from .schemas import FineTemporalFact
from .scope import SearchHint, VisualEventType
from .smoke_errors import ProviderPayloadError
from .sources import AnalysisSourceResolver, CandidateSourceLink
from .visual import (
    Primitive,
    Target,
    TemporalFact,
    Uncertainty,
    VisualEvidence,
    VisualVerificationResult,
)

_LEGACY_EVENT_NAMES = {"LANE_CHANGE": VisualEventType.SOLID_LINE_LANE_CHANGE}


def _rebase_temporal_facts(
    facts: tuple[FineTemporalFact, ...],
    prepared: PreparedMedia,
    source_duration_sec: float,
    candidate: CandidateEvent,
) -> tuple[TemporalFact, ...]:
    clip_duration_ms = round(prepared.duration_sec * 1000)
    origin_start_ms = round(prepared.origin_start_sec * 1000)
    source_duration_ms = round(source_duration_sec * 1000)
    rebased_offsets: list[int] = []
    rebased_facts: list[TemporalFact] = []
    for item in facts:
        offset = item.at_offset_ms
        if offset is None:
            rebased_facts.append(
                TemporalFact(
                    at_offset_ms=None,
                    fact=item.fact,
                    evidence_refs=item.evidence_refs,
                )
            )
            continue
        if offset < 0 or offset > clip_duration_ms:
            raise ProviderPayloadError("Fine temporal offset outside prepared clip")
        rebased = offset + origin_start_ms
        if rebased < 0 or rebased > source_duration_ms:
            raise ProviderPayloadError("Fine temporal offset outside source duration")
        if not candidate.span.start_ms <= rebased <= candidate.span.end_ms:
            raise ProviderPayloadError("Fine temporal offset outside candidate window")
        rebased_offsets.append(rebased)
        rebased_facts.append(
            TemporalFact(
                at_offset_ms=rebased,
                fact=item.fact,
                evidence_refs=item.evidence_refs,
            )
        )
    if rebased_offsets and candidate.span.representative_ms not in rebased_offsets:
        raise ProviderPayloadError("Fine temporal offsets do not link representative")
    return tuple(rebased_facts)


def normalize_event_type(value: str | VisualEventType) -> VisualEventType:
    if isinstance(value, VisualEventType):
        return value
    legacy = _LEGACY_EVENT_NAMES.get(value)
    return legacy if legacy is not None else VisualEventType(value)


def verify_fine(
    input_ref: ContractRef,
    candidate: CandidateEvent,
    target_hint: SearchHint | None,
    event_type: VisualEventType,
    resolver: AnalysisSourceResolver,
    provider: SearchProvider,
    config: GeminiSearchConfig,
    ledger: SearchLedger,
    media_preparer: CoarseMediaPreparer,
    deadline: RunDeadline,
) -> VisualVerificationResult:
    source = resolver.resolve_reference(input_ref)
    CandidateSourceLink(source_ref=input_ref, candidate=candidate).validate(source)
    start_sec = max(
        0.0,
        candidate.span.start_ms / 1000 - config.fine_padding_sec,
    )
    end_sec = min(
        source.duration_sec,
        candidate.span.end_ms / 1000 + config.fine_padding_sec,
    )
    if start_sec >= end_sec:
        raise InvalidFineSpanError(
            source_ref=input_ref,
            candidate_id=candidate.candidate_id,
            start_sec=start_sec,
            end_sec=end_sec,
        )
    started = datetime.now(UTC)
    run_id = RunId(f"run_fine_{uuid4().hex}")
    hint_text = ""
    if target_hint is not None:
        hint_text = "; ".join(
            filter(None, (target_hint.vehicle, target_hint.free_text))
        )
    with (
        resolver.open_source(input_ref) as media_input,
        media_preparer.prepare_fine(
            media_input, start_sec, end_sec, deadline
        ) as prepared,
    ):
        deadline.check()
        result = provider.verify_fine(
            FineRequest(
                source,
                event_type,
                hint_text,
                start_sec,
                end_sec,
                media=prepared,
                timeout_sec=deadline.remaining_sec(),
            )
        )
        ledger.append(
            UsageRecord(
                case_id=source.source_id,
                model=config.model,
                prompt_version=FINE_PROMPT.version,
                prompt_fingerprint=fine_prompt_for(event_type).fingerprint,
                config_version=config.version,
                processed_duration_sec=source.duration_sec,
                latency_ms=result.latency_ms,
                usage=result.usage,
                cost_usd=result.usage.cost_with_rates(
                    config.input_usd_per_million,
                    config.output_usd_per_million,
                ),
                prepared_media_bytes=prepared.byte_size,
                prepared_duration_ms=round(prepared.duration_sec * 1000),
            )
        )
        response = result.response
        temporal_facts = _rebase_temporal_facts(
            response.temporal_facts,
            prepared,
            source.duration_sec,
            candidate,
        )
    analysis_run = AnalysisRun(
        run_id=run_id,
        operation=Operation.VISUAL_VERIFY,
        input_ref=input_ref,
        implementation=Implementation(
            impl_id="search:gemini-fine-p2",
            model_ref=config.model,
            prompt_version=FINE_PROMPT.version,
            config_version=config.version,
        ),
        outcome=RunOutcome.SUCCEEDED,
        started_at=started,
        completed_at=datetime.now(UTC),
        issues=(),
        usage_refs=(f"usage:{source.source_id}",),
        usage_summary=UsageSummary(
            processed_duration_ms=round(source.duration_sec * 1000),
            token_usage=None,
            latency_ms=result.latency_ms,
            total_cost=None,
        ),
        contract_version="analysis-run-candidate-event/v1.1",
    )
    evidence = VisualEvidence(
        schema_version="visual-evidence/v1.0",
        visual_evidence_id=f"evidence_{uuid4().hex}",
        run_id=run_id,
        input_ref=input_ref,
        candidate_id=candidate.candidate_id,
        verification=response.verification,
        visual_event_type=response.visual_event_type,
        target=Target.model_validate(response.target.model_dump()),
        primitives=tuple(
            Primitive.model_validate(item.model_dump()) for item in response.primitives
        ),
        temporal_facts=temporal_facts,
        uncertainties=tuple(
            Uncertainty.model_validate(item.model_dump())
            for item in response.uncertainties
        ),
        legal_status=None,
    )
    return VisualVerificationResult(analysis_run=analysis_run, visual_evidence=evidence)
