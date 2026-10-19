"""Existing repository semantics: no new public capability is defined here."""

from io import BytesIO
from datetime import timezone

import pytest

from daesingo.recording import RecordingService, load_recording_fixture
from daesingo.recording.models import FailureDetail, SpanResolution, TimeRange
from daesingo.recording.repository import InMemoryRecordingRepository
from test_recording_repository_mysql import adapter, db, check

pytestmark = pytest.mark.mysql


@check("compatibility", "fixture")
def test_fixture_repository_semantics_match_in_memory(db):
    engine, root = db
    fixture = load_recording_fixture("scenario_happy_001")
    with engine.begin() as conn:
        for repo in (InMemoryRecordingRepository(), adapter(conn, root)):
            for asset in fixture.source_assets:
                repo.add_source_asset(asset)
            for stream in fixture.media_streams:
                repo.add_media_stream(stream)
            gps = fixture.gps_observations[0]
            repo.add_gps_observation(gps)
            restored, = repo.list_gps_observations()
            assert restored.model_dump(exclude_unset=True) == gps.model_dump(exclude_unset=True)
            zero_gps = gps.model_copy(update={"value": gps.value.model_copy(update={"lat": 0.0, "lon": 0.0})})
            repo.add_gps_observation(zero_gps)
            for coordinate in ("lat", "lon"):
                same_gps = zero_gps.model_copy(update={"value": zero_gps.value.model_copy(update={coordinate: -0.0})})
                assert same_gps == zero_gps
                with pytest.raises(ValueError, match="GPS"):
                    repo.add_gps_observation(same_gps)
            # Decimal equality in the existing repository treats -0.0 as 0.0.
            zero = fixture.frame_refs[0].model_copy(update={"source_offset_sec": 0.0})
            repo.add_frame(zero, content=b"zero")
            repo.add_frame(zero)
            service = RecordingService(repo)
            assert service.resolve_frame({"kind": "STREAM_POSITION", "media_stream_ref": zero.media_stream_ref,
                                          "source_offset_sec": -0.0}) == zero
            assert service.read_frame(zero.frame_ref) == b"zero"
            resolution = SpanResolution(contract="SpanResolution", contract_version="span-resolution/v1.2",
                timeline_ref=fixture.span_resolutions[0].timeline_ref,
                requested_range=TimeRange(start_sec=0.0, end_sec=1.0), status="FAILED",
                spans=[], missing_ranges=[], failure=FailureDetail(kind="UNAVAILABLE", code="NO_USABLE_SPAN"))
            repo.add_span_resolution(resolution)
            assert repo.get_span_resolution(resolution.timeline_ref,
                TimeRange(start_sec=-0.0, end_sec=1.0)) == resolution
            # Equal aware datetimes retain the in-memory model comparison rule.
            timeline = fixture.recording_timelines[0]
            anchor = timeline.time_basis.working_anchor
            equivalent = timeline.model_copy(update={"time_basis": timeline.time_basis.model_copy(update={
                "working_anchor": anchor.model_copy(update={"value": anchor.value.astimezone(timezone.utc)})})})
            assert equivalent == timeline
            repo.add_timeline(timeline)
            repo.add_timeline(equivalent)
            assert repo.get_latest_timeline(timeline.timeline_id) == timeline
            for facts in fixture.asset_facts:
                repo.add_asset_facts(facts)
                assert repo.get_asset_facts(facts.asset_ref.kind, facts.asset_ref.ref) == facts
            for source in fixture.analysis_sources:
                repo.add_analysis_source(source, stream_factory=lambda: BytesIO(b"analysis"), content_type="video/mp4")
                assert repo.get_analysis_source(source.analysis_source_ref) == source
                stream, content_type = repo.open_analysis_stream(source.analysis_source_ref)
                with stream:
                    assert stream.read() == b"analysis" and content_type == "video/mp4"
            for clip in fixture.incident_clips:
                repo.add_incident_clip(clip)
                assert repo.get_incident_clip(clip.incident_clip_ref) == clip
            for remote in fixture.remote_copies:
                repo.add_remote_copy(remote)
                later = remote.model_copy(update={"remote_copy_ref": "later-" + remote.remote_copy_ref})
                repo.add_remote_copy(later)
                equivalent = remote.model_copy(update={"expires_at": remote.expires_at.astimezone(timezone.utc)})
                assert equivalent == remote
                repo.add_remote_copy(equivalent)
                assert repo.get_remote_copy(remote.analysis_source_ref, remote.provider) == remote
                assert repo.get_remote_copy_by_ref(later.remote_copy_ref) == later


@check("restore", "png_bytes")
def test_real_png_frame_bytes_survive_service_restart_and_missing_original(db):
    import subprocess
    from daesingo.recording import RecordingService
    engine, root = db
    path = root / "original.mkv"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
                    "color=c=blue:s=32x24:r=5:d=1", "-c:v", "ffv1", str(path)],
                   check=True, capture_output=True, timeout=30)
    original = path.read_bytes()
    with engine.begin() as conn:
        service = RecordingService(adapter(conn, root))
        registered = service.register_local_source(path)
        frame = service.resolve_frame({"kind": "STREAM_POSITION",
            "media_stream_ref": registered.media_streams[0].media_stream_ref, "source_offset_sec": 0.1})
        expected = service.read_frame(frame.frame_ref)
        assert expected.startswith(b"\x89PNG\r\n\x1a\n")
        assert path.read_bytes() == original
        service.close()
    path.unlink()
    with engine.begin() as conn:
        assert RecordingService(adapter(conn, root)).read_frame(frame.frame_ref) == expected
    assert list(root.iterdir()) == []


@check("transaction", "no_completion")
def test_adapter_does_not_end_the_caller_transaction(db):
    import sqlalchemy as sa
    engine, root = db
    endings = []
    with engine.connect() as conn:
        tx = conn.begin()
        sa.event.listen(conn, "commit", lambda c: endings.append("commit"))
        sa.event.listen(conn, "rollback", lambda c: endings.append("rollback"))
        repo = adapter(conn, root)
        asset = load_recording_fixture("scenario_happy_001").source_assets[0]
        repo.add_source_asset(asset)
        assert repo.get_source_asset(asset.source_asset_ref) == asset
        assert conn.in_transaction() and endings == []
        tx.rollback()
        assert endings == ["rollback"]
