"""근거 장면(`evidence.preview_ref`) — case가 선택 후보의 IncidentClip에서 frame 하나를 받는다(#446).

결정 `decisions/evidence-preview-frame.md`: 성공한 `INCIDENT_CLIP_BUILD` 반영 때 후보 대표 시각이 든 `asset_spans` 하나로
`STREAM_POSITION` frame을 발급받아 그 clip 결과에 남기고, CaseView는 선택 후보 · 현재 세대의 값을 읽는다. 하나로
정하지 못하면 `null`이고 notice는 없다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from daesingo.case import jobs
from daesingo.case.preview_frame import current_preview_frame_ref
from daesingo.case.reflection import ExecutionOutcome, reflect_execution
from daesingo.case.view import build_case_view
from tests.case.test_observation_chain import FakeReader, FakeTimelines, _after_coarse, _event, _fine, _reflect

CLIP_REF = "ic_1"
# 근거 장면 칸은 evidence가 있을 때 그려진다 — 조립된 EvidenceRecord 하나를 함께 넘긴다.
EVIDENCE = json.loads((Path(__file__).resolve().parents[2] / "data" / "mock" / "evidence" / "scenario_happy_001.json")
                      .read_text(encoding="utf-8"))["evidence_records"][0]


def _events_without_thumbnail() -> list[dict[str, Any]]:
    # 실제 경로처럼 Search 썸네일이 없다 — 화면 값은 case가 발급한 frame뿐이다.
    return [{**_event("cand_1", 1), "thumbnail_ref": None}, {**_event("cand_2", 2), "thumbnail_ref": None}]


def _clip(*, timeline_id: str = "tl_1", revision: int = 1, start: float = 1.0, end: float = 4.0,
          spans: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """`IncidentClip` JSON. 기본 span 하나는 timeline 0~10초 = 원본 `ms_0`의 20~30초다."""
    if spans is None:
        spans = [_span(0.0, 10.0, source_start=20.0)]
    return {
        "incident_clip_ref": CLIP_REF,
        "timeline_ref": {"timeline_id": timeline_id, "revision": revision},
        "timeline_range": {"start_sec": start, "end_sec": end},
        "source_provenance": {"asset_spans": spans},
    }


def _span(start: float, end: float, *, source_start: float = 0.0, stream: str = "ms_0") -> dict[str, Any]:
    return {
        "timeline_range": {"start_sec": start, "end_sec": end},
        "source_range": {"start_sec": source_start, "end_sec": source_start + end - start},
        "media_stream_ref": stream,
    }


class FakeIssuer:
    def __init__(self, clip: dict[str, Any], *, frame_ref: str | None = "fr_preview"):
        self.clip, self.frame_ref = clip, frame_ref
        self.calls: list[tuple[str, float]] = []

    def get_incident_clip(self, incident_clip_ref: str) -> dict[str, Any]:
        assert incident_clip_ref == CLIP_REF
        return self.clip

    def resolve_stream_frame(self, media_stream_ref: str, source_offset_sec: float) -> str | None:
        self.calls.append((media_stream_ref, source_offset_sec))
        return self.frame_ref


def _clip_reflected(issuer: FakeIssuer | None):
    """Coarse → rank=1(cand_1) Fine 관찰됨 → clip 성공 반영. cand_1 대표 시각은 2.5초다."""
    store, case_id, _, _ = _after_coarse(events=_events_without_thumbnail())
    fine = jobs.latest_job_record(store.get_case(case_id), "FINE_VERIFY")
    _reflect(store, case_id, fine, _fine("OBSERVED"))
    clip_job = jobs.latest_job_record(store.get_case(case_id), "INCIDENT_CLIP_BUILD")
    outcome = ExecutionOutcome(execution_id=f"exec_clip_{case_id}", job_id=clip_job["job_id"], case_id=case_id,
                               kind="INCIDENT_CLIP_BUILD", attempt=1, status="SUCCEEDED",
                               produced=({"kind": "result", "ref": "ref_clip"},))
    reflect_execution(outcome, store=store, reader=FakeReader({"INCIDENT_CLIP_BUILD": {"incident_clip_ref": CLIP_REF}}),
                      timelines=FakeTimelines(), preview_frames=issuer)
    return store, case_id, clip_job


def _view(store, case_id) -> dict[str, Any]:
    # 현재 선택 context에서 조립된 evidence만 투영된다(view `_belongs_to_current_selection`).
    case = store.get_case(case_id)
    selected = next(c.candidate_id for c in case.candidates if c.selected)
    evidence = {**EVIDENCE, "selection_rev": case.selection_rev,
                "basis": {**EVIDENCE["basis"], "candidate_ref": {**EVIDENCE["basis"]["candidate_ref"], "ref": selected}}}
    return build_case_view(case, evidence_record=evidence)


def _preview_ref(store, case_id) -> str | None:
    return _view(store, case_id)["evidence"]["preview_ref"]


def test_clip_reflection_issues_representative_frame_and_view_shows_it():
    issuer = FakeIssuer(_clip())

    store, case_id, clip_job = _clip_reflected(issuer)

    # 대표 2.5초 → 그 시각이 든 span의 원본 위치 20 + 2.5초
    assert issuer.calls == [("ms_0", 22.5)]
    assert store.get_case(case_id).observation_outcomes[clip_job["job_id"]]["preview_frame_ref"] == "fr_preview"
    assert current_preview_frame_ref(store.get_case(case_id)) == "fr_preview"
    assert _preview_ref(store, case_id) == "fr_preview"


def test_offset_uses_the_span_that_contains_the_representative_time():
    # 파일 경계: 0~2초는 ms_0, 2~10초는 ms_1(원본 0초부터). 2.5초는 ms_1의 0.5초다.
    issuer = FakeIssuer(_clip(spans=[_span(0.0, 2.0, source_start=8.0), _span(2.0, 10.0, stream="ms_1")]))

    _clip_reflected(issuer)

    assert issuer.calls == [("ms_1", 0.5)]


@pytest.mark.parametrize(
    "clip",
    [
        pytest.param(_clip(start=3.0, end=4.0), id="representative-outside-clip"),
        pytest.param(_clip(spans=[_span(3.0, 10.0)]), id="no-span-at-time"),
        pytest.param(_clip(spans=[_span(0.0, 10.0), _span(2.0, 3.0, stream="ms_1")]), id="two-spans-at-time"),
        pytest.param(_clip(timeline_id="tl_other"), id="other-timeline"),
        pytest.param(_clip(revision=2), id="other-revision"),
    ],
)
def test_undecidable_position_leaves_preview_null_without_decoding(clip):
    issuer = FakeIssuer(clip)

    store, case_id, clip_job = _clip_reflected(issuer)

    assert issuer.calls == []
    assert store.get_case(case_id).observation_outcomes[clip_job["job_id"]]["preview_frame_ref"] is None
    assert _preview_ref(store, case_id) is None
    assert store.get_case(case_id).job_records[-1]["kind"] == "OVERLAY_TIME_READ"  # 판독 후속 발주는 그대로


def test_recording_rejection_leaves_preview_null_and_no_notice():
    store, case_id, _ = _clip_reflected(FakeIssuer(_clip(), frame_ref=None))

    view = _view(store, case_id)
    assert view["evidence"]["preview_ref"] is None
    assert view["notices"] == []


def test_without_issuer_nothing_is_issued():
    # composition root가 꽂기 전 — 지금 develop의 Worker 그대로. 저장 값도 없고 화면도 비어 있다.
    store, case_id, clip_job = _clip_reflected(None)

    assert "preview_frame_ref" not in store.get_case(case_id).observation_outcomes[clip_job["job_id"]]
    assert _preview_ref(store, case_id) is None


def test_reselection_shows_only_the_selected_candidates_clip_frame():
    store, case_id, _ = _clip_reflected(FakeIssuer(_clip()))

    def select(candidate_id: str) -> None:
        case = store.load_for_update(case_id)
        for c in case.candidates:
            c.selected = c.candidate_id == candidate_id
        store.save(case)

    select("cand_2")
    assert current_preview_frame_ref(store.get_case(case_id)) is None  # 이전 후보 값이 남지 않는다
    select("cand_1")
    assert current_preview_frame_ref(store.get_case(case_id)) == "fr_preview"  # A→B→A는 A의 clip 값을 다시 쓴다
