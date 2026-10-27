"""Fail-closed RT-13 local policy checker (source JSON subset or Compose JSON).

This proves structural invariants, not Docker execution or image provenance.
No secret-bearing input or parser exception is printed.
"""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SERVICES = {"api", "worker", "migrate", "mysql"}
LOGGING = {"driver": "local", "options": {"max-size": "20m", "max-file": "5"}}
ENV_PATH = "/run/secrets/runtime.env"


def validate(config: dict, dockerfile: str, dockerignore: str) -> list[str]:
    errors = []
    def require(ok, code):
        if not ok: errors.append(code)
    try:
        services = config.get("services", {})
        require(set(services) == SERVICES, "services")
        require(set(config.get("volumes", {})) == {"mysql_data", "media"}, "volumes")
        for volume in config.get("volumes", {}).values():
            require(not any(k in (volume or {}) for k in ("external", "driver_opts", "driver")), "local_volume")
        images = {services[name].get("image") for name in ("api", "worker", "migrate") if name in services}
        require(images == {"daesingo-rt13:local"}, "same_application_image")
        for name, service in services.items():
            require("env_file" not in service, "no_env_file")
            require(not service.get("tmpfs"), "no_tmpfs")
            # Compose JSON renders an unset ShellCommand as null. Empty string
            # or [] explicitly resets ENTRYPOINT and is still an override.
            require(service.get("entrypoint") is None and not any(k in service
                for k in ("privileged", "network_mode", "volumes_from")), "no_bypass")
            require(service.get("restart", "no") == "no", "no_production_restart")
            require(not service.get("deploy") and service.get("scale", 1) == 1, "single_local_replica")
            require(service.get("logging") == LOGGING, "log_rotation")
            mounts = service.get("volumes", [])
            require(all(isinstance(v, dict) and v.get("type") in {"bind", "volume"} for v in mounts), "mount_type")
            if name == "mysql":
                require(service.get("image") == "mysql:8.4", "mysql_version")
                require(service.get("environment") == {"MYSQL_DATABASE": "daesingo", "MYSQL_USER": "daesingo",
                    "MYSQL_ROOT_PASSWORD_FILE": "/run/secrets/mysql-root-password", "MYSQL_PASSWORD_FILE": "/run/secrets/mysql-password"}, "mysql_file_secrets")
                require(len(mounts) == 3 and mounts[0].get("type") == "volume" and
                    mounts[0].get("source") == "mysql_data" and mounts[0].get("target") == "/var/lib/mysql", "mysql_named_data")
                for target in ("/run/secrets/mysql-root-password", "/run/secrets/mysql-password"):
                    require(any(v.get("type") == "bind" and v.get("target") == target and v.get("read_only") is True
                        and v.get("bind", {}).get("create_host_path") is False for v in mounts), "mysql_secret_mount")
                health = service.get("healthcheck", {})
                require(health.get("test") == ["CMD", "mysqladmin", "ping", "--protocol=tcp", "--host=127.0.0.1", "--silent"] and not health.get("disable"), "mysql_health")
                continue
            require(service.get("user") == "10001:10001", "numeric_identity")
            require(service.get("environment") == {"DAESINGO_ENV_FILE": ENV_PATH}, "path_only_environment")
            require(service.get("command") == ["python", "/app/docker/runtime.py", name], "service_command")
            build = service.get("build", {})
            require(set(build) <= {"context", "args", "dockerfile"} and set(build.get("args", {})) == {"REVISION"}, "build_arguments")
            require(build.get("context") in {".", str(ROOT), ROOT.as_posix()}
                and build.get("dockerfile", "Dockerfile") == "Dockerfile", "application_build_source")
            require(any(v.get("type") == "bind" and v.get("target") == ENV_PATH and v.get("read_only") is True
                and v.get("bind", {}).get("create_host_path") is False for v in mounts), "readonly_runtime_file")
            deps = service.get("depends_on", {})
            dep, condition = ("mysql", "service_healthy") if name == "migrate" else ("migrate", "service_completed_successfully")
            require(deps.get(dep, {}).get("condition") == condition and deps.get(dep, {}).get("required", True) is True, "startup_gate")
            if name in {"api", "worker"}:
                require(len(mounts) == 2 and mounts[0].get("type") == "volume" and mounts[0].get("source") == "media"
                    and mounts[0].get("target") == "/media" and not mounts[0].get("read_only"), "shared_media")
            else:
                require(len(mounts) == 1, "migrate_mounts")
        api = services.get("api", {})
        require(api.get("healthcheck") == {"test": ["CMD", "python", "/app/docker/runtime.py", "ready"],
            "interval": "10s", "timeout": "5s", "retries": 3, "start_period": "10s"}, "ready_baseline")
        require(services.get("worker", {}).get("stop_grace_period") == "30s", "worker_grace")
        require("uv sync --locked --no-dev --extra eval-gemini" in dockerfile, "locked_dependencies")
        require("ffmpeg" in dockerfile and "--no-install-recommends" in dockerfile, "media_tools")
        require(dockerfile.count("FROM python:3.12-slim-bookworm") == 2, "python312")
        require("USER 10001:10001" in dockerfile and not re.search(r"^USER (?!10001:10001$)", dockerfile, re.M), "image_nonroot")
        for line in dockerfile.splitlines():
            if line.startswith("COPY "):
                require(not re.search(r"(?:^|\s)(?:\.|\.env\S*|secrets\S*)(?:\s|$)", line), "no_secret_copy")
            if line.startswith(("ENV ", "ARG ")):
                require(not re.search(r"PASSWORD|TOKEN|API_KEY|DB_URL", line), "no_image_secret")
        require(dockerignore.startswith("**\n") and "!src/**" in dockerignore and "**/.env.*" in dockerignore
            and "**/*.sql" in dockerignore and "**/*.dump" in dockerignore, "allowlist_context")
    except (KeyError, TypeError, AttributeError, IndexError, ValueError):
        errors.append("invalid_structure")
    return sorted(set(errors))


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        config = json.loads(Path(args[0] if args else ROOT / "compose.yaml").read_text(encoding="utf-8"))
        errors = validate(config, (ROOT / "Dockerfile").read_text(), (ROOT / ".dockerignore").read_text())
    except (OSError, ValueError):
        errors = ["invalid_input"]
    print("Compose policy " + ("FAIL: " + ",".join(errors) if errors else "PASS (structural only)"))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
