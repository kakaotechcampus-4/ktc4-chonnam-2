"""#172 [D] case 후속 — 번호판 판독 **실행 실패**(4a)를 「읽지 못함」(1·3)과 구분해 투영한다.

`ReadoutRun.outcome=FAILED`면 PlateReadout이 없어 evidence는 번호판 없이 조립된다. 예전엔
real 경로가 `ReadoutRun`을 버려, 실행 실패와 「읽지 못함」이 둘 다 `plate_display`
`INFO_UNKNOWN`·notice 없음이었고, evidence가 있다는 이유로 진행 상태 `plate_read`는 DONE이었다.
mock fixture(`scenario_infra_failure_001` rev2)의 모양 — `plate_read: FAILED` +
`readout.plate_read_failed` notice — 을 real 경로에서도 만든다.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from daesingo.case import jobs, real_e2e, service
from daesingo.case.adapters import MockFixtureAdapter, RealAdapter
from daesingo.case.domain import Candidate, CaseAggregate
from daesingo.case.view import build_case_view

MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"
FAILED_CODE = "readout.plate_read_failed"


def _fixture(module: str, scenario_id: str) -> dict:
    path = MOCK_ROOT / module / f"scenario_{scenario_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _happy_selected_case() -> CaseAggregate:
    case = CaseAggregate.intake(case_id="case_h001", hints={}, manifest_summary={})
    case.start_search()
    case.receive_candidates(
        [Candidate(candidate_id="candidate_h001", at=None, at_provenance=None, observed="", thumb_ref=None)]
    )
    case.select_candidate("candidate_h001")
    return case


def _plate_state(view: dict) -> str:
    return next(s["state"] for s in view["progress"] if s["step"] == "plate_read")


def test_plate_read_failure_shows_even_when_evidence_exists():
    evidence = _fixture("evidence", "happy_001")["evidence_records"][0]
    view = build_case_view(_happy_selected_case(), evidence_record=evidence, plate_read_status="FAILED")

    assert view["evidence"] is not None
    assert _plate_state(view) == "FAILED"


def test_plate_read_done_when_no_failure_reported():
    evidence = _fixture("evidence", "happy_001")["evidence_records"][0]
    view = build_case_view(_happy_selected_case(), evidence_record=evidence)

    assert _plate_state(view) == "DONE"


def test_failed_plate_read_derives_fixture_notice():
    """notice 모양은 mock fixture가 이미 쓰는 값 그대로다(infra_failure rev2)."""
    fixture_view = _fixture("case", "infra_failure_001")["case_views"][1]
    expected = next(n for n in fixture_view["notices"] if n["code"] == FAILED_CODE)
    assert service.PLATE_READ_FAILED_NOTICE == expected

    view = {
        "evidence": None,
        "candidates": [],
        "package": None,
        "progress": [{"step": "plate_read", "state": "FAILED"}],
        "notices": [],
    }
    assert [n["code"] for n in service.derive_notices(view)["notices"]] == [FAILED_CODE]


def test_no_failure_notice_unless_plate_read_failed():
    for state in ("RUNNING", "DONE", "PARTIAL"):
        view = {
            "evidence": None,
            "candidates": [],
            "package": None,
            "progress": [{"step": "plate_read", "state": state}],
            "notices": [],
        }
        assert service.derive_notices(view)["notices"] == []


def test_real_adapter_projects_readout_run_failure(monkeypatch):
    """real 경로: 판독이 `outcome=FAILED`로 끝나면 CaseView가 실패로 보여 준다."""

    def failed_read_plate(request, **kwargs):
        return SimpleNamespace(outcome="FAILED"), None

    monkeypatch.setattr(real_e2e.readout_api, "read_plate", failed_read_plate)
    scope = MockFixtureAdapter(MOCK_ROOT, "happy_001").get_analysis_scopes()[0]
    case = CaseAggregate.intake(case_id="case_h001_plate_fail", hints={}, manifest_summary={})
    real = RealAdapter(case_id="case_h001_plate_fail", case=case, search_scope=scope, mock_root=MOCK_ROOT)
    case.start_search()
    jobs.issue_coarse_search(case, scope_ref="scope_h001", input_fingerprint="sha1:h001-coarse-search")
    candidates = service.receive_search_candidates(case, real)
    case.select_candidate(candidates[0].candidate_id)

    view = service.build_view_from_adapter(case, real)

    assert view["evidence"]["plate_display"]["info_state"] == "INFO_UNKNOWN"
    assert _plate_state(view) == "FAILED"
    assert FAILED_CODE in [n["code"] for n in view["notices"]]
