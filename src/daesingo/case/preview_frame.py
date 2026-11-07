"""근거 장면(`evidence.preview_ref`) — 선택 후보의 IncidentClip에서 대표 시각 frame 하나를 받는다(#446).

결정은 `docs/modules/case/decisions/evidence-preview-frame.md`. frame은 `INCIDENT_CLIP_BUILD` handler가 clip을 만든 뒤
T1 전에 발급해 produced 결과(`preview_frame_ref`)에 싣고, case는 T2 반영 때 그 값을 clip job의 `observation_outcomes`에
남기기만 한다(결정 5) — T2 transaction · CaseView 조회에서는 디코딩하지 않는다. CaseView는 선택 후보 · 현재 세대의
가장 나중 성공 clip에 남은 값을 읽는다.

어느 위치의 frame인지는 case가 정한다 — handler는 `preview_frame_position`으로 위치를 받아 recording
`resolve_frame(STREAM_POSITION)`에 넘긴다. 하나로 정하지 못하면 `None`이다(결정 6): 대표 시각이 없거나, clip timeline이
후보 span과 다르거나, 시각이 clip 밖이거나, 그 위치의 span이 0개 · 2개 이상일 때. notice는 만들지 않는다.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from daesingo.case.domain import CaseAggregate


def preview_frame_position(clip: dict[str, Any], span: dict[str, Any] | None,
                           representative_ms: int | None) -> tuple[str, float] | None:
    """후보 대표 시각이 든 clip 원본 위치 `(media_stream_ref, source_offset_sec)`. 정하지 못하면 `None`.

    `clip`은 `IncidentClip` JSON, `span`은 후보 span(`timeline_id` · `timeline_revision`)이다."""
    provenance = clip.get("source_provenance") or {}
    return _source_position(clip.get("timeline_ref"), clip.get("timeline_range"), provenance.get("asset_spans", []),
                            span, representative_ms)


def candidate_frame_position(resolution: dict[str, Any], span: dict[str, Any] | None,
                             representative_ms: int | None) -> tuple[str, float] | None:
    """썸네일 후보 대표 시각의 원본 위치(#523). `preview_frame_position`과 같은 해석을 후보 자기 구간에 한다.

    `resolution`은 그 후보 구간의 recording `SpanResolution` JSON이다 — 선택 후보 clip의 provenance에 다른 후보를
    맞추지 않는다. 실패한 resolution(span 없음)도 `None`이다."""
    return _source_position(resolution.get("timeline_ref"), resolution.get("requested_range"),
                            resolution.get("spans", []), span, representative_ms)


def _source_position(timeline_ref: dict[str, Any] | None, timeline_range: dict[str, Any] | None,
                     asset_spans: list[dict[str, Any]], span: dict[str, Any] | None,
                     representative_ms: int | None) -> tuple[str, float] | None:
    if representative_ms is None or timeline_ref is None or timeline_range is None:
        return None
    # 대표 시각은 후보 span의 timeline 좌표다 — 다른 timeline · revision이면 같은 시각이 아니다.
    span = span or {}
    if (span.get("timeline_id"), span.get("timeline_revision")) != (timeline_ref["timeline_id"], timeline_ref["revision"]):
        return None
    at_sec = representative_ms / 1000
    if not timeline_range["start_sec"] <= at_sec < timeline_range["end_sec"]:
        return None
    # readout `IncidentClipFrames.read_at`과 같은 해석 — 그 시각이 든 원본 구간이 정확히 하나여야 한다.
    hits = [s for s in asset_spans if s["timeline_range"]["start_sec"] <= at_sec < s["timeline_range"]["end_sec"]]
    if len(hits) != 1:
        return None
    hit = hits[0]
    return hit["media_stream_ref"], hit["source_range"]["start_sec"] + at_sec - hit["timeline_range"]["start_sec"]


# 썸네일을 만드는 후보 순위 상한 — Fine top-k와 같은 3(#523). Runtime도 rank 1~3 · 최대 3개만 받는다(#527).
THUMBNAIL_MAX_RANK = 3


def thumbnail_candidate_ids(case: CaseAggregate, observation_input: dict[str, Any],
                            events: Iterable[Any]) -> tuple[str, ...]:
    """clip handler가 썸네일을 함께 발급할 후보 ID — 현재 세대 rank 1~3, rank 순(#523).

    3개보다 적으면 있는 만큼만 돌려준다. 위치를 정할 수 없는 후보(rebase로 stale · span 없음 · 그 세대 Coarse 결과에
    없음)는 빼고 4위로 채우지 않는다. 입력이 현재 세대가 아니면 빈 tuple이다. `events`는 그 세대의 search
    `CandidateEvent`(모델 또는 JSON)다."""
    if observation_input.get("generation_job_id") != case.current_generation_job_id():
        return ()
    in_generation = {e["candidate_id"] if isinstance(e, dict) else e.candidate_id for e in events}
    chosen = sorted((c for c in case.candidates
                     if c.rank is not None and 1 <= c.rank <= THUMBNAIL_MAX_RANK and not c.stale_revision
                     and c.span is not None and c.candidate_id in in_generation),
                    key=lambda c: c.rank)
    return tuple(c.candidate_id for c in chosen)


_SPAN_KEYS = ("timeline_id", "timeline_revision", "start_ms", "end_ms", "representative_ms")


def _field(item: Any, name: str) -> Any:
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)


def coarse_thumbnail_candidate_ids(events: Iterable[Any]) -> tuple[str, ...]:
    """Coarse handler가 T1 전에 썸네일을 발급할 후보 ID — 그 Coarse 결과의 rank 1~3, rank 순(#583 E안).

    후보 목록이 아직 case에 반영되기 전이라 case 상태가 아니라 결과 `CandidateEvent`(모델 또는 JSON)만 본다.
    위치를 정할 수 없는 후보(span 다섯 값 중 하나라도 없음 · 대표 시각 없음)는 빼고 4위로 채우지 않는다 —
    `thumbnail_candidate_ids`와 같은 원칙이다. 위치는 후보마다 `candidate_frame_position`으로 정한다."""
    chosen = []
    for event in events:
        rank, span = _field(event, "rank"), _field(event, "span")
        if span is not None and not isinstance(span, dict):
            span = span.model_dump(mode="json")
        if (isinstance(rank, int) and 1 <= rank <= THUMBNAIL_MAX_RANK and span is not None
                and all(span.get(key) is not None for key in _SPAN_KEYS)):
            chosen.append((rank, _field(event, "candidate_id")))
    return tuple(candidate_id for _, candidate_id in sorted(chosen, key=lambda item: item[0]))


def coarse_frame_refs(content: dict[str, Any]) -> dict[str, str | None]:
    """Coarse 결과에 실린 후보별 썸네일(`candidate_frame_refs`)을 검증해 돌려준다(#583 E안).

    키가 없거나 `null`이면 이전 형식 · 발급 없음이라 `{}`다. 값은 `frame_ref` 문자열 또는 `null`(거부된 frame)이다.
    case가 고르지 않은 후보(`coarse_thumbnail_candidate_ids` 밖)의 값이나 다른 모양은 배선 오류(`ValueError`)다 —
    잘못 실린 frame을 조용히 버리면 Runtime 쪽 대조 실수가 보이지 않는다."""
    refs = content.get("candidate_frame_refs")
    if refs is None:
        return {}
    if not isinstance(refs, dict):
        raise ValueError(f"candidate_frame_refs는 후보 ID → frame_ref 매핑이어야 한다: {type(refs).__name__}")
    allowed = set(coarse_thumbnail_candidate_ids(content.get("candidate_events") or []))
    unknown = set(refs) - allowed
    if unknown:
        raise ValueError(f"case가 고르지 않은 후보의 썸네일: {sorted(unknown)!r}")
    for candidate_id, ref in refs.items():
        if ref is not None and (not isinstance(ref, str) or not ref):
            raise ValueError(f"잘못된 frame_ref: {candidate_id!r} → {ref!r}")
    return dict(refs)


def current_preview_frame_ref(case: CaseAggregate) -> str | None:
    """선택 후보 · 현재 세대의 가장 나중 성공 clip에 남은 근거 장면. 없으면 `None`.

    재선택하면 그 후보의 clip 값만 본다 — 이전 후보 값이 남지 않고, A→B→A면 A의 clip 값을 다시 쓴다."""
    selected = next((c.candidate_id for c in case.candidates if c.selected), None)
    generation = case.current_generation_job_id()
    if selected is None or generation is None:
        return None
    for record in reversed(case.job_records):
        source = case.observation_inputs.get(record["job_id"])
        outcome = case.observation_outcomes.get(record["job_id"])
        if (record["kind"] == "INCIDENT_CLIP_BUILD" and source is not None and outcome is not None
                and source["candidate_id"] == selected and source["generation_job_id"] == generation
                and outcome["status"] == "SUCCEEDED"):
            return outcome.get("preview_frame_ref")
    return None


def current_candidate_frame_refs(case: CaseAggregate) -> dict[str, str]:
    """현재 세대 성공 clip들이 남긴 후보별 썸네일(#523). 발급 못 한 후보(`null`)는 빠진다.

    다른 후보를 고르면 그 후보의 clip이 다시 발급한다 — 나중 clip의 frame이 앞의 것을 덮고, 나중 clip의 `null`은
    앞서 만든 frame을 지우지 않는다. 다른 세대 clip의 값은 쓰지 않는다."""
    generation = case.current_generation_job_id()
    refs: dict[str, str] = {}
    if generation is None:
        return refs
    for record in case.job_records:
        source = case.observation_inputs.get(record["job_id"])
        outcome = case.observation_outcomes.get(record["job_id"])
        if (record["kind"] == "INCIDENT_CLIP_BUILD" and source is not None and outcome is not None
                and source["generation_job_id"] == generation and outcome["status"] == "SUCCEEDED"):
            refs.update({k: v for k, v in (outcome.get("candidate_frame_refs") or {}).items() if v is not None})
    return refs
