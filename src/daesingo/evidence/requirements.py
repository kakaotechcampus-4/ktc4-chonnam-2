"""RequirementReport evaluation and ready-only ReportPackage assembly."""

from __future__ import annotations

from copy import deepcopy
from typing import Iterable

from ._contract import Contract, contract_ref, parse_rfc3339, require
from .errors import PackageNotReady, PolicyConfigurationError
from .policy import (
    REPORT_TEXT_MAX_LENGTH,
    REPORT_TEXT_MIN_LENGTH,
    REQUIREMENT_POLICY_REF,
    SAFETY_REPORT_POLICY_REF,
    render_report,
    report_type_label,
)

_PRECEDENCE = {"PASS": 0, "WARN": 1, "UNKNOWN": 2, "BLOCK": 3}


def aggregate_outcomes(checks: Iterable[Contract]) -> str:
    values = [check["outcome"] for check in checks]
    require(bool(values), "a normal RequirementReport needs at least one check")
    require(all(value in _PRECEDENCE for value in values), "invalid requirement outcome")
    return max(values, key=_PRECEDENCE.__getitem__)


def _check(
    *,
    code: str,
    category: str,
    outcome: str,
    reason_code: str,
    subject_refs: list[Contract],
    measurement: Contract | None = None,
) -> Contract:
    item: Contract = {
        "code": code,
        "category": category,
        "outcome": outcome,
        "reason_code": reason_code,
        "subject_refs": deepcopy(subject_refs),
    }
    if measurement is not None:
        item["measurement"] = deepcopy(measurement)
    return item


def _evidence_check(code: str, record: Contract) -> Contract:
    subject = [deepcopy(record["record_ref"])]
    if code == "evidence.vehicle_number.present":
        if record.get("vehicle_number"):
            return _check(code=code, category="VEHICLE", outcome="PASS", reason_code="evidence.value_confirmed", subject_refs=subject)
        return _check(code=code, category="VEHICLE", outcome="UNKNOWN", reason_code="evidence.pending_plate_reread", subject_refs=subject)
    if code == "evidence.occurred_at.present":
        occurred = record.get("occurred_at")
        if not occurred:
            return _check(code=code, category="TIME", outcome="UNKNOWN", reason_code="evidence.time_unavailable", subject_refs=subject)
        if occurred.get("resolution_status") == "NEEDS_REVIEW":
            return _check(code=code, category="TIME", outcome="WARN", reason_code="evidence.time_needs_review", subject_refs=subject)
        return _check(code=code, category="TIME", outcome="PASS", reason_code="evidence.value_confirmed", subject_refs=subject)
    if code == "evidence.visual_event.present":
        value = record["event"]["visual_event_type"].get("value")
        if value is not None:
            return _check(code=code, category="EVIDENCE", outcome="PASS", reason_code="evidence.value_confirmed", subject_refs=subject)
        response = record.get("situation_response", {}).get("value")
        if response == "USER_UNSURE":
            return _check(code=code, category="EVIDENCE", outcome="WARN", reason_code="evidence.visual_event_type_unconfirmed", subject_refs=subject)
        return _check(code=code, category="EVIDENCE", outcome="UNKNOWN", reason_code="evidence.visual_event_unresolved", subject_refs=subject)
    if code == "evidence.location.present":
        if any(item.get("value") is not None for item in (record.get("location") or {}).values()):
            return _check(code=code, category="LOCATION", outcome="PASS", reason_code="evidence.location_available", subject_refs=subject)
        return _check(code=code, category="LOCATION", outcome="WARN", reason_code="evidence.location_unavailable", subject_refs=subject)
    raise PolicyConfigurationError(f"unsupported evidence rule: {code}")


def _asset_by_role(asset_facts: Iterable[Contract], role: str) -> Contract | None:
    matches = [item for item in asset_facts if item.get("derived_role") == role]
    require(len(matches) <= 1, f"multiple AssetFacts entries for role {role}")
    return matches[0] if matches else None


def _mock_fact(facts: Contract, name: str) -> Contract | None:
    value = facts.get(name)
    if value is None:
        return None
    require(isinstance(value, dict) and isinstance(value.get("value"), bool), f"{name} must be a boolean fact")
    require(isinstance(value.get("subject_refs"), list), f"{name}.subject_refs is required")
    return value


def _final_check(
    code: str,
    record: Contract,
    asset_facts: list[Contract],
    observation_facts: Contract,
    policy_values: Contract,
    rendered_report: Contract | None,
) -> Contract:
    evidence_ref = deepcopy(record["record_ref"])
    report_video = _asset_by_role(asset_facts, "REPORT_VIDEO")
    if code == "package.asset.report_video.exists":
        if report_video is None:
            return _check(code=code, category="ASSET", outcome="UNKNOWN", reason_code="asset.fact_missing", subject_refs=[])
        ref = report_video["asset_ref"]
        availability = report_video.get("availability")
        require(availability in {"AVAILABLE", "UNAVAILABLE", "UNKNOWN"}, "invalid AssetFacts availability")
        if availability == "AVAILABLE":
            return _check(code=code, category="ASSET", outcome="PASS", reason_code="asset.available", subject_refs=[ref])
        if availability == "UNKNOWN":
            return _check(code=code, category="ASSET", outcome="UNKNOWN", reason_code="asset.availability_unknown", subject_refs=[ref])
        return _check(code=code, category="ASSET", outcome="BLOCK", reason_code="asset.unavailable", subject_refs=[ref])
    if code == "package.vehicle.plate_visible_in_report_video":
        fact = _mock_fact(observation_facts, "plate_visible_in_report_video")
        if fact is None:
            return _check(code=code, category="VEHICLE", outcome="UNKNOWN", reason_code="readout.visibility_not_observed", subject_refs=[])
        return _check(
            code=code,
            category="VEHICLE",
            outcome="PASS" if fact["value"] else "BLOCK",
            reason_code="readout.plate_legible_in_asset" if fact["value"] else "readout.plate_not_legible_in_asset",
            subject_refs=fact["subject_refs"],
        )
    if code == "package.time.overlay_visible":
        fact = _mock_fact(observation_facts, "time_overlay_visible")
        if fact is None:
            return _check(code=code, category="TIME", outcome="UNKNOWN", reason_code="readout.overlay_visibility_not_observed", subject_refs=[])
        return _check(
            code=code,
            category="TIME",
            outcome="PASS" if fact["value"] else "BLOCK",
            reason_code="time.overlay_visible" if fact["value"] else "time.overlay_not_visible",
            subject_refs=fact["subject_refs"],
        )
    if code == "package.time.post_stamp_applied":
        fact = _mock_fact(observation_facts, "post_stamp_applied")
        if fact is None:
            return _check(code=code, category="TIME", outcome="UNKNOWN", reason_code="time.post_stamp_not_observed", subject_refs=[])
        return _check(
            code=code,
            category="TIME",
            outcome="PASS" if fact["value"] else "BLOCK",
            reason_code="time.post_stamp_burned_in" if fact["value"] else "time.post_stamp_missing",
            subject_refs=fact["subject_refs"],
        )
    if code == "package.evidence.situation_unconfirmed":
        unsure = record.get("situation_response", {}).get("value") == "USER_UNSURE"
        return _check(
            code=code,
            category="EVIDENCE",
            outcome="WARN" if unsure else "PASS",
            reason_code="evidence.visual_event_type_unconfirmed" if unsure else "evidence.situation_confirmed",
            subject_refs=[evidence_ref],
        )
    if code == "package.report.content_length":
        require(rendered_report is not None, "content length needs a rendered report")
        length = rendered_report["content_length"]
        outcome = "PASS" if REPORT_TEXT_MIN_LENGTH <= length <= REPORT_TEXT_MAX_LENGTH else "BLOCK"
        return _check(
            code=code,
            category="REPORT_CONTENT",
            outcome=outcome,
            reason_code="report.content_length_valid" if outcome == "PASS" else "report.content_length_invalid",
            subject_refs=[evidence_ref],
            measurement={"actual": length, "limit": REPORT_TEXT_MAX_LENGTH, "unit": "report.characters"},
        )
    if code == "package.asset.report_video.size":
        if "report_video_max_bytes" not in policy_values:
            raise PolicyConfigurationError("policy/requirement-rules-v1 has no adopted report_video_max_bytes")
        if report_video is None or report_video.get("byte_size") is None:
            return _check(code=code, category="ASSET", outcome="UNKNOWN", reason_code="asset.byte_size_unknown", subject_refs=[])
        limit = policy_values["report_video_max_bytes"]
        actual = report_video["byte_size"]
        return _check(
            code=code,
            category="ASSET",
            outcome="PASS" if actual <= limit else "BLOCK",
            reason_code="asset.size_within_policy" if actual <= limit else "asset.size_exceeds_policy",
            subject_refs=[report_video["asset_ref"]],
            measurement={"actual": actual, "limit": limit, "unit": "asset.bytes"},
        )
    if code == "package.deadline.within_policy":
        raise PolicyConfigurationError("policy/requirement-rules-v1 has no adopted deadline rule data")
    raise PolicyConfigurationError(f"unsupported final-package rule: {code}")


def evaluate_requirements(
    evidence_record: Contract,
    *,
    scope: str,
    report_id: str,
    evaluated_at: str,
    rule_codes: Iterable[str],
    asset_facts: Iterable[Contract] = (),
    template_ref: str | None = None,
    observation_facts: Contract | None = None,
    policy_values: Contract | None = None,
    rendered_report: Contract | None = None,
    supersedes_id: str | None = None,
) -> Contract:
    """Evaluate an explicit versioned rule set over contract values."""
    require(scope in {"EVIDENCE", "FINAL_PACKAGE"}, "invalid RequirementReport scope")
    parse_rfc3339(evaluated_at)
    codes = list(rule_codes)
    require(len(codes) == len(set(codes)), "Requirement check codes must be unique")
    assets = [deepcopy(item) for item in asset_facts]
    if scope == "EVIDENCE":
        checks = [_evidence_check(code, evidence_record) for code in codes]
    else:
        checks = [
            _final_check(
                code,
                evidence_record,
                assets,
                observation_facts or {},
                policy_values or {},
                rendered_report,
            )
            for code in codes
        ]
    report: Contract = {
        "contract_version": "requirement-report/v1",
        "requirement_report_ref": contract_ref("requirement_report", report_id),
        "scope": scope,
        "basis": {
            "evidence_record_ref": deepcopy(evidence_record["record_ref"]),
            "asset_refs": [deepcopy(item["asset_ref"]) for item in assets] if scope == "FINAL_PACKAGE" else [],
        },
        "policy_ref": REQUIREMENT_POLICY_REF,
        "evaluated_at": evaluated_at,
        "overall": aggregate_outcomes(checks),
        "checks": checks,
    }
    if scope == "FINAL_PACKAGE" and template_ref:
        report["basis"]["template_ref"] = template_ref
    if supersedes_id:
        report["supersedes_ref"] = contract_ref("requirement_report", supersedes_id)
    return report


def _location_snapshot(record: Contract) -> Contract:
    location = record.get("location") or {}
    display = next((location[key]["value"] for key in ("address", "place_name", "user_hint") if location.get(key)), None)
    if not isinstance(display, str) or not display.strip():
        raise PackageNotReady("package.input.location_missing")
    result: Contract = {"display_text": display}
    keyword = location.get("search_keyword", {}).get("value")
    if isinstance(keyword, str) and keyword.strip():
        result["search_keyword"] = keyword
    return result


def build_report_package(
    evidence_record: Contract,
    requirement_report: Contract,
    *,
    package_id: str,
    created_at: str,
    asset_facts: Iterable[Contract],
    assembly_succeeded: bool = True,
    supersedes_id: str | None = None,
) -> Contract:
    """Build a ready-only immutable bundle or raise a stable boundary error."""
    parse_rfc3339(created_at)
    if requirement_report.get("scope") != "FINAL_PACKAGE" or requirement_report.get("overall") not in {"PASS", "WARN"}:
        raise PackageNotReady("package.requirement_not_ready")
    if requirement_report.get("basis", {}).get("evidence_record_ref") != evidence_record.get("record_ref"):
        raise PackageNotReady("package.requirement_basis_mismatch")
    if not assembly_succeeded:
        raise PackageNotReady("package.assembly_failed")
    assets = [deepcopy(item) for item in asset_facts]
    report_video = _asset_by_role(assets, "REPORT_VIDEO")
    if report_video is None or report_video.get("availability") != "AVAILABLE":
        raise PackageNotReady("package.asset.report_video_missing")
    if report_video.get("byte_size") is None:
        raise PackageNotReady("package.asset.report_video_size_unknown")

    event = evidence_record["event"]
    visual_event_type = event["visual_event_type"]["value"]
    situation_response = evidence_record.get("situation_response", {}).get("value")
    if visual_event_type is None and situation_response != "USER_UNSURE":
        raise PackageNotReady("package.input.user_unsure_required")
    if visual_event_type is not None and situation_response not in {"CONFIRMED", "CORRECTED"}:
        raise PackageNotReady("package.input.situation_unconfirmed")
    occurred = evidence_record.get("occurred_at")
    plate = evidence_record.get("vehicle_number")
    if occurred is None:
        raise PackageNotReady("package.input.occurred_at_missing")
    if plate is None:
        raise PackageNotReady("package.input.vehicle_number_missing")
    location = _location_snapshot(evidence_record)
    rendered = render_report(
        visual_event_type=visual_event_type,
        situation_response=situation_response,
        occurred_at=occurred["value"],
        location_display=location["display_text"],
        vehicle_number=plate["value"],
        violation_expression=event["violation_expression"]["value"],
    )
    expected_template = requirement_report.get("basis", {}).get("template_ref")
    if expected_template and expected_template != rendered["template_ref"]:
        raise PackageNotReady("package.template_basis_mismatch")

    report_video_ref = deepcopy(report_video["asset_ref"])
    plate_image = _asset_by_role(assets, "PLATE_IMAGE")
    source_refs: list[Contract] = []
    for item in report_video.get("lineage") or []:
        if item.get("kind") in {"source_asset", "external_source"} and item not in source_refs:
            source_refs.append(deepcopy(item))
    derived_refs = [report_video_ref]
    package_assets: Contract = {"report_video_ref": report_video_ref}
    if plate_image and plate_image.get("availability") == "AVAILABLE":
        package_assets["plate_image_ref"] = deepcopy(plate_image["asset_ref"])
        derived_refs.append(deepcopy(plate_image["asset_ref"]))

    package: Contract = {
        "contract_version": "report-package/v1",
        "package_ref": contract_ref("report_package", package_id),
        "evidence_record_ref": deepcopy(evidence_record["record_ref"]),
        "requirement_report_ref": deepcopy(requirement_report["requirement_report_ref"]),
        "created_at": created_at,
        "report_inputs": {
            "safety_report_type": report_type_label(event["safety_report_type"]["value"]),
            "occurred_at": occurred["value"],
            "location": location,
            "vehicle_number": plate["value"],
            "violation_expression": event["violation_expression"]["value"],
        },
        "report": {
            "title": rendered["title"],
            "description": rendered["description"],
            "template_ref": rendered["template_ref"],
        },
        "assets": package_assets,
        "provenance": {
            "source_refs": source_refs,
            "derived_asset_refs": derived_refs,
            "policy_ref": SAFETY_REPORT_POLICY_REF,
        },
        "handoff": {
            "destination": "SAFETY_REPORT",
            "supported_actions": ["DOWNLOAD_ASSETS", "COPY_FIELDS", "OPEN_DESTINATION"],
        },
    }
    if supersedes_id:
        package["supersedes_ref"] = contract_ref("report_package", supersedes_id)
    return package
