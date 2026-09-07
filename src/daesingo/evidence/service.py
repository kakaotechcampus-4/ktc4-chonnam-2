"""Contract-shaped pure functions for evidence integration.

Every public function accepts and returns plain mappings.  Upstream module
objects are deliberately not imported, so callers can replace fixture JSON
with serialized producer output without changing this module.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping, Sequence

from .policy import EVENT_POLICIES, OUTCOME_PRECEDENCE, EventPolicy


class EvidenceContractError(ValueError):
    """Raised when an input cannot satisfy the canonical contract."""


def _ref(kind: str, value: str) -> dict[str, str]:
    if not isinstance(value, str) or not value:
        raise EvidenceContractError(f"{kind} ref must be a non-empty string")
    return {"kind": kind, "ref": value}


def _copy_ref(value: Mapping[str, Any], *, field: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise EvidenceContractError(f"{field} must be a ContractRef")
    kind = value.get("kind")
    ref = value.get("ref")
    if not isinstance(kind, str) or not kind or not isinstance(ref, str) or not ref:
        raise EvidenceContractError(f"{field} must contain non-empty kind/ref")
    return {"kind": kind, "ref": ref}


def _typed_ref(value: Mapping[str, Any], *, field: str, kind: str) -> dict[str, str]:
    copied = _copy_ref(value, field=field)
    if copied["kind"] != kind:
        raise EvidenceContractError(f"{field}.kind must be {kind!r}")
    return copied


def _mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EvidenceContractError(f"{field} must be an object")
    return value


def _offset_datetime(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise EvidenceContractError(f"{field} must be an offset-aware RFC3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceContractError(f"{field} must be an offset-aware RFC3339 string") from exc
    if parsed.utcoffset() is None:
        raise EvidenceContractError(f"{field} must include a UTC offset")
    return parsed


def _overlay_is_verified(overlay: Mapping[str, Any]) -> bool:
    observation = _mapping(overlay.get("observation"), field="overlay_time_readout.observation")
    validation = _mapping(overlay.get("validation"), field="overlay_time_readout.validation")
    value = observation.get("value")
    if observation.get("status") != "OK" or value is None:
        return False
    _offset_datetime(value, field="overlay_time_readout.observation.value")
    return (
        validation.get("format_ok") is True
        and validation.get("monotonic_ok") is True
        and validation.get("duration_match_ok") is True
        and isinstance(validation.get("sample_count"), int)
        and validation["sample_count"] > 0
    )


def _time_candidate_summary(candidate: Mapping[str, Any]) -> dict[str, Any]:
    candidate_id = candidate.get("candidate_id")
    source_kind = candidate.get("source_kind")
    source_names = {
        "FILENAME": "recording.filename_time",
        "FILE_METADATA": "recording.file_metadata_time",
        "VENDOR_METADATA": "recording.vendor_metadata_time",
    }
    if source_kind not in source_names:
        raise EvidenceContractError(f"unsupported TimeSourceCandidate.source_kind: {source_kind!r}")
    value = candidate.get("value")
    if value is not None:
        _offset_datetime(value, field=f"time_source_candidate[{candidate_id}].value")
    return {
        "input_kind": "OBSERVATION",
        "input_ref": _ref("time_source_candidate", candidate_id),
        "source": {"kind": source_names[source_kind]},
        "value": value,
        "observation_status": candidate.get("observation_status"),
        "verification": "UNVERIFIED",
        "used": False,
    }


def resolve_time(
    overlay_time_readout: Mapping[str, Any] | None,
    time_source_candidates: Sequence[Mapping[str, Any]],
    *,
    resolution_ref: Mapping[str, Any],
    supersedes_ref: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve an authoritative event time from contract-shaped observations."""

    result: dict[str, Any] = {
        "contract_version": "time-resolution/v1",
        "resolution_ref": _typed_ref(
            resolution_ref, field="resolution_ref", kind="time_resolution"
        ),
        "status": "UNKNOWN",
        "considered": [],
        "conflict": {"exists": False, "between_refs": [], "requires_user_notice": False},
        "provenance": {"policy_ref": "time-resolution-policy/v1"},
        "post_stamp": {
            "needed": False,
            "reason_code": "time.unresolved",
            "requires_user_notice": False,
        },
    }
    if supersedes_ref is not None:
        previous = _copy_ref(supersedes_ref, field="supersedes_ref")
        if previous == result["resolution_ref"]:
            raise EvidenceContractError("supersedes_ref must differ from resolution_ref")
        result["supersedes_ref"] = previous

    candidate_summaries = [_time_candidate_summary(candidate) for candidate in time_source_candidates]

    if overlay_time_readout is not None:
        overlay = _mapping(overlay_time_readout, field="overlay_time_readout")
        observation = _mapping(overlay.get("observation"), field="overlay_time_readout.observation")
        overlay_summary = {
            "input_kind": "OBSERVATION",
            "input_ref": _ref("overlay_time_readout", overlay.get("readout_id")),
            "source": {"kind": "readout.overlay_timestamp"},
            "value": observation.get("value"),
            "observation_status": observation.get("status"),
            "verification": "VERIFIED" if _overlay_is_verified(overlay) else "UNVERIFIED",
            "used": False,
        }
        result["considered"].append(overlay_summary)
        if _overlay_is_verified(overlay):
            overlay_summary["used"] = True
            for summary in candidate_summaries:
                summary["reason_code"] = "time.overlay_preferred_over_filename"
            result["considered"].extend(candidate_summaries)
            selected_ref = deepcopy(overlay_summary["input_ref"])
            result.update(
                {
                    "status": "OK",
                    "resolved": {
                        "value": observation["value"],
                        "source": {
                            "kind": "readout.overlay_timestamp",
                            "input_ref": deepcopy(selected_ref),
                        },
                        "verification": "VERIFIED",
                        "computation": {
                            "mode": "DIRECT",
                            "timezone": {
                                "zone_id": "Asia/Seoul",
                                "utc_offset": "+09:00",
                                "source": "SOURCE_EXPLICIT",
                            },
                        },
                        "user_corrected": False,
                    },
                    "provenance": {
                        "policy_ref": "time-resolution-policy/v1",
                        "selected_input_ref": deepcopy(selected_ref),
                    },
                    "post_stamp": {
                        "needed": False,
                        "reason_code": "time.already_verified",
                        "requires_user_notice": False,
                    },
                }
            )
            return result

    result["considered"].extend(candidate_summaries)
    usable = [
        item
        for item in candidate_summaries
        if item["observation_status"] == "OK" and item["value"] is not None
    ]
    if not usable:
        return result

    values = {item["value"] for item in usable}
    preferred = next(
        (item for item in usable if item["source"]["kind"] == "recording.filename_time"),
        usable[0],
    )
    preferred["used"] = True
    conflict = len(values) > 1
    for item in usable:
        if item is not preferred:
            item["reason_code"] = (
                "time.filename_fallback_on_conflict" if conflict else "time.sources_agree"
            )
    selected_ref = deepcopy(preferred["input_ref"])
    result.update(
        {
            "status": "NEEDS_REVIEW" if conflict or len(usable) == 1 else "OK",
            "resolved": {
                "value": preferred["value"],
                "source": {
                    "kind": preferred["source"]["kind"],
                    "input_ref": deepcopy(selected_ref),
                },
                "verification": (
                    "AGREED" if len(usable) > 1 and not conflict else "UNVERIFIED"
                ),
                "computation": {
                    "mode": "DIRECT",
                    "timezone": {
                        "zone_id": "Asia/Seoul",
                        "utc_offset": "+09:00",
                        "source": "SOURCE_EXPLICIT",
                    },
                },
                "user_corrected": False,
            },
            "conflict": {
                "exists": conflict,
                "between_refs": [deepcopy(item["input_ref"]) for item in usable] if conflict else [],
                "requires_user_notice": conflict,
            },
            "provenance": {
                "policy_ref": "time-resolution-policy/v1",
                "selected_input_ref": deepcopy(selected_ref),
            },
            "post_stamp": {
                "needed": True,
                "reason_code": "time.overlay_not_verified",
                "requires_user_notice": False,
            },
        }
    )
    return result


def _evidence_value(
    value: Any,
    *,
    source_kind: str,
    source_ref: Mapping[str, Any] | None,
    observability: str,
    label_key: str | None,
    support_refs: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    if observability not in {"OBSERVED", "INFERRED"}:
        raise EvidenceContractError(f"unsupported observability: {observability!r}")
    return {
        "value": deepcopy(value),
        "source": {
            "kind": source_kind,
            "ref": _copy_ref(source_ref, field="source_ref") if source_ref is not None else None,
            "observability": observability,
            "label_key": label_key,
        },
        "support_refs": [_copy_ref(ref, field="support_ref") for ref in support_refs],
        "user_corrected": False,
    }


def _event_policy(visual_evidence: Mapping[str, Any]) -> tuple[EventPolicy, str]:
    if visual_evidence.get("verification") != "OBSERVED":
        raise EvidenceContractError("VisualEvidence must be OBSERVED for first-integration assembly")
    event_type = visual_evidence.get("visual_event_type")
    try:
        return EVENT_POLICIES[event_type], event_type
    except KeyError as exc:
        raise EvidenceContractError(f"unsupported visual_event_type: {event_type!r}") from exc


def _gps_location(observations: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    for index, raw_observation in enumerate(observations):
        observation = _mapping(raw_observation, field=f"observations[{index}]")
        if observation.get("contract_version") != "observation/v1":
            raise EvidenceContractError("Observation.contract_version must be observation/v1")
        status = observation.get("status")
        value = observation.get("value")
        if status in {"UNKNOWN", "ERROR", "NOT_APPLICABLE"}:
            if value is not None:
                raise EvidenceContractError(f"Observation status {status} requires value=null")
            continue
        if status == "OK" and value is None:
            raise EvidenceContractError("Observation status OK requires a value")
        source = _mapping(observation.get("source"), field=f"observations[{index}].source")
        if status == "OK" and source.get("kind") == "recording.gps_stream":
            coordinate = _mapping(value, field=f"observations[{index}].value")
            lat = coordinate.get("lat")
            lon = coordinate.get("lon", coordinate.get("lng"))
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                raise EvidenceContractError("GPS Observation value must contain numeric lat/lon")
            source_ref = source.get("ref")
            return _evidence_value(
                {"lat": lat, "lon": lon},
                source_kind="recording.gps_stream",
                source_ref=source_ref,
                observability="OBSERVED",
                label_key="location.source.gps",
                support_refs=observation.get("support_refs", []),
            )
    return None


def build_evidence_record(
    visual_evidence: Mapping[str, Any],
    plate_readout: Mapping[str, Any] | None,
    observations: Sequence[Mapping[str, Any]],
    time_resolution: Mapping[str, Any],
    *,
    record_ref: Mapping[str, Any],
    case_ref: Mapping[str, Any],
    selection_rev: int,
    candidate_ref: Mapping[str, Any],
    evidence_interval_ref: Mapping[str, Any],
    location_hint: str | None = None,
    supersedes_ref: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Promote usable observations into an immutable EvidenceRecord."""

    visual = _mapping(visual_evidence, field="visual_evidence")
    policy, event_type = _event_policy(visual)
    if not isinstance(selection_rev, int) or selection_rev < 1:
        raise EvidenceContractError("selection_rev must be a positive integer")
    visual_ref = _ref("visual_evidence", visual.get("visual_evidence_id"))
    ambiguous = _mapping(visual.get("target"), field="visual_evidence.target").get(
        "association_status"
    ) == "AMBIGUOUS"
    expression = policy.ambiguous_expression if ambiguous else policy.violation_expression

    record: dict[str, Any] = {
        "contract_version": "evidence-record/v1.1",
        "record_ref": _typed_ref(record_ref, field="record_ref", kind="evidence_record"),
        "case_ref": _typed_ref(case_ref, field="case_ref", kind="case"),
        "selection_rev": selection_rev,
        "basis": {
            "candidate_ref": _typed_ref(
                candidate_ref, field="candidate_ref", kind="candidate_event"
            ),
            "visual_evidence_ref": deepcopy(visual_ref),
            "evidence_interval_ref": _typed_ref(
                evidence_interval_ref, field="evidence_interval_ref", kind="asset_span"
            ),
        },
        "event": {
            "visual_event_type": _evidence_value(
                event_type,
                source_kind="search.visual_inference",
                source_ref=visual_ref,
                observability="OBSERVED",
                label_key="event.source.visual_inference",
            ),
            "safety_report_type": _evidence_value(
                policy.safety_report_type,
                source_kind="evidence.policy_mapping",
                source_ref=None,
                observability="INFERRED",
                label_key="report_type.source.policy_mapping",
            ),
            "violation_expression": _evidence_value(
                expression,
                source_kind="evidence.policy_mapping",
                source_ref=None,
                observability="INFERRED",
                label_key="violation.source.policy_mapping",
            ),
        },
        "provenance": {
            "input_refs": [deepcopy(visual_ref)],
            "correction_refs": [],
            "policy_ref": "evidence-record-policy/v1",
        },
    }
    if supersedes_ref is not None:
        previous = _copy_ref(supersedes_ref, field="supersedes_ref")
        if previous == record["record_ref"]:
            raise EvidenceContractError("supersedes_ref must differ from record_ref")
        record["supersedes_ref"] = previous

    resolution_status = time_resolution.get("status")
    if resolution_status in {"OK", "NEEDS_REVIEW"}:
        resolved = _mapping(time_resolution.get("resolved"), field="time_resolution.resolved")
        record["occurred_at"] = {
            "value": resolved.get("value"),
            "time_resolution_ref": _copy_ref(
                time_resolution.get("resolution_ref"), field="time_resolution.resolution_ref"
            ),
            "resolution_status": resolution_status,
        }

    if plate_readout is not None:
        plate = _mapping(plate_readout, field="plate_readout")
        plate_ref = _ref("plate_readout", plate.get("readout_id"))
        record["provenance"]["input_refs"].append(deepcopy(plate_ref))
        observation = _mapping(plate.get("observation"), field="plate_readout.observation")
        if (
            plate.get("abstained") is False
            and observation.get("status") == "OK"
            and isinstance(observation.get("value"), str)
            and observation["value"].strip()
        ):
            record["vehicle_number"] = _evidence_value(
                observation["value"],
                source_kind="readout.plate_overlay_ocr",
                source_ref=plate_ref,
                observability="OBSERVED",
                label_key="plate.source.overlay_ocr",
            )

    selected = _mapping(
        _mapping(time_resolution.get("provenance"), field="time_resolution.provenance").get(
            "selected_input_ref"
        ),
        field="time_resolution.provenance.selected_input_ref",
    ) if time_resolution.get("resolved") is not None else None
    if selected is not None and selected.get("kind") == "overlay_time_readout":
        record["provenance"]["input_refs"].append(_copy_ref(selected, field="selected_input_ref"))

    location: dict[str, Any] = {}
    gps_value = _gps_location(observations)
    if gps_value is not None:
        location["coord"] = gps_value
    if isinstance(location_hint, str) and location_hint.strip():
        location["user_hint"] = _evidence_value(
            location_hint.strip(),
            source_kind="case.user_hint",
            source_ref=record["case_ref"],
            observability="INFERRED",
            label_key=None,
        )
    if location:
        record["location"] = location
    return record


def build_evidence_needs(evidence_record: Mapping[str, Any]) -> dict[str, Any]:
    """Return declarative follow-up needs without dispatching work."""

    record_ref = _typed_ref(
        evidence_record.get("record_ref"), field="record_ref", kind="evidence_record"
    )
    items: list[dict[str, Any]] = []
    if "occurred_at" not in evidence_record:
        items.append(
            {
                "kind": "OVERLAY_TIME_OCR",
                "would_fill": "OCCURRED_AT",
                "why": {
                    "code": "evidence.occurred_at.unconfirmed",
                    "summary": "사건 발생시각을 확정하지 못했습니다.",
                },
                "optional": False,
                "context_refs": [
                    {
                        "role": "evidence.interval",
                        "ref": _copy_ref(
                            _mapping(evidence_record.get("basis"), field="basis").get(
                                "evidence_interval_ref"
                            ),
                            field="basis.evidence_interval_ref",
                        ),
                    }
                ],
            }
        )
    if "vehicle_number" not in evidence_record:
        basis = _mapping(evidence_record.get("basis"), field="basis")
        items.append(
            {
                "kind": "PLATE_REREAD",
                "would_fill": "VEHICLE_NUMBER",
                "why": {
                    "code": "evidence.vehicle_number.unconfirmed",
                    "summary": "대상 차량 번호판을 확정하지 못했습니다.",
                },
                "optional": False,
                "context_refs": [
                    {
                        "role": "evidence.interval",
                        "ref": _copy_ref(
                            basis.get("evidence_interval_ref"),
                            field="basis.evidence_interval_ref",
                        ),
                    },
                    {
                        "role": "evidence.target_hint",
                        "ref": _copy_ref(
                            basis.get("visual_evidence_ref"),
                            field="basis.visual_evidence_ref",
                        ),
                    },
                ],
            }
        )
    return {
        "contract_version": "evidence-needs/v1",
        "basis_record_ref": record_ref,
        "items": items,
    }


def aggregate_requirement_outcomes(outcomes: Sequence[str]) -> str:
    """Aggregate RequirementCheck outcomes using the canonical precedence."""

    if not outcomes:
        raise EvidenceContractError("a RequirementReport must contain at least one check")
    invalid = [outcome for outcome in outcomes if outcome not in OUTCOME_PRECEDENCE]
    if invalid:
        raise EvidenceContractError(f"unsupported requirement outcome: {invalid[0]!r}")
    return max(outcomes, key=OUTCOME_PRECEDENCE.__getitem__)


def evaluate_requirements(
    evidence_record: Mapping[str, Any],
    *,
    requirement_report_ref: Mapping[str, Any],
    scope: str,
    evaluated_at: str,
    asset_refs: Sequence[Mapping[str, Any]] = (),
    supersedes_ref: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply the first-slice rule table and return an immutable report."""

    if scope not in {"EVIDENCE", "FINAL_PACKAGE"}:
        raise EvidenceContractError(f"unsupported RequirementReport.scope: {scope!r}")
    _offset_datetime(evaluated_at, field="evaluated_at")
    copied_assets = [_copy_ref(ref, field="asset_ref") for ref in asset_refs]
    if scope == "FINAL_PACKAGE" and not copied_assets:
        raise EvidenceContractError("FINAL_PACKAGE evaluation requires asset_refs")

    record_ref = _typed_ref(
        evidence_record.get("record_ref"), field="record_ref", kind="evidence_record"
    )
    checks: list[dict[str, Any]] = []
    if "vehicle_number" in evidence_record:
        checks.append(
            {
                "code": "evidence.vehicle_number.present",
                "category": "VEHICLE",
                "outcome": "PASS",
                "reason_code": "vehicle_number.confirmed",
                "subject_refs": [deepcopy(record_ref)],
            }
        )
    else:
        checks.append(
            {
                "code": "evidence.vehicle_number.present",
                "category": "VEHICLE",
                "outcome": "BLOCK",
                "reason_code": "vehicle_number.unconfirmed",
                "summary": "번호판 판독이 abstain되어 아직 확정되지 않았습니다.",
                "subject_refs": [deepcopy(record_ref)],
            }
        )

    occurred_at = evidence_record.get("occurred_at")
    if isinstance(occurred_at, Mapping):
        time_ref = _copy_ref(occurred_at.get("time_resolution_ref"), field="occurred_at.time_resolution_ref")
        checks.append(
            {
                "code": "evidence.occurred_at.present",
                "category": "TIME",
                "outcome": "PASS",
                "reason_code": "occurred_at.resolved_ok",
                "subject_refs": [time_ref],
            }
        )
    else:
        checks.append(
            {
                "code": "evidence.occurred_at.present",
                "category": "TIME",
                "outcome": "UNKNOWN",
                "reason_code": "occurred_at.no_source_available",
                "subject_refs": [deepcopy(record_ref)],
            }
        )

    location = evidence_record.get("location")
    if isinstance(location, Mapping) and "coord" in location:
        checks.append(
            {
                "code": "evidence.location.confidence",
                "category": "LOCATION",
                "outcome": "PASS",
                "reason_code": "location.gps_confirmed",
                "subject_refs": [deepcopy(record_ref)],
            }
        )
    elif isinstance(location, Mapping) and "user_hint" in location:
        checks.append(
            {
                "code": "evidence.location.confidence",
                "category": "LOCATION",
                "outcome": "WARN",
                "reason_code": "location.user_hint_needs_review",
                "summary": "위치가 사용자 기억 단서이므로 최종 위치 확인이 필요합니다.",
                "subject_refs": [deepcopy(record_ref)],
            }
        )
    else:
        checks.append(
            {
                "code": "evidence.location.present",
                "category": "LOCATION",
                "outcome": "UNKNOWN",
                "reason_code": "location.no_source_available",
                "summary": "GPS가 없고 시각적 위치 단서도 확보되지 않았습니다.",
                "subject_refs": [deepcopy(record_ref)],
            }
        )

    codes = [check["code"] for check in checks]
    if len(codes) != len(set(codes)):
        raise EvidenceContractError("RequirementCheck.code values must be unique")
    report: dict[str, Any] = {
        "contract_version": "requirement-report/v1",
        "requirement_report_ref": _typed_ref(
            requirement_report_ref,
            field="requirement_report_ref",
            kind="requirement_report",
        ),
        "scope": scope,
        "basis": {"evidence_record_ref": record_ref, "asset_refs": copied_assets},
        "policy_ref": "requirement-policy/v1",
        "evaluated_at": evaluated_at,
        "overall": aggregate_requirement_outcomes([check["outcome"] for check in checks]),
        "checks": checks,
    }
    if supersedes_ref is not None:
        previous = _copy_ref(supersedes_ref, field="supersedes_ref")
        if previous == report["requirement_report_ref"]:
            raise EvidenceContractError("supersedes_ref must differ from requirement_report_ref")
        report["supersedes_ref"] = previous
    return report


def _location_snapshot(location: Mapping[str, Any]) -> tuple[dict[str, str], str]:
    explicit_search_keyword = location.get("search_keyword")
    confirmed_keyword = None
    if (
        isinstance(explicit_search_keyword, Mapping)
        and isinstance(explicit_search_keyword.get("value"), str)
        and explicit_search_keyword["value"].strip()
    ):
        confirmed_keyword = explicit_search_keyword["value"].strip()

    for key in ("place_name", "address", "user_hint", "search_keyword"):
        value = location.get(key)
        if isinstance(value, Mapping) and isinstance(value.get("value"), str) and value["value"].strip():
            display = value["value"].strip()
            snapshot = {"display_text": display}
            keyword = confirmed_keyword or display
            if confirmed_keyword is None and key == "user_hint":
                for suffix in (" 근처", " 인근", " 부근"):
                    if keyword.endswith(suffix):
                        keyword = keyword[: -len(suffix)].strip()
                        break
            if keyword:
                snapshot["search_keyword"] = keyword
            return snapshot, key
    raise EvidenceContractError("ReportPackage requires a displayable location")


def build_report_package(
    evidence_record: Mapping[str, Any],
    requirement_report: Mapping[str, Any],
    *,
    package_ref: Mapping[str, Any],
    created_at: str,
    report_video_ref: Mapping[str, Any],
    source_refs: Sequence[Mapping[str, Any]],
    plate_image_ref: Mapping[str, Any] | None = None,
    supersedes_ref: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Create a ready-only package, or return None when the gate is closed."""

    if requirement_report.get("scope") != "FINAL_PACKAGE" or requirement_report.get(
        "overall"
    ) not in {"PASS", "WARN"}:
        return None
    _offset_datetime(created_at, field="created_at")
    report_video = _typed_ref(
        report_video_ref, field="report_video_ref", kind="derived_asset"
    )
    record_ref = _typed_ref(
        evidence_record.get("record_ref"), field="record_ref", kind="evidence_record"
    )
    requirement_ref = _typed_ref(
        requirement_report.get("requirement_report_ref"),
        field="requirement_report_ref",
        kind="requirement_report",
    )
    requirement_basis = _mapping(requirement_report.get("basis"), field="requirement_report.basis")
    basis_record_ref = _typed_ref(
        requirement_basis.get("evidence_record_ref"),
        field="requirement_report.basis.evidence_record_ref",
        kind="evidence_record",
    )
    if basis_record_ref != record_ref:
        raise EvidenceContractError("RequirementReport basis does not match EvidenceRecord")
    requirement_assets = [
        _copy_ref(value, field="requirement_report.basis.asset_ref")
        for value in requirement_basis.get("asset_refs", [])
    ]
    if report_video not in requirement_assets:
        raise EvidenceContractError("report_video_ref is absent from RequirementReport basis")
    event = _mapping(evidence_record.get("event"), field="event")
    event_type = _mapping(event.get("visual_event_type"), field="event.visual_event_type").get(
        "value"
    )
    try:
        policy = EVENT_POLICIES[event_type]
    except KeyError as exc:
        raise EvidenceContractError(f"unsupported visual_event_type: {event_type!r}") from exc
    occurred_at = _mapping(evidence_record.get("occurred_at"), field="occurred_at").get("value")
    parsed_time = _offset_datetime(occurred_at, field="occurred_at.value")
    vehicle_number = _mapping(
        evidence_record.get("vehicle_number"), field="vehicle_number"
    ).get("value")
    if not isinstance(vehicle_number, str) or not vehicle_number.strip():
        raise EvidenceContractError("ReportPackage requires a confirmed vehicle number")
    location, location_source = _location_snapshot(
        _mapping(evidence_record.get("location"), field="location")
    )
    safety_report_type = _mapping(
        event.get("safety_report_type"), field="event.safety_report_type"
    ).get("value")
    violation_expression = _mapping(
        event.get("violation_expression"), field="event.violation_expression"
    ).get("value")

    assets: dict[str, Any] = {"report_video_ref": report_video}
    derived_refs = [deepcopy(report_video)]
    if plate_image_ref is not None:
        plate_ref = _typed_ref(
            plate_image_ref, field="plate_image_ref", kind="derived_asset"
        )
        assets["plate_image_ref"] = plate_ref
        derived_refs.append(deepcopy(plate_ref))
    if location_source == "user_hint":
        location_phrase = f"사용자가 '{location['display_text']}'로 기억한 지점"
    else:
        location_phrase = location["display_text"]
    package: dict[str, Any] = {
        "contract_version": "report-package/v1",
        "package_ref": _typed_ref(package_ref, field="package_ref", kind="report_package"),
        "evidence_record_ref": record_ref,
        "requirement_report_ref": requirement_ref,
        "created_at": created_at,
        "report_inputs": {
            "safety_report_type": safety_report_type,
            "occurred_at": occurred_at,
            "location": location,
            "vehicle_number": vehicle_number,
            "violation_expression": violation_expression,
        },
        "report": {
            "title": f"{policy.title} ({vehicle_number})",
            "description": (
                f"{parsed_time:%Y-%m-%d %H:%M}경 {location_phrase}에서 "
                f"차량({vehicle_number})이 {policy.description_clause}"
            ),
            "template_ref": policy.template_ref,
        },
        "assets": assets,
        "provenance": {
            "source_refs": [
                _typed_ref(ref, field="source_ref", kind="source_asset") for ref in source_refs
            ],
            "derived_asset_refs": derived_refs,
            "policy_ref": "report-package-policy/v1",
        },
        "handoff": {
            "destination": "SAFETY_REPORT",
            "supported_actions": ["DOWNLOAD_ASSETS", "COPY_FIELDS", "OPEN_DESTINATION"],
        },
    }
    if supersedes_ref is not None:
        previous = _copy_ref(supersedes_ref, field="supersedes_ref")
        if previous == package["package_ref"]:
            raise EvidenceContractError("supersedes_ref must differ from package_ref")
        package["supersedes_ref"] = previous
    return package


def assemble(request: Mapping[str, Any]) -> dict[str, Any]:
    """Run the first-integration Evidence pipeline from one JSON-compatible request."""

    req = deepcopy(_mapping(request, field="request"))
    refs = _mapping(req.get("refs"), field="refs")
    assets = _mapping(req.get("assets", {}), field="assets")
    case_ref = _typed_ref(req.get("case_ref"), field="case_ref", kind="case")
    candidate_ref = _typed_ref(
        req.get("candidate_ref"), field="candidate_ref", kind="candidate_event"
    )
    visual = _mapping(req.get("visual_evidence"), field="visual_evidence")
    if visual.get("candidate_id") != candidate_ref["ref"]:
        raise EvidenceContractError("VisualEvidence.candidate_id does not match candidate_ref")
    for field in ("plate_readout", "overlay_time_readout"):
        upstream = req.get(field)
        if upstream is None:
            continue
        upstream = _mapping(upstream, field=field)
        if upstream.get("case_id") != case_ref["ref"]:
            raise EvidenceContractError(f"{field}.case_id does not match case_ref")
        if upstream.get("candidate_id") != candidate_ref["ref"]:
            raise EvidenceContractError(f"{field}.candidate_id does not match candidate_ref")
    time_resolution = resolve_time(
        req.get("overlay_time_readout"),
        req.get("time_source_candidates", []),
        resolution_ref=_mapping(refs.get("resolution_ref"), field="refs.resolution_ref"),
    )
    evidence_record = build_evidence_record(
        visual,
        req.get("plate_readout"),
        req.get("observations", []),
        time_resolution,
        record_ref=_mapping(refs.get("record_ref"), field="refs.record_ref"),
        case_ref=case_ref,
        selection_rev=req.get("selection_rev"),
        candidate_ref=candidate_ref,
        evidence_interval_ref=_mapping(
            req.get("evidence_interval_ref"), field="evidence_interval_ref"
        ),
        location_hint=req.get("location_hint"),
    )
    evidence_needs = build_evidence_needs(evidence_record)
    requirement_report = evaluate_requirements(
        evidence_record,
        requirement_report_ref=_mapping(
            refs.get("requirement_report_ref"), field="refs.requirement_report_ref"
        ),
        scope=req.get("requirement_scope"),
        evaluated_at=req.get("evaluated_at"),
        asset_refs=assets.get("requirement_asset_refs", []),
    )
    report_package = None
    if refs.get("package_ref") is not None and assets.get("report_video_ref") is not None:
        report_package = build_report_package(
            evidence_record,
            requirement_report,
            package_ref=_mapping(refs.get("package_ref"), field="refs.package_ref"),
            created_at=req.get("package_created_at"),
            report_video_ref=_mapping(
                assets.get("report_video_ref"), field="assets.report_video_ref"
            ),
            plate_image_ref=assets.get("plate_image_ref"),
            source_refs=assets.get("source_refs", []),
        )
    return {
        "time_resolution": time_resolution,
        "evidence_record": evidence_record,
        "evidence_needs": evidence_needs,
        "requirement_report": requirement_report,
        "report_package": report_package,
    }
