"""Host state machine with external Docker/AWS calls replaced, real disk state."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "1" * 12 + ".dkr.ecr.ap-northeast-2.amazonaws.com/runtime@sha256:" + "a" * 64
REV = "b" * 40


def module():
    path = ROOT / "deploy/ec2.py"
    assert path.is_file(), "RT-14 host controller missing"
    spec = importlib.util.spec_from_file_location("rt14_ec2", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class Host:
    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail

    def __call__(self, stage, release):
        self.calls.append(stage)
        if stage == self.fail:
            raise RuntimeError("PRIVATE-CANARY")


def release():
    return {"image": IMAGE, "revision": REV, "config_id": "config-1",
            "rollback_targets": ["c" * 40], "initial_state": "verified-empty-owned-volumes"}


@pytest.mark.parametrize("stage", ["preflight", "quiesce", "mysql", "packet", "migrate", "start", "health", "smoke"])
def test_failures_do_not_promote_known_good(tmp_path, stage):
    m = module()
    old = {**release(), "revision": "c" * 40}
    m.atomic_json(tmp_path / "current.json", old)
    host = Host(stage)
    with pytest.raises(RuntimeError):
        m.transition(tmp_path, release(), "deploy", host)
    assert json.loads((tmp_path / "current.json").read_text()) == old
    assert "promote" not in host.calls
    if stage in {"migrate", "start", "health", "smoke"}:
        assert (tmp_path / "dirty.json").exists()
    assert host.calls.count("migrate") <= 1


def test_success_promotes_only_after_all_checks(tmp_path):
    m = module()
    host = Host()
    m.transition(tmp_path, release(), "deploy", host)
    assert host.calls == ["preflight", "quiesce", "mysql", "packet", "migrate", "start", "health", "smoke"]
    assert json.loads((tmp_path / "current.json").read_text())["image"] == IMAGE
    assert not (tmp_path / "dirty.json").exists()


def test_partial_or_uncertain_migration_blocks_retry_and_rollback(tmp_path):
    m = module()
    with pytest.raises(RuntimeError):
        m.transition(tmp_path, release(), "deploy", Host("migrate"))
    for op in ("deploy", "rollback"):
        host = Host()
        with pytest.raises(m.HostError):
            m.transition(tmp_path, release(), op, host)
        assert host.calls == []


def test_rollback_exact_record_and_schema_approval_no_migration(tmp_path):
    m = module()
    old = {**release(), "revision": "c" * 40, "config_id": "config-old"}
    m.atomic_json(tmp_path / "current.json", old)
    with pytest.raises(RuntimeError):
        m.transition(tmp_path, release(), "deploy", Host("health"))
    host = Host()
    m.transition(tmp_path, old, "rollback", host)
    assert "migrate" not in host.calls and "packet" in host.calls
    assert json.loads((tmp_path / "current.json").read_text()) == old
    assert not (tmp_path / "dirty.json").exists()


def test_rollback_unknown_config_or_digest_rejected(tmp_path):
    m = module()
    m.atomic_json(tmp_path / "current.json", release())
    m.atomic_json(tmp_path / "dirty.json", {**release(), "phase": "migration_complete", "rollback_targets": [REV]})
    host = Host()
    with pytest.raises(m.HostError):
        m.transition(tmp_path, {**release(), "config_id": "other"}, "rollback", host)
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
    m.atomic_json(tmp_path / "current.json", b)
    with pytest.raises(RuntimeError):
        m.transition(tmp_path, c, "deploy", Host("health"))
    if fail_rollback:
        with pytest.raises(RuntimeError):
            m.transition(tmp_path, b, "rollback", Host("health"))
    else:
        m.transition(tmp_path, b, "rollback", Host())
    host = Host()
    with pytest.raises(m.HostError):
        m.transition(tmp_path, a, "rollback", host)
    assert host.calls == []


def test_first_deploy_without_initial_state_evidence_is_refused(tmp_path):
    m = module()
    candidate = release()
    candidate.pop("initial_state")
    host = Host()
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
