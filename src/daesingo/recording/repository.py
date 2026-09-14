"""1차 Mock E2E에서 사용하는 in-memory recording 저장 경계."""

from __future__ import annotations

from decimal import Decimal

from .models import (
    AssetFacts,
    FrameRef,
    MediaStream,
    RecordingTimeline,
    SourceAsset,
    SpanResolution,
    TimeRange,
    TimelineRef,
)


def _offset_key(value: float) -> Decimal:
    return Decimal(str(value))


class InMemoryRecordingRepository:
    def __init__(self) -> None:
        self._source_assets: dict[str, SourceAsset] = {}
        self._media_streams: dict[str, MediaStream] = {}
        self._frames: dict[str, FrameRef] = {}
        self._frame_by_position: dict[tuple[str, Decimal], str] = {}
        self._frame_content: dict[str, bytes] = {}
        self._asset_facts: dict[tuple[str, str], AssetFacts] = {}
        self._timelines: dict[tuple[str, int], RecordingTimeline] = {}
        self._span_resolutions: dict[tuple[str, int, Decimal, Decimal], SpanResolution] = {}

    def add_source_asset(self, asset: SourceAsset) -> None:
        self._source_assets[asset.source_asset_ref] = asset

    def add_media_stream(self, stream: MediaStream) -> None:
        self._media_streams[stream.media_stream_ref] = stream

    def get_media_stream(self, stream_ref: str) -> MediaStream | None:
        return self._media_streams.get(stream_ref)

    def add_frame(self, frame: FrameRef, *, content: bytes | None = None) -> None:
        self._frames[frame.frame_ref] = frame
        self._frame_by_position[(frame.media_stream_ref, _offset_key(frame.source_offset_sec))] = (
            frame.frame_ref
        )
        if content is not None:
            self._frame_content[frame.frame_ref] = content

    def find_frame_at(self, stream_ref: str, source_offset_sec: float) -> FrameRef | None:
        frame_ref = self._frame_by_position.get((stream_ref, _offset_key(source_offset_sec)))
        return self._frames.get(frame_ref) if frame_ref is not None else None

    def get_frame(self, frame_ref: str) -> FrameRef | None:
        return self._frames.get(frame_ref)

    def get_frame_content(self, frame_ref: str) -> bytes | None:
        return self._frame_content.get(frame_ref)

    def add_asset_facts(self, facts: AssetFacts) -> None:
        key = (facts.asset_ref.kind, facts.asset_ref.ref)
        self._asset_facts[key] = facts

    def get_asset_facts(self, kind: str, ref: str) -> AssetFacts | None:
        return self._asset_facts.get((kind, ref))

    def add_timeline(self, timeline: RecordingTimeline) -> None:
        key = (timeline.timeline_id, timeline.revision)
        current = self._timelines.get(key)
        if current is not None and current != timeline:
            raise ValueError("같은 timeline revision을 다른 payload로 덮어쓸 수 없습니다")
        self._timelines[key] = timeline

    def get_timeline(self, timeline_ref: TimelineRef) -> RecordingTimeline | None:
        return self._timelines.get((timeline_ref.timeline_id, timeline_ref.revision))

    def add_span_resolution(self, resolution: SpanResolution) -> None:
        key = self._resolution_key(resolution.timeline_ref, resolution.requested_range)
        current = self._span_resolutions.get(key)
        if current is not None and current != resolution:
            raise ValueError("같은 span 요청을 다른 결과로 덮어쓸 수 없습니다")
        self._span_resolutions[key] = resolution

    def get_span_resolution(
        self,
        timeline_ref: TimelineRef,
        requested_range: TimeRange,
    ) -> SpanResolution | None:
        return self._span_resolutions.get(self._resolution_key(timeline_ref, requested_range))

    @staticmethod
    def _resolution_key(
        timeline_ref: TimelineRef,
        requested_range: TimeRange,
    ) -> tuple[str, int, Decimal, Decimal]:
        return (
            timeline_ref.timeline_id,
            timeline_ref.revision,
            _offset_key(requested_range.start_sec),
            _offset_key(requested_range.end_sec),
        )
