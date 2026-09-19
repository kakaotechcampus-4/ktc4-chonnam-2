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

import pytest

from daesingo.case import correction, jobs, real_e2e, service
from daesingo.case.adapters import MockFixtureAdapter, RealAdapter
from daesingo.case.domain import CaseAggregate

MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"
SCENARIO_ID = "happy_001"


def _real_scope():
    mock = MockFixtureAdapter(MOCK_ROOT, SCENARIO_ID)
    return mock.get_analysis_scopes()[0]


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
    scope = _real_scope()
    case = CaseAggregate.intake(case_id="case_h001_cache_test", hints={}, manifest_summary={})
    case.start_search()
    real = RealAdapter(case_id="case_h001_cache_test", case=case, search_scope=scope, mock_root=MOCK_ROOT)
    candidates = service.receive_search_candidates(case, real)
    case.select_candidate(candidates[0].candidate_id)

    record_first = real.get_evidence_record()
    record_second = real.get_evidence_record()
    assert record_first is record_second  # 같은 객체 — 재계산 안 했다는 뜻


def test_real_adapter_requires_selected_candidate_before_evidence():
    """2026-09-19 수정 — evidence가 case의 실제 선택값을 쓰게 바꾸면서 생긴 안전장치.
    candidate를 아직 선택하지 않은 case로 evidence를 조회하면 조용히 아무 값이나
    돌려주지 않고 명확히 실패해야 한다(Mock의 정직한 실패 원칙과 동일 — 이전엔
    `search.search_candidates()`를 자체적으로 다시 불러 항상 값을 돌려줬었다)."""
    scope = _real_scope()
    case = CaseAggregate.intake(case_id="case_h001_no_selection", hints={}, manifest_summary={})
    case.start_search()
    real = RealAdapter(case_id="case_h001_no_selection", case=case, search_scope=scope, mock_root=MOCK_ROOT)
    service.receive_search_candidates(case, real)  # CANDIDATE_REVIEW까지만, 선택은 안 함

    with pytest.raises(NotImplementedError, match="선택된"):
        real.get_evidence_record()


def test_real_adapter_recomputes_evidence_after_event_time_manual_correction():
    """이슈 #73 WARN ① — 부분 재실행 정책 표 13행(`EVENT_TIME_MANUAL` → "제자리, 요건
    검사만 재발주", "절대 안 건드리는 것: 전부")이 RealAdapter 경로에서 실제로 지켜지는지
    확인한다. `correction.apply_correction()`은 새 `JobRecord`를 발주하지 않는다 —
    `case_rev`만 올리고, `RealAdapter`가 그 변화를 보고 evidence를 다시 계산해 정정을
    반영해야 한다(2026-09-19 수정 전에는 캐시가 영구적이라 이게 안 됐다)."""
    scope = _real_scope()
    case = CaseAggregate.intake(case_id="case_h001_correction_rerun", hints={}, manifest_summary={})
    real = RealAdapter(case_id="case_h001_correction_rerun", case=case, search_scope=scope, mock_root=MOCK_ROOT)

    case.start_search()
    jobs.issue_coarse_search(case, scope_ref="scope_h001", input_fingerprint="sha1:h001-coarse-search")
    candidates = service.receive_search_candidates(case, real)
    case.select_candidate(candidates[0].candidate_id)

    record_before = real.get_evidence_record()
    assert record_before["occurred_at"]["value"] == "2026-08-24T18:05:12+09:00"
    assert record_before["occurred_at"]["user_corrected"] is False

    jobs_before_correction = list(case.job_records)

    corrected_value = "2026-08-24T18:10:00+09:00"
    correction.apply_correction(
        case,
        kind="EVENT_TIME_MANUAL",
        target_field="occurred_at",
        previous_value=record_before["occurred_at"]["value"],
        new_value=corrected_value,
    )

    # "절대 안 건드리는 것: 전부" — Search/Readout/Fine 재실행이 전혀 발주되지 않는다.
    assert case.job_records == jobs_before_correction

    record_after = real.get_evidence_record()
    assert record_after is not record_before  # case_rev 변화로 캐시가 무효화돼 다시 계산됨
    assert record_after["occurred_at"]["value"] == corrected_value
    assert record_after["occurred_at"]["user_corrected"] is True
    assert record_after["occurred_at"]["source"]["kind"] == "case.user_correction"

    # 정정과 무관한 값(번호판)은 내용이 그대로 유지된다 — 이슈 #39와 같은 원칙.
    # (참조 id는 다르다 — `real_e2e.py`가 아직 "요건 검사만" 단위로 쪼개 재실행하지
    # 못하고 recording/search/readout까지 통째로 다시 부르는 하나의 함수라서, 매번
    # 새 readout_id가 생긴다. `RealAdapter`가 발주하는 JobRecord가 없다는 것과, 이
    # glue 함수 내부의 참조 id 재생성은 다른 층위의 문제라 이 이슈 범위에서는 값만
    # 확인한다 — 진짜 세분화된 부분 재실행은 W7 대상.)
    assert record_after["vehicle_number"]["value"] == record_before["vehicle_number"]["value"]
    assert record_after["vehicle_number"]["source"]["kind"] == record_before["vehicle_number"]["source"]["kind"]

    # case_rev가 안 바뀐 재조회는 여전히 캐시를 재사용한다 — 원래 캐시 의도(중복 계산
    # 방지) 자체는 그대로 유지된다.
    assert real.get_evidence_record() is record_after


def test_real_adapter_recomputes_evidence_after_report_type_change_correction():
    """이슈 #73 체크리스트 "다른 correction kind에도 같은 gap이 있는지 확인" —
    `REPORT_TYPE_CHANGE`도 정책 표 12행에서 `EVENT_TIME_MANUAL`과 똑같이 "제자리,
    요건 검사만 재발주"다. `assemble_evidence()`가 `event.*` target_field 정정을
    전부 같은 방식(`correction_heads()`)으로 접합하므로, 위 테스트와 같은 배선
    (`correction_records` 전달 + `case_rev` 캐시 무효화) 하나로 이 kind도 같이
    해결된다는 걸 확인한다 — 별도 코드 경로가 필요 없다."""
    scope = _real_scope()
    case = CaseAggregate.intake(case_id="case_h001_report_type_change", hints={}, manifest_summary={})
    real = RealAdapter(case_id="case_h001_report_type_change", case=case, search_scope=scope, mock_root=MOCK_ROOT)

    case.start_search()
    jobs.issue_coarse_search(case, scope_ref="scope_h001", input_fingerprint="sha1:h001-coarse-search")
    candidates = service.receive_search_candidates(case, real)
    case.select_candidate(candidates[0].candidate_id)

    record_before = real.get_evidence_record()
    assert record_before["event"]["safety_report_type"]["value"] == "TRAFFIC_VIOLATION"

    jobs_before_correction = list(case.job_records)
    correction.apply_correction(
        case,
        kind="REPORT_TYPE_CHANGE",
        target_field="event.safety_report_type",
        previous_value="TRAFFIC_VIOLATION",
        new_value="MOTORCYCLE_VIOLATION",
    )
    assert case.job_records == jobs_before_correction  # 여기도 재실행되는 Job은 없다

    record_after = real.get_evidence_record()
    assert record_after["event"]["safety_report_type"]["value"] == "MOTORCYCLE_VIOLATION"
    assert record_after["event"]["safety_report_type"]["user_corrected"] is True
    assert record_after["event"]["safety_report_type"]["source"]["kind"] == "case.user_correction"


def test_real_adapter_evidence_includes_case_location_hint():
    """이슈 #84 — `real_e2e.py`가 `assemble_evidence()`에 `location_hint`를 아예 안
    넘겨서(`gps_observation=None`만 명시), 공용 case fixture에 `hints.location`이
    있는데도 real 경로의 `EvidenceRecord.location`이 항상 비고 `evidence.location.present`
    하나 때문에 EVIDENCE scope가 WARN으로 내려갔었다. `location_hint`가 없는 case와
    있는 case를 나란히 돌려서 WARN → PASS로 바뀌는 것까지 값으로 확인한다."""
    scope = _real_scope()
    location_hint = "상무중앙로 사거리 부근"  # data/mock/case/scenario_happy_001.json 그대로

    case_without_hint = CaseAggregate.intake(case_id="case_h001_no_location_hint", hints={}, manifest_summary={})
    case_without_hint.start_search()
    real_without_hint = RealAdapter(
        case_id="case_h001_no_location_hint", case=case_without_hint, search_scope=scope, mock_root=MOCK_ROOT
    )
    candidates = service.receive_search_candidates(case_without_hint, real_without_hint)
    case_without_hint.select_candidate(candidates[0].candidate_id)

    record_before = real_without_hint.get_evidence_record()
    assert "location" not in record_before
    assert real_without_hint.get_requirement_report("EVIDENCE")["overall"] == "WARN"

    case_with_hint = CaseAggregate.intake(
        case_id="case_h001_location_hint", hints={"location": location_hint}, manifest_summary={}
    )
    case_with_hint.start_search()
    real_with_hint = RealAdapter(
        case_id="case_h001_location_hint", case=case_with_hint, search_scope=scope, mock_root=MOCK_ROOT
    )
    candidates = service.receive_search_candidates(case_with_hint, real_with_hint)
    case_with_hint.select_candidate(candidates[0].candidate_id)

    record_after = real_with_hint.get_evidence_record()
    assert record_after["location"]["user_hint"]["value"] == location_hint
    assert record_after["location"]["user_hint"]["source"]["kind"] == "case.user_location_hint"
    # gps_observation은 여전히 None이다(recording이 아직 공개 경로를 안 내놓음, 「알려진 단순화」).
    assert "coord" not in record_after["location"]

    report_after = real_with_hint.get_requirement_report("EVIDENCE")
    assert report_after["overall"] == "PASS"
    location_check = next(c for c in report_after["checks"] if c["code"] == "evidence.location.present")
    assert location_check["outcome"] == "PASS"
    assert location_check["reason_code"] == "evidence.location_available"


def test_real_e2e_happy_path_reaches_ready_caseview():
    """recording→search→후보 선택→readout→evidence 전부 real로 돌려서 `CaseView`가
    `READY`까지 도달하는지 확인한다 — 이번 W5/W6 마감의 증빙 테스트다.

    `hints`는 `data/mock/case/scenario_happy_001.json`의 값을 그대로 쓴다 — 특히
    `location`이 real 경로까지 전달돼야 EVIDENCE scope가 PASS까지 간다(이슈 #84,
    수정 전에는 `location_hint`가 안 넘어가 WARN에 머물렀다)."""
    scope = _real_scope()
    case = CaseAggregate.intake(
        case_id="case_h001_full_e2e",
        hints={
            "time": "18시쯤",
            "vehicle": "흰색 SUV",
            "situation": "백색 실선 구간에서 차로변경",
            "location": "상무중앙로 사거리 부근",
        },
        manifest_summary={},
    )
    real = RealAdapter(case_id="case_h001_full_e2e", case=case, search_scope=scope, mock_root=MOCK_ROOT)

    case.start_search()
    jobs.issue_coarse_search(case, scope_ref="scope_h001", input_fingerprint="sha1:h001-coarse-search")

    candidates = service.receive_search_candidates(case, real)
    assert len(candidates) == 1
    case.select_candidate(candidates[0].candidate_id)
    assert case.selection_rev == 1  # RealAdapter가 이 값을 그대로 evidence에 넘긴다(2026-09-19)

    jobs.issue_plate_read(case, input_fingerprint="sha1:h001-plate-read-clip_h001")
    jobs.issue_overlay_time_read(case, input_fingerprint="sha1:h001-overlay-read-clip_h001")
    jobs.issue_fine_verify(case, input_fingerprint="sha1:h001-fine-verify-as_h001_fine")
    jobs.issue_report_video_export(case, input_fingerprint="sha1:h001-report-video-export")
    case.mark_ready()

    view = service.build_view_from_adapter(case, real)

    assert view["stage"] == "READY"
    assert view["evidence"]["plate_display"]["value"] == "12가3456"
    assert view["evidence"]["event_time_display"]["value"] == "2026-08-24T18:05:12+09:00"
    # 이슈 #84 수정분 — location_hint가 real 경로까지 전달돼 location_display가 채워지고,
    # 그 결과 EVIDENCE scope가 WARN이 아니라 PASS까지 간다(수정 전에는 여기서 늘 WARN이었음).
    assert view["evidence"]["location_display"]["value"] == "상무중앙로 사거리 부근"
    assert view["evidence"]["location_display"]["info_state"] == "INFO_NEEDS_REVIEW"
    assert view["evidence"]["location_display"]["coord"] is None  # gps_observation은 여전히 None(알려진 단순화)
    assert view["requirements_evidence"]["readiness"] == "PASS"
    # package는 알려진 단순화 2 때문에 None일 수 있다 — 존재 자체를 요구하지 않는다.
    assert view["package"] is None or "package_ref" in view["package"]
