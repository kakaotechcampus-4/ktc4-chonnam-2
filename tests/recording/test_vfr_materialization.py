"""Presentation coverage must survive VFR encoding, including reordering boundaries."""
from fractions import Fraction
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

import pytest

from daesingo.recording import (
    AnalysisProfile, IncidentClipEncoding, LocalAnalysisMaterializer, LocalIncidentMaterializer,
    RecordingCapabilityError, RecordingService,
)
from daesingo.recording import multi_analysis
from daesingo.recording.chain_clock import prepare_mixed_parts
from daesingo.recording.materialization import MaterializedVideo
from daesingo.recording.models import TimeRange
from tests.recording.test_local_analysis_source import fingerprint


def observed_frames(path):
    raw = json.loads(subprocess.run([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_frames',
        '-show_entries', 'stream=time_base:frame=best_effort_timestamp,duration,pkt_duration',
        '-of', 'json', str(path)], check=True, capture_output=True, timeout=30).stdout)
    base = Fraction(raw['streams'][0]['time_base'])
    return [(int(f['best_effort_timestamp']) * base,
             int(f.get('duration', f.get('pkt_duration'))) * base) for f in raw['frames']]


def observe_encodes(engine, monkeypatch):
    commands = []
    run = engine._run

    def observed_run(argv):
        if '-vf' in argv:
            commands.append(list(argv))
        return run(argv)

    monkeypatch.setattr(engine, '_run', observed_run)
    return commands


def assert_bframe_policy(commands, frame_sets):
    assert len(commands) == len(frame_sets)
    for command, frames in zip(commands, frame_sets):
        variable = len({duration for _, duration in frames}) > 1
        assert ('-bf' in command) == variable
        if variable:
            assert command[command.index('-bf') + 1] == '0'


def single_preset(frames):
    # Keep the original veryfast VFR regression. On ffprobe 6.1, reordered
    # passthrough CFR MP4 can lack duration evidence; this control needs none.
    return 'veryfast' if len({duration for _, duration in frames}) > 1 else 'ultrafast'


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
def test_vfr_transition_preserves_every_frame_duration(vfr_media, tmp_path, monkeypatch, capability):
    path, expected = vfr_media
    before = fingerprint(path)
    work = tmp_path / 'work'
    work.mkdir()
    preset = single_preset(expected)
    engine = LocalAnalysisMaterializer({'profile': AnalysisProfile(48, preset, 23)}, temp_root=work)
    incident = LocalIncidentMaterializer(IncidentClipEncoding(48, preset, 23), temp_root=work)
    commands = observe_encodes(engine if capability == 'analysis' else incident._engine, monkeypatch)
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
    assert_bframe_policy(commands, [expected])


@pytest.mark.parametrize('corruption', ['pts', 'duration', 'tail'])
def test_vfr_output_corruption_still_rejected(vfr_media, tmp_path, monkeypatch, corruption):
    path, expected = vfr_media
    before = fingerprint(path)
    work = tmp_path / 'work'
    work.mkdir()
    engine = LocalAnalysisMaterializer({'profile': AnalysisProfile(48, single_preset(expected), 23)}, temp_root=work)
    probe = engine._probe
    frames = engine._frames
    injected, validated = [], []

    def observe_validation(data, **kwargs):
        if injected and data is injected[0]:
            validated.append(True)
        return frames(data, **kwargs)

    monkeypatch.setattr(engine, '_frames', observe_validation)

    def corrupt_output(target, index=None):
        data = probe(target, index)
        if index is None:
            # Prove this is valid output before the intended mutation.
            frames(data)
            if corruption == 'tail':
                data['frames'][-1].pop('duration', None)
                data['frames'][-1].pop('pkt_duration', None)
            else:
                keys = (['best_effort_timestamp'] if corruption == 'pts'
                    else [key for key in ('duration', 'pkt_duration') if key in data['frames'][1]])
                for key in keys:
                    data['frames'][1][key] = int(data['frames'][1][key]) + 1
            injected.append(data)
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
    assert len(injected) == len(validated) == 1
    assert fingerprint(path) == before
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
    # Isolate VFR/CFR seam coverage from old MOV demuxer B-frame duration limits.
    # Command assertions below still require explicit -bf 0 only for VFR parts.
    engine = LocalAnalysisMaterializer({'profile': AnalysisProfile(48, 'ultrafast', 23)}, temp_root=work)
    incident = LocalIncidentMaterializer(IncidentClipEncoding(48, 'ultrafast', 23), temp_root=work)
    selected_engine = engine if capability == 'analysis' else incident._engine
    commands = observe_encodes(selected_engine, monkeypatch)
    packets_checked, decoded, injected, frames_checked = [], [], [], []
    validate_packets, strict_decode = multi_analysis.validate_packets, selected_engine._strict_decode

    def observe_packets(*args):
        validate_packets(*args)
        packets_checked.append(True)

    def observe_decode(target):
        strict_decode(target)
        decoded.append(True)

    monkeypatch.setattr(multi_analysis, 'validate_packets', observe_packets)
    monkeypatch.setattr(selected_engine, '_strict_decode', observe_decode)
    if bad_duration:
        probe = selected_engine._probe
        parse_frames = selected_engine._frames

        def observe_frames(data, **kwargs):
            result = parse_frames(data, **kwargs)
            if injected and data is injected[0]:
                assert result[1] == expected
                frames_checked.append(True)
            return result

        monkeypatch.setattr(selected_engine, '_frames', observe_frames)

        def corrupt_format_duration(target, index=None):
            data = probe(target, index)
            if index is None and len(data['frames']) == 10:
                # Exact PTS/packets do not excuse incorrect container metadata.
                assert parse_frames(data, expected_coverage=expected)[1] == expected
                data['format']['duration'] = '0.450000'
                injected.append(data)
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
    assert_bframe_policy(commands, [frames for _, frames in entries])
    assert len(packets_checked) == 1
    assert len(decoded) == (0 if bad_duration else 1)
    if bad_duration:
        assert len(injected) == len(frames_checked) == 1


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('vfr_media', ['long_short', 'short_long'], indirect=True)
def test_same_clock_packet_projection_with_reorder(vfr_media, tmp_path, reverse):
    """Keep a real nonzero decode origin without old MOV re-demux duration loss."""
    path, vfr_frames = vfr_media
    other = tmp_path / 'reordered-cfr.mp4'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-f', 'lavfi',
        '-i', 'color=c=blue:s=64x48:r=30', '-frames:v', '6', '-c:v', 'libx264',
        '-video_track_timescale', '30000', str(other)], check=True, capture_output=True, timeout=30)
    entries = [(path, vfr_frames), (other, observed_frames(other))]
    if reverse:
        entries.reverse()
    before = [fingerprint(p) for p, _ in entries]
    engine = LocalAnalysisMaterializer({})
    parts, presentation = [], []
    offset = Fraction(0)
    for source, frames in entries:
        raw = json.loads(engine._run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_packets', '-show_entries', 'stream=time_base,has_b_frames:packet=pts,dts,duration',
            '-of', 'json', str(source)]))
        stream = raw['streams'][0]
        clock = Fraction(stream['time_base'])
        assert clock == Fraction(1, 30000)
        packets = [tuple(int(p[k]) * clock for k in ('pts', 'dts', 'duration')) for p in raw['packets']]
        if source == other:
            assert stream['has_b_frames'] > 0 and packets[0][1] == Fraction(-2, 30)
        else:
            assert stream['has_b_frames'] == 0 and packets[0][1] == 0
        length = frames[-1][0] + frames[-1][1]
        parts.append(MaterializedVideo(source.read_bytes(), float(length),
            TimeRange(start_sec=float(offset), end_sec=float(offset + length)),
            tuple(frames), clock, (64, 48), source_frames=tuple(frames)))
        presentation.extend((offset + pts, duration) for pts, _, duration in packets)
        offset += length
    # Independent reference: retain every presentation instant/interval while
    # the decode intervals form one continuous sequence with the shared delay.
    reference, decode_at = [], Fraction(-2, 30)
    for pts, duration in presentation:
        reference.append((pts * 30, decode_at * 30, duration * 30))
        decode_at += duration
    work = tmp_path / 'projection'
    work.mkdir()
    with TemporaryDirectory(dir=work) as directory:
        root = Path(directory)
        lines, options, expected, base = prepare_mixed_parts(engine, parts, root)
        assert base == Fraction(1, 30)
        assert expected == reference
        manifest = root / 'parts.txt'
        manifest.write_text('\n'.join(lines) + '\n', encoding='ascii')
        # Copy-mux directly to framecrc: observe the actual setts packet result
        # before a second MP4 demuxer can hide or infer presentation durations.
        result = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror',
            '-protocol_whitelist', 'file', '-f', 'concat', '-safe', '1', '-i', str(manifest),
            '-map', '0:v:0', '-c:v', 'copy', *options, '-f', 'framecrc', '-'],
            check=True, capture_output=True, text=True, timeout=30)
        assert '#tb 0: 1/30' in result.stdout
        rows = [line.split(',') for line in result.stdout.splitlines() if line and not line.startswith('#')]
        actual = [(int(row[2]), int(row[1]), int(row[3])) for row in rows]
        assert actual == reference
        assert len(actual) == 10 and actual[0][1] == -2
        assert all(a[1] + a[2] == b[1] for a, b in zip(actual, actual[1:]))
    assert [fingerprint(p) for p, _ in entries] == before
    assert not list(work.iterdir())
