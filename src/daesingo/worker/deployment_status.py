"""Opt-in registration evidence from the actual Worker, not a second OCR load.

This is process identity/registration, not an idle heartbeat or job health API.
Active lease/heartbeat observation remains the Runtime DB/log boundary.
"""
import json
import os
from pathlib import Path
import re

PATH = Path("/tmp/daesingo-worker.json")
EXPECTED = frozenset({"HINT_EXTRACT", "COARSE_SEARCH", "FINE_VERIFY", "INCIDENT_CLIP_BUILD",
    "PLATE_READ", "OVERLAY_TIME_READ", "REPORT_VIDEO_EXPORT", "PLATE_IMAGE_EXPORT"})


def process_token(pid):
    # proc comm may contain spaces; starttime is field 22 (index19 after comm).
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]


def publish(registry, revision, path=PATH, *, token=None):
    kinds = set(registry._handlers)
    if kinds != EXPECTED or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("deployment_registry_invalid")
    data = {"pid": os.getpid(), "process_start": process_token(os.getpid()) if token is None else token,
            "revision": revision, "handlers": sorted(kinds)}
    temporary = path.with_suffix(".new")
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def verify(path=PATH, revision=None, *, token=None, pid=1):
    data = json.loads(path.read_text())
    expected_token = process_token(pid) if token is None else token
    if (data.get("pid") != pid or data.get("process_start") != expected_token
            or data.get("revision") != revision or set(data.get("handlers", ())) != EXPECTED):
        raise ValueError("deployment_registry_unavailable")


def clear(path=PATH):
    path.unlink(missing_ok=True)
    path.with_suffix(".new").unlink(missing_ok=True)
