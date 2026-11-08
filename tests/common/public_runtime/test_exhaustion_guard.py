"""A deferred HINT exhaustion must not bypass either stop mode."""
from types import SimpleNamespace
from threading import Event
from types import MappingProxyType
import json

import pytest

from test_admission import public, setup_case  # noqa: F401
from a1_support import policy_values
from daesingo.common.bootstrap import Startup
from daesingo.common.config import RuntimeConfig
from daesingo.common.logging import configure_logging
from daesingo.common.jobs.exhaustion import ExhaustionResult
from daesingo.common.public_runtime.policy import PublicDenied
from daesingo.worker.registry import KindRegistry
from daesingo.worker import composition


@pytest.mark.parametrize("mode", ["pause", "stop", "no_jobs"])
def test_exhaustion_uses_same_guard_before_new_coarse_job(public, tmp_path, monkeypatch, mode):
    engine, store = public
    setup_case(public)
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE exhaustion_probe (effect TEXT)")
        store.pause_analysis(conn) if mode == "pause" else store.set_open(conn, False)
    values = policy_values(tmp_path)
    path = tmp_path / "policy.private.json"
    path.write_text(json.dumps(values), encoding="utf8"); path.chmod(0o600)
    config = RuntimeConfig.from_mapping("worker", {"DAESINGO_RUNTIME_PUBLIC_MODE": "internal",
        "DAESINGO_RUNTIME_DB_URL": "mysql+pymysql://test:secret@127.0.0.1:1/fixture_test",
        "DAESINGO_RUNTIME_MEDIA_ROOT": str(tmp_path / "media"), "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(tmp_path / "temp"),
        "DAESINGO_RUNTIME_PUBLIC_POLICY_FILE": str(path)})
    def receive(conn, notice):
        conn.exec_driver_sql("INSERT INTO exhaustion_probe VALUES ('CASE_SAVED')")
        return ExhaustionResult("NO_CHANGE") if mode == "no_jobs" else ExhaustionResult("APPLIED",
            [{"job_id": "coarse", "case_id": "case_1", "kind": "COARSE_SEARCH"}])
    def redeliver(engine, receiver, *, transaction_guard=None, **kw):
        with engine.begin() as conn:
            if transaction_guard is not None:
                transaction_guard(conn)
            return receiver.receive(conn, SimpleNamespace(case_id="case_1", notice_id="notice"))
    monkeypatch.setattr(composition, "redeliver_exhaustion_once", redeliver)
    loop = composition.compose_worker(engine=engine, startup=Startup(config, MappingProxyType({}),
        configure_logging("worker"), "1"*40), registry=KindRegistry({}), stop=Event(),
        exhaustion_receiver=SimpleNamespace(receive=receive))
    if mode == "no_jobs":
        assert loop.sweeper.redeliver_exhaustion().status == "NO_CHANGE"
    else:
        with pytest.raises(PublicDenied) as denied:
            loop.sweeper.redeliver_exhaustion()
        assert denied.value.code == ("STOPPED" if mode == "pause" else "JOBS_STOPPED")
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM exhaustion_probe").scalar_one() == (1 if mode == "no_jobs" else 0)
