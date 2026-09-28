"""#184 — `CaseView.candidates[].marker_ms`: 후보 비교 타임라인의 마커 위치.

- search `CandidateEvent.span.representative_ms`(그 후보 timeline revision 기준 상대 ms)를 그대로
  옮긴다. case는 값을 계산하거나 보정하지 않는다.
- stale 후보(과거 timeline revision 기준)는 `null` — rebase가 기존 원본 배치를 유지한다는 보장을
  recording에 확인하기 전까지(#184 case 답변).
"""
from __future__ import annotations

from pathlib import Path

from daesingo.case import service
from daesingo.case.adapters import MockFixtureAdapter, RealAdapter
from daesingo.case.domain import Candidate, CaseAggregate
from daesingo.case.view import build_case_view

MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"


def _searching_case() -> CaseAggregate:
    case = CaseAggregate.intake(case_id="case_marker", hints={}, manifest_summary={})
    case.start_search()
    return case


def test_receive_search_candidates_carries_representative_ms():
    case = _searching_case()
    candidates = service.receive_search_candidates(case, MockFixtureAdapter(MOCK_ROOT, "happy_001"))

    assert [c.representative_ms for c in candidates] == [312480]


def test_real_adapter_candidate_events_include_span():
    scope = MockFixtureAdapter(MOCK_ROOT, "happy_001").get_analysis_scopes()[0]
    real = RealAdapter(case_id="case_marker", case=_searching_case(), search_scope=scope, mock_root=MOCK_ROOT)

    assert [c["span"]["representative_ms"] for c in real.get_candidate_events()] == [312480]


def _case_with(candidate: Candidate) -> CaseAggregate:
    case = _searching_case()
    case.receive_candidates([candidate])
    return case


def test_marker_ms_is_representative_ms_for_current_revision():
    case = _case_with(Candidate(candidate_id="c1", at=None, at_provenance=None, observed="", thumb_ref=None,
                                rank=1, representative_ms=512000, timeline_revision=1))

    view = build_case_view(case, current_timeline_revision=1)

    assert view["candidates"][0]["marker_ms"] == 512000


def test_marker_ms_is_null_for_stale_candidate():
    case = _case_with(Candidate(candidate_id="c1", at=None, at_provenance=None, observed="", thumb_ref=None,
                                rank=1, representative_ms=512000, timeline_revision=1))

    view = build_case_view(case, current_timeline_revision=2)

    assert view["candidates"][0]["stale_revision"] is True
    assert view["candidates"][0]["marker_ms"] is None


def test_marker_ms_is_null_when_unknown():
    case = _case_with(Candidate(candidate_id="c1", at=None, at_provenance=None, observed="", thumb_ref=None, rank=1))

    assert build_case_view(case)["candidates"][0]["marker_ms"] is None
