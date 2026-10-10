"""Single-execution scheduling; only short claim/T1 callbacks touch the DB."""

from collections.abc import Callable
import logging
from threading import Event
import time

from sqlalchemy.exc import DBAPIError, TimeoutError

from daesingo.common.config import WorkerSettings
from daesingo.common.db.errors import TransactionRetryExhausted, db_reason
from daesingo.common.jobs.execution import ExecutionContext, HandlerResult, runtime_failure, validated_terminal
from daesingo.common.jobs.repository import ClaimedExecution, ClaimLostError
from daesingo.common.logging import bind_context, log_event_best_effort, safe_correlation

_DB_ERRORS = (DBAPIError, TimeoutError, TransactionRetryExhausted)


class WorkerLoop:
    def __init__(
        self, *, claim: Callable[[], ClaimedExecution | None],
        dispatch: Callable[[ExecutionContext], HandlerResult],
        record: Callable[[ExecutionContext, HandlerResult], bool],
        settings: WorkerSettings, stop: Event, logger: logging.Logger,
        reflect: Callable[[ExecutionContext, HandlerResult], object] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        idle_wait: Callable[[float], object] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.claim, self.dispatch, self.record = claim, dispatch, record
        self.settings, self.stop, self.logger = settings, stop, logger
        self.reflect = reflect
        self.sleep, self.idle_wait, self.clock = sleep, idle_wait or sleep, clock

    def _db_error(self, error: Exception):
        # Never serialize the exception, SQL, parameters or raw driver message.
        reason = db_reason(error) or "db_failure"
        log_event_best_effort(self.logger, "runtime.db.error_count", level=logging.ERROR,
                  status=reason.upper())

    def run(self) -> None:
        while not self.stop.is_set():
            try:
                claimed = self.claim()
            except _DB_ERRORS as error:
                self._db_error(error)
                self.idle_wait(self.settings.error_backoff_sec)
                continue
            except ClaimLostError:
                log_event_best_effort(self.logger, "runtime.execution.claim_lost", level=logging.WARNING)
                self.idle_wait(self.settings.error_backoff_sec)
                continue
            if claimed is None:
                if not self.stop.is_set():
                    self.idle_wait(self.settings.idle_poll_sec)
                continue
            context = ExecutionContext(claimed.execution_id, claimed.job_id,
                                       claimed.case_id, claimed.kind, claimed.attempt, claimed.trace_id)
            with bind_context(**safe_correlation(
                trace_id=context.trace_id, case_id=context.case_id,
                job_id=context.job_id, execution_id=context.execution_id,
            )):
                started = self.clock()
                log_event_best_effort(self.logger, "runtime.execution.started", status="RUNNING")
                try:
                    result = self.dispatch(context)
                    if not isinstance(result, HandlerResult):
                        result = runtime_failure("RUNTIME_INVALID_RESULT")
                    else:
                        result = validated_terminal(result)
                except Exception:
                    result = runtime_failure("RUNTIME_HANDLER_ERROR")
                # Preserve this result through every DB retry. Stop signals only
                # apply at the next idle point; they cannot interrupt T1 either.
                while True:
                    try:
                        committed = self.record(context, result)
                        break
                    except _DB_ERRORS as error:
                        self._db_error(error)
                        self.sleep(self.settings.error_backoff_sec)
                if committed:
                    log_event_best_effort(self.logger, "runtime.execution.completed", status=result.status,
                              duration_ms=max(0, (self.clock() - started) * 1000))
                    if self.reflect is not None:
                        try:
                            self.reflect(context, result)
                        except _DB_ERRORS as error:
                            # RT-06 owns T2 redelivery. Back off before the next
                            # claim, using the same interruptible idle boundary.
                            self._db_error(error)
                            log_event_best_effort(self.logger, "runtime.reflect.failed", level=logging.ERROR,
                                                  status="FAILED")
                            self.idle_wait(self.settings.error_backoff_sec)
                        except Exception:
                            # T1 is durable. RT-06 owns redelivery, not this loop.
                            log_event_best_effort(self.logger, "runtime.reflect.failed", level=logging.ERROR,
                                                  status="FAILED")
                else:
                    log_event_best_effort(self.logger, "runtime.execution.finish_rejected", level=logging.WARNING)
