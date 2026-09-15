"""RecordingTimeline repository와 COMPLETE SpanResolution 검증."""

import pytest
from pydantic import ValidationError

from daesingo.recording import RecordingService, SpanResolution, load_recording_fixture


@pytest.fixture
def service() -> RecordingService:
    return RecordingService.from_fixture(load_recording_fixture("scenario_happy_001"))


def test_get_timeline_keeps_identity_and_revision(service: RecordingService) -> None:
    timeline = service.get_timeline("tl_h001", 1)

    assert timeline.contract_version == "recording-timeline/v1"
    assert timeline.timeline_id == "tl_h001"
    assert timeline.revision == 1
    assert timeline.timeline_status == "USABLE"
    assert len(timeline.source_placements) == 2


def test_resolve_span_returns_fixture_complete_contract(service: RecordingService) -> None:
    resolution = service.resolve_span(
        {"timeline_id": "tl_h001", "revision": 1},
        {"start_sec": 300.0, "end_sec": 420.0},
    )

    assert resolution.status == "COMPLETE"
    assert resolution.failure is None
    assert resolution.missing_ranges == []
    assert len(resolution.spans) == 1
    assert resolution.spans[0].model_dump(mode="json") == {
        "sequence": 0,
        "timeline_range": {"start_sec": 300.0, "end_sec": 420.0},
        "source_asset_ref": "sa_h001_front",
        "media_stream_ref": "ms_h001_front_v",
        "source_range": {"start_sec": 300.0, "end_sec": 420.0},
    }


def test_invalid_range_is_input_validation_failure(service: RecordingService) -> None:
    with pytest.raises(ValidationError):
        service.resolve_span(
            {"timeline_id": "tl_h001", "revision": 1},
            {"start_sec": 420.0, "end_sec": 300.0},
        )


def test_unknown_timeline_is_input_validation_failure(service: RecordingService) -> None:
    with pytest.raises(ValueError, match="timeline reference"):
        service.resolve_span(
            {"timeline_id": "tl_missing", "revision": 1},
            {"start_sec": 300.0, "end_sec": 420.0},
        )


def test_complete_resolution_rejects_unexplained_range() -> None:
    fixture = load_recording_fixture("scenario_happy_001")
    payload = fixture.span_resolutions[0].model_dump(mode="json")
    payload["spans"][0]["timeline_range"]["end_sec"] = 410.0

    with pytest.raises(ValidationError, match="requested_range 전체"):
        SpanResolution.model_validate(payload)
