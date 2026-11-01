"""ADR-EVIDENCE-006 · #487 — the versioned plate format rules as a pure function.

The rules ask for review; they never say VALID or INVALID.  The parity fixture records what
the PR #91 experiment engine (`classify()` / `notes()`) returned for each vector when the
fixture was generated, so this file checks the product evaluator against that engine
without importing experiment code.
"""

from __future__ import annotations

import json
import unicodedata
import unittest
from pathlib import Path

from daesingo.evidence import PolicyConfigurationError
from daesingo.evidence import plate_format
from daesingo.evidence.plate_format import (
    CONSISTENCY_PARTIAL_COVERAGE,
    OBSERVED_OUTSIDE_NOTICE_SCOPE,
    OFFICIAL,
    assess_plate_format,
    load_plate_format_rules,
    normalize_plate_for_check,
    plate_format_rule_ref,
)
from daesingo.evidence.policy import EVIDENCE_POLICY_REF, PLATE_FORMAT_RULE_REF

ROOT = Path(__file__).resolve().parents[2]
PARITY = json.loads(
    (ROOT / "tests/evidence/fixtures/plate_format_parity_kr_v1.json").read_text(encoding="utf-8"))


def _codes(value: str) -> tuple[str, ...]:
    return assess_plate_format(value).reason_codes


class RuleSourceTests(unittest.TestCase):
    def setUp(self):
        self.data = load_plate_format_rules()

    def test_revision_is_pinned_to_the_evidence_policy(self):
        self.assertEqual("plate-format/kr-v1", plate_format_rule_ref())
        self.assertEqual(PLATE_FORMAT_RULE_REF, plate_format_rule_ref())
        self.assertEqual("policy/evidence-assembly-v2", EVIDENCE_POLICY_REF)
        self.assertIsNone(self.data["supersedes_rule_ref"])
        self.assertEqual("2026-11-28", self.data["basis"]["pending_notice"]["effective_on"])

    def test_notice_values_match_the_pr88_research(self):
        sets = {name: entry["symbols"] for name, entry in self.data["symbol_sets"].items()}
        car_use = sets["use_private"] + sets["use_business"] + sets["use_rental"]
        self.assertEqual((32, 5, 3, 40), (len(sets["use_private"]), len(sets["use_business"]),
                                          len(sets["use_rental"]), len(set(car_use))))
        self.assertEqual(["바", "사", "아", "자", "배"], sets["use_business"])
        self.assertEqual(["허", "하", "호"], sets["use_rental"])
        self.assertTrue(set(sets["use_parcel"]) <= set(sets["use_business"]))  # 「배」는 운수사업용의 일부
        self.assertEqual(17, len(sets["regions"]))
        self.assertEqual(28, len(sets["use_motorcycle"]))
        self.assertEqual(7, len(sets["diplomatic_prefixes"]))
        three = [(b["from"], b["to"]) for b in self.data["class_bands"]["three_digit"]["bands"]]
        two = [(b["from"], b["to"]) for b in self.data["class_bands"]["two_digit"]["bands"]]
        self.assertEqual([(100, 699), (700, 799), (800, 979), (980, 997), (998, 999)], three)
        self.assertEqual([(1, 69), (70, 79), (80, 97), (98, 99)], two)

    def test_observed_profiles_are_marked_outside_the_notice(self):
        provenance = {p["id"]: p["provenance"] for p in self.data["profiles"]}
        self.assertEqual(
            {"CONSTR_BIZ", "REGION_LEGACY1", "MIL"},
            {pid for pid, value in provenance.items() if value == OBSERVED_OUTSIDE_NOTICE_SCOPE})
        self.assertEqual(OBSERVED_OUTSIDE_NOTICE_SCOPE, self.data["symbol_sets"]["use_military"]["provenance"])
        self.assertTrue(all(value in {OFFICIAL, OBSERVED_OUTSIDE_NOTICE_SCOPE} for value in provenance.values()))

    def test_a_missing_revision_file_is_a_configuration_error(self):
        with self.assertRaises(PolicyConfigurationError):
            load_plate_format_rules("plate_format_rules_kr_v999.json")


class AssessmentSemanticsTests(unittest.TestCase):
    def test_known_profiles_need_no_review(self):
        cases = {
            "12가3456": "NAT2_PRIVATE", "123가4567": "NAT3_PRIVATE", "서울12가3456": "REGION_PRIVATE",
            "12바3456": "NAT2_BIZ", "12배3456": "NAT2_PARCEL", "서울12바3456": "REGION_BIZ",
            "12허3456": "NAT2_RENT", "12하3456": "NAT2_RENT", "12호3456": "NAT2_RENT",
            "123하4567": "NAT3_RENT", "700허1234": "NAT3_RENT",
        }
        for value, profile in cases.items():
            with self.subTest(value=value):
                result = assess_plate_format(value)
                self.assertEqual(profile, result.matched_profile)
                self.assertEqual(OFFICIAL, result.provenance)
                self.assertEqual((), result.reason_codes)
                self.assertFalse(result.review_required)
                self.assertEqual("plate-format/kr-v1", result.rule_ref)

    def test_pr80_lower_row_fragment_asks_for_review(self):
        result = assess_plate_format("바5215")
        self.assertIsNone(result.matched_profile)
        self.assertEqual(("plate.format.incomplete",), result.reason_codes)
        self.assertTrue(result.review_required)

    def test_mismatches_ask_for_review_with_one_format_code(self):
        cases = {
            "12가34?6": "plate.format.incomplete",
            "abc": "plate.format.incomplete",
            "12": "plate.format.incomplete",
            "12가34567": "plate.format.unknown_shape",
            "12쿠3456": "plate.format.use_code_unknown",
            "한국12바3456": "plate.format.region_unknown",
            "012가3456": "plate.format.head_out_of_range",
            "00가1234": "plate.format.head_out_of_range",
            "12가0000": "plate.format.serial_out_of_range",
        }
        for value, code in cases.items():
            with self.subTest(value=value):
                result = assess_plate_format(value)
                self.assertIsNone(result.matched_profile)
                self.assertEqual((code,), result.reason_codes)
                self.assertTrue(result.review_required)

    def test_explained_but_unusual_combinations_ask_for_review(self):
        cases = {
            "123바4567": ("NAT3_BIZ", ("plate.consistency.biz_with_3digit_band",)),
            "800하1234": ("NAT3_RENT", ("plate.consistency.rent_band_mismatch",)),
            "998가1234": ("NAT3_PRIVATE", ("plate.consistency.emergency_band",)),
        }
        for value, (profile, codes) in cases.items():
            with self.subTest(value=value):
                result = assess_plate_format(value)
                self.assertEqual(profile, result.matched_profile)
                self.assertEqual(codes, result.reason_codes)
                self.assertTrue(result.review_required)

    def test_special_profiles_are_recognized_but_not_passed_silently(self):
        # ADR-EVIDENCE-006 §4-7: profiles the notice does not cover, or the rules cannot fully
        # check, go to review — recognized, never rejected, never reported as plainly normal.
        cases = {
            "서울3가1234": ("REGION_LEGACY1", OBSERVED_OUTSIDE_NOTICE_SCOPE, ("plate.consistency.legacy_scheme",)),
            "12육3456": ("MIL", OBSERVED_OUTSIDE_NOTICE_SCOPE, ("plate.consistency.outside_notice_scope",)),
            "영서울06가5001": ("CONSTR_BIZ", OBSERVED_OUTSIDE_NOTICE_SCOPE, ("plate.consistency.outside_notice_scope",)),
            "영서울06가1234": ("CONSTR_BIZ", OBSERVED_OUTSIDE_NOTICE_SCOPE,
                           ("plate.consistency.constr_serial_band_mismatch", "plate.consistency.outside_notice_scope")),
            "서울강남가1234": ("MOTO", OFFICIAL, (CONSISTENCY_PARTIAL_COVERAGE,)),
            "외교123456": ("DIPLO", OFFICIAL, (CONSISTENCY_PARTIAL_COVERAGE,)),
        }
        for value, (profile, provenance, codes) in cases.items():
            with self.subTest(value=value):
                result = assess_plate_format(value)
                self.assertEqual((profile, provenance, codes),
                                 (result.matched_profile, result.provenance, result.reason_codes))
                self.assertTrue(result.review_required)

    def test_a_shape_preserving_misread_still_passes(self):
        # PR #91 §2-④ · §4: passing is not evidence of a correct read. Losing only the region of a
        # two-line plate leaves a valid national plate; the rules cannot see it.
        self.assertFalse(assess_plate_format("37바1234").review_required)

    def test_there_is_no_valid_invalid_verdict(self):
        result = assess_plate_format("바5215")
        for name in ("valid", "is_valid", "invalid", "verdict", "status"):
            self.assertFalse(hasattr(result, name), name)


class NormalizationTests(unittest.TestCase):
    def test_only_whitespace_is_removed_from_the_checked_copy(self):
        # core-user-flow.md §12: spaces are removed only to compare or check.
        for raw in ("12가 3456", " 12가3456\t", "12 가 3456"):
            with self.subTest(raw=raw):
                result = assess_plate_format(raw)
                self.assertEqual("12가3456", result.normalized)
                self.assertEqual("NAT2_PRIVATE", result.matched_profile)
                self.assertFalse(result.review_required)

    def test_punctuation_is_kept_and_asks_for_review(self):
        # PR #91 E-0 also dropped '-', '.', '·' for human label notation. The product keeps them
        # (web #513 and readout do too), so such a value goes to review instead of passing.
        for raw in ("12-가-3456", "12·가·3456", "12.가.3456"):
            with self.subTest(raw=raw):
                result = assess_plate_format(raw)
                self.assertEqual(raw, result.normalized)
                self.assertTrue(result.review_required)

    def test_decomposed_hangul_is_composed_before_checking(self):
        decomposed = unicodedata.normalize("NFD", "12가3456")
        self.assertNotEqual("12가3456", decomposed)
        self.assertEqual("12가3456", normalize_plate_for_check(decomposed))
        self.assertFalse(assess_plate_format(decomposed).review_required)

    def test_other_characters_are_not_dropped(self):
        self.assertEqual("12가34?6", normalize_plate_for_check("12가34?6"))

    def test_non_string_is_a_caller_error(self):
        with self.assertRaises(TypeError):
            assess_plate_format(None)  # type: ignore[arg-type]


class Pr91ParityTests(unittest.TestCase):
    def test_fixture_covers_the_adr_vectors(self):
        inputs = {row["input"] for row in PARITY["vectors"]}
        self.assertEqual("plate-format/kr-v1", PARITY["rule_ref"])
        self.assertTrue({"바5215", "12가3456", "123가4567", "서울12가3456", "12가34?6", "abc", "12"} <= inputs)

    def test_product_matches_the_recorded_expectation(self):
        for row in PARITY["vectors"]:
            with self.subTest(value=row["input"], label=row["label"]):
                result = assess_plate_format(row["input"])
                expected = row["expected"]
                self.assertEqual(
                    (expected["shape"], expected["matched_profile"], expected["provenance"],
                     expected["review_required"], tuple(expected["reason_codes"])),
                    (result.shape, result.matched_profile, result.provenance,
                     result.review_required, result.reason_codes))

    def test_product_agrees_with_the_experiment_engine(self):
        # classify(): format_id is the matched profile, or the family on a failed check.
        # notes(): the consistency codes. partial_coverage is the product's ADR §4-7 addition.
        for row in PARITY["vectors"]:
            with self.subTest(value=row["input"]):
                result = assess_plate_format(row["input"])
                experiment = row["experiment"]
                format_codes = [c for c in result.reason_codes if c.startswith("plate.format.")]
                notes = [c for c in result.reason_codes
                         if c.startswith("plate.consistency.") and c != CONSISTENCY_PARTIAL_COVERAGE]
                self.assertEqual(experiment["format_id"], result.matched_profile or result.shape)
                self.assertEqual([experiment["reason_code"]] if experiment["reason_code"] else [], format_codes)
                self.assertEqual(experiment["notes"], notes)
                self.assertEqual(
                    bool(experiment["reason_code"] or experiment["notes"]) or CONSISTENCY_PARTIAL_COVERAGE in result.reason_codes,
                    result.review_required)


class RevisionLoadingTests(unittest.TestCase):
    def test_active_revision_file_is_the_only_input(self):
        self.assertEqual("plate_format_rules_kr_v1.json", plate_format.ACTIVE_RULE_FILE)
        self.assertEqual(plate_format_rule_ref(), plate_format._rules(plate_format.ACTIVE_RULE_FILE).rule_ref)


if __name__ == "__main__":
    unittest.main()
