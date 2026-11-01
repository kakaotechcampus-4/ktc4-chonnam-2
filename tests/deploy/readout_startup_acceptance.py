"""Mutate only a disposable container, then test the real default Worker as UID10001."""
from importlib.metadata import distribution
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from daesingo.worker.readout_runtime import CACHE_ROOT


def main(problem):
    assert os.getuid() == 0
    if problem == "dependency":
        metadata = Path(distribution("paddleocr")._path)
        shutil.rmtree(metadata)
    elif problem == "cache":
        (CACHE_ROOT / "models.json").unlink()
    elif problem == "permission":
        (CACHE_ROOT / "official_models" / "PP-OCRv5_mobile_det" / "inference.pdiparams").chmod(0)
    else:
        raise ValueError()
    with TemporaryDirectory(prefix="readout-startup-") as directory:
        root = Path(directory)
        root.chmod(0o755)
        values = dict(DAESINGO_RUNTIME_DB_URL="mysql+pymysql://offline@127.0.0.1:1/test",
            DAESINGO_RUNTIME_MEDIA_ROOT="/media", DAESINGO_RUNTIME_WORKER_TEMP_ROOT="/media/worker-temp",
            GEMINI_API_KEY="offline-credential-canary")
        env_file = root / "runtime.env"
        env_file.write_text("\n".join(f"{key}={value}" for key, value in values.items()))
        env_file.chmod(0o644)
        # subprocess user/group performs the privilege drop before Python starts.
        result = subprocess.run([sys.executable, "-m", "daesingo.worker"],
            user=10001, group=10001, extra_groups=(), capture_output=True, text=True, timeout=60,
            env={**os.environ, "DAESINGO_ENV_FILE": str(env_file)})
        assert result.returncode == 1
        assert result.stderr == ""
        events = [json.loads(line)["event"] for line in result.stdout.splitlines()]
        assert "runtime.worker.failed" in events
        for token in ("Traceback", "offline-credential-canary", str(CACHE_ROOT), "PP-OCRv5", str(root)):
            assert token not in result.stdout + result.stderr
    return {problem: "PASS", "worker_exit": 1, "uid": 10001}


if __name__ == "__main__":
    try:
        print(json.dumps(main(sys.argv[1]), sort_keys=True))
    except BaseException:
        print("readout startup acceptance: FAIL", file=sys.stderr)
        raise SystemExit(1)
