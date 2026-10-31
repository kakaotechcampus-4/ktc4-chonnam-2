"""Caller-transaction stored Case adapters for T2 and separate exhaustion delivery."""
from daesingo.case.store import CaseStore
from daesingo.case.store_mysql import MySQLCaseRepository
from daesingo.case.stored_observation import stored_adapter_factory
from daesingo.evidence import attachment_constraint
from daesingo.case.timeline_source import RecordingSequentialTimelineSource
from daesingo.common.jobs.produced import ProducedReader
from daesingo.common.jobs.read_port import read_executions
from daesingo.recording import RecordingFacts, RecordingService, ConnectionRecordingRepository
from daesingo.worker.case_reflector import CaseReflector
from daesingo.case.exhaustion_adapter import CaseExhaustionReceiver


def stored_case_store(conn, *, storage_root, reader=None):
    reader = reader if reader is not None else ProducedReader()
    facts = RecordingFacts(ConnectionRecordingRepository(conn, storage_root=storage_root))
    return CaseStore(repository=MySQLCaseRepository(), conn=conn, executions=read_executions,
        adapter_factory=stored_adapter_factory(reader=reader, executions=read_executions, recording=facts,
            export_max_byte_size=attachment_constraint("PLATE_IMAGE")["max_byte_size"]))


class StoredCaseReflector:
    def __init__(self, *, storage_root=None, startup=None):
        self.storage_root, self.startup = storage_root, startup
        self.reader = ProducedReader()

    def reflect(self, conn, incoming):
        root = self.storage_root if self.storage_root is not None else self.startup.config.media_root
        # The caller owns T2/receipt/enqueue and the Connection. No STALE policy
        # or exhaustion policy is introduced by this T2 adapter.
        with RecordingService(ConnectionRecordingRepository(conn, storage_root=root)) as recording:
            reflector = CaseReflector(reader=self.reader,
                timelines=RecordingSequentialTimelineSource(recording),
                store_factory=lambda connection: stored_case_store(connection, storage_root=root, reader=self.reader))
            return reflector.reflect(conn, incoming)


class StoredCaseExhaustionReceiver:
    def __init__(self, *, storage_root=None, startup=None):
        self.storage_root, self.startup = storage_root, startup

    def receive(self, conn, notice):
        root = self.storage_root if self.storage_root is not None else self.startup.config.media_root
        with RecordingService(ConnectionRecordingRepository(conn, storage_root=root)) as recording:
            receiver = CaseExhaustionReceiver(
                timelines=RecordingSequentialTimelineSource(recording),
                store_factory=lambda connection: stored_case_store(connection, storage_root=root))
            return receiver.receive(conn, notice)
