"""Observe exception classes only at live Worker logging boundaries."""

from functools import partial
from io import StringIO
import json
from threading import Event
from types import MappingProxyType

import pytest
from sqlalchemy.exc import DBAPIError

from daesingo.common.bootstrap import Startup
from daesingo.common.config import RuntimeConfig, WorkerSettings
from daesingo.common.jobs.execution import ExecutionContext, HandlerResult
from daesingo.common.jobs.worker_loop import WorkerLoop
from daesingo.common.logging import configure_logging
from daesingo.common.logging.catalog import validate_event
from daesingo.worker.registry import KindRegistry
from daesingo.worker.composition import compose_worker
from logging_faults import install_logging_fault
from test_worker_loop import claim
from worker_error_support import NAMES, assert_private_absent, private_error


def run_failure(path, error, sink="healthy"):
    stop, recorded, reflected, stream = Event(), [], [], StringIO()
    logger = configure_logging("worker", stream=stream)

    def fail(ctx):
        raise error

    dispatch = partial(KindRegistry({"TEST": fail}).dispatch, logger=logger) if path == "registry" else fail

    def record(ctx, result):
        recorded.append(result.model_dump())
        stop.set()
        return True

    def reflect(ctx, result):
        reflected.append(result.model_dump())
        if path == "reflection":
            raise error

    event_name = "runtime.reflect.failed" if path == "reflection" else "runtime.execution.failed"
    seen, remove = ([], lambda: None)
    if sink != "healthy":
        seen, remove = install_logging_fault(logger, sink, lambda name: name == event_name)
    try:
        WorkerLoop(claim=claim, dispatch=(lambda ctx: HandlerResult()) if path == "reflection" else dispatch,
            record=record, reflect=reflect, settings=WorkerSettings(), stop=stop,
            logger=logger, sleep=lambda seconds: None, clock=lambda: 1).run()
    finally:
        remove()
    expected = {"status": "SUCCEEDED" if path == "reflection" else "FAILED",
                "produced": (), "objects": (),
                "failure_kind": None if path == "reflection" else "RUNTIME_HANDLER_ERROR"}
    assert recorded == reflected == [expected]
    assert_private_absent(stream.getvalue())
    rows = [json.loads(line) for line in stream.getvalue().splitlines()]
    failures = [row for row in rows if row["event"] == event_name]
    return failures, seen


@pytest.mark.parametrize("path", ["registry", "dispatch"])
def test_handler_error_type_at_conversion_boundary(path):
    failures, _ = run_failure(path, private_error())
    assert len(failures) == 1
    assert failures[0]["error_type"] == "_FrameCoverageError"


@pytest.mark.parametrize("error,expected", [
    (private_error("InvalidTransition"), "InvalidTransition"),
    (DBAPIError("SELECT secret FROM private_jobs", {"payload": "PRIVATE_PROVIDER_PAYLOAD"},
               RuntimeError("credential_SENTINEL_464")), "DBAPIError"),
])
def test_initial_reflection_error_type_is_outermost(error, expected):
    failures, _ = run_failure("reflection", error)
    assert len(failures) == 1
    assert failures[0]["error_type"] == expected


@pytest.mark.parametrize("path", ["registry", "dispatch", "reflection"])
@pytest.mark.parametrize("qualname,expected", NAMES)
def test_failure_tokens_and_privacy_at_worker_boundaries(path, qualname, expected, capsys):
    failures, _ = run_failure(path, private_error(qualname))
    assert len(failures) == 1
    row = failures[0]
    assert row.get("error_type") == expected
    assert ("error_type" in row) == (expected is not None)
    assert set(row) == {"timestamp", "level", "service", "event", "status",
                        "trace_id", "case_id", "job_id", "execution_id"} | ({"error_type"} if expected else set())
    assert [row[key] for key in ("trace_id", "case_id", "job_id", "execution_id")] == ["trace", "case", "job", "exec_job"]
    validate_event(row)
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("path", ["registry", "dispatch", "reflection"])
@pytest.mark.parametrize("sink", ["filter", "handler"])
def test_error_observation_logging_fault_preserves_terminal(path, sink, capsys):
    _, seen = run_failure(path, private_error(), sink)
    assert seen == ["runtime.reflect.failed" if path == "reflection" else "runtime.execution.failed"]
    assert capsys.readouterr().err == ""


def test_composition_supplies_logger_at_registry_exception_boundary(tmp_path):
    stream = StringIO()
    config = RuntimeConfig.from_mapping("worker", {
        "DAESINGO_RUNTIME_DB_URL": "mysql+pymysql://test@127.0.0.1:1/not_connected",
        "DAESINGO_RUNTIME_MEDIA_ROOT": str(tmp_path / "media"),
        "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(tmp_path / "temp"),
    })
    logger = configure_logging("worker", stream=stream)

    def fail(ctx):
        raise private_error()

    worker = compose_worker(engine=object(), startup=Startup(config, MappingProxyType({}), logger),
        registry=KindRegistry({"TEST": fail}), stop=Event())
    result = worker.dispatch(ExecutionContext("exec", "job", "case", "TEST", 1, "trace"))
    assert result == HandlerResult(status="FAILED", failure_kind="RUNTIME_HANDLER_ERROR")
    row = json.loads(stream.getvalue())
    assert row["event"] == "runtime.execution.failed" and row["error_type"] == "_FrameCoverageError"
    assert row["execution_id"] == "exec"
    assert_private_absent(stream.getvalue())
    validate_event(row)
