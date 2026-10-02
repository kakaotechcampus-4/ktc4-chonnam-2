"""구버전 ffprobe 출력 형태 fixture와 실제 공통 엔진 공개 경로 회귀."""

from fractions import Fraction
import shutil
import subprocess

import pytest

from daesingo.recording import (
    AnalysisProfile, IncidentClipEncoding, LocalAnalysisMaterializer,
    LocalIncidentMaterializer, RecordingCapabilityError, RecordingService,
)


def payload(frames):
    return {"streams": [{"codec_type": "video", "time_base": "1/10"}], "frames": frames}


def quantized_payload():
    return {"format": {"format_name": "matroska,webm"},
            "streams": [{"codec_type": "video", "time_base": "1/1000"}],
            "frames": [{"best_effort_timestamp": at, "duration": 33}
                       for at in [0, 33, 67, 100, 133, 167, 200]]}


def test_millisecond_quantization_preserves_pts_and_observed_tail():
    base, frames = LocalAnalysisMaterializer._frames(quantized_payload())
    assert base == Fraction(1, 1000)
    assert [at for at, _ in frames] == [Fraction(at, 1000) for at in [0, 33, 67, 100, 133, 167, 200]]
    assert [length for _, length in frames] == [Fraction(n, 1000) for n in [33, 34, 33, 33, 34, 33, 33]]


@pytest.mark.parametrize("change", ["gap", "one_tick_gap", "reverse", "duplicate", "tail", "mp4", "coarse"])
def test_quantization_does_not_hide_invalid_coverage(change):
    data = quantized_payload()
    if change in {"gap", "one_tick_gap"}:
        for frame in data["frames"][3:]:
            frame["best_effort_timestamp"] += 3 if change == "gap" else 1
    elif change == "reverse":
        data["frames"][3]["best_effort_timestamp"] = 66
    elif change == "duplicate":
        data["frames"][3]["best_effort_timestamp"] = 67
    elif change == "tail":
        del data["frames"][-1]["duration"]
    elif change == "mp4":
        data["format"]["format_name"] = "mov,mp4,m4a,3gp,3g2,mj2"
    else:
        data["streams"][0]["time_base"] = "1/10"
    with pytest.raises(RecordingCapabilityError):
        LocalAnalysisMaterializer._frames(data)


def test_negative_one_tick_rounding_and_legacy_duration():
    data = quantized_payload()
    for frame, at in zip(data["frames"], [0, 34, 67, 101, 134, 168, 201]):
        frame["best_effort_timestamp"] = at
        frame["pkt_duration"] = 34
        del frame["duration"]
    _, frames = LocalAnalysisMaterializer._frames(data)
    assert [length * 1000 for _, length in frames] == [34, 33, 34, 33, 34, 33, 34]


@pytest.mark.parametrize("change", [None, "pts", "gap", "tail"])
def test_output_quantization_requires_exact_selected_source_pts(change):
    data = quantized_payload()
    _, expected = LocalAnalysisMaterializer._frames(data)
    data["format"]["format_name"] = "mov,mp4"
    if change == "pts":
        data["frames"][3]["best_effort_timestamp"] += 1
    elif change == "gap":
        data["frames"][1]["duration"] -= 2
    elif change == "tail":
        del data["frames"][-1]["duration"]
    if change:
        with pytest.raises(RecordingCapabilityError):
            LocalAnalysisMaterializer._frames(data, expected_coverage=expected)
    else:
        assert LocalAnalysisMaterializer._frames(data, expected_coverage=expected)[1] == expected


def test_generated_h264_mkv_public_materialization(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe 필요")
    from tests.recording.test_local_analysis_source import fingerprint
    path = tmp_path / "quantized.mkv"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
        "testsrc2=s=64x48:r=30:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        check=True, capture_output=True, timeout=30)
    before = fingerprint(path)
    work = tmp_path / "work"
    work.mkdir()
    analysis = LocalAnalysisMaterializer({"profile": AnalysisProfile(48, "veryfast", 23)}, temp_root=work)
    raw = analysis._probe(path, 0)
    assert any(int(a["best_effort_timestamp"]) + int(a.get("duration", a.get("pkt_duration")))
               != int(b["best_effort_timestamp"]) for a, b in zip(raw["frames"], raw["frames"][1:]))
    with RecordingService(analysis_materializer=analysis,
            incident_materializer=LocalIncidentMaterializer(IncidentClipEncoding(48, "veryfast", 23), temp_root=work)) as service:
        registered = service.register_local_source(path)
        video, = registered.media_streams
        timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
        ref = {"timeline_id": timeline.timeline_id, "revision": timeline.revision}
        resolved = service.resolve_span(ref, {"start_sec": 0.0, "end_sec": 1.0}, media_stream_ref=video.media_stream_ref)
        assert resolved.status == "COMPLETE"
        prepared = service.prepare_analysis_source(resolved.spans[0], "profile", timeline_ref=ref)
        with service.open_analysis_source(prepared.analysis_source_ref).stream as opened:
            assert len(opened.read()) == prepared.byte_size > 0
        clip = service.build_incident_clip(resolved)
        assert clip.byte_size > 0 and clip.source_provenance.asset_spans == resolved.spans
        assert prepared.timeline_range == clip.timeline_range
        assert prepared.duration_sec == clip.duration_sec == 1.0
        frame = service.resolve_frame({"kind": "STREAM_POSITION", "media_stream_ref": video.media_stream_ref,
                                       "source_offset_sec": 0.5})
        assert service.read_frame(frame.frame_ref).startswith(b"\x89PNG\r\n\x1a\n")
    assert fingerprint(path) == before and not list(work.iterdir())


@pytest.mark.parametrize("mode", ["duration", "legacy", "mixed", "adjacent"])
def test_frame_duration_observations(mode):
    frames = [{"best_effort_timestamp": at, "duration": length} for at, length in [(7, 1), (8, 2), (10, 3)]]
    for i, frame in enumerate(frames):
        if mode == "legacy" or (mode == "mixed" and i % 2 == 0):
            frame["pkt_duration"] = frame.pop("duration")
        if mode == "adjacent" and i < 2:
            del frame["duration"]
    base, actual = LocalAnalysisMaterializer._frames(payload(frames))
    assert base == Fraction(1, 10)
    assert actual == [(Fraction(0), Fraction(1, 10)), (Fraction(1, 10), Fraction(2, 10)),
                      (Fraction(3, 10), Fraction(3, 10))]


@pytest.mark.parametrize("frames,reason", [
    ([{"best_effort_timestamp": 0}, {"best_effort_timestamp": 1}], "마지막 frame"),
    ([{"best_effort_timestamp": 0}], "마지막 frame"),
    ([{"best_effort_timestamp": 1}, {"best_effort_timestamp": 0, "duration": 1}], "엄격히 증가"),
    ([{"best_effort_timestamp": 0}, {"best_effort_timestamp": 0, "duration": 1}], "엄격히 증가"),
    ([{"best_effort_timestamp": 0, "pkt_duration": 1}, {"best_effort_timestamp": 3, "duration": 1}], "불연속"),
    ([{"best_effort_timestamp": 0, "duration": 1, "pkt_duration": 2}], "서로 다릅니다"),
    ([{"best_effort_timestamp": 0, "duration": 0}], "유효하지"),
])
def test_unverifiable_coverage_rejected(frames, reason):
    data = payload(frames)
    data["format"] = {"duration": "100"}  # container 길이나 fps로 마지막 frame을 꾸미지 않는다.
    data["streams"][0].update(duration="100", avg_frame_rate="30/1")
    with pytest.raises(RecordingCapabilityError, match=reason) as caught:
        LocalAnalysisMaterializer._frames(data)
    assert caught.value.code == "UNSUPPORTED_MEDIA"


@pytest.mark.parametrize("capability", ["analysis", "incident"])
@pytest.mark.parametrize("mode", ["legacy", "mixed", "adjacent", "no_tail", "gap", "output_no_tail"])
def test_public_materialization_with_legacy_probe_shape(tmp_path, monkeypatch, capability, mode):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe 필요")
    path = tmp_path / "private-original.avi"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
        "testsrc2=s=64x48:r=10:d=1", "-c:v", "mpeg4", str(path)], check=True, capture_output=True, timeout=30)
    work = tmp_path / "work"
    work.mkdir()
    analysis = LocalAnalysisMaterializer({"profile": AnalysisProfile(48, "veryfast", 23)}, temp_root=work)
    incident = LocalIncidentMaterializer(IncidentClipEncoding(48, "veryfast", 23), temp_root=work)
    engine = analysis if capability == "analysis" else incident._engine
    original_probe = engine._probe
    calls = []

    def legacy_probe(target, index=None):
        data = original_probe(target, index)
        calls.append(index)
        for i, frame in enumerate(data["frames"]):
            # 現 ffprobe 실제 관찰값을 옛 필드 이름으로 옮기는 출력 형태 fixture.
            if mode != "mixed" or i % 2 == 0:
                frame["pkt_duration"] = frame.pop("duration")
            if mode == "adjacent" and i < len(data["frames"]) - 1:
                frame.pop("duration", None)
                frame.pop("pkt_duration", None)
        if mode == "no_tail" or (mode == "output_no_tail" and index is None):
            data["frames"][-1].pop("duration", None)
            data["frames"][-1].pop("pkt_duration", None)
        if mode == "gap":
            data["frames"][0]["pkt_duration"] *= 2
        return data

    monkeypatch.setattr(engine, "_probe", legacy_probe)
    with RecordingService(analysis_materializer=analysis, incident_materializer=incident) as service:
        registered = service.register_local_source(path)
        timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
        ref = {"timeline_id": timeline.timeline_id, "revision": timeline.revision}
        resolution = service.resolve_span(ref, {"start_sec": 0.0, "end_sec": 1.0},
                                         media_stream_ref=registered.media_streams[0].media_stream_ref)

        def build():
            if capability == "analysis":
                return service.prepare_analysis_source(resolution.spans[0], "profile", timeline_ref=ref)
            return service.build_incident_clip(resolution)

        if mode in {"no_tail", "gap", "output_no_tail"}:
            with pytest.raises(RecordingCapabilityError) as caught:
                build()
            assert caught.value.code == ("UNSUPPORTED_MEDIA" if capability == "analysis" else "INCIDENT_CLIP_BUILD_FAILED")
            assert ("불연속" if mode == "gap" else "마지막 frame") in str(caught.value)
            assert str(path) not in str(caught.value) and path.name not in str(caught.value)
            assert not service._local_analysis and not service._local_clips
        else:
            result = build()
            assert calls == [0, None]  # 원본과 실제 인코딩 결과 모두 같은 호환 경로로 검증
            assert result.duration_sec == 1.0
            assert result.timeline_range.start_sec == 0.0 and result.timeline_range.end_sec == 1.0
            if capability == "analysis":
                with service.open_analysis_source(result.analysis_source_ref).stream as stream:
                    content = stream.read()
            else:
                content = service._local_clips[result.incident_clip_ref][1]
            assert len(content) == result.byte_size > 0
        assert not list(work.iterdir())
