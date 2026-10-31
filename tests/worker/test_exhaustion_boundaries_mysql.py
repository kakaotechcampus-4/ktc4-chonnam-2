"""Composition and invalid-port edges on the same real persistence boundary."""
from io import StringIO
from threading import Event
from types import MappingProxyType, SimpleNamespace

import pytest
import sqlalchemy as sa

from daesingo.common.bootstrap import Startup
from daesingo.common.db import create_worker_engine
from daesingo.common.jobs.sweep import sweep_once
from daesingo.common.jobs.schema import job_execution as jobs
from daesingo.common.logging import configure_logging
from daesingo.recording import load_recording_fixture, ConnectionRecordingRepository
from daesingo.worker.composition import compose_worker
from daesingo.worker.registry import KindRegistry
from mysql_fault_proxy import CommitResponseProxy
from redelivery_support import config, store, snapshot
from test_exhaustion_mysql import queue, api, notices, exhausted, receiver, deliver, mark

pytestmark = pytest.mark.mysql


@pytest.mark.parametrize('mode', mark('port', ('stored','job_record_kind','reason','terminal_status','result_type','cross_case','receipt_zero','unowned','store_connection')))
def test_production_adapter_and_port_reject_invalid_transactions(queue, tmp_path, mode):
    engine, _ = queue
    case_id, execution, n = exhausted(engine)
    actual = receiver()
    if mode == 'stored':
        from daesingo.worker.case_composition import StoredCaseExhaustionReceiver
        fixture = load_recording_fixture('scenario_happy_001')
        source = fixture.source_assets[0]
        video, = [s for s in fixture.media_streams if s.source_asset_ref == source.source_asset_ref and s.media_type == 'VIDEO']
        with engine.begin() as conn:
            repo = ConnectionRecordingRepository(conn, storage_root=tmp_path)
            repo.add_source_asset(source)
            for stream in fixture.media_streams:
                if stream.source_asset_ref == source.source_asset_ref:
                    repo.add_media_stream(stream)
            case = store(conn).load_for_update(case_id)
            case.sources = [{'source_asset_ref':source.source_asset_ref, 'video_stream_ref':video.media_stream_ref,
                             'duration_sec':source.duration_sec}]
            store(conn).save(case)
        assert deliver(engine, StoredCaseExhaustionReceiver(storage_root=tmp_path))[0].status == 'APPLIED'
        assert len(snapshot(engine, case_id).job_records) == 2
        return
    if mode == 'job_record_kind':
        # Real Case-issued COARSE_SEARCH JobRecord, Runtime miswired as HINT.
        from redelivery_support import seed
        from daesingo.common.config import WorkerSettings
        other_case, other_exec = seed(engine, terminal=False)
        from daesingo.common.jobs.repository import claim_one
        assert claim_one(engine, 'other_owner').execution_id == other_exec
        with engine.begin() as conn:
            conn.execute(jobs.update().where(jobs.c.execution_id == other_exec).values(
                kind='HINT_EXTRACT', attempt=2, lease_expires_at=sa.text('UTC_TIMESTAMP(6) - INTERVAL 1 SECOND')))
            conn.execute(api().job_exhaustion_notice.update().where(
                api().job_exhaustion_notice.c.notice_id == n['notice_id']).values(case_acknowledged_at=sa.func.utc_timestamp(6)))
        sweep_once(engine, WorkerSettings())
        assert deliver(engine) == ()
        assert len(snapshot(engine, other_case).job_records) == 1
        assert [v['case_acknowledged_at'] for v in notices(engine) if v['final_execution_id']==other_exec] == [None]
        return
    if mode == 'unowned':
        with engine.connect() as conn, pytest.raises(ValueError, match='caller-owned'):
            api().acknowledge_exhaustion(conn, api().notice_from_row(n), actual, n['trace_id'])
        return
    if mode == 'store_connection':
        from daesingo.case.exhaustion_adapter import CaseExhaustionReceiver
        from redelivery_support import Timelines
        actual = CaseExhaustionReceiver(timelines=Timelines(), store_factory=lambda conn: SimpleNamespace(conn=object()))
    class Invalid:
        def receive(self, conn, notice):
            if mode in ('reason','terminal_status'):
                object.__setattr__(notice, mode, 'unsupported_private_value')
            result = actual.receive(conn, notice)
            if mode == 'result_type':
                return SimpleNamespace(status='NO_CHANGE', appended_job_records=[])
            if mode == 'cross_case':
                object.__setattr__(result, 'appended_job_records', [{'job_id':'other', 'case_id':'other', 'kind':'COARSE_SEARCH'}])
            return result
    def zero(conn, cursor, sql, params, *args):
        if sql.upper().startswith('UPDATE JOB_EXHAUSTION_NOTICE SET CASE_ACKNOWLEDGED_AT'):
            return sql+' AND 1=0', params
        return sql, params
    if mode == 'receipt_zero':
        sa.event.listen(engine, 'before_cursor_execute', zero, retval=True)
    try:
        assert deliver(engine, Invalid()) == ()
    finally:
        if mode == 'receipt_zero':
            sa.event.remove(engine, 'before_cursor_execute', zero)
    assert len(snapshot(engine, case_id).job_records) == 1
    assert notices(engine)[0]['case_acknowledged_at'] is None


@pytest.mark.parametrize('phase', mark('scan_policy', ('startup','periodic')))
def test_scan_failure_uses_existing_admission_retry_and_periodic_policy(queue, phase):
    engine, cfg = queue
    case_id, _, _ = exhausted(engine)
    stop = Event()
    output = StringIO()
    loop = compose_worker(engine=engine, startup=Startup(cfg, MappingProxyType({}), configure_logging('worker',stream=output)),
        registry=KindRegistry({}), stop=stop, exhaustion_receiver=receiver())
    faulted = []
    def scan_fault(conn, cursor, sql, *args):
        if 'FROM job_exhaustion_notice' in sql and not faulted:
            faulted.append(True)
            raise sa.exc.OperationalError(sql, None, Exception(2006,'private scan failure'))
    sa.event.listen(engine,'before_cursor_execute',scan_fault)
    try:
        if phase == 'startup':
            waits = []
            def retry(seconds):
                waits.append(seconds)
                assert len(snapshot(engine,case_id).job_records) == 1
            loop.sweeper.retry_wait = retry
            def claim():
                assert len(snapshot(engine,case_id).job_records) == 2
                stop.set()
                return None
            loop.claim = claim
            loop.run()
            assert waits == [cfg.worker.error_backoff_sec]
            assert not loop.sweeper.thread.is_alive()
        else:
            ticks = []
            def wait(seconds):
                ticks.append(seconds)
                return len(ticks) == 3
            loop.sweeper.wait = wait
            loop.sweeper.run()
    finally:
        sa.event.remove(engine,'before_cursor_execute',scan_fault)
    assert faulted == [True]
    assert len(snapshot(engine,case_id).job_records) == 2
    assert 'runtime.sweep.failed' in output.getvalue() and 'private' not in output.getvalue()


@pytest.mark.mysql_check('exhaustion','port',parameter='nochange_commit_unknown')
def test_no_change_receipt_survives_unknown_commit_without_recalling_case(queue):
    engine,cfg=queue
    case_id, _, n=exhausted(engine)
    with engine.begin() as conn:
        case=store(conn).load_for_update(case_id)
        case.settle_job(n['job_id'],'CANCELLED')
        store(conn).save(case)
    actual=receiver()
    calls=[]
    class Spy:
        def receive(self,conn,notice):
            calls.append(notice.notice_id)
            return actual.receive(conn,notice)
    with CommitResponseProxy(engine.url.host,engine.url.port) as proxy:
        url=engine.url.set(host='127.0.0.1',port=proxy.port).update_query_dict({'ssl_disabled':'true'})
        other=create_worker_engine(config(url.render_as_string(hide_password=False)).db)
        def arm(conn,cursor,sql,*args):
            if sql.upper().startswith('UPDATE JOB_EXHAUSTION_NOTICE SET CASE_ACKNOWLEDGED_AT'):
                proxy.arm()
        sa.event.listen(other,'after_cursor_execute',arm)
        try:
            deliver(other,Spy())
            assert proxy.commit_ok_dropped==1
        finally:
            other.dispose()
    assert calls==[n['notice_id']]
    assert len(snapshot(engine,case_id).job_records)==1
    assert notices(engine)[0]['case_acknowledged_at'] is not None
