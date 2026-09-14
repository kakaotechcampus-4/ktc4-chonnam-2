"""Recording 모듈의 공개 패키지 경계."""

from .fixtures import RecordingFixture, load_recording_fixture
from .errors import RecordingCapabilityError
from .models import (
    AssetFacts,
    AssetSpan,
    ContractRef,
    FrameRef,
    MediaStream,
    RecordingTimeline,
    SourceAsset,
    SpanResolution,
    TimeRange,
    TimelineRef,
    TimelinePositionLocator,
)
from .service import RecordingService

__all__ = [
    "AssetFacts",
    "AssetSpan",
    "ContractRef",
    "FrameRef",
    "MediaStream",
    "RecordingCapabilityError",
    "RecordingFixture",
    "RecordingService",
    "RecordingTimeline",
    "SourceAsset",
    "SpanResolution",
    "TimeRange",
    "TimelineRef",
    "TimelinePositionLocator",
    "load_recording_fixture",
]
