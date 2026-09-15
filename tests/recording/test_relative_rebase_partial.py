"""Relative-only timeline, rebase, PARTIAL·FAILED 계약 검증."""

from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from daesingo.recording import RecordingService, SpanResolution, load_recording_fixture


@pytest.fixture
def fixture():
    return load_recording_fixture("scenario_relative_rebase_001")


@pytest.fixture
def service(fixture) -> RecordingService:
    return RecordingService.from_fixture(fixture)


def test_relative_only_timeline_is_usable_without_fake_anchor(service: RecordingService) -> None:
    timeline = service.get_timeline("tl_rb001", 1)

    assert timeline.timeline_status == "USABLE_RELATIVE_ONLY"
    assert timeline.time_basis.working_anchor.status == "UNKNOWN"
    assert timeline.time_basis.working_anchor.value is None
    assert timeline.time_basis.working_anchor.source_candidate_ref is None


def test_rebase_keeps_old_revision_and_exposes_latest(service: RecordingService) -> None:
    revision_one = service.get_timeline("tl_rb001", 1)
    revision_two = service.get_timeline("tl_rb001", 2)

    assert revision_one.revision == 1
    assert len(revision_one.source_placements) == 1
    assert revision_one.gaps == []
    assert revision_two.revision == 2
    assert len(revision_two.source_placements) == 2
    assert revision_two.gaps[0].model_dump(mode="json") == {
        "start_sec": 600.0,
        "end_sec": 630.0,
    }
    assert service.get_latest_timeline("tl_rb001") == revision_two


def test_resolve_span_preserves_partial_gap(service: RecordingService) -> None:
    resolution = service.resolve_span(
        {"timeline_id": "tl_rb001", "revision": 2},
        {"start_sec": 580.0, "end_sec": 650.0},
    )

    assert resolution.status == "PARTIAL"
    assert resolution.failure is None
    assert [span.sequence for span in resolution.spans] == [0, 1]
    assert resolution.missing_ranges[0].reason == "TIMELINE_GAP"
    assert resolution.missing_ranges[0].source_ref is None
    assert resolution.model_dump(mode="json")["requested_range"] == {
        "start_sec": 580.0,
        "end_sec": 650.0,
    }


def test_timeline_position_resolves_stable_frame_across_rebase(
    service: RecordingService,
) -> None:
    revision_one_frame = service.resolve_frame(
        {
            "kind": "TIMELINE_POSITION",
            "timeline_ref": {"timeline_id": "tl_rb001", "revision": 1},
            "at_sec": 512.0,
            "stream_selector": None,
        }
    )
    revision_two_frame = service.resolve_frame(
        {
            "kind": "TIMELINE_POSITION",
            "timeline_ref": {"timeline_id": "tl_rb001", "revision": 2},
            "at_sec": 512.0,
            "stream_selector": None,
        }
    )

    assert revision_one_frame.frame_ref == "fr_rb001_thumb"
    assert revision_two_frame == revision_one_frame


def test_relative_only_timeline_rejects_absolute_anchor(fixture) -> None:
    payload = fixture.model_dump(mode="json")
    payload["recording_timelines"][0]["time_basis"]["working_anchor"] = {
        "value": "2026-09-14T12:00:00+09:00",
        "source_candidate_ref": "made_up",
        "status": "OK",
    }

    with pytest.raises(ValidationError, match="absolute anchor"):
        type(fixture).model_validate_json(json.dumps(payload))


def test_failed_resolution_requires_failure_detail(fixture) -> None:
    partial = fixture.span_resolutions[0].model_dump(mode="json")
    failed = {
        **partial,
        "status": "FAILED",
        "spans": [],
        "missing_ranges": [],
        "failure": None,
    }

    with pytest.raises(ValidationError, match="failure가 있어야"):
        SpanResolution.model_validate(failed)


def test_position_unknown_failed_resolution_accepts_contract_shape(fixture) -> None:
    payload = deepcopy(fixture.span_resolutions[0].model_dump(mode="json"))
    payload.update(
        {
            "status": "FAILED",
            "spans": [],
            "missing_ranges": [],
            "failure": {"kind": "EXAMPLE_KIND", "code": "EXAMPLE_CODE"},
        }
    )

    resolution = SpanResolution.model_validate(payload)
    assert resolution.status == "FAILED"
    assert resolution.failure is not None
    assert resolution.failure.code == "EXAMPLE_CODE"


def test_timeline_gap_rejects_non_null_source_ref(fixture) -> None:
    payload = fixture.span_resolutions[0].model_dump(mode="json")
    payload["missing_ranges"][0]["source_ref"] = {
        "kind": "source_asset",
        "ref": "sa_rb001_a",
    }

    with pytest.raises(ValidationError, match="source_ref는 null"):
        SpanResolution.model_validate(payload)
