"""PM 리뷰 회귀 테스트(2026-09-23, PR #147) — `stage=READY`인데 `report_package`가
아직 없는 조합(예: `PackageNotReady`로 BLOCKED)에서 `progress[].package_assembly`가
정직하게 `PENDING`으로 나오는지 고정한다.

발견 경위: `youtube_clip_01` real E2E 실행(첫 OBSERVED 결과)에서
`evidence_record`는 있는데(`verification=OBSERVED`) `occurred_at`/
`situation_response` 미확보로 `report_package`가 `None`이었다. 그런데
`_build_progress()`에 있던 `if stage_rank == 4: progress = {s: "DONE" for s in
_PROGRESS_STEPS}` 블랭킷 override가, 바로 위에서 이미 올바르게 계산해둔
`package_assembly=PENDING`을 무시하고 `DONE`으로 덮어써서 CaseView에 허위
상태가 찍혔다 — PM 리뷰로 발견, 이 파일에서 override를 제거해 고쳤다.
"""
from daesingo.case.domain import Candidate, CaseAggregate
from daesingo.case.view import _build_progress


def _case_at_ready_with_selected_candidate() -> CaseAggregate:
    case = CaseAggregate.intake(case_id="case_progress_test", hints={}, manifest_summary={})
    case.start_search()
    case.receive_candidates(
        [
            Candidate(
                candidate_id="candidate_progress_test",
                at=None,
                at_provenance="recording.timeline_relative_only",
                observed="테스트용 후보",
                thumb_ref=None,
            )
        ]
    )
    case.select_candidate("candidate_progress_test")
    case.mark_ready()
    return case


def test_package_assembly_is_pending_when_evidence_exists_but_package_does_not():
    case = _case_at_ready_with_selected_candidate()
    assert case.stage == "READY"

    progress = _build_progress(
        case,
        evidence_record={"record_ref": {"kind": "evidence_record", "ref": "er_test_001"}},
        report_package=None,
        requirement_report_evidence={"readiness": "UNKNOWN", "checks": []},
    )

    by_step = {p["step"]: p["state"] for p in progress}
    assert by_step["package_assembly"] == "PENDING"
    # 나머지 7단계는 그대로 DONE이어야 한다 — evidence/requirement는 실제로 조립됐다.
    for step in (
        "file_intake",
        "coarse_search",
        "candidate_review",
        "plate_read",
        "overlay_time_read",
        "evidence_assembly",
        "requirement_check",
    ):
        assert by_step[step] == "DONE", f"{step} expected DONE, got {by_step[step]}"


def test_all_eight_steps_done_when_package_also_exists():
    """package_assembly까지 실제로 완성된 happy path는 여전히 8단계 전부 DONE이어야
    한다 — override를 지웠어도 이 결과가 자연스럽게 나오는지 확인(회귀 방지)."""
    case = _case_at_ready_with_selected_candidate()

    progress = _build_progress(
        case,
        evidence_record={"record_ref": {"kind": "evidence_record", "ref": "er_test_001"}},
        report_package={"package_ref": {"kind": "report_package", "ref": "pkg_test_001"}},
        requirement_report_evidence={"readiness": "PASS", "checks": []},
    )

    by_step = {p["step"]: p["state"] for p in progress}
    assert all(state == "DONE" for state in by_step.values()), by_step
