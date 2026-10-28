"""Runtime #405 durable terminal notice, separate from result T2 receipts.

All writes participate in caller-owned transactions. Delivery locks Case before
the notice; scans and initial receipt reads never acquire Runtime row locks.
"""
from collections.abc import Callable
from contextvars import Context
from dataclasses import dataclass, field
from datetime import datetime
import logging
import time
from typing import Literal, Protocol

from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection, Engine

from daesingo.common.db.transactions import run_worker_transaction
from daesingo.common.logging import log_event_best_effort
from .repository import _identifier, enqueue
from .schema import job_execution, job_exhaustion_notice


@dataclass(frozen=True, slots=True)
class JobExhaustionNotice:
    notice_id: str
    job_id: str
    case_id: str
    kind: str
    final_execution_id: str
    attempt: int
    exhausted_at: datetime
    terminal_status: Literal['STALE'] = 'STALE'
    reason: Literal['EXHAUSTED'] = 'EXHAUSTED'

    def __post_init__(self):
        try:
            for key, maximum in (('notice_id',128),('job_id',191),('case_id',128),('final_execution_id',128)):
                _identifier(getattr(self, key), key, maximum)
            if (self.kind != 'HINT_EXTRACT' or self.terminal_status != 'STALE' or self.reason != 'EXHAUSTED'
                    or type(self.attempt) is not int or self.attempt < 1
                    or type(self.exhausted_at) is not datetime or self.exhausted_at.tzinfo is not None):
                raise ValueError()
        except Exception:
            raise ValueError('invalid exhaustion notice') from None


def validated_notice(value: JobExhaustionNotice) -> JobExhaustionNotice:
    if type(value) is not JobExhaustionNotice:
        raise ValueError('invalid exhaustion notice')
    return JobExhaustionNotice(**{name:getattr(value, name) for name in JobExhaustionNotice.__dataclass_fields__})


@dataclass(frozen=True, slots=True)
class ExhaustionResult:
    status: Literal['APPLIED', 'NO_CHANGE']
    appended_job_records: list[dict] = field(default_factory=list)

    def __post_init__(self):
        try:
            if type(self.status) is not str or self.status not in ('APPLIED','NO_CHANGE'):
                raise ValueError()
            if type(self.appended_job_records) is not list:
                raise ValueError()
            expected = 1 if self.status == 'APPLIED' else 0
            if len(self.appended_job_records) != expected:
                raise ValueError()
            projected = []
            for record in self.appended_job_records:
                if type(record) is not dict or record['kind'] != 'COARSE_SEARCH':
                    raise ValueError()
                projected.append({key:_identifier(record[key], key, maximum)
                    for key,maximum in (('job_id',191),('case_id',128),('kind',64))})
            object.__setattr__(self, 'appended_job_records', projected)
        except Exception:
            raise ValueError('invalid exhaustion result') from None


class ExhaustionReceiver(Protocol):
    def receive(self, conn: Connection, notice: JobExhaustionNotice) -> ExhaustionResult:
        """Lock Case first. Never commit, rollback or retry the caller transaction."""
        ...


def notice_from_row(row) -> JobExhaustionNotice:
    return JobExhaustionNotice(**{key:row[key] for key in JobExhaustionNotice.__dataclass_fields__})


def verify_execution(conn: Connection, notice: JobExhaustionNotice, trace_id: str) -> None:
    """Verify immutable terminal ledger facts without a Runtime-first lock."""
    row = conn.execute(select(job_execution).where(
        job_execution.c.execution_id == notice.final_execution_id)).mappings().one_or_none()
    expected = {'execution_id':notice.final_execution_id, 'job_id':notice.job_id, 'case_id':notice.case_id, 'kind':notice.kind,
        'attempt':notice.attempt, 'status':notice.terminal_status, 'ended_at':notice.exhausted_at,
        'trace_id':trace_id}
    if row is None or any(row[key] != value for key,value in expected.items()):
        raise ValueError('exhaustion terminal facts mismatch')
    # A later STOP_ANALYSIS may mark an already-STALE execution. That mutable
    # cancellation marker does not invalidate the durable exhaustion; Case
    # returns NO_CHANGE(CANCELLED). Generation checks the marker under its lock.
    # A later attempt, however, contradicts final exhaustion.
    later = conn.scalar(select(job_execution.c.execution_id).where(
        job_execution.c.job_id == notice.job_id, job_execution.c.attempt > notice.attempt).limit(1))
    if later is not None:
        raise ValueError('exhaustion terminal facts mismatch')


def acknowledge_exhaustion(conn: Connection, notice: JobExhaustionNotice,
                           receiver: ExhaustionReceiver, trace_id: str) -> ExhaustionResult:
    """Case save, enqueue and receipt are one caller-owned transaction.

    The caller must re-read the receipt on each whole-transaction replay. Case
    serializes concurrent deliveries before Runtime takes the notice row lock.
    """
    if not conn.in_transaction():
        raise ValueError('exhaustion requires a caller-owned transaction')
    notice = validated_notice(notice)
    trace = _identifier(trace_id, 'trace_id', 128)
    # Separate copy prevents a receiver mutating our expected immutable facts.
    result = receiver.receive(conn, validated_notice(notice))
    if type(result) is not ExhaustionResult:
        raise ValueError('invalid exhaustion result')
    result = ExhaustionResult(result.status, result.appended_job_records)
    if any(job['case_id'] != notice.case_id for job in result.appended_job_records):
        raise ValueError('invalid exhaustion job case')
    stored = conn.execute(select(job_exhaustion_notice).where(
        job_exhaustion_notice.c.notice_id == notice.notice_id).with_for_update()).mappings().one_or_none()
    if stored is None or notice_from_row(stored) != notice or stored['trace_id'] != trace:
        raise ValueError('exhaustion immutable facts mismatch')
    verify_execution(conn, notice, trace)
    if stored['case_acknowledged_at'] is not None:
        if result.status == 'APPLIED':
            raise ValueError('exhaustion receipt conflict')
        return result
    enqueue(conn, result.appended_job_records, trace)
    changed = conn.execute(update(job_exhaustion_notice).where(
        job_exhaustion_notice.c.notice_id == notice.notice_id,
        job_exhaustion_notice.c.case_acknowledged_at.is_(None),
    ).values(case_acknowledged_at=func.utc_timestamp(6))).rowcount
    if changed != 1:
        raise ValueError('exhaustion receipt not recorded')
    return result


def redeliver_exhaustion_once(engine: Engine, receiver: ExhaustionReceiver, *,
                              sleep: Callable = time.sleep, logger: logging.Logger | None = None
                              ) -> tuple[ExhaustionResult, ...]:
    """Nonlocking scan; isolated candidate transactions; scan DB faults propagate."""
    with engine.connect() as conn:
        candidates = conn.execute(select(job_exhaustion_notice.c.notice_id).where(
            job_exhaustion_notice.c.case_acknowledged_at.is_(None)
        ).order_by(job_exhaustion_notice.c.notice_id)).scalars().all()
    results = []
    for notice_id in candidates:
        def operation(conn):
            stored = conn.execute(select(job_exhaustion_notice).where(
                job_exhaustion_notice.c.notice_id == notice_id)).mappings().one_or_none()
            if stored is None or stored['case_acknowledged_at'] is not None:
                return None
            return acknowledge_exhaustion(conn, notice_from_row(stored), receiver, stored['trace_id'])
        try:
            result = run_worker_transaction(engine, operation, sleep=sleep, logger=logger)
        except Exception:
            if logger is not None:
                # Suppress even ambient correlation: this failure event exposes
                # neither notice identity, payload nor original exception.
                Context().run(log_event_best_effort, logger, 'runtime.exhaustion.failed',
                    level=logging.ERROR, status='FAILED')
            continue
        if result is not None:
            results.append(result)
    return tuple(results)
