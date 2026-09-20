import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

from daesingo.search.cache import MemoryUploadCache
from daesingo.search.config import GeminiSearchConfig
from daesingo.search.provider import CoarseRequest, FineRequest, GeminiProvider
from daesingo.search.scope import VisualEventType
from daesingo.search.sources import ResolvedAnalysisSource


@dataclass(frozen=True, slots=True)
class _Remote:
    name: str
    uri: str
    state: str


@dataclass(frozen=True, slots=True)
class _FakeFiles:
    upload_calls: list[str] = field(default_factory=list)
    get_calls: list[str] = field(default_factory=list)

    def upload(self, file: str, config: dict[str, str]) -> _Remote:
        del config
        self.upload_calls.append(file)
        return _Remote("uploaded-1", "gemini://uploaded-1", "ACTIVE")

    def get(self, name: str) -> _Remote:
        self.get_calls.append(name)
        return _Remote(name, "gemini://uploaded-1", "ACTIVE")


@dataclass(frozen=True, slots=True)
class _VideoContent:
    type: str
    uri: str
    mime_type: str
    resolution: str
    processing: dict[str, str | float]


@dataclass(frozen=True, slots=True)
class _TextContent:
    type: str
    text: str


class _TextResponseFormat:
    def __init__(self, type: str, mime_type: str, schema: dict[str, object]) -> None:
        del type, mime_type, schema


@dataclass(frozen=True, slots=True)
class _Response:
    status: str
    output_text: str
    usage: None = None


@dataclass(frozen=True, slots=True)
class _FakeInteractions:
    videos: list[_VideoContent] = field(default_factory=list)

    def create(
        self,
        model: str,
        input: list[_VideoContent | _TextContent],
        response_format: _TextResponseFormat,
    ) -> _Response:
        del model, response_format
        video, _ = input
        self.videos.append(video)
        payload = (
            {
                "candidates": [
                    {
                        "event_type": "SIGNAL",
                        "span": {"start_sec": 1, "end_sec": 2},
                        "at_sec": 1.5,
                        "observed": ["signal"],
                        "score": 0.9,
                    }
                ]
            }
            if len(self.videos) == 1
            else {
                "verification": "UNCERTAIN",
                "visual_event_type": None,
                "target": {
                    "association_status": "AMBIGUOUS",
                    "described_as": None,
                    "match_with_hint": None,
                    "association_confidence": None,
                    "track_ref": None,
                    "evidence_refs": [],
                },
                "primitives": [],
                "temporal_facts": [],
                "uncertainties": [],
            }
        )
        return _Response("completed", json.dumps(payload))


@dataclass(frozen=True, slots=True)
class _FakeClient:
    files: _FakeFiles
    interactions: _FakeInteractions


class _FakeApiError(Exception):
    pass


def test_gemini_provider_reuses_cached_upload_for_sequential_coarse_and_fine(
    monkeypatch,
) -> None:
    # Given
    files = _FakeFiles()
    interactions_client = _FakeInteractions()
    client = _FakeClient(files, interactions_client)
    genai = ModuleType("google.genai")
    genai.Client = lambda **kwargs: client
    interactions = ModuleType("google.genai.interactions")
    interactions.VideoContent = _VideoContent
    interactions.TextContent = _TextContent
    interactions.TextResponseFormat = _TextResponseFormat
    errors = ModuleType("google.genai.errors")
    errors.APIError = _FakeApiError
    original_import_module = sys.modules["daesingo.search.provider"].importlib.import_module

    def fake_import_module(name: str) -> ModuleType:
        match name:
            case "google.genai":
                return genai
            case "google.genai.interactions":
                return interactions
            case _:
                return original_import_module(name)

    monkeypatch.setitem(sys.modules, "google.genai", genai)
    monkeypatch.setitem(sys.modules, "google.genai.interactions", interactions)
    monkeypatch.setitem(sys.modules, "google.genai.errors", errors)
    monkeypatch.setattr(
        "daesingo.search.provider.importlib.import_module",
        fake_import_module,
    )
    source = ResolvedAnalysisSource(
        "source-1", Path("clip.mp4"), 10.0, "timeline-1", 4
    )
    provider = GeminiProvider("test-key", GeminiSearchConfig(), MemoryUploadCache())

    # When
    provider.search_coarse(CoarseRequest(source, (VisualEventType.SIGNAL,)))
    provider.verify_fine(
        FineRequest(source, VisualEventType.SIGNAL, "", 0.5, 7.5)
    )

    # Then
    assert files.upload_calls == ["clip.mp4"]
    assert files.get_calls == ["uploaded-1"]
    assert [video.uri for video in interactions_client.videos] == [
        "gemini://uploaded-1",
        "gemini://uploaded-1",
    ]
    assert interactions_client.videos[1].processing == {
        "type": "static",
        "fps": 2.0,
        "start_offset": "0.500s",
        "end_offset": "7.500s",
    }
