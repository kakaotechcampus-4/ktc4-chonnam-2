"""Snapshot/read and immutable publish transactions surround a DB-free export."""
from contextlib import contextmanager

from daesingo.common.db.transactions import run_worker_transaction
from daesingo.common.config import RuntimeConfig
from daesingo.common.storage.cleanup import configured_cleanup
from daesingo.common.storage.media import MediaRoot
from daesingo.recording import RecordingService
from daesingo.recording.mysql_repository import MySQLRecordingRepository
from daesingo.recording.exports import LocalExportMaterializer, export_snapshot, publish_exports
from daesingo.worker.case_composition import stored_case_store
from daesingo.worker.export_handlers import export_registry
from daesingo.worker.export_inputs import ExportInputs


class ExportRecordingFactory:
    def __init__(self, *, transaction, storage_root, temp_root, media=None):
        self.transaction, self.storage_root, self.temp_root, self.media = transaction, storage_root, temp_root, media

    @contextmanager
    def __call__(self, data):
        def repository(conn):
            return MySQLRecordingRepository(conn, storage_root=self.storage_root)
        snapshot = self.transaction(lambda conn: export_snapshot(repository(conn), data.case_id, data.request))
        materializer = self.media.materializer(LocalExportMaterializer) if self.media else LocalExportMaterializer(temp_root=self.temp_root)
        with RecordingService(snapshot, export_materializer=materializer, case_id=data.case_id) as recording:
            yield recording
            # Same output identity/bytes on transaction retry or lost COMMIT ACK.
            self.transaction(lambda conn: publish_exports(snapshot, repository(conn), data.case_id))


def compose_export_registry(*, engine, startup, service_factory=None):
    def transaction(callback):
        return run_worker_transaction(engine, callback, logger=startup.logger)
    inputs = ExportInputs(transaction=transaction,
        store_factory=lambda conn: stored_case_store(conn, storage_root=startup.config.media_root))
    if service_factory is None and isinstance(getattr(startup, "config", None), RuntimeConfig):
        cleanup = configured_cleanup(startup.config, startup.logger)
        media = MediaRoot(next(s for s in cleanup.scanners if s.kind == "temp"))
        service_factory = ExportRecordingFactory(transaction=transaction, storage_root=startup.config.media_root,
            temp_root=startup.config.temp_root, media=media)
    return export_registry(load=inputs, service_factory=service_factory)
