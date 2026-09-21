"""Recording 모듈의 공개 패키지 경계."""

from .fixtures import RecordingFixture, load_recording_fixture
from .errors import RecordingCapabilityError
from .models import (
    AnalysisSource,
    AssetFacts,
    AssetSpan,
    ContractRef,
    DeletionReport,
    DerivedAsset,
    FrameRef,
    IncidentClip,
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
from .probe import FfprobeMediaProbe
from .materialize import LocalAnalysisMaterializer, LocalAnalysisProfile
from .service import OpenedAnalysisSource, RecordingService, RegisteredSource

__all__ = [
    "AnalysisSource",
    "AssetFacts",
    "AssetSpan",
    "ContractRef",
    "DeletionReport",
    "DerivedAsset",
    "FrameRef",
    "FfprobeMediaProbe",
    "IncidentClip",
    "LocalAnalysisMaterializer",
    "LocalAnalysisProfile",
    "MediaStream",
    "OpenedAnalysisSource",
    "RecordingCapabilityError",
    "RecordingFixture",
    "RecordingService",
    "RegisteredSource",
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
