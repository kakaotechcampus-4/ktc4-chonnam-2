"""Validate and select CorrectionRecord values consumed by evidence."""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from typing import Any

from ._contract import Contract, parse_rfc3339, require
from .policy import EVENT_POLICY, REPORT_TYPE_LABELS

_LOCATION_FIELDS = {
    "location.address",
    "location.place_name",
    "location.search_keyword",
    "location.user_hint",
}
EVIDENCE_TARGET_FIELDS = {
    "event.visual_event_type",
    "event.safety_report_type",
    "event.violation_expression",
    "occurred_at",
    "vehicle_number",
    "location.coord",
    *_LOCATION_FIELDS,
}
_KINDS = {
    "TIME_HINT_EDIT",
    "OTHER_CANDIDATE",
    "PLATE_MANUAL_EDIT",
    "PLATE_REREAD",
    "SPAN_ADJUST",
    "REPORT_TYPE_CHANGE",
    "EVENT_TIME_MANUAL",
    "TIMELINE_REBASE",
    "SITUATION_CHANGE",
}


def _valid_value(target: str, value: Any) -> bool:
    if target == "event.visual_event_type":
        return value is None or value in EVENT_POLICY
    if target == "event.safety_report_type":
        return value is None or value in REPORT_TYPE_LABELS
    if target == "event.violation_expression":
        return value is None or isinstance(value, str) and 5 <= len(value) <= 900
    if target == "occurred_at":
        parse_rfc3339(value)
        return True
    if target == "vehicle_number":
        return isinstance(value, str)
    if target == "location.coord":
        return (
            isinstance(value, dict)
            and isinstance(value.get("lat"), (int, float))
            and not isinstance(value.get("lat"), bool)
            and isinstance(value.get("lon"), (int, float))
            and not isinstance(value.get("lon"), bool)
        )
    if target in _LOCATION_FIELDS:
        return value is None or isinstance(value, str)
    return False


def correction_heads(
    records: Iterable[Contract], *, case_id: str, selection_rev: int
) -> dict[str, Contract]:
    """Return one supersede-chain head for each evidence semantic path."""
    relevant: list[Contract] = []
    ids: set[str] = set()
    for raw in records:
        record = deepcopy(raw)
        correction_id = record.get("correction_id")
        require(isinstance(correction_id, str) and bool(correction_id), "correction_id is required")
        require(correction_id not in ids, "correction_id must be unique")
        ids.add(correction_id)
        if record.get("case_id") != case_id:
            continue
        target = record.get("target_field")
        if target not in EVIDENCE_TARGET_FIELDS:
            continue
        require(record.get("kind") in _KINDS, "invalid correction kind")
        require(
            isinstance(record.get("selection_rev"), int)
            and not isinstance(record["selection_rev"], bool)
            and record["selection_rev"] >= 1,
            "invalid correction selection_rev",
        )
        require(_valid_value(target, record.get("previous_value")), f"invalid previous_value for {target}")
        require(_valid_value(target, record.get("new_value")), f"invalid new_value for {target}")
        require(
            record.get("kind") != "SITUATION_CHANGE" or target.startswith("event."),
            "SITUATION_CHANGE must target an event field",
        )
        require(record.get("previous_value") != record.get("new_value"), "a correction must change the value")
        parse_rfc3339(record.get("corrected_at"))
        supersedes = record.get("supersedes_ref")
        require(
            supersedes is None
            or supersedes.get("kind") == "correction_record"
            and isinstance(supersedes.get("ref"), str),
            "invalid correction supersedes_ref",
        )
        relevant.append(record)

    by_id = {item["correction_id"]: item for item in relevant}
    for record in relevant:
        prior_ref = record.get("supersedes_ref")
        if prior_ref is None:
            continue
        prior = by_id.get(prior_ref["ref"])
        require(prior is not None, "correction supersedes_ref must resolve in the supplied chain")
        require(prior["target_field"] == record["target_field"], "correction chain cannot change target_field")
        require(prior["new_value"] == record["previous_value"], "correction chain values are discontinuous")

    superseded_in_context = {
        item["supersedes_ref"]["ref"]
        for item in relevant
        if item["selection_rev"] == selection_rev and item.get("supersedes_ref") is not None
    }
    heads: dict[str, Contract] = {}
    for record in relevant:
        if record["selection_rev"] != selection_rev:
            continue
        if record["correction_id"] in superseded_in_context:
            continue
        target = record["target_field"]
        require(target not in heads, f"multiple correction heads for {target}")
        heads[target] = record
    return heads
