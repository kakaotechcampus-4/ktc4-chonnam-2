"""Durable HINT_EXTRACT exhaustion outbox; frozen forward-only DDL."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

revision = "runtime_0006"
down_revision = "runtime_0005"
branch_labels = None
depends_on = None

def _id(length=128):
    return sa.String(length, collation="ascii_bin")

def upgrade():
    op.create_table(
    "job_exhaustion_notice",
    sa.Column("notice_id", _id(), primary_key=True),
    sa.Column("job_id", _id(191), nullable=False),
    sa.Column("case_id", _id(), nullable=False),
    sa.Column("kind", _id(64), nullable=False),
    sa.Column("final_execution_id", _id(), sa.ForeignKey("job_execution.execution_id",
              name="fk_exhaustion_final_execution"), nullable=False),
    sa.Column("attempt", sa.Integer, nullable=False),
    sa.Column("terminal_status", _id(16), nullable=False),
    sa.Column("reason", _id(16), nullable=False),
    sa.Column("exhausted_at", DATETIME(fsp=6), nullable=False),
    sa.Column("trace_id", _id(), nullable=False),
    sa.Column("case_acknowledged_at", DATETIME(fsp=6)),
    sa.UniqueConstraint("job_id", name="uq_exhaustion_job"),
    sa.CheckConstraint("attempt >= 1", name="ck_exhaustion_attempt"),
    sa.CheckConstraint("kind = 'HINT_EXTRACT'", name="ck_exhaustion_kind"),
    sa.CheckConstraint("terminal_status = 'STALE'", name="ck_exhaustion_status"),
    sa.CheckConstraint("reason = 'EXHAUSTED'", name="ck_exhaustion_reason"),
    mysql_engine="InnoDB", mysql_charset="utf8mb4",
)
    op.create_index("ix_exhaustion_unacknowledged", "job_exhaustion_notice", ["case_acknowledged_at", "notice_id"])

def downgrade():
    raise NotImplementedError("forward-only runtime migration")
