"""Real Search usage identities cross both supported guards before fake HTTP.

Reuse Search's media/provider doubles. Only Usage persistence is recorded in
memory; no DB, ffmpeg, provider network, or operational approval is involved.
"""
from dataclasses import replace
from types import SimpleNamespace

from pydantic import SecretStr
import pytest

from a1_support import policy_values, supported_policy_values
from daesingo.common.public_runtime.policy import PublicDenied, PublicPolicy
from daesingo.common.usage.sink import DurableUsageSink
from daesingo.search.execution import RunDeadline
from daesingo.search.fine import verify_fine
from daesingo.search.ledger import SearchLedger
from daesingo.search.provider import GeminiProvider
from daesingo.search.runs import ContractRef, RunOutcome
from daesingo.search.schemas import CoarseResponse
from daesingo.search.scope import SearchHint, VisualEventType
from daesingo.search.sources import ResolvedAnalysisSource
from daesingo.worker.bootstrap import SearchSettings, require_supported_elice
from tests.search.test_fine_media_flow import _candidate, _Preparer, _Resolver, _response
from tests.search.test_usage_sink import (
    _coarse_service, _Completions, _media, _provider, _RecordingSink,
)


@pytest.fixture(params=[
    ("coarse", "SEARCH_COARSE", "CANDIDATE_SEARCH"),
    ("fine", "SEARCH_FINE", "VISUAL_VERIFY"),
], ids=["coarse", "fine"])
def supported_search(request, monkeypatch, tmp_path):
    stage, approved_operation, actual_operation = request.param

    def configure(denial=None):
        completions = _Completions([
            CoarseResponse(candidates=()) if stage == "coarse" else _response(),
        ])
        original = _provider(monkeypatch, completions)
        approved_label = "elice:" + original._config.model
        config = replace(original._config,
            model="unapproved-model" if denial == "model" else original._config.model,
            base_url="https://generativelanguage.googleapis.com/v1" if denial == "endpoint" else original._config.base_url)
        provider = GeminiProvider("test-only", config)
        policy_operation = (
            "SEARCH_FINE" if stage == "coarse" else "SEARCH_COARSE"
        ) if denial == "scope" else approved_operation
        policy = PublicPolicy.model_validate(supported_policy_values(tmp_path,
            supported_calls=[{"operation": policy_operation, "provider_label": approved_label}]))
        modules = {"search": SearchSettings(SecretStr("test-only"), config)}
        events, rows, observations = [], [], []

        def before_begin(conn, snapshot):
            untouched = dict(snapshot)
            assert snapshot["operation"] == actual_operation
            events.append("policy")
            policy.require_supported(snapshot["operation"], snapshot["provider_label"])
            events.append("endpoint")
            require_supported_elice(modules, snapshot)
            assert snapshot == untouched

        def started(conn, snapshot):
            events.append("STARTED")
            rows.append(dict(snapshot))

        def observed(conn, identity, execution, case, snapshot, stamp):
            assert identity == rows[0]["usage_id"]
            events.append("OBSERVED")
            observations.append(dict(snapshot))
            return False

        monkeypatch.setattr("daesingo.common.usage.sink._begin", started)
        monkeypatch.setattr("daesingo.common.usage.sink._finish", observed)
        sink = _RecordingSink(runtime=DurableUsageSink(execution_ref="exec-supported",
            case_id="case-supported", transaction=lambda callback: callback(None),
            before_begin=before_begin))
        parse = completions.parse

        def http(**kwargs):
            assert rows and rows[0]["operation"] == actual_operation
            events.append("HTTP")
            return parse(**kwargs)

        monkeypatch.setattr(completions, "parse", http)
        if stage == "coarse":
            search = _coarse_service(monkeypatch, tmp_path, provider)

            def invoke():
                return search(sink)
        else:
            ref = ContractRef(kind="analysis_source", ref="source-fine")
            resolver = _Resolver(ResolvedAnalysisSource(ref, 10.0, "timeline-fine", 2))
            prepared = replace(_media(tmp_path), duration_sec=7.0,
                               origin_start_sec=0.5, origin_end_sec=7.5)
            preparer = _Preparer(prepared)

            def invoke():
                return verify_fine(ref, _candidate(), SearchHint(vehicle=None, free_text=None),
                    VisualEventType.SIGNAL, resolver, provider, config, SearchLedger(), preparer,
                    RunDeadline(lambda: 0.0, budget_ms=30_000), usage_sink=sink).analysis_run

        return SimpleNamespace(invoke=invoke, policy=policy, sink=sink, completions=completions,
            events=events, rows=rows, observations=observations, approved_label=approved_label,
            approved_operation=approved_operation, actual_operation=actual_operation)

    return configure


def test_supported_search_keeps_actual_usage_identity_and_policy(supported_search):
    call = supported_search()
    original = call.policy.model_dump(mode="json")
    fingerprint = call.policy.fingerprint()
    session_key = call.policy.session_key.get_secret_value()

    run = call.invoke()

    assert run.outcome is RunOutcome.SUCCEEDED
    assert call.events == ["policy", "endpoint", "STARTED", "HTTP", "OBSERVED"]
    assert call.completions.calls == 1
    assert len(call.rows) == len(call.observations) == 1
    row = call.rows[0]
    assert row["operation"] == call.actual_operation
    assert row["provider_label"] == call.approved_label
    assert run.usage_refs == (row["usage_id"],)
    assert call.sink.begins[0]["operation"] == call.actual_operation
    assert call.sink.finishes[0]["cost"] == {"amount": None, "currency": "KRW"}
    assert call.observations[0]["amount"] is None
    assert call.policy.model_dump(mode="json") == original
    assert call.policy.fingerprint() == fingerprint
    assert call.policy.session_key.get_secret_value() == session_key
    assert call.policy.supported_calls[0].operation == call.approved_operation
    assert call.policy.bounds == ()
    assert (call.policy.case_budget_micros, call.policy.daily_budget_micros,
            call.policy.total_budget_micros) == (None, None, None)


@pytest.mark.parametrize("denial", ["scope", "model", "endpoint"])
def test_unsupported_search_never_starts_usage_or_http(supported_search, denial):
    call = supported_search(denial)

    with pytest.raises(PublicDenied) as error:
        call.invoke()

    assert error.value.code == "UNSUPPORTED"
    assert call.completions.calls == 0
    assert call.rows == call.observations == []
    assert call.sink.begins == call.sink.finishes == []
    assert call.events == (["policy", "endpoint"] if denial == "endpoint" else ["policy"])


def test_supported_aliases_do_not_reinterpret_krw_bounds(tmp_path):
    policy = PublicPolicy.model_validate(policy_values(tmp_path))
    original, fingerprint = policy.model_dump(mode="json"), policy.fingerprint()
    assert policy.bound("SEARCH_COARSE", "fake:test") == 10
    with pytest.raises(PublicDenied) as error:
        policy.bound("CANDIDATE_SEARCH", "fake:test")
    assert error.value.code == "UNPRICED"
    assert policy.model_dump(mode="json") == original
    assert policy.fingerprint() == fingerprint
