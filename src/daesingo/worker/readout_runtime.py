"""Offline production OCR preflight. Importing this module needs no Paddle stack."""
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path


MODEL_NAMES = ("PP-OCRv5_mobile_det", "korean_PP-OCRv5_mobile_rec")
CACHE_ROOT = Path("/opt/daesingo/paddlex")
DEPENDENCIES = {"paddleocr": "3.7.0", "paddlepaddle": "3.3.1",
                "opencv-contrib-python": "4.10.0.84"}


@contextmanager
def quiet_ocr_startup():
    """Third-party/native diagnostics may contain cache paths. Startup is serial."""
    with open(os.devnull, "w") as sink:
        saved = [os.dup(fd) for fd in (1, 2)]
        try:
            for fd in (1, 2):
                os.dup2(sink.fileno(), fd)
            with redirect_stdout(sink), redirect_stderr(sink):
                yield
        finally:
            for fd, original in zip((1, 2), saved):
                os.dup2(original, fd)
                os.close(original)


def verify_model_cache(root):
    """Hash/read every required artifact as the runtime UID, before Paddle import."""
    root = Path(root)
    manifest = json.loads((root / "models.json").read_text())
    if set(manifest) != set(MODEL_NAMES):
        raise ValueError("invalid OCR cache")
    for name in MODEL_NAMES:
        files = manifest[name]
        if not isinstance(files, dict) or not {"inference.json", "inference.pdiparams", "inference.yml"} <= files.keys():
            raise ValueError("incomplete OCR cache")
        for filename, digest in files.items():
            if not isinstance(filename, str) or Path(filename).name != filename or filename in (".", ".."):
                raise ValueError("invalid OCR artifact")
            path = root / "official_models" / name / filename
            if path.is_symlink():
                raise ValueError("invalid OCR artifact")
            with path.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                    raise ValueError("invalid OCR artifact")


def create_ocr_engine(*, root=None):
    """Names remain fixed; explicit local directories bypass model downloading."""
    from paddleocr import PaddleOCR
    options = dict(lang="korean", text_detection_model_name=MODEL_NAMES[0],
        text_recognition_model_name=MODEL_NAMES[1], device="cpu", enable_mkldnn=False,
        use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False)
    if root is not None:
        options.update(text_detection_model_dir=str(Path(root) / "official_models" / MODEL_NAMES[0]),
                       text_recognition_model_dir=str(Path(root) / "official_models" / MODEL_NAMES[1]))
    return PaddleOCR(**options)


def warm_ocr_engine(engine):
    import numpy as np
    # Execute inference before claims, including lazy native kernel initialization.
    list(engine.predict(np.full((64, 256, 3), 255, dtype=np.uint8)))


def load_production_ocr_engine():
    """Called only by production main/image preflight; callers sanitize failures."""
    with quiet_ocr_startup():
        for package, expected in DEPENDENCIES.items():
            if version(package) != expected:
                raise ValueError("OCR dependency version mismatch")
        verify_model_cache(CACHE_ROOT)
        os.environ["PADDLE_PDX_CACHE_HOME"] = str(CACHE_ROOT)
        os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
        engine = create_ocr_engine(root=CACHE_ROOT)
        warm_ocr_engine(engine)
        return engine
