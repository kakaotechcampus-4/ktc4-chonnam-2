from datetime import datetime, timezone

import pytest

from daesingo.common.public_runtime.policy import PublicDenied
from daesingo.common.usage.sink import DurableUsageSink


def test_paid_boundary_checks_gate_in_same_callback_before_started_and_http(monkeypatch):
    seen = []
    def gate(conn, row):
        seen.append(("reserve", conn, row["usage_id"]))
    monkeypatch.setattr("daesingo.common.usage.sink._begin", lambda conn, row:
                        seen.append(("STARTED", conn, row["usage_id"])))
    sink = DurableUsageSink(execution_ref="exec", case_id="case", before_begin=gate,
        transaction=lambda callback: callback("same-connection"),
        clock=lambda: datetime(2026, 11, 8, tzinfo=timezone.utc))
    usage = sink.begin("SEARCH_COARSE", "fake:test", {"pricing_id": "fake", "unit": "fixed"})
    seen.append(("HTTP", None, usage))
    assert [x[0] for x in seen] == ["reserve", "STARTED", "HTTP"]
    assert seen[0][1] == seen[1][1] and seen[0][2] == seen[1][2] == usage


def test_gate_rejection_prevents_started_and_provider_even_after_retry(monkeypatch):
    seen = []
    monkeypatch.setattr("daesingo.common.usage.sink._begin", lambda *a: seen.append("STARTED"))
    def gate(conn, row):
        raise PublicDenied("BUDGET")
    sink = DurableUsageSink(execution_ref="exec", case_id="case", before_begin=gate,
                            transaction=lambda callback: callback(None))
    for _ in range(2):
        with pytest.raises(PublicDenied):
            sink.begin("SEARCH_COARSE", "fake:test", {"pricing_id": "fake", "unit": "fixed"})
            seen.append("HTTP")
    assert seen == []


def test_begin_cancellation_remains_worker_control_flow_not_persistence_failure(monkeypatch):
    from daesingo.common.jobs.cancel import CancellationRequested
    def cancelled(conn, row):
        raise CancellationRequested()
    monkeypatch.setattr("daesingo.common.usage.sink._begin", lambda *args: pytest.fail("no STARTED after cancel"))
    sink = DurableUsageSink(execution_ref="exec", case_id="case", before_begin=cancelled,
                            transaction=lambda cb: cb(None))
    with pytest.raises(CancellationRequested):
        sink.begin("SEARCH_COARSE", "fake:test", {"pricing_id": "fake", "unit": "fixed"})


def test_cancel_after_http_does_not_prevent_actual_observation_persistence(monkeypatch):
    calls, stopped = [], [False]
    def begin_transaction(callback):
        if stopped[0]:
            raise PublicDenied("STOPPED")
        return callback(None)
    monkeypatch.setattr("daesingo.common.usage.sink._begin", lambda *a: calls.append("STARTED"))
    monkeypatch.setattr("daesingo.common.usage.sink._finish", lambda *a: calls.append("OBSERVED"))
    sink = DurableUsageSink(execution_ref="exec", case_id="case", transaction=lambda cb: cb(None),
                            begin_transaction=begin_transaction)
    identity = sink.begin("SEARCH_COARSE", "fake:test", {"pricing_id": "fake", "unit": "fixed"})
    stopped[0] = True
    sink.finish(identity, token_usage=None, processed_duration_sec=None, latency_ms=10,
        pricing_context={"pricing_id": "fake", "unit": "fixed"}, cost={"amount": "0.1", "currency": "KRW"},
        outcome="SUCCEEDED")
    with pytest.raises(PublicDenied):
        sink.begin("SEARCH_COARSE", "fake:test", {"pricing_id": "fake", "unit": "fixed"})
    assert calls == ["STARTED", "OBSERVED"]
