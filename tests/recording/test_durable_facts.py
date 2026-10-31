"""Recording's public facts must survive a new service, never Runtime schema reads."""
from dataclasses import replace

import pytest

from daesingo import recording
from daesingo.recording import RecordingService, ContractRef, load_recording_fixture
from daesingo.recording.repository import InMemoryRecordingRepository
from test_ownership_reads import MP4, OTHER_MP4


def test_legacy_lookup_still_refuses_unobserved_metadata_while_new_query_reports_unknown():
    repo = InMemoryRecordingRepository()
    model = load_recording_fixture("scenario_happy_001").source_assets[0]
    model = model.model_copy(update={"external_source_ref": ContractRef(kind="external_source", ref="original")})
    repo.add_source_asset(model)
    ref = ContractRef(kind="source_asset", ref=model.source_asset_ref)
    repo.associate_case_asset("case", ref)
    with RecordingService(repo) as service:
        with pytest.raises(recording.RecordingCapabilityError) as caught:
            service.lookup_asset_facts(ref)
        assert caught.value.code == "UNKNOWN_REF"
        facts, = service.list_case_asset_facts("case")
        assert facts.availability == "UNKNOWN" and facts.byte_size is None
        assert [r.model_dump() for r in facts.lineage] == [{"kind": "external_source", "ref": "original"}]


@pytest.mark.parametrize("kind", ["analysis_source", "incident_clip"])
def test_durable_publication_keeps_case_link_atomic_on_conflict(kind):
    fixture = load_recording_fixture("scenario_happy_001")
    model = (fixture.analysis_sources if kind == "analysis_source" else fixture.incident_clips)[0]
    model = model.model_copy(update={"byte_size": len(MP4), "availability": "AVAILABLE"})
    repo = InMemoryRecordingRepository()
    repo.add_prepared_media(model, MP4, case_id="case-a")
    with pytest.raises(ValueError): repo.add_prepared_media(model, OTHER_MP4, case_id="case-b")
    assert repo.get_case_assets("case-b") == []
    assert len(repo.get_case_assets("case-a")) == 1


@pytest.mark.parametrize("kind", ["analysis_source", "incident_clip"])
def test_prepared_bytes_and_metadata_are_detached_immutable_and_reopenable(kind):
    fixture = load_recording_fixture("scenario_happy_001")
    model = fixture.analysis_sources[0] if kind == "analysis_source" else fixture.incident_clips[0]
    model = model.model_copy(update={"byte_size": len(MP4), "availability": "AVAILABLE"})
    ref = getattr(model, "analysis_source_ref" if kind == "analysis_source" else "incident_clip_ref")
    repo = InMemoryRecordingRepository()
    repo.add_prepared_media(model, MP4)
    repo.add_prepared_media(model, MP4)
    with pytest.raises(ValueError): repo.add_prepared_media(model, OTHER_MP4)
    with RecordingService(repo) as first:
        if kind == "analysis_source":
            opened = first.open_analysis_source(ref)
            with opened.stream: assert opened.stream.read() == MP4
        else:
            assert first.get_incident_clip(ref) == model
            assert repo.get_prepared_content(ContractRef(kind=kind, ref=ref)) == (MP4, "video/mp4")
    with RecordingService(repo) as second:
        value = second.get_analysis_source(ref) if kind == "analysis_source" else second.get_incident_clip(ref)
        assert value == model
        value.media_stream_refs.clear()
        other = second.get_analysis_source(ref) if kind == "analysis_source" else second.get_incident_clip(ref)
        assert other.media_stream_refs
        if kind == "analysis_source":
            opened = second.open_analysis_source(ref)
            with opened.stream: assert opened.stream.read() == MP4
        else:
            assert repo.get_prepared_content(ContractRef(kind=kind, ref=ref)) == (MP4, "video/mp4")


def test_public_case_fact_queries_return_contract_json_and_detached_values():
    fixture = load_recording_fixture("scenario_happy_001")
    seeded = RecordingService.from_fixture(fixture, case_id="case-a")
    repo = seeded._repository  # test fixture setup; production consumes only public queries
    seeded.close()
    query = recording.RecordingFacts(repo)
    clip = fixture.incident_clips[0]
    assert query.get_incident_clip(clip.incident_clip_ref) == clip.model_dump(mode="json")
    values = query.list_case_asset_facts("case-a")
    assert len(values) == 4 and all(v["contract"] == "AssetFacts" for v in values)
    assert all(v["asset_ref"]["kind"] != "remote_copy" for v in values)
    assert query.list_case_asset_facts("case-b") == []
    values[0]["lineage"].clear()
    assert query.get_incident_clip(clip.incident_clip_ref)["source_provenance"]
    assert query.get_time_source_candidates(fixture.source_assets[0].source_asset_ref) == []


def test_time_observation_is_readable_by_new_service_with_same_candidate_identity(make_media):
    from daesingo.recording import LocalTimeSourceObserver
    path = make_media()
    repo = InMemoryRecordingRepository()
    service = RecordingService(repo, time_source_observer=LocalTimeSourceObserver(filename_offset="+09:00"))
    registered = service.register_local_source(path)
    observed = service.observe_time_sources(registered.source_asset.source_asset_ref)
    assert len(observed.candidates) == 1
    service.close()
    with RecordingService(repo) as fresh:
        assert fresh.get_time_sources(registered.source_asset.source_asset_ref) == observed
        assert fresh.get_source_asset(registered.source_asset.source_asset_ref) == registered.source_asset
        assert fresh.get_media_stream(registered.media_streams[0].media_stream_ref) == registered.media_streams[0]
        assert fresh.get_time_source_candidates(registered.source_asset.source_asset_ref) == list(observed.candidates)


def test_local_prepared_publication_is_opt_in_and_survives_close(media, tmp_path):
    from test_local_analysis_source import setup, span_for
    old, repo, registered, timeline, profile, materializer, _ = setup(media, tmp_path)
    old.close()
    with RecordingService(repo, analysis_materializer=materializer, durable_prepared=True) as service:
        span = span_for(service, timeline, registered.media_streams[0], 0.0, 1.0)
        result = service.prepare_analysis_source(span, profile, timeline_ref=timeline)
        opened = service.open_analysis_source(result.analysis_source_ref)
        with opened.stream: content = opened.stream.read()
    with RecordingService(repo) as fresh:
        assert fresh.get_analysis_source(result.analysis_source_ref) == result
        opened = fresh.open_analysis_source(result.analysis_source_ref)
        with opened.stream: assert opened.stream.read() == content
    with RecordingService(repo, analysis_materializer=materializer, durable_prepared=True) as replay:
        assert replay.prepare_analysis_source(span, profile, timeline_ref=timeline) == result


from test_local_analysis_source import media  # generated local media fixture
from test_local_time_sources import make_media
