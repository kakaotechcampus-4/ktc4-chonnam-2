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

from typing import Any

from daesingo.case.domain import CaseAggregate


def preview_frame_position(clip: dict[str, Any], span: dict[str, Any] | None,
                           representative_ms: int | None) -> tuple[str, float] | None:
    """후보 대표 시각이 든 clip 원본 위치 `(media_stream_ref, source_offset_sec)`. 정하지 못하면 `None`.

    `clip`은 `IncidentClip` JSON, `span`은 후보 span(`timeline_id` · `timeline_revision`)이다."""
    if representative_ms is None:
        return None
    timeline_ref, clip_range = clip.get("timeline_ref"), clip.get("timeline_range")
    if timeline_ref is None or clip_range is None:
        return None
    # 대표 시각은 후보 span의 timeline 좌표다 — clip이 다른 timeline · revision이면 같은 시각이 아니다.
    span = span or {}
    if (span.get("timeline_id"), span.get("timeline_revision")) != (timeline_ref["timeline_id"], timeline_ref["revision"]):
        return None
    at_sec = representative_ms / 1000
    if not clip_range["start_sec"] <= at_sec < clip_range["end_sec"]:
        return None
    # readout `IncidentClipFrames.read_at`과 같은 해석 — 그 시각이 든 원본 구간이 정확히 하나여야 한다.
    spans = [s for s in clip["source_provenance"]["asset_spans"]
             if s["timeline_range"]["start_sec"] <= at_sec < s["timeline_range"]["end_sec"]]
    if len(spans) != 1:
        return None
    hit = spans[0]
    return hit["media_stream_ref"], hit["source_range"]["start_sec"] + at_sec - hit["timeline_range"]["start_sec"]


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
