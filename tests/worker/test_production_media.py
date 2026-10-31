"""Production Recording -> Search source bridge, generated local input only."""
from importlib import import_module
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from daesingo.recording import RecordingService, ContractRef
from daesingo.recording.repository import InMemoryRecordingRepository
from daesingo.search import AnalysisScope
from daesingo.search.config import GeminiSearchConfig
from daesingo.worker.search_handlers import SearchInput
from daesingo.common.jobs.cancel import CancelSignal, CancellationRequested
from tests.recording.test_local_time_sources import make_media


def setup_media(make_media, monkeypatch, tmp_path, *, cancel=False, foreign=False):
    module = import_module("daesingo.worker.production_media")
    from daesingo.recording.factory import RecordingSettings
    from tests.recording.test_factory_config import mapping
    repo = InMemoryRecordingRepository()
    with RecordingService(repo) as seed:
        registered = seed.register_local_source(make_media(), case_id="case-a")
        timeline = seed.create_relative_timeline(registered.source_asset.source_asset_ref)
    scope = AnalysisScope.model_validate({"scope_id": "scope", "contract_version": "1.1.0",
        "time_ranges": [{"kind": "TIMELINE_RELATIVE", "timeline_ref": {"timeline_id": timeline.timeline_id, "revision": 1},
                         "start_ms": 0, "end_ms": 1000}],
        "target_event_types": ["SIGNAL"], "hint": {"vehicle": None, "free_text": None},
        "budget": {"max_cost_krw": 100, "max_latency_sec": 30}})
    active = []; closes = []; signal = CancelSignal()
    def transaction(callback):
        active.append(True)
        try: return callback(object())
        finally: active.pop()
    class RepositoryAdapter(InMemoryRecordingRepository):
        def __new__(cls, *args, **kwargs): return repo
    monkeypatch.setattr("daesingo.recording.transactional.MySQLRecordingRepository", RepositoryAdapter)
    original_close = RecordingService.close
    def close(service):
        closes.append(service)
        original_close(service)
    monkeypatch.setattr(RecordingService, "close", close)
    from daesingo.recording.materialization import LocalAnalysisMaterializer
    original_encode = LocalAnalysisMaterializer.materialize
    def encode(*args):
        assert not active
        return original_encode(*args)
    monkeypatch.setattr(LocalAnalysisMaterializer, "materialize", encode)
    count = []
    def checkpoint():
        count.append(True)
        if cancel and len(count) == 1: signal.request()
        signal.checkpoint()
    data = SearchInput(scope=scope, case_id="foreign" if foreign else "case-a", checkpoint=checkpoint,
                       video_stream_refs=(registered.media_streams[0].media_stream_ref,))
    factory = module.ProductionMediaFactory(transaction=transaction, storage_root=tmp_path,
        temp_root=tmp_path, settings=RecordingSettings.from_mapping(mapping()),
        search_settings=SimpleNamespace(api_key=SecretStr("local-test"), config=GeminiSearchConfig()))
    return factory, data, repo, closes, active


def test_execution_local_source_is_public_reopenable_and_closes_after_provider_error(make_media, monkeypatch, tmp_path):
    factory, data, repo, closes, active = setup_media(make_media, monkeypatch, tmp_path)
    with pytest.raises(RuntimeError):
        with factory(data) as service:
            assert not active
            source, = service.resolver.resolve(data.scope)
            with service.resolver.open_source(source.source_ref) as media:
                assert not active and media.stream.read(4)
            raise RuntimeError("provider failure")
    assert len(closes) == 1
    with RecordingService(repo) as restarted:
        assert restarted.get_analysis_source(source.source_ref.ref).media_stream_refs
        assert ContractRef(kind="analysis_source", ref=source.source_ref.ref) in repo.get_case_assets("case-a")
        opened = restarted.open_analysis_source(source.source_ref.ref)
        with opened.stream: assert opened.stream.read(4)
    assert not active


@pytest.mark.parametrize("mode", ["cancel", "foreign"])
def test_checkpoint_and_case_ownership_prevent_media_preparation(make_media, monkeypatch, tmp_path, mode):
    factory, data, repo, closes, active = setup_media(make_media, monkeypatch, tmp_path,
        cancel=mode == "cancel", foreign=mode == "foreign")
    with pytest.raises(CancellationRequested if mode == "cancel" else ValueError):
        with factory(data): pytest.fail("invalid source entered Search")
    assert len(closes) == 1 and not active
