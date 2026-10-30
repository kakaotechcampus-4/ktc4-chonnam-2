"""Opt-in destructive ONLY to its generated project: RT-13 Docker acceptance.

Linux Docker engine + root on the HOST are required to provision 0400 files
owned by container UIDs without broadening permissions. Apps run as 10001.
No production credentials or provider calls. Results are stage evidence only;
absence of Docker is failure, never skip/pass. No docker system/volume prune.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def assert_no_secrets(value, secret_values):
    text = json.dumps(value, ensure_ascii=False)
    if any(secret and secret in text for secret in secret_values):
        raise ValueError("secret_disclosure")


def cleanup_command(project, files):
    if not re.fullmatch(r"daesingo-rt13-smoke-[0-9a-f]{12}", project):
        raise ValueError("unsafe_project")
    return ["docker", "compose", "--project-name", project,
        *[arg for path in files for arg in ("-f", str(path))], "down", "--volumes", "--remove-orphans"]


def compose_command(project, files):
    return cleanup_command(project, files)[:-3]


def record_failure(report, stage, error):
    report["result"] = "FAIL"
    # Cleanup errors must not replace the original operation's failure.
    report.setdefault("failed_stage", stage)
    report.setdefault("failure_type", type(error).__name__)


def cleanup_resources(project, files, image, run):
    down = cleanup_command(project, files)
    if image != project + ":local":
        raise ValueError("unsafe_image")
    failures, remaining = [], []
    operations = [("down", down),
        ("containers", ["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=" + project]),
        ("volumes", ["docker", "volume", "ls", "-q", "--filter", "label=com.docker.compose.project=" + project]),
        ("networks", ["docker", "network", "ls", "-q", "--filter", "label=com.docker.compose.project=" + project]),
        ("image", ["docker", "image", "rm", image])]
    for operation, command in operations:
        try:
            result = run(command, check=False, timeout=120)
            if result.returncode:
                failures.append({"operation": operation, "failure_type": "NonzeroExit",
                    "exit_code": result.returncode})
            elif operation in {"containers", "volumes", "networks"} and result.stdout.strip():
                remaining.append(operation)
        except BaseException as error:
            # Best effort for EVERY owned resource; no exception/command text.
            failures.append({"operation": operation, "failure_type": type(error).__name__})
    return {"result": "FAIL" if failures or remaining else "PASS",
        "failures": failures, "remaining": remaining}


def wait_for(callback, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            value = callback()
            if value: return value
        except (OSError, ValueError, KeyError, AssertionError):
            pass
        time.sleep(.5)
    raise TimeoutError("smoke_deadline")


def run_smoke(evidence, *, after_persistence=None):
    from check_compose import validate_rendered
    project = "daesingo-rt13-smoke-" + secrets.token_hex(6)
    image = project + ":local"
    report = {"project": project, "stages": [], "result": "FAIL", "cleanup": "not_needed"}
    secret_values = [secrets.token_hex(24) for _ in range(3)]
    env = {**os.environ, "COMPOSE_DISABLE_ENV_FILE": "1"}
    stage = "docker_preflight"
    touched = False
    def record(name, **fields):
        assert_no_secrets(fields, secret_values)
        report["stages"].append({"name": name, **fields})
        print("compose smoke: " + name, flush=True)
    def run(args, *, check=True, timeout=120):
        result = subprocess.run(args, env=env, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        assert_no_secrets([result.stdout, result.stderr], secret_values)
        if check and result.returncode:
            raise RuntimeError("docker_command_failed")
        return result
    try:
        if not shutil.which("docker"):
            raise RuntimeError("docker_unavailable")
        run(["docker", "version"])
        run(["docker", "compose", "version"])
        if os.name != "posix" or os.geteuid() != 0:
            raise RuntimeError("linux_host_root_required_for_file_ownership")
        # No externally supplied project/name/volumes. Refuse accidental collision.
        assert not run(["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=" + project]).stdout.strip()
        assert not run(["docker", "volume", "ls", "-q", "--filter", "label=com.docker.compose.project=" + project]).stdout.strip()
        assert not run(["docker", "network", "ls", "-q", "--filter", "label=com.docker.compose.project=" + project]).stdout.strip()
        # Discover upstream MySQL's numeric owner rather than assume 999/1000.
        ids = run(["docker", "run", "--rm", "--entrypoint", "sh", "mysql:8.4", "-c", "id -u mysql; id -g mysql"]).stdout.split()
        mysql_uid, mysql_gid = map(int, ids)
        with tempfile.TemporaryDirectory(prefix=project + "-") as directory:
            root = Path(directory)
            def protected(name, text, uid, gid):
                path = root / name
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as stream: stream.write(text)
                os.chown(path, uid, gid)
                path.chmod(0o400)
                return str(path)
            env["DAESINGO_RUNTIME_ENV_FILE"] = protected("runtime.env", "\n".join([
                "DAESINGO_RUNTIME_DB_URL=mysql+pymysql://daesingo:" + secret_values[0] + "@mysql/daesingo",
                "DAESINGO_RUNTIME_MEDIA_ROOT=/media", "DAESINGO_RUNTIME_API_TEMP_ROOT=/media/api-temp",
                "DAESINGO_RUNTIME_WORKER_TEMP_ROOT=/media/worker-temp", "GEMINI_API_KEY=" + secret_values[2]]), 10001, 10001)
            env["DAESINGO_MYSQL_PASSWORD_FILE"] = protected("mysql-password", secret_values[0], mysql_uid, mysql_gid)
            env["DAESINGO_MYSQL_ROOT_PASSWORD_FILE"] = protected("mysql-root-password", secret_values[1], mysql_uid, mysql_gid)
            env["DAESINGO_API_PORT"] = "0"  # Docker chooses a free loopback-only port.
            env["DAESINGO_REVISION"] = "compose-smoke"
            overlay = root / "override.json"
            overlay.write_text(json.dumps({"services": {name: {"image": image} for name in ("api", "worker", "migrate")}}))
            files = [ROOT / "compose.yaml", overlay]
            base = compose_command(project, files)
            def compose(*args, **kwargs): return run([*base, *args], **kwargs)
            probe_path = str((ROOT / "tests/deploy/compose_probe.py").resolve())
            probe_mount = {"type": "bind", "source": probe_path, "target": "/opt/rt13-probe.py", "read_only": True}
            media_mount = {"type": "bind", "source": str((ROOT / "tests/deploy/media_acceptance.py").resolve()),
                "target": "/opt/media-acceptance.py", "read_only": True}
            # Probe runs in API/worker containers; it is a test mount, not image content.
            overlay.write_text(json.dumps({"services": {name: {"image": image,
                **({"volumes": [probe_mount, media_mount]} if name in {"api", "worker"} else {})} for name in ("api", "worker", "migrate")}}))
            try:
                stage = "compose_config"
                config = json.loads(compose("config", "--format", "json").stdout)
                # Validate the production file separately; test overlay adds only probe/image/ephemeral port.
                production = json.loads(run(["docker", "compose", "-f", str(ROOT / "compose.yaml"), "config", "--format", "json"]).stdout)
                assert not validate_rendered(production, json.loads((ROOT / "compose.yaml").read_text()),
                    (ROOT / "Dockerfile").read_text(), (ROOT / ".dockerignore").read_text())
                record(stage)
                stage = "clean_build"
                touched = True
                report["cleanup"] = "pending"
                compose("build", "--no-cache", "api", timeout=900)
                record(stage)
                # Negative control uses a fresh project state, no DDL yet.
                stage = "migration_failure_blocks_startup"
                fail = root / "failure.json"
                fail.write_text(json.dumps({"services": {"migrate": {"command": ["python", "-c", "raise SystemExit(7)"]}}}))
                failure = run([*base, "-f", str(fail), "up", "-d", "api", "worker"], check=False, timeout=240)
                assert failure.returncode != 0
                for name in ("api", "worker"):
                    cid = compose("ps", "--all", "--quiet", name).stdout.strip()
                    if cid: assert json.loads(run(["docker", "inspect", cid]).stdout)[0]["State"]["Status"] == "created"
                compose("down", "--volumes", "--remove-orphans")
                record(stage, exit_code=failure.returncode)
                stage = "clean_up_migration_ready"
                compose("up", "-d", "api", "worker", timeout=240)
                def inspect(name):
                    cid = compose("ps", "--all", "--quiet", name).stdout.strip()
                    return json.loads(run(["docker", "inspect", cid]).stdout)[0]
                wait_for(lambda: inspect("mysql")["State"].get("Health", {}).get("Status") == "healthy", 180)
                migration = inspect("migrate")
                assert migration["State"]["Status"] == "exited" and migration["State"]["ExitCode"] == 0
                wait_for(lambda: inspect("api")["State"].get("Health", {}).get("Status") == "healthy", 120)
                record(stage, migration_exit=0, mysql="healthy", api="healthy")
                stage = "pinned_media_materialization"
                for name in ("api", "worker"):
                    compose("exec", "-T", name, "python", "/app/docker/runtime.py", "media-preflight")
                media = json.loads(compose("exec", "-T", "worker", "python", "/opt/media-acceptance.py").stdout)
                assert media == {"mp4": "PASS", "avi": "PASS", "mkv": "PASS", "mp4_chain_analysis_incident": "PASS"}
                record(stage, toolchain="8.1", materialization=media)
                port = compose("port", "api", "8000").stdout.strip().rsplit(":", 1)[1]
                def http(path, body=None, content_type="application/json"):
                    data = json.dumps(body).encode() if isinstance(body, dict) else body
                    request = urllib.request.Request("http://127.0.0.1:" + port + path, data=data,
                        headers={"Content-Type": content_type}, method="POST" if body is not None else "GET")
                    with urllib.request.urlopen(request, timeout=15) as response:
                        return response.status, json.load(response)
                def probe(name, mode):
                    output = compose("exec", "-T", name, "python", "/opt/rt13-probe.py", mode).stdout
                    return json.loads(output.strip().splitlines()[-1]) if mode != "seed" else None
                stage = "cross_container_media_identity"
                identities = [probe(name, "identity") for name in ("api", "worker")]
                assert all(i["uid"] == i["gid"] == 10001 and i["media"] == "/media" and i["same_device"] and i["spool"] == "/tmp" for i in identities)
                video = base64.b64decode(probe("worker", "media")["bytes"])
                digest = hashlib.sha256(video).hexdigest()
                status, created = http("/cases", {})
                assert status == 201
                case = created["case_id"]
                multipart = b'--rt13\r\nContent-Disposition: form-data; name="file"; filename="20260620_141956_EVT_1.avi"\r\nContent-Type: video/x-msvideo\r\n\r\n' + video + b'\r\n--rt13--\r\n'
                status, uploaded = http("/cases/" + case + "/sources", multipart, "multipart/form-data; boundary=rt13")
                assert status == 201
                shared = probe("worker", "files")
                assert digest in shared.values() and shared == probe("api", "files")
                record(stage, identities=identities, shared_hashes=shared)
                stage = "command_view"
                status, accepted = http("/cases/" + case + "/commands", {"case_id": case,
                    "expected_case_rev": uploaded["case_view"]["case_rev"], "kind": "START_ANALYSIS", "payload": {"description": ""}})
                assert status == 202
                wait_for(lambda: not http("/cases/" + case + "/view")[1]["running_jobs"], 90)
                record(stage, command_status=status, view_status=200)
                stage = "kill_stale_attempt2"
                compose("stop", "worker")
                compose("exec", "-T", "api", "python", "/opt/rt13-probe.py", "seed")
                block = root / "block.json"
                block.write_text(json.dumps({"services": {"worker": {"command": ["python", "/opt/rt13-probe.py", "block"]}}}))
                run([*base, "-f", str(block), "up", "-d", "--no-deps", "--force-recreate", "worker"])
                wait_for(lambda: probe("api", "rows") == [{"attempt": 1, "status": "RUNNING"}], 45)
                compose("kill", "-s", "SIGKILL", "worker")
                compose("up", "-d", "--no-deps", "--force-recreate", "worker")
                expected = [{"attempt": 1, "status": "STALE"}, {"attempt": 2, "status": "FAILED"}]
                wait_for(lambda: probe("api", "rows") == expected, 180)
                record(stage, rows=expected)
                stage = "inspect_secrets_settings"
                containers = {name: inspect(name) for name in ("api", "worker", "migrate", "mysql")}
                assert containers["api"]["Id"] != containers["worker"]["Id"]
                assert containers["api"]["Image"] == containers["worker"]["Image"] == containers["migrate"]["Image"]
                for name, container in containers.items():
                    assert_no_secrets(container, secret_values)
                    assert container["HostConfig"]["LogConfig"] == {"Type": "local", "Config": {"max-size": "20m", "max-file": "5"}}
                    assert not container["HostConfig"].get("Tmpfs")
                    assert not any(m["Type"] == "tmpfs" for m in container["Mounts"])
                    run(["docker", "history", "--no-trunc", container["Image"]])
                    compose("logs", "--no-color", name)
                health = containers["api"]["Config"]["Healthcheck"]
                assert [health[k] for k in ("Interval", "Timeout", "Retries", "StartPeriod")] == [10000000000, 5000000000, 3, 10000000000]
                assert containers["worker"]["Config"]["StopTimeout"] == 30
                for name in ("api", "worker", "migrate"):
                    assert containers[name]["Config"]["User"] == "10001:10001"
                    assert next(m for m in containers[name]["Mounts"] if m["Destination"] == "/run/secrets/runtime.env")["RW"] is False
                def volume(name, target): return next(m for m in containers[name]["Mounts"] if m["Destination"] == target)
                data, media = volume("mysql", "/var/lib/mysql"), volume("api", "/media")
                assert data["Type"] == media["Type"] == "volume" and data["Name"] != media["Name"]
                assert media["Name"] == volume("worker", "/media")["Name"]
                record(stage, uid_gid="10001:10001", tmpfs=False, rotation="20m x 5", health=health, stop_grace=30)
                stage = "recreate_persistence"
                compose("down")  # Keep named volumes for this assertion only.
                compose("up", "-d", "api", "worker", timeout=240)
                wait_for(lambda: inspect("api")["State"].get("Health", {}).get("Status") == "healthy", 120)
                assert probe("worker", "files") == shared and probe("api", "rows") == expected
                containers = {name: inspect(name) for name in ("api", "worker", "migrate", "mysql")}
                assert volume("mysql", "/var/lib/mysql")["Name"] == data["Name"]
                assert volume("worker", "/media")["Name"] == media["Name"]
                record(stage, mysql_rows=expected, media_hashes=shared)
                if after_persistence is not None:
                    stage = "logical_backup_restore"
                    after_persistence({"project": project, "root": root, "base": base,
                        "compose": compose, "run": run, "probe": probe, "http": http,
                        "inspect": inspect, "env": env, "record": record, "report": report,
                        "secrets": secret_values, "shared": shared, "case": case})
                report["result"] = "PASS"
            except BaseException as error:
                record_failure(report, stage, error)
            finally:
                # Execute while secret source paths/override files still exist.
                if touched:
                    report["cleanup"] = "FAIL"
                    cleanup = cleanup_resources(project, files, image, run)
                    report["cleanup"] = cleanup["result"]
                    report["cleanup_details"] = cleanup
                    if cleanup["result"] != "PASS":
                        record_failure(report, "cleanup", RuntimeError())
    except BaseException as error:
        # Only exception TYPE is safe; original command output/values stay private.
        record_failure(report, stage, error)
    finally:
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("compose smoke: " + report["result"] + "; cleanup=" + report["cleanup"], flush=True)
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    raise SystemExit(run_smoke(parser.parse_args().evidence))
