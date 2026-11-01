from copy import deepcopy
from dataclasses import replace
from importlib import import_module

import pytest

from daesingo.case.store import CaseStore
from test_search_inputs import setup_input


def bound(kind="PLATE_READ"):
    ctx, case, store, coarse_reader, execution = setup_input(kind)
    source = case.observation_inputs[ctx.job_id]
    source.pop("span"); source.pop("max_latency_sec")
    source["incident_clip_ref"] = "fixed-clip"
    case.job_records.insert(1, {"job_id": "clip", "case_id": ctx.case_id,
        "kind": "INCIDENT_CLIP_BUILD", "scope_ref": case.job_records[0]["scope_ref"]})
    case.observation_inputs["clip"] = {"candidate_id": source["candidate_id"],
        "generation_job_id": "generation", "fine_job_id": "fine"}
    executions = [execution, {"job_id": "clip", "attempt": 1, "status": "SUCCEEDED",
        "produced": [{"kind": "clip", "ref": "clip-result"}]}]
    clip = {"incident_clip_ref": "fixed-clip"}
    def reader(conn, kind, refs):
        if kind == "COARSE_SEARCH": return coarse_reader(conn, kind, refs)
        assert kind == "INCIDENT_CLIP_BUILD"
        return deepcopy(clip)
    def load():
        facade = CaseStore(conn=store.conn, executions=lambda conn, ids: deepcopy(executions))
        facade.register(case)
        return import_module("daesingo.worker.readout_inputs").ReadoutInputs(
            transaction=lambda callback: callback(store.conn), store_factory=lambda conn: facade, reader=reader)
    return ctx, case, executions, clip, load


@pytest.mark.parametrize("kind", ["PLATE_READ", "OVERLAY_TIME_READ"])
def test_fixed_job_input_detached_and_not_current_selection(kind):
    ctx, case, executions, clip, load = bound(kind)
    value = load()(ctx)
    assert value.case_id == ctx.case_id and value.incident_clip_ref == "fixed-clip"
    case.observation_inputs[ctx.job_id]["incident_clip_ref"] = "changed"
    assert value.incident_clip_ref == "fixed-clip"


@pytest.mark.parametrize("mode", ["case", "job", "duplicate_job", "kind", "context_kind", "candidate", "generation",
    "generation_kind", "generation_case", "scope", "clip_input_candidate", "clip_input_generation", "clip_scope",
    "clip_case", "clip_ref", "clip_payload", "clip_failed", "clip_newer_failed", "coarse_failed", "empty_clip"])
def test_all_binding_mismatches_rejected(mode):
    ctx, case, executions, clip, load = bound()
    source = case.observation_inputs[ctx.job_id]
    if mode == "case": case.job_records[-1]["case_id"] = "other"
    elif mode == "job": ctx = replace(ctx, job_id="absent")
    elif mode == "duplicate_job": case.job_records.append(deepcopy(case.job_records[-1]))
    elif mode == "kind": case.job_records[-1]["kind"] = "OVERLAY_TIME_READ"
    elif mode == "context_kind": ctx = replace(ctx, kind="FINE_VERIFY")
    elif mode == "candidate": source["candidate_id"] = "other"
    elif mode == "generation": source["generation_job_id"] = "absent"
    elif mode == "generation_kind": case.job_records[0]["kind"] = "FINE_VERIFY"
    elif mode == "generation_case": case.job_records[0]["case_id"] = "other"
    elif mode == "scope": case.job_records[-1]["scope_ref"] = "other"
    elif mode == "clip_input_candidate": case.observation_inputs["clip"]["candidate_id"] = "other"
    elif mode == "clip_input_generation": case.observation_inputs["clip"]["generation_job_id"] = "other"
    elif mode == "clip_scope": case.job_records[1]["scope_ref"] = "other"
    elif mode == "clip_case": case.job_records[1]["case_id"] = "other"
    elif mode == "clip_ref": source["incident_clip_ref"] = "other"
    elif mode == "clip_payload": clip["incident_clip_ref"] = "other"
    elif mode == "clip_failed": executions[1]["status"] = "FAILED"
    elif mode == "clip_newer_failed": executions.append({**executions[1], "attempt": 2, "status": "FAILED"})
    elif mode == "coarse_failed": executions[0]["status"] = "FAILED"
    else: source["incident_clip_ref"] = ""
    with pytest.raises((ValueError, KeyError)): load()(ctx)


def test_input_read_transaction_returns_before_provider_context():
    ctx, case, executions, clip, load = bound()
    inputs = load()
    active = []
    def transaction(callback):
        active.append(True)
        try: return callback(inputs.store_factory(None).conn)
        finally: active.pop()
    inputs.transaction = transaction
    data = inputs(ctx)
    assert not active and data.incident_clip_ref == "fixed-clip"


@pytest.mark.parametrize("change", ["reselect", "new_generation"])
def test_queued_job_keeps_original_binding_after_case_selection_changes(change):
    from daesingo.case.domain import Candidate
    ctx, case, executions, clip, load = bound()
    original = deepcopy(case.observation_inputs[ctx.job_id])
    case.candidates = [Candidate("another-candidate", None, None, "new selection", None, selected=True)]
    if change == "new_generation":
        case.job_records.append({**case.job_records[0], "job_id": "new-generation"})
        case.settled_jobs["new-generation"] = "REFLECTED"
        assert case.current_generation_job_id() == "new-generation"
    data = load()(ctx)
    assert data.candidate_id == original["candidate_id"] != case.candidates[0].candidate_id
    assert data.generation_job_id == original["generation_job_id"]
    assert data.incident_clip_ref == "fixed-clip"
