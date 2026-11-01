from contextlib import contextmanager
from importlib import import_module
import logging
from types import SimpleNamespace

import pytest

from daesingo.case import service as case_service
from daesingo.common.jobs.execution import ExecutionContext
from daesingo.search.schemas import CoarseResponse
from daesingo.search.sources import StaticAnalysisSourceResolver
from tests.case.test_search_progress import setup_search
from tests.search.test_coarse_boundaries import _service, _source
from tests.search._search_service_support import OpenableResolver
from search_failure_support import SuccessfulSearchPolicy


@pytest.mark.parametrize("broken_progress_storage", [False, True])
def test_production_wiring_reports_real_search_and_tolerates_display_write_failure(monkeypatch, broken_progress_storage):
    module = import_module("daesingo.worker.search_composition")
    store, case_id, job, execution = setup_search()
    monkeypatch.setattr(module, "run_worker_transaction", lambda engine, callback, **kw: callback(store.conn))
    monkeypatch.setattr(module, "stored_case_store", lambda conn, **kw: store)
    if broken_progress_storage:
        def unavailable(*args, **kwargs):
            raise RuntimeError("display storage unavailable")
        monkeypatch.setattr(module, "record_search_progress", unavailable)
    search = _service(_source(), CoarseResponse(candidates=[]))
    search.resolver = OpenableResolver(StaticAnalysisSourceResolver({job["scope_ref"]: (_source(),)}, {}))
    original = search.provider
    phases = []
    @contextmanager
    def media(data):
        phases.append(case_service.get_view(case_id, store=store)["scene_search"]["phase"])
        yield search
    class Provider:
        def search_coarse(self, request):
            phases.append(case_service.get_view(case_id, store=store)["scene_search"]["phase"])
            return original.search_coarse(request)
    search.provider = Provider()
    startup = SimpleNamespace(config=SimpleNamespace(media_root=None), modules={}, logger=logging.getLogger("test-progress"))
    registry = module.compose_search_registry(engine=object(), startup=startup,
                                               service_factory=media, failures=SuccessfulSearchPolicy())
    context = ExecutionContext(execution["execution_id"], job["job_id"], case_id,
                               "COARSE_SEARCH", 1, "trace", usage_sink=object())
    result = registry.dispatch(context)
    assert result.status == "SUCCEEDED"
    detail = case_service.get_view(case_id, store=store)["scene_search"]
    assert phases == ["PREPARING", "PREPARING" if broken_progress_storage else "SEARCHING"]
    assert detail["phase"] == ("PREPARING" if broken_progress_storage else "ORGANIZING")
