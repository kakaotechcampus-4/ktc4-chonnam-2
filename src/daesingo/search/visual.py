from enum import StrEnum, unique
from typing import Annotated, Literal, Self, assert_never

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from ._base import ContractModel
from .runs import AnalysisRun, CandidateId, ContractRef, Operation, RunId
from .scope import VisualEventType

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
Offset = Annotated[int, Field(ge=0)]
FrameRef = Annotated[str, Field(pattern=r"^fr_[A-Za-z0-9_-]+$")]


@unique
class Verification(StrEnum):
    OBSERVED = "OBSERVED"
    NOT_OBSERVED = "NOT_OBSERVED"
    UNCERTAIN = "UNCERTAIN"


@unique
class AssociationStatus(StrEnum):
    MATCHED = "MATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"


@unique
class PrimitiveState(StrEnum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    UNCERTAIN = "UNCERTAIN"


class Target(ContractModel):
    association_status: AssociationStatus
    described_as: str | None = None
    match_with_hint: bool | None = None
    association_confidence: Confidence | None = None
    track_ref: str | None = None
    evidence_refs: tuple[FrameRef, ...]


class Primitive(ContractModel):
    kind: str = Field(min_length=1)
    state: PrimitiveState
    confidence: Confidence | None = None
    evidence_refs: tuple[FrameRef, ...]


class TemporalFact(ContractModel):
    at_offset_ms: Offset | None = None
    fact: str = Field(min_length=1)
    evidence_refs: tuple[FrameRef, ...]


class Uncertainty(ContractModel):
    kind: str = Field(min_length=1)
    detail: str | None = None
    evidence_refs: tuple[FrameRef, ...]


class VisualEvidence(ContractModel):
    schema_version: Literal["visual-evidence/v1.0"]
    visual_evidence_id: str = Field(min_length=1)
    run_id: RunId
    input_ref: ContractRef
    candidate_id: CandidateId | None
    verification: Verification
    visual_event_type: VisualEventType | None
    target: Target
    primitives: tuple[Primitive, ...]
    temporal_facts: tuple[TemporalFact, ...]
    uncertainties: tuple[Uncertainty, ...]
    legal_status: None

    @model_validator(mode="after")
    def check_verification(self) -> Self:
        match self.verification:
            case Verification.OBSERVED:
                if self.visual_event_type is None:
                    raise PydanticCustomError(
                        "observed_event_type", "OBSERVED requires visual_event_type"
                    )
            case Verification.NOT_OBSERVED | Verification.UNCERTAIN:
                if self.visual_event_type is not None:
                    raise PydanticCustomError(
                        "unobserved_event_type",
                        "NOT_OBSERVED and UNCERTAIN require a null visual_event_type",
                    )
            case unreachable:
                assert_never(unreachable)
        return self


class VisualVerificationResult(ContractModel):
    analysis_run: AnalysisRun
    visual_evidence: VisualEvidence

    @model_validator(mode="after")
    def check_links(self) -> Self:
        if self.analysis_run.operation is not Operation.VISUAL_VERIFY:
            raise PydanticCustomError("visual_operation", "visual result requires VISUAL_VERIFY")
        if self.analysis_run.run_id != self.visual_evidence.run_id:
            raise PydanticCustomError("visual_run", "VisualEvidence run_id must match AnalysisRun")
        if self.analysis_run.input_ref != self.visual_evidence.input_ref:
            raise PydanticCustomError(
                "visual_input", "VisualEvidence input_ref must match AnalysisRun"
            )
        return self
