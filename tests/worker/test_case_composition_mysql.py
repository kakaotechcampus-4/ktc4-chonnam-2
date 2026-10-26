"""Public stored adapters on caller Connection, durable T1 and bounded T2 semantics."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from daesingo.api.app import create_app
from daesingo.case.domain import CaseAggregate
from daesingo.case import jobs
from daesingo.case.timeline_source import RecordingSequentialTimelineSource
from daesingo.common.jobs.execution import ExecutionContext, HandlerResult
from daesingo.common.jobs.produced import ProducedReader
from daesingo.common.jobs.reflection import ReflectionInput
from daesingo.common.jobs.repository import enqueue
from daesingo.recording import RecordingService
from daesingo.recording.mysql_repository import MySQLRecordingRepository
from test_worker_mysql import queue
from test_search_handlers import fixtures
from redelivery_support import store

pytestmark = pytest.mark.mysql


@pytest.fixture
def db(queue, tmp_path):
    return queue, tmp_path


@pytest.mark.parametrize("status,outcome", [("SUCCEEDED", "SUCCEEDED"), ("SUCCEEDED", "PARTIAL"), ("FAILED", "FAILED")])
@pytest.mark.mysql_check("search_composition", "stored_t2")
def test_stored_worker_reflector_applies_success_failure_partial_without_extending_receipt(db, status, outcome):
    from daesingo.worker.case_composition import StoredCaseReflector, stored_case_store
    from daesingo.common.jobs.reflection import reflect_terminal
    from daesingo.common.jobs.produced import ProducedObject, append_objects, prepare_objects
    engine, root = db
    scope, coarse, _ = fixtures()
    case = CaseAggregate.empty("case-composed")
    case.start_search()
    case.analysis_scopes[scope.scope_id] = scope.model_dump(mode="json")
    job = jobs.issue_coarse_search(case, scope_ref=scope.scope_id, input_fingerprint="fixed")
    with engine.begin() as conn:
        store(conn).register(case)
        execution, = enqueue(conn, [job], "trace")
        conn.exec_driver_sql("UPDATE job_execution SET status=%s,started_at=NOW(6),ended_at=NOW(6),failure_kind=%s,produced=%s WHERE execution_id=%s",
            (status, "SEARCH_PROVIDER_ERROR" if status == "FAILED" else None,
             '[{"kind":"analysis_run","ref":"run-stored"}]', execution))
        if status == "SUCCEEDED":
            payload = {"outcome": outcome, "analysis_run": coarse.analysis_run.model_dump(mode="json"),
                       "candidate_events": [c.model_dump(mode="json") for c in coarse.candidates]}
            append_objects(conn, case_id=case.case_id, execution_id=execution, job_kind="COARSE_SEARCH",
                objects=prepare_objects(execution, (ProducedObject(kind="analysis_run", ref="run-stored", payload=payload),)))
    terminal = HandlerResult(status=status, failure_kind="SEARCH_PROVIDER_ERROR" if status == "FAILED" else None,
                             produced=({"kind": "analysis_run", "ref": "run-stored"},))
    incoming = ReflectionInput(execution, job["job_id"], case.case_id, "COARSE_SEARCH", 1, terminal)
    selected_root = root / "absent-media-root" if status == "FAILED" else root
    reflector = StoredCaseReflector(storage_root=selected_root)
    with engine.begin() as conn:
        assert reflect_terminal(conn, incoming, reflector, "trace").status == "APPLIED"
    with engine.begin() as conn:
        assert reflect_terminal(conn, incoming, reflector, "trace").status == "ALREADY_APPLIED"
        facade = stored_case_store(conn, storage_root=selected_root)
        loaded = facade.get_case(case.case_id)
        view = __import__("daesingo.case", fromlist=["get_view"]).get_view(case.case_id, store=facade)
        # Case T2 selects rank=1 and issues the first Fine (Case W12:C2).
        assert [j["kind"] for j in view["running_jobs"]] == (["FINE_VERIFY"] if status == "SUCCEEDED" else [])
        assert loaded.processed_executions[execution] == job["job_id"]
        assert bool(view["candidates"]) == (status == "SUCCEEDED")
        assert conn.exec_driver_sql("SELECT case_applied_at IS NOT NULL FROM job_execution WHERE execution_id=%s", (execution,)).scalar_one()


@pytest.mark.mysql_check("search_composition", "api_stored_adapter")
def test_api_case_store_attaches_stored_adapter_on_same_caller_transaction(api_db):
    startup, _, engine = api_db
    app = create_app(startup=startup)
    try:
        with engine.begin() as conn:
            facade = app.state.composition._store(conn)
            assert facade.conn is conn and facade.adapter_factory is not None
            from daesingo.case.stored_observation import StoredObservationAdapter
            case = CaseAggregate.empty("new-case")
            assert isinstance(facade.adapter_for(case), StoredObservationAdapter)
            assert facade.adapter_for(case).get_evidence_records() == []
    finally: app.state.composition.close()


from tests.api.test_cases_view_mysql import api_db
from tests.api.conftest import api_startup
