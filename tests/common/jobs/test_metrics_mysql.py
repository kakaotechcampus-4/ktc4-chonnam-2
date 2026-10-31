"""RT-12(b): real MySQL values and caller-owned, SELECT-only boundaries."""
from datetime import datetime, timedelta
from importlib import import_module, util

import pytest
from sqlalchemy import event, insert, select

from daesingo.common.db.migrate import upgrade_all
from daesingo.common.jobs.schema import job_execution as jobs

pytestmark = pytest.mark.mysql


def check(scenario, parameter):
    return pytest.mark.mysql_check('observability', scenario, parameter=parameter)


@pytest.fixture
def db(mysql_engine, mysql_schema_url):
    upgrade_all(mysql_schema_url)
    return mysql_engine


def read(conn, **kwargs):
    assert util.find_spec('daesingo.common.jobs.metrics'), 'RT-12(b) metrics missing'
    return import_module('daesingo.common.jobs.metrics').read_metrics(conn, **kwargs)


BASE = datetime(2026, 1, 1)


def seed(conn, identity, *, status='SUCCEEDED', attempt=1, kind='TEST',
         wait=10, duration=20, heartbeat=True, cancel=None, **extra):
    row = dict(execution_id=identity, job_id=identity, trace_id='trace', case_id='case',
        kind=kind, attempt=attempt, status=status, produced=[], queued_at=BASE,
        available_at=BASE, started_at=BASE+timedelta(milliseconds=wait),
        ended_at=BASE+timedelta(milliseconds=wait+duration),
        heartbeat_at=BASE if heartbeat else None, cancel_requested_at=cancel)
    row.update(extra)
    conn.execute(insert(jobs).values(**row))


@check('distribution', 'empty')
def test_empty_has_fixed_attempt_groups_global_nulls_and_no_dynamic_groups(db):
    from daesingo.common.jobs.metrics import Distribution
    with db.begin() as conn:
        got = read(conn)
    assert got.queue_wait == {'1': Distribution(), '2+': Distribution()}
    assert got.execution_duration == {}
    assert got.stale_latency == Distribution()
    assert got.cancel_latency == Distribution()
    assert got.oldest_queued_age_s is None
    assert got.stale_count == got.retry_auto_count == got.retry_exhausted_count == 0
    assert got.usage_recovered_count == got.usage_inflight_count == 0
    assert got.usage_inflight_oldest_age_s is None


@pytest.mark.parametrize('n', [pytest.param(n, marks=check('distribution', str(n))) for n in (1, 2, 20, 21)])
def test_nearest_rank_returns_actual_sample_at_percentile_boundaries(db, n):
    from math import ceil
    with db.begin() as conn:
        for i in range(1, n+1):
            seed(conn, str(i), wait=i, duration=i*2)
        got = read(conn)
    dist = got.queue_wait['1']
    assert (dist.count, dist.p50, dist.p95, dist.maximum) == (n, ceil(n*.5), ceil(n*.95), n)
    execution = got.execution_duration['TEST', 'SUCCEEDED']
    assert (execution.count, execution.p50, execution.p95, execution.maximum) == (n, ceil(n*.5)*2, ceil(n*.95)*2, n*2)


@check('boundaries', 'attempt_kind_status_null')
def test_attempt_kind_status_and_terminal_inflight_null_boundaries(db):
    with db.begin() as conn:
        seed(conn, 'initial', duration=30)
        seed(conn, 'retry', attempt=2, kind='OTHER', status='FAILED', wait=5000, duration=0)
        seed(conn, 'third', attempt=3, status='STALE', duration=50, heartbeat=False)
        seed(conn, 'stale', status='STALE', duration=40)
        seed(conn, 'cancel', status='CANCELLED', cancel=BASE, started_at=None, duration=70)
        seed(conn, 'cancel_stale', status='STALE', attempt=2, cancel=BASE)
        seed(conn, 'running', status='RUNNING', ended_at=None)
        seed(conn, 'queued', status='QUEUED', started_at=None, ended_at=None)
        got = read(conn)
    assert got.queue_wait['1'].count == 3  # initial, stale, running
    assert got.queue_wait['2+'].count == 3
    assert set(got.execution_duration) == {('TEST','SUCCEEDED'), ('OTHER','FAILED'), ('TEST','STALE')}
    assert got.execution_duration['OTHER','FAILED'].p50 == 0
    assert got.stale_count == 3 and got.stale_latency.count == 2
    assert got.stale_latency.p95 == .05
    assert got.retry_auto_count == 3 and got.retry_exhausted_count == 1
    assert got.cancel_latency.count == 1 and got.cancel_latency.p95 == 80


@check('boundaries', 'oldest_db_clock')
def test_oldest_filters_available_at_and_clamps_rollback_to_zero(db):
    with db.begin() as conn:
        conn.exec_driver_sql('SET timestamp=1767225600')
        seed(conn, 'eligible', status='QUEUED', queued_at=BASE-timedelta(seconds=30),
             available_at=BASE, started_at=None, ended_at=None)
        seed(conn, 'future', status='QUEUED', queued_at=BASE-timedelta(days=1),
             available_at=BASE+timedelta(seconds=1), started_at=None, ended_at=None)
        assert read(conn).oldest_queued_age_s == 30
        conn.exec_driver_sql("DELETE FROM job_execution WHERE execution_id='eligible'")
        assert read(conn).oldest_queued_age_s is None
        seed(conn, 'rollback', status='QUEUED', queued_at=BASE+timedelta(seconds=10),
             available_at=BASE, started_at=None, ended_at=None)
        assert read(conn).oldest_queued_age_s == 0
        conn.exec_driver_sql('SET timestamp=0')


@check('transaction', 'read_only')
def test_select_only_in_actual_read_only_transaction_and_no_product_changes(db):
    with db.begin() as conn:
        seed(conn, 'committed')
    statements, endings = [], []
    def sql(conn, cursor, statement, *args): statements.append(statement)
    def ended(conn): endings.append(True)
    with db.connect() as conn:
        with conn.begin() as tx:
            # Start on the fresh connection before any table access. A preceding
            # COMMIT consumes SET TRANSACTION's one-transaction characteristic.
            conn.exec_driver_sql('START TRANSACTION READ ONLY')
            before = conn.execute(select(jobs)).mappings().all()
            event.listen(conn, 'before_cursor_execute', sql)
            event.listen(conn, 'commit', ended)
            event.listen(conn, 'rollback', ended)
            try:
                assert read(conn).queue_wait['1'].p50 == 10
                assert tx.is_active and not endings
                assert len(statements) == 1 and statements[0].lstrip().upper().startswith('WITH')
            finally:
                event.remove(conn, 'before_cursor_execute', sql)
                event.remove(conn, 'commit', ended)
                event.remove(conn, 'rollback', ended)
            assert conn.execute(select(jobs)).mappings().all() == before
            # Prove MySQL really enforces READ ONLY, not merely a SELECT-shaped
            # test double or an application transaction flag.
            from sqlalchemy.exc import DBAPIError
            with pytest.raises(DBAPIError) as rejected:
                conn.exec_driver_sql("UPDATE job_execution SET status='FAILED'")
            assert rejected.value.orig.args[0] == 1792
    assert db.pool.checkedout() == 0


@check('transaction', 'caller_rollback')
def test_query_reads_own_writes_without_committing_or_rolling_back(db):
    with db.connect() as conn:
        tx = conn.begin()
        seed(conn, 'uncommitted')
        assert read(conn).queue_wait['1'].count == 1
        with db.begin() as other:
            assert read(other).queue_wait['1'].count == 0
        tx.rollback()
    with db.begin() as conn:
        assert read(conn).queue_wait['1'].count == 0


@check('boundaries', 'usage')
def test_usage_counts_match_existing_recovery_and_preserve_rows(db):
    from daesingo.common.usage.schema import usage_inflight as tracker
    from daesingo.common.usage.reconciliation import _metrics
    with db.begin() as conn:
        conn.exec_driver_sql('SET timestamp=1767225600')
        for i, state in enumerate(('STARTED','OBSERVED','FINALIZED','FINALIZED')):
            conn.execute(insert(tracker).values(usage_id=str(i), state=state,
                occurred_at=BASE-timedelta(seconds=123 if i==0 else 20),
                provider_label='provider', operation='op', pricing_id='p', unit='u', currency='KRW',
                run_ref_reason='DIRECT_NO_RUN', recovered_at=BASE if i==2 else None))
        before = conn.execute(select(tracker)).mappings().all()
        got, existing = read(conn), _metrics(conn)
        assert got.usage_recovered_count == existing.recovered_count == 1
        assert got.usage_inflight_count == existing.inflight_count == 2
        assert got.usage_inflight_oldest_age_s == existing.inflight_oldest_age_s == 123
        assert conn.execute(select(tracker)).mappings().all() == before
        conn.exec_driver_sql('SET timestamp=0')


@pytest.mark.parametrize('state', [pytest.param(s, marks=check('catalog', 'false_'+s)) for s in
    ('STALE','SUCCEEDED','FAILED','CANCELLED','QUEUED','foreign','missing')])
def test_false_stale_requires_original_owner_zero_row_terminal_attempt(db, state):
    from io import StringIO
    import json
    from threading import Event
    from types import MappingProxyType
    from sqlalchemy import update
    from daesingo.common.bootstrap import Startup
    from daesingo.common.config import RuntimeConfig
    from daesingo.common.jobs.execution import ExecutionContext, HandlerResult
    from daesingo.common.jobs.repository import claim_one, enqueue
    from daesingo.common.logging import configure_logging
    from daesingo.worker.composition import compose_worker
    from daesingo.worker.registry import KindRegistry
    with db.begin() as conn:
        identity, = enqueue(conn, [dict(job_id='job', case_id='case',kind='TEST')], 'trace')
    claim_one(db, 'owner')
    context = ExecutionContext(identity, 'job', 'case', 'TEST', 1, 'trace')
    with db.begin() as conn:
        if state == 'missing':
            conn.execute(jobs.delete())
        else:
            conn.execute(update(jobs).values(status='STALE' if state=='foreign' else state,
                lease_owner='other' if state=='foreign' else 'owner'))
    output = StringIO()
    config = RuntimeConfig.from_mapping('worker', {
        'DAESINGO_RUNTIME_DB_URL':db.url.render_as_string(hide_password=False),
        'DAESINGO_RUNTIME_MEDIA_ROOT':'/private/media',
        'DAESINGO_RUNTIME_WORKER_TEMP_ROOT':'/private/temp'})
    loop = compose_worker(engine=db, startup=Startup(config,MappingProxyType({}),
        configure_logging('worker',stream=output)), registry=KindRegistry({}),
        stop=Event(), worker_id='owner')
    with db.begin() as conn:
        before = conn.execute(select(jobs)).mappings().all()
    result = loop.record(context, HandlerResult())
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    false = [e for e in events if e['event']=='runtime.stale.false_count']
    assert len(false) == (1 if state=='STALE' else 0)
    if false:
        assert false[0]['status']=='STALE' and false[0]['count']==1
        assert false[0]['execution_id']==identity
    assert bool(result) == (state=='SUCCEEDED')
    with db.begin() as conn:
        assert conn.execute(select(jobs)).mappings().all() == before


@check('boundaries', 'cap')
def test_exhaustion_uses_explicit_sweep_cap_and_excludes_cancellation(db):
    with db.begin() as conn:
        seed(conn, 'one', status='STALE')
        seed(conn, 'two', status='STALE', attempt=2)
        seed(conn, 'cancelled', status='STALE', attempt=3, cancel=BASE)
        assert read(conn, retry_max=0).retry_exhausted_count == 2
        assert read(conn, retry_max=1).retry_exhausted_count == 1
        assert read(conn, retry_max=2).retry_exhausted_count == 0


@check('privacy', 'logger_cleanup')
def test_actual_raw_logger_and_cleanup_emitter_keep_private_context_out(db):
    from io import StringIO
    import json
    from daesingo.common.logging import configure_logging, bind_context
    from daesingo.common.storage.cleanup import cleanup_emitter, ScanResult
    private = '12가3456 GPS=37.123456,127.123456 /private/frame PRIVATE_VIDEO_FRAME_BYTES PRIVATE_AI_REQUEST_RESPONSE PRIVATE_FREE_TEXT sk_PRIVATE_API_KEY PRIVATE_ACCESS_TOKEN PRIVATE_SECRET PRIVATE_RAW_PROVIDER'
    output = StringIO()
    logger = configure_logging('worker', stream=output)
    with bind_context(case_id='case_PRIVATE', trace_id='tr_PRIVATE', job_id='job_PRIVATE',
                      execution_id='exec_PRIVATE', module='PRIVATE'):
        logger.error(private, extra={'provider_payload':private})
        start = len(output.getvalue())
        for kind in ('staging','temp'):
            cleanup_emitter(logger)(kind, ScanResult())
    assert private not in output.getvalue()
    cleanup = [json.loads(line) for line in output.getvalue()[start:].splitlines()]
    assert len(cleanup) == 6
    assert all(set(e)=={'timestamp','level','service','event','count'} for e in cleanup)
    assert 'PRIVATE' not in output.getvalue()[start:]


@check('catalog', 'pool_timeout')
def test_catalog_observes_actual_pool_timeout_transaction_emitter(db):
    from io import StringIO
    import json
    from daesingo.common.config import DbSettings
    from daesingo.common.db import create_api_engine
    from daesingo.common.db.errors import BeforeCommitFailure
    from daesingo.common.db.transactions import run_api_transaction
    from daesingo.common.logging import configure_logging
    from daesingo.common.logging.catalog import validate_event
    output = StringIO()
    engine = create_api_engine(DbSettings(url=db.url.render_as_string(hide_password=False),
        pool_size=1, max_overflow=0, pool_timeout_sec=.05))
    try:
        with engine.connect():
            with pytest.raises(BeforeCommitFailure) as failed:
                run_api_transaction(engine, lambda conn: pytest.fail('pool should be exhausted'),
                    logger=configure_logging('api',stream=output))
            assert failed.value.reason=='pool_timeout'
        assert engine.pool.checkedout()==0
    finally:
        engine.dispose()
    value, = [json.loads(line) for line in output.getvalue().splitlines()]
    assert value['event']=='runtime.db.pool_timeout_count' and value['status']=='POOL_TIMEOUT'
    validate_event(value)
