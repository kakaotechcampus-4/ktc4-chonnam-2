"""Search 전체 경로(Coarse → Fine) 시점별 실행기.

운영 Search가 바뀐 세 시점을 같은 코드·같은 데이터로 다시 돌린다. 시점 사이에
바뀐 설정(모델 · 전송 배속 · Fine 분기부 문장 · 단가)만 갈아 끼우고, 그 밖의
코드(검증·실패 처리 등 이후 수정)는 지금 것을 함께 쓴다 — 시점별 원래 코드
그대로가 아니라 「바뀐 요소」만 가른 비교다.

| 시점 | 근거 | 모델 | Coarse/Fine 원본 fps(배속) | Fine 분기부 문장 |
| --- | --- | --- | --- | --- |
| s1 | 9/18 baseline | gemini-3.8-flash | 1 / 1 (1x) | 없음 |
| s2 | 10/01 v3 늘린 영상 | gemini-3.8-flash | 2 / 4 (0.5x / 0.25x) | 없음 |
| s3 | 10/27 v4 argon (현재 운영) | gemini-4-argon | 2 / 4 | fine-gore-v1 |

s1의 Fine은 당시 2 fps·720p로 보냈지만 프록시가 1 fps·low로 처리했으므로
(gemini-proxy-video-sampling-2026-09-28) 모델 입력 기준 1 fps로 둔다.

Fine은 클립마다 점수 상위 FINE_TOP_K개 후보에만 돌린다. 사용자가 고른 후보에만
Fine이 도는 제품 흐름을 Recall@3과 같은 범위로 근사한다. 대상 힌트는 주지 않는다.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from typing import Final

from daesingo.search import (
    AnalysisScope,
    ResolvedAnalysisSource,
    SearchHint,
    SearchService,
    search_candidates,
    verify_visual,
)
from daesingo.search.config import GeminiSearchConfig
from daesingo.search.media import MediaPreparer
from daesingo.search.prompts import FINE_PROMPT, load_prompt
from daesingo.search.provider import (
    CoarseRequest,
    FineRequest,
    GeminiProvider,
    ProviderResult,
    SearchProvider,
    StructuredInvocation,
)
from daesingo.search.runs import CandidateEvent, ContractRef, RunOutcome
from daesingo.search.schemas import CoarseResponse, FineResponse
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
FINE_TOP_K: Final = 3
# 프록시 동시 호출. 클립 단위로 나눠 돌린다.
MAX_WORKERS: Final = 4
_EVENT_TYPES: Final = tuple(VisualEventType)
_FLASH_BASE_URL: Final = "https://mlapi.run/a90d8545-f100-4276-bf86-eb774596b91d/v1"
_ARGON_BASE_URL: Final = GeminiSearchConfig().base_url
# 1M 토큰당 USD. 사용자 제공 원화 단가(search-structure-confirmation-plan §6)를 ₩1,400/USD로 환산.
_FLASH_USD: Final = (0.815, 4.078)
_ARGON_USD: Final = (2.025, 10.125)


@dataclass(frozen=True, slots=True)
class Point:
    name: str
    model: str
    base_url: str
    coarse_fps: float
    fine_fps: float
    gore_note: bool
    usd_per_million: tuple[float, float]
    version: str

    @property
    def fine_prompt_version(self) -> str:
        return "fine-p3+fine-gore-v1" if self.gore_note else "fine-p3"


POINTS: Final = {
    "s1": Point("s1", "gemini-3.8-flash", _FLASH_BASE_URL, 1.0, 1.0, False, _FLASH_USD,
                "gemini-search-v2"),
    "s2": Point("s2", "gemini-3.8-flash", _FLASH_BASE_URL, 2.0, 4.0, False, _FLASH_USD,
                "gemini-search-v3"),
    "s3": Point("s3", "gemini-4-argon", _ARGON_BASE_URL, 2.0, 4.0, True, _ARGON_USD,
                "gemini-search-v4"),
}

_last_facts: dict[str, object] = {}


def config_for(point: Point) -> GeminiSearchConfig:
    return replace(
        GeminiSearchConfig(),
        model=point.model,
        base_url=point.base_url,
        coarse_fps=point.coarse_fps,
        fine_fps=point.fine_fps,
        input_usd_per_million=point.usd_per_million[0],
        output_usd_per_million=point.usd_per_million[1],
        version=point.version,
    )


class _NoGoreFineProvider:
    """Fine 프롬프트에서 분기부 문장(v4에서 추가)만 뺀다. 나머지 호출은 그대로 넘긴다."""

    def __init__(self, inner: GeminiProvider) -> None:
        self._inner = inner

    def search_coarse(self, request: CoarseRequest) -> ProviderResult[CoarseResponse]:
        return self._inner.search_coarse(request)

    def verify_fine(self, request: FineRequest) -> ProviderResult[FineResponse]:
        if request.media is None:
            raise ValueError("FineRequest.media required")
        suffix = request.event_type.value.lower().replace("_", "-")
        delta = load_prompt(f"fine-p3-{suffix}")
        prompt = f"{FINE_PROMPT.text.rstrip()}\n\n{delta.text.rstrip()}".format(
            event_type=request.event_type.value,
            target_hint=request.target_hint or "없음",
            start_sec=request.start_sec,
            end_sec=request.end_sec,
        )
        return self._inner.invoke_structured(
            StructuredInvocation(request.media, prompt, FineResponse, request.timeout_sec)
        )


def _build_service(prepared: gemini_preflight.PreparedEval, point: Point) -> SearchService:
    sources = {
        clip.clip_id: ResolvedAnalysisSource(
            source_ref=ContractRef(kind="analysis_source", ref=clip.clip_id),
            duration_sec=clip.duration_sec,
            timeline_id=clip.clip_id,
            timeline_revision=1,
        )
        for clip in prepared.clips
    }
    resolver = LocalAnalysisSourceResolver(
        sources_by_scope={clip_id: (source,) for clip_id, source in sources.items()},
        sources_by_ref=sources,
        paths_by_ref={clip.clip_id: clip.path for clip in prepared.clips},
    )
    config = config_for(point)
    provider: SearchProvider = GeminiProvider(prepared.api_key, config)
    if not point.gore_note:
        provider = _NoGoreFineProvider(provider)
    return SearchService(resolver, provider, config, MediaPreparer(config))


def _verify(service: SearchService, clip_id: str, candidate: CandidateEvent) -> dict[str, object]:
    if candidate.event_type_hint is None:
        return {"verification": None, "fine_error": "NO_EVENT_TYPE"}
    try:
        result = verify_visual(
            ContractRef(kind="analysis_source", ref=clip_id),
            service=service,
            event_type=candidate.event_type_hint,
            candidate=candidate,
        )
    except Exception as error:  # 한 후보의 실패로 전체 run을 잃지 않는다
        return {"verification": None, "fine_error": type(error).__name__}
    evidence = result.visual_evidence
    return {
        "verification": evidence.verification.value,
        "verified_event_type": (
            evidence.visual_event_type.value if evidence.visual_event_type else None
        ),
        "fine_target": evidence.target.described_as,
        "fine_facts": [fact.fact for fact in evidence.temporal_facts],
        "fine_error": None,
    }


def _run_clip(service: SearchService, clip: gemini_preflight.PreparedClip) -> dict[str, object]:
    result = search_candidates(_scope_for(clip), service=service)
    run_record = result.analysis_run
    ordered = sorted(result.candidates, key=lambda c: -c.ranking_score)
    fine_ids = {c.candidate_id for c in ordered[:FINE_TOP_K]}
    candidates = []
    for candidate in result.candidates:
        item: dict[str, object] = {
            "rank": candidate.rank,
            "score": candidate.ranking_score,
            "event_type": (
                candidate.event_type_hint.value if candidate.event_type_hint else None
            ),
            "t_start_sec": candidate.span.start_ms / 1000,
            "t_end_sec": candidate.span.end_ms / 1000,
            "representative_sec": candidate.span.representative_ms / 1000,
            "timeline_revision": candidate.span.timeline_revision,
            "summary": candidate.summary,
            "uncertainties": list(candidate.uncertainties),
            "verification": None,
        }
        if candidate.candidate_id in fine_ids:
            item.update(_verify(service, clip.clip_id, candidate))
        candidates.append(item)
    return {
        "clip_id": clip.clip_id,
        "outcome": run_record.outcome.value,
        "issues": [issue.code for issue in run_record.issues],
        "candidates": candidates,
    }


def run_point(point: Point, scope: dict[str, str]) -> list[dict[str, object]]:
    prepared = gemini_preflight.prepare(scope)
    service = _build_service(prepared, point)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        raw = list(pool.map(lambda clip: _run_clip(service, clip), prepared.clips))

    failed = [
        {"clip_id": item["clip_id"], "outcome": item["outcome"], "issues": item["issues"]}
        for item in raw
        if item["outcome"] != RunOutcome.SUCCEEDED.value
    ]
    fine_errors = [
        {"clip_id": item["clip_id"], "error": c["fine_error"]}
        for item in raw
        for c in item["candidates"]
        if c.get("fine_error")
    ]
    records = service.ledger.records()
    global _last_facts
    _last_facts = {
        "contract_version": CONTRACT_VERSION,
        "processed_duration_sec": sum(clip.duration_sec for clip in prepared.clips),
        "point": point.name,
        "model": service.config.model,
        "coarse_fps": point.coarse_fps,
        "fine_fps": point.fine_fps,
        "prompt_version": "coarse-p3",
        "fine_prompt_version": point.fine_prompt_version,
        "fine_top_k": FINE_TOP_K,
        "usd_per_million": list(point.usd_per_million),
        "config_version": service.config.version,
        "config_fingerprint": service.config.fingerprint,
        "sdk_version": prepared.sdk_version,
        # ledger의 Fine prompt_version은 search 코드 상수(gore 포함)라 s1·s2에서는
        # 실제와 다르다. 실제 Fine 프롬프트는 위 fine_prompt_version이다.
        "usage_records": [record.as_eval_fact() for record in records],
        "clips": [clip.clip_id for clip in prepared.clips],
        "scenarios": [clip.clip_id for clip in prepared.clips],
        "n_not_succeeded_clips": len(failed),
        "not_succeeded_clips": failed,
        "n_fine_errors": len(fine_errors),
        "fine_errors": fine_errors,
    }
    return raw


def run_s1(scope: dict[str, str]) -> list[dict[str, object]]:
    return run_point(POINTS["s1"], scope)


def run_s2(scope: dict[str, str]) -> list[dict[str, object]]:
    return run_point(POINTS["s2"], scope)


def run_s3(scope: dict[str, str]) -> list[dict[str, object]]:
    return run_point(POINTS["s3"], scope)


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
