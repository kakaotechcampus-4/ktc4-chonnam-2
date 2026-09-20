from datetime import UTC, datetime
from uuid import uuid4

from .config import GeminiSearchConfig
from .errors import InvalidFineSpanError
from .ledger import SearchLedger, UsageRecord
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
from .scope import SearchHint, VisualEventType
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
    result = provider.verify_fine(
        FineRequest(source, event_type, hint_text, start_sec, end_sec)
    )
    ledger.append(
        UsageRecord(
            case_id=source.source_id,
            model=config.model,
            prompt_version=FINE_PROMPT.version,
            prompt_fingerprint=fine_prompt_for(event_type).fingerprint,
            config_version=config.version,
            processed_duration_sec=end_sec - start_sec,
            latency_ms=result.latency_ms,
            usage=result.usage,
            cost_usd=result.usage.cost_usd,
        )
    )
    response = result.response
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
            processed_duration_ms=round((end_sec - start_sec) * 1000),
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
        temporal_facts=tuple(
            TemporalFact.model_validate(item.model_dump())
            for item in response.temporal_facts
        ),
        uncertainties=tuple(
            Uncertainty.model_validate(item.model_dump())
            for item in response.uncertainties
        ),
        legal_status=None,
    )
    return VisualVerificationResult(analysis_run=analysis_run, visual_evidence=evidence)
