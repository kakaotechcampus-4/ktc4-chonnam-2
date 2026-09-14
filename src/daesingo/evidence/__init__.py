"""Public pure-function boundary for the evidence module."""

from .assembly import assemble_evidence, calculate_evidence_needs
from .corrections import correction_heads
from .errors import ContractInputError, EvidenceError, PackageNotReady, PolicyConfigurationError
from .policy import EVENT_POLICY, SAFETY_REPORT_POLICY_REF, render_report
from .requirements import aggregate_outcomes, build_report_package, evaluate_requirements
from .time_resolution import resolve_time
from .validation import validate_contract

__all__ = [
    "EVENT_POLICY",
    "SAFETY_REPORT_POLICY_REF",
    "ContractInputError",
    "EvidenceError",
    "PackageNotReady",
    "PolicyConfigurationError",
    "aggregate_outcomes",
    "assemble_evidence",
    "build_report_package",
    "calculate_evidence_needs",
    "correction_heads",
    "evaluate_requirements",
    "render_report",
    "resolve_time",
    "validate_contract",
]
