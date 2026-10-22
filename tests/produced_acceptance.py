"""Independent RT-10(a) acceptance obligations; never imported by checker."""

PRODUCED_PARAMETERS = tuple(("produced_store", s, p) for s, p in (
    ("terminal", "SUCCEEDED"), ("terminal", "FAILED"),
    ("atomicity", "payload"), ("atomicity", "terminal"),
    ("replay", "identical"), ("replay", "payload"), ("replay", "binding"),
    ("concurrent", "same"), ("concurrent", "conflict"),
    ("ownership", "stolen"), ("commit_unknown", "SUCCEEDED"), ("commit_unknown", "FAILED"),
    ("reader", "single"), ("reader", "multiple"), ("reader", "missing"), ("reader", "wrong_kind"),
    ("reader", "mixed_execution"), ("reader", "empty"),
    ("process", "fresh_read"), ("redelivery", "stored_hint"),
    ("migration", "upgrade"), ("transaction", "caller_rollback"),
    ("receipt", "intact"), ("receipt", "missing"), ("receipt", "changed"),
    ("replay", "batch_conflict"),
    ("json", "large_uint"), ("json", "large_int"),
))
PRODUCED_CHECKS = tuple(sorted({(r, s) for r, s, p in PRODUCED_PARAMETERS}))
