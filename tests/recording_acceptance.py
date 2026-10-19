"""Independent REC-1(a) inventory; never imported by the production checker."""

RECORDING_PARAMETERS = tuple(("recording", scenario, parameter) for scenario, parameter in (
    ("restore", "identities"), ("restore", "local_source"), ("restore", "timeline_span"),
    ("transaction", "rollback"), ("transaction", "visibility"),
    ("transaction", "failed_registration"), ("transaction", "failed_frame"),
    ("ownership", "cross_case"), ("ownership", "duplicates"),
    ("identity", "repeat_registration"), ("identity", "immutable_conflict"),
    ("storage", "relative"), ("storage", "outside"), ("storage", "traversal"),
    ("storage", "absolute"), ("storage", "symlink"), ("storage", "wrong_root"),
    ("concurrent", "frame"), ("concurrent", "lock_scope"),
    ("failure", "commit_unknown"), ("failure", "disconnect"), ("failure", "unrelated_sql"),
    ("migration", "fresh"), ("migration", "previous"), ("migration", "failure"),
    ("compatibility", "fixture"), ("transaction", "no_completion"), ("restore", "png_bytes"),
))
RECORDING_CHECKS = tuple(sorted({(r, s) for r, s, p in RECORDING_PARAMETERS}))
