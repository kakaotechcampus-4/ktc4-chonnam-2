"""`evidence.event_time_missing` — #449 case 결정.

발동 조건: evidence가 조립됐고(`record_id` non-null — 응답 전 부분 투영이 아니다) `event_time_display.value`가
null일 때. 발생시각이 없으면 evidence가 Package를 만들지 않으므로 blocking이고, 출구는 입력형 command
`EDIT_EVENT_TIME`이다. 사용자가 시각을 입력하면 값이 생겨 사라진다.
"""
import copy
import json
from pathlib import Path

from daesingo.case import service
from daesingo.case.adapters import RealAdapter
from tests.case.test_input_commands import _evidence, _rebind, _send, _store

MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"
CODE = "evidence.event_time_missing"


def _view_without_time() -> dict:
    """`happy_001` rev4에서 발생시각만 없는 상태."""
    with open(MOCK_ROOT / "case" / "scenario_happy_001.json", encoding="utf-8") as fh:
        rev4 = next(v for v in json.load(fh)["case_views"] if v["case_rev"] == 4)
    view = copy.deepcopy(rev4)
    view["notices"] = []
    view["evidence"]["event_time_display"].update(value=None, info_state="INFO_UNKNOWN", source_label_key=None)
    return view


def _notice(view: dict) -> dict | None:
    return next((n for n in view["notices"] if n["code"] == CODE), None)


def test_notice_shape():
    assert service.EVENT_TIME_MISSING_NOTICE == {
        "code": CODE,
        "severity": "WARN",
        "blocking": True,
        "message_key": "notice.event_time_missing",
        "actions": ["EDIT_EVENT_TIME"],
    }


def test_notice_when_event_time_is_missing():
    assert _notice(service.derive_notices(_view_without_time())) is not None


def test_no_notice_when_event_time_exists():
    view = _view_without_time()
    view["evidence"]["event_time_display"]["value"] = "2026-08-24T18:06:00+09:00"
    assert _notice(service.derive_notices(view)) is None


def test_no_notice_on_partial_projection_before_response():
    # 응답 전 부분 투영은 시각을 아직 정하지 않았다 — 이유는 `case.situation_response_pending`이 나른다.
    view = _view_without_time()
    view["evidence"]["record_id"] = None
    assert _notice(service.derive_notices(view)) is None


def test_no_notice_without_evidence():
    view = _view_without_time()
    view["evidence"] = None
    assert _notice(service.derive_notices(view)) is None


class _TimeUnresolved(RealAdapter):
    """발생시각 출처가 모두 빈 결과 — 사용자 정정 전에는 EvidenceRecord에 `occurred_at`이 없다."""

    def get_evidence_record(self):
        record = super().get_evidence_record()
        if record is not None and not any(c["target_field"] == "occurred_at" for c in self._case.correction_records):
            record = {k: v for k, v in record.items() if k != "occurred_at"}
        return record


def test_edit_event_time_clears_the_notice():
    store, case_id = _store()
    store.adapters.put(case_id, _rebind(store, case_id, _TimeUnresolved))
    assert _evidence(store, case_id)["event_time_display"]["value"] is None
    assert _notice(service.get_view(case_id, store=store)) is not None

    result = _send(store, case_id, "EDIT_EVENT_TIME", {"value": "2026-08-24T18:06:00+09:00"})

    assert result.response["ok"] is True
    assert result.response["case_view"]["evidence"]["event_time_display"]["value"] == "2026-08-24T18:06:00+09:00"
    assert _notice(result.response["case_view"]) is None
