"""A queued job must never silently switch to the currently selected candidate."""

from copy import deepcopy
from importlib import import_module

import pytest

from daesingo.case.domain import CaseAggregate
from daesingo.case.store import CaseStore
from daesingo.common.jobs.execution import ExecutionContext


def setup_input(kind="FINE_VERIFY"):
    from test_search_handlers import fixtures
    scope, coarse, _ = fixtures()
    case = CaseAggregate.empty("case_one")
    case.description, case.hints = "description", {"vehicle": "old hint"}
    case.analysis_scopes[scope.scope_id] = scope.model_dump(mode="json")
    case.job_records = [
        {"job_id": "generation", "case_id": case.case_id, "kind": "COARSE_SEARCH", "scope_ref": scope.scope_id},
        {"job_id": "job_one", "case_id": case.case_id, "kind": kind, "scope_ref": scope.scope_id},
    ]
    candidate = coarse.candidates[0]
    case.observation_inputs["job_one"] = {"candidate_id": candidate.candidate_id,
        "generation_job_id": "generation", "span": {key: getattr(candidate.span, key)
            for key in ("timeline_id", "timeline_revision", "start_ms", "end_ms")}}
    content = {"candidate_events": [c.model_dump(mode="json") for c in coarse.candidates]}
    execution = {"job_id": "generation", "attempt": 1, "status": "SUCCEEDED", "produced": [{"kind": "test", "ref": "object"}]}
    conn = object()
    store = CaseStore(conn=conn, executions=lambda actual, ids: [execution])
    store.register(case)
    def reader(actual, read_kind, produced):
        assert actual is conn and read_kind == "COARSE_SEARCH"
        assert produced == ({"kind": "test", "ref": "object"},)
        return deepcopy(content)
    ctx = ExecutionContext("exec_one", "job_one", case.case_id, kind, 1, "trace")
    return ctx, case, store, reader, execution


@pytest.mark.parametrize("kind", ["HINT_EXTRACT", "COARSE_SEARCH", "FINE_VERIFY"])
def test_reads_detached_public_case_input_and_fixed_generation(kind):
    m = import_module("daesingo.worker.search_inputs")
    ctx, case, store, reader, _ = setup_input(kind)
    load = m.SearchInputs(transaction=lambda callback: callback(store.conn), store_factory=lambda conn: store, reader=reader)
    data = load(ctx)
    case.hints["vehicle"] = "changed"
    assert data.prior_hints == {"vehicle": "old hint"}
    if kind == "HINT_EXTRACT": assert data.description == "description"
    else: assert data.scope.scope_id == case.job_records[0]["scope_ref"]
    if kind == "FINE_VERIFY":
        assert data.candidate.candidate_id == case.observation_inputs[ctx.job_id]["candidate_id"]
        assert data.candidate.span.start_ms == case.observation_inputs[ctx.job_id]["span"]["start_ms"]


@pytest.mark.parametrize("mode", ["job", "kind", "case", "scope", "generation", "failed_generation", "candidate", "span"])
def test_invalid_job_binding_is_rejected_before_public_search(mode):
    m = import_module("daesingo.worker.search_inputs")
    ctx, case, store, reader, execution = setup_input()
    if mode == "job": case.job_records.pop()
    elif mode == "kind": case.job_records[-1]["kind"] = "PLATE_READ"
    elif mode == "case": case.job_records[-1]["case_id"] = "other"
    elif mode == "scope": case.job_records[-1]["scope_ref"] = "absent"
    elif mode == "generation": case.job_records[0]["scope_ref"] = "other"
    elif mode == "failed_generation": execution["status"] = "FAILED"
    elif mode == "candidate": case.observation_inputs[ctx.job_id]["candidate_id"] = "absent"
    else: case.observation_inputs[ctx.job_id]["span"]["end_ms"] += 1
    store = CaseStore(conn=store.conn, executions=store.executions)
    store.register(case)
    load = m.SearchInputs(transaction=lambda callback: callback(store.conn), store_factory=lambda conn: store, reader=reader)
    with pytest.raises((ValueError, KeyError)):
        load(ctx)
