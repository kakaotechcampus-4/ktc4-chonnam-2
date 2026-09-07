#!/usr/bin/env python3
"""Validate the first evidence implementation against shared canonical fixtures.

This module-owned check is intentionally separate from validate_mock_pack.py so
the team-wide fixture validator stays independent from one module's runtime.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from daesingo.common import validate_execution_usage_links  # noqa: E402
from daesingo.evidence import assemble  # noqa: E402
from evidence_fixture_support import (  # noqa: E402
    expected_evidence_outputs,
    json_shape,
    load_evidence_request,
    load_json,
)


def main() -> int:
    errors: list[str] = []
    checked_scenarios = ("happy_001", "partial_001")

    for tag in checked_scenarios:
        generated = assemble(load_evidence_request(tag))
        expected = expected_evidence_outputs(tag)

        if generated.keys() != expected.keys():
            errors.append(f"[{tag}] output key set differs from canonical fixture")

        for name, value in generated.items():
            if name not in expected or json_shape(value) != json_shape(expected[name]):
                errors.append(f"[{tag}] {name} JSON shape differs from canonical fixture")

        for name in (
            "time_resolution",
            "evidence_record",
            "evidence_needs",
            "requirement_report",
        ):
            if generated.get(name) != expected.get(name):
                errors.append(f"[{tag}] {name} value differs from canonical fixture")

        executions = load_json(ROOT / "data" / "mock" / "case" / f"job_executions.{tag}.json")
        usage_records = load_json(ROOT / "data" / "mock" / "case" / f"usage_records.{tag}.json")
        try:
            validate_execution_usage_links(executions, usage_records)
        except (TypeError, ValueError) as exc:
            errors.append(f"[{tag}] JobExecution/UsageRecord link validation failed: {exc}")

        package = generated["report_package"]
        if tag == "happy_001":
            if package is None:
                errors.append("[happy_001] WARN requirement did not produce ReportPackage")
            else:
                report_text = json.dumps(package["report"], ensure_ascii=False)
                if "흰색 SUV" in report_text:
                    errors.append(
                        "[happy_001] report used a vehicle description absent from confirmed Evidence"
                    )
                if "사용자가" not in package["report"]["description"]:
                    errors.append(
                        "[happy_001] user_hint provenance is not disclosed in report description"
                    )
        elif package is not None:
            errors.append("[partial_001] BLOCK requirement produced ReportPackage")

    print(f"검사한 evidence 시나리오 수: {len(checked_scenarios)}")
    print(f"오류(ERROR): {len(errors)}")
    for error in errors:
        print("  -", error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
