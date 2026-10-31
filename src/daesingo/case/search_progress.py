"""Persist display-only search milestones without changing Case revision or job outcomes."""

from datetime import UTC, datetime

from .domain import ANALYSIS_JOB_KINDS, CaseAggregate
from .store import CaseStore

PHASES = ("PREPARING", "SEARCHING", "ORGANIZING")


def current_search_job(case: CaseAggregate):
    return next((r for r in reversed(case.job_records) if r["kind"] in ANALYSIS_JOB_KINDS), None)


def record_search_progress(store: CaseStore, case_id: str, job_id: str, phase: str,
                           *, execution_id: str, now: datetime | None = None) -> bool:
    if phase not in PHASES:
        raise ValueError("unknown search phase")
    now = now or datetime.now(UTC)
    case = store.load_for_update(case_id)
    job = current_search_job(case)
    if (case.stage != "SEARCHING" or job is None or job["job_id"] != job_id
            or job["kind"] != "COARSE_SEARCH" or job_id in case.settled_jobs):
        return False
    deadline = case.wait_deadline(job)
    if deadline is not None and now >= deadline:
        return False
    executions = [e for e in store.read_executions(case) if e["job_id"] == job_id]
    latest = max(executions, key=lambda e: e["attempt"], default=None)
    if latest is None or latest["execution_id"] != execution_id or latest["status"] != "RUNNING":
        return False
    previous = case.scene_search_progress
    if previous is None or previous["job_id"] != job_id:
        previous = {"job_id": job_id, "phase": "PREPARING", "search_started_at": None}
    elif PHASES.index(phase) <= PHASES.index(previous["phase"]):
        return False
    case.scene_search_progress = {
        "job_id": job_id,
        "phase": phase,
        "search_started_at": previous["search_started_at"] or (now.isoformat() if phase != "PREPARING" else None),
    }
    store.save(case)
    return True


def search_progress_view(case: CaseAggregate):
    job = current_search_job(case)
    if case.stage != "SEARCHING" or job is None or job["job_id"] in case.settled_jobs:
        return None
    progress = case.scene_search_progress
    if progress is not None and progress["job_id"] == job["job_id"]:
        return dict(progress)
    return {"job_id": job["job_id"], "phase": "PREPARING", "search_started_at": None}
