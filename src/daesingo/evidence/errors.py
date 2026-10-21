"""Errors raised at the evidence public boundary."""


class EvidenceError(ValueError):
    """Base error for invalid inputs or unavailable policy data."""


class ContractInputError(EvidenceError):
    """An upstream value does not satisfy the consumed contract."""


class InvalidCorrectionValue(ContractInputError):
    """A correction's `new_value` is outside its target's value space.

    Raised only by `validate_correction_append()`, before case records the correction.  It is
    the one rejection a user can fix by entering another value; every other pre-append rejection
    (chain, kind/target, previous value, structure) is a plain `ContractInputError` because case
    built the record.  A stored record with the same defect is read as a plain
    `ContractInputError` by `correction_heads()` — the read path does not reclassify it.
    """

    def __init__(self, target_field: str):
        super().__init__(f"invalid new_value for {target_field}")
        self.target_field = target_field


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
