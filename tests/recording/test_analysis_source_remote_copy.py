"""AnalysisSource stream과 RemoteCopy registry 검증."""

from datetime import datetime

import pytest

from daesingo.recording import (
    RecordingCapabilityError,
    RecordingService,
    load_recording_fixture,
)


@pytest.fixture
def fixture():
    return load_recording_fixture("scenario_happy_001")


@pytest.fixture
def service(fixture) -> RecordingService:
    return RecordingService.from_fixture(fixture)


def test_prepare_analysis_source_uses_opaque_profile_equality(
    fixture,
    service: RecordingService,
) -> None:
    span = fixture.span_resolutions[0].spans[0]

    source = service.prepare_analysis_source(span, "prof_fine_v1")

    assert source.analysis_source_ref == "as_h001_fine"
    assert source.profile_ref == "prof_fine_v1"
    assert source.contract_version == "analysis-source-derived/v1"


def test_open_analysis_source_returns_fresh_stream_each_time(
    service: RecordingService,
) -> None:
    first = service.open_analysis_source("as_h001_fine")
    second = service.open_analysis_source("as_h001_fine")

    assert first.content_type == "application/octet-stream"
    assert first.byte_size == 41943040
    assert first.stream is not second.stream
    assert first.stream.tell() == 0
    assert first.stream.read(8) == bytes(8)
    assert first.stream.tell() == 8
    assert second.stream.tell() == 0


def test_prepare_analysis_source_does_not_parse_profile_value(
    fixture,
    service: RecordingService,
) -> None:
    with pytest.raises(RecordingCapabilityError) as raised:
        service.prepare_analysis_source(fixture.span_resolutions[0].spans[0], "fine")

    assert raised.value.code == "NOT_FOUND"


def test_find_remote_copy_returns_only_available_unexpired_entry(
    service: RecordingService,
) -> None:
    before_expiry = datetime.fromisoformat("2026-08-26T17:59:59+09:00")
    at_expiry = datetime.fromisoformat("2026-08-26T18:00:00+09:00")

    found = service.find_remote_copy("as_h001_fine", "gemini", now=before_expiry)

    assert found is not None
    assert found.remote_copy_ref == "rc_h001_fine"
    assert service.find_remote_copy("as_h001_fine", "gemini", now=at_expiry) is None
    assert service.find_remote_copy("as_h001_fine", "other", now=before_expiry) is None


def test_find_remote_copy_rejects_naive_clock(service: RecordingService) -> None:
    with pytest.raises(ValueError, match="offset-aware"):
        service.find_remote_copy(
            "as_h001_fine",
            "gemini",
            now=datetime(2026, 8, 26, 17, 59, 59),
        )


def test_register_remote_copy_assigns_identity_and_initial_availability(
    service: RecordingService,
) -> None:
    expires_at = datetime.fromisoformat("2026-09-01T00:00:00+09:00")
    registered = service.register_remote_copy(
        "as_h001_fine",
        "example-provider",
        {
            "provider_object_ref": "opaque-object-001",
            "expires_at": expires_at,
        },
    )

    assert registered.remote_copy_ref.startswith("rc_")
    assert registered.analysis_source_ref == "as_h001_fine"
    assert registered.availability == "AVAILABLE"
    assert (
        service.find_remote_copy(
            "as_h001_fine",
            "example-provider",
            now=datetime.fromisoformat("2026-08-31T00:00:00+09:00"),
        )
        == registered
    )


def test_analysis_source_does_not_expose_storage_locator(service: RecordingService) -> None:
    source = service.prepare_analysis_source(
        {
            "sequence": 0,
            "timeline_range": {"start_sec": 300.0, "end_sec": 420.0},
            "source_asset_ref": "sa_h001_front",
            "media_stream_ref": "ms_h001_front_v",
            "source_range": {"start_sec": 300.0, "end_sec": 420.0},
        },
        "prof_fine_v1",
    )

    public_payload = source.model_dump(mode="json")
    assert "path" not in public_payload
    assert "url" not in public_payload
    assert "provider_object_ref" not in public_payload
