"""#122 — `CaseView.candidates[].rank` 투영 + rank1 자동 선택(#168 결정 1).

- rank는 search `CandidateEvent.rank`를 그대로 옮긴다(case가 다시 매기지 않는다).
- `candidates[]`는 rank 오름차순으로 내린다.
- 자동 선택은 최근 Run(= case가 들고 있는 후보 목록)의 `rank=1`이고, stale이면 고르지 않는다.
- web은 `selected`로 진행 중 후보를 판단하고 `rank`는 순서 표시에만 쓴다(신유민 확인, #122).
"""
from __future__ import annotations

from pathlib import Path

from daesingo.case import service
from daesingo.case.adapters import MockFixtureAdapter, RealAdapter
from daesingo.case.domain import Candidate, CaseAggregate
from daesingo.case.view import build_case_view

MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"


def _candidate(cid: str, rank: int | None, *, stale: bool = False) -> Candidate:
    return Candidate(
        candidate_id=cid, at=None, at_provenance=None, observed="", thumb_ref=None,
        rank=rank, stale_revision=stale,
    )


def _searching_case() -> CaseAggregate:
    case = CaseAggregate.intake(case_id="case_rank", hints={}, manifest_summary={})
    case.start_search()
    return case


def test_receive_search_candidates_carries_rank():
    case = _searching_case()
    candidates = service.receive_search_candidates(case, MockFixtureAdapter(MOCK_ROOT, "happy_001"))

    assert [c.rank for c in candidates] == [1]


def test_real_adapter_candidate_events_include_rank():
    scope = MockFixtureAdapter(MOCK_ROOT, "happy_001").get_analysis_scopes()[0]
    case = _searching_case()
    real = RealAdapter(case_id="case_rank", case=case, search_scope=scope, mock_root=MOCK_ROOT)

    assert [c["rank"] for c in real.get_candidate_events()] == [1]


def test_view_projects_rank_in_ascending_order():
    case = _searching_case()
    case.receive_candidates([_candidate("c3", 3), _candidate("c1", 1), _candidate("c2", 2)])

    view = build_case_view(case)

    assert [(c["candidate_id"], c["rank"]) for c in view["candidates"]] == [("c1", 1), ("c2", 2), ("c3", 3)]


def test_auto_select_picks_rank_one():
    case = _searching_case()
    case.receive_candidates([_candidate("c2", 2), _candidate("c1", 1)])

    chosen = case.select_top_ranked()

    assert chosen == "c1"
    assert case.stage == "EVIDENCE_REVIEW"
    assert [c.candidate_id for c in case.candidates if c.selected] == ["c1"]


def test_auto_select_skips_stale_rank_one():
    """최신 후보가 아니면 가장 유력한 후보를 임의로 정하지 않는다(core-user-flow §8)."""
    case = _searching_case()
    case.receive_candidates([_candidate("c1", 1, stale=True), _candidate("c2", 2)])

    assert case.select_top_ranked() is None
    assert case.stage == "CANDIDATE_REVIEW"
    assert not any(c.selected for c in case.candidates)


def test_auto_select_without_candidates_is_noop():
    case = _searching_case()
    case.receive_candidates([])

    assert case.select_top_ranked() is None
    assert case.stage == "CANDIDATE_REVIEW"
