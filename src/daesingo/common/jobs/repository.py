"""Enqueue initial attempts on an explicit caller-owned transaction Connection."""

from collections.abc import Iterable, Mapping
from typing import Any
from uuid import uuid4

from sqlalchemy import insert, select, func
from sqlalchemy.engine import Connection

from .schema import job_execution


def _identifier(value: Any, name: str, length: int) -> str:
    # Match existing Case ascii_bin identity storage. Never silently truncate IDs.
    if not isinstance(value, str) or not value or len(value) > length or not value.isascii():
        raise ValueError(f"invalid {name}")
    return value


def enqueue(conn: Connection, job_records: Iterable[Mapping[str, Any]], trace_id: str) -> list[str]:
    """Append attempt 1 QUEUED rows and return their IDs in input order.

    Consume only job_id/case_id/kind; Case retains ownership of intent and kind
    semantics. Unknown kinds are accepted for later Worker dispatch. Validate
    the entire input before writing; one multi-row INSERT is statement-atomic
    on InnoDB. Duplicate (job_id, attempt) propagates IntegrityError; the caller
    decides rollback. This is not an idempotent unknown-COMMIT retry callback.
    """
    if not conn.in_transaction():
        raise ValueError("enqueue requires a caller-owned transaction")
    trace = _identifier(trace_id, "trace_id", 128)
    rows = [
        {"execution_id": f"exec_{uuid4().hex}",
         "job_id": _identifier(job["job_id"], "job_id", 191),
         "case_id": _identifier(job["case_id"], "case_id", 128),
         "kind": _identifier(job["kind"], "kind", 64), "trace_id": trace,
         "status": "QUEUED", "attempt": 1, "produced": []}
        for job in job_records
    ]
    if not rows:
        return []
    # MySQL DATETIME has no timezone. Use the DB's UTC clock, independent of
    # session timezone or API/container clocks; preserve microsecond precision.
    now = conn.scalar(select(func.utc_timestamp(6)))
    for row in rows:
        row.update(queued_at=now, available_at=now)
    conn.execute(insert(job_execution).values(rows))
    return [row["execution_id"] for row in rows]
