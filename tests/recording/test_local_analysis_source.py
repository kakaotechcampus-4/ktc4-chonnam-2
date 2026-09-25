"""공개 capability로 실제 bytes/coverage/재사용/cleanup을 검증한다."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

import pytest

from daesingo.recording import (
    AnalysisProfile, AnalysisSource, LocalAnalysisMaterializer, RecordingCapabilityError, RecordingService,
)
from daesingo.recording.repository import InMemoryRecordingRepository


def fingerprint(path):
    with path.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
    info = path.stat()
    return info.st_size, info.st_mtime_ns, digest


@pytest.fixture
def media(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("실제 media 검증에는 ffmpeg/ffprobe가 필요합니다")
    path = tmp_path / "원본.avi"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n",
        "-f", "lavfi", "-i", "color=c=red:s=160x90:r=10:d=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=2",
        "-map", "0:v", "-map", "1:a", "-map", "2:v", "-c:v", "mpeg4", "-c:a", "pcm_s16le", str(path)],
        check=True, capture_output=True, timeout=30)
    return path


def setup(path, tmp_path):
    work = tmp_path / "materialization"
    work.mkdir()
    profile = f"prof_{uuid4().hex}"
    materializer = LocalAnalysisMaterializer({profile: AnalysisProfile(480, "veryfast", 23)}, temp_root=work)
    repo = InMemoryRecordingRepository()
    service = RecordingService(repo, analysis_materializer=materializer)
    registered = service.register_local_source(path)
    timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
    ref = {"timeline_id": timeline.timeline_id, "revision": timeline.revision}
    return service, repo, registered, ref, profile, materializer, work


def span_for(service, ref, video, start, end):
    result = service.resolve_span(ref, {"start_sec": start, "end_sec": end}, media_stream_ref=video.media_stream_ref)
    assert result.status == "COMPLETE" and len(result.spans) == 1
    return result.spans[0]


def inspect_bytes(service, source, tmp_path):
    # 공개 bytes만 임시 테스트 디렉터리에 기록하고 독립 ffprobe로 검증한다.
    first = service.open_analysis_source(source.analysis_source_ref)
    second = service.open_analysis_source(source.analysis_source_ref)
    assert first.stream is not second.stream
    assert not hasattr(first.stream, "name")
    assert first.content_type == second.content_type == "video/mp4"
    with first.stream, second.stream:
        prefix = first.stream.read(7)
        content = second.stream.read()
        assert prefix + first.stream.read() == content
    assert len(content) == source.byte_size == first.byte_size == second.byte_size
    target = tmp_path / "verify-output.mp4"
    try:
        target.write_bytes(content)
        output = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(target)],
            check=True, capture_output=True, timeout=30)
        payload = json.loads(output.stdout)
        assert len(payload["streams"]) == 1
        stream = payload["streams"][0]
        assert stream["codec_type"] == "video" and stream["codec_name"] == "h264"
        assert stream["height"] == 480 and stream["pix_fmt"] == "yuv420p"
        assert "mp4" in payload["format"]["format_name"]
        assert float(payload["format"]["duration"]) == source.duration_sec
        pixels = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(target),
            "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
            check=True, capture_output=True, timeout=30).stdout
        return pixels
    finally:
        target.unlink(missing_ok=True)


def test_full_partial_selected_video_public_bytes_and_reuse(media, tmp_path):
    before = fingerprint(media)
    service, _, registered, ref, profile, materializer, work = setup(media, tmp_path)
    video = [s for s in registered.media_streams if s.media_type == "VIDEO"][1]
    with service:
        full_span = span_for(service, ref, video, 0.0, 2.0)
        full = service.prepare_analysis_source(full_span, profile, timeline_ref=ref)
        part_span = span_for(service, ref, video, 0.35, 1.26)
        part = service.prepare_analysis_source(part_span, profile, timeline_ref=ref)
        assert full.analysis_source_ref != part.analysis_source_ref
        assert full.media_stream_refs == part.media_stream_refs == [video.media_stream_ref]
        assert full.timeline_range.start_sec == 0.0 and full.timeline_range.end_sec == 2.0
        assert part.timeline_range.start_sec == 0.4 and part.timeline_range.end_sec == 1.3
        assert part.duration_sec == 0.9
        assert AnalysisSource.model_validate_json(part.model_dump_json()) == part
        assert media.name not in part.model_dump_json()
        for source in [full, part]:
            pixels = inspect_bytes(service, source, tmp_path)
            assert pixels[2] > 240 and pixels[0] < 10  # 선택한 두 번째 VIDEO는 blue다.
        assert not list(work.iterdir())
        def fail(*args):
            raise AssertionError("재사용 요청에 encode를 수행했습니다")
        materializer.materialize = fail
        assert service.prepare_analysis_source(part_span, profile, timeline_ref=ref) == part
        part.media_stream_refs.clear()
        assert service.prepare_analysis_source(part_span, profile, timeline_ref=ref).media_stream_refs == [video.media_stream_ref]
    assert not list(work.iterdir())
    with pytest.raises(RecordingCapabilityError) as caught:
        service.open_analysis_source(full.analysis_source_ref)
    assert caught.value.code == "UNAVAILABLE"
    assert fingerprint(media) == before


@pytest.mark.parametrize("failure", ["encoder", "timeout", "probe"])
def test_failure_cleanup_no_publication(media, tmp_path, failure, monkeypatch):
    service, _, registered, ref, profile, materializer, work = setup(media, tmp_path)
    video = registered.media_streams[0]
    span = span_for(service, ref, video, 0.0, 1.0)
    original = materializer._run
    def run(args):
        if args[0] == "ffmpeg":
            Path(args[-1]).write_bytes(b"partial file")
            if failure == "timeout":
                raise subprocess.TimeoutExpired("private command", 1)
            if failure == "encoder":
                raise RecordingCapabilityError("TEMPORARY_FAILURE", "encoder failed")
            return b""
        if args[-1].endswith("prepared.mp4"):
            return b"{}"
        return original(args)
    monkeypatch.setattr(materializer, "_run", run)
    with pytest.raises(RecordingCapabilityError) as caught:
        service.prepare_analysis_source(span, profile, timeline_ref=ref)
    assert str(work) not in str(caught.value) and media.name not in str(caught.value)
    assert not list(work.iterdir()) and not service._local_analysis and not service._analysis_reuse
    service.close()


def test_revision_identity_and_invalid_span_profile(media, tmp_path):
    service, repo, registered, ref, profile, _, work = setup(media, tmp_path)
    span = span_for(service, ref, registered.media_streams[0], 0.0, 1.0)
    with service:
        with pytest.raises(ValueError):
            service.prepare_analysis_source(span, profile)
        with pytest.raises(ValueError):
            service.prepare_analysis_source(span, profile, timeline_ref=dict(ref, revision=99))
        malformed = span.model_dump()
        malformed["source_range"]["end_sec"] = -1.0
        with pytest.raises(ValueError):
            service.prepare_analysis_source(malformed, profile, timeline_ref=ref)
        with pytest.raises(ValueError):
            service.prepare_analysis_source(span, "480p", timeline_ref=ref)
        bad = span.model_copy(update={"source_range": span.source_range.model_copy(update={"start_sec": 0.1})})
        with pytest.raises(ValueError):
            service.prepare_analysis_source(bad, profile, timeline_ref=ref)
        first = service.prepare_analysis_source(span, profile, timeline_ref=ref)
        new = service.get_timeline(ref["timeline_id"], 1).model_copy(update={"revision": 2})
        repo.add_timeline(new)
        second = service.prepare_analysis_source(span, profile, timeline_ref=dict(ref, revision=2))
        assert first.analysis_source_ref != second.analysis_source_ref
        assert first.timeline_ref.revision == 1 and second.timeline_ref.revision == 2
        with media.open("ab") as file:  # 자동 생성한 테스트 원본만 변경한다.
            file.write(b"changed")
        with pytest.raises(RecordingCapabilityError) as caught:
            service.prepare_analysis_source(span, profile, timeline_ref=ref)
        assert caught.value.code == "SOURCE_UNAVAILABLE"
    assert not list(work.iterdir())


@pytest.mark.parametrize("condition,code", [
    ("missing", "SOURCE_UNAVAILABLE"),
    ("source_unavailable", "SOURCE_UNAVAILABLE"),
    ("stream_unavailable", "STREAM_UNAVAILABLE"),
    ("partial_stream", "STREAM_UNAVAILABLE"),
    ("inspection_failure", "SOURCE_INSPECTION_FAILED"),
    ("unknown_coverage", "STREAM_COVERAGE_UNKNOWN"),
])
def test_resolution_runtime_failure_preserves_code(media, tmp_path, monkeypatch, condition, code):
    service, repo, registered, ref, profile, _, work = setup(media, tmp_path)
    video = registered.media_streams[0]
    span = span_for(service, ref, video, 0.0, 1.0)
    with service:
        if condition == "missing":
            media.unlink()  # tmp_path에서 생성한 테스트 원본만 삭제한다.
        elif condition == "source_unavailable":
            repo.add_source_asset(registered.source_asset.model_copy(update={"availability": "UNAVAILABLE"}))
        elif condition == "inspection_failure":
            def fail(*args):
                raise RecordingCapabilityError("TEMPORARY_FAILURE", "private path")
            monkeypatch.setattr("daesingo.recording.spans.inspect_local_source", fail)
        else:
            update = ({"availability": "UNAVAILABLE"} if condition == "stream_unavailable"
                      else {"duration_sec": 0.5 if condition == "partial_stream" else None})
            repo.add_media_stream(video.model_copy(update=update))
        with pytest.raises(RecordingCapabilityError) as caught:
            service.prepare_analysis_source(span, profile, timeline_ref=ref)
        assert caught.value.code == code
        assert media.name not in str(caught.value) and "private path" not in str(caught.value)
        assert not service._local_analysis and not service._analysis_reuse
        assert not list(work.iterdir())


def test_public_example_and_profile_configuration_is_opaque(media, tmp_path):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, "-m", "examples.recording_analysis_source", str(media),
        "--video-index", "1", "--start", "0.35", "--end", "1.26"], cwd=root,
        env=dict(os.environ, PYTHONPATH=str(root / "src"), PYTHONIOENCODING="utf-8"),
        capture_output=True, check=True, timeout=30)
    payload = json.loads(result.stdout)
    assert payload["reused"] and payload["content_type"] == "video/mp4"
    assert payload["analysis_source"]["duration_sec"] == 0.9
    assert payload["analysis_source"]["profile_ref"]
    assert media.name not in result.stdout.decode("utf-8") and not result.stderr


def test_fixture_prepare_and_open_are_unchanged():
    from daesingo.recording import load_recording_fixture
    fixture = load_recording_fixture("scenario_happy_001")
    with RecordingService.from_fixture(fixture) as service:
        span = fixture.span_resolutions[0].spans[0]
        expected = fixture.analysis_sources[0]
        source = service.prepare_analysis_source(span, expected.profile_ref)
        assert source == expected
        first = service.open_analysis_source(source.analysis_source_ref)
        second = service.open_analysis_source(source.analysis_source_ref)
        with first.stream, second.stream:
            assert first.stream is not second.stream
            assert first.stream.read(4) == second.stream.read(4)
            assert first.byte_size == expected.byte_size


def test_opt_in_real_analysis_source(tmp_path):
    value = os.environ.get("DAESINGO_RECORDING_VIDEO")
    if not value:
        pytest.skip("DAESINGO_RECORDING_VIDEO 미지정")
    path = Path(value)
    before = fingerprint(path)
    service, _, registered, ref, profile, _, work = setup(path, tmp_path)
    videos = [s for s in registered.media_streams if s.media_type == "VIDEO"]
    assert len(videos) == 1
    reports = []
    with service:
        for start, end in [(0.0, registered.source_asset.duration_sec), (3.7,18.4)]:
            span = span_for(service, ref, videos[0], start, end)
            source = service.prepare_analysis_source(span, profile, timeline_ref=ref)
            assert source == service.prepare_analysis_source(span, profile, timeline_ref=ref)
            inspect_bytes(service, source, tmp_path)
            assert source.timeline_ref.model_dump() == ref
            assert source.media_stream_refs == [videos[0].media_stream_ref]
            assert not list(work.iterdir())
            reports.append({"requested": [start,end], "actual_range": source.timeline_range.model_dump(),
                            "duration": source.duration_sec, "bytes": source.byte_size})
    assert not list(work.iterdir()) and not service._local_analysis
    assert fingerprint(path) == before
    print(json.dumps({"results": reports, "original_unchanged": True, "cleanup": True}))
