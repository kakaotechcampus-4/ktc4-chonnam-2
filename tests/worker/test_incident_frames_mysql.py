"""Production Case selection/positions, Recording, MySQL T1/T2 and HTTP."""
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
from daesingo.worker.incident_clip_composition import compose_incident_clip_registry
from test_incident_clip_mysql import prepare
from test_worker_mysql import queue  # noqa: F401

pytestmark = pytest.mark.mysql


@pytest.mark.parametrize("count,mode,want", [
    (0, "current", 0), (1, "current", 1), (2, "current", 2), (3, "current", 3),
    (4, "stale_second", 2), (4, "missing_span", 2),
    (3, "generation_before", 0), (3, "generation_after_t1", 3),
])
def test_production_top3_and_generation_boundaries(queue, tmp_path, monkeypatch, count, mode, want):
    from daesingo.case.preview_frame import (
        candidate_frame_position, current_candidate_frame_refs, current_preview_frame_ref,
    )
    from daesingo.case.view import build_case_view
    from daesingo.common.jobs.produced import produced_objects
    case_id, root, _, startup = prepare(queue, tmp_path, monkeypatch, frame_candidates=count)
    def change_generation(conn):
        facade = stored_case_store(conn, storage_root=root)
        case = facade.load_for_update(case_id)
        prior = next(j for j in case.job_records if j["kind"] == "COARSE_SEARCH")
        # Test fixture: a newer Coarse result has replaced this generation.
        case.job_records.append({**prior, "job_id": "next-generation"})
        case.settled_jobs["next-generation"] = "REFLECTED"
        facade.save(case)
    if mode in {"stale_second", "missing_span", "generation_before"}:
        with queue.begin() as conn:
            facade = stored_case_store(conn, storage_root=root)
            case = facade.load_for_update(case_id)
            if mode == "stale_second":
                case.candidates[1].stale_revision = True
            elif mode == "missing_span":
                case.candidates[1].span = None
            facade.save(case)
            if mode == "generation_before":
                change_generation(conn)
    original = FfmpegFrameExtractor.extract
    locators, decodes, resolutions = [], [], []
    resolve, span = RecordingService.resolve_frame, RecordingService.resolve_span
    def extract(self, *args):
        assert queue.pool.checkedout() == 0
        decodes.append(True)
        return original(self, *args)
    def resolve_frame(self, locator):
        assert queue.pool.checkedout() == 0
        locators.append(locator)
        return resolve(self, locator)
    def resolve_span(self, timeline, requested, **kwargs):
        assert queue.pool.checkedout() == 0
        result = span(self, timeline, requested, **kwargs)
        # build_incident_clip also resolves an internal TimeRange. Record the
        # public dict requests from the handler/issuer, with their own results.
        if isinstance(requested, dict):
            resolutions.append((requested.copy(), result.model_dump(mode="json")))
        return result
    monkeypatch.setattr(FfmpegFrameExtractor, "extract", extract)
    monkeypatch.setattr(RecordingService, "resolve_frame", resolve_frame)
    monkeypatch.setattr(RecordingService, "resolve_span", resolve_span)
    registry = compose_incident_clip_registry(engine=queue, startup=startup)
    stop = Event()
    def invoke(ctx):
        try:
            return registry.dispatch(ctx)
        finally:
            stop.set()
    actual = StoredCaseReflector(storage_root=root)
    class Reflector:
        changed = False
        def reflect(self, conn, incoming):
            if mode == "generation_after_t1" and not self.changed:
                # T1 is committed; Case receives a new generation before T2.
                with queue.begin() as other:
                    change_generation(other)
                self.changed = True
            return actual.reflect(conn, incoming)
    reflector = Reflector()
    compose_worker(engine=queue, startup=startup, registry=KindRegistry({"INCIDENT_CLIP_BUILD": invoke}),
        stop=stop, reflector=reflector, idle_wait=lambda seconds: stop.set()).run()
    redeliver_once(queue, reflector, sleep=lambda seconds: None)
    assert len(decodes) == len(locators) == want and queue.pool.checkedout() == 0
    with queue.begin() as conn:
        facade = stored_case_store(conn, storage_root=root)
        case = facade.get_case(case_id)
        view = build_case_view(case)
        if count == 0:
            assert case.candidates == [] and view["candidates"] == []
            assert not conn.scalar(sa.select(sa.func.count()).select_from(job_execution).where(
                job_execution.c.kind == "INCIDENT_CLIP_BUILD"))
            return
        row = conn.execute(sa.select(job_execution).where(job_execution.c.kind == "INCIDENT_CLIP_BUILD")).mappings().one()
        assert row["status"] == "SUCCEEDED" and row["case_applied_at"] is not None
        payload = worker_produced_reader()(conn, row["kind"], tuple(row["produced"]))
        assert len(payload["candidate_frame_refs"]) == want
        if want:
            chosen = [c for c in case.candidates if c.rank <= 3 and not c.stale_revision and c.span is not None]
            assert set(payload["candidate_frame_refs"]) == {c.candidate_id for c in chosen}
            assert all(isinstance(ref, str) and ref for ref in payload["candidate_frame_refs"].values())
            assert payload["preview_frame_ref"] == payload["candidate_frame_refs"][case.candidates[0].candidate_id]
            assert [request for request, _ in resolutions[1:]] == [
                {"start_sec": c.span["start_ms"] / 1000, "end_sec": c.span["end_ms"] / 1000} for c in chosen]
            # Case is authoritative for source-local positions, including float
            # arithmetic. Compare exact returned positions, never assume that
            # a source offset equals a timeline representative coordinate.
            assert [(p["media_stream_ref"], p["source_offset_sec"]) for p in locators] == [
                candidate_frame_position(resolution, c.span, c.representative_ms)
                for c, (_, resolution) in zip(chosen, resolutions[1:], strict=True)]
            # All other representatives are outside the selected clip's range.
            assert all(c.representative_ms > case.candidates[0].span["end_ms"] for c in chosen[1:])
        if mode.startswith("generation_"):
            assert current_candidate_frame_refs(case) == {} and current_preview_frame_ref(case) is None
            assert all(c["thumb_ref"] is None for c in view["candidates"])
            assert not any(j["kind"] in {"PLATE_READ", "OVERLAY_TIME_READ"} for j in case.job_records)
        else:
            assert current_candidate_frame_refs(case) == payload["candidate_frame_refs"]
            assert current_preview_frame_ref(case) == payload["preview_frame_ref"]
            assert {c["candidate_id"]: c["thumb_ref"] for c in view["candidates"] if c["thumb_ref"]} == payload["candidate_frame_refs"]
            assert len([j for j in case.job_records if j["kind"] in {"PLATE_READ", "OVERLAY_TIME_READ"}]) == 2
        assert conn.scalar(sa.select(sa.func.count()).select_from(produced_objects).where(
            produced_objects.c.job_kind == "INCIDENT_CLIP_BUILD")) == 1
        from daesingo.recording import ConnectionRecordingRepository
        with RecordingService(ConnectionRecordingRepository(conn, storage_root=root)) as recording:
            expected_images = {ref: recording.read_owned_frame_image(case_id, ref).content
                               for ref in payload["candidate_frame_refs"].values() if ref is not None}
    from fastapi.testclient import TestClient
    from daesingo.api.app import create_app
    from daesingo.api.bootstrap import bootstrap
    from io import StringIO
    def forbidden(*args, **kwargs): raise AssertionError("durable HTTP/View read decoded a frame")
    monkeypatch.setattr(FfmpegFrameExtractor, "extract", forbidden)
    with TestClient(create_app(startup=bootstrap(revision="test", stream=StringIO()))) as client:
        other = client.post("/cases").json()["case_id"]
        for ref, content in expected_images.items():
            response = client.get(f"/cases/{case_id}/frames/{ref}")
            assert response.status_code == 200 and response.content == content
            assert response.headers["content-type"] == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n")
            assert client.get(f"/cases/{other}/frames/{ref}").status_code == 404
            assert client.get(f"/cases/{case_id}%20/frames/{ref}").status_code == 404
        assert client.get(f"/cases/{case_id}/view").status_code == 200
    assert len(decodes) == want


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
    stop, registry = Event(), compose_incident_clip_registry(engine=queue, startup=startup)
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
        case = stored_case_store(conn, storage_root=root).get_case(case_id)
        outcome = case.observation_outcomes[row["job_id"]]
        assert outcome["preview_frame_ref"] == content["preview_frame_ref"]
        assert outcome["candidate_frame_refs"] == content["candidate_frame_refs"]
        from daesingo.case.preview_frame import current_preview_frame_ref
        from daesingo.case.view import build_case_view
        assert current_preview_frame_ref(case) == content["preview_frame_ref"]
        thumbs = {c["candidate_id"]: c["thumb_ref"] for c in build_case_view(case)["candidates"]}
        assert thumbs == content["candidate_frame_refs"]
        facade = stored_case_store(conn, storage_root=root)
        readouts = [j for j in case.job_records if j["kind"] in {"PLATE_READ", "OVERLAY_TIME_READ"}]
        assert {j["kind"] for j in readouts} == {"PLATE_READ", "OVERLAY_TIME_READ"} and len(readouts) == 2
        assert all(facade.observation_input(case_id, j["job_id"])["incident_clip_ref"] == content["incident_clip_ref"]
                   for j in readouts)
        from daesingo.common.jobs.execution import HandlerResult
        from daesingo.common.jobs.reflection import ReflectionInput, reflect_terminal
        replay = ReflectionInput(row["execution_id"], row["job_id"], row["case_id"], row["kind"], row["attempt"],
            HandlerResult(status=row["status"], produced=row["produced"]))
        assert reflect_terminal(conn, replay, reflector, row["trace_id"]).status == "ALREADY_APPLIED"
        from daesingo.recording import ConnectionRecordingRepository
        with RecordingService(ConnectionRecordingRepository(conn, storage_root=root)) as recording:
            assert recording.read_owned_frame_image(case_id, content["preview_frame_ref"]).content.startswith(b"\x89PNG")
    assert queue.pool.checkedout() == 0
    assert len(decodes) == len(resolves) == len(builds) == 1


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
    stop, registry = Event(), compose_incident_clip_registry(engine=queue, startup=startup)
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


@pytest.mark.parametrize("legacy", ["missing", "null"])
def test_historical_payload_is_consumed_without_frame_repair(queue, tmp_path, monkeypatch, legacy):
    from daesingo.common.jobs.produced import ProducedObject, produced_objects
    from daesingo.common.jobs.execution import HandlerResult
    from daesingo.case.preview_frame import current_preview_frame_ref
    from daesingo.case.view import build_case_view
    case_id, root, _, startup = prepare(queue, tmp_path, monkeypatch)
    registry = compose_incident_clip_registry(engine=queue, startup=startup)
    original = FfmpegFrameExtractor.extract
    decodes, snapshots = [], []
    def extract(self, *args):
        assert queue.pool.checkedout() == 0
        decodes.append(True)
        return original(self, *args)
    monkeypatch.setattr(FfmpegFrameExtractor, "extract", extract)
    stop = Event()
    def invoke(ctx):
        try:
            result = registry.dispatch(ctx)
            assert result.status == "SUCCEEDED"
            # Simulate the serialized shape from an older producer. Do not
            # rewrite a durable receipt or use a fake clip/Recording capability.
            payload = {"incident_clip_ref": result.objects[0].payload["incident_clip_ref"]}
            if legacy == "null": payload.update(preview_frame_ref=None, candidate_frame_refs=None)
            snapshots.append(payload.copy())
            return HandlerResult(objects=(ProducedObject(kind="incident_clip_result", payload=payload),))
        finally: stop.set()
    actual = StoredCaseReflector(storage_root=root)
    class Reflector:
        def reflect(self, conn, incoming):
            def forbidden(*args, **kwargs): raise AssertionError("T2 repaired a historical frame")
            monkeypatch.setattr(FfmpegFrameExtractor, "extract", forbidden)
            return actual.reflect(conn, incoming)
    reflector = Reflector()
    compose_worker(engine=queue, startup=startup, registry=KindRegistry({"INCIDENT_CLIP_BUILD": invoke}),
        stop=stop, reflector=reflector).run()
    redeliver_once(queue, reflector, sleep=lambda seconds: None)
    assert decodes == [True]
    with queue.begin() as conn:
        row = conn.execute(sa.select(job_execution).where(job_execution.c.kind == "INCIDENT_CLIP_BUILD")).mappings().one()
        assert row["status"] == "SUCCEEDED" and row["case_applied_at"] is not None
        raw = conn.execute(sa.select(produced_objects.c.payload).where(
            produced_objects.c.job_kind == "INCIDENT_CLIP_BUILD")).scalar_one()
        assert raw == snapshots[0]
        assert worker_produced_reader()(conn, row["kind"], tuple(row["produced"])) == {
            "incident_clip_ref": raw["incident_clip_ref"], "preview_frame_ref": None, "candidate_frame_refs": {}}
        case = stored_case_store(conn, storage_root=root).get_case(case_id)
        assert current_preview_frame_ref(case) is None
        assert case.observation_outcomes[row["job_id"]]["candidate_frame_refs"] == {}
        assert all(c["thumb_ref"] is None for c in build_case_view(case)["candidates"])
        assert len([j for j in case.job_records if j["kind"] in {"PLATE_READ", "OVERLAY_TIME_READ"}]) == 2
    assert queue.pool.checkedout() == 0


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
        stop, registry = Event(), compose_incident_clip_registry(engine=active, startup=startup)
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
        from tests.e2e_runtime.production_processes import worker_peer
        for kind in ("PLATE_READ", "OVERLAY_TIME_READ"):
            readout = run(worker_peer, "clip_readout_ok", kind)
            assert readout["http_calls"] == 0
            assert len(readout["readout_calls"]) == 1
            assert readout["readout_calls"][0][1] == worker["payload"]["incident_clip_ref"]
            assert readout["terminals"] == [{"status": "SUCCEEDED", "failure_kind": None}]
        api = run(frame_api_peer, case_id, frame)
        assert len({os.getpid(), worker["pid"], api["pid"]}) == 3
        assert api["foreign"] == api["exact"] == 404
        assert api["thumbs"] == [frame]
        assert api["preview_ref"] == frame
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
    registry = compose_incident_clip_registry(engine=queue, startup=startup)
    reflector = StoredCaseReflector(storage_root=root)
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
