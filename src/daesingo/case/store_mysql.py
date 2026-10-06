"""case MySQL 저장소 — `decisions/case-store-mysql.md` §4 · §5. sqlalchemy는 이 파일에서만 import한다
(in-memory만 쓰는 테스트 · 스크립트가 DB 의존성 없이 돌게)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

metadata = sa.MetaData()

_ID = 128  # case_id · scope_id
_RECORD_ID = 191  # job_id · correction_id — `job_{case_id}_{kind}_{uuid8}`가 들어가게


def _id(length: int = _ID) -> sa.String:
    return sa.String(length, collation="ascii_bin")


cases_table = sa.Table(
    "cases",
    metadata,
    sa.Column("case_id", _id(), primary_key=True),
    sa.Column("case_rev", sa.Integer, nullable=False),
    sa.Column("stage", sa.String(32), nullable=False),
    sa.Column("selection_rev", sa.Integer, nullable=False),
    sa.Column("state", sa.JSON, nullable=False),
    sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
    sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False),
    mysql_engine="InnoDB",
    mysql_charset="utf8mb4",
)

job_records_table = sa.Table(
    "job_records",
    metadata,
    sa.Column("job_id", _id(_RECORD_ID), primary_key=True),
    sa.Column("case_id", _id(), sa.ForeignKey("cases.case_id"), nullable=False),
    sa.Column("seq", sa.Integer, nullable=False),
    sa.Column("record", sa.JSON, nullable=False),
    sa.UniqueConstraint("case_id", "seq", name="uq_job_records_case_seq"),
    mysql_engine="InnoDB",
    mysql_charset="utf8mb4",
)

correction_records_table = sa.Table(
    "correction_records",
    metadata,
    sa.Column("correction_id", _id(_RECORD_ID), primary_key=True),
    sa.Column("case_id", _id(), sa.ForeignKey("cases.case_id"), nullable=False),
    sa.Column("seq", sa.Integer, nullable=False),
    sa.Column("record", sa.JSON, nullable=False),
    sa.UniqueConstraint("case_id", "seq", name="uq_correction_records_case_seq"),
    mysql_engine="InnoDB",
    mysql_charset="utf8mb4",
)

analysis_scopes_table = sa.Table(
    "analysis_scopes",
    metadata,
    sa.Column("case_id", _id(), sa.ForeignKey("cases.case_id"), primary_key=True),
    sa.Column("scope_id", _id(), primary_key=True),
    sa.Column("scope", sa.JSON, nullable=False),
    mysql_engine="InnoDB",
    mysql_charset="utf8mb4",
)
