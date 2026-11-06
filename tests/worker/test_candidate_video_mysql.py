"""Candidate video preview on real MySQL: public command → real worker/FFmpeg → T1/T2 → stored bytes.

Only external provider HTTP is faked (the incident clip ``prepare`` seed). MySQL, Case store,
enqueue/claim, preview handler, Recording/FFmpeg, T1/T2 and the API video loader are real.
IDs refer to docs/superpowers/plans/2026-11-03-candidate-video-real-test-plan.md.
"""
import hashlib
import json
import subprocess
from io import StringIO
from threading import Event

import pytest
import sqlalchemy as sa

from daesingo.common.jobs.produced import produced_objects
from daesingo.common.jobs.redelivery import redeliver_once
from daesingo.common.jobs.schema import job_execution
from daesingo.recording import (ConnectionRecordingRepository, LocalIncidentMaterializer,
                                RecordingCapabilityError, RecordingService)
from daesingo.worker.case_composition import StoredCaseReflector, stored_case_store
from daesingo.worker.composition import compose_worker
from daesingo.worker.composition_root import compose_registry
from daesingo.worker.registry import KindRegistry
from test_incident_clip_mysql import prepare
from test_worker_mysql import queue  # noqa: F401

pytestmark = pytest.mark.mysql
KIND = "CANDIDATE_VIDEO_PREVIEW"
# Fields a preview may change; everything else in the CaseView must stay identical (DB-07).
VOLATILE = {"case_rev", "running_jobs"}


def _client(monkeypatch, tmp_path, *, raise_server_exceptions=True):
    from fastapi.testclient import TestClient
    from daesingo.api.app import create_app
    from daesingo.api.bootstrap import bootstrap as api_bootstrap
    monkeypatch.setenv("DAESINGO_ENV_FILE", str(tmp_path / "peer.env"))
    return TestClient(create_app(startup=api_bootstrap(revision="test", stream=StringIO())),
                      raise_server_exceptions=raise_server_exceptions)


def _view(client, case_id):
    response = client.get(f"/cases/{case_id}/view")
    assert response.status_code == 200
    return response.json()


def _request(client, case_id, candidate_id):
    view = _view(client, case_id)
    return client.post(f"/cases/{case_id}/commands", json={"case_id": case_id, "expected_case_rev": view["case_rev"],
        "kind": "REQUEST_CANDIDATE_VIDEO_PREVIEW", "payload": {"candidate_id": candidate_id}})


def _stable(view):
    out = {k: v for k, v in view.items() if k not in VOLATILE}
    out["candidates"] = [{k: v for k, v in c.items() if k != "video_preview"} for c in view["candidates"]]
    return out


def _jobs(queue, kind=None):
    with queue.begin() as conn:
        query = sa.select(job_execution).order_by(job_execution.c.queued_at, job_execution.c.attempt, job_execution.c.execution_id)
        if kind:
            query = query.where(job_execution.c.kind == kind)
        return [dict(r) for r in conn.execute(query).mappings()]


def _run(queue, startup, root, kinds, count, *, engine=None):
    """Run the real worker loop until ``count`` executions of ``kinds`` were dispatched."""
    engine = engine or queue
    registry, stop, seen = compose_registry(engine=engine, startup=startup), Event(), []
    def invoke(ctx):
        seen.append(ctx.kind)
        try:
            return registry.dispatch(ctx)
        finally:
            if len(seen) >= count:
                stop.set()
    compose_worker(engine=engine, startup=startup, registry=KindRegistry({k: invoke for k in kinds}),
                   stop=stop, reflector=StoredCaseReflector(storage_root=root), sleep=lambda s: None).run()
    return seen


def _settle_evidence(queue, startup, root, case_id):
    """Finish the selected candidate's clip, then cancel OCR so only preview jobs remain queued."""
    from daesingo.common.jobs.cancel import request_cancel
    _run(queue, startup, root, {"INCIDENT_CLIP_BUILD"}, 1)
    with queue.begin() as conn:
        case = stored_case_store(conn, storage_root=root).get_case(case_id)
        request_cancel(conn, [j["job_id"] for j in case.job_records if j["kind"] in {"PLATE_READ", "OVERLAY_TIME_READ"}])
        queued = conn.execute(sa.select(job_execution.c.kind).where(job_execution.c.status == "QUEUED")).scalars().all()
    assert queued == [], queued


def _settle_with_readouts(queue, tmp_path, startup, root):
    """Finish the selected clip and both readouts (offline OCR, real worker path) so the Case is idle."""
    import multiprocessing
    from tests.e2e_runtime.production_processes import worker_peer
    _run(queue, startup, root, {"INCIDENT_CLIP_BUILD"}, 1)
    for _ in range(2):
        with queue.connect() as conn:
            kind = conn.scalar(sa.select(job_execution.c.kind).where(job_execution.c.status == "QUEUED")
                .order_by(job_execution.c.available_at, job_execution.c.execution_id).limit(1))
        assert kind in {"PLATE_READ", "OVERLAY_TIME_READ"}, kind
        incoming, outgoing = multiprocessing.Pipe()
        worker_peer(outgoing, str(tmp_path / "peer.env"), "clip_readout_ok", kind)
        result = incoming.recv()
        assert "error" not in result and result["terminals"][0]["status"] == "SUCCEEDED", result


@pytest.fixture
def counted(monkeypatch, queue):
    builds, encodes = [], []
    original_build, original_encode = RecordingService.build_incident_clip, LocalIncidentMaterializer.materialize
    def build(service, resolution, options=None):
        assert queue.pool.checkedout() == 0
        builds.append(resolution)
        return original_build(service, resolution, options)
    def encode(materializer, *args):
        assert queue.pool.checkedout() == 0
        encodes.append(True)
        return original_encode(materializer, *args)
    monkeypatch.setattr(RecordingService, "build_incident_clip", build)
    monkeypatch.setattr(LocalIncidentMaterializer, "materialize", encode)
    return builds, encodes


@pytest.mark.parametrize("count", [0, 1, 2, 3, 5])
@pytest.mark.mysql_check("candidate_video", "counts")
def test_db01_cards_match_candidates_and_only_top_three_are_eligible(queue, tmp_path, monkeypatch, count):
    case_id, *_ = prepare(queue, tmp_path, monkeypatch, frame_candidates=count)
    with _client(monkeypatch, tmp_path) as client:
        view = _view(client, case_id)
    assert len(view["candidates"]) == count
    statuses = [c["video_preview"]["status"] for c in sorted(view["candidates"], key=lambda c: c["rank"])]
    assert statuses == ["NOT_REQUESTED"] * min(count, 3) + ["UNAVAILABLE"] * max(count - 3, 0)
    assert [c["rank"] for c in sorted(view["candidates"], key=lambda c: c["rank"])] == list(range(1, count + 1))


@pytest.mark.mysql_check("candidate_video", "end_to_end")
def test_db02_to_db07_request_build_reuse_and_report_untouched(queue, tmp_path, monkeypatch, counted):
    builds, encodes = counted
    case_id, root, _, startup = prepare(queue, tmp_path, monkeypatch, frame_candidates=5)
    _settle_evidence(queue, startup, root, case_id)
    builds.clear(); encodes.clear()
    with _client(monkeypatch, tmp_path) as client:
        before = _view(client, case_id)
        by_rank = {c["rank"]: c for c in before["candidates"]}
        other_jobs = [(j["job_id"], j["status"]) for j in _jobs(queue) if j["kind"] != KIND]

        # DB-03: rank 4/5 and unknown targets are refused without new jobs.
        for target in (by_rank[4]["candidate_id"], by_rank[5]["candidate_id"], "unknown-candidate"):
            assert _request(client, case_id, target).status_code >= 400
        assert _jobs(queue, KIND) == []

        # DB-02/DB-05: rank 2 and 3 each get exactly one preview job; repeating while PREPARING is a no-op (DB-04).
        for rank in (2, 3, 2):
            assert _request(client, case_id, by_rank[rank]["candidate_id"]).status_code < 300
        jobs = _jobs(queue, KIND)
        assert len(jobs) == 2
        preparing = {c["rank"]: c["video_preview"]["status"] for c in _view(client, case_id)["candidates"]}
        assert preparing == {1: "NOT_REQUESTED", 2: "PREPARING", 3: "PREPARING", 4: "UNAVAILABLE", 5: "UNAVAILABLE"}
        with queue.begin() as conn:
            facade = stored_case_store(conn, storage_root=root)
            case = facade.get_case(case_id)
            for job in jobs:
                fixed = facade.observation_input(case_id, job["job_id"])
                candidate = next(c for c in case.candidates if c.candidate_id == fixed["candidate_id"])
                assert candidate.rank in {2, 3}
                assert fixed["generation_job_id"] == case.current_generation_job_id()
                assert fixed["span"] == candidate.span
                assert fixed["video_stream_refs"] == [s["video_stream_ref"] for s in case.sources if s.get("video_stream_ref")]

        # Real worker: both complete, neither supersedes the other (DB-05), connection never held while encoding.
        assert sorted(_run(queue, startup, root, {KIND}, 2)) == [KIND, KIND]
        assert len(builds) == 2 and len(encodes) == 2

        # DB-06: a fresh connection sees READY with distinct, durable clips.
        after = _view(client, case_id)
        ready = {c["rank"]: c["video_preview"] for c in after["candidates"]}
        assert ready[2]["status"] == ready[3]["status"] == "READY"
        assert ready[2]["clip_ref"] and ready[3]["clip_ref"] and ready[2]["clip_ref"] != ready[3]["clip_ref"]
        assert ready[1]["status"] == "NOT_REQUESTED"

        # DB-04: re-requesting a READY preview and T2 redelivery create no job and no encode.
        assert _request(client, case_id, by_rank[2]["candidate_id"]).status_code < 300
        redeliver_once(queue, StoredCaseReflector(storage_root=root), sleep=lambda s: None)
        assert len(_jobs(queue, KIND)) == 2 and len(builds) == 2 and len(encodes) == 2

        # DB-07/DB-08: selection, answers, evidence and package are unchanged; no Fine/OCR/export was issued.
        assert _stable(after) == _stable(before)
        assert [(j["job_id"], j["status"]) for j in _jobs(queue) if j["kind"] != KIND] == other_jobs
        assert all(j["status"] == "SUCCEEDED" and j["case_applied_at"] is not None for j in _jobs(queue, KIND))

        # HTTP: stored MP4 bytes decode and Range is honoured; a foreign ref is 404.
        url = f"/cases/{case_id}/candidate-videos/{ready[2]['clip_ref']}"
        full = client.get(url)
        assert full.status_code == 200 and full.headers["content-type"] == "video/mp4" and len(full.content) > 0
        part = client.get(url, headers={"Range": "bytes=0-9"})
        assert part.status_code == 206 and part.content == full.content[:10]
        assert part.headers["content-range"] == f"bytes 0-9/{len(full.content)}"
        assert client.get(f"/cases/{case_id}/candidate-videos/not-a-current-ref").status_code == 404
        assert len(builds) == 2, "GET must never encode"
    video = tmp_path / "preview.mp4"
    video.write_bytes(full.content)
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json",
                                       str(video)], check=True, capture_output=True, timeout=30).stdout)
    assert float(probe["format"]["duration"]) > 0
    with queue.begin() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(produced_objects)
                           .where(produced_objects.c.job_kind == KIND)) == 2
    assert queue.pool.checkedout() == 0
    print("preview sha256", hashlib.sha256(full.content).hexdigest(), len(full.content))


@pytest.mark.mysql_check("candidate_video", "failure_local_retry")
def test_rc05_failed_preview_is_card_local_and_explicit_retry_succeeds(queue, tmp_path, monkeypatch, counted):
    builds, encodes = counted
    case_id, root, _, startup = prepare(queue, tmp_path, monkeypatch, frame_candidates=3)
    _settle_evidence(queue, startup, root, case_id)
    wrapped = LocalIncidentMaterializer.materialize
    failures = []
    def fail_first(materializer, *args):
        if not failures:
            failures.append(True)
            raise RecordingCapabilityError("INCIDENT_CLIP_BUILD_FAILED", "probe failure")
        return wrapped(materializer, *args)
    monkeypatch.setattr(LocalIncidentMaterializer, "materialize", fail_first)
    with _client(monkeypatch, tmp_path) as client:
        before = _view(client, case_id)
        by_rank = {c["rank"]: c["candidate_id"] for c in before["candidates"]}
        assert _request(client, case_id, by_rank[2]).status_code < 300
        _run(queue, startup, root, {KIND}, 1)
        assert _request(client, case_id, by_rank[3]).status_code < 300
        _run(queue, startup, root, {KIND}, 1)
        state = {c["rank"]: c["video_preview"]["status"] for c in _view(client, case_id)["candidates"]}
        assert state == {1: "NOT_REQUESTED", 2: "FAILED", 3: "READY"}
        assert _request(client, case_id, by_rank[2]).status_code < 300  # explicit retry → new job
        _run(queue, startup, root, {KIND}, 1)
        after = _view(client, case_id)
        assert {c["rank"]: c["video_preview"]["status"] for c in after["candidates"]} == {1: "NOT_REQUESTED", 2: "READY", 3: "READY"}
        assert _stable(after) == _stable(before)
    statuses = [j["status"] for j in _jobs(queue, KIND)]
    assert statuses == ["FAILED", "SUCCEEDED", "SUCCEEDED"]


@pytest.mark.parametrize("fault", ["t1_rollback", "t2_rollback", "t2_redelivery"])
@pytest.mark.mysql_check("candidate_video", "t1_t2_faults")
def test_rc03_rc04_faults_end_ready_without_extra_encode(queue, tmp_path, monkeypatch, counted, fault):
    builds, encodes = counted
    case_id, root, _, startup = prepare(queue, tmp_path, monkeypatch, frame_candidates=2)
    _settle_evidence(queue, startup, root, case_id)
    builds.clear(); encodes.clear()
    with _client(monkeypatch, tmp_path) as client:
        rank2 = next(c["candidate_id"] for c in _view(client, case_id)["candidates"] if c["rank"] == 2)
        assert _request(client, case_id, rank2).status_code < 300
        injected = []
        def after_write(conn, cursor, sql, *args):
            target = "UPDATE CASES" if fault.startswith("t2_") else "INSERT INTO PRODUCED_OBJECTS"
            if not injected and sql.upper().startswith(target):
                injected.append(True)
                if fault.endswith("rollback"):
                    raise sa.exc.OperationalError("probe", {}, Exception(1213, "deadlock"))
                raise ValueError("T2 interruption")
        sa.event.listen(queue, "after_cursor_execute", after_write)
        try:
            _run(queue, startup, root, {KIND}, 1)
            redeliver_once(queue, StoredCaseReflector(storage_root=root), sleep=lambda s: None)
        finally:
            sa.event.remove(queue, "after_cursor_execute", after_write)
        assert injected
        # The worker retries the failed transaction with the same handler result: one encode in every case.
        assert len(builds) == len(encodes) == 1
        preview = {c["rank"]: c["video_preview"] for c in _view(client, case_id)["candidates"]}
        assert preview[2]["status"] == "READY" and preview[2]["clip_ref"]
        assert client.get(f"/cases/{case_id}/candidate-videos/{preview[2]['clip_ref']}").status_code == 200
    applied = [j for j in _jobs(queue, KIND) if j["status"] == "SUCCEEDED"]
    assert len(applied) == 1 and applied[0]["case_applied_at"] is not None
    assert queue.pool.checkedout() == 0
    print("fault", fault, "builds", len(builds), "encodes", len(encodes),
          "attempts", [(j["attempt"], j["status"]) for j in _jobs(queue, KIND)])


@pytest.mark.mysql_check("candidate_video", "chain_boundary")
def test_db09_preview_across_two_source_files_decodes(queue, tmp_path, monkeypatch, counted):
    builds, encodes = counted
    case_id, root, _, startup = prepare(queue, tmp_path, monkeypatch, multisource=True)
    _settle_evidence(queue, startup, root, case_id)
    builds.clear(); encodes.clear()
    with _client(monkeypatch, tmp_path) as client:
        rank1 = next(c for c in _view(client, case_id)["candidates"] if c["rank"] == 1)
        assert _request(client, case_id, rank1["candidate_id"]).status_code < 300
        _run(queue, startup, root, {KIND}, 1)
        preview = next(c for c in _view(client, case_id)["candidates"] if c["rank"] == 1)["video_preview"]
        assert preview["status"] == "READY"
        body = client.get(f"/cases/{case_id}/candidate-videos/{preview['clip_ref']}").content
    assert len(builds) == 1 and len(builds[0].spans) == 2, "span must cross the file boundary"
    with queue.begin() as conn, RecordingService(ConnectionRecordingRepository(conn, storage_root=root)) as recording:
        span = next(c.span for c in stored_case_store(conn, storage_root=root).get_case(case_id).candidates
                    if c.candidate_id == rank1["candidate_id"])
        clip = recording.get_incident_clip(preview["clip_ref"])
        assert len(clip.source_provenance.asset_spans) == 2
        assert clip.source_provenance.requested_range.start_sec == span["start_ms"] / 1000
        assert clip.source_provenance.requested_range.end_sec == span["end_ms"] / 1000
    video = tmp_path / "chain.mp4"
    video.write_bytes(body)
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"], check=True, capture_output=True, timeout=30)


@pytest.mark.mysql_check("candidate_video", "crash_before_t1")
def test_rc02_crash_before_t1_rebuilds_once_then_t2_replay_does_not(queue, tmp_path, monkeypatch, counted):
    from daesingo.common.jobs.sweep import sweep_expired
    builds, encodes = counted
    case_id, root, _, startup = prepare(queue, tmp_path, monkeypatch, frame_candidates=2)
    _settle_evidence(queue, startup, root, case_id)
    builds.clear(); encodes.clear()
    with _client(monkeypatch, tmp_path) as client:
        rank2 = next(c["candidate_id"] for c in _view(client, case_id)["candidates"] if c["rank"] == 2)
        assert _request(client, case_id, rank2).status_code < 300
    reflector = StoredCaseReflector(storage_root=root)
    registry = compose_registry(engine=queue, startup=startup)
    first = compose_worker(engine=queue, startup=startup, registry=registry, stop=Event(), reflector=reflector)
    def crash_before_t1(*args):
        raise SystemExit("test crash before terminal transaction")
    first.record = crash_before_t1
    with pytest.raises(SystemExit):
        first.run()
    assert len(builds) == 1
    with queue.begin() as conn:
        old = conn.execute(sa.select(job_execution).where(job_execution.c.kind == KIND)).mappings().one()
        assert old["status"] == "RUNNING" and old["produced"] == []
        conn.execute(job_execution.update().where(job_execution.c.execution_id == old["execution_id"]).values(
            lease_expires_at=sa.text("DATE_SUB(NOW(6), INTERVAL 1 SECOND)")))
        outcome = sweep_expired(conn, old["execution_id"], first.settings)
        assert outcome.reason == "RETRIED"
        conn.execute(job_execution.update().where(job_execution.c.execution_id == outcome.retry_execution_id)
                     .values(available_at=sa.func.now(6)))
    _run(queue, startup, root, {KIND}, 1)
    assert len(builds) == 2  # the new attempt may re-encode: nothing was durable before T1
    redeliver_once(queue, reflector, sleep=lambda s: None)
    assert len(builds) == 2
    rows = _jobs(queue, KIND)
    assert [(r["attempt"], r["status"]) for r in rows] == [(1, "STALE"), (2, "SUCCEEDED")]
    with _client(monkeypatch, tmp_path) as client:
        preview = next(c for c in _view(client, case_id)["candidates"] if c["rank"] == 2)["video_preview"]
        assert preview["status"] == "READY"
    assert queue.pool.checkedout() == 0


def _ready(queue, tmp_path, monkeypatch, *, count=2, rank=2, raise_server_exceptions=True):
    """Seed a case whose rank-``rank`` preview is READY; returns an open API client too."""
    case_id, root, _, startup = prepare(queue, tmp_path, monkeypatch, frame_candidates=count)
    _settle_evidence(queue, startup, root, case_id)
    client = _client(monkeypatch, tmp_path, raise_server_exceptions=raise_server_exceptions).__enter__()
    target = next(c["candidate_id"] for c in _view(client, case_id)["candidates"] if c["rank"] == rank)
    assert _request(client, case_id, target).status_code < 300
    _run(queue, startup, root, {KIND}, 1)
    preview = next(c for c in _view(client, case_id)["candidates"] if c["rank"] == rank)["video_preview"]
    assert preview["status"] == "READY"
    return client, case_id, root, startup, preview["clip_ref"]


@pytest.mark.parametrize("damage", ["chunks_missing", "chunk_changed", "disconnect", "pool"])
@pytest.mark.mysql_check("candidate_video", "storage_damage")
def test_rc07_stored_clip_damage_is_bounded_and_never_regenerates(queue, tmp_path, monkeypatch, damage):
    from daesingo.recording import mysql_repository as repo
    client, case_id, root, startup, clip_ref = _ready(queue, tmp_path, monkeypatch, raise_server_exceptions=False)
    with client:
        jobs_before = len(_jobs(queue))
        condition = sa.and_(repo.chunks.c.kind == "incident_clip", repo.chunks.c.entry_key == repo._key(clip_ref))
        with queue.begin() as conn:
            if damage == "chunks_missing":
                assert conn.execute(repo.chunks.delete().where(condition)).rowcount >= 1
            if damage == "chunk_changed":
                first = conn.execute(sa.select(repo.chunks.c.content).where(condition, repo.chunks.c.chunk_index == 0)).scalar_one()
                changed = bytes([first[0] ^ 0xFF]) + first[1:]
                conn.execute(repo.chunks.update().where(condition, repo.chunks.c.chunk_index == 0).values(content=changed))
        url = f"/cases/{case_id}/candidate-videos/{clip_ref}"
        held = []
        if damage == "disconnect":  # the API's own connection is killed mid-read (same as test_assets_mysql)
            original = RecordingService.open_incident_video
            def killed(self, ref):
                identity = self._repository._connection.exec_driver_sql("SELECT CONNECTION_ID()").scalar_one()
                with queue.connect() as other:
                    other.exec_driver_sql(f"KILL CONNECTION {identity}")
                return original(self, ref)
            monkeypatch.setattr(RecordingService, "open_incident_video", killed)
        if damage == "pool":
            engine = client.app.state.composition.engine
            held = [engine.connect() for _ in range(engine.pool.size() + engine.pool._max_overflow)]
        try:
            response = client.get(url)
        finally:
            for conn in held:
                conn.close()
        monkeypatch.undo() if damage == "disconnect" else None
        if damage in {"disconnect", "pool"}:
            assert client.get(url).status_code == 200, "next read recovers"
        view = _view(client, case_id)
    status = next(c for c in view["candidates"] if c["rank"] == 2)["video_preview"]["status"]
    print("RC07", damage, response.status_code, response.text[:120].replace("\n", " "), "view", status)
    assert response.status_code in {404, 503}, (response.status_code, response.text[:200])
    assert "Traceback" not in response.text and str(root) not in response.text
    assert len(_jobs(queue)) == jobs_before, "no automatic regeneration"


@pytest.mark.mysql_check("candidate_video", "source_lost")
def test_rc07_source_lost_before_build_fails_card_not_stuck(queue, tmp_path, monkeypatch):
    case_id, root, _, startup = prepare(queue, tmp_path, monkeypatch, frame_candidates=2)
    _settle_evidence(queue, startup, root, case_id)
    with _client(monkeypatch, tmp_path) as client:
        before = _view(client, case_id)
        rank2 = next(c["candidate_id"] for c in before["candidates"] if c["rank"] == 2)
        assert _request(client, case_id, rank2).status_code < 300
        sources = list((root / "source").iterdir())
        assert len(sources) == 1
        sources[0].unlink()  # the uploaded original disappears before the worker builds the preview
        _run(queue, startup, root, {KIND}, 1)
        after = _view(client, case_id)
        assert _request(client, case_id, rank2).status_code < 300  # explicit retry is still offered
    preview = next(c for c in after["candidates"] if c["rank"] == 2)["video_preview"]
    jobs = _jobs(queue, KIND)
    print("RC07 source", [(j["status"], j["failure_kind"]) for j in jobs], "view", preview["status"])
    assert jobs[0]["status"] == "FAILED" and preview["status"] == "FAILED"
    assert len(jobs) == 2 and jobs[1]["status"] == "QUEUED"
    assert _stable(after) == _stable(before)
    assert queue.pool.checkedout() == 0


@pytest.mark.mysql_check("candidate_video", "stale_generation")
def test_rc06_new_generation_isolates_late_preview(queue, tmp_path, monkeypatch):
    import multiprocessing
    from daesingo.case import command
    from tests.e2e_runtime.production_processes import worker_peer
    case_id, root, _, startup = prepare(queue, tmp_path, monkeypatch, frame_candidates=3)
    _settle_evidence(queue, startup, root, case_id)
    original = command._HANDLERS["EDIT_HINT"]
    # This state shows no 「설명 고치기」 exit; open only that screen gate. The generation change itself is real.
    monkeypatch.setitem(command._HANDLERS, "EDIT_HINT", lambda case, payload, view, **kw: original(
        case, payload, {**view, "notices": [*view["notices"], {"actions": ["EDIT_HINT"]}]}, **kw))
    with _client(monkeypatch, tmp_path) as client:
        old = _view(client, case_id)
        old_rank2 = next(c["candidate_id"] for c in old["candidates"] if c["rank"] == 2)
        assert _request(client, case_id, old_rank2).status_code < 300
        view = _view(client, case_id)
        edit = client.post(f"/cases/{case_id}/commands", json={"case_id": case_id, "expected_case_rev": view["case_rev"],
                                                                "kind": "EDIT_HINT", "payload": {"description": ""}})
        assert edit.status_code < 300, edit.text
        # The old preview job is claimed first and finishes (or refuses) after the generation moved on.
        _run(queue, startup, root, {KIND}, 1)
        old_job = _jobs(queue, KIND)[0]
        # A refused late preview is labelled as such, not as a handler crash.
        assert old_job["status"] != "FAILED" or old_job["failure_kind"] == "RUNTIME_PREVIEW_NOT_CURRENT"
        produced = []
        with queue.begin() as conn:
            if old_job["produced"]:
                from daesingo.common.jobs.produced import ProducedReader
                produced = [ProducedReader()(conn, KIND, tuple(old_job["produced"]))["incident_clip_ref"]]
        mid = _view(client, case_id)
        assert old_rank2 not in {c["candidate_id"] for c in mid["candidates"]}
        assert all(c["video_preview"]["clip_ref"] is None for c in mid["candidates"])
        for ref in produced:
            assert client.get(f"/cases/{case_id}/candidate-videos/{ref}").status_code == 404
        # The new generation's Coarse runs and its candidates can be previewed normally.
        incoming, outgoing = multiprocessing.Pipe()
        worker_peer(outgoing, str(tmp_path / "peer.env"), "clip_frames_3", "COARSE_SEARCH")
        assert "error" not in incoming.recv()
        new = _view(client, case_id)
        new_rank2 = next(c for c in new["candidates"] if c["rank"] == 2)
        response = _request(client, case_id, new_rank2["candidate_id"])
        print("RC06 old", old_job["status"], old_job["failure_kind"], "produced", produced,
              "new stage", new["stage"], "new rank2", new_rank2["video_preview"], "request", response.status_code)
        assert response.status_code < 300, response.text
        _run(queue, startup, root, {KIND}, 1)
        latest = next(c for c in _view(client, case_id)["candidates"] if c["rank"] == 2)["video_preview"]
    assert latest["status"] == "READY" and latest["clip_ref"] not in produced


@pytest.mark.mysql_check("candidate_video", "commit_unknown")
def test_rc03_t1_commit_response_lost_keeps_one_receipt(queue, tmp_path, monkeypatch, counted):
    from daesingo.common.config import DbSettings
    from daesingo.common.db import create_worker_engine
    from mysql_fault_proxy import CommitResponseProxy
    builds, encodes = counted
    case_id, root, _, startup = prepare(queue, tmp_path, monkeypatch, frame_candidates=2)
    _settle_evidence(queue, startup, root, case_id)
    builds.clear(); encodes.clear()
    with _client(monkeypatch, tmp_path) as client:
        rank2 = next(c["candidate_id"] for c in _view(client, case_id)["candidates"] if c["rank"] == 2)
        assert _request(client, case_id, rank2).status_code < 300
        with CommitResponseProxy(queue.url.host, queue.url.port) as proxy:
            engine = create_worker_engine(DbSettings(url=queue.url.set(host="127.0.0.1", port=proxy.port)
                .update_query_dict({"ssl_disabled": "true"}).render_as_string(hide_password=False)))
            armed = []
            def arm(conn, cursor, sql, *args):
                if not armed and sql.upper().startswith("INSERT INTO PRODUCED_OBJECTS"):
                    armed.append(True); proxy.arm()
            sa.event.listen(engine, "after_cursor_execute", arm)
            try:
                _run(queue, startup, root, {KIND}, 1, engine=engine)
                redeliver_once(engine, StoredCaseReflector(storage_root=root), sleep=lambda s: None)
                dropped = proxy.commit_ok_dropped
            finally:
                sa.event.remove(engine, "after_cursor_execute", arm)
                engine.dispose()
        preview = next(c for c in _view(client, case_id)["candidates"] if c["rank"] == 2)["video_preview"]
    assert armed and dropped == 1
    assert len(builds) == len(encodes) == 1
    assert preview["status"] == "READY"
    with queue.begin() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(produced_objects)
                           .where(produced_objects.c.job_kind == KIND)) == 1
    rows = _jobs(queue, KIND)
    assert len(rows) == 1 and rows[0]["status"] == "SUCCEEDED" and rows[0]["case_applied_at"] is not None


@pytest.mark.mysql_check("candidate_video", "parallel_fine")
def test_db08_preview_alongside_pending_fine_does_not_block_or_add_followups(queue, tmp_path, monkeypatch):
    import multiprocessing
    from tests.e2e_runtime.production_processes import worker_peer
    case_id, root, _, startup = prepare(queue, tmp_path, monkeypatch, frame_candidates=3)
    _settle_with_readouts(queue, tmp_path, startup, root)
    with _client(monkeypatch, tmp_path) as client:
        view = _view(client, case_id)
        by_rank = {c["rank"]: c["candidate_id"] for c in view["candidates"]}
        reselect = client.post(f"/cases/{case_id}/commands", json={"case_id": case_id, "expected_case_rev": view["case_rev"],
            "kind": "SELECT_OTHER_CANDIDATE", "payload": {"candidate_id": by_rank[2]}})
        assert reselect.status_code < 300, reselect.text
        fine = [j for j in _jobs(queue, "FINE_VERIFY") if j["status"] == "QUEUED"]
        assert len(fine) == 1
        preview = _request(client, case_id, by_rank[3])
        print("DB08 request while Fine queued", preview.status_code, preview.json().get("error"))
        assert preview.status_code < 300, preview.text
        kinds_before = sorted(j["kind"] for j in _jobs(queue) if j["kind"] != KIND)
        # This harness worker only serves previews, so park the Fine row while it runs (claim is kind-agnostic).
        fine_row = job_execution.c.execution_id == fine[0]["execution_id"]
        with queue.begin() as conn:
            conn.execute(job_execution.update().where(fine_row).values(
                available_at=sa.text("DATE_ADD(NOW(6), INTERVAL 1 HOUR)")))
        _run(queue, startup, root, {KIND}, 1)
        with queue.begin() as conn:
            conn.execute(job_execution.update().where(fine_row).values(available_at=fine[0]["available_at"]))
        assert sorted(j["kind"] for j in _jobs(queue) if j["kind"] != KIND) == kinds_before, "preview T2 issued follow-ups"
        assert [j["status"] for j in _jobs(queue, "FINE_VERIFY") if j["job_id"] == fine[0]["job_id"]] == ["QUEUED"]
        # The waiting Fine still runs and the selected candidate's clip build follows as usual.
        incoming, outgoing = multiprocessing.Pipe()
        worker_peer(outgoing, str(tmp_path / "peer.env"), "clip_frames_3", "FINE_VERIFY")
        assert "error" not in incoming.recv()
        after = _view(client, case_id)
    assert next(c for c in after["candidates"] if c["rank"] == 2)["selected"]
    assert next(c for c in after["candidates"] if c["rank"] == 3)["video_preview"]["status"] == "READY"
    clip_jobs = [j for j in _jobs(queue, "INCIDENT_CLIP_BUILD") if j["status"] == "QUEUED"]
    assert len(clip_jobs) == 1, "selected candidate's clip build was issued after Fine"


@pytest.mark.mysql_check("candidate_video", "range_concurrency")
def test_range_reads_hold_share_lock_briefly_and_never_strand_case_writes(queue, tmp_path, monkeypatch):
    """Review 3 (정철원): each Range read loads the whole MP4 under the Case share lock.

    While several seeks are inside that lock, a command and a T2 reflection on the same Case must
    finish; failed reads must return their connection; per-request memory is recorded."""
    import time
    import tracemalloc
    from concurrent.futures import ThreadPoolExecutor
    client, case_id, root, startup, clip_ref = _ready(queue, tmp_path, monkeypatch, count=3, rank=2,
                                                      raise_server_exceptions=False)
    url = f"/cases/{case_id}/candidate-videos/{clip_ref}"
    engine = client.app.state.composition.engine
    hold, readers = 0.4, 6
    original = RecordingService.open_incident_video
    inside, failures = [], {"mode": None}
    def slow(self, ref):
        inside.append(time.monotonic())
        time.sleep(hold)  # keep the share lock long enough that the writers below must wait on it
        if failures["mode"] == "crash":
            raise RuntimeError("injected read crash")
        if failures["mode"] == "unavailable":
            raise RecordingCapabilityError("UNAVAILABLE", "injected")
        return original(self, ref)
    with client:
        full = client.get(url).content
        size = len(full)
        monkeypatch.setattr(RecordingService, "open_incident_video", slow)
        ranges = [(i * size // readers, min(size - 1, (i + 1) * size // readers + 1023)) for i in range(readers)]
        def seek(span):
            response = client.get(url, headers={"Range": f"bytes={span[0]}-{span[1]}"})
            return span, response.status_code, response.content
        rank3 = next(c["candidate_id"] for c in _view(client, case_id)["candidates"] if c["rank"] == 3)
        with ThreadPoolExecutor(readers) as pool:
            futures = [pool.submit(seek, span) for span in ranges]
            while len(inside) < readers // 2:
                time.sleep(0.01)
            started = time.monotonic()
            command = _request(client, case_id, rank3)  # FOR UPDATE on the same Case
            command_sec = time.monotonic() - started
            started = time.monotonic()
            _run(queue, startup, root, {KIND}, 1)  # T1 + T2 reflection on the same Case
            t2_sec = time.monotonic() - started
            results = [f.result(timeout=60) for f in futures]
        assert command.status_code < 300, command.text
        for (start, end), status, body in results:
            assert status == 206 and body == full[start:end + 1]
        assert next(c for c in _view(client, case_id)["candidates"] if c["rank"] == 3)["video_preview"]["status"] == "READY"
        assert engine.pool.checkedout() == 0

        # Failed reads (crash → 500, storage → 404) during concurrent seeks give every connection back.
        for mode, expected in (("crash", 500), ("unavailable", 404)):
            failures["mode"] = mode
            with ThreadPoolExecutor(readers) as pool:
                statuses = [r[1] for r in pool.map(seek, ranges)]
            assert statuses == [expected] * readers, (mode, statuses)
            assert engine.pool.checkedout() == 0, mode
        failures["mode"] = None
        assert client.get(url).status_code == 200, "reads recover after failures"

        # Memory: every seek materialises the whole clip (plus the sliced response).
        monkeypatch.setattr(RecordingService, "open_incident_video", original)
        tracemalloc.start()
        client.get(url, headers={"Range": "bytes=0-1023"})
        single = tracemalloc.get_traced_memory()[1]
        tracemalloc.reset_peak()
        with ThreadPoolExecutor(readers) as pool:
            list(pool.map(seek, ranges))
        concurrent = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
    print(f"RANGE clip={size}B readers={readers} hold={hold}s command={command_sec:.2f}s t2={t2_sec:.2f}s "
          f"peak_single={single}B peak_{readers}x={concurrent}B")
    # Writers waited at most for the readers in flight, never a lock-wait timeout.
    assert command_sec < hold * readers + 5 and t2_sec < 60
