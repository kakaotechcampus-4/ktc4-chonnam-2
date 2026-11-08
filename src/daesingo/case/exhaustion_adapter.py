"""Runtime이 보낸 job 소진 알림(재시도까지 `STALE`로 끝남)을 case에 반영하는 어댑터.

호출자 DB 연결로 `CaseStore`를 만들고 `service.receive_hint_exhaustion()`에 넘긴다.
정책은 service가, 알림 전달은 Runtime이 맡는다(#405).
"""
from collections.abc import Callable

from sqlalchemy.engine import Connection

from daesingo.common.jobs.exhaustion import JobExhaustionNotice, ExhaustionResult, validated_notice
from daesingo.common.jobs.read_port import read_executions
from . import service
from .analysis_start import InitialSearchBudget
from .store import CaseStore
from .store_mysql import MySQLCaseRepository
from .timeline_source import CaseTimelineSource


def _store(conn: Connection) -> CaseStore:
    return CaseStore(repository=MySQLCaseRepository(), conn=conn, executions=read_executions)


class CaseExhaustionReceiver:
    def __init__(self, *, timelines: CaseTimelineSource,
                 store_factory: Callable[[Connection], CaseStore] = _store,
                 budget: InitialSearchBudget | None = None):
        self.timelines, self.store_factory, self.budget = timelines, store_factory, budget

    def receive(self, conn: Connection, notice: JobExhaustionNotice) -> ExhaustionResult:
        notice = validated_notice(notice)
        store = self.store_factory(conn)
        if store.conn is not conn:
            raise ValueError('exhaustion store must share caller connection')
        result = service.receive_hint_exhaustion(notice.case_id, job_id=notice.job_id,
            kind=notice.kind, store=store, timelines=self.timelines, budget=self.budget)
        return ExhaustionResult(result.status, result.appended_job_records)
