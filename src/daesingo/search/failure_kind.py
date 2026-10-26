"""Search 실패 → `JobExecution.failure_kind` 투영 (#297 RT-10(b)).

값과 규칙의 원문은 `docs/modules/search/decisions/failure-taxonomy.md`다. Worker는 이
함수들의 결과를 그대로 쓰고 따로 매핑하지 않는다.

`None`은 「Search 실패가 아니다」라는 뜻이다 — 성공 · PARTIAL Run, intent OK · ABSTAINED,
그리고 Runtime 소유인 `UsageError`.
"""

from enum import StrEnum, unique

from daesingo.common.usage.port import UsageError

from .errors import (
    CandidateSourceMismatchError,
    CoarseDurationMismatchError,
    InvalidCoarseSpanError,
    InvalidFineSpanError,
    MissingCandidateError,
    UnknownCandidateError,
    UnknownCandidateRunError,
    UnsafeGeminiBaseUrlError,
    VideoStreamSelectionError,
)
from .execution import DeadlineExceededError
from .intent import IntentFailureKind, IntentHintResult, IntentHintStatus
from .media import (
    ByteSizeMismatchError,
    FfmpegError,
    FfprobeError,
    MediaTooLargeError,
    MissingFfmpegError,
    SourceTooLargeError,
)
from .provider import MediaSizeError, RequestSizeError
from .runs import AnalysisRun, RunOutcome
from .smoke_errors import ProviderPayloadError, SmokeProviderError


@unique
class SearchFailureKind(StrEnum):
    PROVIDER_CONFIG = "SEARCH_PROVIDER_CONFIG"
    PROVIDER_ERROR = "SEARCH_PROVIDER_ERROR"
    DEADLINE_EXCEEDED = "SEARCH_DEADLINE_EXCEEDED"
    RESPONSE_INVALID = "SEARCH_RESPONSE_INVALID"
    MEDIA_PREPARATION_FAILED = "SEARCH_MEDIA_PREPARATION_FAILED"
    INPUT_INVALID = "SEARCH_INPUT_INVALID"
    UNCLASSIFIED = "SEARCH_UNCLASSIFIED"


# 인증 · 권한 · 모델 경로 오류. 다시 불러도 같은 결과다.
_CONFIG_STATUS = frozenset({401, 403, 404})

_MEDIA_ERRORS = (
    CoarseDurationMismatchError,
    SourceTooLargeError,
    ByteSizeMismatchError,
    MediaTooLargeError,
    MissingFfmpegError,
    FfprobeError,
    FfmpegError,
    MediaSizeError,
    RequestSizeError,
)
_INPUT_ERRORS = (
    CandidateSourceMismatchError,
    MissingCandidateError,
    UnknownCandidateError,
    UnknownCandidateRunError,
    InvalidFineSpanError,
    VideoStreamSelectionError,
)

# AnalysisRun.issues[].code → failure_kind. 등재 안 된 code는 UNCLASSIFIED.
ISSUE_CODE_KIND: dict[str, SearchFailureKind] = {
    "PROVIDER_CONFIG_ERROR": SearchFailureKind.PROVIDER_CONFIG,
    "PROVIDER_CALL_FAILED": SearchFailureKind.PROVIDER_ERROR,
    "PROVIDER_RESPONSE_INVALID": SearchFailureKind.RESPONSE_INVALID,
    "RUN_DEADLINE_EXCEEDED": SearchFailureKind.DEADLINE_EXCEEDED,
    "MEDIA_PREPARATION_FAILED": SearchFailureKind.MEDIA_PREPARATION_FAILED,
    "COARSE_SPAN_OUT_OF_SOURCE": SearchFailureKind.RESPONSE_INVALID,
}

_INTENT_KIND = {
    IntentFailureKind.CONFIG_ERROR: SearchFailureKind.PROVIDER_CONFIG,
    IntentFailureKind.PROVIDER_ERROR: SearchFailureKind.PROVIDER_ERROR,
    IntentFailureKind.DEADLINE_EXCEEDED: SearchFailureKind.DEADLINE_EXCEEDED,
    IntentFailureKind.RESPONSE_INVALID: SearchFailureKind.RESPONSE_INVALID,
}


def failure_kind_for_error(error: BaseException) -> SearchFailureKind | None:
    """Search public capability가 던진 예외를 분류한다. `UsageError`는 Runtime 몫이라 None."""
    if isinstance(error, UsageError):
        return None
    if isinstance(error, DeadlineExceededError):
        return SearchFailureKind.DEADLINE_EXCEEDED
    if isinstance(error, UnsafeGeminiBaseUrlError):
        return SearchFailureKind.PROVIDER_CONFIG
    if isinstance(error, _MEDIA_ERRORS):
        return SearchFailureKind.MEDIA_PREPARATION_FAILED
    if isinstance(error, _INPUT_ERRORS):
        return SearchFailureKind.INPUT_INVALID
    if isinstance(error, InvalidCoarseSpanError) or _is_unusable_response(error):
        return SearchFailureKind.RESPONSE_INVALID
    status = getattr(error.__cause__, "status_code", None)
    if status in _CONFIG_STATUS:
        return SearchFailureKind.PROVIDER_CONFIG
    if isinstance(error, ProviderPayloadError) and status is None:
        # 응답은 받았지만 JSON · schema · 시각 범위가 맞지 않는다.
        return SearchFailureKind.RESPONSE_INVALID
    if _is_provider_error(error):
        return SearchFailureKind.PROVIDER_ERROR
    return SearchFailureKind.UNCLASSIFIED


def failure_kind_for_run(run: AnalysisRun) -> SearchFailureKind | None:
    """FAILED Run만 실패다. Search는 Run을 실패로 만든 issue를 첫 번째에 둔다."""
    if run.outcome is not RunOutcome.FAILED:
        return None
    if not run.issues:
        return SearchFailureKind.UNCLASSIFIED
    return ISSUE_CODE_KIND.get(run.issues[0].code, SearchFailureKind.UNCLASSIFIED)


def failure_kind_for_intent(result: IntentHintResult) -> SearchFailureKind | None:
    if result.status is not IntentHintStatus.FAILED:
        return None
    if result.failure_kind is None:
        return SearchFailureKind.UNCLASSIFIED
    return _INTENT_KIND.get(result.failure_kind, SearchFailureKind.UNCLASSIFIED)


def provider_issue_code(error: Exception) -> str:
    """Coarse가 provider 호출 실패를 issue code로 남길 때 쓴다 — 위 표와 한 규칙."""
    match failure_kind_for_error(error):
        case SearchFailureKind.PROVIDER_CONFIG:
            return "PROVIDER_CONFIG_ERROR"
        case SearchFailureKind.RESPONSE_INVALID:
            return "PROVIDER_RESPONSE_INVALID"
        case SearchFailureKind.MEDIA_PREPARATION_FAILED:
            return "MEDIA_PREPARATION_FAILED"
        case _:
            return "PROVIDER_CALL_FAILED"


def _is_unusable_response(error: BaseException) -> bool:
    """SDK가 응답을 받았지만 잘리거나 걸러져 쓸 수 없다고 던진 예외."""
    try:
        from openai import ContentFilterFinishReasonError, LengthFinishReasonError
    except ImportError:  # eval-gemini extra 없이 도는 환경
        return False
    return isinstance(error, LengthFinishReasonError | ContentFilterFinishReasonError)


def _is_provider_error(error: BaseException) -> bool:
    if isinstance(error, SmokeProviderError):
        return True
    try:
        from openai import OpenAIError
    except ImportError:
        return False
    return isinstance(error, OpenAIError)
