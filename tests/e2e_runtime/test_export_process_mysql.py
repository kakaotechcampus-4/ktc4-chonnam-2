"""Full native media chain with independent API and fresh Worker processes."""
import json
import multiprocessing
import os
import subprocess

import pytest
import sqlalchemy as sa

from daesingo.case.jobs import JOB_KINDS
from daesingo.common.jobs.produced import ProducedReader
from daesingo.common.jobs.schema import job_execution
from daesingo.common.jobs.redelivery import redeliver_once
from daesingo.recording import RecordingService, ConnectionRecordingRepository
from daesingo.worker.case_composition import stored_case_store, StoredCaseReflector
from production_processes import api_peer, worker_peer
from test_production_search_process_mysql import receive, public

pytestmark = pytest.mark.mysql


@pytest.mark.parametrize("timing", ["command", "observation"])
@pytest.mark.mysql_check("recording_exports", "separate_api_worker")
def test_both_exports_after_response_restart_and_duplicate_t2(async_db, tmp_path, timing):
    _, _, engine = async_db
    root, temp = tmp_path / "media", tmp_path / "temp"
    root.mkdir(); temp.mkdir()
    source = tmp_path / "input.avi"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=160x96:r=10:d=1",
        "-c:v", "mpeg4", str(source)], capture_output=True, check=True, timeout=30)
    env = {"DAESINGO_RUNTIME_DB_URL": engine.url.render_as_string(hide_password=False),
        "DAESINGO_RUNTIME_MEDIA_ROOT": str(root), "DAESINGO_RUNTIME_API_TEMP_ROOT": str(temp),
        "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(temp), "GEMINI_API_KEY": "offline",
        "DAESINGO_RECORDING_ANALYSIS_PROFILE_REF": "process-test",
        "DAESINGO_RECORDING_ANALYSIS_HEIGHT": "240", "DAESINGO_RECORDING_ANALYSIS_PRESET": "veryfast",
        "DAESINGO_RECORDING_ANALYSIS_CRF": "23", "DAESINGO_RECORDING_INCIDENT_HEIGHT": "240",
        "DAESINGO_RECORDING_ANALYSIS_MAX_BYTES": "1000000", "DAESINGO_RECORDING_ANALYSIS_MAX_DURATION_MS": "10000",
        "DAESINGO_RECORDING_INCIDENT_PRESET": "veryfast", "DAESINGO_RECORDING_INCIDENT_CRF": "23",
        "DAESINGO_RECORDING_FILENAME_OFFSET": "+09:00"}
    env_file = tmp_path / "process.env"
    env_file.write_text("\n".join(f"{k}={v}" for k, v in env.items()), encoding="utf-8")
    mp = multiprocessing.get_context("spawn")
    local, remote = mp.Pipe()
    api = mp.Process(target=api_peer, args=(remote, str(env_file)))
    children, export_calls = [], []
    api.start(); remote.close()
    try:
        api_pid = receive(local)["pid"]
        local.send(("POST", "/cases", None)); identity = public(receive(local))["case_id"]
        local.send(("upload", f"/cases/{identity}/sources", str(source))); upload = public(receive(local))
        def view():
            local.send(("GET", f"/cases/{identity}/view", None))
            return public(receive(local))
        def command(kind, payload, current=None):
            current = view() if current is None else current
            local.send(("POST", f"/cases/{identity}/commands", {"case_id": identity,
                "expected_case_rev": current["case_rev"], "kind": kind, "payload": payload}))
            return public(receive(local))["case_view"]
        command("START_ANALYSIS", {"description": "red signal"}, upload["case_view"])
        def run(kind, rollback=False):
            incoming, outgoing = mp.Pipe()
            child = mp.Process(target=worker_peer, args=(outgoing, str(env_file), "clip_export", kind, rollback))
            children.append(child); child.start(); outgoing.close()
            try: result = receive(incoming)
            finally: incoming.close()
            child.join(20)
            assert child.exitcode == 0 and result["pid"] not in {api_pid, os.getpid()}
            assert result["pool_checkedout"] == 0
            assert result["terminals"] == [{"status": "SUCCEEDED", "failure_kind": None}]
            expected_http = int(kind in {"HINT_EXTRACT", "COARSE_SEARCH", "FINE_VERIFY"})
            assert result["http_calls"] == expected_http
            if kind in {"PLATE_READ", "OVERLAY_TIME_READ"}:
                assert set(result["registered_kinds"]) == JOB_KINDS
            if kind.endswith("EXPORT"):
                assert result["export_calls"] == ["export_report_video" if kind == "REPORT_VIDEO_EXPORT" else "export_plate_image"]
                export_calls.extend(result["export_calls"])
            return result
        for kind in ("HINT_EXTRACT", "COARSE_SEARCH", "FINE_VERIFY", "INCIDENT_CLIP_BUILD"): run(kind)
        if timing == "observation":
            responded = command("RECORD_SITUATION_RESPONSE", {"value": "CONFIRMED"})
            assert all(not j["kind"].endswith("EXPORT") for j in responded["running_jobs"])
        for _ in range(2):
            with engine.connect() as conn:
                kind = conn.scalar(sa.select(job_execution.c.kind).where(job_execution.c.status == "QUEUED")
                    .order_by(job_execution.c.available_at, job_execution.c.execution_id).limit(1))
            assert kind in {"PLATE_READ", "OVERLAY_TIME_READ"}
            run(kind)
        if timing == "command":
            assert not view()["running_jobs"]
            command("RECORD_SITUATION_RESPONSE", {"value": "CONFIRMED"})
        exporting = view()
        assert {j["kind"] for j in exporting["running_jobs"]} == {"REPORT_VIDEO_EXPORT", "PLATE_IMAGE_EXPORT"}
        assert any(n["code"] == "case.report_video_not_generated" and n["actions"] == [] for n in exporting["notices"])
        for _ in range(2):
            with engine.connect() as conn:
                kind = conn.scalar(sa.select(job_execution.c.kind).where(job_execution.c.status == "QUEUED")
                    .order_by(job_execution.c.available_at, job_execution.c.execution_id).limit(1))
            run(kind, rollback=True)
        # New delivery contexts restore both T1 results. No media process remains.
        reflector = StoredCaseReflector(storage_root=root)
        for _ in range(4): redeliver_once(engine, reflector)
        final = view()
        assert not final["running_jobs"]
        assert not any(n["code"] == "case.report_video_not_generated" for n in final["notices"])
        check = next(c for c in final["requirements_package"]["checks"] if c["code"] == "package.asset.report_video.exists")
        assert check["outcome"] == "PASS"
        assert len(export_calls) == 2
        with engine.begin() as conn:
            store = stored_case_store(conn, storage_root=root)
            case = store.get_case(identity)
            exports = [r for r in case.job_records if r["kind"].endswith("EXPORT")]
            assert len(exports) == 2
            with RecordingService(ConnectionRecordingRepository(conn, storage_root=root)) as recording:
                for job in exports:
                    terminal = conn.execute(sa.select(job_execution).where(job_execution.c.job_id == job["job_id"])).mappings().one()
                    assert terminal["case_applied_at"] is not None
                    payload = ProducedReader()(conn, job["kind"], tuple(terminal["produced"]))
                    asset = recording.get_derived_asset(payload["derived_asset_ref"])
                    opened = recording.open_derived_asset(asset.derived_asset_ref)
                    try: assert len(opened.stream.read()) == asset.byte_size > 0
                    finally: opened.stream.close()
                    assert recording.get_export_transform(asset.transform_ref)["input"] == store.export_input(identity, job["job_id"])
        assert engine.pool.checkedout() == 0
    finally:
        if api.is_alive():
            try: local.send(("stop", None, None))
            except (EOFError, OSError): pass
        api.join(10)
        if api.is_alive(): api.terminate(); api.join(10)
        local.close()
        for child in children:
            if child.is_alive(): child.terminate(); child.join(10)
