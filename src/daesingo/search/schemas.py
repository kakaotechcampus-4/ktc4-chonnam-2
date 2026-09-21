from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .scope import VisualEventType
from .visual import AssociationStatus, PrimitiveState, Verification


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CoarseSpan(WireModel):
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)

    @model_validator(mode="after")
    def check_order(self) -> Self:
        if self.end_sec <= self.start_sec:
            raise ValueError("coarse span end must follow start")
        return self


class CoarseCandidate(WireModel):
    event_type: VisualEventType
    span: CoarseSpan
    at_sec: float = Field(ge=0)
    observed: tuple[str, ...]
    score: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def check_representative(self) -> Self:
        if not self.span.start_sec <= self.at_sec <= self.span.end_sec:
            raise ValueError("at_sec must fall inside span")
        return self


class CoarseResponse(WireModel):
    candidates: tuple[CoarseCandidate, ...]


class FineTarget(WireModel):
    association_status: AssociationStatus
    described_as: str | None
    match_with_hint: bool | None
    association_confidence: float | None = Field(default=None, ge=0, le=1)
    track_ref: str | None
    evidence_refs: tuple[str, ...]


class FinePrimitive(WireModel):
    kind: str
    state: PrimitiveState
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_refs: tuple[str, ...]


class FineTemporalFact(WireModel):
    at_offset_ms: int | None = Field(default=None, ge=0)
    fact: str
    evidence_refs: tuple[str, ...]


class FineUncertainty(WireModel):
    kind: str
    detail: str | None
    evidence_refs: tuple[str, ...]


class FineResponse(WireModel):
    verification: Verification
    visual_event_type: VisualEventType | None
    target: FineTarget
    primitives: tuple[FinePrimitive, ...]
    temporal_facts: tuple[FineTemporalFact, ...]
    uncertainties: tuple[FineUncertainty, ...]

    @model_validator(mode="after")
    def check_event_type(self) -> Self:
        if (
            self.verification is Verification.OBSERVED
            and self.visual_event_type is None
        ):
            raise ValueError("OBSERVED requires visual_event_type")
        if (
            self.verification is not Verification.OBSERVED
            and self.visual_event_type is not None
        ):
            raise ValueError(
                "non-observed verification requires null visual_event_type"
            )
        return self
