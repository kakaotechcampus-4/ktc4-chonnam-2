"""등록 사실 → 단일 원본 상대 Timeline 생성·저장·조회 검증."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from daesingo.recording import (
    MediaStream, RecordingCapabilityError, RecordingService, RecordingTimeline, SourceAsset,
)
from daesingo.recording.repository import InMemoryRecordingRepository


def registered_metadata(duration=60.033333):
    """경계 조건용 metadata. 실제 ffprobe 검증은 아래 media smoke에서 수행한다."""
    repo = InMemoryRecordingRepository()
    source = SourceAsset(
        contract="SourceAsset", contract_version="source-asset-media-stream/v1",
        source_asset_ref="source-test", asset_kind="SOURCE_ASSET", external_source_ref=None,
        media_stream_refs=["video-a", "audio", "video-b"], byte_size=100,
        availability="AVAILABLE", duration_sec=duration,
    )
    repo.add_source_asset(source)
    for ref, media_type, duration in [("video-a", "VIDEO", 60.033333), ("audio", "AUDIO", None),
                                      ("video-b", "VIDEO", 59.9)]:
        repo.add_media_stream(MediaStream(
            contract="MediaStream", contract_version="source-asset-media-stream/v1",
            media_stream_ref=ref, source_asset_ref=source.source_asset_ref,
            media_type=media_type, role="UNKNOWN" if media_type == "VIDEO" else None,
            availability="UNKNOWN", duration_sec=duration,
        ))
    return RecordingService(repo), repo, source


def test_relative_timeline_preserves_source_and_stream_facts():
    service, repo, source = registered_metadata()
    streams_before = [repo.get_media_stream(ref).model_dump() for ref in source.media_stream_refs]
    timeline = service.create_relative_timeline(source.source_asset_ref)
    assert timeline.contract_version == "recording-timeline/v1"
    assert timeline.revision == 1
    assert timeline.produced_by == "recording"
    assert timeline.timeline_status == "USABLE_RELATIVE_ONLY"
    assert timeline.time_basis.mode == "ABSOLUTE_AND_RELATIVE"
    assert timeline.time_basis.working_anchor.model_dump() == {
        "value": None, "source_candidate_ref": None, "status": "UNKNOWN",
    }
    assert timeline.time_source_candidates == []
    assert timeline.gaps == []
    assert [p.model_dump() for p in timeline.source_placements] == [{
        "source_asset_ref": source.source_asset_ref, "timeline_start_sec": 0.0,
        "timeline_end_sec": 60.033333, "media_stream_refs": ["video-a", "audio", "video-b"],
    }]
    assert RecordingTimeline.model_validate_json(timeline.model_dump_json()) == timeline
    assert service.get_timeline(timeline.timeline_id, 1) == timeline
    assert service.get_latest_timeline(timeline.timeline_id) == timeline
    assert [repo.get_media_stream(ref).model_dump() for ref in source.media_stream_refs] == streams_before


@pytest.mark.parametrize("duration", [None, 0.0, float("inf"), float("nan")])
def test_unknown_or_invalid_duration_does_not_create_timeline(duration):
    service, repo, source = registered_metadata()
    # NaN은 정상 계약 파싱에서도 거부된다. 내부 adapter가 validation을 우회한
    # 손상 snapshot을 넣더라도 새 Timeline을 발행하지 않는지 검사한다.
    repo.add_source_asset(source.model_copy(update={"duration_sec": duration}))
    with pytest.raises(ValueError, match="duration"):
        service.create_relative_timeline(source.source_asset_ref)
    assert repo._timelines == {}


def test_unknown_source_ref_is_not_a_path_or_fixture_fallback():
    service = RecordingService()
    with pytest.raises(RecordingCapabilityError) as caught:
        service.create_relative_timeline("private-path.AVI")
    assert caught.value.code == "UNKNOWN_REF"
    assert "private-path" not in str(caught.value)


@pytest.mark.parametrize("case", ["no_streams", "missing_stream", "wrong_parent", "duplicate",
                                  "audio_only", "source_unknown", "source_unavailable", "stream_unavailable"])
def test_unsupported_source_or_broken_refs_do_not_publish(case):
    service, repo, source = registered_metadata()
    if case == "no_streams":
        repo.add_source_asset(source.model_copy(update={"media_stream_refs": []}))
    elif case == "missing_stream":
        repo.add_source_asset(source.model_copy(update={"media_stream_refs": ["absent"]}))
    elif case == "duplicate":
        repo.add_source_asset(source.model_copy(update={"media_stream_refs": ["video-a", "video-a"]}))
    elif case == "audio_only":
        repo.add_source_asset(source.model_copy(update={"media_stream_refs": ["audio"]}))
    elif case.startswith("source_"):
        availability = "UNKNOWN" if case == "source_unknown" else "UNAVAILABLE"
        repo.add_source_asset(source.model_copy(update={"availability": availability}))
    else:
        stream = repo.get_media_stream("video-a")
        update = {"source_asset_ref": "another-source"} if case == "wrong_parent" else {"availability": "UNAVAILABLE"}
        repo.add_media_stream(stream.model_copy(update=update))
    with pytest.raises(ValueError):
        service.create_relative_timeline(source.source_asset_ref)
    assert not repo._timelines


def test_repeated_creation_is_not_implicit_rebase():
    service, _, source = registered_metadata()
    first = service.create_relative_timeline(source.source_asset_ref)
    second = service.create_relative_timeline(source.source_asset_ref)
    assert first.timeline_id != second.timeline_id
    assert first.revision == second.revision == 1
    assert service.get_timeline(first.timeline_id, 1) == first
    assert service.get_timeline(second.timeline_id, 1) == second


def test_nested_mutation_cannot_change_stored_revision():
    service, repo, source = registered_metadata()
    timeline = service.create_relative_timeline(source.source_asset_ref)
    expected = timeline.model_dump(mode="json")
    timeline.source_placements[0].media_stream_refs.clear()
    timeline.time_source_candidates.append("not-observed")
    stored = service.get_timeline(timeline.timeline_id, 1)
    assert stored.model_dump(mode="json") == expected
    stored.source_placements.clear()
    latest = service.get_latest_timeline(timeline.timeline_id)
    assert latest.model_dump(mode="json") == expected
    latest.source_placements.clear()
    assert service.get_timeline(timeline.timeline_id, 1).model_dump(mode="json") == expected
    # 기존 revision 덮어쓰기 금지와 새 revision 보존도 유지된다.
    with pytest.raises(ValueError, match="덮어쓸"):
        repo.add_timeline(timeline)
    second = service.get_timeline(timeline.timeline_id, 1).model_copy(update={"revision": 2})
    repo.add_timeline(second)
    assert service.get_latest_timeline(timeline.timeline_id).revision == 2
    assert service.get_timeline(timeline.timeline_id, 1).model_dump(mode="json") == expected


def fingerprint(path):
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    info = path.stat()
    return digest, info.st_size, info.st_mtime_ns


def test_generated_media_public_example(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("media smoke에 ffmpeg/ffprobe가 필요합니다")
    path = tmp_path / "상대 시간축 영상.mkv"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
                    "color=c=blue:s=64x48:r=10:d=1", "-c:v", "ffv1", str(path)],
                   check=True, capture_output=True, timeout=30)
    before = fingerprint(path)
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONPATH=str(root / "src"), PYTHONIOENCODING="utf-8")
    run = subprocess.run([sys.executable, "-m", "examples.recording_relative_timeline", str(path)],
                         cwd=root, env=env, capture_output=True, timeout=30, check=True)
    payload = json.loads(run.stdout)
    source = SourceAsset.model_validate(payload["source_asset"])
    timeline = RecordingTimeline.model_validate(payload["recording_timeline"])
    assert timeline.source_placements[0].timeline_end_sec == source.duration_sec == 1.0
    assert timeline.source_placements[0].source_asset_ref == source.source_asset_ref
    assert timeline.timeline_status == "USABLE_RELATIVE_ONLY"
    assert timeline.time_basis.working_anchor.value is None
    assert str(path) not in run.stdout.decode("utf-8")
    assert path.name not in run.stdout.decode("utf-8")
    assert not run.stderr
    assert fingerprint(path) == before


def test_opt_in_real_source_relative_timeline():
    configured = os.environ.get("DAESINGO_RECORDING_VIDEO")
    if not configured:
        pytest.skip("DAESINGO_RECORDING_VIDEO 미지정")
    path = Path(configured)
    before = fingerprint(path)
    service = RecordingService()
    registered = service.register_local_source(path)
    timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
    assert timeline.source_placements[0].timeline_end_sec == registered.source_asset.duration_sec
    assert timeline.source_placements[0].media_stream_refs == registered.source_asset.media_stream_refs
    assert timeline.source_placements[0].source_asset_ref == registered.source_asset.source_asset_ref
    assert timeline.source_placements[0].timeline_start_sec == 0.0
    assert timeline.timeline_status == "USABLE_RELATIVE_ONLY"
    assert timeline.time_basis.working_anchor.value is None
    assert timeline.time_source_candidates == []
    assert service.get_timeline(timeline.timeline_id, 1) == timeline
    assert service.get_latest_timeline(timeline.timeline_id) == timeline
    assert fingerprint(path) == before
