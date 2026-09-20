from datetime import UTC, datetime
from decimal import Decimal
from math import isfinite
from uuid import uuid4

from .config import GeminiSearchConfig
from .errors import InvalidCoarseSpanError
from .ledger import SearchLedger, UsageRecord
from .prompts import COARSE_PROMPT
from .provider import CoarseRequest, ProviderResult, SearchProvider
from .runs import (
    AnalysisRun,
    CandidateEvent,
    CandidateId,
    CandidateSearchResult,
    CandidateSpan,
    ContractRef,
    Implementation,
    Money,
    Operation,
    RunId,
    RunOutcome,
    TokenUsage,
    UsageSummary,
)
from .schemas import CoarseCandidate, CoarseResponse
from .scope import AnalysisScope
from .sources import AnalysisSourceResolver, ResolvedAnalysisSource
from .usage import ProviderUsage


def search_coarse(
    scope: AnalysisScope,
    resolver: AnalysisSourceResolver,
    provider: SearchProvider,
    config: GeminiSearchConfig,
    ledger: SearchLedger,
) -> CandidateSearchResult:
    started = datetime.now(UTC)
    run_id = RunId(f"run_search_{uuid4().hex}")
    gathered: list[tuple[ResolvedAnalysisSource, CoarseCandidate]] = []
    usages: list[ProviderUsage] = []
    latency_ms = 0
    usage_refs: list[str] = []
    duration_sec = 0.0

    for source in resolver.resolve(scope):
        result = provider.search_coarse(CoarseRequest(source, scope.target_event_types))
        duration_sec += source.duration_sec
        latency_ms += result.latency_ms
        usages.append(result.usage)
        usage_ref = f"usage:{source.source_id}"
        usage_refs.append(usage_ref)
        ledger.append(_usage_record(source, result, config))
        gathered.extend((source, candidate) for candidate in result.response.candidates)

    ranked = sorted(gathered, key=lambda item: (-item[1].score, item[1].at_sec))
    candidates = tuple(
        _candidate(run_id, rank, source, candidate)
        for rank, (source, candidate) in enumerate(ranked, start=1)
    )
    completed = datetime.now(UTC)
    analysis_run = AnalysisRun(
        run_id=run_id,
        operation=Operation.CANDIDATE_SEARCH,
        input_ref=ContractRef(kind="analysis_scope", ref=scope.scope_id),
        implementation=Implementation(
            impl_id="search:gemini-coarse-p3",
            model_ref=config.model,
            prompt_version=COARSE_PROMPT.version,
            config_version=config.version,
        ),
        outcome=RunOutcome.SUCCEEDED,
        started_at=started,
        completed_at=completed,
        issues=(),
        usage_refs=tuple(usage_refs),
        usage_summary=_usage_summary(usages, duration_sec, latency_ms),
        contract_version="analysis-run-candidate-event/v1.1",
    )
    return CandidateSearchResult(analysis_run=analysis_run, candidates=candidates)


def _candidate(
    run_id: RunId,
    rank: int,
    source: ResolvedAnalysisSource,
    candidate: CoarseCandidate,
) -> CandidateEvent:
    values_are_finite = all(
        isfinite(value)
        for value in (
            candidate.span.start_sec,
            candidate.span.end_sec,
            candidate.at_sec,
        )
    )
    span_is_nonnegative = (
        candidate.span.start_sec >= 0
        and candidate.span.end_sec >= 0
        and candidate.at_sec >= 0
    )
    span_is_ordered = candidate.span.start_sec < candidate.span.end_sec
    span_overlaps_source = (
        candidate.span.start_sec < source.duration_sec
        and candidate.span.end_sec > 0
    )
    if not (
        values_are_finite
        and span_is_nonnegative
        and span_is_ordered
        and span_overlaps_source
    ):
        raise InvalidCoarseSpanError(
            source_id=source.source_id,
            start_sec=candidate.span.start_sec,
            end_sec=candidate.span.end_sec,
            at_sec=candidate.at_sec,
            duration_sec=source.duration_sec,
        )
    start = max(0.0, min(candidate.span.start_sec, source.duration_sec))
    end = max(start + 0.001, min(candidate.span.end_sec, source.duration_sec))
    representative = min(max(candidate.at_sec, start), end)
    uncertainties = tuple(
        fact
        for fact in candidate.observed
        if any(word in fact for word in ("불확실", "판별", "가림", "저해상도", "점선"))
    )
    return CandidateEvent(
        candidate_id=CandidateId(f"candidate_{uuid4().hex}"),
        run_id=run_id,
        span=CandidateSpan(
            timeline_id=source.timeline_id,
            timeline_revision=source.timeline_revision,
            start_ms=round(start * 1000),
            end_ms=round(end * 1000),
            representative_ms=round(representative * 1000),
        ),
        rank=rank,
        ranking_score=candidate.score,
        event_type_hint=candidate.event_type,
        summary="; ".join(candidate.observed) or "관찰 사실 없음",
        uncertainties=uncertainties,
        thumbnail_ref=None,
    )


def _usage_record(
    source: ResolvedAnalysisSource,
    result: ProviderResult[CoarseResponse],
    config: GeminiSearchConfig,
) -> UsageRecord:
    return UsageRecord(
        case_id=source.source_id,
        model=config.model,
        prompt_version=COARSE_PROMPT.version,
        prompt_fingerprint=COARSE_PROMPT.fingerprint,
        config_version=config.version,
        processed_duration_sec=source.duration_sec,
        latency_ms=result.latency_ms,
        usage=result.usage,
        cost_usd=result.usage.cost_usd,
    )


def _usage_summary(
    usages: list[ProviderUsage], duration_sec: float, latency_ms: int
) -> UsageSummary:
    complete = all(
        usage.input_tokens is not None
        and usage.output_tokens is not None
        and usage.thought_tokens is not None
        for usage in usages
    )
    token_usage = None
    if complete:
        input_tokens = sum(usage.input_tokens or 0 for usage in usages)
        output_tokens = sum(
            (usage.output_tokens or 0) + (usage.thought_tokens or 0) for usage in usages
        )
        token_usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        )
    costs = [usage.cost_usd for usage in usages]
    total_cost = None
    if all(cost is not None for cost in costs):
        total_cost = Money(
            amount=sum((cost or Decimal(0) for cost in costs), start=Decimal(0)),
            currency="USD",
        )
    return UsageSummary(
        processed_duration_ms=round(duration_sec * 1000),
        token_usage=token_usage,
        latency_ms=latency_ms,
        total_cost=total_cost,
    )
