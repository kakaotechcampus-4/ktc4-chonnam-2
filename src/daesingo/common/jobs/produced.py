"""Opaque append-only produced objects. Callers own transactions and meaning.

No module schema, candidate filtering, capability calls or Case imports live
here. Explicit refs are caller supplied; absent refs use execution/ordinal.
"""

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BINARY, LONGTEXT
from sqlalchemy.exc import IntegrityError

from daesingo.common.job_execution import RuntimeContractRef
from daesingo.common.jobs.schema import metadata


class _OpaqueJSON(sa.TypeDecorator):
    """Lossless JSON text: MySQL binary JSON coerces large ints to doubles.

    Validation remains structural only, independent of module schemas. A SQL
    JSON_VALID constraint would reintroduce MySQL's numeric parser limits.
    """
    impl = LONGTEXT
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if type(value) is not dict:
            raise ValueError("invalid produced JSON object")
        return _json(value)

    def process_result_value(self, value, dialect):
        return json.loads(value)


produced_objects = sa.Table(
    "produced_objects", metadata,
    sa.Column("execution_id", sa.String(128, collation="ascii_bin"), primary_key=True),
    sa.Column("ordinal", sa.Integer, primary_key=True),
    sa.Column("case_id", sa.String(128, collation="ascii_bin"), nullable=False),
    sa.Column("job_kind", sa.String(64, collation="ascii_bin"), nullable=False),
    sa.Column("kind", sa.Text(collation="utf8mb4_bin"), nullable=False),
    sa.Column("ref", sa.Text(collation="utf8mb4_bin"), nullable=False),
    sa.Column("ref_key", BINARY(32), nullable=False, unique=True),
    sa.Column("payload", _OpaqueJSON(), nullable=False),
    sa.CheckConstraint("ordinal >= 0", name="ck_produced_objects_ordinal"),
    mysql_engine="InnoDB", mysql_charset="utf8mb4",
)


def _json(value: Any) -> str:
    def check(item):
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float and math.isfinite(item):
            return
        if type(item) is list:
            for child in item:
                check(child)
            return
        if type(item) is dict and all(type(key) is str for key in item):
            for child in item.values():
                check(child)
            return
        raise ValueError("invalid produced JSON")
    try:
        check(value)
        return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    except (ValueError, TypeError, RecursionError):
        raise ValueError("invalid produced JSON") from None


class ProducedObject(BaseModel):
    """Internal handler payload. Never infer a ref from arbitrary payload keys."""
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    kind: str = Field(min_length=1)
    ref: str | None = Field(default=None, min_length=1)
    payload: dict[str, Any]

    @field_validator("payload", mode="before")
    @classmethod
    def json_snapshot(cls, value):
        if type(value) is not dict:
            raise ValueError("invalid produced JSON object")
        return json.loads(_json(value))


@dataclass(frozen=True)
class PreparedObject:
    ordinal: int
    reference: RuntimeContractRef
    payload_json: str

    @property
    def payload(self) -> dict[str, Any]:
        return json.loads(self.payload_json)


def prepare_objects(execution_id: str, objects: tuple[ProducedObject, ...]) -> tuple[PreparedObject, ...]:
    if (type(execution_id) is not str or not execution_id or len(execution_id) > 128
            or not execution_id.isascii()):
        raise ValueError("invalid produced execution identity")
    prepared = tuple(PreparedObject(index, RuntimeContractRef(kind=obj.kind,
        ref=obj.ref if obj.ref is not None else f"runtime:{execution_id}:{index}"), _json(obj.payload))
        for index, obj in enumerate(objects))
    if len({(o.reference.kind, o.reference.ref) for o in prepared}) != len(prepared):
        raise ValueError("invalid produced duplicate reference")
    return prepared


def _key(kind: str, ref: str) -> bytes:
    # JSON array encoding is injective, including separators embedded in IDs.
    return hashlib.sha256(_json([kind, ref]).encode("utf-8")).digest()


class ProducedConflict(ValueError):
    """A durable identity cannot be rebound or its contents replaced."""


def _rows(case_id, execution_id, job_kind, objects):
    for value, length in ((case_id, 128), (execution_id, 128), (job_kind, 64)):
        if type(value) is not str or not value or len(value) > length or not value.isascii():
            raise ValueError("invalid produced binding")
    return [dict(execution_id=execution_id, ordinal=o.ordinal, case_id=case_id, job_kind=job_kind,
                 kind=o.reference.kind, ref=o.reference.ref, ref_key=_key(o.reference.kind, o.reference.ref),
                 payload=o.payload) for o in objects]


def _same(stored, expected):
    return (len(stored) == len(expected) and all(
        all(row[key] == value for key, value in want.items() if key != "payload")
        and _json(row["payload"]) == _json(want["payload"])
        for row, want in zip(stored, expected)))


def verify_objects(conn, *, case_id: str, execution_id: str, job_kind: str,
                   objects: tuple[PreparedObject, ...]) -> None:
    """Verify, never repair, payloads on a recovered terminal COMMIT receipt."""
    expected = _rows(case_id, execution_id, job_kind, objects)
    stored = conn.execute(sa.select(produced_objects).where(
        produced_objects.c.execution_id == execution_id).order_by(produced_objects.c.ordinal)
        .with_for_update()).mappings().all()
    if not _same(stored, expected):
        raise ProducedConflict("produced persistence conflict")


def append_objects(conn, *, case_id: str, execution_id: str, job_kind: str,
                   objects: tuple[PreparedObject, ...]) -> None:
    if not conn.in_transaction():
        raise ValueError("produced append requires caller-owned transaction")
    expected = _rows(case_id, execution_id, job_kind, objects)
    if not expected:
        return
    # The production T1 already owns the execution row lock. A savepoint also
    # keeps standalone batch conflicts atomic when the caller catches them.
    try:
        with conn.begin_nested():
            conn.execute(sa.insert(produced_objects), expected)
    except IntegrityError:
        verify_objects(conn, case_id=case_id, execution_id=execution_id,
                       job_kind=job_kind, objects=objects)


class ProducedReader:
    """Implement Case's existing (conn, kind, produced) callable.

    A single object is returned unchanged. Multi-object projections belong to
    the consuming composition, supplied as assemble(kind, ordered_payloads).
    Missing, mismatched or mixed execution references fail closed.
    """
    def __init__(self, assemble: Callable[[str, tuple[dict[str, Any], ...]], dict[str, Any]] | None = None):
        self.assemble = assemble

    def __call__(self, conn, kind: str, produced: tuple[dict[str, str], ...]) -> dict[str, Any]:
        if not produced:
            raise ValueError("produced references required")
        rows = []
        seen = set()
        for reference in produced:
            ref = RuntimeContractRef.model_validate(reference)
            identity = (ref.kind, ref.ref)
            if identity in seen:
                raise ValueError("duplicate produced reference")
            seen.add(identity)
            row = conn.execute(sa.select(produced_objects).where(
                produced_objects.c.ref_key == _key(*identity))).mappings().one_or_none()
            if row is None or (row["kind"], row["ref"]) != identity or row["job_kind"] != kind:
                raise ValueError("produced reference unavailable")
            rows.append(row)
        if len({(row["execution_id"], row["case_id"]) for row in rows}) != 1:
            raise ValueError("mixed produced executions")
        values = tuple(row["payload"] for row in rows)
        if self.assemble is not None:
            return self.assemble(kind, values)
        if len(values) != 1:
            raise ValueError("produced assembly required")
        return values[0]
