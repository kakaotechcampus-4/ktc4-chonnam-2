from decimal import Decimal
from enum import StrEnum, unique
from typing import Annotated, Literal, NewType, Self, assert_never

from pydantic import AwareDatetime, Field, model_validator
from pydantic_core import PydanticCustomError

from ._base import ContractModel
from .scope import VisualEventType

RunId = NewType("RunId", str)
CandidateId = NewType("CandidateId", str)
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


@unique
class Operation(StrEnum):
    CANDIDATE_SEARCH = "CANDIDATE_SEARCH"
    VISUAL_VERIFY = "VISUAL_VERIFY"


@unique
class RunOutcome(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


@unique
class FailureKind(StrEnum):
    SEARCH_FAILURE = "SEARCH_FAILURE"
    PRIMITIVE_FAILURE = "PRIMITIVE_FAILURE"
    TEMPORAL_ORDER_FAILURE = "TEMPORAL_ORDER_FAILURE"
    TARGET_ASSOCIATION = "TARGET_ASSOCIATION"
    FINE_FALSE_NEGATIVE = "FINE_FALSE_NEGATIVE"
    COST = "COST"
    INFRA = "INFRA"


class ContractRef(ContractModel):
    kind: str = Field(min_length=1)
    ref: str = Field(min_length=1)


class Implementation(ContractModel):
    impl_id: str = Field(min_length=1)
    model_ref: str | None
    prompt_version: str | None
    config_version: str | None


class Issue(ContractModel):
    kind: FailureKind
    code: str = Field(min_length=1)
    scope_ref: str | None = None
    detail: str | None = None


class TokenUsage(ContractModel):
    input_tokens: NonNegativeInt
    output_tokens: NonNegativeInt
    total_tokens: NonNegativeInt

    @model_validator(mode="after")
    def check_total(self) -> Self:
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise PydanticCustomError(
                "token_total", "total_tokens must equal input plus output"
            )
        return self


class Money(ContractModel):
    amount: Decimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)


class UsageSummary(ContractModel):
    processed_duration_ms: NonNegativeInt | None
    token_usage: TokenUsage | None
    latency_ms: NonNegativeInt | None
    total_cost: Money | None


class AnalysisRun(ContractModel):
    run_id: RunId
    operation: Operation
    input_ref: ContractRef
    implementation: Implementation
    outcome: RunOutcome
    started_at: AwareDatetime
    completed_at: AwareDatetime
    issues: tuple[Issue, ...]
    usage_refs: tuple[str, ...]
    usage_summary: UsageSummary
    contract_version: Literal["analysis-run-candidate-event/v1.1"]

    @model_validator(mode="after")
    def check_terminal_state(self) -> Self:
        if self.completed_at < self.started_at:
            raise PydanticCustomError(
                "run_time_order", "completed_at must not precede started_at"
            )
        match self.outcome:
            case RunOutcome.SUCCEEDED:
                if self.issues:
                    raise PydanticCustomError(
                        "succeeded_issues", "SUCCEEDED cannot contain issues"
                    )
            case RunOutcome.PARTIAL:
                if not self.issues:
                    raise PydanticCustomError(
                        "partial_issues", "PARTIAL requires at least one issue"
                    )
            case RunOutcome.FAILED:
                pass
            case unreachable:
                assert_never(unreachable)
        return self


class CandidateSpan(ContractModel):
    timeline_id: str = Field(min_length=1)
    timeline_revision: PositiveInt
    start_ms: NonNegativeInt
    end_ms: PositiveInt
    representative_ms: NonNegativeInt

    @model_validator(mode="after")
    def check_order(self) -> Self:
        if self.end_ms <= self.start_ms:
            raise PydanticCustomError(
                "candidate_span_order", "end_ms must follow start_ms"
            )
        if not self.start_ms <= self.representative_ms <= self.end_ms:
            raise PydanticCustomError(
                "candidate_representative",
                "representative_ms must fall inside the span",
            )
        return self


class CandidateEvent(ContractModel):
    candidate_id: CandidateId
    run_id: RunId
    span: CandidateSpan
    rank: PositiveInt
    ranking_score: Confidence
    event_type_hint: VisualEventType | None
    summary: str
    uncertainties: tuple[str, ...]
    thumbnail_ref: str | None


class AnalysisRunCandidateEvents(ContractModel):
    analysis_run: AnalysisRun
    candidates: tuple[CandidateEvent, ...]

    @model_validator(mode="after")
    def check_candidates(self) -> Self:
        if self.analysis_run.outcome is RunOutcome.FAILED and self.candidates:
            raise PydanticCustomError(
                "failed_candidates", "FAILED cannot return candidates"
            )
        if any(
            candidate.run_id != self.analysis_run.run_id
            for candidate in self.candidates
        ):
            raise PydanticCustomError(
                "candidate_run", "candidate run_id must match AnalysisRun"
            )
        ranks = sorted(candidate.rank for candidate in self.candidates)
        if ranks != list(range(1, len(ranks) + 1)):
            raise PydanticCustomError(
                "candidate_ranks", "ranks must be contiguous from one"
            )
        return self


class CandidateSearchResult(AnalysisRunCandidateEvents):
    @model_validator(mode="after")
    def check_operation(self) -> Self:
        if self.analysis_run.operation is not Operation.CANDIDATE_SEARCH:
            raise PydanticCustomError(
                "search_operation", "search result requires CANDIDATE_SEARCH"
            )
        return self
