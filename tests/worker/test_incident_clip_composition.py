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
