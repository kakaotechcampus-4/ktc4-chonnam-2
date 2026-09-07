"""Versioned evidence policy data used by the first integration slice."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventPolicy:
    safety_report_type: str
    violation_expression: str
    ambiguous_expression: str
    title: str
    description_clause: str
    template_ref: str


EVENT_POLICIES: dict[str, EventPolicy] = {
    "SIGNAL": EventPolicy(
        safety_report_type="교통위반 › 신호위반",
        violation_expression="적색 신호에 교차로에 진입함",
        ambiguous_expression="적색 신호에 교차로에 진입함 (대상 차량 특정 모호)",
        title="신호위반 신고",
        description_clause="적색 신호에 교차로에 진입했습니다.",
        template_ref="report-template/signal/v1",
    ),
    "CENTER_LINE_CROSSING": EventPolicy(
        safety_report_type="교통위반 › 중앙선 침범",
        violation_expression="중앙선을 침범함",
        ambiguous_expression="중앙선을 침범함 (대상 차량 특정 모호)",
        title="중앙선 침범 신고",
        description_clause="중앙선을 침범했습니다.",
        template_ref="report-template/center-line/v1",
    ),
    "SOLID_LINE_LANE_CHANGE": EventPolicy(
        safety_report_type="교통위반 › 진로변경 위반",
        violation_expression="백색 실선 구간에서 진로를 변경함",
        ambiguous_expression="백색 실선 구간에서 진로를 변경함 (대상 차량 특정 모호)",
        title="백색 실선 침범 신고",
        description_clause="백색 실선 구간에서 진로를 변경했습니다.",
        template_ref="report-template/lane-change/v1",
    ),
    "MOTORCYCLE_HELMET_NON_USE": EventPolicy(
        safety_report_type="이륜차 위반 › 안전모 미착용",
        violation_expression="이륜차 운전자가 안전모를 착용하지 않음",
        ambiguous_expression="이륜차 운전자가 안전모를 착용하지 않음 (대상 특정 모호)",
        title="이륜차 안전모 미착용 신고",
        description_clause="이륜차 운전자가 안전모를 착용하지 않았습니다.",
        template_ref="report-template/motorcycle-helmet/v1",
    ),
}

OUTCOME_PRECEDENCE = {"PASS": 0, "WARN": 1, "UNKNOWN": 2, "BLOCK": 3}
