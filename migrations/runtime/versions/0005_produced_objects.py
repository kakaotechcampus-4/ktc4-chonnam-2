"""Opaque produced payloads; frozen and independent of live metadata."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BINARY, LONGTEXT

revision = "runtime_0005"
down_revision = "runtime_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "produced_objects",
        sa.Column("execution_id", sa.String(128, collation="ascii_bin"), primary_key=True),
        sa.Column("ordinal", sa.Integer, primary_key=True),
        sa.Column("case_id", sa.String(128, collation="ascii_bin"), nullable=False),
        sa.Column("job_kind", sa.String(64, collation="ascii_bin"), nullable=False),
        sa.Column("kind", sa.Text(collation="utf8mb4_bin"), nullable=False),
        sa.Column("ref", sa.Text(collation="utf8mb4_bin"), nullable=False),
        sa.Column("ref_key", BINARY(32), nullable=False, unique=True),
        # Serialized strict JSON text preserves integers beyond native JSON's
        # uint64/int64 range. Snapshot validation belongs to the opaque binder.
        sa.Column("payload", LONGTEXT, nullable=False),
        sa.CheckConstraint("ordinal >= 0", name="ck_produced_objects_ordinal"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )


def downgrade():
    raise NotImplementedError("forward-only runtime migration")
