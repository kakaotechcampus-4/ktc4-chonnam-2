"""지원하지 않는 영상으로 탐색이 실패하면 「다시 찾기」를 싣지 않는다(#542).

같은 입력으로 다시 찾아도 또 실패한다 — 같은 미지원 입력의 불필요한 재준비 · 재발주를 막는다. Runtime이 Search 호출 전에 거부하므로
유료 호출이 나간다고 보지 않는다. #452 `analysis_range_too_long`과 같은 기준이다. 실패 이유는
반영 때 `outcome.failure_kind`로 정해 aggregate에 남긴다(#452와 같은 방식). CaseView 조회 때 실행 기록에서 다시 계산하지
않는다.
"""
import pytest

from daesingo.case import command, service
from daesingo.case.store_state import from_row, to_row
from tests.case.test_result_reflection import _coarse_failed_with, _outcome, _reflect, _store_searching


def _search_failed_notice(view: dict) -> dict:
    return next(n for n in view["notices"] if n["code"] == "search.candidate_search_failed")


def _retry(store, case_id):
    return command.execute_command({
        "case_id": case_id,
        "expected_case_rev": store.get_case(case_id).case_rev,
        "kind": "RUN_NOTICE_ACTION",
        "payload": {"notice_code": "search.candidate_search_failed", "action": "RETRY_SEARCH"},
    }, store=store)


@pytest.mark.parametrize(
    ("failure_kind", "expected_actions"),
    [("RECORDING_UNSUPPORTED_MEDIA", []), ("SEARCH_PROVIDER_FAILED", ["RETRY_SEARCH"])],
)
def test_failed_search_retry_follows_the_reflected_failure_kind(failure_kind, expected_actions):
    store, case_id = _store_searching()
    _coarse_failed_with(store, case_id, failure_kind)

    view = service.get_view(case_id, store=store)

    assert _search_failed_notice(view)["actions"] == expected_actions
    assert view["stage"] == "SEARCHING"
    assert view["candidates"] == []
    assert view["running_jobs"] == []


def test_unsupported_input_does_not_depend_on_execution_rows():
    # 실행 기록 조회가 비어 있어도(읽기 포트 없음 · 다른 job의 기록) 반영 때 정한 이유를 쓴다.
    store, case_id = _store_searching()
    _coarse_failed_with(store, case_id, "RECORDING_UNSUPPORTED_MEDIA")
    store.executions = lambda _conn, _ids: []

    assert _search_failed_notice(service.get_view(case_id, store=store))["actions"] == []


def test_a_later_failure_overwrites_the_reason():
    # 일시 실패 → 다시 찾기 → 미지원 입력이면 그때부터 다시 찾기가 없다. 실패마다 이유를 덮어쓴다.
    store, case_id = _store_searching()
    _coarse_failed_with(store, case_id, "SEARCH_PROVIDER_FAILED")
    assert _retry(store, case_id).response["ok"] is True

    _coarse_failed_with(store, case_id, "RECORDING_UNSUPPORTED_MEDIA", execution_id="exec_2")

    assert _search_failed_notice(service.get_view(case_id, store=store))["actions"] == []


def test_unsupported_input_survives_store_round_trip():
    store, case_id = _store_searching()
    _coarse_failed_with(store, case_id, "RECORDING_UNSUPPORTED_MEDIA")

    assert from_row(to_row(store.get_case(case_id))).search_input_unsupported is True


def test_redelivery_of_unsupported_input_does_not_create_more_jobs():
    store, case_id = _store_searching()
    _coarse_failed_with(store, case_id, "RECORDING_UNSUPPORTED_MEDIA")
    outcome = _outcome(store, case_id, "COARSE_SEARCH", status="FAILED")
    records_before = store.get_case(case_id).job_records

    result = _reflect(store, outcome)

    assert result.status == "ALREADY_APPLIED"
    assert store.get_case(case_id).job_records == records_before
    assert _search_failed_notice(service.get_view(case_id, store=store))["actions"] == []


@pytest.mark.parametrize(
    ("failure_kind", "accepted"),
    [("RECORDING_UNSUPPORTED_MEDIA", False), ("SEARCH_PROVIDER_FAILED", True)],
)
def test_direct_retry_command_follows_the_reflected_failure_kind(failure_kind, accepted):
    # 화면 버튼을 거치지 않고 RETRY_SEARCH를 바로 보내도 미지원 입력이면 새 탐색을 발주하지 않는다.
    store, case_id = _store_searching()
    _coarse_failed_with(store, case_id, failure_kind)
    jobs_before = len(store.get_case(case_id).job_records)

    result = _retry(store, case_id)

    assert result.response["ok"] is accepted
    coarse = [r for r in store.get_case(case_id).job_records if r["kind"] == "COARSE_SEARCH"]
    if accepted:
        assert [r["kind"] for r in result.appended_job_records] == ["COARSE_SEARCH"]
        assert len(coarse) == 2
    else:
        assert result.response["error"]["code"] == "case.command.unknown_target"
        assert result.appended_job_records == []
        assert len(store.get_case(case_id).job_records) == jobs_before
        assert len(coarse) == 1

