"""`case/service.py`가 스모크 테스트에서 손으로 짜던 adapter↔domain 연결을 그대로
재현하는지 확인한다. `test_scenario_happy_smoke.py`를 대체하지 않는다 — 그 파일은
"case가 계약을 재현하는가"를 검증하고, 이 파일은 "service.py로 뽑아낸 함수가 그 연결을
그대로 재현하는가"만 검증한다.
"""
import json
from pathlib import Path

from daesingo.case import jobs, service
from daesingo.case.adapters import MockFixtureAdapter, RealAdapter
from daesingo.case.domain import CaseAggregate

MOCK_ROOT = Path(__file__).resolve().parents[4] / "data" / "mock"
SCENARIO_ID = "happy_001"


def _load_case_fixture() -> dict:
    path = MOCK_ROOT / "case" / f"scenario_{SCENARIO_ID}.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def test_receive_search_candidates_matches_manual_wiring():
    fixture = _load_case_fixture()
    ready = fixture["case_views"][-1]
    adapter = MockFixtureAdapter(MOCK_ROOT, SCENARIO_ID)

    case = CaseAggregate.intake(case_id="case_h001_svc", hints={}, manifest_summary={})
    case.start_search()
    jobs.issue_coarse_search(case, scope_ref="scope_h001", input_fingerprint="sha1:h001-coarse-search")

    candidates = service.receive_search_candidates(case, adapter)

    assert len(candidates) == len(ready["candidates"])
    assert candidates[0].candidate_id == ready["candidates"][0]["candidate_id"]
    assert candidates[0].observed == ready["candidates"][0]["observed"]
    # service.receive_search_candidates가 case.receive_candidates까지 이미 호출했으므로
    # case 쪽 상태에도 반영돼 있어야 한다 — 호출자가 따로 case.receive_candidates를
    # 부르지 않아도 된다는 것이 이 함수의 계약이다.
    assert len(case.candidates) == len(ready["candidates"])


def test_build_view_from_adapter_matches_manual_wiring():
    fixture = _load_case_fixture()
    ready = fixture["case_views"][-1]
    adapter = MockFixtureAdapter(MOCK_ROOT, SCENARIO_ID)

    case = CaseAggregate.intake(case_id="case_h001_svc2", hints={}, manifest_summary={})
    case.start_search()
    jobs.issue_coarse_search(case, scope_ref="scope_h001", input_fingerprint="sha1:h001-coarse-search")
    service.receive_search_candidates(case, adapter)
    case.select_candidate(ready["candidates"][0]["candidate_id"])

    jobs.issue_plate_read(case, input_fingerprint="sha1:h001-plate-read-clip_h001")
    jobs.issue_overlay_time_read(case, input_fingerprint="sha1:h001-overlay-read-clip_h001")
    jobs.issue_fine_verify(case, input_fingerprint="sha1:h001-fine-verify-as_h001_fine")
    jobs.issue_report_video_export(case, input_fingerprint="sha1:h001-report-video-export")
    case.mark_ready()

    view = service.build_view_from_adapter(case, adapter)

    # test_scenario_happy_smoke.py의 정답지 비교 항목과 동일한 부분집합만 비교한다 —
    # 이 테스트의 목적은 "값이 옳은가"(이미 그 파일이 검증)가 아니라 "service.py를
    # 거쳐도 같은 값이 나오는가"다.
    assert view["stage"] == ready["stage"]
    assert view["evidence"] == ready["evidence"]
    assert view["requirements_evidence"] == ready["requirements_evidence"]
    assert view["requirements_package"] == ready["requirements_package"]
    assert view["package"]["report_fields"] == ready["package"]["report_fields"]


def test_real_adapter_is_not_ready_yet():
    """`RealAdapter`는 아직 골격뿐이라는 것 자체를 회귀 테스트로 고정한다 — 어느 모듈이든
    실제로 채워지면 그 메서드에 대해서는 이 테스트가 깨져야 하고(= 알아채야 하고), 그때
    이 테스트를 그 메서드만 빼고 좁히면 된다.
    """
    adapter = RealAdapter(case_id="case_real_placeholder")
    for method in (
        adapter.get_candidate_events,
        adapter.get_analysis_scopes,
        adapter.get_evidence_record,
        adapter.get_evidence_records,
        adapter.get_report_package,
        adapter.get_job_executions,
    ):
        try:
            method()
        except NotImplementedError:
            continue
        raise AssertionError(f"{method} should still raise NotImplementedError")
