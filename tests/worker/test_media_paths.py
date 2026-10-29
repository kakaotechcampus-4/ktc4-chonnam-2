"""Worker composition must keep cleanup identities out of media tool paths."""
from io import StringIO
import json
import os
from pathlib import Path
import struct
import subprocess
from threading import Event
from types import MappingProxyType

import pytest

from daesingo.common.bootstrap import Startup
from daesingo.common.config import RuntimeConfig
from daesingo.common.logging import configure_logging
from daesingo.common.storage._filesystem import configuration_path
from daesingo.recording import (
    AnalysisProfile, IncidentClipEncoding, LocalAnalysisMaterializer,
    LocalIncidentMaterializer, RecordingService,
    RecordingCapabilityError,
)
from daesingo.recording.exports import LocalExportMaterializer, PostStamp
from daesingo.recording.observability import capture_materialization
from daesingo.worker.composition import compose_worker
from daesingo.worker.registry import KindRegistry


@pytest.fixture
def worker_media(tmp_path):
    work = tmp_path / 'worker temp 한글'
    work.mkdir()
    config = RuntimeConfig.from_mapping('worker', {
        'DAESINGO_RUNTIME_DB_URL': 'mysql+pymysql://test@127.0.0.1:1/test_media_paths',
        'DAESINGO_RUNTIME_MEDIA_ROOT': str(tmp_path / 'media'),
        'DAESINGO_RUNTIME_WORKER_TEMP_ROOT': str(work),
    })
    startup = Startup(config, MappingProxyType({}), configure_logging('worker', stream=StringIO()))
    worker = compose_worker(engine=object(), startup=startup, registry=KindRegistry({}), stop=Event())
    yield worker.media, work
    # No DB/provider or background services are started by this fixture.
    assert not list(work.glob('recording-*'))
    assert not list(work.glob('export-*'))


def test_worker_media_keeps_canonical_cleanup_identity_and_ordinary_tool_path(worker_media):
    media, work = worker_media
    engine = media.materializer(LocalAnalysisMaterializer, {'profile': AnalysisProfile(48, 'veryfast', 23)})
    assert media.scanner.root == configuration_path(work)
    if os.name == 'nt':
        assert str(media.scanner.root).startswith('\\\\?\\Volume{')
    assert engine._temp_root == work
    assert engine._temp_root.is_absolute()


@pytest.fixture
def sources(tmp_path):
    paths = []
    for i, color in enumerate(('red', 'blue')):
        path = tmp_path / f'synthetic-{i}.mp4'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-n', '-f', 'lavfi', '-i',
            f'color=c={color}:s=64x48:r=10:d=1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            '-video_track_timescale', '10000', str(path)], check=True, capture_output=True, timeout=30)
        paths.append(path)
    return paths


@pytest.mark.parametrize('kind', ['analysis', 'incident'])
@pytest.mark.parametrize('count', [1, 2])
def test_worker_media_real_single_and_chain(worker_media, sources, tmp_path, monkeypatch, kind, count):
    media, work = worker_media
    write_bytes = Path.write_bytes

    def write_with_cleanup(path, content):
        result = write_bytes(path, content)
        if path.parent.name.startswith('recording-chain-'):
            # Cleanup must remain excluded between the ffmpeg calls too.
            os.utime(path, (1, 1))
            os.utime(path.parent, (1, 1))
            assert media.scanner.scan().count == 0
            assert path.read_bytes() == content
        return result

    monkeypatch.setattr(Path, 'write_bytes', write_with_cleanup)
    analysis = media.materializer(LocalAnalysisMaterializer, {'profile': AnalysisProfile(48, 'veryfast', 23)})
    incident = media.materializer(LocalIncidentMaterializer, IncidentClipEncoding(48, 'veryfast', 23))
    with RecordingService(analysis_materializer=analysis, incident_materializer=incident) as service:
        registered = [service.register_local_source(p) for p in sources[:count]]
        timeline = service.create_relative_timeline_from_placements([
            dict(source_asset_ref=r.source_asset.source_asset_ref,
                 media_stream_ref=r.media_streams[0].media_stream_ref,
                 timeline_start_sec=float(i), timeline_end_sec=float(i + 1))
            for i, r in enumerate(registered)])
        resolution = service.resolve_span(dict(timeline_id=timeline.timeline_id, revision=timeline.revision),
            dict(start_sec=0., end_sec=float(count)),
            media_stream_refs=[r.media_streams[0].media_stream_ref for r in registered])
        if kind == 'analysis':
            result = service.prepare_analysis_source_from_resolution(resolution, 'profile')
            with service.open_analysis_source(result.analysis_source_ref).stream as stream:
                content = stream.read()
        else:
            result = service.build_incident_clip(resolution)
            content = service._local_clips[result.incident_clip_ref][1]
        assert result.duration_sec == float(count)
        output = tmp_path / 'checked.mp4'
        output.write_bytes(content)
        raw = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(output)],
                             capture_output=True, check=True, timeout=30)
        stream, = json.loads(raw.stdout)['streams']
        assert int(stream['nb_frames']) == count * 10
        assert (stream['width'], stream['height'], stream['time_base']) == (64, 48, '1/10000')
        pixels = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(output),
            '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'], capture_output=True, check=True, timeout=30).stdout
        assert len(pixels) == count * 10 * 64 * 48 * 3
        assert pixels[0] > 230 and pixels[2] < 10
        if count == 2:
            second = pixels[10 * 64 * 48 * 3:]
            assert second[2] > 230 and second[0] < 10
    assert media.scanner.scan().failed == 0


def test_worker_media_real_report_and_plate_export(worker_media, sources):
    media, _ = worker_media
    export = media.materializer(LocalExportMaterializer)
    content = sources[0].read_bytes()
    copied, operations = export.report(content, PostStamp(needed=False, value=None))
    assert copied == content and operations[0]['copy']
    stamped, operations = export.report(content, PostStamp(needed=True, value='2026-10-29T12:00:00+09:00'))
    assert stamped != content and operations[0]['post_stamp_applied']
    frame = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(sources[0]), '-frames:v', '1',
        '-f', 'image2pipe', '-c:v', 'png', 'pipe:1'], capture_output=True, check=True, timeout=30).stdout
    cropped, _ = export.plate(frame, [0, 0, 32, 24], 30000)
    assert struct.unpack('>II', cropped[16:24]) == (32, 24)


@pytest.mark.parametrize('kind', ['analysis', 'incident'])
def test_worker_concat_failure_does_not_expose_paths_or_filenames(worker_media, sources, monkeypatch, caplog, kind):
    media, work = worker_media
    analysis = media.materializer(LocalAnalysisMaterializer, {'profile': AnalysisProfile(48, 'veryfast', 23)})
    incident = media.materializer(LocalIncidentMaterializer, IncidentClipEncoding(48, 'veryfast', 23))
    write_text = Path.write_text
    private_name = 'private-original-filename.mp4'

    def broken_manifest(path, text, *args, **kwargs):
        if path.name == 'parts.txt':
            text = f'ffconcat version 1.0\nfile {private_name}\n'
        return write_text(path, text, *args, **kwargs)

    monkeypatch.setattr(Path, 'write_text', broken_manifest)
    with RecordingService(analysis_materializer=analysis, incident_materializer=incident) as service:
        registered = [service.register_local_source(p) for p in sources]
        timeline = service.create_relative_timeline_from_placements([
            dict(source_asset_ref=r.source_asset.source_asset_ref,
                 media_stream_ref=r.media_streams[0].media_stream_ref,
                 timeline_start_sec=float(i), timeline_end_sec=float(i + 1))
            for i, r in enumerate(registered)])
        resolution = service.resolve_span(dict(timeline_id=timeline.timeline_id, revision=timeline.revision),
            dict(start_sec=0., end_sec=2.),
            media_stream_refs=[r.media_streams[0].media_stream_ref for r in registered])
        with capture_materialization() as traces, pytest.raises(RecordingCapabilityError) as caught:
            if kind == 'analysis':
                service.prepare_analysis_source_from_resolution(resolution, 'profile')
            else:
                service.build_incident_clip(resolution)
        assert caught.value.code == ('TEMPORARY_FAILURE' if kind == 'analysis' else 'INCIDENT_CLIP_BUILD_FAILED')
        observed = str(caught.value) + caplog.text + json.dumps(traces)
        assert all(secret not in observed for secret in
                   [str(work), private_name, *[str(p) for p in sources], *[p.name for p in sources]])
        assert not service._local_analysis and not service._local_clips
    assert not list(work.glob('recording-*'))
