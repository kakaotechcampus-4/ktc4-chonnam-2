"""Build-only model fetch; the runtime receives artifacts, never downloader caches."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

from daesingo.worker.readout_runtime import (
    CACHE_ROOT, MODEL_NAMES, create_ocr_engine, quiet_ocr_startup, warm_ocr_engine,
)


def main():
    with quiet_ocr_startup():
        engine = create_ocr_engine()
        warm_ocr_engine(engine)
        output = Path("/opt/readout-cache")
        manifest = {}
        for name in MODEL_NAMES:
            source = CACHE_ROOT / "official_models" / name
            destination = output / "official_models" / name
            destination.mkdir(parents=True)
            manifest[name] = {}
            for filename in ("inference.json", "inference.pdiparams", "inference.yml"):
                shutil.copyfile(source / filename, destination / filename)
                with (destination / filename).open("rb") as stream:
                    manifest[name][filename] = hashlib.file_digest(stream, "sha256").hexdigest()
        (output / "models.json").write_text(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        print("container: operation_failed", file=sys.stderr)
        raise SystemExit(1)
