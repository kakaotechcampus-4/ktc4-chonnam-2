"""Independent RT-08(d) MySQL obligations; never import the gate's inventory."""

CANCEL_API_PARAMETERS = (
    *(("api_cancel", "atomicity", p) for p in ("QUEUED", "RUNNING", "STALE", "SUCCEEDED", "multiple")),
    *(("api_cancel", "rollback", p) for p in ("before", "after", "disconnect", "sql")),
    ("api_cancel", "commit_unknown", "ack_loss"),
    *(("api_cancel", "repeat", p) for p in ("sequential", "concurrent", "current_revision")),
    *(("api_cancel", "interruption", p) for p in ("before_cancel", "after_cancel", "after_commit")),
    *(("api_cancel", "delivery", p) for p in ("late_success", "cancelled", "ownership")),
)
CANCEL_API_CHECKS = tuple(dict.fromkeys((r, s) for r, s, p in CANCEL_API_PARAMETERS))
