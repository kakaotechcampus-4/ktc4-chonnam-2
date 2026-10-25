"""RT-09 test-only composition; no provider, upload or timeline generation."""

from io import StringIO
import json
from threading import Event, Thread, current_thread
from types import MappingProxyType

import sqlalchemy as sa

from daesingo.case import jobs
from daesingo.case.store import CaseStore
from daesingo.case.store_mysql import MySQLCaseRepository
from daesingo.common.bootstrap import Startup
from daesingo.common.config import RuntimeConfig
from daesingo.common.db import create_worker_engine
from daesingo.common.jobs.execution import HandlerResult
from daesingo.common.jobs.read_port import read_executions
from daesingo.common.jobs.reflection import ReflectionInput, reflect_terminal
from daesingo.common.jobs.repository import claim_one, enqueue, finish
from daesingo.common.jobs.schema import job_execution
from daesingo.common.logging import configure_logging
from daesingo.worker.case_reflector import CaseReflector
from daesingo.worker.composition import compose_worker
from daesingo.worker.registry import KindRegistry


class UnusedTimelines:
    def timeline_for(self, sources):
        raise AssertionError("RT-09 COARSE_SEARCH must not request a timeline")


def store(conn):
    return CaseStore(repository=MySQLCaseRepository(), conn=conn, executions=read_executions)


def reader(conn, kind, produced):
    assert conn.in_transaction() and kind == "COARSE_SEARCH"
    assert produced == ({"kind": "analysis_run", "ref": "run_rt09"},)
    return {"outcome": "SUCCEEDED", "candidate_events": [{
        "candidate_id": "cand_rt09", "summary": "test candidate", "thumbnail_ref": "frame_rt09",
        "rank": 1, "span": {"representative_ms": 4000, "timeline_revision": 1}}]}


def prepare_retry(engine, identity):
    """Plan §4 fixture: an existing failed search, using no START_ANALYSIS."""
    with engine.begin() as conn:
        current = store(conn)
        case = current.load_for_update(identity)
        case.start_search()
        job = jobs.issue_coarse_search(case, scope_ref="scope_rt09", input_fingerprint="fixture_rt09")
        current.save(case)
        execution_id, = enqueue(conn, [job], "trace_fixture_rt09")
    claimed = claim_one(engine, "fixture_owner_rt09")
    assert claimed.execution_id == execution_id
    terminal = HandlerResult(status="FAILED", failure_kind="SEARCH_PROVIDER_FAILED")
    with engine.begin() as conn:
        assert finish(conn, execution_id, claimed.lease_owner, status="FAILED",
                      failure_kind=terminal.failure_kind) == 1
    with engine.begin() as conn:
        incoming = ReflectionInput(execution_id, job["job_id"], identity, "COARSE_SEARCH", 1, terminal)
        assert reflect_terminal(conn, incoming, CaseReflector(reader=reader, timelines=UnusedTimelines()),
                                "trace_fixture_rt09").status == "APPLIED"
    return {"case_id": identity, "expected_case_rev": case.case_rev, "kind": "RUN_NOTICE_ACTION",
            "payload": {"notice_code": "search.candidate_search_failed", "action": "RETRY_SEARCH"}}


def snapshot(engine, identity, job_id=None):
    with engine.begin() as conn:
        # Independent committed observer, never locks the Case against T2.
        stage, state = conn.exec_driver_sql("SELECT stage,state FROM cases WHERE case_id=%s", (identity,)).one()
        records = conn.exec_driver_sql("SELECT record FROM job_records WHERE case_id=%s ORDER BY seq", (identity,)).scalars()
        query = sa.select(job_execution).where(job_execution.c.case_id == identity)
        if job_id is not None:
            query = query.where(job_execution.c.job_id == job_id)
        return {"case": {**json.loads(state), "stage": stage}, "records": [json.loads(record) for record in records],
                "executions": [dict(row) for row in conn.execute(query).mappings()]}


class AsyncWorker:
    def __init__(self, observer_engine, tmp_path):
        config = RuntimeConfig.from_mapping("worker", {
            "DAESINGO_RUNTIME_DB_URL": observer_engine.url.render_as_string(hide_password=False),
            "DAESINGO_RUNTIME_MEDIA_ROOT": str(tmp_path),
            "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(tmp_path),
        })
        self.engine = create_worker_engine(config.db)
        self.stream = StringIO()
        self.stop, self.entered, self.release_handler = Event(), Event(), Event()
        self.t1_ready, self.release_t2 = Event(), Event()
        self.calls, self.errors, self.locks, self.precommit = [], [], [], []
        startup = Startup(config, MappingProxyType({}), configure_logging("worker", stream=self.stream))
        self.loop = compose_worker(engine=self.engine, startup=startup, stop=self.stop,
            registry=KindRegistry({"COARSE_SEARCH": self.handle}),
            reflector=CaseReflector(reader=reader, timelines=UnusedTimelines()))
        reflect = self.loop.reflect
        def t1_gap(context, terminal):
            self.t1_ready.set()
            assert self.release_t2.wait(20), "test did not release T2"
            return reflect(context, terminal)
        self.loop.reflect = t1_gap
        self.thread = Thread(target=self.run, name="rt09-worker", daemon=True)
        sa.event.listen(self.engine, "before_cursor_execute", self.observe_lock)
        sa.event.listen(self.engine, "after_cursor_execute", self.observe_marker)

    def observe_lock(self, conn, cursor, statement, *args):
        if current_thread() is self.thread and "FOR UPDATE" in statement.upper():
            self.locks.append(statement.upper())

    def observe_marker(self, conn, cursor, statement, *args):
        if not statement.upper().startswith("UPDATE JOB_EXECUTION SET CASE_APPLIED_AT"):
            return
        context, = self.calls
        assert conn.in_transaction()
        stage, state = conn.exec_driver_sql("SELECT stage,state FROM cases WHERE case_id=%s", (context.case_id,)).one()
        own_state = json.loads(state)
        assert stage == "CANDIDATE_REVIEW"
        assert own_state["processed_executions"][context.execution_id] == context.job_id
        own_marker = conn.scalar(sa.select(job_execution.c.case_applied_at).where(
            job_execution.c.execution_id == context.execution_id))
        assert own_marker is not None
        outside = snapshot(self.engine, context.case_id, context.job_id)
        assert outside["case"]["stage"] == "SEARCHING"
        assert context.execution_id not in outside["case"]["processed_executions"]
        assert outside["executions"][0]["case_applied_at"] is None
        self.precommit.append({"case": outside["case"]["stage"], "receipt": None})

    def handle(self, context):
        assert self.engine.pool.checkedout() == 0
        self.calls.append(context)
        self.entered.set()
        assert self.release_handler.wait(20), "test did not release fake capability"
        return HandlerResult(produced=[{"kind": "analysis_run", "ref": "run_rt09"}])

    def run(self):
        try:
            self.loop.run()
        except BaseException as error:
            self.errors.append(error)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.release_handler.set()
        self.release_t2.set()
        self.stop.set()
        if self.thread.ident is not None:
            self.thread.join(10)
        assert not self.thread.is_alive(), "RT-09 Worker cleanup did not finish"
        self.engine.dispose()
        if exc[0] is None:
            assert not self.errors, self.errors
