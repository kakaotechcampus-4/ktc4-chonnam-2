from dataclasses import replace

import pytest

from daesingo.case import command, jobs, service
from tests.case.test_result_reflection import _outcome, _reflect, _store_searching


@pytest.mark.parametrize(
    ("failure_kind", "expected_actions"),
    [
        ("RECORDING_UNSUPPORTED_MEDIA", []),
        ("SEARCH_PROVIDER_FAILED", ["RETRY_SEARCH"]),
        (None, ["RETRY_SEARCH"]),
    ],
)
def test_failed_search_retry_follows_the_terminal_reason(
    failure_kind: str | None, expected_actions: list[str],
) -> None:
    # Given: a real Case result reflection and reload, with a Runtime read port.
    store, case_id = _store_searching()
    outcome = replace(
        _outcome(store, case_id, "COARSE_SEARCH", status="FAILED"),
        failure_kind=failure_kind,
    )
    executions = [{"job_id": outcome.job_id, "attempt": 1,
                   "status": "FAILED", "failure_kind": failure_kind}]
    store.executions = lambda _conn, _ids: executions
    _reflect(store, outcome)

    # When: the API-facing read path reloads the persisted Case.
    view = service.get_view(case_id, store=store)

    # Then: unsupported input stays a failure without offering another paid retry.
    notice = next(n for n in view["notices"] if n["code"] == "search.candidate_search_failed")
    assert notice["actions"] == expected_actions
    assert view["stage"] == "SEARCHING"
    assert view["candidates"] == []
    assert view["running_jobs"] == []
    assert view["package"] is None


def test_a_new_attempt_does_not_reuse_an_older_unsupported_reason() -> None:
    # Given: an earlier attempt rejected media, but the latest failure is transient.
    store, case_id = _store_searching()
    outcome = _outcome(store, case_id, "COARSE_SEARCH", status="FAILED")
    store.executions = lambda _conn, _ids: [
        {"job_id": outcome.job_id, "attempt": 1, "status": "FAILED",
         "failure_kind": "RECORDING_UNSUPPORTED_MEDIA"},
        {"job_id": outcome.job_id, "attempt": 2, "status": "FAILED",
         "failure_kind": "SEARCH_PROVIDER_FAILED"},
    ]
    _reflect(store, outcome)

    # When: the current failure is projected.
    view = service.get_view(case_id, store=store)

    # Then: the old attempt must not remove the valid transient retry.
    notice = next(n for n in view["notices"] if n["code"] == "search.candidate_search_failed")
    assert notice["actions"] == ["RETRY_SEARCH"]


def test_redelivery_of_unsupported_input_does_not_create_more_jobs() -> None:
    # Given: the unsupported execution has already been applied once.
    store, case_id = _store_searching()
    outcome = replace(
        _outcome(store, case_id, "COARSE_SEARCH", status="FAILED"),
        failure_kind="RECORDING_UNSUPPORTED_MEDIA",
    )
    store.executions = lambda _conn, _ids: [
        {"job_id": outcome.job_id, "attempt": 1, "status": "FAILED",
         "failure_kind": "RECORDING_UNSUPPORTED_MEDIA"},
    ]
    _reflect(store, outcome)
    records_before = store.get_case(case_id).job_records

    # When: Runtime delivers the same terminal execution again.
    result = _reflect(store, outcome)

    # Then: delivery is idempotent, and the same-input retry is still unavailable.
    assert result.status == "ALREADY_APPLIED"
    assert store.get_case(case_id).job_records == records_before
    assert jobs.latest_job_record(store.get_case(case_id), "COARSE_SEARCH")["job_id"] == outcome.job_id
    notice = next(n for n in service.get_view(case_id, store=store)["notices"]
                  if n["code"] == "search.candidate_search_failed")
    assert notice["actions"] == []


@pytest.mark.parametrize(
    ("failure_kind", "accepted"),
    [("RECORDING_UNSUPPORTED_MEDIA", False), ("SEARCH_PROVIDER_FAILED", True)],
)
def test_direct_retry_command_follows_the_terminal_reason(failure_kind: str, accepted: bool) -> None:
    # Given: a failed search whose terminal reason is projected from the Runtime read port.
    store, case_id = _store_searching()
    outcome = replace(
        _outcome(store, case_id, "COARSE_SEARCH", status="FAILED"),
        failure_kind=failure_kind,
    )
    store.executions = lambda _conn, _ids: [
        {"job_id": outcome.job_id, "attempt": 1, "status": "FAILED", "failure_kind": failure_kind},
    ]
    _reflect(store, outcome)
    jobs_before = len(store.get_case(case_id).job_records)

    # When: a client sends RETRY_SEARCH directly, bypassing the screen's buttons.
    result = command.execute_command({
        "case_id": case_id,
        "expected_case_rev": store.get_case(case_id).case_rev,
        "kind": "RUN_NOTICE_ACTION",
        "payload": {"notice_code": "search.candidate_search_failed", "action": "RETRY_SEARCH"},
    }, store=store)

    # Then: unsupported input gets no new paid search; a transient failure keeps its retry.
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
