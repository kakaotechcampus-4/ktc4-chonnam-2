"""§11 제외 범위였던 `scenario_unknown_abstain_partial_001`(WARN Package + 위치 미확보)을
`build_case_view()` 공개 API로 전체 파리티 검증한다 — `test_scenario_happy_smoke.py`와 같은
패턴(정답지: `data/mock/case/scenario_unknown_abstain_partial_001.json`의 `case_views[-1]`).

이 시나리오가 골랐던 이유: `contract-requirement-report-package.md` §13 "Mock/구현 최소 케이스"가
요구하는 "WARN + 사용자 notice가 있는 Package" 조합을 이 fixture 하나만 만족하고(2026-09-13 확인),
이슈 #47/#48(위치 없는 WARN Package 허용 결정)의 근거 fixture이기도 하다. 이 테스트가 통과한다는
것은 그 결정이 문서로만 존재하는 게 아니라 실제 코드가 재현한다는 뜻이다.

이 시나리오를 재현하려고 이번에 `labels.py`/`view.py`에 추가/정정한 것(§7 원문 근거):
  - `case_type_display`: `visual_event_type.value == null`일 때 `INFO_UNKNOWN`(B절 §7-(1) 규칙 1).
  - `report_type_display`/`package.report_field_states.safety_report_type`: `needs_review == true`가
    `observability`보다 우선한다는 §7-(1) 규칙 3 — 이전 코드는 이 우선순위를 누락하고 있었다.
  - `event_time_display.needs_review`: `resolution_status == NEEDS_REVIEW` 그대로 옮김(§7-(2)) —
    이전 코드는 `False`로 고정돼 있었다.
  - `candidates[].situation_confirmation`: `EvidenceRecord.situation_response.value` 반영.
  - `evidence.review_needed`/`reason_code`: 6개 `*_display` 전체를 보는 집계식(§7, 이슈 #26 B-web-6) —
    이전 코드는 `location`만 봤다.
  - `requirements_package.checks`: fixture 자체에 evidence 원본과 어긋나는 누락이 있어 함께 고쳤다
    (case는 안전 projection만 하고 check를 필터링하지 않는다는 원칙에 따라 fixture 쪽을 고쳤다).
"""
import json
from pathlib import Path

from daesingo.case import jobs
from daesingo.case.adapters import MockFixtureAdapter
from daesingo.case.domain import Candidate, CaseAggregate
from daesingo.case.view import build_case_view

MOCK_ROOT = Path(__file__).resolve().parents[4] / "data" / "mock"
SCENARIO_ID = "unknown_abstain_partial_001"


def _load_case_fixture() -> dict:
    path = MOCK_ROOT / "case" / f"scenario_{SCENARIO_ID}.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def test_unknown_abstain_partial_ready_matches_fixture():
    fixture = _load_case_fixture()
    ready = fixture["case_views"][-1]
    assert ready["stage"] == "READY"

    adapter = MockFixtureAdapter(MOCK_ROOT, SCENARIO_ID)

    case = CaseAggregate.intake(case_id="case_u001", hints={}, manifest_summary={})
    case.start_search()
    jobs.issue_coarse_search(case, scope_ref="scope_u001", input_fingerprint="sha1:u001-coarse-search")

    raw_candidates = adapter.get_candidate_events()
    candidates = [
        Candidate(
            candidate_id=c["candidate_id"],
            at=None,
            at_provenance=None,
            observed=c["summary"],
            thumb_ref=c["thumbnail_ref"],
        )
        for c in raw_candidates
    ]
    case.receive_candidates(candidates)
    case.select_candidate("candidate_u001")

    jobs.issue_plate_read(case, input_fingerprint="sha1:u001-plate-read")
    jobs.issue_overlay_time_read(case, input_fingerprint="sha1:u001-overlay-read")
    jobs.issue_fine_verify(case, input_fingerprint="sha1:u001-fine-verify")

    evidence_record = adapter.get_evidence_record()
    requirement_evidence = adapter.get_requirement_report("EVIDENCE")
    requirement_package = adapter.get_requirement_report("FINAL_PACKAGE")
    report_package = adapter.get_report_package()

    jobs.issue_report_video_export(case, input_fingerprint="sha1:u001-report-video-export")
    case.mark_ready()

    view = build_case_view(
        case,
        evidence_record=evidence_record,
        requirement_report_evidence=requirement_evidence,
        requirement_report_package=requirement_package,
        report_package=report_package,
    )

    # case_rev/candidates[].thumb_ref 등 이 fixture 고유의 누적 이력값이 아니라, projection 결과
    # 전체(stage/progress/candidates/evidence/requirements_*/package)를 바이트 단위로 비교한다.
    assert view["stage"] == ready["stage"]
    assert view["progress"] == ready["progress"]
    assert view["candidates"] == ready["candidates"]
    assert view["evidence"] == ready["evidence"]
    assert view["requirements_evidence"] == ready["requirements_evidence"]
    assert view["requirements_package"] == ready["requirements_package"]
    assert view["package"] == ready["package"]
