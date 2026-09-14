from pathlib import Path

from daesingo.case.adapters import MockFixtureAdapter
from daesingo.case.domain import CaseAggregate
from daesingo.case import jobs

MOCK_ROOT = Path(__file__).resolve().parents[4] / "data" / "mock"


def _ready_case() -> CaseAggregate:
    case = CaseAggregate.intake("case_t002", hints={}, manifest_summary={})
    case.start_search()
    return case


def test_issue_job_always_mints_new_job_id():
    case = _ready_case()
    j1 = jobs.issue_plate_read(case, input_fingerprint="fp1")
    j2 = jobs.issue_plate_read(case, input_fingerprint="fp1", force_rerun=True)
    assert j1["job_id"] != j2["job_id"]
    assert j1["kind"] == j2["kind"] == "PLATE_READ"
    assert j1["force_rerun"] is False
    assert j2["force_rerun"] is True
    assert case.job_records == [j1, j2]


def test_resume_search_issues_new_job_id_not_same_job_id_plus_attempt():
    """2026-09-13 ERD 결정: "이어서 찾기"도 새 job_id — 같은 job_id+attempt 증가가 아니다."""
    case = _ready_case()
    original = jobs.issue_coarse_search(case, scope_ref="scope1", input_fingerprint="fp-coarse")
    resumed = jobs.issue_resume_search(case, scope_ref="scope1", input_fingerprint="fp-coarse")
    assert resumed["job_id"] != original["job_id"]
    assert resumed["kind"] == "COARSE_SEARCH"
    assert resumed["force_rerun"] is True


def test_plate_reread_is_force_rerun_new_job():
    case = _ready_case()
    first = jobs.issue_plate_read(case, input_fingerprint="fp")
    reread = jobs.issue_plate_reread(case, input_fingerprint="fp")
    assert reread["job_id"] != first["job_id"]
    assert reread["force_rerun"] is True


def test_issue_needed_jobs_maps_plate_reread_need_and_reuses_fingerprint():
    """`EvidenceNeeds.items` → Job Intent 자동 매핑(`contract-evidence-record-needs.md` §8.1/§8.2).
    `scenario_plate_reread_001`의 evidence_needs[0](basis=ev_p001)에는 `PLATE_REREAD` 1건이
    있고, 그걸 처리한 실제 JobRecord(`job_p001_plate_reread`)의 `input_fingerprint`가 원본
    `PLATE_READ` job(`job_p001_plate`)과 완전히 동일하다 — case가 새로 지문을 계산하지 않고
    "같은 입력을 다시 본다"는 뜻으로 재사용한다는 근거."""
    adapter = MockFixtureAdapter(MOCK_ROOT, "plate_reread_001")
    evidence_needs = adapter.get_evidence_needs()
    assert len(evidence_needs) == 2  # 전제 확인 — v1(need 1건)/v2(need 0건, 재판독 성공 후)
    need_v1, need_v2 = evidence_needs
    assert [item["kind"] for item in need_v1["items"]] == ["PLATE_REREAD"]
    assert need_v2["items"] == []

    case = _ready_case()
    original = jobs.issue_plate_read(case, input_fingerprint="sha1:p001-plate-read-clip_p001")

    issued = jobs.issue_needed_jobs(case, need_v1)
    assert len(issued) == 1
    reread = issued[0]
    assert reread["kind"] == "PLATE_READ"
    assert reread["force_rerun"] is True
    assert reread["input_fingerprint"] == original["input_fingerprint"] == "sha1:p001-plate-read-clip_p001"
    assert reread["job_id"] != original["job_id"]

    # v2(items=[])는 아무 Job도 새로 발주하지 않는다.
    assert jobs.issue_needed_jobs(case, need_v2) == []


def test_issue_needed_jobs_maps_overlay_time_ocr_need():
    case = _ready_case()
    original = jobs.issue_overlay_time_read(case, input_fingerprint="sha1:same-clip-overlay")

    evidence_needs = {
        "contract": "EvidenceNeeds",
        "contract_version": "evidence-needs/v1",
        "basis_record_ref": {"kind": "evidence_record", "ref": "ev_x001"},
        "items": [{"kind": "OVERLAY_TIME_OCR", "would_fill": "OCCURRED_AT"}],
    }
    issued = jobs.issue_needed_jobs(case, evidence_needs)
    assert len(issued) == 1
    reread = issued[0]
    assert reread["kind"] == "OVERLAY_TIME_READ"
    assert reread["force_rerun"] is True
    assert reread["input_fingerprint"] == original["input_fingerprint"]
    assert reread["job_id"] != original["job_id"]


def test_issue_needed_jobs_rejects_unknown_kind():
    import pytest

    case = _ready_case()
    with pytest.raises(ValueError):
        jobs.issue_needed_jobs(case, {"items": [{"kind": "SOMETHING_NEW"}]})


def test_job_record_shape_matches_contract_fields():
    case = _ready_case()
    job = jobs.issue_coarse_search(case, scope_ref="scope1", input_fingerprint="fp")
    assert job["contract"] == "JobRecord"
    assert job["contract_version"] == "job-record/v1"
    assert set(job.keys()) == {
        "contract",
        "contract_version",
        "job_id",
        "case_id",
        "case_rev",
        "kind",
        "scope_ref",
        "input_fingerprint",
        "force_rerun",
        "requested_at",
    }
