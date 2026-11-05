"""C's production default is envelope; legacy remains an explicit policy."""
from types import SimpleNamespace

import pytest

from daesingo.recording.mysql_repository import MySQLRecordingRepository
from daesingo.recording.prepared_metadata import decode_prepared_payload


@pytest.mark.parametrize("kind", ["analysis_source", "incident_clip"])
def test_default_repository_writes_envelope_metadata(tmp_path, kind):
    repository = MySQLRecordingRepository(
        SimpleNamespace(dialect=SimpleNamespace(name="mysql"), closed=False),
        storage_root=tmp_path,
    )
    payload = {"availability": "UNKNOWN", "duration_sec": 12.25}
    stored = repository._row(kind, "ref", payload)["payload"]
    assert set(stored) == {"__recording_prepared_metadata__"}
    assert decode_prepared_payload(stored) == payload


@pytest.mark.parametrize("kind", ["analysis_source", "incident_clip"])
def test_explicit_legacy_policy_remains_native(tmp_path, kind):
    repository = MySQLRecordingRepository(
        SimpleNamespace(dialect=SimpleNamespace(name="mysql"), closed=False),
        storage_root=tmp_path, prepared_write_format="legacy",
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
