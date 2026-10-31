"""Fixed public Case inputs must bind Fine, generation, candidate and scope."""
from copy import deepcopy
from importlib import import_module

import pytest

from daesingo.case.store import CaseStore
from test_search_inputs import setup_input
from test_search_handlers import fixtures


def bound_input():
    ctx, case, old_store, coarse_reader, coarse_execution = setup_input("INCIDENT_CLIP_BUILD")
    source = case.observation_inputs[ctx.job_id]
    source.pop("max_latency_sec")
    source["fine_job_id"] = "fine"
    scope = case.analysis_scopes[case.job_records[0]["scope_ref"]]
    scope["time_ranges"] = [{"kind": "TIMELINE_RELATIVE", "timeline_ref": {
        "timeline_id": source["span"]["timeline_id"], "revision": source["span"]["timeline_revision"]},
        "start_ms": 0, "end_ms": source["span"]["end_ms"] + 1000}]
    case.job_records.insert(1, {"job_id": "fine", "case_id": ctx.case_id, "kind": "FINE_VERIFY",
                              "scope_ref": case.job_records[0]["scope_ref"]})
    case.observation_inputs["fine"] = {k: deepcopy(v) for k, v in source.items() if k != "fine_job_id"}
    _, _, fine = fixtures()
    content = fine.model_dump(mode="json")
    content["visual_evidence"]["candidate_id"] = source["candidate_id"]
    content["analysis_run"]["input_ref"] = {"kind": "analysis_source", "ref": "fixed-analysis"}
    content["visual_evidence"]["input_ref"] = content["analysis_run"]["input_ref"].copy()
    executions = [coarse_execution, {"job_id": "fine", "attempt": 1, "status": "SUCCEEDED",
        "produced": [{"kind": "analysis_run", "ref": content["analysis_run"]["run_id"]}]}]
    def reader(conn, kind, refs):
        if kind == "COARSE_SEARCH":
            value = coarse_reader(conn, kind, refs)
            value["analysis_run"] = fixtures()[1].analysis_run.model_dump(mode="json")
            return value
        assert conn is old_store.conn and kind == "FINE_VERIFY"
        assert refs == tuple(executions[1]["produced"])
        return deepcopy(content)
    def make_load():
        store = CaseStore(conn=old_store.conn, executions=lambda conn, ids: deepcopy(executions))
        store.register(case)
        module = import_module("daesingo.worker.incident_clip_inputs")
        return module.IncidentClipInputs(transaction=lambda callback: callback(store.conn),
            store_factory=lambda conn: store, reader=reader)
    return ctx, case, content, executions, make_load


def test_reads_successful_fine_through_public_reader_and_detaches_fixed_span():
    ctx, case, content, executions, make_load = bound_input()
    data = make_load()(ctx)
    assert data.case_id == ctx.case_id and data.analysis_source_ref == "fixed-analysis"
    span = case.observation_inputs[ctx.job_id]["span"]
    assert data.timeline_ref == {"timeline_id": span["timeline_id"], "revision": span["timeline_revision"]}
    assert data.requested_range == {"start_sec": span["start_ms"] / 1000, "end_sec": span["end_ms"] / 1000}
    case.observation_inputs[ctx.job_id]["span"]["end_ms"] += 1000
    assert data.requested_range["end_sec"] != case.observation_inputs[ctx.job_id]["span"]["end_ms"] / 1000


def test_case_explicit_stream_selection_is_detached_for_the_whole_timeline():
    ctx, case, _, _, make_load = bound_input()
    case.sources = [{"video_stream_ref": "a-rear"}, {"video_stream_ref": "b-rear"}]
    data = make_load()(ctx)
    case.sources[1]["video_stream_ref"] = "b-front"
    assert data.video_stream_refs == ("a-rear", "b-rear")


@pytest.mark.parametrize("mode", ["kind", "case", "scope", "generation", "candidate", "span", "fine_kind",
    "fine_scope", "fine_candidate", "fine_generation", "fine_span", "fine_failed", "newer_failed",
    "visual_candidate", "visual_run", "visual_source", "source_kind", "run_failed", "coarse_candidate_run",
    "scope_timeline", "scope_revision"])
def test_binding_mismatch_rejected_before_media(mode):
    ctx, case, content, executions, make_load = bound_input()
    source = case.observation_inputs[ctx.job_id]
    fine = case.observation_inputs["fine"]
    if mode == "kind": case.job_records[-1]["kind"] = "PLATE_READ"
    elif mode == "case": case.job_records[-1]["case_id"] = "foreign"
    elif mode == "scope": case.job_records[-1]["scope_ref"] = "foreign"
    elif mode == "generation": case.job_records[0]["kind"] = "FINE_VERIFY"
    elif mode == "candidate": source["candidate_id"] = fine["candidate_id"] = "foreign"
    elif mode == "span": source["span"]["end_ms"] += 1
    elif mode == "fine_kind": case.job_records[1]["kind"] = "COARSE_SEARCH"
    elif mode == "fine_scope": case.job_records[1]["scope_ref"] = "foreign"
    elif mode == "fine_candidate": fine["candidate_id"] = "foreign"
    elif mode == "fine_generation": fine["generation_job_id"] = "foreign"
    elif mode == "fine_span": fine["span"]["end_ms"] += 1
    elif mode == "fine_failed": executions[1]["status"] = "FAILED"
    elif mode == "newer_failed": executions.append({**executions[1], "attempt": 2, "status": "FAILED"})
    elif mode == "visual_candidate": content["visual_evidence"]["candidate_id"] = "foreign"
    elif mode == "visual_run": content["visual_evidence"]["run_id"] = "run_foreign"
    elif mode == "visual_source": content["visual_evidence"]["input_ref"]["ref"] = "foreign"
    elif mode == "source_kind":
        content["analysis_run"]["input_ref"]["kind"] = "ANALYSIS_SCOPE"
        content["visual_evidence"]["input_ref"]["kind"] = "ANALYSIS_SCOPE"
    elif mode == "run_failed": content["analysis_run"]["outcome"] = "FAILED"
    elif mode.startswith("scope_"):
        scope = case.analysis_scopes[case.job_records[0]["scope_ref"]]
        if mode == "scope_timeline": scope["time_ranges"][0]["timeline_ref"]["timeline_id"] = "foreign"
        else: scope["time_ranges"][0]["timeline_ref"]["revision"] += 1
    else:
        # Coarse reader is wrapped separately below to corrupt only its candidate link.
        load = make_load(); original = load.reader
        def corrupt(conn, kind, refs):
            value = original(conn, kind, refs)
            if kind == "COARSE_SEARCH": value["candidate_events"][0]["run_id"] = "run_foreign"
            return value
        load.reader = corrupt
        with pytest.raises((ValueError, KeyError)): load(ctx)
        return
    with pytest.raises((ValueError, KeyError)): make_load()(ctx)


def test_frame_aligned_candidate_is_not_restricted_to_original_requested_scope_tail():
    ctx, case, content, executions, make_load = bound_input()
    span = case.observation_inputs[ctx.job_id]["span"]
    scope = case.analysis_scopes[case.job_records[0]["scope_ref"]]
    # Recording preserves actual frame coverage (e.g. request end 1.26s ->
    # source end 1.3s); Search publishes that actual coordinate in CandidateSpan.
    scope["time_ranges"][0]["start_ms"] = span["start_ms"]
    scope["time_ranges"][0]["end_ms"] = span["end_ms"] - 40
    data = make_load()(ctx)
    assert data.requested_range["end_sec"] == span["end_ms"] / 1000
    assert data.analysis_source_ref == "fixed-analysis"
