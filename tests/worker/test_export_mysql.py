"""Real exports with InnoDB, replay faults and connection-event assertions."""
from contextlib import contextmanager
from dataclasses import replace
from io import StringIO
from threading import Event
from types import MappingProxyType
import subprocess

import pytest
import sqlalchemy as sa

from daesingo.case.domain import CaseAggregate
from daesingo.case.jobs import issue_job
from daesingo.common.bootstrap import Startup
from daesingo.common.config import RuntimeConfig, DbSettings
from daesingo.common.db import create_worker_engine
from daesingo.common.db.transactions import run_worker_transaction
from daesingo.common.jobs.produced import ProducedReader, produced_objects
from daesingo.common.jobs.repository import enqueue
from daesingo.common.jobs.redelivery import redeliver_once
from daesingo.common.jobs.schema import job_execution
from daesingo.common.logging import configure_logging
from daesingo.recording import RecordingService, TransactionalRecordingRepository, LocalIncidentMaterializer, IncidentClipEncoding
from daesingo.recording.exports import LocalExportMaterializer, export_fingerprint
from daesingo.recording.mysql_repository import MySQLRecordingRepository, entries
from daesingo.worker.case_composition import stored_case_store, StoredCaseReflector
from daesingo.worker.composition_root import compose_registry
from daesingo.worker.composition import compose_worker
from daesingo.worker.registry import KindRegistry
from mysql_fault_proxy import CommitResponseProxy
from test_worker_mysql import queue  # noqa: F401

pytestmark = pytest.mark.mysql
KINDS = ("REPORT_VIDEO_EXPORT", "PLATE_IMAGE_EXPORT")


def prepare_export(engine, tmp_path, kind, *, limit=30_000_000):
    root, temp = tmp_path / "media", tmp_path / "temp"
    root.mkdir(); temp.mkdir()
    video = root / "source.avi"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
        "testsrc2=s=160x96:r=10:d=1", "-c:v", "mpeg4", str(video)],
        capture_output=True, check=True, timeout=30)
    tx = lambda callback: run_worker_transaction(engine, callback)
    repo = TransactionalRecordingRepository(tx, storage_root=root)
    with RecordingService(repo, incident_materializer=LocalIncidentMaterializer(IncidentClipEncoding(240, "veryfast", 23),
            temp_root=temp), durable_prepared=True, case_id="case") as service:
        source = service.register_local_source(video, case_id="case")
        timeline = service.create_relative_timeline(source.source_asset.source_asset_ref)
        stream, = [s for s in source.media_streams if s.media_type == "VIDEO"]
        resolution = service.resolve_span({"timeline_id": timeline.timeline_id, "revision": 1},
            {"start_sec": .1, "end_sec": .8}, media_stream_ref=stream.media_stream_ref)
        clip = service.build_incident_clip(resolution)
        frame = service.resolve_frame({"kind": "STREAM_POSITION", "media_stream_ref": stream.media_stream_ref, "source_offset_sec": .3})
        service.read_frame(frame.frame_ref)
    request = {"incident_clip_ref": clip.incident_clip_ref, "post_stamp": {"needed": True, "value": "2026-06-20T14:19:56+09:00"}}
    if kind == "PLATE_IMAGE_EXPORT":
        request = {"incident_clip_ref": clip.incident_clip_ref, "frame_ref": frame.frame_ref,
            "plate_bbox_xywh": [10, 10, 40, 20], "max_byte_size": limit}
    case = CaseAggregate.empty("case")
    job = issue_job(case, kind, input_fingerprint=export_fingerprint({"kind": kind, "input": request}), export_input=request)
    with engine.begin() as conn:
        stored_case_store(conn, storage_root=root).register(case)
        execution, = enqueue(conn, [job], "trace")
    config = RuntimeConfig.from_mapping("worker", {"DAESINGO_RUNTIME_DB_URL": engine.url.render_as_string(hide_password=False),
        "DAESINGO_RUNTIME_MEDIA_ROOT": str(root), "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(temp)})
    stream = StringIO()
    startup = Startup(config, MappingProxyType({}), configure_logging("worker", stream=stream))
    return startup, execution, request, stream


def products(engine):
    with engine.connect() as conn:
        return conn.scalar(sa.select(sa.func.count()).select_from(entries).where(entries.c.kind == "derived_asset"))


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("fault", ["none", "publish_rollback", "publish_commit_unknown", "t1_rollback", "t1_commit_unknown",
    "t2_rollback", "t2_commit_unknown", "t2_redelivery", "reconcile"])
@pytest.mark.mysql_check("recording_exports", "replay")
def test_export_once_across_real_transaction_faults(queue, tmp_path, monkeypatch, kind, fault):
    startup, execution, request, log = prepare_export(queue, tmp_path, kind)
    calls, encodes, inside, injected = [], [], [], []
    active = queue
    capability = "export_report_video" if kind == KINDS[0] else "export_plate_image"
    operation = "report" if kind == KINDS[0] else "plate"
    actual = getattr(RecordingService, capability)
    encode = getattr(LocalExportMaterializer, operation)
    def invoke(service, **kw):
        assert active.pool.checkedout() == 0
        calls.append(kw); inside.append(True)
        try: return actual(service, **kw)
        finally: inside.pop()
    def materialize(materializer, *args):
        assert active.pool.checkedout() == 0
        encodes.append(True)
        return encode(materializer, *args)
    monkeypatch.setattr(RecordingService, capability, invoke)
    monkeypatch.setattr(LocalExportMaterializer, operation, materialize)
    def checkout(*args): assert not inside, "DB checkout inside public export"
    with CommitResponseProxy(queue.url.host, queue.url.port) as proxy:
        if fault.endswith("commit_unknown"):
            active = create_worker_engine(DbSettings(url=queue.url.set(host="127.0.0.1", port=proxy.port)
                .update_query_dict({"ssl_disabled": "true"}).render_as_string(hide_password=False)))
        sa.event.listen(active, "checkout", checkout)
        def after_write(conn, cursor, sql, parameters, *args):
            upper = sql.upper()
            target = (upper.startswith("INSERT INTO RECORDING_ENTRY") if fault.startswith("publish") else
                upper.startswith("INSERT INTO PRODUCED_OBJECTS") if fault.startswith("t1") else
                upper.startswith("UPDATE CASES"))
            if fault not in {"none", "reconcile"} and target and not injected:
                injected.append(True)
                if fault.endswith("rollback"):
                    raise sa.exc.OperationalError("probe", {}, Exception(1213, "deadlock"))
                if fault == "t2_redelivery": raise ValueError("interrupted T2")
                if fault.endswith("commit_unknown"): proxy.arm()
        sa.event.listen(active, "after_cursor_execute", after_write)
        if fault == "reconcile":
            import daesingo.worker.composition as composition
            monkeypatch.setattr(composition, "reconcile_once", lambda *a, **k: (_ for _ in ()).throw(ValueError("interrupted reconciliation")))
        try:
            registry = compose_registry(engine=active, startup=startup)
            stop = Event()
            def dispatch(ctx):
                result = registry.dispatch(ctx)
                stop.set()
                return result
            reflector = StoredCaseReflector(storage_root=startup.config.media_root)
            loop = compose_worker(engine=active, startup=startup, registry=KindRegistry({kind: dispatch}), stop=stop,
                reflector=reflector, sleep=lambda _: None)
            loop.run()
            assert calls == [request] and len(encodes) == 1
            if fault not in {"none", "reconcile"}: assert injected
            assert proxy.commit_ok_dropped == int(fault.endswith("commit_unknown"))
            for _ in range(2): redeliver_once(active, reflector, sleep=lambda _: None)
            assert products(active) == 1 and len(calls) == len(encodes) == 1
            with active.begin() as conn:
                terminal = conn.execute(sa.select(job_execution).where(job_execution.c.execution_id == execution)).mappings().one()
                assert terminal["status"] == "SUCCEEDED" and terminal["case_applied_at"] is not None
                payload = ProducedReader()(conn, kind, tuple(terminal["produced"]))
                recording = RecordingService(MySQLRecordingRepository(conn, storage_root=startup.config.media_root))
                asset = recording.get_derived_asset(payload["derived_asset_ref"])
                facts = recording.lookup_asset_facts({"kind": "derived_asset", "ref": asset.derived_asset_ref})
                assert facts.byte_size == asset.byte_size and facts.availability == "AVAILABLE"
                assert asset.byte_size == recording.open_derived_asset(asset.derived_asset_ref).byte_size > 0
                assert recording.get_export_transform(asset.transform_ref)["input"] == request
                assert conn.scalar(sa.select(sa.func.count()).select_from(produced_objects)) == 1
            assert active.pool.checkedout() == 0
            assert "source.avi" not in log.getvalue() and "probe" not in log.getvalue()
        finally:
            sa.event.remove(active, "after_cursor_execute", after_write)
            sa.event.remove(active, "checkout", checkout)
            if active is not queue: active.dispose()


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.mysql_check("recording_exports", "cancellation")
def test_cancel_after_actual_export_discards_snapshot_before_publication(queue, tmp_path, monkeypatch, kind):
    startup, execution, request, log = prepare_export(queue, tmp_path, kind)
    name = "export_report_video" if kind == KINDS[0] else "export_plate_image"
    actual = getattr(RecordingService, name)
    current, calls = [], []
    def capability(service, **kw):
        result = actual(service, **kw)
        calls.append(True); current[0].cancel_signal.request()
        return result
    monkeypatch.setattr(RecordingService, name, capability)
    registry = compose_registry(engine=queue, startup=startup)
    stop = Event()
    def dispatch(ctx):
        current.append(ctx)
        try: return registry.dispatch(ctx)
        finally: stop.set()
    compose_worker(engine=queue, startup=startup, registry=KindRegistry({kind: dispatch}), stop=stop).run()
    with queue.connect() as conn:
        assert conn.scalar(sa.select(job_execution.c.status).where(job_execution.c.execution_id == execution)) == "CANCELLED"
    assert calls == [True] and products(queue) == 0 and queue.pool.checkedout() == 0


@pytest.mark.parametrize("mode,expected", [("limit", "PLATE_IMAGE_OUTPUT_LIMIT_UNSATISFIABLE"),
    ("generation", "PLATE_IMAGE_EXPORT_FAILED")])
@pytest.mark.mysql_check("recording_exports", "failure")
def test_real_plate_failures_leave_no_asset_or_produced(queue, tmp_path, mode, expected):
    startup, execution, request, log = prepare_export(queue, tmp_path, "PLATE_IMAGE_EXPORT", limit=1 if mode == "limit" else 30_000_000)
    if mode == "generation":
        with queue.begin() as conn:
            store = stored_case_store(conn, storage_root=startup.config.media_root)
            case = store.load_for_update("case")
            # Add a new intent with a genuine out-of-frame bbox, leaving prior input immutable.
            from daesingo.case.jobs import issue_same_input
            request = {**request, "plate_bbox_xywh": [9999, 0, 10, 10]}
            prior = case.job_records[-1]
            case.settle_job(prior["job_id"], "SUPERSEDED")
            conn.execute(job_execution.update().where(job_execution.c.execution_id == execution).values(status="CANCELLED"))
            job = issue_job(case, "PLATE_IMAGE_EXPORT", input_fingerprint=export_fingerprint({"kind": "PLATE_IMAGE_EXPORT", "input": request}), export_input=request)
            store.save(case)
            execution, = enqueue(conn, [job], "trace")
    registry = compose_registry(engine=queue, startup=startup)
    stop = Event()
    def dispatch(ctx):
        result = registry.dispatch(ctx); stop.set(); return result
    compose_worker(engine=queue, startup=startup, registry=KindRegistry({"PLATE_IMAGE_EXPORT": dispatch}), stop=stop,
        reflector=StoredCaseReflector(storage_root=startup.config.media_root)).run()
    with queue.connect() as conn:
        terminal = conn.execute(sa.select(job_execution).where(job_execution.c.execution_id == execution)).mappings().one()
        assert terminal["status"] == "FAILED" and terminal["failure_kind"] == expected
        assert terminal["produced"] == [] and terminal["case_applied_at"] is not None
        assert conn.scalar(sa.select(sa.func.count()).select_from(produced_objects)) == 0
    assert products(queue) == 0 and queue.pool.checkedout() == 0


@pytest.mark.mysql_check("recording_exports", "input_immutability")
def test_export_input_mutation_rejected_before_any_mysql_save(queue, tmp_path):
    from daesingo.case.store import AppendOnlyViolation
    startup, execution, request, log = prepare_export(queue, tmp_path, "PLATE_IMAGE_EXPORT")
    with queue.begin() as conn:
        store = stored_case_store(conn, storage_root=startup.config.media_root)
        case = store.load_for_update("case")
        job = case.job_records[-1]
        case.export_inputs[job["job_id"]]["max_byte_size"] = 1
        with pytest.raises(AppendOnlyViolation): store.save(case)
        assert store.export_input("case", job["job_id"]) == request
