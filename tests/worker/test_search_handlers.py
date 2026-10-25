"""Public Search calls stay real; only provider/media I/O is replaced offline."""

from contextlib import contextmanager
from importlib import import_module
from types import SimpleNamespace

import pytest

from daesingo.common.jobs.execution import ExecutionContext, validated_terminal
from daesingo.common.jobs.cancel import CancellationRequested
from daesingo.common.usage.port import UsagePersistenceError
from daesingo.search import IntentHintExtractor
from daesingo.search.config import GeminiSearchConfig
from daesingo.search.fixtures import FixtureSearchService
from daesingo.search.intent import IntentHintExtraction
from daesingo.search.provider import ProviderResult
from daesingo.search.usage import ProviderUsage
from pathlib import Path
from search_failure_support import SuccessfulSearchPolicy


def module():
    return import_module("daesingo.worker.search_handlers")


def context(kind="HINT_EXTRACT", sink=None):
    return ExecutionContext("exec_one", "job_one", "case_one", kind, 1, "trace", usage_sink=sink)


class IntentProvider:
    def __init__(self, callback=None):
        self.calls = 0
        self.callback = callback

    def invoke_text(self, request):
        self.calls += 1
        assert request.usage is not None
        if self.callback:
            self.callback(request.usage)
        return ProviderResult(response=IntentHintExtraction(time_hint=None, vehicle_hint="흰 차",
            situation_hint=None, location_hint=None, correction_target=None, confidence="high", reasoning="private"),
            usage=ProviderUsage(10, 2, 0, 12), latency_ms=7)


def dependencies(ctx, *, provider=None, cancel_at=None):
    m = module()
    seen = []
    scope, coarse, fine = fixtures()
    provider = provider or IntentProvider(lambda usage: seen.append(usage.sink))
    data = m.SearchInput(description="private description", prior_hints={}, scope=scope,
                         candidate=coarse.candidates[0])

    def load(incoming):
        assert incoming is ctx
        seen.append("load")
        if cancel_at == "load": ctx.cancel_signal.request()
        return data

    @contextmanager
    def service(incoming):
        assert incoming is data
        seen.append("open")
        if cancel_at == "open": ctx.cancel_signal.request()
        class Resolver:
            def resolve(self, value):
                assert value is scope
                seen.append("resolve")
                if cancel_at == "resolve": ctx.cancel_signal.request()
                return (SimpleNamespace(source_ref=fine.analysis_run.input_ref),)
        class Service:
            resolver = Resolver()
            def search_candidates(self, value, *, usage_sink):
                assert value is scope and usage_sink is ctx.usage_sink
                seen.append("coarse")
                return coarse
            def verify_visual(self, ref, candidate, hint, event_type, *, max_latency_sec, usage_sink):
                assert ref == fine.analysis_run.input_ref and candidate is data.candidate
                assert hint == scope.hint and event_type == data.candidate.event_type_hint
                assert max_latency_sec == scope.budget.max_latency_sec and usage_sink is ctx.usage_sink
                seen.append("fine")
                return fine
        try:
            yield Service()
        finally:
            seen.append("close")
    registry = m.search_registry(load=load,
        intent_factory=lambda: IntentHintExtractor(provider, GeminiSearchConfig()),
        service_factory=service, failures=SuccessfulSearchPolicy())
    return registry, seen, provider


def fixtures():
    from daesingo.search.scope import AnalysisScope
    import json
    raw = json.loads(Path("data/mock/search/scenario_happy_001.json").read_text(encoding="utf-8"))
    scope = AnalysisScope.model_validate(raw["analysis_scopes"][0])
    service = FixtureSearchService(Path("data/mock/search"))
    coarse = service.search_candidates(scope)
    from daesingo.search import ContractRef
    fine = service.verify_visual(ContractRef.model_validate(raw["visual_evidences"][0]["input_ref"]), scope.hint)
    return scope, coarse, fine


@pytest.mark.parametrize("kind,key", [("HINT_EXTRACT", "status"), ("COARSE_SEARCH", "candidate_events"),
                                      ("FINE_VERIFY", "visual_evidence")])
def test_public_payload_and_actual_run_reference(kind, key):
    ctx = context(kind, object())
    registry, seen, provider = dependencies(ctx)
    result = registry.dispatch(ctx)
    assert result.status == "SUCCEEDED" and len(result.objects) == 1
    payload = result.objects[0].payload
    assert key in payload
    if kind == "HINT_EXTRACT":
        assert payload["vehicle_hint"] == "흰 차" and "usage" not in payload and "reasoning" not in payload
        assert result.produced == () and provider.calls == 1 and ctx.usage_sink in seen
    else:
        run = payload["analysis_run"]
        assert [(r.kind, r.ref) for r in result.produced] == [("analysis_run", run["run_id"])]
        terminal = validated_terminal(result, execution_id=ctx.execution_id)
        assert len(terminal.produced) == 1  # the stored envelope is also the actual Run receipt
        assert result.objects[0].kind == "analysis_run" and result.objects[0].ref == run["run_id"]
        assert seen[-1] == "close" and seen.count("fine" if kind == "FINE_VERIFY" else "coarse") == 1


@pytest.mark.parametrize("kind", ["HINT_EXTRACT", "COARSE_SEARCH", "FINE_VERIFY"])
def test_missing_sink_never_invokes_capability(kind):
    ctx = context(kind)
    registry, seen, provider = dependencies(ctx)
    assert registry.dispatch(ctx).status == "FAILED"
    assert not seen and provider.calls == 0


@pytest.mark.parametrize("kind,at", [("HINT_EXTRACT", "load"), ("COARSE_SEARCH", "load"),
    ("COARSE_SEARCH", "open"), ("FINE_VERIFY", "resolve")])
def test_cooperative_checkpoint_prevents_next_public_call_and_closes(kind, at):
    ctx = context(kind, object())
    registry, seen, provider = dependencies(ctx, cancel_at=at)
    with pytest.raises(CancellationRequested):
        registry.dispatch(ctx)
    assert provider.calls == 0 and "coarse" not in seen and "fine" not in seen
    if "open" in seen: assert seen[-1] == "close"


def test_usage_error_is_not_wrapped_retried_or_finalized_by_handler():
    error = UsagePersistenceError()
    def fail(binding):
        raise error
    provider = IntentProvider(fail)
    ctx = context(sink=object())
    registry, _, _ = dependencies(ctx, provider=provider)
    with pytest.raises(UsagePersistenceError) as caught:
        registry.dispatch(ctx)
    assert caught.value is error and provider.calls == 1


def test_registry_inventory_and_no_media_fallback():
    from daesingo.case.jobs import JOB_KINDS
    m = module()
    registry = m.search_registry(load=lambda ctx: None, intent_factory=lambda: None,
                                 failures=SuccessfulSearchPolicy())
    assert m.SEARCH_KINDS <= JOB_KINDS
    for kind in JOB_KINDS - {"HINT_EXTRACT"}:
        assert registry.dispatch(context(kind, object())).failure_kind == "RUNTIME_UNREGISTERED_KIND"
