"""The process peer must preserve the real composition dispatch/logger contract."""
from io import StringIO
import json
from types import MappingProxyType, SimpleNamespace

import pytest
from pydantic import SecretStr

from daesingo.common.bootstrap import Startup
from daesingo.common.config import RuntimeConfig
from daesingo.common.jobs.execution import ExecutionContext, HandlerResult
from daesingo.common.logging import configure_logging
from daesingo.search.config import GeminiSearchConfig
from daesingo.worker.bootstrap import SearchSettings
from daesingo.worker.composition import compose_worker
from daesingo.worker.registry import KindRegistry
from production_processes import worker_peer


@pytest.mark.parametrize("handler_fails", [False, True])
def test_worker_peer_forwards_composition_logger_and_stops_after_dispatch(tmp_path, monkeypatch, handler_fails):
    from daesingo.common import db
    from daesingo.worker import bootstrap, composition, composition_root

    stream, replies, dispatches = StringIO(), [], []
    startup = Startup(RuntimeConfig.from_mapping("worker", {
        "DAESINGO_RUNTIME_DB_URL": "mysql+pymysql://test@127.0.0.1:1/not_connected",
        "DAESINGO_RUNTIME_MEDIA_ROOT": str(tmp_path / "media"),
        "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(tmp_path / "temp"),
    }), MappingProxyType({"search": SearchSettings(SecretStr("offline"), GeminiSearchConfig())}),
        configure_logging("worker", stream=stream))
    context = ExecutionContext("execution", "job", "case", "HINT_EXTRACT", 1, "trace")
    engine = SimpleNamespace(pool=SimpleNamespace(checkedout=lambda: 0), dispose=lambda: None)

    def handler(ctx):
        dispatches.append(ctx)
        if handler_fails:
            raise RuntimeError("private sentinel must not be logged")
        return HandlerResult()

    registry = KindRegistry({"HINT_EXTRACT": handler})
    monkeypatch.setenv("DAESINGO_ENV_FILE", "unused-by-injected-bootstrap")
    monkeypatch.setattr(bootstrap, "bootstrap", lambda **kwargs: startup)
    monkeypatch.setattr(db, "create_worker_engine", lambda config: engine)
    monkeypatch.setattr(composition_root, "compose_registry", lambda **kwargs: registry)

    def dispatch_only(**kwargs):
        # Keep the actual composition binding and nested peer wrapper real.
        # Only scheduling/DB/media work is outside this contract regression.
        loop = compose_worker(**kwargs)

        def run():
            result = loop.dispatch(context)
            assert kwargs["stop"].is_set()
            assert result.status == ("FAILED" if handler_fails else "SUCCEEDED")

        return SimpleNamespace(run=run)

    monkeypatch.setattr(composition, "compose_worker", dispatch_only)
    worker_peer(SimpleNamespace(send=replies.append, close=lambda: None),
                "unused-by-injected-bootstrap", "clip", "HINT_EXTRACT")
    assert len(replies) == 1 and "error" not in replies[0]
    assert replies[0]["terminals"] == [{"status": "FAILED" if handler_fails else "SUCCEEDED",
        "failure_kind": "RUNTIME_HANDLER_ERROR" if handler_fails else None}]
    assert dispatches == [context]
    rows = [json.loads(line) for line in stream.getvalue().splitlines()]
    failures = [row for row in rows if row["event"] == "runtime.execution.failed"]
    assert len(failures) == int(handler_fails)
    if handler_fails:
        assert failures[0]["error_type"] == "RuntimeError"
    assert "private sentinel" not in stream.getvalue()
