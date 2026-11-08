"""Official input verification; fixtures are synthetic, never approved public media."""
import hashlib
import json
from pathlib import Path

import pytest

from daesingo.api.official_samples import OfficialSamples, SampleRejected
from daesingo.recording.probe import LocalSource, ProbedStream


def encoded(value):
    return json.dumps(value, ensure_ascii=False).encode()


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / "official"
    root.mkdir()
    files = []
    for index in range(2):
        name = f"part-{index}.mp4"
        content = bytes([index]) * 17
        (root / name).write_bytes(content)
        files.append({"name": name, "sha256": hashlib.sha256(content).hexdigest(),
                      "byte_size": len(content), "duration_ms": 300000})
    manifest = {"schema": "official-samples/v1", "samples": [{
        "sample_id": "synthetic-only", "label": "Synthetic input", "example_hint": "Turn",
        "authorization_ref": "test-only-not-public-approval", "files": files}]}
    return root, manifest


def catalog(bundle, *, max_bytes=34):
    root, manifest = bundle
    data = encoded(manifest)
    return OfficialSamples.from_manifest(data, expected_sha256=hashlib.sha256(data).hexdigest(),
                                         root=root, max_total_bytes=max_bytes)


class Probe:
    def __init__(self):
        self.calls = []

    def probe(self, path):
        self.calls.append(path)
        info = path.stat()
        return LocalSource(path, info.st_size, info.st_mtime_ns,
                           hashlib.sha256(path.read_bytes()).hexdigest(), 300.0,
                           (ProbedStream(0, "VIDEO", 300.0),))


def test_exact_600_seconds_is_allowed_and_public_listing_has_no_locators(bundle):
    source = catalog(bundle)
    listing = source.list_samples()
    assert listing == [{"sample_id": "synthetic-only", "label": "Synthetic input",
                        "example_hint": "Turn", "duration_ms": 600000,
                        "byte_size": 34, "file_count": 2}]
    listing[0]["duration_ms"] = 1
    assert source.list_samples()[0]["duration_ms"] == 600000
    probe = Probe()
    verified = source.verify("synthetic-only", probe=probe)
    assert verified.duration_ms == 600000 and verified.byte_size == 34
    assert len(verified.sources) == len(probe.calls) == 2
    assert str(bundle[0]) not in repr(source) + repr(verified)


def test_allowlist_miss_never_probes_or_returns_private_value(bundle):
    probe = Probe()
    with pytest.raises(SampleRejected) as error:
        catalog(bundle).verify("PRIVATE_UNKNOWN_SAMPLE", probe=probe)
    assert error.value.code == "NOT_APPROVED" and probe.calls == []
    assert "PRIVATE" not in str(error.value)


@pytest.mark.parametrize("change", ["duration", "bytes", "unknown_duration", "zero_duration",
                                   "bool_duration", "empty", "duplicate_id", "duplicate_file",
                                   "parent", "absolute", "windows", "nested", "stream",
                                   "trailing_dot", "device", "hash", "approval", "extra"])
def test_invalid_or_over_limit_manifest_is_rejected(bundle, change):
    sample = bundle[1]["samples"][0]
    first = sample["files"][0]
    if change == "duration":
        first["duration_ms"] += 1
    elif change == "bytes":
        first["byte_size"] += 1
    elif change in ("unknown_duration", "zero_duration", "bool_duration"):
        first["duration_ms"] = {"unknown_duration": None, "zero_duration": 0, "bool_duration": True}[change]
    elif change == "empty":
        sample["files"] = []
    elif change == "duplicate_id":
        bundle[1]["samples"].append(sample)
    elif change == "duplicate_file":
        sample["files"][1] = dict(first)
    elif change in ("parent", "absolute", "windows", "nested", "stream", "trailing_dot", "device"):
        first["name"] = {"parent": "../private.mp4", "absolute": "/private.mp4",
                         "windows": "C:\\private.mp4", "nested": "sub/private.mp4",
                         "stream": "clip.mp4:hidden", "trailing_dot": "clip.mp4.",
                         "device": "CON.mp4"}[change]
    elif change == "hash":
        first["sha256"] = "not-a-digest"
    elif change == "approval":
        sample["authorization_ref"] = ""
    else:
        sample["path"] = "PRIVATE"
    with pytest.raises(SampleRejected):
        catalog(bundle)


@pytest.mark.parametrize("raw", [b'{"schema":"official-samples/v1","samples":[],"samples":[]}',
                                b'{"samples":NaN}', b"x" * (262144 + 1), b"\xff"],
                         ids=["duplicate-key", "nonfinite", "oversized", "not-utf8"])
def test_duplicate_keys_non_json_and_unbounded_manifest_rejected(bundle, raw):
    with pytest.raises(SampleRejected):
        OfficialSamples.from_manifest(raw, expected_sha256=hashlib.sha256(raw).hexdigest(),
                                      root=bundle[0], max_total_bytes=34)


def test_manifest_identity_must_match_operator_pin(bundle):
    with pytest.raises(SampleRejected) as error:
        OfficialSamples.from_manifest(encoded(bundle[1]), expected_sha256="0" * 64,
                                      root=bundle[0], max_total_bytes=34)
    assert error.value.code == "INVALID_MANIFEST"


@pytest.mark.parametrize("limit", [0, -1, True, 34.0, None])
def test_unapproved_or_invalid_byte_budget_does_not_get_a_default(bundle, limit):
    with pytest.raises(SampleRejected):
        catalog(bundle, max_bytes=limit)


@pytest.mark.parametrize("change", ["missing", "size", "hash", "hardlink"])
def test_file_must_match_approved_identity_before_probe_or_registration(bundle, change):
    source = catalog(bundle)
    path = bundle[0] / "part-0.mp4"
    if change == "missing":
        path.unlink()
    elif change == "hardlink":
        (bundle[0] / "alias.mp4").hardlink_to(path)
    else:
        path.write_bytes(b"x" * (18 if change == "size" else 17))
    probe = Probe()
    with pytest.raises(SampleRejected):
        source.verify("synthetic-only", probe=probe)
    if change != "hash":
        assert probe.calls == []


@pytest.mark.parametrize("field,value", [("duration_sec", 300.000001), ("duration_sec", None),
                                        ("duration_sec", float("nan")), ("duration_sec", float("inf")),
                                        ("byte_size", 18), ("sha256", "0" * 64),
                                        ("streams", ()), ("path", Path("PRIVATE_OTHER"))])
def test_actual_probe_must_match_manifest_and_have_video(bundle, field, value):
    from dataclasses import replace
    class Mismatch(Probe):
        def probe(self, path):
            return replace(super().probe(path), **{field: value})
    with pytest.raises(SampleRejected):
        catalog(bundle).verify("synthetic-only", probe=Mismatch())


def test_no_rounded_float_escape_over_600_seconds(bundle):
    bundle[1]["samples"][0]["files"][0]["duration_ms"] = 299999
    class Over(Probe):
        def probe(self, path):
            from dataclasses import replace
            return replace(super().probe(path), duration_sec=300.0000001)
    with pytest.raises(SampleRejected):
        catalog(bundle).verify("synthetic-only", probe=Over())


def test_probe_errors_are_sanitized_and_never_include_private_path(bundle):
    class Failure(Probe):
        def probe(self, path):
            raise RuntimeError("PRIVATE_PATH_OR_PROVIDER_DATA")
    with pytest.raises(SampleRejected) as error:
        catalog(bundle).verify("synthetic-only", probe=Failure())
    assert error.value.code == "UNAVAILABLE" and "PRIVATE" not in str(error.value)


def test_input_objects_cannot_mutate_verified_configuration(bundle):
    source = catalog(bundle)
    bundle[1]["samples"][0]["files"][0]["sha256"] = "0" * 64
    assert source.verify("synthetic-only", probe=Probe()).byte_size == 34


def test_longer_video_stream_cannot_hide_behind_short_container_duration(bundle):
    from dataclasses import replace
    class LongerVideo(Probe):
        def probe(self, path):
            return replace(super().probe(path), streams=(ProbedStream(0, "VIDEO", 301.0),))
    with pytest.raises(SampleRejected):
        catalog(bundle).verify("synthetic-only", probe=LongerVideo())


def test_second_file_failure_returns_no_partial_verified_bundle(bundle):
    source = catalog(bundle)
    (bundle[0] / "part-1.mp4").write_bytes(b"x" * 17)
    probe = Probe()
    with pytest.raises(SampleRejected) as error:
        source.verify("synthetic-only", probe=probe)
    assert error.value.code == "INTEGRITY_MISMATCH" and len(probe.calls) == 2


@pytest.mark.parametrize("root", ["relative", "../escape"])
def test_root_must_be_operator_owned_absolute_location(bundle, root):
    data = encoded(bundle[1])
    with pytest.raises(SampleRejected):
        OfficialSamples.from_manifest(data, expected_sha256=hashlib.sha256(data).hexdigest(),
                                      root=Path(root), max_total_bytes=34)


def test_real_recording_probe_with_small_generated_video(tmp_path):
    import shutil
    import subprocess
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None or shutil.which("ffprobe") is None:
        pytest.skip("real local FFmpeg/ffprobe not installed")
    root = tmp_path / "official"
    root.mkdir()
    path = root / "synthetic.mp4"
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=black:s=32x32:r=2:d=1", "-an", "-c:v", "mpeg4", str(path)],
                   check=True, timeout=15, capture_output=True)
    file = {"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "byte_size": path.stat().st_size, "duration_ms": 1000}
    data = encoded({"schema": "official-samples/v1", "samples": [{"sample_id": "generated",
                    "label": "Synthetic", "example_hint": "", "authorization_ref": "test-only",
                    "files": [file]}]})
    official = OfficialSamples.from_manifest(data, expected_sha256=hashlib.sha256(data).hexdigest(),
                                             root=root, max_total_bytes=path.stat().st_size)
    verified = official.verify("generated")
    assert verified.duration_ms == 1000 and verified.sources[0].sha256 == file["sha256"]


def test_playlist_disguised_as_mp4_cannot_read_unapproved_external_video(tmp_path):
    import shutil
    import subprocess
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("real local FFmpeg/ffprobe not installed")
    root = tmp_path / "official"
    root.mkdir()
    outside = root / "outside.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=black:s=32x32:r=2:d=3", "-an", "-c:v", "mpeg4", str(outside)],
                   check=True, timeout=15, capture_output=True)
    wrapper = root / "approved.mp4"
    wrapper.write_bytes(b"ffconcat version 1.0\nstream\nexact_stream_id 1\n"
                        b"stream_meta DURATION 00:00:01.000000\nfile outside.mp4\nduration 1.0\n")
    file = {"name": wrapper.name, "sha256": hashlib.sha256(wrapper.read_bytes()).hexdigest(),
            "byte_size": wrapper.stat().st_size, "duration_ms": 1000}
    data = encoded({"schema": "official-samples/v1", "samples": [{"sample_id": "generated",
                    "label": "Synthetic", "example_hint": "", "authorization_ref": "test-only",
                    "files": [file]}]})
    source = OfficialSamples.from_manifest(data, expected_sha256=hashlib.sha256(data).hexdigest(),
                                           root=root, max_total_bytes=wrapper.stat().st_size)
    with pytest.raises(SampleRejected):
        source.verify("generated")
