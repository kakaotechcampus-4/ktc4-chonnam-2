"""The ordinary module entrypoint must register real Readout capabilities."""
from importlib import import_module
from io import StringIO
from types import SimpleNamespace
from contextlib import contextmanager
import hashlib
import json
import sys
import signal

import pytest

from daesingo.common.logging import configure_logging


def test_default_main_registers_both_readouts(monkeypatch):
    main = import_module("daesingo.worker.__main__")
    # External engine loading is the only substitute; composition stays real.
    import numpy as np
    from daesingo.readout.paddle_provider import RecordingFrameSource, SourceFrame
    from daesingo.worker.readout_handlers import ReadoutInput
    from daesingo.worker.readout_inputs import ReadoutInputs
    from daesingo.common.jobs.execution import ExecutionContext
    from tests.worker.readout_support import ObservedUsage
    class Engine:
        def predict(self, pixels):
            second = int(pixels[0, 0, 0])
            yield SimpleNamespace(json={"res": dict(rec_texts=["12가3456", f"2026-06-20 14:19:{56 + second}"],
                rec_scores=[.99, .99], rec_boxes=[[0, 0, 300, 40], [0, 50, 399, 80]])})
    engine = Engine()
    startup = SimpleNamespace(config=SimpleNamespace(db=object(), media_root="unused"),
        logger=configure_logging("worker", stream=StringIO()))
    monkeypatch.setattr(main, "bootstrap", lambda **kw: startup)
    monkeypatch.setattr(main, "create_worker_engine", lambda db: SimpleNamespace(dispose=lambda: None))
    production = import_module("daesingo.worker.readout_composition")
    monkeypatch.setattr(production, "load_production_ocr_engine", lambda: engine, raising=False)
    original_factory = production.recording_ocr_factory
    @contextmanager
    def recording(data):
        yield SimpleNamespace(get_incident_clip=lambda ref: SimpleNamespace(incident_clip_ref=ref, duration_sec=3))
    def factory(**kw):
        result = original_factory(**kw)
        result.recording_factory = recording
        return result
    monkeypatch.setattr(production, "recording_ocr_factory", factory)
    monkeypatch.setattr(ReadoutInputs, "__call__", lambda self, ctx: ReadoutInput("case", "candidate", "generation", "clip"))
    monkeypatch.setattr(RecordingFrameSource, "frames", lambda self, ref: [
        SourceFrame(f"frame-{i}", i, np.full((100, 400, 3), i, dtype=np.uint8)) for i in range(3)])
    observed, terminals = [], []
    def compose(**kw):
        observed.extend(kw["registry"]._handlers)
        def run():
            for kind in ("PLATE_READ", "OVERLAY_TIME_READ"):
                terminals.append(kw["registry"].dispatch(ExecutionContext("exec", "job", "case", kind, 1,
                    "trace", usage_sink=ObservedUsage())))
        return SimpleNamespace(run=run)
    monkeypatch.setattr(main, "compose_worker", compose)
    assert main.main() == 0
    assert {"PLATE_READ", "OVERLAY_TIME_READ"} <= set(observed)
    assert [t.status for t in terminals] == ["SUCCEEDED", "SUCCEEDED"]
    plate = terminals[0].objects[0].payload["plate_readout"]
    overlay = terminals[1].objects[0].payload["overlay_time_readout"]
    assert plate["observation"]["value"] == "12가3456" and plate["observation"]["status"] == "OK"
    assert overlay["observation"]["status"] == "OK" and overlay["validation"]["duration_match_ok"] is True


def test_production_factory_uses_recording_scope_and_fresh_paddle_provider(monkeypatch):
    from daesingo.readout.paddle_provider import PaddleOcrProvider, RecordingFrameSource
    from daesingo.worker import readout_composition as module
    from daesingo.worker.readout_handlers import ReadoutInput
    warmed = object()
    monkeypatch.setattr(module, "load_production_ocr_engine", lambda: warmed, raising=False)
    closed = []
    @contextmanager
    def recording(data):
        yield SimpleNamespace(get_incident_clip=lambda ref: SimpleNamespace(incident_clip_ref=ref, duration_sec=2))
        closed.append(True)
    original = module.recording_ocr_factory
    def factory(**kw):
        result = original(**kw)
        result.recording_factory = recording
        return result
    monkeypatch.setattr(module, "recording_ocr_factory", factory)
    actual = module.production_readout_factory(engine=object(), startup=SimpleNamespace(
        config=SimpleNamespace(media_root="unused"), logger=object()))
    providers = []
    for _ in range(2):
        with actual(ReadoutInput("case", "candidate", "generation", "clip")) as session:
            assert isinstance(session.provider, PaddleOcrProvider)
            assert isinstance(session.provider._source, RecordingFrameSource)
            assert session.provider._engine is warmed
            assert session.provider._tz_offset == "+09:00"
            providers.append(session.provider)
    assert providers[0] is not providers[1]
    assert closed == [True, True]


def test_worker_reclaims_signal_ownership_after_native_ocr_initialization(monkeypatch):
    main = import_module("daesingo.worker.__main__")
    installed, stopped = {}, []
    startup = SimpleNamespace(config=SimpleNamespace(db=object()),
        logger=configure_logging("worker", stream=StringIO()))
    monkeypatch.setattr(main, "bootstrap", lambda **kw: startup)
    monkeypatch.setattr(main, "create_worker_engine", lambda db: SimpleNamespace(dispose=lambda: None))
    monkeypatch.setattr(main.signal, "getsignal", lambda sig: signal.SIG_DFL)
    monkeypatch.setattr(main.signal, "signal", lambda sig, handler: installed.__setitem__(sig, handler))
    def native_init(**kw):
        # Native libraries can replace the OS handler during import/model setup.
        installed[signal.SIGTERM] = signal.SIG_DFL
        return lambda data: None
    monkeypatch.setattr(main, "production_readout_factory", native_init)
    def compose(**kw):
        def run():
            handler = installed[signal.SIGTERM]
            if callable(handler): handler(signal.SIGTERM, None)
            stopped.append(kw["stop"].is_set())
        return SimpleNamespace(run=run)
    monkeypatch.setattr(main, "compose_worker", compose)
    assert main.main() == 0
    assert stopped == [True]


@pytest.mark.parametrize("problem", ["dependency", "cache", "permission"])
def test_production_startup_failure_is_safe_and_never_enters_loop(monkeypatch, problem):
    main = import_module("daesingo.worker.__main__")
    from daesingo.worker import readout_composition as production
    stream, disposed, loops = StringIO(), [], []
    startup = SimpleNamespace(config=SimpleNamespace(db=object(), media_root="unused"),
        logger=configure_logging("worker", stream=stream))
    monkeypatch.setattr(main, "bootstrap", lambda **kw: startup)
    monkeypatch.setattr(main, "create_worker_engine", lambda db: SimpleNamespace(dispose=lambda: disposed.append(True)))
    def fail():
        raise {"dependency": ImportError, "cache": FileNotFoundError, "permission": PermissionError}[problem](
            "credential /private/cache/model /private/user/video")
    monkeypatch.setattr(production, "load_production_ocr_engine", fail, raising=False)
    monkeypatch.setattr(main, "compose_worker", lambda **kw: loops.append(True) or SimpleNamespace(run=lambda: None))
    assert main.main() == 1
    assert loops == []
    assert disposed == [True]
    assert "runtime.worker.failed" in stream.getvalue()
    assert all(token not in stream.getvalue() for token in ("credential", "private", "model", "video"))


def model_cache(tmp_path):
    from daesingo.worker.readout_runtime import MODEL_NAMES
    manifest = {}
    for name in MODEL_NAMES:
        directory = tmp_path / "official_models" / name
        directory.mkdir(parents=True)
        manifest[name] = {}
        for filename in ("inference.json", "inference.pdiparams", "inference.yml"):
            (directory / filename).write_bytes(b"model-test")
            manifest[name][filename] = hashlib.sha256(b"model-test").hexdigest()
    (tmp_path / "models.json").write_text(json.dumps(manifest))
    return tmp_path


@pytest.mark.parametrize("mutation", ["missing", "partial", "modified", "traversal", "permission"])
def test_invalid_cache_is_rejected_before_loading_paddle(tmp_path, monkeypatch, mutation):
    from pathlib import Path
    from daesingo.worker import readout_runtime as module
    root = model_cache(tmp_path)
    artifact = root / "official_models" / "PP-OCRv5_mobile_det" / "inference.pdiparams"
    if mutation == "missing": (root / "models.json").unlink()
    elif mutation == "partial": artifact.unlink()
    elif mutation == "modified": artifact.write_bytes(b"corrupted")
    elif mutation == "traversal":
        manifest = json.loads((root / "models.json").read_text())
        manifest["PP-OCRv5_mobile_det"]["../outside"] = "invalid"
        (root / "models.json").write_text(json.dumps(manifest))
    else:
        original = Path.open
        def opened(path, *a, **kw):
            if path == artifact: raise PermissionError("private-cache")
            return original(path, *a, **kw)
        monkeypatch.setattr(Path, "open", opened)
    with pytest.raises((OSError, ValueError)):
        module.verify_model_cache(root)


def test_preflight_loads_local_cpu_engine_and_predicts_before_return(tmp_path, monkeypatch):
    from daesingo.worker import readout_runtime as module
    root = model_cache(tmp_path)
    monkeypatch.setattr(module, "CACHE_ROOT", root)
    monkeypatch.setattr(module, "version", lambda name: module.DEPENDENCIES[name])
    calls = []
    class Engine:
        def __init__(self, **options):
            assert options == dict(lang="korean", text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="korean_PP-OCRv5_mobile_rec", device="cpu", enable_mkldnn=False,
                use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False,
                text_detection_model_dir=str(root / "official_models" / "PP-OCRv5_mobile_det"),
                text_recognition_model_dir=str(root / "official_models" / "korean_PP-OCRv5_mobile_rec"))
        def predict(self, pixels):
            calls.append(pixels.shape)
            return iter(())
    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PaddleOCR=Engine))
    assert isinstance(module.load_production_ocr_engine(), Engine)
    assert calls == [(64, 256, 3)]


def test_missing_dependency_is_a_safe_preflight_failure(monkeypatch, capsys):
    from importlib.metadata import PackageNotFoundError
    from daesingo.worker import readout_runtime as module
    def missing(name): raise PackageNotFoundError("private/model-cache credential")
    monkeypatch.setattr(module, "version", missing)
    # Exercise the same adapter that the final image's build runs offline.
    from tests.deploy.test_runtime import adapter
    assert adapter().main(["readout-preflight"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "container: operation_failed\n"
