"""Recording 공개 capability의 실행별 측정. stdout에는 공유 가능한 JSON만 출력한다."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
from time import perf_counter
from uuid import uuid4

from daesingo.recording import (
    AnalysisProfile, IncidentClipEncoding, LocalAnalysisMaterializer,
    LocalIncidentMaterializer, RecordingCapabilityError, RecordingService,
)


STAGES = ("input_fingerprint", "tool_versions", "register_probe", "timeline", "stream_selection",
          "resolve_span", "analysis_source", "incident_clip", "frame", "original_integrity")
# 공유 report에는 예외 메시지나 임의 exception.code를 복사하지 않는다.
SAFE_CODES = {"UNKNOWN_REF", "UNAVAILABLE", "TEMPORARY_FAILURE", "UNSUPPORTED_MEDIA",
              "SOURCE_UNAVAILABLE", "SOURCE_INSPECTION_FAILED", "STREAM_COVERAGE_UNKNOWN",
              "TIMELINE_METADATA_INVALID", "INCIDENT_CLIP_BUILD_FAILED", "FRAME_NOT_FOUND",
              "NOT_FOUND"}


class BenchmarkFailure(Exception):
    def __init__(self, code):
        self.code = code


def fingerprint(path):
    before = path.stat()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise BenchmarkFailure("INPUT_CHANGED_DURING_HASH")
    return {"sha256": digest, "byte_size": after.st_size, "mtime_ns": after.st_mtime_ns}


def tool_versions():
    versions = {"python": platform.python_version()}
    for tool in ("ffmpeg", "ffprobe"):
        run = subprocess.run([tool, "-version"], capture_output=True, timeout=10, check=True)
        # build configuration과 임의 vendor 문자열은 공유하지 않는다.
        match = re.match(rf"{tool} version (\d+(?:\.\d+)*)", run.stdout.decode("utf-8", errors="replace"))
        versions[tool] = match[1] if match else "unparsed"
    return versions


def run_benchmark(video, *, video_index, start_sec, end_sec, height=480):
    """Benchmark 전용 report를 반환한다. Canonical Contract/profile registry와 별개다."""
    report = {
        "schema_version": "recording-benchmark/v1", "run_id": f"bench_{uuid4().hex}",
        "status": "SUCCESS", "failure": None, "original_unchanged": None,
        "input_before": None, "input_after": None, "tools": {}, "settings": {},
        "requested_range": None, "results": {},
        "stages": [{"name": name, "status": "SKIPPED", "elapsed_sec": None, "failure": None}
                   for name in STAGES],
    }
    started = perf_counter()

    def step(name, action):
        entry = next(item for item in report["stages"] if item["name"] == name)
        at = perf_counter()
        try:
            result = action()
            entry["status"] = "SUCCESS"
            return result
        except Exception as error:
            if isinstance(error, BenchmarkFailure):
                code = error.code
            elif isinstance(error, RecordingCapabilityError):
                code = error.code if error.code in SAFE_CODES else "CAPABILITY_FAILED"
            elif isinstance(error, ValueError):
                code = "INVALID_INPUT"
            elif isinstance(error, subprocess.TimeoutExpired):
                code = "TOOL_TIMEOUT"
            elif isinstance(error, subprocess.CalledProcessError):
                code = "TOOL_FAILED"
            elif isinstance(error, OSError):
                code = "IO_OR_TOOL_UNAVAILABLE"
            else:
                code = "UNEXPECTED_ERROR"
            entry.update(status="FAILED", failure={"code": code})
            if report["failure"] is None:
                report["failure"] = {"stage": name, "code": code}
            report["status"] = "FAILED"
            raise
        finally:
            entry["elapsed_sec"] = perf_counter() - at

    def fallback(name, reason):
        entry = next(item for item in report["stages"] if item["name"] == name)
        entry.update(status="FALLBACK", reason=reason)
        if report["status"] != "FAILED":
            report["status"] = "FALLBACK"

    path = None
    try:
        def validate_and_hash():
            nonlocal path
            if video is None:
                raise ValueError("video input is required")
            if (type(video_index) is not int or video_index < 0
                    or type(start_sec) not in (int, float) or type(end_sec) not in (int, float)
                    or not math.isfinite(start_sec) or not math.isfinite(end_sec)
                    or start_sec < 0 or end_sec <= start_sec):
                raise ValueError("invalid benchmark input")
            AnalysisProfile(height, "veryfast", 23)
            path = Path(video)
            report["settings"] = {"video_index": video_index, "height": height,
                "codec": "h264", "preset": "veryfast", "crf": 23, "audio": False,
                "pixel_format": "yuv420p", "faststart": True, "profile_scope": "benchmark_trial"}
            report["requested_range"] = {"start_sec": float(start_sec), "end_sec": float(end_sec)}
            return fingerprint(path)

        report["input_before"] = step("input_fingerprint", validate_and_hash)
        report["tools"] = step("tool_versions", tool_versions)
        profile = f"prof_{uuid4().hex}"
        with RecordingService(
            analysis_materializer=LocalAnalysisMaterializer({profile: AnalysisProfile(height, "veryfast", 23)}),
            incident_materializer=LocalIncidentMaterializer(IncidentClipEncoding(height, "veryfast", 23)),
        ) as service:
            registered = step("register_probe", lambda: service.register_local_source(path))
            report["results"]["input"] = {"byte_size": registered.source_asset.byte_size,
                "duration_sec": registered.source_asset.duration_sec,
                "video_stream_count": sum(s.media_type == "VIDEO" for s in registered.media_streams)}
            timeline = step("timeline", lambda: service.create_relative_timeline(registered.source_asset.source_asset_ref))
            report["results"]["timeline"] = {"revision": timeline.revision, "status": timeline.timeline_status}
            if timeline.timeline_status == "USABLE_RELATIVE_ONLY":
                fallback("timeline", "RELATIVE_ONLY_NO_TRUSTED_ANCHOR")
            ref = {"timeline_id": timeline.timeline_id, "revision": timeline.revision}

            def select():
                videos = [s for s in registered.media_streams if s.media_type == "VIDEO"]
                if video_index >= len(videos):
                    raise ValueError("invalid video index")
                return videos[video_index]

            selected = step("stream_selection", select)

            def resolve():
                result = service.resolve_span(ref, report["requested_range"], media_stream_ref=selected.media_stream_ref)
                report["results"]["resolution"] = {"status": result.status,
                    "ranges": [s.timeline_range.model_dump(mode="json") for s in result.spans],
                    "missing_ranges": [{"timeline_range": r.timeline_range.model_dump(mode="json"), "reason": r.reason}
                                       for r in result.missing_ranges]}
                if result.status == "FAILED" or len(result.spans) != 1:
                    code = result.failure.code if result.failure else "NO_SINGLE_USABLE_SPAN"
                    raise BenchmarkFailure(code if code in SAFE_CODES else "NO_SINGLE_USABLE_SPAN")
                return result

            resolution = step("resolve_span", resolve)
            if resolution.status == "PARTIAL":
                fallback("resolve_span", "PARTIAL_COVERAGE")
            span, = resolution.spans

            def prepare():
                source = service.prepare_analysis_source(span, profile, timeline_ref=ref)
                opened = service.open_analysis_source(source.analysis_source_ref)
                count = 0
                digest = hashlib.sha256()
                with opened.stream:
                    while chunk := opened.stream.read(1024 * 1024):
                        count += len(chunk)
                        digest.update(chunk)
                if count != source.byte_size or count != opened.byte_size:
                    raise BenchmarkFailure("DERIVED_SIZE_MISMATCH")
                return {"byte_size": count, "duration_sec": source.duration_sec,
                        "timeline_range": source.timeline_range.model_dump(mode="json"),
                        "sha256": digest.hexdigest(), "content_type": opened.content_type}

            report["results"]["analysis_source"] = step("analysis_source", prepare)

            def clip():
                built = service.build_incident_clip(resolution)
                stored = service.get_incident_clip(built.incident_clip_ref)
                return {"byte_size": stored.byte_size, "duration_sec": stored.duration_sec,
                        "timeline_range": stored.timeline_range.model_dump(mode="json"),
                        "byte_size_basis": "producer_measured"}

            report["results"]["incident_clip"] = step("incident_clip", clip)

            def frame():
                resolved = service.resolve_frame({"kind": "STREAM_POSITION", "media_stream_ref": selected.media_stream_ref,
                    "source_offset_sec": span.source_range.start_sec})
                content = service.read_frame(resolved.frame_ref)
                return {"requested_source_offset_sec": span.source_range.start_sec,
                        "actual_source_offset_sec": resolved.source_offset_sec, "byte_size": len(content),
                        "sha256": hashlib.sha256(content).hexdigest()}

            report["results"]["frame"] = step("frame", frame)
    except Exception:
        if report["status"] != "FAILED":
            report.update(status="FAILED", failure={"stage": "runner", "code": "UNEXPECTED_ERROR"})
    finally:
        if report["input_before"] is not None:
            def integrity():
                report["input_after"] = fingerprint(path)
                report["original_unchanged"] = report["input_before"] == report["input_after"]
                if not report["original_unchanged"]:
                    raise BenchmarkFailure("ORIGINAL_CHANGED")
            try:
                step("original_integrity", integrity)
            except Exception:
                pass
        report["total_elapsed_sec"] = perf_counter() - started
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", nargs="?", default=os.environ.get("DAESINGO_RECORDING_VIDEO"))
    parser.add_argument("--video-index", type=int, required=True, help="VIDEO만 센 명시적 0 기반 순번")
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--end", type=float, required=True)
    args = parser.parse_args(argv)
    report = run_benchmark(args.video, video_index=args.video_index, start_sec=args.start, end_sec=args.end)
    print(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2))
    return 1 if report["status"] == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
