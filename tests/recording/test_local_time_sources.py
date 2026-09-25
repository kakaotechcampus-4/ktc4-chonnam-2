"""원본 시각 관찰, 명시적 offset, 수동 anchor revision 경계 검증."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from daesingo.recording import (LocalTimeSourceObserver, RecordingCapabilityError, RecordingService,
                               TimeSourceCandidate, TimeSourceCheck)


def fingerprint(path):
    with path.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
    info = path.stat()
    return info.st_size, info.st_mtime_ns, digest


@pytest.fixture
def make_media(tmp_path):
    def make(name="20260620_141956_EVT_1.avi", creation=None):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            pytest.skip("ffmpeg/ffprobe 필요")
        path = tmp_path / name
        args = ["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
                "color=c=blue:s=64x48:r=10:d=1", "-c:v", "mpeg4"]
        if creation is not None:
            args += ["-metadata", f"creation_time={creation}"]
        subprocess.run([*args, str(path)], check=True, capture_output=True, timeout=30)
        return path
    return make


def setup(path, offset="+09:00", century=None):
    service = RecordingService(time_source_observer=LocalTimeSourceObserver(filename_offset=offset, mdr_century=century))
    source = service.register_local_source(path).source_asset
    timeline = service.create_relative_timeline(source.source_asset_ref)
    return service, source, timeline


def statuses(observed):
    return {check.source_kind: check.status for check in observed.checks}


@pytest.mark.parametrize("offset", ["+09:00", "+00:00", "-04:30"])
def test_filename_explicit_offset_lookup_and_no_path(make_media, offset):
    path = make_media()
    before = fingerprint(path)
    service, source, timeline = setup(path, offset)
    with pytest.raises(RecordingCapabilityError):
        service.get_time_sources(source.source_asset_ref)
    observed = service.observe_time_sources(source.source_asset_ref)
    assert statuses(observed) == {"FILENAME": "FOUND", "FILE_METADATA": "NOT_FOUND", "VENDOR_METADATA": "UNSUPPORTED"}
    candidate, = observed.candidates
    assert candidate.value.isoformat() == f"2026-06-20T14:19:56{offset}"
    assert candidate.applies_to.model_dump() == {"source_asset_ref": source.source_asset_ref, "source_offset_sec": 0.0}
    assert re.fullmatch(r"tsc_[0-9a-f]{32}", candidate.candidate_id)
    assert candidate.provenance.observed_from == path.name
    assert candidate.producer_checks.model_dump() == {"parse_valid": True}
    assert "evt" in candidate.source_detail
    payload = candidate.model_dump_json()
    assert str(path.parent) not in payload
    assert not any(term in payload for term in ["confidence", "VERIFIED", "AGREED", "CONFLICT", "VIDEO_OVERLAY_OCR"])
    assert TimeSourceCandidate.model_validate_json(payload) == candidate
    for check in observed.checks:
        assert TimeSourceCheck.model_validate_json(check.model_dump_json()) == check
    assert service.get_time_source_candidate(candidate.candidate_id) == candidate
    assert service.get_time_sources(source.source_asset_ref) == observed
    assert service.observe_time_sources(source.source_asset_ref) == observed
    assert service.get_timeline(timeline.timeline_id, 1) == timeline  # 관찰만으로 rebase하지 않는다.
    assert fingerprint(path) == before


@pytest.mark.parametrize("name,offset,century,status,year", [
    ("unsupported.avi", "+09:00", None, "UNSUPPORTED", None),
    ("20260230_141956_EVT_1.avi", "+09:00", None, "PARSE_ERROR", None),
    ("20260620_251956_EVT_1.avi", "+09:00", None, "PARSE_ERROR", None),
    ("20260620_141956_EVT_1.avi", None, None, "UNSUPPORTED", None),
    ("MDR_260829_125711.AVI", "+09:00", None, "UNSUPPORTED", None),
    ("MDR_260829_125711.AVI", "+09:00", 2000, "FOUND", 2026),
    ("MDR_260829_125711.AVI", "+09:00", 1900, "FOUND", 1926),
    ("MDR_260230_125711.AVI", "+09:00", 2000, "PARSE_ERROR", None),
    ("260829_125711_EVT_1.avi", "+09:00", 2000, "UNSUPPORTED", None),
])
def test_explicit_filename_rules(make_media, name, offset, century, status, year):
    service, source, _ = setup(make_media(name), offset, century)
    observed = service.observe_time_sources(source.source_asset_ref)
    assert statuses(observed)["FILENAME"] == status
    if year is None:
        assert observed.candidates == ()
    else:
        assert observed.candidates[0].value.year == year
        assert "mdr" in observed.candidates[0].source_detail


@pytest.mark.parametrize("value,status", [("invalid", "PARSE_ERROR"),
    ("2026-06-20T14:19:56", "PARSE_ERROR"), (None, "PARSE_ERROR"),
    ("2026-06-20T14:19:56+09:99", "PARSE_ERROR"),
    ("2026-06-20T14:19:56Z", "FOUND")])
def test_metadata_parse_status_is_not_missing(make_media, monkeypatch, value, status):
    service, source, _ = setup(make_media("unknown.avi"))
    # metadata 파싱 오류용 도구 응답 double. 실제 field 추출은 별도 MP4 smoke로 검사한다.
    monkeypatch.setattr(service._time_source_observer, "_metadata", lambda _: {"format": {"tags": {"creation_time": value}}})
    observed = service.observe_time_sources(source.source_asset_ref)
    assert statuses(observed)["FILE_METADATA"] == status
    assert len(observed.candidates) == (1 if status == "FOUND" else 0)


def test_real_container_creation_time(make_media):
    path = make_media("container.mp4", "2026-06-20T14:19:56+09:00")
    before = fingerprint(path)
    service, source, _ = setup(path, offset=None)
    observed = service.observe_time_sources(source.source_asset_ref)
    assert statuses(observed)["FILENAME"] == "UNSUPPORTED"
    candidate, = observed.candidates
    assert candidate.source_kind == "FILE_METADATA"
    assert candidate.value.isoformat() == "2026-06-20T05:19:56+00:00"  # MP4 muxer가 UTC로 저장한다.
    assert candidate.provenance.observed_from == path.name
    assert fingerprint(path) == before


@pytest.mark.parametrize("matches,trusted", [(False,True),(None,True),(True,False)])
def test_untrusted_anchor_keeps_relative_only(make_media, matches, trusted):
    service, source, timeline = setup(make_media())
    candidate, = service.observe_time_sources(source.source_asset_ref).candidates
    result = service.apply_filename_anchor({"timeline_id": timeline.timeline_id, "revision": 1},
        candidate.candidate_id, overlay_matches=matches, trusted=trusted)
    assert result.applied is False and result.timeline == timeline
    assert result.overlay_matches == matches and result.trusted == trusted
    assert service.get_latest_timeline(timeline.timeline_id).revision == 1


def verify_anchor(path):
    before = fingerprint(path)
    service, source, timeline = setup(path)
    observed = service.observe_time_sources(source.source_asset_ref)
    candidate, = [c for c in observed.candidates if c.source_kind == "FILENAME"]
    assert candidate.value.isoformat() == "2026-06-20T14:19:56+09:00"
    result = service.apply_filename_anchor({"timeline_id": timeline.timeline_id, "revision": 1},
        candidate.candidate_id, overlay_matches=True, trusted=True)
    assert result.applied and result.timeline.revision == 2 and result.timeline.timeline_status == "USABLE"
    assert result.timeline.time_basis.working_anchor.value == candidate.value
    assert result.timeline.time_basis.working_anchor.source_candidate_ref == candidate.candidate_id
    assert result.timeline.source_placements == timeline.source_placements
    assert candidate.candidate_id in result.timeline.time_source_candidates
    assert service.get_timeline(timeline.timeline_id, 1) == timeline
    assert service.get_time_sources(source.source_asset_ref) == observed
    result.timeline.source_placements.clear()
    assert service.get_latest_timeline(timeline.timeline_id).source_placements
    assert fingerprint(path) == before
    return statuses(observed)


def test_trusted_anchor_new_revision_and_observations_immutable(make_media):
    verify_anchor(make_media())


def test_stale_anchor_revision_rejected_without_mutating_history(make_media):
    service, source, revision_one = setup(make_media())
    candidate, = service.observe_time_sources(source.source_asset_ref).candidates
    ref = {"timeline_id": revision_one.timeline_id, "revision": 1}
    result = service.apply_filename_anchor(ref, candidate.candidate_id, overlay_matches=True, trusted=True)
    revision_two = result.timeline.model_copy(deep=True)
    assert revision_two.revision == 2

    with pytest.raises(ValueError, match="stale timeline revision"):
        service.apply_filename_anchor(ref, candidate.candidate_id, overlay_matches=True, trusted=True)

    assert service.get_latest_timeline(revision_one.timeline_id) == revision_two
    assert service.get_timeline(revision_one.timeline_id, 1) == revision_one
    assert service.get_timeline(revision_one.timeline_id, 2) == revision_two
    with pytest.raises(ValueError, match="존재하지 않는 timeline reference"):
        service.get_timeline(revision_one.timeline_id, 3)


def test_parse_failure_no_fake_anchor_and_source_change_failure(make_media):
    path = make_media("20260230_141956_EVT_1.avi")
    service, source, timeline = setup(path)
    assert not service.observe_time_sources(source.source_asset_ref).candidates
    result = service.apply_filename_anchor({"timeline_id": timeline.timeline_id, "revision": 1},
                                          None, overlay_matches=True, trusted=True)
    assert not result.applied and result.timeline == timeline
    with path.open("ab") as file:
        file.write(b"changed")  # 자동 생성한 테스트 파일만 변경한다.
    with pytest.raises(RecordingCapabilityError) as caught:
        service.observe_time_sources(source.source_asset_ref)
    assert caught.value.code == "UNAVAILABLE"


def test_opt_in_real_time_sources():
    value = os.environ.get("DAESINGO_RECORDING_VIDEO")
    if not value:
        pytest.skip("DAESINGO_RECORDING_VIDEO 미지정")
    checks = verify_anchor(Path(value))
    assert checks == {"FILENAME": "FOUND", "FILE_METADATA": "NOT_FOUND", "VENDOR_METADATA": "UNSUPPORTED"}
    print(json.dumps({"configured_offset": "+09:00", "value": "2026-06-20T14:19:56+09:00", "checks": checks,
                      "manual_input_simulated": True, "new_revision": 2, "original_unchanged": True}))


def test_anchor_rejects_foreign_candidate_and_container_candidate(make_media):
    service, source, timeline = setup(make_media())
    ref = {"timeline_id": timeline.timeline_id, "revision": timeline.revision}
    other = service.register_local_source(make_media("20260621_141956_EVT_2.avi")).source_asset
    foreign, = service.observe_time_sources(other.source_asset_ref).candidates
    container = service.register_local_source(make_media("container.mp4", "2026-06-20T14:19:56Z")).source_asset
    metadata, = service.observe_time_sources(container.source_asset_ref).candidates
    for candidate in (foreign, metadata):
        with pytest.raises(ValueError):
            service.apply_filename_anchor(ref, candidate.candidate_id, overlay_matches=True, trusted=True)
    with pytest.raises(RecordingCapabilityError) as caught:
        service.apply_filename_anchor(ref, "unknown", overlay_matches=True, trusted=True)
    assert caught.value.code == "UNKNOWN_REF"
    assert service.get_latest_timeline(timeline.timeline_id) == timeline


def test_anchor_rejects_changed_original_without_path_leak(make_media):
    path = make_media()
    service, source, timeline = setup(path)
    candidate, = service.observe_time_sources(source.source_asset_ref).candidates
    path.unlink()  # 합성 테스트 원본만 제거한다.
    with pytest.raises(RecordingCapabilityError) as caught:
        service.apply_filename_anchor({"timeline_id": timeline.timeline_id, "revision": 1},
                                      candidate.candidate_id, overlay_matches=True, trusted=True)
    assert caught.value.code == "UNAVAILABLE"
    assert str(path) not in str(caught.value)
    assert service.get_latest_timeline(timeline.timeline_id) == timeline


def test_probe_failure_is_capability_error_without_path_leak(make_media):
    path = make_media()
    service = RecordingService(time_source_observer=LocalTimeSourceObserver(
        filename_offset="+09:00", ffprobe="missing-time-source-probe"))
    source = service.register_local_source(path).source_asset
    with pytest.raises(RecordingCapabilityError) as caught:
        service.observe_time_sources(source.source_asset_ref)
    assert caught.value.code == "TEMPORARY_FAILURE"
    assert str(path) not in str(caught.value)
    with pytest.raises(RecordingCapabilityError) as absent:
        service.get_time_sources(source.source_asset_ref)
    assert absent.value.code == "NOT_FOUND"
