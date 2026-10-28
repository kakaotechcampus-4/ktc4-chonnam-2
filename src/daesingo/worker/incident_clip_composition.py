"""Production clip context; short repository transactions surround media work."""
from contextlib import contextmanager
from functools import partial

from daesingo.common.db.transactions import run_worker_transaction
from daesingo.common.storage.cleanup import configured_cleanup
from daesingo.common.storage.media import MediaRoot
from daesingo.recording import TransactionalRecordingRepository, LocalIncidentMaterializer
from daesingo.recording.factory import build_incident_recording_service
from daesingo.worker.case_composition import stored_case_store
from daesingo.worker.incident_clip_handlers import incident_clip_registry
from daesingo.worker.incident_clip_inputs import IncidentClipInputs


class IncidentRecordingFactory:
    def __init__(self, *, transaction, storage_root, temp_root, settings, media=None):
        self.transaction, self.storage_root, self.temp_root = transaction, storage_root, temp_root
        self.settings, self.media = settings, media

    @contextmanager
    def __call__(self, data):
        repository = TransactionalRecordingRepository(self.transaction, storage_root=self.storage_root)
        materializer = partial(self.media.materializer, LocalIncidentMaterializer) if self.media is not None else None
        with build_incident_recording_service(repository, self.settings, temp_root=self.temp_root,
                materializer_factory=materializer, case_id=data.case_id) as recording:
            yield recording


def compose_incident_clip_registry(*, engine, startup, service_factory=None):
    def transaction(callback):
        return run_worker_transaction(engine, callback, logger=startup.logger)
    inputs = IncidentClipInputs(transaction=transaction,
        store_factory=lambda conn: stored_case_store(conn, storage_root=startup.config.media_root))
    settings = getattr(startup, "modules", {}).get("recording")
    if service_factory is None and settings is not None and settings.incident_encoding is not None:
        cleanup = configured_cleanup(startup.config, startup.logger)
        media = MediaRoot(next(s for s in cleanup.scanners if s.kind == "temp"))
        service_factory = IncidentRecordingFactory(transaction=transaction, storage_root=startup.config.media_root,
            temp_root=startup.config.temp_root, settings=settings, media=media)
    return incident_clip_registry(load=inputs, service_factory=service_factory)
