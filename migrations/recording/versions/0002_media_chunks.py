"""Additive prepared-media chunks; legacy entry BLOBs remain readable."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMBLOB

revision = "recording_0002"
down_revision = "recording_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recording_media_chunk",
        sa.Column("kind", sa.String(32, collation="ascii_bin"), primary_key=True),
        sa.Column("entry_key", sa.String(64, collation="ascii_bin"), primary_key=True),
        sa.Column("chunk_index", sa.Integer, primary_key=True),
        sa.Column("content", MEDIUMBLOB, nullable=False),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )


def downgrade():
    raise NotImplementedError("Recording migrations are forward-only")
