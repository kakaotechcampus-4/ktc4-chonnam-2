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
    ("registration_input", "restore"), ("registration_input", "rollback"),
    ("registration_input", "atomic_link"), ("registration_input", "legacy"),
    ("registration_input", "concurrent"), ("registration_input", "commit_unknown"),
    ("registration_input", "filename_path"), ("registration_input", "filename_unicode"),
    ("registration_input", "filename_empty"), ("registration_input", "filename_nul"),
    ("registration_input", "case_accept"), ("registration_input", "case_reject"),
    ("registration_taxonomy", "unsupported"), ("registration_taxonomy", "tool"),
    ("registration_taxonomy", "read"),
    ("media_read", "restart"), ("media_read", "rollback"),
    ("media_read", "atomic_failure"), ("media_read", "conflict"),
    ("media_read", "legacy"), ("media_read", "commit_unknown"), ("media_read", "concurrent"),
    ("media_validation", "type"), ("media_validation", "digest"), ("media_validation", "size"),
    ("media_validation", "model"), ("media_validation", "image"), ("media_validation", "empty"),
    ("media_validation", "small"),
    ("media_validation", "large"), ("media_validation", "ownership_lock"),
    ("media_failure", "1205"), ("media_failure", "1213"),
    ("media_validation", "packet_limit"), ("media_validation", "inputs"),
    ("media_validation", "ownership_source"), ("media_validation", "ownership_derived"),
    ("media_validation", "ownership_relation"),
    ("media_validation", "wrong_type"), ("media_read", "png_derived"),
    # Issue #387: independent inventory, including both directions per test.
    *(("exact_ownership", layer + "_" + variant)
      for layer in ("scope", "source", "stream", "frame", "derived")
      for variant in ("space", "case", "unicode", "unicode_case")),
    ("exact_ownership", "concurrent"),
    ("exact_purge", "forward"), ("exact_purge", "reverse"),
    *(("exact_privacy", parameter) for parameter in (
        "source_asset", "derived_asset", "frame", "media_stream", "case_asset",
        "source_asset_identity", "derived_asset_identity", "nonstring_case", "padded_kind", "remote_copy")),
))
RECORDING_CHECKS = tuple(sorted({(r, s) for r, s, p in RECORDING_PARAMETERS}))
