class SmokeProviderError(Exception):
    pass


class ProviderInteractionStatusError(SmokeProviderError):
    def __init__(self, status: str) -> None:
        self.status = status
        super().__init__(str(self))

    def __str__(self) -> str:
        return f"Gemini interaction ended with status={self.status}"


class ProviderUploadStateError(SmokeProviderError):
    def __init__(self, state: str) -> None:
        self.state = state
        super().__init__(state)


class ProviderUploadTimeoutError(SmokeProviderError):
    def __init__(self, timeout_sec: float) -> None:
        self.timeout_sec = timeout_sec
        super().__init__(f"upload timed out after {timeout_sec}s")


class FixtureRateLimitError(SmokeProviderError):
    def __str__(self) -> str:
        return "429 RESOURCE_EXHAUSTED"


class ProviderApiError(SmokeProviderError):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)

    def __str__(self) -> str:
        return self.detail


class ProviderPayloadError(SmokeProviderError):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)

    def __str__(self) -> str:
        return self.detail
