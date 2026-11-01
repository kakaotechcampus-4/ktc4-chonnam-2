from datetime import timedelta

from daesingo.case import jobs, service
from daesingo.case.search_progress import record_search_progress, search_progress_view
from tests.case.test_case_wait_timeout import _searching, _requested_at


def setup_search():
    store, case_id = _searching()
    job = jobs.latest_job_record(store.get_case(case_id), "COARSE_SEARCH")
    execution = {"job_id": job["job_id"], "execution_id": "exec_1", "attempt": 1, "status": "RUNNING"}
    store.executions = lambda conn, ids: [execution]
    return store, case_id, job, execution


def test_progress_survives_reload_and_retry_without_resetting_search_clock():
    store, case_id, job, execution = setup_search()
    start = _requested_at(store, case_id)
    def report(phase, seconds=0):
        return record_search_progress(store, case_id, job["job_id"], phase,
                                      execution_id=execution["execution_id"], now=start + timedelta(seconds=seconds))
    revision = store.get_case(case_id).case_rev
    assert report("PREPARING")
    assert report("SEARCHING", 10)
    progress = service.get_view(case_id, store=store)["scene_search"]
    assert progress["phase"] == "SEARCHING"
    assert progress["search_started_at"] == (start + timedelta(seconds=10)).isoformat()
    execution.update(execution_id="exec_2", attempt=2)
    assert not report("PREPARING", 100)
    assert not report("SEARCHING", 110)
    assert service.get_view(case_id, store=store)["scene_search"] == progress
    assert report("ORGANIZING", 130)
    latest = store.get_case(case_id)
    assert latest.scene_search_progress["search_started_at"] == progress["search_started_at"]
    assert latest.case_rev == revision


def test_late_or_stale_worker_cannot_change_stopped_or_new_search():
    store, case_id, job, execution = setup_search()
    start = _requested_at(store, case_id)
    def report(**overrides):
        return record_search_progress(store, case_id, job["job_id"], "SEARCHING",
                                      **{"execution_id": "exec_1", "now": start, **overrides})
    assert not report(execution_id="old_execution")
    assert not report(now=start + timedelta(seconds=180))
    assert report()
    case = store.load_for_update(case_id)
    case.settled_jobs[job["job_id"]] = "CANCELLED"
    store.save(case)
    assert not report()
    assert search_progress_view(store.get_case(case_id)) is None
    case = store.load_for_update(case_id)
    new_job = {**job, "job_id": "new_job"}
    case.job_records.append(new_job)
    store.save(case)
    assert not report()
    assert search_progress_view(store.get_case(case_id)) == {
        "job_id": "new_job", "phase": "PREPARING", "search_started_at": None}


def test_hint_preparation_has_no_invented_search_clock():
    store, case_id = _searching("흰 차가 실선을 넘었어요")
    detail = service.get_view(case_id, store=store)["scene_search"]
    assert detail["phase"] == "PREPARING"
    assert detail["search_started_at"] is None
