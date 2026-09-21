"""실제 생성 영상 smoke + probe 경계 실패/계약 회귀 검사."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from daesingo.recording import (
    FfprobeMediaProbe, MediaStream, RecordingCapabilityError, RecordingService, SourceAsset,
)
from daesingo.recording.repository import InMemoryRecordingRepository


@pytest.fixture(scope="module")
def generated_video(tmp_path_factory):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("실제 media smoke에는 ffmpeg와 ffprobe가 필요합니다")
    path = tmp_path_factory.mktemp("recording media") / "테스트 영상.mkv"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-n",
         "-f", "lavfi", "-i", "color=c=blue:s=64x48:r=10:d=1",
         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=8000:duration=1",
         "-map", "0:v", "-map", "0:v", "-map", "1:a",
         "-c:v", "ffv1", "-c:a", "pcm_s16le", str(path)],
        check=True, capture_output=True, timeout=30,
    )
    return path


def fingerprint(path):
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    stat = path.stat()
    return digest, stat.st_size, stat.st_mtime_ns


def test_real_ffprobe_registration_preserves_source_and_contract(generated_video):
    before = fingerprint(generated_video)
    repo = InMemoryRecordingRepository()
    service = RecordingService(repo)
    result = service.register_local_source(generated_video)
    asset, streams = result.source_asset, result.media_streams

    assert fingerprint(generated_video) == before
    assert asset.byte_size == before[1]
    assert asset.duration_sec == pytest.approx(1.0, abs=0.01)
    assert asset.availability == "AVAILABLE"
    assert asset.external_source_ref is None
    assert [s.media_type for s in streams] == ["VIDEO", "VIDEO", "AUDIO"]
    assert [s.role for s in streams] == ["UNKNOWN", "UNKNOWN", None]
    assert all(s.availability == "UNKNOWN" for s in streams)
    assert asset.media_stream_refs == [s.media_stream_ref for s in streams]
    assert len(set(asset.media_stream_refs)) == 3
    assert all(s.source_asset_ref == asset.source_asset_ref for s in streams)
    assert SourceAsset.model_validate_json(asset.model_dump_json()) == asset
    for stream in streams:
        assert MediaStream.model_validate_json(stream.model_dump_json()) == stream
        assert repo.get_media_stream(stream.media_stream_ref) == stream
    internal = repo.get_local_source(asset.source_asset_ref)
    assert internal.path == generated_video.resolve()
    assert internal.sha256 == before[0]
    assert [repo.get_local_stream_index(s.media_stream_ref) for s in streams] == [0, 1, 2]
    public = asset.model_dump_json() + "".join(s.model_dump_json() for s in streams) + repr(result)
    assert generated_video.name not in public
    assert str(generated_video.parent) not in public
    assert "sha256" not in public
    assert "path" not in public
    # 등록은 파일이나 기존 등록을 덮어쓰지 않는다. dedup은 이번 범위가 아니다.
    second = service.register_local_source(generated_video)
    assert second.source_asset.source_asset_ref != asset.source_asset_ref
    assert not set(second.source_asset.media_stream_refs).intersection(asset.media_stream_refs)
    assert fingerprint(generated_video) == before


def test_corrupt_file_is_not_registered(tmp_path):
    if not shutil.which("ffprobe"):
        pytest.skip("ffprobe가 필요합니다")
    path = tmp_path / "broken.mp4"
    path.write_bytes(b"not a media container")
    before = fingerprint(path)
    repo = InMemoryRecordingRepository()
    with pytest.raises(RecordingCapabilityError, match="조사하지 못") as caught:
        RecordingService(repo).register_local_source(path)
    assert caught.value.code == "TEMPORARY_FAILURE"
    assert str(path) not in str(caught.value)
    assert not repo._source_assets and not repo._media_streams and not repo._local_sources
    assert fingerprint(path) == before


def test_public_consumer_example_outputs_only_contract_objects(generated_video):
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONPATH=str(root / "src"), PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "examples.recording_register_local", str(generated_video)],
        cwd=root, env=env, capture_output=True, timeout=30, check=True,
    )
    output = result.stdout.decode("utf-8")
    payload = json.loads(output)
    assert set(payload) == {"source_asset", "media_streams"}
    assert SourceAsset.model_validate(payload["source_asset"]).byte_size == generated_video.stat().st_size
    assert len([MediaStream.model_validate(item) for item in payload["media_streams"]]) == 3
    assert generated_video.name not in output
    assert not result.stderr

    failed = subprocess.run(
        [sys.executable, "-m", "examples.recording_register_local", str(generated_video.parent / "missing.mp4")],
        cwd=root, env=env, capture_output=True, timeout=30,
    )
    assert failed.returncode == 1
    assert set(json.loads(failed.stdout)) == {"error"}
    assert b"missing.mp4" not in failed.stdout
    assert not failed.stderr


@pytest.fixture
def probe_input(tmp_path):
    # adapter 응답/오류 제어용 파일. 실제 영상 검증은 위 smoke가 담당한다.
    path = tmp_path / "private name.mp4"
    path.write_bytes(b"adapter test input")
    return path


def mock_response(monkeypatch, payload):
    def run(command, **kwargs):
        assert isinstance(command, list)
        assert kwargs.get("shell", False) is False
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["timeout"] > 0
        return subprocess.CompletedProcess(command, 0, json.dumps(payload).encode(), b"")
    monkeypatch.setattr("daesingo.recording.probe.subprocess.run", run)


def test_durations_are_stream_specific_and_missing_is_null(monkeypatch, probe_input):
    mock_response(monkeypatch, {
        "format": {"duration": "12.5"},
        "streams": [
            {"index": 3, "codec_type": "video", "duration": "10.25"},
            {"index": 7, "codec_type": "audio", "duration": "N/A"},
            {"index": 8, "codec_type": "subtitle"},
            {"index": 9, "codec_type": "video", "disposition": {"attached_pic": 1}},
        ],
    })
    repo = InMemoryRecordingRepository()
    result = RecordingService(repo).register_local_source(probe_input)
    assert result.source_asset.duration_sec == 12.5
    assert [s.duration_sec for s in result.media_streams] == [10.25, None]
    assert [repo.get_local_stream_index(s.media_stream_ref) for s in result.media_streams] == [3, 7]


def test_missing_format_and_stream_duration_remain_unknown(monkeypatch, probe_input):
    mock_response(monkeypatch, {"streams": [{"index": 0, "codec_type": "video"}]})
    result = RecordingService().register_local_source(probe_input)
    assert result.source_asset.duration_sec is None
    assert result.media_streams[0].duration_sec is None


@pytest.mark.parametrize("payload", [
    {}, {"streams": []}, {"streams": [{"index": 0, "codec_type": "audio"}]},
    {"streams": [{"index": 0, "codec_type": "video", "disposition": {"attached_pic": 1}}]},
    {"streams": [{"index": -1, "codec_type": "video"}]},
    {"streams": [{"index": True, "codec_type": "video"}]},
    {"streams": [{"index": 0, "codec_type": {}}]},
    {"streams": [{"index": 0, "codec_type": "video"}, {"index": 0, "codec_type": "audio"}]},
    *[{"streams": [{"index": 0, "codec_type": "video", "duration": value}]}
      for value in ["NaN", "inf", "-1", "invalid", True]],
])
def test_invalid_or_unsupported_metadata_is_not_registered(monkeypatch, probe_input, payload):
    mock_response(monkeypatch, payload)
    repo = InMemoryRecordingRepository()
    with pytest.raises(ValueError):
        RecordingService(repo).register_local_source(probe_input)
    assert not repo._source_assets and not repo._media_streams


@pytest.mark.parametrize("failure", ["timeout", "missing_tool", "permission", "bad_json", "failed"])
def test_probe_failures_do_not_leak_paths_or_register(monkeypatch, probe_input, failure):
    def run(command, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 30, stderr=str(probe_input))
        if failure == "missing_tool":
            raise FileNotFoundError(str(probe_input))
        if failure == "permission":
            raise PermissionError(str(probe_input))
        return subprocess.CompletedProcess(command, 0 if failure == "bad_json" else 1,
                                           b"not json", str(probe_input).encode())
    monkeypatch.setattr("daesingo.recording.probe.subprocess.run", run)
    repo = InMemoryRecordingRepository()
    with pytest.raises((RecordingCapabilityError, ValueError)) as caught:
        RecordingService(repo).register_local_source(probe_input)
    assert str(probe_input) not in str(caught.value)
    assert not repo._source_assets and not repo._local_sources


def test_source_change_during_probe_prevents_registration(monkeypatch, probe_input):
    def run(command, **kwargs):
        probe_input.write_bytes(b"changed by external process")
        return subprocess.CompletedProcess(command, 0,
            b'{"streams":[{"index":0,"codec_type":"video"}]}', b"")
    monkeypatch.setattr("daesingo.recording.probe.subprocess.run", run)
    repo = InMemoryRecordingRepository()
    with pytest.raises(RecordingCapabilityError, match="원본 변경"):
        RecordingService(repo).register_local_source(probe_input)
    assert not repo._source_assets and not repo._local_sources


def test_missing_file_and_directory_do_not_invoke_probe(monkeypatch, tmp_path):
    def unexpected(*args, **kwargs):
        pytest.fail("유효하지 않은 경로에 ffprobe를 실행했습니다")
    monkeypatch.setattr("daesingo.recording.probe.subprocess.run", unexpected)
    with pytest.raises(RecordingCapabilityError):
        RecordingService().register_local_source(tmp_path / "absent.mp4")
    with pytest.raises(ValueError):
        RecordingService().register_local_source(tmp_path)


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_invalid_probe_timeout(timeout):
    with pytest.raises(ValueError):
        FfprobeMediaProbe(timeout_sec=timeout)


def test_opt_in_real_local_video():
    path = os.environ.get("DAESINGO_RECORDING_VIDEO")
    if not path:
        pytest.skip("DAESINGO_RECORDING_VIDEO 미지정: 실제 사용자 영상 검증 미실행")
    original = Path(path)
    before = fingerprint(original)
    result = RecordingService().register_local_source(original)
    assert result.source_asset.byte_size == before[1]
    assert any(stream.media_type == "VIDEO" for stream in result.media_streams)
    assert fingerprint(original) == before
