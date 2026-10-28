"""#405: real MySQL outbox, Case-first delivery, recovery and admission."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from importlib import import_module, util
from io import StringIO
import json
from threading import Barrier, Event
from types import MappingProxyType

from alembic import command
from alembic.config import Config
import pytest
import sqlalchemy as sa

from daesingo.common.bootstrap import Startup
from daesingo.common.config import WorkerSettings
from daesingo.common.db import create_worker_engine
from daesingo.common.db.migrate import upgrade_all
from daesingo.common.jobs.repository import claim_one, enqueue
from daesingo.common.jobs.schema import job_execution as jobs
from daesingo.common.jobs.sweep import sweep_once, sweep_expired
from daesingo.common.logging import bind_context, configure_logging
from daesingo.worker.composition import compose_worker
from daesingo.worker.registry import KindRegistry
from mysql_fault_proxy import CommitResponseProxy
from migration_support import ROOT
from redelivery_support import Timelines, config, row, seed, snapshot, store

pytestmark = pytest.mark.mysql


def mark(family, values):
    return [pytest.param(v, marks=pytest.mark.mysql_check('exhaustion', family, parameter=v)) for v in values]


def api():
    assert util.find_spec('daesingo.common.jobs.exhaustion'), 'durable exhaustion port missing'
    return import_module('daesingo.common.jobs.exhaustion')


def receiver():
    module = import_module('daesingo.case.exhaustion_adapter')
    return module.CaseExhaustionReceiver(timelines=Timelines())


@pytest.fixture
def queue(mysql_schema_url):
    upgrade_all(mysql_schema_url)
    cfg = config(mysql_schema_url.render_as_string(hide_password=False))
    engine = create_worker_engine(cfg.db)
    try:
        yield engine, cfg
    finally:
        engine.dispose()


def notices(engine):
    table = api().job_exhaustion_notice
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(sa.select(table)).mappings()]


def expired(engine, *, kind='HINT_EXTRACT', attempt=2, cancelled=False):
    case_id, execution = seed(engine, description='private description', terminal=False, attempt=attempt)
    assert claim_one(engine, 'owner') is not None
    with engine.begin() as conn:
        conn.execute(jobs.update().where(jobs.c.execution_id == execution).values(
            kind=kind, lease_expires_at=sa.text('UTC_TIMESTAMP(6) - INTERVAL 1 SECOND'),
            cancel_requested_at=sa.func.utc_timestamp(6) if cancelled else None))
    return case_id, execution


def exhausted(engine, **kwargs):
    case_id, execution = expired(engine, **kwargs)
    result, = sweep_once(engine, WorkerSettings(), sleep=lambda _: None)
    assert result.reason == 'EXHAUSTED'
    notice, = (n for n in notices(engine) if n['final_execution_id'] == execution)
    return case_id, execution, notice


def deliver(engine, target=None, **kwargs):
    return api().redeliver_exhaustion_once(engine, target or receiver(), sleep=lambda _: None, **kwargs)


@pytest.mark.parametrize('mode', mark('creation', ('final', 'retry', 'cancel', 'COARSE_SEARCH', 'FINE_VERIFY', 'PLATE_READ', 'REPORT_VIDEO_EXPORT')))
def test_only_final_uncancelled_hint_gets_notice(queue, mode):
    engine, _ = queue
    case_id, execution = expired(engine, kind=mode if mode.isupper() else 'HINT_EXTRACT',
        attempt=1 if mode == 'retry' else 2, cancelled=mode == 'cancel')
    result, = sweep_once(engine, WorkerSettings(), sleep=lambda _: None)
    actual = notices(engine)
    assert len(actual) == int(mode == 'final')
    assert result.reason == ('RETRIED' if mode == 'retry' else 'CANCELLED' if mode == 'cancel' else 'EXHAUSTED')
    assert row(engine, execution)['case_applied_at'] is None
    if actual:
        n, = actual
        assert n['case_id'] == case_id and n['job_id'] == result.job_id
        assert n['exhausted_at'] == row(engine, execution)['ended_at']
        assert n['final_execution_id'] == execution and n['attempt'] == 2
        assert n['terminal_status'] == 'STALE' and n['reason'] == 'EXHAUSTED'
        assert n['case_acknowledged_at'] is None
        assert sweep_once(engine, WorkerSettings()) == ()
        assert notices(engine) == actual


@pytest.mark.parametrize('mode', mark('atomicity', ('commit', 'rollback', 'insert_error')))
def test_stale_and_notice_share_caller_transaction(queue, mode):
    engine, _ = queue
    _, execution = expired(engine)
    # Catch the missing outbox before trying to inject its INSERT fault.
    assert 'job_exhaustion_notice' in sa.inspect(engine).get_table_names()
    def fault(conn, cursor, sql, *args):
        if sql.upper().startswith('INSERT INTO JOB_EXHAUSTION_NOTICE'):
            raise RuntimeError('private path and payload')
    if mode == 'insert_error':
        sa.event.listen(engine, 'before_cursor_execute', fault)
    try:
        if mode == 'insert_error':
            with pytest.raises(RuntimeError), engine.begin() as conn:
                sweep_expired(conn, execution, WorkerSettings(), notice_id='notice_fixed')
        else:
            with engine.connect() as conn:
                tx = conn.begin()
                sweep_expired(conn, execution, WorkerSettings(), notice_id='notice_fixed')
                assert row(engine, execution)['status'] == 'RUNNING'
                assert notices(engine) == []
                tx.commit() if mode == 'commit' else tx.rollback()
    finally:
        if mode == 'insert_error':
            sa.event.remove(engine, 'before_cursor_execute', fault)
    assert row(engine, execution)['status'] == ('STALE' if mode == 'commit' else 'RUNNING')
    assert len(notices(engine)) == int(mode == 'commit')
    if mode == 'commit':
        assert notices(engine)[0]['notice_id'] == 'notice_fixed'


@pytest.mark.parametrize('mode', mark('identity', ('rollback_retry', 'commit_unknown', 'parallel', 'unique_job')))
def test_creation_identity_and_recovery(queue, mysql_schema_url, mode, monkeypatch):
    engine, cfg = queue
    _, execution = expired(engine)
    api()
    ids = []
    if mode == 'rollback_retry':
        def fault(conn, cursor, sql, params, *args):
            if sql.upper().startswith('INSERT INTO JOB_EXHAUSTION_NOTICE'):
                ids.append(params['notice_id'])
                if len(ids) == 1:
                    raise sa.exc.OperationalError(sql, None, Exception(1213, 'private deadlock'))
        sa.event.listen(engine, 'before_cursor_execute', fault)
        try:
            sweep_once(engine, cfg.worker, sleep=lambda _: None)
        finally:
            sa.event.remove(engine, 'before_cursor_execute', fault)
        assert len(ids) == 2 and ids[0] == ids[1] == notices(engine)[0]['notice_id']
    elif mode == 'commit_unknown':
        with CommitResponseProxy(mysql_schema_url.host, mysql_schema_url.port) as proxy:
            url = mysql_schema_url.set(host='127.0.0.1', port=proxy.port).update_query_dict({'ssl_disabled':'true'})
            proxy_engine = create_worker_engine(config(url.render_as_string(hide_password=False)).db)
            def arm(conn, cursor, sql, *args):
                if sql.upper().startswith('INSERT INTO JOB_EXHAUSTION_NOTICE'):
                    proxy.arm()
            sa.event.listen(proxy_engine, 'after_cursor_execute', arm)
            try:
                result, = sweep_once(proxy_engine, cfg.worker, sleep=lambda _: None)
                assert result.execution_id == execution
                assert len(notices(engine)) == 1
                assert proxy.commit_ok_dropped == 1
            finally:
                proxy_engine.dispose()
    elif mode == 'parallel':
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(sweep_once, engine, cfg.worker) for _ in range(2)]
            assert sum(len(f.result(15)) for f in futures) == 1
        assert len(notices(engine)) == 1
    else:
        sweep_once(engine, cfg.worker)
        original, = notices(engine)
        with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
            conn.execute(api().job_exhaustion_notice.insert().values(**(original | {'notice_id':'notice_second'})))
        assert notices(engine) == [original]


@pytest.mark.parametrize('mode', mark('delivery', ('APPLIED', 'CANCELLED', 'REFLECTED', 'EXHAUSTED', 'receipt')))
def test_case_followup_and_receipt_are_idempotent(queue, mode):
    engine, _ = queue
    case_id, execution, n = exhausted(engine)
    before = snapshot(engine, case_id)
    if mode in ('CANCELLED', 'REFLECTED', 'EXHAUSTED'):
        with engine.begin() as conn:
            c = store(conn).load_for_update(case_id)
            c.settle_job(n['job_id'], mode)
            store(conn).save(c)
    elif mode == 'receipt':
        with engine.begin() as conn:
            conn.execute(api().job_exhaustion_notice.update().values(case_acknowledged_at=sa.func.utc_timestamp(6)))
    calls = []
    actual = receiver()
    class Spy:
        def receive(self, conn, notice):
            calls.append(notice)
            assert conn.in_transaction() and not conn.closed
            return actual.receive(conn, notice)
    results = deliver(engine, Spy())
    assert len(calls) == int(mode != 'receipt')
    if mode != 'receipt':
        assert results[0].status == ('APPLIED' if mode == 'APPLIED' else 'NO_CHANGE')
    case = snapshot(engine, case_id)
    assert case.case_rev == before.case_rev
    assert case.settled_jobs[n['job_id']] == ('EXHAUSTED' if mode == 'APPLIED' else mode) if mode != 'receipt' else case.settled_jobs == before.settled_jobs
    assert len(case.job_records) == 1 + int(mode == 'APPLIED')
    if mode == 'APPLIED':
        assert case.job_records[-1]['kind'] == 'COARSE_SEARCH'
        assert all(v is None for v in case.hints.values())
        assert not case.hint_unclear
    assert notices(engine)[0]['case_acknowledged_at'] is not None
    assert row(engine, execution)['case_applied_at'] is None
    with engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(jobs)) == 1 + int(mode == 'APPLIED')
    assert deliver(engine, Spy()) == ()
    assert len(calls) == int(mode != 'receipt')


@pytest.mark.parametrize('mode', mark('rollback', ('case', 'enqueue', 'receipt', 'commit', 'rollback')))
def test_delivery_failures_leave_case_and_receipt_unwritten(queue, mode):
    engine, _ = queue
    case_id, _, _ = exhausted(engine)
    actual = receiver()
    class Faulty:
        def receive(self, conn, notice):
            result = actual.receive(conn, notice)
            if mode == 'case':
                raise RuntimeError('private exception')
            if mode in ('commit', 'rollback'):
                getattr(conn, mode)()
            return result
    def fault(conn, cursor, sql, *args):
        target = 'INSERT INTO JOB_EXECUTION' if mode == 'enqueue' else 'UPDATE JOB_EXHAUSTION_NOTICE SET CASE_ACKNOWLEDGED_AT'
        if mode in ('enqueue', 'receipt') and sql.upper().startswith(target):
            raise RuntimeError('private payload')
    sa.event.listen(engine, 'before_cursor_execute', fault)
    try:
        assert deliver(engine, Faulty()) == ()
    finally:
        sa.event.remove(engine, 'before_cursor_execute', fault)
    assert len(snapshot(engine, case_id).job_records) == 1
    assert notices(engine)[0]['case_acknowledged_at'] is None
    assert deliver(engine)[0].status == 'APPLIED'


@pytest.mark.parametrize('mode', mark('invalid', ('missing_case', 'unknown_job', 'kind', 'execution', 'job', 'case', 'attempt', 'status', 'reason', 'exhausted_at', 'trace')))
def test_invalid_notice_rolls_back_without_identifiers_in_event(queue, mode):
    engine, _ = queue
    case_id, execution, n = exhausted(engine)
    if mode in ('missing_case', 'unknown_job'):
        # Update both immutable Runtime sources so the real Case rejects wiring.
        column, value = ('case_id', 'missing_private_case') if mode == 'missing_case' else ('job_id', 'unknown_private_job')
        with engine.begin() as conn:
            conn.execute(jobs.update().where(jobs.c.execution_id == execution).values(**{column:value}))
            conn.execute(api().job_exhaustion_notice.update().values(**{column:value}))
    elif mode == 'kind':
        # CHECK protects storage; DTO boundary must independently reject kinds.
        pass
    actual = receiver()
    class Tamper:
        def receive(self, conn, incoming):
            if mode == 'kind':
                object.__setattr__(incoming, 'kind', 'PLATE_READ')
                return actual.receive(conn, incoming)
            result = actual.receive(conn, incoming)
            changes = {'execution':('final_execution_id', 'wrong_private_execution'),
                'job':('job_id', 'wrong_private_job'), 'case':('case_id', 'wrong_private_case'),
                'attempt':('attempt', 1), 'status':('status', 'FAILED'),
                'reason':('kind', 'COARSE_SEARCH'), 'exhausted_at':('ended_at', sa.func.utc_timestamp(6)),
                'trace':('trace_id','wrong_private_trace')}
            if mode in changes:
                key, value = changes[mode]
                target = api().job_exhaustion_notice if mode in ('execution','job','case','attempt','trace') else jobs
                conn.execute(target.update().values(**{key:value}))
            return result
    stream = StringIO()
    logger = configure_logging('worker', stream=stream)
    with bind_context(case_id='ambient_private_case', job_id='ambient_private_job'):
        assert deliver(engine, Tamper(), logger=logger) == ()
    assert len(snapshot(engine, case_id).job_records) == 1
    assert notices(engine)[0]['case_acknowledged_at'] is None
    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    failed, = [e for e in events if e['event'] == 'runtime.exhaustion.failed']
    assert set(failed) == {'timestamp','level','service','event','status'}
    assert failed['status'] == 'FAILED'
    assert 'private' not in stream.getvalue()


@pytest.mark.parametrize('mode', mark('redelivery', ('parallel', 'commit_unknown', 'isolation', 'scan')))
def test_redelivery_recovery_isolation_and_case_first_locking(queue, mysql_schema_url, mode):
    engine, cfg = queue
    case_id, _, n = exhausted(engine)
    actual = receiver()
    if mode == 'parallel':
        barrier = Barrier(2)
        locks = []
        class Concurrent:
            def receive(self, conn, notice):
                barrier.wait(10)
                return actual.receive(conn, notice)
        def observe(conn, cursor, sql, *args):
            if 'FOR UPDATE' in sql.upper():
                locks.append((id(conn), sql.upper()))
        sa.event.listen(engine, 'before_cursor_execute', observe)
        try:
            with ThreadPoolExecutor(2) as pool:
                futures = [pool.submit(deliver, engine, Concurrent()) for _ in range(2)]
                for f in futures:
                    f.result(20)
        finally:
            sa.event.remove(engine, 'before_cursor_execute', observe)
        for connection in {c for c, _ in locks}:
            queries = [sql for c, sql in locks if c == connection]
            assert 'CASES' in queries[0] and 'JOB_EXHAUSTION_NOTICE' in queries[1]
    elif mode == 'commit_unknown':
        calls = []
        class Spy:
            def receive(self, conn, notice):
                calls.append(notice.notice_id)
                return actual.receive(conn, notice)
        with CommitResponseProxy(mysql_schema_url.host, mysql_schema_url.port) as proxy:
            url = mysql_schema_url.set(host='127.0.0.1', port=proxy.port).update_query_dict({'ssl_disabled':'true'})
            other = create_worker_engine(config(url.render_as_string(hide_password=False)).db)
            def arm(conn, cursor, sql, *args):
                if sql.upper().startswith('UPDATE JOB_EXHAUSTION_NOTICE SET CASE_ACKNOWLEDGED_AT'):
                    proxy.arm()
            sa.event.listen(other, 'after_cursor_execute', arm)
            try:
                deliver(other, Spy())
                assert proxy.commit_ok_dropped == 1
            finally:
                other.dispose()
        assert calls == [n['notice_id']]
    elif mode == 'isolation':
        other_case, _, _ = exhausted(engine)
        class Broken:
            def receive(self, conn, notice):
                if notice.case_id == case_id:
                    raise RuntimeError('private failure')
                return actual.receive(conn, notice)
        assert len(deliver(engine, Broken())) == 1
        assert len(snapshot(engine, case_id).job_records) == 1
        assert len(snapshot(engine, other_case).job_records) == 2
        return
    else:
        def fault(conn, cursor, sql, *args):
            if 'FROM job_exhaustion_notice' in sql:
                raise sa.exc.OperationalError(sql, None, Exception(2006, 'private scan'))
        sa.event.listen(engine, 'before_cursor_execute', fault)
        try:
            with pytest.raises(sa.exc.OperationalError):
                deliver(engine)
        finally:
            sa.event.remove(engine, 'before_cursor_execute', fault)
        return
    assert len(snapshot(engine, case_id).job_records) == 2
    assert notices(engine)[0]['case_acknowledged_at'] is not None
    assert deliver(engine) == ()


@pytest.mark.parametrize('mode', mark('composition', ('startup', 'periodic', 'absent')))
def test_worker_connects_distinct_exhaustion_redelivery(queue, mode):
    engine, cfg = queue
    case_id, _, _ = exhausted(engine)
    stop = Event()
    loop = compose_worker(engine=engine, startup=Startup(cfg, MappingProxyType({}), configure_logging('worker', stream=StringIO())),
        registry=KindRegistry({}), stop=stop, exhaustion_receiver=None if mode == 'absent' else receiver())
    if mode == 'startup':
        def claim():
            assert notices(engine)[0]['case_acknowledged_at'] is not None
            stop.set()
            return None
        loop.claim = claim
        loop.run()
        assert loop.sweeper.thread is not None and not loop.sweeper.thread.is_alive()
    elif mode == 'periodic':
        def tick(_):
            stop.set()
            return False
        loop.sweeper.wait = tick
        # An interval pass is allowed to finish after the stop check at entry.
        ticks = []
        def wait(_):
            ticks.append(1)
            return len(ticks) > 1
        loop.sweeper.wait = wait
        loop.sweeper.run()
    else:
        loop.sweeper._pass()
    assert len(snapshot(engine, case_id).job_records) == 1 + int(mode != 'absent')


@pytest.mark.parametrize('mode', mark('migration', ('clean', 'upgrade', 'constraints', 'downgrade')))
def test_forward_migration_and_schema_boundaries(mysql_schema_url, mode):
    engine = create_worker_engine(config(mysql_schema_url.render_as_string(hide_password=False)).db)
    try:
        if mode == 'upgrade':
            with engine.begin() as conn:
                cfg = Config(str(ROOT/'migrations/runtime/alembic.ini'))
                cfg.attributes['connection'] = conn
                command.upgrade(cfg, 'runtime_0005')
                conn.exec_driver_sql("INSERT INTO job_execution (execution_id,job_id,status,attempt,queued_at,available_at,produced,trace_id,kind,case_id) VALUES ('retained','retained','QUEUED',1,NOW(6),NOW(6),'[]','trace','TEST','case')")
        upgrade_all(mysql_schema_url)
        api()
        with engine.connect() as conn:
            inspector = sa.inspect(conn)
            assert conn.exec_driver_sql('SELECT version_num FROM runtime_alembic_version').scalar_one() == 'runtime_0006'
            columns = {c['name']:c for c in inspector.get_columns('job_exhaustion_notice')}
            assert set(columns) == {'notice_id','job_id','case_id','kind','final_execution_id','attempt','terminal_status','reason','exhausted_at','trace_id','case_acknowledged_at'}
            assert {k for k,c in columns.items() if c['nullable']} == {'case_acknowledged_at'}
            assert columns['exhausted_at']['type'].fsp == columns['case_acknowledged_at']['type'].fsp == 6
            assert inspector.get_pk_constraint('job_exhaustion_notice')['constrained_columns'] == ['notice_id']
            assert any(c['column_names'] == ['job_id'] for c in inspector.get_unique_constraints('job_exhaustion_notice'))
            assert any(i['column_names'] == ['case_acknowledged_at','notice_id'] for i in inspector.get_indexes('job_exhaustion_notice'))
            assert [f['referred_table'] for f in inspector.get_foreign_keys('job_exhaustion_notice')] == ['job_execution']
            assert set(columns) == set(api().job_exhaustion_notice.c.keys())
            if mode == 'upgrade':
                assert conn.exec_driver_sql('SELECT execution_id FROM job_execution').scalar_one() == 'retained'
        if mode == 'constraints':
            _, _, n = exhausted(engine)
            for key,value in [('kind','PLATE_READ'),('terminal_status','FAILED'),('reason','OTHER'),('attempt',0),('final_execution_id','missing')]:
                with pytest.raises(sa.exc.DBAPIError) as error, engine.begin() as conn:
                    conn.execute(api().job_exhaustion_notice.update().values(**{key:value}))
                assert error.value.orig.args[0] == (1452 if key == 'final_execution_id' else 3819)
            assert notices(engine) == [n]
        if mode == 'downgrade':
            with pytest.raises(NotImplementedError), engine.begin() as conn:
                cfg = Config(str(ROOT/'migrations/runtime/alembic.ini'))
                cfg.attributes['connection'] = conn
                command.downgrade(cfg, 'runtime_0005')
        upgrade_all(mysql_schema_url)
    finally:
        engine.dispose()
