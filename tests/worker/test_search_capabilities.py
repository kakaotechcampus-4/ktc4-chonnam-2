"""Handler -> real Search -> real Gemini adapter -> offline SDK transport fake."""

from contextlib import contextmanager

import pytest

from daesingo.common.jobs.execution import ExecutionContext
from daesingo.common.usage.port import UsagePersistenceError
from daesingo.search import IntentHintExtractor, SearchService
from daesingo.search.config import GeminiSearchConfig
from daesingo.search.intent import IntentHintExtraction
from daesingo.search.schemas import CoarseResponse, FineResponse
from daesingo.search.scope import AnalysisScope
from daesingo.search.sources import StaticAnalysisSourceResolver
from daesingo.worker.search_handlers import SearchInput, search_registry
from tests.search._search_service_support import OpenableResolver
from tests.search.test_usage_sink import _Completions, _RecordingSink, _provider, _source, _media
from search_failure_support import SuccessfulSearchPolicy


@pytest.mark.parametrize("kind", ["HINT_EXTRACT", "COARSE_SEARCH", "FINE_VERIFY"])
@pytest.mark.parametrize("fault", [None, "begin", "finish"])
def test_actual_capability_usage_attempts_and_error_boundary(monkeypatch, tmp_path, kind, fault):
    scope = AnalysisScope.model_validate({"scope_id": "scope-test", "contract_version": "1.1.0",
        "time_ranges": [{"kind": "TIMELINE_RELATIVE", "timeline_ref": {"timeline_id": "clip-usage-1", "revision": 1},
                         "start_ms": 0, "end_ms": 5000}],
        "target_event_types": ["SIGNAL"], "hint": {"vehicle": None, "free_text": None},
        "budget": {"max_cost_krw": 100, "max_latency_sec": 30}})
    coarse = CoarseResponse.model_validate({"candidates": [{"event_type": "SIGNAL", "span": {"start_sec": 1, "end_sec": 3},
        "at_sec": 2, "observed": ["red signal"], "score": .9}]})
    fine = FineResponse.model_validate({"verification": "NOT_OBSERVED", "visual_event_type": None,
        "target": {"association_status": "NOT_FOUND", "described_as": None, "match_with_hint": None, "track_ref": None},
        "primitives": [], "temporal_facts": [], "uncertainties": []})
    hint = IntentHintExtraction(time_hint=None, vehicle_hint="흰 차", situation_hint=None, location_hint=None,
                               correction_target=None, confidence="high", reasoning="not persisted")
    calls = _Completions([coarse, fine] if kind == "FINE_VERIFY" else [hint if kind == "HINT_EXTRACT" else coarse])
    provider = _provider(monkeypatch, calls)
    config = GeminiSearchConfig(max_retries=0)
    source = _source()
    resolver = OpenableResolver(StaticAnalysisSourceResolver({scope.scope_id: (source,)}, {source.source_id: source}))
    class Media:
        @contextmanager
        def prepare_coarse(self, media, deadline): yield _media(tmp_path)
        @contextmanager
        def prepare_fine(self, media, start, end, deadline): yield _media(tmp_path)
    def make(): return SearchService(resolver, provider, config, Media())
    candidate = make().search_candidates(scope).candidates[0] if kind == "FINE_VERIFY" else None
    before = calls.calls
    sink = _RecordingSink(fail_begin=fault == "begin", fail_finish=fault == "finish")
    ctx = ExecutionContext("exec-capability", "job", "case", kind, 1, "trace", usage_sink=sink)
    @contextmanager
    def media_factory(data): yield make()  # fresh service, no Coarse budget cache
    registry = search_registry(load=lambda _: SearchInput(description="text", scope=scope, candidate=candidate),
        intent_factory=lambda: IntentHintExtractor(provider, config), service_factory=media_factory,
        failures=SuccessfulSearchPolicy())
    if fault:
        with pytest.raises(UsagePersistenceError): registry.dispatch(ctx)
        assert calls.calls - before == (0 if fault == "begin" else 1)
    else:
        result = registry.dispatch(ctx)
        assert result.status == "SUCCEEDED", result.failure_kind
        assert calls.calls - before == len(sink.begins) == len(sink.finishes) == 1
        assert sink.finishes[0]["cost"] == {"amount": None, "currency": "KRW"}
        if kind == "HINT_EXTRACT":
            assert sink.begins[0]["run_ref_reason"] == "DIRECT_NO_RUN"
        else:
            assert sink.begins[0]["run_ref"] == result.produced[0].model_dump()
            assert result.objects[0].payload["analysis_run"]["usage_refs"] == [sink.begins[0]["usage_id"]]
            if kind == "FINE_VERIFY":
                assert result.objects[0].payload["visual_evidence"]["verification"] == "NOT_OBSERVED"
