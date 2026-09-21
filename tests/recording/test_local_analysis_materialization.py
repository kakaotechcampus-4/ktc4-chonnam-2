"""Real local media path tests without provider calls or user video fixtures."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
import os
from pathlib import Path

from daesingo.recording import (
    FfprobeMediaProbe,
    LocalAnalysisMaterializer,
    LocalAnalysisProfile,
    RecordingCapabilityError,
    RecordingService,
    load_recording_fixture,
)


FFMPEG = os.environ.get("DAESINGO_FFMPEG") or shutil.which("ffmpeg")
FFPROBE = os.environ.get("DAESINGO_FFPROBE") or shutil.which("ffprobe")


def selected_video_ref(registered) -> str:
    return next(
        stream.media_stream_ref for stream in registered.media_streams
        if stream.media_type == "VIDEO"
    )


@unittest.skipUnless(FFMPEG and FFPROBE, "ffmpeg/ffprobe required")
class LocalAnalysisMaterializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory(prefix="recording-media-test-")
        self.path = Path(self.folder.name) / "source.mp4"
        subprocess.run(
            [
                FFMPEG, "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10",
                "-t", "3", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(self.path),
            ],
            check=True, capture_output=True, timeout=30,
        )

    def tearDown(self) -> None:
        self.folder.cleanup()

    def test_full_and_partial_source_are_real_mp4_and_reused(self) -> None:
        materializer = LocalAnalysisMaterializer(
            ffmpeg_executable=FFMPEG, ffprobe_executable=FFPROBE,
            temp_root=Path(self.folder.name),
        )
        temp_path = materializer.temp_path
        with RecordingService(
            media_probe=FfprobeMediaProbe(executable=FFPROBE),
            analysis_profiles={"test-480p": LocalAnalysisProfile(height=480)},
            media_materializer=materializer,
        ) as service:
            registered = service.register_local_source(self.path)
            timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
            for start, end in ((0.0, timeline.source_placements[0].timeline_end_sec), (0.4, 2.2)):
                resolution = service.resolve_span(
                    {"timeline_id": timeline.timeline_id, "revision": 1},
                    {"start_sec": start, "end_sec": end},
                    media_stream_ref=selected_video_ref(registered),
                )
                self.assertEqual(resolution.status, "COMPLETE")
                self.assertEqual(len(resolution.spans), 1)
                span = resolution.spans[0]
                source = service.prepare_analysis_source(span, "test-480p")
                reused = service.prepare_analysis_source(span, "test-480p")
                self.assertEqual(reused.analysis_source_ref, source.analysis_source_ref)
                self.assertEqual(source.timeline_ref, resolution.timeline_ref)
                self.assertEqual(source.timeline_range, span.timeline_range)
                self.assertLessEqual(abs(source.duration_sec - (end - start)), 0.15)
                facts = service.lookup_asset_facts({
                    "kind": "analysis_source", "ref": source.analysis_source_ref,
                })
                self.assertEqual(facts.byte_size, source.byte_size)
                self.assertEqual(facts.timeline_range, source.timeline_range)
                opened = service.open_analysis_source(source.analysis_source_ref)
                self.assertEqual(opened.content_type, "video/mp4")
                with opened.stream as stream:
                    payload = stream.read()
                self.assertEqual(len(payload), opened.byte_size)
                self.assertEqual(opened.byte_size, source.byte_size)
                self.assertIn(b"ftyp", payload[:16])
            self.assertEqual(len(list(temp_path.glob("*.mp4"))), 2)
        self.assertFalse(temp_path.exists())
        with self.assertRaises(RecordingCapabilityError) as caught:
            service.open_analysis_source(source.analysis_source_ref)
        self.assertEqual(caught.exception.code, "UNAVAILABLE")

    def test_encoder_failure_leaves_no_temp_media(self) -> None:
        materializer = LocalAnalysisMaterializer(
            ffmpeg_executable="missing-ffmpeg-for-test", ffprobe_executable=FFPROBE,
            temp_root=Path(self.folder.name),
        )
        temp_path = materializer.temp_path
        with RecordingService(
            media_probe=FfprobeMediaProbe(executable=FFPROBE),
            analysis_profiles={"test-480p": LocalAnalysisProfile(height=480)},
            media_materializer=materializer,
        ) as service:
            registered = service.register_local_source(self.path)
            timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
            span = service.resolve_span(
                {"timeline_id": timeline.timeline_id, "revision": 1},
                {"start_sec": 0.0, "end_sec": 1.0},
                media_stream_ref=selected_video_ref(registered),
            ).spans[0]
            with self.assertRaises(RecordingCapabilityError) as caught:
                service.prepare_analysis_source(span, "test-480p")
            self.assertEqual(caught.exception.code, "TEMPORARY_FAILURE")
            self.assertFalse(list(temp_path.glob("*.mp4")))
        self.assertFalse(temp_path.exists())

    def test_encoder_timeout_leaves_no_temp_media(self) -> None:
        materializer = LocalAnalysisMaterializer(
            ffmpeg_executable=FFMPEG, ffprobe_executable=FFPROBE,
            timeout_sec=0.0001, temp_root=Path(self.folder.name),
        )
        temp_path = materializer.temp_path
        with RecordingService(
            media_probe=FfprobeMediaProbe(executable=FFPROBE),
            analysis_profiles={"test-480p": LocalAnalysisProfile(height=480)},
            media_materializer=materializer,
        ) as service:
            registered = service.register_local_source(self.path)
            timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
            span = service.resolve_span(
                {"timeline_id": timeline.timeline_id, "revision": 1},
                {"start_sec": 0.0, "end_sec": 2.0},
                media_stream_ref=selected_video_ref(registered),
            ).spans[0]
            with self.assertRaises(RecordingCapabilityError) as caught:
                service.prepare_analysis_source(span, "test-480p")
            self.assertEqual(caught.exception.code, "TEMPORARY_FAILURE")
            self.assertFalse(list(temp_path.glob("*.mp4")))
        self.assertFalse(temp_path.exists())

    def test_source_changed_after_registration_is_rejected(self) -> None:
        materializer = LocalAnalysisMaterializer(
            ffmpeg_executable=FFMPEG, ffprobe_executable=FFPROBE,
            temp_root=Path(self.folder.name),
        )
        temp_path = materializer.temp_path
        with RecordingService(
            media_probe=FfprobeMediaProbe(executable=FFPROBE),
            analysis_profiles={"test-480p": LocalAnalysisProfile(height=480)},
            media_materializer=materializer,
        ) as service:
            registered = service.register_local_source(self.path)
            timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
            span = service.resolve_span(
                {"timeline_id": timeline.timeline_id, "revision": 1},
                {"start_sec": 0.0, "end_sec": 2.0},
                media_stream_ref=selected_video_ref(registered),
            ).spans[0]
            with self.path.open("ab") as source_file:
                source_file.write(b"changed")
            with self.assertRaises(RecordingCapabilityError) as caught:
                service.prepare_analysis_source(span, "test-480p")
            self.assertEqual(caught.exception.code, "SOURCE_UNAVAILABLE")
            self.assertFalse(list(temp_path.glob("*.mp4")))
        self.assertFalse(temp_path.exists())

    def test_reuse_rejects_changed_source(self) -> None:
        materializer = LocalAnalysisMaterializer(
            ffmpeg_executable=FFMPEG, ffprobe_executable=FFPROBE,
            temp_root=Path(self.folder.name),
        )
        with RecordingService(
            media_probe=FfprobeMediaProbe(executable=FFPROBE),
            analysis_profiles={"test-480p": LocalAnalysisProfile(height=480)},
            media_materializer=materializer,
        ) as service:
            registered = service.register_local_source(self.path)
            timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
            span = service.resolve_span(
                {"timeline_id": timeline.timeline_id, "revision": 1},
                {"start_sec": 0.0, "end_sec": 1.0},
                media_stream_ref=selected_video_ref(registered),
            ).spans[0]
            service.prepare_analysis_source(span, "test-480p")
            with self.path.open("ab") as source_file:
                source_file.write(b"changed")
            with self.assertRaises(RecordingCapabilityError) as caught:
                service.prepare_analysis_source(span, "test-480p")
            self.assertEqual(caught.exception.code, "SOURCE_UNAVAILABLE")

    def test_out_of_range_is_not_misreported_complete(self) -> None:
        service = RecordingService(media_probe=FfprobeMediaProbe(executable=FFPROBE))
        registered = service.register_local_source(self.path)
        timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
        resolution = service.resolve_span(
            {"timeline_id": timeline.timeline_id, "revision": 1},
            {"start_sec": 3.1, "end_sec": 4.0},
            media_stream_ref=selected_video_ref(registered),
        )
        self.assertEqual(resolution.status, "FAILED")
        self.assertFalse(resolution.spans)


class FixtureCompatibilityTests(unittest.TestCase):
    def test_existing_fixture_analysis_source_still_opens(self) -> None:
        fixture = load_recording_fixture("scenario_happy_001")
        service = RecordingService.from_fixture(fixture)
        source = service.prepare_analysis_source(fixture.span_resolutions[0].spans[0], "prof_fine_v1")
        opened = service.open_analysis_source(source.analysis_source_ref)
        with opened.stream as stream:
            self.assertEqual(stream.read(8), bytes(8))


if __name__ == "__main__":
    unittest.main()
