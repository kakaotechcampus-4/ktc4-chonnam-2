import hashlib
import json

import pytest

from daesingo.api.official_samples import OfficialSamples, SampleRejected


def test_bundle_selection_uses_content_and_manifest_order(tmp_path):
    payloads = (b"first", b"second", b"different")
    paths = [tmp_path / str(i) for i in range(len(payloads))]
    for path, payload in zip(paths, payloads, strict=True):
        path.write_bytes(payload)

    def spec(payload, name):
        return {"name": name, "sha256": hashlib.sha256(payload).hexdigest(),
                "byte_size": len(payload), "duration_ms": 1000}

    raw = json.dumps({"schema": "official-samples/v1", "samples": [
        {"sample_id": "short", "label": "short", "example_hint": "", "authorization_ref": "TEST",
         "files": [spec(payloads[0], "one.mp4"), spec(payloads[1], "two.mp4")]},
        {"sample_id": "other", "label": "other", "example_hint": "", "authorization_ref": "TEST",
         "files": [spec(payloads[2], "one.mp4")]},
    ]}).encode()
    catalog = OfficialSamples.from_manifest(raw, expected_sha256=hashlib.sha256(raw).hexdigest(),
                                            root=tmp_path, max_total_bytes=100)
    sample_id, ordered = catalog.match_uploads([paths[1], paths[0]])
    assert sample_id == "short"
    assert [path for path, _ in ordered] == paths[:2]
    sample_id, ordered = catalog.match_uploads([paths[0]])
    assert sample_id == "short"
    assert [path for path, _ in ordered] == paths[:1]
    sample_id, ordered = catalog.match_uploads([paths[2]])
    assert sample_id == "other"
    assert [path for path, _ in ordered] == paths[2:]

    modified = tmp_path / "modified.mp4"
    modified.write_bytes(b"firST")
    for invalid in ([], [paths[0], paths[0]], [paths[0], paths[2]], paths, [modified]):
        with pytest.raises(SampleRejected, match="not_approved"):
            catalog.match_uploads(invalid)
