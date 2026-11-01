"""Smoke guards are executable even when Docker is unavailable."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def smoke():
    path = ROOT / "scripts/smoke_compose.py"
    assert path.is_file(), "Compose smoke runner missing"
    spec = importlib.util.spec_from_file_location("rt13_smoke", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("project", ["default", "daesingo", "", "daesingo-rt13-smoke-../../other"])
def test_cleanup_refuses_non_smoke_project(project):
    with pytest.raises(ValueError): smoke().cleanup_command(project, ["compose.yaml"])


def test_cleanup_is_limited_to_exact_project_and_files():
    command = smoke().cleanup_command("daesingo-rt13-smoke-0123456789ab", ["compose.yaml", "override.json"])
    assert command == ["docker", "compose", "--project-name", "daesingo-rt13-smoke-0123456789ab",
        "-f", "compose.yaml", "-f", "override.json", "down", "--volumes", "--remove-orphans"]
    assert "prune" not in command


@pytest.mark.parametrize("surface", ["Env", "Cmd", "Args", "history", "logs"])
def test_secret_inspection_rejects_canary_on_every_surface(surface):
    with pytest.raises(ValueError, match="secret_disclosure"):
        smoke().assert_no_secrets({surface: ["prefix-private-canary-suffix"]}, ["private-canary"])


def test_secret_inspection_accepts_file_paths():
    smoke().assert_no_secrets({"Env": ["DAESINGO_ENV_FILE=/run/secrets/runtime.env"]}, ["private-canary"])


def test_compose_invocation_keeps_both_override_paths():
    assert smoke().compose_command("daesingo-rt13-smoke-0123456789ab", ["compose.yaml", "override.json"])[-4:] == [
        "-f", "compose.yaml", "-f", "override.json"]


def test_absent_docker_is_failure_with_no_resources(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    module = smoke()
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    import json
    evidence = tmp_path / "smoke.json"
    assert module.run_smoke(evidence) == 1
    report = json.loads(evidence.read_text())
    assert report["result"] == "FAIL" and report["failed_stage"] == "docker_preflight"
    assert report["cleanup"] == "not_needed" and report["stages"] == []


def test_media_persistence_compares_sources_and_excludes_mutable_leases(tmp_path):
    spec = importlib.util.spec_from_file_location("compose_probe", ROOT / "tests/deploy/compose_probe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / "source").mkdir()
    (tmp_path / "source/video.bin").write_bytes(b"uploaded")
    (tmp_path / ".cleanup-lease").write_bytes(b"changes-on-restart")
    snapshot = module.source_snapshot(tmp_path)
    import hashlib
    assert snapshot == {"source/video.bin": hashlib.sha256(b"uploaded").hexdigest()}


@pytest.mark.parametrize("failed_operation", ["down", "containers", "volumes", "networks", "image"])
def test_cleanup_attempts_all_owned_resources_after_each_operation_fails(failed_operation):
    import subprocess
    from types import SimpleNamespace
    module = smoke()
    calls = []
    def run(command, **kwargs):
        operation = ("down" if "down" in command else "image" if command[1:3] == ["image", "rm"]
            else "containers" if command[1:3] == ["ps", "-aq"] else command[1] + "s")
        calls.append(operation)
        if operation == failed_operation:
            raise subprocess.TimeoutExpired("private-canary", 1)
        return SimpleNamespace(returncode=0, stdout="")
    result = module.cleanup_resources("daesingo-rt13-smoke-0123456789ab", ["compose.yaml"],
        "daesingo-rt13-smoke-0123456789ab:local", run)
    assert set(calls) == {"down", "containers", "volumes", "networks", "image"}
    assert result["result"] == "FAIL" and result["failures"] == [
        {"operation": failed_operation, "failure_type": "TimeoutExpired"}]
    import json
    assert "private-canary" not in json.dumps(result)


def test_cleanup_success_requires_no_remaining_resources():
    from types import SimpleNamespace
    module = smoke()
    for remaining, expected in [("", "PASS"), ("owned-container-id", "FAIL")]:
        def run(command, **kwargs):
            return SimpleNamespace(returncode=0, stdout=remaining if command[1:3] == ["ps", "-aq"] else "")
        result = module.cleanup_resources("daesingo-rt13-smoke-0123456789ab", ["compose.yaml"],
            "daesingo-rt13-smoke-0123456789ab:local", run)
        assert result["result"] == expected
        assert result["remaining"] == (["containers"] if remaining else [])


def test_cleanup_error_cannot_overwrite_original_failure_or_disclose_values():
    import json
    import subprocess
    module = smoke()
    report = {}
    module.record_failure(report, "clean_build", RuntimeError("private-canary"))
    module.record_failure(report, "cleanup", subprocess.TimeoutExpired("private-canary", 1))
    assert report == {"result": "FAIL", "failed_stage": "clean_build", "failure_type": "RuntimeError"}
    assert "private-canary" not in json.dumps(report)


def test_cleanup_refuses_an_image_outside_its_project():
    with pytest.raises(ValueError, match="unsafe_image"):
        smoke().cleanup_resources("daesingo-rt13-smoke-0123456789ab", ["compose.yaml"],
            "shared-project:local", lambda *args, **kwargs: pytest.fail("must not run Docker"))
