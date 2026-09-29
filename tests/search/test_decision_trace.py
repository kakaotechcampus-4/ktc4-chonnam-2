from copy import deepcopy

import pytest
from pydantic import ValidationError

from daesingo.search.decision_trace import (
    DiagnosticCoarseResponse,
    DiagnosticFineResponse,
    coarse_trace_issues,
    fine_trace_issues,
)
from daesingo.search.schemas import FineResponse
from daesingo.search.scope import VisualEventType


def fine_payload() -> dict:
    return {
        "verification": "NOT_OBSERVED",
        "visual_event_type": None,
        "target": {
            "association_status": "MATCHED",
            "described_as": "vehicle",
            "match_with_hint": None,
            "association_confidence": None,
            "track_ref": None,
        },
        "primitives": [],
        "temporal_facts": [],
        "uncertainties": [],
        "decision_reason": "The visible boundary is dashed.",
        "decision_basis": [
            {
                "criterion": key,
                "observation": "Visible fact",
                "at_offset_ms": 0,
                "limitation": None,
            }
            for key in (
                "target_association",
                "origin_lane",
                "lateral_movement",
                "divider_identity",
                "marking_at_crossing",
                "crossing_event",
                "destination_lane",
                "temporal_order",
            )
        ],
    }


@pytest.mark.parametrize("verification", ["OBSERVED", "NOT_OBSERVED", "UNCERTAIN"])
def test_diagnostic_fine_keeps_p3_verification_contract(verification: str) -> None:
    # Given: old wire fields plus observation explanations.
    payload = fine_payload()
    payload["verification"] = verification
    payload["visual_event_type"] = (
        "SOLID_LINE_LANE_CHANGE" if verification == "OBSERVED" else None
    )
    # When: the diagnostic shape is parsed.
    response = DiagnosticFineResponse.model_validate(payload)
    # Then: explanation fields can be removed to recover the unchanged p3 shape.
    public_wire = response.model_dump(exclude={"decision_reason", "decision_basis"})
    assert FineResponse.model_validate(public_wire).verification.value == verification
    assert (
        fine_trace_issues(response, VisualEventType.SOLID_LINE_LANE_CHANGE, 5000) == ()
    )


def test_incomplete_or_out_of_bounds_explanation_remains_visible() -> None:
    # Given: the model's explanation is incomplete and mentions a time past the clip.
    payload = fine_payload()
    payload["decision_basis"] = [
        {
            "criterion": "target_association",
            "observation": "Visible fact",
            "at_offset_ms": 6000,
            "limitation": None,
        }
    ]
    # When: the experiment inspects the parsed response.
    response = DiagnosticFineResponse.model_validate(payload)
    issues = fine_trace_issues(response, VisualEventType.SOLID_LINE_LANE_CHANGE, 5000)
    # Then: it keeps the answer for diagnosis without producing public evidence.
    assert "TRACE_CRITERION_MISSING" in issues
    assert "TRACE_TIME_OUT_OF_BOUNDS" in issues
    assert response.decision_reason == payload["decision_reason"]


def test_negative_fine_time_is_a_shape_failure() -> None:
    payload = deepcopy(fine_payload())
    payload["decision_basis"][0]["at_offset_ms"] = -1
    with pytest.raises(ValidationError):
        DiagnosticFineResponse.model_validate(payload)


def test_empty_coarse_candidates_still_require_complete_window_reviews() -> None:
    # Given: the video is 6 seconds and no candidates were selected.
    reviews = [
        {
            "start_sec": start,
            "end_sec": end,
            "event_type": "SIGNAL",
            "decision": "NO_CANDIDATE",
            "observations": ["No visible crossing"],
            "reason": "No candidate movement",
            "limitations": [],
        }
        for start, end in ((0, 5), (5, 6))
    ]
    # When: coverage is inspected.
    response = DiagnosticCoarseResponse.model_validate(
        {"candidates": [], "window_reviews": reviews}
    )
    # Then: the entire input has an explicit review, including the final partial window.
    assert coarse_trace_issues(response, (VisualEventType.SIGNAL,), 6) == ()
    missing = response.model_copy(
        update={"window_reviews": response.window_reviews[:1]}
    )
    assert "TRACE_WINDOW_COVERAGE" in coarse_trace_issues(
        missing, (VisualEventType.SIGNAL,), 6
    )


def test_old_p3_parser_rejects_diagnostic_fields() -> None:
    # Given / When / Then: diagnostic data cannot silently enter the old provider wire path.
    with pytest.raises(ValidationError):
        FineResponse.model_validate(fine_payload())
