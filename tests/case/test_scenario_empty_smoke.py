"""`scenario_empty_001`(검색은 성공했지만 후보 0개) 전체 파리티 — §11 제외 범위였던
시나리오를 `build_case_view()` 공개 API 레벨에서 fixture와 바이트 단위로 비교한다.

이 시나리오를 재현하면서 정정한 것:
  - `domain.CaseAggregate.receive_candidates([])`가 예전엔 `SEARCHING`에 머문다고
    잘못 가정돼 있었다 — 실제 fixture(`case_rev:2`, `stage=CANDIDATE_REVIEW`)를 보면
    빈 배열도 검색 성공이므로 `CANDIDATE_REVIEW`로 전진한다(`test_domain.py` 참고).
  - `notices[]`(`search.no_candidates`, 비차단 INFO, `actions=[EDIT_HINT, RETRY_SEARCH]`)는
    `build_case_view()`가 자동 합성하지 않는다 — 호출자가 채운다(§11 제외 범위, 이 테스트도
    `test_scenario_happy_smoke.py`의 rev1(SEARCHING) 뷰가 `running_jobs`를 직접 채워 넣는
    것과 같은 패턴으로 fixture 값을 그대로 넘긴다).
"""
import json
from pathlib import Path

from daesingo.case import jobs
from daesingo.case.adapters import MockFixtureAdapter
from daesingo.case.domain import CaseAggregate
from daesingo.case.view import build_case_view

MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"
SCENARIO_ID = "empty_001"


def _load_case_fixture() -> dict:
    path = MOCK_ROOT / "case" / f"scenario_{SCENARIO_ID}.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def test_empty_candidates_matches_fixture():
    fixture = _load_case_fixture()
    ready = fixture["case_views"][-1]
    assert ready["stage"] == "CANDIDATE_REVIEW"

    adapter = MockFixtureAdapter(MOCK_ROOT, SCENARIO_ID)

    case = CaseAggregate.intake(
        case_id="case_e001",
        hints=ready["hints"],
        manifest_summary=ready["manifest_summary"],
    )
    case.start_search()
    jobs.issue_coarse_search(case, scope_ref="scope_e001", input_fingerprint="sha1:e001-coarse-search")

    raw_candidates = adapter.get_candidate_events()
    assert raw_candidates == []  # 전제 확인 — 검색은 성공했지만 후보가 0개인 fixture

    case.receive_candidates([])

    view = build_case_view(
        case,
        notices=ready["notices"],  # notice 자동 합성은 §11 제외 범위 — fixture 값을 그대로 공급
    )

    assert view["stage"] == ready["stage"]
    assert view["case_rev"] == ready["case_rev"]
    assert view["progress"] == ready["progress"]
    assert view["hints"] == ready["hints"]
    assert view["manifest_summary"] == ready["manifest_summary"]
    assert view["candidates"] == []
    assert view["evidence"] is None
    assert view["requirements_evidence"] is None
    assert view["requirements_package"] is None
    assert view["package"] is None
    assert view["running_jobs"] == []
    assert view["notices"] == ready["notices"]
