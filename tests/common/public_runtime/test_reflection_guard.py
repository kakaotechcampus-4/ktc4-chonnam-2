"""SQLite proves the new T2 guard rolls back one callback; real T1/T2 is MySQL-only."""
from threading import Event
from types import MappingProxyType, SimpleNamespace
import json

import pytest

from a1_support import policy_values
from test_admission import public, setup_case  # noqa: F401
from daesingo.common.bootstrap import Startup
from daesingo.common.config import RuntimeConfig
from daesingo.common.logging import configure_logging
from daesingo.common.jobs.execution import ExecutionContext, HandlerResult
from daesingo.common.jobs.reflection import ReflectionResult, RuntimeJobRecord
from daesingo.common.public_runtime.policy import PublicPolicy, PublicDenied
from daesingo.worker.registry import KindRegistry
from daesingo.worker import composition


@pytest.mark.parametrize("kind", [None, "REPORT_VIDEO_EXPORT", "FINE_VERIFY"])
@pytest.mark.parametrize("entry", ["direct", "redelivery"])
def test_emergency_guard_is_inside_reflection_transaction(public, tmp_path, monkeypatch, kind, entry):
    engine, store = public
    values = policy_values(tmp_path, local_work={"case_jobs": 4, "ip_daily_jobs": 8, "global_concurrent": 2})
    store.policy = PublicPolicy.model_validate(values)
    setup_case(public)
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE t2_probe (effect TEXT PRIMARY KEY)")
        store.set_open(conn, False)
    policy_file = tmp_path / "policy.private.json"
    policy_file.write_text(json.dumps(values), encoding="utf8")
    policy_file.chmod(0o600)
    config = RuntimeConfig.from_mapping("worker", {"DAESINGO_RUNTIME_PUBLIC_MODE": "internal",
        "DAESINGO_RUNTIME_DB_URL": "mysql+pymysql://test:secret@127.0.0.1:1/fixture_test",
        "DAESINGO_RUNTIME_MEDIA_ROOT": str(tmp_path / "media"), "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(tmp_path / "temp"),
        "DAESINGO_RUNTIME_PUBLIC_POLICY_FILE": str(policy_file)})
    def reflect(conn, incoming):
        conn.exec_driver_sql("INSERT INTO t2_probe VALUES ('CASE_APPLIED')")
        if kind is not None:
            conn.exec_driver_sql("INSERT INTO t2_probe VALUES ('CHILD_ENQUEUED')")
        return ReflectionResult("APPLIED", jobs=() if kind is None else (RuntimeJobRecord("child", "case_1", kind),))
    monkeypatch.setattr(composition, "reflect_terminal", lambda conn, incoming, reflector, trace: reflector.reflect(conn, incoming))
    def redeliver(engine, reflector, *, transaction_guard=None, **kw):
        with engine.begin() as conn:
            if transaction_guard is not None:
                transaction_guard(conn)
            return reflector.reflect(conn, SimpleNamespace(case_id="case_1", execution_id="execution"))
    monkeypatch.setattr(composition, "redeliver_once", redeliver)
    loop = composition.compose_worker(engine=engine, startup=Startup(config, MappingProxyType({}),
        configure_logging("worker"), "1"*40), registry=KindRegistry({}), stop=Event(), reflector=SimpleNamespace(reflect=reflect))
    context = ExecutionContext("execution", "parent", "case_1", "TEST", 1, "trace")
    run = (lambda: loop.reflect(context, HandlerResult())) if entry == "direct" else loop.sweeper.redeliver
    if kind is None:
        assert run().status == "APPLIED"
    else:
        with pytest.raises(PublicDenied) as error:
            run()
        assert error.value.code == "JOBS_STOPPED"
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM t2_probe").scalar_one() == (1 if kind is None else 0)
    if kind is not None:
        with engine.begin() as conn:
            store.set_open(conn, True)
        assert run().status == "APPLIED"
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT COUNT(*) FROM t2_probe").scalar_one() == 2


@pytest.mark.parametrize('paused', [False, True])
def test_accepted_auto_exports_are_not_double_charged_and_guarded_followup_is_not_exempt(public, tmp_path, paused):
    import sqlalchemy as sa
    from daesingo.common.public_runtime import schema
    from daesingo.worker.public_reflection import PublicResultReflector
    engine, store = public
    store.policy = PublicPolicy.model_validate(policy_values(tmp_path,
        local_work={'case_jobs': 4, 'ip_daily_jobs': 8, 'global_concurrent': 2}))
    setup_case(public)
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE mixed_effect (value TEXT)')
        if paused:
            store.pause_analysis(conn)
    auto = [{'job_id': 'report', 'case_id': 'case_1', 'kind': 'REPORT_VIDEO_EXPORT'},
            {'job_id': 'plate', 'case_id': 'case_1', 'kind': 'PLATE_IMAGE_EXPORT'}]
    def reflect_with_admission(conn, incoming, *, admit_auto_exports, on_auto_exports_deferred):
        assert admit_auto_exports(auto)
        conn.exec_driver_sql("INSERT INTO mixed_effect VALUES ('CASE_APPLIED')")
        return ReflectionResult('APPLIED', jobs=tuple(RuntimeJobRecord(**j) for j in auto)
            + (RuntimeJobRecord('required', 'case_1', 'FINE_VERIFY'),))
    inner = SimpleNamespace(reflect_with_admission=reflect_with_admission)
    wrapper = PublicResultReflector(inner, store)
    def run():
        with engine.begin() as conn:
            return wrapper.reflect(conn, SimpleNamespace(case_id='case_1', execution_id='mixed'))
    if paused:
        with pytest.raises(PublicDenied) as denied:
            run()
        assert denied.value.code == 'STOPPED'
    else:
        assert len(run().jobs) == 3
    with engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(schema.local_admissions)) == (0 if paused else 1)
        assert conn.exec_driver_sql('SELECT COUNT(*) FROM mixed_effect').scalar_one() == (0 if paused else 1)
