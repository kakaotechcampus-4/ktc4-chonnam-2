import io
import json

import pytest

from daesingo.worker.bootstrap import bootstrap


@pytest.mark.parametrize("suffix,value", [
    ("HEARTBEAT_INTERVAL_SEC", "0"),
    ("LEASE_DURATION_SEC", "10"),
    ("STALE_SWEEP_INTERVAL_SEC", "0"),
    ("HEARTBEAT_DB_CONNECT_TIMEOUT_SEC", "0"),
    ("HEARTBEAT_DB_READ_TIMEOUT_SEC", "2"),
    ("HEARTBEAT_DB_WRITE_TIMEOUT_SEC", "0"),
    ("DB_LOCK_WAIT_TIMEOUT_SEC", "10"),
])
def test_worker_baseline_invariants_fail_startup_without_values(monkeypatch, tmp_path, suffix, value):
    key = "DAESINGO_RUNTIME_" + suffix
    path = tmp_path / "worker.env"
    path.write_text("\n".join([
        "DAESINGO_RUNTIME_DB_URL=mysql+pymysql://user:private-secret@localhost/runtime",
        "DAESINGO_RUNTIME_MEDIA_ROOT=/private/media",
        "DAESINGO_RUNTIME_WORKER_TEMP_ROOT=/private/worker",
        "GEMINI_API_KEY=private-secret",
        f"{key}={value}",
    ]), encoding="utf-8")
    monkeypatch.setenv("DAESINGO_ENV_FILE", str(path))
    stream = io.StringIO()
    with pytest.raises(SystemExit) as error:
        bootstrap(revision="test", stream=stream)
    assert error.value.code == 1
    row = json.loads(stream.getvalue())
    assert row["event"] == "runtime.config.invalid" and key in row["keys"]
    assert "private" not in stream.getvalue()


def test_intent_config_uses_search_mapping_and_own_model(monkeypatch, tmp_path):
    path = tmp_path / "worker.env"
    path.write_text("\n".join([
        "DAESINGO_RUNTIME_DB_URL=mysql+pymysql://user:private-secret@localhost/runtime",
        "DAESINGO_RUNTIME_MEDIA_ROOT=/private/media",
        "DAESINGO_RUNTIME_WORKER_TEMP_ROOT=/private/worker",
        "GEMINI_API_KEY=private-secret", "DAESINGO_GEMINI_MODEL=coarse-model",
        "DAESINGO_INTENT_MODEL=intent-model",
    ]), encoding="utf-8")
    monkeypatch.setenv("DAESINGO_ENV_FILE", str(path))
    monkeypatch.setenv("DAESINGO_INTENT_MODEL", "wrong-environment")
    startup = bootstrap(revision="test", stream=io.StringIO())
    assert startup.modules["search"].config.model == "coarse-model"
    assert startup.modules["intent"].model == "intent-model"


def test_recording_profile_mapping_is_owned_and_validated_by_recording(monkeypatch, tmp_path):
    from tests.recording.test_factory_config import mapping
    path = tmp_path / "worker.env"
    values = {"DAESINGO_RUNTIME_DB_URL": "mysql+pymysql://user:private@localhost/runtime",
              "DAESINGO_RUNTIME_MEDIA_ROOT": str(tmp_path), "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(tmp_path),
              "GEMINI_API_KEY": "private", **mapping()}
    path.write_text("\n".join(f"{k}={v}" for k, v in values.items()), encoding="utf-8")
    monkeypatch.setenv("DAESINGO_ENV_FILE", str(path))
    startup = bootstrap(revision="test", stream=io.StringIO())
    assert startup.modules["recording"].profile_ref == "explicit-profile"
    path.write_text(path.read_text().replace("HEIGHT=240", "HEIGHT=241"))
    with pytest.raises(SystemExit): bootstrap(revision="test", stream=io.StringIO())
