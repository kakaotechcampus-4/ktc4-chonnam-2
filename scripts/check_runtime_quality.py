"""Same locked Runtime lint/type gate on developer machines and CI.

Both supported OS branches are analyzed; no imports or providers are executed.
"""
from pathlib import Path
import os
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("src/daesingo/common", "src/daesingo/api", "src/daesingo/worker", "migrations/runtime")


def main() -> int:
    if any(not (ROOT / path).is_dir() for path in TARGETS):
        print("Runtime quality target missing", file=sys.stderr)
        return 1
    commands = [
        [sys.executable, "-m", "ruff", "check", "--no-cache", *TARGETS],
        *([sys.executable, "-m", "mypy", "--platform", platform,
           "--no-incremental", "--cache-dir", os.devnull]
          for platform in ("linux", "win32")),
    ]
    failed = False
    for command in commands:
        print("+ " + " ".join(command[1:]), flush=True)
        result = subprocess.run(command, cwd=ROOT, check=False)
        failed = failed or result.returncode != 0
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
