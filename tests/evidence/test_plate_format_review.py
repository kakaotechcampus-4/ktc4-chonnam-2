"""ADR-EVIDENCE-006 · #487 — plate format review on the PlateReadout → vehicle_number path.

Records are built with the real `assemble_evidence()` from the happy scenario; only the
PlateReadout (and CorrectionRecords) change per case.

- value present + suspicious → value kept as observed, `needs_review=true` (`INFO_NEEDS_REVIEW`)
- value absent / readout abstained → `vehicle_number` absent, existing `PLATE_REREAD` path
- user correction → `user_corrected=true`, `needs_review=false`, never rejected for its format
"""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from daesingo.case.view import _field_states
from daesingo.evidence import (
    calculate_evidence_needs,
    evaluate_requirements,
    resolve_independent_facts,
    validate_contract,
    validate_correction_append,
)
from daesingo.evidence import mock_integration as mock

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = json.loads((ROOT / "tests/evidence/fixtures/adapter_inputs.json").read_text(encoding="utf-8"))["scenarios"]
SCENARIO = "scenario_happy_001"
EVIDENCE_AT = CONFIGS[SCENARIO]["evaluated_at"][0]


class PlateFormatReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = CONFIGS[SCENARIO]
        cls.time = mock.run_scenario(ROOT, SCENARIO, cls.config)["outputs"]["time_resolutions"][0]
        cls.upstream = mock._upstream(ROOT, SCENARIO)
        cls.plate = cls.upstream["readout"]["plate_readouts"][0]
        cls.case_id = cls.upstream["case"]["case_views"][-1]["case_id"]

    # --- inputs -------------------------------------------------------------------------------

    def _ocr(self, value, *, status="OK", abstained=False, reason=None):
        plate = deepcopy(self.plate)
        plate["observation"]["value"] = value
        plate["observation"]["status"] = status
        plate["abstained"] = abstained
        plate["abstain_reason"] = reason
        return plate

    def _correction(self, new_value, previous_value, correction_id="corr_plate_format"):
        return {
            "contract_version": "correction-record/v1.2", "correction_id": correction_id,
            "case_id": self.case_id, "selection_rev": self.config["selection_rev"],
            "kind": "PLATE_MANUAL_EDIT", "target_field": "vehicle_number",
            "previous_value": previous_value, "new_value": new_value,
            "supersedes_ref": None, "corrected_at": EVIDENCE_AT,
        }

    def _record(self, plate, corrections=None):
        record = mock._assemble(upstream=self.upstream, config=self.config, time=self.time, plate=plate,
                                record_id="ev_plate_format", correction_records=corrections)
        self.assertEqual([], validate_contract(record))
        return record

    def _plate_state(self, record):
        return _field_states(record)["vehicle_number"]["info_state"]

    def _plate_check(self, record):
        report = evaluate_requirements(record, scope="EVIDENCE", report_id="req_plate_format",
                                       evaluated_at=EVIDENCE_AT, time_resolution=self.time)
        return next(item for item in report["checks"] if item["code"] == "evidence.vehicle_number.present")

    # --- readout OCR value --------------------------------------------------------------------

    def test_normal_plate_is_kept_without_review(self):
        for value in ("12가3456", "123가4567", "서울12바3456", "123하4567"):
            with self.subTest(value=value):
                plate = self._ocr(value)
                record = self._record(plate)
                self.assertEqual(value, record["vehicle_number"]["value"])
                self.assertFalse(record["vehicle_number"]["needs_review"])
                self.assertFalse(record["vehicle_number"]["user_corrected"])
                self.assertEqual("INFO_SOURCE_VERIFIED", self._plate_state(record))
                self.assertEqual([], calculate_evidence_needs(record, plate)["items"])
                self.assertEqual("policy/evidence-assembly-v2", record["provenance"]["policy_ref"])

    def test_pr80_fragment_is_kept_and_needs_review(self):
        # PR #80: the lower row of a two-line plate read 5/5 frames, OK and not abstained.
        plate = self._ocr("바5215")
        record = self._record(plate)
        self.assertEqual("바5215", record["vehicle_number"]["value"])
        self.assertTrue(record["vehicle_number"]["needs_review"])
        self.assertFalse(record["vehicle_number"]["user_corrected"])
        self.assertEqual("readout.plate_ocr", record["vehicle_number"]["source"]["kind"])
        self.assertEqual("INFO_NEEDS_REVIEW", self._plate_state(record))
        # needs_review is not PLATE_REREAD, and it does not turn the value into a missing one.
        self.assertEqual([], calculate_evidence_needs(record, plate)["items"])
        check = self._plate_check(record)
        self.assertEqual(("PASS", "evidence.value_confirmed"), (check["outcome"], check["reason_code"]))

    def test_usable_format_mismatches_are_kept_and_need_review(self):
        for value in ("12가34?6", "abc", "12", "12쿠3456", "12가34567", "서울강남가1234", "12육3456"):
            with self.subTest(value=value):
                record = self._record(self._ocr(value))
                self.assertEqual(value, record["vehicle_number"]["value"])
                self.assertTrue(record["vehicle_number"]["needs_review"])
                self.assertEqual("INFO_NEEDS_REVIEW", self._plate_state(record))

    def test_stored_value_is_the_observed_text_not_the_checked_copy(self):
        record = self._record(self._ocr("12가 3456"))
        self.assertEqual("12가 3456", record["vehicle_number"]["value"])
        self.assertFalse(record["vehicle_number"]["needs_review"])

    def test_pre_response_projection_uses_the_same_review(self):
        # #239 · ADR-EVIDENCE-009: the projection before the situation response shares the rule.
        facts = resolve_independent_facts(case_id=self.case_id, selection_rev=self.config["selection_rev"],
                                          time_resolution=self.time, plate_readout=self._ocr("바5215"))
        self.assertEqual(("바5215", True), (facts["vehicle_number"]["value"], facts["vehicle_number"]["needs_review"]))

    # --- no value / abstain: unchanged --------------------------------------------------------

    def test_readout_partial_abstain_keeps_the_reread_path(self):
        # Readout's own guard abstains on a fragment (PARTIAL_PLATE_READ). That path is not
        # changed here: no vehicle_number, PLATE_REREAD, WARN (ADR-EVIDENCE-008 §4.3).
        plate = self._ocr("바5215", status="NEEDS_REVIEW", abstained=True, reason="PARTIAL_PLATE_READ")
        record = self._record(plate)
        self.assertNotIn("vehicle_number", record)
        self.assertEqual("INFO_UNKNOWN", self._plate_state(record))
        self.assertEqual(["PLATE_REREAD"], [item["kind"] for item in calculate_evidence_needs(record, plate)["items"]])
        self.assertEqual("WARN", self._plate_check(record)["outcome"])

    def test_unread_plate_stays_absent_without_reread(self):
        plate = self._ocr(None, status="UNKNOWN")
        record = self._record(plate)
        self.assertNotIn("vehicle_number", record)
        self.assertEqual([], calculate_evidence_needs(record, plate)["items"])
        self.assertEqual(("WARN", "evidence.plate_unidentified"),
                         tuple(self._plate_check(record)[key] for key in ("outcome", "reason_code")))

    # --- user correction ----------------------------------------------------------------------

    def test_user_correction_with_a_normal_plate_is_confirmed(self):
        correction = self._correction("34나5678", "12가3456")
        validate_correction_append(correction, existing_records=[])
        record = self._record(self._ocr("12가3456"), [correction])
        self.assertEqual(("34나5678", True, False), (
            record["vehicle_number"]["value"], record["vehicle_number"]["user_corrected"],
            record["vehicle_number"]["needs_review"]))
        self.assertEqual("INFO_USER_CONFIRMED", self._plate_state(record))

    def test_user_correction_that_breaks_the_format_is_kept_as_confirmed(self):
        # ADR-EVIDENCE-006 §2.5: the user looked at the video. The format rule neither rejects the
        # value nor sends the same field back to review.
        for new_value in ("바1234", "abc", "12가 34?6", "서울강남가1234"):
            with self.subTest(new_value=new_value):
                correction = self._correction(new_value, "바5215")
                validate_correction_append(correction, existing_records=[])  # no rejection
                record = self._record(self._ocr("바5215"), [correction])
                value = record["vehicle_number"]
                self.assertEqual(new_value, value["value"])  # stored verbatim, not normalized
                self.assertTrue(value["user_corrected"])
                self.assertFalse(value["needs_review"])
                self.assertEqual("case.user_correction", value["source"]["kind"])
                self.assertEqual("INFO_USER_CONFIRMED", self._plate_state(record))
                self.assertEqual("PASS", self._plate_check(record)["outcome"])

    def test_manual_input_after_abstain_is_not_rejected_for_its_format(self):
        plate = self._ocr("바5215", status="NEEDS_REVIEW", abstained=True, reason="PARTIAL_PLATE_READ")
        correction = self._correction("서울74바5215", None)
        validate_correction_append(correction, existing_records=[])
        record = self._record(plate, [correction])
        self.assertEqual(("서울74바5215", True, False), (
            record["vehicle_number"]["value"], record["vehicle_number"]["user_corrected"],
            record["vehicle_number"]["needs_review"]))
        # The confirmed value fills the field, so the reread need is no longer emitted.
        self.assertEqual([], calculate_evidence_needs(record, plate)["items"])


if __name__ == "__main__":
    unittest.main()
