from __future__ import annotations

import base64
import importlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast, final

if TYPE_CHECKING:
    import openai as _openai
    from openai.types.chat import ChatCompletionMessageParam
    from openai.types.shared_params import ReasoningEffort

from pydantic import BaseModel, ValidationError

from .config import GeminiSearchConfig
from .media import PreparedMedia
from .prompts import COARSE_PROMPT, fine_prompt_for
from .retry import RetryPolicy, call_with_retry
from .schemas import CoarseResponse, FineResponse
from .scope import VisualEventType
from .smoke_errors import ProviderApiError, ProviderPayloadError
from .sources import ResolvedAnalysisSource
from .usage import ProviderUsage


class MediaSizeError(ValueError):
    """Prepared media file exceeds the inline media cap before the network call."""


class RequestSizeError(ValueError):
    """Serialized request payload exceeds the inline request cap before the network call."""


@dataclass(frozen=True, slots=True)
class CoarseRequest:
    source: ResolvedAnalysisSource
    event_types: tuple[VisualEventType, ...]
    media: PreparedMedia | None = field(default=None)
    timeout_sec: float = field(default=60.0)


@dataclass(frozen=True, slots=True)
class FineRequest:
    source: ResolvedAnalysisSource
    event_type: VisualEventType
    target_hint: str
    start_sec: float
    end_sec: float
    media: PreparedMedia | None = field(default=None)
    timeout_sec: float = field(default=60.0)


@dataclass(frozen=True, slots=True)
class ProviderResult[ResponseT: BaseModel]:
    response: ResponseT
    usage: ProviderUsage
    latency_ms: int


@dataclass(frozen=True, slots=True)
class ProviderRuntimeOptions:
    request_timeout_sec: float = 60.0


class SearchProvider(Protocol):
    def search_coarse(
        self, request: CoarseRequest
    ) -> ProviderResult[CoarseResponse]: ...

    def verify_fine(self, request: FineRequest) -> ProviderResult[FineResponse]: ...


def _video_data_url(path: Path, content_type: str) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def _usage_from_completion(usage: object | None) -> ProviderUsage:
    if usage is None:
        return ProviderUsage(None, None, None, None)
    prompt_tokens: int | None = getattr(usage, "prompt_tokens", None)
    completion_tokens: int | None = getattr(usage, "completion_tokens", None)
    total: int | None = None
    if prompt_tokens is not None and completion_tokens is not None:
        total = prompt_tokens + completion_tokens
    # 이 프록시는 사고(thought) 토큰을 별도로 보고하지 않는다. completion_tokens 에
    # 포함되므로 thought 는 0 으로 두어 비용식이 중복 계산하지 않게 한다.
    return ProviderUsage(
        input_tokens=prompt_tokens,
        output_tokens=completion_tokens,
        thought_tokens=0 if completion_tokens is not None else None,
        total_tokens=total,
    )


@final
class GeminiProvider:
    _client: _openai.OpenAI
    _config: GeminiSearchConfig

    def __init__(
        self,
        api_key: str,
        config: GeminiSearchConfig,
        *,
        runtime: ProviderRuntimeOptions | None = None,
    ) -> None:
        _openai_mod = importlib.import_module("openai")
        _OpenAI = cast("type[_openai.OpenAI]", getattr(_openai_mod, "OpenAI"))
        # 프록시(Elice MLAPI)는 OpenAI 호환 /v1/chat/completions 만 제공한다.
        # base_url 이 .../v1 로 끝나면 SDK 가 /chat/completions 를 덧붙인다.
        # Bearer 인증은 api_key 로 자동 구성된다. Files API 는 없으므로 영상은
        # file 콘텐츠 파트에 base64 data URL 로 인라인 전송한다.
        # timeout 은 per-attempt 로 _invoke 에서 주입한다; 여기서는 기본값만 둔다.
        self._client = _OpenAI(
            base_url=config.base_url,
            api_key=api_key,
            timeout=(runtime or ProviderRuntimeOptions()).request_timeout_sec,
            max_retries=0,  # 재시도는 call_with_retry 로 직접 제어한다
        )
        self._config = config

    def search_coarse(self, request: CoarseRequest) -> ProviderResult[CoarseResponse]:
        if request.media is None:
            raise ValueError(
                f"CoarseRequest.media required (source {request.source.source_id!r})"
            )
        prompt = COARSE_PROMPT.render(
            event_types=", ".join(event.value for event in request.event_types),
            duration_sec=request.source.duration_sec,
        )
        return self._invoke(request.media, prompt, CoarseResponse, request.timeout_sec)

    def verify_fine(self, request: FineRequest) -> ProviderResult[FineResponse]:
        if request.media is None:
            raise ValueError(
                f"FineRequest.media required (source {request.source.source_id!r})"
            )
        prompt = fine_prompt_for(request.event_type).render(
            event_type=request.event_type.value,
            target_hint=request.target_hint or "없음",
            start_sec=request.start_sec,
            end_sec=request.end_sec,
        )
        return self._invoke(request.media, prompt, FineResponse, request.timeout_sec)

    def _invoke[ResponseT: BaseModel](
        self,
        media: PreparedMedia,
        prompt: str,
        response_model: type[ResponseT],
        timeout_sec: float,
    ) -> ProviderResult[ResponseT]:
        # ponytail: 전체 영상을 인라인 전송한다 (Files API 없음). 서버측 구간
        # 클리핑·fps·해상도는 미결이라 Fine 구간은 프롬프트로만 지시한다 —
        # config.media_resolution/fps 는 그 처리 도입 시 사용할 자리로 남긴다.

        # --- Cap 1: raw media bytes (BEFORE encoding) ---
        if media.byte_size > self._config.max_inline_media_bytes:
            cap = self._config.max_inline_media_bytes
            raise MediaSizeError(
                f"prepared media is {media.byte_size} bytes, exceeds cap of {cap}"
            )

        data_url = _video_data_url(media.path, media.content_type)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "file",
                        "file": {"file_data": data_url},
                    },
                ],
            }
        ]

        # --- Cap 2: serialized request bytes (BEFORE network call) ---
        serialized = json.dumps(
            {
                "model": self._config.model,
                "messages": messages,
                "reasoning_effort": self._config.reasoning_effort,
            },
            separators=(",", ":"),
        ).encode()
        if len(serialized) > self._config.max_inline_request_bytes:
            req_cap = self._config.max_inline_request_bytes
            raise RequestSizeError(
                f"serialized request is {len(serialized)} bytes, exceeds cap of {req_cap}"
            )

        def operation() -> ProviderResult[ResponseT]:
            started = time.monotonic()
            completion = self._client.chat.completions.parse(
                model=self._config.model,
                messages=cast("list[ChatCompletionMessageParam]", messages),
                response_format=response_model,
                reasoning_effort=cast("ReasoningEffort", self._config.reasoning_effort),
                timeout=timeout_sec,
            )
            latency_ms = round((time.monotonic() - started) * 1000)
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                raise ProviderPayloadError("provider returned no parsed content")
            usage = _usage_from_completion(getattr(completion, "usage", None))
            return ProviderResult(parsed, usage, latency_ms)

        from openai import APIError, BadRequestError

        try:
            return call_with_retry(
                operation,
                RetryPolicy(self._config.max_retries, self._config.retry_base_sec),
            )
        except (BadRequestError, ValidationError) as error:
            raise ProviderPayloadError("provider rejected the request") from error
        except APIError as error:
            raise ProviderApiError("provider API error") from error
