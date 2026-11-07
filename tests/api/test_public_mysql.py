"""Mandatory InnoDB/API/Worker paths; synthetic samples and costs, no provider.

SQLite fixtures are not evidence for these current-read and caller-transaction
boundaries. Collected by the existing canonical MySQL job and strict inventory.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
from threading import Barrier, Event
from types import MappingProxyType
from io import StringIO

from fastapi.testclient import TestClient
import pytest
import sqlalchemy as sa

from a1_support import policy_values
from daesingo.api.app import create_app
from daesingo.common.bootstrap import Startup
from daesingo.common.config import DbSettings, RuntimeConfig
from daesingo.common.db import create_api_engine
from daesingo.common.db.migrate import upgrade_all
from daesingo.common.jobs.execution import ExecutionContext, HandlerResult
from daesingo.common.jobs.repository import enqueue, claim_one
from daesingo.common.jobs.schema import job_execution
from daesingo.common.logging import configure_logging
from daesingo.common.public_runtime import schema as t
from daesingo.common.public_runtime.policy import PublicPolicy, PublicDenied
from daesingo.common.public_runtime.repository import PublicStore
from daesingo.worker.composition import compose_worker
from daesingo.worker.registry import KindRegistry
from tests.api.conftest import api_startup

pytestmark = pytest.mark.mysql


@pytest.fixture
def public_db(mysql_schema_url, tmp_path):
    upgrade_all(mysql_schema_url)
    engine = create_api_engine(DbSettings(url=mysql_schema_url.render_as_string(hide_password=False)))
    store = PublicStore(PublicPolicy.model_validate(policy_values(tmp_path)), require_public=True, worker_id="worker")
    with engine.begin() as conn:
        assert conn.execute(sa.select(t.control.c.accepting)).scalar_one() is False
        assert conn.exec_driver_sql("SELECT version_num FROM runtime_alembic_version").scalar_one() == "runtime_0007"
    yield engine, store
    engine.dispose()


def bind(engine, store, names=("case_1", "case_2")):
    owner = store.fingerprint("test-session")
    with engine.begin() as conn:
        store.set_open(conn, True)
        store.create_session(conn, owner, store.fingerprint("test-ip"))
        for case_id in names:
            store.claim_case(conn, case_id, owner)
            store.bind_sample(conn, case_id, "synthetic", [{"source_asset_ref": "sa_" + case_id,
                "sha256": "a" * 64, "byte_size": 10, "duration_ms": 1000}])
    return owner


@pytest.mark.mysql_check("public_a1", "admission")
def test_concurrent_connections_share_admission_and_queue_transaction(public_db):
    engine, prior = public_db
    policy = prior.policy.model_copy(update={"global_concurrent": 1})
    store = PublicStore(policy, require_public=True)
    bind(engine, store)
    barrier = Barrier(2)
    def request(case_id):
        barrier.wait(timeout=5)
        try:
            with engine.begin() as conn:
                store.admit(conn, case_id, hashlib.sha256(case_id.encode()).digest(), initial=True)
                enqueue(conn, [{"job_id": "job_" + case_id, "case_id": case_id, "kind": "TEST"}], "trace")
            return "ACCEPTED"
        except PublicDenied as error:
            return error.code
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(request, ("case_1", "case_2")))
    assert sorted(results) == ["ACCEPTED", "CONCURRENT"]
    with engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(job_execution)).scalar_one() == 1
        assert conn.execute(sa.select(sa.func.count()).select_from(t.admissions)).scalar_one() == 1


@pytest.mark.mysql_check("public_a1", "admission")
def test_concurrent_repeat_requests_do_not_exceed_case_quota(public_db):
    engine, prior = public_db
    store = PublicStore(prior.policy.model_copy(update={"case_repeats": 1,
        "global_concurrent": 4, "session_concurrent": 4}), require_public=True)
    bind(engine, store, names=("case_1",))
    barrier = Barrier(2)
    def request(index):
        barrier.wait(timeout=5)
        try:
            with engine.begin() as conn:
                store.admit(conn, "case_1", hashlib.sha256(str(index).encode()).digest(), initial=False)
                enqueue(conn, [{"job_id": "repeat_" + str(index), "case_id": "case_1", "kind": "TEST"}], "trace")
            return "ACCEPTED"
        except PublicDenied as error:
            return error.code
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(request, (1, 2))) == ["ACCEPTED", "LIMIT"]
    with engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(t.admissions)).scalar_one() == 1
        assert conn.execute(sa.select(sa.func.count()).select_from(job_execution)).scalar_one() == 1


@pytest.mark.mysql_check("public_a1", "admission")
def test_terminal_recovery_does_not_recycle_an_unobserved_http_slot(public_db, tmp_path):
    from daesingo.common.db.transactions import run_worker_transaction
    from daesingo.common.jobs.repository import finish
    from daesingo.common.usage.sink import DurableUsageSink
    from daesingo.common.usage.reconciliation import reconcile_once
    from daesingo.common.usage.schema import usage_inflight
    engine, store = public_db
    bind(engine, store)
    with engine.begin() as conn:
        store.admit(conn, "case_1", b"a" * 32, initial=True)
        enqueue(conn, [{"job_id": "uncertain", "case_id": "case_1", "kind": "TEST"}], "trace")
    claim = claim_one(engine, "worker", lease_duration_sec=60)
    sink = DurableUsageSink(execution_ref=claim.execution_id, case_id="case_1", before_begin=store.reserve,
        transaction=lambda cb: run_worker_transaction(engine, cb, sleep=lambda _: None))
    identity = sink.begin("SEARCH_COARSE", "fake:test", {"pricing_id": "TEST_ONLY", "unit": "fixed"},
                          run_ref=None, run_ref_reason="DIRECT_NO_RUN")
    with engine.begin() as conn:
        assert finish(conn, claim.execution_id, "worker", status="FAILED", failure_kind="TEST_CRASH") == 1
        conn.execute(job_execution.update().where(job_execution.c.execution_id == claim.execution_id)
                     .values(case_applied_at=sa.func.now(6)))
    reconcile_once(engine, execution_ref=claim.execution_id, recovery=True, sleep=lambda _: None)
    with engine.begin() as conn:
        row = conn.execute(sa.select(usage_inflight).where(usage_inflight.c.usage_id == identity)).mappings().one()
        assert row["state"] == "FINALIZED" and row["observed_at"] is None
        store.begin_delete(conn, "case_1")
    from daesingo.api.public_retention import PublicRetention
    root, temp = tmp_path / "retained-media", tmp_path / "retained-temp"
    root.mkdir(); temp.mkdir()
    retention = PublicRetention(engine=engine, store=store, media_root=root, temp_root=temp)
    assert retention.purge("case_1") == {"state": "DELETING", "reason": "BUSY"}
    with engine.begin() as conn:
        with pytest.raises(PublicDenied) as error:
            store.admit(conn, "case_2", b"b" * 32, initial=True)
        assert error.value.code == "CONCURRENT"


@pytest.mark.mysql_check("public_a1", "budget_worker")
def test_real_worker_default_gate_reserves_before_each_fake_http_and_keeps_observation(public_db, tmp_path):
    engine, prior = public_db
    values = policy_values(tmp_path, global_concurrent=2, session_concurrent=2, total_budget_micros=10)
    store = PublicStore(PublicPolicy.model_validate(values), require_public=True, worker_id="worker")
    bind(engine, store)
    with engine.begin() as conn:
        for case_id in ("case_1", "case_2"):
            store.admit(conn, case_id, hashlib.sha256(case_id.encode()).digest(), initial=True)
            enqueue(conn, [{"job_id": "job_" + case_id, "case_id": case_id, "kind": "TEST"}], "trace")
    claimed = [claim_one(engine, f"worker-{i}", lease_duration_sec=60) for i in range(2)]
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(values), encoding="utf-8"); path.chmod(0o600)
    media, temp = tmp_path / "shared-media", tmp_path / "worker-temp"
    media.mkdir(); temp.mkdir()
    config = RuntimeConfig.from_mapping("worker", {"DAESINGO_RUNTIME_DB_URL": engine.url.render_as_string(hide_password=False),
        "DAESINGO_RUNTIME_MEDIA_ROOT": str(media), "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(temp),
        "DAESINGO_RUNTIME_PUBLIC_POLICY_FILE": str(path)})  # default a1, actual Worker composition
    calls, barrier = [], Barrier(2)
    def handler(context):
        from daesingo.common.public_runtime.temporary import temporary_root
        assert temporary_root.get().parent == media / "public-temp"
        barrier.wait(timeout=5)
        pricing = {"pricing_id": "TEST_ONLY", "unit": "fixed"}
        usage = context.usage_sink.begin("SEARCH_COARSE", "fake:test", pricing)
        calls.append(usage)  # Represents HTTP only after the acknowledged STARTED+reserve.
        context.usage_sink.finish(usage, token_usage=None, processed_duration_sec=None, latency_ms=1,
            pricing_context=pricing, cost={"currency": "KRW", "amount": "0.00001"}, outcome="SUCCEEDED")
        return HandlerResult()
    output = StringIO()
    workers = []
    logger = configure_logging("worker", stream=output)
    for i in range(2):
        slot = temp / str(i)
        slot.mkdir()
        # Two actual Worker instances share DB/public media. Their private tool
        # roots differ: Windows CRT read locks serialize the same temp root.
        workers.append(compose_worker(engine=engine, startup=Startup(replace(config, temp_root=slot),
            MappingProxyType({}), logger, "1" * 40), registry=KindRegistry({"TEST": handler}),
            stop=Event(), worker_id=f"worker-{i}"))
    def run(item):
        i, claim = item
        worker = workers[i]
        context = ExecutionContext(claim.execution_id, claim.job_id, claim.case_id, claim.kind, claim.attempt, claim.trace_id)
        context = replace(context, usage_sink=worker.usage_sink_factory(context))
        try:
            terminal = worker.dispatch(context)
            assert terminal.status == "SUCCEEDED", terminal.failure_kind
            return "ACCEPTED"
        except PublicDenied as error:
            return error.code
    with ThreadPoolExecutor(2) as pool:
        try:
            results = list(pool.map(run, enumerate(claimed)))
        except AssertionError:
            print("SANITIZED_WORKER_ERRORS", [(json.loads(line).get("event"), json.loads(line).get("error_type"))
                                              for line in output.getvalue().splitlines()])
            raise
    assert sorted(results) == ["ACCEPTED", "BUDGET"] and len(calls) == 1
    with engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.sum(t.reservations.c.amount_micros))).scalar_one() == 10
        store.set_open(conn, False)
    # Emergency stop blocks further paid attempts even for an existing claim.
    context = claimed[0]
    snapshot = dict(usage_id="late", execution_ref=context.execution_id, case_id=context.case_id,
                    operation="SEARCH_COARSE", provider_label="fake:test")
    with engine.begin() as conn, pytest.raises(PublicDenied) as stopped:
        store.reserve(conn, snapshot)
    assert stopped.value.code == "STOPPED"
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM usage_inflight WHERE state='OBSERVED'").scalar_one() == 1


@pytest.fixture
def public_api(public_db, api_startup, tmp_path, monkeypatch, request):
    engine, _ = public_db
    root = tmp_path / "official"
    root.mkdir(); (root / "part.mp4").write_bytes(b"synthetic!")
    manifest = {"schema": "official-samples/v1", "samples": [{"sample_id": "fixture", "label": "Fixture",
        "example_hint": "Test", "authorization_ref": "TEST_ONLY",
        "files": [{"name": "part.mp4", "byte_size": 10, "sha256": hashlib.sha256(b"synthetic!").hexdigest(), "duration_ms": 1000}]}]}
    raw = json.dumps(manifest).encode()
    (tmp_path / "manifest.json").write_bytes(raw)
    values = policy_values(tmp_path, manifest_sha256=hashlib.sha256(raw).hexdigest(), **getattr(request, "param", {}))
    path = tmp_path / "private-policy.json"
    path.write_text(json.dumps(values), encoding="utf-8"); path.chmod(0o600)
    startup, _ = api_startup
    startup = replace(startup, revision="1" * 40, config=replace(startup.config,
        db=DbSettings(url=engine.url.render_as_string(hide_password=False)),
        public=startup.config.public.model_copy(update={"mode": "a1", "policy_file": path})))
    from daesingo.recording.probe import LocalSource, ProbedStream
    def probe(self, source):
        return LocalSource(source, 10, source.stat().st_mtime_ns, hashlib.sha256(b"synthetic!").hexdigest(),
            1.0, (ProbedStream(0, "VIDEO", 1.0),))
    monkeypatch.setattr("daesingo.recording.probe.FfprobeMediaProbe.probe", probe)
    app = create_app(startup=startup)  # Real default Case and Recording repositories; no port replacements.
    with engine.begin() as conn:
        app.state.composition.public.store.set_open(conn, True)
    with TestClient(app, base_url="https://testserver") as client:
        assert client.post("/public/session", headers={"Origin": "https://testserver"}).status_code == 201
        yield client, app.state.composition, engine, root


def register(client):
    headers = {"Origin": "https://testserver"}
    response = client.post("/cases", headers=headers)
    assert response.status_code == 201
    case_id = response.json()["case_id"]
    registered = client.post(f"/cases/{case_id}/official-samples", json={"sample_id": "fixture"}, headers=headers)
    assert registered.status_code == 201
    return case_id, registered.json()["case_view"]["case_rev"]


@pytest.mark.mysql_check("public_a1", "api_atomicity")
def test_default_api_same_transaction_rolls_back_admission_case_and_queue(public_api, monkeypatch):
    client, composition, engine, _ = public_api
    cid, revision = register(client)
    def failed_enqueue(conn, records, trace):
        enqueue(conn, records, trace)
        raise RuntimeError("synthetic failure after queue insert")
    monkeypatch.setattr("daesingo.api.composition.enqueue", failed_enqueue)
    result = client.post(f"/cases/{cid}/commands", headers={"Origin": "https://testserver"},
        json={"case_id": cid, "expected_case_rev": revision, "kind": "START_ANALYSIS", "payload": {"description": "Test"}})
    assert result.status_code == 500
    with engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(t.admissions)).scalar_one() == 0
        assert conn.execute(sa.select(sa.func.count()).select_from(job_execution)).scalar_one() == 0
    assert client.get(f"/cases/{cid}/view").json()["case_rev"] == revision


@pytest.mark.mysql_check("public_a1", "deletion")
def test_default_delete_removes_source_chunks_case_and_keeps_official_and_budget_ledger(public_api):
    from daesingo.recording.mysql_repository import entries, chunks, _key
    client, composition, engine, canonical = public_api
    cid, _ = register(client)
    with engine.begin() as conn:
        binding = conn.execute(sa.select(t.cases).where(t.cases.c.case_id == cid)).mappings().one()
        source = binding["sources"][0]["source_asset_ref"]
        conn.execute(entries.insert().values(kind="time_observation", entry_key=_key(source), payload={"candidates": [], "checks": []}))
        conn.execute(entries.insert().values(kind="analysis_source", entry_key=_key("as_fixture"),
            payload={"analysis_source_ref": "as_fixture", "source_refs": [{"kind": "source_asset", "ref": source}]}))
        conn.execute(entries.insert().values(kind="prepared_content", entry_key=_key(["analysis_source", "as_fixture"]), payload={"version": 1, "chunk_count": 1}))
        conn.execute(chunks.insert().values(kind="analysis_source", entry_key=_key("as_fixture"), chunk_index=0, content=b"DISPOSABLE"))
        from daesingo.common.public_runtime.repository import now
        conn.execute(t.reservations.insert().values(usage_id="historic-cost", execution_ref="past", case_id=cid,
            operation="SEARCH_COARSE", provider_label="fake:test", amount_micros=10, created_at=now(conn)))
    result = client.delete(f"/cases/{cid}", headers={"Origin": "https://testserver"})
    assert result.status_code == 200 and result.json()["state"] == "DELETED"
    assert client.get(f"/cases/{cid}/view").status_code == 404
    assert not list((composition.startup.config.media_root / "source").glob("*"))
    assert (canonical / "part.mp4").read_bytes() == b"synthetic!"
    with engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(entries)).scalar_one() == 0
        assert conn.execute(sa.select(sa.func.count()).select_from(chunks)).scalar_one() == 0
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM cases").scalar_one() == 0
        assert conn.execute(sa.select(sa.func.count()).select_from(t.reservations)).scalar_one() == 1
