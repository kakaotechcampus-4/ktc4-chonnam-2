from daesingo.case.domain import CaseAggregate
from daesingo.case import jobs


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
