"""원본 stream의 실제 frame을 읽는 내부 adapter. 원본에는 쓰지 않는다."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math
import re
import subprocess
from typing import Protocol

from .errors import RecordingCapabilityError
from .probe import LocalSource, _snapshot


@dataclass(frozen=True)
class DecodedFrame:
    source_offset_sec: float
    content: bytes


class FrameExtractor(Protocol):
    def extract(self, source: LocalSource, stream_index: int, offset: float) -> DecodedFrame: ...


class FfmpegFrameExtractor:
    """첫 decoded PTS를 0으로 정규화하고 요청 이상 첫 frame을 PNG로 반환한다."""

    def __init__(self, executable: str = "ffmpeg", *, timeout_sec: float = 60.0) -> None:
        if not math.isfinite(timeout_sec) or timeout_sec <= 0:
            raise ValueError("timeout_sec은 유한한 양수여야 합니다")
        self.executable = executable
        self.timeout_sec = timeout_sec

    def extract(self, source: LocalSource, stream_index: int, offset: float) -> DecodedFrame:
        if not math.isfinite(offset) or offset < 0 or type(stream_index) is not int or stream_index < 0:
            raise ValueError("유효한 stream index와 유한한 offset이 필요합니다")
        try:
            before = _snapshot(source.path)
            if (before[2], before[3], before[4]) != (source.byte_size, source.mtime_ns, source.sha256):
                raise RecordingCapabilityError("STREAM_UNAVAILABLE", "등록 이후 원본이 변경되었습니다")
            result = subprocess.run(
                [self.executable, "-nostdin", "-v", "info", "-xerror",
                 "-protocol_whitelist", "file", "-noautorotate", "-i", str(source.path),
                 "-map", f"0:{stream_index}", "-an", "-sn", "-dn",
                 "-vf", f"setpts=PTS-STARTPTS,select=gte(t\\,{offset!r}),showinfo",
                 "-frames:v", "1", "-fps_mode", "passthrough", "-c:v", "png",
                 "-f", "image2pipe", "pipe:1"],
                stdin=subprocess.DEVNULL, capture_output=True, timeout=self.timeout_sec,
                check=False,
            )
            after = _snapshot(source.path)
            if after != before:
                raise RecordingCapabilityError("STREAM_UNAVAILABLE", "frame 추출 중 원본 변경을 감지했습니다")
        except subprocess.TimeoutExpired:
            raise RecordingCapabilityError("TEMPORARY_FAILURE", "frame 추출 제한 시간을 초과했습니다") from None
        except FileNotFoundError:
            # subprocess의 실행 파일 부재와 원본 부재를 구분한다. 경로는 공개하지 않는다.
            code = "TEMPORARY_FAILURE" if source.path.is_file() else "STREAM_UNAVAILABLE"
            raise RecordingCapabilityError(code, "원본 또는 ffmpeg에 접근할 수 없습니다") from None
        except OSError:
            raise RecordingCapabilityError("TEMPORARY_FAILURE", "원본 또는 ffmpeg에 접근할 수 없습니다") from None
        if result.returncode != 0:
            raise RecordingCapabilityError("STREAM_UNAVAILABLE", "원본 frame을 decode하지 못했습니다")
        if not result.stdout:
            raise RecordingCapabilityError("FRAME_NOT_FOUND", "요청 위치 이후에 decoded frame이 없습니다")
        # showinfo가 기록한 정수 PTS와 time base로 계산한다. 표시용 pts_time은 반올림된다.
        log = result.stderr.decode("utf-8", errors="replace")
        time_base = re.search(r"\[Parsed_showinfo_[^\]]+\] config in time_base: (\d+/\d+)", log)
        first_pts = re.search(r"\[Parsed_showinfo_[^\]]+\]\s+n:\s*0\s+pts:\s*(-?\d+)\s", log)
        if (time_base is None or first_pts is None
                or not result.stdout.startswith(b"\x89PNG\r\n\x1a\n")
                or not result.stdout.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82")):
            raise RecordingCapabilityError("TEMPORARY_FAILURE", "decoded frame의 시각 또는 PNG를 검증할 수 없습니다")
        try:
            actual = float(int(first_pts[1]) * Fraction(time_base[1]))
        except (ValueError, ZeroDivisionError, OverflowError):
            raise RecordingCapabilityError("TEMPORARY_FAILURE", "decoded frame의 시각이 유효하지 않습니다") from None
        if not math.isfinite(actual) or actual < offset:
            raise RecordingCapabilityError("TEMPORARY_FAILURE", "decoded frame의 시각이 요청과 일치하지 않습니다")
        return DecodedFrame(actual, result.stdout)
