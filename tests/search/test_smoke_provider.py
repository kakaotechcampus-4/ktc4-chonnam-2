import importlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

import pytest

from daesingo.search.config import GeminiSearchConfig
from daesingo.search.provider import (
    CoarseRequest,
    GeminiProvider,
    ProviderRuntimeOptions,
)
from daesingo.search.runs import ContractRef
from daesingo.search.schemas import CoarseResponse
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


class _ApiError(Exception):
    pass


class _BadRequest(_ApiError):
    pass


@dataclass(frozen=True, slots=True)
class _Message:
    parsed: object


@dataclass(frozen=True, slots=True)
class _Choice:
    message: _Message


@dataclass(frozen=True, slots=True)
class _Completion:
    choices: list[_Choice]
    usage: object | None = None


@dataclass
class _Completions:
    calls: list[dict[str, JsonValue]] = field(default_factory=list)

    def parse(self, **kwargs: JsonValue) -> _Completion:
        self.calls.append(kwargs)
        return _Completion([_Choice(_Message(CoarseResponse(candidates=())))])


@dataclass(frozen=True, slots=True)
class _Chat:
    completions: _Completions


@dataclass(frozen=True, slots=True)
class _OpenAIClient:
    chat: _Chat


def test_gemini_provider_uses_openai_chat_completions_with_inline_video(
    monkeypatch, tmp_path: Path
) -> None:
    # Given
    client_kwargs: dict[str, JsonValue] = {}
    completions = _Completions()
    client = _OpenAIClient(_Chat(completions))

    def openai_factory(**kwargs: JsonValue) -> _OpenAIClient:
        client_kwargs.update(kwargs)
        return client

    openai_module = ModuleType("openai")
    openai_module.OpenAI = openai_factory
    openai_module.APIError = _ApiError
    openai_module.BadRequestError = _BadRequest
    original = importlib.import_module

    def fake_import(name: str) -> ModuleType:
        return openai_module if name == "openai" else original(name)

    monkeypatch.setattr("daesingo.search.provider.importlib.import_module", fake_import)
    monkeypatch.setitem(sys.modules, "openai", openai_module)
    source_file = tmp_path / "clip.mp4"
    source_file.write_bytes(b"video-bytes")
    provider = GeminiProvider(
        "secret",
        GeminiSearchConfig(max_retries=1),
        runtime=ProviderRuntimeOptions(request_timeout_sec=7.5),
    )
    source = ResolvedAnalysisSource(
        ContractRef(kind="analysis_source", ref="s"), 12, "t", 1
    )

    # When
    provider.search_coarse(
        CoarseRequest(source, (VisualEventType.SIGNAL,), source_path=source_file)
    )

    # Then: OpenAI-compatible client, SDK retries off, proxy base_url + Bearer key
    assert client_kwargs["base_url"] == GeminiSearchConfig().base_url
    assert client_kwargs["api_key"] == "secret"
    assert client_kwargs["timeout"] == 7.5
    assert client_kwargs["max_retries"] == 0
    # And: chat.completions.parse with structured output and inline base64 video
    call = completions.calls[0]
    assert call["model"] == "gemini-3.8-flash"
    assert call["response_format"] is CoarseResponse
    assert call["reasoning_effort"] == "low"
    content = call["messages"][0]["content"]
    file_part = next(part for part in content if part["type"] == "file")
    assert file_part["file"]["file_data"].startswith("data:video/mp4;base64,")
    assert not any(part.get("type") == "video" for part in content)


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
    source = ResolvedAnalysisSource(
        ContractRef(kind="analysis_source", ref="s"), 12, "t", 1
    )

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
    source = ResolvedAnalysisSource(
        ContractRef(kind="analysis_source", ref="s"), 12, "t", 1
    )

    # When
    with pytest.raises(FixtureTimeoutError):
        provider.search_coarse(CoarseRequest(source, (VisualEventType.SIGNAL,)))

    # Then
    assert provider.call_counts == (1, 0)
