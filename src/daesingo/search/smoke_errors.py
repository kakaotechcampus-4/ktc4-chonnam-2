from dataclasses import dataclass
from typing import override


class SmokeProviderError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ProviderInteractionStatusError(SmokeProviderError):
    status: str

    def __str__(self) -> str:
        return f"Gemini interaction ended with status={self.status}"


@dataclass(frozen=True, slots=True)
class ProviderUploadStateError(SmokeProviderError):
    state: str


@dataclass(frozen=True, slots=True)
class ProviderUploadTimeoutError(SmokeProviderError):
    timeout_sec: float


@dataclass(frozen=True, slots=True)
class FixtureRateLimitError(SmokeProviderError):
    def __str__(self) -> str:
        return "429 RESOURCE_EXHAUSTED"


@dataclass(frozen=True, slots=True)
class ProviderApiError(SmokeProviderError):
    detail: str

    def __str__(self) -> str:
        return self.detail


@dataclass(slots=True)
class ProviderPayloadError(SmokeProviderError):
    detail: str

    @override
    def __str__(self) -> str:
        return self.detail
