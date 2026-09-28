"""로컬 원본 전용 probe adapter. 경로와 fingerprint는 내부 값이다."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import stat
import subprocess
from typing import Literal, Protocol

from .errors import RecordingCapabilityError


@dataclass(frozen=True)
class ProbedStream:
    index: int
    media_type: Literal["VIDEO", "AUDIO"]
    duration_sec: float | None


@dataclass(frozen=True)
class LocalSource:
    path: Path = field(repr=False)
    byte_size: int
    mtime_ns: int
    sha256: str
    duration_sec: float | None
    streams: tuple[ProbedStream, ...]


class MediaProbe(Protocol):
    def probe(self, path: Path) -> LocalSource: ...


def _snapshot(path: Path) -> tuple[int, int, int, int, str]:
    """원본을 읽기만 하며, 읽는 동안의 교체·변경도 검사한다."""
    before = path.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("일반 로컬 영상 파일이 필요합니다")
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    after = path.stat()
    identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
    if identity(before) != identity(after):
        raise RecordingCapabilityError("TEMPORARY_FAILURE", "등록 중 원본 변경을 감지했습니다")
    return (*identity(after), digest)


def _duration(value: object) -> float | None:
    if value is None or value == "N/A":
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("유효하지 않은 duration metadata입니다")
    try:
        duration = float(value)
    except (ValueError, OverflowError):
        raise ValueError("유효하지 않은 duration metadata입니다") from None
    if not math.isfinite(duration) or duration < 0:
        raise ValueError("유효하지 않은 duration metadata입니다")
    return duration


def _parse_metadata(payload: object) -> tuple[float | None, tuple[ProbedStream, ...]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("streams"), list):
        raise ValueError("ffprobe stream metadata가 없습니다")
    format_info = payload.get("format", {})
    if not isinstance(format_info, dict):
        raise ValueError("ffprobe format metadata가 유효하지 않습니다")
    streams = []
    indices: set[int] = set()
    for item in payload["streams"]:
        if not isinstance(item, dict):
            raise ValueError("ffprobe stream metadata가 유효하지 않습니다")
        media_type = item.get("codec_type")
        if not isinstance(media_type, str):
            raise ValueError("ffprobe stream 종류가 유효하지 않습니다")
        if media_type not in {"video", "audio"}:
            continue  # subtitle/data는 Canonical MediaStream 대상이 아니다.
        disposition = item.get("disposition", {})
        if not isinstance(disposition, dict):
            raise ValueError("ffprobe stream disposition이 유효하지 않습니다")
        if media_type == "video" and disposition.get("attached_pic") == 1:
            continue  # 앨범 표지를 동영상 stream으로 등록하지 않는다.
        index = item.get("index")
        if type(index) is not int or index < 0 or index in indices:
            raise ValueError("ffprobe stream index가 유효하지 않습니다")
        indices.add(index)
        streams.append(ProbedStream(index, "VIDEO" if media_type == "video" else "AUDIO",
                                    _duration(item.get("duration"))))
    if not any(stream.media_type == "VIDEO" for stream in streams):
        raise ValueError("등록 가능한 video stream이 없습니다")
    return _duration(format_info.get("duration")), tuple(streams)


class FfprobeMediaProbe:
    """metadata만 조사한다. stream 전체 decode 가능성을 보증하지 않는다."""

    def __init__(self, executable: str = "ffprobe", *, timeout_sec: float = 30.0) -> None:
        if not math.isfinite(timeout_sec) or timeout_sec <= 0:
            raise ValueError("timeout_sec은 유한한 양수여야 합니다")
        self.executable = executable
        self.timeout_sec = timeout_sec

    def probe(self, path: Path) -> LocalSource:
        try:
            resolved = path.resolve(strict=True)
            before = _snapshot(resolved)
            result = subprocess.run(
                [self.executable, "-v", "error", "-protocol_whitelist", "file",
                 "-show_entries", "format=duration:stream=index,codec_type,duration:stream_disposition=attached_pic",
                 "-of", "json", str(resolved)],
                stdin=subprocess.DEVNULL, capture_output=True, timeout=self.timeout_sec,
                check=False,
            )
            if result.returncode != 0:
                raise RecordingCapabilityError("TEMPORARY_FAILURE", "ffprobe가 원본을 조사하지 못했습니다")
            try:
                payload = json.loads(result.stdout)
            except (ValueError, UnicodeDecodeError):
                raise ValueError("ffprobe JSON 응답이 유효하지 않습니다") from None
            duration, streams = _parse_metadata(payload)
            after = _snapshot(resolved)
            if before != after:
                raise RecordingCapabilityError("TEMPORARY_FAILURE", "등록 중 원본 변경을 감지했습니다")
            return LocalSource(resolved, after[2], after[3], after[4], duration, streams)
        except subprocess.TimeoutExpired:
            raise RecordingCapabilityError("TEMPORARY_FAILURE", "ffprobe 실행 제한 시간을 초과했습니다") from None
        except OSError:
            # 예외 filename, subprocess argv/stderr에 비공개 경로가 있을 수 있다.
            raise RecordingCapabilityError("TEMPORARY_FAILURE", "원본 또는 ffprobe 실행 파일에 접근할 수 없습니다") from None
