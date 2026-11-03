"""다른 후보 화면 썸네일(`candidates[].thumb_ref`) — 상위 3개 후보 frame을 clip handler가 함께 발급한다(#523 A안).

case가 정하는 것: 어느 후보의 썸네일을 만들지(`thumbnail_candidate_ids`), 그 후보의 원본 위치
(`candidate_frame_position`), handler가 실은 `candidate_frame_refs`를 남기고 현재 세대 값을 CaseView에 투영하는 것.
후보가 3개보다 적으면 있는 만큼만 고르고, 무효 후보는 빼되 4위로 채우지 않는다(#523 댓글 2026-11-02).
"""
from __future__ import annotations

from typing import Any

import pytest

from daesingo.case import jobs
from daesingo.case.preview_frame import (
    candidate_frame_position,
    current_candidate_frame_refs,
    thumbnail_candidate_ids,
)
from daesingo.case.reflection import ExecutionOutcome, reflect_execution
from daesingo.case.view import build_case_view
from tests.case.test_observation_chain import FakeReader, FakeTimelines, _after_coarse, _event, _fine, _reflect


def _events(count: int) -> list[dict[str, Any]]:
    return [{**_event(f"cand_{rank}", rank), "thumbnail_ref": None} for rank in range(1, count + 1)]


def _case(count: int):
    store, case_id, _, _ = _after_coarse(events=_events(count))
    return store, case_id


def _input(case) -> dict[str, Any]:
    return {"candidate_id": "cand_1", "generation_job_id": case.current_generation_job_id()}


# --- 어느 후보를 고르는가 --------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("count", "expected"), [
    pytest.param(5, ("cand_1", "cand_2", "cand_3"), id="more-than-three"),
    pytest.param(3, ("cand_1", "cand_2", "cand_3"), id="exactly-three"),
    pytest.param(2, ("cand_1", "cand_2"), id="two"),
    pytest.param(1, ("cand_1",), id="one"),
])
def test_selects_rank_one_to_three_in_rank_order(count, expected):
    store, case_id = _case(count)
    case = store.get_case(case_id)

    assert thumbnail_candidate_ids(case, _input(case), _events(count)) == expected


def test_no_candidates_selects_nothing():
    store, case_id = _case(0)
    case = store.get_case(case_id)

    assert thumbnail_candidate_ids(case, {"candidate_id": "cand_1", "generation_job_id": case.current_generation_job_id()},
                                   []) == ()


def test_stale_candidate_is_dropped_without_filling_from_rank_four():
    store, case_id = _case(5)
    case = store.get_case(case_id)
    next(c for c in case.candidates if c.candidate_id == "cand_2").stale_revision = True

    assert thumbnail_candidate_ids(case, _input(case), _events(5)) == ("cand_1", "cand_3")


def test_candidate_without_span_is_dropped():
    # 이전 형식 후보는 위치를 정할 구간이 없다 — Runtime의 후보 대조에도 걸린다.
    store, case_id = _case(3)
    case = store.get_case(case_id)
    next(c for c in case.candidates if c.candidate_id == "cand_3").span = None

    assert thumbnail_candidate_ids(case, _input(case), _events(3)) == ("cand_1", "cand_2")


def test_candidate_missing_from_generation_events_is_dropped():
    store, case_id = _case(3)
    case = store.get_case(case_id)

    assert thumbnail_candidate_ids(case, _input(case), _events(3)[:2]) == ("cand_1", "cand_2")


def test_input_from_an_older_generation_selects_nothing():
    store, case_id = _case(3)
    case = store.get_case(case_id)

    assert thumbnail_candidate_ids(case, {"candidate_id": "cand_1", "generation_job_id": "job_old"}, _events(3)) == ()


def test_accepts_events_as_models():
    # Runtime은 search `CandidateEvent` 모델을 넘긴다 — `candidate_id` 속성만 읽는다.
    class Event:
        def __init__(self, candidate_id): self.candidate_id = candidate_id

    store, case_id = _case(2)
    case = store.get_case(case_id)

    assert thumbnail_candidate_ids(case, _input(case), [Event("cand_1"), Event("cand_2")]) == ("cand_1", "cand_2")


# --- 후보별 원본 위치 ----------------------------------------------------------------------------------------------------

SPAN = {"timeline_id": "tl_1", "timeline_revision": 1, "start_ms": 2_000, "end_ms": 5_000, "representative_ms": 3_500}


def _asset(start: float, end: float, *, source_start: float = 0.0, stream: str = "ms_0") -> dict[str, Any]:
    return {"timeline_range": {"start_sec": start, "end_sec": end},
            "source_range": {"start_sec": source_start, "end_sec": source_start + end - start},
            "media_stream_ref": stream}


def _resolution(*, timeline_id: str = "tl_1", revision: int = 1, start: float = 2.0, end: float = 5.0,
                spans: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """recording `SpanResolution` JSON. 기본 span 하나는 timeline 2~5초 = 원본 `ms_0`의 10~13초다."""
    return {"timeline_ref": {"timeline_id": timeline_id, "revision": revision},
            "requested_range": {"start_sec": start, "end_sec": end},
            "spans": _default_spans() if spans is None else spans}


def _default_spans() -> list[dict[str, Any]]:
    return [_asset(2.0, 5.0, source_start=10.0)]


def test_position_is_source_offset_of_candidate_representative_time():
    assert candidate_frame_position(_resolution(), SPAN, 3_500) == ("ms_0", 11.5)


def test_position_uses_the_asset_span_that_contains_the_time():
    resolution = _resolution(spans=[_asset(2.0, 3.0, source_start=40.0), _asset(3.0, 5.0, stream="ms_1")])

    assert candidate_frame_position(resolution, SPAN, 3_500) == ("ms_1", 0.5)


@pytest.mark.parametrize(("resolution", "representative_ms"), [
    pytest.param(_resolution(start=4.0, end=5.0, spans=[_asset(4.0, 5.0)]), 3_500, id="outside-requested-range"),
    pytest.param(_resolution(spans=[_asset(4.0, 5.0)]), 3_500, id="no-span-at-time"),
    pytest.param(_resolution(spans=[_asset(2.0, 5.0), _asset(3.0, 4.0, stream="ms_1")]), 3_500, id="two-spans-at-time"),
    pytest.param(_resolution(spans=[]), 3_500, id="failed-resolution"),
    pytest.param(_resolution(timeline_id="tl_other"), 3_500, id="other-timeline"),
    pytest.param(_resolution(revision=2), 3_500, id="other-revision"),
    pytest.param(_resolution(), None, id="no-representative-time"),
])
def test_undecidable_candidate_position_is_none(resolution, representative_ms):
    assert candidate_frame_position(resolution, SPAN, representative_ms) is None


# --- T2 반영과 CaseView 투영 -----------------------------------------------------------------------------------------

_ABSENT = object()


def _reflect_clip(store, case_id, refs: Any) -> None:
    clip_job = jobs.latest_job_record(store.get_case(case_id), "INCIDENT_CLIP_BUILD")
    content: dict[str, Any] = {"incident_clip_ref": f"ic_{clip_job['job_id']}"}
    if refs is not _ABSENT:
        content["candidate_frame_refs"] = refs
    outcome = ExecutionOutcome(execution_id=f"exec_clip_{clip_job['job_id']}", job_id=clip_job["job_id"],
                               case_id=case_id, kind="INCIDENT_CLIP_BUILD", attempt=1, status="SUCCEEDED",
                               produced=({"kind": "result", "ref": "ref_clip"},))
    reflect_execution(outcome, store=store, reader=FakeReader({"INCIDENT_CLIP_BUILD": content}), timelines=FakeTimelines())


def _clip_ready(count: int = 3):
    """Coarse → rank=1 Fine 관찰됨 → clip 발주까지."""
    store, case_id = _case(count)
    fine = jobs.latest_job_record(store.get_case(case_id), "FINE_VERIFY")
    _reflect(store, case_id, fine, _fine("OBSERVED"))
    return store, case_id


def _thumbs(store, case_id) -> dict[str, Any]:
    return {c["candidate_id"]: c["thumb_ref"] for c in build_case_view(store.get_case(case_id))["candidates"]}


def test_reflected_candidate_frames_become_thumb_refs():
    store, case_id = _clip_ready(3)
    _reflect_clip(store, case_id, {"cand_1": "fr_1", "cand_2": "fr_2", "cand_3": None})

    assert current_candidate_frame_refs(store.get_case(case_id)) == {"cand_1": "fr_1", "cand_2": "fr_2"}
    assert _thumbs(store, case_id) == {"cand_1": "fr_1", "cand_2": "fr_2", "cand_3": None}


@pytest.mark.parametrize("refs", [pytest.param(None, id="null"), pytest.param({}, id="empty"),
                                  pytest.param(_ABSENT, id="result-without-field")])
def test_no_candidate_frames_leaves_thumb_refs_null(refs):
    store, case_id = _clip_ready(2)
    _reflect_clip(store, case_id, refs)

    assert current_candidate_frame_refs(store.get_case(case_id)) == {}
    assert _thumbs(store, case_id) == {"cand_1": None, "cand_2": None}


def test_new_generation_drops_previous_candidate_frames():
    store, case_id = _clip_ready(2)
    _reflect_clip(store, case_id, {"cand_1": "fr_1", "cand_2": "fr_2"})

    case = store.load_for_update(case_id)
    case.job_records.append({"job_id": "job_coarse_2", "kind": "COARSE_SEARCH", "scope_ref": None})
    case.settled_jobs["job_coarse_2"] = "REFLECTED"
    store.save(case)

    assert current_candidate_frame_refs(store.get_case(case_id)) == {}


def test_later_clip_null_does_not_erase_an_issued_frame():
    # 다른 후보를 고르면 그 후보의 clip이 다시 발급한다 — 이번에 못 만든 후보(null)는 앞서 만든 frame을 지우지 않는다.
    store, case_id = _clip_ready(2)
    _reflect_clip(store, case_id, {"cand_1": "fr_1", "cand_2": "fr_2"})
    case = store.get_case(case_id)
    first_clip = jobs.latest_job_record(case, "INCIDENT_CLIP_BUILD")["job_id"]
    second = {**case.observation_outcomes[first_clip], "candidate_frame_refs": {"cand_1": None, "cand_2": "fr_2b"}}
    case.job_records.append({"job_id": "job_clip_2", "kind": "INCIDENT_CLIP_BUILD", "scope_ref": None})
    case.observation_inputs["job_clip_2"] = {**case.observation_inputs[first_clip], "candidate_id": "cand_2"}
    case.observation_outcomes["job_clip_2"] = second

    assert current_candidate_frame_refs(case) == {"cand_1": "fr_1", "cand_2": "fr_2b"}
