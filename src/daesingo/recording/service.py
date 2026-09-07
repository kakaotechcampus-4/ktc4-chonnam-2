"""Executable recording boundary for the first Mock E2E integration.

The fixture-backed implementation is deliberately replaceable: consumers call
canonical methods and do not know how probing, decoding, or persistence works.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import (
    Interval,
    Observation,
    RecordingTimeline,
    SpanResolution,
    TimeSourceCandidate,
    TimelineRef,
)


class RecordingOutputNotPrepared(LookupError):
    """Raised when the Seed stub has no canonical output for a request."""


class FixtureRecordingService:
    """Canonical recording API backed by one common Mock scenario."""

    def __init__(
        self,
        *,
        timeline: RecordingTimeline,
        span_resolution: SpanResolution,
        time_source_candidates: tuple[TimeSourceCandidate, ...],
        observations: tuple[Observation, ...],
    ) -> None:
        if span_resolution.timeline_ref != TimelineRef(
            timeline_id=timeline.timeline_id,
            revision=timeline.revision,
        ):
            raise ValueError("SpanResolution must reference the supplied RecordingTimeline")
        candidate_ids = {item.candidate_id for item in time_source_candidates}
        if not set(timeline.time_source_candidates).issubset(candidate_ids):
            raise ValueError("RecordingTimeline references an unavailable TimeSourceCandidate")
        self._timeline = timeline
        self._span_resolution = span_resolution
        self._time_source_candidates = time_source_candidates
        self._observations = observations

    @classmethod
    def from_mock_directory(
        cls,
        mock_directory: str | Path,
        scenario: str,
    ) -> "FixtureRecordingService":
        """Load a common `happy_001` or `partial_001` fixture set."""

        root = Path(mock_directory)
        timeline = cls._load_json(root / "recording" / f"timeline.{scenario}.json")
        resolution = cls._load_json(
            root / "recording" / f"span_resolution.{scenario}.json"
        )
        candidates = cls._load_json(
            root / "recording" / f"time_source_candidates.{scenario}.json"
        )
        observations = cls._load_json(
            root / "evidence" / f"observations.{scenario}.json"
        )
        if not isinstance(candidates, list) or not isinstance(observations, list):
            raise ValueError("candidate and observation fixtures must be arrays")
        return cls(
            timeline=RecordingTimeline.from_dict(timeline),
            span_resolution=SpanResolution.from_dict(resolution),
            time_source_candidates=tuple(
                TimeSourceCandidate.from_dict(item) for item in candidates
            ),
            observations=tuple(Observation.from_dict(item) for item in observations),
        )

    @staticmethod
    def _load_json(path: Path) -> Any:
        with path.open("r", encoding="utf-8") as fixture:
            return json.load(fixture)

    def get_timeline(self, timeline_id: str, revision: int) -> RecordingTimeline:
        if timeline_id != self._timeline.timeline_id or revision != self._timeline.revision:
            raise RecordingOutputNotPrepared(
                f"timeline output not prepared: {timeline_id}@{revision}"
            )
        return self._timeline

    def resolve_span(
        self,
        timeline_ref: TimelineRef,
        requested_range: Interval,
    ) -> SpanResolution:
        """Return the canonical prepared resolution for an exact Seed request."""

        prepared = self._span_resolution
        if timeline_ref != prepared.timeline_ref or requested_range != prepared.requested_range:
            raise RecordingOutputNotPrepared(
                "span output is not prepared for the requested timeline revision and range"
            )
        return prepared

    def list_time_source_candidates(
        self,
        source_asset_ref: str | None = None,
    ) -> tuple[TimeSourceCandidate, ...]:
        if source_asset_ref is None:
            return self._time_source_candidates
        return tuple(
            item
            for item in self._time_source_candidates
            if item.applies_to["source_asset_ref"] == source_asset_ref
        )

    def list_observations(self) -> tuple[Observation, ...]:
        return self._observations

    def export_artifacts(self) -> dict[str, Any]:
        """Expose JSON-ready canonical outputs to integration consumers."""

        return {
            "timeline": self._timeline.to_dict(),
            "span_resolution": self._span_resolution.to_dict(),
            "time_source_candidates": [
                item.to_dict() for item in self._time_source_candidates
            ],
            "observations": [item.to_dict() for item in self._observations],
        }
