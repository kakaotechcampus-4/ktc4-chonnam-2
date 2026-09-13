"""JobRecord(Job Intent) 발주 — case가 유일하게 소유하는 발주 의도.

핵심 규칙 (`contract-job-execution.md` 2026-09-13 명확화, `contract-job-record-case-view.md`
`RESUME_SEARCH` 행 신설분 그대로): 사용자의 새 Intent는 **항상 새 job_id**로 발주한다.
`RETRY_PLATE_READ`/`RETRY_SEARCH`/`RESUME_SEARCH`("이어서 찾기")도 전부 새 job_id다.
같은 job_id + attempt 증가는 자동 인프라 재시도(`STALE`)뿐이며, 그건 common/runtime의
책임이라 이 모듈에는 아예 그 분기가 없다 — `domain.CaseAggregate.next_job_id()` 참고.

`JobRecord`는 발주 의도만 담고 실행 상태(`JobExecution`)는 담지 않는다(append-only).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from daesingo.case.domain import CaseAggregate

CONTRACT_VERSION = "job-record/v1"

JOB_KINDS = frozenset(
    {
        "COARSE_SEARCH",
        "PLATE_READ",
        "OVERLAY_TIME_READ",
        "FINE_VERIFY",
        "REPORT_VIDEO_EXPORT",
    }
)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def issue_job(
    case: CaseAggregate,
    kind: str,
    *,
    scope_ref: str | None = None,
    input_fingerprint: str,
    force_rerun: bool = False,
) -> dict[str, Any]:
    if kind not in JOB_KINDS:
        raise ValueError(f"알 수 없는 JobRecord.kind: {kind!r} (등록된 kind: {sorted(JOB_KINDS)})")
    job_record: dict[str, Any] = {
        "contract": "JobRecord",
        "contract_version": CONTRACT_VERSION,
        "job_id": case.next_job_id(kind),
        "case_id": case.case_id,
        "case_rev": case.case_rev,
        "kind": kind,
        "scope_ref": scope_ref,
        "input_fingerprint": input_fingerprint,
        "force_rerun": force_rerun,
        "requested_at": _now(),
    }
    case.record_job(job_record)
    return job_record


def issue_coarse_search(case: CaseAggregate, *, scope_ref: str, input_fingerprint: str) -> dict[str, Any]:
    return issue_job(case, "COARSE_SEARCH", scope_ref=scope_ref, input_fingerprint=input_fingerprint)


def issue_plate_read(case: CaseAggregate, *, input_fingerprint: str, force_rerun: bool = False) -> dict[str, Any]:
    return issue_job(case, "PLATE_READ", input_fingerprint=input_fingerprint, force_rerun=force_rerun)


def issue_overlay_time_read(case: CaseAggregate, *, input_fingerprint: str) -> dict[str, Any]:
    return issue_job(case, "OVERLAY_TIME_READ", input_fingerprint=input_fingerprint)


def issue_fine_verify(case: CaseAggregate, *, input_fingerprint: str) -> dict[str, Any]:
    return issue_job(case, "FINE_VERIFY", input_fingerprint=input_fingerprint)


def issue_report_video_export(case: CaseAggregate, *, input_fingerprint: str) -> dict[str, Any]:
    return issue_job(case, "REPORT_VIDEO_EXPORT", input_fingerprint=input_fingerprint)


def issue_resume_search(case: CaseAggregate, *, scope_ref: str, input_fingerprint: str) -> dict[str, Any]:
    """"이어서 찾기" — CANCELLED 이후 재개. 2026-09-13 결정: 새 job_id(kind=COARSE_SEARCH,
    force_rerun=True)로 발주한다. 같은 job_id를 재사용하지 않는다."""
    return issue_job(
        case,
        "COARSE_SEARCH",
        scope_ref=scope_ref,
        input_fingerprint=input_fingerprint,
        force_rerun=True,
    )


def issue_plate_reread(case: CaseAggregate, *, input_fingerprint: str) -> dict[str, Any]:
    """`EvidenceNeeds.items`가 `PLATE_REREAD`를 요청했을 때의 자동 발주(force_rerun=True)."""
    return issue_job(case, "PLATE_READ", input_fingerprint=input_fingerprint, force_rerun=True)
