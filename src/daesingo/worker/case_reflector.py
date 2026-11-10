"""Worker-owned bridge to the existing Case 8-8 public surface.

Reader/timeline capabilities are supplied by composition (RT-10 owns durable
module results). Unsupported kinds preserve Case's fail-closed ValueError.
"""

from collections.abc import Callable

from sqlalchemy.engine import Connection

from daesingo.case.analysis_start import InitialSearchBudget
from daesingo.case.reflection import ExecutionOutcome, ProducedReader, reflect_execution, resume_auto_exports
from daesingo.case.store import CaseStore
from daesingo.case.store_mysql import MySQLCaseRepository
from daesingo.case.timeline_source import CaseTimelineSource
from daesingo.common.jobs.read_port import read_executions
from daesingo.common.jobs.reflection import ReflectionInput, ReflectionResult, RuntimeJobRecord


def _store(conn: Connection) -> CaseStore:
    return CaseStore(repository=MySQLCaseRepository(), conn=conn, executions=read_executions)


class CaseReflector:
    def __init__(self, *, reader: ProducedReader, timelines: CaseTimelineSource,
                 store_factory: Callable[[Connection], CaseStore] = _store,
                 budget: InitialSearchBudget | None = None):
        self.reader, self.timelines, self.store_factory, self.budget = reader, timelines, store_factory, budget

    def reflect(self, conn: Connection, incoming: ReflectionInput, *, admit_auto_exports=None,
                on_auto_exports_deferred=None) -> ReflectionResult:
        store = self.store_factory(conn)
        if store.conn is not conn:
            raise ValueError("reflection store must share caller connection")
        outcome = ExecutionOutcome(
            execution_id=incoming.execution_id, job_id=incoming.job_id, case_id=incoming.case_id,
            kind=incoming.kind, attempt=incoming.attempt, status=incoming.terminal.status,
            produced=tuple(ref.model_dump() for ref in incoming.terminal.produced),
            failure_kind=incoming.terminal.failure_kind,
        )
        deferred = False
        def admission(records):
            nonlocal deferred
            accepted = admit_auto_exports(records)
            deferred = deferred or not accepted
            return accepted
        result = reflect_execution(outcome, store=store, reader=self.reader,
            timelines=self.timelines, budget=self.budget,
            admit_auto_exports=admission if admit_auto_exports is not None else None)
        if deferred and on_auto_exports_deferred is not None:
            on_auto_exports_deferred(store.get_case(incoming.case_id).case_rev)
        return ReflectionResult(result.status, result.reason, tuple(
            RuntimeJobRecord(job["job_id"], job["case_id"], job["kind"])
            for job in result.appended_job_records))

    def reflect_with_admission(self, conn, incoming, *, admit_auto_exports, on_auto_exports_deferred):
        return self.reflect(conn, incoming, admit_auto_exports=admit_auto_exports,
                            on_auto_exports_deferred=on_auto_exports_deferred)

    def resume_auto_exports(self, conn: Connection, case_id: str, *,
                            admit_auto_exports) -> tuple[RuntimeJobRecord, ...]:
        """#674: Case's own gate re-issues exports that admission deferred during an earlier T2."""
        store = self.store_factory(conn)
        if store.conn is not conn:
            raise ValueError("resume store must share caller connection")
        return tuple(RuntimeJobRecord(job["job_id"], job["case_id"], job["kind"])
                     for job in resume_auto_exports(case_id, store=store, admit_auto_exports=admit_auto_exports))
