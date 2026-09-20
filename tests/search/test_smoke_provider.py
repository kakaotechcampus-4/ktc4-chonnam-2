import importlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

import pytest

from daesingo.search.cache import MemoryUploadCache
from daesingo.search.config import GeminiSearchConfig
from daesingo.search.provider import (
    CoarseRequest,
    GeminiProvider,
    ProviderRuntimeOptions,
)
from daesingo.search.scope import VisualEventType
from daesingo.search.smoke_errors import FixtureRateLimitError
from daesingo.search.smoke_fixture import (
    FixtureTimeoutError,
    SmokeFixtureProvider,
    SmokeProviderFixture,
)
from daesingo.search.sources import ResolvedAnalysisSource

type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)


@dataclass(frozen=True, slots=True)
class _Remote:
    name: str = "upload-1"
    uri: str = "gemini://upload-1"
    state: str = "ACTIVE"


@dataclass(frozen=True, slots=True)
class _Files:
    def upload(self, *, file: str, config: dict[str, str]) -> _Remote:
        del file, config
        return _Remote()

    def get(self, *, name: str) -> _Remote:
        del name
        return _Remote()


@dataclass(frozen=True, slots=True)
class _Interactions:
    calls: list[dict[str, JsonValue]] = field(default_factory=list)

    def create(self, **kwargs: JsonValue) -> "_Response":
        self.calls.append(kwargs)
        return _Response()


@dataclass(frozen=True, slots=True)
class _Response:
    status: str = "completed"
    output_text: str = '{"candidates": []}'
    usage: None = None


class _ApiError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class _Client:
    files: _Files
    interactions: _Interactions


def test_gemini_provider_disables_sdk_retries_and_sets_both_timeout_units(
    monkeypatch,
) -> None:
    # Given
    client_kwargs: list[dict[str, JsonValue]] = []
    interactions_client = _Interactions()
    client = _Client(_Files(), interactions_client)
    genai = ModuleType("google.genai")

    def client_factory(**kwargs: JsonValue) -> _Client:
        client_kwargs.append(kwargs)
        return client

    genai.Client = client_factory
    interactions = ModuleType("google.genai.interactions")
    interactions.VideoContent = lambda **kwargs: kwargs
    interactions.TextContent = lambda **kwargs: kwargs
    interactions.TextResponseFormat = lambda **kwargs: kwargs
    errors = ModuleType("google.genai.errors")
    errors.APIError = _ApiError
    genai.errors = errors
    original = importlib.import_module

    def fake_import(name: str) -> ModuleType:
        known = {
            "google.genai": genai,
            "google.genai.interactions": interactions,
            "google.genai.errors": errors,
        }.get(name)
        if known is not None:
            return known
        return original(name)

    monkeypatch.setattr("daesingo.search.provider.importlib.import_module", fake_import)
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    monkeypatch.setitem(sys.modules, "google.genai.errors", errors)
    provider = GeminiProvider(
        "secret",
        GeminiSearchConfig(max_retries=1),
        MemoryUploadCache(),
        runtime=ProviderRuntimeOptions(request_timeout_sec=7.5),
    )
    source = ResolvedAnalysisSource("s", Path("clip.mp4"), 12, "t", 1)

    # When
    provider.search_coarse(CoarseRequest(source, (VisualEventType.SIGNAL,)))

    # Then
    http_options = client_kwargs[0]["http_options"]
    assert isinstance(http_options, dict)
    assert http_options["timeout"] == 7500
    assert http_options["retry_options"] == {"attempts": 1}
    assert interactions_client.calls[0]["timeout"] == 7.5


def test_fixture_provider_retries_once_without_sleep_and_stops_at_two_attempts() -> (
    None
):
    # Given
    fixture_path = Path(__file__).parent / "fixtures" / "smoke_provider.json"
    fixture = SmokeProviderFixture.from_path(fixture_path)
    retrying = fixture.model_copy(
        update={"coarse": fixture.coarse.model_copy(update={"rate_limit_failures": 2})}
    )
    provider = SmokeFixtureProvider(retrying)
    source = ResolvedAnalysisSource("s", Path("clip.mp4"), 12, "t", 1)

    # When
    with pytest.raises(FixtureRateLimitError, match="429"):
        provider.search_coarse(CoarseRequest(source, (VisualEventType.SIGNAL,)))

    # Then
    assert provider.call_counts == (2, 0)


def test_fixture_provider_timeout_is_immediate_and_never_calls_fine() -> None:
    # Given
    fixture_path = Path(__file__).parent / "fixtures" / "smoke_provider.json"
    fixture = SmokeProviderFixture.from_path(fixture_path)
    timing_out = fixture.model_copy(
        update={"coarse": fixture.coarse.model_copy(update={"times_out": True})}
    )
    provider = SmokeFixtureProvider(timing_out)
    source = ResolvedAnalysisSource("s", Path("clip.mp4"), 12, "t", 1)

    # When
    with pytest.raises(FixtureTimeoutError):
        provider.search_coarse(CoarseRequest(source, (VisualEventType.SIGNAL,)))

    # Then
    assert provider.call_counts == (1, 0)
