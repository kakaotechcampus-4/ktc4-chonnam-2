"""readout 불변조건 — fixture가 규칙을 지키는지, 그리고 **규칙이 실제로 잡는지**.

두 방향을 같이 본다. 앞쪽만 있으면 아무것도 검사하지 않는 함수도 초록색으로 통과한다.
그래서 뒤쪽(고의로 깨뜨려 위반이 나오는지)이 규칙 하나하나에 붙어 있다.

`python -m unittest discover -s tests` 로 돈다.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from daesingo.readout import invariants  # noqa: E402
from daesingo.readout.contracts import ReadoutFixture  # noqa: E402
from daesingo.readout.fixtures import fixture_paths, load_all, load_raw  # noqa: E402


def _raw(scenario_id):
    return load_raw(Path(invariants.__file__).resolve().parents[3]
                    / "data" / "mock" / "readout" / f"{scenario_id}.json")


def _rules(violations):
    return sorted({v.rule for v in violations})


class FixturesHoldTest(unittest.TestCase):
    def test_mock_pack_v5_has_no_violation(self):
        fixtures = list(load_all().values())
        self.assertEqual(len(fixtures), len(fixture_paths()))
        violations = invariants.check_all(fixtures)
        self.assertEqual([str(v) for v in violations], [])


class RuleFiresTest(unittest.TestCase):
    """규칙별로 fixture를 한 군데씩 깨뜨려, 그 규칙이 잡는지 본다."""

    def _check(self, scenario_id, mutate):
        raw = copy.deepcopy(_raw(scenario_id))
        mutate(raw)
        return invariants.check_fixture(ReadoutFixture.from_dict(raw))

    def test_R1_outcome_failure_mismatch(self):
        def mutate(raw):
            raw["readout_runs"][0]["failure"] = {"kind": "INFRA", "code": "READOUT_PIPELINE_ERROR"}
        self.assertIn("R1", _rules(self._check("scenario_happy_001", mutate)))

    def test_R2_overlay_validation_is_not_a_run_failure(self):
        def mutate(raw):
            run = raw["readout_runs"][1]
            run["outcome"] = "FAILED"
            run["failure"] = {"kind": "OVERLAY_VALIDATION", "code": "READOUT_PIPELINE_ERROR"}
        self.assertIn("R2", _rules(self._check("scenario_happy_001", mutate)))

    def test_R3_total_failure_must_not_produce_a_result(self):
        """Merge 중단 기준 — 완전 실패인데 결과 객체가 생성됨."""
        def mutate(raw):
            donor = copy.deepcopy(_raw("scenario_happy_001")["plate_readouts"][0])
            donor["run_ref"]["ref"] = "rr_x001_plate"        # outcome=FAILED인 run
            donor["observation"]["produced_by"]["run_ref"]["ref"] = "rr_x001_plate"
            raw["plate_readouts"].append(donor)
        self.assertIn("R3", _rules(self._check("scenario_infra_failure_001", mutate)))

    def test_R4_run_ref_must_resolve(self):
        def mutate(raw):
            raw["plate_readouts"][0]["run_ref"]["ref"] = "rr_does_not_exist"
        self.assertIn("R4", _rules(self._check("scenario_happy_001", mutate)))

    def test_R6_produced_by_must_match_run_ref(self):
        def mutate(raw):
            raw["plate_readouts"][0]["observation"]["produced_by"]["run_ref"]["ref"] = \
                "rr_h001_overlay"
        self.assertIn("R6", _rules(self._check("scenario_happy_001", mutate)))

    def test_R5_one_run_one_result(self):
        def mutate(raw):
            raw["plate_readouts"].append(copy.deepcopy(raw["plate_readouts"][0]))
        self.assertIn("R5", _rules(self._check("scenario_happy_001", mutate)))

    def test_R7_operation_must_match_result_type(self):
        def mutate(raw):
            raw["plate_readouts"][0]["run_ref"]["ref"] = "rr_h001_overlay"
            raw["plate_readouts"][0]["observation"]["produced_by"]["run_ref"]["ref"] = "rr_h001_overlay"
        self.assertIn("R7", _rules(self._check("scenario_happy_001", mutate)))

    def test_R8_unknown_must_have_null_value(self):
        def mutate(raw):
            raw["overlay_time_readouts"][0]["observation"]["value"] = "2026-08-30T09:11:00+09:00"
        self.assertIn("R8", _rules(self._check("scenario_infra_failure_001", mutate)))

    def test_R9_support_refs_must_be_empty(self):
        def mutate(raw):
            raw["plate_readouts"][0]["observation"]["support_refs"] = ["fr_h001_plate1"]
        self.assertIn("R9", _rules(self._check("scenario_happy_001", mutate)))

    def test_R10_abstain_needs_review(self):
        def mutate(raw):
            raw["plate_readouts"][0]["observation"]["status"] = "OK"
        self.assertIn("R10", _rules(self._check("scenario_plate_reread_001", mutate)))

    def test_R11_abstain_must_not_produce_a_confirmed_plate(self):
        """Merge 중단 기준 — abstained=true인데 확정 번호판 값이 함께 나옴."""
        def mutate(raw):
            plate = raw["plate_readouts"][0]
            plate["observation"]["value"] = "17나2867"
            plate["consensus"]["text"] = "17나2867"
            plate["consensus"]["disagree_positions"] = []
        self.assertIn("R11", _rules(self._check("scenario_plate_reread_001", mutate)))

    def test_R11_does_not_fire_outside_frame_disagreement(self):
        """저신뢰도·저해상도·association 보류는 값이 온전해도 위반이 아니다.

        계약 §5가 「OCR 문자열이 정확해 보여도 `target_association`이 `AMBIGUOUS`면 evidence는
        최종 확정을 보류할 수 있다」고 쓴 그 조합이다. 여기를 R11로 잡으면 구현이 보류할 때마다
        관찰값을 지우게 되고, evidence는 번호판을, eval은 abstention 분석 대상을 잃는다.
        """
        def mutate(raw):
            plate = raw["plate_readouts"][0]
            plate["abstain_reason"] = "OCR_LOW_CONFIDENCE"
            plate["observation"]["value"] = "17나2867"
            plate["consensus"]["text"] = "17나2867"
            plate["consensus"]["disagree_positions"] = []
        self.assertNotIn("R11", _rules(self._check("scenario_plate_reread_001", mutate)))

    def test_R12_abstain_reason_is_the_only_source(self):
        def mutate(raw):
            raw["plate_readouts"][0]["observation"]["reason"] = {
                "code": "readout.plate.frame_disagreement", "note": "중복 기재"}
        self.assertIn("R12", _rules(self._check("scenario_plate_reread_001", mutate)))

    def test_R13_no_reason_when_not_abstained(self):
        def mutate(raw):
            raw["plate_readouts"][0]["abstain_reason"] = "LOW_RESOLUTION"
        self.assertIn("R13", _rules(self._check("scenario_happy_001", mutate)))

    def test_R14_association_wins_over_frame_consensus(self):
        def mutate(raw):
            raw["plate_readouts"][0]["target_association"]["status"] = "AMBIGUOUS"
        self.assertIn("R14", _rules(self._check("scenario_plate_reread_001", mutate)))

    def test_R15_disagree_positions_track_the_question_marks(self):
        def mutate(raw):
            raw["plate_readouts"][0]["consensus"]["disagree_positions"] = [2, 3]
        self.assertIn("R15", _rules(self._check("scenario_plate_reread_001", mutate)))

    def test_R17_overlay_branches_must_not_be_merged(self):
        """Merge 중단 기준 — overlay 갈래가 한 값으로 합쳐짐."""
        def mutate(raw):
            # 「없음」(사실)의 reason을 「있는지 못 봄」(모름)으로 바꿔 단다
            raw["overlay_time_readouts"][0]["observation"]["reason"]["code"] = \
                "readout.overlay.presence_undetermined"
        violations = self._check("scenario_correction_rerun_001", mutate)
        self.assertIn("R17", _rules(violations))

    def test_R17_unregistered_branch_is_caught(self):
        def mutate(raw):
            raw["overlay_time_readouts"][0]["observation"]["reason"]["code"] = \
                "readout.overlay.something_new"
        self.assertIn("R17", _rules(self._check("scenario_correction_rerun_001", mutate)))

    def test_R18_sample_count_matches_samples(self):
        def mutate(raw):
            raw["overlay_time_readouts"][0]["validation"]["sample_count"] = 99
        self.assertIn("R18", _rules(self._check("scenario_happy_001", mutate)))

    def test_R16_crop_ref_is_not_reused_across_runs(self):
        """재판독이 앞 run의 crop_ref를 다시 쓰면 잡힌다."""
        raw = copy.deepcopy(_raw("scenario_plate_reread_001"))
        reread = raw["plate_readouts"][1]
        reread["best_frame"]["crop_ref"] = "crop_p001_001"   # 최초 판독이 발급한 crop
        reread["best_frame"]["frame_ref"] = "fr_p001_plate3"
        fixture = ReadoutFixture.from_dict(raw)
        self.assertIn("R16", _rules(invariants.check_crop_identity([fixture])))


if __name__ == "__main__":
    unittest.main()
