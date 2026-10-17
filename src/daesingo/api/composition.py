"""API-owned resources and caller transactions for the public Case boundary."""
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic

from sqlalchemy.engine import Engine
import daesingo.case as case_api
from daesingo.case.store import CaseStore
from daesingo.case.store_mysql import MySQLCaseRepository
from daesingo.common.bootstrap import Startup
from daesingo.common.db import create_api_engine, create_ready_engine
from daesingo.common.db.transactions import run_api_transaction
from daesingo.common.jobs.read_port import read_executions
from daesingo.common.logging import bind_context, safe_correlation
from .health import Readiness
from .storage import storage_available


@dataclass(frozen=True)
class ApiComposition:
    startup: Startup
    engine: Engine
    ready_engine: Engine
    readiness: Readiness
    _lock: object = field(default_factory=Lock, repr=False, compare=False)
    _closed: bool = field(default=False, init=False, repr=False, compare=False)
    cleanup_failed: bool = field(default=False, init=False, repr=False, compare=False)

    def _store(self, connection):
        # Empty Cases need no process-local adapter cache. Keep the facade and
        # its default registry local to this transaction (Case 8-6 is separate).
        return CaseStore(repository=MySQLCaseRepository(),
                         conn=connection, executions=read_executions)

    def get_view(self, case_id: str):
        started = monotonic()
        # RT-02 owns classification, and neither Case nor Runtime owns commit.
        # Do not pass a synchronous logger into the request's DB stack.
        view = run_api_transaction(self.engine,
            lambda conn: case_api.get_view(case_id, store=self._store(conn)))
        with bind_context(**safe_correlation(case_id=view["case_id"])):
            self.readiness.events.emit("api.view.completed", status="200",
                                       duration_ms=(monotonic() - started) * 1000)
        return view

    def create_case(self):
        case_id = run_api_transaction(self.engine,
            lambda conn: case_api.create_case(store=self._store(conn)))
        # The write is acknowledged before this separate public read begins.
        # A failed read cannot make the already committed POST safely retryable.
        try:
            view = self.get_view(case_id)
        except Exception:
            raise RuntimeError("case response unavailable after commit") from None
        return {"case_id": case_id, "case_view": view}

    def close(self):
        with self._lock:
            if self._closed:
                return
            object.__setattr__(self, "_closed", True)
        failure = None
        for close in (self.readiness.close, self.ready_engine.dispose, self.engine.dispose):
            try:
                close()
            except BaseException as error:
                object.__setattr__(self, "cleanup_failed", True)
                if failure is None:
                    failure = error
        if failure is not None:
            raise failure


def compose_api(startup: Startup) -> ApiComposition:
    config = startup.config
    if config.service != "api" or config.ready is None:
        raise ValueError("API startup configuration required")
    engine = create_api_engine(config.db)
    ready_engine = None
    try:
        ready_engine = create_ready_engine(config.db, config.ready)
        def db_probe():
            with ready_engine.connect() as connection:
                return connection.exec_driver_sql("SELECT 1").scalar_one() == 1
        readiness = Readiness(settings=config.ready, db_probe=db_probe,
                              storage_probe=lambda: storage_available(config.media_root), logger=startup.logger)
        return ApiComposition(startup, engine, ready_engine, readiness)
    except BaseException:
        # Construction can fail before a composition/lifespan owner exists.
        # Try every allocated engine, retaining the original fatal/error policy.
        for allocated in (ready_engine, engine):
            if allocated is not None:
                try:
                    allocated.dispose()
                except BaseException:
                    pass
        raise
