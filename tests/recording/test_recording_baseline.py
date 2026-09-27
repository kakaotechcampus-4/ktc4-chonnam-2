import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


spec = importlib.util.spec_from_file_location("recording_baseline", Path(__file__).parents[2] / "examples/recording_baseline.py")
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
DATASET_ID = "ds_8bac6448a72947819e73d32b101e2d98"


@pytest.fixture
def media(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe 필요")
    path = tmp_path / "private-source-name.avi"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
                    "testsrc2=s=64x48:r=10:d=1", "-c:v", "mpeg4", str(path)],
                   check=True, capture_output=True, timeout=30)
    return path


def run(video, output, **options):
    return baseline.run_baseline(video, dataset_id=DATASET_ID, output=output,
        **({"repeats": 3, "video_index": 0, "start_sec": 0.0, "end_sec": 1.0, "height": 48} | options))


def verify_bundle(directory, bundle):
    assert json.loads((directory / "bundle.json").read_text(encoding="utf-8")) == bundle
    reports = []
    for item in bundle["runs"]:
        content = (directory / item["file"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == item["sha256"]
        report = json.loads(content)
        assert report["schema_version"] == "recording-benchmark/v1"
        reports.append(report)
    assert bundle["summary"] == baseline.summarize(reports)
    return reports


def test_generated_media_frozen_bundle_preserves_raw_results(media, tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "private-auth-secret")
    output = tmp_path / "baseline"
    captured = []
    original = baseline.benchmark.run_benchmark
    def capture(*args, **kwargs):
        report = original(*args, **kwargs)
        captured.append(copy.deepcopy(report))
        return report
    monkeypatch.setattr(baseline.benchmark, "run_benchmark", capture)
    bundle = run(media, output)
    reports = verify_bundle(output, bundle)
    assert reports == captured
    assert bundle["status"] == "FROZEN" and all(bundle["freeze_checks"].values())
    assert len({r["run_id"] for r in reports}) == 3
    assert bundle["dataset"]["fingerprint"] == baseline.benchmark.fingerprint(media)
    assert bundle["dataset"]["technical_metadata"]["duration_sec"] == 1.0
    assert bundle["summary"]["status_counts"] == {"FALLBACK": 3}
    for value in bundle["summary"]["stages"].values():
        stats = value["elapsed_sec"]
        assert stats["count"] == 3 and 0 <= stats["min"] <= stats["median"] <= stats["max"]
    for path in output.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert all(secret not in text for secret in (media.name, str(media.parent), "private-auth-secret"))
    previous = {p: p.read_bytes() for p in output.rglob("*.json")}
    with pytest.raises(baseline.BaselineError, match="OUTPUT_EXISTS"):
        run(media, output)
    assert all(p.read_bytes() == content for p, content in previous.items())


def test_statistics_does_not_mix_failure_or_skip():
    def report(status, seconds):
        return {"status": status, "total_elapsed_sec": 10.0,
                "stages": [{"name": "frame", "status": status, "elapsed_sec": seconds}]}
    reports = [report("SUCCESS", 1.0), report("FALLBACK", 3.0), report("FAILED", 20.0), report("SKIPPED", None)]
    entry = baseline.summarize(reports)["stages"]["frame"]
    assert entry["elapsed_sec"] == {"count": 2, "min": 1.0, "median": 2.0, "max": 3.0}
    assert entry["failed_elapsed_sec"] == {"count": 1, "min": 20.0, "median": 20.0, "max": 20.0}
    assert baseline.summarize(reports)["stages"]["timeline"]["elapsed_sec"]["median"] is None


@pytest.mark.parametrize("field", ["tools", "settings", "input_before", "metadata"])
def test_drift_prevents_freeze_preserves_reports(media, tmp_path, monkeypatch, field):
    sample = baseline.benchmark.run_benchmark(media, video_index=0, start_sec=0.0, end_sec=1.0, height=48)
    other = copy.deepcopy(sample)
    if field == "tools":
        other["tools"]["ffprobe"] = "4.3.1"
    elif field == "settings":
        other["settings"]["height"] = 480
    elif field == "metadata":
        other["results"]["input"]["duration_sec"] = 2.0
    else:
        other["input_before"]["sha256"] = "0" * 64
        other["input_after"] = copy.deepcopy(other["input_before"])
    reports = iter([sample, other])
    monkeypatch.setattr(baseline.benchmark, "run_benchmark", lambda *a, **kw: next(reports))
    bundle = run(media, tmp_path / "drift", repeats=2)
    assert bundle["status"] == "INCOMPLETE"
    assert verify_bundle(tmp_path / "drift", bundle) == [sample, other]


def test_failed_runs_preserved_without_freeze(tmp_path):
    path = tmp_path / "corrupt.avi"
    path.write_bytes(b"corrupt")
    bundle = run(path, tmp_path / "failed", repeats=2)
    reports = verify_bundle(tmp_path / "failed", bundle)
    assert bundle["status"] == "INCOMPLETE" and len(reports) == 2
    assert bundle["summary"]["status_counts"] == {"FAILED": 2}
    assert bundle["summary"]["stages"]["register_probe"]["failed_elapsed_sec"]["count"] == 2
    assert bundle["summary"]["stages"]["frame"]["elapsed_sec"]["count"] == 0


def test_original_change_stops_remaining_runs(media, tmp_path, monkeypatch):
    def modify(*args, **kwargs):
        with media.open("ab") as stream:
            stream.write(b"modified")  # 합성 테스트 영상만 수정한다.
        raise ValueError("private exception")
    monkeypatch.setattr(baseline.benchmark.RecordingService, "resolve_span", modify)
    bundle = run(media, tmp_path / "changed")
    reports = verify_bundle(tmp_path / "changed", bundle)
    assert bundle["status"] == "INCOMPLETE" and len(reports) == 1
    assert not bundle["freeze_checks"]["all_repeats_completed"]
    assert not bundle["freeze_checks"]["original_unchanged"]


def test_cli_missing_input_and_invalid_id_safe(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("DAESINGO_RECORDING_VIDEO", raising=False)
    output = tmp_path / "unused"
    args = ["--dataset-id", DATASET_ID, "--output", str(output), "--video-index", "0", "--start", "0", "--end", "1"]
    assert baseline.main(args) == 1
    assert json.loads(capsys.readouterr().out)["failure"]["code"] == "INVALID_INPUT"
    args[1] = "C:/private-person.avi"
    assert baseline.main(args) == 1
    text = capsys.readouterr().out
    assert "private-person" not in text and json.loads(text)["failure"]["code"] == "INVALID_DATASET_ID"
    assert not output.exists()


def test_opt_in_real_baseline(tmp_path):
    video = os.environ.get("DAESINGO_RECORDING_VIDEO")
    index = os.environ.get("DAESINGO_RECORDING_VIDEO_INDEX")
    if not video or index is None:
        pytest.skip("실제 영상과 명시적 VIDEO_INDEX opt-in 필요")
    bundle = run(video, tmp_path / "real-baseline", repeats=2, video_index=int(index),
                 start_sec=1.0, end_sec=2.0, height=480)
    assert bundle["status"] == "FROZEN", bundle["freeze_checks"]
    reports = verify_bundle(tmp_path / "real-baseline", bundle)
    assert all(r["original_unchanged"] is True for r in reports)
    print(json.dumps({"status": bundle["status"], "runs": len(reports), "freeze_checks": bundle["freeze_checks"]}))


def split_run(video, output, **kwargs):
    return baseline.run_baseline(video, dataset_id=DATASET_ID, output=output,
        **({"repeats": 2, "video_index": 0, "analysis_start": 0.0, "analysis_end": 1.0,
            "incident_start": 0.3, "incident_end": 0.7, "height": 48} | kwargs))


def test_split_bundle_preserves_raw_reports_and_both_range_settings(media, tmp_path, monkeypatch):
    reports = []
    original = baseline.benchmark.run_benchmark
    def capture(*a, **kw):
        report = original(*a, **kw)
        reports.append(copy.deepcopy(report))
        return report
    monkeypatch.setattr(baseline.benchmark, "run_benchmark", capture)
    directory = tmp_path / "split"
    bundle = split_run(media, directory)
    assert bundle["schema_version"] == "recording-baseline/v2" and bundle["status"] == "FROZEN"
    assert bundle["execution"]["requested_ranges"] == reports[0]["requested_ranges"]
    assert "requested_range" not in bundle["execution"]
    for index, item in enumerate(bundle["runs"]):
        data = (directory / item["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == item["sha256"]
        assert json.loads(data) == reports[index]
    for kind in ("analysis", "incident"):
        assert bundle["summary"]["stages"][f"resolve_{kind}_span"]["elapsed_sec"]["count"] == 2
        changed = copy.deepcopy(reports)
        changed[1]["requested_ranges"][kind]["end_sec"] += 0.1
        assert baseline._freeze_checks(changed, 2)["same_settings"] is False


def test_opt_in_real_split_baseline(tmp_path):
    video = os.environ.get("DAESINGO_RECORDING_VIDEO")
    index = os.environ.get("DAESINGO_RECORDING_VIDEO_INDEX")
    if not video or index is None:
        pytest.skip("실제 영상과 명시적 VIDEO_INDEX opt-in 필요")
    output = tmp_path / "real-split"
    bundle = split_run(video, output, video_index=int(index), analysis_end=10.0,
                       incident_start=1.0, incident_end=2.0, height=480)
    assert bundle["status"] == "FROZEN", bundle["freeze_checks"]
    for item in bundle["runs"]:
        data = (output / item["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == item["sha256"]
        report = json.loads(data)
        assert report["schema_version"] == "recording-benchmark/v2"
        assert all(r["status"] == "COMPLETE" for r in report["results"]["resolutions"].values())
        assert report["results"]["analysis_source"]["duration_sec"] > report["results"]["incident_clip"]["duration_sec"]
        assert 1.0 <= report["results"]["frame"]["actual_source_offset_sec"] < 2.0
        assert report["original_unchanged"] is True
    print(json.dumps({"status": bundle["status"], "runs": len(bundle["runs"]),
                      "requested_ranges": bundle["execution"]["requested_ranges"], "checks": bundle["freeze_checks"]}))
