"""Versioned evidence mappings and deterministic report rendering."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from ._contract import parse_rfc3339
from .errors import ContractInputError

with Path(__file__).with_name("policy_data.json").open(encoding="utf-8") as policy_file:
    _POLICY = json.load(policy_file)

SAFETY_REPORT_POLICY_REF = _POLICY["policy_ref"]
REQUIREMENT_POLICY_REF = "policy/requirement-rules-v1"
TIME_POLICY_REF = "policy/time-source-priority-v1"
EVIDENCE_POLICY_REF = "policy/evidence-assembly-v1"

SPECIFIC_TEMPLATE_REF = _POLICY["specific_template_ref"]
GENERIC_TEMPLATE_REF = _POLICY["generic_template_ref"]

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
    location_display: str,
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
    for name, value in (
        ("location_display", location_display),
        ("vehicle_number", vehicle_number),
        ("violation_expression", violation_expression),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ContractInputError(f"{name} must be a non-empty string")

    if visual_event_type is None:
        title = _POLICY["generic_title"]
        description = (
            f"{display_time}경 {location_display}에서 촬영된 차량번호 {vehicle_number} 차량의 "
            f"{_POLICY['generic_description_tail']}"
        )
        template_ref = GENERIC_TEMPLATE_REF
    else:
        title = event_policy(visual_event_type)["title"]
        description = (
            f"{display_time}경 {location_display}에서\n"
            f"차량번호 {vehicle_number} 차량이\n"
            f"{violation_expression}{_POLICY['specific_description_tail']}"
        )
        template_ref = SPECIFIC_TEMPLATE_REF

    if not REPORT_TEXT_MIN_LENGTH <= len(description) <= REPORT_TEXT_MAX_LENGTH:
        raise ContractInputError("rendered report description is outside the 5..900 character policy")
    return {
        "title": title,
        "description": description,
        "template_ref": template_ref,
        "content_length": len(description),
    }
