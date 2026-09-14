"""CaseView 표시용 label·info_state 파생 규칙.

⚠️ label 매핑 표만 placeholder다(`EVENT_TYPE_LABELS`/`REPORT_TYPE_LABELS`) — 전체
enum→label 매핑은 이 모듈이 새로 설계하는 게 아니라 evidence/registry 쪽 공용 값 공간
(`docs/mock/01_mock_dataset_overview.md` §4-6번 참고 — 아직 어느 Final Contract에도
등재돼 있지 않다고 명시된 gap)을 참조해야 한다. registry가 생기기 전까지 case의
projection 코드가 죽지 않게 하는 placeholder다.

info_state 파생 규칙(`evidence_value_info_state`/`occurred_at_info_state`/
`location_representative`)은 placeholder가 아니다 — `contract-job-record-case-view.md`
B절 §7 원문(2026-09-14, 이슈 #47/#48 후속으로 `scenario_unknown_abstain_partial_001`
전체 파리티 작업 중 정식 구현)을 그대로 옮긴 것이다.
"""
from __future__ import annotations

from typing import Any

# event.visual_event_type.value → 사용자 표시용 한글 label
EVENT_TYPE_LABELS: dict[str, str] = {
    "SOLID_LINE_LANE_CHANGE": "백색 실선 구간 차로변경",
    "SIGNAL": "신호 위반",  # scenario_plate_reread_001로 확인(2026-09-14)
    "MOTORCYCLE_HELMET_NON_USE": "이륜차 안전모 미착용",  # scenario_correction_rerun_001로 확인(2026-09-14)
}

# event.safety_report_type.value → 사용자 표시용 한글 label
REPORT_TYPE_LABELS: dict[str, str] = {
    "TRAFFIC_VIOLATION": "교통위반(고속도로 포함)",
    "MOTORCYCLE_VIOLATION": "이륜차 위반",  # scenario_correction_rerun_001로 확인(2026-09-14)
}

# EvidenceValue.source.observability → CaseView *_display.info_state (규칙 (1)의 마지막 단계)
_OBSERVABILITY_TO_INFO_STATE: dict[str, str] = {
    "OBSERVED": "INFO_SOURCE_VERIFIED",
    "INFERRED": "INFO_AI_ESTIMATED",
}

# B절 §7-(3) location 대표값 후보 우선순위. 존재하는 첫 값 하나를 쓴다.
_LOCATION_CANDIDATE_KEYS: tuple[str, ...] = ("address", "place_name", "user_hint")


def observability_to_info_state(observability: str | None) -> str:
    """observability가 미등록 값이면 INFO_UNKNOWN으로 떨어뜨린다(조용히 단정하지 않는다)."""
    return _OBSERVABILITY_TO_INFO_STATE.get(observability or "", "INFO_UNKNOWN")


def evidence_value_info_state(
    value: Any,
    *,
    needs_review: bool,
    user_corrected: bool,
    observability: str | None,
) -> str:
    """B절 §7-(1) `EvidenceValue` 기반 display 공통 규칙 — 5단계 우선순위.

    `case_type_display`(← `visual_event_type`) · `report_type_display`(← `safety_report_type`) ·
    `violation_display`(← `violation_expression`) · `plate_display`(← `vehicle_number`), 그리고
    `location_display` 대표값이 `user_hint`가 아닐 때(§7-(3))가 이 규칙을 쓴다.
    `value == null`이 `user_corrected`/`needs_review`보다 먼저 검사된다 — evidence가
    「`value=null`과 `needs_review=true` 동시 발생 금지」를 보장하므로 순서가 바뀌어도
    결과는 같지만, 계약 원문의 우선순위를 그대로 코드에 남긴다.
    """
    if value is None:
        return "INFO_UNKNOWN"
    if user_corrected:
        return "INFO_USER_CONFIRMED"
    if needs_review:
        return "INFO_NEEDS_REVIEW"
    return observability_to_info_state(observability)


def occurred_at_info_state(occurred_at: dict[str, Any] | None) -> str:
    """B절 §7-(2) — `occurred_at`은 `EvidenceValue`가 아니라 별도 구조라 규칙이 다르다
    (`{value, resolution_status, user_corrected, source}`, `needs_review` 필드가 없다).
    """
    if occurred_at is None:
        return "INFO_UNKNOWN"
    if occurred_at.get("user_corrected"):
        return "INFO_USER_CONFIRMED"
    if occurred_at.get("resolution_status") == "OK":
        return "INFO_SOURCE_VERIFIED"
    return "INFO_NEEDS_REVIEW"


def location_representative(location: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str | None]:
    """B절 §7-(3) — `address → place_name → user_hint` 중 존재하는 첫 값 하나.
    반환은 (선택된 `EvidenceValue`, 그 키 이름) — 키 이름은 `user_hint` 특수 규칙 분기에 쓴다.

    ⚠️ `address`/`place_name`은 2026-09-14 기준 어떤 mock fixture도 채우지 않는다
    (스키마는 `contract-evidence-record-needs.md`가 이미 선언해뒀다) — 그래서 이 두 분기는
    테스트로 아직 검증되지 않았다. `user_hint`(및 location 자체가 없는 분기)만 실제
    fixture(`scenario_happy_001`/`scenario_unknown_abstain_partial_001`)로 검증됐다.
    """
    if location is None:
        return None, None
    for key in _LOCATION_CANDIDATE_KEYS:
        candidate = location.get(key)
        if candidate is not None:
            return candidate, key
    return None, None


def event_type_label(code: str | None) -> str | None:
    if code is None:
        return None
    return EVENT_TYPE_LABELS.get(code, code)  # 모르는 코드는 원문 코드를 그대로 노출(침묵 실패 금지)


def report_type_label(code: str | None) -> str | None:
    if code is None:
        return None
    return REPORT_TYPE_LABELS.get(code, code)
