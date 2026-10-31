"""RT-13 accepted configuration and deliberate unsafe mutations."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def bundle():
    for name in ("compose.yaml", "Dockerfile", ".dockerignore", "scripts/check_compose.py"):
        assert (ROOT / name).is_file(), f"RT-13 bundle missing: {name}"
    spec = importlib.util.spec_from_file_location("compose_check", ROOT / "scripts/check_compose.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return (module.validate, json.loads((ROOT / "compose.yaml").read_text()),
            (ROOT / "Dockerfile").read_text(), (ROOT / ".dockerignore").read_text())


def test_repository_bundle_matches_owner_approval():
    validate, config, dockerfile, ignore = bundle()
    assert validate(config, dockerfile, ignore) == []


def test_image_pins_verified_media_source_and_keeps_build_tools_out_of_runtime():
    _, _, dockerfile, _ = bundle()
    assert "https://ffmpeg.org/releases/ffmpeg-8.1.tar.xz" in dockerfile
    assert "b072aed6871998cce9b36e7774033105ca29e33632be5b6347f3206898e0756a" in dockerfile
    assert "sha256sum -c -" in dockerfile
    assert "snapshot.debian.org/archive/debian/20261027T000000Z" in dockerfile
    runtime = dockerfile.split(" AS runtime\n", 1)[1]
    assert "COPY --from=media-build /opt/media/bin/ /usr/local/bin/" in runtime
    assert "build-essential" not in runtime and "curl" not in runtime
    assert "media-preflight" in runtime


def test_mysql_health_waits_for_tcp_not_temporary_init_socket():
    _, config, _, _ = bundle()
    command = config["services"]["mysql"]["healthcheck"]["test"]
    assert "--protocol=tcp" in command and "--host=127.0.0.1" in command


def test_resolved_compose_null_entrypoint_preserves_image_default():
    validate, config, dockerfile, ignore = bundle()
    for service in config["services"].values():
        service["entrypoint"] = None
    assert validate(config, dockerfile, ignore) == []


@pytest.mark.parametrize("change", [None, "source_missing", "source_true", "rendered_true", "unknown_mount"])
def test_rendered_bind_false_omission_requires_valid_explicit_source(change):
    _, source, dockerfile, ignore = bundle()
    spec = importlib.util.spec_from_file_location("compose_check", ROOT / "scripts/check_compose.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rendered = deepcopy(source)
    for service in rendered["services"].values():
        for mount in service["volumes"]:
            if mount["type"] == "bind": mount["bind"] = {}
    original = source["services"]["api"]["volumes"][1]
    resolved = rendered["services"]["api"]["volumes"][1]
    if change == "source_missing": original["bind"] = {}
    elif change == "source_true": original["bind"]["create_host_path"] = True
    elif change == "rendered_true": resolved["bind"]["create_host_path"] = True
    elif change == "unknown_mount": resolved["target"] = "/unknown"
    errors = module.validate_rendered(rendered, source, dockerfile, ignore)
    assert bool(errors) is (change is not None)
    assert resolved["bind"] == ({"create_host_path": True} if change == "rendered_true" else {})


@pytest.mark.parametrize("entrypoint", [[], "", ["sh", "-c", "echo bypass"]])
def test_entrypoint_reset_or_override_remains_rejected(entrypoint):
    validate, config, dockerfile, ignore = bundle()
    config["services"]["api"]["entrypoint"] = entrypoint
    assert validate(config, dockerfile, ignore)


def mutate(config, case):
    services = config["services"]
    api, worker, migrate, mysql = (services[n] for n in ("api", "worker", "migrate", "mysql"))
    if case == "different_image": worker["image"] = "other:local"
    elif case == "migration_started": api["depends_on"]["migrate"]["condition"] = "service_started"
    elif case == "migration_optional": worker["depends_on"]["migrate"]["required"] = False
    elif case == "migration_dependency_missing": del api["depends_on"]["migrate"]
    elif case == "mysql_dependency_missing": del migrate["depends_on"]["mysql"]
    elif case == "secret_env": api["environment"]["GEMINI_API_KEY"] = "private-canary"
    elif case == "secret_env_file": worker["env_file"] = [".env"]
    elif case == "secret_command": migrate["command"].append("private-canary")
    elif case == "secret_build_arg": api["build"]["args"]["TOKEN"] = "private-canary"
    elif case == "different_build_context": worker["build"]["context"] = "other"
    elif case == "different_dockerfile": worker["build"]["dockerfile"] = "Otherfile"
    elif case == "worker_replicas": worker["deploy"] = {"replicas": 2}
    elif case == "api_scale": api["scale"] = 2
    elif case == "mysql_layer": mysql["volumes"] = []
    elif case == "mysql_bind": mysql["volumes"][0]["type"] = "bind"
    elif case == "same_volume": mysql["volumes"][0]["source"] = "media"
    elif case == "media_path": worker["volumes"][0]["target"] = "/other"
    elif case == "media_readonly": worker["volumes"][0]["read_only"] = True
    elif case == "uid": worker["user"] = "10002:10001"
    elif case == "root": api["user"] = worker["user"] = "0:0"
    elif case == "spool_tmpfs": api["tmpfs"] = ["/tmp"]
    elif case == "media_tmpfs": worker["volumes"].append({"type": "tmpfs", "target": "/media/staging"})
    elif case == "writable_secret": api["volumes"][1]["read_only"] = False
    elif case == "secret_missing": worker["volumes"].pop()
    elif case == "timeout_budget": api["healthcheck"]["timeout"] = "3s"
    elif case == "timeout_unapproved": api["healthcheck"]["timeout"] = "6s"
    elif case == "interval": api["healthcheck"]["interval"] = "11s"
    elif case == "retries": api["healthcheck"]["retries"] = 4
    elif case == "start_period": api["healthcheck"]["start_period"] = "11s"
    elif case == "health_disabled": api["healthcheck"]["disable"] = True
    elif case == "grace_missing": del worker["stop_grace_period"]
    elif case == "grace_changed": worker["stop_grace_period"] = "60s"
    elif case == "rotation": del mysql["logging"]
    elif case == "rotation_changed": api["logging"]["options"]["max-file"] = "6"
    elif case.startswith("missing_service_"): del services[case.removeprefix("missing_service_")]
    elif case == "missing_volume": del config["volumes"]["media"]
    elif case == "missing_healthcheck": del api["healthcheck"]
    elif case == "override_entrypoint": api["entrypoint"] = ["sh", "-c", "echo bypass"]
    elif case == "production_restart": worker["restart"] = "always"
    else: raise AssertionError(case)


@pytest.mark.parametrize("case", [
    "different_image", "migration_started", "migration_optional", "migration_dependency_missing",
    "mysql_dependency_missing", "secret_env", "secret_env_file", "secret_command", "secret_build_arg",
    "different_build_context", "different_dockerfile", "worker_replicas", "api_scale",
    "mysql_layer", "mysql_bind", "same_volume", "media_path", "media_readonly", "uid", "root",
    "spool_tmpfs", "media_tmpfs", "writable_secret", "secret_missing", "timeout_budget",
    "timeout_unapproved", "interval", "retries", "start_period", "health_disabled",
    "grace_missing", "grace_changed", "rotation", "rotation_changed", "missing_service_api",
    "missing_service_worker", "missing_service_migrate", "missing_service_mysql", "missing_volume",
    "missing_healthcheck", "override_entrypoint", "production_restart",
])
def test_unsafe_compose_is_rejected(case):
    validate, original, dockerfile, ignore = bundle()
    config = deepcopy(original)
    mutate(config, case)
    assert validate(config, dockerfile, ignore), f"unsafe mutation escaped: {case}"


@pytest.mark.parametrize("case", ["root", "unlocked", "no_ffmpeg", "copy_secrets", "secret_env", "wide_context"])
def test_unsafe_image_is_rejected(case):
    validate, config, dockerfile, ignore = bundle()
    if case == "root": dockerfile = dockerfile.replace("USER 10001:10001", "USER root")
    elif case == "unlocked": dockerfile = dockerfile.replace("uv sync --locked", "uv sync")
    elif case == "no_ffmpeg": dockerfile = dockerfile.replace("ffmpeg", "curl")
    elif case == "copy_secrets": dockerfile += "\nCOPY .env /app/.env\n"
    elif case == "secret_env": dockerfile += "\nENV GEMINI_API_KEY=private-canary\n"
    else: ignore = ""
    assert validate(config, dockerfile, ignore)
