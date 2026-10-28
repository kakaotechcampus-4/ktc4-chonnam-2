"""MySQL PAD SPACE aliases must not acknowledge a miswired terminal ID."""
import pytest
import sqlalchemy as sa

from test_exhaustion_mysql import queue, api, exhausted, notices, deliver
from redelivery_support import snapshot
from daesingo.common.jobs.schema import job_execution

pytestmark=pytest.mark.mysql


@pytest.mark.mysql_check('exhaustion','port',parameter='exact_execution_id')
def test_final_execution_identity_requires_exact_python_equality(queue):
    engine,_=queue
    case_id,execution,n=exhausted(engine)
    with engine.begin() as conn:
        # Real MySQL accepts this same-module FK alias under ascii_bin.
        conn.execute(api().job_exhaustion_notice.update().values(final_execution_id=execution+' '))
        assert conn.scalar(sa.select(job_execution.c.execution_id).where(
            job_execution.c.execution_id==execution+' ')) == execution
    assert deliver(engine)==()
    assert len(snapshot(engine,case_id).job_records)==1
    assert notices(engine)[0]['case_acknowledged_at'] is None
