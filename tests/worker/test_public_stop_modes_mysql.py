"""Emergency stop rolls back T2 child enqueue, without losing durable T1."""
from importlib import import_module
import pytest
import sqlalchemy as sa

from a1_support import policy_values
from daesingo.common.public_runtime.policy import PublicPolicy, PublicDenied
from daesingo.common.public_runtime.repository import PublicStore
from daesingo.common.jobs.schema import job_execution
from daesingo.common.jobs.reflection import RuntimeJobRecord
from daesingo.common.jobs.execution import ExecutionContext
from test_reflection_mysql import fake_case, FakeReflector, case_state  # noqa: F401
from test_worker_mysql import queue, seed, row  # noqa: F401 — fake_case depends on queue.

pytestmark = pytest.mark.mysql


@pytest.mark.mysql_check("public_a1", "stop_modes")
@pytest.mark.parametrize("kind", [pytest.param(kind, marks=pytest.mark.mysql_check("public_a1", "stop_modes", parameter=kind))
    for kind in ("REPORT_VIDEO_EXPORT", "FINE_VERIFY")])
def test_stop_blocks_new_t2_jobs_and_resumption_reuses_durable_terminal(fake_case, tmp_path, monkeypatch, kind):
    from threading import Event
    from types import MappingProxyType
    from daesingo.common.bootstrap import Startup
    from daesingo.common.config import RuntimeConfig
    from daesingo.common.logging import configure_logging
    from daesingo.worker.registry import KindRegistry
    media_root, temp_root = tmp_path / "media", tmp_path / "temp"
    media_root.mkdir()
    temp_root.mkdir()
    config = RuntimeConfig.from_mapping("worker", {
        "DAESINGO_RUNTIME_PUBLIC_MODE": "internal",
        "DAESINGO_RUNTIME_DB_URL": fake_case.url.render_as_string(hide_password=False),
        "DAESINGO_RUNTIME_MEDIA_ROOT": str(media_root),
        "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(temp_root),
    })
    policy = PublicPolicy.model_validate(policy_values(tmp_path, local_work={"case_jobs": 4, "ip_daily_jobs": 8, "global_concurrent": 2}))
    store = PublicStore(policy, require_public=True)
    with fake_case.begin() as conn:
        store.set_open(conn, True)
        owner = store.fingerprint("TEST_ONLY_SESSION")
        store.create_session(conn, owner, store.fingerprint("TEST_ONLY_IP"))
        store.claim_case(conn, "case", owner)
        store.bind_sample(conn, "case", "TEST_ONLY", [{"source_asset_ref": "sa_test", "duration_ms": 1000,
            "sha256": "a"*64, "byte_size": 10}])
    composition = import_module("daesingo.worker.composition")
    monkeypatch.setattr(composition, "load_policy", lambda *args, **kw: policy)
    execution, = seed(fake_case)
    reflector = FakeReflector(fake_case, jobs=(RuntimeJobRecord("child", "case", kind),))
    current = composition.compose_worker(engine=fake_case,
        startup=Startup(config, MappingProxyType({}), configure_logging("worker")),
        registry=KindRegistry({}), stop=Event(), worker_id="worker", reflector=reflector)
    from daesingo.common.jobs.repository import claim_one
    from daesingo.common.jobs.execution import HandlerResult
    claimed = claim_one(fake_case, "worker", lease_duration_sec=60)
    context = ExecutionContext(claimed.execution_id, claimed.job_id, claimed.case_id, claimed.kind, claimed.attempt, claimed.trace_id)
    with fake_case.begin() as conn:
        store.set_open(conn, False)
    # An already-running operation may finish T1 during emergency stop.
    assert current.record(context, HandlerResult())
    with pytest.raises(PublicDenied) as stopped:
        current.reflect(context, HandlerResult())
    assert stopped.value.code == "JOBS_STOPPED"
    assert current.sweeper.redeliver() == ()  # same guard on startup/periodic redelivery
    assert row(fake_case, execution)["status"] == "SUCCEEDED"
    assert row(fake_case, execution)["case_applied_at"] is None
    assert case_state(fake_case) == (0, 0)
    with fake_case.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(job_execution).where(job_execution.c.job_id == "child")) == 0
    with fake_case.begin() as conn:
        store.set_open(conn, True)
    assert len(current.sweeper.redeliver()) == 1
    assert current.reflect(context, HandlerResult()).status == "ALREADY_APPLIED"
    assert case_state(fake_case) == (1, 1)
    with fake_case.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(job_execution).where(job_execution.c.job_id == "child")) == 1


@pytest.mark.mysql_check("public_a1", "stop_modes")
@pytest.mark.parametrize("mode", [pytest.param(mode, marks=pytest.mark.mysql_check("public_a1", "stop_modes", parameter="exhaustion_"+mode))
    for mode in ("pause", "stop")])
def test_hint_exhaustion_cannot_enqueue_coarse_until_resumed(fake_case, tmp_path, monkeypatch, mode):
    from threading import Event
    from types import MappingProxyType
    from daesingo.common.bootstrap import Startup
    from daesingo.common.logging import configure_logging
    from daesingo.worker.registry import KindRegistry
    from daesingo.worker.composition import compose_worker
    from test_exhaustion_mysql import exhausted, receiver, config
    from daesingo.common.jobs.schema import job_exhaustion_notice
    cid, execution, notice = exhausted(fake_case)
    policy = PublicPolicy.model_validate(policy_values(tmp_path))
    store = PublicStore(policy, require_public=True)
    with fake_case.begin() as conn:
        store.set_open(conn, True)
        owner = store.fingerprint("TEST_OWNER")
        store.create_session(conn, owner, store.fingerprint("TEST_IP"))
        store.claim_case(conn, cid, owner)
        store.pause_analysis(conn) if mode == "pause" else store.set_open(conn, False)
    composition = import_module("daesingo.worker.composition")
    monkeypatch.setattr(composition, "load_policy", lambda *args, **kw: policy)
    loop = compose_worker(engine=fake_case, startup=Startup(config(fake_case.url.render_as_string(hide_password=False)),
        MappingProxyType({}), configure_logging("worker"), "1"*40), registry=KindRegistry({}), stop=Event(),
        exhaustion_receiver=receiver())
    assert loop.sweeper.redeliver_exhaustion() == ()
    with fake_case.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(job_execution).where(job_execution.c.kind == "COARSE_SEARCH")) == 0
        assert conn.scalar(sa.select(job_exhaustion_notice.c.case_acknowledged_at).where(
            job_exhaustion_notice.c.notice_id == notice["notice_id"])) is None
    assert row(fake_case, execution)["status"] == "STALE"
    with fake_case.begin() as conn:
        store.set_open(conn, True)
    assert len(loop.sweeper.redeliver_exhaustion()) == 1
    assert loop.sweeper.redeliver_exhaustion() == ()
    with fake_case.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(job_execution).where(job_execution.c.kind == "COARSE_SEARCH")) == 1
