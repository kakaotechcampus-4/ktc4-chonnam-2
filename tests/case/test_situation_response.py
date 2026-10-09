"""통합 항목 I1 — 사용자의 신고 상황 응답(`situation_response`)을 case가 기록해 evidence에 전달한다.

#171 B-2(Case 동의): 결과 화면 「신고 상황」 항목에서 사용자가 실제로 누른 시점에 기록하고,
무응답은 `NOT_ASKED`로 남긴다. ADR-EVIDENCE-005 D2-c: `NOT_ASKED`면 Package가 나가지 않는다.
응답 모양은 `EvidenceRecord.situation_response`(`value`·`responded_at`·`candidate_ref`)를 그대로 쓴다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from daesingo.case import correction, jobs, real_e2e, service
from daesingo.case.adapters import MockFixtureAdapter, RealAdapter
from daesingo.case.domain import Candidate, CaseAggregate, InvalidTransition

MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"


def _selected_case() -> CaseAggregate:
    case = CaseAggregate.intake(case_id="case_sr001", hints={}, manifest_summary={})
    case.start_search()
    case.receive_candidates(
        [
            Candidate(candidate_id=cid, at=None, at_provenance=None, observed="", thumb_ref=None)
            for cid in ("cand_a", "cand_b")
        ]
    )
    case.select_candidate("cand_a")
    return case


def test_no_response_until_user_answers():
    case = _selected_case()
    assert case.situation_response is None


def test_record_response_uses_selected_candidate_and_bumps_case_rev():
    case = _selected_case()
    rev_before = case.case_rev

    response = case.record_situation_response("CONFIRMED", responded_at="2026-08-24T18:22:30+09:00")

    assert response == {
        "value": "CONFIRMED",
        "responded_at": "2026-08-24T18:22:30+09:00",
        "candidate_ref": {"kind": "candidate_event", "ref": "cand_a"},
    }
    assert case.situation_response == response
    assert case.case_rev == rev_before + 1


def test_record_response_rejects_unknown_value():
    case = _selected_case()
    with pytest.raises(ValueError):
        case.record_situation_response("NOT_ASKED", responded_at="2026-08-24T18:22:30+09:00")


def test_record_response_requires_selected_candidate():
    case = CaseAggregate.intake(case_id="case_sr002", hints={}, manifest_summary={})
    with pytest.raises(InvalidTransition):
        case.record_situation_response("CONFIRMED", responded_at="2026-08-24T18:22:30+09:00")


def test_other_candidate_clears_previous_response():
    """응답은 선택된 candidate에 묶인다 — 다른 후보를 고르면 새 후보에 대해 다시 묻는다."""
    case = _selected_case()
    case.record_situation_response("CONFIRMED", responded_at="2026-08-24T18:22:30+09:00")

    correction.reselect_candidate(case, "cand_b")

    assert case.situation_response is None


def _happy_real_adapter() -> tuple[CaseAggregate, RealAdapter]:
    scope = MockFixtureAdapter(MOCK_ROOT, "happy_001").get_analysis_scopes()[0]
    case = CaseAggregate.intake(case_id="case_h001_sr", hints={}, manifest_summary={})
    real = RealAdapter(case_id="case_h001_sr", case=case, search_scope=scope, mock_root=MOCK_ROOT)
    case.start_search()
    jobs.issue_coarse_search(case, scope_ref="scope_h001", input_fingerprint="sha1:h001-coarse-search")
    candidates = service.receive_search_candidates(case, real)
    case.select_candidate(candidates[0].candidate_id)
    return case, real


def test_response_reaches_evidence_record_without_new_fine(monkeypatch):
    case, real = _happy_real_adapter()
    fine_calls = {"n": 0}
    original = real_e2e._resolve_via_search_stream_context

    def spy(*args, **kwargs):
        fine_calls["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(real_e2e, "_resolve_via_search_stream_context", spy)

    before = real.get_evidence_record()
    assert "situation_response" not in before

    case.record_situation_response("CONFIRMED", responded_at="2026-08-24T18:22:30+09:00")
    after = real.get_evidence_record()

    assert after["situation_response"]["value"] == "CONFIRMED"
    assert after["situation_response"]["candidate_ref"]["ref"] == case.candidates[0].candidate_id
    assert fine_calls["n"] == 1
