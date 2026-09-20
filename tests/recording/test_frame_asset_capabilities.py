"""FrameRef와 AssetFacts 공개 capability 검증."""

import pytest
from pydantic import ValidationError

from daesingo.recording import (
    RecordingCapabilityError,
    RecordingService,
    load_recording_fixture,
)


@pytest.fixture
def service() -> RecordingService:
    fixture = load_recording_fixture("scenario_happy_001")
    return RecordingService.from_fixture(fixture)


def test_resolve_and_read_frame_by_stream_position(service: RecordingService) -> None:
    frame = service.resolve_frame(
        {
            "kind": "STREAM_POSITION",
            "media_stream_ref": "ms_h001_front_v",
            "source_offset_sec": 312.48,
        }
    )

    assert frame.frame_ref == "fr_h001_thumb"
    assert frame.model_dump(mode="json") == {
        "contract": "FrameRef",
        "contract_version": "source-asset-media-stream/v1",
        "frame_ref": "fr_h001_thumb",
        "media_stream_ref": "ms_h001_front_v",
        "source_offset_sec": 312.48,
    }
    assert service.read_frame(frame.frame_ref) == b"fixture-frame:fr_h001_thumb"


def test_same_canonical_position_returns_same_frame_ref(service: RecordingService) -> None:
    locator = {
        "kind": "STREAM_POSITION",
        "media_stream_ref": "ms_h001_front_v",
        "source_offset_sec": 313.1,
    }

    assert service.resolve_frame(locator) == service.resolve_frame(locator)


def test_locator_rejects_mixed_coordinate_fields(service: RecordingService) -> None:
    with pytest.raises(ValidationError):
        service.resolve_frame(
            {
                "kind": "STREAM_POSITION",
                "media_stream_ref": "ms_h001_front_v",
                "source_offset_sec": 312.48,
                "timeline_ref": {"timeline_id": "tl_h001", "revision": 1},
                "at_sec": 312.48,
            }
        )


def test_frame_errors_keep_machine_readable_code(service: RecordingService) -> None:
    with pytest.raises(RecordingCapabilityError) as raised:
        service.resolve_frame(
            {
                "kind": "STREAM_POSITION",
                "media_stream_ref": "ms_h001_front_v",
                "source_offset_sec": 9999.0,
            }
        )

    assert raised.value.code == "OUT_OF_RANGE"


def test_lookup_asset_facts_returns_canonical_payload(service: RecordingService) -> None:
    facts = service.lookup_asset_facts(
        {"kind": "derived_asset", "ref": "da_h001_report_video"}
    )

    assert facts.asset_kind == "DERIVED_ASSET"
    assert facts.derived_role == "REPORT_VIDEO"
    assert facts.timeline_ref is not None
    assert facts.timeline_ref.revision == 1
    assert any(item.kind == "source_asset" for item in facts.lineage)


def test_lookup_distinguishes_invalid_kind_and_unknown_ref(service: RecordingService) -> None:
    with pytest.raises(RecordingCapabilityError) as invalid_kind:
        service.lookup_asset_facts({"kind": "frame", "ref": "fr_h001_thumb"})
    assert invalid_kind.value.code == "INVALID_REF_KIND"

    with pytest.raises(RecordingCapabilityError) as unknown_ref:
        service.lookup_asset_facts({"kind": "derived_asset", "ref": "missing"})
    assert unknown_ref.value.code == "UNKNOWN_REF"
