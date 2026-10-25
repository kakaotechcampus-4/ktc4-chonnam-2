from importlib import import_module
from types import SimpleNamespace

from daesingo.common.jobs.execution import ExecutionContext
from search_failure_support import SuccessfulSearchPolicy


def test_stock_worker_registers_intent_without_media_fixture_or_eager_provider():
    module = import_module("daesingo.worker.search_composition")
    # Construction is DB/network-free. Missing sink rejects HINT before loading.
    registry = module.compose_search_registry(engine=object(), startup=SimpleNamespace(),
                                             failures=SuccessfulSearchPolicy())
    intent = registry.dispatch(ExecutionContext("e", "j", "c", "HINT_EXTRACT", 1, "t"))
    assert intent.failure_kind == "RUNTIME_HANDLER_ERROR"
    for kind in ("COARSE_SEARCH", "FINE_VERIFY", "INCIDENT_CLIP_BUILD", "PLATE_READ", "OVERLAY_TIME_READ"):
        assert registry.dispatch(ExecutionContext("e", "j", "c", kind, 1, "t")).failure_kind == "RUNTIME_UNREGISTERED_KIND"
