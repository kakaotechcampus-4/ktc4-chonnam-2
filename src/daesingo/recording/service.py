"""Consumer가 저장 구조를 몰라도 호출할 수 있는 recording 공개 entry."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import RawIOBase
from typing import Any, BinaryIO
from uuid import uuid4

from pydantic import TypeAdapter

from .errors import RecordingCapabilityError
from .fixtures import RecordingFixture
from .models import (
    AnalysisSource,
    AssetSpan,
    AssetFacts,
    ContractRef,
    FrameLocator,
    FrameRef,
    RecordingTimeline,
    RemoteCopy,
    RemoteCopyInfo,
    SpanResolution,
    StreamPositionLocator,
    TimelinePositionLocator,
    TimeRange,
    TimelineRef,
)
from .repository import InMemoryRecordingRepository


_FRAME_LOCATOR_ADAPTER = TypeAdapter(FrameLocator)
_ASSET_FACT_KINDS = {"source_asset", "analysis_source", "incident_clip", "derived_asset"}


@dataclass(frozen=True)
class OpenedAnalysisSource:
    stream: BinaryIO
    content_type: str
    byte_size: int


class _SyntheticBinaryStream(RawIOBase):
    """Fixture의 선언 크기를 메모리 할당 없이 재현하는 seekable stream."""

    def __init__(self, size: int) -> None:
        super().__init__()
        self._size = size
        self._position = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._position

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            position = offset
        elif whence == 1:
            position = self._position + offset
        elif whence == 2:
            position = self._size + offset
        else:
            raise ValueError("지원하지 않는 whence입니다")
        if position < 0:
            raise ValueError("stream 시작 전으로 이동할 수 없습니다")
        self._position = min(position, self._size)
        return self._position

    def read(self, size: int = -1) -> bytes:
        remaining = self._size - self._position
        count = remaining if size is None or size < 0 else min(size, remaining)
        self._position += count
        return bytes(count)


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
        for source in fixture.analysis_sources:
            stream_factory = None
            if source.availability == "AVAILABLE" and source.byte_size is not None:
                stream_factory = lambda size=source.byte_size: _SyntheticBinaryStream(size)
            service._repository.add_analysis_source(source, stream_factory=stream_factory)
        for remote_copy in fixture.remote_copies:
            service._repository.add_remote_copy(remote_copy)
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

    def prepare_analysis_source(
        self,
        span: AssetSpan | dict[str, Any],
        profile_ref: str,
    ) -> AnalysisSource:
        parsed_span = AssetSpan.model_validate(span)
        if not profile_ref:
            raise ValueError("profile_ref는 비어 있을 수 없습니다")
        sources = self._repository.find_analysis_sources(parsed_span, profile_ref)
        if not sources:
            raise RecordingCapabilityError(
                "NOT_FOUND",
                "해당 span과 profile의 AnalysisSource가 준비되지 않았습니다",
            )
        if len(sources) > 1:
            raise RecordingCapabilityError(
                "TEMPORARY_FAILURE",
                "같은 span과 profile에 여러 AnalysisSource가 등록되어 있습니다",
            )
        return sources[0]

    def open_analysis_source(self, analysis_source_ref: str) -> OpenedAnalysisSource:
        source = self._repository.get_analysis_source(analysis_source_ref)
        if source is None:
            raise RecordingCapabilityError("NOT_FOUND", "등록되지 않은 AnalysisSource입니다")
        if source.availability != "AVAILABLE" or source.byte_size is None:
            raise RecordingCapabilityError("UNAVAILABLE", "AnalysisSource를 읽을 수 없습니다")
        opened = self._repository.open_analysis_stream(analysis_source_ref)
        if opened is None:
            raise RecordingCapabilityError("UNAVAILABLE", "AnalysisSource stream이 없습니다")
        stream, content_type = opened
        return OpenedAnalysisSource(
            stream=stream,
            content_type=content_type,
            byte_size=source.byte_size,
        )

    def find_remote_copy(
        self,
        analysis_source_ref: str,
        provider: str,
        *,
        now: datetime | None = None,
    ) -> RemoteCopy | None:
        remote_copy = self._repository.get_remote_copy(analysis_source_ref, provider)
        if remote_copy is None or remote_copy.availability != "AVAILABLE":
            return None
        checked_at = now or datetime.now(timezone.utc)
        if checked_at.tzinfo is None or checked_at.utcoffset() is None:
            raise ValueError("now는 offset-aware datetime이어야 합니다")
        if remote_copy.expires_at is not None and remote_copy.expires_at <= checked_at:
            return None
        return remote_copy

    def register_remote_copy(
        self,
        analysis_source_ref: str,
        provider: str,
        remote_info: RemoteCopyInfo | dict[str, Any],
    ) -> RemoteCopy:
        if self._repository.get_analysis_source(analysis_source_ref) is None:
            raise RecordingCapabilityError("NOT_FOUND", "등록되지 않은 AnalysisSource입니다")
        if not provider:
            raise ValueError("provider는 비어 있을 수 없습니다")
        parsed_info = RemoteCopyInfo.model_validate(remote_info)
        remote_copy = RemoteCopy(
            contract="RemoteCopy",
            contract_version="analysis-source-derived/v1",
            remote_copy_ref=f"rc_{uuid4().hex}",
            analysis_source_ref=analysis_source_ref,
            provider=provider,
            provider_object_ref=parsed_info.provider_object_ref,
            availability="AVAILABLE",
            expires_at=parsed_info.expires_at,
        )
        self._repository.add_remote_copy(remote_copy)
        return remote_copy
