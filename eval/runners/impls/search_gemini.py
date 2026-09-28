from typing import Final

from daesingo.search import (
    AnalysisScope,
    ResolvedAnalysisSource,
    SearchHint,
    SearchService,
    build_gemini_search_service,
    search_candidates,
)
from daesingo.search.runs import ContractRef, RunOutcome
from daesingo.search.scope import (
    SearchBudget,
    TimelineRef,
    TimelineRelativeTimeRange,
    TimeRangeKind,
    VisualEventType,
)
from daesingo.search.sources import LocalAnalysisSourceResolver
from eval import gemini_preflight

IMPL_VERSION = "v1"
CONTRACT_VERSION = "analysis-run-candidate-event/v1.1"
_EVENT_TYPES: Final = tuple(VisualEventType)
_last_facts: dict[str, object] = {}


def _build_service(
    prepared: gemini_preflight.PreparedEval, clip: gemini_preflight.PreparedClip
) -> SearchService:
    # 클립마다 서비스를 새로 만든다. 서비스가 가진 실행 시간 상한은 생성 시점부터
    # 흐르므로, 하나를 123클립이 공유하면 뒤 클립이 조용히 FAILED가 된다(#149).
    source = ResolvedAnalysisSource(
        ContractRef(kind="analysis_source", ref=clip.clip_id),
        clip.duration_sec,
        clip.clip_id,
        1,
    )
    resolver = LocalAnalysisSourceResolver(
        {clip.clip_id: (source,)}, {clip.clip_id: source}, {clip.clip_id: clip.path}
    )
    return build_gemini_search_service(prepared.api_key, resolver)


def run(scope: dict[str, str]) -> list[dict[str, object]]:
    prepared = gemini_preflight.prepare(scope)
    raw: list[dict[str, object]] = []
    records = []
    failed: list[dict[str, object]] = []
    config = None
    for clip in prepared.clips:
        service = _build_service(prepared, clip)
        config = service.config
        result = search_candidates(_scope_for(clip), service=service)
        records.extend(service.ledger.records())
        run_record = result.analysis_run
        if run_record.outcome is not RunOutcome.SUCCEEDED:
            failed.append(
                {
                    "clip_id": clip.clip_id,
                    "outcome": run_record.outcome.value,
                    "issues": [issue.code for issue in run_record.issues],
                }
            )
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
        raw.append(
            {
                "clip_id": clip.clip_id,
                "outcome": run_record.outcome.value,
                "candidates": candidates,
            }
        )

    global _last_facts
    _last_facts = {
        "contract_version": CONTRACT_VERSION,
        "processed_duration_sec": sum(clip.duration_sec for clip in prepared.clips),
        "model": config.model if config else None,
        "prompt_version": "coarse-p3",
        "prompt_fingerprint": records[0].prompt_fingerprint if records else None,
        "config_version": config.version if config else None,
        "config_fingerprint": config.fingerprint if config else None,
        "sdk_version": prepared.sdk_version,
        "usage_records": [
            record.as_eval_fact() for record in records if record.cost_usd is not None
        ],
        "provider_usage_records": [record.as_eval_fact() for record in records],
        "clips": [clip.clip_id for clip in prepared.clips],
        "scenarios": [clip.clip_id for clip in prepared.clips],
        # FAILED/PARTIAL 클립은 후보 0개로 채점된다. 지표만 보고 원인을 오해하지
        # 않도록 어떤 클립이 왜 실패했는지 남긴다.
        "n_not_succeeded_clips": len(failed),
        "not_succeeded_clips": failed,
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
