"""Declarative requirements for a single submission asset (#47 P-1)."""

from typing import TypedDict

from .errors import ContractInputError
from .policy_catalog import load_attachment_policy


class AttachmentConstraint(TypedDict):
    """Per-file byte ceiling and the policy that requires it."""

    max_byte_size: int
    policy_ref: str


def attachment_constraint(derived_role: str) -> AttachmentConstraint:
    """Return the current submission requirement, without a generation strategy.

    Only PLATE_IMAGE is supported. Evidence independently evaluates the produced
    asset afterward; satisfying this constraint alone does not make a package ready.
    """
    if derived_role != "PLATE_IMAGE":
        raise ContractInputError(f"unsupported attachment derived_role: {derived_role!r}")
    policy = load_attachment_policy()
    return {
        "max_byte_size": policy["limits"]["image_each_bytes"],
        "policy_ref": policy["policy_ref"],
    }
