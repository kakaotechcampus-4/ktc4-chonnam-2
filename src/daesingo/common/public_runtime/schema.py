"""Shared public state, introduced by frozen runtime_0007; no cross-domain FK."""
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BINARY

metadata = sa.MetaData()


def table(name, *columns):
    for column in columns:
        if isinstance(column, sa.Column):
            if isinstance(column.type, sa.LargeBinary):
                column.type = column.type.with_variant(BINARY(32), "mysql")
            elif isinstance(column.type, sa.String):
                column.type = column.type.with_variant(sa.String(column.type.length, collation="ascii_bin"), "mysql")
    return sa.Table(name, metadata, *columns, mysql_engine="InnoDB", mysql_charset="utf8mb4")


control = table("public_control",
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=False),
    sa.Column("accepting", sa.Boolean, nullable=False),
    sa.Column("policy_hash", sa.LargeBinary(32)),
    sa.CheckConstraint("id = 1", name="ck_public_control_singleton"))

sessions = table("public_session",
    sa.Column("session_hash", sa.LargeBinary(32), primary_key=True),
    sa.Column("ip_hash", sa.LargeBinary(32), nullable=False),
    sa.Column("created_at", sa.DateTime, nullable=False),
    sa.Column("expires_at", sa.DateTime, nullable=False),
    sa.Index("ix_public_session_ip", "ip_hash", "created_at"))

cases = table("public_case",
    sa.Column("case_id", sa.String(128), primary_key=True),
    sa.Column("session_hash", sa.LargeBinary(32)),
    sa.Column("ip_hash", sa.LargeBinary(32)),
    sa.Column("created_at", sa.DateTime, nullable=False),
    sa.Column("expires_at", sa.DateTime, nullable=False),
    sa.Column("source_expires_at", sa.DateTime, nullable=False),
    sa.Column("state", sa.String(16), nullable=False),
    sa.Column("sample_id", sa.String(64)),
    sa.Column("manifest_hash", sa.LargeBinary(32)),
    sa.Column("sources", sa.JSON, nullable=False),
    sa.Column("deletion_plan", sa.JSON),
    sa.Column("temp_token", sa.String(32), nullable=False),
    sa.Column("sources_deleted_at", sa.DateTime),
    sa.Index("ix_public_case_owner", "session_hash", "created_at"),
    sa.Index("ix_public_case_expiry", "state", "expires_at"),
    sa.CheckConstraint("state IN ('ACTIVE','DELETING','DELETED')", name="ck_public_case_state"))

admissions = table("public_admission",
    sa.Column("case_id", sa.String(128), primary_key=True),
    sa.Column("request_hash", sa.LargeBinary(32), primary_key=True),
    sa.Column("session_hash", sa.LargeBinary(32), nullable=False),
    sa.Column("ip_hash", sa.LargeBinary(32), nullable=False),
    sa.Column("created_at", sa.DateTime, nullable=False),
    sa.Column("initial", sa.Boolean, nullable=False),
    sa.Column("active", sa.Boolean, nullable=False),
    sa.Index("ix_public_admission_session", "session_hash", "created_at"),
    sa.Index("ix_public_admission_ip", "ip_hash", "created_at"))

preparations = table("public_preparation",
    sa.Column("token", sa.String(64), primary_key=True),
    sa.Column("case_id", sa.String(128), nullable=False),
    sa.Column("session_hash", sa.LargeBinary(32), nullable=False),
    sa.Column("ip_hash", sa.LargeBinary(32), nullable=False),
    sa.Column("created_at", sa.DateTime, nullable=False),
    sa.Column("finished_at", sa.DateTime),
    sa.Index("ix_public_preparation_case", "case_id"),
    sa.Index("ix_public_preparation_ip", "ip_hash", "created_at"))

reservations = table("public_reservation",
    sa.Column("usage_id", sa.String(128), primary_key=True),
    sa.Column("execution_ref", sa.String(128), nullable=False),
    sa.Column("case_id", sa.String(128), nullable=False),
    sa.Column("operation", sa.String(64), nullable=False),
    sa.Column("provider_label", sa.String(191), nullable=False),
    sa.Column("amount_micros", sa.BigInteger, nullable=False),
    sa.Column("created_at", sa.DateTime, nullable=False),
    sa.Column("settled_at", sa.DateTime),
    sa.Index("ix_public_reservation_day", "created_at"),
    sa.Index("ix_public_reservation_case", "case_id"),
    sa.CheckConstraint("amount_micros >= 0", name="ck_public_reservation_amount"))
