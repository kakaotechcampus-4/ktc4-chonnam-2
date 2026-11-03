"""Recording repository operations on short caller-owned transactions.

Media inspection/encoding and provider calls happen between operations. No live
Connection, DB cursor or borrowed stream escapes this repository facade.
"""
from contextlib import nullcontext
from .mysql_repository import MySQLRecordingRepository
from .repository import RecordingRepository


class ConnectionRecordingRepository:
    """Lazy caller-connection facade; Case-only work does not require media I/O."""
    def __init__(self, connection, *, storage_root, temp_root=None):
        self.connection, self.storage_root = connection, storage_root
        self.temp_root = temp_root

    def __getattr__(self, name):
        if name.startswith("_") or name not in RecordingRepository.__dict__:
            raise AttributeError(name)

        def call(*args, **kwargs):
            repository = MySQLRecordingRepository(self.connection, storage_root=self.storage_root, temp_root=self.temp_root)
            return getattr(repository, name)(*args, **kwargs)
        return call


class TransactionalRecordingRepository:
    def __init__(self, transaction, *, storage_root, temp_root=None, temp_context=None):
        self.transaction = transaction
        self.storage_root = storage_root
        self.temp_root = temp_root
        self.temp_context = temp_context

    def __getattr__(self, name):
        if name.startswith("_") or name not in RecordingRepository.__dict__:
            raise AttributeError(name)
        method = getattr(MySQLRecordingRepository, name)

        def call(*args, **kwargs):
            owned = []
            def operation(conn):
                context = (self.temp_context() if self.temp_context is not None
                           and name in {"open_prepared_stream", "open_analysis_stream", "get_prepared_content"}
                           else nullcontext(self.temp_root))
                with context as temp_root:
                    value = method(MySQLRecordingRepository(conn, storage_root=self.storage_root,
                        temp_root=temp_root), *args, **kwargs)
                    if name in {"open_prepared_stream", "open_analysis_stream"} and value is not None:
                        owned.append(value[0])
                return value
            try:
                value = self.transaction(operation)
            except BaseException:
                for stream in owned:
                    try:
                        stream.close()
                    except BaseException:
                        pass
                raise
            # Existing transaction runners may invoke the callback again. Only
            # the successfully returned stream escapes; superseded files close.
            for stream in owned:
                if value is None or stream is not value[0]:
                    stream.close()
            return value
        return call
