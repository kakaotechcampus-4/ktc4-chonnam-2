"""Clip capability has its own terminal boundary; no provider calls."""
from contextlib import contextmanager
from dataclasses import replace
from importlib import import_module
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from daesingo.common.jobs.cancel import CancellationRequested
from daesingo.common.jobs.execution import ExecutionContext, validated_terminal
from daesingo.common.db.errors import BeforeCommitFailure, CommitOutcomeUnknown, TransactionBoundaryError, TransactionRetryExhausted
from daesingo.recording import RecordingCapabilityError


def dependencies(*, error=None, cancel=None, load_error=None, metadata=None, owns=True, close_error=None, source_error=None,
                 requested_range=None):
    module = import_module("daesingo.worker.incident_clip_handlers")
    context = ExecutionContext("exec", "clip", "case", "INCIDENT_CLIP_BUILD", 1, "trace")
    calls = []
    data = SimpleNamespace(case_id="case", timeline_ref={"timeline_id": "tl", "revision": 1},
        requested_range=requested_range or {"start_sec": 1, "end_sec": 2}, analysis_source_ref="analysis")
    def checkpoint(stage):
        if cancel == stage: context.cancel_signal.request()
    def load(ctx):
        calls.append("load")
        if load_error: raise load_error
        checkpoint("load")
        return data
    class Recording:
        def get_analysis_source(self, ref):
            assert ref == "analysis"
            calls.append("source"); checkpoint("source")
            if source_error: raise source_error
            return metadata or SimpleNamespace(timeline_ref=SimpleNamespace(timeline_id="tl", revision=1),
                timeline_range=SimpleNamespace(start_sec=0, end_sec=3), duration_sec=3, media_stream_refs=["video"])
        def get_media_stream(self, ref):
            assert ref == "video"
            calls.append("stream"); checkpoint("stream")
            return SimpleNamespace(media_type="VIDEO", source_asset_ref="asset")
        def owns_asset(self, case_id, ref):
            assert case_id == "case" and ref.ref == "asset"
            calls.append("owns"); checkpoint("owns")
            return owns
        def resolve_span(self, timeline, requested, *, media_stream_ref):
            assert timeline == data.timeline_ref and requested == data.requested_range
            assert media_stream_ref == "video"
            calls.append("resolve"); checkpoint("resolve")
            return "resolution"
        def build_incident_clip(self, resolution):
            assert resolution == "resolution"
            calls.append("build"); checkpoint("build")
            if error: raise error
            return SimpleNamespace(incident_clip_ref="clip-ref")
    @contextmanager
    def service(value):
        assert value is data
        calls.append("open"); checkpoint("open")
        try: yield Recording()
        finally:
            calls.append("close")
            checkpoint("close")
            if close_error: raise close_error
    registry = module.incident_clip_registry(load=load, service_factory=service)
    return registry, context, calls


def test_success_exact_payload_and_one_capability_call():
    registry, context, calls = dependencies()
    result = validated_terminal(registry.dispatch(context), execution_id=context.execution_id)
    assert result.status == "SUCCEEDED" and result.failure_kind is None
    assert len(result.objects) == len(result.produced) == 1
    assert result.objects[0].payload == {"incident_clip_ref": "clip-ref"}
    assert calls == ["load", "open", "source", "stream", "owns", "resolve", "build", "close"]


def test_same_immutable_clip_has_distinct_execution_object_receipts():
    registry, context, calls = dependencies()
    first = validated_terminal(registry.dispatch(context), execution_id=context.execution_id)
    second_context = replace(context, execution_id="exec-second", job_id="new-clip-job")
    second = validated_terminal(registry.dispatch(second_context), execution_id=second_context.execution_id)
    assert first.objects[0].payload == second.objects[0].payload == {"incident_clip_ref": "clip-ref"}
    assert first.produced != second.produced
    assert calls.count("build") == 2  # one call for each independent execution


@pytest.mark.parametrize("code,want", [
    ("INCIDENT_CLIP_BUILD_FAILED", "RECORDING_INCIDENT_CLIP_BUILD_FAILED"),
    ("UNKNOWN_CODE_private/path", "RUNTIME_HANDLER_ERROR"),
    ("UNAVAILABLE", "RUNTIME_HANDLER_ERROR"),
])
def test_only_confirmed_capability_code_maps_without_raw_details(code, want):
    registry, context, calls = dependencies(error=RecordingCapabilityError(code, "private credential locator"))
    result = registry.dispatch(context)
    assert result.status == "FAILED" and result.failure_kind == want
    assert result.produced == result.objects == ()
    assert calls.count("build") == 1 and calls[-1] == "close"


@pytest.mark.parametrize("stage", ["before", "load", "open", "source", "stream", "owns", "resolve", "build"])
def test_checkpoint_cancel_never_publishes_success_and_closes(stage):
    registry, context, calls = dependencies(cancel=stage)
    if stage == "before": context.cancel_signal.request()
    with pytest.raises(CancellationRequested): registry.dispatch(context)
    assert calls.count("build") == (1 if stage == "build" else 0)
    if "open" in calls: assert calls[-1] == "close"


@pytest.mark.parametrize("error", [ValueError("private"), OperationalError("private", {}, Exception("db")),
    BeforeCommitFailure("db"), CommitOutcomeUnknown(), TransactionBoundaryError(), TransactionRetryExhausted(3, outcome_unknown=True)])
def test_capability_runtime_errors_do_not_become_recording_failures(error):
    registry, context, calls = dependencies(error=error)
    assert registry.dispatch(context).failure_kind == "RUNTIME_HANDLER_ERROR"
    assert calls.count("build") == 1 and calls[-1] == "close"


def test_input_recording_shaped_error_is_not_capability_failure():
    registry, context, calls = dependencies(load_error=RecordingCapabilityError("INCIDENT_CLIP_BUILD_FAILED", "private"))
    assert registry.dispatch(context).failure_kind == "RUNTIME_HANDLER_ERROR"
    assert calls == ["load"]


@pytest.mark.parametrize("where", ["source", "close", "checkpoint"])
def test_recording_shaped_errors_outside_build_keep_runtime_boundary(where, monkeypatch):
    error = RecordingCapabilityError("INCIDENT_CLIP_BUILD_FAILED", "private path")
    registry, context, calls = dependencies(source_error=error if where == "source" else None,
        close_error=error if where == "close" else None)
    if where == "checkpoint":
        def checkpoint(ctx): raise error
        monkeypatch.setattr(ExecutionContext, "checkpoint", checkpoint)
    result = registry.dispatch(context)
    assert result.failure_kind == "RUNTIME_HANDLER_ERROR" and result.produced == result.objects == ()
    assert calls.count("build") == (1 if where == "close" else 0)


def test_cancel_during_close_after_known_capability_failure_reaches_checkpoint():
    registry, context, calls = dependencies(cancel="close",
        error=RecordingCapabilityError("INCIDENT_CLIP_BUILD_FAILED", "private"))
    with pytest.raises(CancellationRequested): registry.dispatch(context)
    assert calls.count("build") == 1 and calls[-1] == "close"


@pytest.mark.parametrize("mode", ["timeline", "revision", "duration", "missing_timeline", "no_stream", "ambiguous_stream", "foreign"])
def test_source_binding_rejects_before_build_and_always_closes(mode):
    source = SimpleNamespace(timeline_ref=SimpleNamespace(timeline_id="tl", revision=1),
        timeline_range=SimpleNamespace(start_sec=0, end_sec=3), duration_sec=3, media_stream_refs=["video"])
    if mode == "timeline": source.timeline_ref.timeline_id = "other"
    elif mode == "revision": source.timeline_ref.revision = 2
    elif mode == "duration": source.duration_sec = 1.5
    elif mode == "missing_timeline": source.timeline_ref = None
    elif mode == "no_stream": source.media_stream_refs = []
    elif mode == "ambiguous_stream": source.media_stream_refs = ["video", "video"]
    registry, context, calls = dependencies(metadata=source, owns=mode != "foreign")
    assert registry.dispatch(context).failure_kind == "RUNTIME_HANDLER_ERROR"
    assert "build" not in calls and calls[-1] == "close"


def test_source_range_uses_search_millisecond_coordinates_without_clamping_case_span():
    # Search emits round(seconds * 1000). 30fps boundaries 1/30 and 20/30
    # therefore become the Case-fixed interval [33, 667] ms.
    source = SimpleNamespace(timeline_ref=SimpleNamespace(timeline_id="tl", revision=1),
        timeline_range=SimpleNamespace(start_sec=1 / 30, end_sec=20 / 30), duration_sec=19 / 30, media_stream_refs=["video"])
    registry, context, calls = dependencies(metadata=source, requested_range={"start_sec": .033, "end_sec": .667})
    result = registry.dispatch(context)
    assert result.status == "SUCCEEDED" and result.objects[0].payload == {"incident_clip_ref": "clip-ref"}
    assert calls.count("resolve") == calls.count("build") == 1


def test_source_endpoint_uses_the_same_duration_coordinate_as_search():
    # MP4 duration and actual frame timeline coverage are independently probed.
    # Search computes round((source.start + source.duration) * 1000), not
    # round(source.timeline_range.end * 1000): these yield 84 vs 83 here.
    source = SimpleNamespace(timeline_ref=SimpleNamespace(timeline_id="tl", revision=1),
        timeline_range=SimpleNamespace(start_sec=1 / 60, end_sec=5 / 60), duration_sec=.067,
        media_stream_refs=["video"])
    registry, context, calls = dependencies(metadata=source, requested_range={"start_sec": .017, "end_sec": .084})
    assert registry.dispatch(context).status == "SUCCEEDED"
    assert calls.count("build") == 1


def test_absent_capability_is_unregistered_without_loading():
    module = import_module("daesingo.worker.incident_clip_handlers")
    def load(ctx): pytest.fail("unconfigured kind loaded input")
    registry = module.incident_clip_registry(load=load)
    assert registry.dispatch(ExecutionContext("e", "j", "c", "INCIDENT_CLIP_BUILD", 1, "t")).failure_kind == "RUNTIME_UNREGISTERED_KIND"
