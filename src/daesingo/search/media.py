"""Bounded media preparation: materialize → probe → coarse proxy + fine clip.

Never sends the original source to a model. Temp dir is always cleaned up
on success, failure, timeout, and cancellation.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, TypeGuard, final

from .config import GeminiSearchConfig
from .execution import DeadlineExceededError, RunDeadline

_CHUNK = 64 * 1024  # 64 KiB read chunks


def _ffprobe_object_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """object_pairs_hook that yields a properly-typed dict for basedpyright."""
    result: dict[str, object] = {}
    for key, val in pairs:
        result[key] = val
    return result


def _json_parse(text: str) -> object:
    """Call json.loads and return object (not Any) for basedpyright callers."""
    result: object = json.loads(text, object_pairs_hook=_ffprobe_object_hook)
    return result


def _parse_ffprobe_json(data: bytes) -> dict[str, object]:
    """Parse ffprobe JSON bytes into a typed dict. Raises FfprobeError on issues."""
    text = data.decode(errors="replace")
    try:
        obj = _json_parse(text)
    except json.JSONDecodeError as exc:
        raise FfprobeError(f"ffprobe output is not valid JSON: {exc}") from exc
    if not _is_str_obj_dict(obj):
        raise FfprobeError("ffprobe output is not a JSON object")
    return obj


def _is_str_obj_dict(val: object) -> TypeGuard[dict[str, object]]:
    return isinstance(val, dict)


def _is_list_of_dicts(val: object) -> TypeGuard[list[dict[str, object]]]:
    if not isinstance(val, list):
        return False
    for elem in val:
        item: object = elem
        if not isinstance(item, dict):
            return False
    return True


def _get_streams(root: dict[str, object]) -> list[dict[str, object]]:
    """Extract the streams array from a parsed ffprobe dict."""
    streams_val = root.get("streams")
    if _is_list_of_dicts(streams_val):
        return streams_val
    return []


def _get_fmt(root: dict[str, object]) -> dict[str, object]:
    """Extract the format dict from a parsed ffprobe dict."""
    fmt_val = root.get("format")
    return fmt_val if _is_str_obj_dict(fmt_val) else {}


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
    """Run a subprocess with deadline guard. Terminates and reaps on timeout.

    Uses Popen + communicate so the process handle is always available for
    terminate+wait on TimeoutExpired (pattern from test_runtime_deadline.py).
    """
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
        proc.terminate()
        _rc = proc.wait()  # reap — no zombie
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
    root = _parse_ffprobe_json(result.stdout or b"")
    streams = _get_streams(root)
    fmt = _get_fmt(root)

    # Find first video stream
    video: dict[str, object] | None = next(
        (s for s in streams if s.get("codec_type") == "video"),
        None,
    )
    if video is None:
        raise FfprobeError("no video stream found in ffprobe output")

    try:
        dur_raw = fmt.get("duration") or video.get("duration") or "0"
        duration = float(str(dur_raw))
        width = int(str(video["width"]))
        height = int(str(video["height"]))
        codec_raw = video.get("codec_name")
        codec = str(codec_raw) if codec_raw is not None else "unknown"
        fmt_name_raw = fmt.get("format_name")
        fmt_name = str(fmt_name_raw) if fmt_name_raw is not None else "unknown"
        container = fmt_name.split(",")[0]
    except (KeyError, ValueError, TypeError) as exc:
        raise FfprobeError(f"ffprobe output missing required fields: {exc}") from exc

    return MediaProbe(
        container=container,
        codec=codec,
        duration_sec=duration,
        width=width,
        height=height,
    )


def _scale_filter(max_height: int) -> str:
    # Downscale-only: cap height but never upscale. Width keeps aspect ratio (-2 = even).
    return f"scale=-2:'min({max_height},ih)'"


# ---------------------------------------------------------------------------
# MediaPreparer
# ---------------------------------------------------------------------------


@final
class MediaPreparer:
    """Materializes, probes, and produces bounded Coarse + Fine MP4s."""

    def __init__(self, config: GeminiSearchConfig) -> None:
        self._cfg = config

    def prepare(
        self,
        media_input: MediaInput,
        fine_start_sec: float,
        fine_end_sec: float,
        deadline: RunDeadline,
    ) -> tuple[PreparedMedia, PreparedMedia]:
        """Return (coarse, fine). Temp dir is always cleaned up on any exit."""
        cfg = self._cfg
        max_src = cfg.max_materialized_source_bytes
        max_inline = cfg.max_inline_media_bytes

        # Reject declared size before streaming
        if media_input.declared_byte_size > max_src:
            raise SourceTooLargeError(
                f"declared size {media_input.declared_byte_size} > cap {max_src}"
            )

        tmpdir = Path(tempfile.mkdtemp(prefix="daesingo_media_"))
        try:
            # 1. Materialize source
            src_path = tmpdir / "source.mp4"
            materialized = _materialize(media_input, src_path, max_src, deadline)

            # 2. Coarse proxy
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
            coarse = PreparedMedia(
                path=coarse_path,
                content_type="video/mp4",
                byte_size=coarse_path.stat().st_size,
                duration_sec=coarse_probe.duration_sec,
                origin_start_sec=0.0,
                origin_end_sec=materialized.probe.duration_sec,
            )

            # 3. Fine clip (clamped interval)
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
            fine = PreparedMedia(
                path=fine_path,
                content_type="video/mp4",
                byte_size=fine_path.stat().st_size,
                duration_sec=fine_probe.duration_sec,
                origin_start_sec=start,
                origin_end_sec=end,
            )

            return coarse, fine

        except Exception:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise


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
