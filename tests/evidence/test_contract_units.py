from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from daesingo.evidence import (
    ContractInputError,
    PackageNotReady,
    PolicyConfigurationError,
    aggregate_outcomes,
    assemble_evidence,
    build_report_package,
    correction_heads,
    evaluate_requirements,
    render_report,
    resolve_time,
)
from daesingo.evidence.mock_integration import run_scenario
from daesingo.evidence.policy import EVENT_POLICY, SPECIFIC_TEMPLATE_REF


ROOT = Path(__file__).resolve().parents[2]
CONFIGS = json.loads((ROOT / "tests/evidence/fixtures/adapter_inputs.json").read_text(encoding="utf-8"))["scenarios"]


class ContractUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.happy = run_scenario(ROOT, "scenario_happy_001", CONFIGS["scenario_happy_001"])
        cls.record = cls.happy["outputs"]["evidence_records"][0]
        cls.assets = json.loads((ROOT / "data/mock/recording/scenario_happy_001.json").read_text(encoding="utf-8"))["asset_facts"]

    def test_time_without_basis_is_unknown_and_has_no_resolved_value(self):
        result = resolve_time(
            time_source_candidates=[],
            overlay_time_readout=None,
            candidate_event={"span": {"representative_ms": 0}},
            case_id="case_unit",
            selection_rev=1,
            resolution_id="time_unit_unknown",
        )
        self.assertEqual("UNKNOWN", result["status"])
        self.assertNotIn("resolved", result)
        self.assertNotIn("selected_input_ref", result["provenance"])

    def test_outcome_precedence(self):
        def checks(values):
            return [{"outcome": value} for value in values]

        self.assertEqual("PASS", aggregate_outcomes(checks(["PASS", "PASS"])))
        self.assertEqual("WARN", aggregate_outcomes(checks(["PASS", "WARN"])))
        self.assertEqual("UNKNOWN", aggregate_outcomes(checks(["BLOCK", "UNKNOWN", "WARN", "PASS"])[1:]))
        self.assertEqual("BLOCK", aggregate_outcomes(checks(["UNKNOWN", "BLOCK", "WARN"])))

    def test_unknown_and_block_reports_do_not_build_packages(self):
        for overall in ("UNKNOWN", "BLOCK"):
            report = deepcopy(self.happy["outputs"]["requirement_reports"][1])
            report["overall"] = overall
            with self.assertRaisesRegex(PackageNotReady, "package.requirement_not_ready"):
                build_report_package(self.record, report, package_id=f"pkg_{overall}", created_at="2026-09-13T10:00:00+09:00", asset_facts=self.assets)

    def test_missing_and_unavailable_asset_produce_unknown_and_block(self):
        missing = evaluate_requirements(
            self.record, scope="FINAL_PACKAGE", report_id="req_missing",
            evaluated_at="2026-09-13T10:00:00+09:00",
            rule_codes=["package.asset.report_video.exists"], asset_facts=[],
        )
        unavailable_assets = deepcopy(self.assets)
        report_video = next(item for item in unavailable_assets if item.get("derived_role") == "REPORT_VIDEO")
        report_video["availability"] = "UNAVAILABLE"
        blocked = evaluate_requirements(
            self.record, scope="FINAL_PACKAGE", report_id="req_blocked",
            evaluated_at="2026-09-13T10:00:00+09:00",
            rule_codes=["package.asset.report_video.exists"], asset_facts=unavailable_assets,
        )
        self.assertEqual("UNKNOWN", missing["overall"])
        self.assertEqual("BLOCK", blocked["overall"])
        report_video["availability"] = "UNKNOWN"
        unknown = evaluate_requirements(
            self.record, scope="FINAL_PACKAGE", report_id="req_unknown_asset",
            evaluated_at="2026-09-13T10:00:00+09:00",
            rule_codes=["package.asset.report_video.exists"], asset_facts=unavailable_assets,
        )
        self.assertEqual("UNKNOWN", unknown["overall"])

    def test_missing_asset_and_failed_assembly_do_not_build_packages(self):
        report = self.happy["outputs"]["requirement_reports"][1]
        with self.assertRaisesRegex(PackageNotReady, "package.asset.report_video_missing"):
            build_report_package(self.record, report, package_id="pkg_no_asset", created_at="2026-09-13T10:00:00+09:00", asset_facts=[])
        with self.assertRaisesRegex(PackageNotReady, "package.assembly_failed"):
            build_report_package(self.record, report, package_id="pkg_failed", created_at="2026-09-13T10:00:00+09:00", asset_facts=self.assets, assembly_succeeded=False)

    def test_plate_image_is_optional_and_package_supersede_is_additive(self):
        report = self.happy["outputs"]["requirement_reports"][1]
        report_only = [item for item in self.assets if item.get("derived_role") == "REPORT_VIDEO"]
        package = build_report_package(self.record, report, package_id="pkg_unit", created_at="2026-09-13T10:00:00+09:00", asset_facts=report_only)
        self.assertNotIn("plate_image_ref", package["assets"])
        replacement = build_report_package(self.record, report, package_id="pkg_unit_v2", created_at="2026-09-13T10:01:00+09:00", asset_facts=report_only, supersedes_id="pkg_unit")
        self.assertEqual({"kind": "report_package", "ref": "pkg_unit"}, replacement["supersedes_ref"])
        self.assertEqual("pkg_unit", package["package_ref"]["ref"])

    def test_unadopted_size_and_deadline_rules_are_not_invented(self):
        for rule in ("package.asset.report_video.size", "package.deadline.within_policy"):
            with self.assertRaises(PolicyConfigurationError):
                evaluate_requirements(
                    self.record,
                    scope="FINAL_PACKAGE",
                    report_id="req_policy_gap",
                    evaluated_at="2026-09-13T10:00:00+09:00",
                    rule_codes=[rule],
                    asset_facts=self.assets,
                )

    def test_all_four_event_mappings_render_with_adopted_template_and_length(self):
        for visual_type, policy in EVENT_POLICY.items():
            rendered = render_report(
                visual_event_type=visual_type,
                occurred_at="2026-09-13T10:00:00+09:00",
                location_display="서울시 테스트로 1",
                vehicle_number="12가3456",
                violation_expression=policy["violation_expression"],
            )
            self.assertEqual(SPECIFIC_TEMPLATE_REF, rendered["template_ref"])
            self.assertGreaterEqual(rendered["content_length"], 5)
            self.assertLessEqual(rendered["content_length"], 900)
        generic = render_report(
            visual_event_type=None,
            occurred_at="2026-09-13T10:00:00+09:00",
            location_display="서울시 테스트로 1",
            vehicle_number="12가3456",
            violation_expression="확인이 필요한 주행 상황",
        )
        self.assertEqual("tmpl/safety-report-generic-v1", generic["template_ref"])
        self.assertGreaterEqual(generic["content_length"], 5)
        self.assertLessEqual(generic["content_length"], 900)

    def test_correction_head_validates_type_chain_and_actual_application(self):
        first = self._correction("corr_plate_1", "vehicle_number", "11가1111", "22나2222", kind="PLATE_MANUAL_EDIT")
        second = self._correction("corr_plate_2", "vehicle_number", "22나2222", "33다3333", kind="PLATE_MANUAL_EDIT", supersedes="corr_plate_1")
        heads = correction_heads([first, second], case_id="case_h001", selection_rev=1)
        self.assertEqual("corr_plate_2", heads["vehicle_number"]["correction_id"])
        assembled = self._reassemble([first, second])
        self.assertEqual("33다3333", assembled["vehicle_number"]["value"])
        self.assertTrue(assembled["vehicle_number"]["user_corrected"])
        self.assertIn({"kind": "correction_record", "ref": "corr_plate_2"}, assembled["provenance"]["correction_refs"])
        with self.assertRaises(ContractInputError):
            correction_heads([self._correction("bad", "location.coord", {"lat": 1, "lon": 2}, "not-a-coordinate")], case_id="case_h001", selection_rev=1)

    def test_all_ten_evidence_correction_target_types(self):
        values = {
            "event.visual_event_type": ("SIGNAL", "CENTER_LINE_CROSSING"),
            "event.safety_report_type": ("TRAFFIC_VIOLATION", "MOTORCYCLE_VIOLATION"),
            "event.violation_expression": ("기존 위반 표현", "수정된 위반 표현"),
            "occurred_at": ("2026-09-13T10:00:00+09:00", "2026-09-13T10:01:00+09:00"),
            "vehicle_number": ("11가1111", "22나2222"),
            "location.coord": ({"lat": 35.1, "lon": 126.1}, {"lat": 35.2, "lon": 126.2}),
            "location.address": ("이전 주소", "수정 주소"),
            "location.place_name": ("이전 장소", "수정 장소"),
            "location.search_keyword": ("이전 검색어", "수정 검색어"),
            "location.user_hint": ("이전 위치 단서", "수정 위치 단서"),
        }
        kinds = {
            "event.visual_event_type": "SITUATION_CHANGE",
            "occurred_at": "EVENT_TIME_MANUAL",
            "vehicle_number": "PLATE_MANUAL_EDIT",
        }
        records = [
            self._correction(f"corr_type_{index}", target, previous, new, kind=kinds.get(target, "REPORT_TYPE_CHANGE"))
            for index, (target, (previous, new)) in enumerate(values.items())
        ]
        self.assertEqual(set(values), set(correction_heads(records, case_id="case_h001", selection_rev=1)))

    def test_corrected_situation_requires_change_but_user_unsure_does_not(self):
        situation = {"value": "CORRECTED", "responded_at": "2026-09-13T10:00:00+09:00", "candidate_ref": {"kind": "candidate_event", "ref": "candidate_h001"}}
        with self.assertRaisesRegex(ContractInputError, "SITUATION_CHANGE"):
            self._reassemble([], situation_response=situation)
        change = self._correction("corr_situation", "event.visual_event_type", "SIGNAL", "CENTER_LINE_CROSSING", kind="SITUATION_CHANGE")
        assembled = self._reassemble([change], situation_response=situation)
        self.assertEqual("CORRECTED", assembled["situation_response"]["value"])
        self.assertEqual("CENTER_LINE_CROSSING", assembled["event"]["visual_event_type"]["value"])
        unsure = {"value": "USER_UNSURE", "responded_at": "2026-09-13T10:00:00+09:00", "candidate_ref": None}
        self.assertEqual("USER_UNSURE", self._reassemble([], situation_response=unsure)["situation_response"]["value"])

    def _correction(self, correction_id, target, previous, new, *, kind="REPORT_TYPE_CHANGE", supersedes=None):
        return {
            "contract_version": "correction-record/v1.1",
            "correction_id": correction_id,
            "case_id": "case_h001",
            "selection_rev": 1,
            "kind": kind,
            "target_field": target,
            "previous_value": previous,
            "new_value": new,
            "supersedes_ref": None if supersedes is None else {"kind": "correction_record", "ref": supersedes},
            "corrected_at": "2026-09-13T10:00:00+09:00",
        }

    def _reassemble(self, corrections, situation_response=None):
        recording = json.loads((ROOT / "data/mock/recording/scenario_happy_001.json").read_text(encoding="utf-8"))
        search = json.loads((ROOT / "data/mock/search/scenario_happy_001.json").read_text(encoding="utf-8"))
        readout = json.loads((ROOT / "data/mock/readout/scenario_happy_001.json").read_text(encoding="utf-8"))
        case = json.loads((ROOT / "data/mock/case/scenario_happy_001.json").read_text(encoding="utf-8"))
        candidate = next(item for group in search["analysis_run_candidate_events"] for item in group["candidates"] if item["candidate_id"] == "candidate_h001")
        visual = next(item for item in search["visual_evidences"] if item["candidate_id"] == "candidate_h001")
        time = self.happy["outputs"]["time_resolutions"][0]
        return assemble_evidence(
            case_id="case_h001", selection_rev=1, candidate_event=candidate, visual_evidence=visual,
            time_resolution=time, plate_readout=readout["plate_readouts"][0], incident_clip=recording["incident_clips"][0],
            record_id="ev_correction_unit", location_hint=case["case_views"][-1]["hints"]["location"],
            correction_records=corrections, situation_response=situation_response,
        )


if __name__ == "__main__":
    unittest.main()
