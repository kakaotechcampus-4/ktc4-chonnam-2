"""Tests for src/daesingo/search/media.py.

All tests that invoke ffmpeg/ffprobe are skipped when the binaries are absent.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

import pytest
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from daesingo.search.config import GeminiSearchConfig
from daesingo.search.execution import DeadlineExceededError, RunDeadline
from daesingo.search.media import (
    ByteSizeMismatchError,
    FfprobeError,
    MediaInput,
    MediaPreparer,
    MediaTooLargeError,
    MissingFfmpegError,
    SourceTooLargeError,
)

# ---------------------------------------------------------------------------
# Skip guards
# ---------------------------------------------------------------------------

_FFMPEG_MISSING = shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None
_NEEDS_FFMPEG = pytest.mark.skipif(_FFMPEG_MISSING, reason="ffmpeg/ffprobe not on PATH")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_CFG = GeminiSearchConfig()


def _real_deadline(budget_ms: int = 120_000) -> RunDeadline:
    return RunDeadline(time.monotonic, budget_ms)


def _make_test_mp4(duration_sec: float = 6.0, size: str = "320x240") -> bytes:
    """Generate a minimal H.264 MP4 using ffmpeg's testsrc."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        out = f.name
    _ = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=duration={duration_sec}:size={size}:rate=25",
            "-c:v",
            "libx264",
            "-an",
            out,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    data = Path(out).read_bytes()
    Path(out).unlink(missing_ok=True)
    return data


def _media_input(data: bytes) -> MediaInput:
    return MediaInput(
        stream=io.BytesIO(data),
        content_type="video/mp4",
        declared_byte_size=len(data),
    )


def _parse_streams(data: bytes) -> list[dict[str, object]]:
    """Parse ffprobe JSON and return the streams list, typed."""

    class _Stream(BaseModel):
        model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")
        codec_type: str = "unknown"

    class _Probe(BaseModel):
        model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")
        streams: list[_Stream] = []

    try:
        probe = TypeAdapter(_Probe).validate_json(data)
    except (ValidationError, ValueError):
        return []
    result: list[dict[str, object]] = []
    for s in probe.streams:
        result.append(s.model_dump())
    return result


def _ffprobe_streams(path: Path) -> list[dict[str, object]]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            str(path),
        ],
        capture_output=True,
        check=True,
    )
    return _parse_streams(result.stdout)


def _video_stream(path: Path) -> dict[str, object]:
    streams = _ffprobe_streams(path)
    video = next(
        (s for s in streams if s.get("codec_type") == "video"),
        None,
    )
    assert video is not None, f"No video stream in {path}"
    return video


def _stream_fps(video: dict[str, object]) -> float:
    r = str(video.get("r_frame_rate", "1/1"))
    num, den = map(int, r.split("/"))
    return num / den


# ---------------------------------------------------------------------------
# Smoke: happy path — coarse only
# ---------------------------------------------------------------------------


@_NEEDS_FFMPEG
def test_prepare_coarse_returns_prepared_media() -> None:
    data = _make_test_mp4(duration_sec=6.0)
    preparer = MediaPreparer(_DEFAULT_CFG)
    with preparer.prepare_coarse(
        _media_input(data), deadline=_real_deadline()
    ) as coarse:
        assert coarse.content_type == "video/mp4"
        assert coarse.byte_size > 0
        tmpdir = coarse.path.parent
    assert not tmpdir.exists(), "temp dir must be cleaned up after `with` block"


# ---------------------------------------------------------------------------
# Smoke: happy path — fine only
# ---------------------------------------------------------------------------


@_NEEDS_FFMPEG
def test_prepare_fine_returns_prepared_media() -> None:
    data = _make_test_mp4(duration_sec=6.0)
    preparer = MediaPreparer(_DEFAULT_CFG)
    with preparer.prepare_fine(
        _media_input(data),
        fine_start_sec=1.0,
        fine_end_sec=4.0,
        deadline=_real_deadline(),
    ) as fine:
        assert fine.content_type == "video/mp4"
        assert fine.byte_size > 0
        tmpdir = fine.path.parent
    assert not tmpdir.exists(), "temp dir must be cleaned up after `with` block"


# ---------------------------------------------------------------------------
# Coarse ffprobe assertions: ≤1 fps, ≤360p, no audio
# ---------------------------------------------------------------------------


@_NEEDS_FFMPEG
def test_coarse_fps_at_most_1() -> None:
    data = _make_test_mp4(duration_sec=6.0, size="640x480")
    preparer = MediaPreparer(_DEFAULT_CFG)
    with preparer.prepare_coarse(
        _media_input(data), deadline=_real_deadline()
    ) as coarse:
        fps = _stream_fps(_video_stream(coarse.path))
        assert fps <= 1.0 + 1e-3, f"Coarse fps={fps} exceeds 1"


@_NEEDS_FFMPEG
def test_coarse_height_at_most_360() -> None:
    data = _make_test_mp4(duration_sec=6.0, size="640x480")
    preparer = MediaPreparer(_DEFAULT_CFG)
    with preparer.prepare_coarse(
        _media_input(data), deadline=_real_deadline()
    ) as coarse:
        video = _video_stream(coarse.path)
        assert int(str(video["height"])) <= 360, (
            f"Coarse height={video['height']} exceeds 360"
        )


@_NEEDS_FFMPEG
def test_coarse_no_audio() -> None:
    data = _make_test_mp4(duration_sec=6.0)
    preparer = MediaPreparer(_DEFAULT_CFG)
    with preparer.prepare_coarse(
        _media_input(data), deadline=_real_deadline()
    ) as coarse:
        audio = [
            s for s in _ffprobe_streams(coarse.path) if s.get("codec_type") == "audio"
        ]
        assert audio == [], "Coarse must have no audio streams"


@_NEEDS_FFMPEG
def test_coarse_origin_spans_full_source() -> None:
    data = _make_test_mp4(duration_sec=6.0)
    preparer = MediaPreparer(_DEFAULT_CFG)
    with preparer.prepare_coarse(
        _media_input(data), deadline=_real_deadline()
    ) as coarse:
        assert coarse.origin_start_sec == 0.0
        assert coarse.origin_end_sec > 0.0


# ---------------------------------------------------------------------------
# Fine ffprobe assertions: ≤2 fps, ≤720p, no audio, expected duration
# ---------------------------------------------------------------------------


@_NEEDS_FFMPEG
def test_fine_fps_at_most_2() -> None:
    data = _make_test_mp4(duration_sec=10.0)
    preparer = MediaPreparer(_DEFAULT_CFG)
    with preparer.prepare_fine(
        _media_input(data),
        fine_start_sec=2.0,
        fine_end_sec=7.0,
        deadline=_real_deadline(),
    ) as fine:
        fps = _stream_fps(_video_stream(fine.path))
        assert fps <= 2.0 + 1e-3, f"Fine fps={fps} exceeds 2"


@_NEEDS_FFMPEG
def test_fine_height_at_most_720() -> None:
    data = _make_test_mp4(duration_sec=10.0, size="1280x720")
    preparer = MediaPreparer(_DEFAULT_CFG)
    with preparer.prepare_fine(
        _media_input(data),
        fine_start_sec=2.0,
        fine_end_sec=7.0,
        deadline=_real_deadline(),
    ) as fine:
        video = _video_stream(fine.path)
        assert int(str(video["height"])) <= 720, (
            f"Fine height={video['height']} exceeds 720"
        )


@_NEEDS_FFMPEG
def test_fine_no_audio() -> None:
    data = _make_test_mp4(duration_sec=10.0)
    preparer = MediaPreparer(_DEFAULT_CFG)
    with preparer.prepare_fine(
        _media_input(data),
        fine_start_sec=2.0,
        fine_end_sec=7.0,
        deadline=_real_deadline(),
    ) as fine:
        audio = [
            s for s in _ffprobe_streams(fine.path) if s.get("codec_type") == "audio"
        ]
        assert audio == [], "Fine must have no audio streams"


@_NEEDS_FFMPEG
def test_fine_duration_matches_clamped_interval() -> None:
    data = _make_test_mp4(duration_sec=10.0)
    preparer = MediaPreparer(_DEFAULT_CFG)
    with preparer.prepare_fine(
        _media_input(data),
        fine_start_sec=2.0,
        fine_end_sec=7.0,
        deadline=_real_deadline(),
    ) as fine:
        # Physical interval is 5s; allow ±1.5s tolerance for encoder rounding
        assert abs(fine.duration_sec - 5.0) <= 1.5, (
            f"Fine duration={fine.duration_sec} not close to expected 5.0s"
        )


@_NEEDS_FFMPEG
def test_fine_interval_clamped_to_source_bounds() -> None:
    """Requesting an interval beyond source end clamps to source duration."""
    data = _make_test_mp4(duration_sec=6.0)
    preparer = MediaPreparer(_DEFAULT_CFG)
    with preparer.prepare_fine(
        _media_input(data),
        fine_start_sec=4.0,
        fine_end_sec=999.0,
        deadline=_real_deadline(),
    ) as fine:
        assert fine.origin_end_sec <= 6.5  # clamped


# ---------------------------------------------------------------------------
# Downscale-only: small input is NOT upscaled
# ---------------------------------------------------------------------------


@_NEEDS_FFMPEG
def test_coarse_does_not_upscale_small_input() -> None:
    data = _make_test_mp4(duration_sec=4.0, size="160x120")
    preparer = MediaPreparer(_DEFAULT_CFG)
    with preparer.prepare_coarse(
        _media_input(data), deadline=_real_deadline()
    ) as coarse:
        video = _video_stream(coarse.path)
        assert int(str(video["height"])) <= 120 + 2, "Small input must not be upscaled"


# ---------------------------------------------------------------------------
# Error paths — coarse: assert temp dir cleaned up
# ---------------------------------------------------------------------------


@_NEEDS_FFMPEG
def test_coarse_declared_size_too_large_raises_and_cleans_up() -> None:
    data = _make_test_mp4(duration_sec=2.0)
    cfg = GeminiSearchConfig(max_materialized_source_bytes=100)
    mi = MediaInput(
        stream=io.BytesIO(data),
        content_type="video/mp4",
        declared_byte_size=len(data),
    )
    preparer = MediaPreparer(cfg)
    recorded: list[str] = []
    real_mkdtemp = tempfile.mkdtemp

    def _capturing_mkdtemp(
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | None = None,
    ) -> str:
        path = real_mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        recorded.append(path)
        return path

    with (
        patch("daesingo.search.media.tempfile.mkdtemp", side_effect=_capturing_mkdtemp),
        pytest.raises(SourceTooLargeError),
        preparer.prepare_coarse(mi, _real_deadline()),
    ):
        pass  # pragma: no cover

    for p in recorded:
        assert not Path(p).exists(), f"temp dir {p} was not cleaned up"


@_NEEDS_FFMPEG
def test_coarse_stream_hard_cap_raises_and_cleans_up() -> None:
    data = _make_test_mp4(duration_sec=4.0)
    cap = len(data) // 2
    cfg = GeminiSearchConfig(max_materialized_source_bytes=cap)
    mi = MediaInput(
        stream=io.BytesIO(data),
        content_type="video/mp4",
        declared_byte_size=cap,
    )
    preparer = MediaPreparer(cfg)
    recorded: list[str] = []
    real_mkdtemp = tempfile.mkdtemp

    def _capturing_mkdtemp(
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | None = None,
    ) -> str:
        path = real_mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        recorded.append(path)
        return path

    with (
        patch("daesingo.search.media.tempfile.mkdtemp", side_effect=_capturing_mkdtemp),
        pytest.raises(SourceTooLargeError),
        preparer.prepare_coarse(mi, _real_deadline()),
    ):
        pass  # pragma: no cover

    assert recorded, "mkdtemp must have been called"
    for p in recorded:
        assert not Path(p).exists(), f"temp dir {p} was not cleaned up"


@_NEEDS_FFMPEG
def test_coarse_byte_size_mismatch_raises_and_cleans_up() -> None:
    data = _make_test_mp4(duration_sec=2.0)
    mi = MediaInput(
        stream=io.BytesIO(data),
        content_type="video/mp4",
        declared_byte_size=len(data) + 9999,
    )
    preparer = MediaPreparer(_DEFAULT_CFG)
    recorded: list[str] = []
    real_mkdtemp = tempfile.mkdtemp

    def _capturing_mkdtemp(
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | None = None,
    ) -> str:
        path = real_mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        recorded.append(path)
        return path

    with (
        patch("daesingo.search.media.tempfile.mkdtemp", side_effect=_capturing_mkdtemp),
        pytest.raises(ByteSizeMismatchError),
        preparer.prepare_coarse(mi, _real_deadline()),
    ):
        pass  # pragma: no cover

    assert recorded, "mkdtemp must have been called"
    for p in recorded:
        assert not Path(p).exists(), f"temp dir {p} was not cleaned up"


@_NEEDS_FFMPEG
def test_coarse_malformed_input_raises_ffprobe_error_and_cleans_up() -> None:
    garbage = b"\x00" * 1024
    mi = MediaInput(
        stream=io.BytesIO(garbage),
        content_type="video/mp4",
        declared_byte_size=len(garbage),
    )
    preparer = MediaPreparer(_DEFAULT_CFG)
    recorded: list[str] = []
    real_mkdtemp = tempfile.mkdtemp

    def _capturing_mkdtemp(
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | None = None,
    ) -> str:
        path = real_mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        recorded.append(path)
        return path

    with (
        patch("daesingo.search.media.tempfile.mkdtemp", side_effect=_capturing_mkdtemp),
        pytest.raises(FfprobeError),
        preparer.prepare_coarse(mi, _real_deadline()),
    ):
        pass  # pragma: no cover

    assert recorded, "mkdtemp must have been called"
    for p in recorded:
        assert not Path(p).exists(), f"temp dir {p} was not cleaned up"


@_NEEDS_FFMPEG
def test_coarse_media_too_large_raises_and_cleans_up() -> None:
    data = _make_test_mp4(duration_sec=6.0)
    cfg = GeminiSearchConfig(max_inline_media_bytes=1)
    preparer = MediaPreparer(cfg)
    recorded: list[str] = []
    real_mkdtemp = tempfile.mkdtemp

    def _capturing_mkdtemp(
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | None = None,
    ) -> str:
        path = real_mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        recorded.append(path)
        return path

    with (
        patch("daesingo.search.media.tempfile.mkdtemp", side_effect=_capturing_mkdtemp),
        pytest.raises(MediaTooLargeError),
        preparer.prepare_coarse(_media_input(data), _real_deadline()),
    ):
        pass  # pragma: no cover

    assert recorded, "mkdtemp must have been called"
    for p in recorded:
        assert not Path(p).exists(), f"temp dir {p} was not cleaned up"


# ---------------------------------------------------------------------------
# Error paths — fine: assert temp dir cleaned up
# ---------------------------------------------------------------------------


@_NEEDS_FFMPEG
def test_fine_declared_size_too_large_raises_and_cleans_up() -> None:
    data = _make_test_mp4(duration_sec=2.0)
    cfg = GeminiSearchConfig(max_materialized_source_bytes=100)
    mi = MediaInput(
        stream=io.BytesIO(data),
        content_type="video/mp4",
        declared_byte_size=len(data),
    )
    preparer = MediaPreparer(cfg)
    recorded: list[str] = []
    real_mkdtemp = tempfile.mkdtemp

    def _capturing_mkdtemp(
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | None = None,
    ) -> str:
        path = real_mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        recorded.append(path)
        return path

    with (
        patch("daesingo.search.media.tempfile.mkdtemp", side_effect=_capturing_mkdtemp),
        pytest.raises(SourceTooLargeError),
        preparer.prepare_fine(mi, 0.0, 2.0, _real_deadline()),
    ):
        pass  # pragma: no cover

    for p in recorded:
        assert not Path(p).exists(), f"temp dir {p} was not cleaned up"


@_NEEDS_FFMPEG
def test_fine_malformed_input_raises_ffprobe_error_and_cleans_up() -> None:
    garbage = b"\x00" * 1024
    mi = MediaInput(
        stream=io.BytesIO(garbage),
        content_type="video/mp4",
        declared_byte_size=len(garbage),
    )
    preparer = MediaPreparer(_DEFAULT_CFG)
    recorded: list[str] = []
    real_mkdtemp = tempfile.mkdtemp

    def _capturing_mkdtemp(
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | None = None,
    ) -> str:
        path = real_mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        recorded.append(path)
        return path

    with (
        patch("daesingo.search.media.tempfile.mkdtemp", side_effect=_capturing_mkdtemp),
        pytest.raises(FfprobeError),
        preparer.prepare_fine(mi, 0.0, 1.0, _real_deadline()),
    ):
        pass  # pragma: no cover

    assert recorded, "mkdtemp must have been called"
    for p in recorded:
        assert not Path(p).exists(), f"temp dir {p} was not cleaned up"


@_NEEDS_FFMPEG
def test_fine_media_too_large_raises_and_cleans_up() -> None:
    data = _make_test_mp4(duration_sec=6.0)
    cfg = GeminiSearchConfig(max_inline_media_bytes=1)
    preparer = MediaPreparer(cfg)
    recorded: list[str] = []
    real_mkdtemp = tempfile.mkdtemp

    def _capturing_mkdtemp(
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | None = None,
    ) -> str:
        path = real_mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        recorded.append(path)
        return path

    with (
        patch("daesingo.search.media.tempfile.mkdtemp", side_effect=_capturing_mkdtemp),
        pytest.raises(MediaTooLargeError),
        preparer.prepare_fine(_media_input(data), 0.0, 6.0, _real_deadline()),
    ):
        pass  # pragma: no cover

    assert recorded, "mkdtemp must have been called"
    for p in recorded:
        assert not Path(p).exists(), f"temp dir {p} was not cleaned up"


@_NEEDS_FFMPEG
def test_exhausted_deadline_raises_before_work() -> None:
    data = _make_test_mp4(duration_sec=2.0)
    clock_val = [0.0]
    dl = RunDeadline(lambda: clock_val[0], budget_ms=1)
    clock_val[0] = 1.0  # now exhausted

    preparer = MediaPreparer(_DEFAULT_CFG)
    with (
        pytest.raises(DeadlineExceededError),
        preparer.prepare_coarse(_media_input(data), dl),
    ):
        pass  # pragma: no cover


# ---------------------------------------------------------------------------
# Cleanup on success
# ---------------------------------------------------------------------------


@_NEEDS_FFMPEG
def test_coarse_temp_dir_cleaned_up_on_success() -> None:
    data = _make_test_mp4(duration_sec=4.0)
    preparer = MediaPreparer(_DEFAULT_CFG)
    tmpdir_path: Path | None = None
    with preparer.prepare_coarse(
        _media_input(data), deadline=_real_deadline()
    ) as coarse:
        tmpdir_path = coarse.path.parent
        assert tmpdir_path.exists(), "temp dir must exist inside the `with` block"
    assert tmpdir_path is not None
    assert not tmpdir_path.exists(), "temp dir must be gone after `with` block"


@_NEEDS_FFMPEG
def test_fine_temp_dir_cleaned_up_on_success() -> None:
    data = _make_test_mp4(duration_sec=4.0)
    preparer = MediaPreparer(_DEFAULT_CFG)
    tmpdir_path: Path | None = None
    with preparer.prepare_fine(
        _media_input(data),
        fine_start_sec=0.0,
        fine_end_sec=4.0,
        deadline=_real_deadline(),
    ) as fine:
        tmpdir_path = fine.path.parent
        assert tmpdir_path.exists(), "temp dir must exist inside the `with` block"
    assert tmpdir_path is not None
    assert not tmpdir_path.exists(), "temp dir must be gone after `with` block"


# ---------------------------------------------------------------------------
# Missing binary error (no ffmpeg skip — we test the production error path)
# ---------------------------------------------------------------------------


def test_missing_ffmpeg_raises_typed_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """If ffmpeg is absent at runtime, raise MissingFfmpegError (not a crash)."""
    import daesingo.search.media as media_mod

    def _raise_missing() -> str:
        raise MissingFfmpegError("ffmpeg not found on PATH")

    monkeypatch.setattr(media_mod, "_ffmpeg_path", _raise_missing)
    monkeypatch.setattr(media_mod, "_ffprobe_path", _raise_missing)

    data = b"\x00" * 16
    mi = MediaInput(
        stream=io.BytesIO(data),
        content_type="video/mp4",
        declared_byte_size=len(data),
    )
    preparer = MediaPreparer(_DEFAULT_CFG)
    with (
        pytest.raises(MissingFfmpegError),
        preparer.prepare_coarse(mi, _real_deadline()),
    ):
        pass  # pragma: no cover


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


def test_config_rejects_negative_max_materialized_source_bytes() -> None:
    with pytest.raises(ValueError, match="max_materialized_source_bytes"):
        _ = GeminiSearchConfig(max_materialized_source_bytes=-1)


def test_config_rejects_negative_max_inline_media_bytes() -> None:
    with pytest.raises(ValueError, match="max_inline_media_bytes"):
        _ = GeminiSearchConfig(max_inline_media_bytes=-1)
