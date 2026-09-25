import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from .smoke_models import SmokeFailureCode


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
        """Legacy property using hard-coded Gemini Flash rates (USD/M tokens).

        Kept for coarse.py / fine.py callers that are outside this task's edit
        scope. Callers that need injected rates must use cost_with_rates().
        # ponytail: hard-coded rates; Task 11 must migrate coarse/fine to cost_with_rates()
        # AND replace _budget_failure in smoke.py with check_fine_reserve (or an equivalent
        # injected-rates check) in the same sweep — both paths compute cost independently and
        # will diverge once real rates != 0.75/3.75.
        """
        if self.input_tokens is None or self.output_tokens is None:
            return None
        thought = self.thought_tokens
        if thought is None:
            return None
        return (
            Decimal(self.input_tokens) * Decimal("0.75")
            + Decimal(self.output_tokens + thought) * Decimal("3.75")
        ) / Decimal(1_000_000)

    def cost_with_rates(
        self,
        input_usd_per_million: float,
        output_usd_per_million: float,
    ) -> Decimal | None:
        """Return exact Decimal cost using injected per-million-token rates.

        Returns None if any token count is missing (→ BUDGET_UNAVAILABLE upstream).
        """
        if (
            self.input_tokens is None
            or self.output_tokens is None
            or self.thought_tokens is None
        ):
            return None
        in_rate = Decimal(str(input_usd_per_million))
        out_rate = Decimal(str(output_usd_per_million))
        return (
            Decimal(self.input_tokens) * in_rate
            + Decimal(self.output_tokens + self.thought_tokens) * out_rate
        ) / Decimal(1_000_000)


def check_fine_reserve(
    spent_usd: Decimal | None,
    config_max_cost_usd: float,
    config_fine_reserve_usd: float,
) -> SmokeFailureCode | None:
    """Guard called before the Fine stage.

    Returns:
        None              — budget is sufficient, proceed.
        BUDGET_UNAVAILABLE — cost facts missing (spent_usd is None).
        COST_EXCEEDED      — spent + fine_reserve would exceed max_cost_usd.
    """
    if spent_usd is None:
        return SmokeFailureCode.BUDGET_UNAVAILABLE
    if not math.isfinite(config_max_cost_usd) or not math.isfinite(
        config_fine_reserve_usd
    ):
        return SmokeFailureCode.BUDGET_UNAVAILABLE
    max_cost = Decimal(str(config_max_cost_usd))
    reserve = Decimal(str(config_fine_reserve_usd))
    if spent_usd + reserve > max_cost:
        return SmokeFailureCode.COST_EXCEEDED
    return None
