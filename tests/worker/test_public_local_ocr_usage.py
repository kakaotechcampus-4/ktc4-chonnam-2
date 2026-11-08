"""Production OCR composition meets the public usage boundary before inference.

SQLite supplies caller transactions, not MySQL locking evidence. Recording frame
access and Paddle's warmed inference engine are explicit doubles; the production
factory, Paddle provider, Readout APIs, usage sink and admission code are real.
No model download, ffmpeg, provider HTTP or operational approval is involved.
"""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from io import StringIO
import socket
from threading import Event
from types import MappingProxyType, SimpleNamespace

import cv2
import numpy as np
import pytest
import sqlalchemy as sa

from a1_support import sqlite_engine, supported_policy_values
from daesingo.common.bootstrap import Startup
from daesingo.common.config import RuntimeConfig
from daesingo.common.jobs.cancel import CancellationRequested
from daesingo.common.jobs.execution import ExecutionContext
from daesingo.common.jobs.schema import job_execution
from daesingo.common.logging import configure_logging
from daesingo.common.public_runtime import schema as public_tables
from daesingo.common.public_runtime.policy import PublicDenied, PublicPolicy
from daesingo.common.public_runtime.repository import PublicStore, now
from daesingo.common.usage import schema as usage_tables
from daesingo.common.usage.sink import DurableUsageSink
from daesingo.readout.paddle_provider import PaddleOcrProvider
from daesingo.worker.composition import compose_worker
from daesingo.worker.readout_composition import RecordingOcrFactory, production_readout_factory
from daesingo.worker.readout_handlers import ReadoutInput, readout_registry


KINDS = ("PLATE_READ", "OVERLAY_TIME_READ")
PRICING = {"pricing_id": "local-2026-09", "unit": "per_second"}
OPERATIONS = {"PLATE_READ": "READOUT_PLATE", "OVERLAY_TIME_READ": "READOUT_OVERLAY_TIME"}


def _production_ocr_factory(monkeypatch, *, engine, startup, case_id, clip_ref,
                            events, inferences, before_inference):
    """Keep actual production registration; double only frame I/O and inference.

    The MySQL lifecycle test can reuse this same narrow provider boundary while
    retaining its own actual Case input reader, claim, transactions and sink.
    """
    image = np.zeros((80, 200, 3), dtype=np.uint8)
    encoded, png = cv2.imencode(".png", image)
    assert encoded
    content = png.tobytes()

    class RecordingFrames:
        def __init__(self, repository, *, case_id):
            self.case_id = case_id

        def __enter__(self):
            assert self.case_id == case_id
            events.append("recording-open")
            return self

        def __exit__(self, *args):
            events.append("recording-close")

        def get_incident_clip(self, ref):
            assert ref == clip_ref
            return SimpleNamespace(incident_clip_ref=ref, duration_sec=10.0,
                timeline_range=SimpleNamespace(start_sec=0.0, end_sec=10.0),
                source_provenance=SimpleNamespace(asset_spans=[SimpleNamespace(
                    media_stream_ref="video-test",
                    timeline_range=SimpleNamespace(start_sec=0.0, end_sec=10.0),
                    source_range=SimpleNamespace(start_sec=0.0, end_sec=10.0))]))

        def resolve_frame(self, locator):
            assert locator["media_stream_ref"] == "video-test"
            return SimpleNamespace(frame_ref="frame-" + str(locator["source_offset_sec"]),
                source_offset_sec=locator["source_offset_sec"])

        def read_frame(self, ref):
            assert ref.startswith("frame-")
            return content

    class WarmedEngine:
        def predict(self, pixels):
            before_inference()
            assert pixels.shape == image.shape
            events.append("inference")
            index = len(inferences)
            inferences.append(True)
            return [SimpleNamespace(json={"res": {
                "rec_texts": ["12가3456", "2026-10-11 09:08:" + str(7 + index).zfill(2)],
                "rec_scores": [0.99, 0.99],
                "rec_boxes": [[5, 5, 105, 35], [0, 45, 180, 65]]}})]

    monkeypatch.setattr("daesingo.worker.readout_composition.RecordingService", RecordingFrames)
    monkeypatch.setattr("daesingo.worker.readout_composition.load_production_ocr_engine", WarmedEngine)
    factory = production_readout_factory(engine=engine, startup=startup)
    assert type(factory) is RecordingOcrFactory
    return factory


@pytest.fixture
def local_ocr(tmp_path, monkeypatch):
    """One claimed OCR job and its exact finite local admission receipt."""
    engine = sqlite_engine(tmp_path / "local-ocr.sqlite")

    @sa.event.listens_for(engine, "connect")
    def sqlite_collation(connection, record):
        connection.create_collation("ascii_bin", lambda a, b: (a > b) - (a < b))

    public_tables.metadata.create_all(engine)
    # MySQL's CAST(... AS BINARY) constraints have different SQLite semantics.
    # Keep all real columns/types and production SQL, without pretending these
    # portable fixtures prove the frozen MySQL DDL or current-read locking.
    portable = sa.MetaData()
    job_execution.to_metadata(portable)
    for table in (usage_tables.usage_inflight, usage_tables.usage_record):
        copied = table.to_metadata(portable)
        for constraint in list(copied.constraints):
            if isinstance(constraint, sa.CheckConstraint):
                copied.constraints.remove(constraint)
    portable.create_all(engine)
    values = supported_policy_values(tmp_path,
        supported_calls=[{"operation": operation, "provider_label": "elice:test-model"}
                         for operation in ("HINT_EXTRACT", "SEARCH_COARSE", "SEARCH_FINE")],
        local_work={"case_jobs": 4, "ip_daily_jobs": 8, "global_concurrent": 2})
    policy = PublicPolicy.model_validate(values)
    store = PublicStore(policy, require_public=True, worker_id="ocr-worker")
    owner = store.fingerprint("TEST_ONLY_SESSION")
    with engine.begin() as conn:
        conn.execute(public_tables.control.insert().values(id=1, accepting=False,
            jobs_stopped=True, policy_hash=None))
        store.set_open(conn, True)
        store.create_session(conn, owner, store.fingerprint("TEST_ONLY_IP"))
        store.claim_case(conn, "case-local-ocr", owner)
        store.bind_sample(conn, "case-local-ocr", "synthetic", [{
            "source_asset_ref": "source-test", "sha256": "a" * 64,
            "byte_size": 12, "duration_ms": 1000}])
        stamp = now(conn)
        # Retain two existing analysis-repeat receipts, including the active
        # parent case slot. Local inference must never rewrite/refund either.
        for index in range(2):
            conn.execute(public_tables.admissions.insert().values(case_id="case-local-ocr",
                request_hash=bytes([index + 1]) * 32, session_hash=owner,
                ip_hash=store.fingerprint("TEST_ONLY_IP"), created_at=stamp,
                initial=False, active=index == 1))

    media, temp = tmp_path / "media", tmp_path / "worker-temp"
    media.mkdir()
    temp.mkdir()
    config = RuntimeConfig.from_mapping("worker", {
        "DAESINGO_RUNTIME_DB_URL": "mysql+pymysql://test:test@localhost/test",
        "DAESINGO_RUNTIME_MEDIA_ROOT": str(media),
        "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(temp)})
    startup = Startup(config, MappingProxyType({}),
        configure_logging("worker", stream=StringIO()), "1" * 40)
    monkeypatch.setattr("daesingo.worker.composition.load_policy", lambda *a, **k: policy)
    network = []

    def forbidden_network(*args, **kwargs):
        network.append(True)
        raise AssertionError("TEST_ONLY_NETWORK_FORBIDDEN")

    monkeypatch.setattr(socket.socket, "connect", forbidden_network)
    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    events, snapshots, sql_connections, inferences = [], [], [], []

    def before_inference():
        # begin must already have committed before the first local compute.
        with engine.connect() as conn:
            observed = conn.execute(sa.select(usage_tables.usage_inflight)).mappings().all()
            assert len(observed) == 1 and observed[0]["state"] == "STARTED"
    actual_reserve = PublicStore.reserve

    def reserve_spy(self, conn, snapshot):
        events.append("reserve")
        snapshots.append(dict(snapshot))
        sql_connections.append(conn)
        return actual_reserve(self, conn, snapshot)

    monkeypatch.setattr(PublicStore, "reserve", reserve_spy)

    @sa.event.listens_for(engine, "before_cursor_execute")
    def usage_sql(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO usage_inflight"):
            events.append("STARTED")
            assert conn is sql_connections[-1]
        if statement.startswith("UPDATE usage_inflight"):
            events.append("OBSERVED")

    def prepare(kind, *, paid_active=True):
        with engine.begin() as conn:
            stamp = now(conn)
            if not paid_active:
                conn.execute(public_tables.admissions.update().values(active=False))
            conn.execute(job_execution.insert().values(execution_id="exec-local-ocr",
                job_id="job-local-ocr", case_id="case-local-ocr", kind=kind, status="RUNNING",
                attempt=1, queued_at=stamp, started_at=stamp, available_at=stamp,
                produced=[], trace_id="trace-test", lease_owner="ocr-worker",
                lease_expires_at=stamp + timedelta(hours=1)))
            conn.execute(public_tables.local_admissions.insert().values(case_id="case-local-ocr",
                request_hash=b"l" * 32, session_hash=owner,
                ip_hash=store.fingerprint("TEST_ONLY_IP"), created_at=stamp,
                job_ids=["job-local-ocr"], job_count=1, active=True))
            paid_before = [dict(row) for row in conn.execute(sa.select(public_tables.admissions)).mappings()]
        data = ReadoutInput("case-local-ocr", "candidate-test", "generation-test", "same-successful-clip")
        factory = _production_ocr_factory(monkeypatch, engine=engine, startup=startup,
            case_id=data.case_id, clip_ref=data.incident_clip_ref, events=events,
            inferences=inferences, before_inference=before_inference)
        with factory(data) as session:
            assert type(session.provider) is PaddleOcrProvider
        events.clear()
        registry = readout_registry(load=lambda context: data, provider_factory=factory)
        loop = compose_worker(engine=engine, startup=startup, registry=registry,
            stop=Event(), worker_id="ocr-worker")
        context = ExecutionContext("exec-local-ocr", "job-local-ocr", "case-local-ocr", kind, 1, "trace-test")
        sink = loop.usage_sink_factory(context)
        assert type(sink) is DurableUsageSink
        context = replace(context, usage_sink=sink)
        return SimpleNamespace(context=context, sink=sink, sink_for=loop.usage_sink_factory,
            registry=registry, paid_before=paid_before)

    yield SimpleNamespace(prepare=prepare, engine=engine, store=store, events=events,
        snapshots=snapshots, inferences=inferences, network=network, policy=policy)
    engine.dispose()


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("paid_active", [True, False], ids=["inherited-parent", "local-retry-only"])
def test_production_local_ocr_keeps_usage_identity_before_real_readout_api(local_ocr, kind, paid_active):
    attempt = local_ocr.prepare(kind, paid_active=paid_active)
    policy_before, fingerprint = local_ocr.policy.model_dump(mode="json"), local_ocr.policy.fingerprint()
    result = attempt.registry.dispatch(attempt.context)
    assert result.status == "SUCCEEDED", result.failure_kind
    assert len(local_ocr.inferences) == 7 and local_ocr.network == []
    assert local_ocr.events == ["recording-open", "reserve", "STARTED", *["inference"] * 7,
                                "OBSERVED", "recording-close"]
    snapshot, = local_ocr.snapshots
    run = result.objects[0].payload["readout_run"]
    assert run["operation"] == kind and run["outcome"] == "SUCCEEDED"
    assert snapshot["operation"] == OPERATIONS[kind] and snapshot["provider_label"] == "ocr-local"
    assert (snapshot["pricing_id"], snapshot["unit"]) == ("local-2026-09", "per_second")
    assert snapshot["planned_run_kind"] == "readout_run" and snapshot["planned_run_ref"] == run["run_id"]
    assert snapshot["direct_no_run"] is False
    key = "plate_readout" if kind == "PLATE_READ" else "overlay_time_readout"
    assert result.objects[0].payload[key] is not None
    with local_ocr.engine.connect() as conn:
        row = conn.execute(sa.select(usage_tables.usage_inflight)).mappings().one()
        assert row["usage_id"] == snapshot["usage_id"] and row["operation"] == OPERATIONS[kind]
        assert row["provider_label"] == "ocr-local" and row["state"] == "OBSERVED"
        assert row["outcome"] == "SUCCEEDED" and row["amount"] == Decimal("0")
        assert row["observed_at"] is not None and row["planned_run_ref"] == run["run_id"]
        assert conn.scalar(sa.select(sa.func.count()).select_from(public_tables.reservations)) == 0
        assert [dict(r) for r in conn.execute(sa.select(public_tables.admissions)).mappings()] == attempt.paid_before
    assert local_ocr.policy.model_dump(mode="json") == policy_before
    assert local_ocr.policy.fingerprint() == fingerprint


@pytest.mark.parametrize("alteration", ["context-kind", "provider", "pricing", "db-kind", "db-job-id", "receipt-job-id"])
def test_local_ocr_identity_mismatch_never_starts_usage_or_inference(local_ocr, alteration):
    attempt = local_ocr.prepare("PLATE_READ")
    sink = attempt.sink
    if alteration == "context-kind":
        context = replace(attempt.context, kind="FINE_VERIFY")
        sink = attempt.sink_for(context)
    operation = "READOUT_PLATE"
    with local_ocr.engine.begin() as conn:
        if alteration == "db-kind":
            conn.execute(job_execution.update().values(kind="FINE_VERIFY"))
        elif alteration == "db-job-id":
            conn.execute(job_execution.update().values(job_id="other-claimed-job"))
        elif alteration == "receipt-job-id":
            conn.execute(public_tables.local_admissions.update().values(job_ids=["other-local-job"]))
    with pytest.raises(PublicDenied):
        sink.begin(operation, "ocr-other" if alteration == "provider" else "ocr-local",
            {**PRICING, "pricing_id": "other-local-pricing"} if alteration == "pricing" else PRICING,
            run_ref={"kind": "readout_run", "ref": "rr_test_only"})
    assert "STARTED" not in local_ocr.events and local_ocr.inferences == [] and local_ocr.network == []
    with local_ocr.engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(usage_tables.usage_inflight)) == 0
        assert conn.scalar(sa.select(sa.func.count()).select_from(public_tables.reservations)) == 0


@pytest.mark.parametrize("condition", ["stop", "cancel", "claim-owner", "expired-lease"])
def test_local_ocr_preserves_stop_cancellation_and_claim_guards(local_ocr, condition):
    attempt = local_ocr.prepare("PLATE_READ")
    with local_ocr.engine.begin() as conn:
        if condition == "stop":
            local_ocr.store.set_open(conn, False)
        elif condition == "cancel":
            conn.execute(job_execution.update().values(cancel_requested_at=now(conn)))
        elif condition == "claim-owner":
            conn.execute(job_execution.update().values(lease_owner="other-worker"))
        else:
            conn.execute(job_execution.update().values(lease_expires_at=now(conn) - timedelta(seconds=1)))
    error = CancellationRequested if condition == "cancel" else PublicDenied
    with pytest.raises(error):
        attempt.registry.dispatch(attempt.context)
    assert "STARTED" not in local_ocr.events and local_ocr.inferences == [] and local_ocr.network == []
    with local_ocr.engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(usage_tables.usage_inflight)) == 0
