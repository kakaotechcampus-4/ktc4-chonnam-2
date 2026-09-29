import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from daesingo.recording import AnalysisProfile, IncidentClipEncoding, LocalAnalysisMaterializer, LocalIncidentMaterializer, RecordingService, RecordingCapabilityError
from daesingo.recording import materialization
from daesingo.recording.observability import PHASES, capture_materialization

spec = importlib.util.spec_from_file_location("baseline_trace", Path(__file__).parents[2] / "examples/recording_baseline.py")
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
benchmark = baseline.benchmark


@pytest.fixture
def media(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe 필요")
    path = tmp_path / "private-source.avi"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
                    "testsrc2=s=64x48:r=10:d=1", "-c:v", "mpeg4", str(path)],
                   check=True, capture_output=True, timeout=30)
    return path


def run(video, trace, split=True):
    ranges = dict(analysis_start=0.0, analysis_end=1.0, incident_start=0.3, incident_end=0.7) if split else dict(start_sec=0.0, end_sec=1.0)
    return benchmark.run_benchmark(video, video_index=0, height=48, materialization_trace=trace, **ranges)


@pytest.mark.parametrize("split", [False, True])
def test_opt_in_trace_same_bytes_and_no_duplicate_tools(media, monkeypatch, split):
    calls = []
    original = LocalAnalysisMaterializer._run
    def counted(self, args):
        calls.append(args[0])
        return original(self, args)
    monkeypatch.setattr(LocalAnalysisMaterializer, "_run", counted)
    before = benchmark.fingerprint(media)
    plain = run(media, False, split)
    plain_calls = calls[:]
    calls.clear()
    traced = run(media, True, split)
    assert plain["schema_version"] == ("recording-benchmark/v2" if split else "recording-benchmark/v1")
    assert "materialization_trace" not in plain and "materialization_trace" not in plain["settings"]
    assert traced["schema_version"] == "recording-benchmark/v3"
    assert calls == plain_calls and len(calls) == 5  # source inspection 공유 1회 + output probe/encode 각 2회
    for kind in ("analysis_source", "incident_clip", "frame"):
        assert traced["results"][kind] == plain["results"][kind]
    for kind in ("analysis_source", "incident_clip"):
        trace, = traced["materialization_trace"][kind]
        assert trace["status"] == "SUCCESS" and trace["failure"] is None
        assert [p["name"] for p in trace["phases"]] == list(PHASES)
        assert all(p["status"] == "SUCCESS" and p["elapsed_sec"] >= 0 for p in trace["phases"])
    assert benchmark.fingerprint(media) == before
    assert traced["original_unchanged"] is True
    assert media.name not in json.dumps(traced) and str(media.parent) not in json.dumps(traced)


@pytest.mark.parametrize("kind", ["analysis_source", "incident_clip"])
@pytest.mark.parametrize("failed_phase", PHASES)
def test_failure_phase_error_preserved_and_cleanup(media, tmp_path, monkeypatch, kind, failed_phase):
    work = tmp_path / "work"
    work.mkdir()
    analysis = LocalAnalysisMaterializer({"profile": AnalysisProfile(48, "veryfast", 23)}, temp_root=work)
    incident = LocalIncidentMaterializer(IncidentClipEncoding(48, "veryfast", 23), temp_root=work)
    engine = analysis if kind == "analysis_source" else incident._engine
    service = RecordingService(analysis_materializer=analysis, incident_materializer=incident)
    registered = service.register_local_source(media)
    timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
    resolution = service.resolve_span({"timeline_id": timeline.timeline_id, "revision": 1},
        {"start_sec": 0.0, "end_sec": 1.0}, media_stream_ref=registered.media_streams[0].media_stream_ref)
    original_snapshot, original_probe, original_run, original_read = materialization._snapshot, engine._probe, engine._run, Path.read_bytes
    snapshots = 0
    def snapshot(path):
        nonlocal snapshots
        snapshots += 1
        if (failed_phase == "source_snapshot" and snapshots % 2 == 1) or (failed_phase == "source_verify" and snapshots % 2 == 0):
            raise OSError(f"private-auth {media}")
        return original_snapshot(path)
    def probe(path, index=None):
        if failed_phase == ("source_probe" if index is not None else "output_probe"):
            raise ValueError(f"private-auth {media}")
        result = original_probe(path, index)
        if failed_phase == "frame_prepare" and index is not None:
            result["streams"][0]["height"] = 0
        if failed_phase == "output_validate" and index is None:
            result["streams"][0]["codec_name"] = "invalid"
        return result
    def execute(args):
        if args[0] == "ffmpeg" and failed_phase == "encode":
            Path(args[-1]).write_bytes(b"partial")
            raise subprocess.TimeoutExpired(f"private-auth {media}", 1, stderr=b"private-stderr")
        return original_run(args)
    def read(path):
        if path.name == "prepared.mp4":
            if failed_phase == "bytes_read":
                raise OSError(f"private-auth {media}")
            if failed_phase == "bytes_validate":
                return b""
        return original_read(path)
    monkeypatch.setattr(materialization, "_snapshot", snapshot)
    monkeypatch.setattr(engine, "_probe", probe)
    monkeypatch.setattr(engine, "_run", execute)
    monkeypatch.setattr(Path, "read_bytes", read)
    def build():
        if kind == "analysis_source":
            return service.prepare_analysis_source(resolution.spans[0], "profile", timeline_ref=resolution.timeline_ref)
        return service.build_incident_clip(resolution)
    with pytest.raises(RecordingCapabilityError) as plain:
        build()
    snapshots = 0
    with capture_materialization() as traces:
        with pytest.raises(RecordingCapabilityError) as traced:
            build()
    assert (traced.value.code, str(traced.value)) == (plain.value.code, str(plain.value))
    trace, = traces
    assert trace["status"] == "FAILED" and trace["failure"]["phase"] == failed_phase
    failed_index = PHASES.index(failed_phase)
    assert all(p["status"] == "SUCCESS" for p in trace["phases"][:failed_index])
    assert trace["phases"][failed_index]["status"] == "FAILED"
    assert all(p["status"] == "SKIPPED" and p["elapsed_sec"] is None for p in trace["phases"][failed_index+1:])
    assert "private" not in json.dumps(trace)
    assert not list(work.iterdir())
    with capture_materialization() as empty:
        pass
    assert empty == []  # 실패 이후 collector context가 누적/누출되지 않는다.
    service.close()


def test_v3_bundle_summary_and_raw_preservation(media, tmp_path):
    output = tmp_path / "traced"
    bundle = baseline.run_baseline(media, dataset_id="ds_8bac6448a72947819e73d32b101e2d98", output=output,
        repeats=2, video_index=0, start_sec=0.0, end_sec=1.0, height=48, materialization_trace=True)
    assert bundle["schema_version"] == "recording-baseline/v3" and bundle["status"] == "FROZEN"
    assert bundle["freeze_checks"]["materialization_trace_complete"] is True
    reports = [json.loads((output / r["file"]).read_text(encoding="utf-8")) for r in bundle["runs"]]
    assert all(r["schema_version"] == "recording-benchmark/v3" for r in reports)
    assert bundle["summary"]["materialization_trace"] == baseline.summarize_materialization(reports)
    for kind in ("analysis_source", "incident_clip"):
        for name in PHASES:
            stats = bundle["summary"]["materialization_trace"][kind]["phases"][name]["elapsed_sec"]
            assert stats["count"] == 2 and 0 <= stats["min"] <= stats["median"] <= stats["max"]


def test_opt_in_real_materialization_trace(tmp_path):
    video, index = os.environ.get("DAESINGO_RECORDING_VIDEO"), os.environ.get("DAESINGO_RECORDING_VIDEO_INDEX")
    if not video or index is None:
        pytest.skip("실제 영상과 명시적 VIDEO_INDEX opt-in 필요")
    bundle = baseline.run_baseline(video, dataset_id="ds_8bac6448a72947819e73d32b101e2d98", output=tmp_path / "real-trace",
        repeats=2, video_index=int(index), analysis_start=0.0, analysis_end=20.024656,
        incident_start=1.0, incident_end=2.0, materialization_trace=True)
    assert bundle["schema_version"] == "recording-baseline/v3" and bundle["status"] == "FROZEN"
    assert all(bundle["freeze_checks"].values())
    print(json.dumps(bundle["summary"]["materialization_trace"]))


def test_trace_cli_flags_and_failed_phase_statistics(media, tmp_path, capsys):
    args = [str(media), "--video-index", "0", "--start", "0", "--end", "1", "--materialization-trace"]
    assert benchmark.main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["schema_version"] == "recording-benchmark/v3"
    assert baseline.main(args + ["--dataset-id", "ds_8bac6448a72947819e73d32b101e2d98",
                                "--output", str(tmp_path / "cli"), "--repeats", "1"]) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == "recording-baseline/v3"
    # 고정값으로 집계 경계 확인: 실패 시간과 SKIPPED를 성공 시간에 섞지 않는다.
    synthetic = [{"materialization_trace": {"analysis_source": [{"phases": [
        {"name": "encode", "status": "FAILED", "elapsed_sec": 2.0},
        {"name": "output_probe", "status": "SKIPPED", "elapsed_sec": None}]}], "incident_clip": []}}]
    summary = baseline.summarize_materialization(synthetic)
    assert summary["analysis_source"]["phases"]["encode"]["elapsed_sec"]["count"] == 0
    assert summary["analysis_source"]["phases"]["encode"]["failed_elapsed_sec"]["median"] == 2.0
    assert summary["analysis_source"]["phases"]["output_probe"]["elapsed_sec"]["median"] is None
