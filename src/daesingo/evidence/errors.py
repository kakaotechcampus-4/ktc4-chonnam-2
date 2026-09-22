"""Errors raised at the evidence public boundary."""


class EvidenceError(ValueError):
    """Base error for invalid inputs or unavailable policy data."""


class ContractInputError(EvidenceError):
    """An upstream value does not satisfy the consumed contract."""


class PolicyConfigurationError(EvidenceError):
    """A requested rule has no versioned policy value."""


class VisualEventNotAssembled(EvidenceError):
    """A valid VisualEvidence that must not be adopted into an EvidenceRecord.

    Raised when `assemble_evidence()` is called for an input the caller should have
    consumed as a non-assembly result — a `NOT_OBSERVED` Fine result.  The producer
    contract is intact, so this is not a `ContractInputError`: `classify_visual_evidence()`
    answers the same question without raising.
    """

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class PackageNotReady(EvidenceError):
    """A ready-only ReportPackage cannot be assembled."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code
