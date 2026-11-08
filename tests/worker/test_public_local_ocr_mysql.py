"""Canonical InnoDB claim/local receipt/real OCR usage and retry transactions.

Only Recording pixels and Paddle inference are deterministic doubles. The
production factory/Readout/Worker sink/T1/reconciliation use their real paths.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import StringIO
import hashlib
from threading import Barrier, Event
from types import MappingProxyType

import pytest
import sqlalchemy as sa

from a1_support import policy_values, supported_policy_values
from daesingo.common.bootstrap import Startup
from daesingo.common.config import RuntimeConfig
from daesingo.common.jobs.execution import ExecutionContext
from daesingo.common.jobs.repository import claim_one, enqueue
from daesingo.common.jobs.schema import job_execution
from daesingo.common.logging import configure_logging
from daesingo.common.public_runtime import schema as t
from daesingo.common.public_runtime.policy import PublicDenied, PublicPolicy
from daesingo.common.public_runtime.repository import PublicStore
from daesingo.common.usage.reconciliation import reconcile_once
from daesingo.common.usage.schema import usage_inflight, usage_record
from daesingo.worker.composition import compose_worker
from daesingo.worker.readout_handlers import ReadoutInput, readout_registry
from tests.api import test_public_mysql
from tests.worker.test_public_local_ocr_usage import _production_ocr_factory

pytestmark = pytest.mark.mysql
public_db = test_public_mysql.public_db
bind = test_public_mysql.bind


def configured(public_db, tmp_path, *, funding="elice_supported", **limits):
    engine, _ = public_db
    values = (supported_policy_values if funding == "elice_supported" else policy_values)(tmp_path,
        local_work={"case_jobs": 4, "ip_daily_jobs": 8, "global_concurrent": 2, **limits})
    store = PublicStore(PublicPolicy.model_validate(values), require_public=True, worker_id="worker")
    bind(engine, store)
    return engine, store


def queued(engine, store, kind="PLATE_READ", *, case_id="case_1", key="local"):
    record = {"job_id": "job_" + key, "case_id": case_id, "kind": kind}
    with engine.begin() as conn:
        store.admit_local(conn, case_id, hashlib.sha256(key.encode()).digest(), [record])
        enqueue(conn, [record], "TEST_ONLY_LOCAL_OCR")
    claimed = claim_one(engine, "worker", lease_duration_sec=60)
    assert claimed is not None and claimed.job_id == record["job_id"]
    return claimed


@pytest.mark.mysql_check("public_a1", "local_ocr")
@pytest.mark.parametrize("mode", [pytest.param(mode,
    marks=pytest.mark.mysql_check("public_a1", "local_ocr", parameter=mode))
    for mode in ("plate_supported", "overlay_supported", "plate_krw", "overlay_krw", "restart")])
def test_real_local_ocr_usage_survives_t1_reconciliation_and_restart(public_db, tmp_path, monkeypatch, mode):
    restart = mode == "restart"
    supported = mode.endswith("supported") or restart
    engine, store = configured(public_db, tmp_path, funding="elice_supported" if supported else "krw")
    with engine.begin() as conn:
        store.pause_analysis(conn)
    kind = "OVERLAY_TIME_READ" if mode.startswith("overlay") else "PLATE_READ"
    claim = queued(engine, store, kind)
    media, temp = tmp_path / "media", tmp_path / "temp"
    media.mkdir()
    temp.mkdir()
    config = RuntimeConfig.from_mapping("worker", {
        "DAESINGO_RUNTIME_DB_URL": engine.url.render_as_string(hide_password=False),
        "DAESINGO_RUNTIME_MEDIA_ROOT": str(media), "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(temp)})
    startup = Startup(config, MappingProxyType({}), configure_logging("worker", stream=StringIO()), "1" * 40)
    monkeypatch.setattr("daesingo.worker.composition.load_policy", lambda *a, **k: store.policy)
    events, inferences = [], []
    def before_inference():
        with engine.connect() as conn:
            row = conn.execute(sa.select(usage_inflight)).mappings().one()
            assert row["state"] == "STARTED" and row["execution_ref"] == claim.execution_id
            assert conn.scalar(sa.select(sa.func.count()).select_from(t.reservations)) == 0
    factory = _production_ocr_factory(monkeypatch, engine=engine, startup=startup, case_id="case_1",
        clip_ref="same-clip", events=events, inferences=inferences, before_inference=before_inference)
    registry = readout_registry(load=lambda ctx: ReadoutInput("case_1", "candidate", "generation", "same-clip"),
                               provider_factory=factory)
    worker = compose_worker(engine=engine, startup=startup, registry=registry, stop=Event(), worker_id="worker")
    context = ExecutionContext(claim.execution_id, claim.job_id, claim.case_id, claim.kind, claim.attempt, claim.trace_id)
    context = replace(context, usage_sink=worker.usage_sink_factory(context))
    terminal = worker.dispatch(context)
    assert terminal.status == "SUCCEEDED" and len(inferences) == 7
    interrupted = []
    if restart:
        def interrupt_after_t1(*args, **kwargs):
            interrupted.append(kwargs["execution_ref"])
            raise RuntimeError("TEST_ONLY_POST_T1_INTERRUPTION")
        monkeypatch.setattr("daesingo.worker.composition.reconcile_once", interrupt_after_t1)
    assert worker.record(context, terminal)
    if restart:
        assert interrupted == [claim.execution_id]
        with engine.connect() as conn:
            assert conn.scalar(sa.select(job_execution.c.status)) == "SUCCEEDED"
            assert conn.scalar(sa.select(usage_inflight.c.state)) == "OBSERVED"
        assert len(reconcile_once(engine, execution_ref=claim.execution_id, recovery=True)) == 1
    else:
        # Normal record already reconciles after T1; a second scan is a replay.
        assert reconcile_once(engine, execution_ref=claim.execution_id, recovery=False) == ()
    assert reconcile_once(engine, execution_ref=claim.execution_id, recovery=True) == ()
    with engine.connect() as conn:
        row = conn.execute(sa.select(usage_inflight)).mappings().one()
        final = conn.execute(sa.select(usage_record)).mappings().one()
        assert row["state"] == "FINALIZED" and row["observed_at"] is not None
        assert row["outcome"] == "SUCCEEDED" and row["provider_label"] == "ocr-local"
        assert row["operation"] == ("READOUT_PLATE" if kind == "PLATE_READ" else "READOUT_OVERLAY_TIME")
        assert row["amount"] == final["amount"] == 0
        assert final["run_ref"] == terminal.produced[0].ref
        assert conn.scalar(sa.select(sa.func.count()).select_from(t.admissions)) == 0
        assert conn.scalar(sa.select(sa.func.sum(t.local_admissions.c.job_count))) == 1
        assert conn.scalar(sa.select(sa.func.count()).select_from(t.reservations)) == 0


@pytest.mark.mysql_check("public_a1", "local_ocr", parameter="concurrent")
def test_racing_ocr_pair_and_export_never_exceed_two_local_slots(public_db, tmp_path):
    engine, store = configured(public_db, tmp_path)
    with engine.begin() as conn:
        store.pause_analysis(conn)
    barrier = Barrier(2)
    def request(number):
        case_id = "case_" + str(number)
        records = ([{"job_id": "plate", "case_id": case_id, "kind": "PLATE_READ"},
                    {"job_id": "overlay", "case_id": case_id, "kind": "OVERLAY_TIME_READ"}]
                   if number == 1 else [{"job_id": "report", "case_id": case_id, "kind": "REPORT_VIDEO_EXPORT"}])
        barrier.wait(timeout=5)
        try:
            with engine.begin() as conn:
                store.admit_local(conn, case_id, bytes([number]) * 32, records)
                enqueue(conn, records, "TEST_ONLY_LOCAL_RACE")
            return "ACCEPTED", len(records)
        except PublicDenied as denied:
            return denied.code, 0
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(request, (1, 2)))
    assert sorted(value[0] for value in results) == ["ACCEPTED", "LOCAL_CONCURRENT"]
    with engine.connect() as conn:
        total = conn.scalar(sa.select(sa.func.sum(t.local_admissions.c.job_count)))
        assert total == sum(count for _, count in results) and 0 < total <= 2
        assert conn.scalar(sa.select(sa.func.count()).select_from(job_execution)) == total
        assert conn.scalar(sa.select(sa.func.count()).select_from(t.admissions)) == 0


@pytest.mark.mysql_check("public_a1", "local_ocr")
@pytest.mark.parametrize("condition", [pytest.param(condition,
    marks=pytest.mark.mysql_check("public_a1", "local_ocr", parameter=condition))
    for condition in ("stop", "cancel", "lease", "identity")])
def test_local_ocr_rejection_creates_no_usage_or_monetary_reservation(public_db, tmp_path, condition):
    engine, store = configured(public_db, tmp_path)
    claim = queued(engine, store)
    snapshot = {"usage_id": "rejected-usage", "case_id": "case_1", "execution_ref": claim.execution_id,
        "operation": "READOUT_PLATE", "provider_label": "ocr-local", "pricing_id": "local-2026-09",
        "unit": "per_second", "planned_run_kind": "readout_run", "planned_run_ref": "rr_test", "direct_no_run": False}
    with engine.begin() as conn:
        if condition == "stop":
            store.set_open(conn, False)
        elif condition == "cancel":
            conn.execute(job_execution.update().values(cancel_requested_at=sa.func.now(6)))
        elif condition == "lease":
            conn.execute(job_execution.update().values(lease_owner="other"))
        else:
            snapshot["provider_label"] = "elice:unapproved"
    with engine.begin() as conn, pytest.raises(PublicDenied) as denied:
        store.reserve(conn, snapshot)
    assert denied.value.code == {"stop": "JOBS_STOPPED", "cancel": "CANCELLED",
                                 "lease": "CLAIM_LOST", "identity": "UNSUPPORTED"}[condition]
    with engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(usage_inflight)) == 0
        assert conn.scalar(sa.select(sa.func.count()).select_from(t.reservations)) == 0


def _retry_failed_plate_scenario(engine, tmp_path):
    """Exact Case command/receipt/queue transaction, with explicit failed history."""
    from copy import deepcopy
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from daesingo.api.public_access import PublicAPI
    from daesingo.case import command
    from daesingo.case.store import CaseStore
    from daesingo.case.store_mysql import MySQLCaseRepository
    from daesingo.common.jobs.execution import HandlerResult
    from daesingo.common.jobs.read_port import read_executions
    from daesingo.common.jobs.reflection import ReflectionInput, reflect_terminal
    from daesingo.worker.case_reflector import CaseReflector
    from daesingo.worker.public_reflection import PublicResultReflector
    from tests.case.test_command import _store_with_selected_case, _NoPackageAdapter, MOCK_ROOT
    _, case = _store_with_selected_case()
    cid = case.case_id
    prior = case.job_records[-1]
    pinned = {"candidate_id": "cand_a", "generation_job_id": case.job_records[0]["job_id"],
              "incident_clip_ref": "same-successful-clip"}
    case.observation_inputs[prior["job_id"]] = deepcopy(pinned)
    case.observation_outcomes[prior["job_id"]] = {"status": "FAILED"}
    case.settle_job(prior["job_id"], "REFLECTED")
    old_records = deepcopy(case.job_records)
    public = PublicStore(PublicPolicy.model_validate(supported_policy_values(tmp_path,
        local_work={"case_jobs": 2, "ip_daily_jobs": 8, "global_concurrent": 2})), require_public=True)
    bind(engine, public, names=(cid,))
    class FailedReadoutProjection(_NoPackageAdapter):
        def __init__(self, connection):
            super().__init__(MOCK_ROOT, "happy_001")
            self.connection = connection
        def get_plate_read_status(self):
            # Use the actual terminal history for the visible retry action;
            # unrelated evidence fields remain the existing contract fixture.
            return self.connection.scalar(sa.select(job_execution.c.status).where(
                job_execution.c.case_id == cid, job_execution.c.kind == "PLATE_READ")
                .order_by(job_execution.c.queued_at.desc(), job_execution.c.execution_id.desc()).limit(1))
    def case_store(conn):
        return CaseStore(repository=MySQLCaseRepository(), conn=conn, executions=read_executions,
            adapter_factory=lambda case, connection: FailedReadoutProjection(connection))
    def stamp():
        return datetime.now(timezone.utc).replace(tzinfo=None)
    def queue(conn, records):
        if conn.dialect.name == "mysql":
            return enqueue(conn, records, "TEST_ONLY_OCR_RETRY")
        identities = []
        for r in records:
            identity = "exec_" + r["job_id"]
            conn.execute(job_execution.insert().values(execution_id=identity, job_id=r["job_id"], case_id=cid,
                kind=r["kind"], status="QUEUED", attempt=1, produced=[], trace_id="test-ocr",
                queued_at=stamp(), available_at=stamp()))
            identities.append(identity)
        return identities
    with engine.begin() as conn:
        case_store(conn).repository.insert(conn, case)
        owner = conn.execute(sa.select(t.cases).where(t.cases.c.case_id == cid)).mappings().one()
        for index in range(2):
            conn.execute(t.admissions.insert().values(case_id=cid, request_hash=bytes([index]) * 32,
                session_hash=owner["session_hash"], ip_hash=owner["ip_hash"], created_at=stamp(), initial=False, active=False))
        old_execution, = queue(conn, [prior])
        conn.execute(job_execution.update().where(job_execution.c.execution_id == old_execution).values(status="FAILED",
            failure_kind="RUNTIME_USAGE_UNSUPPORTED", started_at=stamp(), ended_at=stamp(), case_applied_at=stamp()))
        conn.execute(t.reservations.insert().values(usage_id="protected-prior", execution_ref=old_execution,
            case_id=cid, operation="SEARCH_COARSE", provider_label="elice:prior", amount_micros=99, created_at=stamp()))
        paid_before = [dict(x) for x in conn.execute(sa.select(t.admissions)).mappings()]
        public.pause_analysis(conn)
    reflector = PublicResultReflector(CaseReflector(reader=lambda *args: None, timelines=object(),
                                                   store_factory=case_store), public)
    for number in range(3):
        with engine.connect() as conn:
            before = deepcopy(case_store(conn).get_case(cid))
        payload = {"case_id": cid, "expected_case_rev": before.case_rev, "kind": "RUN_NOTICE_ACTION",
            "payload": {"notice_code": "readout.plate_read_failed", "action": "RETRY_PLATE_READ"}}
        def retry():
            with engine.begin() as conn:
                result = command.execute_command(payload, store=case_store(conn))
                assert result.response["ok"] is True, result.response
                PublicAPI.admit_result(SimpleNamespace(store=public), conn, payload, result)
                identity, = queue(conn, result.appended_job_records)
                record, = result.appended_job_records
                return identity, record
        if number == 2:
            with pytest.raises(PublicDenied) as denied:
                retry()
            assert denied.value.code == "LOCAL_LIMIT"
            with engine.connect() as conn:
                current = case_store(conn).get_case(cid)
                assert current.case_rev == before.case_rev and current.job_records == before.job_records
            break
        identity, record = retry()
        with engine.begin() as conn:
            current = case_store(conn).get_case(cid)
            assert current.observation_inputs[record["job_id"]] == pinned
            assert current.job_records[:len(old_records)] == old_records
            assert current.case_rev > before.case_rev and record["kind"] == "PLATE_READ"
            duplicate = command.execute_command(payload, store=case_store(conn))
            assert not duplicate.response["ok"] and duplicate.response["error"]["code"] == "case.command.stale_revision"
            assert duplicate.appended_job_records == []
            conn.execute(job_execution.update().where(job_execution.c.execution_id == identity).values(status="FAILED",
                failure_kind="READOUT_INFRA", started_at=stamp(), ended_at=stamp()))
        incoming = ReflectionInput(identity, record["job_id"], cid, "PLATE_READ", 1,
                                   HandlerResult(status="FAILED", failure_kind="READOUT_INFRA"))
        def deliver():
            with engine.begin() as conn:
                public.locked(conn)
                if conn.dialect.name == "mysql":
                    return reflect_terminal(conn, incoming, reflector, "test-ocr")
                result = reflector.reflect(conn, incoming)
                assert result.jobs == ()
                conn.execute(job_execution.update().where(job_execution.c.execution_id == identity)
                             .values(case_applied_at=stamp()))
                return result
        assert deliver().status == "APPLIED"
        assert deliver().status == "ALREADY_APPLIED"
    with engine.connect() as conn:
        assert [dict(x) for x in conn.execute(sa.select(t.admissions)).mappings()] == paid_before
        assert conn.scalar(sa.select(sa.func.sum(t.local_admissions.c.job_count))) == 2
        assert conn.scalar(sa.select(sa.func.count()).select_from(job_execution)) == 3
        assert conn.scalar(sa.select(sa.func.sum(t.reservations.c.amount_micros))) == 99


@pytest.mark.mysql_check("public_a1", "local_ocr", parameter="retry")
def test_existing_failed_clip_retries_without_refunding_analysis_or_duplicate_jobs(public_db, tmp_path):
    _retry_failed_plate_scenario(public_db[0], tmp_path)
