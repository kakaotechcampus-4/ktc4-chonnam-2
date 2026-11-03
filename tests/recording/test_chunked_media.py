"""Bounded read validation and metadata projections (not DB acceptance)."""

import hashlib
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import mysql

from daesingo.recording.mysql_repository import MySQLRecordingRepository
from test_ownership_reads import MP4


def test_metadata_lookup_does_not_select_content():
    repo = object.__new__(MySQLRecordingRepository)
    statements = []
    repo._execute = lambda statement: (
        statements.append(statement)
        or SimpleNamespace(mappings=lambda: SimpleNamespace(one_or_none=lambda: None))
    )
    assert repo.get_analysis_source("as-test") is None
    assert "content" not in str(statements[0].compile(dialect=mysql.dialect()))


def info():
    return {
        "version": 1,
        "chunk_size": 512,
        "chunk_count": (len(MP4) + 511) // 512,
        "content_type": "video/mp4",
        "byte_size": len(MP4),
        "sha256": hashlib.sha256(MP4).hexdigest(),
    }


@pytest.mark.parametrize(
    "damage",
    [None, "missing", "extra", "short", "hash", "version", "order", "oversize"],
)
def test_detached_file_validates_manifest_and_cleans_failures(
    tmp_path, monkeypatch, damage
):
    from daesingo.recording import chunked_media as cm

    manifest = info()
    parts = [MP4[i : i + 512] for i in range(0, len(MP4), 512)]
    if damage == "missing":
        parts.pop()
    if damage == "extra":
        parts.append(b"x")
    if damage == "short":
        parts[0] = parts[0][:-1]
    if damage == "hash":
        manifest["sha256"] = "0" * 64
    if damage == "version":
        manifest["version"] = 99
    if damage == "order":
        parts.reverse()
    if damage == "oversize":
        parts[0] += b"x"
    opened = []
    original = cm.TemporaryFile

    def temporary(**kwargs):
        stream = original(**kwargs)
        opened.append(stream)
        return stream

    monkeypatch.setattr(cm, "TemporaryFile", temporary)
    if damage:
        with pytest.raises(ValueError):
            cm.detached_stream(iter(parts), manifest, temp_root=tmp_path)
        assert all(stream.closed for stream in opened)
    else:
        with cm.detached_stream(iter(parts), manifest, temp_root=tmp_path) as stream:
            assert stream.read() == MP4
            assert stream.seek(0) == 0
        assert all(stream.closed for stream in opened)
    # Windows directory enumeration can retain a delete-pending name briefly.
    assert not any(path.exists() for path in tmp_path.iterdir())


def test_stream_cancel_closes_owned_file(tmp_path, monkeypatch):
    from daesingo.recording import chunked_media as cm

    opened = []
    original = cm.TemporaryFile

    def temporary(**kwargs):
        stream = original(**kwargs)
        opened.append(stream)
        return stream

    monkeypatch.setattr(cm, "TemporaryFile", temporary)

    def cancelled():
        yield MP4[:512]
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        cm.detached_stream(cancelled(), info(), temp_root=tmp_path)
    assert opened and all(s.closed for s in opened)


def test_savepoint_cleanup_failure_keeps_original_and_blocks_commit():
    class CleanupFailure(Exception):
        pass

    class OriginalFailure(Exception):
        pass

    class Savepoint:
        is_active = True

        def rollback(self):
            raise CleanupFailure

    class Connection:
        invalidated = False

        def begin_nested(self):
            return Savepoint()

        def invalidate(self):
            self.invalidated = True

    repository = object.__new__(MySQLRecordingRepository)
    repository._connection = Connection()
    with pytest.raises(OriginalFailure):
        with repository._publish_savepoint():
            raise OriginalFailure
    assert repository._connection.invalidated


def test_mp4_signature_failure_closes_file(tmp_path):
    from daesingo.recording.chunked_media import detached_stream

    value = b"x" * len(MP4)
    manifest = {**info(), "sha256": hashlib.sha256(value).hexdigest()}
    with pytest.raises(ValueError):
        detached_stream(
            (value[i : i + 512] for i in range(0, len(value), 512)),
            manifest,
            temp_root=tmp_path,
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("phase", ["begin", "release"])
def test_savepoint_control_errors_keep_errno_without_private_diagnostics(phase):
    import sqlalchemy as sa

    error = sa.exc.OperationalError(
        "private-sql",
        {"secret": "private-parameter"},
        Exception(2013, "private-driver"),
        connection_invalidated=True,
    )

    class Savepoint:
        is_active = True

        def commit(self):
            raise error

        def rollback(self):
            pass

    class Connection:
        def begin_nested(self):
            if phase == "begin":
                raise error
            return Savepoint()

    repository = object.__new__(MySQLRecordingRepository)
    repository._connection = Connection()
    with pytest.raises(sa.exc.OperationalError) as caught:
        with repository._publish_savepoint():
            pass
    assert caught.value.connection_invalidated
    assert caught.value.orig.args[0] == 2013
    assert "private" not in str(caught.value)


@pytest.mark.parametrize("method", ["open_prepared_stream", "open_analysis_stream"])
def test_transaction_failure_closes_detached_result(monkeypatch, method):
    from io import BytesIO
    from daesingo.recording import TransactionalRecordingRepository
    from daesingo.recording import transactional

    streams = []

    class Repository:
        def __init__(self, *args, **kwargs):
            pass

    def opened(self, *args):
        stream = BytesIO(MP4)
        streams.append(stream)
        return stream, "video/mp4"

    setattr(Repository, method, opened)
    monkeypatch.setattr(transactional, "MySQLRecordingRepository", Repository)

    def transaction(callback):
        callback(None)
        raise RuntimeError("commit failed")

    facade = TransactionalRecordingRepository(transaction, storage_root="unused")
    with pytest.raises(RuntimeError):
        getattr(facade, method)("ref")
    assert streams and all(stream.closed for stream in streams)


def test_case_media_metadata_does_not_open_or_read_content(monkeypatch):
    from daesingo.recording import RecordingService, load_recording_fixture
    from daesingo.recording.repository import InMemoryRecordingRepository

    repository = InMemoryRecordingRepository()
    media = (
        load_recording_fixture("scenario_happy_001")
        .analysis_sources[0]
        .model_copy(update={"byte_size": len(MP4), "availability": "AVAILABLE"})
    )
    repository.add_prepared_media(media, MP4, case_id="case")

    def forbidden(*args):
        pytest.fail("metadata read opened payload")

    monkeypatch.setattr(repository, "open_prepared_stream", forbidden)
    monkeypatch.setattr(repository, "get_prepared_content", forbidden)
    with RecordingService(repository) as service:
        (facts,) = service.list_case_asset_facts("case")
        assert facts.byte_size == len(MP4) and facts.availability == "AVAILABLE"


def test_temp_context_exit_failure_closes_detached_result(monkeypatch):
    from contextlib import contextmanager
    from io import BytesIO
    from daesingo.recording import TransactionalRecordingRepository
    from daesingo.recording import transactional

    stream = BytesIO(MP4)

    class Repository:
        def __init__(self, *args, **kwargs):
            assert kwargs["temp_root"] == "pinned"

        def open_analysis_stream(self, ref):
            return stream, "video/mp4"

    @contextmanager
    def temp_context():
        yield "pinned"
        raise RuntimeError("temp lease exit failed")

    monkeypatch.setattr(transactional, "MySQLRecordingRepository", Repository)
    repository = TransactionalRecordingRepository(
        lambda callback: callback(None),
        storage_root="unused",
        temp_context=temp_context,
    )
    with pytest.raises(RuntimeError):
        repository.open_analysis_stream("ref")
    assert stream.closed
