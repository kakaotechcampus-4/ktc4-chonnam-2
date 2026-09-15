"""JobExecution v1.1 fixture와 lifecycle 검증."""

from datetime import datetime
import json

import pytest
from pydantic import ValidationError

from daesingo.common import (
    InMemoryJobExecutionStore,
    JobExecution,
    JobExecutionError,
    load_common_fixture,
)


SCENARIOS = [
    "scenario_happy_001",
    "scenario_empty_001",
    "scenario_unknown_abstain_partial_001",
    "scenario_plate_reread_001",
    "scenario_correction_rerun_001",
    "scenario_infra_failure_001",
    "scenario_relative_rebase_001",
]


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_common_fixture_loads_every_scenario(scenario_id: str) -> None:
    assert load_common_fixture(scenario_id).scenario_id == scenario_id


def test_infra_fixture_preserves_stale_retry_failed_and_cancelled() -> None:
    fixture = load_common_fixture("scenario_infra_failure_001")
    store = InMemoryJobExecutionStore.from_executions(fixture.job_executions)

    attempts = store.list_for_job("job_x001_plate")
    assert [(item.attempt, item.status) for item in attempts] == [(1, "STALE"), (2, "FAILED")]
    assert attempts[0].ended_at is None
    assert attempts[0].produced == []
    assert attempts[0].usage_refs == ["usage_x001_plate_a1"]
    assert attempts[1].failure_kind == "READOUT_INFRA"
    cancelled = store.get("exec_x001_plate_reread")
    assert cancelled.status == "CANCELLED"


def test_queue_run_and_finish_successfully() -> None:
    store = InMemoryJobExecutionStore()
    queued_at = datetime.fromisoformat("2026-09-14T10:00:00+09:00")
    started_at = datetime.fromisoformat("2026-09-14T10:00:01+09:00")
    ended_at = datetime.fromisoformat("2026-09-14T10:00:02+09:00")

    queued = store.queue_execution("job_test", queued_at)
    running = store.start_execution(queued.execution_id, started_at)
    succeeded = store.finish_execution(
        running.execution_id,
        "SUCCEEDED",
        ended_at,
        produced=[{"kind": "analysis_run", "ref": "run_test"}],
        usage_refs=["usage_test"],
    )

    assert queued.attempt == 1
    assert running.status == "RUNNING"
    assert succeeded.status == "SUCCEEDED"
    assert succeeded.produced[0].kind == "analysis_run"
    assert succeeded.usage_refs == ["usage_test"]
    assert "cost" not in succeeded.model_dump()


def test_stale_retry_uses_same_job_and_new_execution_identity() -> None:
    store = InMemoryJobExecutionStore()
    first = store.queue_execution(
        "job_retry",
        datetime.fromisoformat("2026-09-14T10:00:00+09:00"),
    )
    store.start_execution(
        first.execution_id,
        datetime.fromisoformat("2026-09-14T10:00:01+09:00"),
    )
    stale = store.finish_execution(first.execution_id, "STALE", None)
    retry = store.queue_execution(
        "job_retry",
        datetime.fromisoformat("2026-09-14T10:01:00+09:00"),
    )

    assert stale.status == "STALE"
    assert retry.attempt == 2
    assert retry.execution_id != first.execution_id


def test_cancelled_execution_can_preserve_partial_result() -> None:
    store = InMemoryJobExecutionStore()
    queued = store.queue_execution(
        "job_cancel",
        datetime.fromisoformat("2026-09-14T10:00:00+09:00"),
    )
    store.start_execution(
        queued.execution_id,
        datetime.fromisoformat("2026-09-14T10:00:01+09:00"),
    )
    cancelled = store.finish_execution(
        queued.execution_id,
        "CANCELLED",
        datetime.fromisoformat("2026-09-14T10:00:02+09:00"),
        produced=[{"kind": "analysis_run", "ref": "run_partial"}],
    )

    assert cancelled.status == "CANCELLED"
    assert cancelled.produced[0].ref == "run_partial"


def test_invalid_transition_is_rejected() -> None:
    store = InMemoryJobExecutionStore()
    queued = store.queue_execution(
        "job_invalid",
        datetime.fromisoformat("2026-09-14T10:00:00+09:00"),
    )

    with pytest.raises(JobExecutionError) as raised:
        store.finish_execution(
            queued.execution_id,
            "SUCCEEDED",
            datetime.fromisoformat("2026-09-14T10:00:02+09:00"),
        )

    assert raised.value.code == "INVALID_STATUS_TRANSITION"


def test_failed_execution_requires_failure_kind() -> None:
    fixture = load_common_fixture("scenario_infra_failure_001")
    payload = fixture.job_executions[1].model_dump(mode="json")
    payload["failure_kind"] = None

    with pytest.raises(ValidationError, match="failure_kind"):
        JobExecution.model_validate_json(json.dumps(payload))


def test_timestamp_order_is_validated() -> None:
    fixture = load_common_fixture("scenario_happy_001")
    payload = fixture.job_executions[0].model_dump(mode="json")
    payload["started_at"] = "2026-08-24T18:19:00+09:00"

    with pytest.raises(ValidationError, match="queued_at보다 빠를 수 없습니다"):
        JobExecution.model_validate_json(json.dumps(payload))
