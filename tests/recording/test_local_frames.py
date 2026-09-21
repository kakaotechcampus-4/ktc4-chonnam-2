"""실제 원본 frame decode, canonical identity, 오류 및 원본 보존 검증."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from daesingo.recording import FrameRef, RecordingCapabilityError, RecordingService
from daesingo.recording.frames import FfmpegFrameExtractor
from daesingo.recording.probe import LocalSource, ProbedStream


def fingerprint(path):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    info = path.stat()
    return info.st_size, info.st_mtime_ns, digest


def locate(service, ref, offset):
    return service.resolve_frame({"kind": "STREAM_POSITION", "media_stream_ref": ref,
                                  "source_offset_sec": offset})


@pytest.fixture
def media(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("media smoke에는 ffmpeg/ffprobe가 필요합니다")
    path = tmp_path / "비공개 원본.mkv"
    subprocess.run([
        "ffmpeg", "-nostdin", "-v", "error", "-n",
        "-f", "lavfi", "-i", "color=c=red:s=64x48:r=10:d=1",
        "-f", "lavfi", "-i", "color=c=blue:s=32x24:r=5:d=1",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-map", "0:v", "-map", "2:a", "-map", "1:v",
        "-c:v", "ffv1", "-c:a", "pcm_s16le", str(path),
    ], check=True, capture_output=True, timeout=30)
    return path


def pixels(content):
    return subprocess.run([
        "ffmpeg", "-nostdin", "-v", "error", "-i", "pipe:0", "-frames:v", "1",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
    ], input=content, check=True, capture_output=True, timeout=30).stdout


def test_actual_pixels_positions_identity_and_original_preserved(media):
    before = fingerprint(media)
    service = RecordingService()
    registered = service.register_local_source(media)
    video_a, audio, video_b = registered.media_streams
    first = locate(service, video_a.media_stream_ref, 0.11)
    same = locate(service, video_a.media_stream_ref, 0.19)
    other = locate(service, video_b.media_stream_ref, 0.11)
    assert first.source_offset_sec == same.source_offset_sec == other.source_offset_sec == 0.2
    assert first == same
    assert first.frame_ref != other.frame_ref
    assert FrameRef.model_validate_json(first.model_dump_json()) == first
    assert media.name not in first.model_dump_json()
    red = pixels(service.read_frame(first.frame_ref))
    blue = pixels(service.read_frame(other.frame_ref))
    assert len(red) == 64 * 48 * 3 and red[0] > 240 and red[1] < 10 and red[2] < 10
    assert len(blue) == 32 * 24 * 3 and blue[2] > 240 and blue[0] < 10
    assert service.read_frame(first.frame_ref) == service.read_frame(same.frame_ref)
    assert all(s.availability == "UNKNOWN" for s in registered.media_streams)
    with pytest.raises(RecordingCapabilityError) as caught:
        locate(service, audio.media_stream_ref, 0.0)
    assert caught.value.code == "FRAME_NOT_FOUND"
    # stream duration이 없는 MKV도 decoded EOF에서 실패하며 마지막 frame을 재사용하지 않는다.
    with pytest.raises(RecordingCapabilityError) as caught:
        locate(service, video_a.media_stream_ref, 1.0)
    assert caught.value.code == "FRAME_NOT_FOUND"
    assert fingerprint(media) == before


def test_nonzero_start_pts_is_normalized(media, tmp_path):
    shifted = tmp_path / "shifted.mkv"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-i", str(media),
                    "-map", "0:0", "-vf", "setpts=PTS+5/TB", "-c:v", "ffv1", str(shifted)],
                   check=True, capture_output=True, timeout=30)
    service = RecordingService()
    registered = service.register_local_source(shifted)
    frame = locate(service, registered.media_streams[0].media_stream_ref, 0.11)
    assert frame.source_offset_sec == 0.2


def test_changed_source_rejected_but_published_bytes_stable(media):
    service = RecordingService()
    registered = service.register_local_source(media)
    ref = registered.media_streams[0].media_stream_ref
    frame = locate(service, ref, 0.0)
    content = service.read_frame(frame.frame_ref)
    # 자동 생성한 테스트 파일만 변경한다.
    with media.open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(RecordingCapabilityError) as caught:
        locate(service, ref, 0.0)
    assert caught.value.code == "STREAM_UNAVAILABLE"
    assert media.name not in str(caught.value)
    assert service.read_frame(frame.frame_ref) == content


@pytest.mark.parametrize("offset", [-1.0, float("nan"), float("inf")])
def test_invalid_position_is_validation_error(offset):
    with pytest.raises(ValueError):
        locate(RecordingService(), "unknown", offset)


def test_unknown_refs():
    service = RecordingService()
    for action in [lambda: locate(service, "unknown", 0.0), lambda: service.read_frame("unknown")]:
        with pytest.raises(RecordingCapabilityError) as caught:
            action()
        assert caught.value.code == "UNKNOWN_REF"


def test_known_duration_boundary_and_missing_source(media):
    service = RecordingService()
    registered = service.register_local_source(media)
    stream = registered.media_streams[0]
    service._repository.add_media_stream(stream.model_copy(update={"duration_sec": 1.0}))
    with pytest.raises(RecordingCapabilityError) as caught:
        locate(service, stream.media_stream_ref, 1.0)
    assert caught.value.code == "OUT_OF_RANGE"
    # tmp_path 아래 자동 생성한 테스트 파일만 삭제한다.
    media.unlink()
    with pytest.raises(RecordingCapabilityError) as caught:
        locate(service, stream.media_stream_ref, 0.0)
    assert caught.value.code == "STREAM_UNAVAILABLE"
    assert not service._repository._frames


@pytest.mark.parametrize("mode", ["precision", "mutation", "bad_timebase", "before_request"])
def test_adapter_integrity_and_integer_pts(tmp_path, monkeypatch, mode):
    path = tmp_path / "adapter-unit-input"
    path.write_bytes(b"unit-only; not real media")
    size, mtime, digest = fingerprint(path)
    source = LocalSource(path, size, mtime, digest, None, (ProbedStream(0, "VIDEO", None),))
    # subprocess 출력 구조만 검증하는 unit double. 실제 PNG decode는 media smoke에서 검증한다.
    png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x00IEND\xaeB`\x82"

    def run(argv, **kwargs):
        assert argv[argv.index("-map") + 1] == "0:0"
        assert argv[-1] == "pipe:1" and "-y" not in argv
        if mode == "mutation":
            path.write_bytes(b"changed during decode")
        base = "1/0" if mode == "bad_timebase" else "1/90000"
        pts = "0" if mode == "before_request" else "90001"
        log = f"[Parsed_showinfo_2 @ abc] config in time_base: {base}, frame_rate: 30/1\n"
        log += f"[Parsed_showinfo_2 @ abc] n: 0 pts: {pts} pts_time: 1.00001\n"
        return subprocess.CompletedProcess(argv, 0, png, log.encode())

    monkeypatch.setattr("daesingo.recording.frames.subprocess.run", run)
    if mode == "precision":
        assert FfmpegFrameExtractor().extract(source, 0, 1.0).source_offset_sec == 90001 / 90000
    else:
        with pytest.raises(RecordingCapabilityError) as caught:
            FfmpegFrameExtractor().extract(source, 0, 1.0)
        assert caught.value.code == ("STREAM_UNAVAILABLE" if mode == "mutation" else "TEMPORARY_FAILURE")


@pytest.mark.parametrize("outcome,code", [
    ("timeout", "TEMPORARY_FAILURE"), ("missing_tool", "TEMPORARY_FAILURE"),
    ("decode_failure", "STREAM_UNAVAILABLE"), ("empty", "FRAME_NOT_FOUND"),
    ("bad_metadata", "TEMPORARY_FAILURE"), ("bad_png", "TEMPORARY_FAILURE"),
])
def test_adapter_failures_never_publish_frame(media, monkeypatch, outcome, code):
    service = RecordingService()
    registered = service.register_local_source(media)

    def run(*args, **kwargs):
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(str(media), 1)
        if outcome == "missing_tool":
            raise FileNotFoundError(str(media))
        return subprocess.CompletedProcess([], 1 if outcome == "decode_failure" else 0,
            b"" if outcome == "empty" else b"bad" if outcome == "bad_png" else b"\x89PNG\r\n\x1a\n",
            str(media).encode())

    monkeypatch.setattr("daesingo.recording.frames.subprocess.run", run)
    with pytest.raises(RecordingCapabilityError) as caught:
        locate(service, registered.media_streams[0].media_stream_ref, 0.0)
    assert caught.value.code == code
    assert str(media) not in str(caught.value)
    assert not service._repository._frames


def test_public_example(media):
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONPATH=str(root / "src"), PYTHONIOENCODING="utf-8")
    result = subprocess.run([sys.executable, "-m", "examples.recording_local_frame", str(media),
                             "--video-index", "1", "--offset", "0.11"],
                            cwd=root, env=env, check=True, capture_output=True, timeout=30)
    payload = json.loads(result.stdout)
    assert payload["frame"]["source_offset_sec"] == 0.2
    assert payload["png_byte_size"] > 0
    assert media.name not in result.stdout.decode("utf-8")
    assert not result.stderr


def test_opt_in_real_source_frames():
    configured = os.environ.get("DAESINGO_RECORDING_VIDEO")
    if not configured:
        pytest.skip("DAESINGO_RECORDING_VIDEO 미지정")
    path = Path(configured)
    before = fingerprint(path)
    service = RecordingService()
    registered = service.register_local_source(path)
    for stream in registered.media_streams:
        if stream.media_type != "VIDEO":
            continue
        frame = locate(service, stream.media_stream_ref, 1.01)
        assert 1.01 <= frame.source_offset_sec < 2.0
        assert frame == locate(service, stream.media_stream_ref, 1.01)
        assert pixels(service.read_frame(frame.frame_ref))
        assert path.name not in frame.model_dump_json()
    assert fingerprint(path) == before
