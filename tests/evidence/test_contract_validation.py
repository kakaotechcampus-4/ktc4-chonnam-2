from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from daesingo.evidence import validate_contract
from daesingo.evidence.mock_integration import run_scenario
from daesingo.evidence.validation import validate_report_package


ROOT = Path(__file__).resolve().parents[2]
CONFIGS = json.loads((ROOT / "tests/evidence/fixtures/adapter_inputs.json").read_text(encoding="utf-8"))["scenarios"]


class ContractValidationTests(unittest.TestCase):
    def test_every_generated_contract_passes_boundary_validation(self):
        for scenario_id, config in CONFIGS.items():
            outputs = run_scenario(ROOT, scenario_id, config)["outputs"]
            for values in outputs.values():
                for value in values:
                    self.assertEqual([], validate_contract(value), (scenario_id, value))

    def test_validator_rejects_unknown_time_with_resolved(self):
        value = {
            "contract_version": "time-resolution/v1",
            "resolution_ref": {"kind": "time_resolution", "ref": "bad"},
            "status": "UNKNOWN",
            "resolved": {"value": "2026-09-13T10:00:00+09:00"},
            "conflict": {"exists": False, "between_refs": [], "requires_user_notice": False},
            "post_stamp": {"needed": False, "reason_code": "none", "requires_user_notice": False},
            "considered": [],
            "provenance": {"policy_ref": "policy/time-source-priority-v1"},
        }
        self.assertTrue(validate_contract(value))

    def test_evidence_value_types_reject_null_empty_and_boolean_coordinates(self):
        outputs = run_scenario(
            ROOT, "scenario_happy_001", CONFIGS["scenario_happy_001"]
        )["outputs"]
        record = outputs["evidence_records"][0]

        null_plate = deepcopy(record)
        null_plate["vehicle_number"]["value"] = None
        self.assertIn("vehicle_number:value", validate_contract(null_plate))

        empty_report_type = deepcopy(record)
        empty_report_type["event"]["safety_report_type"]["value"] = "  "
        self.assertIn(
            "event.safety_report_type:value", validate_contract(empty_report_type)
        )

        for invalid_latitude in (True, float("inf")):
            invalid_coordinate = deepcopy(record)
            invalid_coordinate["location"]["coord"]["value"]["lat"] = invalid_latitude
            self.assertIn(
                "location.coord:value", validate_contract(invalid_coordinate)
            )

    def test_requirement_report_validator_rejects_incomplete_basis_and_checks(self):
        outputs = run_scenario(
            ROOT, "scenario_happy_001", CONFIGS["scenario_happy_001"]
        )["outputs"]
        report = next(
            item for item in outputs["requirement_reports"]
            if item["scope"] == "FINAL_PACKAGE"
        )
        malformed = deepcopy(report)
        malformed["basis"].pop("asset_refs")
        malformed["policy_ref"] = ""
        malformed["checks"][0].pop("category")
        malformed["checks"][0].pop("reason_code")
        malformed["checks"][0].pop("subject_refs")

        errors = validate_contract(malformed)
        self.assertIn("basis.asset_refs", errors)
        self.assertIn("policy_ref", errors)
        self.assertIn("checks[0].category", errors)
        self.assertIn("checks[0].reason_code", errors)
        self.assertIn("checks[0].subject_refs", errors)

    def test_report_package_v1_1_requires_nullable_location_key(self):
        fixture = json.loads(
            (ROOT / "data/mock/evidence/scenario_unknown_abstain_partial_001.json").read_text(
                encoding="utf-8"
            )
        )
        package = next(
            item for item in fixture["report_packages"]
            if item["package_ref"]["ref"] == "pkg_u001"
        )
        package["contract_version"] = "report-package/v1.1"

        self.assertEqual([], validate_report_package(package))

        missing = json.loads(json.dumps(package))
        missing["report_inputs"].pop("location")
        self.assertIn("location", validate_report_package(missing))

        empty = json.loads(json.dumps(package))
        empty["report_inputs"]["location"] = {}
        self.assertIn("location", validate_report_package(empty))

        legacy = json.loads(json.dumps(package))
        legacy["contract_version"] = "report-package/v1"
        self.assertIn("location", validate_contract(legacy))


if __name__ == "__main__":
    unittest.main()
