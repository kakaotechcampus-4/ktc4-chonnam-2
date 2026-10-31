"""Baseline §6 log observations: emitted schema, status and producer authority.

This catalog describes existing Runtime/API events; it installs no logger,
transport, scheduler or HTTP surface. Several metrics intentionally share an
event. Count observations once, not once for each alias in METRICS.
"""
from dataclasses import dataclass
import re
from types import MappingProxyType

from . import _validate


@dataclass(frozen=True)
class EventSpec:
    required: frozenset[str]
    statuses: str | None
    source: str
    meaning: str
    optional: frozenset[str] = frozenset()


@dataclass(frozen=True)
class MetricSpec:
    events: tuple[str, ...]
    meaning: str


def spec(fields, statuses, source, meaning, optional=''):
    return EventSpec(frozenset(fields.split()), statuses, source, meaning, frozenset(optional.split()))


_HTTP = r'[1-5][0-9]{2}'
_DB = r'LOCK_WAIT_TIMEOUT|DEADLOCK|POOL_TIMEOUT|DISCONNECT|CONNECT_FAILURE|CLEANUP|DB_FAILURE'
EVENTS = MappingProxyType({
    'runtime.execution.failed': spec('status', 'FAILED',
        'worker/registry.py:KindRegistry.dispatch; common/jobs/worker_loop.py:WorkerLoop._run_claims',
        'Exception converted to RUNTIME_HANDLER_ERROR, before T1; not a committed terminal result. '
        'Optional outermost class qualname only, ASCII [A-Za-z_][A-Za-z0-9_]{0,63}; omit invalid names',
        optional='error_type'),
    'runtime.reflect.failed': spec('status', 'FAILED',
        'common/jobs/worker_loop.py:WorkerLoop._run_claims; common/jobs/redelivery.py:redeliver_once',
        'Initial T2 or redelivery candidate failure; T1 remains durable. '
        'Optional outermost class qualname only, ASCII [A-Za-z_][A-Za-z0-9_]{0,63}; omit invalid names',
        optional='error_type'),
    'runtime.exhaustion.failed': spec('status', 'FAILED',
        'common/jobs/exhaustion.py:redeliver_exhaustion_once',
        'Candidate rolled back; no identifiers, payload or exception text'),
    'runtime.heartbeat.attempt_ms': spec('status duration_ms', 'RENEWED|FAILED|OWNERSHIP_LOST',
        'common/jobs/heartbeat.py:Heartbeat._observe', 'Every attempt, milliseconds; no hard upper bound'),
    'runtime.heartbeat.lag_ms': spec('status duration_ms', 'RENEWED',
        'common/jobs/heartbeat.py:Heartbeat._observe', 'Successful interval minus cadence, milliseconds'),
    **{f'runtime.heartbeat.{name}': spec('status', r'0|[1-9][0-9]*',
        'common/jobs/heartbeat.py:Heartbeat._observe', 'Nonnegative integer encoded in status; preserve existing schema')
       for name in ('skipped_tick_count','consecutive_failures')},
    'runtime.stale.detect_latency_s': spec('status duration_ms', 'STALE',
        'common/jobs/sweep.py:sweep_once', 'Post-COMMIT causal ended_at-heartbeat_at; duration_ms / 1000; omit NULL heartbeat'),
    'runtime.stale.false_count': spec('status count trace_id case_id job_id execution_id', 'STALE',
        'worker/composition.py:compose_worker.record', 'Original owner attempted terminal write with zero rows and durable STALE; count=1'),
    'runtime.retry.after_case_stopped_count': spec('status', 'STOPPED_WAITING',
        'common/jobs/redelivery.py:observe_reflection', 'Committed attempt>=2 T2 NOT_APPLIED(STOPPED_WAITING) only'),
    'runtime.cancel.observe_latency_ms': spec('status duration_ms', 'REQUESTED',
        'common/jobs/heartbeat.py:LeaseConnection.renew', 'Committed DB marker observation plus monotonic signal-delivery interval'),
    'runtime.db.claim_latency_ms': spec('status duration_ms',
        'CLAIMED|EMPTY|COMMIT_UNKNOWN|LOCK_WAIT_TIMEOUT|DEADLOCK|DISCONNECT|FAILED',
        'common/jobs/repository.py:claim_one.observe', 'Transaction start to outcome; use successful commit outcomes for claim latency'),
    **{f'runtime.db.{name}': spec('status', statuses, 'common/db/transactions.py:_emit; common/jobs/worker_loop.py:WorkerLoop._db_error',
        'One observed DB failure/retry; sanitized DB taxonomy, never exception text')
       for name,statuses in (('lock_wait_timeout_count','LOCK_WAIT_TIMEOUT'),('deadlock_count','DEADLOCK'),
           ('pool_timeout_count','POOL_TIMEOUT'),('error_count',_DB),
           ('tx_retry_count','LOCK_WAIT_TIMEOUT|DEADLOCK|DISCONNECT'))},
    'runtime.reflect.redelivery_count': spec('status', 'APPLIED|ALREADY_APPLIED|NOT_APPLIED',
        'common/jobs/redelivery.py:redeliver_once', 'Committed T2 redelivery result'),
    'api.view.completed': spec('status duration_ms', '200', 'api/composition.py:ApiComposition.get_view',
        'Existing successful composition observation; not additive with route observations'),
    'api.view.request_rate': spec('count', None, 'api/routes_view.py:view_router.view',
        'Every routed GET view attempt, including failures'),
    'api.view.latency_ms': spec('duration_ms', None, 'api/routes_view.py:view_router.view',
        'View route execution duration, including failures; outer send is api.request.completed'),
    'api.request.completed': spec('status duration_ms', _HTTP, 'api/app.py:create_app.access',
        'Request latency/status; status=413 counts rejected requests, route-specific counters are not additive'),
    'api.request.rejected_413_count': spec('count', None, 'api/routes_commands.py:commands_router',
        'Commands body-limit rejection; sources are covered by api.request.completed status=413'),
    'api.upload.bytes': spec('count', None, 'api/upload.py:receive_source', 'Received upload bytes after publish; no raw body'),
    'api.upload.duration_ms': spec('duration_ms', None, 'api/upload.py:receive_source', 'Upload receive-through-publish duration'),
    'api.upload.aborted_count': spec('status count', 'idle|duration|disconnect', 'api/app.py:create_app.access',
        'One rowless abort, reason in status'),
    'api.upload.rejected_413_count': spec('count', None,
        'api/upload.py:SourceBodyLimitMiddleware; api/errors.py:install_error_handlers', 'Source upload limit rejection'),
    'api.request.failed': spec('status', _HTTP, 'api/errors.py:install_error_handlers; api/app.py:create_app.access',
        'HTTP failure by status, including source failures; correlate source requests by trace_id'),
    'api.upload.failed': spec('status', '400|404|405|409|413|415|422|500|503',
        'api/errors.py:install_error_handlers; api/upload.py:SourceBodyLimitMiddleware; api/app.py:create_app.access',
        'Source-specific HTTP failure by status; excludes rowless idle/duration/disconnect aborts'),
    'api.frame.latency_ms': spec('status duration_ms', _HTTP+'|CANCELLED|FAILED',
        'api/frame_lifetime.py:FrameLifetimeMiddleware.__call__', 'Outer ASGI response lifetime'),
    'api.frame.wait_ms': spec('duration_ms', None, 'api/frame_lifetime.py:FrameLifetimeMiddleware.__call__', 'Frame permit admission wait'),
    'api.frame.request_rate': spec('count', None, 'api/frame_lifetime.py:FrameLifetimeMiddleware.__call__', 'One frame admission occurrence'),
    **{f'api.asset.{name}': spec(fields, _HTTP+'|CANCELLED|FAILED',
        'api/asset_lifetime.py:AssetLifetimeMiddleware.__call__', meaning)
       for name, fields, meaning in (
           ('download_latency_ms','status duration_ms','Outer ASGI send lifetime'),
           ('bytes','status count','Bytes successfully returned from downstream send, not client-received bytes'))},
    'api.ready.completed': spec('status duration_ms', 'OK|UNAVAILABLE', 'api/health.py:Readiness.check',
        'Total readiness duration; UNAVAILABLE occurrence is unavailable_count, once per check'),
})

METRICS = MappingProxyType({
    **{name: MetricSpec((name,), value.meaning) for name,value in EVENTS.items()
       if (name.startswith('runtime.') and name not in (
           'runtime.exhaustion.failed', 'runtime.execution.failed', 'runtime.reflect.failed'))
       or name.startswith('api.frame.') or name.startswith('api.asset.')
       or (name.startswith('api.upload.') and name != 'api.upload.failed')},
    'api.view.request_rate': MetricSpec(('api.view.request_rate',), 'Count routed GET view attempts over operator-selected log interval'),
    'api.view.latency_ms': MetricSpec(('api.view.latency_ms',), 'View route duration_ms including failures'),
    'api.request.latency_ms': MetricSpec(('api.request.completed',), 'duration_ms across response statuses'),
    'api.request.rejected_413_count': MetricSpec(('api.request.completed',), 'Count status=413, once per request'),
    'api.upload.throughput_bps': MetricSpec(('api.upload.bytes','api.upload.duration_ms'),
        'Paired byte/duration observations by trace_id; no rate field or periodic recording is emitted'),
    'api.upload.failures': MetricSpec(('api.upload.failed',), 'Source request failures by status and request trace'),
    'api.ready.duration_ms': MetricSpec(('api.ready.completed',), 'duration_ms of each readiness check'),
    'api.ready.unavailable_count': MetricSpec(('api.ready.completed',), 'Count status=UNAVAILABLE once per readiness check'),
})


def validate_event(value):
    """Validate decoded real output in catalog tests; never serialize bad input."""
    base = {'timestamp','level','service','event'}
    correlation = {'trace_id','case_id','job_id','execution_id','module'}
    try:
        definition = EVENTS[value['event']]
        fields = {k:v for k,v in value.items() if k not in base}
        if not base <= value.keys() or not definition.required <= fields.keys():
            raise ValueError()
        if fields.keys() - definition.required - definition.optional - correlation:
            raise ValueError()
        _validate(fields)
        if definition.statuses is not None and re.fullmatch(definition.statuses, fields['status']) is None:
            raise ValueError()
        if value['service'] not in ('api','worker'):
            raise ValueError()
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValueError('event does not match Runtime catalog') from None
