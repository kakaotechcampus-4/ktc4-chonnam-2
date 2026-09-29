"""`service.derive_notices()` — 조립된 CaseView 값만으로 발동하는 notice(이슈 #48).

`evidence.location_search_keyword_missing`의 계약 발동 조건은
`evidence.location_display.search_keyword == null`이다(`contract-job-record-case-view.md`
B절 `notices[].code`, 2026-09-14 등재). 정답지는 이 notice가 들어간 case fixture 3개와,
검색어가 있어 대상이 아닌 `happy_001`이다.

`case.situation_response_pending` — #171 C-2(Case 결정): Package 전 결과 화면의 「준비 전」
이유를 notice로 내린다. 발동 조건은 evidence가 있고, 선택된 후보의 `situation_confirmation`이
`NOT_ASKED`이며, `package`가 없을 때다(ADR-EVIDENCE-005 D2-c로 Package가 막힌 상태).
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
PENDING_CODE = "case.situation_response_pending"
DERIVED_CODES = {CODE, PENDING_CODE}


def _case_views(scenario_id: str) -> list[dict]:
    path = MOCK_ROOT / "case" / f"scenario_{scenario_id}.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["case_views"]


def _without_notice(view: dict) -> dict:
    stripped = copy.deepcopy(view)
    stripped["notices"] = [n for n in stripped["notices"] if n["code"] not in DERIVED_CODES]
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
    case.start_search()
    service.receive_search_candidates(case, adapter)
    case.select_candidate("candidate_u001")  # 현재 선택의 evidence만 투영된다(W7 6.6순위)
    view = service.build_view_from_adapter(case, adapter)

    assert view["evidence"]["location_display"]["search_keyword"] is None
    assert [n["code"] for n in view["notices"]] == [CODE]


# ── case.situation_response_pending ─────────────────────────────────────


def test_pending_notice_shape_matches_contract():
    assert service.SITUATION_RESPONSE_PENDING_NOTICE == {
        "code": PENDING_CODE,
        "severity": "INFO",
        "blocking": False,
        "message_key": "notice.situation_response_pending",
        "actions": [],
    }


@pytest.mark.parametrize("scenario_id", ["correction_rerun_001", "plate_reread_001"])
def test_pending_notice_on_evidence_without_response(scenario_id):
    """P·R은 evidence가 있지만 상황 응답 전이라 Package가 없다 — 모든 스냅샷이 대상이다."""
    for expected in _case_views(scenario_id):
        assert expected["evidence"] is not None and expected["package"] is None
        codes = [n["code"] for n in service.derive_notices(_without_notice(expected))["notices"]]
        assert PENDING_CODE in codes


def test_no_pending_notice_after_response():
    """U는 `USER_UNSURE`로 이미 응답했다 — 무응답이 아니다."""
    for view in _case_views("unknown_abstain_partial_001"):
        codes = [n["code"] for n in service.derive_notices(_without_notice(view))["notices"]]
        assert PENDING_CODE not in codes


def test_no_pending_notice_without_evidence():
    """evidence가 아직 없으면(조립 전·실패) 값 화면 자체가 없어 붙이지 않는다(#165 미결)."""
    for view in _case_views("infra_failure_001"):
        assert view["evidence"] is None
        codes = [n["code"] for n in service.derive_notices(_without_notice(view))["notices"]]
        assert PENDING_CODE not in codes


def test_no_pending_notice_when_package_exists():
    view = copy.deepcopy(_case_views("plate_reread_001")[-1])
    view["package"] = {"package_ref": "pkg_x"}
    codes = [n["code"] for n in service.derive_notices(_without_notice(view))["notices"]]
    assert PENDING_CODE not in codes
