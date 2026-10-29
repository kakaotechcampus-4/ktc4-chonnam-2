from contextlib import contextmanager
from importlib import import_module
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from daesingo.common.jobs.cancel import CancellationRequested
from daesingo.common.jobs.execution import ExecutionContext, validated_terminal
from daesingo.recording import RecordingCapabilityError


KINDS = ("REPORT_VIDEO_EXPORT", "PLATE_IMAGE_EXPORT")


def dependencies(kind, *, code=None, fault=None, cancel=None):
    module = import_module("daesingo.worker.export_handlers")
    ctx = ExecutionContext("execution", "job", "case", kind, 1, "trace")
    calls = []
    request = {"incident_clip_ref": "clip", "post_stamp": {"needed": False, "value": None}} if kind == KINDS[0] else {
        "incident_clip_ref": "clip", "frame_ref": "frame", "plate_bbox_xywh": [1, 2, 3, 4], "max_byte_size": 30_000_000}
    def load(context):
        calls.append("load")
        if fault == "load": raise RecordingCapabilityError("REPORT_VIDEO_EXPORT_FAILED", "private")
        if cancel == "load": ctx.cancel_signal.request()
        return module.ExportInput("case", request)
    class Recording:
        def invoke(self, **kw):
            assert kw == request
            calls.append("capability")
            if cancel == "capability": ctx.cancel_signal.request()
            if code: raise RecordingCapabilityError(code, "private credential /source")
            if fault == "db": raise OperationalError("private", {}, Exception())
            return SimpleNamespace(derived_asset_ref="derived")
        export_report_video = export_plate_image = invoke
    @contextmanager
    def factory(data):
        calls.append("open")
        try:
            if cancel == "open": ctx.cancel_signal.request()
            yield Recording()
            if fault == "publish": raise RecordingCapabilityError("PLATE_IMAGE_EXPORT_FAILED", "private")
        finally:
            calls.append("close")
            if cancel == "close": ctx.cancel_signal.request()
    return module.export_registry(load=load, service_factory=factory), ctx, calls


@pytest.mark.parametrize("kind", KINDS)
def test_one_capability_and_execution_owned_result(kind):
    registry, ctx, calls = dependencies(kind)
    result = validated_terminal(registry.dispatch(ctx), execution_id=ctx.execution_id)
    assert result.status == "SUCCEEDED"
    assert result.objects[0].payload == {"derived_asset_ref": "derived"}
    assert calls == ["load", "open", "capability", "close"]


@pytest.mark.parametrize("kind,code,want", [
    (KINDS[0], "REPORT_VIDEO_EXPORT_FAILED", "REPORT_VIDEO_EXPORT_FAILED"),
    (KINDS[1], "PLATE_IMAGE_EXPORT_FAILED", "PLATE_IMAGE_EXPORT_FAILED"),
    (KINDS[1], "PLATE_IMAGE_OUTPUT_LIMIT_UNSATISFIABLE", "PLATE_IMAGE_OUTPUT_LIMIT_UNSATISFIABLE"),
    (KINDS[0], "PLATE_IMAGE_EXPORT_FAILED", "RUNTIME_HANDLER_ERROR"),
    (KINDS[1], "unknown /private", "RUNTIME_HANDLER_ERROR")])
def test_literal_taxonomy_only(kind, code, want):
    registry, ctx, calls = dependencies(kind, code=code)
    result = registry.dispatch(ctx)
    assert result.status == "FAILED" and result.failure_kind == want and not result.objects
    assert calls[-1] == "close" and calls.count("capability") == 1


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("phase", ["load", "open", "capability", "close"])
def test_cancel_propagates_and_closes(kind, phase):
    registry, ctx, calls = dependencies(kind, cancel=phase)
    with pytest.raises(CancellationRequested): registry.dispatch(ctx)
    assert calls.count("capability") == (1 if phase in {"capability", "close"} else 0)
    if phase != "load": assert calls[-1] == "close"


@pytest.mark.parametrize("fault", ["load", "db", "publish"])
def test_infrastructure_is_not_export_failure(fault):
    registry, ctx, calls = dependencies(KINDS[1], fault=fault)
    result = registry.dispatch(ctx)
    assert result.failure_kind == "RUNTIME_HANDLER_ERROR"


def test_cancel_after_known_failure_still_propagates():
    registry, ctx, calls = dependencies(KINDS[1], code="PLATE_IMAGE_EXPORT_FAILED", cancel="close")
    with pytest.raises(CancellationRequested): registry.dispatch(ctx)


def test_absent_factory_leaves_kinds_unregistered():
    module = import_module("daesingo.worker.export_handlers")
    result = module.export_registry(load=lambda ctx: None).dispatch(ExecutionContext("e", "j", "c", KINDS[1], 1, "t"))
    assert result.failure_kind == "RUNTIME_UNREGISTERED_KIND"
