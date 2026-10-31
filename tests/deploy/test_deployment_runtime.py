"""Deployment configuration and real-process registration observation boundary."""
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def adapter():
    spec = importlib.util.spec_from_file_location("rt14_adapter", ROOT / "docker/runtime.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_missing_recording_limits_fail_deployment_not_ready(tmp_path, monkeypatch, capsys):
    path = tmp_path / "runtime.env"
    path.write_text("DAESINGO_RUNTIME_DB_URL=mysql+pymysql://u:p@mysql/daesingo\n"
                    "GEMINI_API_KEY=PRIVATE-CANARY\n")
    monkeypatch.setenv("DAESINGO_ENV_FILE", str(path))
    assert adapter().main(["deploy-config"]) == 1
    assert "PRIVATE-CANARY" not in str(capsys.readouterr())


def test_actual_worker_publishes_registry_before_loop_and_removes_on_exit(tmp_path, monkeypatch):
    import daesingo.worker.__main__ as main
    import daesingo.worker.deployment_status as status
    from daesingo.worker.registry import KindRegistry
    from daesingo.common.logging import configure_logging
    import io
    target = tmp_path / "worker.json"
    original_publish, original_clear = status.publish, status.clear
    monkeypatch.setattr(status, "publish", lambda registry, revision: original_publish(registry, revision, target, token="process-A"))
    monkeypatch.setattr(status, "clear", lambda: original_clear(target))
    monkeypatch.setenv("DAESINGO_DEPLOYMENT_CHECK", "1")
    monkeypatch.setenv("DAESINGO_REVISION", "a" * 40)
    startup = SimpleNamespace(config=SimpleNamespace(db=object()), logger=configure_logging("worker", stream=io.StringIO()),
        modules={"recording": SimpleNamespace(profile=object(), analysis_limits=object(), incident_encoding=object())})
    monkeypatch.setattr(main, "bootstrap", lambda **kw: startup)
    monkeypatch.setattr(main, "create_worker_engine", lambda _: SimpleNamespace(dispose=lambda: None))
    registry = KindRegistry({kind: lambda _: None for kind in status.EXPECTED})
    monkeypatch.setattr(main, "compose_registry", lambda **kw: registry)
    entered = []
    def loop():
        status.verify(target, "a" * 40, token="process-A", pid=os.getpid())
        entered.append(True)
    monkeypatch.setattr(main, "compose_worker", lambda **kw: SimpleNamespace(run=loop))
    assert main.main(readout_provider_factory=lambda _: None) == 0
    assert entered == [True] and not target.exists()
    monkeypatch.setattr(main, "compose_registry", lambda **kw: KindRegistry({}))
    entered.clear()
    assert main.main(readout_provider_factory=lambda _: None) == 1
    assert entered == [] and not target.exists()


def test_packet_limit_requires_explicit_margin_and_strict_gap():
    m = adapter()
    assert hasattr(m, "check_packet"), "deployment packet guard missing"
    m.check_packet(1024, 8192, 4096)
    for maximum, packet, margin in [(4096, 8192, 4096), (8192, 8192, 1), (1, 8192, 0)]:
        with pytest.raises(ValueError):
            m.check_packet(maximum, packet, margin)


@pytest.mark.parametrize("missing", ["profile", "analysis_limits", "incident_encoding"])
def test_worker_missing_recording_setting_rejects_before_publish_and_loop(monkeypatch, missing):
    import io
    import daesingo.worker.__main__ as main
    import daesingo.worker.deployment_status as status
    from daesingo.common.logging import configure_logging
    from daesingo.worker.registry import KindRegistry
    monkeypatch.setenv("DAESINGO_DEPLOYMENT_CHECK", "1")
    fields = dict(profile=object(), analysis_limits=object(), incident_encoding=object())
    fields[missing] = None
    startup = SimpleNamespace(config=SimpleNamespace(db=object()),
        logger=configure_logging("worker", stream=io.StringIO()),
        modules={"recording": SimpleNamespace(**fields)})
    calls = []
    monkeypatch.setattr(main, "bootstrap", lambda **kw: startup)
    monkeypatch.setattr(main, "create_worker_engine", lambda _: SimpleNamespace(dispose=lambda: calls.append("dispose")))
    registry = KindRegistry({kind: lambda _: None for kind in status.EXPECTED})
    monkeypatch.setattr(main, "compose_registry", lambda **kw: registry)
    monkeypatch.setattr(main, "compose_worker", lambda **kw: SimpleNamespace(run=lambda: calls.append("loop")))
    monkeypatch.setattr(status, "publish", lambda *args: calls.append("publish"))
    monkeypatch.setattr(status, "clear", lambda: calls.append("clear"))
    assert main.main(readout_provider_factory=lambda _: None) == 1
    assert calls == ["clear", "clear", "dispose"]


def complete_config():
    # Synthetic fixture only; none of these values are operational defaults.
    return {"DAESINGO_RUNTIME_DB_URL": "mysql+pymysql://daesingo:PRIVATE-CANARY@mysql/daesingo",
        "DAESINGO_RUNTIME_MEDIA_ROOT": "/media", "DAESINGO_RUNTIME_API_TEMP_ROOT": "/media/api-temp",
        "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": "/media/worker-temp", "GEMINI_API_KEY": "PRIVATE-CANARY",
        "DAESINGO_RECORDING_ANALYSIS_PROFILE_REF": "synthetic-test", "DAESINGO_RECORDING_ANALYSIS_HEIGHT": "64",
        "DAESINGO_RECORDING_ANALYSIS_PRESET": "ultrafast", "DAESINGO_RECORDING_ANALYSIS_CRF": "30",
        "DAESINGO_RECORDING_ANALYSIS_MAX_BYTES": "1024", "DAESINGO_RECORDING_ANALYSIS_MAX_DURATION_MS": "1000",
        "DAESINGO_RECORDING_INCIDENT_HEIGHT": "64", "DAESINGO_RECORDING_INCIDENT_PRESET": "ultrafast",
        "DAESINGO_RECORDING_INCIDENT_CRF": "30"}


def test_full_synthetic_config_and_each_missing_required_group(tmp_path, monkeypatch):
    m = adapter()
    path = tmp_path / "runtime.env"
    monkeypatch.setenv("DAESINGO_ENV_FILE", str(path))
    def write(values):
        path.write_text("\n".join(k + "=" + v for k, v in values.items()))
    values = complete_config()
    write(values)
    assert m.main(["deploy-config"]) == 0
    for key in ("DAESINGO_RECORDING_ANALYSIS_MAX_BYTES", "DAESINGO_RECORDING_ANALYSIS_MAX_DURATION_MS",
                "DAESINGO_RECORDING_INCIDENT_HEIGHT", "GEMINI_API_KEY"):
        write({k: v for k, v in values.items() if k != key})
        assert m.main(["deploy-config"]) == 1


def test_worker_registration_marker_rejects_partial_set_and_stale_process(tmp_path):
    path = ROOT / "src/daesingo/worker/deployment_status.py"
    assert path.is_file(), "actual Worker observation missing"
    spec = importlib.util.spec_from_file_location("rt14_status", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    target = tmp_path / "status.json"
    expected = {"HINT_EXTRACT", "COARSE_SEARCH", "FINE_VERIFY", "INCIDENT_CLIP_BUILD", "PLATE_READ",
                "OVERLAY_TIME_READ", "REPORT_VIDEO_EXPORT", "PLATE_IMAGE_EXPORT"}
    with pytest.raises(ValueError):
        m.publish(SimpleNamespace(_handlers={"HINT_EXTRACT": None}), "a" * 40, target, token="process-A")
    assert not target.exists()
    m.publish(SimpleNamespace(_handlers={k: None for k in expected}), "a" * 40, target, token="process-A")
    m.verify(target, "a" * 40, token="process-A", pid=os.getpid())
    for kwargs in ({"token": "process-B", "pid": os.getpid()}, {"token": "process-A", "pid": 0}):
        with pytest.raises(ValueError):
            m.verify(target, "a" * 40, **kwargs)
    with pytest.raises(ValueError):
        m.verify(target, "b" * 40, token="process-A", pid=os.getpid())
    assert "PRIVATE-CANARY" not in target.read_text()


def test_read_only_smoke_rejects_server_error(monkeypatch):
    m = adapter()
    assert hasattr(m, "deployment_smoke"), "deployment smoke missing"
    calls = []
    def response(url, timeout):
        calls.append(url)
        return SimpleNamespace(__enter__=lambda _: None)
    # Actual HTTP errors are expected for a missing case only; never accept 5xx.
    from urllib.error import HTTPError
    def fail(url, timeout):
        raise HTTPError(url, 503, "PRIVATE-CANARY", None, None)
    monkeypatch.setattr(m.urllib.request, "urlopen", fail)
    with pytest.raises(HTTPError):
        m.deployment_smoke()


def test_marker_cleanup_failure_does_not_skip_engine_disposal(monkeypatch):
    import io
    import daesingo.worker.__main__ as main
    import daesingo.worker.deployment_status as status
    from daesingo.common.logging import configure_logging
    from daesingo.worker.registry import KindRegistry
    monkeypatch.setenv("DAESINGO_DEPLOYMENT_CHECK", "1")
    startup = SimpleNamespace(config=SimpleNamespace(db=object()), logger=configure_logging("worker", stream=io.StringIO()),
        modules={"recording": SimpleNamespace(profile=object(), analysis_limits=object(), incident_encoding=object())})
    monkeypatch.setattr(main, "bootstrap", lambda **kw: startup)
    disposed = []
    monkeypatch.setattr(main, "create_worker_engine", lambda _: SimpleNamespace(dispose=lambda: disposed.append(True)))
    monkeypatch.setattr(main, "compose_registry", lambda **kw: KindRegistry({}))
    monkeypatch.setattr(main, "compose_worker", lambda **kw: SimpleNamespace(run=lambda: None))
    monkeypatch.setattr(status, "publish", lambda *args: None)
    calls = []
    def clear():
        calls.append(True)
        if len(calls) == 2:
            raise OSError("PRIVATE-CANARY")
    monkeypatch.setattr(status, "clear", clear)
    assert main.main(readout_provider_factory=lambda _: None) == 1
    assert disposed == [True]
