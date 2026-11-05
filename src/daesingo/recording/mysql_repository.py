"""Recording-owned persistence on the caller's Connection.

No outer transaction completion, retries, filesystem publication or connection ownership.
Contract JSON and frame bytes share InnoDB DML. Stream reads lock their row until
the caller ends its transaction, serializing same-stream frame identity creation.
"""

from collections.abc import Callable
from contextlib import contextmanager, nullcontext
from decimal import Decimal
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import BinaryIO

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import LONGBLOB, MEDIUMBLOB, insert
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from . import models as m
from .probe import LocalSource, ProbedStream
from .media_content import derived_content, descriptor, checked_content, frame_format, identity
from .durable import media_identity, prepared_content, observation_payload, observation_from_payload
from .publication import PublishRegistration, managed_publish_locator, registration_from_payloads
from .chunked_media import MAX_CHUNK_BYTES, COMMAND_ALLOWANCE, checked_manifest, legacy_manifest, detached_stream
from .prepared_metadata import encode_prepared_payload, decode_prepared_payload

_PREPARED_KINDS = frozenset({'analysis_source', 'incident_clip'})
# Release identity, not configuration. A final writer release changes this
# default deliberately, with its own SHA/image/compatibility approval.
PREPARED_WRITE_FORMAT = "chunked"


def prepared_command_limits(packet, *, write_format, command_budget=None):
    """Shared writer/startup calculation; actual rendered SQL is guarded too."""
    if type(packet) is not int or packet <= 0:
        raise ValueError("invalid prepared-media packet limit")
    if write_format not in ("legacy", "chunked"):
        raise ValueError("invalid prepared-media write format")
    if command_budget is not None and (type(command_budget) is not int or command_budget <= COMMAND_ALLOWANCE):
        raise ValueError("invalid prepared-media command budget")
    # Reserve 64 KiB for packet/protocol slack and room for 2x binary escaping.
    # Legacy keeps its whole-BLOB budget; chunked defaults to 1 MiB commands.
    default_budget = packet - 64*1024 if write_format == "legacy" else 1024*1024
    budget = min(command_budget or default_budget, packet - 64*1024)
    size = min(MAX_CHUNK_BYTES, (budget-COMMAND_ALLOWANCE)//2)
    if size <= 0:
        raise ValueError("insufficient prepared-media command budget")
    return budget, size


metadata = sa.MetaData()
entries = sa.Table(
    "recording_entry", metadata,
    sa.Column("kind", sa.String(32, collation="ascii_bin"), nullable=False),
    sa.Column("entry_key", sa.String(64, collation="ascii_bin"), nullable=False),
    sa.Column("ordinal", sa.BigInteger, primary_key=True, autoincrement=True),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.Column("content", LONGBLOB),
    sa.UniqueConstraint("kind", "entry_key", name="uq_recording_entry_identity"),
    mysql_engine="InnoDB", mysql_charset="utf8mb4",
)
chunks = sa.Table(
    "recording_media_chunk", metadata,
    sa.Column("kind", sa.String(32, collation="ascii_bin"), primary_key=True),
    sa.Column("entry_key", sa.String(64, collation="ascii_bin"), primary_key=True),
    sa.Column("chunk_index", sa.Integer, primary_key=True),
    sa.Column("content", MEDIUMBLOB, nullable=False),
    mysql_engine="InnoDB", mysql_charset="utf8mb4",
)


def _key(identity) -> str:
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _coordinate(value: float) -> str:
    decimal = Decimal(str(value))
    return str((decimal if decimal else Decimal(0)).normalize())


def _gps_identity(value):
    # Model equality treats either floating zero as equal, including nested
    # coordinates/confidence. Keep the original payload representation separate.
    if isinstance(value, dict):
        return {key: _gps_identity(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_gps_identity(item) for item in value]
    return 0.0 if type(value) is float and value == 0 else value


class _DatabaseFailure(Exception):
    """Preserve only the driver number needed by existing transaction classifiers."""

    def __init__(self, code):
        super().__init__(code, "recording database operation failed")


class MySQLRecordingRepository:
    # Release C selects chunked/envelope writes while retaining B's readers and
    # replay guards. Release identity is not an environment toggle.
    _prepared_write_format = PREPARED_WRITE_FORMAT

    def __init__(self, connection: Connection, *, storage_root: str | Path, temp_root=None,
                 command_budget=None, prepared_write_format=PREPARED_WRITE_FORMAT):
        if connection.dialect.name != "mysql" or connection.closed:
            raise ValueError("recording requires an open MySQL Connection")
        self._connection = connection
        try:
            self._root = Path(storage_root).resolve(strict=True)
            if not self._root.is_dir():
                raise ValueError
        except (OSError, ValueError, RuntimeError):
            raise ValueError("invalid recording storage root") from None
        self._root_key = _key(str(self._root))
        self._temp_root = temp_root
        if command_budget is not None and (type(command_budget) is not int or command_budget <= COMMAND_ALLOWANCE):
            raise ValueError("invalid prepared-media command budget")
        self._command_budget = command_budget
        if prepared_write_format not in ("legacy", "chunked"):
            raise ValueError("invalid prepared-media write format")
        self._prepared_write_format = prepared_write_format
        self._analysis_streams: dict[str, tuple[Callable[[], BinaryIO], str]] = {}

    def _execute(self, statement):
        return self._database_call(lambda: self._connection.execute(statement))

    @staticmethod
    def _database_call(operation):
        try:
            return operation()
        except DBAPIError as error:
            code = error.orig.args[0] if getattr(error.orig, "args", ()) else None
            code = code if type(code) is int else None
            # Keep DBAPI type/disconnect/errno for RT-02; drop SQL, parameters,
            # driver text, paths and chained diagnostic data from rendered errors.
            raise type(error)(None, None, _DatabaseFailure(code),
                              connection_invalidated=error.connection_invalidated) from None

    def _row(self, kind, identity, payload, content=None):
        if kind in _PREPARED_KINDS and self._prepared_write_format == "chunked":
            payload = encode_prepared_payload(payload)
        return {"kind": kind, "entry_key": _key(identity), "payload": payload, "content": content}

    def _write(self, rows):
        # One InnoDB statement: a rejected registration/frame cannot leave a
        # subset of its rows, even if the caller catches the error and commits.
        rows = sorted(rows, key=lambda row: (row["kind"], row["entry_key"]))
        stmt = insert(entries).values(rows)
        self._execute(stmt.on_duplicate_key_update(
            payload=stmt.inserted.payload,
            content=sa.func.coalesce(stmt.inserted.content, entries.c.content),
        ))

    def _get(self, kind, identity, *, lock=False, content=False):
        columns = [entries.c.payload, entries.c.content] if content else [entries.c.payload]
        query = sa.select(*columns).where(
            entries.c.kind == kind, entries.c.entry_key == _key(identity))
        if lock:
            query = query.with_for_update()
        row = self._execute(query).mappings().one_or_none()
        if row is not None and kind in _PREPARED_KINDS:
            return {**row, 'payload': decode_prepared_payload(row['payload'])}
        return row

    def _immutable_write(self, rows):
        # The duplicate branch deliberately raises a server JSON error on any
        # conflict. InnoDB rolls back the entire statement, including earlier
        # inserted case links. A SELECT-before-write check would race under RC.
        rows = sorted(rows, key=lambda row: (row["kind"], row["entry_key"]))
        stmt = insert(entries).values(rows)
        compatible = sa.and_(
            entries.c.payload == stmt.inserted.payload,
            sa.or_(entries.c.content.is_(None), stmt.inserted.content.is_(None),
                   entries.c.content == stmt.inserted.content))
        try:
            self._execute(stmt.on_duplicate_key_update(
                payload=sa.case((compatible, entries.c.payload),
                                else_=sa.func.json_extract("recording immutable conflict", "$")),
                content=sa.func.coalesce(stmt.inserted.content, entries.c.content)))
        except DBAPIError as error:
            if error.orig.args[0] == 3141:
                raise ValueError("recording immutable identity conflicts with stored payload") from None
            raise

    def _model(self, kind, identity, model, *, lock=False):
        row = self._get(kind, identity, lock=lock)
        return model.model_validate_json(json.dumps(row["payload"])) if row is not None else None

    def _models(self, kind, model):
        return [model.model_validate_json(json.dumps(
            decode_prepared_payload(row[0]) if kind in _PREPARED_KINDS else row[0])) for row in self._execute(
            sa.select(entries.c.payload).where(entries.c.kind == kind).order_by(entries.c.ordinal))]

    def _put(self, kind, identity, model, *, immutable=False):
        payload = model.model_dump(mode="json")
        row = self._row(kind, identity, payload)
        if not immutable:
            self._write([row])
            return
        # Native MySQL JSON can change a float. Refuse that registration without
        # leaving a row even if the caller catches the conflict and commits.
        with self._publish_savepoint() if kind in _PREPARED_KINDS else nullcontext():
            stmt = insert(entries).values(row)
            self._execute(stmt.on_duplicate_key_update(entry_key=entries.c.entry_key))
            stored = self._get(kind, identity, lock=True)
            if type(model).model_validate_json(json.dumps(stored["payload"])) != model:
                raise ValueError("recording immutable identity conflicts with stored payload")

    def add_source_asset(self, asset):
        self._put("source_asset", asset.source_asset_ref, asset)

    def read_publish_registration(self, locator):
        """Locking current read, including under REPEATABLE READ snapshots.

        Lock every local-source metadata row, not BLOB content. NOWAIT means
        pending registration/deletion is uncertainty, never committed absence.
        Caller ends the short transaction before filesystem work. No retry,
        commit, rollback or filesystem lookup belongs to this method.
        """
        if not managed_publish_locator(locator):
            return PublishRegistration.UNKNOWN
        if not self._connection.in_transaction():
            raise ValueError('publish registration requires caller transaction')
        rows = self._execute(sa.select(entries.c.payload).where(
            entries.c.kind == 'local_source').with_for_update(nowait=True)).scalars().all()
        return registration_from_payloads(locator, rows)

    def add_prepared_media(self, media, content, *, case_id=None):
        info = prepared_content(media, content)
        if case_id is not None:
            identity(case_id)
        kind, ref = media_identity(media)
        packet = self._execute(sa.select(sa.literal_column("@@session.max_allowed_packet"))).scalar_one()
        budget, size = prepared_command_limits(packet, write_format=self._prepared_write_format,
                                               command_budget=self._command_budget)
        with self._prepared_commands(budget), self._publish_savepoint():
            # A duplicate no-op is a current read/row lock even under RR; never
            # compare/transfer legacy content or overwrite immutable metadata.
            row = self._row(kind, ref, media.model_dump(mode="json"))
            stmt = insert(entries).values(row)
            self._execute(stmt.on_duplicate_key_update(entry_key=entries.c.entry_key))
            stored = self._get(kind, ref, lock=True)
            if type(media).model_validate(stored["payload"]) != media:
                raise ValueError("recording immutable identity conflicts with stored payload")
            prior = self._get("prepared_content", [kind, ref], lock=True)
            if prior is not None:
                value = prior["payload"]
                if "version" in value:
                    checked_manifest(value)
                    previous_info = {key: value[key] for key in info}
                    # Validate persisted chunks, not only their descriptor. The
                    # detached reader verifies count/size/hash with bounded reads.
                    opened = self._read_prepared_stream(m.ContractRef(kind=kind, ref=ref), current=True)
                    with opened[0]:
                        pass
                else:
                    legacy_manifest(value)
                    previous_info = value
                    # Check old bytes on the server, returning only small facts.
                    length, digest = self._execute(sa.select(sa.func.octet_length(entries.c.content),
                        sa.func.sha2(entries.c.content, 256)).where(
                            entries.c.kind == kind, entries.c.entry_key == _key(ref)).with_for_update()).one()
                    if length != info["byte_size"] or digest != info["sha256"]:
                        raise ValueError("recording immutable identity conflicts with stored payload")
                if previous_info != info:
                    raise ValueError("recording immutable identity conflicts with stored payload")
            else:
                # Metadata-only registrations can acquire content once. A legacy
                # BLOB without its integrity descriptor is never silently replaced.
                length = self._execute(sa.select(sa.func.octet_length(entries.c.content)).where(
                    entries.c.kind == kind, entries.c.entry_key == _key(ref)).with_for_update()).scalar_one()
                if length is not None:
                    raise ValueError("invalid recording stored content")
                if self._prepared_write_format == "legacy":
                    # Existing metadata may already be an envelope. Update only
                    # content, never its representation or canonical identity.
                    self._execute(entries.update().where(entries.c.kind == kind,
                        entries.c.entry_key == _key(ref)).values(content=content))
                    manifest = info
                else:
                    for index, offset in enumerate(range(0, len(content), size)):
                        self._execute(insert(chunks).values(kind=kind, entry_key=_key(ref),
                            chunk_index=index, content=content[offset:offset+size]))
                    manifest = {**info, "version": 1, "chunk_size": size,
                                "chunk_count": (len(content)+size-1)//size}
                self._immutable_write([self._row("prepared_content", [kind, ref], manifest)])
            if case_id is not None:
                self._immutable_write([self._row("case_asset", [case_id, kind, ref],
                    {"case_id": case_id, "asset_ref": {"kind": kind, "ref": ref}})])

    @contextmanager
    def _prepared_commands(self, budget):
        def guard(conn, cursor, statement, parameters, context, many):
            if many:
                raise ValueError("prepared media cannot batch commands")
            rendered = cursor.mogrify(statement, parameters)
            length = len(rendered.encode(cursor.connection.encoding) if isinstance(rendered, str) else rendered)
            if length + 1 > budget:
                raise ValueError("prepared-media command exceeds budget")
        sa.event.listen(self._connection, "before_cursor_execute", guard)
        try:
            yield
        finally:
            sa.event.remove(self._connection, "before_cursor_execute", guard)

    @contextmanager
    def _publish_savepoint(self):
        savepoint = self._database_call(self._connection.begin_nested)
        try:
            yield
            self._database_call(savepoint.commit)  # RELEASE only; caller owns outer transaction.
        except BaseException:
            try:
                if not savepoint.is_active:
                    # RELEASE may fail after deactivating the local object.
                    self._connection.invalidate()
                else:
                    savepoint.rollback()
            except BaseException:
                # Deadlock can remove the server SAVEPOINT; disconnect can make
                # rollback impossible. Never hide the initiating error or let a
                # caught error commit an uncertain partial publish.
                try:
                    self._connection.invalidate()
                except BaseException:
                    pass
            raise

    def get_prepared_content(self, ref):
        # Compatibility boundary for existing byte-oriented export callers.
        # AnalysisSource and metadata reads use open_prepared_stream directly.
        opened = self.open_prepared_stream(ref)
        if opened is None:
            return None
        stream, content_type = opened
        with stream:
            return stream.read(), content_type

    def get_prepared_metadata(self, ref):
        """Published descriptor, not a fresh integrity scan of the video bytes."""
        row = self._get(ref.kind, ref.ref)
        info = self._get("prepared_content", [ref.kind, ref.ref])
        if row is None or info is None:
            return None
        value = info["payload"]
        manifest = checked_manifest(value) if isinstance(value, dict) and "version" in value else legacy_manifest(value)
        if row["payload"].get("byte_size") != manifest["byte_size"]:
            raise ValueError("invalid recording stored content")
        return {key: manifest[key] for key in ("byte_size", "sha256", "content_type")}

    def open_prepared_stream(self, ref):
        return self._read_prepared_stream(ref, current=False)

    def _read_prepared_stream(self, ref, *, current):
        # Replay has already locked the immutable media identity. Under RR,
        # all integrity reads must share that current view, not an older snapshot.
        def execute(statement):
            return self._execute(statement.with_for_update() if current else statement)

        row = self._get(ref.kind, ref.ref, lock=current)
        info = self._get("prepared_content", [ref.kind, ref.ref], lock=current)
        if row is None or info is None:
            return None
        value = info["payload"]
        if "version" in value:
            manifest = checked_manifest(value)
            condition = sa.and_(chunks.c.kind == ref.kind, chunks.c.entry_key == _key(ref.ref))
            count, low, high = execute(sa.select(sa.func.count(), sa.func.min(chunks.c.chunk_index),
                sa.func.max(chunks.c.chunk_index)).where(condition)).one()
            if (count, low, high) != (manifest["chunk_count"], 0, manifest["chunk_count"]-1):
                raise ValueError("invalid recording media chunks")
            def parts():
                for index in range(count):
                    # Bound results even if a damaged row contains a giant BLOB.
                    with execute(sa.select(sa.func.substring(chunks.c.content, 1, manifest["chunk_size"]+1),
                            sa.func.octet_length(chunks.c.content)).where(condition, chunks.c.chunk_index == index)) as result:
                        part = result.one_or_none()
                    if part is None or len(part[0]) != part[1]:
                        raise ValueError("invalid recording media chunk")
                    yield part[0]
        else:
            # Legacy format is read in bounded substrings without a full BLOB row.
            manifest = legacy_manifest(value)
            condition = sa.and_(entries.c.kind == ref.kind, entries.c.entry_key == _key(ref.ref))
            length = execute(sa.select(sa.func.octet_length(entries.c.content)).where(condition)).scalar_one()
            if length != manifest["byte_size"]:
                raise ValueError("invalid recording stored content")
            def parts():
                for offset in range(0, length, MAX_CHUNK_BYTES):
                    with execute(sa.select(sa.func.substring(entries.c.content, offset+1,
                            min(MAX_CHUNK_BYTES, length-offset))).where(condition)) as result:
                        part = result.scalar_one()
                    yield part
        if row["payload"].get("byte_size") != manifest["byte_size"]:
            raise ValueError("invalid recording stored content")
        return detached_stream(parts(), manifest, temp_root=self._temp_root), manifest["content_type"]

    def save_time_sources(self, source_ref, observed):
        stmt = insert(entries).values(self._row("time_observation", source_ref, observation_payload(observed)))
        self._execute(stmt.on_duplicate_key_update(entry_key=entries.c.entry_key))
        return observation_from_payload(self._get("time_observation", source_ref, lock=True)["payload"])

    def get_time_sources(self, source_ref):
        row = self._get("time_observation", source_ref)
        return observation_from_payload(row["payload"]) if row is not None else None

    def get_time_source_candidate(self, candidate_id):
        rows = self._execute(sa.select(entries.c.payload).where(entries.c.kind == "time_observation"))
        return next((c for row in rows for c in observation_from_payload(row[0]).candidates
                     if c.candidate_id == candidate_id), None)

    def get_source_asset(self, source_ref):
        return self._model("source_asset", source_ref, m.SourceAsset)

    def _path(self, locator):
        try:
            if (not isinstance(locator, str) or not locator or "\\" in locator
                    or PurePosixPath(locator).is_absolute() or PureWindowsPath(locator).drive
                    or any(part in ("", ".", "..") for part in locator.split("/"))):
                raise ValueError
            path = (self._root / locator).resolve()
            path.relative_to(self._root)
            return path
        except (OSError, ValueError, RuntimeError):
            raise ValueError("invalid recording relative locator") from None

    def add_local_source(self, asset, streams, source, *, case_id=None):
        try:
            path = source.path.resolve(strict=True)
            locator = path.relative_to(self._root).as_posix()
            if self._path(locator) != path:
                raise ValueError
            indices = dict(zip(asset.media_stream_refs, (s.index for s in source.streams), strict=True))
            if [s.media_stream_ref for s in streams] != asset.media_stream_refs:
                raise ValueError
        except (OSError, ValueError, RuntimeError):
            raise ValueError("invalid recording local source") from None
        payload = {"locator": locator, "root_key": self._root_key,
                   "byte_size": source.byte_size, "mtime_ns": source.mtime_ns,
                   "sha256": source.sha256, "duration_sec": source.duration_sec,
                   "streams": [{"index": s.index, "media_type": s.media_type,
                                "duration_sec": s.duration_sec} for s in source.streams]}
        if source.original_filename is not None:
            payload["original_filename"] = source.original_filename
        rows = [self._row("source_asset", asset.source_asset_ref, asset.model_dump(mode="json")),
                self._row("local_source", asset.source_asset_ref, payload)]
        for stream in streams:
            rows += [self._row("media_stream", stream.media_stream_ref, stream.model_dump(mode="json")),
                     self._row("stream_index", stream.media_stream_ref, {"index": indices[stream.media_stream_ref]})]
        if case_id is not None:
            ref = m.ContractRef(kind="source_asset", ref=asset.source_asset_ref)
            rows.append(self._row("case_asset", [case_id, ref.kind, ref.ref],
                                  {"case_id": case_id, "asset_ref": ref.model_dump(mode="json")}))
        self._write(rows)

    def get_local_source(self, source_ref):
        row = self._get("local_source", source_ref)
        if row is None:
            return None
        payload = row["payload"]
        if payload["root_key"] != self._root_key:
            raise ValueError("recording storage root mismatch")
        return LocalSource(self._path(payload["locator"]), payload["byte_size"], payload["mtime_ns"],
                           payload["sha256"], payload["duration_sec"],
                           tuple(ProbedStream(**stream) for stream in payload["streams"]),
                           original_filename=payload.get("original_filename"))

    def get_local_stream_index(self, stream_ref):
        row = self._get("stream_index", stream_ref)
        return row["payload"]["index"] if row is not None else None

    def add_media_stream(self, stream):
        self._put("media_stream", stream.media_stream_ref, stream)

    def get_media_stream(self, stream_ref):
        return self._model("media_stream", stream_ref, m.MediaStream, lock=True)

    def get_ownership_stream(self, stream_ref):
        return self._model("media_stream", stream_ref, m.MediaStream)

    def add_gps_observation(self, observation):
        checked = m.GPSObservation.model_validate(observation)
        if checked.source.ref is not None and self.get_media_stream(checked.source.ref.ref) is None:
            raise ValueError("GPS source ref has no MediaStream")
        identity = _gps_identity(checked.model_dump(mode="json"))
        if self._get("gps", identity) is not None:
            raise ValueError("duplicate GPS observation")
        # Plain insert preserves duplicate rejection in concurrent transactions.
        self._execute(insert(entries).values(self._row(
            "gps", identity, checked.model_dump(mode="json", exclude_unset=True))))

    def list_gps_observations(self):
        return self._models("gps", m.GPSObservation)

    @staticmethod
    def _position(stream_ref, offset):
        return [stream_ref, _coordinate(offset)]

    def add_frame(self, frame, *, content=None, image_format=None):
        frame_format(content, image_format)
        self._immutable_write([self._row("frame", frame.frame_ref, frame.model_dump(mode="json"), content),
                     self._row("frame_position", self._position(frame.media_stream_ref, frame.source_offset_sec),
                               {"frame_ref": frame.frame_ref})])

    def find_frame_at(self, stream_ref, source_offset_sec):
        row = self._get("frame_position", self._position(stream_ref, source_offset_sec))
        return self.get_frame(row["payload"]["frame_ref"]) if row is not None else None

    def get_frame(self, frame_ref):
        return self._model("frame", frame_ref, m.FrameRef)

    def get_frame_content(self, frame_ref):
        row = self._get("frame", frame_ref, content=True)
        return row["content"] if row is not None else None

    def get_owned_frame(self, case_id, frame_ref):
        """One RC statement scopes ownership before restoring any model.

        A statement-consistent snapshot covers relation and bytes; no check/read
        gap, row locks, transaction completion or new association is introduced.
        Index predicates narrow candidates; lengthless BINARY casts check exact
        identity, including trailing space. utf8mb4_bin is PAD SPACE in MySQL.
        """
        frame, stream, source, link = (entries.alias(n) for n in ('f', 's', 'a', 'l'))
        def text(column, *keys):
            value = column
            for key in keys:
                value = value[key]
            # Invalid relationship JSON types cannot become string identities.
            return sa.case((sa.func.json_type(value) == 'STRING', value.as_string()), else_=sa.null())
        def exact(left, right):
            # No length: BINARY(N) would pad/truncate and change identity.
            return sa.cast(left, sa.LargeBinary()) == sa.cast(right, sa.LargeBinary())
        def kind(table, name):
            return sa.and_(table.c.kind == name, exact(table.c.kind, sa.literal(name)))
        joined = frame.join(stream, sa.and_(kind(stream, 'media_stream'),
            exact(text(frame.c.payload, 'media_stream_ref'), text(stream.c.payload, 'media_stream_ref'))))
        joined = joined.join(source, sa.and_(kind(source, 'source_asset'),
            exact(text(stream.c.payload, 'source_asset_ref'), text(source.c.payload, 'source_asset_ref'))))
        joined = joined.join(link, sa.and_(kind(link, 'case_asset'),
            exact(text(link.c.payload, 'case_id'), sa.literal(case_id)),
            exact(text(link.c.payload, 'asset_ref', 'kind'), sa.literal('source_asset')),
            exact(text(link.c.payload, 'asset_ref', 'ref'), text(source.c.payload, 'source_asset_ref'))))
        row = self._execute(sa.select(frame.c.payload, frame.c.content,
            stream.c.payload.label('stream'), source.c.payload.label('source')).select_from(joined).where(
                kind(frame, 'frame'), frame.c.entry_key == _key(frame_ref))).mappings().one_or_none()
        if row is None:
            return None
        restored = m.FrameRef.model_validate(row['payload'])
        m.MediaStream.model_validate(row['stream'])
        m.SourceAsset.model_validate(row['source'])
        if restored.frame_ref != frame_ref:
            raise ValueError('stored frame identity mismatch')
        return restored, row['content']

    def add_asset_facts(self, facts):
        self._put("asset_facts", [facts.asset_ref.kind, facts.asset_ref.ref], facts)

    def get_asset_facts(self, kind, ref):
        return self._model("asset_facts", [kind, ref], m.AssetFacts)

    def add_timeline(self, timeline):
        self._put("timeline", [timeline.timeline_id, timeline.revision], timeline, immutable=True)

    def get_timeline(self, timeline_ref):
        return self._model("timeline", [timeline_ref.timeline_id, timeline_ref.revision], m.RecordingTimeline)

    def get_latest_timeline(self, timeline_id):
        return max((t for t in self._models("timeline", m.RecordingTimeline) if t.timeline_id == timeline_id),
                   key=lambda t: t.revision, default=None)

    def find_frames_at_timeline_position(self, timeline, at_sec):
        matches = {}
        for placement in timeline.source_placements:
            if placement.timeline_start_sec <= at_sec < placement.timeline_end_sec:
                for stream_ref in placement.media_stream_refs:
                    frame = self.find_frame_at(stream_ref, at_sec - placement.timeline_start_sec)
                    if frame is not None:
                        matches[frame.frame_ref] = frame
        return list(matches.values())

    @staticmethod
    def _resolution_key(ref, requested_range):
        return [ref.timeline_id, ref.revision, _coordinate(requested_range.start_sec),
                _coordinate(requested_range.end_sec)]

    def add_span_resolution(self, resolution):
        self._put("span", self._resolution_key(resolution.timeline_ref, resolution.requested_range),
                  resolution, immutable=True)

    def get_span_resolution(self, timeline_ref, requested_range):
        return self._model("span", self._resolution_key(timeline_ref, requested_range), m.SpanResolution)

    def add_analysis_source(self, source, *, stream_factory=None, content_type="application/octet-stream"):
        self._put("analysis_source", source.analysis_source_ref, source, immutable=True)
        if stream_factory is not None:
            self._analysis_streams[source.analysis_source_ref] = (stream_factory, content_type)

    def get_analysis_source(self, source_ref):
        return self._model("analysis_source", source_ref, m.AnalysisSource)

    def find_analysis_sources(self, span, profile_ref):
        return [s for s in self._models("analysis_source", m.AnalysisSource)
                if s.profile_ref == profile_ref and s.timeline_range == span.timeline_range
                and span.media_stream_ref in s.media_stream_refs
                and m.ContractRef(kind="source_asset", ref=span.source_asset_ref) in s.source_refs]

    def open_analysis_stream(self, source_ref):
        stored = self.open_prepared_stream(m.ContractRef(kind="analysis_source", ref=source_ref))
        if stored is not None:
            return stored
        value = self._analysis_streams.get(source_ref)
        # A rolled-back registration cannot expose its process-local stream.
        if value is None or self.get_analysis_source(source_ref) is None:
            return None
        factory, content_type = value
        return factory(), content_type

    def add_remote_copy(self, remote_copy):
        current = self._model("remote_copy", remote_copy.remote_copy_ref, m.RemoteCopy, lock=True)
        if current is not None and current != remote_copy:
            raise ValueError("recording immutable identity conflicts with stored payload")
        # Equal aware instants may serialize with different timezone offsets.
        # Reuse the locked immutable payload so equal re-registration advances
        # provider lookup order without changing its original representation.
        payload = (current if current is not None else remote_copy).model_dump(mode="json")
        row = self._row("remote_copy", remote_copy.remote_copy_ref, payload)
        row["ordinal"] = None  # Include the generated column in MySQL 8's inserted-row alias.
        stmt = insert(entries).values(row)
        # The allocated auto-increment ordinal also orders a repeated registration.
        # Preserve immutable payloads and leave conflicts entirely unchanged.
        self._execute(stmt.on_duplicate_key_update(ordinal=sa.case(
            (entries.c.payload == stmt.inserted.payload, stmt.inserted.ordinal), else_=entries.c.ordinal)))
        if self.get_remote_copy_by_ref(remote_copy.remote_copy_ref) != remote_copy:
            raise ValueError("recording immutable identity conflicts with stored payload")

    def get_remote_copy(self, analysis_source_ref, provider):
        matches = [r for r in self._models("remote_copy", m.RemoteCopy)
                   if r.analysis_source_ref == analysis_source_ref and r.provider == provider]
        return matches[-1] if matches else None

    def get_remote_copy_by_ref(self, remote_copy_ref):
        return self._model("remote_copy", remote_copy_ref, m.RemoteCopy)

    def add_incident_clip(self, clip):
        self._put("incident_clip", clip.incident_clip_ref, clip, immutable=True)

    def find_incident_clips(self, resolution):
        return [c for c in self._models("incident_clip", m.IncidentClip)
                if c.source_provenance.timeline_ref == resolution.timeline_ref
                and c.source_provenance.requested_range == resolution.requested_range
                and c.source_provenance.asset_spans == resolution.spans]

    def get_incident_clip(self, clip_ref):
        return self._model("incident_clip", clip_ref, m.IncidentClip)

    def add_export_transform(self, ref, payload):
        self._immutable_write([self._row("export_transform", ref, payload)])

    def get_export_transform(self, ref):
        row = self._get("export_transform", ref)
        return row["payload"] if row is not None else None

    def add_derived_asset(self, asset, *, content=None, content_type=None, case_id=None):
        derived_content(asset, content, content_type, case_id)
        rows = [self._row("derived_asset", asset.derived_asset_ref, asset.model_dump(mode="json"), content)]
        if content is not None:
            rows.append(self._row("derived_content", asset.derived_asset_ref, descriptor(content, content_type)))
        if case_id is not None:
            ref = m.ContractRef(kind="derived_asset", ref=asset.derived_asset_ref)
            rows.append(self._row("case_asset", [case_id, ref.kind, ref.ref],
                                  {"case_id": case_id, "asset_ref": ref.model_dump(mode="json")}))
        self._immutable_write(rows)

    def get_derived_content(self, asset_ref):
        row = self._get("derived_asset", asset_ref, content=True)
        info = self._get("derived_content", asset_ref)
        if row is None or row["content"] is None or info is None:
            return None
        return checked_content(row["content"], info["payload"])

    def get_derived_asset(self, asset_ref):
        return self._model("derived_asset", asset_ref, m.DerivedAsset)

    def associate_case_asset(self, case_id, asset_ref):
        if asset_ref.kind == "external_source":
            raise ValueError("external sources are not managed deletion targets")
        self._write([self._row("case_asset", [case_id, asset_ref.kind, asset_ref.ref],
                              {"case_id": case_id, "asset_ref": asset_ref.model_dump(mode="json")})])

    def get_case_assets(self, case_id):
        scope = entries.c.payload["case_id"]
        query = sa.select(entries.c.payload).where(entries.c.kind == "case_asset",
            scope.as_string() == case_id,
            # Retain candidate predicates; PAD SPACE and JSON coercion must not
            # authorize an alias. BINARY without a length neither pads nor truncates.
            sa.cast(entries.c.kind, sa.LargeBinary()) == sa.cast(sa.literal("case_asset"), sa.LargeBinary()),
            sa.func.json_type(scope) == "STRING",
            sa.cast(scope.as_string(), sa.LargeBinary()) == sa.cast(sa.literal(case_id), sa.LargeBinary()),
        ).order_by(entries.c.ordinal)
        try:
            return [m.ContractRef.model_validate(row[0]["asset_ref"]) for row in self._execute(query)]
        except (ValueError, KeyError, TypeError):
            raise ValueError("stored case asset metadata is invalid") from None

    def mark_deleted(self, asset_ref):
        identity = [asset_ref.kind, asset_ref.ref]
        stmt = insert(entries).values(self._row("deleted", identity, asset_ref.model_dump(mode="json")))
        # rowcount: 1 inserted; 0 unchanged with CLIENT_FOUND_ROWS? SQLAlchemy
        # enables FOUND_ROWS, so inspect locked existence instead.
        if self._get("deleted", identity, lock=True) is not None:
            return False
        self._execute(stmt)
        return True
