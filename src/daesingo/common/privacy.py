"""Allowlist-oriented sanitization for structured operational logs."""

from __future__ import annotations

import re
from typing import Any, Mapping


_SENSITIVE_KEYS = {
    "address",
    "api_payload",
    "external_payload",
    "frame",
    "frame_data",
    "free_text",
    "gps",
    "lat",
    "latitude",
    "location_hint",
    "lng",
    "lon",
    "longitude",
    "plate",
    "plate_number",
    "raw_payload",
    "user_hint",
    "vehicle_number",
}
_PLATE_PATTERN = re.compile(r"(?<!\w)\d{2,3}[가-힣]\s?\d{4}(?!\w)")
_COORD_PATTERN = re.compile(r"(?<!\d)(?:[1-8]?\d(?:\.\d{4,})?),\s*(?:1[0-7]\d|\d{1,2})(?:\.\d{4,})?(?!\d)")


def _redact_text(value: str) -> str:
    value = _PLATE_PATTERN.sub("[REDACTED_PLATE]", value)
    return _COORD_PATTERN.sub("[REDACTED_COORDINATE]", value)


def sanitize_log_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Return a sanitized copy suitable for structured operational logging."""

    def sanitize(value: Any, key: str | None = None) -> Any:
        if key is not None and key.lower() in _SENSITIVE_KEYS:
            return "[REDACTED]"
        if isinstance(value, Mapping):
            return {str(child_key): sanitize(child, str(child_key)) for child_key, child in value.items()}
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        if isinstance(value, str):
            return _redact_text(value)
        return value

    return sanitize(event)
