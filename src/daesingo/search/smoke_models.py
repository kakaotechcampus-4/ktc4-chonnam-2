from decimal import Decimal
from enum import StrEnum, unique
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .runs import CandidateEvent
from .visual import VisualVerificationResult


class SmokeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


@unique
class SmokeStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@unique
class SmokeFailureStage(StrEnum):
    INPUT = "input"
    COARSE = "coarse"
    NO_CANDIDATES = "no_candidates"
    TIME_BUDGET = "time_budget"
    COST_BUDGET = "cost_budget"
    BUDGET_UNAVAILABLE = "budget_unavailable"
    FINE = "fine"


class SmokeUsage(SmokeModel):
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    thought_tokens: int | None
    total_tokens: int | None
    cost_usd: Decimal | None


class SmokeReport(SmokeModel):
    schema_version: Literal["daesingo-search-smoke/v1"] = "daesingo-search-smoke/v1"
    status: SmokeStatus
    failure_stage: SmokeFailureStage | None
    model: str
    config_fingerprint: str
    input_sha256: str
    coarse_candidates: tuple[CandidateEvent, ...]
    selected_candidate: CandidateEvent | None
    fine_result: VisualVerificationResult | None
    usage: SmokeUsage
