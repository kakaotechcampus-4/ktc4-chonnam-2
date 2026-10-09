"""provider HTTP 시도 1회마다 usage를 begin → finish로 남기는 seam(#303, Runtime Tech Spec §11.1).

Runtime이 durable sink를 이 Protocol로 구현한다. Runtime 밖(eval · CLI)은 `InMemoryUsageSink`를 쓴다.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final, Literal, Protocol
from uuid import uuid4

from .usage import ProviderUsage

type UsageOperation = Literal[
    "CANDIDATE_SEARCH", "VISUAL_VERIFY", "HINT_EXTRACT", "DIAGNOSTIC"
]

# ponytail: KRW 단가 · 환율(RD-08) 미정이라 금액은 늘 None. 정해지면 pricing_id와 함께 채운다.
UNPRICED_PRICING_ID: Final = "elice-unpriced-placeholder"
UNPRICED_COST_UNIT: Final = "per_1m_tokens"


class UsagePersistenceError(Exception):
    """usage 기록 실패. provider 재시도 대상이 아니다(저장 실패 ≠ provider 재시도)."""


@dataclass(frozen=True, slots=True)
class UsageAttempt:
    run_ref: str | None
    # run_ref가 None이면 "DIRECT_NO_RUN"(Run 없이 부른 호출).
    run_ref_reason: Literal["DIRECT_NO_RUN"] | None
    provider: str
    model: str
    operation: UsageOperation


@dataclass(frozen=True, slots=True)
class UsageCost:
    # 모르는 비용은 0이 아니라 None이다.
    amount: Decimal | None
    pricing_id: str
    unit: str
    currency: Literal["KRW"] = "KRW"


@dataclass(frozen=True, slots=True)
class UsageObservation:
    succeeded: bool
    # 응답을 못 받았으면 None(관측 안 됨).
    token_usage: ProviderUsage | None
    latency_ms: int
    cost: UsageCost


class UsageSink(Protocol):
    def begin(self, attempt: UsageAttempt) -> str: ...

    def finish(self, usage_id: str, observed: UsageObservation) -> None: ...


@dataclass(slots=True)
class InMemoryUsageSink:
    """Runtime 밖 기본 sink. (usage_id, attempt, observation|None)을 순서대로 쌓는다."""

    _entries: dict[str, tuple[UsageAttempt, UsageObservation | None]] = field(
        default_factory=dict
    )

    def begin(self, attempt: UsageAttempt) -> str:
        usage_id = f"usage_{uuid4().hex}"
        self._entries[usage_id] = (attempt, None)
        return usage_id

    def finish(self, usage_id: str, observed: UsageObservation) -> None:
        attempt, _ = self._entries[usage_id]
        self._entries[usage_id] = (attempt, observed)

    def entries(
        self,
    ) -> tuple[tuple[str, UsageAttempt, UsageObservation | None], ...]:
        return tuple((key, *value) for key, value in self._entries.items())
