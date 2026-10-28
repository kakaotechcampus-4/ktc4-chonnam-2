"""Explicit OCR factory registration; no fixture provider or implicit model load."""
from contextlib import contextmanager

from daesingo.common.db.transactions import run_worker_transaction
from daesingo.recording import RecordingService, TransactionalRecordingRepository
from daesingo.worker.case_composition import stored_case_store
from daesingo.worker.readout_handlers import ReadoutSession, readout_registry
from daesingo.worker.readout_inputs import ReadoutInputs


class RecordingOcrFactory:
    """Own a Recording context per execution, using only public clip facts.

    ocr_factory is explicit: e.g. PaddleOcrProvider(RecordingFrameSource(recording)).
    Its model/settings and installation remain Readout deployment concerns.
    """
    def __init__(self, *, recording_factory, ocr_factory):
        self.recording_factory, self.ocr_factory = recording_factory, ocr_factory

    @contextmanager
    def __call__(self, data):
        with self.recording_factory(data) as recording:
            clip = recording.get_incident_clip(data.incident_clip_ref)
            if clip.incident_clip_ref != data.incident_clip_ref:
                raise ValueError("Readout Recording clip binding mismatch")
            yield ReadoutSession(self.ocr_factory(recording), clip.duration_sec)


def recording_ocr_factory(*, transaction, storage_root, ocr_factory):
    """Build the execution-local durable Recording context for an explicit OCR."""
    @contextmanager
    def recording(data):
        repository = TransactionalRecordingRepository(transaction, storage_root=storage_root)
        with RecordingService(repository, case_id=data.case_id) as service:
            yield service
    return RecordingOcrFactory(recording_factory=recording, ocr_factory=ocr_factory)


def compose_readout_registry(*, engine, startup, provider_factory=None):
    def transaction(callback):
        return run_worker_transaction(engine, callback, logger=startup.logger)
    inputs = ReadoutInputs(transaction=transaction,
        store_factory=lambda conn: stored_case_store(conn, storage_root=startup.config.media_root))
    return readout_registry(load=inputs, provider_factory=provider_factory)
