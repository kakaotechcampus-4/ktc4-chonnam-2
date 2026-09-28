"""단일 로컬 원본 Timeline의 보수적인 metadata 좌표 매핑."""

from decimal import Decimal
import math

from .errors import RecordingCapabilityError
from .facts import inspect_local_source
from .models import (
    AssetSpan, ContractRef, FailureDetail, MissingRange, RecordingTimeline,
    SpanResolution, TimeRange, TimelineRef,
)
from .repository import InMemoryRecordingRepository


def resolve_local_span(
    repository: InMemoryRecordingRepository, timeline: RecordingTimeline, request: TimeRange,
    *, selected_stream_ref: str,
) -> SpanResolution:
    # 공개 service에서 소속·VIDEO·유일성을 검증한 명시적 ref만 전달한다.
    if (not math.isfinite(request.start_sec) or not math.isfinite(request.end_sec)
            or request.start_sec < 0 or request.end_sec <= request.start_sec):
        raise ValueError("유효한 요청 범위가 필요합니다")
    ref = TimelineRef(timeline_id=timeline.timeline_id, revision=timeline.revision)

    def result(spans, missing, code=None, kind="UNAVAILABLE"):
        status = "FAILED" if not spans else "PARTIAL" if missing else "COMPLETE"
        return SpanResolution(
            contract="SpanResolution", contract_version="span-resolution/v1.2",
            timeline_ref=ref, requested_range=request, status=status, spans=spans,
            missing_ranges=missing,
            failure=FailureDetail(kind=kind, code=code or "NO_USABLE_SPAN") if not spans else None,
        )

    if len(timeline.source_placements) != 1:
        return result([], [], "TIMELINE_NOT_SUPPORTED", "UNSUPPORTED")
    placement = timeline.source_placements[0]
    source = repository.get_source_asset(placement.source_asset_ref)
    local = repository.get_local_source(placement.source_asset_ref)
    refs = placement.media_stream_refs
    streams = [repository.get_media_stream(selected_stream_ref)] if selected_stream_ref else []
    if (source is None or local is None or not refs or len(set(refs)) != len(refs)
            or any(r not in source.media_stream_refs for r in refs)
            or any(s is not None and s.source_asset_ref != source.source_asset_ref for s in streams)
            or not math.isfinite(placement.timeline_start_sec)
            or not math.isfinite(placement.timeline_end_sec)
            or source.duration_sec is None or not math.isfinite(source.duration_sec)
            or source.duration_sec <= 0):
        return result([], [], "TIMELINE_METADATA_INVALID", "INVALID_STATE")
    d = lambda value: Decimal(str(value))
    begin, end = d(placement.timeline_start_sec), d(placement.timeline_end_sec)
    if begin < 0 or end <= begin or end - begin > d(source.duration_sec) or timeline.timeline_status == "UNUSABLE":
        return result([], [], "TIMELINE_METADATA_INVALID", "INVALID_STATE")
    gaps = []
    for gap in timeline.gaps:
        if (not math.isfinite(gap.start_sec) or not math.isfinite(gap.end_sec)
                or gap.start_sec < placement.timeline_start_sec
                or gap.end_sec > placement.timeline_end_sec):
            return result([], [], "TIMELINE_METADATA_INVALID", "INVALID_STATE")
        gaps.append((d(gap.start_sec), d(gap.end_sec)))
    if selected_stream_ref is not None and selected_stream_ref not in refs:
        raise ValueError("선택 stream은 해당 placement에 속해야 합니다")
    start, stop = d(request.start_sec), d(request.end_sec)
    bounds = {start, stop}
    bounds.update(x for pair in [(begin, end), *gaps] for x in pair if start < x < stop)
    for stream in streams:
        if stream is not None and stream.duration_sec is not None and math.isfinite(stream.duration_sec):
            boundary = begin + d(stream.duration_sec)
            if start < boundary < stop:
                bounds.add(boundary)
    points = sorted(bounds)
    parts = list(zip(points, points[1:]))
    usable_parts = [(a, b) for a, b in parts if begin <= a < end
                    and not any(g <= a < h for g, h in gaps)]
    source_available = False
    if usable_parts:
        selected = streams[0]
        if selected is None:
            return result([], [], "TIMELINE_METADATA_INVALID", "INVALID_STATE")
        if (selected.availability != "UNAVAILABLE"
                and (selected.duration_sec is None or not math.isfinite(selected.duration_sec))):
            return result([], [], "STREAM_COVERAGE_UNKNOWN", "UNRESOLVED")
        try:
            source_available = (inspect_local_source(source, local).availability == "AVAILABLE"
                                and source.availability != "UNAVAILABLE")
        except RecordingCapabilityError:
            return result([], [], "SOURCE_INSPECTION_FAILED", "TEMPORARY")
    spans, missing = [], []

    def absent(a, b, reason, kind=None, identity=None):
        missing.append(MissingRange(
            timeline_range=TimeRange(start_sec=float(a), end_sec=float(b)), reason=reason,
            source_ref=ContractRef(kind=kind, ref=identity) if kind else None,
        ))

    for a, b in parts:
        if a < begin or a >= end:
            absent(a, b, "OUT_OF_TIMELINE_RANGE")
        elif any(g <= a < h for g, h in gaps):
            absent(a, b, "TIMELINE_GAP")
        elif not source_available:
            absent(a, b, "SOURCE_UNAVAILABLE", "source_asset", source.source_asset_ref)
        else:
            for stream in streams:
                stream_ref = selected_stream_ref
                if (stream.availability == "UNAVAILABLE" or b - begin > d(stream.duration_sec)):
                    absent(a, b, "STREAM_UNAVAILABLE", "media_stream", stream_ref)
                else:
                    spans.append(AssetSpan(
                        sequence=len(spans), source_asset_ref=source.source_asset_ref,
                        media_stream_ref=stream_ref,
                        timeline_range=TimeRange(start_sec=float(a), end_sec=float(b)),
                        source_range=TimeRange(start_sec=float(a - begin), end_sec=float(b - begin)),
                    ))
    return result(spans, missing)
