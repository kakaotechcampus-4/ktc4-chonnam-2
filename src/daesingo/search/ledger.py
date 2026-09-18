from dataclasses import dataclass, field
from decimal import Decimal

from .usage import ProviderUsage


@dataclass(frozen=True, slots=True)
class UsageRecord:
    case_id: str
    model: str
    prompt_version: str
    prompt_fingerprint: str
    config_version: str
    processed_duration_sec: float
    latency_ms: int
    usage: ProviderUsage
    cost_usd: Decimal | None

    def as_eval_fact(self) -> dict[str, object]:
        cost = None
        if self.cost_usd is not None:
            cost = {"amount": str(self.cost_usd), "currency": "USD"}
        return {
            "case_id": self.case_id,
            "provider": "google",
            "model": self.model,
            "prompt_version": self.prompt_version,
            "prompt_fingerprint": self.prompt_fingerprint,
            "config_version": self.config_version,
            "processed_duration_sec": self.processed_duration_sec,
            "latency_ms": self.latency_ms,
            "input_tokens": self.usage.input_tokens,
            "output_tokens": self.usage.output_tokens,
            "thought_tokens": self.usage.thought_tokens,
            "total_tokens": self.usage.total_tokens,
            "cost": cost,
        }


@dataclass(slots=True)
class SearchLedger:
    _records: list[UsageRecord] = field(default_factory=list)

    def append(self, record: UsageRecord) -> None:
        self._records.append(record)

    def records(self) -> tuple[UsageRecord, ...]:
        return tuple(self._records)
