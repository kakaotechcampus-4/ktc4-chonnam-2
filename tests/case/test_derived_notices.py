"""`service.derive_notices()` — 조립된 CaseView 값만으로 발동하는 notice(이슈 #48).

`evidence.location_search_keyword_missing`의 계약 발동 조건은
`evidence.location_display.search_keyword == null`이다(`contract-job-record-case-view.md`
B절 `notices[].code`, 2026-09-14 등재). 정답지는 이 notice가 들어간 case fixture 3개와,
검색어가 있어 대상이 아닌 `happy_001`이다.
"""
import copy
import json
from pathlib import Path

import pytest

from daesingo.case import service
from daesingo.case.adapters import MockFixtureAdapter
from daesingo.case.domain import CaseAggregate

MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"
CODE = "evidence.location_search_keyword_missing"


def _case_views(scenario_id: str) -> list[dict]:
    path = MOCK_ROOT / "case" / f"scenario_{scenario_id}.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["case_views"]


def _without_notice(view: dict) -> dict:
    stripped = copy.deepcopy(view)
    stripped["notices"] = [n for n in stripped["notices"] if n["code"] != CODE]
    return stripped


@pytest.mark.parametrize(
    "scenario_id", ["correction_rerun_001", "plate_reread_001", "unknown_abstain_partial_001"]
)
def test_derives_notice_when_search_keyword_is_null(scenario_id):
    for expected in _case_views(scenario_id):
        if expected["evidence"] is None:
            continue
        assert expected["evidence"]["location_display"]["search_keyword"] is None
        derived = service.derive_notices(_without_notice(expected))
        assert derived["notices"] == expected["notices"]


def test_notice_shape_matches_contract():
    assert service.LOCATION_SEARCH_KEYWORD_MISSING_NOTICE == {
        "code": CODE,
        "severity": "INFO",
        "blocking": False,
        "message_key": "notice.location_search_keyword_missing",
        "actions": [],
    }


def test_no_notice_when_search_keyword_present():
    for view in _case_views("happy_001"):
        if view["evidence"] is None:
            continue
        assert view["evidence"]["location_display"]["search_keyword"] is not None
        assert service.derive_notices(copy.deepcopy(view))["notices"] == view["notices"]


def test_no_notice_before_evidence():
    view = {"evidence": None, "notices": []}
    assert service.derive_notices(view)["notices"] == []


def test_does_not_duplicate_or_mutate_caller_notices():
    view = _without_notice(_case_views("unknown_abstain_partial_001")[-1])
    caller_notices = view["notices"]
    before = list(caller_notices)

    once = service.derive_notices(view)
    twice = service.derive_notices(once)

    assert [n["code"] for n in twice["notices"]].count(CODE) == 1
    assert caller_notices == before


def test_build_view_from_adapter_attaches_notice():
    """실제 진입점(`build_view_from_adapter()`)에서도 붙는지 — 호출자는 notice를 넘기지 않는다."""
    adapter = MockFixtureAdapter(MOCK_ROOT, "unknown_abstain_partial_001")
    case = CaseAggregate.intake(case_id="case_u001", hints={}, manifest_summary={})
    view = service.build_view_from_adapter(case, adapter)

    assert view["evidence"]["location_display"]["search_keyword"] is None
    assert [n["code"] for n in view["notices"]] == [CODE]
