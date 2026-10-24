"""`search.hint_unclear` — #266 case 결정(1단계).

단서 구조화(`HINT_EXTRACT`)가 끝났지만 설명을 잘 이해하지 못한 경우 — `OK`인데 `confidence=low`이거나, 모델이
판단을 보류한 `ABSTAINED` — 결과 화면에 비차단 안내를 붙인다. 실행 실패(`FAILED`)는 #259 결정대로 notice가 없고,
빈 설명은 구조화를 건너뛰어 대상이 아니다. 「다시 적기」(`EDIT_HINT`)는 입력형 command 판본(PR #356) 전이라
`actions`를 비운다. 결과 화면(`stage`가 `SEARCHING` 뒤)에서만 붙인다(#224).
"""
from __future__ import annotations

import pytest

from daesingo.case import command, service
from daesingo.case.store import CaseStore
from daesingo.case.timeline_source import CaseTimeline

CODE = "search.hint_unclear"


class FakeTimelines:
    def timeline_for(self, sources):
        return CaseTimeline(timeline_id="tl_1", revision=1, duration_ms=10_000)


def _started(description: str = "흰 SUV가 끼어들었어요") -> tuple[CaseStore, str]:
    store = CaseStore()
    case_id = service.create_case(store=store)
    service.record_source_registered(
        case_id,
        {"source_asset_ref": "sa_0", "availability": "AVAILABLE", "duration_sec": 10.0},
        media_streams=[{"media_stream_ref": "ms_0", "media_type": "VIDEO"}],
        store=store,
    )
    request = {"case_id": case_id, "expected_case_rev": 1, "kind": "START_ANALYSIS", "payload": {"description": description}}
    assert command.execute_command(request, store=store, timelines=FakeTimelines()).response["ok"] is True
    return store, case_id


def _reflect(store: CaseStore, case_id: str, result: dict) -> None:
    case = store.get_case(case_id)
    job_id = next(r["job_id"] for r in case.job_records if r["kind"] == "HINT_EXTRACT")
    assert service.receive_hint_extraction_result(
        case_id, result, job_id=job_id, store=store, timelines=FakeTimelines()
    ).reflected


def _search_done(store: CaseStore, case_id: str) -> None:
    case = store.load_for_update(case_id)
    case.receive_candidates([])
    store.save(case)


def _codes(store: CaseStore, case_id: str) -> list[str]:
    return [n["code"] for n in service.get_view(case_id, store=store)["notices"]]


def test_notice_shape():
    assert service.HINT_UNCLEAR_NOTICE == {
        "code": CODE,
        "severity": "INFO",
        "blocking": False,
        "message_key": "notice.hint_unclear",
        "actions": [],
    }


@pytest.mark.parametrize(
    "result",
    [
        {"status": "OK", "vehicle_hint": "흰색 SUV", "confidence": "low"},
        {"status": "ABSTAINED", "confidence": "low"},
        {"status": "ABSTAINED"},
    ],
    ids=["ok_low", "abstained_low", "abstained_without_confidence"],
)
def test_unclear_result_shows_notice_on_result_screen(result):
    store, case_id = _started()
    _reflect(store, case_id, result)
    _search_done(store, case_id)

    assert CODE in _codes(store, case_id)


@pytest.mark.parametrize(
    "result",
    [
        {"status": "OK", "vehicle_hint": "흰색 SUV", "confidence": "high"},
        # confidence를 싣지 않은 결과는 low로 읽지 않는다 — 값을 지어내지 않는다.
        {"status": "OK", "vehicle_hint": "흰색 SUV"},
        # 실행 실패는 #259 결정대로 notice가 없다 — 사용자가 할 일이 없고, Runtime 원장으로 알아챈다.
        {"status": "FAILED", "confidence": "low"},
    ],
    ids=["ok_high", "ok_without_confidence", "failed"],
)
def test_no_notice_otherwise(result):
    store, case_id = _started()
    _reflect(store, case_id, result)
    _search_done(store, case_id)

    assert CODE not in _codes(store, case_id)


def test_no_notice_while_searching():
    # 진행 화면은 끝까지 흐르고 결과 화면에서 알린다(#224) — 과거형 문구(「넓게 찾았어요」)와도 맞는다.
    store, case_id = _started()
    _reflect(store, case_id, {"status": "ABSTAINED"})

    assert service.get_view(case_id, store=store)["stage"] == "SEARCHING"
    assert CODE not in _codes(store, case_id)


def test_blank_description_skips_extraction_and_notice():
    # 빈 설명은 구조화를 건너뛴다 — 이해할 문장이 없었으니 「이해하지 못했다」는 안내도 없다.
    store, case_id = _started(description="  ")
    _search_done(store, case_id)

    assert CODE not in _codes(store, case_id)


def test_shown_alongside_no_candidates():
    # 「왜 넓게 찾았는지」와 「결과 없음」은 뜻이 달라 둘 다 둔다.
    store, case_id = _started()
    _reflect(store, case_id, {"status": "OK", "vehicle_hint": "흰색 SUV", "confidence": "low"})
    _search_done(store, case_id)

    codes = _codes(store, case_id)
    assert "search.no_candidates" in codes
    assert CODE in codes


def test_derive_notices_needs_the_flag():
    view = {"stage": "CANDIDATE_REVIEW", "candidates": [], "progress": [], "notices": []}

    assert CODE not in [n["code"] for n in service.derive_notices(dict(view, notices=[]))["notices"]]
    assert CODE in [n["code"] for n in service.derive_notices(dict(view, notices=[]), hint_unclear=True)["notices"]]
