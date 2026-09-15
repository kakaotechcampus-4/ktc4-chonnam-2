"""recording 공개 경계만 사용하는 1차 Mock E2E Consumer 예시."""

from __future__ import annotations

import json
from typing import Any

from daesingo.recording import RecordingService, load_recording_fixture


def run_happy_path() -> dict[str, Any]:
    """공용 Happy fixture를 공개 entry로 실행하고 JSON 호환 결과를 반환한다."""

    fixture = load_recording_fixture("scenario_happy_001")
    service = RecordingService.from_fixture(fixture, case_id="case_h001")

    expected_resolution = fixture.span_resolutions[0]
    resolution = service.resolve_span(
        expected_resolution.timeline_ref.model_dump(mode="json"),
        expected_resolution.requested_range.model_dump(mode="json"),
    )
    analysis_source = service.prepare_analysis_source(
        resolution.spans[0].model_dump(mode="json"),
        fixture.analysis_sources[0].profile_ref,
    )
    incident_clip = service.build_incident_clip(resolution.model_dump(mode="json"))
    frame = service.resolve_frame(
        {
            "kind": "STREAM_POSITION",
            "media_stream_ref": fixture.frame_refs[0].media_stream_ref,
            "source_offset_sec": fixture.frame_refs[0].source_offset_sec,
        }
    )

    return {
        "span_resolution": resolution.model_dump(mode="json"),
        "analysis_source": analysis_source.model_dump(mode="json"),
        "incident_clip": incident_clip.model_dump(mode="json"),
        "frame_ref": frame.model_dump(mode="json"),
    }


if __name__ == "__main__":
    print(json.dumps(run_happy_path(), ensure_ascii=False, indent=2))
