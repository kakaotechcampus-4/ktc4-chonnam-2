"""Read-only local/integration observations; no scheduler or transaction owner.

Issue #299 Owner comment 6367448332 fixes nearest-rank, empty groups and
oldest age. Durations use durable causal timestamps (#370), never host time.
retry_max must be the same policy used by the observed sweep (B-R1 default 1).
"""
from dataclasses import dataclass

from sqlalchemy import text


@dataclass(frozen=True)
class Distribution:
    count: int = 0
    p50: float | None = None
    p95: float | None = None
    maximum: float | None = None


@dataclass(frozen=True)
class RuntimeMetrics:
    queue_wait: dict[str, Distribution]
    execution_duration: dict[tuple[str, str], Distribution]
    stale_latency: Distribution
    cancel_latency: Distribution
    oldest_queued_age_s: float | None
    stale_count: int
    retry_auto_count: int
    retry_exhausted_count: int
    usage_recovered_count: int
    usage_inflight_count: int
    usage_inflight_oldest_age_s: float | None


# One statement: counts, DB NOW(6), samples and ranks share a statement snapshot
# even on existing READ COMMITTED connections. No locks, writes or tx control.
_QUERY = text("""
WITH samples AS (
 SELECT 'queue' metric, IF(attempt=1,'1','2+') g1, '' g2,
        TIMESTAMPDIFF(MICROSECOND,queued_at,started_at)/1000.0 value
 FROM job_execution WHERE started_at IS NOT NULL
 UNION ALL
 SELECT 'execution',kind,status,TIMESTAMPDIFF(MICROSECOND,started_at,ended_at)/1000.0
 FROM job_execution WHERE status IN ('SUCCEEDED','FAILED','STALE','CANCELLED')
 AND started_at IS NOT NULL AND ended_at IS NOT NULL
 UNION ALL
 SELECT 'stale','','',TIMESTAMPDIFF(MICROSECOND,heartbeat_at,ended_at)/1000000.0
 FROM job_execution WHERE status='STALE' AND heartbeat_at IS NOT NULL AND ended_at IS NOT NULL
 UNION ALL
 SELECT 'cancel','','',TIMESTAMPDIFF(MICROSECOND,cancel_requested_at,ended_at)/1000.0
 FROM job_execution WHERE status='CANCELLED' AND cancel_requested_at IS NOT NULL AND ended_at IS NOT NULL
), ranked AS (
 SELECT metric,g1,g2,value,
 ROW_NUMBER() OVER (PARTITION BY metric,g1,g2 ORDER BY value) rn,
 COUNT(*) OVER (PARTITION BY metric,g1,g2) n FROM samples
), distributions AS (
 SELECT metric,g1,g2,MAX(n) n,
 MAX(CASE WHEN rn=CEIL(n*0.50) THEN value END) p50,
 MAX(CASE WHEN rn=CEIL(n*0.95) THEN value END) p95,MAX(value) maximum
 FROM ranked GROUP BY metric,g1,g2
), counters AS (
 SELECT
 (SELECT MAX(GREATEST(TIMESTAMPDIFF(MICROSECOND,queued_at,NOW(6)),0))/1000000.0
  FROM job_execution WHERE status='QUEUED' AND available_at<=NOW(6)) oldest,
 (SELECT COUNT(*) FROM job_execution WHERE status='STALE') stale_count,
 (SELECT COUNT(*) FROM job_execution WHERE attempt>=2) retry_auto_count,
 (SELECT COUNT(*) FROM job_execution WHERE status='STALE' AND attempt>:retry_max
  AND cancel_requested_at IS NULL) retry_exhausted_count,
 (SELECT COUNT(*) FROM usage_inflight WHERE recovered_at IS NOT NULL) recovered_count,
 (SELECT COUNT(*) FROM usage_inflight WHERE state!='FINALIZED') inflight_count,
 (SELECT GREATEST(TIMESTAMPDIFF(MICROSECOND,MIN(occurred_at),NOW(6)),0)/1000000.0
  FROM usage_inflight WHERE state!='FINALIZED') inflight_age
)
SELECT counters.*,distributions.* FROM counters LEFT JOIN distributions ON TRUE
""")


def read_metrics(conn, *, retry_max: int = 1) -> RuntimeMetrics:
    """Materialize one SELECT in an active caller-owned transaction.

    Supports MySQL READ ONLY transactions and SELECT-only accounts. Does not
    begin, commit, rollback, set isolation/session clock, or retain DB resources.
    No time window is imposed: this is a snapshot of retained Runtime rows.
    """
    if type(retry_max) is not int or retry_max < 0:
        raise ValueError('invalid retry cap')
    if not conn.in_transaction():
        raise ValueError('metrics require a caller-owned transaction')
    rows = conn.execute(_QUERY, {'retry_max': retry_max}).mappings().all()
    queue = {'1': Distribution(), '2+': Distribution()}
    execution = {}
    global_dist = {'stale': Distribution(), 'cancel': Distribution()}
    for row in rows:
        if row['metric'] is None:
            continue
        dist = Distribution(int(row['n']), float(row['p50']), float(row['p95']), float(row['maximum']))
        if row['metric'] == 'queue':
            queue[row['g1']] = dist
        elif row['metric'] == 'execution':
            execution[row['g1'], row['g2']] = dist
        else:
            global_dist[row['metric']] = dist
    values = rows[0]
    def number(name):
        return None if values[name] is None else float(values[name])
    return RuntimeMetrics(queue, execution, global_dist['stale'], global_dist['cancel'],
        number('oldest'), int(values['stale_count']), int(values['retry_auto_count']),
        int(values['retry_exhausted_count']), int(values['recovered_count']),
        int(values['inflight_count']), number('inflight_age'))
