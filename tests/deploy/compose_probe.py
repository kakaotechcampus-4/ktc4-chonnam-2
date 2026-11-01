"""TEST ONLY: mounted by the isolated Compose smoke, never copied to image.

Uses the existing queue/worker lifecycle; blocking handler is only a kill barrier.
Production defaults (lease, sweep, backoff and grace) remain unchanged.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from threading import Event

from daesingo.common.db import create_worker_engine
from daesingo.worker.bootstrap import bootstrap


def source_snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root / "source").rglob("*") if p.is_file()}


def main():
    mode = sys.argv[1]
    if mode == "media":
        path = Path("/media/smoke-input.avi")
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i",
            "color=c=red:s=64x48:r=10:d=1", "-c:v", "mpeg4", "-pix_fmt", "yuv420p", str(path)], check=True)
        print(json.dumps({"bytes": base64.b64encode(path.read_bytes()).decode()}))
        return
    if mode == "files":
        print(json.dumps(source_snapshot(Path("/media"))))
        return
    if mode == "identity":
        from daesingo.common.env import load_env_file
        values = load_env_file(os.environ["DAESINGO_ENV_FILE"])
        import tempfile
        root = Path(values["DAESINGO_RUNTIME_MEDIA_ROOT"])
        staging = root / "staging"
        staging.mkdir(exist_ok=True)
        print(json.dumps({"uid": os.getuid(), "gid": os.getgid(), "media": str(root),
            "same_device": root.stat().st_dev == staging.stat().st_dev,
            "spool": tempfile.gettempdir(), "temp": values["DAESINGO_RUNTIME_WORKER_TEMP_ROOT"]}))
        return
    startup = bootstrap(revision="compose-smoke")
    engine = create_worker_engine(startup.config.db)
    try:
        if mode == "seed":
            from daesingo.common.jobs.repository import enqueue
            with engine.begin() as conn:
                enqueue(conn, [{"job_id": "compose-smoke-job", "case_id": "compose-smoke-case",
                    "kind": "COMPOSE_SMOKE"}], "compose-smoke")
        elif mode == "rows":
            with engine.connect() as conn:
                rows = conn.exec_driver_sql("SELECT attempt,status FROM job_execution WHERE job_id=%s ORDER BY attempt",
                    ("compose-smoke-job",)).mappings().all()
            print(json.dumps([dict(r) for r in rows]))
        elif mode == "block":
            from daesingo.worker.composition import compose_worker
            from daesingo.worker.registry import KindRegistry
            from daesingo.common.jobs.execution import HandlerResult
            stop = Event()
            signal.signal(signal.SIGTERM, lambda *args: stop.set())
            def block(context):
                Event().wait()  # Docker SIGKILL ends this process, including its heartbeat.
                return HandlerResult()
            compose_worker(engine=engine, startup=startup, stop=stop,
                registry=KindRegistry({"COMPOSE_SMOKE": block})).run()
        else:
            raise ValueError("invalid mode")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
