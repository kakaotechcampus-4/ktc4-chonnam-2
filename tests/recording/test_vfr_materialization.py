"""Presentation coverage must survive VFR encoding, including reordering boundaries."""
from fractions import Fraction
from io import BytesIO
import json
import shutil
import subprocess

import pytest

from daesingo.recording import (
    AnalysisProfile, IncidentClipEncoding, LocalAnalysisMaterializer, LocalIncidentMaterializer,
    RecordingCapabilityError, RecordingService,
)
from tests.recording.test_local_analysis_source import fingerprint


def observed_frames(path):
    raw = json.loads(subprocess.run([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_frames',
        '-show_entries', 'stream=time_base:frame=best_effort_timestamp,duration,pkt_duration',
        '-of', 'json', str(path)], check=True, capture_output=True, timeout=30).stdout)
    base = Fraction(raw['streams'][0]['time_base'])
    return [(int(f['best_effort_timestamp']) * base,
             int(f.get('duration', f.get('pkt_duration'))) * base) for f in raw['frames']]


@pytest.fixture(params=['long_short', 'short_long', 'constant'])
def vfr_media(request, tmp_path):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('ffmpeg/ffprobe required')
    path = tmp_path / 'synthetic-vfr.mp4'
    mode = request.param
    pts = [0, 3000, 4000, 5000] if mode == 'long_short' else [0, 1000, 2000, 3000]
    tail = 3000 if mode == 'short_long' else 1000
    expression = r'if(eq(N\,0)\,0\,(N+2)*1000)' if mode == 'long_short' else 'N*1000'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-f', 'lavfi',
        '-i', f'color=c=red:s=64x48:r={10 if mode == "short_long" else 30}', '-frames:v', '4',
        '-vf', f'settb=1/30000,setpts={expression}',
        '-fps_mode', 'passthrough', '-enc_time_base', '1/30000',
        '-video_track_timescale', '30000', '-c:v', 'libx264', '-bf', '0', str(path)],
        check=True, capture_output=True, timeout=30)
    expected = [(Fraction(at, 30000), Fraction(d, 30000))
                for at, d in zip(pts, [b-a for a, b in zip(pts, pts[1:])] + [tail])]
    assert observed_frames(path) == expected
    return path, expected


@pytest.mark.parametrize('capability', ['analysis', 'incident'])
def test_vfr_transition_preserves_every_frame_duration(vfr_media, tmp_path, capability):
    path, expected = vfr_media
    before = fingerprint(path)
    work = tmp_path / 'work'
    work.mkdir()
    engine = LocalAnalysisMaterializer({'profile': AnalysisProfile(48, 'veryfast', 23)}, temp_root=work)
    incident = LocalIncidentMaterializer(IncidentClipEncoding(48, 'veryfast', 23), temp_root=work)
    with RecordingService(analysis_materializer=engine, incident_materializer=incident) as service:
        registered = service.register_local_source(path)
        timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
        ref = dict(timeline_id=timeline.timeline_id, revision=timeline.revision)
        end = float(expected[-1][0] + expected[-1][1])
        # Stay inside decimal stream metadata; actual frame coverage is asserted separately.
        requested_end = int(end * 1000000) / 1000000
        resolution = service.resolve_span(ref, dict(start_sec=0., end_sec=requested_end),
            media_stream_ref=registered.media_streams[0].media_stream_ref)
        assert resolution.status == 'COMPLETE'
        if capability == 'analysis':
            prepared = service.prepare_analysis_source(resolution.spans[0], 'profile', timeline_ref=ref)
            opened = service.open_analysis_source(prepared.analysis_source_ref).stream
        else:
            prepared = service.build_incident_clip(resolution)
            assert prepared.source_provenance.asset_spans == resolution.spans
            opened = BytesIO(service._local_clips[prepared.incident_clip_ref][1])
        with opened as stream:
            output = tmp_path / 'output.mp4'
            output.write_bytes(stream.read())
        assert observed_frames(output) == expected
        assert prepared.timeline_range.start_sec == 0.
        assert prepared.timeline_range.end_sec == end
        assert abs(prepared.duration_sec - end) <= 0.001
    assert fingerprint(path) == before
    assert not list(work.iterdir())


@pytest.mark.parametrize('corruption', ['pts', 'duration', 'tail'])
def test_vfr_output_corruption_still_rejected(vfr_media, tmp_path, monkeypatch, corruption):
    path, expected = vfr_media
    work = tmp_path / 'work'
    work.mkdir()
    engine = LocalAnalysisMaterializer({'profile': AnalysisProfile(48, 'veryfast', 23)}, temp_root=work)
    probe = engine._probe

    def corrupt_output(target, index=None):
        data = probe(target, index)
        if index is None:
            if corruption == 'tail':
                data['frames'][-1].pop('duration', None)
                data['frames'][-1].pop('pkt_duration', None)
            else:
                key = 'best_effort_timestamp' if corruption == 'pts' else 'duration'
                data['frames'][1][key] = int(data['frames'][1][key]) + 1
        return data

    monkeypatch.setattr(engine, '_probe', corrupt_output)
    with RecordingService(analysis_materializer=engine) as service:
        registered = service.register_local_source(path)
        timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
        ref = dict(timeline_id=timeline.timeline_id, revision=timeline.revision)
        end = int(float(expected[-1][0] + expected[-1][1]) * 1000000) / 1000000
        resolution = service.resolve_span(ref, dict(start_sec=0., end_sec=end),
            media_stream_ref=registered.media_streams[0].media_stream_ref)
        with pytest.raises(RecordingCapabilityError) as caught:
            service.prepare_analysis_source(resolution.spans[0], 'profile', timeline_ref=ref)
        assert caught.value.code == 'UNSUPPORTED_MEDIA'
        assert not service._local_analysis
    assert not list(work.iterdir())


@pytest.mark.parametrize('capability', ['analysis', 'incident'])
@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('vfr_media', ['long_short', 'short_long'], indirect=True)
@pytest.mark.parametrize('bad_duration', [False, True])
def test_vfr_and_cfr_same_clock_chain(vfr_media, tmp_path, monkeypatch, capability, reverse, bad_duration):
    path, first_frames = vfr_media
    other = tmp_path / 'constant.mp4'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-f', 'lavfi',
        '-i', 'color=c=blue:s=64x48:r=30', '-frames:v', '6', '-c:v', 'libx264',
        '-video_track_timescale', '30000', str(other)], check=True, capture_output=True, timeout=30)
    entries = [(path, first_frames), (other, observed_frames(other))]
    if reverse:
        entries.reverse()
    before = [fingerprint(p) for p, _ in entries]
    work = tmp_path / 'work'
    work.mkdir()
    engine = LocalAnalysisMaterializer({'profile': AnalysisProfile(48, 'veryfast', 23)}, temp_root=work)
    incident = LocalIncidentMaterializer(IncidentClipEncoding(48, 'veryfast', 23), temp_root=work)
    if bad_duration:
        selected_engine = engine if capability == 'analysis' else incident._engine
        probe = selected_engine._probe

        def corrupt_format_duration(target, index=None):
            data = probe(target, index)
            if index is None and len(data['frames']) == 10:
                # Exact PTS/packets do not excuse incorrect container metadata.
                data['format']['duration'] = '0.450000'
            return data

        monkeypatch.setattr(selected_engine, '_probe', corrupt_format_duration)
    expected, offset, rows = [], Fraction(0), []
    with RecordingService(analysis_materializer=engine, incident_materializer=incident) as service:
        for source, frames in entries:
            registered = service.register_local_source(source)
            length = frames[-1][0] + frames[-1][1]
            # Decimal metadata for thirds is covered by existing mixed-clock regressions.
            # Use exact 0.2-second VFR/CFR parts here to isolate reorder delay at a seam.
            assert length == Fraction(1, 5)
            rows.append(dict(source_asset_ref=registered.source_asset.source_asset_ref,
                media_stream_ref=registered.media_streams[0].media_stream_ref,
                timeline_start_sec=float(offset), timeline_end_sec=float(offset+length)))
            expected.extend((offset+at, d) for at, d in frames)
            offset += length
        timeline = service.create_relative_timeline_from_placements(rows)
        resolution = service.resolve_span(dict(timeline_id=timeline.timeline_id, revision=timeline.revision),
            dict(start_sec=0., end_sec=float(offset)), media_stream_refs=[r['media_stream_ref'] for r in rows])
        assert resolution.status == 'COMPLETE'
        def build():
            return (service.prepare_analysis_source_from_resolution(resolution, 'profile')
                if capability == 'analysis' else service.build_incident_clip(resolution))

        if bad_duration:
            with pytest.raises(RecordingCapabilityError) as caught:
                build()
            assert caught.value.code == ('UNSUPPORTED_MEDIA' if capability == 'analysis' else 'INCIDENT_CLIP_BUILD_FAILED')
            assert not service._local_analysis and not service._local_clips
        else:
            prepared = build()
            if capability == 'analysis':
                opened = service.open_analysis_source(prepared.analysis_source_ref).stream
            else:
                assert prepared.source_provenance.asset_spans == resolution.spans
                opened = BytesIO(service._local_clips[prepared.incident_clip_ref][1])
            with opened as stream:
                output = tmp_path / 'chain.mp4'
                output.write_bytes(stream.read())
            assert observed_frames(output) == expected
            assert prepared.timeline_range == resolution.requested_range
    assert [fingerprint(p) for p, _ in entries] == before
    assert not list(work.iterdir())
