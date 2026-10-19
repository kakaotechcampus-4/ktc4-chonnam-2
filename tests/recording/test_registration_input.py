"""REC-1(b): registration input is metadata, never a filesystem locator."""

from dataclasses import replace
import json
import subprocess

import pytest

from daesingo.recording import RecordingCapabilityError, RecordingService
from daesingo.recording.probe import LocalSource, ProbedStream
from daesingo.recording.repository import InMemoryRecordingRepository
from daesingo.recording.time_sources import LocalTimeSourceObserver


class Probe:
    def probe(self, path):
        return LocalSource(path, 5, path.stat().st_mtime_ns, "a" * 64, 1.0,
                           (ProbedStream(0, "VIDEO", 1.0),))


@pytest.mark.parametrize("name", ["20260620_141956_EVT_1.avi", " 한글 e\u0301 영상.AVI ",
    "../private/name.avi", "C:\\private\\name.avi", "", "x\x00y", "x" * 10000])
def test_original_name_is_opaque_exact_metadata_not_a_locator(tmp_path, name):
    path = tmp_path / "canonical.bin"
    path.write_bytes(b"video")
    repo = InMemoryRecordingRepository()
    result = RecordingService(repo, media_probe=Probe()).register_local_source(path, original_filename=name)
    local = repo.get_local_source(result.source_asset.source_asset_ref)
    assert local.path == path
    assert local.original_filename == name
    assert name not in repr(local) if name else True
    assert "original_filename" not in result.source_asset.model_dump()
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("name", [1, b"secret", ["secret"], {"secret": 1}, "secret\ud800"])
def test_wrong_filename_type_is_rejected_without_probe_or_error_echo(tmp_path, name):
    class NeverProbe:
        def probe(self, path):
            pytest.fail("bad input reached dependency")
    with pytest.raises(ValueError) as error:
        RecordingService(media_probe=NeverProbe()).register_local_source(tmp_path / "secret", original_filename=name)
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("case_id", ["", 1, {"secret": 1}, b"secret"])
def test_invalid_case_id_is_rejected_before_probe(tmp_path, case_id):
    class NeverProbe:
        def probe(self, path):
            pytest.fail("invalid case id reached probe")
    with pytest.raises(ValueError) as error:
        RecordingService(media_probe=NeverProbe()).register_local_source(tmp_path / "canonical", case_id=case_id)
    assert "secret" not in str(error.value)


def test_observer_uses_original_name_after_canonical_publish(tmp_path, monkeypatch):
    path = tmp_path / "canonical.bin"
    path.write_bytes(b"video")
    observer = LocalTimeSourceObserver(filename_offset="+09:00")
    monkeypatch.setattr(observer, "verify_source", lambda local: None)
    monkeypatch.setattr(observer, "_metadata", lambda local: {})
    repo = InMemoryRecordingRepository()
    registered = RecordingService(repo, media_probe=Probe()).register_local_source(
        path, original_filename="20260620_141956_EVT_1.avi")
    observed = RecordingService(repo, time_source_observer=observer).observe_time_sources(registered.source_asset.source_asset_ref)
    candidate, = observed.candidates
    assert candidate.source_kind == "FILENAME"
    assert candidate.value.isoformat() == "2026-06-20T14:19:56+09:00"
    assert candidate.provenance.observed_from == "20260620_141956_EVT_1.avi"
    # No fabricated original filename for old registrations.
    legacy = replace(repo.get_local_source(registered.source_asset.source_asset_ref), original_filename=None)
    assert not observer.observe("legacy", legacy).candidates


@pytest.mark.parametrize("returncode,payload,expected", [
    (1, {"error": {"code": -1094995529, "string": "private-secret"}}, "UNSUPPORTED_MEDIA"),
    (1, {"error": {"code": -5, "string": "Invalid data private-secret"}}, "TEMPORARY_FAILURE"),
    (1, {"error": {"code": -13}}, "TEMPORARY_FAILURE"),
    (1, {"error": {"code": "-1094995529"}}, "TEMPORARY_FAILURE"),
    (1, {}, "TEMPORARY_FAILURE"),
    (0, {"streams": []}, "UNSUPPORTED_MEDIA"),
    (0, {"streams": [{"index": 0, "codec_type": "audio"}]}, "UNSUPPORTED_MEDIA"),
    (0, {"streams": [{"index": -1, "codec_type": "video"}]}, "TEMPORARY_FAILURE"),
    (0, {}, "TEMPORARY_FAILURE"),
    (0, {"streams": [], "format": {"duration": "invalid"}}, "TEMPORARY_FAILURE"),
    (0, {"streams": [{"index": 0, "codec_type": "audio"}],
         "format": {"duration": "invalid"}}, "TEMPORARY_FAILURE"),
])
def test_probe_taxonomy_uses_structured_result_not_stderr(tmp_path, monkeypatch, returncode, payload, expected):
    path = tmp_path / "private-secret.bin"
    path.write_bytes(b"stable bytes")
    def run(command, **kwargs):
        assert "-show_error" in command
        return subprocess.CompletedProcess(command, returncode, json.dumps(payload).encode(), str(path).encode())
    monkeypatch.setattr("daesingo.recording.probe.subprocess.run", run)
    repo = InMemoryRecordingRepository()
    with pytest.raises(RecordingCapabilityError) as error:
        RecordingService(repo).register_local_source(path)
    assert error.value.code == expected
    assert "private-secret" not in str(error.value)
    assert not repo._source_assets and not repo._local_sources


def test_changed_source_overrides_deterministic_probe_rejection(tmp_path, monkeypatch):
    path = tmp_path / "canonical.bin"
    path.write_bytes(b"stable")
    def run(command, **kwargs):
        path.write_bytes(b"replaced")
        return subprocess.CompletedProcess(command, 1, b'{"error":{"code":-1094995529}}', b"secret")
    monkeypatch.setattr("daesingo.recording.probe.subprocess.run", run)
    with pytest.raises(RecordingCapabilityError) as error:
        RecordingService().register_local_source(path)
    assert error.value.code == "TEMPORARY_FAILURE"
