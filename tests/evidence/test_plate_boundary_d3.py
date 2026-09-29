"""#172 D · D-2 · D-3 — 번호판 식별 실패와 실행 실패의 Requirement 경계(ADR-EVIDENCE-008).

- WARN = 판독·관찰을 실제로 수행했고 번호판 정보가 부족함을 확인한 경우
- UNKNOWN = 아직 판정할 수 없거나 판독 결과 자체가 없는 경우
- 실행 실패(PlateReadout=None)는 WARN으로 위장하지 않는다 — FINAL이 PASS/WARN이 되지 않아 Package가 없다

기록은 모두 실제 `assemble_evidence()`로 만든다. 입력 PlateReadout만 상황별로 바꾼다.
"""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from daesingo.evidence import (
    PackageNotReady,
    build_report_package,
    calculate_evidence_needs,
    evaluate_requirements,
    validate_contract,
)
from daesingo.evidence import mock_integration as mock
from daesingo.evidence.policy_catalog import load_requirement_catalog

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = json.loads((ROOT / "tests/evidence/fixtures/adapter_inputs.json").read_text(encoding="utf-8"))["scenarios"]
SCENARIO = "scenario_happy_001"
EVIDENCE_AT, FINAL_AT = CONFIGS[SCENARIO]["evaluated_at"]


class PlateBoundaryD3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = CONFIGS[SCENARIO]
        cls.happy = mock.run_scenario(ROOT, SCENARIO, cls.config)
        cls.time = cls.happy["outputs"]["time_resolutions"][0]
        cls.upstream = mock._upstream(ROOT, SCENARIO)
        cls.plate = cls.upstream["readout"]["plate_readouts"][0]
        cls.assets = json.loads(
            (ROOT / "data/mock/recording/scenario_happy_001.json").read_text(encoding="utf-8"))["asset_facts"]

    def _record(self, plate):
        return mock._assemble(upstream=self.upstream, config=self.config, time=self.time,
                              plate=plate, record_id="ev_d3_unit")

    def _unread_plate(self):
        plate = deepcopy(self.plate)
        plate["observation"]["value"] = None
        plate["observation"]["status"] = "UNKNOWN"
        return plate

    def _partial_plate(self):
        plate = deepcopy(self.plate)
        plate["observation"]["value"] = "12가34?6"
        plate["observation"]["status"] = "NEEDS_REVIEW"
        plate["abstained"] = True
        return plate

    def _evidence(self, record):
        return evaluate_requirements(record, scope="EVIDENCE", report_id="req_d3_evidence",
                                     evaluated_at=EVIDENCE_AT, time_resolution=self.time)

    def _final(self, record, facts):
        return evaluate_requirements(record, scope="FINAL_PACKAGE", report_id="req_d3_final",
                                     evaluated_at=FINAL_AT, time_resolution=self.time,
                                     asset_facts=self.assets, observation_facts=facts)

    def _facts(self, plate_visible):
        facts = deepcopy(self.config["requirement_observation_facts"])
        if plate_visible is None:
            facts.pop("plate_visible_in_report_video")
        else:
            facts["plate_visible_in_report_video"]["value"] = plate_visible
        return facts

    @staticmethod
    def _check(report, code):
        return next(item for item in report["checks"] if item["code"] == code)

    def test_active_catalog_is_v5_superseding_v4(self):
        catalog = load_requirement_catalog()
        self.assertEqual("policy/requirement-rules-v5", catalog["policy_ref"])
        self.assertEqual("policy/requirement-rules-v4", catalog["supersedes_policy_ref"])

    def test_v4_revision_is_preserved_with_its_historical_block(self):
        v4 = json.loads((ROOT / "src/daesingo/evidence/requirement_rules_v4.json").read_text(encoding="utf-8"))
        rule = next(item for item in v4["scopes"]["FINAL_PACKAGE"]["always"]
                    if item["code"] == "package.vehicle.plate_visible_in_report_video")
        self.assertEqual("policy/requirement-rules-v4", v4["policy_ref"])
        self.assertEqual("BLOCK", rule["outcomes"]["observed_false"])

    def test_1_plate_secured_is_pass(self):
        record = self._record(self.plate)
        check = self._check(self._evidence(record), "evidence.vehicle_number.present")
        self.assertEqual(("PASS", "evidence.value_confirmed"), (check["outcome"], check["reason_code"]))

    def test_2_readout_ran_but_read_nothing_is_warn_with_null_value_and_not_a_blocker(self):
        record = self._record(self._unread_plate())
        self.assertNotIn("vehicle_number", record)  # 값은 만들지 않는다 — "UNKNOWN" 같은 sentinel 없음
        report = self._evidence(record)
        check = self._check(report, "evidence.vehicle_number.present")
        self.assertEqual(("WARN", "evidence.plate_unidentified"), (check["outcome"], check["reason_code"]))
        self.assertNotIn(report["overall"], {"BLOCK", "UNKNOWN"})
        # 1·3은 재판독 대상이 아니다(abstained=false) — Need가 나오지 않는다.
        self.assertEqual([], calculate_evidence_needs(record, self._unread_plate())["items"])
        # FINAL에서도 번호판 두 rule 중 어느 것도 BLOCK/UNKNOWN을 만들지 않는다.
        final = self._final(record, self._facts(True))
        plate_codes = {"package.vehicle.plate_visible_in_report_video"}
        self.assertTrue(all(item["outcome"] in {"PASS", "WARN"}
                            for item in final["checks"] if item["code"] in plate_codes))

    def test_2b_plate_null_package_is_still_gated_by_report_inputs_followup(self):
        # 번호판 rule은 blocker가 아니지만, 번호판 없는 신고문·report_inputs는 아직 계약이 없다
        # (ADR-EVIDENCE-008 §6). 남는 비-PASS/WARN check는 렌더 입력 하나뿐이어야 한다.
        final = self._final(self._record(self._unread_plate()), self._facts(True))
        blocking = {item["code"] for item in final["checks"] if item["outcome"] not in {"PASS", "WARN"}}
        self.assertEqual({"package.report.content_length"}, blocking)

    def test_3_partial_read_needs_review_is_warn_and_keeps_reread_need(self):
        plate = self._partial_plate()
        record = self._record(plate)
        self.assertNotIn("vehicle_number", record)
        check = self._check(self._evidence(record), "evidence.vehicle_number.present")
        self.assertEqual("WARN", check["outcome"])
        needs = calculate_evidence_needs(record, plate)
        self.assertEqual(["PLATE_REREAD"], [item["kind"] for item in needs["items"]])

    def test_4_i4_observed_plate_not_visible_is_warn_not_block(self):
        # v4는 observed_false → BLOCK이었다. #172 D-3이 WARN으로 대체했다.
        record = self._record(self.plate)
        final = self._final(record, self._facts(False))
        check = self._check(final, "package.vehicle.plate_visible_in_report_video")
        self.assertEqual(("WARN", "readout.plate_visibility.not_visible"),
                         (check["outcome"], check["reason_code"]))
        self.assertEqual("WARN", final["overall"])
        package = build_report_package(record, final, package_id="pkg_d3_not_visible",
                                       created_at="2026-08-24T18:26:00+09:00", asset_facts=self.assets)
        self.assertEqual([], validate_contract(package))

    def test_5_i4_not_run_is_unknown(self):
        record = self._record(self.plate)
        final = self._final(record, self._facts(None))
        check = self._check(final, "package.vehicle.plate_visible_in_report_video")
        self.assertEqual(("UNKNOWN", "readout.plate_visibility.not_observed"),
                         (check["outcome"], check["reason_code"]))
        self.assertEqual("UNKNOWN", final["overall"])

    def test_6_readout_execution_failure_is_unknown_and_never_package_ready(self):
        # 4a: ReadoutRun.outcome=FAILED면 PlateReadout=None이 온다. 식별 실패 WARN으로 바꾸지 않는다.
        record = self._record(None)
        self.assertNotIn("vehicle_number", record)
        self.assertFalse(any(ref["kind"] == "plate_readout" for ref in record["provenance"]["input_refs"]))
        evidence = self._evidence(record)
        check = self._check(evidence, "evidence.vehicle_number.present")
        self.assertEqual(("UNKNOWN", "evidence.plate_readout_missing"), (check["outcome"], check["reason_code"]))
        self.assertEqual("UNKNOWN", evidence["overall"])
        # 실행 실패는 I4 관찰 fact가 아니다 — observed_false로 바꾸지 않으면 FINAL은 PASS/WARN이 아니다.
        final = self._final(record, self._facts(None))
        self.assertNotIn(final["overall"], {"PASS", "WARN"})
        with self.assertRaises(PackageNotReady):
            build_report_package(record, final, package_id="pkg_d3_failed",
                                 created_at="2026-08-24T18:26:00+09:00", asset_facts=self.assets)
        # 별도 실행 실패 notice(readout.plate_read_failed)는 case가 투영한다:
        # tests/case/test_plate_read_failure_projection.py


if __name__ == "__main__":
    unittest.main()
