"""CaseView `package.plate_image_ref` — 번호판 이미지 다운로드 주소(#569, `case-view/v1.11`).

`ReportPackage.assets.plate_image_ref.ref`를 그대로 옮긴다. evidence는 PLATE_IMAGE가
AVAILABLE일 때만 이 키를 싣으므로, 키가 없으면(번호판 못 읽음 · 생성 실패 · 생성 중) `null`이다."""

from copy import deepcopy
from pathlib import Path

import pytest

from daesingo.case.adapters import MockFixtureAdapter
from daesingo.case.view import _build_package_view

MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"


@pytest.mark.parametrize("scenario_id", ["happy_001", "unknown_abstain_partial_001"])
def test_package_carries_plate_image_ref(scenario_id):
    adapter = MockFixtureAdapter(MOCK_ROOT, scenario_id)
    report_package = adapter.get_report_package()

    package = _build_package_view(report_package, adapter.get_evidence_record())

    assert package["plate_image_ref"] == report_package["assets"]["plate_image_ref"]["ref"]


def test_package_plate_image_ref_is_null_without_plate_image_asset():
    adapter = MockFixtureAdapter(MOCK_ROOT, "happy_001")
    report_package = deepcopy(adapter.get_report_package())
    del report_package["assets"]["plate_image_ref"]

    package = _build_package_view(report_package, adapter.get_evidence_record())

    assert package["plate_image_ref"] is None
    assert package["artifact_ref"] == report_package["assets"]["report_video_ref"]["ref"]
