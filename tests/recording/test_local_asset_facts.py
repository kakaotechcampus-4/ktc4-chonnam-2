"""실제 source lookup의 freshness, identity, 계약·원본 보존 검증."""

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from daesingo.recording import AssetFacts, RecordingCapabilityError, RecordingService


def fingerprint(path):
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, digest


@pytest.fixture
def media(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("실제 media smoke에는 ffmpeg/ffprobe가 필요합니다")
    path = tmp_path / "비공개 원본.mkv"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
        "color=c=blue:s=32x24:r=10:d=1", "-c:v", "ffv1", str(path)],
        check=True, capture_output=True, timeout=30)
    return path


def register(path):
    service = RecordingService()
    source = service.register_local_source(path).source_asset
    ref = {"kind": "source_asset", "ref": source.source_asset_ref}
    return service, source, ref


def verify_available(path):
    before = fingerprint(path)
    service, source, ref = register(path)
    begin = datetime.now(timezone.utc)
    facts = service.lookup_asset_facts(ref)
    assert begin <= facts.checked_at <= datetime.now(timezone.utc)
    assert facts.availability == "AVAILABLE"
    assert facts.byte_size == source.byte_size == before[0]
    assert facts.duration_sec == source.duration_sec
    assert facts.asset_ref.model_dump() == ref
    assert facts.asset_kind == "SOURCE_ASSET" and facts.derived_role is None
    assert facts.lineage == []
    assert facts.timeline_ref is facts.timeline_range is None
    assert AssetFacts.model_validate_json(facts.model_dump_json()) == facts
    assert path.name not in facts.model_dump_json()
    # 같은 source의 여러 Timeline 중 임의의 revision을 선택하지 않는다.
    service.create_relative_timeline(source.source_asset_ref)
    service.create_relative_timeline(source.source_asset_ref)
    again = service.lookup_asset_facts(ref)
    assert again.checked_at >= facts.checked_at
    assert again.timeline_ref is again.timeline_range is None
    assert fingerprint(path) == before


def test_real_generated_source_facts(media):
    verify_available(media)


@pytest.mark.parametrize("change", ["missing", "directory", "same_size", "mtime"])
def test_changed_source_is_unavailable_and_old_result_immutable(media, change):
    service, source, ref = register(media)
    original = service.lookup_asset_facts(ref)
    stat = media.stat()
    if change in {"missing", "directory"}:
        media.unlink()  # 자동 생성된 tmp_path의 파일만 삭제한다.
        if change == "directory":
            media.mkdir()
    elif change == "same_size":
        data = bytearray(media.read_bytes())
        data[-1] ^= 1
        media.write_bytes(data)
        os.utime(media, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    else:
        os.utime(media, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    current = service.lookup_asset_facts(ref)
    assert current.availability == "UNAVAILABLE"
    assert current.byte_size is current.duration_sec is None
    assert current.asset_ref == original.asset_ref
    assert current.checked_at >= original.checked_at
    assert original.availability == source.availability == "AVAILABLE"
    assert media.name not in current.model_dump_json()


@pytest.mark.parametrize("error", [PermissionError("private path"), OSError("private path"),
    RecordingCapabilityError("TEMPORARY_FAILURE", "등록 중 원본 변경을 감지했습니다")])
def test_inspection_failure_does_not_return_stale_success(media, monkeypatch, error):
    service, _, ref = register(media)
    assert service.lookup_asset_facts(ref).availability == "AVAILABLE"
    def fail(path):
        raise error
    monkeypatch.setattr("daesingo.recording.facts._snapshot", fail)
    with pytest.raises(RecordingCapabilityError) as caught:
        service.lookup_asset_facts(ref)
    assert caught.value.code == "TEMPORARY_FAILURE"
    assert "private path" not in str(caught.value)


@pytest.mark.parametrize("kind,code", [("source_asset", "UNKNOWN_REF"),
    ("media_stream", "INVALID_REF_KIND"), ("frame", "INVALID_REF_KIND")])
def test_ref_failures_remain_distinct(kind, code):
    with pytest.raises(RecordingCapabilityError) as caught:
        RecordingService().lookup_asset_facts({"kind": kind, "ref": "unknown"})
    assert caught.value.code == code


def test_public_example(media):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, "-m", "examples.recording_source_facts", str(media)],
        cwd=root, env=dict(os.environ, PYTHONPATH=str(root / "src")),
        check=True, capture_output=True, timeout=30)
    facts = AssetFacts.model_validate_json(result.stdout)
    assert facts.availability == "AVAILABLE" and facts.duration_sec == 1.0
    assert not result.stderr


def test_opt_in_real_source_facts():
    configured = os.environ.get("DAESINGO_RECORDING_VIDEO")
    if not configured:
        pytest.skip("DAESINGO_RECORDING_VIDEO 미지정")
    verify_available(Path(configured))
