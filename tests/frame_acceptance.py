"""Independent RT-11(b) required evidence, never imported by the checker."""
FRAME_PARAMETERS = tuple(('api_frame', scenario, parameter) for scenario, parameter in (
    ('read', 'headers_repeat'), ('read', 'process_restart'),
    ('isolation', 'missing_case'), ('isolation', 'unknown'), ('isolation', 'cross_case'),
    ('isolation', 'unavailable'), ('isolation', 'bad_format'),
    ('concurrency', 'none'), ('concurrency', 'wait'), ('concurrency', 'active'),
    ('connection', 'slow_send'),
    ('failure', 'pool'), ('failure', 'disconnect'), ('failure', 'unexpected'),
    ('failure', 'temporary'), ('failure', 'read_failure'),
    ('transaction', 'caller_rollback'),
    ('transaction', 'relation_snapshot'),
    *(('corrupt_scope', p) for p in ('frame', 'stream', 'source', 'bytes', 'frame_link', 'frame_identity')),
    *(('send_lifetime', phase + '_' + ending) for phase in ('body', 'final')
      for ending in ('normal', 'cancel', 'disconnect', 'oserror', 'unexpected')),
    ('send_lifetime', 'network_disconnect'),
    *(('exact_identity', layer + '_' + boundary + '_' + variant)
      for layer in ('capability', 'http') for boundary in ('stream', 'source', 'frame')
      for variant in ('trailing', 'leading', 'case', 'multiple', 'unicode', 'unicode_space')),
    ('exact_identity', 'case_scope'),
))
FRAME_CHECKS = tuple(sorted({(r, s) for r, s, p in FRAME_PARAMETERS}))
