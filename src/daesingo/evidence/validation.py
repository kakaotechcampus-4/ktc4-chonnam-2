"""Boundary validators for the five evidence-owned contracts."""

from __future__ import annotations

from typing import Any, Callable

from ._contract import Contract, parse_rfc3339


def _ref(value: Any, kind: str | None = None) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("kind"), str)
        and bool(value["kind"])
        and isinstance(value.get("ref"), str)
        and bool(value["ref"])
        and (kind is None or value["kind"] == kind)
    )


def _required(value: Contract, keys: tuple[str, ...], errors: list[str]) -> None:
    for key in keys:
        if key not in value:
            errors.append(f"missing:{key}")


def _datetime(value: Any, name: str, errors: list[str]) -> None:
    try:
        parse_rfc3339(value)
    except ValueError:
        errors.append(f"invalid_datetime:{name}")


def validate_time_resolution(value: Contract) -> list[str]:
    errors: list[str] = []
    _required(value, ("contract_version", "resolution_ref", "status", "considered", "conflict", "provenance", "post_stamp"), errors)
    if value.get("contract_version") != "time-resolution/v1":
        errors.append("version")
    if not _ref(value.get("resolution_ref"), "time_resolution"):
        errors.append("resolution_ref")
    if value.get("supersedes_ref") is not None and not _ref(value.get("supersedes_ref"), "time_resolution"):
        errors.append("supersedes_ref")
    status = value.get("status")
    if status not in {"OK", "NEEDS_REVIEW", "UNKNOWN"}:
        errors.append("status")
    resolved = value.get("resolved")
    if status == "OK" and not isinstance(resolved, dict):
        errors.append("ok_requires_resolved")
    if status == "UNKNOWN" and resolved is not None:
        errors.append("unknown_forbids_resolved")
    if isinstance(resolved, dict):
        _datetime(resolved.get("value"), "resolved.value", errors)
        verification = resolved.get("verification")
        if verification not in {"AGREED", "VERIFIED", "UNVERIFIED"}:
            errors.append("resolved.verification")
        computation = resolved.get("computation") or {}
        if computation.get("mode") not in {"DIRECT", "BASE_PLUS_OFFSET", "USER_OVERRIDE"}:
            errors.append("computation.mode")
        if computation.get("mode") == "BASE_PLUS_OFFSET":
            if not _ref(computation.get("base_input_ref")) or not isinstance(computation.get("source_offset_ms"), int):
                errors.append("base_plus_offset_inputs")
        if computation.get("mode") == "USER_OVERRIDE":
            selected = value.get("provenance", {}).get("selected_input_ref")
            used = [item for item in value.get("considered", []) if item.get("used")]
            if not (
                status == "OK"
                and verification == "AGREED"
                and resolved.get("user_corrected") is True
                and _ref(selected, "correction_record")
                and len(used) == 1
                and used[0].get("input_kind") == "USER_INPUT"
                and used[0].get("verification") == "AGREED"
            ):
                errors.append("user_override_chain")
        if not _ref(value.get("provenance", {}).get("selected_input_ref")):
            errors.append("resolved_selected_input_ref")
    conflict = value.get("conflict") or {}
    if conflict.get("exists") is False and conflict.get("between_refs") != []:
        errors.append("conflict_false_refs")
    return errors


def _validate_evidence_value(item: Any, name: str, errors: list[str]) -> None:
    if not isinstance(item, dict):
        errors.append(f"{name}:shape")
        return
    _required(item, ("value", "source", "support_refs", "user_corrected", "needs_review"), errors)
    source = item.get("source") or {}
    if source.get("observability") not in {"OBSERVED", "INFERRED"} or not _ref(source.get("ref")):
        errors.append(f"{name}:source")
    if item.get("user_corrected") and item.get("needs_review"):
        errors.append(f"{name}:corrected_needs_review")
    if item.get("value") is None and item.get("needs_review"):
        errors.append(f"{name}:null_needs_review")


def validate_evidence_record(value: Contract) -> list[str]:
    errors: list[str] = []
    _required(value, ("contract_version", "record_ref", "case_ref", "selection_rev", "basis", "event", "provenance"), errors)
    if value.get("contract_version") != "evidence-record/v1.3":
        errors.append("version")
    if not _ref(value.get("record_ref"), "evidence_record") or not _ref(value.get("case_ref"), "case"):
        errors.append("identity_ref")
    if value.get("supersedes_ref") is not None and not _ref(value.get("supersedes_ref"), "evidence_record"):
        errors.append("supersedes_ref")
    if not isinstance(value.get("selection_rev"), int) or value.get("selection_rev", 0) < 1:
        errors.append("selection_rev")
    basis = value.get("basis") or {}
    if not _ref(basis.get("candidate_ref"), "candidate_event") or not _ref(basis.get("visual_evidence_ref"), "visual_evidence"):
        errors.append("basis")
    if not _ref(basis.get("evidence_interval_ref")) or basis.get("evidence_interval_ref", {}).get("kind") not in {"incident_clip", "candidate_event"}:
        errors.append("basis_interval")
    event = value.get("event") or {}
    for name in ("visual_event_type", "safety_report_type", "violation_expression"):
        _validate_evidence_value(event.get(name), f"event.{name}", errors)
    occurred = value.get("occurred_at")
    if occurred is not None:
        _datetime(occurred.get("value"), "occurred_at.value", errors)
        if not _ref(occurred.get("time_resolution_ref"), "time_resolution"):
            errors.append("occurred_at.ref")
        if occurred.get("resolution_status") not in {"OK", "NEEDS_REVIEW"}:
            errors.append("occurred_at.status")
        if "observability" in (occurred.get("source") or {}):
            errors.append("occurred_at.observability")
    if value.get("vehicle_number") is not None:
        _validate_evidence_value(value["vehicle_number"], "vehicle_number", errors)
    for name, item in (value.get("location") or {}).items():
        _validate_evidence_value(item, f"location.{name}", errors)
    response = value.get("situation_response")
    if response is not None:
        if response.get("value") not in {"CONFIRMED", "CORRECTED", "USER_UNSURE"}:
            errors.append("situation_response.value")
        _datetime(response.get("responded_at"), "situation_response.responded_at", errors)
        if response.get("value") != "USER_UNSURE" and not _ref(response.get("candidate_ref"), "candidate_event"):
            errors.append("situation_response.candidate_ref")
        if response.get("value") == "CORRECTED" and not value.get("provenance", {}).get("correction_refs"):
            errors.append("corrected_without_correction_ref")
    return errors


def validate_evidence_needs(value: Contract) -> list[str]:
    errors: list[str] = []
    _required(value, ("contract_version", "basis_record_ref", "items"), errors)
    if value.get("contract_version") != "evidence-needs/v1" or not _ref(value.get("basis_record_ref"), "evidence_record"):
        errors.append("header")
    seen: set[tuple[Any, Any]] = set()
    mapping = {"OVERLAY_TIME_OCR": "OCCURRED_AT", "PLATE_REREAD": "VEHICLE_NUMBER"}
    for item in value.get("items") or []:
        pair = (item.get("kind"), item.get("would_fill"))
        if pair in seen:
            errors.append("duplicate_need")
        seen.add(pair)
        if mapping.get(item.get("kind")) != item.get("would_fill"):
            errors.append("need_mapping")
        if not isinstance(item.get("why", {}).get("code"), str):
            errors.append("need_reason")
    return errors


def validate_requirement_report(value: Contract) -> list[str]:
    errors: list[str] = []
    _required(value, ("contract_version", "requirement_report_ref", "scope", "basis", "policy_ref", "evaluated_at", "overall", "checks"), errors)
    if value.get("contract_version") != "requirement-report/v1" or not _ref(value.get("requirement_report_ref"), "requirement_report"):
        errors.append("header")
    if value.get("scope") not in {"EVIDENCE", "FINAL_PACKAGE"}:
        errors.append("scope")
    _datetime(value.get("evaluated_at"), "evaluated_at", errors)
    checks = value.get("checks") or []
    codes = [check.get("code") for check in checks]
    if not checks or len(codes) != len(set(codes)):
        errors.append("checks")
    outcomes = [check.get("outcome") for check in checks]
    if any(item not in {"PASS", "WARN", "BLOCK", "UNKNOWN"} for item in outcomes):
        errors.append("outcome")
    else:
        precedence = {"PASS": 0, "WARN": 1, "UNKNOWN": 2, "BLOCK": 3}
        if outcomes and value.get("overall") != max(outcomes, key=precedence.__getitem__):
            errors.append("overall")
    return errors


def _validate_report_package(value: Contract, *, version: str, location_nullable: bool) -> list[str]:
    errors: list[str] = []
    _required(value, ("contract_version", "package_ref", "evidence_record_ref", "requirement_report_ref", "created_at", "report_inputs", "report", "assets", "provenance", "handoff"), errors)
    if value.get("contract_version") != version or not _ref(value.get("package_ref"), "report_package"):
        errors.append("header")
    _datetime(value.get("created_at"), "created_at", errors)
    inputs = value.get("report_inputs") or {}
    _required(inputs, ("safety_report_type", "occurred_at", "location", "vehicle_number", "violation_expression"), errors)
    location_present = "location" in inputs
    location = inputs.get("location")
    valid_location = (
        isinstance(location, dict)
        and isinstance(location.get("display_text"), str)
        and bool(location["display_text"])
        and (
            "search_keyword" not in location
            or isinstance(location.get("search_keyword"), str) and bool(location["search_keyword"])
        )
    )
    if not location_present or not (valid_location or location_nullable and location is None):
        errors.append("location")
    if not _ref(value.get("assets", {}).get("report_video_ref"), "derived_asset"):
        errors.append("report_video_ref")
    if "status" in value or "user_reviewed" in value or "submitted" in value:
        errors.append("forbidden_lifecycle")
    handoff = value.get("handoff") or {}
    if handoff.get("destination") != "SAFETY_REPORT":
        errors.append("handoff.destination")
    return errors


def validate_report_package(value: Contract) -> list[str]:
    return _validate_report_package(value, version="report-package/v1.1", location_nullable=True)


def validate_report_package_v1(value: Contract) -> list[str]:
    return _validate_report_package(value, version="report-package/v1", location_nullable=False)


VALIDATORS: dict[str, Callable[[Contract], list[str]]] = {
    "time-resolution/v1": validate_time_resolution,
    "evidence-record/v1.3": validate_evidence_record,
    "evidence-needs/v1": validate_evidence_needs,
    "requirement-report/v1": validate_requirement_report,
    "report-package/v1": validate_report_package_v1,
    "report-package/v1.1": validate_report_package,
}


def validate_contract(value: Contract) -> list[str]:
    version = value.get("contract_version")
    validator = VALIDATORS.get(version)
    if validator is None:
        return [f"unsupported_contract_version:{version}"]
    return validator(value)
