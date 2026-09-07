import unittest
from pathlib import Path

from daesingo.recording import FixtureRecordingService, RecordingOutputNotPrepared
from daesingo.recording.contracts import Interval, TimelineRef


ROOT = Path(__file__).resolve().parents[2]
MOCK = ROOT / "data" / "mock"


class FixtureRecordingServiceTests(unittest.TestCase):
    def test_happy_scenario_is_complete(self):
        service = FixtureRecordingService.from_mock_directory(MOCK, "happy_001")

        result = service.resolve_span(
            TimelineRef("tl_h001", 1),
            Interval(690.0, 708.0),
        )

        self.assertEqual(result.status.value, "COMPLETE")
        self.assertEqual(len(result.spans), 1)
        self.assertEqual(result.missing_ranges, ())
        self.assertEqual(result.spans[0].media_stream_ref, "ms_h001_01")

    def test_partial_scenario_preserves_usable_and_missing_ranges(self):
        service = FixtureRecordingService.from_mock_directory(MOCK, "partial_001")

        result = service.resolve_span(
            TimelineRef("tl_p001", 1),
            Interval(1180.0, 1260.0),
        )

        self.assertEqual(result.status.value, "PARTIAL")
        self.assertEqual(result.spans[0].timeline_range, Interval(1180.0, 1200.0))
        self.assertEqual(
            result.missing_ranges[0].timeline_range,
            Interval(1200.0, 1260.0),
        )
        self.assertEqual(
            service.get_timeline("tl_p001", 1).timeline_status.value,
            "PARTIAL",
        )

    def test_gps_absence_stays_unknown(self):
        service = FixtureRecordingService.from_mock_directory(MOCK, "happy_001")

        observation = service.list_observations()[0]

        self.assertIsNone(observation.value)
        self.assertEqual(observation.status.value, "UNKNOWN")
        self.assertEqual(observation.reason["code"], "recording.gps.source_absent")

    def test_unknown_request_is_not_fabricated(self):
        service = FixtureRecordingService.from_mock_directory(MOCK, "happy_001")

        with self.assertRaises(RecordingOutputNotPrepared):
            service.resolve_span(
                TimelineRef("tl_h001", 1),
                Interval(0.0, 1.0),
            )

    def test_exports_json_ready_contract_artifacts(self):
        service = FixtureRecordingService.from_mock_directory(MOCK, "happy_001")

        artifacts = service.export_artifacts()

        self.assertEqual(artifacts["timeline"]["timeline_id"], "tl_h001")
        self.assertEqual(artifacts["span_resolution"]["status"], "COMPLETE")
        self.assertEqual(
            artifacts["time_source_candidates"][0]["candidate_id"],
            "tsc_h001_filename",
        )


if __name__ == "__main__":
    unittest.main()
