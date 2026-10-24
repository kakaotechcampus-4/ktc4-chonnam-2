"""새 후보 준비 중 재선택 금지 — 6.6순위 조건 1(#173 E-4), `decisions/reselect-while-preparing.md`.

`core-user-flow.md` §8-1: 새 후보를 준비하는 동안에는 다시 후보를 바꾸지 않고, 준비가 끝난 뒤 결과 화면에서 고른다.
「준비 중」 = 선택 후보 · 현재 세대의 관찰 job(입력이 고정된 `FINE_VERIFY` · `INCIDENT_CLIP_BUILD` · 판독 2종) 중 case가
아직 결과를 기다리는 것이 있다. 상황 응답 대기는 기다리는 job이 없어 막지 않고, Fine 실패 뒤 「다른 후보 보기」도 열린다.
"""
from __future__ import annotations

from typing import Any

import pytest

from daesingo.case import command, jobs, observation
from daesingo.case.domain import CaseAggregate, InvalidTransition
from daesingo.case.service import candidates_from_events
from daesingo.case.store import CaseStore


def _event(candidate_id: str, rank: int) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "summary": candidate_id,
        "thumbnail_ref": f"fr_{candidate_id}",
        "rank": rank,
        "span": {"timeline_id": "tl_1", "timeline_revision": 1, "start_ms": 1_000 * rank,
                 "end_ms": 1_000 * rank + 3_000, "representative_ms": 1_000 * rank + 1_500},
    }


EVENTS = [_event("cand_a", 1), _event("cand_b", 2)]
VISUAL = {"candidate_id": "cand_a", "verification": "OBSERVED"}


class NoDownstream:
    """command가 CaseView를 만들 때 조회하는 adapter — downstream 값이 없다."""

    def get_candidate_events(self): return []
    def get_candidate_search_outcome(self): return None
    def get_analysis_scopes(self): return []
    def get_evidence_record(self): return None
    def get_evidence_records(self): return []
    def get_requirement_report(self, scope): return None
    def get_requirement_reports(self, scope): return []
    def get_evidence_needs(self): return []
    def get_report_package(self): return None
    def get_plate_readouts(self): return []
    def get_overlay_time_readouts(self): return []
    def get_plate_read_status(self): return None
    def get_visual_evidence_decision(self): return None
    def get_independent_facts(self): return None
    def get_job_executions(self): return []


def _selected_with_fine(scope_ref: str = "scope_1") -> tuple[CaseAggregate, dict[str, Any]]:
    """rank=1 후보를 고르고 첫 Fine을 발주한 case(`EVIDENCE_REVIEW`)."""
    case = CaseAggregate(case_id="case_r", stage="SEARCHING")
    coarse = jobs.issue_coarse_search(case, scope_ref=scope_ref, input_fingerprint="sha256:coarse")
    case.receive_candidates(candidates_from_events(EVENTS), job_id=coarse["job_id"])
    case.select_top_ranked()
    return case, observation.issue_fine_for_selected(case)


def _finish_chain(case: CaseAggregate, fine: dict[str, Any]) -> None:
    case.settle_job(fine["job_id"], "REFLECTED")
    clip = observation.follow_fine(case, fine["job_id"], VISUAL)
    case.settle_job(clip["job_id"], "REFLECTED")
    for readout in observation.follow_clip(case, clip["job_id"], "clip_a"):
        case.settle_job(readout["job_id"], "REFLECTED")


def _select_other(case: CaseAggregate, candidate_id: str = "cand_b") -> tuple[dict[str, Any], CaseAggregate]:
    store = CaseStore()
    store.register(case, NoDownstream())
    request = {"case_id": case.case_id, "expected_case_rev": case.case_rev, "kind": "SELECT_OTHER_CANDIDATE",
               "payload": {"candidate_id": candidate_id}}
    return command.execute_command(request, store=store).response, store.get_case(case.case_id)


# ── 준비 중이면 거부 ─────────────────────────────────────────────────────


def test_reselect_is_rejected_while_fine_of_selected_candidate_is_waiting():
    case, _ = _selected_with_fine()

    with pytest.raises(InvalidTransition):
        case.check_reselect("cand_b")


def test_rejected_reselect_changes_nothing():
    case, _ = _selected_with_fine()
    rev = case.case_rev

    response, saved = _select_other(case)

    assert response["error"]["code"] == "case.command.not_allowed"
    assert [c.candidate_id for c in saved.candidates if c.selected] == ["cand_a"]
    assert saved.case_rev == rev
    assert saved.correction_records == []


def test_reselect_is_rejected_while_later_step_of_the_chain_is_waiting():
    case, fine = _selected_with_fine()
    case.settle_job(fine["job_id"], "REFLECTED")
    observation.follow_fine(case, fine["job_id"], VISUAL)  # INCIDENT_CLIP_BUILD 기다리는 중

    with pytest.raises(InvalidTransition):
        case.check_reselect("cand_b")


# ── 준비가 끝났으면 허용 ─────────────────────────────────────────────────


def test_reselect_is_allowed_after_the_chain_is_settled():
    case, fine = _selected_with_fine()
    _finish_chain(case, fine)

    response, saved = _select_other(case)

    assert response["ok"] is True
    assert [c.candidate_id for c in saved.candidates if c.selected] == ["cand_b"]


def test_reselect_is_allowed_after_fine_failed():
    # 실패 뒤 출구는 「다른 후보 보기」다(8-14 `search.visual_verify_failed`).
    case, fine = _selected_with_fine()
    case.settle_job(fine["job_id"], "REFLECTED")

    response, _ = _select_other(case)

    assert response["ok"] is True


def test_waiting_job_of_previous_generation_does_not_block():
    case, _old_fine = _selected_with_fine()  # 이전 세대 Fine은 기다리는 채로 남는다
    case.regress_to_searching()
    coarse = jobs.issue_coarse_search(case, scope_ref="scope_2", input_fingerprint="sha256:again")
    case.receive_candidates(candidates_from_events(EVENTS), job_id=coarse["job_id"])
    case.select_top_ranked()

    case.check_reselect("cand_b")


def test_jobs_issued_without_observation_input_do_not_block():
    # 동기 · 데모 경로의 관찰 job은 입력이 없어 「준비 중」 판단에 쓰지 않는다.
    case = CaseAggregate(case_id="case_r", stage="SEARCHING")
    coarse = jobs.issue_coarse_search(case, scope_ref="scope_1", input_fingerprint="sha256:coarse")
    case.receive_candidates(candidates_from_events(EVENTS), job_id=coarse["job_id"])
    case.select_top_ranked()
    jobs.issue_fine_verify(case, input_fingerprint="sha256:legacy")

    case.check_reselect("cand_b")
