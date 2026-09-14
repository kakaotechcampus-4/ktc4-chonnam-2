"""Recording 모듈의 공개 패키지 경계."""

from .fixtures import RecordingFixture, load_recording_fixture
from .errors import RecordingCapabilityError
from .models import (
    AnalysisSource,
    AssetFacts,
    AssetSpan,
    ContractRef,
    FrameRef,
    MediaStream,
    RecordingTimeline,
    RemoteCopy,
    RemoteCopyInfo,
    SourceAsset,
    SpanResolution,
    TimeRange,
    TimelineRef,
    TimelinePositionLocator,
)
from .service import OpenedAnalysisSource, RecordingService

__all__ = [
    "AnalysisSource",
    "AssetFacts",
    "AssetSpan",
    "ContractRef",
    "FrameRef",
    "MediaStream",
    "OpenedAnalysisSource",
    "RecordingCapabilityError",
    "RecordingFixture",
    "RecordingService",
    "RecordingTimeline",
    "RemoteCopy",
    "RemoteCopyInfo",
    "SourceAsset",
    "SpanResolution",
    "TimeRange",
    "TimelineRef",
    "TimelinePositionLocator",
    "load_recording_fixture",
]
