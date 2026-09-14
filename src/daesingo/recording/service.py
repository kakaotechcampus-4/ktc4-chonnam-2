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
    StreamPositionLocator,
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
        return service

    def resolve_frame(self, locator: FrameLocator | dict[str, Any]) -> FrameRef:
        parsed = _FRAME_LOCATOR_ADAPTER.validate_python(locator)
        if not isinstance(parsed, StreamPositionLocator):
            raise RecordingCapabilityError(
                "TEMPORARY_FAILURE",
                "TIMELINE_POSITION 해소는 timeline repository 구현 후 제공됩니다",
            )

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
