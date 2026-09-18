"""IncidentClip·DerivedAsset·DeletionReport lifecycle 검증."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from daesingo.recording import (
    DerivedAsset,
    RecordingService,
    load_recording_fixture,
)


@pytest.fixture
def fixture():
    return load_recording_fixture("scenario_happy_001")


@pytest.fixture
def service(fixture) -> RecordingService:
    return RecordingService.from_fixture(fixture, case_id="case_h001")


def test_build_incident_clip_reuses_fixture_identity(fixture, service: RecordingService) -> None:
    resolution = fixture.span_resolutions[0]

    first = service.build_incident_clip(resolution)
    second = service.build_incident_clip(resolution)

    assert first.incident_clip_ref == "clip_h001"
    assert second == first
    assert first.source_provenance.timeline_ref == resolution.timeline_ref
    assert first.source_provenance.asset_spans == resolution.spans


def test_build_incident_clip_rejects_unconfirmed_options(
    fixture,
    service: RecordingService,
) -> None:
    with pytest.raises(ValueError, match="options schema"):
        service.build_incident_clip(fixture.span_resolutions[0], {"padding_sec": 5})


def test_derived_assets_keep_role_and_direct_parent(service: RecordingService) -> None:
    report_video = service.get_derived_asset("da_h001_report_video")
    plate_image = service.get_derived_asset("da_h001_plate_image")

    assert report_video.derived_role == "REPORT_VIDEO"
    assert report_video.source_refs[0].model_dump() == {
        "kind": "incident_clip",
        "ref": "clip_h001",
    }
    assert plate_image.derived_role == "PLATE_IMAGE"
    assert plate_image.duration_sec is None
    assert plate_image.timeline_ref is None
    assert plate_image.timeline_range is None


def test_register_derived_asset_rejects_timeline_pair_mismatch(fixture) -> None:
    payload = fixture.derived_assets[0].model_dump(mode="json")
    payload["timeline_ref"] = None

    with pytest.raises(ValidationError, match="함께 존재"):
        DerivedAsset.model_validate(payload)


def test_purge_case_deletes_managed_assets_but_waits_for_remote_expiry(
    service: RecordingService,
) -> None:
    requested_at = datetime.fromisoformat("2026-08-25T12:00:00+09:00")

    report = service.purge_case("case_h001", requested_at=requested_at)

    assert report.status == "PARTIAL"
    assert report.completed_at == requested_at
    results = {(item.asset_ref.kind, item.result) for item in report.items}
    assert ("analysis_source", "DELETED") in results
    assert ("incident_clip", "DELETED") in results
    assert ("derived_asset", "DELETED") in results
    assert ("remote_copy", "PENDING_EXPIRY") in results
    assert all(item.asset_ref.kind != "external_source" for item in report.items)


def test_second_purge_reports_already_removed_managed_assets(
    service: RecordingService,
) -> None:
    requested_at = datetime.fromisoformat("2026-08-25T12:00:00+09:00")
    service.purge_case("case_h001", requested_at=requested_at)

    second = service.purge_case("case_h001", requested_at=requested_at)

    assert any(item.result == "NOT_FOUND" for item in second.items)
    assert any(item.result == "PENDING_EXPIRY" for item in second.items)


def test_empty_case_purge_is_complete() -> None:
    service = RecordingService()

    report = service.purge_case(
        "case_empty",
        requested_at=datetime.fromisoformat("2026-09-14T12:00:00+09:00"),
    )

    assert report.status == "COMPLETE"
    assert report.items == []
