"""짧은 합성 입력으로 metadata 반올림의 연결 검증을 재현한다."""
from decimal import Decimal
from dataclasses import replace
from fractions import Fraction
import subprocess
import struct
from types import SimpleNamespace

import pytest

from daesingo.recording import AnalysisProfile, LocalAnalysisMaterializer, RecordingCapabilityError, RecordingService
from daesingo.recording.materialization import MaterializedVideo
from daesingo.recording.models import AssetSpan, TimeRange
from daesingo.recording.multi_analysis import materialize_chain
from daesingo.recording.probe import LocalSource, ProbedStream, _snapshot
from tests.recording.test_local_analysis_source import fingerprint


def test_decimal_duration_sum_is_distinct_from_frame_coverage():
    # 실제 15개 수치의 대조는 보호 증거에서 별도 실행한다. 여기는 합성 산술이다.
    assert 7 * Fraction(1, 30) - 7 * Fraction("0.033333") == Fraction(7, 3000000)


class _ConcatReached(RuntimeError):
    """도구 실행 직전까지만 검사하는 무미디어 경계 재현의 종료점."""


@pytest.mark.parametrize("length,metadata", [(Fraction(1, 30), ".033333"), (Fraction(1, 15), ".066667")])
@pytest.mark.parametrize("mutation", [None, "gap", "overlap", "drift", "no_bounds", "no_full_end", "metadata",
    "partial", "duration", "missing", "duplicate", "source_duration", "fine_clock"])
def test_chain_boundary_requires_rounding_evidence(tmp_path, length, metadata, mutation):
    # 실제 파일은 identity 검사에만 쓴다. FFmpeg·DB 없이 제품 연결 함수에 진입한다.
    inputs, parts = [], []
    for i in range(7):
        path = tmp_path / f"identity-{i}"
        path.write_bytes(b"synthetic identity only")
        stat = _snapshot(path)
        source = LocalSource(path, stat[2], stat[3], stat[4], float(metadata),
            (ProbedStream(0, "VIDEO", float(metadata)),))
        a, b = Decimal(metadata) * i, Decimal(metadata) * (i + 1)
        span = AssetSpan(sequence=i, source_asset_ref=f"source-{i}", media_stream_ref=f"stream-{i}",
            timeline_range=TimeRange(start_sec=float(a), end_sec=float(b)),
            source_range=TimeRange(start_sec=0., end_sec=float(metadata)))
        frames = ((Fraction(0), length),)
        part = MaterializedVideo(b"synthetic part", float(length),
            TimeRange(start_sec=float(a), end_sec=float(Fraction(a) + length)), frames,
            Fraction(1, 30000), (64, 48), False, frames, (Fraction(0), length), length)
        if mutation == "gap" and i == 1:
            part = replace(part, timeline_range=part.timeline_range.model_copy(update={
                "start_sec": part.timeline_range.start_sec + .01}))
        elif mutation == "overlap" and i == 1:
            part = replace(part, timeline_range=part.timeline_range.model_copy(update={
                "start_sec": part.timeline_range.start_sec - .01}))
        elif mutation == "drift":
            part = replace(part, timeline_range=part.timeline_range.model_copy(update={
                "start_sec": part.timeline_range.start_sec + i * .00000075,
                "end_sec": part.timeline_range.end_sec + i * .00000075}))
        elif mutation == "no_bounds":
            part = replace(part, source_bounds=None)
        elif mutation == "no_full_end":
            part = replace(part, source_end=None)
        elif mutation == "metadata":
            source = replace(source, duration_sec=float(Decimal(metadata) + Decimal(".000001")))
        elif mutation == "partial":
            span = span.model_copy(update={"source_range": span.source_range.model_copy(update={
                "end_sec": span.source_range.end_sec - .000001})})
        elif mutation == "duration":
            part = replace(part, frames=((Fraction(0), length + Fraction(1, 30000)),))
        elif mutation == "missing":
            part = replace(part, frames=())
        elif mutation == "duplicate":
            part = replace(part, frames=frames + ((length, length),))
        elif mutation == "source_duration":
            part = replace(part, source_frames=((Fraction(0), length + Fraction(1, 30000)),))
        elif mutation == "fine_clock":
            part = replace(part, time_base=Fraction(1, 10000000))
        inputs.append((source, 0, span))
        parts.append(part)

    def stop(args):
        raise _ConcatReached()

    engine = SimpleNamespace(materialize=lambda source, index, span, profile: parts[span.sequence],
        _temp_root=tmp_path, _ffmpeg="unused", _run=stop)
    if mutation is None:
        with pytest.raises(_ConcatReached):
            materialize_chain(engine, inputs, "profile")
    else:
        with pytest.raises(RecordingCapabilityError) as caught:
            materialize_chain(engine, inputs, "profile")
        assert caught.value.code == "UNSUPPORTED_MEDIA"
    assert not list(tmp_path.glob("recording-chain-*"))


def test_seven_short_sources_preserve_frames_despite_rounded_placements(tmp_path):
    paths = []
    for i in range(7):
        path = tmp_path / f"synthetic-{i}.avi"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
            "color=c=red:s=64x48:r=30", "-frames:v", "1", "-c:v", "mpeg4", str(path)],
            check=True, capture_output=True, timeout=30)
        paths.append(path)
    before = [fingerprint(p) for p in paths]
    work = tmp_path / "work"
    work.mkdir()
    engine = LocalAnalysisMaterializer({"profile": AnalysisProfile(48, "veryfast", 23)}, temp_root=work)
    with RecordingService(analysis_materializer=engine) as service:
        registered = [service.register_local_source(p) for p in paths]
        assert all(r.source_asset.duration_sec == .033333 for r in registered)
        rows = [dict(source_asset_ref=r.source_asset.source_asset_ref,
            media_stream_ref=r.media_streams[0].media_stream_ref,
            timeline_start_sec=float(Decimal("0.033333") * i),
            timeline_end_sec=float(Decimal("0.033333") * (i + 1))) for i, r in enumerate(registered)]
        timeline = service.create_relative_timeline_from_placements(rows)
        resolution = service.resolve_span(dict(timeline_id=timeline.timeline_id, revision=timeline.revision),
            dict(start_sec=0., end_sec=.233331), media_stream_refs=[r["media_stream_ref"] for r in rows])
        prepared = service.prepare_analysis_source_from_resolution(resolution, "profile")
        assert prepared.timeline_range.start_sec == 0.
        assert prepared.timeline_range.end_sec == float(Fraction(".199998") + Fraction(1, 30))
        assert [r.ref for r in prepared.source_refs] == [s.source_asset_ref for s in resolution.spans]
        with service.open_analysis_source(prepared.analysis_source_ref).stream as stream:
            output = tmp_path / "chain.mp4"
            output.write_bytes(stream.read())
        raw = engine._probe(output)
        _, frames = engine._frames(raw)
        assert prepared.duration_sec == float(raw["format"]["duration"])
        assert len(frames) == 7
        assert frames == [(Fraction(i, 30), Fraction(1, 30)) for i in range(7)]
        engine._strict_decode(output)
    assert [fingerprint(p) for p in paths] == before
    assert not list(work.iterdir())


def test_truncated_header_duration_does_not_prove_full_source_end(tmp_path):
    paths = []
    for i in range(7):
        path = tmp_path / f"synthetic-header-{i}.avi"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
            "color=c=red:s=64x48:r=30", "-frames:v", "2", "-c:v", "mpeg4", str(path)],
            check=True, capture_output=True, timeout=30)
        data = bytearray(path.read_bytes())
        # 직접 생성한 2프레임 AVI의 header만 1프레임으로 위장한다.
        avih, strh = data.find(b"avih"), data.find(b"strh")
        assert avih >= 0 and strh >= 0
        struct.pack_into("<I", data, avih + 8 + 16, 1)
        struct.pack_into("<I", data, strh + 8 + 32, 1)
        path.write_bytes(data)
        paths.append(path)
    before = [fingerprint(p) for p in paths]
    work = tmp_path / "work"
    work.mkdir()
    engine = LocalAnalysisMaterializer({"profile": AnalysisProfile(48, "veryfast", 23)}, temp_root=work)
    with RecordingService(analysis_materializer=engine) as service:
        registered = [service.register_local_source(p) for p in paths]
        assert all(r.source_asset.duration_sec == .033333 for r in registered)
        assert all(len(engine._frames(engine._probe(p, 0))[1]) == 2 for p in paths)
        rows = [dict(source_asset_ref=r.source_asset.source_asset_ref,
            media_stream_ref=r.media_streams[0].media_stream_ref,
            timeline_start_sec=float(Decimal(".033333") * i),
            timeline_end_sec=float(Decimal(".033333") * (i + 1))) for i, r in enumerate(registered)]
        timeline = service.create_relative_timeline_from_placements(rows)
        resolution = service.resolve_span(dict(timeline_id=timeline.timeline_id, revision=timeline.revision),
            dict(start_sec=0., end_sec=.233331), media_stream_refs=[r["media_stream_ref"] for r in rows])
        with pytest.raises(RecordingCapabilityError) as caught:
            service.prepare_analysis_source_from_resolution(resolution, "profile")
        assert caught.value.code == "UNSUPPORTED_MEDIA"
        assert not service._local_analysis
    assert [fingerprint(p) for p in paths] == before
    assert not list(work.iterdir())
