"""등록된 Source 사실을 단일 파일 상대 시간축으로 배치하는 내부 정책."""

from __future__ import annotations

import math
from uuid import uuid4

from .models import (
    MediaStream, RecordingTimeline, SourceAsset, SourcePlacement, TimeBasis, WorkingAnchor,
)


def build_relative_timeline(
    asset: SourceAsset, streams: tuple[MediaStream, ...],
) -> RecordingTimeline:
    """파일의 시간 범위를 기술한다. stream decode/coverage를 보증하지 않는다."""
    duration = asset.duration_sec
    if asset.availability != "AVAILABLE":
        raise ValueError("읽기가 확인된 SourceAsset으로만 시간축을 생성할 수 있습니다")
    if duration is None or not math.isfinite(duration) or duration <= 0:
        raise ValueError("시간축 생성에는 유한한 양수의 Source duration이 필요합니다")
    refs = [stream.media_stream_ref for stream in streams]
    if (
        not refs
        or refs != asset.media_stream_refs
        or len(refs) != len(set(refs))
        or any(stream.source_asset_ref != asset.source_asset_ref for stream in streams)
    ):
        raise ValueError("SourceAsset과 MediaStream 참조가 일치하지 않습니다")
    if not any(stream.media_type == "VIDEO" for stream in streams):
        raise ValueError("단일 영상 시간축에는 video stream이 필요합니다")
    if any(stream.availability == "UNAVAILABLE" for stream in streams):
        raise ValueError("접근 불가 stream이 있는 Source의 시간축 생성은 지원하지 않습니다")

    return RecordingTimeline(
        contract="RecordingTimeline", contract_version="recording-timeline/v1",
        timeline_id=f"tl_{uuid4().hex}", revision=1,
        # 기존 relative-only fixture의 표기를 따른다. 새로운 mode enum을 만들지 않는다.
        time_basis=TimeBasis(
            mode="ABSOLUTE_AND_RELATIVE",
            working_anchor=WorkingAnchor(value=None, source_candidate_ref=None, status="UNKNOWN"),
        ),
        time_source_candidates=[],
        source_placements=[SourcePlacement(
            source_asset_ref=asset.source_asset_ref,
            timeline_start_sec=0.0, timeline_end_sec=duration,
            media_stream_refs=refs,
        )],
        gaps=[], timeline_status="USABLE_RELATIVE_ONLY", produced_by="recording",
    )
