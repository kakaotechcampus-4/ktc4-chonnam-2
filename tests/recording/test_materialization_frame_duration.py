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
