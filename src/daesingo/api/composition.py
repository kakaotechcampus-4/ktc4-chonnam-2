"""API-owned resources and caller transactions for the public Case boundary."""
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from time import monotonic

from sqlalchemy.engine import Engine
import daesingo.case as case_api
from daesingo.case.store import CaseStore, validate_case_id
from daesingo.case.store_mysql import MySQLCaseRepository
from daesingo.case.timeline_source import RecordingSequentialTimelineSource
from daesingo.common.bootstrap import Startup
from daesingo.common.db import create_api_engine, create_ready_engine
from daesingo.common.db.transactions import run_api_transaction
from daesingo.common.jobs.read_port import read_executions
from daesingo.common.jobs.cancel import request_cancel
from daesingo.common.jobs.repository import enqueue
from daesingo.common.logging import bind_context, safe_correlation
from daesingo.common.storage.cleanup import configured_cleanup
from daesingo.common.storage.media import MediaRoot
from daesingo.recording import RecordingService, FfprobeMediaProbe, RecordingCapabilityError, ContractRef
from daesingo.recording.mysql_repository import MySQLRecordingRepository
from daesingo.case.domain import SourceNotAccepted
from .health import Readiness
from .storage import storage_available


def _file_identity(path):
    value = path.stat()
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


class _PreparedMediaProbe:
    """Request-local adapter for Recording's existing public probe injection.

    File hashes/ffprobe run without a checkout. A typed failed result is deferred
    until registration so missing/non-INTAKE Case404/409 still take precedence.
    No new Recording capability, schema, taxonomy or cache lifetime is introduced.
    """
    def __init__(self, path):
        self._failure = None
        try:
            self._path = Path(path).resolve(strict=True)
            self._identity = _file_identity(self._path)
            self._source = FfprobeMediaProbe().probe(self._path)
            if _file_identity(self._path) != self._identity:
                raise RecordingCapabilityError('TEMPORARY_FAILURE', 'source changed during preparation')
        except OSError:
            self._failure = RecordingCapabilityError('TEMPORARY_FAILURE', 'source preparation unavailable')
        except Exception as error:
            self._failure = error

    def probe(self, path):
        if self._failure is not None:
            raise self._failure from None
        try:
            unchanged = Path(path).resolve(strict=True) == self._path and _file_identity(self._path) == self._identity
        except OSError:
            unchanged = False
        if not unchanged:
            raise RecordingCapabilityError('TEMPORARY_FAILURE', 'prepared source changed') from None
        return self._source


@dataclass(frozen=True)
class ApiComposition:
    startup: Startup
    engine: Engine
    ready_engine: Engine
    readiness: Readiness
    recording: RecordingService = field(default_factory=RecordingService, repr=False, compare=False)
    cleanup: object = field(default=None, repr=False, compare=False)
    media: object = field(default=None, repr=False, compare=False)
    _lock: object = field(default_factory=Lock, repr=False, compare=False)
    _closed: bool = field(default=False, init=False, repr=False, compare=False)
    cleanup_failed: bool = field(default=False, init=False, repr=False, compare=False)

    def _store(self, connection):
        # Keep the facade and its default registry local to this transaction
        # (Case 8-6 is separate).
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

    def execute_command(self, payload, trace_id: str):
        def operation(conn):
            result = case_api.execute_command(payload, store=self._store(conn),
                timelines=RecordingSequentialTimelineSource(self.recording))
            if result.cancelled_job_ids:
                request_cancel(conn, result.cancelled_job_ids)
            if result.appended_job_records:
                enqueue(conn, result.appended_job_records, trace_id)
            return result
        # One attempt, Case lock first, same Connection and acknowledged commit.
        # The returned Case body was built before enqueue and is left untouched.
        return run_api_transaction(self.engine, operation)

    def register_source(self, case_id, path, original_filename):
        prepared = _PreparedMediaProbe(path)
        def operation(conn):
            store = self._store(conn)
            case = store.load_for_update(case_id)
            if case.stage != 'INTAKE':
                raise SourceNotAccepted()
            with RecordingService(MySQLRecordingRepository(conn,
                    storage_root=self.startup.config.media_root), media_probe=prepared) as recording:
                registered = recording.register_local_source(path,
                    original_filename=original_filename, case_id=case_id)
                case_api.record_source_registered(case_id,
                    registered.source_asset.model_dump(mode='json'),
                    media_streams=[s.model_dump(mode='json') for s in registered.media_streams], store=store)
                return registered.source_asset.source_asset_ref
        source_ref = run_api_transaction(self.engine, operation)
        try:
            view = self.get_view(case_id)
        except Exception:
            # A post-commit view failure must never promise non-application.
            raise RuntimeError('source response unavailable after commit') from None
        return {'case_id': case_id, 'source_asset_ref': source_ref, 'case_view': view}

    def load_frame(self, case_id: str, frame_ref: str):
        def operation(conn):
            # Case existence is checked with the existing public store. No new
            # association, projection mediation or Case callback is introduced.
            self._store(conn).get_case(case_id)
            with RecordingService(MySQLRecordingRepository(conn,
                    storage_root=self.startup.config.media_root)) as recording:
                return recording.read_owned_frame_image(case_id, frame_ref)
        # Only detached bytes/metadata escape; the caller connection is returned
        # before the route constructs headers or starts transmitting the body.
        return run_api_transaction(self.engine, operation)

    def load_asset(self, case_id: str, asset_ref: str):
        validate_case_id(case_id)
        def operation(conn):
            self._store(conn).get_case(case_id)
            with RecordingService(MySQLRecordingRepository(conn,
                    storage_root=self.startup.config.media_root)) as recording:
                if not recording.owns_asset(case_id, ContractRef(kind='derived_asset', ref=asset_ref)):
                    raise RecordingCapabilityError('UNKNOWN_REF', 'asset is not owned')
                opened = recording.open_derived_asset(asset_ref)
                with opened.stream:
                    content = opened.stream.read()
                if not isinstance(content, bytes) or len(content) != opened.byte_size:
                    raise RuntimeError('stored asset read is incomplete')
                return content, opened.content_type
        # Recording uses the caller Connection. Close its stream before ending
        # the transaction; only detached bytes and media type reach the route.
        return run_api_transaction(self.engine, operation)

    def close(self):
        with self._lock:
            if self._closed:
                return
            object.__setattr__(self, "_closed", True)
        failure = None
        closes = ((self.cleanup.stop_and_join,) if self.cleanup is not None else ())
        for close in (*closes, self.readiness.close, self.ready_engine.dispose, self.engine.dispose):
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
        cleanup = configured_cleanup(config, startup.logger, emit=readiness.events.emit)
        media = MediaRoot(next(s for s in cleanup.scanners if s.kind == 'temp'))
        return ApiComposition(startup, engine, ready_engine, readiness, cleanup=cleanup, media=media)
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
