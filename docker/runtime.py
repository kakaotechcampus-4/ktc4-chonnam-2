"""Small container adapters; credentials never enter argv or environment."""
import json
import os
import subprocess
import sys
import urllib.request

from daesingo.common.config import DbSettings
from daesingo.common.env import load_env_file


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
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
