"""Trusted local AnalysisSource materialization; paths stay behind Recording."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import subprocess
import tempfile
from typing import Literal
from uuid import uuid4

from .errors import RecordingCapabilityError
from .probe import FfprobeMediaProbe, LocalSource


@dataclass(frozen=True)
class LocalAnalysisProfile:
    """Local adapter setting, not a canonical profile_ref value/schema."""

    height: int | None = None
    include_audio: bool = False
    crf: int = 23
    preset: Literal["ultrafast", "superfast", "veryfast", "faster", "fast", "medium"] = "veryfast"

    def __post_init__(self) -> None:
        if self.height is not None and (self.height < 2 or self.height % 2 != 0):
            raise ValueError("height must be an even positive pixel count")
        if not 0 <= self.crf <= 51:
            raise ValueError("crf must be between 0 and 51")


@dataclass(frozen=True)
class MaterializedMedia:
    path: Path
    byte_size: int
    duration_sec: float


class LocalAnalysisMaterializer:
    def __init__(
        self,
        *,
        ffmpeg_executable: str = "ffmpeg",
        ffprobe_executable: str = "ffprobe",
        timeout_sec: float = 600.0,
        temp_root: Path | None = None,
    ) -> None:
        if not math.isfinite(timeout_sec) or timeout_sec <= 0:
            raise ValueError("timeout_sec must be positive and finite")
        self.ffmpeg_executable = ffmpeg_executable
        self._probe = FfprobeMediaProbe(executable=ffprobe_executable, timeout_sec=60.0)
        self.timeout_sec = timeout_sec
        self._temp = tempfile.TemporaryDirectory(prefix="daesingo-analysis-", dir=temp_root)
        self._closed = False

    @property
    def temp_path(self) -> Path:
        return Path(self._temp.name)

    def close(self) -> None:
        if not self._closed:
            self._temp.cleanup()
            self._closed = True

    def _verify_input(self, local: LocalSource) -> None:
        try:
            current = local.path.stat()
            if current.st_size != local.byte_size or current.st_mtime_ns != local.mtime_ns:
                raise RecordingCapabilityError("SOURCE_UNAVAILABLE", "등록 후 원본이 변경되었습니다")
            with local.path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != local.sha256:
                raise RecordingCapabilityError("SOURCE_UNAVAILABLE", "등록 후 원본이 변경되었습니다")
        except OSError:
            raise RecordingCapabilityError("SOURCE_UNAVAILABLE", "원본을 읽을 수 없습니다") from None

    def materialize(
        self,
        local: LocalSource,
        *,
        video_stream_index: int,
        audio_stream_index: int | None,
        start_sec: float,
        end_sec: float,
        profile: LocalAnalysisProfile,
    ) -> MaterializedMedia:
        if self._closed:
            raise RecordingCapabilityError("UNAVAILABLE", "materializer가 종료되었습니다")
        if not 0 <= start_sec < end_sec:
            raise ValueError("유효한 구간이 필요합니다")
        if local.duration_sec is not None and end_sec > local.duration_sec + 1e-6:
            raise ValueError("요청 구간이 원본 길이를 벗어납니다")
        self._verify_input(local)
        output = self.temp_path / f"analysis-{uuid4().hex}.mp4"
        duration = end_sec - start_sec
        command = [
            self.ffmpeg_executable,
            "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{start_sec:.6f}", "-i", str(local.path),
            "-t", f"{duration:.6f}", "-map", f"0:{video_stream_index}",
        ]
        if profile.include_audio:
            if audio_stream_index is None:
                raise RecordingCapabilityError("STREAM_UNAVAILABLE", "요청한 Audio stream이 없습니다")
            command.extend(["-map", f"0:{audio_stream_index}"])
        else:
            command.append("-an")
        if profile.height is not None:
            command.extend(["-vf", f"scale=-2:{profile.height}"])
        command.extend([
            "-c:v", "libx264", "-preset", profile.preset,
            "-crf", str(profile.crf), "-pix_fmt", "yuv420p",
        ])
        if profile.include_audio:
            command.extend(["-c:a", "aac", "-b:a", "64k"])
        command.extend(["-movflags", "+faststart", str(output)])
        succeeded = False
        try:
            result = subprocess.run(
                command, stdin=subprocess.DEVNULL, capture_output=True,
                timeout=self.timeout_sec, check=False,
            )
            if result.returncode != 0:
                raise RecordingCapabilityError("TEMPORARY_FAILURE", "분석용 MP4 생성에 실패했습니다")
            measured = self._probe.probe(output)
            if measured.duration_sec is None or abs(measured.duration_sec - duration) > 0.15:
                raise RecordingCapabilityError("TEMPORARY_FAILURE", "생성된 MP4 길이가 요청과 다릅니다")
            if profile.include_audio and not any(
                stream.media_type == "AUDIO" for stream in measured.streams
            ):
                raise RecordingCapabilityError("TEMPORARY_FAILURE", "생성된 MP4에 Audio가 없습니다")
            self._verify_input(local)
            succeeded = True
            return MaterializedMedia(output, measured.byte_size, measured.duration_sec)
        except subprocess.TimeoutExpired:
            raise RecordingCapabilityError("TEMPORARY_FAILURE", "분석용 MP4 생성 시간이 초과됐습니다") from None
        except OSError:
            raise RecordingCapabilityError("TEMPORARY_FAILURE", "미디어 처리 도구에 접근할 수 없습니다") from None
        finally:
            if not succeeded:
                output.unlink(missing_ok=True)
