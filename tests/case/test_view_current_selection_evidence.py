"""CaseView는 **현재 선택 context의 evidence만** 투영한다(#173 E-4 조건 1의 전제, W7 6.6순위).

web은 `stage=EVIDENCE_REVIEW`이면서 `evidence=null`일 때만 진행 화면을 띄우고, evidence가 있으면
「다른 후보 보기」가 있는 결과 화면으로 간다(`apps/web/src/state/selectScreen.ts`). 재선택 직후
case가 이전 후보의 evidence를 그대로 내리면 web은 준비 중인데도 결과 화면을 띄워 재선택을 다시
허용한다. 그래서 `EvidenceRecord`의 `basis.candidate_ref`·`selection_rev`가 현재 선택과 다르면
evidence와, 그 evidence에서 나온 RequirementReport·ReportPackage를 모두 투영하지 않는다.
"""
from __future__ import annotations

import json
from pathlib import Path

from daesingo.case import correction
from daesingo.case.domain import Candidate, CaseAggregate
from daesingo.case.view import build_case_view

MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"


def _evidence_fixture() -> dict:
    path = MOCK_ROOT / "evidence" / "scenario_happy_001.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _inputs() -> dict:
    ev = _evidence_fixture()
    return dict(
        evidence_record=ev["evidence_records"][-1],
        requirement_report_evidence=next(r for r in ev["requirement_reports"] if r["scope"] == "EVIDENCE"),
        requirement_report_package=next(r for r in ev["requirement_reports"] if r["scope"] == "FINAL_PACKAGE"),
        report_package=ev["report_packages"][-1],
    )


def _case_with_selection() -> CaseAggregate:
    case = CaseAggregate.intake(case_id="case_h001", hints={}, manifest_summary={})
    case.start_search()
    case.receive_candidates(
        [
            Candidate(candidate_id=cid, at=None, at_provenance=None, observed="", thumb_ref=None)
            for cid in ("candidate_h001", "candidate_other")
        ]
    )
    case.select_candidate("candidate_h001")
    return case


def _assert_nothing_projected(view: dict) -> None:
    assert view["evidence"] is None
    assert view["requirements_evidence"] is None
    assert view["requirements_package"] is None
    assert view["package"] is None


def test_evidence_of_current_selection_is_projected():
    view = build_case_view(_case_with_selection(), **_inputs())

    assert view["evidence"] is not None
    assert view["package"] is not None


def test_evidence_of_previous_candidate_is_not_projected():
    """다른 후보로 바꾼 직후, adapter가 아직 이전 후보의 evidence를 들고 있는 경우."""
    case = _case_with_selection()
    correction.reselect_candidate(case, "candidate_other")

    view = build_case_view(case, **_inputs())

    _assert_nothing_projected(view)
    assert view["stage"] == "EVIDENCE_REVIEW"


def test_evidence_of_older_selection_of_same_candidate_is_not_projected():
    """A → B → A로 돌아와도 이전 선택 context의 evidence다(selection_rev가 다름)."""
    case = _case_with_selection()
    correction.reselect_candidate(case, "candidate_other")
    correction.reselect_candidate(case, "candidate_h001")

    view = build_case_view(case, **_inputs())

    _assert_nothing_projected(view)
