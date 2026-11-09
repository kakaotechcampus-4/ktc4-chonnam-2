"""#674: the post-T2 resume of deferred exports on real InnoDB/COMMIT.

The resume is injected to fail (as other worker_t2 tests inject faults); the
logged event goes through the real formatter and the committed T2 is untouched.
"""
from io import StringIO
import json

import pytest
import sqlalchemy as sa

from daesingo.common.jobs.schema import job_execution
from daesingo.common.logging import catalog
from daesingo.worker.public_reflection import PublicResultReflector
from test_reflection_mysql import FakeReflector, case_state, fake_case, worker  # noqa: F401
from test_worker_mysql import queue, row, seed  # noqa: F401

pytestmark = pytest.mark.mysql


def test_resume_failure_after_committed_t2_is_logged_and_keeps_t2(fake_case, monkeypatch):  # noqa: F811 (fixture)
    execution_id, = seed(fake_case)
    monkeypatch.setattr(PublicResultReflector, 'capacity_deferred', staticmethod(lambda conn, case_id: True))
    def failing(self, conn, case_id, execution_id):
        assert conn.in_transaction()  # a separate transaction, after the T2 commit
        with fake_case.connect() as other:
            assert other.scalar(sa.select(job_execution.c.case_applied_at).where(
                job_execution.c.execution_id == execution_id)) is not None
        raise RuntimeError('TEST_ONLY_PRIVATE_RESUME_FAILURE')
    monkeypatch.setattr(PublicResultReflector, 'resume_deferred_exports', failing)
    stream = StringIO()
    worker(fake_case, FakeReflector(fake_case), stream=stream).run()
    stored = row(fake_case, execution_id)
    assert stored['status'] == 'SUCCEEDED' and stored['case_applied_at'] is not None
    assert case_state(fake_case) == (1, 1)
    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    failed = [event for event in events if event['event'] == 'runtime.reflect.resume_failed']
    assert len(failed) == 1
    catalog.validate_event(failed[0])
    assert failed[0]['error_type'] == 'RuntimeError' and failed[0]['execution_id'] == execution_id
    assert 'PRIVATE' not in stream.getvalue()


def test_applied_t2_without_deferral_skips_resume_on_real_schema(fake_case, monkeypatch):  # noqa: F811 (fixture)
    """The nonlocking precheck reads the real public schema; nothing deferred means no resume."""
    execution_id, = seed(fake_case)
    def unexpected(self, conn, case_id, execution_id):
        raise AssertionError('resume must not run without a deferral')
    monkeypatch.setattr(PublicResultReflector, 'resume_deferred_exports', unexpected)
    stream = StringIO()
    worker(fake_case, FakeReflector(fake_case), stream=stream).run()
    assert row(fake_case, execution_id)['case_applied_at'] is not None
    assert 'runtime.reflect.resume_failed' not in stream.getvalue()
