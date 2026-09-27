from pathlib import Path

import pytest

from daesingo.search import (
    AnalysisSourceStream,
    ContractRef,
    VideoStreamSelectionError,
    select_single_video_stream,
    verify_visual_with_stream_context,
)
from daesingo.search.fixtures import SearchScenario


MOCK_DIR = Path(__file__).resolve().parents[2] / "data" / "mock" / "search"


def _happy() -> SearchScenario:
    return SearchScenario.model_validate_json(
        (MOCK_DIR / "scenario_happy_001.json").read_text(encoding="utf-8")
    )


def test_select_single_video_stream_ignores_audio_with_explicit_type() -> None:
    source_ref = ContractRef(kind="analysis_source", ref="as_h001_fine")

    selected = select_single_video_stream(
        source_ref,
        (
            AnalysisSourceStream("ms_h001_front_v", "VIDEO"),
            AnalysisSourceStream("ms_h001_front_a", "AUDIO"),
        ),
    )

    assert selected.analysis_source_ref == source_ref
    assert selected.media_stream_ref == "ms_h001_front_v"


@pytest.mark.parametrize(
    ("streams", "code"),
    [
        ((AnalysisSourceStream("ms_h001_front_a", "AUDIO"),), "VIDEO_STREAM_NOT_FOUND"),
        (
            (
                AnalysisSourceStream("ms_h001_front_v", "VIDEO"),
                AnalysisSourceStream("ms_h001_rear_v", "VIDEO"),
            ),
            "AMBIGUOUS_VIDEO_STREAM",
        ),
    ],
)
def test_select_single_video_stream_rejects_missing_or_ambiguous_video(
    streams: tuple[AnalysisSourceStream, ...], code: str
) -> None:
    with pytest.raises(VideoStreamSelectionError, match=code):
        _ = select_single_video_stream(
            ContractRef(kind="analysis_source", ref="as_h001_fine"), streams
        )


def test_verify_visual_with_stream_context_keeps_canonical_result_unchanged() -> None:
    scenario = _happy()
    candidate = scenario.candidate_search_result.candidates[0]
    evidence = scenario.visual_evidences[0]

    execution = verify_visual_with_stream_context(
        evidence.input_ref,
        candidate,
        (
            AnalysisSourceStream("ms_h001_front_v", "VIDEO"),
            AnalysisSourceStream("ms_h001_front_a", "AUDIO"),
        ),
        scenario.analysis_scopes[0].hint,
    )

    assert execution.result.visual_evidence == evidence
    assert execution.selected_video_stream.media_stream_ref == "ms_h001_front_v"
