"""이슈 #137 — Evidence public boundary가 세 verification 상태를 각각 어떻게 소비하는가.

`contract-visual-evidence.md` §4-1의 세 상태가 EvidenceRecord 조립 이전에 각각 다른
결말을 갖는다는 것을 고정한다. 특히 `NOT_OBSERVED`는 예외가 아니라 안정적인 비조립
결과이고, `UNCERTAIN`의 기존 대기/USER_UNSURE 규칙은 이 변경으로 바뀌지 않는다.
"""
from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from daesingo.evidence import (
    ASSEMBLE,
    AWAIT_SITUATION_RESPONSE,
    NOT_ASSEMBLED,
    ContractInputError,
    VisualEventNotAssembled,
    assemble_evidence,
    build_report_package,
    evaluate_requirements,
    render_report_draft,
    classify_visual_evidence,
)
from daesingo.evidence.disposition import NOT_OBSERVED_REASON
from daesingo.evidence.mock_integration import run_scenario

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = json.loads((ROOT / "tests/evidence/fixtures/adapter_inputs.json").read_text(encoding="utf-8"))["scenarios"]
USER_UNSURE = {"value": "USER_UNSURE", "responded_at": "2026-09-13T10:00:00+09:00", "candidate_ref": None}


class VisualEvidenceDispositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        happy = run_scenario(ROOT, "scenario_happy_001", CONFIGS["scenario_happy_001"])
        cls.time = happy["outputs"]["time_resolutions"][0]
        recording = json.loads((ROOT / "data/mock/recording/scenario_happy_001.json").read_text(encoding="utf-8"))
        search = json.loads((ROOT / "data/mock/search/scenario_happy_001.json").read_text(encoding="utf-8"))
        readout = json.loads((ROOT / "data/mock/readout/scenario_happy_001.json").read_text(encoding="utf-8"))
        cls.candidate = next(
            item
            for group in search["analysis_run_candidate_events"]
            for item in group["candidates"]
            if item["candidate_id"] == "candidate_h001"
        )
        cls.observed = next(item for item in search["visual_evidences"] if item["candidate_id"] == "candidate_h001")
        cls.plate_readout = readout["plate_readouts"][0]
        cls.assets = recording["asset_facts"]
        cls.incident_clip = recording["incident_clips"][0]

    def _visual(self, verification, visual_event_type):
        visual = deepcopy(self.observed)
        visual["verification"] = verification
        visual["visual_event_type"] = visual_event_type
        return visual

    def _assemble(self, visual, situation_response=None, corrections=()):
        return assemble_evidence(
            case_id="case_h001",
            selection_rev=1,
            candidate_event=self.candidate,
            visual_evidence=visual,
            time_resolution=self.time,
            plate_readout=self.plate_readout,
            incident_clip=self.incident_clip,
            record_id="ev_disposition_unit",
            situation_response=situation_response,
            correction_records=corrections,
        )

    # ── 1. OBSERVED + non-null type ────────────────────────────────────
    def test_observed_assembles_as_before(self):
        visual = self._visual("OBSERVED", "SOLID_LINE_LANE_CHANGE")

        self.assertEqual(ASSEMBLE, classify_visual_evidence(visual).decision)
        record = self._assemble(visual)
        self.assertEqual("SOLID_LINE_LANE_CHANGE", record["event"]["visual_event_type"]["value"])
        self.assertNotIn("situation_response", record)
        self.assertIsNotNone(render_report_draft(record))

    # ── 2. UNCERTAIN + null, 사용자 응답 전 ─────────────────────────────
    def test_uncertain_without_response_still_waits(self):
        visual = self._visual("UNCERTAIN", None)

        disposition = classify_visual_evidence(visual)
        self.assertEqual(AWAIT_SITUATION_RESPONSE, disposition.decision)
        # 기존 동작 유지 — 대기 상태에서 assemble을 강행하면 지금까지와 같은 계약 오류다.
        with self.assertRaises(ContractInputError):
            self._assemble(visual)

    def test_uncertain_does_not_assemble_on_confirmed_or_corrected(self):
        visual = self._visual("UNCERTAIN", None)
        for value in ("CONFIRMED", "CORRECTED"):
            with self.subTest(response=value):
                response = {**USER_UNSURE, "value": value,
                            "candidate_ref": {"kind": "candidate_event", "ref": self.candidate["candidate_id"]}}
                self.assertEqual(AWAIT_SITUATION_RESPONSE, classify_visual_evidence(visual, response).decision)
                with self.assertRaises(ContractInputError):
                    self._assemble(visual, response)

    def test_situation_change_updates_draft_package_type_and_expression(self):
        visual = self._visual("OBSERVED", "MOTORCYCLE_HELMET_NON_USE")
        before = self._assemble(visual)
        correction = {
            "contract_version": "correction-record/v1.2", "correction_id": "corr_597",
            "case_id": "case_h001", "selection_rev": 1, "kind": "SITUATION_CHANGE",
            "target_field": "event.visual_event_type", "previous_value": "MOTORCYCLE_HELMET_NON_USE",
            "new_value": "CENTER_LINE_CROSSING", "supersedes_ref": None,
            "corrected_at": "2026-08-24T18:24:00+09:00",
        }
        response = {"value": "CORRECTED", "responded_at": correction["corrected_at"],
                    "candidate_ref": before["basis"]["candidate_ref"]}
        corrected = self._assemble(visual, response, [correction])
        event = corrected["event"]
        self.assertEqual("CENTER_LINE_CROSSING", event["visual_event_type"]["value"])
        self.assertEqual("TRAFFIC_VIOLATION", event["safety_report_type"]["value"])
        self.assertNotEqual(before["event"]["safety_report_type"]["value"], event["safety_report_type"]["value"])
        self.assertIn("중앙선", event["violation_expression"]["value"])
        self.assertEqual(before["basis"], corrected["basis"])
        draft = render_report_draft(corrected)
        self.assertNotEqual(render_report_draft(before), draft)
        final = evaluate_requirements(
            corrected, scope="FINAL_PACKAGE", report_id="req_corrected",
            evaluated_at="2026-08-24T18:25:00+09:00", time_resolution=self.time, asset_facts=self.assets,
        )
        check = next(check for check in final["checks"] if check["code"] == "package.evidence.situation_response")
        self.assertEqual(("PASS", "evidence.situation_corrected"), (check["outcome"], check["reason_code"]))
        package = build_report_package(
            corrected, final, package_id="pkg_corrected",
            created_at="2026-08-24T18:26:00+09:00", asset_facts=self.assets,
        )
        self.assertEqual("교통위반(고속도로 포함)", package["report_inputs"]["safety_report_type"])
        self.assertEqual(event["violation_expression"]["value"], package["report_inputs"]["violation_expression"])
        self.assertEqual(draft, {key: package["report"][key] for key in ("title", "description")})

    def test_helmet_draft_matches_package_for_observed_and_corrected_types(self):
        helmet_type = "MOTORCYCLE_HELMET_NON_USE"
        observed = self._assemble(self._visual("OBSERVED", helmet_type))
        self.assertNotIn("situation_response", observed)

        solid_line = self._visual("OBSERVED", "SOLID_LINE_LANE_CHANGE")
        before = self._assemble(solid_line)
        correction = {
            "contract_version": "correction-record/v1.2", "correction_id": "corr_helmet",
            "case_id": "case_h001", "selection_rev": 1, "kind": "SITUATION_CHANGE",
            "target_field": "event.visual_event_type", "previous_value": "SOLID_LINE_LANE_CHANGE",
            "new_value": helmet_type, "supersedes_ref": None,
            "corrected_at": "2026-08-24T18:24:00+09:00",
        }
        response = {"value": "CORRECTED", "responded_at": correction["corrected_at"],
                    "candidate_ref": before["basis"]["candidate_ref"]}
        corrected = self._assemble(solid_line, response, [correction])

        for record, expected_reason in (
            (observed, "evidence.situation_observed_without_response"),
            (corrected, "evidence.situation_corrected"),
        ):
            with self.subTest(reason=expected_reason):
                self.assertEqual(helmet_type, record["event"]["visual_event_type"]["value"])
                draft = render_report_draft(record)
                self.assertIsNotNone(draft)
                self.assertEqual("이륜차 안전모 미착용 신고", draft["title"])
                self.assertIn(
                    "차량번호 12가3456의 이륜차 운전자 또는 탑승자가 안전모를 착용하지 않고 주행하는 것을 확인하여 신고합니다.",
                    draft["description"],
                )
                self.assertNotIn("차량이", draft["description"])
                final = evaluate_requirements(
                    record, scope="FINAL_PACKAGE", report_id="req_helmet",
                    evaluated_at="2026-08-24T18:25:00+09:00", time_resolution=self.time, asset_facts=self.assets,
                )
                check = next(check for check in final["checks"] if check["code"] == "package.evidence.situation_response")
                self.assertEqual(("PASS", expected_reason), (check["outcome"], check["reason_code"]))
                package = build_report_package(
                    record, final, package_id="pkg_helmet",
                    created_at="2026-08-24T18:26:00+09:00", asset_facts=self.assets,
                )
                self.assertEqual("이륜차 위반", package["report_inputs"]["safety_report_type"])
                self.assertEqual("12가3456", package["report_inputs"]["vehicle_number"])
                self.assertEqual(draft, {key: package["report"][key] for key in ("title", "description")})

    # ── 3. UNCERTAIN + null + USER_UNSURE ──────────────────────────────
    def test_uncertain_with_user_unsure_keeps_generic_path(self):
        visual = self._visual("UNCERTAIN", None)

        self.assertEqual(ASSEMBLE, classify_visual_evidence(visual, USER_UNSURE).decision)
        record = self._assemble(visual, situation_response=USER_UNSURE)
        self.assertIsNone(record["event"]["visual_event_type"]["value"])
        self.assertEqual("INFERRED", record["event"]["visual_event_type"]["source"]["observability"])
        self.assertTrue(record["event"]["safety_report_type"]["needs_review"])
        self.assertEqual("교통법규 위반 상황 확인 요청", render_report_draft(record)["title"])

    # ── 4. NOT_OBSERVED + null ─────────────────────────────────────────
    def test_not_observed_is_a_stable_non_assembly_result(self):
        visual = self._visual("NOT_OBSERVED", None)

        disposition = classify_visual_evidence(visual)

        self.assertEqual(NOT_ASSEMBLED, disposition.decision)
        self.assertEqual("NOT_OBSERVED", disposition.verification)
        self.assertEqual(NOT_OBSERVED_REASON, disposition.reason_code)
        self.assertFalse(disposition.assembles)
        # 분류 자체는 예외를 던지지 않는다 — 정상적인 negative Fine 결과이기 때문이다.
        self.assertEqual({"kind": "visual_evidence", "ref": "ve_h001"}, disposition.visual_evidence_ref)

    def test_not_observed_never_assembles_even_with_a_response(self):
        visual = self._visual("NOT_OBSERVED", None)
        for value in ("CONFIRMED", "CORRECTED", "USER_UNSURE"):
            with self.subTest(response=value):
                response = {**USER_UNSURE, "value": value,
                            "candidate_ref": {"kind": "candidate_event", "ref": self.candidate["candidate_id"]}}
                self.assertEqual(NOT_ASSEMBLED, classify_visual_evidence(visual, response).decision)
                with self.assertRaises(VisualEventNotAssembled):
                    self._assemble(visual, response)

    def test_direct_assemble_call_does_not_promote_not_observed(self):
        visual = self._visual("NOT_OBSERVED", None)

        with self.assertRaises(VisualEventNotAssembled) as caught:
            self._assemble(visual)

        self.assertEqual(NOT_OBSERVED_REASON, caught.exception.code)
        # 계약 위반이 아니다 — producer는 유효한 결과를 줬고 호출자가 분류를 건너뛴 것뿐이다.
        self.assertNotIsInstance(caught.exception, ContractInputError)

    # ── 5. NOT_OBSERVED + non-null type ────────────────────────────────
    def test_not_observed_with_a_visual_event_type_is_blocked(self):
        visual = self._visual("NOT_OBSERVED", "SOLID_LINE_LANE_CHANGE")

        with self.assertRaises(ContractInputError):
            classify_visual_evidence(visual)
        with self.assertRaises(ContractInputError):
            self._assemble(visual)

    def test_unknown_verification_is_blocked(self):
        with self.assertRaises(ContractInputError):
            classify_visual_evidence(self._visual("NEEDS_REVIEW", None))


if __name__ == "__main__":
    unittest.main()
