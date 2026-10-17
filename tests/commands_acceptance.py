"""Independent RT-08(c) inventory for gate and actual-report omission tests."""
COMMAND_PARAMETERS = (
    *(("api_commands", "success", p) for p in ("append", "no_append")),
    *(("api_commands", "domain", p) for p in ("invalid", "missing", "stale", "target", "not_allowed")),
    *(("api_commands", "rollback", p) for p in ("enqueue", "save", "disconnect", "unrelated_sql")),
    *(("api_commands", "failure", p) for p in ("pool", "lock_timeout", "commit_unknown")),
    *(("api_commands", "idempotency", p) for p in ("sequential", "concurrent")),
    ("api_commands", "boundary", "cancel_deferred"),
)
COMMAND_CHECKS = tuple(sorted({(r, s) for r, s, p in COMMAND_PARAMETERS}))
