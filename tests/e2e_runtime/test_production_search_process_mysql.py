"""Generated media, real MySQL and independent API/Worker OS processes."""
import multiprocessing
import os
import subprocess

import pytest

from daesingo.common.jobs.produced import ProducedReader
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


@pytest.mark.parametrize("scenario", ["normal", "partial", "failed", "fine_failed", "hint", "clip", "clip_fractional", "clip_multisource"])
@pytest.mark.mysql_check("search_process", "separate_api_worker")
def test_public_api_worker_search_t1_t2_across_processes(async_db, tmp_path, scenario):
    _, _, engine = async_db
    clip_scenario = scenario.startswith("clip")
    root = tmp_path / "storage"
    root.mkdir()
    api_temp, worker_temp = tmp_path / "api-temp", tmp_path / "worker-temp"
    api_temp.mkdir(); worker_temp.mkdir()
    # The integration fixture needs observed frame coverage on Ubuntu ffprobe 6
    # as well as newer Windows builds. Recording's strict tail policy stays real.
    video = tmp_path / "input.avi"
    rate, frames = (30, 30) if scenario == "clip_fractional" else (10, 10)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
        f"color=c=red:s=64x48:r={rate}:d=1", "-frames:v", str(frames), "-c:v", "mpeg4", "-pix_fmt", "yuv420p", str(video)],
        check=True, capture_output=True, timeout=30)
    values = {"DAESINGO_RUNTIME_DB_URL": engine.url.render_as_string(hide_password=False),
        "DAESINGO_RUNTIME_MEDIA_ROOT": str(root), "DAESINGO_RUNTIME_API_TEMP_ROOT": str(api_temp),
        "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(worker_temp), "GEMINI_API_KEY": "offline-key",
        "DAESINGO_RECORDING_ANALYSIS_PROFILE_REF": "process-profile",
        "DAESINGO_RECORDING_ANALYSIS_HEIGHT": "240", "DAESINGO_RECORDING_ANALYSIS_PRESET": "veryfast",
        "DAESINGO_RECORDING_ANALYSIS_CRF": "23",
        "DAESINGO_RECORDING_ANALYSIS_MAX_BYTES": "1000000", "DAESINGO_RECORDING_ANALYSIS_MAX_DURATION_MS": "10000",
        "DAESINGO_RECORDING_INCIDENT_HEIGHT": "240", "DAESINGO_RECORDING_INCIDENT_PRESET": "veryfast",
        "DAESINGO_RECORDING_INCIDENT_CRF": "23"}
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
        if scenario == "clip_multisource":
            second = tmp_path / "second.mp4"
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
                "color=c=blue:s=64x48:r=10:d=1", "-c:v", "libx264", "-video_track_timescale", "10", str(second)],
                check=True, capture_output=True, timeout=30)
            local.send(("upload", f"/cases/{identity}/sources", str(second))); uploaded = public(receive(local))
        local.send(("POST", f"/cases/{identity}/commands", {"case_id": identity,
            "expected_case_rev": uploaded["case_view"]["case_rev"],
            "kind": "START_ANALYSIS", "payload": {"description": "red signal" if scenario == "hint" else ""}}))
        accepted = public(receive(local))
        assert accepted["case_view"]["running_jobs"][0]["kind"] == ("HINT_EXTRACT" if scenario == "hint" else "COARSE_SEARCH")
        def run_worker(kind):
            incoming, outgoing = context.Pipe()
            child = context.Process(target=worker_peer, args=(outgoing, str(env_file), scenario, kind))
            children.append(child); child.start(); outgoing.close()
            result = receive(incoming)
            incoming.close(); child.join(20)
            assert child.exitcode == 0 and not child.is_alive()
            assert result["pid"] not in {os.getpid(), api_pid}
            is_clip = kind == "INCIDENT_CLIP_BUILD"
            assert result["http_calls"] == (0 if is_clip else 1) and result["pool_checkedout"] == 0, result
            assert result["clip_calls"] == (1 if is_clip else 0), result
            assert result["encodes"] == (2 if scenario == "clip_multisource" else 1) * int(is_clip), result
            failed = scenario == "failed" or scenario == "fine_failed" and kind == "FINE_VERIFY"
            assert result["terminals"] == [{"status": "FAILED" if failed else "SUCCEEDED",
                "failure_kind": "SEARCH_PROVIDER_ERROR" if failed else None}], result
        if scenario == "hint":
            run_worker("HINT_EXTRACT")
            local.send(("GET", f"/cases/{identity}/view", None))
            hinted = public(receive(local))
            assert [job["kind"] for job in hinted["running_jobs"]] == ["COARSE_SEARCH"]
            assert hinted["hints"]["vehicle"] == "white car"
            assert hinted["hints"]["situation"] == "red signal"
        run_worker("COARSE_SEARCH")
        local.send(("GET", f"/cases/{identity}/view", None)); view = public(receive(local))
        assert bool(view["candidates"]) == (scenario != "failed")
        # Case selects rank=1 and issues the first Fine in Coarse T2 (W12:C2); the reflector enqueues it.
        # Runtime still invents no selection or downstream policy.
        assert [job["kind"] for job in view["running_jobs"]] == ([] if scenario == "failed" else ["FINE_VERIFY"])
        if scenario != "failed":
            run_worker("FINE_VERIFY")
            local.send(("GET", f"/cases/{identity}/view", None)); final_view = public(receive(local))
            assert [job["kind"] for job in final_view["running_jobs"]] == (["INCIDENT_CLIP_BUILD"] if clip_scenario else [])
            if clip_scenario:
                run_worker("INCIDENT_CLIP_BUILD")
                local.send(("GET", f"/cases/{identity}/view", None))
                clip_view = public(receive(local))
                assert {job["kind"] for job in clip_view["running_jobs"]} == {"PLATE_READ", "OVERLAY_TIME_READ"}
        with engine.begin() as conn:
            rows = conn.exec_driver_sql("SELECT execution_id,kind,status,produced,case_applied_at FROM job_execution ORDER BY queued_at").mappings().all()
            assert all(row["case_applied_at"] is not None for row in rows if row["kind"] not in {"PLATE_READ", "OVERLAY_TIME_READ"})
            coarse, = [row for row in rows if row["kind"] == "COARSE_SEARCH"]
            assert coarse["status"] == ("FAILED" if scenario == "failed" else "SUCCEEDED")
            import json
            refs = json.loads(coarse["produced"]) if isinstance(coarse["produced"], str) else coarse["produced"]
            payload = ProducedReader()(conn, "COARSE_SEARCH", tuple(refs))
            assert payload["analysis_run"]["outcome"] == {"partial": "PARTIAL", "failed": "FAILED"}.get(scenario, "SUCCEEDED")
            if scenario == "fine_failed": assert rows[-1]["status"] == "FAILED"
            if clip_scenario:
                from daesingo.worker.case_composition import stored_case_store
                from daesingo.recording import RecordingService, ConnectionRecordingRepository
                case_store = stored_case_store(conn, storage_root=root)
                clip_row, = [row for row in rows if row["kind"] == "INCIDENT_CLIP_BUILD"]
                assert clip_row["status"] == "SUCCEEDED"
                refs = json.loads(clip_row["produced"]) if isinstance(clip_row["produced"], str) else clip_row["produced"]
                payload = ProducedReader()(conn, "INCIDENT_CLIP_BUILD", tuple(refs))
                assert set(payload) == {"incident_clip_ref"}
                readouts = [row for row in rows if row["kind"] in {"PLATE_READ", "OVERLAY_TIME_READ"}]
                assert len(readouts) == 2 and all(row["status"] == "QUEUED" for row in readouts)
                case = case_store.get_case(identity)
                for job in case.job_records:
                    if job["kind"] in {"PLATE_READ", "OVERLAY_TIME_READ"}:
                        assert case_store.observation_input(identity, job["job_id"])["incident_clip_ref"] == payload["incident_clip_ref"]
                with RecordingService(ConnectionRecordingRepository(conn, storage_root=root)) as recording:
                    clip = recording.get_incident_clip(payload["incident_clip_ref"])
                    assert clip.availability == "AVAILABLE" and clip.byte_size > 0 and clip.duration_sec > 0
                    if scenario == "clip_multisource":
                        spans = clip.source_provenance.asset_spans
                        assert [(s.timeline_range.start_sec, s.timeline_range.end_sec,
                                 s.source_range.start_sec, s.source_range.end_sec) for s in spans] == [
                            (.5, 1., .5, 1.), (1., 1.5, 0., .5)]
                        assert len({s.source_asset_ref for s in spans}) == 2
                        assert clip.media_stream_refs == [s.media_stream_ref for s in spans]
                        assert clip.duration_sec == 1.
                # Readout capability remains absent even with complete clip config.
                from daesingo.worker.composition_root import compose_registry
                from daesingo.common.jobs.execution import ExecutionContext
                from types import SimpleNamespace
                registry = compose_registry(engine=engine, startup=SimpleNamespace())
                for kind in ("PLATE_READ", "OVERLAY_TIME_READ"):
                    assert registry.dispatch(ExecutionContext("e", "j", identity, kind, 1, "t")).failure_kind == "RUNTIME_UNREGISTERED_KIND"
    finally:
        if api.is_alive():
            try: local.send(("stop", None, None))
            except (EOFError, OSError): pass
        api.join(20)
        for child in [api, *children]:
            if child.is_alive(): child.terminate(); child.join(10)
        local.close()
    assert api.exitcode == 0
