"""Public capabilities for the evidence module."""

from .service import (
    EvidenceContractError,
    assemble,
    build_evidence_needs,
    build_evidence_record,
    build_report_package,
    evaluate_requirements,
    resolve_time,
)

__all__ = [
    "EvidenceContractError",
    "assemble",
    "build_evidence_needs",
    "build_evidence_record",
    "build_report_package",
    "evaluate_requirements",
    "resolve_time",
]
