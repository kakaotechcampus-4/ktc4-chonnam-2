from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


class UsageLike(Protocol):
    total_input_tokens: int | None
    total_output_tokens: int | None
    total_thought_tokens: int | None
    total_tokens: int | None


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    input_tokens: int | None
    output_tokens: int | None
    thought_tokens: int | None
    total_tokens: int | None

    @classmethod
    def from_sdk(cls, usage: UsageLike | None) -> "ProviderUsage":
        if usage is None:
            return cls(None, None, None, None)
        return cls(
            input_tokens=usage.total_input_tokens,
            output_tokens=usage.total_output_tokens,
            thought_tokens=usage.total_thought_tokens,
            total_tokens=usage.total_tokens,
        )

    @property
    def cost_usd(self) -> Decimal | None:
        if self.input_tokens is None or self.output_tokens is None:
            return None
        thought = self.thought_tokens
        if thought is None:
            return None
        return (
            Decimal(self.input_tokens) * Decimal("0.75")
            + Decimal(self.output_tokens + thought) * Decimal("3.75")
        ) / Decimal(1_000_000)
