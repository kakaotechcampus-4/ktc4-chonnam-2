"""실제 clip 생성과 Readout의 원본 frame 소비 경계를 검증한다."""

from dataclasses import replace
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from daesingo.recording import (
    IncidentClip, IncidentClipEncoding, LocalIncidentMaterializer, RecordingCapabilityError, RecordingService,
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
        pytest.skip("ffmpeg/ffprobe 필요")
    path = tmp_path / "clip 원본.avi"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
        "testsrc2=s=160x90:r=10:d=2", "-f", "lavfi", "-i", "sine=duration=2",
        "-c:v", "mpeg4", "-c:a", "pcm_s16le", str(path)],
        check=True, capture_output=True, timeout=30)
    return path


def setup(path, tmp_path):
    work = tmp_path / "clip-work"
    work.mkdir()
    adapter = LocalIncidentMaterializer(IncidentClipEncoding(480, "veryfast", 23), temp_root=work)
    repo = InMemoryRecordingRepository()
    service = RecordingService(repo, incident_materializer=adapter)
    registered = service.register_local_source(path)
    timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
    video, = [s for s in registered.media_streams if s.media_type == "VIDEO"]
    ref = {"timeline_id": timeline.timeline_id, "revision": 1}
    return service, repo, registered, ref, video, adapter, work


def resolution(service, ref, video, start, end):
    return service.resolve_span(ref, {"start_sec": start, "end_sec": end}, media_stream_ref=video.media_stream_ref)


def inspect_materialized_bytes(service, clip, tmp_path):
    # 내부 bytes의 측정값을 검증하는 테스트 전용 접근이다. Readout 공개 API가 아니다.
    content = service._local_clips[clip.incident_clip_ref][1]
    assert clip.byte_size == len(content) > 0
    target = tmp_path / "clip-verification.mp4"
    try:
        target.write_bytes(content)
        run = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(target)],
                             check=True, capture_output=True, timeout=30)
        data = json.loads(run.stdout)
        assert float(data["format"]["duration"]) == clip.duration_sec
        assert len(data["streams"]) == 1 and data["streams"][0]["codec_type"] == "video"
        assert data["streams"][0]["codec_name"] == "h264"
    finally:
        target.unlink(missing_ok=True)


def readout_frame(service, clip):
    stored = service.get_incident_clip(clip.incident_clip_ref)
    span, = stored.source_provenance.asset_spans
    frame = service.resolve_frame({"kind": "STREAM_POSITION", "media_stream_ref": span.media_stream_ref,
                                   "source_offset_sec": span.source_range.start_sec + 0.01})
    assert frame.media_stream_ref == span.media_stream_ref
    assert span.source_range.start_sec <= frame.source_offset_sec < span.source_range.end_sec
    image = service.read_frame(frame.frame_ref)
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", "pipe:0", "-f", "null", "-"],
                   input=image, check=True, capture_output=True, timeout=30)
    return frame


def test_provenance_actual_metadata_identity_and_readout(media, tmp_path):
    before = fingerprint(media)
    service, _, _, ref, video, _, work = setup(media, tmp_path)
    requested = resolution(service, ref, video, 0.35, 1.26)
    original = requested.model_dump(mode="json")
    with service:
        clip = service.build_incident_clip(requested)
        # Producer 직렬화 convention만 검증한다. Consumer의 종류/lineage 판정에는 사용하지 않는다.
        assert re.fullmatch(r"clip_[0-9a-f]{32}", clip.incident_clip_ref)
        assert IncidentClip.model_validate_json(clip.model_dump_json()) == clip
        assert clip.availability == "AVAILABLE" and clip.duration_sec == 0.9
        assert clip.timeline_range.start_sec == 0.4 and clip.timeline_range.end_sec == 1.3
        assert clip.source_provenance.timeline_ref == requested.timeline_ref
        assert clip.source_provenance.requested_range == requested.requested_range
        assert clip.source_provenance.asset_spans == requested.spans
        assert clip.media_stream_refs == [video.media_stream_ref]
        assert "profile_ref" not in clip.model_dump() and "source_profile" not in clip.model_dump()
        assert media.name not in clip.model_dump_json()
        assert service.build_incident_clip(requested).incident_clip_ref == clip.incident_clip_ref
        inspect_materialized_bytes(service, clip, tmp_path)
        readout_frame(service, clip)
        assert not hasattr(service, "open_incident_clip")
        assert requested.model_dump(mode="json") == original
        clip.source_provenance.asset_spans.clear()
        assert service.get_incident_clip(clip.incident_clip_ref).source_provenance.asset_spans
        fetched = service.get_incident_clip(clip.incident_clip_ref)
        fetched.media_stream_refs.clear()
        assert service.get_incident_clip(clip.incident_clip_ref).media_stream_refs == [video.media_stream_ref]
        assert not list(work.iterdir())
    assert not service._local_clips and not service._clip_identity and not list(work.iterdir())
    with pytest.raises(RecordingCapabilityError) as caught:
        service.get_incident_clip(clip.incident_clip_ref)
    assert caught.value.code == "UNAVAILABLE"
    assert fingerprint(media) == before


def test_changed_provenance_revision_bytes_and_conditions_get_new_refs(media, tmp_path, monkeypatch):
    service, repo, _, ref, video, adapter, _ = setup(media, tmp_path)
    with service:
        requested = resolution(service, ref, video, 0.0, 1.0)
        first = service.build_incident_clip(requested)
        new = service.get_timeline(ref["timeline_id"], 1).model_copy(update={"revision": 2})
        repo.add_timeline(new)
        second = service.build_incident_clip(resolution(service, dict(ref, revision=2), video, 0.0, 1.0))
        different_range = service.build_incident_clip(resolution(service, ref, video, 0.0, 1.5))
        real = adapter.materialize
        def changed_bytes(*args):
            prepared = real(*args)
            # 유효한 빈 MP4 free box를 추가하여 다른 실제 bytes를 모사한다.
            return replace(prepared, content=prepared.content + b"\x00\x00\x00\x08free")
        monkeypatch.setattr(adapter, "materialize", changed_bytes)
        third = service.build_incident_clip(requested)
        inspect_materialized_bytes(service, third, tmp_path)
        assert len({first.incident_clip_ref, second.incident_clip_ref, third.incident_clip_ref,
                    different_range.incident_clip_ref}) == 4
        assert service.get_incident_clip(first.incident_clip_ref) == first
        # 같은 bytes라도 다른 생성 조건은 이전 ref를 공유하지 않는다.
        monkeypatch.setattr(adapter, "_identity", ("different-test-condition",))
        fourth = service.build_incident_clip(requested)
        assert fourth.incident_clip_ref != third.incident_clip_ref


def test_partial_boundary_request_keeps_requested_provenance(media, tmp_path):
    service, _, _, ref, video, _, _ = setup(media, tmp_path)
    requested = resolution(service, ref, video, 1.0, 3.0)
    assert requested.status == "PARTIAL"
    with service:
        clip = service.build_incident_clip(requested)
        assert clip.source_provenance.requested_range.end_sec == 3.0
        assert clip.source_provenance.asset_spans == requested.spans
        assert clip.timeline_range.end_sec == 2.0 and clip.duration_sec == 1.0


@pytest.mark.parametrize("failure", ["changed", "missing", "encoder", "timeout", "wrong_span", "multiple", "failed"])
def test_build_failure_and_cleanup(media, tmp_path, failure, monkeypatch):
    service, _, _, ref, video, adapter, work = setup(media, tmp_path)
    requested = resolution(service, ref, video, 0.0, 1.0)
    if failure == "changed":
        with media.open("ab") as file:
            file.write(b"changed")  # 자동 생성한 테스트 원본만 변경한다.
    elif failure == "missing":
        media.unlink()
    elif failure in {"encoder", "timeout"}:
        original = adapter._engine._run
        def run(args):
            if args[0] == "ffmpeg":
                Path(args[-1]).write_bytes(b"partial")
                if failure == "timeout":
                    raise subprocess.TimeoutExpired("private path", 1)
                raise RecordingCapabilityError("TEMPORARY_FAILURE", "private path")
            return original(args)
        monkeypatch.setattr(adapter._engine, "_run", run)
    elif failure == "failed":
        requested = resolution(service, ref, video, 2.0, 3.0)
    else:
        payload = requested.model_dump()
        if failure == "wrong_span":
            payload["spans"][0]["source_range"]["start_sec"] = 0.1
        else:
            second = dict(payload["spans"][0], sequence=1, media_stream_ref="unregistered-other-video")
            payload["spans"].append(second)
        requested = payload
    with service, pytest.raises(RecordingCapabilityError) as caught:
        service.build_incident_clip(requested)
    assert caught.value.code == "INCIDENT_CLIP_BUILD_FAILED"
    assert "private path" not in str(caught.value) and media.name not in str(caught.value)
    assert not service._local_clips and not list(work.iterdir())


def test_fixture_compatibility():
    from daesingo.recording import load_recording_fixture
    fixture = load_recording_fixture("scenario_happy_001")
    service = RecordingService.from_fixture(fixture)
    clip = service.build_incident_clip(fixture.span_resolutions[0])
    assert clip == fixture.incident_clips[0]
    assert service.get_incident_clip(clip.incident_clip_ref) == clip


def test_public_example_uses_original_frame_path(media):
    before = fingerprint(media)
    root = Path(__file__).resolve().parents[2]
    output = subprocess.run([sys.executable, "-m", "examples.recording_incident_clip", str(media),
        "--video-index", "0", "--start", "0.35", "--end", "1.26"], cwd=root,
        env=dict(os.environ, PYTHONPATH=str(root / "src"), PYTHONIOENCODING="utf-8"),
        capture_output=True, check=True, timeout=30)
    payload = json.loads(output.stdout)
    clip = IncidentClip.model_validate(payload["incident_clip"])
    assert payload["frame"]["media_stream_ref"] == clip.source_provenance.asset_spans[0].media_stream_ref
    assert payload["frame_byte_size"] > 0 and clip.byte_size > 0
    assert not output.stderr and media.name not in output.stdout.decode("utf-8")
    assert fingerprint(media) == before


def test_opt_in_real_incident_clip(tmp_path):
    value = os.environ.get("DAESINGO_RECORDING_VIDEO")
    if not value:
        pytest.skip("DAESINGO_RECORDING_VIDEO 미지정")
    path = Path(value)
    before = fingerprint(path)
    service, _, _, ref, video, _, work = setup(path, tmp_path)
    requested = resolution(service, ref, video, 3.7, 8.7)
    with service:
        clip = service.build_incident_clip(requested)
        assert clip == service.build_incident_clip(requested)
        assert clip.source_provenance.asset_spans == requested.spans
        inspect_materialized_bytes(service, clip, tmp_path)
        frame = readout_frame(service, clip)
        assert not list(work.iterdir())
        print(json.dumps({"requested": requested.requested_range.model_dump(),
            "actual": clip.timeline_range.model_dump(), "bytes": clip.byte_size,
            "duration": clip.duration_sec, "frame_offset": frame.source_offset_sec,
            "reused": True}))
    assert fingerprint(path) == before and not list(work.iterdir()) and not service._local_clips
