from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from daesingo.evidence import (  # noqa: E402
    EvidenceContractError,
    assemble,
    build_report_package,
    resolve_time,
)
from daesingo.evidence.service import aggregate_requirement_outcomes  # noqa: E402
from evidence_fixture_support import (  # noqa: E402
    expected_evidence_outputs,
    json_shape,
    load_evidence_request,
)


class EvidenceIntegrationTests(unittest.TestCase):
    def test_happy_scenario_matches_contract_fixture_shape(self) -> None:
        outputs = assemble(load_evidence_request("happy_001"))
        expected = expected_evidence_outputs("happy_001")

        for name in outputs:
            with self.subTest(name=name):
                self.assertEqual(json_shape(outputs[name]), json_shape(expected[name]))

        for name in ("time_resolution", "evidence_record", "evidence_needs", "requirement_report"):
            self.assertEqual(outputs[name], expected[name])
        self.assertEqual(outputs["requirement_report"]["overall"], "WARN")
        self.assertIsNotNone(outputs["report_package"])
        self.assertNotIn("흰색 SUV", outputs["report_package"]["report"]["title"])
        self.assertNotIn("흰색 SUV", outputs["report_package"]["report"]["description"])
        self.assertIn("사용자가", outputs["report_package"]["report"]["description"])

    def test_partial_scenario_matches_all_expected_outputs(self) -> None:
        outputs = assemble(load_evidence_request("partial_001"))
        expected = expected_evidence_outputs("partial_001")
        self.assertEqual(outputs, expected)
        self.assertNotIn("vehicle_number", outputs["evidence_record"])
        self.assertNotIn("location", outputs["evidence_record"])
        self.assertEqual(outputs["requirement_report"]["overall"], "BLOCK")
        self.assertIsNone(outputs["report_package"])

    def test_assembly_does_not_mutate_caller_input(self) -> None:
        request = load_evidence_request("happy_001")
        before = deepcopy(request)
        assemble(request)
        self.assertEqual(request, before)

    def test_requirement_precedence(self) -> None:
        cases = [
            (["PASS"], "PASS"),
            (["PASS", "WARN"], "WARN"),
            (["WARN", "UNKNOWN"], "UNKNOWN"),
            (["PASS", "UNKNOWN", "BLOCK"], "BLOCK"),
        ]
        for outcomes, expected in cases:
            with self.subTest(outcomes=outcomes):
                self.assertEqual(aggregate_requirement_outcomes(outcomes), expected)

    def test_unresolved_time_omits_resolved_value(self) -> None:
        result = resolve_time(
            None,
            [],
            resolution_ref={"kind": "time_resolution", "ref": "tres_unknown"},
        )
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertNotIn("resolved", result)
        self.assertNotIn("selected_input_ref", result["provenance"])

    def test_vendor_metadata_is_the_canonical_recording_source_kind(self) -> None:
        result = resolve_time(
            None,
            [
                {
                    "candidate_id": "tsc_vendor",
                    "source_kind": "VENDOR_METADATA",
                    "value": "2026-08-24T18:20:00+09:00",
                    "observation_status": "OK",
                }
            ],
            resolution_ref={"kind": "time_resolution", "ref": "tres_vendor"},
        )
        self.assertEqual(
            result["resolved"]["source"]["kind"], "recording.vendor_metadata_time"
        )

        with self.assertRaises(EvidenceContractError):
            resolve_time(
                None,
                [
                    {
                        "candidate_id": "tsc_noncanonical",
                        "source_kind": "MANUFACTURER_METADATA",
                        "value": "2026-08-24T18:20:00+09:00",
                        "observation_status": "OK",
                    }
                ],
                resolution_ref={"kind": "time_resolution", "ref": "tres_invalid"},
            )

    def test_conflicting_time_sources_are_not_marked_agreed(self) -> None:
        candidates = [
            {
                "candidate_id": "tsc_filename",
                "source_kind": "FILENAME",
                "value": "2026-08-24T18:20:00+09:00",
                "observation_status": "OK",
            },
            {
                "candidate_id": "tsc_metadata",
                "source_kind": "FILE_METADATA",
                "value": "2026-08-24T18:21:00+09:00",
                "observation_status": "OK",
            },
        ]
        result = resolve_time(
            None,
            candidates,
            resolution_ref={"kind": "time_resolution", "ref": "tres_conflict"},
        )
        self.assertEqual(result["status"], "NEEDS_REVIEW")
        self.assertTrue(result["conflict"]["exists"])
        self.assertEqual(result["resolved"]["verification"], "UNVERIFIED")

    def test_matching_time_sources_are_marked_agreed(self) -> None:
        candidates = [
            {
                "candidate_id": "tsc_filename",
                "source_kind": "FILENAME",
                "value": "2026-08-24T18:20:00+09:00",
                "observation_status": "OK",
            },
            {
                "candidate_id": "tsc_metadata",
                "source_kind": "FILE_METADATA",
                "value": "2026-08-24T18:20:00+09:00",
                "observation_status": "OK",
            },
        ]
        result = resolve_time(
            None,
            candidates,
            resolution_ref={"kind": "time_resolution", "ref": "tres_agreed"},
        )
        self.assertEqual(result["status"], "OK")
        self.assertFalse(result["conflict"]["exists"])
        self.assertEqual(result["resolved"]["verification"], "AGREED")

    def test_contract_enum_typo_fails_closed(self) -> None:
        request = load_evidence_request("happy_001")
        request["requirement_scope"] = "FINAL"
        with self.assertRaises(EvidenceContractError):
            assemble(request)

    def test_cross_case_readout_is_rejected(self) -> None:
        request = load_evidence_request("happy_001")
        request["plate_readout"]["case_id"] = "case_other"
        with self.assertRaises(EvidenceContractError):
            assemble(request)

    def test_cross_candidate_visual_evidence_is_rejected(self) -> None:
        request = load_evidence_request("happy_001")
        request["visual_evidence"]["candidate_id"] = "cand_other"
        with self.assertRaises(EvidenceContractError):
            assemble(request)

    def test_package_rejects_mismatched_requirement_basis(self) -> None:
        request = load_evidence_request("happy_001")
        outputs = assemble(request)
        report = deepcopy(outputs["requirement_report"])
        report["basis"]["evidence_record_ref"]["ref"] = "ev_other"
        with self.assertRaises(EvidenceContractError):
            build_report_package(
                outputs["evidence_record"],
                report,
                package_ref=request["refs"]["package_ref"],
                created_at=request["package_created_at"],
                report_video_ref=request["assets"]["report_video_ref"],
                plate_image_ref=request["assets"]["plate_image_ref"],
                source_refs=request["assets"]["source_refs"],
            )

    def test_block_requirement_closes_package_gate_even_with_valid_assets(self) -> None:
        request = load_evidence_request("partial_001")
        outputs = assemble(request)
        self.assertIsNone(
            build_report_package(
                outputs["evidence_record"],
                outputs["requirement_report"],
                package_ref={"kind": "report_package", "ref": "pkg_gate_test"},
                created_at="2026-08-24T18:40:00+09:00",
                report_video_ref={"kind": "derived_asset", "ref": "da_gate_test"},
                source_refs=[{"kind": "source_asset", "ref": "sa_gate_test"}],
            )
        )

    def test_confirmed_search_keyword_wins_over_user_hint_derivation(self) -> None:
        request = load_evidence_request("happy_001")
        outputs = assemble(request)
        record = deepcopy(outputs["evidence_record"])
        record["location"]["search_keyword"] = deepcopy(record["location"]["user_hint"])
        record["location"]["search_keyword"]["value"] = "정자역"
        package = build_report_package(
            record,
            outputs["requirement_report"],
            package_ref=request["refs"]["package_ref"],
            created_at=request["package_created_at"],
            report_video_ref=request["assets"]["report_video_ref"],
            plate_image_ref=request["assets"]["plate_image_ref"],
            source_refs=request["assets"]["source_refs"],
        )
        self.assertIsNotNone(package)
        self.assertEqual(package["report_inputs"]["location"]["display_text"], "미금역 근처")
        self.assertEqual(package["report_inputs"]["location"]["search_keyword"], "정자역")

    def test_malformed_known_empty_gps_is_rejected(self) -> None:
        request = load_evidence_request("happy_001")
        request["observations"][0]["status"] = "OK"
        request["observations"][0]["value"] = []
        with self.assertRaises(EvidenceContractError):
            assemble(request)

    def test_request_is_json_serializable(self) -> None:
        json.dumps(load_evidence_request("happy_001"), ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
