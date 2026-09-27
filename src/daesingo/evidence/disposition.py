"""Consumption decision for a VisualEvidence, before any EvidenceRecord exists.

`contract-visual-evidence.md` §4-1 defines three observation states and §12 requires
this consumer to treat `NOT_OBSERVED` and `UNCERTAIN` as separate input states.
`NOT_OBSERVED` is a valid Fine result — the run succeeded and found no support for
the candidate — so it is not a contract violation and must not become a Record.

Closing that meaning here keeps `verification` string comparisons out of the call
sites: a consumer asks once what to do with a VisualEvidence and gets a tagged
answer back.  Selecting another candidate after a `NOT_OBSERVED` is not an evidence
decision and is deliberately absent from this module.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._contract import Contract, contract_ref, require

#: The VisualEvidence supports an EvidenceRecord.
ASSEMBLE = "ASSEMBLE"
#: `UNCERTAIN` with no user answer yet — the existing v1 fallback still waits.
AWAIT_SITUATION_RESPONSE = "AWAIT_SITUATION_RESPONSE"
#: A valid negative Fine result — no Record, no report, no package, no error.
NOT_ASSEMBLED = "NOT_ASSEMBLED"

NOT_OBSERVED_REASON = "evidence.visual_event.not_observed"
SITUATION_RESPONSE_MISSING_REASON = "evidence.visual_event.situation_response_missing"


@dataclass(frozen=True)
class VisualEvidenceDisposition:
    """What a consumer may do with one VisualEvidence."""

    decision: str
    verification: str
    visual_evidence_ref: Contract
    reason_code: str | None = None

    @property
    def assembles(self) -> bool:
        return self.decision == ASSEMBLE


def classify_visual_evidence(
    visual_evidence: Contract,
    situation_response: Contract | None = None,
) -> VisualEvidenceDisposition:
    """Decide whether this VisualEvidence may be adopted into an EvidenceRecord.

    Raises `ContractInputError` only when the producer contract itself is broken —
    an unknown `verification`, or a `visual_event_type` that disagrees with it.
    """
    visual_ref = contract_ref("visual_evidence", visual_evidence["visual_evidence_id"])
    verification = visual_evidence.get("verification")
    visual_type = visual_evidence.get("visual_event_type")
    require(verification in {"OBSERVED", "NOT_OBSERVED", "UNCERTAIN"}, "invalid VisualEvidence verification")
    require((verification == "OBSERVED") == (visual_type is not None), "VisualEvidence value/verification mismatch")

    if verification == "NOT_OBSERVED":
        return VisualEvidenceDisposition(
            decision=NOT_ASSEMBLED,
            verification=verification,
            visual_evidence_ref=visual_ref,
            reason_code=NOT_OBSERVED_REASON,
        )
    if verification == "UNCERTAIN" and (situation_response or {}).get("value") != "USER_UNSURE":
        return VisualEvidenceDisposition(
            decision=AWAIT_SITUATION_RESPONSE,
            verification=verification,
            visual_evidence_ref=visual_ref,
            reason_code=SITUATION_RESPONSE_MISSING_REASON,
        )
    return VisualEvidenceDisposition(
        decision=ASSEMBLE,
        verification=verification,
        visual_evidence_ref=visual_ref,
    )
