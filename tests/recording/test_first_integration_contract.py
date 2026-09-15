"""recording 1차 Mock E2E의 최종 fixture·Consumer 접합 검증."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from daesingo.recording import RecordingFixture, RecordingService, load_recording_fixture


SCENARIOS = [
    "scenario_happy_001",
    "scenario_empty_001",
    "scenario_unknown_abstain_partial_001",
    "scenario_plate_reread_001",
    "scenario_correction_rerun_001",
    "scenario_infra_failure_001",
    "scenario_relative_rebase_001",
]
MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"


@pytest.mark.parametrize("scenario_id", SCENARIOS)
def test_all_recording_fixtures_round_trip_as_canonical_json(scenario_id: str) -> None:
    fixture = load_recording_fixture(scenario_id)
    serialized = fixture.model_dump_json()
    restored = RecordingFixture.model_validate_json(serialized)

    assert restored == fixture
    assert json.loads(serialized)["scenario_id"] == scenario_id


def test_happy_path_is_consumable_through_public_entries() -> None:
    fixture = load_recording_fixture("scenario_happy_001")
    service = RecordingService.from_fixture(fixture, case_id="case_h001")
    expected = fixture.span_resolutions[0]

    resolution = service.resolve_span(
        expected.timeline_ref.model_dump(mode="json"),
        expected.requested_range.model_dump(mode="json"),
    )
    analysis_source = service.prepare_analysis_source(
        resolution.spans[0].model_dump(mode="json"),
        fixture.analysis_sources[0].profile_ref,
    )
    clip = service.build_incident_clip(resolution.model_dump(mode="json"))

    assert resolution.model_dump(mode="json") == expected.model_dump(mode="json")
    assert analysis_source == fixture.analysis_sources[0]
    assert clip == fixture.incident_clips[0]
    assert json.loads(resolution.model_dump_json())["status"] == "COMPLETE"


def test_empty_scenario_is_a_valid_recording_input_not_a_failure() -> None:
    fixture = load_recording_fixture("scenario_empty_001")
    service = RecordingService.from_fixture(fixture)

    assert fixture.span_resolutions == []
    assert fixture.analysis_sources == []
    assert service.get_latest_timeline(fixture.recording_timelines[0].timeline_id) == (
        fixture.recording_timelines[0]
    )


def test_readout_offsets_resolve_to_recording_frame_source_offsets() -> None:
    fixture = load_recording_fixture("scenario_infra_failure_001")
    readout = json.loads(
        (MOCK_ROOT / "readout" / "scenario_infra_failure_001.json").read_text(
            encoding="utf-8"
        )
    )
    clip = fixture.incident_clips[0]
    samples = readout["overlay_time_readouts"][1]["samples"]
    frames = {frame.frame_ref: frame for frame in fixture.frame_refs}

    assert [
        frames[sample["frame_ref"]].source_offset_sec - clip.timeline_range.start_sec
        for sample in samples
    ] == [sample["offset_sec"] for sample in samples]
