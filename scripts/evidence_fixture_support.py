"""Shared loader for the versioned first-integration evidence fixtures."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MOCK_ROOT = ROOT / "data" / "mock"
REQUEST_ROOT = ROOT / "tests" / "fixtures"


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_evidence_request(tag: str) -> dict[str, Any]:
    request_path = REQUEST_ROOT / f"evidence_request.{tag}.json"
    request = deepcopy(load_json(request_path))
    fixture_paths = request.pop("fixture_paths")
    for field, relative_path in fixture_paths.items():
        request[field] = load_json(MOCK_ROOT / relative_path)
    return request


def expected_evidence_outputs(tag: str) -> dict[str, Any]:
    names = {
        "time_resolution": f"time_resolution.{tag}.json",
        "evidence_record": f"evidence_record.{tag}.json",
        "evidence_needs": f"evidence_needs.{tag}.json",
        "requirement_report": f"requirement_report.{tag}.json",
        "report_package": f"report_package.{tag}.json",
    }
    outputs: dict[str, Any] = {}
    for key, filename in names.items():
        path = MOCK_ROOT / "evidence" / filename
        outputs[key] = load_json(path) if path.exists() else None
    return outputs


def json_shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_shape(child) for key, child in value.items()}
    if isinstance(value, list):
        return [json_shape(child) for child in value]
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "string"
