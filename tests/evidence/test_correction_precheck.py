"""#235 — CorrectionRecord `previous_value=null`(E-1 · E-2)과 기록 전 검사(E-3).

- E-1 · E-2: 값이 없던 상태의 첫 입력은 `previous_value=null`이다. `occurred_at` · `vehicle_number` ·
  `location.coord`도 이전 값 `null`을 받고, `new_value`는 target 값 공간 그대로 non-null이다
  (`correction-record/v1.2` §6).
- E-3: case는 기록하기 전에 `validate_correction_append()`를 부른다. 값만 틀리면
  `InvalidCorrectionValue`(사용자가 다시 입력해 고칠 수 있음), case가 채운 나머지(chain · kind/target ·
  이전 값 · 구조)나 이미 기록된 위반이면 `ContractInputError`다(ADR-EVIDENCE-011).
- 이미 기록된 위반 정정은 건너뛰거나 고치지 않고 계약 오류로 남는다(#235 E-3 Evidence 결정).
"""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from daesingo.evidence import (
    ContractInputError,
    InvalidCorrectionValue,
    correction_heads,
    resolve_independent_facts,
    resolve_time,
    validate_correction_append,
)

ROOT = Path(__file__).resolve().parents[2]
_NON_NULL_NEW = {
    "occurred_at": ("EVENT_TIME_MANUAL", "2026-08-24T18:22:00+09:00"),
    "vehicle_number": ("PLATE_MANUAL_EDIT", "55나5555"),
    "location.coord": ("REPORT_TYPE_CHANGE", {"lat": 35.2, "lon": 126.2}),
}


def _correction(correction_id, target, previous, new, *, kind="REPORT_TYPE_CHANGE", supersedes=None,
                selection_rev=1, case_id="case_h001", version="correction-record/v1.2"):
    return {
        "contract_version": version,
        "correction_id": correction_id,
        "case_id": case_id,
        "selection_rev": selection_rev,
        "kind": kind,
        "target_field": target,
        "previous_value": previous,
        "new_value": new,
        "supersedes_ref": None if supersedes is None else {"kind": "correction_record", "ref": supersedes},
        "corrected_at": "2026-09-13T10:00:00+09:00",
    }


class NullablePreviousValueTests(unittest.TestCase):
    """E-1 · E-2 — 읽는 쪽(`correction_heads`)이 v1.2를 받는다."""

    def test_first_input_from_no_value_is_accepted_for_the_three_non_null_paths(self):
        for target, (kind, new) in _NON_NULL_NEW.items():
            with self.subTest(target=target):
                record = _correction(f"corr_{target}", target, None, new, kind=kind)
                heads = correction_heads([record], case_id="case_h001", selection_rev=1)
                self.assertEqual(new, heads[target]["new_value"])

    def test_a_v1_1_record_does_not_get_null_previous_retroactively(self):
        # v1.1에서 이전 값 null은 위반이었다 — 이미 기록된 위반은 고쳐 읽지 않는다(#235 E-3).
        for target, (kind, new) in _NON_NULL_NEW.items():
            for version in ("correction-record/v1.1", None):
                with self.subTest(target=target, version=version):
                    record = _correction(f"corr_{target}", target, None, new, kind=kind, version=version)
                    with self.assertRaisesRegex(ContractInputError, f"invalid previous_value for {target}"):
                        correction_heads([record], case_id="case_h001", selection_rev=1)

    def test_v1_1_paths_that_already_took_null_are_unchanged(self):
        record = _correction("corr_place", "location.place_name", None, "수정 장소", version="correction-record/v1.1")
        self.assertIn("location.place_name", correction_heads([record], case_id="case_h001", selection_rev=1))

    def test_new_value_stays_non_null_for_the_three_paths(self):
        for target, (kind, new) in _NON_NULL_NEW.items():
            with self.subTest(target=target):
                record = _correction(f"corr_{target}", target, new, None, kind=kind)
                with self.assertRaisesRegex(ContractInputError, f"invalid new_value for {target}"):
                    correction_heads([record], case_id="case_h001", selection_rev=1)

    def test_chain_from_null_continues_with_the_first_input(self):
        first = _correction("corr_1", "vehicle_number", None, "11가1111", kind="PLATE_MANUAL_EDIT")
        second = _correction("corr_2", "vehicle_number", "11가1111", "22나2222", kind="PLATE_MANUAL_EDIT", supersedes="corr_1")
        heads = correction_heads([first, second], case_id="case_h001", selection_rev=1)
        self.assertEqual("corr_2", heads["vehicle_number"]["correction_id"])

    def test_a_malformed_previous_value_is_still_rejected(self):
        record = _correction("corr_time", "occurred_at", "2026-08-24 18:21:44", "2026-08-24T18:22:00+09:00", kind="EVENT_TIME_MANUAL")
        with self.assertRaisesRegex(ContractInputError, "invalid previous_value for occurred_at"):
            correction_heads([record], case_id="case_h001", selection_rev=1)


class AppendPrecheckTests(unittest.TestCase):
    """E-3 — 기록 전 검사와 두 부류의 거부."""

    def setUp(self):
        self.plate = _correction("corr_plate_1", "vehicle_number", None, "11가1111", kind="PLATE_MANUAL_EDIT")

    def test_a_valid_correction_passes_and_becomes_the_head_once_appended(self):
        follow_up = _correction("corr_plate_2", "vehicle_number", "11가1111", "22나2222",
                                kind="PLATE_MANUAL_EDIT", supersedes="corr_plate_1")
        self.assertIsNone(validate_correction_append(self.plate, existing_records=[]))
        self.assertIsNone(validate_correction_append(follow_up, existing_records=[self.plate]))
        heads = correction_heads([self.plate, follow_up], case_id="case_h001", selection_rev=1)
        self.assertEqual("corr_plate_2", heads["vehicle_number"]["correction_id"])

    def test_a_value_outside_the_target_value_space_is_a_user_fixable_rejection(self):
        cases = {
            "occurred_at without offset": ("occurred_at", "EVENT_TIME_MANUAL", "2026-08-24T18:22:00"),
            "occurred_at not a string": ("occurred_at", "EVENT_TIME_MANUAL", 1724491320),
            "occurred_at erased": ("occurred_at", "EVENT_TIME_MANUAL", None),
            "plate not a string": ("vehicle_number", "PLATE_MANUAL_EDIT", 123),
            "plate erased": ("vehicle_number", "PLATE_MANUAL_EDIT", None),
            "unknown visual event type": ("event.visual_event_type", "SITUATION_CHANGE", "NOT_A_TYPE"),
            "expression too short": ("event.violation_expression", "REPORT_TYPE_CHANGE", "짧음"),
            "coord without lon": ("location.coord", "REPORT_TYPE_CHANGE", {"lat": 35.2}),
        }
        for label, (target, kind, value) in cases.items():
            with self.subTest(label):
                record = _correction("corr_new", target, None, value, kind=kind)
                with self.assertRaises(InvalidCorrectionValue) as caught:
                    validate_correction_append(record, existing_records=[])
                self.assertEqual(target, caught.exception.target_field)
                # 같은 위반이 기록돼 있었다면 읽는 쪽은 계약 오류로 본다 — 하위 타입이라 기존 처리와 맞는다.
                self.assertIsInstance(caught.exception, ContractInputError)

    def test_what_case_built_is_an_internal_contract_error_not_a_value_error(self):
        plate = "PLATE_MANUAL_EDIT"
        cases = {
            "supersedes a missing record": (
                [], _correction("c", "vehicle_number", "11가1111", "22나2222", kind=plate, supersedes="corr_gone")),
            "supersedes another target": (
                [self.plate], _correction("c", "location.address", "11가1111", "주소", supersedes="corr_plate_1")),
            "chain values discontinuous": (
                [self.plate], _correction("c", "vehicle_number", "99하9999", "22나2222", kind=plate, supersedes="corr_plate_1")),
            "second head in one context": (
                [self.plate], _correction("c", "vehicle_number", "11가1111", "22나2222", kind=plate)),
            "unknown kind": (
                [], _correction("c", "vehicle_number", None, "22나2222", kind="NOT_A_KIND")),
            "SITUATION_CHANGE on a non-event path": (
                [], _correction("c", "vehicle_number", None, "22나2222", kind="SITUATION_CHANGE")),
            "occurred_at without EVENT_TIME_MANUAL": (
                [], _correction("c", "occurred_at", None, "2026-08-24T18:22:00+09:00", kind="TIME_HINT_EDIT")),
            "no change": (
                [], _correction("c", "vehicle_number", "22나2222", "22나2222", kind=plate)),
            "malformed previous value": (
                [], _correction("c", "vehicle_number", 123, "22나2222", kind=plate)),
            "reused correction_id": (
                [self.plate], _correction("corr_plate_1", "location.address", None, "주소")),
            "bad selection_rev": (
                [], _correction("c", "vehicle_number", None, "22나2222", kind=plate, selection_rev=0)),
            "missing case_id": (
                [], _correction("c", "vehicle_number", None, "22나2222", kind=plate, case_id=None)),
            "null previous labelled v1.1": (
                [], _correction("c", "vehicle_number", None, "22나2222", kind=plate, version="correction-record/v1.1")),
        }
        for label, (existing, record) in cases.items():
            with self.subTest(label):
                with self.assertRaises(ContractInputError) as caught:
                    validate_correction_append(record, existing_records=existing)
                self.assertNotIsInstance(caught.exception, InvalidCorrectionValue)

    def test_a_stored_violation_is_not_skipped_or_repaired(self):
        # #235 E-3: 이미 기록된 위반은 조용히 무시하지 않는다 — 다른 target의 새 정정도 그 case에서는 거부된다.
        stored = _correction("corr_bad", "occurred_at", None, "not-a-time", kind="EVENT_TIME_MANUAL")
        record = _correction("corr_plate", "vehicle_number", None, "22나2222", kind="PLATE_MANUAL_EDIT")
        with self.assertRaisesRegex(ContractInputError, "invalid new_value for occurred_at") as caught:
            validate_correction_append(record, existing_records=[stored])
        self.assertNotIsInstance(caught.exception, InvalidCorrectionValue)

    def test_a_new_selection_context_starts_its_own_chain(self):
        # #173 E-1: 새 후보의 첫 정정은 supersedes_ref=null — 이전 context의 head와 겹치지 않는다.
        record = _correction("corr_rev2", "vehicle_number", None, "22나2222", kind="PLATE_MANUAL_EDIT", selection_rev=2)
        self.assertIsNone(validate_correction_append(record, existing_records=[self.plate]))

    def test_other_cases_are_not_mixed_into_the_chain(self):
        other = _correction("corr_other", "vehicle_number", None, "33다3333", kind="PLATE_MANUAL_EDIT", case_id="case_other")
        self.assertIsNone(validate_correction_append(self.plate, existing_records=[other]))

    def test_case_namespace_targets_are_not_evidence_values(self):
        hints = _correction("corr_hints", "hints", {"time": None}, {"time": "저녁 6시쯤"}, kind="TIME_HINT_EDIT")
        self.assertIsNone(validate_correction_append(hints, existing_records=[]))

    def test_inputs_are_not_mutated(self):
        follow_up = _correction("corr_plate_2", "vehicle_number", "11가1111", "22나2222",
                                kind="PLATE_MANUAL_EDIT", supersedes="corr_plate_1")
        existing = [self.plate]
        before = deepcopy((existing, follow_up))
        validate_correction_append(follow_up, existing_records=existing)
        self.assertEqual(before, (existing, follow_up))


class AwaitingResponseCorrectionTests(unittest.TestCase):
    """#234 「응답 대기 중 정정」 — 값이 없던 번호판 · 시각을 직접 입력해도 부분 투영이 계속 만들어진다."""

    @classmethod
    def setUpClass(cls):
        def load(module):
            return json.loads((ROOT / f"data/mock/{module}/scenario_happy_001.json").read_text(encoding="utf-8"))

        search = load("search")
        cls.candidate = next(
            item for group in search["analysis_run_candidate_events"] for item in group["candidates"]
            if item["candidate_id"] == "candidate_h001"
        )

    def test_first_inputs_from_no_value_project_as_user_corrected(self):
        corrections = [
            _correction("corr_plate", "vehicle_number", None, "55나5555", kind="PLATE_MANUAL_EDIT"),
            _correction("corr_time", "occurred_at", None, "2026-08-24T18:22:00+09:00", kind="EVENT_TIME_MANUAL"),
        ]
        recorded = []
        for record in corrections:
            validate_correction_append(record, existing_records=recorded)
            recorded.append(record)
        # 판독 실행 실패(PlateReadout=None) · 시각 후보 없음 — 두 값 모두 이전에는 없었다.
        time = resolve_time(
            time_source_candidates=[], overlay_time_readout=None, candidate_event=self.candidate,
            correction_records=recorded, case_id="case_h001", selection_rev=1, resolution_id="tr_null_prev",
        )
        facts = resolve_independent_facts(
            case_id="case_h001", selection_rev=1, time_resolution=time, plate_readout=None,
            correction_records=recorded,
        )
        self.assertEqual(("55나5555", True), (facts["vehicle_number"]["value"], facts["vehicle_number"]["user_corrected"]))
        self.assertEqual(("2026-08-24T18:22:00+09:00", True), (facts["occurred_at"]["value"], facts["occurred_at"]["user_corrected"]))
        self.assertEqual({"kind": "correction_record", "ref": "corr_time"}, time["provenance"]["selected_input_ref"])


if __name__ == "__main__":
    unittest.main()
