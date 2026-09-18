from datetime import UTC, datetime
from uuid import uuid4

from .config import GeminiSearchConfig
from .ledger import SearchLedger, UsageRecord
from .prompts import FINE_PROMPT, fine_prompt_for
from .provider import FineRequest, SearchProvider
from .runs import (
    AnalysisRun,
    CandidateId,
    ContractRef,
    Implementation,
    Operation,
    RunId,
    RunOutcome,
    UsageSummary,
)
from .scope import SearchHint, VisualEventType
from .sources import AnalysisSourceResolver
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
    target_hint: SearchHint | None,
    event_type: VisualEventType,
    resolver: AnalysisSourceResolver,
    provider: SearchProvider,
    config: GeminiSearchConfig,
    ledger: SearchLedger,
) -> VisualVerificationResult:
    source = resolver.resolve_reference(input_ref)
    started = datetime.now(UTC)
    run_id = RunId(f"run_fine_{uuid4().hex}")
    hint_text = ""
    if target_hint is not None:
        hint_text = "; ".join(
            filter(None, (target_hint.vehicle, target_hint.free_text))
        )
    result = provider.verify_fine(
        FineRequest(source, event_type, hint_text, 0.0, source.duration_sec)
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
        candidate_id=CandidateId(input_ref.ref)
        if input_ref.kind == "candidate"
        else None,
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
