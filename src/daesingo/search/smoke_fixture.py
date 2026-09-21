from pathlib import Path

from pydantic import Field

from .provider import CoarseRequest, FineRequest, ProviderResult
from .retry import RetryPolicy, call_with_retry
from .schemas import CoarseResponse, FineResponse
from .smoke_errors import FixtureRateLimitError, SmokeProviderError
from .smoke_models import SmokeModel
from .usage import ProviderUsage


class FixtureUsage(SmokeModel):
    input_tokens: int | None
    output_tokens: int | None
    thought_tokens: int | None
    total_tokens: int | None

    def provider_usage(self) -> ProviderUsage:
        return ProviderUsage(
            self.input_tokens,
            self.output_tokens,
            self.thought_tokens,
            self.total_tokens,
        )


class CoarseFixtureStage(SmokeModel):
    response: CoarseResponse
    usage: FixtureUsage
    latency_ms: int = Field(ge=0)
    rate_limit_failures: int = Field(default=0, ge=0)
    times_out: bool = False


class FineFixtureStage(SmokeModel):
    response: FineResponse
    usage: FixtureUsage
    latency_ms: int = Field(ge=0)
    rate_limit_failures: int = Field(default=0, ge=0)
    times_out: bool = False


class SmokeProviderFixture(SmokeModel):
    model: str = Field(min_length=1)
    coarse: CoarseFixtureStage
    fine: FineFixtureStage

    @classmethod
    def from_path(cls, path: Path) -> "SmokeProviderFixture":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


class FixtureTimeoutError(SmokeProviderError):
    def __init__(self, stage: str) -> None:
        self.stage = stage
        super().__init__(str(self))

    def __str__(self) -> str:
        return f"fixture {self.stage} timed out"


class SmokeFixtureProvider:
    def __init__(self, fixture: SmokeProviderFixture) -> None:
        self._fixture = fixture
        self._coarse_calls = 0
        self._fine_calls = 0

    @property
    def call_counts(self) -> tuple[int, int]:
        return self._coarse_calls, self._fine_calls

    def search_coarse(self, request: CoarseRequest) -> ProviderResult[CoarseResponse]:
        del request

        def operation() -> ProviderResult[CoarseResponse]:
            self._coarse_calls += 1
            if self._fixture.coarse.times_out:
                raise FixtureTimeoutError("coarse")
            if self._coarse_calls <= self._fixture.coarse.rate_limit_failures:
                raise FixtureRateLimitError
            return ProviderResult(
                self._fixture.coarse.response,
                self._fixture.coarse.usage.provider_usage(),
                self._fixture.coarse.latency_ms,
            )

        return call_with_retry(operation, RetryPolicy(1, 0), lambda _: None)

    def verify_fine(self, request: FineRequest) -> ProviderResult[FineResponse]:
        del request

        def operation() -> ProviderResult[FineResponse]:
            self._fine_calls += 1
            if self._fixture.fine.times_out:
                raise FixtureTimeoutError("fine")
            if self._fine_calls <= self._fixture.fine.rate_limit_failures:
                raise FixtureRateLimitError
            return ProviderResult(
                self._fixture.fine.response,
                self._fixture.fine.usage.provider_usage(),
                self._fixture.fine.latency_ms,
            )

        return call_with_retry(operation, RetryPolicy(1, 0), lambda _: None)
