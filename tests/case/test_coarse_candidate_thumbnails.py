"""Coarse 결과에 실린 후보 썸네일(#583 E안) — Fine · clip 결과와 무관하게 상위 3개 후보 썸네일이 보인다.

#523 A안은 선택 후보 clip handler가 다른 후보 썸네일까지 발급해, 첫 Fine이 `NOT_OBSERVED`거나 실패하면 clip이
발주되지 않아 다른 후보 썸네일도 최초 미생성이었다. E안은 Coarse handler가 T1 전에 발급해 Coarse 결과
`candidate_frame_refs`에 싣고, case는 Coarse 반영 때 그 값을 후보 `thumb_ref`로 남긴다.

case가 정하는 것: 어느 후보를 발급할지(`coarse_thumbnail_candidate_ids`), 실린 값의 검증과 반영, 투영 우선순위.
"""
from __future__ import annotations

from typing import Any

import pytest

from daesingo.case import command, jobs
from daesingo.case.analysis_start import InitialSearchBudget, edit_hint
from daesingo.case.preview_frame import THUMBNAIL_MAX_RANK, coarse_thumbnail_candidate_ids
from daesingo.case.reflection import ExecutionOutcome, reflect_execution
from daesingo.case.view import build_case_view
from tests.case.test_observation_chain import FakeReader, FakeTimelines, NoDownstream, _event, _fine, _reflect, _searching

_ABSENT = object()


def _events(count: int) -> list[dict[str, Any]]:
    return [{**_event(f"cand_{rank}", rank), "thumbnail_ref": None} for rank in range(1, count + 1)]


def _coarse_content(count: int, refs: Any = _ABSENT) -> dict[str, Any]:
    content: dict[str, Any] = {"outcome": "SUCCEEDED", "candidate_events": _events(count)}
    if refs is not _ABSENT:
        content["candidate_frame_refs"] = refs
    return content


def _after_coarse(count: int = 3, refs: Any = _ABSENT):
    store, case_id = _searching()
    store.adapters.put(case_id, NoDownstream())
    coarse = jobs.latest_job_record(store.get_case(case_id), "COARSE_SEARCH")
    _reflect(store, case_id, coarse, _coarse_content(count, refs))
    return store, case_id


def _thumbs(store, case_id) -> dict[str, Any]:
    return {c["candidate_id"]: c["thumb_ref"] for c in build_case_view(store.get_case(case_id))["candidates"]}


def _latest(store, case_id, kind: str) -> dict[str, Any]:
    return jobs.latest_job_record(store.get_case(case_id), kind)


THREE = {"cand_1": "fr_1", "cand_2": "fr_2", "cand_3": "fr_3"}


# --- 어느 후보를 발급하는가 ------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("count", "expected"), [
    pytest.param(5, ("cand_1", "cand_2", "cand_3"), id="more-than-three"),
    pytest.param(3, ("cand_1", "cand_2", "cand_3"), id="exactly-three"),
    pytest.param(2, ("cand_1", "cand_2"), id="two"),
    pytest.param(0, (), id="none"),
])
def test_selects_rank_one_to_three_in_rank_order(count, expected):
    assert coarse_thumbnail_candidate_ids(list(reversed(_events(count)))) == expected


def test_candidate_without_full_span_is_dropped_without_filling_from_rank_four():
    events = _events(4)
    del events[1]["span"]["end_ms"]
    events[2]["span"]["representative_ms"] = None

    assert coarse_thumbnail_candidate_ids(events) == ("cand_1",)


def test_accepts_events_as_models():
    # Runtime은 search `CandidateEvent` 모델을 넘긴다 — `candidate_id` · `rank` · `span` 속성만 읽는다.
    class Span:
        def __init__(self, raw): self.__dict__.update(raw)

        def model_dump(self, mode="json"): return dict(self.__dict__)

    class Event:
        def __init__(self, raw):
            self.candidate_id, self.rank, self.span = raw["candidate_id"], raw["rank"], Span(raw["span"])

    assert coarse_thumbnail_candidate_ids([Event(e) for e in _events(4)]) == ("cand_1", "cand_2", "cand_3")
    assert THUMBNAIL_MAX_RANK == 3


# --- Coarse 반영 ------------------------------------------------------------------------------------------------------

def test_coarse_frames_become_thumb_refs_before_any_fine():
    store, case_id = _after_coarse(3, THREE)

    assert _thumbs(store, case_id) == THREE


@pytest.mark.parametrize("refs", [pytest.param(None, id="null"), pytest.param({}, id="empty"),
                                  pytest.param(_ABSENT, id="result-without-field")])
def test_coarse_result_without_frames_leaves_thumb_refs_null(refs):
    store, case_id = _after_coarse(2, refs)

    assert _thumbs(store, case_id) == {"cand_1": None, "cand_2": None}


def test_refused_frame_stays_null_for_that_candidate_only():
    store, case_id = _after_coarse(3, {"cand_1": "fr_1", "cand_2": None, "cand_3": "fr_3"})

    assert _thumbs(store, case_id) == {"cand_1": "fr_1", "cand_2": None, "cand_3": "fr_3"}


@pytest.mark.parametrize("refs", [
    pytest.param({"cand_4": "fr_4"}, id="rank-four"),
    pytest.param({"cand_9": "fr_9"}, id="not-in-result"),
    pytest.param({"cand_1": ""}, id="empty-ref"),
    pytest.param({"cand_1": 7}, id="not-a-string"),
    pytest.param(["fr_1"], id="not-a-mapping"),
])
def test_frames_for_candidates_case_did_not_choose_are_a_wiring_error(refs):
    store, case_id = _searching()
    coarse = jobs.latest_job_record(store.get_case(case_id), "COARSE_SEARCH")
    rev = store.get_case(case_id).case_rev

    with pytest.raises(ValueError):
        _reflect(store, case_id, coarse, _coarse_content(5, refs))

    case = store.get_case(case_id)
    assert (case.stage, case.candidates, case.case_rev) == ("SEARCHING", [], rev)  # 저장하지 않는다


# --- #583: Fine · clip 결과와 무관하다 --------------------------------------------------------------------------------

@pytest.mark.parametrize(("content", "status"), [
    pytest.param(_fine("NOT_OBSERVED"), "SUCCEEDED", id="fine-not-observed"),
    pytest.param(None, "FAILED", id="fine-failed"),
])
def test_other_candidates_keep_thumbnails_when_first_fine_does_not_lead_to_a_clip(content, status):
    store, case_id = _after_coarse(3, THREE)

    _reflect(store, case_id, _latest(store, case_id, "FINE_VERIFY"), content, status=status)

    assert _latest(store, case_id, "INCIDENT_CLIP_BUILD") is None
    assert _thumbs(store, case_id) == THREE


def test_thumbnails_survive_a_failed_clip():
    store, case_id = _after_coarse(3, THREE)
    _reflect(store, case_id, _latest(store, case_id, "FINE_VERIFY"), _fine("OBSERVED"))

    _reflect(store, case_id, _latest(store, case_id, "INCIDENT_CLIP_BUILD"), status="FAILED")

    assert _thumbs(store, case_id) == THREE


def _reflect_clip(store, case_id, refs: dict[str, Any]) -> None:
    clip = _latest(store, case_id, "INCIDENT_CLIP_BUILD")
    _reflect(store, case_id, clip, {"incident_clip_ref": f"ic_{clip['job_id']}", "candidate_frame_refs": refs})


def test_clip_frame_still_wins_and_clip_null_keeps_the_coarse_frame():
    # #523 경로는 그대로 둔다 — clip이 낸 frame이 우선이고, clip의 `null`은 Coarse frame을 지우지 않는다.
    store, case_id = _after_coarse(3, THREE)
    _reflect(store, case_id, _latest(store, case_id, "FINE_VERIFY"), _fine("OBSERVED"))

    _reflect_clip(store, case_id, {"cand_1": "fr_1_clip", "cand_2": None})

    assert _thumbs(store, case_id) == {"cand_1": "fr_1_clip", "cand_2": "fr_2", "cand_3": "fr_3"}


# --- 세대 ------------------------------------------------------------------------------------------------------------

def _search_again(store, case_id) -> None:
    """설명을 고쳐 다시 찾는다 — 후보 목록 세대가 바뀐다. 허용 조건(notice)은 `test_edit_hint_command.py`가 본다."""
    case = store.load_for_update(case_id)
    edit_hint(case, "", timelines=FakeTimelines(), budget=InitialSearchBudget())
    store.save(case)


def test_new_search_replaces_previous_thumbnails():
    store, case_id = _after_coarse(3, THREE)
    _search_again(store, case_id)

    _reflect(store, case_id, _latest(store, case_id, "COARSE_SEARCH"), _coarse_content(2, {"cand_2": "fr_2_new"}))

    assert _thumbs(store, case_id) == {"cand_1": None, "cand_2": "fr_2_new"}


def test_late_result_of_a_superseded_search_does_not_write_thumbnails():
    store, case_id = _searching()
    store.adapters.put(case_id, NoDownstream())
    old = jobs.latest_job_record(store.get_case(case_id), "COARSE_SEARCH")
    stop = {"case_id": case_id, "expected_case_rev": store.get_case(case_id).case_rev,
            "kind": "STOP_ANALYSIS", "payload": {}}
    assert command.execute_command(stop, store=store).response["ok"] is True

    result = _reflect(store, case_id, old, _coarse_content(3, THREE))

    assert (result.status, result.reason) == ("NOT_APPLIED", "CANCELLED")
    assert store.get_case(case_id).candidates == []


def test_redelivered_execution_is_not_applied_twice():
    store, case_id = _searching()
    store.adapters.put(case_id, NoDownstream())
    coarse = jobs.latest_job_record(store.get_case(case_id), "COARSE_SEARCH")
    outcome = ExecutionOutcome("exec_coarse", coarse["job_id"], case_id, "COARSE_SEARCH", 1, "SUCCEEDED",
                               ({"kind": "result", "ref": "ref_coarse"},))
    reader = FakeReader({"COARSE_SEARCH": _coarse_content(3, THREE)})
    reflect_execution(outcome, store=store, reader=reader, timelines=FakeTimelines())

    again = reflect_execution(outcome, store=store, reader=reader, timelines=FakeTimelines())

    assert again.status == "ALREADY_APPLIED"
    assert reader.calls == ["COARSE_SEARCH"]
    assert _thumbs(store, case_id) == THREE
