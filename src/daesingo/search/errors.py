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


class UnsafeGeminiBaseUrlError(Exception):
    def __init__(self, reason: GeminiBaseUrlRejectionReason) -> None:
        self.reason = reason
        super().__init__(str(self))

    def __str__(self) -> str:
        return f"unsafe Gemini base URL: {self.reason}"


class InvalidCoarseSpanError(Exception):
    def __init__(
        self,
        source_id: str,
        start_sec: float,
        end_sec: float,
        at_sec: float,
        duration_sec: float,
    ) -> None:
        self.source_id = source_id
        self.start_sec = start_sec
        self.end_sec = end_sec
        self.at_sec = at_sec
        self.duration_sec = duration_sec
        super().__init__(str(self))

    def __str__(self) -> str:
        return (
            f"invalid coarse span for source {self.source_id!r}: "
            f"start={self.start_sec}, end={self.end_sec}, at={self.at_sec}, "
            f"duration={self.duration_sec}"
        )


class CandidateSourceMismatchError(Exception):
    def __init__(
        self,
        source_ref: ContractRef,
        candidate_id: CandidateId,
        candidate_timeline_id: str,
        candidate_timeline_revision: int,
        source_timeline_id: str,
        source_timeline_revision: int,
    ) -> None:
        self.source_ref = source_ref
        self.candidate_id = candidate_id
        self.candidate_timeline_id = candidate_timeline_id
        self.candidate_timeline_revision = candidate_timeline_revision
        self.source_timeline_id = source_timeline_id
        self.source_timeline_revision = source_timeline_revision
        super().__init__(str(self))

    def __str__(self) -> str:
        return (
            f"candidate {self.candidate_id!r} cannot use source "
            f"{self.source_ref.ref!r}: candidate timeline "
            f"{self.candidate_timeline_id!r}@{self.candidate_timeline_revision} "
            f"does not match source timeline "
            f"{self.source_timeline_id!r}@{self.source_timeline_revision}"
        )


class MissingCandidateError(Exception):
    def __init__(self, source_ref: ContractRef) -> None:
        self.source_ref = source_ref
        super().__init__(str(self))

    def __str__(self) -> str:
        return f"Fine verification requires a candidate for source {self.source_ref.ref!r}"


class UnknownCandidateError(Exception):
    def __init__(self, candidate_id: CandidateId) -> None:
        self.candidate_id = candidate_id
        super().__init__(str(self))

    def __str__(self) -> str:
        return f"unknown candidate: {self.candidate_id!r}"


class InvalidFineSpanError(Exception):
    def __init__(
        self,
        source_ref: ContractRef,
        candidate_id: CandidateId,
        start_sec: float,
        end_sec: float,
    ) -> None:
        self.source_ref = source_ref
        self.candidate_id = candidate_id
        self.start_sec = start_sec
        self.end_sec = end_sec
        super().__init__(str(self))

    def __str__(self) -> str:
        return (
            f"candidate {self.candidate_id!r} produced a degenerate Fine span "
            f"[{self.start_sec}, {self.end_sec}] for source {self.source_ref.ref!r}"
        )


class CoarseDurationMismatchError(Exception):
    """Probed duration differs by >250 ms."""

    def __init__(self, source_id: str, declared_sec: float, probed_sec: float) -> None:
        self.source_id = source_id
        self.declared_sec = declared_sec
        self.probed_sec = probed_sec
        super().__init__(str(self))

    def __str__(self) -> str:
        return (
            f"duration mismatch for source {self.source_id!r}: "
            f"declared {self.declared_sec:.3f}s vs probed {self.probed_sec:.3f}s "
            f"(delta {abs(self.probed_sec - self.declared_sec) * 1000:.0f}ms > 250ms)"
        )


class VideoStreamSelectionError(Exception):
    """The execution input cannot identify exactly one VIDEO stream."""

    def __init__(
        self,
        *,
        analysis_source_ref: ContractRef,
        code: str,
        stream_refs: tuple[str, ...],
    ) -> None:
        self.analysis_source_ref = analysis_source_ref
        self.code = code
        self.stream_refs = stream_refs
        super().__init__(str(self))

    def __str__(self) -> str:
        return (
            f"cannot select VIDEO stream for analysis source "
            f"{self.analysis_source_ref.ref!r}: {self.code} "
            f"(stream_refs={self.stream_refs!r})"
        )
