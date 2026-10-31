"""Independent RT-12(b) inventory, never derived from the gate's constants."""
OBSERVABILITY_PARAMETERS = (
    *(('observability','distribution',p) for p in ('empty','1','2','20','21')),
    *(('observability','boundaries',p) for p in ('attempt_kind_status_null','oldest_db_clock','usage','cap')),
    *(('observability','transaction',p) for p in ('read_only','caller_rollback')),
    *(('observability','catalog','false_'+p) for p in
      ('STALE','SUCCEEDED','FAILED','CANCELLED','QUEUED','foreign','missing')),
    ('observability','catalog','api'), ('observability','privacy','http_inputs'),
    ('observability','catalog','pool_timeout'),
    ('observability','privacy','logger_cleanup'),
)
OBSERVABILITY_CHECKS = tuple(dict.fromkeys((r,s) for r,s,p in OBSERVABILITY_PARAMETERS))
