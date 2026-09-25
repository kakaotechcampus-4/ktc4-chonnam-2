"""원본 파일명/container의 시간 관찰. 시각의 신뢰도나 Evidence 판단을 만들지 않는다."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
import re
import subprocess
from typing import Literal
from uuid import uuid4

from pydantic import AwareDatetime, Field

from .errors import RecordingCapabilityError
from .models import ContractModel, RecordingTimeline
from .probe import LocalSource, _snapshot


class TimeSourceAppliesTo(ContractModel):
    source_asset_ref: str = Field(min_length=1)
    source_offset_sec: float = Field(ge=0)


class TimeSourceProducerChecks(ContractModel):
    parse_valid: Literal[True]


class TimeSourceProvenance(ContractModel):
    producer: Literal["recording"]
    observed_from: str


class TimeSourceCandidate(ContractModel):
    candidate_id: str = Field(min_length=1)
    source_kind: Literal["FILENAME", "FILE_METADATA", "VENDOR_METADATA"]
    source_detail: str = Field(min_length=1)
    value: AwareDatetime
    applies_to: TimeSourceAppliesTo
    observation_status: Literal["OK"]
    producer_checks: TimeSourceProducerChecks
    provenance: TimeSourceProvenance


class TimeSourceCheck(ContractModel):
    source_asset_ref: str = Field(min_length=1)
    source_kind: Literal["FILENAME", "FILE_METADATA", "VENDOR_METADATA"]
    source_detail: str = Field(min_length=1)
    status: Literal["FOUND", "NOT_FOUND", "UNSUPPORTED", "PARSE_ERROR"]


@dataclass(frozen=True)
class ObservedTimeSources:
    candidates: tuple[TimeSourceCandidate, ...]
    checks: tuple[TimeSourceCheck, ...]


@dataclass(frozen=True)
class AnchorApplication:
    timeline: RecordingTimeline
    overlay_matches: bool | None
    trusted: bool
    applied: bool


class LocalTimeSourceObserver:
    """offset은 실행 설정이다. 파일명에서 지역/세기를 추측하지 않는다."""

    def __init__(self, *, filename_offset: str | None = None, mdr_century: int | None = None,
                 ffprobe: str = "ffprobe", timeout_sec: float = 30.0):
        self._zone = None
        if filename_offset is not None:
            match = re.fullmatch(r"([+-])(\d{2}):(\d{2})", filename_offset)
            if not match or int(match[2]) > 23 or int(match[3]) > 59:
                raise ValueError("filename_offset은 명시적인 ±HH:MM이어야 합니다")
            seconds = (int(match[2]) * 60 + int(match[3])) * 60
            self._zone = timezone(timedelta(seconds=seconds * (-1 if match[1] == "-" else 1)))
        if mdr_century is not None and (type(mdr_century) is not int or not 0 <= mdr_century <= 9900 or mdr_century % 100):
            raise ValueError("mdr_century는 명시적인 100년 단위 기준이어야 합니다")
        if not math.isfinite(timeout_sec) or timeout_sec <= 0:
            raise ValueError("유한한 양수 timeout이 필요합니다")
        self._century = mdr_century
        self._ffprobe, self._timeout = ffprobe, timeout_sec

    @staticmethod
    def verify_source(local: LocalSource):
        try:
            actual = _snapshot(local.path)
        except OSError:
            raise RecordingCapabilityError("UNAVAILABLE", "등록 원본을 조사할 수 없습니다") from None
        except ValueError:
            raise RecordingCapabilityError("UNAVAILABLE", "등록 원본이 일반 파일이 아닙니다") from None
        if (actual[2], actual[3], actual[4]) != (local.byte_size, local.mtime_ns, local.sha256):
            raise RecordingCapabilityError("UNAVAILABLE", "등록 이후 원본이 변경되었습니다")

    def _metadata(self, local):
        try:
            run = subprocess.run([self._ffprobe, "-v", "error", "-protocol_whitelist", "file",
                "-show_entries", "format_tags=creation_time", "-of", "json", str(local.path)],
                stdin=subprocess.DEVNULL, capture_output=True, check=False, timeout=self._timeout)
            if run.returncode:
                raise RecordingCapabilityError("TEMPORARY_FAILURE", "container 시각 metadata를 조사하지 못했습니다")
            return json.loads(run.stdout)
        except (OSError, subprocess.TimeoutExpired):
            raise RecordingCapabilityError("TEMPORARY_FAILURE", "container 시각 metadata 도구에 접근할 수 없습니다") from None
        except (ValueError, UnicodeDecodeError):
            raise RecordingCapabilityError("TEMPORARY_FAILURE", "container metadata 응답이 유효하지 않습니다") from None

    def observe(self, source_ref: str, local: LocalSource) -> ObservedTimeSources:
        self.verify_source(local)
        name = local.path.name
        candidates, checks = [], []

        def record(kind, detail, status, value=None):
            checks.append(TimeSourceCheck(source_asset_ref=source_ref, source_kind=kind,
                                           source_detail=detail, status=status))
            if value is not None:
                candidates.append(TimeSourceCandidate(
                    candidate_id=f"tsc_{uuid4().hex}", source_kind=kind, source_detail=detail, value=value,
                    applies_to=TimeSourceAppliesTo(source_asset_ref=source_ref, source_offset_sec=0.0),
                    observation_status="OK", producer_checks=TimeSourceProducerChecks(parse_valid=True),
                    provenance=TimeSourceProvenance(producer="recording", observed_from=name),
                ))

        evt = re.fullmatch(r"(\d{8})_(\d{6})_EVT_([0-9]+)\.avi", name, re.IGNORECASE)
        mdr = re.fullmatch(r"MDR_(\d{6})_(\d{6})\.AVI", name, re.IGNORECASE)
        detail = "filename.evt.YYYYMMDD_HHMMSS_EVT_n/v1" if evt else "filename.mdr.YYMMDD_HHMMSS/v1" if mdr else "filename.supported-rules/v1"
        if not (evt or mdr) or self._zone is None or (mdr and self._century is None):
            record("FILENAME", detail, "UNSUPPORTED")
        else:
            match = evt or mdr
            date, time = match[1], match[2]
            year = int(date[:4]) if evt else self._century + int(date[:2])
            try:
                value = datetime(year, int(date[-4:-2]), int(date[-2:]), int(time[:2]),
                                 int(time[2:4]), int(time[4:]), tzinfo=self._zone)
            except ValueError:
                record("FILENAME", detail, "PARSE_ERROR")
            else:
                record("FILENAME", detail, "FOUND", value)

        payload = self._metadata(local)
        try:
            if not isinstance(payload, dict) or not isinstance(payload.get("format", {}), dict):
                raise ValueError("유효하지 않은 format metadata")
            tags = payload.get("format", {}).get("tags", {})
            if not isinstance(tags, dict):
                raise ValueError("유효하지 않은 container tags")
            if "creation_time" not in tags:
                record("FILE_METADATA", "container.creation_time.iso8601/v1", "NOT_FOUND")
            else:
                raw = tags["creation_time"]
                if not isinstance(raw, str) or not re.fullmatch(
                        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", raw):
                    raise ValueError("명시적 offset 없는 metadata")
                if not raw.endswith("Z") and (int(raw[-5:-3]) > 23 or int(raw[-2:]) > 59):
                    raise ValueError("유효하지 않은 metadata offset")
                value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                record("FILE_METADATA", "container.creation_time.iso8601/v1", "FOUND", value)
        except (ValueError, TypeError, AttributeError):
            record("FILE_METADATA", "container.creation_time.iso8601/v1", "PARSE_ERROR")
        record("VENDOR_METADATA", "vendor.parser-unavailable/v1", "UNSUPPORTED")
        self.verify_source(local)
        return ObservedTimeSources(tuple(candidates), tuple(checks))
