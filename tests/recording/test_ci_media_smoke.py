"""Required synthetic CI smoke: missing tools or failed generation must fail, never skip."""

import shutil
import subprocess

from daesingo.recording import (
    AnalysisProfile, IncidentClipEncoding, LocalAnalysisMaterializer,
    LocalIncidentMaterializer, RecordingService,
)
from tests.recording.test_local_analysis_source import fingerprint, inspect_bytes
from tests.recording.test_local_incident_clip import readout_frame


def test_ci_synthetic_media_public_path(tmp_path):
    for tool in ("ffmpeg", "ffprobe"):
        assert shutil.which(tool), f"CI media smoke requires {tool}"
    source = tmp_path / "synthetic.avi"
    subprocess.run([
        "ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
        "testsrc2=s=160x90:r=10:d=2", "-f", "lavfi", "-i", "sine=duration=2",
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "mpeg4", "-c:a", "pcm_s16le",
        str(source),
    ], check=True, capture_output=True, timeout=30)
    before = fingerprint(source)
    work = tmp_path / "materialization"
    work.mkdir()
    profile = "ci-analysis"
    service = RecordingService(
        analysis_materializer=LocalAnalysisMaterializer(
            {profile: AnalysisProfile(480, "veryfast", 23)}, temp_root=work),
        incident_materializer=LocalIncidentMaterializer(
            IncidentClipEncoding(480, "veryfast", 23), temp_root=work),
    )
    try:
        with service:
            registered = service.register_local_source(source)
            assert registered.source_asset.byte_size == before[0]
            video, = [s for s in registered.media_streams if s.media_type == "VIDEO"]
            timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
            assert timeline.timeline_status == "USABLE_RELATIVE_ONLY"
            ref = {"timeline_id": timeline.timeline_id, "revision": timeline.revision}
            resolutions = []
            for start, end in ((0.0, 2.0), (0.5, 1.5)):
                resolved = service.resolve_span(ref, {"start_sec": start, "end_sec": end},
                                                media_stream_ref=video.media_stream_ref)
                assert resolved.status == "COMPLETE" and not resolved.missing_ranges
                span, = resolved.spans
                assert span.media_stream_ref == video.media_stream_ref
                resolutions.append(resolved)
            analysis = service.prepare_analysis_source(resolutions[0].spans[0], profile, timeline_ref=ref)
            assert analysis.duration_sec == 2.0
            assert analysis.timeline_range == resolutions[0].requested_range
            assert analysis.media_stream_refs == [video.media_stream_ref]
            # Two independent public streams, actual size, ffprobe codec/coverage and decode.
            inspect_bytes(service, analysis, tmp_path)
            clip = service.build_incident_clip(resolutions[1])
            assert service.get_incident_clip(clip.incident_clip_ref) == clip
            assert clip.availability == "AVAILABLE" and clip.byte_size > 0
            assert clip.duration_sec == 1.0 and clip.timeline_range == resolutions[1].requested_range
            assert clip.source_provenance.timeline_ref == resolutions[1].timeline_ref
            assert clip.source_provenance.requested_range == resolutions[1].requested_range
            assert clip.source_provenance.asset_spans == resolutions[1].spans
            # Readout consumes provenance -> STREAM_POSITION -> PNG, not clip bytes.
            readout_frame(service, clip)
            assert source.name not in analysis.model_dump_json() + clip.model_dump_json()
    finally:
        assert fingerprint(source) == before
        assert not list(work.iterdir())
