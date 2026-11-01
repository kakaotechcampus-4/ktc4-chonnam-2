"""The image adapter transports credentials over stdin and fails closed."""
import importlib.util
import io
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

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


def media_pair(tmp_path, monkeypatch, module, *, version="8.1", probe_version=None,
               probe_configuration="same"):
    hashes = {}
    for name in ("ffmpeg", "ffprobe"):
        path = tmp_path / name
        path.write_bytes(name.encode())
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = tmp_path / "media.json"
    manifest.write_text(json.dumps({"version": "8.1", "sha256": hashes}))
    monkeypatch.setattr(module.shutil, "which", lambda name: str(tmp_path / name))
    def run(argv, **kwargs):
        name = Path(argv[0]).name
        value = (probe_version or version) if name == "ffprobe" else version
        configuration = probe_configuration if name == "ffprobe" else "same"
        return SimpleNamespace(returncode=0, stdout=f"{name} version {value} Copyright\nconfiguration: {configuration}\n")
    monkeypatch.setattr(module.subprocess, "run", run)
    return manifest


def test_supported_media_pair_passes(tmp_path, monkeypatch):
    module = adapter()
    manifest = media_pair(tmp_path, monkeypatch, module)
    module.verify_media_tools(manifest)


@pytest.mark.parametrize("version,probe", [("5.1.9", None), ("8.0", None),
    ("8.1.1", None), ("9.0.1", None), ("8.1-custom", None), ("8.1", "5.1.9")])
def test_unsupported_or_mixed_media_pair_fails(tmp_path, monkeypatch, version, probe):
    module = adapter()
    manifest = media_pair(tmp_path, monkeypatch, module, version=version, probe_version=probe)
    with pytest.raises(ValueError, match="media_toolchain"):
        module.verify_media_tools(manifest)


@pytest.mark.parametrize("mutation", ["binary", "configuration", "missing", "manifest"])
def test_changed_or_unverifiable_media_build_fails(tmp_path, monkeypatch, mutation):
    module = adapter()
    manifest = media_pair(tmp_path, monkeypatch, module,
        probe_configuration="different" if mutation == "configuration" else "same")
    if mutation == "binary": (tmp_path / "ffprobe").write_bytes(b"different-build")
    elif mutation == "missing": monkeypatch.setattr(module.shutil, "which", lambda name: None)
    elif mutation == "manifest": manifest.write_text("{}")
    with pytest.raises((ValueError, OSError), match="media_toolchain"):
        module.verify_media_tools(manifest)


@pytest.mark.parametrize("mode", ["api", "worker", "media-preflight"])
def test_media_preflight_blocks_startup_without_tool_output_disclosure(monkeypatch, capsys, mode):
    module = adapter()
    def fail(*args): raise ValueError("private-path-canary")
    monkeypatch.setattr(module, "verify_media_tools", fail, raising=False)
    monkeypatch.setattr(module.os, "execv", lambda *args: pytest.fail("startup bypassed preflight"))
    assert module.main([mode]) == 1
    assert capsys.readouterr().err == "container: media_toolchain_invalid (requires matching pinned ffmpeg/ffprobe 8.1)\n"
