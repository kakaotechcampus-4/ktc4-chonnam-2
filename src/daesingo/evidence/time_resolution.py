"""Pure TimeResolution policy."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta

from ._contract import Contract, contract_ref, parse_rfc3339, require
from .corrections import correction_heads
from .policy import TIME_POLICY_REF

_SOURCE_KIND = {
    "FILENAME": "recording.filename_time",
    "FILE_METADATA": "recording.file_metadata_time",
    "MANUFACTURER_METADATA": "recording.manufacturer_metadata_time",
}


def _candidate_summary(candidate: Contract, *, used: bool, reason_code: str | None = None) -> Contract:
    source_kind = candidate.get("source_kind")
    require(source_kind in _SOURCE_KIND, f"unsupported TimeSourceCandidate.source_kind: {source_kind!r}")
    item: Contract = {
        "input_kind": "OBSERVATION",
        "input_ref": contract_ref("time_source_candidate", candidate["candidate_id"]),
        "source": {"kind": _SOURCE_KIND[source_kind]},
        "value": candidate.get("value"),
        "observation_status": candidate.get("observation_status"),
        "verification": "UNVERIFIED",
        "used": used,
    }
    if reason_code:
        item["reason_code"] = reason_code
    return item


def _valid_overlay(overlay: Contract | None) -> bool:
    if not overlay:
        return False
    observation = overlay.get("observation") or {}
    validation = overlay.get("validation") or {}
    return (
        observation.get("status") == "OK"
        and isinstance(observation.get("value"), str)
        and all(validation.get(key) is True for key in ("format_ok", "monotonic_ok", "duration_match_ok"))
    )


def _correction_head(
    records: Iterable[Contract], *, case_id: str, selection_rev: int
) -> Contract | None:
    return correction_heads(records, case_id=case_id, selection_rev=selection_rev).get("occurred_at")


def _event_source_position(incident_clip: Contract, candidate_event: Contract) -> tuple[str, int] | None:
    """Source asset holding the representative moment and the moment's position inside it (ms).

    `representative_ms` is a timeline position; a time source value belongs to one source asset. The clip's
    AssetSpans map one to the other. A span owns `[start, end)`, the last span also owns its end. `None` when the
    moment falls outside every span (a timeline gap)."""
    span = candidate_event.get("span") or {}
    provenance = incident_clip.get("source_provenance") or {}
    timeline = provenance.get("timeline_ref") or {}
    require(span.get("timeline_id") == timeline.get("timeline_id"), "CandidateEvent and IncidentClip timeline_id mismatch")
    require(
        span.get("timeline_revision") == timeline.get("revision"),
        "CandidateEvent and IncidentClip timeline revision mismatch",
    )
    asset_spans = sorted(provenance.get("asset_spans") or [], key=lambda item: item["sequence"])
    require(bool(asset_spans), "IncidentClip asset_spans is required")
    representative_ms = span["representative_ms"]
    for index, item in enumerate(asset_spans):
        start_ms = round(item["timeline_range"]["start_sec"] * 1000)
        end_ms = round(item["timeline_range"]["end_sec"] * 1000)
        if start_ms <= representative_ms < end_ms or (index == len(asset_spans) - 1 and representative_ms == end_ms):
            return item["source_asset_ref"], representative_ms - start_ms + round(item["source_range"]["start_sec"] * 1000)
    return None


def resolve_time(
    *,
    time_source_candidates: Iterable[Contract],
    overlay_time_readout: Contract | None,
    candidate_event: Contract,
    correction_records: Iterable[Contract] = (),
    case_id: str,
    selection_rev: int,
    resolution_id: str,
    supersedes_id: str | None = None,
    incident_clip: Contract | None = None,
) -> Contract:
    """Resolve existing contract values without calling an upstream module.

    With `incident_clip`, a base-plus-offset time uses only the time sources of the source asset that holds the
    representative moment, offset from inside that asset. Without it the timeline position is added to the base
    as is, which is right only when the timeline is a single source starting at 0."""
    candidates = [dict(item) for item in time_source_candidates]
    for item in candidates:
        require(item.get("observation_status") in {"OK", "UNKNOWN", "ERROR"}, "invalid time observation status")
        if item.get("value") is not None:
            parse_rfc3339(item["value"])
    span = candidate_event.get("span") or {}
    representative_ms = span.get("representative_ms")
    require(isinstance(representative_ms, int) and representative_ms >= 0, "CandidateEvent representative_ms is required")

    correction = _correction_head(correction_records, case_id=case_id, selection_rev=selection_rev)
    result: Contract = {
        "contract_version": "time-resolution/v1",
        "resolution_ref": contract_ref("time_resolution", resolution_id),
    }
    if supersedes_id:
        result["supersedes_ref"] = contract_ref("time_resolution", supersedes_id)

    considered: list[Contract] = []
    selected_ref: Contract | None = None

    if correction is not None:
        selected_ref = contract_ref("correction_record", correction["correction_id"])
        considered.append(
            {
                "input_kind": "USER_INPUT",
                "input_ref": selected_ref,
                "source": {"kind": "case.user_correction"},
                "value": correction["new_value"],
                "verification": "AGREED",
                "used": True,
            }
        )
        for item in candidates:
            summary = _candidate_summary(item, used=False, reason_code="time.superseded_by_user_correction")
            considered.append(summary)
        result.update(
            {
                "status": "OK",
                "resolved": {
                    "value": correction["new_value"],
                    "source": {"kind": "case.user_correction", "input_ref": selected_ref},
                    "verification": "AGREED",
                    "computation": {
                        "mode": "USER_OVERRIDE",
                        "timezone": {
                            "zone_id": "Asia/Seoul",
                            "utc_offset": "+09:00",
                            "source": "PRODUCT_CONTEXT",
                        },
                    },
                    "user_corrected": True,
                },
                "conflict": {"exists": False, "between_refs": [], "requires_user_notice": False},
                "post_stamp": {
                    "needed": True,
                    "reason_code": "time.user_confirmed_no_overlay_present",
                    "requires_user_notice": True,
                },
            }
        )
    elif _valid_overlay(overlay_time_readout):
        assert overlay_time_readout is not None
        readout_id = overlay_time_readout.get("readout_id")
        require(isinstance(readout_id, str) and readout_id, "OverlayTimeReadout.readout_id is required")
        selected_ref = contract_ref("overlay_time_readout", readout_id)
        value = overlay_time_readout["observation"]["value"]
        parse_rfc3339(value)
        considered.append(
            {
                "input_kind": "OBSERVATION",
                "input_ref": selected_ref,
                "source": {"kind": "readout.overlay_ocr"},
                "value": value,
                "observation_status": "OK",
                "verification": "VERIFIED",
                "used": True,
            }
        )
        for item in candidates:
            considered.append(_candidate_summary(item, used=False, reason_code="time.superseded_by_verified_overlay"))
        result.update(
            {
                "status": "OK",
                "resolved": {
                    "value": value,
                    "source": {"kind": "readout.overlay_ocr", "input_ref": selected_ref},
                    "verification": "VERIFIED",
                    "computation": {
                        "mode": "DIRECT",
                        "timezone": {
                            "zone_id": "Asia/Seoul",
                            "utc_offset": "+09:00",
                            "source": "PRODUCT_CONTEXT",
                        },
                    },
                    "user_corrected": False,
                },
                "conflict": {"exists": False, "between_refs": [], "requires_user_notice": False},
                "post_stamp": {
                    "needed": False,
                    "reason_code": "time.verified_overlay_already_present",
                    "requires_user_notice": False,
                },
            }
        )
    else:
        if overlay_time_readout:
            observation = overlay_time_readout.get("observation") or {}
            considered.append(
                {
                    "input_kind": "OBSERVATION",
                    "input_ref": contract_ref("overlay_time_readout", overlay_time_readout["readout_id"]),
                    "source": {"kind": "readout.overlay_ocr"},
                    "value": observation.get("value"),
                    "observation_status": observation.get("status"),
                    "verification": "UNVERIFIED",
                    "used": False,
                    "reason_code": "time.overlay_not_verified",
                }
            )
        # A time source value is the clock of one source asset; it may only meet a position inside that asset.
        position = None if incident_clip is None else _event_source_position(incident_clip, candidate_event)
        if incident_clip is None:
            eligible = candidates
        else:
            event_asset = position[0] if position else None
            eligible = [c for c in candidates if (c.get("applies_to") or {}).get("source_asset_ref") == event_asset]
        eligible_ids = {c["candidate_id"] for c in eligible}
        valid_candidates = [c for c in eligible if c.get("observation_status") == "OK" and c.get("value")]
        filename = next((c for c in valid_candidates if c.get("source_kind") == "FILENAME"), None)
        selected = filename or (valid_candidates[0] if valid_candidates else None)
        if selected is None:
            considered.extend(
                _candidate_summary(
                    item,
                    used=False,
                    reason_code="time.no_usable_value" if item["candidate_id"] in eligible_ids else "time.other_source_asset",
                )
                for item in candidates
            )
            result.update(
                {
                    "status": "UNKNOWN",
                    "conflict": {"exists": False, "between_refs": [], "requires_user_notice": False},
                    "post_stamp": {
                        "needed": False,
                        "reason_code": "time.no_resolvable_source",
                        "requires_user_notice": True,
                    },
                }
            )
        else:
            selected_ref = contract_ref("time_source_candidate", selected["candidate_id"])
            distinct_values = {c["value"] for c in valid_candidates}
            conflict = len(distinct_values) > 1
            for item in candidates:
                is_selected = item["candidate_id"] == selected["candidate_id"]
                reason = None
                if item["candidate_id"] not in eligible_ids:
                    reason = "time.other_source_asset"
                elif not is_selected:
                    reason = "time.conflicting_metadata_candidate" if conflict else "time.not_selected"
                considered.append(_candidate_summary(item, used=is_selected, reason_code=reason))
            base = parse_rfc3339(selected["value"])
            if position is None:
                source_offset_ms = representative_ms
            else:
                # The value may describe a point other than the asset start (`applies_to.source_offset_sec`).
                applies_at_ms = round(selected["applies_to"].get("source_offset_sec", 0) * 1000)
                source_offset_ms = position[1] - applies_at_ms
            resolved_value = (base + timedelta(milliseconds=source_offset_ms)).isoformat()
            result.update(
                {
                    "status": "NEEDS_REVIEW",
                    "resolved": {
                        "value": resolved_value,
                        "source": {"kind": _SOURCE_KIND[selected["source_kind"]], "input_ref": selected_ref},
                        "verification": "UNVERIFIED",
                        "computation": {
                            "mode": "BASE_PLUS_OFFSET",
                            "base_input_ref": selected_ref,
                            "source_offset_ms": source_offset_ms,
                            "timezone": {
                                "zone_id": "Asia/Seoul",
                                "utc_offset": "+09:00",
                                "source": "PRODUCT_CONTEXT",
                            },
                        },
                        "user_corrected": False,
                    },
                    "conflict": {
                        "exists": conflict,
                        "between_refs": [
                            contract_ref("time_source_candidate", c["candidate_id"]) for c in valid_candidates
                        ]
                        if conflict
                        else [],
                        "requires_user_notice": conflict,
                    },
                    "post_stamp": {
                        "needed": True,
                        "reason_code": "time.no_verified_overlay_present",
                        "requires_user_notice": True,
                    },
                }
            )

    result["considered"] = considered
    result["provenance"] = {"policy_ref": TIME_POLICY_REF}
    if selected_ref is not None:
        result["provenance"]["selected_input_ref"] = selected_ref
    return result
