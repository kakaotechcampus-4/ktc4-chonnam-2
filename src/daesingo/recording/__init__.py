"""Recording 모듈의 공개 패키지 경계."""

from .fixtures import RecordingFixture, load_recording_fixture
from .errors import RecordingCapabilityError
from .models import AssetFacts, ContractRef, FrameRef, MediaStream, SourceAsset
from .service import RecordingService

__all__ = [
    "AssetFacts",
    "ContractRef",
    "FrameRef",
    "MediaStream",
    "RecordingCapabilityError",
    "RecordingFixture",
    "RecordingService",
    "SourceAsset",
    "load_recording_fixture",
]
