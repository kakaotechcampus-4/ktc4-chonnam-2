"""Real media/DB issuance seam, NOT production Case helper/Top-3 integration."""
from threading import Event

import pytest
import sqlalchemy as sa

from daesingo.common.jobs.redelivery import redeliver_once
from daesingo.common.jobs.schema import job_execution
from daesingo.recording import RecordingService
from daesingo.recording.frames import FfmpegFrameExtractor
from daesingo.worker.case_composition import StoredCaseReflector, stored_case_store
from daesingo.worker.composition import compose_worker
from daesingo.worker.produced_reader import worker_produced_reader
from daesingo.worker.registry import KindRegistry
from incident_frame_support import test_registry as frame_registry
from test_incident_clip_mysql import prepare
from test_worker_mysql import queue  # noqa: F401

pytestmark = pytest.mark.mysql


@pytest.mark.parametrize("fault", ["none", "t1_rollback", "t2_rollback", "t2_redelivery"])
def test_frames_are_durable_and_replay_never_decodes(queue, tmp_path, monkeypatch, fault):
    case_id, root, temp, startup = prepare(queue, tmp_path, monkeypatch)
    decodes, resolves, builds = [], [], []
    original_extract, original_resolve, original_build = (
        FfmpegFrameExtractor.extract, RecordingService.resolve_frame, RecordingService.build_incident_clip)
    def extract(self, *args):
        assert queue.pool.checkedout() == 0
        decodes.append(True)
        return original_extract(self, *args)
    def resolve(self, locator):
        assert queue.pool.checkedout() == 0
        resolves.append(locator)
        return original_resolve(self, locator)
    def build(self, *args):
        assert queue.pool.checkedout() == 0
        builds.append(True)
        return original_build(self, *args)
    monkeypatch.setattr(FfmpegFrameExtractor, "extract", extract)
    monkeypatch.setattr(RecordingService, "resolve_frame", resolve)
    monkeypatch.setattr(RecordingService, "build_incident_clip", build)
    injected = []
    def fail(conn, cursor, sql, *args):
        target = "INSERT INTO PRODUCED_OBJECTS" if fault == "t1_rollback" else "UPDATE CASES"
        if fault != "none" and not injected and sql.upper().startswith(target):
            injected.append(True)
            if fault == "t2_redelivery": raise ValueError("test T2 interruption")
            raise sa.exc.OperationalError("test", {}, Exception(1213, "deadlock"))
    sa.event.listen(queue, "after_cursor_execute", fail)
    stop, registry = Event(), frame_registry(queue, startup)
    def invoke(ctx):
        try: return registry.dispatch(ctx)
        finally: stop.set()
    reflector = StoredCaseReflector(storage_root=root)
    try:
        compose_worker(engine=queue, startup=startup, registry=KindRegistry({"INCIDENT_CLIP_BUILD": invoke}),
            stop=stop, reflector=reflector, sleep=lambda seconds: None).run()
        redeliver_once(queue, reflector, sleep=lambda seconds: None)
    finally:
        sa.event.remove(queue, "after_cursor_execute", fail)
    assert len(decodes) == len(resolves) == len(builds) == 1
    assert bool(injected) == (fault != "none")
    with queue.begin() as conn:
        row = conn.execute(sa.select(job_execution).where(job_execution.c.kind == "INCIDENT_CLIP_BUILD")).mappings().one()
        assert row["status"] == "SUCCEEDED" and row["case_applied_at"] is not None
        content = worker_produced_reader()(conn, row["kind"], tuple(row["produced"]))
        assert content["preview_frame_ref"] and set(content["candidate_frame_refs"].values()) == {content["preview_frame_ref"]}
        # Existing develop consumes the clip and starts Readout, but has no
        # preview/Top-3 consumer. Do not fake that missing integration.
        case = stored_case_store(conn, storage_root=root).get_case(case_id)
        assert "preview_frame_ref" not in case.observation_outcomes[row["job_id"]]
        from daesingo.recording import ConnectionRecordingRepository
        with RecordingService(ConnectionRecordingRepository(conn, storage_root=root)) as recording:
            assert recording.read_owned_frame_image(case_id, content["preview_frame_ref"]).content.startswith(b"\x89PNG")
    assert queue.pool.checkedout() == 0


@pytest.mark.parametrize("failure", ["db", "cancel"])
def test_frame_persistence_and_cancel_cannot_publish_null_success(queue, tmp_path, monkeypatch, failure):
    _, root, temp, startup = prepare(queue, tmp_path, monkeypatch)
    from daesingo.recording.mysql_repository import MySQLRecordingRepository
    original = MySQLRecordingRepository.add_frame
    contexts, decodes = [], []
    def add(self, *args, **kwargs):
        decodes.append(True)
        if failure == "db": raise sa.exc.OperationalError("private", {}, Exception("persistence"))
        value = original(self, *args, **kwargs)
        contexts[0].cancel_signal.request()
        return value
    monkeypatch.setattr(MySQLRecordingRepository, "add_frame", add)
    stop, registry = Event(), frame_registry(queue, startup)
    def invoke(ctx):
        contexts.append(ctx)
        try: return registry.dispatch(ctx)
        finally: stop.set()
    compose_worker(engine=queue, startup=startup, registry=KindRegistry({"INCIDENT_CLIP_BUILD": invoke}),
        stop=stop, reflector=StoredCaseReflector(storage_root=root), sleep=lambda seconds: None).run()
    with queue.begin() as conn:
        row = conn.execute(sa.select(job_execution).where(job_execution.c.kind == "INCIDENT_CLIP_BUILD")).mappings().one()
        assert row["status"] == ("FAILED" if failure == "db" else "CANCELLED")
        assert row["produced"] == []
        if failure == "db": assert row["failure_kind"] == "RUNTIME_HANDLER_ERROR"
    assert decodes == [True] and queue.pool.checkedout() == 0


def test_frame_receipt_survives_real_lost_t1_commit_ack(queue, tmp_path, monkeypatch):
    from daesingo.common.config import DbSettings
    from daesingo.common.db import create_worker_engine
    from mysql_fault_proxy import CommitResponseProxy
    _, root, _, startup = prepare(queue, tmp_path, monkeypatch)
    original, decodes = FfmpegFrameExtractor.extract, []
    with CommitResponseProxy(queue.url.host, queue.url.port) as proxy:
        active = create_worker_engine(DbSettings(url=queue.url.set(host="127.0.0.1", port=proxy.port)
            .update_query_dict({"ssl_disabled": "true"}).render_as_string(hide_password=False)))
        def extract(self, *args):
            assert active.pool.checkedout() == 0
            decodes.append(True)
            return original(self, *args)
        monkeypatch.setattr(FfmpegFrameExtractor, "extract", extract)
        injected = []
        def arm(conn, cursor, sql, *args):
            if not injected and sql.upper().startswith("INSERT INTO PRODUCED_OBJECTS"):
                injected.append(True)
                proxy.arm()
        sa.event.listen(active, "after_cursor_execute", arm)
        stop, registry = Event(), frame_registry(active, startup)
        def invoke(ctx):
            try: return registry.dispatch(ctx)
            finally: stop.set()
        reflector = StoredCaseReflector(storage_root=root)
        try:
            compose_worker(engine=active, startup=startup, registry=KindRegistry({"INCIDENT_CLIP_BUILD": invoke}),
                stop=stop, reflector=reflector, sleep=lambda seconds: None).run()
            redeliver_once(active, reflector, sleep=lambda seconds: None)
            assert proxy.commit_ok_dropped == 1 and decodes == [True]
            with active.begin() as conn:
                row = conn.execute(sa.select(job_execution).where(job_execution.c.kind == "INCIDENT_CLIP_BUILD")).mappings().one()
                assert row["status"] == "SUCCEEDED" and row["case_applied_at"] is not None
                assert worker_produced_reader()(conn, row["kind"], tuple(row["produced"]))["preview_frame_ref"]
        finally:
            sa.event.remove(active, "after_cursor_execute", arm)
            active.dispose()


def test_separate_worker_and_api_processes_read_exact_owned_frame(queue, tmp_path, monkeypatch):
    import hashlib
    import multiprocessing
    import os
    from frame_process_support import frame_api_peer, frame_worker_peer
    from daesingo.recording import ConnectionRecordingRepository
    case_id, root, _, _ = prepare(queue, tmp_path, monkeypatch)
    context = multiprocessing.get_context("spawn")
    children = []
    def run(target, *args):
        local, remote = context.Pipe()
        child = context.Process(target=target, args=(remote, str(tmp_path / "peer.env"), *args))
        children.append(child)
        try:
            child.start(); remote.close()
            assert local.poll(60), "peer did not respond"
            value = local.recv()
            assert "error" not in value, value
            child.join(20)
            assert not child.is_alive() and child.exitcode == 0
            return value
        finally:
            local.close(); remote.close()
    try:
        worker = run(frame_worker_peer)
        assert worker["decodes"] == 1 and worker["checkedout"] == 0
        frame = worker["payload"]["preview_frame_ref"]
        api = run(frame_api_peer, case_id, frame)
        assert len({os.getpid(), worker["pid"], api["pid"]}) == 3
        assert api["foreign"] == api["exact"] == 404
        assert all(ref is None for ref in api["thumbs"])  # actual Case consumer is still absent
        with queue.begin() as conn:
            with RecordingService(ConnectionRecordingRepository(conn, storage_root=root)) as recording:
                content = recording.read_owned_frame_image(case_id, frame).content
                assert api["sha256"] == hashlib.sha256(content).hexdigest()
    finally:
        for child in children:
            if child.is_alive(): child.terminate(); child.join(10)
        assert all(not child.is_alive() for child in children)


def test_crash_before_t1_may_decode_again_in_a_new_attempt(queue, tmp_path, monkeypatch):
    from daesingo.common.jobs.sweep import sweep_expired
    _, root, _, startup = prepare(queue, tmp_path, monkeypatch)
    original, decodes = FfmpegFrameExtractor.extract, []
    def extract(self, *args):
        assert queue.pool.checkedout() == 0
        decodes.append(True)
        return original(self, *args)
    monkeypatch.setattr(FfmpegFrameExtractor, "extract", extract)
    registry, reflector = frame_registry(queue, startup), StoredCaseReflector(storage_root=root)
    first = compose_worker(engine=queue, startup=startup, registry=registry, stop=Event(), reflector=reflector)
    def crash(*args): raise SystemExit("test crash before T1")
    first.record = crash
    with pytest.raises(SystemExit): first.run()
    assert decodes == [True]
    with queue.begin() as conn:
        old = conn.execute(sa.select(job_execution).where(job_execution.c.kind == "INCIDENT_CLIP_BUILD")).mappings().one()
        assert old["status"] == "RUNNING" and old["produced"] == []
        conn.execute(job_execution.update().where(job_execution.c.execution_id == old["execution_id"]).values(
            lease_expires_at=sa.text("DATE_SUB(NOW(6), INTERVAL 1 SECOND)")))
        retry = sweep_expired(conn, old["execution_id"], first.settings)
        assert retry.reason == "RETRIED"
        conn.execute(job_execution.update().where(job_execution.c.execution_id == retry.retry_execution_id).values(
            available_at=sa.func.now(6)))
    stop = Event()
    def invoke(ctx):
        try: return registry.dispatch(ctx)
        finally: stop.set()
    compose_worker(engine=queue, startup=startup, registry=KindRegistry({"INCIDENT_CLIP_BUILD": invoke}),
        stop=stop, reflector=reflector).run()
    assert decodes == [True, True]
    redeliver_once(queue, reflector, sleep=lambda seconds: None)
    assert decodes == [True, True] and queue.pool.checkedout() == 0
