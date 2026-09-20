import base64
import importlib
import mimetypes
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ValidationError

from .config import GeminiSearchConfig
from .prompts import COARSE_PROMPT, fine_prompt_for
from .retry import RetryPolicy, call_with_retry
from .schemas import CoarseResponse, FineResponse
from .scope import VisualEventType
from .smoke_errors import ProviderApiError, ProviderPayloadError
from .sources import ResolvedAnalysisSource
from .usage import ProviderUsage


@dataclass(frozen=True, slots=True)
class CoarseRequest:
    source: ResolvedAnalysisSource
    event_types: tuple[VisualEventType, ...]
    # ponytail: temporary path bridge until the media-pipeline task wires
    # open_source through the provider; replace with MediaInput then.
    source_path: Path | None = field(default=None)


@dataclass(frozen=True, slots=True)
class FineRequest:
    source: ResolvedAnalysisSource
    event_type: VisualEventType
    target_hint: str
    start_sec: float
    end_sec: float
    # ponytail: temporary path bridge — same as CoarseRequest.source_path
    source_path: Path | None = field(default=None)


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


def _video_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path)[0] or "video/mp4"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _usage_from_completion(usage: object | None) -> ProviderUsage:
    if usage is None:
        return ProviderUsage(None, None, None, None)
    prompt_tokens = getattr(usage, "prompt_tokens", None)
    completion_tokens = getattr(usage, "completion_tokens", None)
    total = None
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


class GeminiProvider:
    def __init__(
        self,
        api_key: str,
        config: GeminiSearchConfig,
        *,
        runtime: ProviderRuntimeOptions | None = None,
    ) -> None:
        openai = importlib.import_module("openai")
        selected_runtime = runtime or ProviderRuntimeOptions()
        # 프록시(Elice MLAPI)는 OpenAI 호환 /v1/chat/completions 만 제공한다.
        # base_url 이 .../v1 로 끝나면 SDK 가 /chat/completions 를 덧붙인다.
        # Bearer 인증은 api_key 로 자동 구성된다. Files API 는 없으므로 영상은
        # file 콘텐츠 파트에 base64 data URL 로 인라인 전송한다.
        self._client = openai.OpenAI(
            base_url=config.base_url,
            api_key=api_key,
            timeout=selected_runtime.request_timeout_sec,
            max_retries=0,  # 재시도는 call_with_retry 로 직접 제어한다
        )
        self._config = config

    def search_coarse(self, request: CoarseRequest) -> ProviderResult[CoarseResponse]:
        prompt = COARSE_PROMPT.render(
            event_types=", ".join(event.value for event in request.event_types),
            duration_sec=request.source.duration_sec,
        )
        return self._invoke(
            request.source, prompt, CoarseResponse, source_path=request.source_path
        )

    def verify_fine(self, request: FineRequest) -> ProviderResult[FineResponse]:
        prompt = fine_prompt_for(request.event_type).render(
            event_type=request.event_type.value,
            target_hint=request.target_hint or "없음",
            start_sec=request.start_sec,
            end_sec=request.end_sec,
        )
        return self._invoke(
            request.source, prompt, FineResponse, source_path=request.source_path
        )

    def _invoke[ResponseT: BaseModel](
        self,
        source: ResolvedAnalysisSource,
        prompt: str,
        response_model: type[ResponseT],
        *,
        source_path: Path | None = None,
    ) -> ProviderResult[ResponseT]:
        # ponytail: 전체 영상을 인라인 전송한다 (Files API 없음). 서버측 구간
        # 클리핑·fps·해상도는 미결이라 Fine 구간은 프롬프트로만 지시한다 —
        # config.media_resolution/fps 는 그 처리 도입 시 사용할 자리로 남긴다.
        if source_path is None:
            raise ValueError(
                f"source_path required for provider invocation (source {source.source_id!r})"
            )
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "file",
                        "file": {"file_data": _video_data_url(source_path)},
                    },
                ],
            }
        ]

        def operation() -> ProviderResult[ResponseT]:
            started = time.monotonic()
            completion = self._client.chat.completions.parse(
                model=self._config.model,
                messages=messages,
                response_format=response_model,
                reasoning_effort=self._config.reasoning_effort,
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
            raise ProviderPayloadError(str(error)) from error
        except APIError as error:
            raise ProviderApiError(str(error)) from error
