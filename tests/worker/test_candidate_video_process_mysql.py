"""HTTP-01~04 and RC-01 against a real ``python -m daesingo.api`` process on a TCP port.

The READY preview is produced by the real worker path from test_candidate_video_mysql; the API under
test is a separate OS process that reads it back from MySQL and media storage, before and after restart.
"""
import hashlib
import os
import socket
import subprocess
import sys
import time

import httpx
import pytest

from tests.preview_writer_fixture import final_preview_writer  # noqa: F401
import sqlalchemy as sa

from daesingo.common.jobs.produced import produced_objects
from daesingo.common.jobs.schema import job_execution
from test_candidate_video_mysql import KIND, _client, _request, _run, _settle_evidence, _view
from test_incident_clip_mysql import prepare
from test_worker_mysql import queue  # noqa: F401

pytestmark = pytest.mark.mysql


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_api(env_file, port):
    env = {**os.environ, "DAESINGO_ENV_FILE": str(env_file), "PYTHONUTF8": "1"}
    proc = subprocess.Popen([sys.executable, "-m", "daesingo.api", "--revision", "test", "--port", str(port)],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise AssertionError(f"api exited {proc.returncode}: {proc.stderr.read()[-2000:]!r}")
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health/ready", timeout=2).status_code == 200:
                return proc
        except httpx.TransportError:
            pass
        time.sleep(.3)
    proc.kill()
    raise AssertionError("api did not become ready")


def _stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill(); proc.wait()


def _through_caddy(tmp_path, api_port, path, body):
    """Opt-in (Docker): deploy/Caddyfile's /cases* reverse proxy in front of the same API process."""
    image, name, port = os.environ["DAESINGO_CANDIDATE_VIDEO_CADDY_IMAGE"], f"cv554-caddy-{api_port}", _free_port()
    conf = tmp_path / "Caddyfile"
    conf.write_text(":80 {\n\t@api path /cases* /health*\n\thandle @api {\n\t\theader Cache-Control \"no-store\"\n"
                    f"\t\treverse_proxy host.docker.internal:{api_port}\n\t}}\n}}\n", encoding="utf-8")
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "-p", f"127.0.0.1:{port}:80",
                    "-v", f"{conf}:/etc/caddy/Caddyfile:ro", image], check=True, capture_output=True, timeout=120)
    try:
        url, deadline = f"http://127.0.0.1:{port}{path}", time.monotonic() + 30
        while True:
            try:
                full = httpx.get(url, timeout=10)
                break
            except httpx.TransportError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(.5)
        assert full.status_code == 200 and full.content == body
        assert full.headers["content-type"] == "video/mp4" and full.headers["accept-ranges"] == "bytes"
        assert "no-store" in full.headers["cache-control"]
        part = httpx.get(url, headers={"Range": "bytes=-7"}, timeout=10)
        assert part.status_code == 206 and part.content == body[-7:]
        assert part.headers["content-range"] == f"bytes {len(body) - 7}-{len(body) - 1}/{len(body)}"
        assert httpx.get(url, headers={"Range": f"bytes={len(body)}-"}, timeout=10).status_code == 416
        print("caddy", image, "cache-control", full.headers["cache-control"])
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=60)


def _counts(queue):
    with queue.begin() as conn:
        return (conn.scalar(sa.select(sa.func.count()).select_from(job_execution).where(job_execution.c.kind == KIND)),
                conn.scalar(sa.select(sa.func.count()).select_from(produced_objects).where(produced_objects.c.job_kind == KIND)))


@pytest.mark.mysql_check("candidate_video", "tcp_process")
def test_http01_04_rc01_tcp_api_process_ranges_ownership_and_restart(queue, tmp_path, monkeypatch):
    case_id, root, _, startup = prepare(queue, tmp_path, monkeypatch, frame_candidates=3)
    _settle_evidence(queue, startup, root, case_id)
    with _client(monkeypatch, tmp_path) as client:
        rank2 = next(c["candidate_id"] for c in _view(client, case_id)["candidates"] if c["rank"] == 2)
        assert _request(client, case_id, rank2).status_code < 300
        _run(queue, startup, root, {KIND}, 1)
        clip_ref = next(c for c in _view(client, case_id)["candidates"] if c["rank"] == 2)["video_preview"]["clip_ref"]
    assert clip_ref
    before = _counts(queue)
    env_file, port = tmp_path / "peer.env", _free_port()
    base = f"http://127.0.0.1:{port}"
    url = f"{base}/cases/{case_id}/candidate-videos/{clip_ref}"
    api = _start_api(env_file, port)
    first_pid = api.pid
    try:
        with httpx.Client(timeout=30) as http:
            # HTTP-01: inline private MP4 with ranges advertised.
            full = http.get(url)
            assert full.status_code == 200 and full.content
            assert full.headers["content-type"] == "video/mp4"
            assert full.headers["content-disposition"] == "inline"
            assert full.headers["cache-control"] == "private, no-store"
            assert full.headers["accept-ranges"] == "bytes"
            body, size = full.content, len(full.content)
            digest = hashlib.sha256(body).hexdigest()
            # HTTP-02: closed / open / suffix / clamped / unsatisfiable / malformed / multipart / If-Range.
            for header, want_status, want in [
                ("bytes=0-9", 206, body[:10]), (f"bytes={size - 5}-", 206, body[-5:]), ("bytes=-7", 206, body[-7:]),
                (f"bytes=0-{size * 10}", 206, body), (f"bytes={size}-", 416, b""), ("bytes=9-2", 416, b""),
                ("bytes=x-y", 200, body), ("bytes=0-1,4-5", 200, body),
            ]:
                r = http.get(url, headers={"Range": header})
                assert r.status_code == want_status, header
                if want_status != 416:
                    assert r.content == want, header
                if want_status == 206:
                    assert r.headers["content-range"].endswith(f"/{size}")
                if want_status == 416:
                    assert r.headers["content-range"] == f"bytes */{size}"
            assert http.get(url, headers={"Range": "bytes=0-9", "If-Range": '"old"'}).content == body
            # HTTP-03: another Case, unknown ref and malformed case id do not reveal bytes or internals.
            other = http.post(f"{base}/cases").json()["case_id"]
            for probe in (f"{base}/cases/{other}/candidate-videos/{clip_ref}",
                          f"{base}/cases/{case_id}/candidate-videos/unknown-ref",
                          f"{base}/cases/not-a-case/candidate-videos/{clip_ref}"):
                r = http.get(probe)
                assert r.status_code == 404, probe
                assert str(root) not in r.text and "Traceback" not in r.text and body[:16] not in r.content
            # HTTP-04: repeated reads and an aborted transfer never encode or create jobs.
            for _ in range(5):
                assert http.get(url, headers={"Range": "bytes=0-1023"}).status_code == 206
            with http.stream("GET", url) as streamed:
                next(streamed.iter_bytes(1024))  # abort mid-body
            assert http.get(url).content == body
        if os.environ.get("DAESINGO_CANDIDATE_VIDEO_CADDY_IMAGE"):
            _through_caddy(tmp_path, port, url.removeprefix(base), body)
    finally:
        _stop(api)
    assert _counts(queue) == before
    # RC-01: a brand-new API process (new PID) serves the same stored bytes; nothing is regenerated.
    api = _start_api(env_file, port)
    try:
        assert api.pid != first_pid
        again = httpx.get(url, timeout=30)
        assert again.status_code == 200 and hashlib.sha256(again.content).hexdigest() == digest
    finally:
        _stop(api)
    assert _counts(queue) == before
    print("tcp pids", first_pid, api.pid, "sha256", digest, "bytes", size)


def _hanging_preview_worker(env_file, marker):
    """Child process: a real worker that blocks inside the preview encode until it is killed."""
    import io
    from pathlib import Path
    from threading import Event
    from daesingo.common.db import create_worker_engine
    from daesingo.recording import LocalIncidentMaterializer
    from daesingo.worker.bootstrap import bootstrap
    from daesingo.worker.case_composition import StoredCaseReflector
    from daesingo.worker.composition import compose_worker
    from daesingo.worker.composition_root import compose_registry
    os.environ["DAESINGO_ENV_FILE"] = env_file
    startup = bootstrap(revision="test", stream=io.StringIO())
    engine = create_worker_engine(startup.config.db)
    def hang(materializer, *args):
        Path(marker).write_text(str(os.getpid()), encoding="utf-8")
        time.sleep(600)
    LocalIncidentMaterializer.materialize = hang
    registry = compose_registry(engine=engine, startup=startup)
    compose_worker(engine=engine, startup=startup, registry=registry, stop=Event(),
                   reflector=StoredCaseReflector(startup=startup)).run()


@pytest.mark.mysql_check("candidate_video", "process_kill")
def test_rc02_worker_process_killed_mid_encode_recovers_in_new_process(queue, tmp_path, monkeypatch):
    import multiprocessing
    from daesingo.common.jobs.redelivery import redeliver_once
    from daesingo.common.jobs.sweep import sweep_expired
    from daesingo.worker.case_composition import StoredCaseReflector
    from threading import Event
    from daesingo.worker.composition import compose_worker
    from daesingo.worker.composition_root import compose_registry
    from tests.e2e_runtime.production_processes import worker_peer
    case_id, root, _, startup = prepare(queue, tmp_path, monkeypatch, frame_candidates=2)
    _settle_evidence(queue, startup, root, case_id)
    env_file = str(tmp_path / "peer.env")
    with _client(monkeypatch, tmp_path) as client:
        rank2 = next(c["candidate_id"] for c in _view(client, case_id)["candidates"] if c["rank"] == 2)
        assert _request(client, case_id, rank2).status_code < 300
    mp = multiprocessing.get_context("spawn")
    marker = tmp_path / "encoding.pid"
    child = mp.Process(target=_hanging_preview_worker, args=(env_file, str(marker)))
    child.start()
    try:
        deadline = time.monotonic() + 90
        while not marker.exists():
            assert child.is_alive() and time.monotonic() < deadline, "child never reached the encode"
            time.sleep(.2)
        killed_pid = int(marker.read_text(encoding="utf-8"))
        child.kill()  # hard kill mid-encode: no T1, no cleanup code runs
        child.join(30)
    finally:
        if child.is_alive():
            child.kill(); child.join()
    with queue.begin() as conn:
        old = conn.execute(sa.select(job_execution).where(job_execution.c.kind == KIND)).mappings().one()
        assert old["status"] == "RUNNING" and old["produced"] == [] and old["case_applied_at"] is None
        conn.execute(job_execution.update().where(job_execution.c.execution_id == old["execution_id"]).values(
            lease_expires_at=sa.text("DATE_SUB(NOW(6), INTERVAL 1 SECOND)")))
        settings = compose_worker(engine=queue, startup=startup, registry=compose_registry(engine=queue, startup=startup),
                                  stop=Event(), reflector=StoredCaseReflector(storage_root=root)).settings
        outcome = sweep_expired(conn, old["execution_id"], settings)
        assert outcome.reason == "RETRIED"
        conn.execute(job_execution.update().where(job_execution.c.execution_id == outcome.retry_execution_id)
                     .values(available_at=sa.func.now(6)))
    incoming, outgoing = mp.Pipe()
    second = mp.Process(target=worker_peer, args=(outgoing, env_file, "clip", KIND))
    second.start(); outgoing.close()
    try:
        assert incoming.poll(120), "second worker did not report"
        result = incoming.recv()
    finally:
        second.join(30)
    assert "error" not in result, result
    assert result["pid"] not in {killed_pid, os.getpid()} and result["terminals"] == [{"status": "SUCCEEDED", "failure_kind": None}]
    assert result["clip_calls"] == 1 and result["pool_checkedout"] == 0
    redeliver_once(queue, StoredCaseReflector(storage_root=root), sleep=lambda s: None)
    rows = [dict(r) for r in queue.connect().execute(sa.select(job_execution).where(job_execution.c.kind == KIND)
            .order_by(job_execution.c.attempt)).mappings()]
    assert [(r["attempt"], r["status"]) for r in rows] == [(1, "STALE"), (2, "SUCCEEDED")]
    with _client(monkeypatch, tmp_path) as client:
        preview = next(c for c in _view(client, case_id)["candidates"] if c["rank"] == 2)["video_preview"]
        assert preview["status"] == "READY"
        assert client.get(f"/cases/{case_id}/candidate-videos/{preview['clip_ref']}").status_code == 200
    print("killed pid", killed_pid, "recovered pid", result["pid"])
