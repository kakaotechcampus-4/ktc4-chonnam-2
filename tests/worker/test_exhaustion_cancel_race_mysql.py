"""A cancellation after durable exhaustion must still acknowledge the notice."""
import pytest
import sqlalchemy as sa

from daesingo.case import command
from daesingo.common.config import WorkerSettings
from daesingo.common.db import create_worker_engine
from daesingo.common.jobs.cancel import request_cancel
from daesingo.common.jobs.sweep import sweep_once
from mysql_fault_proxy import CommitResponseProxy
from redelivery_support import config, snapshot, store, Timelines
from test_exhaustion_mysql import queue, exhausted, expired, notices, deliver, mark

pytestmark=pytest.mark.mysql


def stop_case(engine, case_id):
    rev=snapshot(engine,case_id).case_rev
    with engine.begin() as conn:
        result=command.execute_command({'case_id':case_id,'expected_case_rev':rev,
            'kind':'STOP_ANALYSIS','payload':{}},store=store(conn),timelines=Timelines())
        assert result.cancelled_job_ids
        request_cancel(conn,result.cancelled_job_ids)


@pytest.mark.parametrize('mode',mark('cancellation',('delivery','recovery')))
def test_late_real_stop_marker_does_not_invalidate_exhaustion(queue,mode):
    engine,cfg=queue
    if mode=='delivery':
        case_id,_,n=exhausted(engine)
        stop_case(engine,case_id)
    else:
        case_id,execution=expired(engine)
        with CommitResponseProxy(engine.url.host,engine.url.port) as proxy:
            url=engine.url.set(host='127.0.0.1',port=proxy.port).update_query_dict({'ssl_disabled':'true'})
            other=create_worker_engine(config(url.render_as_string(hide_password=False)).db)
            def arm(conn,cursor,sql,*args):
                if sql.upper().startswith('INSERT INTO JOB_EXHAUSTION_NOTICE'):proxy.arm()
            sa.event.listen(other,'after_cursor_execute',arm)
            stopped=[]
            def retry(_):
                assert proxy.commit_ok_dropped==1
                stop_case(engine,case_id)
                stopped.append(True)
            try:
                outcome,=sweep_once(other,WorkerSettings(),sleep=retry)
                assert outcome.execution_id==execution and stopped==[True]
            finally:other.dispose()
        n,=notices(engine)
    case=snapshot(engine,case_id)
    assert case.settled_jobs[n['job_id']]=='CANCELLED'
    assert len(case.job_records)==1
    result,=deliver(engine)
    assert result.status=='NO_CHANGE'
    assert notices(engine)[0]['case_acknowledged_at'] is not None
    assert len(snapshot(engine,case_id).job_records)==1
