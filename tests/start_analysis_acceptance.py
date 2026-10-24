"""Independent RT-08 START_ANALYSIS inventory for strict evidence mutations."""

START_ANALYSIS_PARAMETERS = (
    *(("api_start_analysis", "atomicity", kind) for kind in ("hint_extract", "coarse_search")),
    *(("api_start_analysis", "rollback", kind + "_" + fault)
      for kind in ("hint_extract", "coarse_search") for fault in ("save", "enqueue")),
    *(("api_start_analysis", "dependency", fault) for fault in ("timeline_unavailable", "unknown_ref")),
    *(("api_start_analysis", "commit_unknown", kind) for kind in ("hint_extract", "coarse_search")),
    *(("api_start_analysis", "repeat", kind + "_" + mode)
      for kind in ("hint_extract", "coarse_search") for mode in ("sequential", "concurrent")),
    *(("api_start_analysis", "response_loss", kind) for kind in ("hint_extract", "coarse_search")),
)
START_ANALYSIS_CHECKS = tuple(sorted({(r, s) for r, s, p in START_ANALYSIS_PARAMETERS}))
