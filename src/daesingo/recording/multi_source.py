"""명시적 단일 카메라 배치의 실행 입력. Canonical stream_selector가 아니다."""
from decimal import Decimal
import math
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

from .models import (RecordingTimeline, SourcePlacement, TimeBasis, WorkingAnchor,
                     TimeRange, TimelineRef, SpanResolution, MissingRange, FailureDetail)
from .spans import resolve_local_span


class PlacementInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    source_asset_ref: str = Field(min_length=1)
    media_stream_ref: str = Field(min_length=1)
    timeline_start_sec: FiniteFloat = Field(ge=0)
    timeline_end_sec: FiniteFloat = Field(gt=0)

    @model_validator(mode="after")
    def ordered_range(self):
        if self.timeline_end_sec <= self.timeline_start_sec:
            raise ValueError("placement는 양의 구간이어야 합니다")
        return self


def _ordered(rows):
    if not rows:
        raise ValueError("명시적 placement가 필요합니다")
    ordered = sorted(rows, key=lambda p: p.timeline_start_sec)
    if len({p.source_asset_ref for p in ordered}) != len(ordered):
        raise ValueError("Baseline에서 같은 source를 중복 배치할 수 없습니다")
    if any(a.timeline_end_sec > b.timeline_start_sec for a, b in zip(ordered, ordered[1:])):
        raise ValueError("겹치는 placement는 명시적인 경계 합의 후 전달해야 합니다")
    return ordered


def _selected_stream(repository, source_ref, stream_ref):
    source = repository.get_source_asset(source_ref)
    stream = repository.get_media_stream(stream_ref)
    if (source is None or repository.get_local_source(source_ref) is None
            or stream is None or stream.media_type != "VIDEO"
            or stream.source_asset_ref != source_ref
            or source.media_stream_refs.count(stream_ref) != 1):
        raise ValueError("등록된 로컬 source에 소속된 명시적 VIDEO ref가 필요합니다")
    return source


def build_placed_timeline(repository, placements, base_timeline_ref=None):
    if not isinstance(placements, (list, tuple)):
        raise ValueError("placement 목록이 필요합니다")
    rows = _ordered([PlacementInput.model_validate(p) for p in placements])
    previous = None
    if base_timeline_ref is not None:
        base = TimelineRef.model_validate(base_timeline_ref)
        previous = repository.get_timeline(base)
        latest = repository.get_latest_timeline(base.timeline_id)
        if previous is None or latest is None or latest.revision != base.revision:
            raise ValueError("placement 변경은 현재 최신 timeline revision에서만 가능합니다")
        if previous.time_basis.working_anchor.value is not None:
            raise ValueError("absolute anchor가 있는 Timeline의 재배치는 이번 Baseline 범위 밖입니다")
    result = []
    for p in rows:
        source = _selected_stream(repository, p.source_asset_ref, p.media_stream_ref)
        if (source.availability != "AVAILABLE" or source.duration_sec is None
                or not math.isfinite(source.duration_sec) or source.duration_sec <= 0
                or Decimal(str(p.timeline_end_sec)) - Decimal(str(p.timeline_start_sec)) > Decimal(str(source.duration_sec))):
            raise ValueError("placement는 알려진 가용 원본 길이 안에 있어야 합니다")
        result.append(SourcePlacement(source_asset_ref=p.source_asset_ref,
            media_stream_refs=[p.media_stream_ref], timeline_start_sec=p.timeline_start_sec,
            timeline_end_sec=p.timeline_end_sec))
    gaps = [TimeRange(start_sec=a.timeline_end_sec, end_sec=b.timeline_start_sec)
            for a, b in zip(rows, rows[1:]) if a.timeline_end_sec < b.timeline_start_sec]
    return RecordingTimeline(contract="RecordingTimeline", contract_version="recording-timeline/v1",
        timeline_id=previous.timeline_id if previous else f"tl_{uuid4().hex}",
        revision=previous.revision + 1 if previous else 1,
        time_basis=TimeBasis(mode="ABSOLUTE_AND_RELATIVE",
                            working_anchor=WorkingAnchor(value=None, source_candidate_ref=None, status="UNKNOWN")),
        time_source_candidates=list(previous.time_source_candidates) if previous else [],
        source_placements=result, gaps=gaps, timeline_status="USABLE_RELATIVE_ONLY", produced_by="recording")


def resolve_placed_span(repository, timeline, request, stream_refs):
    # 명시적인 ref 집합이 한 카메라의 체인을 구성한다. role이나 ref 이름을 해석하지 않는다.
    if (not isinstance(stream_refs, (list, tuple)) or not stream_refs
            or any(not isinstance(ref, str) or not ref for ref in stream_refs)
            or len(set(stream_refs)) != len(stream_refs)):
        raise ValueError("중복 없는 명시적 VIDEO ref 목록이 필요합니다")
    selected = set(stream_refs)
    rows = _ordered(timeline.source_placements)
    mapping = []
    for p in rows:
        refs = [r for r in p.media_stream_refs if r in selected]
        if len(refs) != 1:
            raise ValueError("각 placement에 VIDEO ref 하나를 명시해야 합니다")
        _selected_stream(repository, p.source_asset_ref, refs[0])
        mapping.append(refs[0])
    if len(mapping) != len(selected) or set(mapping) != selected:
        raise ValueError("선택 stream과 Timeline revision 소속이 일치하지 않습니다")
    expected_gaps = [(a.timeline_end_sec, b.timeline_start_sec) for a, b in zip(rows, rows[1:])
                     if a.timeline_end_sec < b.timeline_start_sec]
    if [(g.start_sec, g.end_sec) for g in timeline.gaps] != expected_gaps:
        raise ValueError("placement와 gap이 일치하지 않습니다")
    ref = TimelineRef(timeline_id=timeline.timeline_id, revision=timeline.revision)
    spans, missing = [], []
    start, end = request.start_sec, request.end_sec

    def absent(a, b, reason):
        a, b = max(a, start), min(b, end)
        if a < b:
            missing.append(MissingRange(timeline_range=TimeRange(start_sec=a, end_sec=b),
                                        reason=reason, source_ref=None))

    absent(start, rows[0].timeline_start_sec, "OUT_OF_TIMELINE_RANGE")
    for i, (p, selected_ref) in enumerate(zip(rows, mapping)):
        if i:
            absent(rows[i-1].timeline_end_sec, p.timeline_start_sec, "TIMELINE_GAP")
        a, b = max(start, p.timeline_start_sec), min(end, p.timeline_end_sec)
        if a >= b:
            continue
        part = resolve_local_span(repository,
            timeline.model_copy(update={"source_placements": [p], "gaps": []}),
            TimeRange(start_sec=a, end_sec=b), selected_stream_ref=selected_ref)
        if part.status == "FAILED" and not part.missing_ranges:
            # 위치를 확정할 수 없는 실패를 가상의 MissingRange로 바꾸지 않는다.
            return SpanResolution(contract="SpanResolution", contract_version="span-resolution/v1.2",
                timeline_ref=ref, requested_range=request, status="FAILED", spans=[], missing_ranges=[], failure=part.failure)
        for span in part.spans:
            spans.append(span.model_copy(update={"sequence": len(spans)}))
        missing.extend(part.missing_ranges)
    absent(rows[-1].timeline_end_sec, end, "OUT_OF_TIMELINE_RANGE")
    status = "FAILED" if not spans else "PARTIAL" if missing else "COMPLETE"
    return SpanResolution(contract="SpanResolution", contract_version="span-resolution/v1.2",
        timeline_ref=ref, requested_range=request, status=status, spans=spans, missing_ranges=missing,
        failure=FailureDetail(kind="UNAVAILABLE", code="NO_USABLE_SPAN") if not spans else None)
