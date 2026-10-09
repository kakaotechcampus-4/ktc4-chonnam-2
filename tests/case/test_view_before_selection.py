"""선택 전(후보 0개 · 탐색 중) CaseView — real 진입점에서도 만들어져야 한다.

`RealAdapter`는 선택된 candidate 없이 evidence를 조회하면 명확히 실패한다(#92 안전장치). 그런데
`build_view_from_adapter()`가 선택 전에도 evidence getter를 불러, 후보 0개(`scenario_empty_001`)나
탐색 중인 case는 real 경로에서 CaseView를 만들지 못했다 — 「후보 없음」 화면(#31 W-1)이 real
경로에서는 나올 수 없었다. 선택 전에는 downstream 값이 없다는 것을 case 상태로 판단하고, adapter
가드는 그대로 둔다.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from daesingo import search as search_module
from daesingo.case import service
from daesingo.case.adapters import MockFixtureAdapter, RealAdapter
from daesingo.case.domain import CaseAggregate

MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"
CODE = "search.no_candidates"


def _real(scenario_id: str) -> tuple[CaseAggregate, RealAdapter]:
    scope = search_module.AnalysisScope.model_validate(
        MockFixtureAdapter(MOCK_ROOT, scenario_id).get_analysis_scopes()[0]
    )
    case = CaseAggregate.intake(case_id=f"case_{scenario_id}", hints={}, manifest_summary={})
    case.start_search()
    return case, RealAdapter(case_id=case.case_id, case=case, search_scope=scope, mock_root=MOCK_ROOT)


def _codes(view: dict) -> list[str]:
    return [n["code"] for n in view["notices"]]


def test_no_candidates_view_is_built_from_real_adapter():
    case, real = _real("empty_001")
    assert service.receive_search_candidates(case, real) == []
    assert case.select_top_ranked() is None

    view = service.build_view_from_adapter(case, real)

    assert view["stage"] == "CANDIDATE_REVIEW"
    assert view["candidates"] == []
    assert view["evidence"] is None and view["package"] is None
    assert _codes(view) == [CODE]


def test_no_candidates_notice_matches_mock_fixture():
    """모양은 `scenario_empty_001` fixture가 먼저 쓰던 값 그대로다(이슈 #31 W-1로 actions 등재)."""
    with open(MOCK_ROOT / "case" / "scenario_empty_001.json", encoding="utf-8") as fh:
        expected = json.load(fh)["case_views"][-1]
    assert service.NO_CANDIDATES_NOTICE == expected["notices"][0]

    stripped = copy.deepcopy(expected)
    stripped["notices"] = []
    assert service.derive_notices(stripped)["notices"] == expected["notices"]
    # 이미 있으면 중복하지 않는다.
    assert service.derive_notices(copy.deepcopy(expected))["notices"] == expected["notices"]


def test_view_while_searching_is_built_without_touching_evidence():
    case, real = _real("happy_001")

    view = service.build_view_from_adapter(case, real)

    assert view["stage"] == "SEARCHING"
    assert view["evidence"] is None
    assert CODE not in _codes(view)


def test_adapter_guard_still_fails_loudly_before_selection():
    """#92 안전장치는 그대로 — 선택 전 evidence를 직접 조회하면 조용히 비지 않고 실패한다."""
    case, real = _real("empty_001")
    service.receive_search_candidates(case, real)

    with pytest.raises(NotImplementedError):
        real.get_evidence_record()


def test_mark_ready_is_noop_before_selection():
    case, real = _real("empty_001")
    service.receive_search_candidates(case, real)

    assert service.mark_ready_if_package_ready(case, real) is False
    assert case.stage == "CANDIDATE_REVIEW"


def test_no_candidates_notice_only_for_empty_candidate_review():
    case, real = _real("happy_001")
    service.receive_search_candidates(case, real)
    case.select_top_ranked()

    view = service.build_view_from_adapter(case, real)

    assert view["candidates"]
    assert CODE not in _codes(view)
