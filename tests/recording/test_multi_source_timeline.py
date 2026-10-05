"""Explicit single-camera placements; adapter facts are not real media metadata."""
from pathlib import Path
import hashlib
from itertools import permutations
import os
import shutil
import subprocess

import pytest

from daesingo.recording import RecordingService, load_recording_fixture
from daesingo.recording.probe import LocalSource, ProbedStream


@pytest.fixture
def sources(tmp_path, request):
    class Probe:
        def probe(self, path):
            stat = path.stat()
            return LocalSource(path, stat.st_size, stat.st_mtime_ns,
                hashlib.sha256(path.read_bytes()).hexdigest(), 10.0,
                (ProbedStream(0, "VIDEO", 10.0), ProbedStream(1, "AUDIO", None)))
    service = RecordingService(media_probe=Probe())
    registered = []
    for i in range(getattr(request, "param", 2)):
        path = tmp_path / f"adapter-{i}"
        path.write_bytes(b"unit adapter only")
        registered.append(service.register_local_source(path))
    yield service, registered
    service.close()


def placements(registered, second=10.0):
    return [dict(source_asset_ref=r.source_asset.source_asset_ref,
                 media_stream_ref=r.media_streams[0].media_stream_ref,
                 timeline_start_sec=start, timeline_end_sec=start + 10.0)
            for r, start in zip(registered, (0.0, second))]


def ref(t):
    return dict(timeline_id=t.timeline_id, revision=t.revision)


def resolve(service, t, rows, start, end):
    result = service.resolve_span(ref(t), dict(start_sec=start, end_sec=end),
        media_stream_refs=[p["media_stream_ref"] for p in rows])
    pieces = sorted([(s.timeline_range.start_sec, s.timeline_range.end_sec) for s in result.spans]
                    + [(m.timeline_range.start_sec, m.timeline_range.end_sec) for m in result.missing_ranges])
    assert pieces[0][0] == start and pieces[-1][1] == end
    assert all(a[1] == b[0] for a, b in zip(pieces, pieces[1:]))
    assert [s.sequence for s in result.spans] == list(range(len(result.spans)))
    return result


@pytest.mark.parametrize("start,end,count", [(9.,11.,2), (0.,10.,1), (10.,20.,1)])
def test_contiguous_boundary(sources, start, end, count):
    service, registered = sources
    rows = placements(registered)
    t = service.create_relative_timeline_from_placements(rows[::-1])
    result = resolve(service, t, rows, start, end)
    assert result.status == "COMPLETE" and len(result.spans) == count
    assert [p.timeline_start_sec for p in t.source_placements] == [0.,10.]
    if count == 2:
        assert [(s.source_range.start_sec, s.source_range.end_sec) for s in result.spans] == [(9.,10.),(0.,1.)]


def test_gap_and_outside(sources):
    service, registered = sources
    rows = placements(registered, 12.)
    t = service.create_relative_timeline_from_placements(rows)
    result = resolve(service, t, rows, 8.,24.)
    assert result.status == "PARTIAL"
    assert [m.reason for m in result.missing_ranges] == ["TIMELINE_GAP", "OUT_OF_TIMELINE_RANGE"]
    assert all(m.source_ref is None for m in result.missing_ranges)
    assert resolve(service, t, rows, 10.,12.).status == "FAILED"


@pytest.mark.parametrize("sources", [3], indirect=True)
@pytest.mark.parametrize("starts,expected_gaps", [
    ((0., 10., 20.), []),
    ((0., 12., 25.), [(10., 12.), (22., 25.)]),
], ids=["three-contiguous-sources", "three-sources-two-gaps"])
def test_three_sources_cross_both_boundaries(sources, starts, expected_gaps):
    service, registered = sources
    rows = [dict(source_asset_ref=r.source_asset.source_asset_ref,
                 media_stream_ref=r.media_streams[0].media_stream_ref,
                 timeline_start_sec=start, timeline_end_sec=start + 10.)
            for r, start in zip(registered, starts)]
    timeline = service.create_relative_timeline_from_placements(rows)
    baseline = None
    # Every explicit stream selection order must yield the same timeline-ordered result.
    for selection in permutations(rows):
        result = resolve(service, timeline, selection, 9., starts[2] + 1.)
        assert result.status == ("PARTIAL" if expected_gaps else "COMPLETE")
        assert result.failure is None
        assert len(result.spans) == 3
        assert [s.sequence for s in result.spans] == [0, 1, 2]
        assert [s.source_asset_ref for s in result.spans] == [p["source_asset_ref"] for p in rows]
        assert [s.media_stream_ref for s in result.spans] == [p["media_stream_ref"] for p in rows]
        assert [(s.source_range.start_sec, s.source_range.end_sec) for s in result.spans] == [
            (9., 10.), (0., 10.), (0., 1.)]
        assert [(s.timeline_range.start_sec, s.timeline_range.end_sec) for s in result.spans] == [
            (9., 10.), (starts[1], starts[1] + 10.), (starts[2], starts[2] + 1.)]
        assert [(m.timeline_range.start_sec, m.timeline_range.end_sec)
                for m in result.missing_ranges] == expected_gaps
        assert all(m.reason == "TIMELINE_GAP" and m.source_ref is None
                   for m in result.missing_ranges)
        # resolve() also checks that spans + missing ranges exactly partition the request.
        if baseline is None:
            baseline = result.model_dump()
        assert result.model_dump() == baseline


@pytest.mark.parametrize("invalid", ["overlap", "duplicate", "source", "audio", "wrong_owner", "negative", "long", "nan"])
def test_invalid_placements_not_published(sources, invalid):
    service, registered = sources
    rows = placements(registered)
    if invalid == "overlap": rows[1]["timeline_start_sec"] = 9.
    if invalid == "duplicate": rows[1] = rows[0].copy()
    if invalid == "source": rows[1]["source_asset_ref"] = "unknown"
    if invalid == "audio": rows[1]["media_stream_ref"] = registered[1].media_streams[1].media_stream_ref
    if invalid == "wrong_owner": rows[1]["media_stream_ref"] = rows[0]["media_stream_ref"]
    if invalid == "negative": rows[0]["timeline_start_sec"] = -1.
    if invalid == "long": rows[1]["timeline_end_sec"] = 21.
    if invalid == "nan": rows[1]["timeline_end_sec"] = float("nan")
    with pytest.raises(ValueError): service.create_relative_timeline_from_placements(rows)


def test_revision_immutability_and_stale_update(sources):
    service, registered = sources
    rows = placements(registered)
    first = service.create_relative_timeline(registered[0].source_asset.source_asset_ref)
    before = first.model_dump()
    second = service.create_relative_timeline_from_placements(rows, base_timeline_ref=ref(first))
    snapshot = second.model_dump()
    with pytest.raises(ValueError):
        service.create_relative_timeline_from_placements(rows, base_timeline_ref=ref(first))
    assert service.get_latest_timeline(first.timeline_id).revision == 2
    second.source_placements.clear()
    assert service.get_timeline(first.timeline_id, 1).model_dump() == before
    assert service.get_timeline(first.timeline_id, 2).model_dump() == snapshot
    assert service.resolve_span(ref(first), dict(start_sec=1.,end_sec=2.),
                               media_stream_ref=rows[0]["media_stream_ref"]).status == "COMPLETE"


@pytest.mark.parametrize("selection", [[], ["unknown"], "duplicate", "audio", "missing"])
def test_invalid_stream_selection(sources, selection):
    service, registered = sources
    rows = placements(registered)
    t = service.create_relative_timeline_from_placements(rows)
    refs = [p["media_stream_ref"] for p in rows]
    if selection == "duplicate": refs = [refs[0], refs[0]]
    elif selection == "audio": refs[1] = registered[1].media_streams[1].media_stream_ref
    elif selection == "missing": refs = refs[:1]
    else: refs = selection
    with pytest.raises(ValueError):
        service.resolve_span(ref(t), dict(start_sec=9.,end_sec=11.), media_stream_refs=refs)
    with pytest.raises(ValueError):
        service.resolve_span(dict(timeline_id=t.timeline_id, revision=99), dict(start_sec=9.,end_sec=11.), media_stream_refs=refs)


def test_relative_rebase_fixture_unchanged():
    fixture = load_recording_fixture("scenario_relative_rebase_001")
    expected, = fixture.span_resolutions
    with RecordingService.from_fixture(fixture) as service:
        assert service.resolve_span(expected.timeline_ref, expected.requested_range) == expected


def test_source_unavailable_and_stream_shortfall(sources):
    service, registered = sources
    rows = placements(registered)
    t = service.create_relative_timeline_from_placements(rows)
    video = registered[1].media_streams[0]
    service._repository.add_media_stream(video.model_copy(update={"duration_sec": 1.0}))
    result = resolve(service, t, rows, 9.,13.)
    assert result.status == "PARTIAL"
    assert result.missing_ranges[0].reason == "STREAM_UNAVAILABLE"
    assert result.missing_ranges[0].source_ref.ref == video.media_stream_ref
    local = service._repository.get_local_source(rows[1]["source_asset_ref"])
    local.path.unlink()  # unit adapter file only
    result = resolve(service, t, rows, 9.,13.)
    assert result.status == "PARTIAL"
    assert all(m.reason == "SOURCE_UNAVAILABLE" for m in result.missing_ranges)
    assert all(m.source_ref.ref == rows[1]["source_asset_ref"] for m in result.missing_ranges)


def test_generated_two_files_public_resolution(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe 필요")
    with RecordingService() as service:
        registered = []
        snapshots = []
        for i in range(2):
            path = tmp_path / f"generated-{i}.mkv"
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
                "testsrc2=s=64x48:r=10:d=2", "-c:v", "libx264", str(path)],
                check=True, capture_output=True, timeout=30)
            snapshots.append((path, fingerprint(path)))
            registered.append(service.register_local_source(path))
        rows = placements(registered, 2.)
        for p in rows: p["timeline_end_sec"] = p["timeline_start_sec"] + 2.
        t = service.create_relative_timeline_from_placements(rows)
        result = resolve(service, t, rows, 1.5,2.5)
        assert result.status == "COMPLETE" and len(result.spans) == 2
        assert result.spans[1].source_range.start_sec == 0.0
        assert all(fingerprint(path) == before for path, before in snapshots)


def fingerprint(path):
    stat = path.stat()
    return hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_size, stat.st_mtime_ns


def test_opt_in_real_pair_registration_only():
    paths = [os.environ.get("DAESINGO_RECORDING_PAIR_A"), os.environ.get("DAESINGO_RECORDING_PAIR_B")]
    if not all(paths):
        pytest.skip("실제 연속 원본 pair opt-in 미지정; placement 추정하지 않음")
    originals = [Path(p) for p in paths]
    before = [fingerprint(p) for p in originals]
    try:
        with RecordingService() as service:
            for path, snapshot in zip(originals, before):
                registered = service.register_local_source(path)
                asset = registered.source_asset
                assert asset.byte_size == snapshot[1]
                assert any(s.media_type == "VIDEO" for s in registered.media_streams)
                facts = service.lookup_asset_facts({"kind": "source_asset", "ref": asset.source_asset_ref})
                assert facts.availability == "AVAILABLE"
                # 파일명/stream 순서에서 역할·overlap을 추정하지 않으며 Timeline을 생성하지 않는다.
    finally:
        assert [fingerprint(p) for p in originals] == before
