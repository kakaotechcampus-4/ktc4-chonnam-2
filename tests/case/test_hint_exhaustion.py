"""단서 구조화(`HINT_EXTRACT`) 소진 알림 — Runtime이 재시도까지 `STALE`로 끝났다고 확정하면 case는 `EXHAUSTED`로
정산하고 빈 단서로 첫 탐색을 이어 간다(#405 D-3, `decisions/start-analysis.md` §3-5)."""

import pytest

from daesingo.case import command, service
from daesingo.case.store import CaseStore
from daesingo.case.timeline_source import TimelineUnavailable
from tests.case.test_start_analysis_command import FakeTimelines, _hint_id, _start, _store_with_sources

_ALL_NULL = {"time": None, "vehicle": None, "situation": None, "location": None}


def _started() -> tuple[CaseStore, str, str]:
    store, case_id = _store_with_sources(1)
    command.execute_command(_start(case_id, "흰 SUV"), store=store, timelines=FakeTimelines())
    return store, case_id, _hint_id(store, case_id)


def _exhaust(store: CaseStore, case_id: str, job_id: str, kind: str = "HINT_EXTRACT"):
    return service.receive_hint_exhaustion(case_id, job_id=job_id, kind=kind, store=store, timelines=FakeTimelines())


def test_exhaustion_settles_hint_and_issues_first_search_with_empty_hints():
    store, case_id, job_id = _started()

    result = _exhaust(store, case_id, job_id)

    assert result.status == "APPLIED" and result.reason is None
    assert [r["kind"] for r in result.appended_job_records] == ["COARSE_SEARCH"]
    saved = store.get_case(case_id)
    assert saved.settled_jobs[job_id] == "EXHAUSTED"
    assert saved.hints == _ALL_NULL
    assert saved.hint_unclear is False  # 보류가 아니라 실행이 끝나지 못한 것 — notice를 띄우지 않는다
    assert saved.stage == "SEARCHING"
    view = service.get_view(case_id, store=store)
    assert [j["kind"] for j in view["running_jobs"]] == ["COARSE_SEARCH"]
    assert not any(n["code"] == "search.hint_unclear" for n in view["notices"])


def test_exhaustion_is_not_a_user_request_and_keeps_case_rev():
    store, case_id, job_id = _started()
    before = store.get_case(case_id).case_rev

    _exhaust(store, case_id, job_id)

    assert store.get_case(case_id).case_rev == before


def test_redelivered_notice_issues_nothing_more():
    store, case_id, job_id = _started()
    _exhaust(store, case_id, job_id)

    again = _exhaust(store, case_id, job_id)

    assert (again.status, again.reason, again.appended_job_records) == ("NO_CHANGE", "EXHAUSTED", [])
    assert [r["kind"] for r in store.get_case(case_id).job_records] == ["HINT_EXTRACT", "COARSE_SEARCH"]


def test_result_reflected_first_makes_notice_no_change():
    store, case_id, job_id = _started()
    service.receive_hint_extraction_result(
        case_id, {"status": "OK", "vehicle_hint": "흰 SUV"}, job_id=job_id, store=store, timelines=FakeTimelines()
    )

    result = _exhaust(store, case_id, job_id)

    assert (result.status, result.reason) == ("NO_CHANGE", "REFLECTED")
    saved = store.get_case(case_id)
    assert saved.hints["vehicle"] == "흰 SUV"
    assert [r["kind"] for r in saved.job_records] == ["HINT_EXTRACT", "COARSE_SEARCH"]


def test_user_stop_first_makes_notice_no_change():
    store, case_id, job_id = _started()
    rev = store.get_case(case_id).case_rev
    command.execute_command(
        {"case_id": case_id, "expected_case_rev": rev, "kind": "STOP_ANALYSIS", "payload": {}}, store=store
    )

    result = _exhaust(store, case_id, job_id)

    assert (result.status, result.reason) == ("NO_CHANGE", "CANCELLED")
    saved = store.get_case(case_id)
    assert saved.analysis_stopped
    assert [r["kind"] for r in saved.job_records] == ["HINT_EXTRACT"]


def test_no_change_saves_nothing():
    store, case_id, job_id = _started()
    _exhaust(store, case_id, job_id)
    saves = []
    original = store.save
    store.save = lambda case: (saves.append(case.case_id), original(case))

    _exhaust(store, case_id, job_id)

    assert saves == []


def test_job_not_issued_by_this_case_is_a_wiring_error():
    """`NO_CHANGE`로 받으면 Runtime이 receipt를 남겨 잘못된 알림이 조용히 사라진다 — T2(`reflect_execution`)와 같이 올린다."""
    store, case_id, _ = _started()

    with pytest.raises(ValueError):
        _exhaust(store, case_id, "job_unknown")


@pytest.mark.parametrize("kind", ["COARSE_SEARCH", "FINE_VERIFY"])
def test_notice_kind_other_than_hint_extract_is_a_wiring_error(kind):
    """이번 범위는 `HINT_EXTRACT`만이다 — 다른 kind의 소진 후속 정책은 아직 없다(#405 일반화)."""
    store, case_id, job_id = _started()

    with pytest.raises(ValueError):
        _exhaust(store, case_id, job_id, kind=kind)
    assert store.get_case(case_id).settled_jobs == {}


def test_notice_for_a_non_hint_job_is_a_wiring_error():
    store, case_id, job_id = _started()
    _exhaust(store, case_id, job_id)
    coarse_id = next(r["job_id"] for r in store.get_case(case_id).job_records if r["kind"] == "COARSE_SEARCH")

    with pytest.raises(ValueError):
        _exhaust(store, case_id, coarse_id)


def test_timeline_failure_saves_nothing():
    store, case_id, job_id = _started()

    with pytest.raises(TimelineUnavailable):
        service.receive_hint_exhaustion(
            case_id, job_id=job_id, kind="HINT_EXTRACT", store=store, timelines=FakeTimelines(fail=True)
        )

    saved = store.get_case(case_id)
    assert saved.settled_jobs == {}
    assert [r["kind"] for r in saved.job_records] == ["HINT_EXTRACT"]
