from typing import Final

from daesingo.search import (
    AnalysisScope,
    ResolvedAnalysisSource,
    SearchHint,
    SearchService,
    build_gemini_search_service,
    search_candidates,
)
from daesingo.search.scope import (
    SearchBudget,
    TimelineRef,
    TimelineRelativeTimeRange,
    TimeRangeKind,
    VisualEventType,
)
from daesingo.search.sources import StaticAnalysisSourceResolver
from eval import gemini_preflight

IMPL_VERSION = "v1"
CONTRACT_VERSION = "analysis-run-candidate-event/v1.1"
_EVENT_TYPES: Final = tuple(VisualEventType)
_last_facts: dict[str, object] = {}


def _build_service(prepared: gemini_preflight.PreparedEval) -> SearchService:
    sources = {
        clip.clip_id: (
            ResolvedAnalysisSource(
                source_id=clip.clip_id,
                path=clip.path,
                duration_sec=clip.duration_sec,
                timeline_id=clip.clip_id,
                timeline_revision=1,
            ),
        )
        for clip in prepared.clips
    }
    resolver = StaticAnalysisSourceResolver(sources_by_scope=sources, sources_by_ref={})
    return build_gemini_search_service(prepared.api_key, resolver)


def run(scope: dict[str, str]) -> list[dict[str, object]]:
    prepared = gemini_preflight.prepare(scope)
    service = _build_service(prepared)
    raw: list[dict[str, object]] = []
    for clip in prepared.clips:
        result = search_candidates(_scope_for(clip), service=service)
        candidates = [
            {
                "rank": candidate.rank,
                "score": candidate.ranking_score,
                "event_type": (
                    candidate.event_type_hint.value
                    if candidate.event_type_hint
                    else None
                ),
                "t_start_sec": candidate.span.start_ms / 1000,
                "t_end_sec": candidate.span.end_ms / 1000,
                "representative_sec": candidate.span.representative_ms / 1000,
                "timeline_revision": candidate.span.timeline_revision,
                "summary": candidate.summary,
                "uncertainties": list(candidate.uncertainties),
            }
            for candidate in result.candidates
        ]
        raw.append({"clip_id": clip.clip_id, "candidates": candidates})

    records = service.ledger.records()
    global _last_facts
    _last_facts = {
        "contract_version": CONTRACT_VERSION,
        "processed_duration_sec": sum(clip.duration_sec for clip in prepared.clips),
        "model": service.config.model,
        "prompt_version": "coarse-p3",
        "prompt_fingerprint": records[0].prompt_fingerprint if records else None,
        "config_version": service.config.version,
        "config_fingerprint": service.config.fingerprint,
        "sdk_version": prepared.sdk_version,
        "usage_records": [record.as_eval_fact() for record in records],
        "provider_usage_records": [record.as_eval_fact() for record in records],
        "clips": [clip.clip_id for clip in prepared.clips],
        "scenarios": [clip.clip_id for clip in prepared.clips],
    }
    return raw


def run_facts(scope: dict[str, str]) -> dict[str, object]:
    del scope
    return dict(_last_facts)


def _scope_for(clip: gemini_preflight.PreparedClip) -> AnalysisScope:
    return AnalysisScope(
        scope_id=clip.clip_id,
        time_ranges=(
            TimelineRelativeTimeRange(
                kind=TimeRangeKind.TIMELINE_RELATIVE,
                timeline_ref=TimelineRef(timeline_id=clip.clip_id, revision=1),
                start_ms=0,
                end_ms=round(clip.duration_sec * 1000),
            ),
        ),
        target_event_types=_EVENT_TYPES,
        hint=SearchHint(vehicle=None, free_text=None),
        budget=SearchBudget(max_cost_krw=100_000, max_latency_sec=3600),
        contract_version="1.1.0",
    )
