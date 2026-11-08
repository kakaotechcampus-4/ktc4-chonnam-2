"""Separate analysis pause, emergency stop and bounded local result work."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BINARY

revision = "runtime_0008"
down_revision = "runtime_0007"
branch_labels = None
depends_on = None

metadata = sa.MetaData()
binary = sa.LargeBinary(32).with_variant(BINARY(32), "mysql")
def string(length):
    return sa.String(length).with_variant(sa.String(length, collation="ascii_bin"), "mysql")

local_admissions = sa.Table("public_local_admission", metadata,
    sa.Column("case_id", string(128), primary_key=True),
    sa.Column("request_hash", binary, primary_key=True),
    sa.Column("session_hash", binary, nullable=False),
    sa.Column("ip_hash", binary, nullable=False),
    sa.Column("created_at", sa.DateTime, nullable=False),
    sa.Column("job_ids", sa.JSON, nullable=False),
    sa.Column("job_count", sa.Integer, nullable=False),
    sa.Column("active", sa.Boolean, nullable=False),
    sa.CheckConstraint("job_count > 0", name="ck_public_local_job_count"),
    sa.Index("ix_public_local_ip", "ip_hash", "created_at"),
    mysql_engine="InnoDB", mysql_charset="utf8mb4")


def upgrade():
    op.add_column("public_control", sa.Column("jobs_stopped", sa.Boolean, nullable=False, server_default=sa.true()))
    op.add_column("public_case", sa.Column("local_work_state", sa.JSON))
    local_admissions.create(bind=op.get_bind())
    # A previous API ignores jobs_stopped; leave its accepting gate closed too.
    op.execute(sa.text("UPDATE public_control SET accepting = FALSE, jobs_stopped = TRUE"))


def downgrade():
    raise NotImplementedError("forward-only runtime migration")
