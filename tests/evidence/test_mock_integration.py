from __future__ import annotations

import json
from pathlib import Path
import unittest

from daesingo.evidence.mock_integration import run_scenario


ROOT = Path(__file__).resolve().parents[2]
CONFIGS = json.loads((ROOT / "tests/evidence/fixtures/adapter_inputs.json").read_text(encoding="utf-8"))["scenarios"]


class SharedScenarioIntegrationTests(unittest.TestCase):
    def run_case(self, scenario_id: str):
        return run_scenario(ROOT, scenario_id, CONFIGS[scenario_id])

    def test_happy_connects_refs_and_exposes_missing_event_observations(self):
        result = self.run_case("scenario_happy_001")
        outputs = result["outputs"]
        record = outputs["evidence_records"][0]
        self.assertEqual(["OK"], [item["status"] for item in outputs["time_resolutions"]])
        self.assertEqual([], outputs["evidence_needs"][0]["items"])
        self.assertEqual(["PASS", "UNKNOWN"], [item["overall"] for item in outputs["requirement_reports"]])
        self.assertEqual([], outputs["report_packages"])
        final = outputs["requirement_reports"][1]
        unknown_codes = {item["code"] for item in final["checks"] if item["outcome"] == "UNKNOWN"}
        self.assertEqual({
            "package.event.violation_visible_in_report_video",
            "package.event.pre_context_present",
            "package.event.post_context_present",
        }, unknown_codes)
        self.assertEqual("CONFIRMED", record["situation_response"]["value"])
        guard = result["policy_guard_check"]
        self.assertEqual("NOT_ASKED", guard["shared_case_situation_confirmation"])
        self.assertEqual("report.input.situation_unconfirmed", guard["without_confirmation"]["render_error"])
        self.assertFalse(guard["without_confirmation"]["normal_final_report_emitted"])
        self.assertFalse(guard["without_confirmation"]["report_package_emitted"])
        self.assertEqual("EVIDENCE_TEST_DERIVED", result["execution_mode"]["case_context"])
        self.assertFalse(result["consumer_mock"]["package_ready"])
        self.assertEqual("CASE_OWNED_NOT_DERIVED", result["consumer_mock"]["user_reviewed"])

    def test_unknown_preserves_uncertainty_and_withholds_invalid_package(self):
        result = self.run_case("scenario_unknown_abstain_partial_001")
        record = result["outputs"]["evidence_records"][0]
        time = result["outputs"]["time_resolutions"][0]
        self.assertEqual("UNCERTAIN", self._shared_visual_verification(result))
        self.assertIsNone(record["event"]["visual_event_type"]["value"])
        self.assertEqual("USER_UNSURE", record["situation_response"]["value"])
        self.assertEqual("NEEDS_REVIEW", time["status"])
        self.assertTrue(time["conflict"]["exists"])
        self.assertEqual(["WARN", "UNKNOWN"], [item["overall"] for item in result["outputs"]["requirement_reports"]])
        self.assertEqual([], result["outputs"]["report_packages"])
        self.assertEqual("package.requirement_not_ready", result["package_boundary_error"])
        final = result["outputs"]["requirement_reports"][1]
        checks = {item["code"]: item for item in final["checks"]}
        self.assertEqual("WARN", checks["package.location.present"]["outcome"])
        self.assertEqual("PASS", checks["package.report.content_length"]["outcome"])

    def _shared_visual_verification(self, result):
        search = json.loads((ROOT / result["source_paths"]["search"]).read_text(encoding="utf-8"))
        candidate_id = result["input_trace"]["candidate_id"]
        return next(item["verification"] for item in search["visual_evidences"] if item["candidate_id"] == candidate_id)

    def test_plate_reread_keeps_other_evidence_and_replaces_only_snapshot(self):
        result = self.run_case("scenario_plate_reread_001")
        first, second = result["outputs"]["evidence_records"]
        first_need, second_need = result["outputs"]["evidence_needs"]
        self.assertNotIn("vehicle_number", first)
        self.assertEqual("17나2867", second["vehicle_number"]["value"])
        self.assertEqual("PLATE_REREAD", first_need["items"][0]["kind"])
        self.assertEqual("VEHICLE_NUMBER", first_need["items"][0]["would_fill"])
        self.assertFalse(first_need["items"][0]["optional"])
        self.assertEqual([], second_need["items"])
        self.assertEqual(first["event"], second["event"])
        self.assertEqual(first["occurred_at"], second["occurred_at"])
        self.assertEqual(1, second["selection_rev"])
        self.assertEqual(first["record_ref"], second["supersedes_ref"])
        self.assertEqual(["UNKNOWN", "WARN"], [item["overall"] for item in result["outputs"]["requirement_reports"]])

    def test_manual_time_correction_is_one_way_and_preserves_plate(self):
        result = self.run_case("scenario_correction_rerun_001")
        old_time, new_time = result["outputs"]["time_resolutions"]
        old_record, new_record = result["outputs"]["evidence_records"]
        self.assertEqual(("NEEDS_REVIEW", "OK"), (old_time["status"], new_time["status"]))
        self.assertEqual("USER_OVERRIDE", new_time["resolved"]["computation"]["mode"])
        self.assertEqual("AGREED", new_time["resolved"]["verification"])
        self.assertTrue(new_time["resolved"]["user_corrected"])
        self.assertEqual({"kind": "correction_record", "ref": "cr_r001_time"}, new_time["provenance"]["selected_input_ref"])
        self.assertEqual("2026-08-27T13:13:00+09:00", new_record["occurred_at"]["value"])
        self.assertEqual(old_record["vehicle_number"], new_record["vehicle_number"])
        self.assertEqual(old_record["basis"], new_record["basis"])
        self.assertEqual(1, new_record["selection_rev"])
        self.assertEqual(old_time["resolution_ref"], new_time["supersedes_ref"])
        self.assertEqual(old_record["record_ref"], new_record["supersedes_ref"])
        self.assertEqual(["WARN", "WARN"], [item["overall"] for item in result["outputs"]["requirement_reports"]])

    def test_adapter_does_not_mutate_shared_sources(self):
        paths = [ROOT / "data/mock" / module / "scenario_correction_rerun_001.json" for module in ("recording", "search", "readout", "case", "evidence")]
        before = {path: path.read_bytes() for path in paths}
        self.run_case("scenario_correction_rerun_001")
        self.assertEqual(before, {path: path.read_bytes() for path in paths})


if __name__ == "__main__":
    unittest.main()
