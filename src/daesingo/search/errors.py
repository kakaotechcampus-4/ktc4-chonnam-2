from dataclasses import dataclass
from enum import StrEnum

from .runs import CandidateId, ContractRef


class GeminiBaseUrlRejectionReason(StrEnum):
    MALFORMED = "malformed"
    HTTPS_REQUIRED = "https_required"
    USERINFO = "userinfo"
    UNAPPROVED_HOST = "unapproved_host"
    NON_DEFAULT_PORT = "non_default_port"
    QUERY = "query"
    FRAGMENT = "fragment"


@dataclass(frozen=True, slots=True)
class UnsafeGeminiBaseUrlError(Exception):
    reason: GeminiBaseUrlRejectionReason

    def __str__(self) -> str:
        return f"unsafe Gemini base URL: {self.reason}"


@dataclass(frozen=True, slots=True)
class InvalidCoarseSpanError(Exception):
    source_id: str
    start_sec: float
    end_sec: float
    at_sec: float
    duration_sec: float

    def __str__(self) -> str:
        return (
            f"invalid coarse span for source {self.source_id!r}: "
            f"start={self.start_sec}, end={self.end_sec}, at={self.at_sec}, "
            f"duration={self.duration_sec}"
        )


@dataclass(frozen=True, slots=True)
class CandidateSourceMismatchError(Exception):
    source_ref: ContractRef
    candidate_id: CandidateId
    candidate_timeline_id: str
    candidate_timeline_revision: int
    source_timeline_id: str
    source_timeline_revision: int

    def __str__(self) -> str:
        return (
            f"candidate {self.candidate_id!r} cannot use source "
            f"{self.source_ref.ref!r}: candidate timeline "
            f"{self.candidate_timeline_id!r}@{self.candidate_timeline_revision} "
            f"does not match source timeline "
            f"{self.source_timeline_id!r}@{self.source_timeline_revision}"
        )


@dataclass(frozen=True, slots=True)
class MissingCandidateError(Exception):
    source_ref: ContractRef

    def __str__(self) -> str:
        return f"Fine verification requires a candidate for source {self.source_ref.ref!r}"


@dataclass(frozen=True, slots=True)
class InvalidFineSpanError(Exception):
    source_ref: ContractRef
    candidate_id: CandidateId
    start_sec: float
    end_sec: float

    def __str__(self) -> str:
        return (
            f"candidate {self.candidate_id!r} produced a degenerate Fine span "
            f"[{self.start_sec}, {self.end_sec}] for source {self.source_ref.ref!r}"
        )
