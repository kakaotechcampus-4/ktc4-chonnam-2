"""설명 고쳐 다시 찾기(`EDIT_HINT{description}`) — #410, `decisions/edit-hint.md`.

원문을 다시 받아 `SEARCHING`으로 역행하고 `HINT_EXTRACT`를 다시 발주한다. 결과 반영은 분석 시작과 같은 경로다.
허용 조건은 「현재 CaseView notice가 `EDIT_HINT`를 싣고 있는가」(`RUN_NOTICE_ACTION`과 같은 근거)다.
"""
from __future__ import annotations

import pytest

from daesingo.case import analysis_start, command, service
from daesingo.case.analysis_start import InitialSearchBudget
from daesingo.case.domain import Candidate, InvalidTransition
from daesingo.case.store import CaseStore
from daesingo.case.timeline_source import CaseTimeline, TimelineUnavailable

_ALL_NULL = {"time": None, "vehicle": None, "situation": None, "location": None}


class FakeTimelines:
    def __init__(self, fail: bool = False):
        self.fail = fail

    def timeline_for(self, sources):
        if self.fail:
            raise TimelineUnavailable("fake")
        return CaseTimeline(timeline_id="tl_1", revision=1, duration_ms=10_000)


def _candidate(cid: str, rank: int = 1) -> Candidate:
    return Candidate(candidate_id=cid, at=None, at_provenance=None, observed="", thumb_ref=None, rank=rank)


def _req(case_id: str, kind: str, payload: dict, rev: int) -> dict:
    return {"case_id": case_id, "expected_case_rev": rev, "kind": kind, "payload": payload}


def _edit(store: CaseStore, case_id: str, description: str, *, timelines=None) -> command.CommandResult:
    rev = store.get_case(case_id).case_rev
    return command.execute_command(
        _req(case_id, "EDIT_HINT", {"description": description}, rev), store=store, timelines=timelines or FakeTimelines()
    )


def _started(description: str = "흰 SUV가 끼어들었어요") -> tuple[CaseStore, str]:
    store = CaseStore()
    case_id = service.create_case(store=store)
    service.record_source_registered(
        case_id,
        {"source_asset_ref": "sa_0", "availability": "AVAILABLE", "duration_sec": 10.0},
        media_streams=[{"media_stream_ref": "ms_0", "media_type": "VIDEO"}],
        store=store,
    )
    result = command.execute_command(
        _req(case_id, "START_ANALYSIS", {"description": description}, 1), store=store, timelines=FakeTimelines()
    )
    assert result.response["ok"] is True
    return store, case_id


def _hint_job(store: CaseStore, case_id: str) -> str:
    return [r["job_id"] for r in store.get_case(case_id).job_records if r["kind"] == "HINT_EXTRACT"][-1]


def _reflect_hint(store: CaseStore, case_id: str, result: dict) -> None:
    assert service.receive_hint_extraction_result(
        case_id, result, job_id=_hint_job(store, case_id), store=store, timelines=FakeTimelines()
    ).reflected


def _receive(store: CaseStore, case_id: str, candidates: list[Candidate]) -> None:
    case = store.load_for_update(case_id)
    case.receive_candidates(candidates)
    store.save(case)


def _no_candidates(description: str = "흰 SUV가 끼어들었어요") -> tuple[CaseStore, str]:
    store, case_id = _started(description)
    _reflect_hint(store, case_id, {"status": "OK", "vehicle_hint": "흰 SUV"})
    _receive(store, case_id, [])
    return store, case_id


def _notice(store: CaseStore, case_id: str, code: str) -> dict | None:
    return next((n for n in service.get_view(case_id, store=store)["notices"] if n["code"] == code), None)


# ── 결과 없음 화면 ─────────────────────────────────────────────────────────────


def test_edit_from_no_candidates_reissues_hint_extraction():
    store, case_id = _no_candidates()
    before = store.get_case(case_id)

    result = _edit(store, case_id, "빨간 트럭이 신호를 무시했어요")

    assert result.response["ok"] is True
    assert [r["kind"] for r in result.appended_job_records] == ["HINT_EXTRACT"]
    saved = store.get_case(case_id)
    assert saved.stage == "SEARCHING"
    assert saved.description == "빨간 트럭이 신호를 무시했어요"
    assert saved.hints == _ALL_NULL
    assert saved.candidates == []
    assert saved.case_rev == before.case_rev + 1
    assert saved.candidate_generation == before.candidate_generation + 1
    view = result.response["case_view"]
    assert view["description"] == "빨간 트럭이 신호를 무시했어요"
    assert [(j["kind"], j["status"]) for j in view["running_jobs"]] == [("HINT_EXTRACT", "PENDING")]


def test_reflected_result_runs_first_search_like_start_analysis():
    store, case_id = _no_candidates()
    _edit(store, case_id, "빨간 트럭")

    result = service.receive_hint_extraction_result(
        case_id, {"status": "OK", "vehicle_hint": "빨간 트럭"}, job_id=_hint_job(store, case_id),
        store=store, timelines=FakeTimelines(),
    )

    assert [r["kind"] for r in result.appended_job_records] == ["COARSE_SEARCH"]
    saved = store.get_case(case_id)
    assert saved.hints["vehicle"] == "빨간 트럭"
    assert [r["kind"] for r in saved.job_records] == ["HINT_EXTRACT", "COARSE_SEARCH", "HINT_EXTRACT", "COARSE_SEARCH"]


def test_blank_description_skips_extraction_and_searches_directly():
    """분석 시작과 같다 — 부를 이유가 없는 구조화를 만들지 않는다."""
    store, case_id = _no_candidates()

    result = _edit(store, case_id, "   ")

    assert [r["kind"] for r in result.appended_job_records] == ["COARSE_SEARCH"]
    saved = store.get_case(case_id)
    assert saved.description == "   "
    assert saved.hints == _ALL_NULL
    scope = saved.analysis_scopes[result.appended_job_records[0]["scope_ref"]]
    assert scope["budget"] == {"max_cost_krw": 1000.0, "max_latency_sec": 150.0}


def test_budget_is_the_same_as_first_search():
    store, case_id = _no_candidates()
    rev = store.get_case(case_id).case_rev
    result = command.execute_command(
        _req(case_id, "EDIT_HINT", {"description": ""}, rev), store=store, timelines=FakeTimelines(),
        budget=InitialSearchBudget(max_cost_krw=500.0),
    )
    scope = store.get_case(case_id).analysis_scopes[result.appended_job_records[0]["scope_ref"]]
    assert scope["budget"]["max_cost_krw"] == 500.0


def test_no_candidates_notice_carries_edit_hint():
    store, case_id = _no_candidates()
    assert _notice(store, case_id, "search.no_candidates")["actions"] == ["EDIT_HINT", "RETRY_SEARCH"]


# ── 설명을 잘 이해하지 못함 · 단서 구조화 중 중단 ───────────────────────────────────


def test_hint_unclear_notice_carries_edit_hint_and_edit_clears_it():
    store, case_id = _started()
    _reflect_hint(store, case_id, {"status": "ABSTAINED"})
    _receive(store, case_id, [_candidate("cand_1")])
    assert _notice(store, case_id, "search.hint_unclear")["actions"] == ["EDIT_HINT"]

    result = _edit(store, case_id, "흰 SUV가 실선을 넘어 끼어들었어요")

    assert result.response["ok"] is True
    saved = store.get_case(case_id)
    assert saved.hint_unclear is False
    assert saved.candidates == []


def test_stop_during_hint_extraction_offers_edit_hint():
    """#405 Known Issue — 다시 낼 이전 탐색이 없어 막다른 화면이던 곳의 출구."""
    store, case_id = _started()
    rev = store.get_case(case_id).case_rev
    assert command.execute_command(_req(case_id, "STOP_ANALYSIS", {}, rev), store=store).response["ok"] is True
    assert _notice(store, case_id, "case.analysis_stopped")["actions"] == ["EDIT_HINT"]

    result = _edit(store, case_id, "다시 적은 설명")

    assert result.response["ok"] is True
    assert [r["kind"] for r in result.appended_job_records] == ["HINT_EXTRACT"]
    saved = store.get_case(case_id)
    assert saved.stage == "SEARCHING"
    assert not saved.analysis_stopped
    assert _notice(store, case_id, "case.analysis_stopped") is None


def test_stop_after_search_started_keeps_retry_only():
    """이전 탐색이 있으면 지금처럼 「이어서 찾기」만 — 다른 화면은 이번에 바꾸지 않는다."""
    store, case_id = _started("")
    rev = store.get_case(case_id).case_rev
    command.execute_command(_req(case_id, "STOP_ANALYSIS", {}, rev), store=store)
    assert _notice(store, case_id, "case.analysis_stopped")["actions"] == ["RETRY_SEARCH"]


# ── 거부 ─────────────────────────────────────────────────────────────────────


def test_rejected_without_a_notice_carrying_edit_hint():
    """후보가 있는 정상 결과 화면 — 버튼이 없었으므로 받지 않는다."""
    store, case_id = _started()
    _reflect_hint(store, case_id, {"status": "OK", "vehicle_hint": "흰 SUV"})
    _receive(store, case_id, [_candidate("cand_1")])
    before = store.get_case(case_id)

    result = _edit(store, case_id, "다른 설명")

    assert result.response["error"]["code"] == "case.command.not_allowed"
    assert result.appended_job_records == []
    after = store.get_case(case_id)
    assert (after.stage, after.description, after.case_rev) == (before.stage, before.description, before.case_rev)


def test_rejected_while_analysis_is_running():
    store, case_id = _started()
    result = _edit(store, case_id, "다른 설명")
    assert result.response["error"]["code"] == "case.command.not_allowed"
    assert [r["kind"] for r in store.get_case(case_id).job_records] == ["HINT_EXTRACT"]


@pytest.mark.parametrize("payload", [{}, {"description": 3}, {"description": "x", "extra": "y"}])
def test_invalid_payload(payload):
    store, case_id = _no_candidates()
    rev = store.get_case(case_id).case_rev
    result = command.execute_command(_req(case_id, "EDIT_HINT", payload, rev), store=store, timelines=FakeTimelines())
    assert result.response["error"]["code"] == "case.command.invalid_payload"


def test_stale_revision():
    store, case_id = _no_candidates()
    rev = store.get_case(case_id).case_rev
    result = command.execute_command(
        _req(case_id, "EDIT_HINT", {"description": "x"}, rev - 1), store=store, timelines=FakeTimelines()
    )
    assert result.response["error"]["code"] == "case.command.stale_revision"


def test_timeline_failure_saves_nothing():
    store, case_id = _no_candidates()
    before = store.get_case(case_id)

    with pytest.raises(TimelineUnavailable):
        _edit(store, case_id, "", timelines=FakeTimelines(fail=True))

    after = store.get_case(case_id)
    assert (after.stage, after.case_rev, len(after.job_records)) == (before.stage, before.case_rev, len(before.job_records))


# ── aggregate 수준 — 후보 선택 뒤 역행 ───────────────────────────────────────────


def test_edit_after_selection_discards_candidates_and_selection():
    store, case_id = _no_candidates()
    case = store.get_case(case_id)
    case.stage = "SEARCHING"  # 결과 없음 → 다시 탐색했다고 보고 후보 1개를 받은 뒤 선택
    case.receive_candidates([_candidate("cand_1")])
    case.select_candidate("cand_1")
    assert case.stage == "EVIDENCE_REVIEW"

    analysis_start.edit_hint(case, "새 설명", timelines=FakeTimelines(), budget=InitialSearchBudget())

    assert case.stage == "SEARCHING"
    assert case.candidates == []
    assert case.description == "새 설명"


def test_edit_is_not_allowed_before_analysis_starts():
    case = service.CaseAggregate.intake(case_id="case_x", hints=dict(_ALL_NULL), manifest_summary={})
    with pytest.raises(InvalidTransition):
        analysis_start.edit_hint(case, "x", timelines=FakeTimelines(), budget=InitialSearchBudget())
