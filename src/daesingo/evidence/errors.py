"""Errors raised at the evidence public boundary."""


class EvidenceError(ValueError):
    """Base error for invalid inputs or unavailable policy data."""


class ContractInputError(EvidenceError):
    """An upstream value does not satisfy the consumed contract."""


class PolicyConfigurationError(EvidenceError):
    """A requested rule has no versioned policy value."""


class PackageNotReady(EvidenceError):
    """A ready-only ReportPackage cannot be assembled."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code
