"""Bounded media preparation: materialize → probe → coarse proxy or fine clip.

Never sends the original source to a model. Temp dir is always cleaned up
on success, failure, timeout, and cancellation.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, ClassVar, final

from pydantic import BaseModel, ConfigDict, TypeAdapter

from .config import GeminiSearchConfig
from .execution import DeadlineExceededError, RunDeadline

_CHUNK = 64 * 1024  # 64 KiB read chunks


# ---------------------------------------------------------------------------
# ffprobe JSON model (replaces all manual dict-traversal helpers)
# ---------------------------------------------------------------------------


class _FfprobeStream(BaseModel, frozen=True):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    codec_type: str = "unknown"
    codec_name: str = "unknown"
    width: int = 0
    height: int = 0
    r_frame_rate: str = "0/1"
    duration: str | None = None


class _FfprobeFormat(BaseModel, frozen=True):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    format_name: str = "unknown"
    duration: str | None = None


class _FfprobeOutput(BaseModel, frozen=True):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    streams: list[_FfprobeStream] = []
    format: _FfprobeFormat = _FfprobeFormat()


_FFPROBE_ADAPTER: TypeAdapter[_FfprobeOutput] = TypeAdapter(_FfprobeOutput)


# ---------------------------------------------------------------------------
# Typed errors
# ---------------------------------------------------------------------------


class MissingFfmpegError(RuntimeError):
    """ffmpeg or ffprobe binary not found on PATH."""


class SourceTooLargeError(ValueError):
    """Declared or actual byte size exceeds max_materialized_source_bytes."""


class ByteSizeMismatchError(ValueError):
    """Actual bytes written differs from the declared byte size."""


class MediaTooLargeError(ValueError):
    """Prepared media output exceeds max_inline_media_bytes."""


class FfprobeError(RuntimeError):
    """ffprobe returned a non-zero exit code or unreadable output."""


class FfmpegError(RuntimeError):
    """ffmpeg returned a non-zero exit code."""


# ---------------------------------------------------------------------------
# Frozen data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MediaInput:
    stream: BinaryIO
    content_type: str
    declared_byte_size: int


@dataclass(frozen=True, slots=True)
class MediaProbe:
    container: str
    codec: str
    duration_sec: float
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class MaterializedSource:
    path: Path
    sha256: str
    actual_byte_size: int
    probe: MediaProbe


@dataclass(frozen=True, slots=True)
class PreparedMedia:
    path: Path
    content_type: str
    byte_size: int
    duration_sec: float
    origin_start_sec: float
    origin_end_sec: float


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ffprobe_path() -> str:
    p = shutil.which("ffprobe")
    if p is None:
        raise MissingFfmpegError("ffprobe not found on PATH")
    return p


def _ffmpeg_path() -> str:
    p = shutil.which("ffmpeg")
    if p is None:
        raise MissingFfmpegError("ffmpeg not found on PATH")
    return p


def _run_subprocess(
    args: list[str],
    deadline: RunDeadline,
    *,
    capture_stdout: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    """Run a subprocess with deadline guard. Kills and drains on timeout."""
    deadline.check()
    timeout = deadline.remaining_sec()
    stdout = subprocess.PIPE if capture_stdout else subprocess.DEVNULL
    proc = subprocess.Popen(
        args,
        stdout=stdout,
        stderr=subprocess.PIPE,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()  # drain pipes, reap — no deadlock
        raise DeadlineExceededError(
            f"subprocess timed out after {timeout:.1f}s: {args[0]}"
        )
    return subprocess.CompletedProcess(args, proc.returncode, out, err)


def _probe(path: Path, deadline: RunDeadline) -> MediaProbe:
    """Run ffprobe and return a MediaProbe. Raises FfprobeError on bad output."""
    result = _run_subprocess(
        [
            _ffprobe_path(),
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(path),
        ],
        deadline,
        capture_stdout=True,
    )
    if result.returncode != 0:
        stderr = (result.stderr or b"").decode(errors="replace")
        raise FfprobeError(f"ffprobe exited {result.returncode}: {stderr}")

    try:
        parsed = _FFPROBE_ADAPTER.validate_json(result.stdout or b"")
    except Exception as exc:
        raise FfprobeError(f"ffprobe output parse failed: {exc}") from exc

    video = next(
        (s for s in parsed.streams if s.codec_type == "video"),
        None,
    )
    if video is None:
        raise FfprobeError("no video stream found in ffprobe output")

    try:
        dur_raw = parsed.format.duration or video.duration or "0"
        duration = float(dur_raw)
        container = parsed.format.format_name.split(",")[0]
    except (ValueError, TypeError) as exc:
        raise FfprobeError(f"ffprobe output missing required fields: {exc}") from exc

    return MediaProbe(
        container=container,
        codec=video.codec_name,
        duration_sec=duration,
        width=video.width,
        height=video.height,
    )


def _scale_filter(max_height: int) -> str:
    # Downscale-only: cap height but never upscale. Width keeps aspect ratio (-2 = even).
    return f"scale=-2:'min({max_height},ih)'"


# ---------------------------------------------------------------------------
# MediaPreparer
# ---------------------------------------------------------------------------


@final
class MediaPreparer:
    """Materializes, probes, and produces bounded Coarse or Fine MP4s."""

    def __init__(self, config: GeminiSearchConfig) -> None:
        self._cfg = config

    @contextmanager
    def prepare_coarse(
        self,
        media_input: MediaInput,
        deadline: RunDeadline,
    ) -> Generator[PreparedMedia]:
        """Materialize + probe + 1fps/360p/no-audio proxy; yield it; rmtree in finally.

        Temp dir is cleaned up on every exit — success, failure, timeout,
        and cancellation (KeyboardInterrupt / asyncio.CancelledError).

        ``origin_start_sec`` / ``origin_end_sec`` span the whole probed source.
        """
        cfg = self._cfg
        max_src = cfg.max_materialized_source_bytes
        max_inline = cfg.max_inline_media_bytes

        if media_input.declared_byte_size > max_src:
            raise SourceTooLargeError(
                f"declared size {media_input.declared_byte_size} > cap {max_src}"
            )

        tmpdir = Path(tempfile.mkdtemp(prefix="daesingo_media_"))
        try:
            src_path = tmpdir / "source.mp4"
            materialized = _materialize(media_input, src_path, max_src, deadline)

            coarse_path = tmpdir / "coarse.mp4"
            deadline.check()
            _run_ffmpeg_encode(
                src_path,
                coarse_path,
                fps=cfg.coarse_fps,
                max_height=360,
                deadline=deadline,
            )
            _verify_output(coarse_path, max_inline)
            coarse_probe = _probe(coarse_path, deadline)
            yield PreparedMedia(
                path=coarse_path,
                content_type="video/mp4",
                byte_size=coarse_path.stat().st_size,
                duration_sec=coarse_probe.duration_sec,
                origin_start_sec=0.0,
                origin_end_sec=materialized.probe.duration_sec,
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @contextmanager
    def prepare_fine(
        self,
        media_input: MediaInput,
        fine_start_sec: float,
        fine_end_sec: float,
        deadline: RunDeadline,
    ) -> Generator[PreparedMedia]:
        """Materialize + probe + clamp [start,end] to probed duration + 2fps/720p/no-audio clip.

        Temp dir is cleaned up on every exit — success, failure, timeout,
        and cancellation (KeyboardInterrupt / asyncio.CancelledError).

        ``origin_start_sec`` / ``origin_end_sec`` are the clamped interval.
        """
        cfg = self._cfg
        max_src = cfg.max_materialized_source_bytes
        max_inline = cfg.max_inline_media_bytes

        if media_input.declared_byte_size > max_src:
            raise SourceTooLargeError(
                f"declared size {media_input.declared_byte_size} > cap {max_src}"
            )

        tmpdir = Path(tempfile.mkdtemp(prefix="daesingo_media_"))
        try:
            src_path = tmpdir / "source.mp4"
            materialized = _materialize(media_input, src_path, max_src, deadline)

            src_dur = materialized.probe.duration_sec
            start = max(0.0, min(fine_start_sec, src_dur))
            end = max(start, min(fine_end_sec, src_dur))

            fine_path = tmpdir / "fine.mp4"
            deadline.check()
            _run_ffmpeg_encode(
                src_path,
                fine_path,
                fps=cfg.fine_fps,
                max_height=720,
                deadline=deadline,
                start_sec=start,
                end_sec=end,
            )
            _verify_output(fine_path, max_inline)
            fine_probe = _probe(fine_path, deadline)
            yield PreparedMedia(
                path=fine_path,
                content_type="video/mp4",
                byte_size=fine_path.stat().st_size,
                duration_sec=fine_probe.duration_sec,
                origin_start_sec=start,
                origin_end_sec=end,
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Internal helpers called from prepare()
# ---------------------------------------------------------------------------


def _materialize(
    media_input: MediaInput,
    dest: Path,
    max_bytes: int,
    deadline: RunDeadline,
) -> MaterializedSource:
    """Stream-copy to dest, hash on the fly, enforce hard cap."""
    deadline.check()
    hasher = hashlib.sha256()
    written = 0

    with dest.open("wb") as out:
        while True:
            chunk = media_input.stream.read(_CHUNK)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                raise SourceTooLargeError(
                    f"stream exceeded hard cap of {max_bytes} bytes"
                )
            _ = out.write(chunk)
            hasher.update(chunk)

    if written != media_input.declared_byte_size:
        raise ByteSizeMismatchError(
            f"declared {media_input.declared_byte_size} bytes but got {written}"
        )

    probe = _probe(dest, deadline)
    return MaterializedSource(
        path=dest,
        sha256=hasher.hexdigest(),
        actual_byte_size=written,
        probe=probe,
    )


def _run_ffmpeg_encode(
    src: Path,
    dest: Path,
    *,
    fps: float,
    max_height: int,
    deadline: RunDeadline,
    start_sec: float | None = None,
    end_sec: float | None = None,
) -> None:
    """Encode src → dest as H.264 MP4, downscale-only, no audio."""
    args = [_ffmpeg_path(), "-y"]
    if start_sec is not None:
        args += ["-ss", str(start_sec)]
    args += ["-i", str(src)]
    if end_sec is not None and start_sec is not None:
        args += ["-t", str(end_sec - start_sec)]
    args += [
        "-vf",
        f"fps={fps},{_scale_filter(max_height)}",
        "-c:v",
        "libx264",
        "-an",  # no audio
        "-movflags",
        "+faststart",
        str(dest),
    ]
    result = _run_subprocess(args, deadline)
    if result.returncode != 0:
        stderr = (result.stderr or b"").decode(errors="replace")
        raise FfmpegError(f"ffmpeg exited {result.returncode}: {stderr[-500:]}")


def _verify_output(path: Path, max_inline: int) -> None:
    """Raise MediaTooLargeError if output exceeds the inline byte cap."""
    size = path.stat().st_size
    if size > max_inline:
        raise MediaTooLargeError(
            f"{path.name} is {size} bytes, exceeds cap of {max_inline}"
        )
