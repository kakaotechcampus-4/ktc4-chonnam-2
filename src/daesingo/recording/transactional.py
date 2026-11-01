"""Recording repository operations on short caller-owned transactions.

Media inspection/encoding and provider calls happen between operations. No live
Connection, DB cursor or borrowed stream escapes this repository facade.
"""
from .mysql_repository import MySQLRecordingRepository
from .repository import RecordingRepository


class ConnectionRecordingRepository:
    """Lazy caller-connection facade; Case-only work does not require media I/O."""
    def __init__(self, connection, *, storage_root):
        self.connection, self.storage_root = connection, storage_root

    def __getattr__(self, name):
        if name.startswith("_") or name not in RecordingRepository.__dict__:
            raise AttributeError(name)

        def call(*args, **kwargs):
            repository = MySQLRecordingRepository(self.connection, storage_root=self.storage_root)
            return getattr(repository, name)(*args, **kwargs)
        return call


class TransactionalRecordingRepository:
    def __init__(self, transaction, *, storage_root):
        self.transaction = transaction
        self.storage_root = storage_root

    def __getattr__(self, name):
        if name.startswith("_") or name not in RecordingRepository.__dict__:
            raise AttributeError(name)
        method = getattr(MySQLRecordingRepository, name)

        def call(*args, **kwargs):
            return self.transaction(lambda conn: method(
                MySQLRecordingRepository(conn, storage_root=self.storage_root), *args, **kwargs))
        return call
