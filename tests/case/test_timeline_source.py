"""타임라인 port 임시 구현 — 등록 순서대로 이어 붙인다(`decisions/start-analysis.md` §3-1)."""

import hashlib

import pytest

from daesingo.case.timeline_source import CaseTimeline, RecordingSequentialTimelineSource, TimelineUnavailable
from daesingo.recording import RecordingService
from daesingo.recording.probe import LocalSource, ProbedStream


def _service(video_streams: int = 1, duration: float = 10.0, durations: list[float] | None = None) -> RecordingService:
    """`durations`를 주면 등록 순서대로 원본 길이를 그 값으로 한다."""
    remaining = list(durations or [])
    by_path: dict = {}

    class Probe:
        def probe(self, path):
            if path not in by_path:
                by_path[path] = remaining.pop(0) if remaining else duration
            length = by_path[path]
            stat = path.stat()
            streams = tuple(ProbedStream(i, "VIDEO", length) for i in range(video_streams))
            streams += (ProbedStream(video_streams, "AUDIO", None),)
            return LocalSource(path, stat.st_size, stat.st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest(),
                               length, streams)

    return RecordingService(media_probe=Probe())


def _register(service: RecordingService, tmp_path, name: str) -> dict:
    path = tmp_path / name
    path.write_bytes(name.encode())
    registered = service.register_local_source(path)
    videos = [s.media_stream_ref for s in registered.media_streams if s.media_type == "VIDEO"]
    return {
        "source_asset_ref": registered.source_asset.source_asset_ref,
        "video_stream_ref": videos[0] if len(videos) == 1 else None,
        "duration_sec": registered.source_asset.duration_sec,
    }


def test_single_source_uses_relative_timeline(tmp_path):
    service = _service()
    source = _register(service, tmp_path, "a.mp4")
    timeline = RecordingSequentialTimelineSource(service).timeline_for([source])
    assert isinstance(timeline, CaseTimeline)
    assert timeline.revision == 1
    assert timeline.duration_ms == 10_000
    placements = service.get_timeline(timeline.timeline_id, timeline.revision).source_placements
    assert [p.source_asset_ref for p in placements] == [source["source_asset_ref"]]


def test_two_sources_are_placed_back_to_back_in_registration_order(tmp_path):
    service = _service()
    first = _register(service, tmp_path, "b.mp4")
    second = _register(service, tmp_path, "a.mp4")
    timeline = RecordingSequentialTimelineSource(service).timeline_for([first, second])
    assert timeline.duration_ms == 20_000
    placements = service.get_timeline(timeline.timeline_id, timeline.revision).source_placements
    assert [(p.source_asset_ref, p.timeline_start_sec, p.timeline_end_sec) for p in placements] == [
        (first["source_asset_ref"], 0.0, 10.0),
        (second["source_asset_ref"], 10.0, 20.0),
    ]


def test_no_sources_is_unavailable():
    with pytest.raises(TimelineUnavailable):
        RecordingSequentialTimelineSource(_service()).timeline_for([])


def test_multiple_sources_need_a_video_stream_each(tmp_path):
    service = _service(video_streams=2)
    sources = [_register(service, tmp_path, "a.avi"), _register(service, tmp_path, "b.avi")]
    with pytest.raises(TimelineUnavailable):
        RecordingSequentialTimelineSource(service).timeline_for(sources)


def test_multiple_sources_need_known_duration(tmp_path):
    service = _service()
    sources = [_register(service, tmp_path, "a.mp4"), _register(service, tmp_path, "b.mp4")]
    sources[1] = dict(sources[1], duration_sec=None)
    with pytest.raises(TimelineUnavailable):
        RecordingSequentialTimelineSource(service).timeline_for(sources)


def test_single_source_with_two_video_streams_is_unavailable(tmp_path):
    # 전방 · 후방이 한 파일(VIDEO 2개)이면 영상이 1개여도 고를 기준이 없다 — 발주 전에 막는다(spec §3-1 한계 4).
    service = _service(video_streams=2)
    with pytest.raises(TimelineUnavailable):
        RecordingSequentialTimelineSource(service).timeline_for([_register(service, tmp_path, "front_rear.avi")])


# ── 좌표 정밀도 (#421 · #422) ──────────────────────────────────────────────────


def _first_search_resolution(service: RecordingService, timeline: CaseTimeline, sources: list[dict]):
    """첫 탐색 범위(`0` ~ `duration_ms`)를 Worker와 같은 방식(ms → 초)으로 Recording에 해소한다."""
    return service.resolve_span(
        {"timeline_id": timeline.timeline_id, "revision": timeline.revision},
        {"start_sec": 0.0, "end_sec": timeline.duration_ms / 1000},
        media_stream_refs=[s["video_stream_ref"] for s in sources],
    )


def test_accumulated_placements_are_not_rejected_by_representation_error(tmp_path):
    """#421 — float 누적이면 4번째 placement가 원본보다 5e-15초 길어 Recording이 거부했다."""
    durations = [20.025323, 20.036430, 20.043529, 20.025323]
    service = _service(durations=durations)
    sources = [_register(service, tmp_path, f"{i}.avi") for i in range(len(durations))]

    timeline = RecordingSequentialTimelineSource(service).timeline_for(sources)

    placements = service.get_timeline(timeline.timeline_id, timeline.revision).source_placements
    assert [p.timeline_start_sec for p in placements[1:]] == [p.timeline_end_sec for p in placements[:-1]]
    assert placements[-1].timeline_end_sec == 80.130605


def test_placement_longer_than_the_source_is_still_rejected(tmp_path):
    """실제 길이 초과는 Recording이 계속 거부한다 — 표현 오차만 없앴다."""
    service = _service(durations=[10.0, 10.0])
    sources = [_register(service, tmp_path, "a.avi"), _register(service, tmp_path, "b.avi")]
    sources[1] = dict(sources[1], duration_sec=10.000001)
    with pytest.raises(ValueError, match="원본 길이"):
        RecordingSequentialTimelineSource(service).timeline_for(sources)


@pytest.mark.parametrize(
    ("duration", "expected_ms"),
    [(17.427524, 17_427), (20.024656, 20_024), (20.025323, 20_025), (20.025, 20_025), (10.0, 10_000)],
)
def test_duration_ms_is_floored_so_first_search_stays_inside(tmp_path, duration, expected_ms):
    """#422 — 반올림하면 17.427524초가 17428ms가 돼 첫 탐색 끝점이 원본 끝을 넘었다."""
    service = _service(duration=duration)
    source = _register(service, tmp_path, "a.avi")

    timeline = RecordingSequentialTimelineSource(service).timeline_for([source])

    assert timeline.duration_ms == expected_ms
    assert _first_search_resolution(service, timeline, [source]).status == "COMPLETE"


def test_two_source_total_is_floored_too(tmp_path):
    """#422 — 2개 합 40.050646초도 반올림이면 40051ms로 넘었다."""
    service = _service(durations=[20.025323, 20.025323])
    sources = [_register(service, tmp_path, "a.avi"), _register(service, tmp_path, "b.avi")]

    timeline = RecordingSequentialTimelineSource(service).timeline_for(sources)

    assert timeline.duration_ms == 40_050
    assert _first_search_resolution(service, timeline, sources).status == "COMPLETE"


def test_source_shorter_than_one_ms_is_unavailable(tmp_path):
    """내린 길이가 0ms면 첫 탐색 범위를 만들 수 없다 — 길이 0인 `COARSE_SEARCH`를 내지 않는다."""
    service = _service(duration=0.0004)
    with pytest.raises(TimelineUnavailable):
        RecordingSequentialTimelineSource(service).timeline_for([_register(service, tmp_path, "a.avi")])
