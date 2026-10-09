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
SPECIFIC_NO_PLATE_TEMPLATE_REF = _POLICY["specific_no_plate_template_ref"]
GENERIC_NO_PLATE_TEMPLATE_REF = _POLICY["generic_no_plate_template_ref"]
SPECIFIC_NO_LOCATION_NO_PLATE_TEMPLATE_REF = _POLICY["specific_no_location_no_plate_template_ref"]
GENERIC_NO_LOCATION_NO_PLATE_TEMPLATE_REF = _POLICY["generic_no_location_no_plate_template_ref"]

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
    vehicle_number: str | None,
    violation_expression: str,
) -> dict[str, Any]:
    """Render only from policy-owned slots; no free-form generation occurs.

    `vehicle_number=None` selects a no-plate template: the plate phrase is dropped and the
    policy-owned `no_plate_notice` states that the plate was not identified. Whether a
    plate-less report may exist at all is the caller's gate (ADR-EVIDENCE-008 §6).
    """
    if visual_event_type is None:
        if situation_response != "USER_UNSURE":
            raise ContractInputError("report.input.user_unsure_required")
    elif situation_response not in {"CONFIRMED", "CORRECTED"}:
        raise ContractInputError("report.input.situation_unconfirmed")
    parsed: datetime = parse_rfc3339(occurred_at)
    display_time = parsed.strftime("%Y-%m-%d %H:%M:%S")
    if not isinstance(violation_expression, str) or not violation_expression.strip():
        raise ContractInputError("violation_expression must be a non-empty string")
    if vehicle_number is not None and (not isinstance(vehicle_number, str) or not vehicle_number.strip()):
        raise ContractInputError("vehicle_number must be null or a non-empty string")
    if location_display is not None and (not isinstance(location_display, str) or not location_display.strip()):
        raise ContractInputError("location_display must be null or a non-empty string")
    has_location, has_plate = location_display is not None, vehicle_number is not None
    vehicle = f"차량번호 {vehicle_number} 차량" if has_plate else "차량"
    plate_line = "" if has_plate else f"\n{_POLICY['no_plate_notice']}"

    if visual_event_type is None:
        title = _POLICY["generic_title"]
        if location_display is None:
            description = f"{display_time}경 촬영된 {vehicle}의 {_POLICY['generic_description_tail']}{plate_line}"
        else:
            description = (
                f"{display_time}경 {location_display}에서 촬영된 {vehicle}의 "
                f"{_POLICY['generic_description_tail']}{plate_line}"
            )
        template_ref = {
            (True, True): GENERIC_TEMPLATE_REF,
            (False, True): GENERIC_NO_LOCATION_TEMPLATE_REF,
            (True, False): GENERIC_NO_PLATE_TEMPLATE_REF,
            (False, False): GENERIC_NO_LOCATION_NO_PLATE_TEMPLATE_REF,
        }[(has_location, has_plate)]
    else:
        title = event_policy(visual_event_type)["title"]
        location_line = f"{display_time}경 {location_display}에서\n" if location_display is not None else f"{display_time}경 촬영된\n"
        description = (
            f"{location_line}{vehicle}이\n"
            f"{violation_expression}{_POLICY['specific_description_tail']}{plate_line}"
        )
        template_ref = {
            (True, True): SPECIFIC_TEMPLATE_REF,
            (False, True): SPECIFIC_NO_LOCATION_TEMPLATE_REF,
            (True, False): SPECIFIC_NO_PLATE_TEMPLATE_REF,
            (False, False): SPECIFIC_NO_LOCATION_NO_PLATE_TEMPLATE_REF,
        }[(has_location, has_plate)]

    if not REPORT_TEXT_MIN_LENGTH <= len(description) <= REPORT_TEXT_MAX_LENGTH:
        raise ContractInputError("rendered report description is outside the 5..900 character policy")
    return {
        "title": title,
        "description": description,
        "template_ref": template_ref,
        "content_length": len(description),
    }
