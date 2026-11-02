"""Report text uses KST while offset-aware source values remain untouched."""

from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path

import pytest

from daesingo.evidence import (
    ContractInputError,
    build_report_package,
    evaluate_requirements,
    render_report,
    validate_contract,
)
from daesingo.evidence.mock_integration import run_scenario

ROOT = Path(__file__).resolve().parents[2]
TIME_CASES = (
    ("2026-11-02T05:00:26+00:00", "2026-11-02 14:00:26"),
    ("2026-11-02T05:00:26Z", "2026-11-02 14:00:26"),
    ("2026-11-02T14:00:26+09:00", "2026-11-02 14:00:26"),
    ("2026-11-02T01:00:26-04:00", "2026-11-02 14:00:26"),
    ("2026-11-02T18:30:00Z", "2026-11-03 03:30:00"),
    ("2026-12-31T15:30:00Z", "2027-01-01 00:30:00"),
)


@pytest.mark.parametrize("occurred_at,display_time", TIME_CASES)
@pytest.mark.parametrize("specific", (True, False), ids=("specific", "generic"))
@pytest.mark.parametrize("location", ("테스트 사거리", None), ids=("location", "no-location"))
@pytest.mark.parametrize("plate", ("12가3456", None), ids=("plate", "no-plate"))
def test_report_uses_kst_in_every_template(occurred_at, display_time, specific, location, plate):
    rendered = render_report(
        visual_event_type="SOLID_LINE_LANE_CHANGE" if specific else None,
        situation_response="CONFIRMED" if specific else "USER_UNSURE",
        occurred_at=occurred_at, location_display=location, vehicle_number=plate,
        violation_expression="백색 실선을 넘어 진로를 변경",
    )
    vehicle = "차량번호 12가3456 차량" if plate else "차량"
    if specific:
        first_line = f"{display_time}경 테스트 사거리에서" if location else f"{display_time}경 촬영된"
        expected = (
            f"{first_line}\n{vehicle}이\n백색 실선을 넘어 진로를 변경하는 것을 확인하여 신고합니다.\n"
            "첨부 영상에서 해당 위반 상황을 확인할 수 있습니다."
        )
    else:
        place = " 테스트 사거리에서" if location else ""
        expected = (
            f"{display_time}경{place} 촬영된 {vehicle}의 주행 상황에 대해 신고합니다.\n"
            "구체적인 위반 유형은 확인하기 어려워 첨부 영상을 바탕으로 확인을 요청드립니다."
        )
    if plate is None:
        expected += "\n차량번호는 영상에서 식별하지 못했습니다."
    template = "specific" if specific else "generic"
    if location is None:
        template += "-no-location"
    if plate is None:
        template += "-no-plate"
    assert rendered == {
        "title": "진로변경 위반 차량 신고" if specific else "교통법규 위반 상황 확인 요청",
        "description": expected,
        "template_ref": f"tmpl/safety-report-{template}-v1",
        "content_length": len(expected),
    }
    assert 5 <= rendered["content_length"] <= 900


@pytest.mark.parametrize("occurred_at", (
    "2026-11-02T05:00:26", "2026-02-30T05:00:26Z",
    "2026-11-02T24:00:26Z", "2026-11-02T05:60:26+09:00", "not-a-datetime",
))
def test_report_keeps_rejecting_invalid_or_naive_times(occurred_at):
    with pytest.raises(ContractInputError):
        render_report(
            visual_event_type="SOLID_LINE_LANE_CHANGE", situation_response="CONFIRMED",
            occurred_at=occurred_at, location_display=None, vehicle_number="12가3456",
            violation_expression="백색 실선을 넘어 진로를 변경",
        )


@pytest.mark.parametrize("host_timezone", ("UTC0", "EST5EDT"))
def test_report_timezone_is_independent_of_host_timezone(monkeypatch, host_timezone):
    with monkeypatch.context() as environment:
        environment.setenv("TZ", host_timezone)
        if hasattr(time, "tzset"):
            time.tzset()
        try:
            rendered = render_report(
                visual_event_type="SOLID_LINE_LANE_CHANGE", situation_response="CONFIRMED",
                occurred_at="2026-12-31T15:30:00Z", location_display=None,
                vehicle_number="12가3456", violation_expression="백색 실선을 넘어 진로를 변경",
            )
            assert rendered["description"].startswith("2027-01-01 00:30:00경 촬영된\n")
        finally:
            environment.undo()
            if hasattr(time, "tzset"):
                time.tzset()


@pytest.fixture(scope="module")
def happy_inputs():
    configs = json.loads((ROOT / "tests/evidence/fixtures/adapter_inputs.json").read_text(encoding="utf-8"))
    outputs = run_scenario(ROOT, "scenario_happy_001", configs["scenarios"]["scenario_happy_001"])["outputs"]
    assets = json.loads((ROOT / "data/mock/recording/scenario_happy_001.json").read_text(encoding="utf-8"))["asset_facts"]
    return outputs["evidence_records"][0], outputs["time_resolutions"][0], assets


@pytest.mark.parametrize("occurred_at,display_time", TIME_CASES)
@pytest.mark.parametrize("status", ("OK", "NEEDS_REVIEW"))
def test_package_preserves_source_time_and_review_status(happy_inputs, occurred_at, display_time, status):
    record, resolution, assets = deepcopy(happy_inputs)
    record["occurred_at"].update(value=occurred_at, resolution_status=status)
    resolution["resolved"]["value"] = occurred_at
    resolution["considered"][0]["value"] = occurred_at
    resolution["status"] = status
    if status == "NEEDS_REVIEW":
        resolution["resolved"]["verification"] = "UNVERIFIED"
        resolution["considered"][0]["verification"] = "UNVERIFIED"
        resolution["post_stamp"] = {
            "needed": True, "reason_code": "time.no_verified_overlay_present",
            "requires_user_notice": True,
        }
    original_record, original_resolution = deepcopy(record), deepcopy(resolution)
    report_video = next(asset for asset in assets if asset.get("derived_role") == "REPORT_VIDEO")
    report = evaluate_requirements(
        record, scope="FINAL_PACKAGE", report_id="req_timezone",
        evaluated_at=occurred_at, time_resolution=resolution, asset_facts=assets,
        observation_facts={"post_stamp_applied": {
            "value": True, "subject_refs": [report_video["asset_ref"]],
        }},
    )
    expected_outcome = "PASS" if status == "OK" else "WARN"
    assert report["overall"] == expected_outcome
    deadline = next(check for check in report["checks"] if check["code"] == "package.deadline.within_policy")
    assert deadline["outcome"] == expected_outcome
    package = build_report_package(
        record, report, package_id="pkg_timezone", created_at=occurred_at, asset_facts=assets,
    )
    assert package["report_inputs"] == {
        "safety_report_type": "교통위반(고속도로 포함)", "occurred_at": occurred_at,
        "location": {"display_text": "상무중앙로 사거리 부근"},
        "vehicle_number": "12가3456", "violation_expression": "백색 실선을 넘어 진로를 변경",
    }
    assert package["report"] == {
        "title": "진로변경 위반 차량 신고",
        "description": (
            f"{display_time}경 상무중앙로 사거리 부근에서\n차량번호 12가3456 차량이\n"
            "백색 실선을 넘어 진로를 변경하는 것을 확인하여 신고합니다.\n"
            "첨부 영상에서 해당 위반 상황을 확인할 수 있습니다."
        ),
        "template_ref": "tmpl/safety-report-specific-v1",
    }
    assert record == original_record
    assert resolution == original_resolution
    assert validate_contract(package) == []
