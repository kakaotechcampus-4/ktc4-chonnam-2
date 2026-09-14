"""SourceAsset·MediaStream 계약과 공용 fixture adapter 검증."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from daesingo.recording import RecordingFixture, SourceAsset, load_recording_fixture


def test_happy_fixture_loads_source_assets_and_media_streams() -> None:
    fixture = load_recording_fixture("scenario_happy_001")

    assert fixture.scenario_id == "scenario_happy_001"
    assert fixture.module == "recording"
    assert len(fixture.source_assets) == 2
    assert len(fixture.media_streams) == 3

    front = next(
        asset for asset in fixture.source_assets if asset.source_asset_ref == "sa_h001_front"
    )
    assert front.media_stream_refs == ["ms_h001_front_v", "ms_h001_front_a"]

    audio = next(
        stream for stream in fixture.media_streams if stream.media_type == "AUDIO"
    )
    assert audio.role is None
    assert audio.source_asset_ref == front.source_asset_ref


def test_source_asset_rejects_unknown_size_when_available() -> None:
    fixture = load_recording_fixture("scenario_happy_001")
    payload = fixture.source_assets[0].model_dump()
    payload["byte_size"] = None

    with pytest.raises(ValidationError, match="byte_size"):
        SourceAsset.model_validate(payload)


def test_media_stream_rejects_camera_role_for_audio() -> None:
    fixture = load_recording_fixture("scenario_happy_001")
    payload = fixture.model_dump()
    audio = next(stream for stream in payload["media_streams"] if stream["media_type"] == "AUDIO")
    audio["role"] = "FRONT"

    with pytest.raises(ValidationError, match="AUDIO MediaStream"):
        RecordingFixture.model_validate(payload)


def test_fixture_rejects_broken_source_stream_reverse_reference() -> None:
    fixture = load_recording_fixture("scenario_happy_001")
    payload = deepcopy(fixture.model_dump())
    payload["media_streams"][0]["source_asset_ref"] = "sa_h001_rear"

    with pytest.raises(ValidationError, match="역참조"):
        RecordingFixture.model_validate(payload)


def test_loader_rejects_path_like_scenario_id() -> None:
    with pytest.raises(ValueError, match="scenario_id"):
        load_recording_fixture("../scenario_happy_001")
