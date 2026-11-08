"""Offline, isolated Linux capacity probe. Never constructs an authenticated SDK.

Run only in an owned, resource-limited container on an internal Docker network.
The source root and manifest must be read-only mounts. Results contain lengths,
anonymous IDs and fixed phase names; no payload, SQL, argv or error messages.
This measures module code, not Worker/Case lifecycle or product acceptance.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
from types import SimpleNamespace
import threading
import time

_json_dumps = json.dumps
JOURNAL = None


class Journal:
    """Flush safe phase/sample/byte events as they happen, including before kill."""
    def __init__(self, path):
        self.path, self.lock = path, threading.Lock()
        with path.open("x", encoding="utf-8"):
            pass
    def emit(self, value):
        with self.lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(_json_dumps(value) + "\n")
            stream.flush()


def emit(value):
    if JOURNAL is not None:
        JOURNAL.emit(value)


class StopBeforeSend(BaseException):
    """Expected sentinel at SDK entry, after the real provider request guard."""


def require_sdk_stop(report):
    if report.get("request_guard") != "PASS_STOP_BEFORE_SEND":
        raise RuntimeError("SDK_STOP_NOT_OBSERVED")


@contextmanager
def measure(events, name):
    event = {"phase": name, "status": "PASS", "start_monotonic_sec": time.monotonic()}
    events.append(event)
    emit({"kind": "phase_start", "event": dict(event)})
    try:
        yield event
    except BaseException as error:
        event.update(status="STOP_BEFORE_SEND" if isinstance(error, StopBeforeSend) else "FAIL",
                     error_type=type(error).__name__)
        code = getattr(error, "code", None)
        if isinstance(code, str) and code in {
            "ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED", "UNSUPPORTED_MEDIA", "UNAVAILABLE", "TEMPORARY_FAILURE"}:
            event["error_code"] = code
        raise
    finally:
        event["elapsed_sec"] = time.monotonic() - event["start_monotonic_sec"]
        emit({"kind": "phase_end", "event": dict(event)})


def verify_stat(path, record):
    observed = path.stat()
    if observed.st_size != record["bytes"] or observed.st_mtime_ns != record["mtime_ns"]:
        raise ValueError("INPUT_IDENTITY_MISMATCH")


def frame_summary(payload):
    frames = payload.get("frames", [])
    pts = [int(f["best_effort_timestamp"]) for f in frames]
    gaps = []
    for index, (a, b) in enumerate(zip(frames, frames[1:])):
        duration = a.get("duration", a.get("pkt_duration"))
        if duration not in (None, "N/A"):
            gap = int(b["best_effort_timestamp"]) - int(a["best_effort_timestamp"]) - int(duration)
            if gap:
                gaps.append({"frame_index": index, "gap_ticks": gap})
    return {"frame_count": len(frames), "time_bases": [s.get("time_base") for s in payload.get("streams", [])],
            "pts_strictly_increasing": bool(pts) and all(b > a for a, b in zip(pts, pts[1:])),
            "coverage_discontinuities": len(gaps), "max_abs_gap_ticks": max([abs(g["gap_ticks"]) for g in gaps] + [0]),
            "first_gap_examples": gaps[:10]}


@contextmanager
def driver_bytes(connection, events):
    """Observe actual PyMySQL command and write-buffer lengths, never their contents.

    Write-buffer bytes include protocol framing, but do not measure kernel/TCP or
    driver buffer allocations. They must not be described as network wire bytes.
    """
    execute, write = connection._execute_command, connection._write_bytes
    def command(code, sql):
        entry = {"command": int(code), "sql_bytes": len(sql.encode(connection.encoding) if isinstance(sql, str) else sql)}
        events.append(entry)
        emit({"kind": "driver_command", "monotonic_sec": time.monotonic(), **entry})
        return execute(code, sql)
    def send(data):
        events.append({"write_buffer_bytes": len(data)})
        emit({"kind": "driver_write_buffer", "monotonic_sec": time.monotonic(), "bytes": len(data)})
        return write(data)
    connection._execute_command, connection._write_bytes = command, send
    try:
        yield
    finally:
        connection._execute_command, connection._write_bytes = execute, write


def tree_bytes(root):
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except FileNotFoundError:
            pass
    return total


class Sampler:
    """200ms samples; sampled maxima can miss shorter peaks."""
    def __init__(self, root, abort_marker=None):
        self.root, self.samples, self.stop = root, [], threading.Event()
        self.error = None
        self.abort_marker = abort_marker
    def trigger_stop(self, reason):
        self.error = reason
        if self.abort_marker is not None:
            self.abort_marker.write_text(reason, encoding="utf-8")
    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
    def run(self):
        import psutil
        process = psutil.Process()
        while not self.stop.is_set():
            try:
                children = []
                for child in process.children(recursive=True):
                    try:
                        cpu = child.cpu_times()
                        children.append({"pid": child.pid, "name": child.name(), "rss_bytes": child.memory_info().rss,
                                         "cpu_sec": cpu.user + cpu.system})
                    except psutil.NoSuchProcess:
                        pass
                memory = Path("/sys/fs/cgroup/memory.current")
                sample = {"monotonic_sec": time.monotonic(), "python_rss_bytes": process.memory_info().rss,
                          "children": children, "temp_bytes": tree_bytes(self.root),
                          "cgroup_bytes": int(memory.read_text()) if memory.exists() else None}
                self.samples.append(sample)
                emit({"kind": "resource_sample", **sample})
                if sample["temp_bytes"] >= 512 * 1024**2 or (sample["cgroup_bytes"] or 0) >= 1100 * 1024**2:
                    self.trigger_stop("RESOURCE_BUDGET_STOP")
            except BaseException as error:
                self.trigger_stop(type(error).__name__)
                return
            self.stop.wait(.2)
    def check(self):
        if self.error:
            raise RuntimeError("SAMPLER_OR_RESOURCE_STOP")
    def close(self):
        self.stop.set()
        self.thread.join(3)


def run(args):
    global JOURNAL
    import sqlalchemy as sa
    from daesingo.recording import RecordingService, LocalAnalysisMaterializer
    from daesingo.recording.factory import RecordingSettings, build_recording_service
    from daesingo.recording.mysql_repository import MySQLRecordingRepository, metadata
    from daesingo.recording.observability import capture_materialization
    from daesingo.search.config import GeminiSearchConfig
    from daesingo.search.media import MediaInput, MediaPreparer
    from daesingo.search.execution import RunDeadline
    from daesingo.search import provider as provider_module
    from daesingo.search.sources import ResolvedAnalysisSource
    from daesingo.search.runs import ContractRef

    if os.name != "posix" or os.environ.get("CAPACITY_PROBE_ISOLATED") != "issue452-owned-internal":
        raise RuntimeError("ISOLATED_CONTAINER_REQUIRED")
    if any(os.environ.get(k) for k in ("GEMINI_API_KEY", "ELICE_ML_API_KEY", "OPENAI_API_KEY")):
        raise RuntimeError("CREDENTIAL_ENV_FORBIDDEN")
    # A second egress boundary in addition to the internal Docker network.
    connect = socket.socket.connect
    def limited_connect(sock, address):
        if not isinstance(address, tuple) or address[:2] != (args.db_host, 3306):
            raise RuntimeError("EGRESS_BLOCKED")
        return connect(sock, address)
    socket.socket.connect = limited_connect
    work = Path("/work")
    work.mkdir(exist_ok=True)
    os.environ["TMPDIR"] = str(work)
    import tempfile
    tempfile.tempdir = str(work)
    output = Path(args.output)
    if output.exists():
        raise ValueError("RESULT_ALREADY_EXISTS")
    JOURNAL = Journal(output.with_suffix(".events.private.jsonl"))
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8-sig"))
    records = manifest["files"][args.first - 1:args.first - 1 + args.count]
    if not records or len(records) != args.count:
        raise ValueError("INVALID_INPUT_SELECTION")
    events, driver, tools, parts, frame_probes = [], [], [], [], []
    report = {"schema": "capacity-probe/v1", "utc_start": datetime.now(timezone.utc).isoformat(),
              "clock": "time.monotonic seconds", "sampling_interval_sec": .2,
              "input_ids": [r["fixture_id"] for r in records], "requested_sec": args.seconds,
              "continuity": "user_report; filename order provisional; independent seam NOT_RUN",
              "code_sha": args.code_sha, "image_id": args.image_id, "config_id": args.config_id,
              "events": events, "driver": driver, "tools": tools, "parts": parts,
              "frame_probes": frame_probes,
              "provider_calls": 0, "sdk_serialization": "NOT_RUN", "network_wire_bytes": "NOT_RUN",
              "driver_buffer_allocations": "NOT_RUN", "case_runtime_e2e": "NOT_RUN",
              "db_store": "NOT_REACHED", "db_read": "NOT_REACHED", "search_media": "NOT_REACHED",
              "request_guard": "NOT_REACHED", "concat": "NOT_REACHED", "status": "FAIL"}
    sampler = Sampler(work, output.with_suffix(".abort"))
    sampler.start()
    engine, conn, service = None, None, None
    config = {
        "DAESINGO_RECORDING_ANALYSIS_PROFILE_REF": args.config_id,
        "DAESINGO_RECORDING_ANALYSIS_HEIGHT": "480", "DAESINGO_RECORDING_ANALYSIS_PRESET": "veryfast",
        "DAESINGO_RECORDING_ANALYSIS_CRF": "23", "DAESINGO_RECORDING_ANALYSIS_MAX_BYTES": str(args.max_bytes),
        "DAESINGO_RECORDING_ANALYSIS_MAX_DURATION_MS": str(args.max_duration_ms)}
    report["recording_config"] = config
    report["config_sha256"] = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    emit({"kind": "identity", "code_sha": args.code_sha, "image_id": args.image_id,
          "config_sha256": report["config_sha256"], "input_ids": report["input_ids"], "requested_sec": args.seconds})
    try:
        import subprocess
        report["tools_version"] = {tool: subprocess.check_output([tool, "-version"], text=True).splitlines()[0]
                                   for tool in ("ffmpeg", "ffprobe")}
        import importlib.metadata
        report["library_versions"] = {name: importlib.metadata.version(name)
                                      for name in ("PyMySQL", "SQLAlchemy", "psutil", "openai", "pydantic")}
        if any(not v.startswith(k + " version 8.1 ") for k, v in report["tools_version"].items()):
            raise RuntimeError("EXPECTED_TOOL_VERSION_NOT_FOUND")
        engine = sa.create_engine(sa.URL.create("mysql+pymysql", username="probe", host=args.db_host,
                                                database="capacity_probe"),
                                  connect_args={"connect_timeout": 10, "read_timeout": 30, "write_timeout": 30},
                                  hide_parameters=True, echo=False, pool_size=1, max_overflow=0)
        # Dedicated empty schema only; no shared host database or full migration suite.
        metadata.create_all(engine)
        conn = engine.connect()
        report["packet_bytes"] = conn.exec_driver_sql("SELECT @@session.max_allowed_packet").scalar_one()
        report["aborted_before"] = int(conn.exec_driver_sql("SHOW GLOBAL STATUS LIKE 'Aborted_clients'").one()[1])
        repo = MySQLRecordingRepository(conn, storage_root="/inputs")
        publish = repo.add_prepared_media
        def observed_publish(*a, **kw):
            report["db_store"] = "FAIL"
            with measure(events, "db_publish") as observed:
                observed["content_bytes"] = len(a[1])
                report["final_prepared_bytes"] = len(a[1])
                result = publish(*a, **kw)
                report["db_store"] = "PASS"
                return result
        repo.add_prepared_media = observed_publish

        class ObservedMaterializer(LocalAnalysisMaterializer):
            def _probe(self, path, index=None):
                payload = super()._probe(path, index)
                frame_probes.append({"role": "source" if Path(path).is_relative_to('/inputs') else "output",
                                     **frame_summary(payload)})
                return payload
            def _run(self, argv):
                kind = "probe" if Path(argv[0]).name == "ffprobe" else (
                    "concat" if "concat" in argv else "encode" if "-vf" in argv else "decode")
                if kind == "concat":
                    report["concat"] = "FAIL"
                with measure(events, "tool_" + kind) as observed:
                    tools.append(observed)
                    value = super()._run(argv)
                    if kind in ("encode", "concat"):
                        observed["output_bytes"] = Path(argv[-1]).stat().st_size
                    if kind == "concat":
                        report["concat"] = "MUX_PASS_VALIDATION_PENDING"
                    return value
            def materialize(self, *a, **kw):
                with measure(events, "individual_materialize") as observed:
                    result = super().materialize(*a, **kw)
                    observed["output_bytes"] = len(result.content)
                    parts.append(len(result.content))
                    observed["cumulative_bytes"] = sum(parts)
                    return result
            def _materialize_many(self, inputs, profile_ref):
                with measure(events, "chain_total"):
                    result = super()._materialize_many(inputs, profile_ref)
                    report["concat"] = "PASS"
                    return result

        def factory(profiles):
            return ObservedMaterializer(profiles, temp_root=work, timeout_sec=120)
        service = build_recording_service(repo, RecordingSettings.from_mapping(config), temp_root=work,
                                          materializer_factory=factory, case_id="capacity-probe",
                                          analysis_checkpoint=sampler.check)
        service.__enter__()
        from decimal import Decimal
        placements, offset = [], Decimal(0)
        with measure(events, "registration"):
            for record in records:
                path = Path("/inputs") / record["filename"]
                verify_stat(path, record)
                registered = service.register_local_source(path, original_filename=record["fixture_id"], case_id="capacity-probe")
                local = repo.get_local_source(registered.source_asset.source_asset_ref)
                if local.sha256 != record["sha256"]:
                    raise ValueError("INPUT_HASH_MISMATCH")
                observed_duration = registered.source_asset.duration_sec
                # Explicit metadata placements are a capacity candidate, not an
                # independently verified physical recording clock or seam.
                placements.append(dict(source_asset_ref=registered.source_asset.source_asset_ref,
                    timeline_start_sec=float(offset), timeline_end_sec=float(offset + Decimal(str(observed_duration))),
                    media_stream_ref=next(s.media_stream_ref for s in registered.media_streams if s.media_type == "VIDEO")))
                offset += Decimal(str(observed_duration))
        report["candidate_duration_sec"] = float(offset)
        if Decimal(str(args.seconds)) > offset:
            raise ValueError("REQUEST_EXCEEDS_CANDIDATE")
        timeline = service.create_relative_timeline_from_placements(placements)
        ref = dict(timeline_id=timeline.timeline_id, revision=timeline.revision)
        with measure(events, "resolve") as observed:
            resolution = service.resolve_span(ref, dict(start_sec=0, end_sec=args.seconds),
                media_stream_refs=[p["media_stream_ref"] for p in placements])
            observed.update(resolution_status=resolution.status, spans=len(resolution.spans), missing=len(resolution.missing_ranges),
                            missing_reasons=sorted({m.reason for m in resolution.missing_ranges}))
        report["resolution"] = observed
        # Keep source registration outside the prepared-media rollback window.
        conn.commit()
        with capture_materialization() as traces:
            report["materialization_traces"] = traces
            with measure(events, "recording_prepare"):
                with driver_bytes(conn.connection.driver_connection, driver):
                    source = service.prepare_analysis_source_from_resolution(resolution, args.config_id)
        report["final_bytes"] = source.byte_size
        report["concat"] = "PASS" if any(t["phase"] == "tool_concat" for t in tools) else "NOT_APPLICABLE"
        report["db_store"] = "PASS"
        report["db_read"] = "FAIL"
        with measure(events, "fresh_service_db_read") as observed:
            # New service forces the real repository read, avoiding instance cache.
            with RecordingService(repo) as reader:
                opened = reader.open_analysis_source(source.analysis_source_ref)
                content = opened.stream.read()
                opened.stream.close()
            sql_hash, sql_length = conn.exec_driver_sql(
                "SELECT SHA2(content,256), OCTET_LENGTH(content) FROM recording_entry WHERE kind='analysis_source'").one()
            digest = hashlib.sha256(content).hexdigest()
            if digest != sql_hash or len(content) != sql_length or len(content) != source.byte_size:
                raise ValueError("DB_HASH_MISMATCH")
            observed.update(content_bytes=len(content), sha256=digest)
        report["db_read"] = "PASS"
        cfg = GeminiSearchConfig()
        report["search_config"] = {"fingerprint": cfg.fingerprint, "source_cap_bytes": cfg.max_materialized_source_bytes,
                                  "media_cap_bytes": cfg.max_inline_media_bytes, "request_cap_bytes": cfg.max_inline_request_bytes,
                                  "coarse_fps": cfg.coarse_fps, "budget_ms": 150000}
        deadline = RunDeadline(time.monotonic, 150000)
        sampler.check()
        from io import BytesIO
        report["search_media"] = "FAIL"
        with measure(events, "search_media_prepare") as observed:
            manager = MediaPreparer(cfg).prepare_coarse(MediaInput(BytesIO(content), "video/mp4", len(content), source.duration_sec), deadline)
            media = manager.__enter__()
            observed.update(media_bytes=media.byte_size, playback_duration_sec=media.duration_sec)
        report["search_media"] = "PASS"
        try:
            sampler.check()
            report["request_guard"] = "FAIL"
            provider = provider_module.GeminiProvider.__new__(provider_module.GeminiProvider)
            provider._config = cfg
            def stop(**kwargs):
                raise StopBeforeSend()
            provider._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
                with_raw_response=SimpleNamespace(parse=stop))))
            original_url = provider_module._video_data_url
            def observed_url(*a, **kw):
                sampler.check()
                with measure(events, "base64_data_url") as event:
                    url = original_url(*a, **kw)
                    event.update(data_url_bytes=len(url.encode()), base64_bytes=len(url.split(",", 1)[1]))
                    sampler.check()
                    return url
            provider_module._video_data_url = observed_url
            original_dumps = provider_module.json.dumps
            def counted_dumps(*a, **kw):
                sampler.check()
                with measure(events, "json_serialize") as event:
                    text = original_dumps(*a, **kw)
                    event["utf8_bytes"] = len(text.encode())
                    sampler.check()
                    return text
            provider_module.json.dumps = counted_dumps
            try:
                with measure(events, "request_guard_and_sdk_entry"):
                    provider.search_coarse(provider_module.CoarseRequest(
                        source=ResolvedAnalysisSource(ContractRef(kind="analysis_source", ref=source.analysis_source_ref),
                            source.duration_sec, timeline.timeline_id), event_types=(), media=media, deadline=deadline))
            except StopBeforeSend:
                report["request_guard"] = "PASS_STOP_BEFORE_SEND"
            finally:
                provider_module._video_data_url = original_url
                provider_module.json.dumps = original_dumps
        finally:
            manager.__exit__(None, None, None)
        require_sdk_stop(report)
        report["status"] = "PASS_STOP_BEFORE_SEND"
    except BaseException as error:
        report["error_type"] = type(error).__name__
        report["error_code"] = getattr(error, "code", None)
        original = getattr(error, "orig", None)
        report["db_errno"] = (original.args[0] if original is not None and original.args
                              and type(original.args[0]) is int else None)
        import traceback
        report["error_frames"] = [{"module_file": Path(f.filename).name, "line": f.lineno, "function": f.name}
                                  for f in traceback.extract_tb(error.__traceback__)]
        if report["error_code"] == "ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED":
            report["status"] = "TYPED_REJECTION"
    finally:
        cleanup_errors = []
        def cleanup(name, operation):
            try:
                with measure(events, name):
                    operation()
            except BaseException as error:
                cleanup_errors.append({"phase": name, "error_type": type(error).__name__})
        if service is not None:
            cleanup("service_close", lambda: service.__exit__(None, None, None))
        def rollback():
            conn.rollback()
            remaining = conn.exec_driver_sql("SELECT COUNT(*) FROM recording_entry WHERE kind IN ('analysis_source','prepared_content')").scalar_one()
            report["prepared_rows_after_rollback"] = remaining
            if remaining:
                raise ValueError("ROLLBACK_LEFT_PREPARED_ROWS")
            report["aborted_after"] = int(conn.exec_driver_sql("SHOW GLOBAL STATUS LIKE 'Aborted_clients'").one()[1])
            report["db_ping"] = conn.exec_driver_sql("SELECT 1").scalar_one()
        if conn is not None:
            cleanup("rollback", rollback)
            cleanup("connection_close", conn.close)
        if engine is not None:
            cleanup("engine_dispose", engine.dispose)
        sampler.close()
        report["samples"] = sampler.samples
        report["sampler_error"] = sampler.error
        report["temp_bytes_after"] = tree_bytes(work)
        report["live_children_after"] = [p.name() for p in __import__("psutil").Process().children(recursive=True)]
        report["cleanup_errors"] = cleanup_errors
        report["input_stat_after"] = "PASS"
        for record in records:
            try:
                verify_stat(Path("/inputs") / record["filename"], record)
            except (OSError, ValueError):
                report["input_stat_after"] = "FAIL"
        if (cleanup_errors or sampler.error or report["temp_bytes_after"] or report["live_children_after"]
                or report["input_stat_after"] != "PASS"
                or report.get("aborted_after") != report.get("aborted_before")):
            report["status"] = "FAIL"
        socket.socket.connect = connect
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        JOURNAL = None
    print(json.dumps({k: report.get(k) for k in ("status", "error_type", "error_code", "final_bytes", "db_store", "search_media", "request_guard", "temp_bytes_after")}))
    return 0 if report["status"] in ("PASS_STOP_BEFORE_SEND", "TYPED_REJECTION") else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("manifest", "output", "db-host", "code-sha", "image-id", "config-id"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument("--first", type=int, default=1)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--max-bytes", type=int, default=50331648)
    parser.add_argument("--max-duration-ms", type=int, default=240000)
    args = parser.parse_args()
    if not (0 < args.seconds <= 1300 and 0 < args.max_duration_ms <= 1300000 and 0 < args.max_bytes <= 128 * 1024**2):
        parser.error("finite experiment ceilings exceeded")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
