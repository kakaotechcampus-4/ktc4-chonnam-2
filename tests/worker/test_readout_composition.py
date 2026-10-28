from contextlib import contextmanager
from types import SimpleNamespace
from importlib import import_module

import pytest

from daesingo.common.jobs.execution import ExecutionContext
from tests.worker.readout_support import OfflineOcr, ObservedUsage


def test_default_root_still_leaves_readout_absent():
    root = import_module("daesingo.worker.composition_root")
    registry = root.compose_registry(engine=object(), startup=SimpleNamespace())
    for kind in ("PLATE_READ", "OVERLAY_TIME_READ"):
        assert registry.dispatch(ExecutionContext("e", "j", "c", kind, 1, "t")).failure_kind == "RUNTIME_UNREGISTERED_KIND"


def test_explicit_factory_registers_both_and_preserves_other_handlers(monkeypatch):
    m = import_module("daesingo.worker.readout_composition")
    handlers = import_module("daesingo.worker.readout_handlers")
    monkeypatch.setattr(m.ReadoutInputs, "__call__", lambda self, ctx: handlers.ReadoutInput("c", "candidate", "generation", "clip"))
    @contextmanager
    def factory(data): yield handlers.ReadoutSession(OfflineOcr(), None)
    root = import_module("daesingo.worker.composition_root")
    registry = root.compose_registry(engine=object(), startup=SimpleNamespace(), readout_provider_factory=factory)
    for kind in ("PLATE_READ", "OVERLAY_TIME_READ"):
        ctx = ExecutionContext("e", "j", "c", kind, 1, "t", usage_sink=ObservedUsage())
        assert registry.dispatch(ctx).status == "SUCCEEDED"
    for kind in ("REPORT_VIDEO_EXPORT", "PLATE_IMAGE_EXPORT"):
        assert registry.dispatch(ExecutionContext("e", "j", "c", kind, 1, "t")).failure_kind == "RUNTIME_UNREGISTERED_KIND"
    assert "HINT_EXTRACT" in registry._handlers


@pytest.mark.parametrize("error_at", [None, "clip", "factory", "body"])
def test_recording_public_clip_lookup_and_close_per_execution(error_at):
    m = import_module("daesingo.worker.readout_composition")
    handlers = import_module("daesingo.worker.readout_handlers")
    events = []
    class Recording:
        def get_incident_clip(self, ref):
            assert ref == "clip"
            events.append("clip")
            if error_at == "clip": raise ValueError("lookup failed")
            return SimpleNamespace(incident_clip_ref=ref, duration_sec=2.5)
        def close(self): events.append("close")
    @contextmanager
    def recording(data):
        try: yield Recording()
        finally: Recording().close()
    def ocr(service):
        events.append("factory")
        if error_at == "factory": raise ValueError("provider construction failed")
        return OfflineOcr()
    factory = m.RecordingOcrFactory(recording_factory=recording, ocr_factory=ocr)
    def body():
        with factory(handlers.ReadoutInput("c", "candidate", "generation", "clip")) as session:
            assert session.processed_duration_sec == 2.5
            assert isinstance(session.provider, OfflineOcr)
            if error_at == "body": raise ValueError("call failed")
    if error_at:
        with pytest.raises(ValueError): body()
    else: body()
    assert events[-1] == "close" and events.count("close") == 1
