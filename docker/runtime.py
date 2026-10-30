"""Small container adapters; credentials never enter argv or environment."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import urllib.error

from daesingo.common.config import DbSettings
from daesingo.common.env import load_env_file


def deployment_config():
    from daesingo.common.config import RuntimeConfig
    from daesingo.recording.factory import RecordingSettings
    from daesingo.worker.bootstrap import _search_config
    values = load_env_file(os.environ["DAESINGO_ENV_FILE"])
    for service in ("api", "worker"):
        config = RuntimeConfig.from_mapping(service, values)
        if config.media_root != Path("/media"):
            raise ValueError("deployment_media_root")
    if (values.get("DAESINGO_RUNTIME_API_TEMP_ROOT") != "/media/api-temp"
            or values.get("DAESINGO_RUNTIME_WORKER_TEMP_ROOT") != "/media/worker-temp"):
        raise ValueError("deployment_temp_roots")
    settings = RecordingSettings.from_mapping(values)
    if settings.profile is None or settings.analysis_limits is None or settings.incident_encoding is None:
        raise ValueError("deployment_recording_incomplete")
    _search_config(values)
    from sqlalchemy.engine import make_url
    url = make_url(values["DAESINGO_RUNTIME_DB_URL"])
    if url.host != "mysql" or url.database != "daesingo" or url.username != "daesingo":
        raise ValueError("deployment_database_target")
    return values, settings


def check_packet(maximum, packet, margin):
    if any(type(v) is not int or v <= 0 for v in (maximum, packet, margin)) or maximum + margin >= packet:
        raise ValueError("deployment_packet_margin")


def deployment_smoke():
    for name in ("live", "ready"):
        with urllib.request.urlopen("http://127.0.0.1:8000/health/" + name, timeout=4) as response:
            if response.status != 200 or json.load(response) != {"status": "ok"}:
                raise ValueError("deployment_health")
    # Read-only representative DB-backed Case route. No media or provider call.
    from uuid import uuid4
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/cases/" + uuid4().hex + "/view", timeout=4):
            raise ValueError("deployment_smoke_expected_missing_case")
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise


def verify_media_tools(manifest=Path("/usr/local/share/daesingo/media.json")):
    """Exact supported release AND the binary pair produced by this image build."""
    try:
        identity = json.loads(manifest.read_text())
        if identity["version"] != "8.1" or set(identity["sha256"]) != {"ffmpeg", "ffprobe"}:
            raise ValueError()
        configurations = []
        for name in ("ffmpeg", "ffprobe"):
            path = shutil.which(name)
            if not path:
                raise ValueError()
            with open(path, "rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != identity["sha256"][name]:
                    raise ValueError()
            result = subprocess.run([path, "-version"], stdin=subprocess.DEVNULL,
                capture_output=True, text=True, timeout=5, check=False)
            lines = result.stdout.splitlines()
            if result.returncode or not lines or not lines[0].startswith(name + " version 8.1 "):
                raise ValueError()
            configuration, = [line for line in lines if line.startswith("configuration: ")]
            configurations.append(configuration)
        if configurations[0] != configurations[1]:
            raise ValueError()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        raise ValueError("media_toolchain_invalid") from None


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args in (["api"], ["worker"], ["media-preflight"]):
        try:
            verify_media_tools()
        except ValueError:
            print("container: media_toolchain_invalid (requires matching pinned ffmpeg/ffprobe 8.1)", file=sys.stderr)
            return 1
        if args == ["media-preflight"]:
            return 0
    try:
        if args == ["deploy-config"]:
            deployment_config()
            return 0
        if len(args) == 2 and args[0] == "deploy-packet":
            values, settings = deployment_config()
            from sqlalchemy import create_engine, text
            engine = create_engine(values["DAESINGO_RUNTIME_DB_URL"], connect_args={"connect_timeout": 5,
                "read_timeout": 5, "write_timeout": 5})
            try:
                with engine.connect() as conn:
                    packet = conn.scalar(text("SELECT @@SESSION.max_allowed_packet"))
                check_packet(settings.analysis_limits.max_bytes, packet, int(args[1]))
            finally:
                engine.dispose()
            return 0
        if args == ["worker-status"]:
            from daesingo.worker.deployment_status import verify
            verify(revision=os.environ["DAESINGO_REVISION"])
            return 0
        if args == ["deploy-smoke"]:
            deployment_smoke()
            return 0
        if args == ["readout-preflight"]:
            from daesingo.worker.readout_runtime import load_production_ocr_engine
            load_production_ocr_engine()
            return 0
        if args == ["migrate"]:
            values = load_env_file(os.environ["DAESINGO_ENV_FILE"])
            settings = DbSettings(url=values.get("DAESINGO_RUNTIME_DB_URL", ""))
            return subprocess.run([sys.executable, "-m", "daesingo.common.db.migrate",
                "--database-url-stdin"], input=settings.url.get_secret_value(), text=True).returncode
        if args == ["ready"]:
            # Caller timeout > B-H3; Compose enforces the outer five-second bound.
            with urllib.request.urlopen("http://127.0.0.1:8000/health/ready", timeout=4) as response:
                return 0 if json.load(response) == {"status": "ok"} else 1
        if args == ["api"]:
            os.execv(sys.executable, [sys.executable, "-m", "daesingo.api", "--revision",
                os.environ.get("DAESINGO_REVISION", "local"), "--host", "0.0.0.0", "--port", "8000"])
        if args == ["worker"]:
            os.execv(sys.executable, [sys.executable, "-m", "daesingo.worker"])
    except BaseException:
        # Do not print exception values (DB URLs, file paths, response contents).
        print("container: operation_failed", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
