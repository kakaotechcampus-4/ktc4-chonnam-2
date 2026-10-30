"""Host state machine with external Docker/AWS calls replaced, real disk state."""
import importlib.util
import json
from pathlib import Path

import pytest
from tests.deploy.test_web_artifact import bundle

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "1" * 12 + ".dkr.ecr.ap-northeast-2.amazonaws.com/runtime@sha256:" + "a" * 64
REV = "b" * 40


def module():
    path = ROOT / "deploy/ec2.py"
    assert path.is_file(), "RT-14 host controller missing"
    spec = importlib.util.spec_from_file_location("deploy.ec2", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class Host:
    def __init__(self, root, fail=None):
        self.root = root
        self.calls = []
        self.fail = fail

    def __call__(self, stage, release):
        self.calls.append(stage)
        if stage == "preflight":
            web = self.root / "releases" / release["revision"] / "web"
            if not web.exists():
                bundle(web, release["revision"])
        if stage == self.fail:
            raise RuntimeError("PRIVATE-CANARY")


def seed_current(m, root, value):
    m.atomic_json(root / "current.json", value)
    web = root / "releases" / value["revision"] / "web"
    if not web.exists():
        bundle(web, value["revision"])
    pointer = root / "releases" / "current"
    if pointer.is_symlink():
        pointer.unlink()
    pointer.symlink_to(value["revision"] + "/web", target_is_directory=True)


def release():
    return {"image": IMAGE, "revision": REV, "config_id": "config-1",
            "rollback_targets": ["c" * 40], "initial_state": "verified-empty-owned-volumes"}


@pytest.mark.parametrize("stage", ["preflight", "quiesce", "mysql", "packet", "migrate", "start", "health", "smoke"])
def test_failures_do_not_promote_known_good(tmp_path, stage):
    m = module()
    old = {**release(), "revision": "c" * 40}
    seed_current(m, tmp_path, old)
    host = Host(tmp_path, stage)
    with pytest.raises(RuntimeError):
        m.transition(tmp_path, release(), "deploy", host)
    assert json.loads((tmp_path / "current.json").read_text()) == old
    assert (tmp_path / "releases/current").readlink().as_posix() == old["revision"] + "/web"
    assert "promote" not in host.calls
    if stage in {"migrate", "start", "health", "smoke"}:
        assert (tmp_path / "dirty.json").exists()
    assert host.calls.count("migrate") <= 1


def test_success_promotes_only_after_all_checks(tmp_path):
    m = module()
    host = Host(tmp_path)
    m.transition(tmp_path, release(), "deploy", host)
    assert host.calls == ["preflight", "quiesce", "mysql", "packet", "migrate", "start", "health", "smoke"]
    assert json.loads((tmp_path / "current.json").read_text())["image"] == IMAGE
    assert not (tmp_path / "dirty.json").exists()


def test_partial_or_uncertain_migration_blocks_retry_and_rollback(tmp_path):
    m = module()
    with pytest.raises(RuntimeError):
        m.transition(tmp_path, release(), "deploy", Host(tmp_path, "migrate"))
    for op in ("deploy", "rollback"):
        host = Host(tmp_path)
        with pytest.raises(m.HostError):
            m.transition(tmp_path, release(), op, host)
        assert host.calls == []


def test_rollback_exact_record_and_schema_approval_no_migration(tmp_path):
    m = module()
    old = {**release(), "revision": "c" * 40, "config_id": "config-old"}
    seed_current(m, tmp_path, old)
    with pytest.raises(RuntimeError):
        m.transition(tmp_path, release(), "deploy", Host(tmp_path, "health"))
    host = Host(tmp_path)
    m.transition(tmp_path, old, "rollback", host)
    assert "migrate" not in host.calls and "packet" in host.calls
    assert json.loads((tmp_path / "current.json").read_text()) == old
    assert not (tmp_path / "dirty.json").exists()


@pytest.mark.parametrize("mutation", [{"config_id": "other"}, {"image": IMAGE[:-1] + "f"}])
def test_rollback_unknown_config_or_digest_rejected(tmp_path, mutation):
    m = module()
    seed_current(m, tmp_path, release())
    m.atomic_json(tmp_path / "schema.json", {**release(), "phase": "migration_complete", "rollback_targets": [REV]})
    host = Host(tmp_path)
    with pytest.raises(m.HostError):
        m.transition(tmp_path, {**release(), **mutation}, "rollback", host)
    assert host.calls == []


def test_production_compose_uses_digest_external_volumes_no_build():
    m = module()
    source = json.loads((ROOT / "compose.yaml").read_text())
    policy = {"project": "daesingo-runtime", "mysql_volume": "owned-db", "media_volume": "owned-media",
              "restart_policy": "unless-stopped", "log_group": "/approved/runtime", "log_buffer_bytes": 4194304,
              "mysql_image": "mysql@sha256:" + "d" * 64}
    result = m.production_compose(source, release(), policy, Path("/opt/daesingo/configs/config-1"))
    for name in ("api", "worker", "migrate"):
        assert result["services"][name]["image"] == IMAGE
        assert "build" not in result["services"][name]
    assert result["services"]["migrate"].get("restart", "no") == "no"
    assert result["services"]["worker"]["environment"]["DAESINGO_DEPLOYMENT_CHECK"] == "1"
    assert result["volumes"]["mysql_data"] == {"external": True, "name": "owned-db"}
    assert result["volumes"]["media"] == {"external": True, "name": "owned-media"}
    assert result["services"]["mysql"]["image"] == "mysql@sha256:" + "d" * 64
    assert "awslogs-stream-prefix" not in result["services"]["api"]["logging"]["options"]


def test_project_collision_cannot_stop_unowned_containers():
    m = module()
    assert hasattr(m, "validate_existing_project"), "project ownership guard missing"
    labels = {"com.docker.compose.project": "owned", "com.docker.compose.service": "mysql"}
    good = {"Config": {"Labels": labels}, "Mounts": [{"Type": "volume", "Destination": "/var/lib/mysql", "Name": "owned-db"}]}
    m.validate_existing_project([good], {"project": "owned", "mysql_volume": "owned-db", "media_volume": "owned-media"}, known=True)
    for known, item in [(False, good), (True, {**good, "Mounts": []})]:
        with pytest.raises(m.HostError):
            m.validate_existing_project([item], {"project": "owned", "mysql_volume": "owned-db", "media_volume": "owned-media"}, known=known)


def test_lock_refuses_concurrent_owner_without_stealing(tmp_path):
    m = module()
    # Linux flock is exercised separately on Linux; portable O_EXCL lock is real here.
    with m.operation_lock(tmp_path):
        with pytest.raises(m.HostError):
            with m.operation_lock(tmp_path):
                pytest.fail("second deployment entered")
    with m.operation_lock(tmp_path):
        pass


def test_invalid_cli_never_echoes_arguments(capsys):
    m = module()
    assert m.main(["PRIVATE-CANARY"]) == 1
    assert "PRIVATE-CANARY" not in str(capsys.readouterr())


@pytest.mark.parametrize("fail_rollback", [False, True])
def test_rollback_cannot_replace_applied_schema_compatibility(tmp_path, fail_rollback):
    m = module()
    a = {**release(), "revision": "a" * 40, "rollback_targets": []}
    b = {**release(), "revision": "b" * 40, "rollback_targets": ["a" * 40]}
    c = {**release(), "revision": "c" * 40, "rollback_targets": ["b" * 40]}
    m.atomic_json(tmp_path / "previous.json", a)
    bundle(tmp_path / "releases" / a["revision"] / "web", a["revision"])
    seed_current(m, tmp_path, b)
    with pytest.raises(RuntimeError):
        m.transition(tmp_path, c, "deploy", Host(tmp_path, "health"))
    if fail_rollback:
        with pytest.raises(RuntimeError):
            m.transition(tmp_path, b, "rollback", Host(tmp_path, "health"))
    else:
        m.transition(tmp_path, b, "rollback", Host(tmp_path))
    host = Host(tmp_path)
    with pytest.raises(m.HostError):
        m.transition(tmp_path, a, "rollback", host)
    assert host.calls == []


def test_first_deploy_without_initial_state_evidence_is_refused(tmp_path):
    m = module()
    candidate = release()
    candidate.pop("initial_state")
    host = Host(tmp_path)
    with pytest.raises(m.HostError):
        m.transition(tmp_path, candidate, "deploy", host)
    assert host.calls == []


def test_bootstrap_refuses_existing_data_even_with_ownership_labels(tmp_path):
    m = module()
    assert hasattr(m, "verify_empty_volume"), "first deploy emptiness guard missing"
    info = {"Mountpoint": str(tmp_path)}
    m.verify_empty_volume(info)
    (tmp_path / "existing-db-or-media").write_text("keep")
    with pytest.raises(m.HostError):
        m.verify_empty_volume(info)
    assert (tmp_path / "existing-db-or-media").read_text() == "keep"


@pytest.mark.parametrize("stage", ["quiesce", "migrate", "start", "health", "smoke"])
def test_first_failure_never_invents_known_good(tmp_path, stage):
    m = module()
    with pytest.raises(RuntimeError):
        m.transition(tmp_path, release(), "deploy", Host(tmp_path, stage))
    assert not (tmp_path / "current.json").exists()
    assert not (tmp_path / "releases/current").is_symlink()
    for op in ("deploy", "rollback"):
        with pytest.raises(m.HostError):
            m.transition(tmp_path, release(), op, Host(tmp_path))


@pytest.mark.parametrize("boundary", ["pointer", "previous", "current", "dirty"])
def test_promotion_interrupt_blocks_both_operations(tmp_path, monkeypatch, boundary):
    m = module()
    old = {**release(), "revision": "c" * 40}
    seed_current(m, tmp_path, old)
    original_json = m.atomic_json
    original_unlink = Path.unlink
    def write(path, value):
        original_json(path, value)
        if path.name == boundary + ".json":
            raise OSError("synthetic interrupt")
    if boundary == "pointer":
        assert hasattr(m, "publish_web"), "atomic Web pointer missing"
        original = m.publish_web
        def publish(root, value):
            original(root, value)
            raise OSError("synthetic interrupt")
        monkeypatch.setattr(m, "publish_web", publish)
    elif boundary == "dirty":
        def unlink(path, *args, **kwargs):
            if path.name == "dirty.json":
                raise OSError("synthetic interrupt")
            return original_unlink(path, *args, **kwargs)
        monkeypatch.setattr(Path, "unlink", unlink)
    else:
        monkeypatch.setattr(m, "atomic_json", write)
    with pytest.raises(OSError):
        m.transition(tmp_path, release(), "deploy", Host(tmp_path))
    assert (tmp_path / "dirty.json").exists()
    assert (tmp_path / "releases/current").readlink().as_posix() == REV + "/web"
    monkeypatch.undo()
    for op in ("deploy", "rollback"):
        host = Host(tmp_path)
        with pytest.raises(m.HostError):
            m.transition(tmp_path, old, op, host)
        assert host.calls == []


def test_success_switches_web_and_rollback_together(tmp_path):
    m = module()
    old = {**release(), "revision": "c" * 40}
    seed_current(m, tmp_path, old)
    m.transition(tmp_path, release(), "deploy", Host(tmp_path))
    assert (tmp_path / "releases/current").readlink().as_posix() == REV + "/web"
    m.transition(tmp_path, old, "rollback", Host(tmp_path))
    assert (tmp_path / "releases/current").readlink().as_posix() == old["revision"] + "/web"
    assert m.read_record(tmp_path / "current.json") == old
    assert m.read_record(tmp_path / "previous.json") == release()


def test_deleted_dirty_cannot_hide_pointer_mismatch(tmp_path):
    m = module()
    old = {**release(), "revision": "c" * 40}
    seed_current(m, tmp_path, old)
    pointer = tmp_path / "releases/current"
    pointer.unlink()
    pointer.symlink_to(REV + "/web", target_is_directory=True)
    host = Host(tmp_path)
    with pytest.raises(m.HostError):
        m.transition(tmp_path, release(), "deploy", host)
    assert host.calls == []


def test_process_exit_after_pointer_keeps_dirty_and_lock(tmp_path):
    import subprocess
    import sys
    m = module()
    old = {**release(), "revision": "c" * 40}
    seed_current(m, tmp_path, old)
    code = """
import os, sys
from pathlib import Path
from deploy import ec2
from tests.deploy.test_ec2_deploy import Host, release
root = Path(sys.argv[1])
original = ec2.publish_web
def stop(root, value):
    original(root, value)
    os._exit(23)
ec2.publish_web = stop
with ec2.operation_lock(root):
    ec2.transition(root, release(), 'deploy', Host(root))
"""
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path)], cwd=ROOT,
                            capture_output=True, timeout=30)
    assert result.returncode == 23
    assert (tmp_path / "operation.lock").is_dir()
    assert m.read_record(tmp_path / "dirty.json")["phase"] == "promotion_pending"
    assert m.read_record(tmp_path / "current.json") == old
    assert (tmp_path / "releases/current").readlink().as_posix() == REV + "/web"
    with pytest.raises(m.HostError):
        with m.operation_lock(tmp_path):
            pytest.fail("abandoned lock stolen")
    for op in ("deploy", "rollback"):
        with pytest.raises(m.HostError):
            m.transition(tmp_path, old, op, Host(tmp_path))
