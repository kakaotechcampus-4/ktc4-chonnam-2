"""Public bundle identity. No private config is ever copied into releases."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys


class ArtifactError(Exception):
    pass


def require(ok):
    if not ok:
        raise ArtifactError("web_artifact_invalid")


def verify_web(web, revision):
    """Verify the entire file set, not merely the mutable version marker."""
    require(revision == "local" or bool(re.fullmatch(r"[0-9a-f]{40}", revision)))
    require(web.is_dir() and not web.is_symlink())
    files = {}
    for path in web.rglob("*"):
        mode = path.lstat().st_mode
        require(stat.S_ISDIR(mode) or stat.S_ISREG(mode))
        if stat.S_ISREG(mode):
            files[path.relative_to(web).as_posix()] = path
    require({"manifest.json", "version.json", "index.html"} <= files.keys())
    manifest_bytes = files.pop("manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    require(set(manifest) == {"revision", "files"} and manifest["revision"] == revision)
    expected = manifest["files"]
    require(isinstance(expected, dict) and set(expected) == set(files))
    for name, digest in expected.items():
        path = PurePosixPath(name)
        require(not path.is_absolute() and ".." not in path.parts and "\\" not in name)
        require(isinstance(digest, str) and bool(re.fullmatch(r"[0-9a-f]{64}", digest)))
        require(hashlib.sha256(files[name].read_bytes()).hexdigest() == digest)
    require(json.loads(files["version.json"].read_bytes()) == {"revision": revision})
    require(files["index.html"].stat().st_size > 0)
    return hashlib.sha256(manifest_bytes).hexdigest()


def sync_directory(path):
    if os.name == "posix":
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def main():
    try:
        require(len(sys.argv) == 3)
        verify_web(Path(sys.argv[1]), sys.argv[2])
        print("rt14-web: verified")
        return 0
    except BaseException:
        print("rt14-web: failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
