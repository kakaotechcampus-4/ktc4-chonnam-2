"""Real AVI, durable Case/Fine input, clip generation and unchanged T1/T2 replay."""
from io import StringIO
import multiprocessing
import subprocess
from threading import Event

import pytest
import sqlalchemy as sa

from daesingo.common.config import DbSettings
from daesingo.common.db import create_worker_engine
from daesingo.common.jobs.produced import ProducedReader, produced_objects
from daesingo.common.jobs.redelivery import redeliver_once
from daesingo.common.jobs.schema import job_execution
from daesingo.recording import RecordingService, LocalIncidentMaterializer, ConnectionRecordingRepository
from daesingo.worker.bootstrap import bootstrap
from daesingo.worker.case_composition import StoredCaseReflector, stored_case_store
from daesingo.worker.composition import compose_worker
from daesingo.worker.composition_root import compose_registry
from daesingo.worker.registry import KindRegistry
from mysql_fault_proxy import CommitResponseProxy
from test_worker_mysql import queue  # noqa: F401

pytestmark = pytest.mark.mysql


def prepare(queue, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from daesingo.api.bootstrap import bootstrap as api_bootstrap
    from daesingo.api.app import create_app
    from tests.e2e_runtime.production_processes import worker_peer
    root, temp = tmp_path / "media", tmp_path / "temp"
    root.mkdir(); temp.mkdir()
    video = tmp_path / "synthetic.avi"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
        "testsrc2=s=64x48:r=10:d=1", "-c:v", "mpeg4", "-pix_fmt", "yuv420p", str(video)],
        check=True, capture_output=True, timeout=30)
    values = {"DAESINGO_RUNTIME_DB_URL": queue.url.render_as_string(hide_password=False),
        "DAESINGO_RUNTIME_MEDIA_ROOT": str(root), "DAESINGO_RUNTIME_API_TEMP_ROOT": str(temp),
        "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(temp), "GEMINI_API_KEY": "offline",
        "DAESINGO_RECORDING_ANALYSIS_PROFILE_REF": "test-analysis",
        "DAESINGO_RECORDING_ANALYSIS_HEIGHT": "240", "DAESINGO_RECORDING_ANALYSIS_PRESET": "veryfast",
        "DAESINGO_RECORDING_ANALYSIS_CRF": "23", "DAESINGO_RECORDING_INCIDENT_HEIGHT": "240",
        "DAESINGO_RECORDING_ANALYSIS_MAX_BYTES": "1000000", "DAESINGO_RECORDING_ANALYSIS_MAX_DURATION_MS": "10000",
        "DAESINGO_RECORDING_INCIDENT_PRESET": "veryfast", "DAESINGO_RECORDING_INCIDENT_CRF": "23"}
    env_file = tmp_path / "peer.env"
    env_file.write_text("\n".join(f"{k}={v}" for k, v in values.items()), encoding="utf-8")
    monkeypatch.setenv("DAESINGO_ENV_FILE", str(env_file))
    with TestClient(create_app(startup=api_bootstrap(revision="test", stream=StringIO()))) as client:
        created = client.post("/cases").json(); case_id = created["case_id"]
        upload = client.post(f"/cases/{case_id}/sources", files={"file": ("synthetic.avi", video.read_bytes(), "video/x-msvideo")})
        assert upload.status_code == 201
        response = client.post(f"/cases/{case_id}/commands", json={"case_id": case_id,
            "expected_case_rev": upload.json()["case_view"]["case_rev"], "kind": "START_ANALYSIS", "payload": {"description": ""}})
        assert response.status_code == 202
    # These are integration seeds in this process; separate OS processes are
    # independently tested in e2e_runtime. Only external provider HTTP is fake.
    for kind in ("COARSE_SEARCH", "FINE_VERIFY"):
        incoming, outgoing = multiprocessing.Pipe()
        try:
            worker_peer(outgoing, str(env_file), "clip", kind)
            result = incoming.recv()
            assert "error" not in result, result
            assert result["http_calls"] == 1 and result["terminals"] == [{"status": "SUCCEEDED", "failure_kind": None}]
        finally: incoming.close(); outgoing.close()
    return case_id, root, temp, bootstrap(revision="test", stream=StringIO())


@pytest.mark.parametrize("fault", ["none", "rollback", "commit_unknown", "t2_rollback", "t2_redelivery"])
@pytest.mark.mysql_check("incident_clip", "t1_replay")
def test_actual_clip_once_and_durable_inputs_survive_t1_replay(queue, tmp_path, monkeypatch, fault):
    case_id, root, temp, startup = prepare(queue, tmp_path, monkeypatch)
    with queue.begin() as conn:
        clip_row = dict(conn.execute(sa.select(job_execution).where(job_execution.c.kind == "INCIDENT_CLIP_BUILD")).mappings().one())
        fixed = stored_case_store(conn, storage_root=root).observation_input(case_id, clip_row["job_id"])
    assert set(fixed) == {"candidate_id", "generation_job_id", "span", "fine_job_id"}
    calls, encodes, closed, seen = [], [], [], []
    original_build, original_encode, original_close = RecordingService.build_incident_clip, LocalIncidentMaterializer.materialize, RecordingService.close
    active = queue
    def build(service, resolution, options=None):
        assert active.pool.checkedout() == 0
        calls.append(resolution)
        return original_build(service, resolution, options)
    def encode(materializer, *args):
        assert active.pool.checkedout() == 0
        encodes.append(True)
        return original_encode(materializer, *args)
    def close(service): closed.append(service); original_close(service)
    monkeypatch.setattr(RecordingService, "build_incident_clip", build)
    monkeypatch.setattr(LocalIncidentMaterializer, "materialize", encode)
    monkeypatch.setattr(RecordingService, "close", close)
    with CommitResponseProxy(queue.url.host, queue.url.port) as proxy:
        extra = None
        if fault == "commit_unknown":
            extra = active = create_worker_engine(DbSettings(url=queue.url.set(host="127.0.0.1", port=proxy.port)
                .update_query_dict({"ssl_disabled": "true"}).render_as_string(hide_password=False)))
        injected = []
        def after_write(conn, cursor, sql, *args):
            target = "UPDATE CASES" if fault.startswith("t2_") else "INSERT INTO PRODUCED_OBJECTS"
            if not injected and sql.upper().startswith(target):
                injected.append(True)
                if fault in {"rollback", "t2_rollback"}: raise sa.exc.OperationalError("probe", {}, Exception(1213, "deadlock"))
                if fault == "t2_redelivery": raise ValueError("T2 interruption")
                if fault == "commit_unknown": proxy.arm()
        sa.event.listen(active, "after_cursor_execute", after_write)
        try:
            registry = compose_registry(engine=active, startup=startup)
            stop = Event()
            def invoke(ctx):
                seen.append(ctx)
                result = registry.dispatch(ctx)
                stop.set()
                return result
            reflector = StoredCaseReflector(storage_root=root)
            loop = compose_worker(engine=active, startup=startup, registry=KindRegistry({"INCIDENT_CLIP_BUILD": invoke}),
                stop=stop, reflector=reflector, sleep=lambda seconds: None)
            loop.run()
            assert len(calls) == len(encodes) == len(seen) == 1
            assert injected
            assert proxy.commit_ok_dropped == (1 if fault == "commit_unknown" else 0)
            # Explicit redelivery must not call the handler or build again.
            redeliver_once(active, reflector, sleep=lambda seconds: None)
            assert len(calls) == 1 and active.pool.checkedout() == 0
        finally:
            sa.event.remove(active, "after_cursor_execute", after_write)
            if extra is not None: extra.dispose()
    assert closed
    with queue.begin() as conn:
        terminal = conn.execute(sa.select(job_execution).where(job_execution.c.execution_id == clip_row["execution_id"])).mappings().one()
        assert terminal["status"] == "SUCCEEDED" and terminal["case_applied_at"] is not None
        content = ProducedReader()(conn, "INCIDENT_CLIP_BUILD", tuple(terminal["produced"]))
        assert set(content) == {"incident_clip_ref"}
        assert conn.scalar(sa.select(sa.func.count()).select_from(produced_objects).where(produced_objects.c.job_kind == "INCIDENT_CLIP_BUILD")) == 1
        facade = stored_case_store(conn, storage_root=root)
        case = facade.get_case(case_id)
        readouts = [j for j in case.job_records if j["kind"] in {"PLATE_READ", "OVERLAY_TIME_READ"}]
        assert len(readouts) == 2
        assert all(facade.observation_input(case_id, j["job_id"])["incident_clip_ref"] == content["incident_clip_ref"] for j in readouts)
        assert facade.observation_input(case_id, clip_row["job_id"]) == fixed
        with RecordingService(ConnectionRecordingRepository(conn, storage_root=root)) as reopened:
            clip = reopened.get_incident_clip(content["incident_clip_ref"])
            assert clip.availability == "AVAILABLE" and clip.byte_size > 0
            assert clip.source_provenance.requested_range.start_sec == fixed["span"]["start_ms"] / 1000
            assert clip.source_provenance.requested_range.end_sec == fixed["span"]["end_ms"] / 1000
    assert {p.name for p in temp.iterdir()} == {".runtime-cleanup-temp.lock"}


@pytest.mark.mysql_check("incident_clip", "cancel_after_build")
def test_cancel_after_real_build_keeps_no_success_or_readout_jobs(queue, tmp_path, monkeypatch):
    case_id, root, temp, startup = prepare(queue, tmp_path, monkeypatch)
    contexts, calls = [], []
    original = RecordingService.build_incident_clip
    def build(service, resolution, options=None):
        assert queue.pool.checkedout() == 0
        calls.append(True)
        result = original(service, resolution, options)
        contexts[0].cancel_signal.request()
        return result
    monkeypatch.setattr(RecordingService, "build_incident_clip", build)
    registry, stop = compose_registry(engine=queue, startup=startup), Event()
    def invoke(ctx):
        contexts.append(ctx)
        try: return registry.dispatch(ctx)
        finally: stop.set()
    compose_worker(engine=queue, startup=startup, registry=KindRegistry({"INCIDENT_CLIP_BUILD": invoke}),
                   stop=stop, reflector=StoredCaseReflector(storage_root=root)).run()
    assert len(calls) == 1 and queue.pool.checkedout() == 0
    with queue.begin() as conn:
        terminal = conn.execute(sa.select(job_execution).where(job_execution.c.kind == "INCIDENT_CLIP_BUILD")).mappings().one()
        assert terminal["status"] == "CANCELLED" and terminal["produced"] == []
        assert conn.scalar(sa.select(sa.func.count()).select_from(produced_objects).where(produced_objects.c.job_kind == "INCIDENT_CLIP_BUILD")) == 0
        assert not any(j["kind"] in {"PLATE_READ", "OVERLAY_TIME_READ"} for j in stored_case_store(conn, storage_root=root).get_case(case_id).job_records)
    assert {p.name for p in temp.iterdir()} == {".runtime-cleanup-temp.lock"}


@pytest.mark.parametrize("mode,want", [("recording", "RECORDING_INCIDENT_CLIP_BUILD_FAILED"), ("db", "RUNTIME_HANDLER_ERROR")])
@pytest.mark.mysql_check("incident_clip", "failure_new_job")
def test_failure_preserves_fine_and_new_case_job_retries_only_clip(queue, tmp_path, monkeypatch, mode, want):
    from daesingo.case import jobs
    from daesingo.common.jobs.repository import enqueue
    from daesingo.recording import RecordingCapabilityError
    case_id, root, temp, startup = prepare(queue, tmp_path, monkeypatch)
    with queue.begin() as conn:
        fine_before = dict(conn.execute(sa.select(job_execution).where(job_execution.c.kind == "FINE_VERIFY")).mappings().one())
    original_build, original_encode = RecordingService.build_incident_clip, LocalIncidentMaterializer.materialize
    builds, encodes = [], []
    def build(service, resolution, options=None):
        assert queue.pool.checkedout() == 0
        builds.append(True)
        return original_build(service, resolution, options)
    def encode(materializer, *args):
        assert queue.pool.checkedout() == 0
        encodes.append(True)
        if len(encodes) == 1:
            if mode == "db": raise sa.exc.OperationalError("private locator", {}, Exception("db"))
            raise RecordingCapabilityError("INCIDENT_CLIP_BUILD_FAILED", "private path credential")
        return original_encode(materializer, *args)
    monkeypatch.setattr(RecordingService, "build_incident_clip", build)
    monkeypatch.setattr(LocalIncidentMaterializer, "materialize", encode)
    registry = compose_registry(engine=queue, startup=startup)
    def once():
        stop = Event()
        def invoke(ctx):
            result = registry.dispatch(ctx)
            stop.set()
            return result
        compose_worker(engine=queue, startup=startup, registry=KindRegistry({"INCIDENT_CLIP_BUILD": invoke}),
            stop=stop, reflector=StoredCaseReflector(storage_root=root)).run()
    once()
    with queue.begin() as conn:
        failed = conn.execute(sa.select(job_execution).where(job_execution.c.kind == "INCIDENT_CLIP_BUILD")).mappings().one()
        assert failed["status"] == "FAILED" and failed["failure_kind"] == want and failed["produced"] == []
        facade = stored_case_store(conn, storage_root=root)
        case = facade.load_for_update(case_id)
        assert not any(j["kind"] in {"PLATE_READ", "OVERLAY_TIME_READ"} for j in case.job_records)
        prior = next(j for j in case.job_records if j["job_id"] == failed["job_id"])
        new_job = jobs.issue_same_input(case, prior)
        facade.save(case)
        enqueue(conn, [new_job], "new-clip-only")
    once()
    assert len(builds) == len(encodes) == 2  # two jobs, one invocation each
    with queue.begin() as conn:
        fine_after = dict(conn.execute(sa.select(job_execution).where(job_execution.c.kind == "FINE_VERIFY")).mappings().one())
        assert fine_after == fine_before
        latest = conn.execute(sa.select(job_execution).where(job_execution.c.job_id == new_job["job_id"])).mappings().one()
        assert latest["status"] == "SUCCEEDED" and latest["case_applied_at"] is not None
        assert len(latest["produced"]) == 1
    assert queue.pool.checkedout() == 0


@pytest.mark.mysql_check("incident_clip", "immutable_clip_new_execution")
def test_two_successful_executions_can_reference_the_same_durable_clip(queue, tmp_path, monkeypatch):
    from daesingo.case import jobs
    from daesingo.common.jobs.cancel import request_cancel
    from daesingo.common.jobs.repository import enqueue
    case_id, root, temp, startup = prepare(queue, tmp_path, monkeypatch)
    original = RecordingService.build_incident_clip
    calls = []
    def build(service, resolution, options=None):
        assert queue.pool.checkedout() == 0
        calls.append(True)
        return original(service, resolution, options)
    monkeypatch.setattr(RecordingService, "build_incident_clip", build)
    registry = compose_registry(engine=queue, startup=startup)
    def once():
        stop = Event()
        def invoke(ctx):
            result = registry.dispatch(ctx)
            stop.set()
            return result
        compose_worker(engine=queue, startup=startup, registry=KindRegistry({"INCIDENT_CLIP_BUILD": invoke}),
            stop=stop, reflector=StoredCaseReflector(storage_root=root)).run()
    once()
    with queue.begin() as conn:
        facade = stored_case_store(conn, storage_root=root)
        case = facade.load_for_update(case_id)
        prior = next(j for j in case.job_records if j["kind"] == "INCIDENT_CLIP_BUILD")
        # Unimplemented readouts must not be claimed by this clip-only probe.
        request_cancel(conn, [j["job_id"] for j in case.job_records if j["kind"] in {"PLATE_READ", "OVERLAY_TIME_READ"}])
        new_job = jobs.issue_same_input(case, prior)
        facade.save(case)
        enqueue(conn, [new_job], "new-clip-receipt")
    once()
    with queue.begin() as conn:
        rows = conn.execute(sa.select(job_execution).where(job_execution.c.kind == "INCIDENT_CLIP_BUILD")).mappings().all()
        assert len(rows) == len(calls) == 2 and all(row["status"] == "SUCCEEDED" for row in rows)
        assert rows[0]["produced"] != rows[1]["produced"]
        payloads = [ProducedReader()(conn, "INCIDENT_CLIP_BUILD", tuple(row["produced"])) for row in rows]
        assert payloads[0] == payloads[1] and set(payloads[0]) == {"incident_clip_ref"}
        assert all(row["case_applied_at"] is not None for row in rows)
    assert queue.pool.checkedout() == 0
