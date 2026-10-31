"""Actual Recording/FFmpeg boundary behind the production clip handler."""
from contextlib import contextmanager
from types import SimpleNamespace
import subprocess
import json
from fractions import Fraction

import pytest

from daesingo.common.jobs.execution import ExecutionContext
from daesingo.recording import IncidentClipEncoding, LocalIncidentMaterializer, RecordingService
from daesingo.worker.incident_clip_handlers import incident_clip_registry
from tests.recording.test_multi_span_analysis_source import chain as chain
from tests.recording.test_local_analysis_source import fingerprint


@pytest.mark.parametrize("start,end,expected", [
    (1., 3., [(1., 2., 1., 2.), (2., 3., 0., 1.)]),
    (2.2, 3.2, [(2.2, 3.2, .2, 1.2)]),
])
def test_handler_uses_case_chain_and_fine_pixels(chain, tmp_path, start, end, expected):
    service, original, paths, work, _ = chain
    refs = [s.media_stream_ref for s in original.spans]
    resolution = service.resolve_span(original.timeline_ref, dict(start_sec=start, end_sec=end), media_stream_refs=refs)
    source = service.prepare_analysis_source_from_resolution(resolution, "profile")
    service._incident_materializer = LocalIncidentMaterializer(IncidentClipEncoding(48, "veryfast", 23), temp_root=work)
    before = [fingerprint(p) for p in paths]
    # Simulate the ownership capability only: all media and resolution remain real.
    service.owns_asset = lambda case_id, ref: case_id == "case" and ref.ref in {s.source_asset_ref for s in original.spans}
    clips = []
    build = service.build_incident_clip
    def capture(resolved):
        clip = build(resolved)
        clips.append(clip)
        return clip
    service.build_incident_clip = capture
    @contextmanager
    def factory(data):
        yield service
    data = SimpleNamespace(case_id="case", timeline_ref=original.timeline_ref.model_dump(),
        requested_range=dict(start_sec=start, end_sec=end), analysis_source_ref=source.analysis_source_ref,
        video_stream_refs=tuple(refs))
    result = incident_clip_registry(load=lambda ctx: data, service_factory=factory).dispatch(
        ExecutionContext("exec", "job", "case", "INCIDENT_CLIP_BUILD", 1, "trace"))
    assert result.status == "SUCCEEDED", result.failure_kind
    clip, = clips
    assert result.objects[0].payload == {"incident_clip_ref": clip.incident_clip_ref}
    spans = clip.source_provenance.asset_spans
    assert [(s.timeline_range.start_sec, s.timeline_range.end_sec, s.source_range.start_sec,
             s.source_range.end_sec) for s in spans] == expected
    assert clip.source_provenance.timeline_ref == original.timeline_ref
    assert clip.source_provenance.requested_range == resolution.requested_range
    assert clip.media_stream_refs == [s.media_stream_ref for s in spans]
    content = service._local_clips[clip.incident_clip_ref][1]
    output = tmp_path / "result.mp4"
    output.write_bytes(content)
    frames = subprocess.run(["ffmpeg", "-v", "error", "-i", str(output), "-f", "rawvideo",
        "-pix_fmt", "rgb24", "-"], capture_output=True, check=True, timeout=30).stdout
    assert len(frames) == round((end-start)*10)*64*48*3
    raw = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_frames", "-show_streams",
        "-of", "json", str(output)], capture_output=True, check=True, timeout=30).stdout)
    base = Fraction(raw["streams"][0]["time_base"])
    assert [(int(f["best_effort_timestamp"]) * base, int(f["duration"]) * base)
            for f in raw["frames"]] == [(Fraction(i, 10), Fraction(1, 10))
                for i in range(round((end-start)*10))]
    assert clip.timeline_range == resolution.requested_range
    assert [fingerprint(p) for p in paths] == before
    assert not list(work.iterdir())


@pytest.mark.parametrize("mode", ["missing_selection", "duplicate", "foreign", "missing_source",
    "changed_source", "timeline", "revision", "fine_missing_video"])
def test_unsafe_chain_never_publishes_clip(chain, mode):
    service, resolution, paths, work, _ = chain
    refs = [s.media_stream_ref for s in resolution.spans]
    source = service.prepare_analysis_source_from_resolution(resolution, "profile")
    service._incident_materializer = LocalIncidentMaterializer(IncidentClipEncoding(48, "veryfast", 23), temp_root=work)
    service.owns_asset = lambda case_id, ref: mode != "foreign" or ref.ref != resolution.spans[1].source_asset_ref
    selected = list(refs)
    if mode == "missing_selection":
        selected.pop(1)
    if mode == "duplicate":
        selected.append(selected[0])
    if mode == "missing_source":
        paths[1].unlink()
    if mode == "changed_source":
        paths[1].write_bytes(b"synthetic corrupt input")
    if mode == "fine_missing_video":
        source.media_stream_refs.remove(refs[1])
        service.get_analysis_source = lambda ref: source
    timeline = resolution.timeline_ref.model_dump()
    if mode == "timeline":
        timeline["timeline_id"] = "foreign"
    if mode == "revision":
        timeline["revision"] += 1
    data = SimpleNamespace(case_id="case", timeline_ref=timeline,
        requested_range=resolution.requested_range.model_dump(), analysis_source_ref=source.analysis_source_ref,
        video_stream_refs=tuple(selected))
    @contextmanager
    def factory(data):
        yield service
    result = incident_clip_registry(load=lambda ctx: data, service_factory=factory).dispatch(
        ExecutionContext("exec", "job", "case", "INCIDENT_CLIP_BUILD", 1, "trace"))
    assert result.status == "FAILED" and result.objects == result.produced == ()
    assert result.failure_kind == ("RECORDING_INCIDENT_CLIP_BUILD_FAILED"
        if mode in {"missing_source", "changed_source"} else "RUNTIME_HANDLER_ERROR")
    assert not service._local_clips and not list(work.iterdir())


@pytest.mark.parametrize("camera", [0, 1, "ambiguous"])
def test_simultaneous_cameras_keep_explicit_selection(tmp_path, camera):
    from daesingo.recording import AnalysisProfile, LocalAnalysisMaterializer
    path = tmp_path / "two-cameras.mkv"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
        "color=c=red:s=64x48:r=10:d=2", "-f", "lavfi", "-i", "color=c=blue:s=64x48:r=10:d=2",
        "-map", "0:v", "-map", "1:v", "-c:v", "libx264", str(path)], check=True, capture_output=True, timeout=30)
    work = tmp_path / "work"
    work.mkdir()
    with RecordingService(analysis_materializer=LocalAnalysisMaterializer(
            {"profile": AnalysisProfile(48, "veryfast", 23)}, temp_root=work),
            incident_materializer=LocalIncidentMaterializer(IncidentClipEncoding(48, "veryfast", 23), temp_root=work)) as service:
        registered = service.register_local_source(path)
        timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
        refs = [s.media_stream_ref for s in registered.media_streams]
        ref = dict(timeline_id=timeline.timeline_id, revision=timeline.revision)
        request = dict(start_sec=.5, end_sec=1.5)
        chosen = refs[camera] if isinstance(camera, int) else refs[0]
        resolution = service.resolve_span(ref, request, media_stream_ref=chosen)
        source = service.prepare_analysis_source(resolution.spans[0], "profile", timeline_ref=ref)
        if camera == "ambiguous":
            source = source.model_copy(update={"media_stream_refs": refs})
            service.get_analysis_source = lambda ref: source
        service.owns_asset = lambda case_id, asset: True
        data = SimpleNamespace(case_id="case", timeline_ref=ref, requested_range=request,
            analysis_source_ref=source.analysis_source_ref,
            video_stream_refs=tuple(refs) if camera == "ambiguous" else (chosen,))
        @contextmanager
        def factory(data):
            yield service
        result = incident_clip_registry(load=lambda ctx: data, service_factory=factory).dispatch(
            ExecutionContext("exec", "job", "case", "INCIDENT_CLIP_BUILD", 1, "trace"))
        if camera == "ambiguous":
            assert result.status == "FAILED" and not service._local_clips
        else:
            assert result.status == "SUCCEEDED", result.failure_kind
            clip = service.get_incident_clip(result.objects[0].payload["incident_clip_ref"])
            assert clip.media_stream_refs == [chosen]
            out = tmp_path / "clip.mp4"
            out.write_bytes(service._local_clips[clip.incident_clip_ref][1])
            pixels = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-f", "rawvideo",
                "-pix_fmt", "rgb24", "-"], check=True, capture_output=True, timeout=30).stdout
            r, _, b = pixels[:3]
            assert (r > 230 and b < 10) if camera == 0 else (b > 230 and r < 10)
        assert not list(work.iterdir())


@pytest.mark.parametrize("stage", ["extra_selection", "encode"])
def test_chain_cancel_releases_context_and_temporary_media(chain, stage):
    from daesingo.common.jobs.cancel import CancellationRequested
    service, original, _, work, _ = chain
    refs = [s.media_stream_ref for s in original.spans]
    request = dict(start_sec=2.2, end_sec=3.2) if stage == "extra_selection" else dict(start_sec=1., end_sec=3.)
    resolution = service.resolve_span(original.timeline_ref, request, media_stream_refs=refs)
    source = service.prepare_analysis_source_from_resolution(resolution, "profile")
    adapter = LocalIncidentMaterializer(IncidentClipEncoding(48, "veryfast", 23), temp_root=work)
    service._incident_materializer = adapter
    service.owns_asset = lambda case_id, asset: True
    context = ExecutionContext("exec", "job", "case", "INCIDENT_CLIP_BUILD", 1, "trace")
    get_stream, materialize = service.get_media_stream, adapter._engine.materialize
    def selected(ref):
        value = get_stream(ref)
        if stage == "extra_selection" and ref == refs[0]:
            context.cancel_signal.request()
        return value
    def encode(*args):
        value = materialize(*args)
        context.cancel_signal.request()
        return value
    service.get_media_stream = selected
    if stage == "encode":
        adapter._engine.materialize = encode
    closed = []
    @contextmanager
    def factory(data):
        try:
            yield service
        finally:
            service.close()
            closed.append(True)
    data = SimpleNamespace(case_id="case", timeline_ref=original.timeline_ref.model_dump(),
        requested_range=request, analysis_source_ref=source.analysis_source_ref, video_stream_refs=tuple(refs))
    with pytest.raises(CancellationRequested):
        incident_clip_registry(load=lambda ctx: data, service_factory=factory).dispatch(context)
    assert closed == [True] and not list(work.iterdir())
