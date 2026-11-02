from importlib import import_module
from types import SimpleNamespace

import pytest

from daesingo.common.jobs.execution import ExecutionContext, HandlerResult
from daesingo.worker.registry import KindRegistry


def test_registry_merge_preserves_dispatch_and_rejects_duplicate_kind():
    one = KindRegistry({"ONE": lambda ctx: HandlerResult()})
    two = KindRegistry({"TWO": lambda ctx: HandlerResult()})
    combined = one.merged(two)
    for kind in ("ONE", "TWO"):
        assert combined.dispatch(ExecutionContext("e", "j", "c", kind, 1, "t")).status == "SUCCEEDED"
    with pytest.raises(ValueError): one.merged(one)
    assert one.dispatch(ExecutionContext("e", "j", "c", "TWO", 1, "t")).failure_kind == "RUNTIME_UNREGISTERED_KIND"


def test_default_composition_does_not_claim_clip_or_readout_capability():
    module = import_module("daesingo.worker.incident_clip_composition")
    registry = module.compose_incident_clip_registry(engine=object(), startup=SimpleNamespace())
    for kind in ("INCIDENT_CLIP_BUILD", "PLATE_READ", "OVERLAY_TIME_READ", "REPORT_VIDEO_EXPORT", "PLATE_IMAGE_EXPORT"):
        assert registry.dispatch(ExecutionContext("e", "j", "c", kind, 1, "t")).failure_kind == "RUNTIME_UNREGISTERED_KIND"


def test_worker_root_combines_search_and_clip_without_eager_db_or_provider():
    module = import_module("daesingo.worker.composition_root")
    registry = module.compose_registry(engine=object(), startup=SimpleNamespace())
    for kind in ("INCIDENT_CLIP_BUILD", "PLATE_READ", "OVERLAY_TIME_READ"):
        assert registry.dispatch(ExecutionContext("e", "j", "c", kind, 1, "t")).failure_kind == "RUNTIME_UNREGISTERED_KIND"


def test_stored_case_consumer_uses_validating_reader():
    from daesingo.worker.case_composition import StoredCaseReflector, stored_case_store
    reflector = StoredCaseReflector(storage_root="unused")
    assert reflector.reader.assemble is not None
    with pytest.raises(ValueError):
        reflector.reader.assemble("INCIDENT_CLIP_BUILD", ({"incident_clip_ref": "clip", "preview_frame_ref": 1},))
    facade = stored_case_store(object(), storage_root="unused")
    # Construction remains lazy; no Recording/media capability was called.
    assert facade.conn is not None


def test_production_composition_connects_real_case_selection_and_positions(monkeypatch):
    from daesingo.case.preview_frame import (
        candidate_frame_position, preview_frame_position, thumbnail_candidate_ids,
    )
    from test_incident_clip_inputs import bound_input
    from daesingo.case.service import candidates_from_events
    from test_search_handlers import fixtures
    from test_incident_frames import inputs

    module = import_module("daesingo.worker.incident_clip_composition")
    captured = {}
    def registry(**kwargs):
        captured.update(kwargs)
        return KindRegistry({})
    monkeypatch.setattr(module, "incident_clip_registry", registry)
    module.compose_incident_clip_registry(engine=object(), startup=SimpleNamespace(), service_factory=object())
    load, issuer = captured["load"], captured["frames"]
    assert load.thumbnail_candidates is thumbnail_candidate_ids
    assert issuer.preview_position is preview_frame_position
    assert issuer.candidate_position is candidate_frame_position

    ctx, case, _, _, make_load = bound_input()
    case.stage = "SEARCHING"
    case.receive_candidates(candidates_from_events([
        c.model_dump(mode="json") for c in fixtures()[1].candidates]), job_id="generation")
    case.select_top_ranked()
    actual = make_load()
    actual.thumbnail_candidates = load.thumbnail_candidates
    data = actual(ctx)
    assert data.frames_current and data.thumbnail_candidates == (data.candidate,)
    span = inputs().candidate.span.model_dump(mode="json")
    resolution = {"status": "RESOLVED_FULL", "timeline_ref": {
        "timeline_id": span["timeline_id"], "revision": span["timeline_revision"]},
        "requested_range": {"start_sec": 1., "end_sec": 2.}, "spans": [{
            "media_stream_ref": "video", "timeline_range": {"start_sec": 1., "end_sec": 2.},
            "source_range": {"start_sec": 4., "end_sec": 5.}}]}
    clip = {"timeline_ref": resolution["timeline_ref"], "timeline_range": resolution["requested_range"],
        "source_provenance": {"asset_spans": resolution["spans"]}}
    assert issuer.preview_position(clip, span, 1500) == ("video", 4.5)
    assert issuer.candidate_position(resolution, span, 1500) == ("video", 4.5)
