from decimal import Decimal
from enum import StrEnum, unique
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from .runs import CandidateEvent, ContractRef
from .scope import VisualEventType
from .visual import (
    AssociationStatus,
    PrimitiveState,
    Verification,
    VisualVerificationResult,
)


class SmokeModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)


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


# ---------------------------------------------------------------------------
# daesingo-search-smoke/v2 — sanitized evidence DTOs
# Trust boundary: these types structurally cannot carry free-text, paths,
# URLs, prompts, raw responses, exception strings, or plate-like content.
# ---------------------------------------------------------------------------

NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


@unique
class SmokeFailureCode(StrEnum):
    MEDIA_NOT_FOUND = "MEDIA_NOT_FOUND"
    MEDIA_UNREADABLE = "MEDIA_UNREADABLE"
    MEDIA_UNSUPPORTED = "MEDIA_UNSUPPORTED"
    SOURCE_MAPPING_INVALID = "SOURCE_MAPPING_INVALID"
    SOURCE_SIZE_MISMATCH = "SOURCE_SIZE_MISMATCH"
    MEDIA_TOO_LARGE = "MEDIA_TOO_LARGE"
    DURATION_MISMATCH = "DURATION_MISMATCH"
    CANDIDATE_SOURCE_LINK_INVALID = "CANDIDATE_SOURCE_LINK_INVALID"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    PROVIDER_AUTH = "PROVIDER_AUTH"
    PROVIDER_RATE_LIMIT = "PROVIDER_RATE_LIMIT"
    PROVIDER_PAYLOAD = "PROVIDER_PAYLOAD"
    BUDGET_UNAVAILABLE = "BUDGET_UNAVAILABLE"
    COST_EXCEEDED = "COST_EXCEEDED"
    NO_CANDIDATES = "NO_CANDIDATES"


class SmokeCandidateProjection(SmokeModel):
    """Safe projection of CandidateEvent — omits summary and uncertainties."""

    candidate_id: str = Field(min_length=1)
    source_ref: ContractRef
    timeline_id: str = Field(min_length=1)
    timeline_revision: PositiveInt
    start_ms: NonNegativeInt
    end_ms: PositiveInt
    representative_ms: NonNegativeInt
    rank: PositiveInt
    ranking_score: Confidence
    event_type_hint: VisualEventType | None


class SmokeFineProjection(SmokeModel):
    """Safe projection of VisualEvidence — omits described_as, track_ref,
    evidence_refs, fact strings, uncertainty details and kinds."""

    run_id: str = Field(min_length=1)
    input_ref: ContractRef
    candidate_id: str = Field(min_length=1)
    verification: Verification
    visual_event_type: VisualEventType | None
    target_association_status: AssociationStatus
    target_association_confidence: Confidence | None
    primitive_states: dict[PrimitiveState, int]
    temporal_offsets_ms: tuple[NonNegativeInt, ...]
    uncertainty_count: NonNegativeInt


class SmokeStageMetrics(SmokeModel):
    """Per-stage timing and prepared-media counts — no paths or URLs."""

    name: str = Field(min_length=1)
    elapsed_ms: NonNegativeInt
    prepared_media_bytes: NonNegativeInt | None
    prepared_duration_ms: NonNegativeInt | None


class SmokeReportV2(SmokeModel):
    """daesingo-search-smoke/v2 wire schema.

    Coexists with v1 SmokeReport. v1 remains importable until Tasks 10/11
    migrate the builder and orchestration; the controller will remove v1 once
    all callers are updated. SmokeReportV2 is exported under the alias
    SmokeReport only after that migration; for now both names are available.
    """

    schema_version: Literal["daesingo-search-smoke/v2"] = "daesingo-search-smoke/v2"
    status: SmokeStatus
    failure_stage: SmokeFailureStage | None
    failure_code: SmokeFailureCode | None
    model: str = Field(min_length=1)
    config_fingerprint: str = Field(min_length=1)
    input_sha256: str = Field(min_length=1)
    selected_source_ref: ContractRef | None
    coarse_candidates: tuple[SmokeCandidateProjection, ...]
    selected_candidate_id: str | None
    fine_result: SmokeFineProjection | None
    stages: tuple[SmokeStageMetrics, ...]
    usage: SmokeUsage
    elapsed_ms: NonNegativeInt
