import importlib
import inspect
import json
import mimetypes
import time
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ValidationError

from .cache import MemoryUploadCache, UploadCache, UploadedFile
from .config import GeminiSearchConfig
from .prompts import COARSE_PROMPT, fine_prompt_for
from .retry import RetryPolicy, call_with_retry
from .schemas import CoarseResponse, FineResponse
from .scope import VisualEventType
from .smoke_errors import (
    ProviderApiError,
    ProviderInteractionStatusError,
    ProviderPayloadError,
    ProviderUploadStateError,
    ProviderUploadTimeoutError,
)
from .sources import ResolvedAnalysisSource
from .usage import ProviderUsage


@dataclass(frozen=True, slots=True)
class CoarseRequest:
    source: ResolvedAnalysisSource
    event_types: tuple[VisualEventType, ...]


@dataclass(frozen=True, slots=True)
class FineRequest:
    source: ResolvedAnalysisSource
    event_type: VisualEventType
    target_hint: str
    start_sec: float
    end_sec: float


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


class GeminiProvider:
    def __init__(
        self,
        api_key: str,
        config: GeminiSearchConfig,
        cache: UploadCache | None = None,
        *,
        runtime: ProviderRuntimeOptions | None = None,
    ) -> None:
        genai = importlib.import_module("google.genai")
        self._interactions = importlib.import_module("google.genai.interactions")
        # 프록시는 Bearer 인증을 요구한다. base_url 을 지정 프록시로 돌리면
        # files.upload 와 interactions.create 가 모두 프록시를 경유한다.
        # ponytail: base_url 이 이미 /v1 을 포함한다. 프록시가 SDK 의 버전
        # 경로(/v1beta 등)를 덧붙이는 경우 운영자가 DAESINGO_GEMINI_BASE_URL 로
        # 버전 없는 base 를 지정하거나 api_version 을 맞춰야 한다 — 로컬 실호출로 확인.
        selected_runtime = runtime or ProviderRuntimeOptions()
        self._client = genai.Client(
            api_key=api_key,
            http_options={
                "base_url": config.base_url,
                "headers": {"Authorization": f"Bearer {api_key}"},
                "timeout": round(selected_runtime.request_timeout_sec * 1000),
                "retry_options": {"attempts": 1},
            },
        )
        self._config = config
        self._cache = cache or MemoryUploadCache()
        self._request_timeout_sec = selected_runtime.request_timeout_sec

    def search_coarse(self, request: CoarseRequest) -> ProviderResult[CoarseResponse]:
        prompt = COARSE_PROMPT.render(
            event_types=", ".join(event.value for event in request.event_types),
            duration_sec=request.source.duration_sec,
        )
        return self._invoke(request.source, prompt, CoarseResponse, None)

    def verify_fine(self, request: FineRequest) -> ProviderResult[FineResponse]:
        prompt = fine_prompt_for(request.event_type).render(
            event_type=request.event_type.value,
            target_hint=request.target_hint or "없음",
            start_sec=request.start_sec,
            end_sec=request.end_sec,
        )
        return self._invoke(
            request.source,
            prompt,
            FineResponse,
            (request.start_sec, request.end_sec),
        )

    def _invoke[ResponseT: BaseModel](
        self,
        source: ResolvedAnalysisSource,
        prompt: str,
        response_model: type[ResponseT],
        offsets: tuple[float, float] | None,
    ) -> ProviderResult[ResponseT]:
        def operation() -> ProviderResult[ResponseT]:
            uploaded = self._uploaded(source)
            processing: dict[str, str | float] = {
                "type": "static",
                "fps": self._config.fine_fps if offsets else self._config.coarse_fps,
            }
            if offsets is not None:
                processing.update(
                    start_offset=f"{offsets[0]:.3f}s",
                    end_offset=f"{offsets[1]:.3f}s",
                )
            video = self._interactions.VideoContent(
                type="video",
                uri=uploaded.uri,
                mime_type=mimetypes.guess_type(source.path)[0] or "video/mp4",
                resolution=(
                    self._config.fine_media_resolution
                    if offsets
                    else self._config.media_resolution
                ),
                processing=processing,
            )
            response_format = self._interactions.TextResponseFormat(
                type="text",
                mime_type="application/json",
                schema=response_model.model_json_schema(),
            )
            started = time.monotonic()
            create = self._client.interactions.create
            parameters = inspect.signature(create).parameters.values()
            supports_timeout = any(
                parameter.name == "timeout"
                or parameter.kind is inspect.Parameter.VAR_KEYWORD
                for parameter in parameters
            )
            create_arguments = {
                "model": self._config.model,
                "input": [
                    video,
                    self._interactions.TextContent(type="text", text=prompt),
                ],
                "response_format": response_format,
            }
            if supports_timeout:
                create_arguments["timeout"] = self._request_timeout_sec
            response = create(**create_arguments)
            latency_ms = round((time.monotonic() - started) * 1000)
            status = str(getattr(response, "status", "") or "")
            if status and status != "completed":
                raise ProviderInteractionStatusError(status)
            payload = json.loads(str(getattr(response, "output_text", "")))
            parsed = response_model.model_validate(payload)
            usage = ProviderUsage.from_sdk(getattr(response, "usage", None))
            return ProviderResult(parsed, usage, latency_ms)

        from google.genai import errors

        try:
            return call_with_retry(
                operation,
                RetryPolicy(self._config.max_retries, self._config.retry_base_sec),
            )
        except errors.APIError as error:
            raise ProviderApiError(str(error)) from error
        except (json.JSONDecodeError, ValidationError) as error:
            raise ProviderPayloadError(str(error)) from error

    def _uploaded(self, source: ResolvedAnalysisSource) -> UploadedFile:
        cached = self._cache.get(source.source_id)
        if cached is not None:
            from google.genai import errors

            try:
                remote = self._client.files.get(name=cached.name)
                if str(getattr(remote.state, "name", remote.state)) == "ACTIVE":
                    return cached
            except errors.APIError:
                cached = None
        mime = mimetypes.guess_type(source.path)[0] or "video/mp4"
        remote = self._client.files.upload(
            file=str(source.path), config={"mime_type": mime}
        )
        processing_started = time.monotonic()
        while str(getattr(remote.state, "name", remote.state)) == "PROCESSING":
            remaining = self._request_timeout_sec - (
                time.monotonic() - processing_started
            )
            if remaining <= 0:
                raise ProviderUploadTimeoutError(self._request_timeout_sec)
            time.sleep(min(2, remaining))
            remote = self._client.files.get(name=remote.name)
        state = str(getattr(remote.state, "name", remote.state))
        if state != "ACTIVE":
            raise ProviderUploadStateError(state)
        uploaded = UploadedFile(name=str(remote.name), uri=str(remote.uri))
        self._cache.put(source.source_id, uploaded)
        return uploaded
