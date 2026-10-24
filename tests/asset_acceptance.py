"""Independent RT-11(c) evidence inventory; never imported by the checker."""
ASSET_PARAMETERS = tuple(('api_asset', scenario, parameter) for scenario, parameter in (
    ('read', 'mp4'), ('read', 'png'), ('read', 'restart'), ('read', 'safe_filename'),
    *(('isolation', p) for p in ('missing_case', 'unknown', 'foreign', 'wrong_kind',
                                'unavailable', 'missing_bytes', 'invalid_bytes')),
    *(('exact_identity', layer+'_'+variant) for layer in ('ref', 'scope')
      for variant in ('trailing', 'leading', 'case', 'multiple', 'unicode', 'unicode_space')),
    *(('corruption', p) for p in ('metadata', 'identity', 'descriptor', 'bytes', 'relation')),
    *(('transaction', p) for p in ('caller_rollback', 'closed_stream', 'read_error', 'length_mismatch', 'cancel_read', 'headers_after_checkin')),
    *(('failure', p) for p in ('pool', 'disconnect', 'temporary', 'unexpected', 'read_failure', 'validation')),
    *(('interruption', p) for p in ('read', 'detached')),
    *(('send', phase+'_'+ending) for phase in ('start', 'body', 'final')
      for ending in ('normal', 'cancel', 'disconnect', 'oserror', 'unexpected')),
    ('send', 'network_disconnect'),
    ('send', 'partial_failure'),
))
ASSET_CHECKS = tuple(sorted({(r, s) for r, s, p in ASSET_PARAMETERS}))
