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


def _client(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from daesingo.api.app import create_app
    from daesingo.api.bootstrap import bootstrap as api_bootstrap
    monkeypatch.setenv("DAESINGO_ENV_FILE", str(tmp_path / "peer.env"))
    return TestClient(create_app(startup=api_bootstrap(revision="test", stream=StringIO())))


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
