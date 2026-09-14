"""Consumer가 저장 구조를 몰라도 호출할 수 있는 recording 공개 entry."""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

from .errors import RecordingCapabilityError
from .fixtures import RecordingFixture
from .models import (
    AssetFacts,
    ContractRef,
    FrameLocator,
    FrameRef,
    RecordingTimeline,
    SpanResolution,
    StreamPositionLocator,
    TimelinePositionLocator,
    TimeRange,
    TimelineRef,
)
from .repository import InMemoryRecordingRepository


_FRAME_LOCATOR_ADAPTER = TypeAdapter(FrameLocator)
_ASSET_FACT_KINDS = {"source_asset", "analysis_source", "incident_clip", "derived_asset"}


class RecordingService:
    def __init__(self, repository: InMemoryRecordingRepository | None = None) -> None:
        self._repository = repository or InMemoryRecordingRepository()

    @classmethod
    def from_fixture(cls, fixture: RecordingFixture) -> RecordingService:
        service = cls()
        for asset in fixture.source_assets:
            service._repository.add_source_asset(asset)
        for stream in fixture.media_streams:
            service._repository.add_media_stream(stream)
        for frame in fixture.frame_refs:
            stub_content = f"fixture-frame:{frame.frame_ref}".encode()
            service._repository.add_frame(frame, content=stub_content)
        for facts in fixture.asset_facts:
            service._repository.add_asset_facts(facts)
        for timeline in fixture.recording_timelines:
            service._repository.add_timeline(timeline)
        for resolution in fixture.span_resolutions:
            service._repository.add_span_resolution(resolution)
        return service

    def resolve_frame(self, locator: FrameLocator | dict[str, Any]) -> FrameRef:
        parsed = _FRAME_LOCATOR_ADAPTER.validate_python(locator)
        if isinstance(parsed, TimelinePositionLocator):
            timeline = self._repository.get_timeline(parsed.timeline_ref)
            if timeline is None:
                raise RecordingCapabilityError("UNKNOWN_REF", "등록되지 않은 timeline입니다")
            frames = self._repository.find_frames_at_timeline_position(timeline, parsed.at_sec)
            if not frames:
                raise RecordingCapabilityError("FRAME_NOT_FOUND", "해당 timeline 위치의 frame이 없습니다")
            if len(frames) > 1:
                raise RecordingCapabilityError(
                    "TEMPORARY_FAILURE",
                    "여러 frame 후보를 구분할 stream_selector가 필요합니다",
                )
            return frames[0]

        stream = self._repository.get_media_stream(parsed.media_stream_ref)
        if stream is None:
            raise RecordingCapabilityError("UNKNOWN_REF", "등록되지 않은 MediaStream입니다")
        if stream.availability != "AVAILABLE":
            raise RecordingCapabilityError("STREAM_UNAVAILABLE", "MediaStream을 읽을 수 없습니다")
        if stream.duration_sec is not None and parsed.source_offset_sec > stream.duration_sec:
            raise RecordingCapabilityError("OUT_OF_RANGE", "요청 위치가 MediaStream 범위를 벗어납니다")

        frame = self._repository.find_frame_at(
            parsed.media_stream_ref,
            parsed.source_offset_sec,
        )
        if frame is None:
            raise RecordingCapabilityError("FRAME_NOT_FOUND", "해당 위치의 FrameRef가 없습니다")
        return frame

    def read_frame(self, frame_ref: str) -> bytes:
        frame = self._repository.get_frame(frame_ref)
        if frame is None:
            raise RecordingCapabilityError("UNKNOWN_REF", "등록되지 않은 FrameRef입니다")
        content = self._repository.get_frame_content(frame_ref)
        if content is None:
            raise RecordingCapabilityError("FRAME_NOT_FOUND", "frame image를 읽을 수 없습니다")
        return content

    def lookup_asset_facts(self, asset_ref: ContractRef | dict[str, Any]) -> AssetFacts:
        parsed = ContractRef.model_validate(asset_ref)
        if parsed.kind not in _ASSET_FACT_KINDS:
            raise RecordingCapabilityError(
                "INVALID_REF_KIND",
                "이 ref kind는 AssetFacts 조회 대상이 아닙니다",
            )
        facts = self._repository.get_asset_facts(parsed.kind, parsed.ref)
        if facts is None:
            raise RecordingCapabilityError("UNKNOWN_REF", "등록되지 않은 자산 ref입니다")
        return facts

    def get_timeline(
        self,
        timeline_id: str,
        revision: int,
    ) -> RecordingTimeline:
        timeline_ref = TimelineRef(timeline_id=timeline_id, revision=revision)
        timeline = self._repository.get_timeline(timeline_ref)
        if timeline is None:
            raise ValueError("존재하지 않는 timeline reference입니다")
        return timeline

    def get_latest_timeline(self, timeline_id: str) -> RecordingTimeline:
        timeline = self._repository.get_latest_timeline(timeline_id)
        if timeline is None:
            raise ValueError("존재하지 않는 timeline_id입니다")
        return timeline

    def resolve_span(
        self,
        timeline_ref: TimelineRef | dict[str, Any],
        requested_range: TimeRange | dict[str, Any],
    ) -> SpanResolution:
        parsed_ref = TimelineRef.model_validate(timeline_ref)
        parsed_range = TimeRange.model_validate(requested_range)
        if self._repository.get_timeline(parsed_ref) is None:
            raise ValueError("존재하지 않는 timeline reference입니다")

        resolution = self._repository.get_span_resolution(parsed_ref, parsed_range)
        if resolution is None:
            raise RecordingCapabilityError(
                "TEMPORARY_FAILURE",
                "이 요청 범위의 SpanResolution이 fixture adapter에 등록되지 않았습니다",
            )
        return resolution
