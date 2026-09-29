"""Private experiment wire shapes: p3 facts plus inspectable observations."""

from enum import StrEnum
from math import ceil
from typing import Annotated

from pydantic import Field

from .schemas import CoarseCandidate, FineResponse, WireModel
from .scope import VisualEventType

Text = Annotated[str, Field(min_length=1)]

CHECKLISTS: dict[VisualEventType, tuple[str, ...]] = {
    VisualEventType.SIGNAL: (
        "target_association",
        "movement_direction",
        "applicable_signal",
        "signal_before_crossing",
        "signal_at_crossing",
        "boundary_identity",
        "crossing_event",
        "temporal_order",
    ),
    VisualEventType.CENTER_LINE_CROSSING: (
        "target_association",
        "road_directions",
        "centerline_identity",
        "vehicle_before",
        "contact_or_crossing",
        "vehicle_after",
        "persistence",
        "road_geometry",
    ),
    VisualEventType.SOLID_LINE_LANE_CHANGE: (
        "target_association",
        "origin_lane",
        "lateral_movement",
        "divider_identity",
        "marking_at_crossing",
        "crossing_event",
        "destination_lane",
        "temporal_order",
    ),
    VisualEventType.MOTORCYCLE_HELMET_NON_USE: (
        "motorcycle_presence",
        "rider_association",
        "rider_role",
        "head_visibility",
        "helmet_presence_or_absence",
        "absence_visibility",
        "observation_consistency",
    ),
}


class WindowDecision(StrEnum):
    CANDIDATE = "CANDIDATE"
    NO_CANDIDATE = "NO_CANDIDATE"
    UNCERTAIN = "UNCERTAIN"


class WindowReview(WireModel):
    start_sec: float = Field(ge=0, allow_inf_nan=False)
    end_sec: float = Field(gt=0, allow_inf_nan=False)
    event_type: VisualEventType
    decision: WindowDecision
    observations: tuple[Text, ...]
    reason: Text
    limitations: tuple[Text, ...]


class DiagnosticCoarseCandidate(CoarseCandidate):
    candidate_reason: Text


class DiagnosticCoarseResponse(WireModel):
    candidates: tuple[DiagnosticCoarseCandidate, ...]
    window_reviews: tuple[WindowReview, ...]


class DecisionBasis(WireModel):
    criterion: Text
    observation: Text
    at_offset_ms: int | None = Field(ge=0)
    limitation: Text | None


class DiagnosticFineResponse(FineResponse):
    decision_reason: Text
    decision_basis: tuple[DecisionBasis, ...]


def review_windows(duration_sec: float) -> tuple[tuple[float, float], ...]:
    return tuple(
        (float(start), min(float(start + 5), round(duration_sec, 3)))
        for start in range(0, ceil(duration_sec), 5)
    )


def coarse_trace_issues(
    response: DiagnosticCoarseResponse,
    event_types: tuple[VisualEventType, ...],
    duration_sec: float,
) -> tuple[str, ...]:
    expected = {
        (start, end, event)
        for start, end in review_windows(duration_sec)
        for event in event_types
    }
    actual = {
        (round(item.start_sec, 3), round(item.end_sec, 3), item.event_type)
        for item in response.window_reviews
    }
    if actual != expected or len(actual) != len(response.window_reviews):
        return ("TRACE_WINDOW_COVERAGE",)
    return ()


def fine_trace_issues(
    response: DiagnosticFineResponse,
    event_type: VisualEventType,
    clip_duration_ms: int,
) -> tuple[str, ...]:
    issues: list[str] = []
    keys = [item.criterion for item in response.decision_basis]
    expected = set(CHECKLISTS[event_type])
    if expected - set(keys):
        issues.append("TRACE_CRITERION_MISSING")
    if set(keys) - expected or len(keys) != len(set(keys)):
        issues.append("TRACE_CRITERION_UNEXPECTED_OR_DUPLICATE")
    if any(
        item.at_offset_ms is not None and item.at_offset_ms > clip_duration_ms
        for item in response.decision_basis
    ):
        issues.append("TRACE_TIME_OUT_OF_BOUNDS")
    return tuple(issues)
