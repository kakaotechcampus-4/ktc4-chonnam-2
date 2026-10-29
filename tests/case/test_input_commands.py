"""입력형 command(case-command 계약 §12, W12 C3) — 번호판 직접 입력 · 발생시각 수정 · `[다른 상황]`.

web은 새 값만 보내고 CorrectionRecord의 나머지는 case가 채운다(§12-2). 기록 전에 evidence 검사
(`validate_correction_append`, #235 E-3)를 부르고, 사용자가 고칠 수 있는 값 오류만 `invalid_value`다(§12-4).
정정 → Evidence → CaseView 경로는 mock 원본으로 evidence를 다시 조립하는 `RealAdapter`로 본다.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from daesingo.case import command, correction, jobs, service
from daesingo.case.adapters import MockFixtureAdapter, RealAdapter
from daesingo.case.domain import Candidate, CaseAggregate
from daesingo.case.store import CaseStore
from daesingo.evidence import ContractInputError

MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"
CASE_ID = "case_input001"


def _store() -> tuple[CaseStore, str]:
    """happy_001 원본으로 첫 후보를 고른 `EVIDENCE_REVIEW` case — 번호판 `12가3456`, 유형 `SOLID_LINE_LANE_CHANGE`."""
    scope = MockFixtureAdapter(MOCK_ROOT, "happy_001").get_analysis_scopes()[0]
    case = CaseAggregate.intake(case_id=CASE_ID, hints={}, manifest_summary={})
    real = RealAdapter(case_id=CASE_ID, case=case, search_scope=scope, mock_root=MOCK_ROOT)
    case.start_search()
    jobs.issue_coarse_search(case, scope_ref="scope_h001", input_fingerprint="sha1:h001-coarse-search")
    candidates = service.receive_search_candidates(case, real)
    case.select_candidate(candidates[0].candidate_id)
    store = CaseStore()
    store.register(case, real)
    return store, CASE_ID


def _send(store: CaseStore, case_id: str, kind: str, payload: dict) -> command.CommandResult:
    rev = store.get_case(case_id).case_rev
    request = {"case_id": case_id, "expected_case_rev": rev, "kind": kind, "payload": payload}
    return command.execute_command(request, store=store)


def _evidence(store: CaseStore, case_id: str) -> dict:
    return service.get_view(case_id, store=store)["evidence"]


def _state(store: CaseStore, case_id: str) -> dict:
    case = store.get_case(case_id)
    return copy.deepcopy(
        {
            "case_rev": case.case_rev,
            "stage": case.stage,
            "situation_response": case.situation_response,
            "correction_records": case.correction_records,
            "job_records": case.job_records,
        }
    )


def _rejected(result: command.CommandResult, code: str) -> None:
    assert result.response["ok"] is False
    assert result.response["error"]["code"] == code
    assert result.response["case_view"] is not None


# ── 번호판 직접 입력 ───────────────────────────────────────────────────────────


def test_manual_plate_input_records_correction_and_reaches_evidence():
    store, case_id = _store()
    before = _evidence(store, case_id)["plate_display"]["value"]
    rev = store.get_case(case_id).case_rev

    result = _send(store, case_id, "MANUAL_PLATE_INPUT", {"value": "34나5678"})

    assert result.response["ok"] is True
    assert result.appended_job_records == []  # 값 정정은 발주하지 않는다(§12-2)
    record = store.get_case(case_id).correction_records[-1]
    assert record["contract_version"] == "correction-record/v1.2"
    assert (record["kind"], record["target_field"]) == ("PLATE_MANUAL_EDIT", "vehicle_number")
    assert (record["previous_value"], record["new_value"]) == (before, "34나5678")
    assert record["supersedes_ref"] is None
    view = result.response["case_view"]
    assert view["case_rev"] == rev + 1
    assert view["evidence"]["plate_display"]["value"] == "34나5678"
    assert view["evidence"]["plate_display"]["info_state"] == "INFO_USER_CONFIRMED"


def test_second_input_supersedes_first_with_its_value():
    store, case_id = _store()
    _send(store, case_id, "MANUAL_PLATE_INPUT", {"value": "34나5678"})

    assert _send(store, case_id, "MANUAL_PLATE_INPUT", {"value": "56다7890"}).response["ok"] is True

    first, second = store.get_case(case_id).correction_records
    assert second["previous_value"] == first["new_value"]
    assert second["supersedes_ref"] == {"kind": "correction_record", "ref": first["correction_id"]}
    assert _evidence(store, case_id)["plate_display"]["value"] == "56다7890"


def test_same_value_as_current_is_not_allowed():
    store, case_id = _store()
    current = _evidence(store, case_id)["plate_display"]["value"]
    before = _state(store, case_id)

    _rejected(_send(store, case_id, "MANUAL_PLATE_INPUT", {"value": current}), "case.command.not_allowed")
    assert _state(store, case_id) == before


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_plate_is_invalid_value_and_records_nothing(value):
    """번호판을 지우는 값은 evidence 값 공간 밖이다(correction-record §6) — 다시 입력하면 고쳐지는 값 오류."""
    store, case_id = _store()
    before = _state(store, case_id)

    _rejected(_send(store, case_id, "MANUAL_PLATE_INPUT", {"value": value}), "case.command.invalid_value")
    assert _state(store, case_id) == before


class _PlateUnread(RealAdapter):
    """번호판을 읽지 못한 결과 — EvidenceRecord에 `vehicle_number`가 없다."""

    def get_evidence_record(self):
        record = super().get_evidence_record()
        if record is not None and not any(
            c["target_field"] == "vehicle_number" for c in self._case.correction_records
        ):
            record = {k: v for k, v in record.items() if k != "vehicle_number"}
        return record


def test_first_input_without_plate_records_null_previous_value():
    """값이 없던 상태의 첫 입력은 `previous_value=null`이다(correction-record v1.2, #235 E-1 · E-2)."""
    store, case_id = _store()
    store.adapters.put(case_id, _rebind(store, case_id, _PlateUnread))
    assert _evidence(store, case_id)["plate_display"]["value"] is None

    assert _send(store, case_id, "MANUAL_PLATE_INPUT", {"value": "34나5678"}).response["ok"] is True

    assert store.get_case(case_id).correction_records[-1]["previous_value"] is None


def _rebind(store: CaseStore, case_id: str, cls: type[RealAdapter]) -> RealAdapter:
    adapter = store.adapter_for(store.get_case(case_id))
    adapter.__class__ = cls
    return adapter


# ── 발생시각 수정 ──────────────────────────────────────────────────────────────


def test_edit_event_time_records_event_time_manual():
    store, case_id = _store()
    before = _evidence(store, case_id)["event_time_display"]["value"]

    result = _send(store, case_id, "EDIT_EVENT_TIME", {"value": "2026-08-24T18:06:00+09:00"})

    assert result.response["ok"] is True
    record = store.get_case(case_id).correction_records[-1]
    assert (record["kind"], record["target_field"]) == ("EVENT_TIME_MANUAL", "occurred_at")
    assert (record["previous_value"], record["new_value"]) == (before, "2026-08-24T18:06:00+09:00")
    assert result.response["case_view"]["evidence"]["event_time_display"]["value"] == "2026-08-24T18:06:00+09:00"


@pytest.mark.parametrize("value", ["2026-08-24T18:06:00", "어제 저녁", ""])
def test_time_without_offset_is_invalid_value_and_records_nothing(value):
    """사용자가 다시 입력하면 고쳐지는 값 오류 — 아무것도 기록하지 않는다(§12-4)."""
    store, case_id = _store()
    before = _state(store, case_id)

    result = _send(store, case_id, "EDIT_EVENT_TIME", {"value": value})

    _rejected(result, "case.command.invalid_value")
    assert result.response["error"]["message_key"] == "command.invalid_value"
    assert _state(store, case_id) == before


# ── [다른 상황] ────────────────────────────────────────────────────────────────


def test_corrected_records_situation_change_and_response_in_one_revision():
    store, case_id = _store()
    rev = store.get_case(case_id).case_rev

    result = _send(
        store, case_id, "RECORD_SITUATION_RESPONSE", {"value": "CORRECTED", "visual_event_type": "CENTER_LINE_CROSSING"}
    )

    assert result.response["ok"] is True
    case = store.get_case(case_id)
    # 정정과 응답이 각자 올리지 않는다(§12-3). 응답으로 Package가 풀려 READY로 오르면 그 전이가 한 번 더 올린다(§5).
    assert case.case_rev == rev + 1 + (case.stage == "READY")
    assert case.situation_response["value"] == "CORRECTED"
    record = case.correction_records[-1]
    assert (record["kind"], record["target_field"]) == ("SITUATION_CHANGE", "event.visual_event_type")
    assert (record["previous_value"], record["new_value"]) == ("SOLID_LINE_LANE_CHANGE", "CENTER_LINE_CROSSING")
    evidence = result.response["case_view"]["evidence"]
    assert evidence["case_type_display"]["code"] == "CENTER_LINE_CROSSING"


def test_corrected_twice_chains_on_the_previous_correction():
    store, case_id = _store()
    _send(store, case_id, "RECORD_SITUATION_RESPONSE", {"value": "CORRECTED", "visual_event_type": "CENTER_LINE_CROSSING"})

    result = _send(store, case_id, "RECORD_SITUATION_RESPONSE", {"value": "CORRECTED", "visual_event_type": "SIGNAL"})

    assert result.response["ok"] is True
    first, second = store.get_case(case_id).correction_records
    assert second["previous_value"] == "CENTER_LINE_CROSSING"
    assert second["supersedes_ref"]["ref"] == first["correction_id"]


@pytest.mark.parametrize(
    "payload",
    [
        {"value": "CORRECTED"},
        {"value": "CONFIRMED", "visual_event_type": "SIGNAL"},
        {"value": "USER_UNSURE", "visual_event_type": "SIGNAL"},
    ],
)
def test_visual_event_type_only_with_corrected(payload):
    store, case_id = _store()
    before = _state(store, case_id)

    _rejected(_send(store, case_id, "RECORD_SITUATION_RESPONSE", payload), "case.command.invalid_payload")
    assert _state(store, case_id) == before


def test_unknown_visual_event_type_is_invalid_value():
    """값 공간은 evidence가 판단한다 — case가 4종 목록을 복제하지 않는다(§12-2)."""
    store, case_id = _store()
    before = _state(store, case_id)

    result = _send(store, case_id, "RECORD_SITUATION_RESPONSE", {"value": "CORRECTED", "visual_event_type": "SPEEDING"})

    _rejected(result, "case.command.invalid_value")
    assert _state(store, case_id) == before


def test_corrected_to_the_current_type_is_not_allowed():
    """지금 값과 같은 유형은 `[맞아요]`다(§12-3)."""
    store, case_id = _store()
    before = _state(store, case_id)

    result = _send(
        store, case_id, "RECORD_SITUATION_RESPONSE", {"value": "CORRECTED", "visual_event_type": "SOLID_LINE_LANE_CHANGE"}
    )

    _rejected(result, "case.command.not_allowed")
    assert _state(store, case_id) == before


def test_unsure_after_corrected_is_not_allowed():
    """`[다른 상황]` 정정이 있는 후보에 「잘 모르겠어요」를 받으면 evidence가 조립하지 않는다 — 정정은 지우지 않으므로 막는다."""
    store, case_id = _store()
    _send(store, case_id, "RECORD_SITUATION_RESPONSE", {"value": "CORRECTED", "visual_event_type": "SIGNAL"})
    before = _state(store, case_id)

    _rejected(_send(store, case_id, "RECORD_SITUATION_RESPONSE", {"value": "USER_UNSURE"}), "case.command.not_allowed")
    assert _state(store, case_id) == before
    assert _evidence(store, case_id)["case_type_display"]["code"] == "SIGNAL"


def test_confirmed_after_corrected_keeps_the_corrected_type():
    store, case_id = _store()
    _send(store, case_id, "RECORD_SITUATION_RESPONSE", {"value": "CORRECTED", "visual_event_type": "SIGNAL"})

    assert _send(store, case_id, "RECORD_SITUATION_RESPONSE", {"value": "CONFIRMED"}).response["ok"] is True
    assert _evidence(store, case_id)["case_type_display"]["code"] == "SIGNAL"


# ── 허용 상태 ──────────────────────────────────────────────────────────────────


def _candidate(cid: str) -> Candidate:
    return Candidate(candidate_id=cid, at=None, at_provenance=None, observed="", thumb_ref=None, rank=1)


@pytest.mark.parametrize(
    ("kind", "payload"),
    [
        ("MANUAL_PLATE_INPUT", {"value": "34나5678"}),
        ("EDIT_EVENT_TIME", {"value": "2026-08-24T18:06:00+09:00"}),
        ("RECORD_SITUATION_RESPONSE", {"value": "CORRECTED", "visual_event_type": "SIGNAL"}),
    ],
)
def test_before_selection_is_not_allowed(kind, payload):
    case = CaseAggregate.intake(case_id="case_input_nosel", hints={}, manifest_summary={})
    case.start_search()
    case.receive_candidates([_candidate("cand_a")])
    store = CaseStore()
    store.register(case, MockFixtureAdapter(MOCK_ROOT, "happy_001"))

    _rejected(_send(store, case.case_id, kind, payload), "case.command.not_allowed")
    assert store.get_case(case.case_id).correction_records == []


class _NoEvidence(RealAdapter):
    def get_evidence_record(self):
        return None


def test_without_evidence_on_screen_is_not_allowed():
    """값 칸이 없는 화면(관찰 전 · 음성 결과)은 사용자가 본 이전 값이 없다."""
    store, case_id = _store()
    store.adapters.put(case_id, _rebind(store, case_id, _NoEvidence))
    assert _evidence(store, case_id) is None
    before = _state(store, case_id)

    _rejected(_send(store, case_id, "MANUAL_PLATE_INPUT", {"value": "34나5678"}), "case.command.not_allowed")
    assert _state(store, case_id) == before


def test_correction_in_ready_returns_to_evidence_review():
    store, case_id = _store()
    case = store.load_for_update(case_id)
    case.stage = "READY"
    store.save(case)

    result = _send(store, case_id, "MANUAL_PLATE_INPUT", {"value": "34나5678"})

    assert result.response["ok"] is True
    assert result.response["case_view"]["stage"] in {"EVIDENCE_REVIEW", "READY"}  # 성공 뒤 READY 재확인(§5)
    assert store.get_case(case_id).correction_records[-1]["kind"] == "PLATE_MANUAL_EDIT"


def test_internal_contract_violation_is_not_an_input_error():
    """case가 만든 레코드의 위반(여기서는 저장된 chain이 계약을 어긴 상태)은 사용자 입력 오류가 아니다 — command 실패 코드로
    바꾸지 않고 배선 오류로 올린다(§12-4). 아무것도 기록하지 않는다."""
    case = CaseAggregate.intake(case_id="case_input_bad", hints={}, manifest_summary={})
    case.start_search()
    case.receive_candidates([_candidate("cand_a")])
    case.select_candidate("cand_a")
    correction.apply_correction(
        case, kind="PLATE_MANUAL_EDIT", target_field="vehicle_number", previous_value="12가3456", new_value="34나5678"
    )
    case.correction_records[-1]["new_value"] = 123  # 저장된 레코드가 계약을 어긴다
    rev = case.case_rev

    with pytest.raises(ContractInputError) as raised:
        correction.apply_correction(
            case, kind="EVENT_TIME_MANUAL", target_field="occurred_at",
            previous_value=None, new_value="2026-08-24T18:06:00+09:00",
        )

    assert type(raised.value) is ContractInputError  # `InvalidCorrectionValue`(→ invalid_value)가 아니다
    assert len(case.correction_records) == 1
    assert case.case_rev == rev


# ── notice ─────────────────────────────────────────────────────────────────────


def test_plate_abstained_notice_offers_manual_input():
    assert service.PLATE_ABSTAINED_NOTICE["actions"] == ["MANUAL_PLATE_INPUT"]
