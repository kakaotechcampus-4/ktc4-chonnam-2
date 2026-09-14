"""Versioned evidence mappings and deterministic report rendering."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ._contract import parse_rfc3339
from .errors import ContractInputError
from .policy_catalog import load_report_policy

_POLICY = load_report_policy()

SAFETY_REPORT_POLICY_REF = _POLICY["policy_ref"]
TIME_POLICY_REF = "policy/time-source-priority-v1"
EVIDENCE_POLICY_REF = "policy/evidence-assembly-v1"

SPECIFIC_TEMPLATE_REF = _POLICY["specific_template_ref"]
GENERIC_TEMPLATE_REF = _POLICY["generic_template_ref"]
SPECIFIC_NO_LOCATION_TEMPLATE_REF = _POLICY["specific_no_location_template_ref"]
GENERIC_NO_LOCATION_TEMPLATE_REF = _POLICY["generic_no_location_template_ref"]

REPORT_TEXT_MIN_LENGTH = _POLICY["report_text_min_length"]
REPORT_TEXT_MAX_LENGTH = _POLICY["report_text_max_length"]
EVENT_POLICY: dict[str, dict[str, str]] = _POLICY["events"]
REPORT_TYPE_LABELS: dict[str, str] = _POLICY["report_type_labels"]
GENERIC_VIOLATION_EXPRESSION: str = _POLICY["generic_violation_expression"]


def event_policy(visual_event_type: str) -> dict[str, str]:
    try:
        return dict(EVENT_POLICY[visual_event_type])
    except KeyError as exc:
        raise ContractInputError(f"unsupported VisualEventType: {visual_event_type!r}") from exc


def report_type_label(safety_report_type: str) -> str:
    try:
        return REPORT_TYPE_LABELS[safety_report_type]
    except KeyError as exc:
        raise ContractInputError(f"unsupported SafetyReportType: {safety_report_type!r}") from exc


def render_report(
    *,
    visual_event_type: str | None,
    situation_response: str | None,
    occurred_at: str,
    location_display: str | None,
    vehicle_number: str,
    violation_expression: str,
) -> dict[str, Any]:
    """Render only from policy-owned slots; no free-form generation occurs."""
    if visual_event_type is None:
        if situation_response != "USER_UNSURE":
            raise ContractInputError("report.input.user_unsure_required")
    elif situation_response not in {"CONFIRMED", "CORRECTED"}:
        raise ContractInputError("report.input.situation_unconfirmed")
    parsed: datetime = parse_rfc3339(occurred_at)
    display_time = parsed.strftime("%Y-%m-%d %H:%M:%S")
    for name, value in (("vehicle_number", vehicle_number), ("violation_expression", violation_expression)):
        if not isinstance(value, str) or not value.strip():
            raise ContractInputError(f"{name} must be a non-empty string")
    if location_display is not None and (not isinstance(location_display, str) or not location_display.strip()):
        raise ContractInputError("location_display must be null or a non-empty string")

    if visual_event_type is None:
        title = _POLICY["generic_title"]
        if location_display is None:
            description = f"{display_time}경 촬영된 차량번호 {vehicle_number} 차량의 {_POLICY['generic_description_tail']}"
            template_ref = GENERIC_NO_LOCATION_TEMPLATE_REF
        else:
            description = (
                f"{display_time}경 {location_display}에서 촬영된 차량번호 {vehicle_number} 차량의 "
                f"{_POLICY['generic_description_tail']}"
            )
            template_ref = GENERIC_TEMPLATE_REF
    else:
        title = event_policy(visual_event_type)["title"]
        location_line = f"{display_time}경 {location_display}에서\n" if location_display is not None else f"{display_time}경 촬영된\n"
        description = (
            f"{location_line}차량번호 {vehicle_number} 차량이\n"
            f"{violation_expression}{_POLICY['specific_description_tail']}"
        )
        template_ref = SPECIFIC_TEMPLATE_REF if location_display is not None else SPECIFIC_NO_LOCATION_TEMPLATE_REF

    if not REPORT_TEXT_MIN_LENGTH <= len(description) <= REPORT_TEXT_MAX_LENGTH:
        raise ContractInputError("rendered report description is outside the 5..900 character policy")
    return {
        "title": title,
        "description": description,
        "template_ref": template_ref,
        "content_length": len(description),
    }
