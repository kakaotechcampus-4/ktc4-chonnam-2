"""단일 원본 구간 계산의 계약/좌표 검증과 opt-in 실제 AVI 검증."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from daesingo.recording import RecordingService, SpanResolution
from daesingo.recording.models import TimeRange
from daesingo.recording.probe import LocalSource, ProbedStream
from daesingo.recording.repository import InMemoryRecordingRepository
from daesingo.recording.errors import RecordingCapabilityError


def fingerprint(path):
    with path.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, digest


@pytest.fixture
def setup_source(tmp_path):
    def setup(durations=(10.0,), offset=0.0, gaps=()):
        path = tmp_path / "unit-adapter-input"
        path.write_bytes(b"synthetic unit input, not actual video")
        size, mtime, digest = fingerprint(path)
        class UnitProbe:
            def probe(self, ignored):
                return LocalSource(path, size, mtime, digest, 10.0,
                    tuple(ProbedStream(i, "VIDEO", duration) for i, duration in enumerate(durations)))
        repo = InMemoryRecordingRepository()
        service = RecordingService(repo, media_probe=UnitProbe())
        registered = service.register_local_source(path)
        timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
        if offset or gaps:
            p = timeline.source_placements[0].model_copy(update={
                "timeline_start_sec": offset, "timeline_end_sec": offset + 10.0})
            timeline = timeline.model_copy(update={"revision": 2, "source_placements": [p],
                "gaps": [TimeRange(start_sec=a, end_sec=b) for a, b in gaps]})
            repo.add_timeline(timeline)
        return service, repo, registered, timeline, path
    return setup


def resolve(service, timeline, start, end, *, selected_index=0):
    # 테스트가 지정한 ref를 공개 capability로 전달한다. 내부 계산을 직접 호출하지 않는다.
    result = service.resolve_span(
        {"timeline_id": timeline.timeline_id, "revision": timeline.revision},
        {"start_sec": start, "end_sec": end},
        media_stream_ref=timeline.source_placements[0].media_stream_refs[selected_index])
    assert SpanResolution.model_validate_json(result.model_dump_json()) == result
    assert [s.sequence for s in result.spans] == list(range(len(result.spans)))
    return result


def test_complete_and_revision_local_coordinates(setup_source):
    service, repo, registered, timeline, path = setup_source(offset=20.25)
    result = resolve(service, timeline, 21.35, 23.45)
    assert result.status == "COMPLETE" and result.failure is None and not result.missing_ranges
    assert result.timeline_ref.revision == 2
    assert result.spans[0].source_range == TimeRange(start_sec=1.1, end_sec=3.2)
    assert result.spans[0].source_asset_ref == registered.source_asset.source_asset_ref
    assert path.name not in result.model_dump_json()
    earlier = service.get_timeline(timeline.timeline_id, 1)
    assert resolve(service, earlier, 1.1, 3.2).timeline_ref.revision == 1
    # 반환 객체를 변경해도 다음 결과와 과거 revision을 오염시키지 않는다.
    result.spans.clear()
    assert resolve(service, timeline, 21.35, 23.45).status == "COMPLETE"


@pytest.mark.parametrize("start,end,status", [(0.0,25.0,"PARTIAL"), (25.0,40.0,"PARTIAL"),
    (0.0,40.0,"PARTIAL"), (0.0,20.0,"FAILED"), (30.0,40.0,"FAILED")])
def test_outside_boundaries(setup_source, start, end, status):
    service, _, _, timeline, _ = setup_source(offset=20.0)
    result = resolve(service, timeline, start, end)
    assert result.status == status
    assert all(m.reason == "OUT_OF_TIMELINE_RANGE" and m.source_ref is None for m in result.missing_ranges)
    assert (result.failure is not None) == (status == "FAILED")


def test_gaps_and_all_gap_failure(setup_source):
    service, _, _, timeline, _ = setup_source(gaps=((2.0,4.0),(3.0,5.0)))
    with pytest.raises(RecordingCapabilityError) as caught:
        resolve(service, timeline, 1.0, 6.0)
    assert caught.value.code == "TEMPORARY_FAILURE"  # gap으로 두 span이면 첫 항목을 고르지 않는다.
    result = resolve(service, timeline, 1.0, 5.0)
    assert result.status == "PARTIAL"
    assert all(m.reason == "TIMELINE_GAP" and m.source_ref is None for m in result.missing_ranges)
    assert resolve(service, timeline, 2.0, 5.0).status == "FAILED"


def test_stream_bounds_unknown_duration_and_unknown_availability(setup_source):
    service, repo, registered, timeline, _ = setup_source((10.0,6.0,None))
    result = resolve(service, timeline, 5.0, 8.0)
    assert result.status == "COMPLETE" and result.failure is None
    refs = [s.media_stream_ref for s in registered.media_streams]
    assert {s.media_stream_ref for s in result.spans} == {refs[0]}
    assert result.missing_ranges == []
    result = resolve(service, timeline, 5.0, 8.0, selected_index=1)
    assert result.status == "PARTIAL"
    assert max(s.source_range.end_sec for s in result.spans) == 6.0
    assert {m.source_ref.ref for m in result.missing_ranges} == {refs[1]}
    assert all(m.reason == "STREAM_UNAVAILABLE" and m.source_ref.kind == "media_stream"
               for m in result.missing_ranges)
    assert all(repo.get_media_stream(ref).availability == "UNKNOWN" for ref in refs)


@pytest.mark.parametrize("mode", ["unknown_duration", "unavailable", "missing_index"])
def test_all_streams_unresolvable(setup_source, mode):
    service, repo, registered, timeline, _ = setup_source((None,) if mode == "unknown_duration" else (10.0,))
    stream = registered.media_streams[0]
    if mode == "unavailable":
        repo.add_media_stream(stream.model_copy(update={"availability": "UNAVAILABLE"}))
    elif mode == "missing_index":
        del repo._media_streams[stream.media_stream_ref]
        with pytest.raises(ValueError):
            resolve(service, timeline, 1.0, 2.0)
        return
    result = resolve(service, timeline, 1.0, 2.0)
    assert result.status == "FAILED"
    if mode == "unavailable":
        assert result.failure.code == "NO_USABLE_SPAN"
        assert result.missing_ranges[0].source_ref.ref == stream.media_stream_ref
    else:
        assert result.failure.code == ("STREAM_COVERAGE_UNKNOWN" if mode == "unknown_duration"
                                       else "TIMELINE_METADATA_INVALID")
        assert result.missing_ranges == []


@pytest.mark.parametrize("mode", ["missing", "changed", "unavailable"])
def test_source_unavailable_and_no_stale_resolution(setup_source, mode):
    service, repo, registered, timeline, path = setup_source()
    assert resolve(service, timeline, 1.0, 2.0).status == "COMPLETE"
    if mode == "missing":
        path.unlink()  # tmp_path 안의 unit 입력만 삭제한다.
    elif mode == "changed":
        path.write_bytes(b"changed")
    else:
        repo.add_source_asset(registered.source_asset.model_copy(update={"availability": "UNAVAILABLE"}))
    result = resolve(service, timeline, 1.0, 2.0)
    assert result.status == "FAILED"
    missing = result.missing_ranges[0]
    assert missing.reason == "SOURCE_UNAVAILABLE"
    assert missing.source_ref.kind == "source_asset" and missing.source_ref.ref == registered.source_asset.source_asset_ref


def test_inspection_failure_has_no_invented_missing_range(setup_source, monkeypatch):
    service, _, _, timeline, _ = setup_source()
    def fail(*args):
        raise RecordingCapabilityError("TEMPORARY_FAILURE", "private input")
    monkeypatch.setattr("daesingo.recording.spans.inspect_local_source", fail)
    result = resolve(service, timeline, 1.0, 2.0)
    assert result.status == "FAILED" and result.missing_ranges == []
    assert result.failure.code == "SOURCE_INSPECTION_FAILED"
    assert "private input" not in result.model_dump_json()
    assert resolve(service, timeline, 10.0, 12.0).missing_ranges[0].reason == "OUT_OF_TIMELINE_RANGE"


@pytest.mark.parametrize("start,end", [(-1.0,1.0),(1.0,1.0),(2.0,1.0),(0.0,float("inf")),(float("nan"),1.0)])
def test_input_errors_do_not_create_failed_contract(setup_source, start, end):
    service, _, _, timeline, _ = setup_source()
    with pytest.raises(ValueError):
        resolve(service, timeline, start, end)
    with pytest.raises(ValueError):
        service.resolve_span({"timeline_id": timeline.timeline_id, "revision": 99},
                             {"start_sec": 0.0, "end_sec": 1.0})


def test_unsupported_multiple_placements_and_invalid_parent(setup_source):
    service, repo, registered, timeline, _ = setup_source()
    multiple = timeline.model_copy(update={"revision": 2, "source_placements": timeline.source_placements * 2})
    repo.add_timeline(multiple)
    with pytest.raises(ValueError):
        resolve(service, multiple, 0.0, 1.0)
    stream = registered.media_streams[0]
    repo.add_media_stream(stream.model_copy(update={"source_asset_ref": "wrong-parent"}))
    with pytest.raises(ValueError):
        resolve(service, timeline, 0.0, 1.0)


def test_opt_in_real_avi():
    configured = os.environ.get("DAESINGO_RECORDING_VIDEO")
    if not configured:
        pytest.skip("DAESINGO_RECORDING_VIDEO 미지정")
    path = Path(configured)
    before = fingerprint(path)
    service = RecordingService()
    registered = service.register_local_source(path)
    timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
    duration = registered.source_asset.duration_sec
    videos = [s for s in registered.media_streams if s.media_type == "VIDEO"]
    for stream in videos:
        index = timeline.source_placements[0].media_stream_refs.index(stream.media_stream_ref)
        selected = resolve(service, timeline, 1.0, 2.0, selected_index=index)
        assert selected.status == "COMPLETE" and selected.missing_ranges == []
        assert len(selected.spans) == 1
        assert {s.media_stream_ref for s in selected.spans} == {stream.media_stream_ref}
        tail = resolve(service, timeline, duration - 1.0, duration + 1.0, selected_index=index)
        assert tail.status == "PARTIAL"
        assert any(m.reason == "OUT_OF_TIMELINE_RANGE" and m.source_ref is None for m in tail.missing_ranges)
        assert all(s.source_range.end_sec <= stream.duration_sec for s in tail.spans)
    assert resolve(service, timeline, duration, duration + 1.0).status == "FAILED"
    assert fingerprint(path) == before


def test_generated_avi_public_example(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("media smoke에는 ffmpeg/ffprobe가 필요합니다")
    path = tmp_path / "실제 생성 영상.avi"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
        "color=c=blue:s=64x48:r=10:d=1", "-c:v", "mpeg4", str(path)],
        check=True, capture_output=True, timeout=30)
    before = fingerprint(path)
    root = Path(__file__).resolve().parents[2]
    for start, end in [(0.1,0.5),(0.5,1.5),(1.0,2.0)]:
        output = subprocess.run([sys.executable, "-m", "examples.recording_resolve_span", str(path),
            "--start", str(start), "--end", str(end), "--video-index", "0"], cwd=root,
            env=dict(os.environ, PYTHONPATH=str(root / "src"), PYTHONIOENCODING="utf-8"),
            check=True, capture_output=True, timeout=30)
        result = SpanResolution.model_validate_json(output.stdout)
        assert result.status == ("COMPLETE" if end <= 1.0 else "PARTIAL" if start < 1.0 else "FAILED")
        assert path.name not in output.stdout.decode("utf-8") and not output.stderr
    assert fingerprint(path) == before


@pytest.mark.parametrize("durations", [(10.0,), (10.0,None), (10.0,10.0,None)])
def test_public_api_never_invents_default_selection(setup_source, durations):
    service, _, _, timeline, _ = setup_source(durations)
    with pytest.raises(ValueError, match="명시적인"):
        service.resolve_span({"timeline_id": timeline.timeline_id, "revision": timeline.revision},
                             {"start_sec": 1.0, "end_sec": 2.0})


def test_happy_fixture_placement_is_not_required_stream_set():
    from daesingo.recording import load_recording_fixture
    fixture = load_recording_fixture("scenario_happy_001")
    service = RecordingService.from_fixture(fixture)
    result = service.resolve_span({"timeline_id": "tl_h001", "revision": 1},
                                  {"start_sec": 300.0, "end_sec": 420.0})
    placement = service.get_timeline("tl_h001", 1).source_placements[0]
    assert "ms_h001_front_a" in placement.media_stream_refs
    assert [s.media_stream_ref for s in result.spans] == ["ms_h001_front_v"]
    assert result.status == "COMPLETE" and result.missing_ranges == []
    explicit = service.resolve_span({"timeline_id": "tl_h001", "revision": 1},
        {"start_sec": 300.0, "end_sec": 420.0}, media_stream_ref="ms_h001_front_v")
    assert explicit == result
    with pytest.raises(RecordingCapabilityError):
        service.resolve_span({"timeline_id": "tl_h001", "revision": 1},
            {"start_sec": 300.0, "end_sec": 420.0}, media_stream_ref="ms_h001_rear_v")


@pytest.mark.parametrize("mode", ["audio", "unknown", "empty", "wrong_revision", "duplicate", "other_source"])
def test_selected_ref_is_input_validation_not_domain_failure(setup_source, mode):
    service, repo, registered, timeline, _ = setup_source((10.0, None))
    video, audio = registered.media_streams
    repo.add_media_stream(audio.model_copy(update={"media_type": "AUDIO", "role": None}))
    ref = video.media_stream_ref
    if mode == "audio":
        ref = audio.media_stream_ref
    elif mode == "unknown":
        ref = "ms_front_looks_valid_but_unknown"
    elif mode == "empty":
        ref = ""
    elif mode == "other_source":
        repo.add_media_stream(video.model_copy(update={"source_asset_ref": "other-source"}))
    else:
        refs = [audio.media_stream_ref] if mode == "wrong_revision" else [ref, ref, audio.media_stream_ref]
        placement = timeline.source_placements[0].model_copy(update={"media_stream_refs": refs})
        timeline = timeline.model_copy(update={"revision": 2, "source_placements": [placement]})
        repo.add_timeline(timeline)
    with pytest.raises(ValueError):
        service.resolve_span({"timeline_id": timeline.timeline_id, "revision": timeline.revision},
            {"start_sec": 1.0, "end_sec": 2.0}, media_stream_ref=ref)


def test_unselected_audio_and_video_do_not_change_result(setup_source):
    service, repo, registered, timeline, _ = setup_source((None, 10.0, None))
    repo.add_media_stream(registered.media_streams[0].model_copy(update={"media_type": "AUDIO", "role": None}))
    repo.add_media_stream(registered.media_streams[2].model_copy(update={"availability": "UNAVAILABLE"}))
    result = resolve(service, timeline, 1.0, 2.0, selected_index=1)
    assert result.status == "COMPLETE" and result.missing_ranges == []
    assert len(result.spans) == 1
    assert result.spans[0].media_stream_ref == registered.media_streams[1].media_stream_ref
