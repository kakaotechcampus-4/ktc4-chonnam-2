"""Canonical recording contract models.

The models validate the public JSON boundary without choosing storage,
probing, decoding, or timeline-building implementations.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping


class ContractValidationError(ValueError):
    """Raised when data cannot satisfy a canonical recording contract."""


class TimelineStatus(str, Enum):
    USABLE = "USABLE"
    USABLE_RELATIVE_ONLY = "USABLE_RELATIVE_ONLY"
    PARTIAL = "PARTIAL"
    UNUSABLE = "UNUSABLE"


class SpanResolutionStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class MissingReason(str, Enum):
    TIMELINE_GAP = "TIMELINE_GAP"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    STREAM_UNAVAILABLE = "STREAM_UNAVAILABLE"


class TimeSourceKind(str, Enum):
    FILENAME = "FILENAME"
    FILE_METADATA = "FILE_METADATA"
    VENDOR_METADATA = "VENDOR_METADATA"


class ObservationStatus(str, Enum):
    OK = "OK"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"
    NOT_APPLICABLE = "NOT_APPLICABLE"


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractValidationError(f"{field} must be an object")
    return value


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractValidationError(f"{field} must be a non-empty string")
    return value


def _require_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractValidationError(f"{field} must be a number")
    return float(value)


def _parse_enum(enum_type: type[Enum], value: Any, field: str) -> Any:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ContractValidationError(
            f"{field} must be one of: {allowed}"
        ) from exc


def _parse_offset_datetime(value: Any, field: str) -> str:
    text = _require_string(value, field)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ContractValidationError(f"{field} must be ISO 8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractValidationError(f"{field} must include a UTC offset")
    return text


def _json_dict(value: Any) -> dict[str, Any]:
    def convert(item: Any) -> Any:
        if isinstance(item, Enum):
            return item.value
        if isinstance(item, dict):
            return {key: convert(val) for key, val in item.items()}
        if isinstance(item, (list, tuple)):
            return [convert(val) for val in item]
        return item

    return convert(asdict(value))


@dataclass(frozen=True)
class Interval:
    start_sec: float
    end_sec: float

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], field: str) -> "Interval":
        obj = _require_mapping(data, field)
        interval = cls(
            start_sec=_require_number(obj.get("start_sec"), f"{field}.start_sec"),
            end_sec=_require_number(obj.get("end_sec"), f"{field}.end_sec"),
        )
        if interval.start_sec >= interval.end_sec:
            raise ContractValidationError(f"{field}.start_sec must be less than end_sec")
        return interval


@dataclass(frozen=True)
class TimelineRef:
    timeline_id: str
    revision: int

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TimelineRef":
        obj = _require_mapping(data, "timeline_ref")
        revision = obj.get("revision")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise ContractValidationError("timeline_ref.revision must be an integer >= 1")
        return cls(
            timeline_id=_require_string(obj.get("timeline_id"), "timeline_ref.timeline_id"),
            revision=revision,
        )


@dataclass(frozen=True)
class SourcePlacement:
    source_asset_ref: str
    timeline_start_sec: float
    timeline_end_sec: float
    media_stream_refs: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourcePlacement":
        obj = _require_mapping(data, "source_placement")
        start = _require_number(obj.get("timeline_start_sec"), "timeline_start_sec")
        end = _require_number(obj.get("timeline_end_sec"), "timeline_end_sec")
        if start >= end:
            raise ContractValidationError("source placement start must be less than end")
        refs = obj.get("media_stream_refs")
        if not isinstance(refs, list) or not refs:
            raise ContractValidationError("media_stream_refs must be a non-empty array")
        return cls(
            source_asset_ref=_require_string(obj.get("source_asset_ref"), "source_asset_ref"),
            timeline_start_sec=start,
            timeline_end_sec=end,
            media_stream_refs=tuple(
                _require_string(ref, "media_stream_ref") for ref in refs
            ),
        )


@dataclass(frozen=True)
class WorkingAnchor:
    value: str | None
    source_candidate_ref: str | None
    status: ObservationStatus

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WorkingAnchor":
        obj = _require_mapping(data, "working_anchor")
        status = _parse_enum(ObservationStatus, obj.get("status"), "working_anchor.status")
        value = obj.get("value")
        source_ref = obj.get("source_candidate_ref")
        if value is not None:
            value = _parse_offset_datetime(value, "working_anchor.value")
        if source_ref is not None:
            source_ref = _require_string(source_ref, "working_anchor.source_candidate_ref")
        if status is ObservationStatus.OK and (value is None or source_ref is None):
            raise ContractValidationError("OK working_anchor requires value and source_candidate_ref")
        return cls(value=value, source_candidate_ref=source_ref, status=status)


@dataclass(frozen=True)
class TimeBasis:
    mode: str
    working_anchor: WorkingAnchor

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TimeBasis":
        obj = _require_mapping(data, "time_basis")
        return cls(
            mode=_require_string(obj.get("mode"), "time_basis.mode"),
            working_anchor=WorkingAnchor.from_dict(obj.get("working_anchor")),
        )


@dataclass(frozen=True)
class RecordingTimeline:
    contract: str
    contract_version: str
    timeline_id: str
    revision: int
    time_basis: TimeBasis
    time_source_candidates: tuple[str, ...]
    source_placements: tuple[SourcePlacement, ...]
    gaps: tuple[Mapping[str, Any], ...]
    timeline_status: TimelineStatus
    produced_by: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RecordingTimeline":
        obj = _require_mapping(data, "RecordingTimeline")
        if obj.get("contract") != "RecordingTimeline":
            raise ContractValidationError("contract must be RecordingTimeline")
        revision = obj.get("revision")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise ContractValidationError("revision must be an integer >= 1")
        candidate_refs = obj.get("time_source_candidates")
        placements = obj.get("source_placements")
        gaps = obj.get("gaps")
        if not isinstance(candidate_refs, list):
            raise ContractValidationError("time_source_candidates must be an array")
        if not isinstance(placements, list):
            raise ContractValidationError("source_placements must be an array")
        if not isinstance(gaps, list):
            raise ContractValidationError("gaps must be an array")
        return cls(
            contract="RecordingTimeline",
            contract_version=_require_string(obj.get("contract_version"), "contract_version"),
            timeline_id=_require_string(obj.get("timeline_id"), "timeline_id"),
            revision=revision,
            time_basis=TimeBasis.from_dict(obj.get("time_basis")),
            time_source_candidates=tuple(
                _require_string(ref, "time_source_candidate_ref") for ref in candidate_refs
            ),
            source_placements=tuple(SourcePlacement.from_dict(item) for item in placements),
            gaps=tuple(_require_mapping(item, "gap") for item in gaps),
            timeline_status=_parse_enum(
                TimelineStatus, obj.get("timeline_status"), "timeline_status"
            ),
            produced_by=_require_string(obj.get("produced_by"), "produced_by"),
        )

    def to_dict(self) -> dict[str, Any]:
        result = _json_dict(self)
        result["time_source_candidates"] = list(self.time_source_candidates)
        result["source_placements"] = [
            {**_json_dict(item), "media_stream_refs": list(item.media_stream_refs)}
            for item in self.source_placements
        ]
        result["gaps"] = [dict(item) for item in self.gaps]
        return result


@dataclass(frozen=True)
class AssetSpan:
    sequence: int
    timeline_range: Interval
    source_asset_ref: str
    media_stream_ref: str
    source_range: Interval

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AssetSpan":
        obj = _require_mapping(data, "AssetSpan")
        sequence = obj.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise ContractValidationError("AssetSpan.sequence must be an integer >= 0")
        return cls(
            sequence=sequence,
            timeline_range=Interval.from_dict(obj.get("timeline_range"), "timeline_range"),
            source_asset_ref=_require_string(obj.get("source_asset_ref"), "source_asset_ref"),
            media_stream_ref=_require_string(obj.get("media_stream_ref"), "media_stream_ref"),
            source_range=Interval.from_dict(obj.get("source_range"), "source_range"),
        )


@dataclass(frozen=True)
class MissingRange:
    timeline_range: Interval
    reason: MissingReason
    source_ref: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MissingRange":
        obj = _require_mapping(data, "MissingRange")
        source_ref = obj.get("source_ref")
        if source_ref is not None:
            source_ref = _require_string(source_ref, "source_ref")
        return cls(
            timeline_range=Interval.from_dict(obj.get("timeline_range"), "timeline_range"),
            reason=_parse_enum(MissingReason, obj.get("reason"), "reason"),
            source_ref=source_ref,
        )


@dataclass(frozen=True)
class SpanResolution:
    contract: str
    contract_version: str
    timeline_ref: TimelineRef
    requested_range: Interval
    status: SpanResolutionStatus
    spans: tuple[AssetSpan, ...]
    missing_ranges: tuple[MissingRange, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SpanResolution":
        obj = _require_mapping(data, "SpanResolution")
        if obj.get("contract") != "SpanResolution":
            raise ContractValidationError("contract must be SpanResolution")
        raw_spans = obj.get("spans")
        raw_missing = obj.get("missing_ranges")
        if not isinstance(raw_spans, list) or not isinstance(raw_missing, list):
            raise ContractValidationError("spans and missing_ranges must be arrays")
        status = _parse_enum(SpanResolutionStatus, obj.get("status"), "status")
        spans = tuple(AssetSpan.from_dict(item) for item in raw_spans)
        missing = tuple(MissingRange.from_dict(item) for item in raw_missing)
        if status is SpanResolutionStatus.COMPLETE and (not spans or missing):
            raise ContractValidationError("COMPLETE requires spans and no missing_ranges")
        if status is SpanResolutionStatus.PARTIAL and (not spans or not missing):
            raise ContractValidationError("PARTIAL requires spans and missing_ranges")
        if status is SpanResolutionStatus.FAILED and spans:
            raise ContractValidationError("FAILED cannot contain usable spans")
        resolution = cls(
            contract="SpanResolution",
            contract_version=_require_string(obj.get("contract_version"), "contract_version"),
            timeline_ref=TimelineRef.from_dict(obj.get("timeline_ref")),
            requested_range=Interval.from_dict(obj.get("requested_range"), "requested_range"),
            status=status,
            spans=spans,
            missing_ranges=missing,
        )
        for interval in [
            *(span.timeline_range for span in spans),
            *(item.timeline_range for item in missing),
        ]:
            if (
                interval.start_sec < resolution.requested_range.start_sec
                or interval.end_sec > resolution.requested_range.end_sec
            ):
                raise ContractValidationError("span or missing range is outside requested_range")
        return resolution

    def to_dict(self) -> dict[str, Any]:
        return _json_dict(self)


@dataclass(frozen=True)
class TimeSourceCandidate:
    candidate_id: str
    source_kind: TimeSourceKind
    source_detail: str
    value: str
    applies_to: Mapping[str, Any]
    observation_status: ObservationStatus
    producer_checks: Mapping[str, Any] | None
    provenance: Mapping[str, Any]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TimeSourceCandidate":
        obj = _require_mapping(data, "TimeSourceCandidate")
        applies_to = _require_mapping(obj.get("applies_to"), "applies_to")
        _require_string(applies_to.get("source_asset_ref"), "applies_to.source_asset_ref")
        _require_number(applies_to.get("source_offset_sec"), "applies_to.source_offset_sec")
        provenance = _require_mapping(obj.get("provenance"), "provenance")
        _require_string(provenance.get("producer"), "provenance.producer")
        _require_string(provenance.get("observed_from"), "provenance.observed_from")
        checks = obj.get("producer_checks")
        if checks is not None:
            checks = _require_mapping(checks, "producer_checks")
        return cls(
            candidate_id=_require_string(obj.get("candidate_id"), "candidate_id"),
            source_kind=_parse_enum(TimeSourceKind, obj.get("source_kind"), "source_kind"),
            source_detail=_require_string(obj.get("source_detail"), "source_detail"),
            value=_parse_offset_datetime(obj.get("value"), "value"),
            applies_to=dict(applies_to),
            observation_status=_parse_enum(
                ObservationStatus, obj.get("observation_status"), "observation_status"
            ),
            producer_checks=dict(checks) if checks is not None else None,
            provenance=dict(provenance),
        )

    def to_dict(self) -> dict[str, Any]:
        return _json_dict(self)


@dataclass(frozen=True)
class Observation:
    contract_version: str
    value: Any
    status: ObservationStatus
    source: Mapping[str, Any]
    support_refs: tuple[Any, ...]
    produced_by: Mapping[str, Any]
    reason: Mapping[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Observation":
        obj = _require_mapping(data, "Observation")
        source = _require_mapping(obj.get("source"), "source")
        produced_by = _require_mapping(obj.get("produced_by"), "produced_by")
        _require_string(source.get("kind"), "source.kind")
        _require_string(produced_by.get("module"), "produced_by.module")
        support_refs = obj.get("support_refs")
        if not isinstance(support_refs, list):
            raise ContractValidationError("support_refs must be an array")
        reason = obj.get("reason")
        if reason is not None:
            reason = _require_mapping(reason, "reason")
            _require_string(reason.get("code"), "reason.code")
        status = _parse_enum(ObservationStatus, obj.get("status"), "status")
        if status in (ObservationStatus.UNKNOWN, ObservationStatus.ERROR) and reason is None:
            raise ContractValidationError(f"{status.value} Observation requires reason")
        return cls(
            contract_version=_require_string(obj.get("contract_version"), "contract_version"),
            value=obj.get("value"),
            status=status,
            source=dict(source),
            support_refs=tuple(support_refs),
            produced_by=dict(produced_by),
            reason=dict(reason) if reason is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        result = _json_dict(self)
        result["support_refs"] = list(self.support_refs)
        if self.reason is None:
            result.pop("reason")
        return result
