import copy
import json
import unittest
from pathlib import Path

from daesingo.recording import (
    ContractValidationError,
    Observation,
    RecordingTimeline,
    SpanResolution,
    TimeSourceCandidate,
)


ROOT = Path(__file__).resolve().parents[2]
MOCK = ROOT / "data" / "mock"


def load_json(relative_path: str):
    with (MOCK / relative_path).open("r", encoding="utf-8") as fixture:
        return json.load(fixture)


class RecordingContractFixtureTests(unittest.TestCase):
    def test_happy_and_partial_fixtures_round_trip(self):
        for scenario in ("happy_001", "partial_001"):
            with self.subTest(scenario=scenario):
                timeline = load_json(f"recording/timeline.{scenario}.json")
                resolution = load_json(f"recording/span_resolution.{scenario}.json")
                candidates = load_json(
                    f"recording/time_source_candidates.{scenario}.json"
                )
                observations = load_json(f"evidence/observations.{scenario}.json")

                self.assertEqual(
                    RecordingTimeline.from_dict(timeline).to_dict(), timeline
                )
                self.assertEqual(
                    SpanResolution.from_dict(resolution).to_dict(), resolution
                )
                self.assertEqual(
                    [TimeSourceCandidate.from_dict(item).to_dict() for item in candidates],
                    candidates,
                )
                self.assertEqual(
                    [Observation.from_dict(item).to_dict() for item in observations],
                    observations,
                )

    def test_partial_requires_usable_and_missing_ranges(self):
        resolution = load_json("recording/span_resolution.partial_001.json")
        resolution["spans"] = []

        with self.assertRaisesRegex(
            ContractValidationError,
            "PARTIAL requires spans and missing_ranges",
        ):
            SpanResolution.from_dict(resolution)

    def test_complete_rejects_missing_range(self):
        resolution = load_json("recording/span_resolution.happy_001.json")
        resolution["missing_ranges"] = [
            {
                "timeline_range": {"start_sec": 700.0, "end_sec": 701.0},
                "reason": "TIMELINE_GAP",
                "source_ref": None,
            }
        ]

        with self.assertRaisesRegex(
            ContractValidationError,
            "COMPLETE requires spans and no missing_ranges",
        ):
            SpanResolution.from_dict(resolution)

    def test_span_outside_requested_range_is_rejected(self):
        resolution = load_json("recording/span_resolution.happy_001.json")
        resolution["spans"][0]["timeline_range"]["end_sec"] = 709.0

        with self.assertRaisesRegex(
            ContractValidationError,
            "outside requested_range",
        ):
            SpanResolution.from_dict(resolution)

    def test_candidate_requires_offset_aware_time(self):
        candidate = load_json("recording/time_source_candidates.happy_001.json")[0]
        candidate["value"] = "2026-08-24T18:20:00"

        with self.assertRaisesRegex(ContractValidationError, "UTC offset"):
            TimeSourceCandidate.from_dict(candidate)

    def test_unknown_observation_requires_reason(self):
        observation = load_json("evidence/observations.happy_001.json")[0]
        observation = copy.deepcopy(observation)
        observation.pop("reason")

        with self.assertRaisesRegex(
            ContractValidationError,
            "UNKNOWN Observation requires reason",
        ):
            Observation.from_dict(observation)


if __name__ == "__main__":
    unittest.main()
