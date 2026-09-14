"""Small contract helpers shared by evidence policies."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import re
from typing import Any

from .errors import ContractInputError

Contract = dict[str, Any]
_RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


def contract_ref(kind: str, ref: str) -> Contract:
    if not isinstance(kind, str) or not kind or not isinstance(ref, str) or not ref:
        raise ContractInputError("ContractRef requires non-empty kind and ref")
    return {"kind": kind, "ref": ref}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractInputError(message)


def parse_rfc3339(value: str) -> datetime:
    require(isinstance(value, str), "datetime must be a string")
    require(bool(_RFC3339.fullmatch(value)), "datetime must be offset-aware RFC3339")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ContractInputError(f"invalid RFC3339 datetime: {value!r}") from exc
    require(parsed.tzinfo is not None, "datetime must include a UTC offset")
    return parsed


def copied(value: Contract | None) -> Contract | None:
    return deepcopy(value)


def ref_id(value: Contract, field: str) -> str:
    raw = value.get(field)
    require(isinstance(raw, str) and bool(raw), f"{field} must be a non-empty string")
    return raw
