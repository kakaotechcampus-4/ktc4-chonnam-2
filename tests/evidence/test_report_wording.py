"""Regression coverage for subject placement in specific reports."""

import pytest

from daesingo.evidence import EVENT_POLICY, render_report


@pytest.mark.parametrize("location,plate,expected_opening", (
    ("상무역", "12가3456", "상무역에서 차량번호 12가3456의 "),
    ("상무역", None, "상무역에서 "),
    (None, "12가3456", "차량번호 12가3456의 "),
    (None, None, ""),
))
def test_helmet_report_uses_rider_as_subject(location, plate, expected_opening):
    event_type = "MOTORCYCLE_HELMET_NON_USE"
    rendered = render_report(
        visual_event_type=event_type,
        situation_response="CONFIRMED",
        occurred_at="2026-11-02T05:00:28Z",
        location_display=location,
        vehicle_number=plate,
        violation_expression=EVENT_POLICY[event_type]["violation_expression"],
    )
    expected = (
        f"2026-11-02 14:00:28경 {expected_opening}"
        "이륜차 운전자 또는 탑승자가 안전모를 착용하지 않고 주행하는 것을 확인하여 신고합니다.\n"
        "첨부 영상에서 해당 위반 상황을 확인할 수 있습니다."
    )
    if plate is None:
        expected += "\n차량번호는 영상에서 식별하지 못했습니다."
    assert rendered["title"] == "이륜차 안전모 미착용 신고"
    assert rendered["description"] == expected
    assert rendered["content_length"] == len(expected)


@pytest.mark.parametrize("event_type,title,expression", (
    ("SIGNAL", "신호위반 차량 신고", "적색신호 상태에서 정지하지 않고 진행"),
    ("CENTER_LINE_CROSSING", "중앙선 침범 차량 신고", "황색 중앙선을 넘어 반대 차로로 진입"),
    ("SOLID_LINE_LANE_CHANGE", "진로변경 위반 차량 신고", "백색 실선을 넘어 진로를 변경"),
))
def test_other_specific_reports_keep_vehicle_subject(event_type, title, expression):
    rendered = render_report(
        visual_event_type=event_type,
        situation_response="CONFIRMED",
        occurred_at="2026-11-02T05:00:28Z",
        location_display="상무역",
        vehicle_number="12가3456",
        violation_expression=EVENT_POLICY[event_type]["violation_expression"],
    )
    assert rendered["title"] == title
    assert rendered["description"] == (
        "2026-11-02 14:00:28경 상무역에서\n차량번호 12가3456 차량이\n"
        f"{expression}하는 것을 확인하여 신고합니다.\n"
        "첨부 영상에서 해당 위반 상황을 확인할 수 있습니다."
    )
