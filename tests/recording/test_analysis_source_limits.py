"""Small synthetic inputs; injected values are test budgets, never deployment policy."""
from pathlib import Path

import pytest

from daesingo.recording import RecordingCapabilityError, RecordingService
from tests.recording.test_local_analysis_source import media, setup, span_for, fingerprint
from tests.recording.test_multi_span_analysis_source import chain


def limits(byte_count, duration_ms=10000):
    from daesingo.recording.analysis_limits import AnalysisSourceLimits
    return AnalysisSourceLimits(byte_count, duration_ms)


@pytest.mark.parametrize("byte_count,duration_ms", [(0, 1), (-1, 1), (True, 1), (1.5, 1),
    (1, 0), (1, -1), (1, True), (1, float("inf")), (1, "100")])
def test_limits_reject_invalid_configuration(byte_count, duration_ms):
    with pytest.raises(ValueError):
        limits(byte_count, duration_ms)


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_single_byte_boundary_before_repository_write(media, tmp_path, monkeypatch, delta):
    seed, repo, registered, ref, profile, engine, work = setup(media, tmp_path)
    span = span_for(seed, ref, registered.media_streams[0], 0, 1)
    baseline = engine.materialize(repo.get_local_source(span.source_asset_ref), 0, span, profile)
    seed.close()
    before = fingerprint(media)
    writes = []
    original = repo.add_prepared_media
    def write(*args, **kwargs):
        writes.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(repo, "add_prepared_media", write)
    with RecordingService(repo, analysis_materializer=engine, durable_prepared=True,
            analysis_limits=limits(len(baseline.content) + delta)) as service:
        if delta < 0:
            with pytest.raises(RecordingCapabilityError) as caught:
                service.prepare_analysis_source(span, profile, timeline_ref=ref)
            assert caught.value.code == "ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED"
            assert str(media) not in str(caught.value)
            assert not writes and not service._local_analysis
        else:
            source = service.prepare_analysis_source(span, profile, timeline_ref=ref)
            assert source.byte_size == len(baseline.content) and len(writes) == 1
    assert fingerprint(media) == before and not list(work.iterdir())


@pytest.mark.parametrize("duration_ms", [999, 1000])
def test_supported_duration_checked_before_encode(media, tmp_path, monkeypatch, duration_ms):
    seed, repo, registered, ref, profile, engine, work = setup(media, tmp_path)
    span = span_for(seed, ref, registered.media_streams[0], 0, 1)
    seed.close()
    calls = []
    original = engine.materialize
    def encode(*args):
        calls.append(True)
        return original(*args)
    monkeypatch.setattr(engine, "materialize", encode)
    with RecordingService(repo, analysis_materializer=engine,
            analysis_limits=limits(100000, duration_ms)) as service:
        if duration_ms < 1000:
            with pytest.raises(RecordingCapabilityError) as caught:
                service.prepare_analysis_source(span, profile, timeline_ref=ref)
            assert caught.value.code == "ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED" and not calls
        else:
            assert service.prepare_analysis_source(span, profile, timeline_ref=ref).duration_sec == 1
            assert len(calls) == 1
    assert not list(work.iterdir())


def test_multi_cumulative_stops_before_later_span_or_concat(chain, monkeypatch):
    seed, resolution, paths, work, engine = chain
    repo = seed._repository
    calls = []
    original = engine.materialize
    def encode(*args):
        calls.append(args[2].sequence)
        return original(*args)
    monkeypatch.setattr(engine, "materialize", encode)
    # Each individual clip fits this budget, but their cumulative output does not.
    first = resolution.spans[0]
    part = original(repo.get_local_source(first.source_asset_ref), 0, first, "profile")
    with RecordingService(repo, analysis_materializer=engine, durable_prepared=True,
            analysis_limits=limits(len(part.content))) as service:
        with pytest.raises(RecordingCapabilityError) as caught:
            service.prepare_analysis_source_from_resolution(resolution, "profile")
        assert caught.value.code == "ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED"
        assert calls == [0, 1] and not service._local_analysis
    assert not list(work.iterdir())


def test_multi_duration_rejected_before_first_encode(chain, monkeypatch):
    seed, resolution, _, work, engine = chain
    def forbidden(*args):
        pytest.fail("unsupported duration encoded")
    monkeypatch.setattr(engine, "materialize", forbidden)
    with RecordingService(seed._repository, analysis_materializer=engine,
            analysis_limits=limits(100000, 3999)) as service:
        with pytest.raises(RecordingCapabilityError) as caught:
            service.prepare_analysis_source_from_resolution(resolution, "profile")
        assert caught.value.code == "ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED"
    assert not list(work.iterdir())


def test_final_concat_overhead_rejected_before_probe_read_or_write(chain, monkeypatch):
    seed, resolution, _, work, engine = chain
    original_run, original_probe = engine._run, engine._probe
    concats = []
    def run(args):
        if "concat" in args:
            concats.append(True)
            Path(args[-1]).write_bytes(b"x" * 20001)
            return b""
        return original_run(args)
    def probe(path, index=None):
        assert not path.parent.name.startswith("recording-chain-")
        return original_probe(path, index)
    monkeypatch.setattr(engine, "_run", run)
    monkeypatch.setattr(engine, "_probe", probe)
    with RecordingService(seed._repository, analysis_materializer=engine, durable_prepared=True,
            analysis_limits=limits(20000)) as service:
        with pytest.raises(RecordingCapabilityError) as caught:
            service.prepare_analysis_source_from_resolution(resolution, "profile")
        assert caught.value.code == "ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED"
        assert concats == [True] and not service._local_analysis
    assert not list(work.iterdir())


def test_injected_materializer_cannot_bypass_publish_guard(media, tmp_path, monkeypatch):
    seed, repo, registered, ref, profile, engine, work = setup(media, tmp_path)
    span = span_for(seed, ref, registered.media_streams[0], 0, 1)
    prepared = engine.materialize(repo.get_local_source(span.source_asset_ref), 0, span, profile)
    monkeypatch.setattr(engine, "materialize", lambda *a: prepared)
    monkeypatch.setattr(repo, "add_prepared_media", lambda *a, **k: pytest.fail("BLOB write"))
    with RecordingService(repo, analysis_materializer=engine, durable_prepared=True,
            analysis_limits=limits(len(prepared.content) - 1)) as service:
        with pytest.raises(RecordingCapabilityError) as caught:
            service.prepare_analysis_source(span, profile, timeline_ref=ref)
        assert caught.value.code == "ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED"


def test_multi_success_at_cumulative_and_duration_boundaries(chain):
    seed, resolution, paths, work, engine = chain
    repo = seed._repository
    parts = [engine.materialize(repo.get_local_source(s.source_asset_ref), 0, s, "profile")
             for s in resolution.spans]
    baseline = seed.prepare_analysis_source_from_resolution(resolution, "profile")
    budget = max(sum(len(p.content) for p in parts), baseline.byte_size)
    before = [fingerprint(p) for p in paths]
    with RecordingService(repo, analysis_materializer=engine, durable_prepared=True,
            analysis_limits=limits(budget, 4000)) as service:
        source = service.prepare_analysis_source_from_resolution(resolution, "profile")
        assert source.byte_size == baseline.byte_size
        assert source.source_refs == baseline.source_refs and source.media_stream_refs == baseline.media_stream_refs
        assert source.timeline_range == baseline.timeline_range and source.duration_sec == 4
    assert [fingerprint(p) for p in paths] == before and not list(work.iterdir())
