from dataclasses import replace
import hashlib

import pytest

from daesingo.api.official_samples import VerifiedSample, SampleRejected
from daesingo.api.public_samples import copy_verified_sample
from daesingo.recording.probe import LocalSource, ProbedStream


def verified(path):
    return VerifiedSample("synthetic", 1000, path.stat().st_size, (LocalSource(path,
        path.stat().st_size, path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest(),
        1.0, (ProbedStream(0, "VIDEO", 1.0),)),))


def test_copy_is_bounded_case_owned_and_canonical_is_preserved(tmp_path):
    root = tmp_path / "media"
    root.mkdir()
    original = tmp_path / "official.mp4"
    original.write_bytes(b"synthetic" * 1024)
    sample = verified(original)
    copied = copy_verified_sample(sample, root)
    assert len(copied) == 1 and copied[0].path.parent == root / "source"
    assert copied[0].sha256 == sample.sources[0].sha256
    assert copied[0].path.read_bytes() == original.read_bytes()
    assert copied[0].path.name != original.name


@pytest.mark.parametrize("change", ["bytes", "mtime", "digest"])
def test_mutation_after_verification_refuses_copy_and_leaves_no_published_file(tmp_path, change):
    root = tmp_path / "media"
    root.mkdir()
    original = tmp_path / "official.mp4"
    original.write_bytes(b"test")
    sample = verified(original)
    if change == "bytes":
        original.write_bytes(b"wrong")
    else:
        source = sample.sources[0]
        sample = replace(sample, sources=(replace(source, **{
            "sha256" if change == "digest" else "mtime_ns": "0" * 64 if change == "digest" else 0}),))
    with pytest.raises(SampleRejected):
        copy_verified_sample(sample, root)
    assert not list((root / "source").glob("*")) and original.exists()
