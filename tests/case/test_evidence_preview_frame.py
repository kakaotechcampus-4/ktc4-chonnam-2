"""근거 장면(`evidence.preview_ref`) — case가 선택 후보의 IncidentClip에서 frame 하나를 받는다(#446).

결정 `decisions/evidence-preview-frame.md`: handler가 후보 대표 시각이 든 `asset_spans` 하나(`preview_frame_position`)로
`STREAM_POSITION` frame을 발급해 clip 결과에 싣고, case는 성공한 `INCIDENT_CLIP_BUILD` 반영 때 그 값을 남기며, CaseView는
선택 후보 · 현재 세대의 값을 읽는다. 하나로 정하지 못하면 `null`이고 notice는 없다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from daesingo.case import jobs
from daesingo.case.preview_frame import current_preview_frame_ref, preview_frame_position
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


_ABSENT = object()
# cand_1(`_event("cand_1", 1)`)의 span · 대표 시각 2.5초 — 위치 해석 단위 테스트 입력.
SPAN = {"timeline_id": "tl_1", "timeline_revision": 1}
REPRESENTATIVE_MS = 2500


def _clip_reflected(preview_frame_ref: Any = "fr_preview"):
    """Coarse → rank=1(cand_1) Fine 관찰됨 → clip 성공 반영. handler 결과에 `preview_frame_ref`를 싣는다(`_ABSENT`면 키 없음)."""
    store, case_id, _, _ = _after_coarse(events=_events_without_thumbnail())
    fine = jobs.latest_job_record(store.get_case(case_id), "FINE_VERIFY")
    _reflect(store, case_id, fine, _fine("OBSERVED"))
    clip_job = jobs.latest_job_record(store.get_case(case_id), "INCIDENT_CLIP_BUILD")
    outcome = ExecutionOutcome(execution_id=f"exec_clip_{case_id}", job_id=clip_job["job_id"], case_id=case_id,
                               kind="INCIDENT_CLIP_BUILD", attempt=1, status="SUCCEEDED",
                               produced=({"kind": "result", "ref": "ref_clip"},))
    content = {"incident_clip_ref": CLIP_REF}
    if preview_frame_ref is not _ABSENT:
        content["preview_frame_ref"] = preview_frame_ref
    reflect_execution(outcome, store=store, reader=FakeReader({"INCIDENT_CLIP_BUILD": content}), timelines=FakeTimelines())
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


def test_cand_1_fixture_matches_position_inputs():
    # 아래 위치 테스트의 SPAN · 대표 시각이 반영 테스트의 cand_1과 같은 값인지 고정한다.
    event = _event("cand_1", 1)
    assert {k: event["span"][k] for k in SPAN} == SPAN
    assert event["span"]["representative_ms"] == REPRESENTATIVE_MS


def test_position_is_source_offset_of_representative_time():
    # 대표 2.5초 → 그 시각이 든 span의 원본 위치 20 + 2.5초
    assert preview_frame_position(_clip(), SPAN, REPRESENTATIVE_MS) == ("ms_0", 22.5)


def test_position_uses_the_span_that_contains_the_representative_time():
    # 파일 경계: 0~2초는 ms_0, 2~10초는 ms_1(원본 0초부터). 2.5초는 ms_1의 0.5초다.
    clip = _clip(spans=[_span(0.0, 2.0, source_start=8.0), _span(2.0, 10.0, stream="ms_1")])

    assert preview_frame_position(clip, SPAN, REPRESENTATIVE_MS) == ("ms_1", 0.5)


@pytest.mark.parametrize(
    ("clip", "representative_ms"),
    [
        pytest.param(_clip(start=3.0, end=4.0), REPRESENTATIVE_MS, id="representative-outside-clip"),
        pytest.param(_clip(spans=[_span(3.0, 10.0)]), REPRESENTATIVE_MS, id="no-span-at-time"),
        pytest.param(_clip(spans=[_span(0.0, 10.0), _span(2.0, 3.0, stream="ms_1")]), REPRESENTATIVE_MS,
                     id="two-spans-at-time"),
        pytest.param(_clip(timeline_id="tl_other"), REPRESENTATIVE_MS, id="other-timeline"),
        pytest.param(_clip(revision=2), REPRESENTATIVE_MS, id="other-revision"),
        pytest.param(_clip(), None, id="no-representative-time"),
    ],
)
def test_undecidable_position_is_none(clip, representative_ms):
    assert preview_frame_position(clip, SPAN, representative_ms) is None


def test_clip_reflection_keeps_produced_frame_and_view_shows_it():
    store, case_id, clip_job = _clip_reflected("fr_preview")

    assert store.get_case(case_id).observation_outcomes[clip_job["job_id"]]["preview_frame_ref"] == "fr_preview"
    assert current_preview_frame_ref(store.get_case(case_id)) == "fr_preview"
    assert _preview_ref(store, case_id) == "fr_preview"


@pytest.mark.parametrize("produced", [pytest.param(None, id="handler-could-not-issue"),
                                      pytest.param(_ABSENT, id="result-without-field")])
def test_missing_produced_frame_leaves_preview_null_without_notice(produced):
    # 발급 불가(null)와 이전 형식 결과(키 없음) 모두 — 반영이 다시 발급하지 않고, 판독 후속 발주는 그대로다.
    store, case_id, clip_job = _clip_reflected(produced)

    assert store.get_case(case_id).observation_outcomes[clip_job["job_id"]]["preview_frame_ref"] is None
    view = _view(store, case_id)
    assert view["evidence"]["preview_ref"] is None
    assert view["notices"] == []
    assert store.get_case(case_id).job_records[-1]["kind"] == "OVERLAY_TIME_READ"


def test_reselection_shows_only_the_selected_candidates_clip_frame():
    store, case_id, _ = _clip_reflected("fr_preview")

    def select(candidate_id: str) -> None:
        case = store.load_for_update(case_id)
        for c in case.candidates:
            c.selected = c.candidate_id == candidate_id
        store.save(case)

    select("cand_2")
    assert current_preview_frame_ref(store.get_case(case_id)) is None  # 이전 후보 값이 남지 않는다
    select("cand_1")
    assert current_preview_frame_ref(store.get_case(case_id)) == "fr_preview"  # A→B→A는 A의 clip 값을 다시 쓴다
