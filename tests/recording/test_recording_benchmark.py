import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


spec = importlib.util.spec_from_file_location("recording_benchmark", Path(__file__).parents[2] / "examples/recording_benchmark.py")
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


@pytest.fixture
def media(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe 필요")
    path = tmp_path / "private-person-20260620.avi"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
        "testsrc2=s=64x48:r=10:d=1", "-c:v", "mpeg4", str(path)],
        check=True, capture_output=True, timeout=30)
    return path


def run(path, end=0.76, **kwargs):
    return benchmark.run_benchmark(path, video_index=0, start_sec=0.15, end_sec=end, height=48, **kwargs)


def test_public_pipeline_report_ranges_size_privacy(media, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "private-authentication-secret")
    before = benchmark.fingerprint(media)
    report = run(media)
    assert report["status"] == "FALLBACK" and report["failure"] is None
    assert report["original_unchanged"] is True
    assert report["input_before"] == report["input_after"] == before
    assert report["results"]["resolution"]["status"] == "COMPLETE"
    for key in ("analysis_source", "incident_clip"):
        asset = report["results"][key]
        assert asset["byte_size"] > 0 and asset["duration_sec"] == 0.6
        assert asset["timeline_range"] == {"start_sec": 0.2, "end_sec": 0.8}
    assert report["results"]["frame"]["actual_source_offset_sec"] >= 0.15
    assert all(s["elapsed_sec"] >= 0 and s["status"] in {"SUCCESS", "FALLBACK"} for s in report["stages"])
    assert report["tools"]["ffprobe"] != "unparsed"
    serialized = json.dumps(report, allow_nan=False)
    assert all(secret not in serialized for secret in (media.name, str(media.parent), "private-authentication-secret"))


def test_boundary_partial_fallback(media):
    report = run(media, end=1.5)
    assert report["status"] == "FALLBACK"
    assert report["results"]["resolution"]["status"] == "PARTIAL"
    assert report["results"]["resolution"]["missing_ranges"][0]["reason"] == "OUT_OF_TIMELINE_RANGE"
    assert report["results"]["incident_clip"]["timeline_range"]["end_sec"] == 1.0


def test_corrupt_source_failure_and_integrity(tmp_path):
    path = tmp_path / "private-corrupt.avi"
    path.write_bytes(b"not video")
    report = run(path)
    assert report["failure"]["stage"] == "register_probe"
    assert report["status"] == "FAILED" and report["original_unchanged"] is True
    assert next(s for s in report["stages"] if s["name"] == "frame")["status"] == "SKIPPED"


def test_failure_does_not_leak_exception_and_original_checked(media, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError(f"stderr {media} token=private-auth")
    monkeypatch.setattr(benchmark.RecordingService, "build_incident_clip", fail)
    report = run(media)
    assert report["failure"] == {"stage": "incident_clip", "code": "UNEXPECTED_ERROR"}
    assert report["original_unchanged"] is True
    assert "private" not in json.dumps(report)


def test_original_change_detected_on_failure(media, monkeypatch):
    def change(*args, **kwargs):
        with media.open("ab") as stream:
            stream.write(b"changed")  # 이 테스트에서 생성한 파일만 변경한다.
        raise ValueError("stop")
    monkeypatch.setattr(benchmark.RecordingService, "resolve_span", change)
    report = run(media)
    assert report["status"] == "FAILED" and report["original_unchanged"] is False
    assert report["stages"][-1]["failure"]["code"] == "ORIGINAL_CHANGED"
    assert report["failure"]["stage"] == "resolve_span"


def test_invalid_input_json_and_cli(media, capsys):
    report = benchmark.run_benchmark(media, video_index=0, start_sec=float("nan"), end_sec=1.0)
    assert report["failure"]["code"] == "INVALID_INPUT"
    json.dumps(report, allow_nan=False)
    assert benchmark.main([str(media), "--video-index", "99", "--start", "0", "--end", "1"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["failure"]["stage"] == "stream_selection"


def test_cli_missing_video_and_environment(monkeypatch, capsys):
    monkeypatch.delenv("DAESINGO_RECORDING_VIDEO", raising=False)
    assert benchmark.main(["--video-index", "0", "--start", "0", "--end", "1"]) == 1
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["status"] == "FAILED"
    assert report["failure"] == {"stage": "input_fingerprint", "code": "INVALID_INPUT"}
    assert report["stages"][0]["failure"] == {"code": "INVALID_INPUT"}
    assert all(stage["status"] == "SKIPPED" for stage in report["stages"][1:])
    assert report["input_before"] is None and report["input_after"] is None
    assert captured.err == ""
    assert "video input is required" not in captured.out
    assert "Traceback" not in captured.out
    assert str(Path.cwd()) not in captured.out


def test_opt_in_real_benchmark():
    path = os.environ.get("DAESINGO_RECORDING_VIDEO")
    index = os.environ.get("DAESINGO_RECORDING_VIDEO_INDEX")
    if not path or index is None:
        pytest.skip("DAESINGO_RECORDING_VIDEO 및 명시적 VIDEO_INDEX 필요")
    report = benchmark.run_benchmark(path, video_index=int(index), start_sec=1.0, end_sec=2.0)
    assert report["status"] == "FALLBACK", report["failure"]
    assert report["original_unchanged"] is True
    assert all(report["results"][key]["byte_size"] > 0 for key in ("analysis_source", "incident_clip", "frame"))
    print(json.dumps(report, ensure_ascii=False, allow_nan=False))


def test_full_range_and_unresolved_range(media):
    full = benchmark.run_benchmark(media, video_index=0, start_sec=0.0, end_sec=1.0, height=48)
    assert full["failure"] is None
    assert full["results"]["analysis_source"]["duration_sec"] == 1.0
    assert full["results"]["incident_clip"]["timeline_range"] == full["requested_range"]
    empty = benchmark.run_benchmark(media, video_index=0, start_sec=2.0, end_sec=3.0, height=48)
    assert empty["failure"]["stage"] == "resolve_span"
    assert empty["original_unchanged"] is True


def test_tool_timeout_sanitized_and_missing_input(media, monkeypatch):
    def timeout():
        raise subprocess.TimeoutExpired(str(media), 10, stderr=b"private-auth")
    monkeypatch.setattr(benchmark, "tool_versions", timeout)
    report = run(media)
    assert report["failure"] == {"stage": "tool_versions", "code": "TOOL_TIMEOUT"}
    assert report["original_unchanged"] is True
    assert "private" not in json.dumps(report)
    missing = run(media.parent / "missing.avi")
    assert missing["failure"]["stage"] == "input_fingerprint"
    assert missing["original_unchanged"] is None
