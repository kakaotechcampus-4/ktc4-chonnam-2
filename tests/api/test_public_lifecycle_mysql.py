"""Actual A-1 API/Worker lifecycle on disposable MySQL; explicit fake spend."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from io import StringIO
import json
from threading import Barrier, Event
from types import MappingProxyType

from fastapi.testclient import TestClient
import pytest
import sqlalchemy as sa

from a1_support import policy_values
from daesingo.common.bootstrap import Startup
from daesingo.common.config import RuntimeConfig
from daesingo.common.jobs.cancel import request_cancel
from daesingo.common.jobs.execution import HandlerResult
from daesingo.common.jobs.repository import enqueue
from daesingo.common.jobs.schema import job_execution
from daesingo.common.logging import configure_logging
from daesingo.common.public_runtime import schema as t
from daesingo.common.public_runtime.policy import PublicPolicy
from daesingo.common.public_runtime.repository import PublicStore
from daesingo.common.usage.schema import usage_record
from daesingo.worker.composition import compose_worker
from daesingo.worker.registry import KindRegistry
from test_public_mysql import public_db, public_api, bind, register  # noqa: F401

pytestmark = pytest.mark.mysql
ORIGIN = {"Origin": "https://testserver"}
PRICING = {"pricing_id": "TEST_ONLY", "unit": "fixed"}


@pytest.mark.mysql_check("public_a1", "deletion")
def test_operator_can_retry_completed_cleanup_and_public_owner_cannot_delete(public_api):
    client, composition, engine, canonical = public_api
    cid, _ = register(client)
    path = f"/cases/{cid}"
    assert client.delete(path, headers=ORIGIN).status_code == 404
    assert client.get(path + "/view").status_code == 200
    public = composition.public
    public.transaction(lambda conn: public.store.begin_delete(conn, cid))
    for _ in range(2):
        assert public.retention.purge(cid)["state"] == "DELETED"
    assert client.get(path + "/view").status_code == 404
    client.cookies.clear()
    assert client.post("/public/session", headers=ORIGIN).status_code == 201
    assert client.delete(path, headers=ORIGIN).status_code == 404
    assert (canonical / "part.mp4").read_bytes() == b"synthetic!"
    with engine.connect() as conn:
        assert conn.execute(sa.select(t.cases.c.state).where(t.cases.c.case_id == cid)).scalar_one() == "DELETED"


def worker(engine, tmp_path, values, handler, *, identity, modules=None):
    path = tmp_path / (identity + ".policy.json")
    path.write_text(json.dumps(values), encoding="utf-8")
    path.chmod(0o600)
    media, temp = tmp_path / "worker-media", tmp_path / identity
    media.mkdir(exist_ok=True)
    temp.mkdir()
    config = RuntimeConfig.from_mapping("worker", {
        "DAESINGO_RUNTIME_DB_URL": engine.url.render_as_string(hide_password=False),
        "DAESINGO_RUNTIME_MEDIA_ROOT": str(media), "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(temp),
        "DAESINGO_RUNTIME_PUBLIC_POLICY_FILE": str(path)})
    stop = Event()
    loop = compose_worker(engine=engine, startup=Startup(config, MappingProxyType(modules or {}),
        configure_logging("worker", stream=StringIO()), "1" * 40), stop=stop,
        worker_id=identity, registry=KindRegistry({"TEST": handler}))
    actual_claim = loop.claim
    def claim():
        value = actual_claim()
        if value is None:
            stop.set()
        return value
    loop.claim = claim
    return loop


def queue(engine, store, case_id):
    with engine.begin() as conn:
        store.admit(conn, case_id, (case_id.encode() * 32)[:32], initial=True)
        return enqueue(conn, [{"job_id": "job_" + case_id, "case_id": case_id, "kind": "TEST"}], "trace")[0]


@pytest.mark.mysql_check("public_a1", "lifecycle")
@pytest.mark.parametrize("funding_mode,signal_known", [
    pytest.param("krw", False, id="krw-db-before-heartbeat"),
    pytest.param("krw", True, id="krw-signal-already-known"),
    pytest.param("elice_supported", False, id="elice_supported-db-before-heartbeat",
        marks=pytest.mark.mysql_check("public_a1", "supported_funding", parameter="cancel_db")),
    pytest.param("elice_supported", True, id="elice_supported-signal-already-known",
        marks=pytest.mark.mysql_check("public_a1", "supported_funding", parameter="cancel_signal")),
])
def test_cancel_at_paid_boundary_is_cancelled_without_reservation_or_http(public_db, tmp_path, signal_known, funding_mode):
    engine, store = public_db
    values = policy_values(tmp_path)
    if funding_mode == "elice_supported":
        from a1_support import supported_policy_values
        values = supported_policy_values(tmp_path)
        store = PublicStore(PublicPolicy.model_validate(values), require_public=True)
    bind(engine, store)
    execution = queue(engine, store, "case_1")
    calls = []
    def handler(context):
        with engine.begin() as conn:
            request_cancel(conn, [context.job_id])
        if signal_known:
            context.cancel_signal.request()
        context.usage_sink.begin("SEARCH_COARSE", "fake:test", PRICING,
                                 run_ref=None, run_ref_reason="DIRECT_NO_RUN")
        calls.append("HTTP")
        return HandlerResult()
    worker(engine, tmp_path, values, handler, identity="cancel-worker").run()
    with engine.connect() as conn:
        row = conn.execute(sa.select(job_execution).where(job_execution.c.execution_id == execution)).mappings().one()
        assert row["status"] == "CANCELLED", row["failure_kind"]
        assert conn.execute(sa.select(sa.func.count()).select_from(t.reservations)).scalar_one() == 0
    assert calls == []


@pytest.mark.mysql_check("public_a1", "supported_funding", parameter="restart")
def test_supported_failed_observation_and_usage_survive_cancellation_and_restart(public_db, tmp_path):
    from a1_support import supported_policy_values
    from pydantic import SecretStr
    from daesingo.search.config import GeminiSearchConfig
    from daesingo.worker.bootstrap import SearchSettings
    engine, _ = public_db
    values = supported_policy_values(tmp_path)
    store = PublicStore(PublicPolicy.model_validate(values), require_public=True)
    modules = {"search": SearchSettings(SecretStr("TEST_ONLY"), GeminiSearchConfig(model="test-model"))}
    bind(engine, store)
    first = queue(engine, store, "case_1")
    calls = []
    def called(context):
        identity = context.usage_sink.begin("SEARCH_COARSE", "elice:test-model", PRICING,
            run_ref=None, run_ref_reason="DIRECT_NO_RUN")
        calls.append(identity)
        with engine.begin() as conn:
            request_cancel(conn, [context.job_id])
        context.cancel_signal.request()
        context.usage_sink.finish(identity, token_usage={"input_tokens": 12, "output_tokens": 3, "total_tokens": 15},
            processed_duration_sec=None, latency_ms=1, pricing_context=PRICING,
            cost={"currency": "KRW", "amount": None}, outcome="FAILED", failure_kind="TEST_ONLY_RESPONSE")
        context.checkpoint()
        return HandlerResult()
    worker(engine, tmp_path, values, called, identity="supported-before", modules=modules).run()
    second = queue(engine, store, "case_2")
    def after_restart(context):
        identity = context.usage_sink.begin("SEARCH_COARSE", "elice:test-model", PRICING,
            run_ref=None, run_ref_reason="DIRECT_NO_RUN")
        calls.append(identity)
        context.usage_sink.finish(identity, token_usage=None, processed_duration_sec=None, latency_ms=1,
            pricing_context=PRICING, cost={"currency": "KRW", "amount": None}, outcome="SUCCEEDED")
        return HandlerResult()
    worker(engine, tmp_path, values, after_restart, identity="supported-after", modules=modules).run()
    with engine.connect() as conn:
        rows = {r.execution_id: r for r in conn.execute(sa.select(job_execution))}
        assert rows[first].status == "CANCELLED" and rows[second].status == "SUCCEEDED"
        assert conn.execute(sa.select(sa.func.count()).select_from(t.reservations)).scalar_one() == 0
        usage = conn.execute(sa.select(usage_record)).mappings().all()
        assert len(usage) == 2 and all(r["amount"] is None for r in usage)
        assert {r["input_tokens"] for r in usage} == {12, None}
        from daesingo.common.usage.schema import usage_inflight
        assert set(conn.execute(sa.select(usage_inflight.c.outcome)).scalars()) == {"FAILED", "SUCCEEDED"}
    assert len(set(calls)) == 2


@pytest.mark.mysql_check("public_a1", "lifecycle")
def test_observed_cancelled_call_keeps_cost_and_reservation_after_worker_restart(public_db, tmp_path):
    engine, _ = public_db
    values = policy_values(tmp_path, total_budget_micros=15)
    store = PublicStore(PublicPolicy.model_validate(values), require_public=True)
    bind(engine, store)
    first = queue(engine, store, "case_1")
    calls = []
    def called(context):
        identity = context.usage_sink.begin("SEARCH_COARSE", "fake:test", PRICING,
            run_ref=None, run_ref_reason="DIRECT_NO_RUN")
        calls.append(identity)
        with engine.begin() as conn:
            request_cancel(conn, [context.job_id])
        context.cancel_signal.request()
        # Actual observation survives a cancellation after the paid attempt.
        context.usage_sink.finish(identity, token_usage=None, processed_duration_sec=None, latency_ms=1,
            pricing_context=PRICING, cost={"currency": "KRW", "amount": "0.000003"}, outcome="FAILED",
            failure_kind="TEST_ONLY_RESPONSE")
        context.checkpoint()
        return HandlerResult()
    worker(engine, tmp_path, values, called, identity="worker-before-restart").run()
    second = queue(engine, store, "case_2")
    def after_restart(context):
        context.usage_sink.begin("SEARCH_COARSE", "fake:test", PRICING,
                                 run_ref=None, run_ref_reason="DIRECT_NO_RUN")
        calls.append("UNEXPECTED_HTTP")
        return HandlerResult()
    worker(engine, tmp_path, values, after_restart, identity="worker-after-restart").run()
    with engine.connect() as conn:
        rows = {r.execution_id: r for r in conn.execute(sa.select(job_execution))}
        assert rows[first].status == "CANCELLED"
        assert (rows[second].status, rows[second].failure_kind) == ("FAILED", "RUNTIME_USAGE_BUDGET")
        assert conn.execute(sa.select(sa.func.sum(t.reservations.c.amount_micros))).scalar_one() == 10
        assert conn.execute(sa.select(t.reservations.c.settled_at)).scalar_one() is not None
        actual = conn.execute(sa.select(usage_record.c.amount)).scalar_one()
        assert Decimal(str(actual)) == Decimal("0.000003")
    assert len(calls) == 1


@pytest.mark.mysql_check("public_a1", "admission")
@pytest.mark.parametrize("public_api", [{"session_daily": 1}], indirect=True, ids=["one-case"])
def test_concurrent_actual_case_creation_cannot_exceed_owner_quota(public_api):
    client, _, engine, _ = public_api
    barrier = Barrier(2)
    def create(_):
        barrier.wait(timeout=5)
        return client.post("/cases", headers=ORIGIN).status_code
    with ThreadPoolExecutor(2) as pool:
        statuses = list(pool.map(create, range(2)))
    assert sorted(statuses) == [201, 429]
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM cases").scalar_one() == 1
        assert conn.execute(sa.select(sa.func.count()).select_from(t.cases)).scalar_one() == 1


@pytest.mark.mysql_check("public_a1", "session_isolation")
def test_other_session_cannot_read_existing_case_media_range_or_download(public_api):
    from test_frames_mysql import seed as seed_frame
    from test_assets_mysql import seed as seed_asset, MP4
    from test_frames import PNG
    client, composition, engine, _ = public_api
    cid, _ = register(client)
    with engine.begin() as conn:
        frame = seed_frame(conn, composition.startup.config.media_root, cid)
        asset = seed_asset(conn, composition.startup.config.media_root, cid, ref="public-export-fixture")
    assert client.get(f"/cases/{cid}/frames/{frame}").content == PNG
    full = client.get(f"/cases/{cid}/assets/{asset}")
    assert full.status_code == 200 and full.content == MP4
    assert "attachment" in full.headers["content-disposition"]
    part = client.get(f"/cases/{cid}/assets/{asset}", headers={"Range": "bytes=0-7"})
    # Existing download Contract3.5 returns the complete attachment for Range;
    # it must still reject a foreign session before returning any bytes.
    assert part.status_code == 200 and part.content == MP4
    other = TestClient(client.app, base_url="https://testserver")
    try:
        assert other.post("/public/session", headers=ORIGIN).status_code == 201
        for path in ("view", f"frames/{frame}", f"assets/{asset}", "candidate-videos/existing-or-unknown"):
            result = other.get(f"/cases/{cid}/{path}", headers={"Range": "bytes=0-7"})
            assert result.status_code == 404
            assert result.json() == {"ok": False, "error": {"code": "http.not_found", "message_key": "http.not_found"}, "case_view": None}
            assert "content-range" not in result.headers and "content-disposition" not in result.headers
        assert other.delete(f"/cases/{cid}", headers=ORIGIN).status_code == 404
    finally:
        other.close()


@pytest.mark.mysql_check("public_a1", "deletion")
@pytest.mark.parametrize("fault", ["hash", "db-after-unlink"])
def test_actual_delete_retries_partial_failure_and_preserves_canonical(public_api, fault):
    client, composition, engine, canonical = public_api
    cid, _ = register(client)
    source = next((composition.startup.config.media_root / "source").iterdir())
    original = source.read_bytes()
    fired = []
    def failure(conn, cursor, sql, *args):
        if sql.lstrip().upper().startswith("DELETE FROM RECORDING_ENTRY") and not fired:
            fired.append(True)
            raise RuntimeError("TEST_ONLY after source unlink")
    if fault == "hash":
        source.write_bytes(b"CHANGED!!!")
    else:
        sa.event.listen(composition.engine, "before_cursor_execute", failure)
    public = composition.public
    public.transaction(lambda conn: public.store.begin_delete(conn, cid))
    try:
        assert public.retention.purge(cid)["state"] == "DELETING"
        assert source.exists() is (fault == "hash")
        with engine.connect() as conn:
            assert conn.execute(sa.select(t.cases.c.deletion_plan).where(t.cases.c.case_id == cid)).scalar_one() is not None
            assert conn.exec_driver_sql("SELECT COUNT(*) FROM cases WHERE case_id=%s", (cid,)).scalar_one() == 1
    finally:
        if fault != "hash":
            sa.event.remove(composition.engine, "before_cursor_execute", failure)
    if fault == "hash":
        source.write_bytes(original)
    assert public.retention.purge(cid)["state"] == "DELETED"
    assert not source.exists() and (canonical / "part.mp4").read_bytes() == b"synthetic!"
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM cases WHERE case_id=%s", (cid,)).scalar_one() == 0
