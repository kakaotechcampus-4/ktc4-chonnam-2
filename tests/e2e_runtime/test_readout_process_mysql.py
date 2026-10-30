"""Separate API/Worker processes through both Readout jobs, with offline OCR."""
import json
import multiprocessing
import os
import subprocess

import pytest
import sqlalchemy as sa

from daesingo.common.jobs.schema import job_execution
from daesingo.common.jobs.produced import ProducedReader
from daesingo.common.jobs.redelivery import redeliver_once
from daesingo.common.usage.schema import usage_record
from daesingo.worker.case_composition import StoredCaseReflector, stored_case_store
from production_processes import api_peer, worker_peer
from test_production_search_process_mysql import receive, public

pytestmark = pytest.mark.mysql


@pytest.mark.parametrize("mode,notice", [("success", None), ("abstain", None),
    ("not_present", "readout.overlay_not_present"),
    ("undetermined", "readout.overlay_presence_undetermined"),
    ("ocr_failed", "readout.overlay_ocr_failed"), ("failed", None)])
@pytest.mark.mysql_check("readout_process", "separate_api_worker")
def test_full_chain_and_stored_caseview_in_separate_processes(async_db, tmp_path, mode, notice):
    _, _, engine = async_db
    root, temp = tmp_path / "media", tmp_path / "temp"
    root.mkdir(); temp.mkdir()
    video = tmp_path / "generated.avi"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
        "testsrc2=s=64x48:r=10:d=1", "-c:v", "mpeg4", "-pix_fmt", "yuv420p", str(video)],
        check=True, capture_output=True, timeout=30)
    values = {"DAESINGO_RUNTIME_DB_URL": engine.url.render_as_string(hide_password=False),
        "DAESINGO_RUNTIME_MEDIA_ROOT": str(root), "DAESINGO_RUNTIME_API_TEMP_ROOT": str(temp),
        "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(temp), "GEMINI_API_KEY": "offline",
        "DAESINGO_RECORDING_ANALYSIS_PROFILE_REF": "test-analysis",
        "DAESINGO_RECORDING_ANALYSIS_HEIGHT": "240", "DAESINGO_RECORDING_ANALYSIS_PRESET": "veryfast",
        "DAESINGO_RECORDING_ANALYSIS_CRF": "23", "DAESINGO_RECORDING_INCIDENT_HEIGHT": "240",
        "DAESINGO_RECORDING_ANALYSIS_MAX_BYTES": "1000000", "DAESINGO_RECORDING_ANALYSIS_MAX_DURATION_MS": "10000",
        "DAESINGO_RECORDING_INCIDENT_PRESET": "veryfast", "DAESINGO_RECORDING_INCIDENT_CRF": "23"}
    env_file = tmp_path / "peer.env"
    env_file.write_text("\n".join(f"{key}={value}" for key, value in values.items()), encoding="utf-8")
    mp = multiprocessing.get_context("spawn")
    local, remote = mp.Pipe()
    api = mp.Process(target=api_peer, args=(remote, str(env_file)))
    children, observed = [], []
    api.start(); remote.close()
    try:
        api_pid = receive(local)["pid"]
        local.send(("POST", "/cases", None)); identity = public(receive(local))["case_id"]
        local.send(("upload", f"/cases/{identity}/sources", str(video)))
        upload = public(receive(local))
        local.send(("POST", f"/cases/{identity}/commands", {"case_id": identity,
            "expected_case_rev": upload["case_view"]["case_rev"], "kind": "START_ANALYSIS",
            "payload": {"description": "red signal"}}))
        public(receive(local))
        for kind in ("HINT_EXTRACT", "COARSE_SEARCH", "FINE_VERIFY", "INCIDENT_CLIP_BUILD", None, None):
            if kind is None:
                # Both readouts are enqueued in the same transaction. Runtime
                # orders them by available_at/execution_id, not by job kind.
                with engine.connect() as conn:
                    kind = conn.scalar(sa.select(job_execution.c.kind).where(job_execution.c.status == "QUEUED")
                        .order_by(job_execution.c.available_at, job_execution.c.execution_id).limit(1))
                assert kind in {"PLATE_READ", "OVERLAY_TIME_READ"}
            incoming, outgoing = mp.Pipe()
            child = mp.Process(target=worker_peer, args=(outgoing, str(env_file), "clip_readout_" + mode, kind,
                kind in {"PLATE_READ", "OVERLAY_TIME_READ"}))
            children.append(child); child.start(); outgoing.close()
            try: result = receive(incoming)
            finally: incoming.close()
            child.join(20)
            assert child.exitcode == 0 and result["pid"] not in {api_pid, os.getpid()}
            assert result["pool_checkedout"] == 0
            is_readout = kind in {"PLATE_READ", "OVERLAY_TIME_READ"}
            assert result["http_calls"] == (0 if is_readout or kind == "INCIDENT_CLIP_BUILD" else 1)
            assert result["terminals"] == [{"status": "FAILED" if is_readout and mode == "failed" else "SUCCEEDED",
                "failure_kind": "READOUT_INFRA" if is_readout and mode == "failed" else None}]
            if is_readout:
                assert len(result["readout_calls"]) == 1
                observed.extend(result["readout_calls"])
        assert observed[0][1] == observed[1][1] and observed[0][2] != observed[1][2]
        # Both Readout Workers rolled back T2 after real Case writes. Delivery now
        # restores the observations from durable T1 without any provider process.
        with engine.connect() as conn:
            assert conn.scalar(sa.select(sa.func.count()).select_from(job_execution).where(
                job_execution.c.kind.in_(("PLATE_READ", "OVERLAY_TIME_READ")),
                job_execution.c.case_applied_at.is_(None))) == 2
        for _ in range(2): redeliver_once(engine, StoredCaseReflector(storage_root=root))
        local.send(("GET", f"/cases/{identity}/view", None))
        view = public(receive(local))
        assert not view["running_jobs"] and view["evidence"] is not None
        codes = {item["code"] for item in view["notices"]}
        if notice:
            assert notice in codes
            assert len(codes & {"readout.overlay_not_present", "readout.overlay_presence_undetermined", "readout.overlay_ocr_failed"}) == 1
        with engine.begin() as conn:
            rows = conn.execute(sa.select(job_execution)).mappings().all()
            assert len(rows) == 6 and all(row["case_applied_at"] is not None for row in rows)
            facade = stored_case_store(conn, storage_root=root)
            adapter = facade.adapter_for(facade.get_case(identity))
            if mode != "failed":
                assert len(adapter.get_plate_readouts()) == len(adapter.get_overlay_time_readouts()) == 1
            else: assert adapter.get_plate_read_status() == "FAILED"
            for row in rows:
                if row["kind"] not in {"PLATE_READ", "OVERLAY_TIME_READ"}: continue
                payload = ProducedReader()(conn, row["kind"], tuple(row["produced"]))
                usage = conn.execute(sa.select(usage_record).where(usage_record.c.execution_ref == row["execution_id"])).mappings().one()
                assert usage["run_ref"] == payload["readout_run"]["run_id"] and usage["run_ref_reason"] is None
                assert usage["processed_duration_sec"] > 0
                assert facade.observation_input(identity, row["job_id"])["incident_clip_ref"] == observed[0][1]
        assert engine.pool.checkedout() == 0
    finally:
        if api.is_alive():
            try: local.send(("stop", None, None))
            except (EOFError, OSError): pass
        api.join(10)
        if api.is_alive(): api.terminate(); api.join(10)
        local.close()
        for child in children:
            if child.is_alive(): child.terminate()
            child.join(10)
        assert not api.is_alive() and all(not child.is_alive() for child in children)
    assert {p.name for p in temp.iterdir()} == {".runtime-cleanup-temp.lock"}
