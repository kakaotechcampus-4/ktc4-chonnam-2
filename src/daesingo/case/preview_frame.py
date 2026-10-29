"""근거 장면(`evidence.preview_ref`) — 선택 후보의 IncidentClip에서 대표 시각 frame 하나를 받는다(#446).

결정은 `docs/modules/case/decisions/evidence-preview-frame.md`. `INCIDENT_CLIP_BUILD` 반영(T2) 때 clip의 대표 시각이 든
`asset_spans` 하나를 골라 `STREAM_POSITION` frame을 발급받고, 그 clip job의 `observation_outcomes`에 남긴다. CaseView는
선택 후보 · 현재 세대의 가장 나중 성공 clip에 남은 값을 읽는다 — 조회 때는 디코딩하지 않는다(결정 5).

하나로 정하지 못하면 `None`이다(결정 6): 대표 시각이 없거나, clip timeline이 후보 span과 다르거나, 시각이 clip 밖이거나,
그 위치의 span이 0개 · 2개 이상이거나, recording이 발급을 거부했을 때. notice는 만들지 않는다.

## 여기 없는 것

- frame 발급 자체. `PreviewFrameIssuer`는 composition root가 recording 공개 함수로 꽂는다 — 어디서 디코딩할지(T2
  transaction 안 · clip handler · 별도 job)는 Runtime · Recording 결정이라, 꽂지 않으면 아무것도 하지 않는다.
"""
from __future__ import annotations

from typing import Any, Protocol

from daesingo.case.domain import CaseAggregate


class PreviewFrameIssuer(Protocol):
    """recording 공개 표면 중 근거 장면 발급에 쓰는 것. 모양은 recording 계약 그대로다."""

    def get_incident_clip(self, incident_clip_ref: str) -> dict[str, Any]:
        """`IncidentClip` JSON."""
        ...

    def resolve_stream_frame(self, media_stream_ref: str, source_offset_sec: float) -> str | None:
        """`resolve_frame({kind: STREAM_POSITION, ...})`의 `frame_ref`. recording이 그 위치를 거부하면 `None`이다 —
        그 밖의 예외는 그대로 올려 T2 rollback · retry에 맡긴다."""
        ...


def issue_preview_frame(case: CaseAggregate, clip_job_id: str, incident_clip_ref: str,
                        issuer: PreviewFrameIssuer) -> str | None:
    """clip job 입력의 후보 대표 시각으로 frame 하나를 발급받는다. 정하지 못하면 `None`."""
    source = case.observation_inputs.get(clip_job_id)
    candidate = None if source is None else next(
        (c for c in case.candidates if c.candidate_id == source["candidate_id"]), None)
    if candidate is None or candidate.representative_ms is None:
        return None
    clip = issuer.get_incident_clip(incident_clip_ref)
    timeline_ref, clip_range = clip.get("timeline_ref"), clip.get("timeline_range")
    if timeline_ref is None or clip_range is None:
        return None
    # 대표 시각은 후보 span의 timeline 좌표다 — clip이 다른 timeline · revision이면 같은 시각이 아니다.
    span = candidate.span or {}
    if (span.get("timeline_id"), span.get("timeline_revision")) != (timeline_ref["timeline_id"], timeline_ref["revision"]):
        return None
    at_sec = candidate.representative_ms / 1000
    if not clip_range["start_sec"] <= at_sec < clip_range["end_sec"]:
        return None
    # readout `IncidentClipFrames.read_at`과 같은 해석 — 그 시각이 든 원본 구간이 정확히 하나여야 한다.
    spans = [s for s in clip["source_provenance"]["asset_spans"]
             if s["timeline_range"]["start_sec"] <= at_sec < s["timeline_range"]["end_sec"]]
    if len(spans) != 1:
        return None
    hit = spans[0]
    offset = hit["source_range"]["start_sec"] + at_sec - hit["timeline_range"]["start_sec"]
    return issuer.resolve_stream_frame(hit["media_stream_ref"], offset)


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
