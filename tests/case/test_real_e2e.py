"""W5/W6 데드라인 증빙: `scenario_happy_001` 대표 시나리오가 recording→search→readout→
evidence→`CaseView`까지 **전부 real 함수 호출로** 통과하는지 확인한다.

`test_scenario_happy_smoke.py`/`test_service.py`가 `MockFixtureAdapter`로 같은 시나리오를
검증하는 것과 짝을 이룬다 — 이 파일은 "같은 계약 모양이 나오는가"가 아니라 "실제 모듈
호출 체인이 안 끊기고 끝까지 도는가"를 확인한다. 그래서 mock 정답지와 완전히 같은 값을
요구하지 않는다 — id는 이 실행에서 새로 생성되고, `situation_response`/`observation_facts`가
없어(real_e2e.py 「알려진 단순화 2」) `package`는 `None`일 수 있다.
"""
from __future__ import annotations

from pathlib import Path

from daesingo.case import jobs, real_e2e, service
from daesingo.case.adapters import MockFixtureAdapter, RealAdapter
from daesingo.case.domain import CaseAggregate

MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"
SCENARIO_ID = "happy_001"


def _real_scope():
    mock = MockFixtureAdapter(MOCK_ROOT, SCENARIO_ID)
    return mock.get_analysis_scopes()[0]


def _real_hints():
    return MockFixtureAdapter(MOCK_ROOT, SCENARIO_ID).get_hints()


def test_evidence_bundle_uses_real_plate_and_time_values():
    """readout/search/recording을 실제로 호출해서 나온 값이지, mock JSON을 베낀 게
    아니라는 걸 값으로 확인한다 — 세 값 다 `data/mock/readout/scenario_happy_001.json`과
    같지만, 이번엔 `readout.read_plate()`/`read_overlay_time()`을 실제로 실행해서 나온
    결과다(`real_e2e.build_happy_001_evidence_bundle` 내부에서 fixture JSON을 읽지 않음
    — 예외는 모듈 docstring에 적은 time_source_candidates 한 곳뿐)."""
    import daesingo.search as search_module

    scope_dict = _real_scope()
    scope = search_module.AnalysisScope.model_validate(scope_dict)
    candidate = search_module.search_candidates(scope).candidates[0]

    bundle = real_e2e.build_happy_001_evidence_bundle(
        case_id="case_h001_bundle_test", candidate=candidate, scope=scope, mock_root=MOCK_ROOT
    )

    assert bundle.evidence_record["vehicle_number"]["value"] == "12가3456"
    assert bundle.evidence_record["occurred_at"]["value"] == "2026-08-24T18:05:12+09:00"
    assert bundle.requirement_report_evidence["scope"] == "EVIDENCE"
    assert bundle.requirement_report_package["scope"] == "FINAL_PACKAGE"
    # 알려진 단순화 2(situation_response/observation_facts 없음) 때문에 package는 못
    # 만들 수 있다 — 이게 조용한 실패가 아니라 사유가 남는다는 것까지 확인한다.
    if bundle.report_package is None:
        assert bundle.package_error is not None


def test_real_adapter_caches_evidence_bundle():
    """evidence 체인(recording/readout/evidence 여러 호출)은 비용이 있으니, 같은
    `RealAdapter` 인스턴스에서 여러 getter를 불러도 한 번만 계산해야 한다."""
    real = RealAdapter(case_id="case_h001_cache_test", search_scope=_real_scope(), mock_root=MOCK_ROOT)
    record_first = real.get_evidence_record()
    record_second = real.get_evidence_record()
    assert record_first is record_second  # 같은 객체 — 재계산 안 했다는 뜻


def test_real_e2e_happy_path_reaches_ready_caseview():
    """recording→search→후보 선택→readout→evidence 전부 real로 돌려서 `CaseView`가
    `READY`까지 도달하는지 확인한다 — 이번 W5/W6 마감의 증빙 테스트다."""
    scope = _real_scope()
    real = RealAdapter(case_id="case_h001_full_e2e", search_scope=scope, mock_root=MOCK_ROOT)

    case = CaseAggregate.intake(case_id="case_h001_full_e2e", hints=_real_hints(), manifest_summary={})
    case.start_search()
    jobs.issue_coarse_search(case, scope_ref="scope_h001", input_fingerprint="sha1:h001-coarse-search")

    candidates = service.receive_search_candidates(case, real)
    assert len(candidates) == 1
    case.select_candidate(candidates[0].candidate_id)

    jobs.issue_plate_read(case, input_fingerprint="sha1:h001-plate-read-clip_h001")
    jobs.issue_overlay_time_read(case, input_fingerprint="sha1:h001-overlay-read-clip_h001")
    jobs.issue_fine_verify(case, input_fingerprint="sha1:h001-fine-verify-as_h001_fine")
    jobs.issue_report_video_export(case, input_fingerprint="sha1:h001-report-video-export")
    case.mark_ready()

    view = service.build_view_from_adapter(case, real)

    assert view["stage"] == "READY"
    assert view["evidence"]["plate_display"]["value"] == "12가3456"
    assert view["evidence"]["event_time_display"]["value"] == "2026-08-24T18:05:12+09:00"
    assert view["requirements_evidence"]["readiness"] in {"PASS", "WARN"}
    # 이슈 #103 — hints가 더 이상 {}로 고정되지 않는다.
    assert view["hints"] != {}
    # package는 알려진 단순화 2 때문에 None일 수 있다 — 존재 자체를 요구하지 않는다.
    assert view["package"] is None or "package_ref" in view["package"]
