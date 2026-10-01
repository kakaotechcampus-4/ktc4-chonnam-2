from pathlib import Path

import pytest

from daesingo.search.decision_trace import DiagnosticFineResponse
from daesingo.search.diagnostic_call import FineInput, _fine_spec
from daesingo.search.diagnostic_models import DiagnosticProfile
from daesingo.search.media import PreparedMedia
from daesingo.search.prompts import fine_prompt_for
from daesingo.search.schemas import CoarseCandidate
from daesingo.search.scope import VisualEventType

_OBSERVED = "전방 흰색 승용차가 황색 복선 중앙선을 바퀴로 침범"


def _probe(event_type: VisualEventType, observed: tuple[str, ...]) -> FineInput:
    candidate = CoarseCandidate.model_validate(
        {
            "event_type": event_type,
            "span": {"start_sec": 9.5, "end_sec": 14.5},
            "at_sec": 11.5,
            "observed": observed,
            "score": 0.8,
        }
    )
    prepared = PreparedMedia(Path("clip.mp4"), "video/mp4", 1, 13.0, 5.5, 18.5)
    return FineInput(candidate, 0, prepared)


def test_handoff_profile_gives_fine_the_coarse_observation_as_a_clue() -> None:
    # Given: Coarse가 대상 차량과 핵심 시각 11.5초를 보고한 후보
    probe = _probe(VisualEventType.CENTER_LINE_CROSSING, (_OBSERVED,))

    # When
    spec = _fine_spec(probe, DiagnosticProfile.DIAGNOSTIC_HANDOFF)

    # Then: 관찰 원문과 clip 시작 5.5초 기준 6.0초가 단서로 전달된다
    assert f"Coarse 관찰: {_OBSERVED}" in spec.prompt
    assert "약 6.0초" in spec.prompt
    assert "검증된 사실이 아닙니다" in spec.prompt
    assert spec.response_model is DiagnosticFineResponse


def test_handoff_profile_marks_an_empty_coarse_observation() -> None:
    spec = _fine_spec(
        _probe(VisualEventType.CENTER_LINE_CROSSING, ()),
        DiagnosticProfile.DIAGNOSTIC_HANDOFF,
    )

    assert "Coarse 관찰: 관찰 사실 없음" in spec.prompt


@pytest.mark.parametrize(
    "event_type",
    [VisualEventType.SOLID_LINE_LANE_CHANGE, VisualEventType.CENTER_LINE_CROSSING],
)
def test_uncertain_profile_adds_the_ambiguity_rule_only_to_line_events(
    event_type: VisualEventType,
) -> None:
    probe = _probe(event_type, (_OBSERVED,))

    uncertain = _fine_spec(probe, DiagnosticProfile.DIAGNOSTIC_UNCERTAIN)
    diagnostic = _fine_spec(probe, DiagnosticProfile.DIAGNOSTIC)

    assert "모호하면 UNCERTAIN을 사용" in uncertain.prompt
    assert "모호하면 UNCERTAIN을 사용" not in diagnostic.prompt
    # 9/26: 불확실성을 비운 채 confidence 0.9 이상으로 기각 -> 보고 규칙을 함께 준다
    assert "uncertainties를 비우는 것은" in uncertain.prompt
    assert "uncertainties를 비우는 것은" not in diagnostic.prompt
    assert "Coarse 관찰" not in uncertain.prompt


def test_uncertain_profile_leaves_other_events_unchanged() -> None:
    probe = _probe(VisualEventType.SIGNAL, (_OBSERVED,))

    uncertain = _fine_spec(probe, DiagnosticProfile.DIAGNOSTIC_UNCERTAIN)
    diagnostic = _fine_spec(probe, DiagnosticProfile.DIAGNOSTIC)

    assert uncertain.prompt == diagnostic.prompt


@pytest.mark.parametrize(
    "profile",
    [
        DiagnosticProfile.P3,
        DiagnosticProfile.DIAGNOSTIC,
        DiagnosticProfile.DIAGNOSTIC_UNCERTAIN,
    ],
)
def test_variants_other_than_handoff_do_not_pass_coarse_observation(
    profile: DiagnosticProfile,
) -> None:
    spec = _fine_spec(
        _probe(VisualEventType.CENTER_LINE_CROSSING, (_OBSERVED,)), profile
    )

    assert "Coarse 관찰" not in spec.prompt


def test_operational_fine_prompt_stays_p3() -> None:
    template = fine_prompt_for(VisualEventType.CENTER_LINE_CROSSING)

    assert template.version == "fine-p3"
    assert "coarse_observation" not in template.placeholders
    assert "모호하면 UNCERTAIN을 사용" not in template.text


def test_handoff_time_is_given_in_slowed_video_time() -> None:
    # Given: Fine 준비 영상이 0.25x로 늘어남(원본 clip 기준 6.0초 = 제공 영상 24.0초)
    probe = _probe(VisualEventType.CENTER_LINE_CROSSING, (_OBSERVED,))
    slowed = PreparedMedia(Path("clip.mp4"), "video/mp4", 1, 52.0, 5.5, 18.5, 0.25)

    spec = _fine_spec(FineInput(probe.candidate, 0, slowed), DiagnosticProfile.DIAGNOSTIC_HANDOFF)

    assert "약 24.0초" in spec.prompt


def test_review_windows_are_given_in_slowed_video_time() -> None:
    from daesingo.search.diagnostic_prompts import window_instruction

    assert window_instruction(10.0, 0.5) == "[[0.0, 10.0], [10.0, 20.0]]"
    assert window_instruction(10.0) == "[[0.0, 5.0], [5.0, 10.0]]"
