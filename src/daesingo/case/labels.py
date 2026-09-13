"""CaseView 표시용 label·info_state 파생 규칙.

⚠️ 1차 구현 범위 한정 — happy path(`scenario_happy_001`)에서 실제로 쓰인 값만 등록했다.
전체 enum→label 매핑은 이 모듈이 새로 설계하는 것이 아니라, 실제로는 evidence/registry
쪽 공용 값 공간(`docs/mock/01_mock_dataset_overview.md` §4-6번 참고 — 아직 어느 Final
Contract에도 등재돼 있지 않다고 명시된 gap)을 참조해야 한다. 여기 있는 표는 그 registry가
생기기 전까지 case의 projection 코드가 죽지 않게 하는 placeholder다.

`location_display`를 항상 INFO_NEEDS_REVIEW로 고정하는 규칙(_LOCATION 관련 함수)도
`contract-job-record-case-view.md` B절 §7의 review_needed 파생 규칙 원문을 그대로
옮긴 것이 아니라, 이 pack의 happy-path fixture 하나에서 관찰된 패턴을 재현한 것이다.
다른 시나리오(예: GPS로 확정된 위치)로 확장하기 전에 §7 원문과 대조해야 한다.
"""
from __future__ import annotations

# event.visual_event_type.value → 사용자 표시용 한글 label
EVENT_TYPE_LABELS: dict[str, str] = {
    "SOLID_LINE_LANE_CHANGE": "백색 실선 구간 차로변경",
}

# event.safety_report_type.value → 사용자 표시용 한글 label
REPORT_TYPE_LABELS: dict[str, str] = {
    "TRAFFIC_VIOLATION": "교통위반(고속도로 포함)",
}

# EvidenceRecord.event.*.source.observability → CaseView *_display.info_state
_OBSERVABILITY_TO_INFO_STATE: dict[str, str] = {
    "OBSERVED": "INFO_SOURCE_VERIFIED",
    "INFERRED": "INFO_AI_ESTIMATED",
}

# EvidenceRecord.occurred_at.resolution_status → CaseView.event_time_display.info_state
_RESOLUTION_STATUS_TO_INFO_STATE: dict[str, str] = {
    "OK": "INFO_SOURCE_VERIFIED",
}


def observability_to_info_state(observability: str | None) -> str:
    """observability가 미등록 값이면 INFO_UNKNOWN으로 떨어뜨린다(조용히 단정하지 않는다)."""
    return _OBSERVABILITY_TO_INFO_STATE.get(observability or "", "INFO_UNKNOWN")


def resolution_status_to_info_state(status: str | None) -> str:
    return _RESOLUTION_STATUS_TO_INFO_STATE.get(status or "", "INFO_NEEDS_REVIEW")


def event_type_label(code: str | None) -> str | None:
    if code is None:
        return None
    return EVENT_TYPE_LABELS.get(code, code)  # 모르는 코드는 원문 코드를 그대로 노출(침묵 실패 금지)


def report_type_label(code: str | None) -> str | None:
    if code is None:
        return None
    return REPORT_TYPE_LABELS.get(code, code)
