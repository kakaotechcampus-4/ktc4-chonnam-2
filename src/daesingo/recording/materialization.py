"""실행별 profile configuration과 로컬 VIDEO materialization. Canonical profile 목록이 아니다."""

from dataclasses import dataclass
from fractions import Fraction
import json
import math
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from .errors import RecordingCapabilityError
from .models import AssetSpan, TimeRange
from .probe import LocalSource, _snapshot


@dataclass(frozen=True)
class AnalysisProfile:
    height: int
    preset: str
    crf: int

    def __post_init__(self):
        if type(self.height) is not int or self.height <= 0 or self.height % 2:
            raise ValueError("height는 양의 짝수여야 합니다")
        if self.preset not in {"ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow"}:
            raise ValueError("지원하지 않는 encoder preset입니다")
        if type(self.crf) is not int or not 0 <= self.crf <= 51:
            raise ValueError("crf는 0부터 51 사이 정수여야 합니다")


@dataclass(frozen=True)
class MaterializedVideo:
    content: bytes
    duration_sec: float
    timeline_range: TimeRange


class LocalAnalysisMaterializer:
    def __init__(self, profiles: dict[str, AnalysisProfile], *, ffmpeg="ffmpeg", ffprobe="ffprobe",
                 timeout_sec=120.0, temp_root: Path | None = None):
        if not math.isfinite(timeout_sec) or timeout_sec <= 0:
            raise ValueError("유한한 양수 timeout이 필요합니다")
        if any(not isinstance(k, str) or not k or not isinstance(v, AnalysisProfile) for k, v in profiles.items()):
            raise ValueError("opaque ref와 명시적인 profile configuration이 필요합니다")
        self._profiles = dict(profiles)
        self._ffmpeg, self._ffprobe = ffmpeg, ffprobe
        self._timeout = timeout_sec
        self._temp_root = temp_root

    def has_profile(self, ref):
        return ref in self._profiles

    def _run(self, args):
        result = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True,
                                timeout=self._timeout, check=False)
        if result.returncode:
            raise RecordingCapabilityError("TEMPORARY_FAILURE", "media 도구가 작업을 완료하지 못했습니다")
        return result.stdout

    def _probe(self, path, index=None):
        args = [self._ffprobe, "-v", "error", "-protocol_whitelist", "file"]
        if index is not None:
            args += ["-select_streams", str(index)]
        args += ["-show_frames", "-show_entries",
                 "format=format_name,duration:stream=codec_type,codec_name,width,height,pix_fmt,time_base,duration:frame=best_effort_timestamp,duration",
                 "-of", "json", str(path)]
        return json.loads(self._run(args))

    @staticmethod
    def _frames(payload):
        streams = payload["streams"]
        if len(streams) != 1 or streams[0]["codec_type"] != "video":
            raise ValueError("단일 VIDEO 검증 실패")
        base = Fraction(streams[0]["time_base"])
        if base <= 0:
            raise ValueError("유효하지 않은 time base")
        frames = [(int(f["best_effort_timestamp"]) * base, int(f["duration"]) * base)
                  for f in payload["frames"]]
        if not frames or any(length <= 0 for _, length in frames):
            raise ValueError("frame coverage 미확인")
        if any(a + length != b for (a, length), (b, _) in zip(frames, frames[1:])):
            raise ValueError("불연속 frame coverage는 지원하지 않습니다")
        return base, [(at - frames[0][0], length) for at, length in frames]

    def materialize(self, source: LocalSource, index: int, span: AssetSpan, profile_ref: str) -> MaterializedVideo:
        if profile_ref not in self._profiles:
            raise ValueError("등록되지 않은 profile_ref입니다")
        profile = self._profiles[profile_ref]
        try:
            before = _snapshot(source.path)
            if (before[2], before[3], before[4]) != (source.byte_size, source.mtime_ns, source.sha256):
                raise RecordingCapabilityError("UNAVAILABLE", "등록 이후 원본이 변경되었습니다")
            raw = self._probe(source.path, index)
            base, frames = self._frames(raw)
            input_stream = raw["streams"][0]
            width = max(2, 2 * math.floor(input_stream["width"] * profile.height / input_stream["height"] / 2 + 0.5))
            start, end = Fraction(str(span.source_range.start_sec)), Fraction(str(span.source_range.end_sec))
            selected = [(i, at, length) for i, (at, length) in enumerate(frames) if start <= at < end]
            if not selected:
                raise RecordingCapabilityError("UNSUPPORTED_MEDIA", "요청 구간에 선택 가능한 frame이 없습니다")
            first, last = selected[0], selected[-1]
            # 출력은 frame 경계의 실제 coverage를 보존한다. 요청 시각으로 위장하지 않는다.
            actual_start, actual_end = first[1], last[1] + last[2]
            with TemporaryDirectory(prefix="recording-analysis-", dir=self._temp_root) as work:
                output = Path(work) / "prepared.mp4"
                self._run([self._ffmpeg, "-nostdin", "-v", "error", "-xerror", "-n",
                    "-protocol_whitelist", "file", "-noautorotate", "-i", str(source.path),
                    "-map", f"0:{index}", "-an", "-sn", "-dn", "-map_metadata", "-1", "-map_chapters", "-1",
                    "-vf", f"trim=start_frame={first[0]}:end_frame={last[0]+1},setpts=PTS-STARTPTS,scale={width}:{profile.height}",
                    "-fps_mode", "passthrough", "-enc_time_base", str(base),
                    "-video_track_timescale", str(base.denominator),
                    "-c:v", "libx264", "-preset", profile.preset, "-crf", str(profile.crf),
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)])
                probed = self._probe(output)
                output_base, output_frames = self._frames(probed)
                stream = probed["streams"][0]
                if (stream["codec_name"] != "h264" or stream["height"] != profile.height
                        or stream["width"] != width or stream["pix_fmt"] != "yuv420p"
                        or "mp4" not in probed["format"]["format_name"].split(",")
                        or len(output_frames) != len(selected)):
                    raise ValueError("출력 media 형식 불일치")
                tolerance = 2 * output_base
                for (_, at, length), (out_at, out_length) in zip(selected, output_frames):
                    if abs(at - actual_start - out_at) > tolerance or abs(length - out_length) > tolerance:
                        raise ValueError("출력 frame timestamp 불일치")
                duration = float(probed["format"]["duration"])
                # MP4 format duration은 millisecond 단위로 반올림될 수 있다.
                if (not math.isfinite(duration) or duration <= 0
                        or abs(duration - float(actual_end - actual_start)) > 0.001 + float(tolerance)):
                    raise ValueError("출력 duration 불일치")
                content = output.read_bytes()
                if not content:
                    raise ValueError("빈 출력 media")
                boxes, position = [], 0
                while position + 8 <= len(content):
                    size = int.from_bytes(content[position:position+4], "big")
                    boxes.append(content[position+4:position+8])
                    if size < 8:
                        raise ValueError("지원하지 않는 MP4 box")
                    position += size
                if position != len(content) or boxes.index(b"moov") > boxes.index(b"mdat"):
                    raise ValueError("faststart 검증 실패")
                if _snapshot(source.path) != before:
                    raise RecordingCapabilityError("UNAVAILABLE", "변환 중 원본 변경을 감지했습니다")
                shift = Fraction(str(span.timeline_range.start_sec)) - start
                return MaterializedVideo(content, duration, TimeRange(
                    start_sec=float(shift + actual_start), end_sec=float(shift + actual_end)))
        except subprocess.TimeoutExpired:
            raise RecordingCapabilityError("TEMPORARY_FAILURE", "materialization 제한 시간을 초과했습니다") from None
        except OSError:
            raise RecordingCapabilityError("TEMPORARY_FAILURE", "media 파일 또는 도구에 접근할 수 없습니다") from None
        except (ValueError, KeyError, TypeError, ZeroDivisionError, OverflowError):
            raise RecordingCapabilityError("UNSUPPORTED_MEDIA", "실제 media의 형식·frame coverage·시각을 검증할 수 없습니다") from None
