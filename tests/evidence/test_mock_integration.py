from __future__ import annotations

import json
import unittest
from pathlib import Path

from daesingo.evidence.mock_integration import (
    _require_reason_per_mismatch,
    run_scenario,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = json.loads((ROOT / "tests/evidence/fixtures/adapter_inputs.json").read_text(encoding="utf-8"))["scenarios"]


class SharedScenarioIntegrationTests(unittest.TestCase):
    def run_case(self, scenario_id: str):
        return run_scenario(ROOT, scenario_id, CONFIGS[scenario_id])

    def test_happy_connects_refs_and_emits_ready_package(self):
        result = self.run_case("scenario_happy_001")
        outputs = result["outputs"]
        record = outputs["evidence_records"][0]
        self.assertEqual(["OK"], [item["status"] for item in outputs["time_resolutions"]])
        self.assertEqual([], outputs["evidence_needs"][0]["items"])
        self.assertEqual(["PASS", "PASS"], [item["overall"] for item in outputs["requirement_reports"]])
        self.assertEqual(["pkg_h001"], [item["package_ref"]["ref"] for item in outputs["report_packages"]])
        final = outputs["requirement_reports"][1]
        unknown_codes = {item["code"] for item in final["checks"] if item["outcome"] == "UNKNOWN"}
        self.assertEqual(set(), unknown_codes)
        self.assertEqual("CONFIRMED", record["situation_response"]["value"])
        guard = result["policy_guard_check"]
        self.assertEqual("NOT_ASKED", guard["shared_case_situation_confirmation"])
        self.assertEqual("report.input.situation_unconfirmed", guard["without_confirmation"]["render_error"])
        self.assertFalse(guard["without_confirmation"]["normal_final_report_emitted"])
        self.assertFalse(guard["without_confirmation"]["report_package_emitted"])
        self.assertEqual("EVIDENCE_TEST_DERIVED", result["execution_mode"]["case_context"])
        self.assertTrue(result["consumer_mock"]["package_ready"])
        self.assertEqual("CASE_OWNED_NOT_DERIVED", result["consumer_mock"]["user_reviewed"])

    def test_unknown_preserves_uncertainty_and_emits_warn_package(self):
        result = self.run_case("scenario_unknown_abstain_partial_001")
        record = result["outputs"]["evidence_records"][0]
        time = result["outputs"]["time_resolutions"][0]
        self.assertEqual("UNCERTAIN", self._shared_visual_verification(result))
        self.assertIsNone(record["event"]["visual_event_type"]["value"])
        self.assertEqual("USER_UNSURE", record["situation_response"]["value"])
        self.assertEqual("NEEDS_REVIEW", time["status"])
        self.assertTrue(time["conflict"]["exists"])
        self.assertEqual(["WARN", "WARN"], [item["overall"] for item in result["outputs"]["requirement_reports"]])
        self.assertEqual(["pkg_u001"], [
            item["package_ref"]["ref"] for item in result["outputs"]["report_packages"]])
        self.assertIsNone(result["package_boundary_error"])
        self.assertTrue(result["consumer_mock"]["package_ready"])
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

    def test_every_recorded_mismatch_carries_a_reason(self):
        """`comparison`이 불일치를 기록하면 그 축을 설명하는 항목이 반드시 있어야 한다.

        불일치 사실만 남고 사유가 비어 있으면 「무엇으로 검증했는지 공개한다」를
        만족하지 못한다 — 읽는 쪽이 차이를 의도된 것으로 볼지 결함으로 볼지
        판단할 근거가 없다.
        """
        for scenario_id in CONFIGS:
            with self.subTest(scenario=scenario_id):
                comparison = self.run_case(scenario_id)["comparison"]
                differences = comparison["known_differences"]
                mismatched = [
                    dimension
                    for dimension, matched in (
                        ("time_statuses", comparison["time_statuses_match"]),
                        ("requirement_overalls", comparison["requirement_overalls_match"]),
                        ("package_count", comparison["common_package_count"] == comparison["baseline_package_count"]),
                    )
                    if not matched
                ]
                for dimension in mismatched:
                    self.assertTrue(
                        any(item.startswith(f"{dimension}: ") for item in differences),
                        f"{scenario_id}: '{dimension}' 불일치를 기록했으나 설명이 없다 — {differences}",
                    )

    def test_uncovered_mismatch_is_rejected(self):
        """새 비교 축이 늘어도 사유 없는 불일치가 통과하지 못하게 막는다.

        `_derived_differences`가 축을 하나 빠뜨리면 artifact는 다시 「다르다는
        사실만 있고 이유가 없는」 상태로 돌아간다. 그때 조용히 통과하지 않고
        생성 단계에서 멈춰야 한다.
        """
        uncovered = {
            "time_statuses_match": True,
            "requirement_overalls_match": False,
            "common_package_count": 0,
            "baseline_package_count": 0,
            "known_differences": ["time_statuses: unrelated reason."],
        }
        with self.assertRaises(ValueError) as caught:
            _require_reason_per_mismatch("scenario_probe", uncovered)
        self.assertIn("requirement_overalls", str(caught.exception))

        covered = dict(uncovered, known_differences=["requirement_overalls: shared X vs baseline Y."])
        _require_reason_per_mismatch("scenario_probe", covered)

    def test_adapter_does_not_mutate_shared_sources(self):
        paths = [ROOT / "data/mock" / module / "scenario_correction_rerun_001.json" for module in ("recording", "search", "readout", "case", "evidence")]
        before = {path: path.read_bytes() for path in paths}
        self.run_case("scenario_correction_rerun_001")
        self.assertEqual(before, {path: path.read_bytes() for path in paths})


if __name__ == "__main__":
    unittest.main()
