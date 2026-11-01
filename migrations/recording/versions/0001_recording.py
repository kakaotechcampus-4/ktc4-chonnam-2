"""Recording durable contracts, relationships and transactional frame bytes."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import LONGBLOB

revision = "recording_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recording_entry",
        sa.Column("kind", sa.String(32, collation="ascii_bin"), nullable=False),
        sa.Column("entry_key", sa.String(64, collation="ascii_bin"), nullable=False),
        sa.Column("ordinal", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("content", LONGBLOB),
        sa.UniqueConstraint("kind", "entry_key", name="uq_recording_entry_identity"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )


def downgrade():
    raise NotImplementedError("Recording migrations are forward-only")
