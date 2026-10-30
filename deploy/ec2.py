"""Root-owned Linux host controller; fixed private root, no install or cleanup.

All child output stays private. Decisions, resource identities and capacity
budgets are supplied by an operator, not discovered/created by deployment.
"""
import argparse
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time

ROOT = Path("/opt/daesingo")
DECISIONS = ("RD-12b", "RD-12c", "RD-12d", "RD-12e", "RD-12f", "RD-12h",
             "RD-13a", "RD-13c", "RD-13d", "RD-11a", "RD-07c")


class HostError(Exception):
    pass


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise HostError("invalid_arguments")


def require(ok):
    if not ok:
        raise HostError("host_precondition_failed")


def atomic_json(path, value):
    temporary = path.with_suffix(".new")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name == "posix":
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def operation_lock(root):
    # mkdir is atomic across processes, survives killed controller. An operator
    # must reconcile SSM/process/dirty state before removing an abandoned lock.
    lock = root / "operation.lock"
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError:
        raise HostError("deployment_already_locked") from None
    try:
        yield
    finally:
        lock.rmdir()


def read_record(path):
    return json.loads(path.read_text()) if path.exists() else None


def transition(root, release, operation, step):
    """Caller holds the host lock. Never downgrade schema or erase data."""
    current = read_record(root / "current.json")
    previous = read_record(root / "previous.json")
    dirty = read_record(root / "dirty.json")
    # DB schema provenance survives application/config rollback. Never replace
    # this authority with an older release's historical compatibility list.
    schema = read_record(root / "schema.json") or dirty or current
    if operation == "deploy":
        require(dirty is None)
        require(schema is None or schema.get("phase", "migration_complete") == "migration_complete")
        if current:
            require(current["revision"] in release["rollback_targets"])
        else:
            require(release.get("initial_state") == "verified-empty-owned-volumes")
        if (root / "schema.json").exists():
            require(release.get("schema_parent") == schema["revision"])
    elif operation == "rollback":
        require(dirty is None or dirty.get("phase") == "migration_complete")
        require(release in (current, previous))
        require(schema is not None and schema.get("phase", "migration_complete") == "migration_complete"
                and release["revision"] in schema["rollback_targets"])
    else:
        raise HostError("invalid_operation")
    step("preflight", release)
    # Write before stopping anything: even interrupt during stop must be audited.
    journal = {**release, "phase": "quiescing"}
    if operation == "rollback":
        journal["rollback_targets"] = schema["rollback_targets"]
        journal["schema_revision"] = schema["revision"]
    atomic_json(root / "dirty.json", journal)
    step("quiesce", release)
    step("mysql", release)
    step("packet", release)
    if operation == "deploy":
        atomic_json(root / "dirty.json", {**journal, "phase": "migration_pending"})
        atomic_json(root / "schema.json", {**journal, "phase": "migration_pending"})
        step("migrate", release)
        atomic_json(root / "schema.json", {**journal, "phase": "migration_complete"})
    atomic_json(root / "dirty.json", {**journal, "phase": "migration_complete"})
    for stage in ("start", "health", "smoke"):
        step(stage, release)
    # Two-record updates interrupted mid-promotion leave dirty marker -> stop.
    if current and current != release:
        atomic_json(root / "previous.json", current)
    atomic_json(root / "current.json", release)
    (root / "dirty.json").unlink()


def protected(path, uid, *, directory=False):
    info = path.lstat()
    require(not stat.S_ISLNK(info.st_mode) and info.st_uid == uid)
    require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
    require(stat.S_IMODE(info.st_mode) == (0o700 if directory else 0o400))


def instance_environment(environ):
    return {**{k: v for k, v in environ.items() if not k.startswith("AWS_")},
        "AWS_CONFIG_FILE": "/dev/null", "AWS_SHARED_CREDENTIALS_FILE": "/dev/null",
        "AWS_DEFAULT_REGION": "ap-northeast-2", "AWS_PAGER": "", "COMPOSE_DISABLE_ENV_FILE": "1"}


def run(argv, *, input=None, timeout=90):
    try:
        result = subprocess.run(argv, input=input, capture_output=True, text=True,
                                timeout=timeout, check=False,
                                env=instance_environment(os.environ))
        require(result.returncode == 0)
        return result.stdout
    except (OSError, subprocess.SubprocessError):
        raise HostError("child_failed_or_timeout") from None


def production_compose(source, release, policy, directory):
    config = deepcopy(source)
    require(set(config["services"]) == {"api", "worker", "migrate", "mysql"})
    substitutions = {"DAESINGO_RUNTIME_ENV_FILE": str(directory / "runtime.env"),
        "DAESINGO_MYSQL_PASSWORD_FILE": str(directory / "mysql-password"),
        "DAESINGO_MYSQL_ROOT_PASSWORD_FILE": str(directory / "mysql-root-password")}
    for name, service in config["services"].items():
        service.pop("build", None)
        # All dependencies are enforced by controller stages. No stale completed
        # migration service may satisfy a subsequent Compose dependency gate.
        service.pop("depends_on", None)
        service["restart"] = "no" if name == "migrate" else policy["restart_policy"]
        service["logging"] = {"driver": "awslogs", "options": {
            "awslogs-region": "ap-northeast-2", "awslogs-group": policy["log_group"],
            "tag": policy["project"] + "/" + name + "/{{.ID}}",
            "awslogs-create-group": "false", "mode": "non-blocking",
            "max-buffer-size": str(policy["log_buffer_bytes"]),
            "cache-max-size": "20m", "cache-max-file": "5"}}
        if name != "mysql":
            service["image"] = release["image"]
        else:
            service["image"] = policy["mysql_image"]
        if name == "worker":
            service["environment"]["DAESINGO_DEPLOYMENT_CHECK"] = "1"
        for mount in service["volumes"]:
            if mount["type"] == "bind":
                found = [value for key, value in substitutions.items() if key in mount["source"]]
                require(len(found) == 1)
                mount["source"] = found[0]
        if name == "api":
            service["ports"] = ["127.0.0.1:8000:8000"]
    config["volumes"] = {"mysql_data": {"external": True, "name": policy["mysql_volume"]},
                         "media": {"external": True, "name": policy["media_volume"]}}
    return config


def validate_policy(policy):
    require(all(isinstance(policy.get("decision_refs", {}).get(key), str)
        and policy["decision_refs"][key].strip()
        and "pending" not in policy["decision_refs"][key].lower() for key in DECISIONS))
    require(policy.get("region") == "ap-northeast-2")
    require(bool(re.fullmatch(r"[0-9]{12}\.dkr\.ecr\.ap-northeast-2\.amazonaws\.com/"
        r"[a-z0-9]+(?:[._/-][a-z0-9]+)*", policy.get("repository", ""))))
    for key in ("project", "mysql_volume", "media_volume"):
        require(bool(re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", policy.get(key, ""))))
    require(policy["mysql_volume"] != policy["media_volume"])
    require(policy.get("restart_policy") in {"no", "unless-stopped"})
    require(bool(re.fullmatch(r"mysql@sha256:[0-9a-f]{64}", policy.get("mysql_image", ""))))
    require(bool(re.fullmatch(r"/[A-Za-z0-9/_-]+", policy.get("log_group", ""))))
    for key in ("log_retention_days", "log_buffer_bytes", "disk_reserve_bytes", "memory_reserve_bytes",
                "packet_margin_bytes", "mysql_uid"):
        require(type(policy.get(key)) is int and policy[key] > 0)


def validate_existing_project(containers, policy, *, known):
    require(not containers or known)
    for info in containers:
        labels = info["Config"].get("Labels") or {}
        service = labels.get("com.docker.compose.service")
        require(labels.get("com.docker.compose.project") == policy["project"]
                and service in {"api", "worker", "migrate", "mysql"})
        target = "/var/lib/mysql" if service == "mysql" else "/media"
        expected = policy["mysql_volume"] if service == "mysql" else policy["media_volume"]
        if service != "migrate":
            require(any(m.get("Type") == "volume" and m.get("Destination") == target
                and m.get("Name") == expected for m in info["Mounts"]))


def verify_empty_volume(info):
    path = Path(info["Mountpoint"])
    require(path.is_absolute() and path.is_dir() and not path.is_symlink())
    require(next(path.iterdir(), None) is None)


class DockerHost:
    def __init__(self, root, policy):
        self.root, self.policy = root, policy
        self.base = None
        self.image_id = None

    def compose(self, *args, timeout=120):
        return run([*self.base, *args], timeout=timeout)

    def __call__(self, stage, release):
        if stage == "preflight":
            return self.preflight(release)
        if stage == "quiesce":
            self.compose("stop", "api", "worker", "migrate")
        elif stage == "mysql":
            self.compose("up", "-d", "--no-deps", "--no-build", "--pull", "never", "--wait", "--wait-timeout", "120", "mysql", timeout=150)
        elif stage == "packet":
            self.compose("run", "--rm", "--no-deps", "migrate", "python", "/app/docker/runtime.py",
                         "deploy-packet", str(self.policy["packet_margin_bytes"]))
        elif stage == "migrate":
            self.compose("run", "--rm", "--no-deps", "migrate", timeout=300)
        elif stage == "start":
            self.compose("up", "-d", "--no-deps", "--no-build", "--pull", "never", "--force-recreate", "api", "worker")
        elif stage == "health":
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                try:
                    self.inspect_services(release)
                    self.compose("exec", "-T", "api", "python", "/app/docker/runtime.py", "ready")
                    self.compose("exec", "-T", "worker", "python", "/app/docker/runtime.py", "worker-status")
                    return
                except HostError:
                    time.sleep(3)
            raise HostError("health_failed")
        elif stage == "smoke":
            self.compose("exec", "-T", "api", "python", "/app/docker/runtime.py", "deploy-smoke")
            self.inspect_services(release)
        else:
            raise HostError("unknown_stage")

    def inspect_services(self, release):
        for name in ("api", "worker", "mysql"):
            ids = self.compose("ps", "-q", name).split()
            require(len(ids) == 1)
            info, = json.loads(run(["docker", "inspect", ids[0]]))
            require(info["State"]["Running"] and not info["State"].get("Restarting")
                    and not info["State"].get("OOMKilled") and info.get("RestartCount", 0) == 0)
            if name != "mysql":
                require(info["Image"] == self.image_id)
                require("DAESINGO_REVISION=" + release["revision"] in info["Config"]["Env"])
            if name in {"api", "mysql"}:
                require(info["State"].get("Health", {}).get("Status") == "healthy")

    def preflight(self, release):
        policy = self.policy
        project_ids = run(["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=" + policy["project"]]).split()
        containers = json.loads(run(["docker", "inspect", *project_ids])) if project_ids else []
        validate_existing_project(containers, policy, known=(self.root / "current.json").exists())
        mysql, = json.loads(run(["docker", "image", "inspect", policy["mysql_image"]]))
        require(mysql["Architecture"] == "amd64" and any(v.startswith("MYSQL_VERSION=8.4.") for v in mysql["Config"]["Env"]))
        for info in containers:
            if info["Config"]["Labels"].get("com.docker.compose.service") == "mysql":
                require(info["Image"] == mysql["Id"])
        require(release["image"].startswith(policy["repository"] + "@sha256:"))
        require(shutil.disk_usage(self.root).free >= policy["disk_reserve_bytes"])
        memory = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        require(int(memory["MemAvailable"].split()[0]) * 1024 >= policy["memory_reserve_bytes"])
        directory = self.root / "configs" / release["config_id"]
        protected(directory, 0, directory=True)
        for name, uid in (("runtime.env", 10001), ("mysql-password", policy["mysql_uid"]),
                          ("mysql-root-password", policy["mysql_uid"])):
            protected(directory / name, uid)
            require((directory / name).stat().st_size > 0)
        # Protect scope: external volumes must preexist with explicit ownership.
        for purpose, name in (("mysql", policy["mysql_volume"]), ("media", policy["media_volume"])):
            info, = json.loads(run(["docker", "volume", "inspect", name]))
            labels = info.get("Labels") or {}
            require(info["Driver"] == "local" and not info.get("Options"))
            require(labels.get("com.daesingo.owner") == policy["project"]
                and labels.get("com.daesingo.purpose") == purpose)
            if not (self.root / "current.json").exists():
                require(release.get("initial_state") == "verified-empty-owned-volumes")
                verify_empty_volume(info)
        # An unrelated container holding either volume must never be adopted.
        for volume in (policy["mysql_volume"], policy["media_volume"]):
            ids = run(["docker", "ps", "-aq", "--filter", "volume=" + volume]).split()
            if ids:
                for info in json.loads(run(["docker", "inspect", *ids])):
                    require(info["Config"].get("Labels", {}).get("com.docker.compose.project") == policy["project"])
        # AWS CLI uses EC2's instance role. No operator/CI credentials are passed.
        groups = json.loads(run(["aws", "logs", "describe-log-groups", "--log-group-name-prefix", policy["log_group"],
            "--region", policy["region"], "--output", "json", "--no-cli-pager"]))["logGroups"]
        require(any(g["logGroupName"] == policy["log_group"] and g.get("retentionInDays") == policy["log_retention_days"] for g in groups))
        password = run(["aws", "ecr", "get-login-password", "--region", policy["region"]])
        # Private Docker config avoids leaving registry credentials on disk.
        run(["docker", "login", "--username", "AWS", "--password-stdin", policy["repository"].split("/")[0]], input=password)
        run(["docker", "pull", "--platform", "linux/amd64", release["image"]], timeout=300)
        info, = json.loads(run(["docker", "image", "inspect", release["image"]]))
        require(info["Architecture"] == "amd64" and info["Os"] == "linux")
        require(info["Config"].get("Labels", {}).get("org.opencontainers.image.revision") == release["revision"])
        self.image_id = info["Id"]
        source = json.loads(run(["docker", "run", "--rm", "--network", "none", "--read-only",
            "--entrypoint", "python", release["image"], "-c",
            "from pathlib import Path; print(Path('/app/compose.yaml').read_text())"]))
        config = production_compose(source, release, policy, directory)
        target = self.root / "release-compose.json"
        atomic_json(target, config)
        self.base = ["docker", "compose", "--project-name", policy["project"], "-f", str(target)]
        self.compose("config", "--quiet")
        # No model duplicate load; full OCR startup is checked on the real Worker.
        self.compose("run", "--rm", "--no-deps", "migrate", "python", "/app/docker/runtime.py", "deploy-config")
        require(shutil.disk_usage(self.root).free >= policy["disk_reserve_bytes"])
        # MySQL remains the RT-13 8.4 line, never upgraded automatically here.
        run(["docker", "image", "inspect", policy["mysql_image"]])


def main(argv=None):
    parser = SafeParser()
    parser.add_argument("operation", choices=("deploy", "rollback"))
    parser.add_argument("--image", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--config-id", required=True)
    try:
        args = parser.parse_args(argv)
        require(os.name == "posix" and os.geteuid() == 0 and os.uname().machine == "x86_64")
        require(bool(re.fullmatch(r"[0-9a-f]{40}", args.revision)))
        require(bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", args.config_id)))
        require(bool(re.fullmatch(r"[0-9]{12}\.dkr\.ecr\.ap-northeast-2\.amazonaws\.com/"
            r"[a-z0-9]+(?:[._/-][a-z0-9]+)*@sha256:[0-9a-f]{64}", args.image)))
        protected(ROOT, 0, directory=True)
        protected(ROOT / "policy.json", 0)
        policy = json.loads((ROOT / "policy.json").read_text())
        validate_policy(policy)
        with operation_lock(ROOT):
            if args.operation == "rollback":
                records = [read_record(ROOT / name) for name in ("current.json", "previous.json")]
                matches = [r for r in records if r and (r["image"], r["revision"], r["config_id"]) ==
                           (args.image, args.revision, args.config_id)]
                require(len(matches) >= 1)
                release = matches[0]
            else:
                approval = ROOT / "approvals" / (args.revision + ".json")
                protected(approval, 0)
                release = json.loads(approval.read_text())
                require((release["image"], release["revision"], release["config_id"]) ==
                        (args.image, args.revision, args.config_id))
                require(isinstance(release.get("rollback_targets"), list) and all(
                    re.fullmatch(r"[0-9a-f]{40}", value) for value in release["rollback_targets"]))
                require(bool(release.get("backup_reference")))
            # Docker auth is operation-owned, removed even on failure.
            import tempfile
            with tempfile.TemporaryDirectory(prefix="docker-", dir=ROOT) as directory:
                os.environ["DOCKER_CONFIG"] = directory
                transition(ROOT, release, args.operation, DockerHost(ROOT, policy))
        print("rt14-host: verified")
        return 0
    except BaseException:
        print("rt14-host: failed_or_unknown (private state requires reconciliation)", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
