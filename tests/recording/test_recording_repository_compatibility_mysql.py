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
        image = RecordingService(adapter(conn, root)).read_frame_image(frame.frame_ref)
        assert image.content == expected and image.content_type == "image/png" and image.image_format == "png"
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


# A SQL collation alias must never become an ownership or deletion authority.
EXACT_PAIRS = (
    ("space", "case-a", "case-a "),
    ("case", "case-a", "CASE-A"),
    ("unicode", "caf\u00e9", "cafe\u0301"),
    ("unicode_case", "\u00e9", "\u00c9"),
)


def exact_chain(repo, case_id, source_ref, stream_ref, frame_ref, derived_ref):
    from daesingo.recording import ContractRef
    from test_ownership_reads import PNG, asset

    fixture = load_recording_fixture("scenario_happy_001")
    frame = fixture.frame_refs[0].model_copy(update={"frame_ref": frame_ref, "media_stream_ref": stream_ref})
    stream = next(s for s in fixture.media_streams if s.media_stream_ref == fixture.frame_refs[0].media_stream_ref)
    source = next(a for a in fixture.source_assets if a.source_asset_ref == stream.source_asset_ref)
    repo.add_source_asset(source.model_copy(update={"source_asset_ref": source_ref, "media_stream_refs": [stream_ref]}))
    repo.add_media_stream(stream.model_copy(update={"media_stream_ref": stream_ref, "source_asset_ref": source_ref}))
    repo.add_frame(frame, content=PNG)
    repo.associate_case_asset(case_id, ContractRef(kind="source_asset", ref=source_ref))
    repo.add_derived_asset(asset(derived_asset_ref=derived_ref), case_id=case_id)
    return [ContractRef(kind="source_asset", ref=source_ref), ContractRef(kind="derived_asset", ref=derived_ref)]


@pytest.mark.parametrize("layer,name,left,right", [
    pytest.param(layer, name, left, right, id=layer+"_"+name,
                 marks=check("exact_ownership", layer+"_"+name))
    for layer in ("scope", "source", "stream", "frame", "derived")
    for name, left, right in EXACT_PAIRS
])
def test_recording_exact_identity_isolates_both_directions(db, layer, name, left, right):
    from daesingo.recording import RecordingCapabilityError
    from test_ownership_reads import PNG

    engine, root = db
    chains = []
    with engine.begin() as conn:
        repo = adapter(conn, root)
        for index, value in enumerate((left, right)):
            values = dict(scope=f"owner-{index}", source=f"source-{index}", stream=f"stream-{index}",
                          frame=f"frame-{index}", derived=f"derived-{index}")
            values[layer] = value
            refs = exact_chain(repo, *values.values())
            chains.append((values, refs))
    with engine.begin() as conn:
        repo = adapter(conn, root)
        service = RecordingService(repo)
        for index, (own, refs) in enumerate(chains):
            foreign, foreign_refs = chains[1-index]
            assert repo.get_case_assets(own["scope"]) == refs
            for ref in refs:
                assert service.owns_asset(own["scope"], ref) is True
            for ref in foreign_refs:
                assert service.owns_asset(own["scope"], ref) is False
            assert service.owns_frame(own["scope"], own["frame"]) is True
            assert service.owns_frame(own["scope"], foreign["frame"]) is False
            assert service.read_owned_frame_image(own["scope"], own["frame"]).content == PNG
            for ref in (foreign["frame"], "unknown"):
                assert service.owns_frame(own["scope"], ref) is False
                with pytest.raises(RecordingCapabilityError) as error:
                    service.read_owned_frame_image(own["scope"], ref)
                assert error.value.code == "UNKNOWN_REF"


@pytest.mark.parametrize("reverse", [
    pytest.param(False, marks=check("exact_purge", "forward")),
    pytest.param(True, marks=check("exact_purge", "reverse")),
])
def test_purge_exact_scope_and_caller_rollback(db, reverse):
    import sqlalchemy as sa
    engine, root = db
    scopes = ("case-a ", "case-a") if reverse else ("case-a", "case-a ")
    with engine.begin() as conn:
        refs = [exact_chain(adapter(conn, root), scope, f"s-{i}", f"m-{i}", f"f-{i}", f"d-{i}")
                for i, scope in enumerate(scopes)]
    with engine.connect() as conn:
        tx = conn.begin()
        endings = []
        sa.event.listen(conn, "commit", lambda c: endings.append("commit"))
        sa.event.listen(conn, "rollback", lambda c: endings.append("rollback"))
        service = RecordingService(adapter(conn, root))
        report = service.purge_case(scopes[0])
        assert [item.asset_ref for item in report.items] == refs[0]
        assert all(item.result == "DELETED" for item in report.items)
        assert service.purge_case("unknown").items == []
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM recording_entry WHERE kind='deleted'").scalar_one() == 2
        assert conn.in_transaction() and endings == []
        tx.rollback()
        assert endings == ["rollback"]
    with engine.begin() as conn:
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM recording_entry WHERE kind='deleted'").scalar_one() == 0
        service = RecordingService(adapter(conn, root))
        assert all(item.result == "DELETED" for item in service.purge_case(scopes[1]).items)
        assert all(item.result == "DELETED" for item in service.purge_case(scopes[0]).items)


@pytest.mark.parametrize("kind", [
    pytest.param(kind, marks=check("exact_privacy", kind))
    for kind in ("source_asset", "derived_asset", "frame", "media_stream", "case_asset")
])
def test_foreign_damaged_metadata_has_unknown_semantics(db, kind):
    from daesingo.recording import RecordingCapabilityError, ContractRef
    engine, root = db
    with engine.begin() as conn:
        exact_chain(adapter(conn, root), "case-a", "source", "stream", "frame", "derived")
        field = {"source_asset": "availability", "derived_asset": "availability", "frame": "source_offset_sec",
                 "media_stream": "media_type", "case_asset": "asset_ref"}[kind]
        conn.exec_driver_sql("UPDATE recording_entry SET payload=JSON_SET(payload, %s, 'PRIVATE_METADATA') WHERE kind=%s",
                             ("$."+field, kind))
    with engine.begin() as conn:
        repo = adapter(conn, root)
        service = RecordingService(repo)
        for scope in ("foreign", "case-a "):
            assert repo.get_case_assets(scope) == []
            for ref in ("source", "unknown"):
                assert service.owns_asset(scope, ContractRef(kind="source_asset", ref=ref)) is False
            for ref in ("derived", "unknown"):
                assert service.owns_asset(scope, ContractRef(kind="derived_asset", ref=ref)) is False
            for ref in ("frame", "unknown"):
                assert service.owns_frame(scope, ref) is False
                with pytest.raises(RecordingCapabilityError) as error:
                    service.read_owned_frame_image(scope, ref)
                assert error.value.code == "UNKNOWN_REF"
                assert "PRIVATE_METADATA" not in str(error.value)
            assert service.purge_case(scope).items == []
        if kind == "case_asset":
            with pytest.raises(RecordingCapabilityError) as error:
                service.purge_case("case-a")
            assert error.value.code == "TEMPORARY_FAILURE"
            assert "PRIVATE_METADATA" not in str(error.value) and "input_value" not in str(error.value)


@check("exact_ownership", "concurrent")
def test_exact_scope_remains_isolated_during_uncommitted_purge(db):
    from concurrent.futures import ThreadPoolExecutor
    engine, root = db
    with engine.begin() as conn:
        exact_chain(adapter(conn, root), "case-a", "source", "stream", "frame", "derived")
        exact_chain(adapter(conn, root), "case-a ", "source ", "stream ", "frame ", "derived ")
    with engine.connect() as conn:
        tx = conn.begin()
        report = RecordingService(adapter(conn, root)).purge_case("case-a")
        assert len(report.items) == 2
        def read_other():
            with engine.begin() as other:
                service = RecordingService(adapter(other, root))
                assert service.owns_frame("case-a ", "frame ") is True
                assert service.owns_frame("case-a ", "frame") is False
                assert len(service.purge_case("case-a ").items) == 2
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(read_other).result(timeout=5)
        tx.rollback()


@pytest.mark.parametrize("kind", [
    pytest.param(kind, marks=check("exact_privacy", kind+"_identity"))
    for kind in ("source_asset", "derived_asset")
])
def test_damaged_asset_identity_cannot_authorize_requested_ref(db, kind):
    from daesingo.recording import ContractRef
    engine, root = db
    with engine.begin() as conn:
        exact_chain(adapter(conn, root), "case-a", "source", "stream", "frame", "derived")
        conn.exec_driver_sql("UPDATE recording_entry SET payload=JSON_SET(payload, %s, 'FOREIGN_REF') WHERE kind=%s",
                             ("$."+kind+"_ref", kind))
    with engine.begin() as conn:
        service = RecordingService(adapter(conn, root))
        assert service.owns_asset("case-a", ContractRef(kind=kind, ref="source" if kind == "source_asset" else "derived")) is False


@pytest.mark.parametrize("damage", [
    pytest.param(damage, marks=check("exact_privacy", damage))
    for damage in ("nonstring_case", "padded_kind")
])
def test_damaged_association_cannot_become_a_scope(db, damage):
    engine, root = db
    with engine.begin() as conn:
        exact_chain(adapter(conn, root), "123", "source", "stream", "frame", "derived")
        if damage == "nonstring_case":
            conn.exec_driver_sql("UPDATE recording_entry SET payload=JSON_SET(payload, '$.case_id', 123) WHERE kind='case_asset'")
        else:
            conn.exec_driver_sql("UPDATE recording_entry SET kind='case_asset ' WHERE kind='case_asset'")
    with engine.begin() as conn:
        repo = adapter(conn, root)
        assert repo.get_case_assets("123") == []
        assert RecordingService(repo).purge_case("123").items == []


@check("exact_privacy", "remote_copy")
def test_purge_damaged_remote_metadata_is_sanitized_after_exact_scope(db):
    from daesingo.recording import ContractRef, RecordingCapabilityError
    engine, root = db
    remote = load_recording_fixture("scenario_happy_001").remote_copies[0]
    with engine.begin() as conn:
        repo = adapter(conn, root)
        repo.add_remote_copy(remote)
        repo.associate_case_asset("case-a", ContractRef(kind="remote_copy", ref=remote.remote_copy_ref))
        conn.exec_driver_sql("UPDATE recording_entry SET payload=JSON_SET(payload, '$.expires_at', 'PRIVATE_METADATA') WHERE kind='remote_copy'")
    with engine.begin() as conn:
        service = RecordingService(adapter(conn, root))
        assert service.purge_case("case-a ").items == service.purge_case("unknown").items == []
        with pytest.raises(RecordingCapabilityError) as error:
            service.purge_case("case-a")
        assert error.value.code == "TEMPORARY_FAILURE"
        assert "PRIVATE_METADATA" not in str(error.value) and "input_value" not in str(error.value)
