"""The image adapter transports credentials over stdin and fails closed."""
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]


def adapter():
    path = ROOT / "docker/runtime.py"
    assert path.is_file(), "RT-13 runtime adapter missing"
    spec = importlib.util.spec_from_file_location("runtime_adapter", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_uses_existing_stdin_cli_and_preserves_failure(tmp_path, monkeypatch):
    module = adapter()
    secret = "mysql+pymysql://user:private-canary@mysql/daesingo"
    config = tmp_path / "runtime.env"
    config.write_text("DAESINGO_RUNTIME_DB_URL=" + secret)
    monkeypatch.setenv("DAESINGO_ENV_FILE", str(config))
    monkeypatch.delenv("DAESINGO_RUNTIME_DB_URL", raising=False)
    calls = []
    def run(argv, **kwargs):
        assert argv == [sys.executable, "-m", "daesingo.common.db.migrate", "--database-url-stdin"]
        assert kwargs["input"] == secret and kwargs["text"] is True
        assert "env" not in kwargs
        calls.append(argv)
        return SimpleNamespace(returncode=7)
    monkeypatch.setattr(module.subprocess, "run", run)
    assert module.main(["migrate"]) == 7
    assert len(calls) == 1


def test_invalid_config_exits_without_disclosing_value(tmp_path):
    adapter()
    import os
    config = tmp_path / "runtime.env"
    config.write_text("DAESINGO_RUNTIME_DB_URL=private-canary")
    result = subprocess.run([sys.executable, str(ROOT / "docker/runtime.py"), "migrate"],
        env={**os.environ, "DAESINGO_ENV_FILE": str(config)}, capture_output=True, text=True)
    assert result.returncode != 0
    assert "private-canary" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def test_ready_requires_success_payload(monkeypatch):
    module = adapter()
    for body, expected in [(b'{"status":"ok"}', 0), (b'{"status":"unavailable"}', 1)]:
        monkeypatch.setattr(module.urllib.request, "urlopen", lambda *a, **kw: io.BytesIO(body))
        assert module.main(["ready"]) == expected
