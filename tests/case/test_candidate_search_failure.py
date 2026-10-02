"""후보 탐색 **실패**를 「찾았지만 후보 없음」과 구분한다(PR #187 리뷰 김대원 후속).

search는 실패하면 후보 0개의 `FAILED` AnalysisRun을 돌려준다(`search/runs.py`). 예전엔 case가
`outcome`을 보지 않고 빈 후보 목록을 받아 `CANDIDATE_REVIEW`로 진행해, web이 「결과 없음」
(NO_RESULT)으로 그렸다. 계약 §7 `RESUME_SEARCH` 행: 실패 Run은 투영 대상을 바꾸지 않는다.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from daesingo.case import service
from daesingo.case.adapters import MockFixtureAdapter, RealAdapter
from daesingo.case.domain import Candidate, CaseAggregate
from daesingo.case.view import build_case_view

MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"
FAILED_CODE = "search.candidate_search_failed"


def _searching_case() -> CaseAggregate:
    case = CaseAggregate.intake(case_id="case_sf", hints={}, manifest_summary={})
    case.start_search()
    return case


class _FailedSearchAdapter:
    """후보 0개 + outcome FAILED를 돌려주는 최소 adapter."""

    def get_candidate_events(self):
        return []

    def get_candidate_search_outcome(self):
        return "FAILED"


def _coarse_state(view: dict) -> str:
    return next(s["state"] for s in view["progress"] if s["step"] == "coarse_search")


def test_failed_search_stays_searching_and_keeps_candidates():
    case = _searching_case()
    kept = [Candidate(candidate_id="c_prev", at=None, at_provenance=None, observed="", thumb_ref=None)]
    case.candidates = list(kept)
    rev_before = case.case_rev

    received = service.receive_search_candidates(case, _FailedSearchAdapter())

    assert received == []
    assert case.stage == "SEARCHING"
    assert [c.candidate_id for c in case.candidates] == ["c_prev"]
    assert case.candidate_search_failed is True
    assert case.case_rev == rev_before  # 실패는 사용자 요청이 아니라 결과다


def test_failed_search_view_shows_failure_not_no_result():
    case = _searching_case()
    service.receive_search_candidates(case, _FailedSearchAdapter())

    view = service.derive_notices(build_case_view(case))

    assert view["stage"] == "SEARCHING"
    assert _coarse_state(view) == "FAILED"
    assert [n["code"] for n in view["notices"]] == [FAILED_CODE]
    assert service.CANDIDATE_SEARCH_FAILED_NOTICE["actions"] == ["RETRY_SEARCH"]


def test_successful_retry_clears_failure():
    case = _searching_case()
    service.receive_search_candidates(case, _FailedSearchAdapter())

    service.receive_search_candidates(case, MockFixtureAdapter(MOCK_ROOT, "happy_001"))

    assert case.candidate_search_failed is False
    assert case.stage == "CANDIDATE_REVIEW"
    view = service.derive_notices(build_case_view(case))
    assert _coarse_state(view) == "DONE"
    assert FAILED_CODE not in [n["code"] for n in view["notices"]]


def test_successful_empty_search_is_still_no_candidates():
    """찾았지만 없음(SUCCEEDED + 0건)은 실패가 아니다 — 기존대로 CANDIDATE_REVIEW."""
    case = _searching_case()
    service.receive_search_candidates(case, MockFixtureAdapter(MOCK_ROOT, "empty_001"))

    assert case.stage == "CANDIDATE_REVIEW"
    assert case.candidate_search_failed is False


def test_mock_adapter_reports_fixture_outcome():
    assert MockFixtureAdapter(MOCK_ROOT, "happy_001").get_candidate_search_outcome() == "SUCCEEDED"


def test_real_adapter_reports_failed_search(monkeypatch):
    failed = SimpleNamespace(candidates=(), analysis_run=SimpleNamespace(outcome="FAILED"))
    monkeypatch.setattr("daesingo.case.adapters.search_module.search_candidates", lambda scope: failed)
    scope = MockFixtureAdapter(MOCK_ROOT, "happy_001").get_analysis_scopes()[0]
    case = _searching_case()
    real = RealAdapter(case_id="case_sf", case=case, search_scope=scope, mock_root=MOCK_ROOT)

    service.receive_search_candidates(case, real)

    assert case.stage == "SEARCHING"
    assert case.candidate_search_failed is True
