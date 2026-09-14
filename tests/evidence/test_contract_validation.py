from __future__ import annotations

import json
from pathlib import Path
import unittest

from daesingo.evidence import validate_contract
from daesingo.evidence.mock_integration import run_scenario


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


if __name__ == "__main__":
    unittest.main()
