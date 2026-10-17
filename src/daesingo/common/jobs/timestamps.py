"""#370 DB causal timestamps; evaluated against the row at each SQL write.

NULL metadata contributes queued_at, never NULL to MySQL GREATEST. Lease expiry
is a future permission bound, not an observed causal event or terminal floor.
Keep the same expression in textual and Core SQL, without an application clock.
"""

from sqlalchemy import literal_column

HEARTBEAT_TIMESTAMP_SQL = (
    "GREATEST(NOW(6), queued_at, COALESCE(started_at, queued_at), "
    "COALESCE(heartbeat_at, queued_at))"
)
TERMINAL_TIMESTAMP_SQL = (
    "GREATEST(NOW(6), queued_at, COALESCE(started_at, queued_at), "
    "COALESCE(heartbeat_at, queued_at), COALESCE(cancel_requested_at, queued_at))"
)


def terminal_timestamp():
    """Use in a row SELECT/UPDATE, including the final conditional UPDATE."""
    return literal_column(TERMINAL_TIMESTAMP_SQL)
