"""Generated media, real MySQL and independent API/Worker OS processes."""
import multiprocessing
import os
import subprocess

import pytest

from daesingo.case import observation
from daesingo.common.jobs.repository import enqueue
from daesingo.common.jobs.produced import ProducedReader
from daesingo.worker.case_composition import stored_case_store
from production_processes import api_peer, worker_peer

pytestmark = pytest.mark.mysql


def receive(pipe, timeout=60):
    assert pipe.poll(timeout), "peer did not respond before deadline"
    message = pipe.recv()
    assert "error" not in message, message.get("error")
    return message


def public(message):
    assert message["status"] in {200, 201, 202}, message
    forbidden = {"execution_id", "attempt", "trace_id", "lease_owner", "claim_token", "lease_expires_at",
                 "heartbeat_at", "available_at", "case_applied_at", "queued_at", "started_at", "ended_at", "cancel_requested_at"}
    def check(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for item in value.values(): check(item)
        elif isinstance(value, list):
            for item in value: check(item)
    check(message["body"])
    return message["body"]


@pytest.mark.parametrize("scenario", ["normal", "partial", "failed", "fine_failed"])
@pytest.mark.mysql_check("search_process", "separate_api_worker")
def test_public_api_worker_search_t1_t2_across_processes(async_db, tmp_path, scenario):
    _, _, engine = async_db
    root = tmp_path / "storage"
    root.mkdir()
    api_temp, worker_temp = tmp_path / "api-temp", tmp_path / "worker-temp"
    api_temp.mkdir(); worker_temp.mkdir()
    video = tmp_path / "input.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
        "color=c=red:s=64x48:r=10:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
        check=True, capture_output=True, timeout=30)
    values = {"DAESINGO_RUNTIME_DB_URL": engine.url.render_as_string(hide_password=False),
        "DAESINGO_RUNTIME_MEDIA_ROOT": str(root), "DAESINGO_RUNTIME_API_TEMP_ROOT": str(api_temp),
        "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(worker_temp), "GEMINI_API_KEY": "offline-key",
        "DAESINGO_RECORDING_ANALYSIS_PROFILE_REF": "process-profile",
        "DAESINGO_RECORDING_ANALYSIS_HEIGHT": "240", "DAESINGO_RECORDING_ANALYSIS_PRESET": "veryfast",
        "DAESINGO_RECORDING_ANALYSIS_CRF": "23"}
    env_file = tmp_path / "process.env"
    env_file.write_text("\n".join(f"{k}={v}" for k, v in values.items()), encoding="utf-8")
    context = multiprocessing.get_context("spawn")
    local, remote = context.Pipe()
    api = context.Process(target=api_peer, args=(remote, str(env_file)))
    children = []
    api.start(); remote.close()
    try:
        api_pid = receive(local)["pid"]
        local.send(("POST", "/cases", None)); created = public(receive(local))
        identity = created["case_id"]
        local.send(("upload", f"/cases/{identity}/sources", str(video))); uploaded = public(receive(local))
        local.send(("POST", f"/cases/{identity}/commands", {"case_id": identity,
            "expected_case_rev": uploaded["case_view"]["case_rev"],
            "kind": "START_ANALYSIS", "payload": {"description": ""}}))
        accepted = public(receive(local))
        assert accepted["case_view"]["running_jobs"][0]["kind"] == "COARSE_SEARCH"
        def run_worker(kind):
            incoming, outgoing = context.Pipe()
            child = context.Process(target=worker_peer, args=(outgoing, str(env_file), scenario, kind))
            children.append(child); child.start(); outgoing.close()
            result = receive(incoming)
            incoming.close(); child.join(20)
            assert child.exitcode == 0 and not child.is_alive()
            assert result["pid"] not in {os.getpid(), api_pid}
            assert result["http_calls"] == 1 and result["pool_checkedout"] == 0
        run_worker("COARSE_SEARCH")
        local.send(("GET", f"/cases/{identity}/view", None)); view = public(receive(local))
        assert not view["running_jobs"]
        assert bool(view["candidates"]) == (scenario != "failed")
        if scenario != "failed":
            # Case owns selection/follow-up. Exercise its public aggregate entry;
            # Runtime must not invent automatic selection or downstream policy.
            with engine.begin() as conn:
                facade = stored_case_store(conn, storage_root=root)
                case = facade.load_for_update(identity)
                case.select_candidate(view["candidates"][0]["candidate_id"])
                fine = observation.issue_fine_for_selected(case)
                facade.save(case); enqueue(conn, [fine], "process-fine")
            run_worker("FINE_VERIFY")
            local.send(("GET", f"/cases/{identity}/view", None)); final_view = public(receive(local))
            assert not final_view["running_jobs"]
        with engine.begin() as conn:
            rows = conn.exec_driver_sql("SELECT execution_id,kind,status,produced,case_applied_at FROM job_execution ORDER BY queued_at").mappings().all()
            assert all(row["case_applied_at"] is not None for row in rows)
            assert rows[0]["status"] == ("FAILED" if scenario == "failed" else "SUCCEEDED")
            import json
            refs = json.loads(rows[0]["produced"]) if isinstance(rows[0]["produced"], str) else rows[0]["produced"]
            payload = ProducedReader()(conn, "COARSE_SEARCH", tuple(refs))
            assert payload["analysis_run"]["outcome"] == {"partial": "PARTIAL", "failed": "FAILED"}.get(scenario, "SUCCEEDED")
            if scenario == "fine_failed": assert rows[-1]["status"] == "FAILED"
    finally:
        if api.is_alive():
            try: local.send(("stop", None, None))
            except (EOFError, OSError): pass
        api.join(20)
        for child in [api, *children]:
            if child.is_alive(): child.terminate(); child.join(10)
        local.close()
    assert api.exitcode == 0
