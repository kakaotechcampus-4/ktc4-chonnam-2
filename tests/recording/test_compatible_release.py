"""B must not publish envelopes that e50 cannot parse, including metadata-only."""
from types import SimpleNamespace

import pytest

from daesingo.recording.mysql_repository import MySQLRecordingRepository


@pytest.mark.parametrize("kind", ["analysis_source", "incident_clip"])
def test_default_repository_writes_native_metadata(tmp_path, kind):
    repository = MySQLRecordingRepository(
        SimpleNamespace(dialect=SimpleNamespace(name="mysql"), closed=False),
        storage_root=tmp_path,
    )
    payload = {"availability": "UNKNOWN", "duration_sec": 12.25}
    assert repository._row(kind, "ref", payload)["payload"] == payload


@pytest.mark.parametrize("policy", [None, "", "other", True])
def test_invalid_write_policy_is_rejected(tmp_path, policy):
    with pytest.raises(ValueError, match="prepared-media write format"):
        MySQLRecordingRepository(
            SimpleNamespace(dialect=SimpleNamespace(name="mysql"), closed=False),
            storage_root=tmp_path, prepared_write_format=policy,
        )
