"""1차 구현 최소 기준: 공용 Fixture로 Happy Path 1개(scenario_happy_001)를 재현한다.

recording/search/readout/evidence는 아직 코드가 없으므로 `MockFixtureAdapter`로 그
모듈들의 산출물(Canonical Contract 모양)을 대신 읽는다 — case 코드 자체는 이 어댑터
인터페이스만 알고, 실제 구현이 생기면 이 어댑터만 교체하면 된다.

비교 대상: `data/mock/case/scenario_happy_001.json`의 `case_views[]`(case 자신의
Producer fixture, 정답지 역할). 이 테스트가 통과한다는 것은 "문서와 Mock JSON만 준비된
상태"가 아니라 실제 코드가 그 계약을 재현한다는 뜻이다.
"""
import json
from pathlib import Path

from daesingo.case import jobs
from daesingo.case.adapters import MockFixtureAdapter
from daesingo.case.domain import Candidate, CaseAggregate
from daesingo.case.view import build_case_view

# repo_root/data/mock — conftest.py가 sys.path에 src/를 얹어주지만, 이 값은 import에
# 얽히지 않게 이 파일에서 직접 계산한다(테스트 파일 간 relative import를 피한다).
MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"

SCENARIO_ID = "happy_001"


def _load_case_fixture() -> dict:
    path = MOCK_ROOT / "case" / f"scenario_{SCENARIO_ID}.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def test_happy_path_rev1_searching_matches_fixture():
    fixture = _load_case_fixture()
    rev1 = fixture["case_views"][0]
    assert rev1["stage"] == "SEARCHING"

    case = CaseAggregate.intake(
        case_id=rev1["case_id"],
        hints=rev1["hints"],
        manifest_summary=rev1["manifest_summary"],
    )
    case.start_search()
    jobs.issue_coarse_search(case, scope_ref="scope_h001", input_fingerprint="sha1:h001-coarse-search")

    view = build_case_view(
        case,
        running_jobs=[
            {
                "job_id": case.job_records[0]["job_id"],
                "kind": "COARSE_SEARCH",
                "label_key": "job.generic_processing",
                "status": "RUNNING",
            }
        ],
    )

    assert view["stage"] == rev1["stage"]
    assert view["case_rev"] == rev1["case_rev"]
    assert view["progress"] == rev1["progress"]
    assert view["hints"] == rev1["hints"]
    assert view["manifest_summary"] == rev1["manifest_summary"]
    assert view["candidates"] == []
    assert view["evidence"] is None


def test_happy_path_ready_matches_fixture():
    fixture = _load_case_fixture()
    ready = fixture["case_views"][-1]
    assert ready["stage"] == "READY"

    adapter = MockFixtureAdapter(MOCK_ROOT, SCENARIO_ID)

    # ── case 스스로 진행시키는 부분 (도메인 로직) ──────────────────────────
    case = CaseAggregate.intake(case_id="case_h001", hints={}, manifest_summary={})
    case.start_search()
    jobs.issue_coarse_search(case, scope_ref="scope_h001", input_fingerprint="sha1:h001-coarse-search")

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
    case.select_candidate("candidate_h001")

    jobs.issue_plate_read(case, input_fingerprint="sha1:h001-plate-read-clip_h001")
    jobs.issue_overlay_time_read(case, input_fingerprint="sha1:h001-overlay-read-clip_h001")
    jobs.issue_fine_verify(case, input_fingerprint="sha1:h001-fine-verify-as_h001_fine")

    # ── 다른 모듈이 (아직 stub이지만) 결과를 만들어줬다고 가정 ─────────────
    evidence_record = adapter.get_evidence_record()
    requirement_evidence = adapter.get_requirement_report("EVIDENCE")
    requirement_package = adapter.get_requirement_report("FINAL_PACKAGE")
    report_package = adapter.get_report_package()

    jobs.issue_report_video_export(case, input_fingerprint="sha1:h001-report-video-export")
    case.mark_ready()

    view = build_case_view(
        case,
        evidence_record=evidence_record,
        requirement_report_evidence=requirement_evidence,
        requirement_report_package=requirement_package,
        report_package=report_package,
    )

    # 이 1차 구현이 실제로 재현하기로 한 부분만 정답지와 비교한다(§11 제외 범위 참고 —
    # manifest_summary/hints는 이 테스트에서 임의로 비워서 시작했으므로 비교하지 않는다).
    assert view["stage"] == ready["stage"]
    assert view["progress"] == ready["progress"]
    assert view["candidates"][0]["candidate_id"] == ready["candidates"][0]["candidate_id"]
    assert view["candidates"][0]["observed"] == ready["candidates"][0]["observed"]
    assert view["candidates"][0]["selected"] is True
    assert view["evidence"] == ready["evidence"]
    assert view["requirements_evidence"] == ready["requirements_evidence"]
    assert view["requirements_package"] == ready["requirements_package"]
    assert view["package"]["report_fields"] == ready["package"]["report_fields"]
    assert view["package"]["report_field_states"] == ready["package"]["report_field_states"]
    assert view["package"]["unconfirmed_fields"] == ready["package"]["unconfirmed_fields"]
    assert view["package"]["artifact_ref"] == ready["package"]["artifact_ref"]
    assert view["package"]["capabilities"] == ready["package"]["capabilities"]
