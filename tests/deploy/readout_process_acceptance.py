"""Production module Worker + independent API peer + actual MySQL/Paddle T1/T2.

Mount this helper, readout_acceptance.py and production_processes.py into /opt.
Use an internal Docker network with a disposable MySQL; no tests enter the image.
"""
import json
import multiprocessing
import os
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from uuid import uuid4

import sqlalchemy as sa

from daesingo.common.db.migrate import upgrade_all
from daesingo.common.jobs.produced import ProducedReader
from daesingo.common.jobs.schema import job_execution
from daesingo.common.usage.schema import usage_record
from daesingo.worker.case_composition import stored_case_store
from production_processes import api_peer, worker_peer
from readout_acceptance import generate, cache_state


def receive(pipe):
    assert pipe.poll(90), "peer timeout"
    result = pipe.recv()
    assert "error" not in result, "peer failed"
    return result


def public(pipe, message):
    pipe.send(message)
    result = receive(pipe)
    assert result["status"] in (200, 201, 202)
    return result["body"]


def main():
    assert os.getuid() == os.getgid() == 10001
    control = sa.create_engine("mysql+pymysql://root@daesingo-issue468-mysql:3306/daesingo_test",
        isolation_level="AUTOCOMMIT")
    schema = "readout_test_" + uuid4().hex
    engine, api, worker, local = None, None, None, None
    before = cache_state()
    with control.connect() as conn:
        conn.exec_driver_sql(f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4")
    try:
        url = control.url.set(database=schema)
        upgrade_all(url)
        engine = sa.create_engine(url, hide_parameters=True)
        with TemporaryDirectory(prefix="readout-process-") as directory:
            root = Path(directory)
            media, temp = root / "media", root / "temp"
            media.mkdir(); temp.mkdir()
            source = generate(root, Path(sys.argv[1]))
            values = dict(DAESINGO_RUNTIME_DB_URL=url.render_as_string(hide_password=False),
                DAESINGO_RUNTIME_MEDIA_ROOT=str(media), DAESINGO_RUNTIME_API_TEMP_ROOT=str(temp),
                DAESINGO_RUNTIME_WORKER_TEMP_ROOT=str(temp), GEMINI_API_KEY="offline",
                DAESINGO_RECORDING_ANALYSIS_PROFILE_REF="acceptance", DAESINGO_RECORDING_ANALYSIS_HEIGHT="720",
                DAESINGO_RECORDING_ANALYSIS_PRESET="veryfast", DAESINGO_RECORDING_ANALYSIS_CRF="10",
                DAESINGO_RECORDING_INCIDENT_HEIGHT="720", DAESINGO_RECORDING_INCIDENT_PRESET="veryfast",
                DAESINGO_RECORDING_INCIDENT_CRF="10")
            env_file = root / "runtime.env"
            env_file.write_text("\n".join(f"{key}={value}" for key, value in values.items()))
            mp = multiprocessing.get_context("spawn")
            local, remote = mp.Pipe()
            api = mp.Process(target=api_peer, args=(remote, str(env_file)))
            api.start(); remote.close()
            api_pid = receive(local)["pid"]
            identity = public(local, ("POST", "/cases", None))["case_id"]
            uploaded = public(local, ("upload", f"/cases/{identity}/sources", str(source)))
            public(local, ("POST", f"/cases/{identity}/commands", dict(case_id=identity,
                expected_case_rev=uploaded["case_view"]["case_rev"], kind="START_ANALYSIS",
                payload={"description": "red signal"})))
            # Only Search is offline. Produce a real IncidentClip through durable T1/T2.
            for kind in ("HINT_EXTRACT", "COARSE_SEARCH", "FINE_VERIFY", "INCIDENT_CLIP_BUILD"):
                incoming, outgoing = mp.Pipe()
                peer = mp.Process(target=worker_peer, args=(outgoing, str(env_file), "clip", kind))
                peer.start(); outgoing.close()
                try:
                    receipt = receive(incoming)
                    assert receipt["terminals"] == [{"status": "SUCCEEDED", "failure_kind": None}]
                finally:
                    incoming.close()
                    peer.join(15)
                    if peer.is_alive(): peer.terminate(); peer.join(15)
                assert peer.exitcode == 0
            # No provider injection, patch, test Worker launcher or alternate main here.
            worker = subprocess.Popen([sys.executable, "-m", "daesingo.worker"],
                env={**os.environ, "DAESINGO_ENV_FILE": str(env_file)},
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            assert worker.pid not in {api_pid, os.getpid()}
            deadline = time.monotonic() + 180
            while True:
                with engine.connect() as conn:
                    rows = conn.execute(sa.select(job_execution).where(job_execution.c.kind.in_(
                        ("PLATE_READ", "OVERLAY_TIME_READ")))).mappings().all()
                assert len(rows) == 2
                assert all(r["status"] not in ("FAILED", "STALE", "CANCELLED") for r in rows), [
                    (r["kind"], r["status"], r["failure_kind"]) for r in rows]
                if all(r["status"] == "SUCCEEDED" and r["case_applied_at"] is not None for r in rows): break
                assert worker.poll() is None, "default Worker exited before Readout reflection"
                assert time.monotonic() < deadline, "Readout T1/T2 timeout"
                time.sleep(.25)
            worker.send_signal(signal.SIGTERM)
            stdout, stderr = worker.communicate(timeout=20)
            assert worker.returncode == 0 and stderr == "", (worker.returncode, len(stderr),
                [token for token in ("Traceback", "FatalError", "SIGTERM") if token in stderr])
            assert all(token not in stdout for token in (str(root), "Traceback", "PP-OCRv5", ".paddlex"))
            view = public(local, ("GET", f"/cases/{identity}/view", None))
            assert not view["running_jobs"] and view["evidence"] is not None
            with engine.connect() as conn:
                facade = stored_case_store(conn, storage_root=media)
                adapter = facade.adapter_for(facade.get_case(identity))
                assert len(adapter.get_plate_readouts()) == len(adapter.get_overlay_time_readouts()) == 1
                for row in rows:
                    assert row["failure_kind"] is None
                    payload = ProducedReader()(conn, row["kind"], tuple(row["produced"]))
                    assert payload["readout_run"]["outcome"] == "SUCCEEDED"
                    name = "plate_readout" if row["kind"] == "PLATE_READ" else "overlay_time_readout"
                    assert payload[name]["observation"]["status"] == "OK"
                    if name == "plate_readout":
                        assert payload[name]["observation"]["value"] == "12가3456", payload[name]["observation"]["value"]
                    usage = conn.execute(sa.select(usage_record).where(
                        usage_record.c.execution_ref == row["execution_id"])).mappings().one()
                    assert usage["run_ref"] == payload["readout_run"]["run_id"]
            local.send(("stop", None, None)); api.join(15)
            assert api.exitcode == 0
            assert {p.name for p in temp.iterdir()} <= {".runtime-cleanup-temp.lock"}
        assert cache_state() == before
        return {"default_worker": "PASS", "actual_paddle": "PASS", "separate_api": "PASS",
                "plate_t1_t2": "PASS", "overlay_t1_t2": "PASS", "uid": 10001}
    finally:
        if worker is not None and worker.poll() is None:
            worker.terminate()
            try: worker.communicate(timeout=20)
            except subprocess.TimeoutExpired: worker.kill(); worker.communicate()
        if api is not None and api.is_alive(): api.terminate(); api.join(15)
        if local is not None: local.close()
        if engine is not None: engine.dispose()
        with control.connect() as conn: conn.exec_driver_sql(f"DROP DATABASE `{schema}`")
        control.dispose()


if __name__ == "__main__":
    try:
        print(json.dumps(main(), sort_keys=True))
    except BaseException:
        print("readout process acceptance: FAIL", file=sys.stderr)
        raise SystemExit(1)
