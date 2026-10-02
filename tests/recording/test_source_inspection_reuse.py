import os
from pathlib import Path

import pytest

from daesingo.recording import AnalysisProfile, IncidentClipEncoding, LocalAnalysisMaterializer, LocalIncidentMaterializer, RecordingService, RecordingCapabilityError
from daesingo.recording import materialization
from daesingo.recording.observability import capture_materialization
from tests.recording.test_local_analysis_source import media, fingerprint


def setup(path, tmp_path):
    work = tmp_path / "inspection-work"
    work.mkdir()
    analysis = LocalAnalysisMaterializer({"profile": AnalysisProfile(48, "veryfast", 23)}, temp_root=work)
    incident = LocalIncidentMaterializer(IncidentClipEncoding(48, "veryfast", 23), temp_root=work)
    service = RecordingService(analysis_materializer=analysis, incident_materializer=incident)
    registered = service.register_local_source(path)
    timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
    ref = {"timeline_id": timeline.timeline_id, "revision": 1}
    resolutions = [service.resolve_span(ref, {"start_sec": 0.0, "end_sec": 1.0}, media_stream_ref=s.media_stream_ref)
                   for s in registered.media_streams if s.media_type == "VIDEO"]
    return service, analysis, incident, resolutions, work


def prepare(service, resolution):
    return service.prepare_analysis_source(resolution.spans[0], "profile", timeline_ref=resolution.timeline_ref)


def observe_calls(monkeypatch):
    calls = []
    original = LocalAnalysisMaterializer._probe
    def probe(self, path, index=None):
        calls.append(index)
        return original(self, path, index)
    monkeypatch.setattr(LocalAnalysisMaterializer, "_probe", probe)
    return calls


def test_shared_source_probe_once_same_bytes_ranges_provenance(media, tmp_path, monkeypatch):
    calls = observe_calls(monkeypatch)
    service, analysis, incident, resolutions, work = setup(media, tmp_path)
    before = fingerprint(media)
    resolution = resolutions[0]
    prepared = prepare(service, resolution)
    with service.open_analysis_source(prepared.analysis_source_ref).stream as stream:
        analysis_bytes = stream.read()
    with capture_materialization() as traces:
        cached = service.build_incident_clip(resolution)
    assert calls == [0, None, None]  # source 1회, 출력 검증은 두 번 모두 실행
    cached_bytes = service._local_clips[cached.incident_clip_ref][1]
    assert traces[0]["status"] == "SUCCESS"
    phase = next(p for p in traces[0]["phases"] if p["name"] == "source_probe")
    assert phase["status"] == "SUCCESS" and phase["elapsed_sec"] >= 0
    # 같은 materializer를 다른 Service에 주입해도 공유 cache가 누출되지 않는다.
    other = RecordingService(service._repository, analysis_materializer=analysis, incident_materializer=incident)
    uncached = other.build_incident_clip(resolution)
    assert calls == [0, None, None, 0, None]
    assert other._local_clips[uncached.incident_clip_ref][1] == cached_bytes == analysis_bytes
    assert cached.duration_sec == uncached.duration_sec == prepared.duration_sec
    assert cached.timeline_range == uncached.timeline_range == prepared.timeline_range
    assert cached.source_provenance == uncached.source_provenance
    assert cached.source_provenance.asset_spans == resolution.spans
    assert fingerprint(media) == before and not list(work.iterdir())
    assert service._source_inspections._entries
    service.close()
    assert service._source_inspections._entries == {}
    assert other._source_inspections._entries  # 한 Service close가 다른 Service에 영향을 주지 않는다.
    other.close()


def test_stream_index_separates_inspections(media, tmp_path, monkeypatch):
    calls = observe_calls(monkeypatch)
    service, _, _, resolutions, _ = setup(media, tmp_path)
    prepare(service, resolutions[0])
    service.build_incident_clip(resolutions[1])
    assert [c for c in calls if c is not None] == [0, 2]
    service.close()


@pytest.mark.parametrize("failure", ["probe", "encode", "output"])
def test_failed_inspection_or_materialization_not_cached(media, tmp_path, monkeypatch, failure):
    service, analysis, _, resolutions, work = setup(media, tmp_path)
    calls = observe_calls(monkeypatch)
    original_probe, original_run = analysis._probe, analysis._run
    def probe(path, index=None):
        result = original_probe(path, index)
        if failure == "probe" and index is not None:
            result["frames"] = []
        if failure == "output" and index is None:
            result["streams"][0]["codec_name"] = "invalid"
        return result
    def execute(args):
        if failure == "encode" and args[0] == "ffmpeg":
            Path(args[-1]).write_bytes(b"partial")
            raise OSError("private-path-secret")
        return original_run(args)
    monkeypatch.setattr(analysis, "_probe", probe)
    monkeypatch.setattr(analysis, "_run", execute)
    with pytest.raises(RecordingCapabilityError):
        prepare(service, resolutions[0])
    assert not service._source_inspections._entries and not list(work.iterdir())
    monkeypatch.setattr(analysis, "_probe", original_probe)
    monkeypatch.setattr(analysis, "_run", original_run)
    service.build_incident_clip(resolutions[0])
    assert [c for c in calls if c is not None] == [0, 0]
    service.close()


@pytest.mark.parametrize("when", ["before", "during"])
def test_changed_original_never_returns_cached_result(media, tmp_path, monkeypatch, when):
    service, _, incident, resolutions, work = setup(media, tmp_path)
    prepare(service, resolutions[0])
    original_run = incident._engine._run
    def change():
        with media.open("ab") as stream:
            stream.write(b"changed")  # 합성 테스트 원본만 수정한다.
    def execute(args):
        result = original_run(args)
        if args[0] == "ffmpeg":
            change()
        return result
    if when == "before":
        change()
    else:
        monkeypatch.setattr(incident._engine, "_run", execute)
    with pytest.raises(RecordingCapabilityError) as caught:
        service.build_incident_clip(resolutions[0])
    assert caught.value.code == "INCIDENT_CLIP_BUILD_FAILED"
    assert str(media) not in str(caught.value)
    assert not service._local_clips and not list(work.iterdir())
    if when == "during":
        assert not service._source_inspections._entries
    service.close()


def test_cache_isolation_and_fingerprint_key(media, tmp_path):
    service, _, _, resolutions, _ = setup(media, tmp_path)
    prepare(service, resolutions[0])
    cache = service._source_inspections
    key, = cache._entries
    snapshot, stream_index, _ = key
    before = fingerprint(media)
    assert (snapshot[2], snapshot[3], snapshot[4]) == before
    assert stream_index == 0
    for position, changed in [(2, snapshot[2] + 1), (3, snapshot[3] + 1), (4, "0" * 64)]:
        values = list(snapshot)
        values[position] = changed
        assert cache.get((tuple(values), *key[1:])) is None
    observed = cache.get(key)
    observed[0]["streams"].clear()
    assert cache.get(key)[0]["streams"]
    service.close()
    cache.put(key, observed)
    assert cache.get(key) is None and not cache._entries


def test_reference_two_probes_become_one_with_same_outputs(media, tmp_path, monkeypatch):
    calls = observe_calls(monkeypatch)
    service, analysis, incident, resolutions, _ = setup(media, tmp_path)
    # cache를 닫은 참조 실행은 조회/저장을 하지 않아 최적화 전 경로를 그대로 실행한다.
    service._source_inspections.close()
    plain_analysis = prepare(service, resolutions[0])
    plain_clip = service.build_incident_clip(resolutions[0])
    assert calls == [0, None, 0, None]
    reference_bytes = service._local_clips[plain_clip.incident_clip_ref][1]
    reference_provenance = plain_clip.source_provenance
    calls.clear()
    other = RecordingService(service._repository, analysis_materializer=analysis, incident_materializer=incident)
    snapshots = []
    original_snapshot = materialization._snapshot
    def snapshot(path):
        value = original_snapshot(path)
        snapshots.append(value)
        return value
    monkeypatch.setattr(materialization, "_snapshot", snapshot)
    with capture_materialization() as traces:
        reused_analysis = prepare(other, resolutions[0])
        reused_clip = other.build_incident_clip(resolutions[0])
    assert calls == [0, None, None]
    assert len(snapshots) == 4 and all(s == snapshots[0] for s in snapshots)
    assert len(traces) == 2 and all(t["status"] == "SUCCESS" for t in traces)
    assert other._local_clips[reused_clip.incident_clip_ref][1] == reference_bytes
    with service.open_analysis_source(plain_analysis.analysis_source_ref).stream as a:
        with other.open_analysis_source(reused_analysis.analysis_source_ref).stream as b:
            assert a.read() == b.read()
    assert reused_clip.source_provenance == reference_provenance
    assert reused_clip.timeline_range == plain_clip.timeline_range
    assert reused_clip.duration_sec == plain_clip.duration_sec
    service.close()
    other.close()


def test_opt_in_real_reuse(tmp_path, monkeypatch):
    path = os.environ.get("DAESINGO_RECORDING_VIDEO")
    index = os.environ.get("DAESINGO_RECORDING_VIDEO_INDEX")
    if not path or index is None:
        pytest.skip("실제 영상과 명시적 VIDEO_INDEX 필요")
    path = Path(path)
    before = fingerprint(path)
    calls = observe_calls(monkeypatch)
    service, _, _, resolutions, work = setup(path, tmp_path)
    resolution, = [r for r in resolutions
                   if service._repository.get_local_stream_index(r.spans[0].media_stream_ref) == int(index)]
    with capture_materialization() as traces:
        prepare(service, resolution)
        clip = service.build_incident_clip(resolution)
    assert len([c for c in calls if c is not None]) == 1
    assert len([c for c in calls if c is None]) == 2
    assert all(t["status"] == "SUCCESS" for t in traces)
    assert clip.source_provenance.asset_spans == resolution.spans
    assert fingerprint(path) == before and not list(work.iterdir())
    service.close()
    assert not service._source_inspections._entries
