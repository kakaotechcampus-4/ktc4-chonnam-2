"""Independent #370 evidence inventory for gate unit/actual-report mutations."""

TIMESTAMP_PARAMETERS = (
    *(("timestamp_order", "terminal", s) for s in
      ("SUCCEEDED", "FAILED", "CANCELLED", "STALE", "QUEUED_CANCEL")),
    *(("timestamp_order", "renewal", s) for s in
      ("non_regression", "sweep_recheck", "null_metadata", "longer_lease")),
    *(("timestamp_order", "bounds", s) for s in ("heartbeat", "cancel", "null")),
    ("timestamp_order", "metrics", "duration_detect_backoff"),
    *(("timestamp_order", "retry", f"{s}_{code}") for s in
      ("SUCCEEDED", "FAILED", "CANCELLED", "STALE") for code in (1205, 1213)),
    ("timestamp_order", "retry", "real_1205"),
    ("timestamp_order", "retry", "real_1213"),
    *(("timestamp_order", "commit_unknown", s) for s in
      ("claim", "SUCCEEDED", "FAILED", "CANCELLED", "STALE", "QUEUED_CANCEL", "T2")),
    *(("timestamp_order", "concurrent", s) for s in
      ("race", "heartbeat", "sweep", "cancel", "finish_snapshot")),
)
TIMESTAMP_CHECKS = tuple(sorted({(r, s) for r, s, p in TIMESTAMP_PARAMETERS}))
