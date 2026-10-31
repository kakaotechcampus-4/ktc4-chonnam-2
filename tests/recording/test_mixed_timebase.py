"""Exact mixed-clock coverage through the existing public capabilities."""
from fractions import Fraction
import json
import subprocess
import os
from io import BytesIO
from types import SimpleNamespace
from dataclasses import replace

import pytest

from daesingo.recording import (AnalysisProfile, IncidentClipEncoding,
    LocalAnalysisMaterializer, LocalIncidentMaterializer, RecordingService, RecordingCapabilityError)
from tests.recording.test_local_analysis_source import fingerprint


def probe(path):
    raw = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_frames', '-show_streams', '-of', 'json', str(path)],
        capture_output=True, check=True, timeout=30).stdout)
    base = Fraction(raw['streams'][0]['time_base'])
    frames = [(int(f['best_effort_timestamp'])*base,
               int(f.get('duration', f.get('pkt_duration')))*base) for f in raw['frames']]
    return base, frames


@pytest.fixture(params=[(15007, 30013, False), (30013, 15360, True)])
def mixed(request, tmp_path):
    clocks = request.param[:2]
    vfr = request.param[2]
    paths, original = [], []
    for i, clock in enumerate(clocks):
        path = tmp_path / f'synthetic-{i}.mp4'
        expr = 'N*1000+floor(N/2)*100' if vfr else 'N*1000'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-f', 'lavfi',
            '-i', f'color=c={"red" if i == 0 else "blue"}:s=64x48:r={clock}/1000',
            '-frames:v', '8', '-vf', f'settb=1/{clock},setpts={expr}',
            '-fps_mode', 'passthrough', '-enc_time_base', f'1/{clock}',
            '-video_track_timescale', str(clock), '-c:v', 'libx264', '-bf', '0', str(path)],
            check=True, capture_output=True, timeout=30)
        paths.append(path)
        original.append(probe(path))
    work = tmp_path / 'work'
    work.mkdir()
    engine = LocalAnalysisMaterializer({'profile': AnalysisProfile(48, 'ultrafast', 23)}, temp_root=work)
    incident = LocalIncidentMaterializer(IncidentClipEncoding(48, 'ultrafast', 23), temp_root=work)
    with RecordingService(analysis_materializer=engine, incident_materializer=incident) as service:
        rows, offset = [], 0.
        for path, (_, frames) in zip(paths, original):
            registered = service.register_local_source(path)
            video = next(s for s in registered.media_streams if s.media_type == 'VIDEO')
            # Public metadata uses decimal seconds. Keep the requested end inside
            # observed stream coverage; materialization retains the final frame.
            length = float((frames[-1][0]+frames[-1][1])*1000000 // 1) / 1000000
            rows.append(dict(source_asset_ref=registered.source_asset.source_asset_ref,
                media_stream_ref=video.media_stream_ref, timeline_start_sec=offset,
                timeline_end_sec=offset+length))
            offset += length
        timeline = service.create_relative_timeline_from_placements(rows)
        resolution = service.resolve_span(dict(timeline_id=timeline.timeline_id, revision=timeline.revision),
            dict(start_sec=0., end_sec=offset), media_stream_refs=[r['media_stream_ref'] for r in rows])
        assert resolution.status == 'COMPLETE'
        yield service, resolution, paths, original, work, engine


@pytest.mark.parametrize('capability', ['analysis', 'incident'])
def test_mixed_public_exact_frames_and_provenance(mixed, tmp_path, capability):
    service, resolution, paths, original, work, engine = mixed
    before = [fingerprint(p) for p in paths]
    # Establish that both individual transformations succeed before chaining.
    for span in resolution.spans:
        engine.materialize(service._repository.get_local_source(span.source_asset_ref),
            service._repository.get_local_stream_index(span.media_stream_ref), span, 'profile')
    if capability == 'analysis':
        result = service.prepare_analysis_source_from_resolution(resolution, 'profile')
        opened = service.open_analysis_source(result.analysis_source_ref)
        assert [r.ref for r in result.source_refs] == [s.source_asset_ref for s in resolution.spans]
    else:
        result = service.build_incident_clip(resolution)
        opened = SimpleNamespace(stream=BytesIO(service._local_clips[result.incident_clip_ref][1]))
        assert result.source_provenance.asset_spans == resolution.spans
    assert result.media_stream_refs == [s.media_stream_ref for s in resolution.spans]
    assert result.timeline_ref == resolution.timeline_ref
    with opened.stream as stream:
        target = tmp_path / 'joined.mp4'
        target.write_bytes(stream.read())
    base, actual = probe(target)
    expected, offset = [], Fraction(0)
    for _, frames in original:
        expected.extend((offset+at, length) for at, length in frames)
        offset += frames[-1][0]+frames[-1][1]
    assert actual == expected
    assert len(actual) == 16
    assert actual[7][0]+actual[7][1] == actual[8][0]
    assert all((at/base).denominator == (length/base).denominator == 1 for at, length in expected)
    assert [fingerprint(p) for p in paths] == before
    assert not list(work.iterdir())
    pixels = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(target),
        '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
        check=True, capture_output=True, timeout=30).stdout
    assert len(pixels) == 16*64*48*3
    for i in range(16):
        red, _, blue = pixels[i*64*48*3:i*64*48*3+3]
        assert (red > 230 and blue < 10) if i < 8 else (blue > 230 and red < 10)


def test_common_clock_reduces_rationals_and_preserves_offsets():
    from daesingo.recording.chain_clock import common_time_base
    frames = ((Fraction(0), Fraction(1, 3)), (Fraction(1, 3), Fraction(1, 6)))
    parts = [SimpleNamespace(time_base=base, frames=frames, source_frames=frames)
             for base in (Fraction(2, 12), Fraction(3, 36))]
    assert common_time_base(parts) == Fraction(1, 6)
    assert common_time_base(parts, [[(Fraction(0), Fraction(-1, 12), Fraction(1, 6))]]) == Fraction(1, 12)


@pytest.mark.parametrize('bad', ['lcm', 'source', 'fraction', 'duration', 'pts', 'gap', 'overlap'])
def test_unrepresentable_clock_is_typed_rejection(bad):
    from daesingo.recording.chain_clock import common_time_base
    frames = ((Fraction(0), Fraction(1, 30)),)
    parts = [SimpleNamespace(time_base=Fraction(1, 30), frames=frames, source_frames=frames)
             for _ in range(2)]
    if bad == 'lcm':
        parts[0].time_base, parts[1].time_base = Fraction(1, 65537), Fraction(1, 65539)
        for part in parts:
            part.frames = part.source_frames = ((Fraction(0), part.time_base),)
    elif bad == 'source':
        parts[0].source_frames = ((Fraction(0), Fraction(1, 31)),)
    elif bad == 'fraction':
        parts[0].frames = ((Fraction(0), Fraction(1, 31)),)
        parts[0].source_frames = parts[0].frames
    elif bad == 'duration':
        parts[0].frames = ((Fraction(0), Fraction(1 << 31, 30)),)
        parts[0].source_frames = parts[0].frames
    elif bad == 'pts':
        # Exercise exact integer tick rejection directly without billions of frames.
        from daesingo.recording.chain_clock import _ticks
        with pytest.raises(RecordingCapabilityError) as caught:
            _ticks(Fraction(1 << 53), Fraction(1))
        assert caught.value.code == 'UNSUPPORTED_MEDIA'
        return
    else:
        parts[0].frames += ((Fraction(2, 30) if bad == 'gap' else Fraction(1, 60), Fraction(1, 30)),)
        parts[0].source_frames = parts[0].frames
    with pytest.raises(RecordingCapabilityError) as caught:
        common_time_base(parts)
    assert caught.value.code == 'UNSUPPORTED_MEDIA'


@pytest.mark.parametrize('mutation', ['offset', 'duration', 'drop', 'origin', 'normalization', 'source'])
def test_mixed_negative_controls_reject_and_cleanup(mixed, monkeypatch, mutation):
    service, resolution, paths, _, work, engine = mixed
    before = [fingerprint(p) for p in paths]
    run, inspect, materialize = engine._run, engine._probe, engine.materialize
    def altered_run(args):
        args = list(args)
        if mutation == 'offset' and '-bsf:v' in args:
            i = args.index('-bsf:v')
            del args[i:i+2]
        if mutation == 'normalization' and 'copy' in args and '-bsf:v' not in args:
            args[args.index('-video_track_timescale')+1] = '1000'
        return run(args)
    def altered_probe(path, index=None):
        raw = inspect(path, index)
        if path.parent.name.startswith('recording-chain-') and path.name == 'prepared.mp4':
            if mutation == 'drop':
                raw['frames'].pop(7)
            if mutation == 'duration':
                raw['frames'][7]['duration'] += 1
            if mutation == 'origin':
                for frame in raw['frames']:
                    frame['best_effort_timestamp'] += 1
        return raw
    def altered_materialize(*args):
        part = materialize(*args)
        if mutation == 'source':
            part = replace(part, source_frames=((Fraction(0), Fraction(1)),))
        return part
    monkeypatch.setattr(engine, '_run', altered_run)
    monkeypatch.setattr(engine, '_probe', altered_probe)
    monkeypatch.setattr(engine, 'materialize', altered_materialize)
    with pytest.raises(RecordingCapabilityError) as caught:
        service.prepare_analysis_source_from_resolution(resolution, 'profile')
    assert caught.value.code == 'UNSUPPORTED_MEDIA'
    assert not service._local_analysis and not list(work.iterdir())
    assert [fingerprint(p) for p in paths] == before


@pytest.mark.parametrize('failure', ['budget', 'timeout', 'cancel'])
def test_mixed_remux_failure_releases_temp_and_keeps_error(mixed, monkeypatch, failure):
    from daesingo.recording.analysis_limits import AnalysisSourceLimits, analysis_source_scope
    from daesingo.common.jobs.cancel import CancellationRequested
    from daesingo.common.storage.cleanup import CleanupScanner
    from daesingo.common.storage.media import MediaRoot
    service, resolution, paths, _, work, engine = mixed
    before = [fingerprint(p) for p in paths]
    cleaner = CleanupScanner(root=work, kind='temp', age_sec=3600, now=lambda: 20000)
    service._analysis_materializer = MediaRoot(cleaner).materializer(lambda *, temp_root: engine)
    run = engine._run
    visited = []
    def fail(args):
        if 'copy' in args and '-bsf:v' not in args:
            visited.append(True)
            from pathlib import Path
            root = Path(args[-1]).parent
            for path in [*root.iterdir(), root]:
                os.utime(path, (1, 1))
            assert cleaner.scan().count == 0  # Remux is inside the chain lease.
            if failure == 'timeout':
                raise subprocess.TimeoutExpired(args, .1)
            if failure == 'cancel':
                raise CancellationRequested()
            # Run the real remux under a deliberately too-small nested budget.
            with analysis_source_scope(AnalysisSourceLimits(1, 1000), lambda: None):
                return run(args)
        return run(args)
    monkeypatch.setattr(engine, '_run', fail)
    with pytest.raises(CancellationRequested if failure == 'cancel' else RecordingCapabilityError) as caught:
        service.prepare_analysis_source_from_resolution(resolution, 'profile')
    if failure != 'cancel':
        assert caught.value.code == ('ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED' if failure == 'budget' else 'TEMPORARY_FAILURE')
    assert visited and not list(work.glob('recording-*')) and not service._local_analysis
    assert [fingerprint(p) for p in paths] == before
    stale = work / 'recording-chain-stale___'
    stale.mkdir()
    (stale / 'partial').write_bytes(b'owned test residue')
    os.utime(stale / 'partial', (1, 1))
    os.utime(stale, (1, 1))
    assert cleaner.scan().count == 1 and not stale.exists()  # Lease released.


@pytest.mark.parametrize('packets', [
    [(0, 0, (1 << 31)-1), ((1 << 31)-1, (1 << 31)-1, 1)],
    [(1 << 31, 0, 1)],
    [(1 << 53, 1 << 53, 1)],
])
def test_packet_ranges_reject_muxer_rewrite_and_numeric_overflow(packets):
    from daesingo.recording.chain_clock import _check_packet_ranges
    with pytest.raises(RecordingCapabilityError) as caught:
        _check_packet_ranges(packets)
    assert caught.value.code == 'UNSUPPORTED_MEDIA'


def test_many_segment_offsets_execute_without_expression_depth_failure(tmp_path):
    from daesingo.recording.chain_clock import _offset_expression
    expression = _offset_expression([(i, i) for i in range(101)])
    path = tmp_path / 'many-offsets.mp4'
    result = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=s=16x16:r=1',
        '-frames:v', '3', '-c:v', 'libx264', '-bf', '0', '-enc_time_base', '1:1',
        '-bsf:v', f'setts=pts=PTS+{expression}:dts=DTS+{expression}',
        '-video_track_timescale', '1', str(path)], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode()
    _, frames = probe(path)
    assert [pts for pts, _ in frames] == [0, 2, 4]


def test_unused_stream_ticks_do_not_force_timescale_overflow(tmp_path):
    engine = LocalAnalysisMaterializer({'profile': AnalysisProfile(48, 'ultrafast', 23)}, temp_root=tmp_path)
    with RecordingService(analysis_materializer=engine) as service:
        rows, paths = [], []
        for i, clock in enumerate((65537, 65539)):
            path = tmp_path / f'sparse-{i}.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=s=64x48:r=1:d=2',
                '-c:v', 'libx264', '-bf', '0', '-video_track_timescale', str(clock), str(path)],
                capture_output=True, check=True, timeout=30)
            registered = service.register_local_source(path)
            video = next(s for s in registered.media_streams if s.media_type == 'VIDEO')
            rows.append(dict(source_asset_ref=registered.source_asset.source_asset_ref,
                media_stream_ref=video.media_stream_ref, timeline_start_sec=float(2*i),
                timeline_end_sec=float(2*i+2)))
            paths.append(path)
        before = [fingerprint(p) for p in paths]
        timeline = service.create_relative_timeline_from_placements(rows)
        resolution = service.resolve_span(dict(timeline_id=timeline.timeline_id, revision=timeline.revision),
            dict(start_sec=0., end_sec=4.), media_stream_refs=[r['media_stream_ref'] for r in rows])
        for span in resolution.spans:
            part = engine.materialize(service._repository.get_local_source(span.source_asset_ref), 0, span, 'profile')
            assert part.frames == part.source_frames == ((0, 1), (1, 1))
        source = service.prepare_analysis_source_from_resolution(resolution, 'profile')
        with service.open_analysis_source(source.analysis_source_ref).stream as stream:
            target = tmp_path / 'sparse-joined.mp4'
            target.write_bytes(stream.read())
        assert probe(target) == (Fraction(1), [(0, 1), (1, 1), (2, 1), (3, 1)])
        assert [fingerprint(p) for p in paths] == before
        assert not list(tmp_path.glob('recording-*'))
