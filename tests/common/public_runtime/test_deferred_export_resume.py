"""#674: automatic exports deferred during T2 are retried once that T2 has committed.

SQLite proves the wrapper/composition contract only; real InnoDB admission is covered elsewhere.
"""
from threading import Event
from types import MappingProxyType, SimpleNamespace
import hashlib
import json

import pytest
import sqlalchemy as sa

from a1_support import policy_values
from test_admission import public, setup_case  # noqa: F401
from daesingo.common.bootstrap import Startup
from daesingo.common.config import RuntimeConfig
from daesingo.common.logging import configure_logging
from daesingo.common.jobs.execution import ExecutionContext, HandlerResult
from daesingo.common.jobs.reflection import ReflectionResult, RuntimeJobRecord
from daesingo.common.public_runtime import schema
from daesingo.common.public_runtime.policy import PublicPolicy
from daesingo.worker.public_reflection import PublicResultReflector
from daesingo.worker.registry import KindRegistry
from daesingo.worker import composition

AUTO = [{'job_id': 'report', 'case_id': 'case_1', 'kind': 'REPORT_VIDEO_EXPORT'},
        {'job_id': 'plate', 'case_id': 'case_1', 'kind': 'PLATE_IMAGE_EXPORT'}]


def deferred_case(db, tmp_path, *, reason, busy):
    """The OCR that deferred the exports is applied. `busy` keeps another local pair occupying the slots."""
    engine, store = db
    store.policy = PublicPolicy.model_validate(policy_values(tmp_path,
        local_work={'case_jobs': 1000, 'ip_daily_jobs': 1000, 'global_concurrent': 2}))
    setup_case(db)
    with engine.begin() as conn:
        if busy:
            store.admit_local(conn, 'case_1', hashlib.sha256(b'ocr').digest(),
                [{'job_id': 'ocr_a', 'case_id': 'case_1', 'kind': 'PLATE_READ'},
                 {'job_id': 'ocr_b', 'case_id': 'case_1', 'kind': 'OVERLAY_TIME_READ'}])
        else:
            conn.exec_driver_sql("UPDATE job_execution SET status = 'SUCCEEDED', case_applied_at = CURRENT_TIMESTAMP")
        conn.execute(schema.cases.update().where(schema.cases.c.case_id == 'case_1').values(
            local_work_state=None if reason is None else {'case_rev': 7, 'reason': reason}))


def inner_case(calls):
    def resume_auto_exports(conn, case_id, *, admit_auto_exports):
        calls.append(case_id)
        if not admit_auto_exports([dict(job) for job in AUTO]):
            return ()
        return tuple(RuntimeJobRecord(**job) for job in AUTO)
    return SimpleNamespace(resume_auto_exports=resume_auto_exports)


def state(engine):
    with engine.connect() as conn:
        return conn.scalar(sa.select(schema.cases.c.local_work_state).where(schema.cases.c.case_id == 'case_1'))


def export_admissions(engine):
    with engine.connect() as conn:
        return [row for row in conn.execute(sa.select(schema.local_admissions.c.job_ids)).scalars() if 'report' in row]


@pytest.mark.parametrize('reason', ['LOCAL_CONCURRENT', 'LOCAL_LIMIT', 'JOBS_STOPPED', None])
def test_only_capacity_deferral_is_resumed_and_then_cleared(public, tmp_path, reason):  # noqa: F811 (fixture)
    engine, store = public
    deferred_case(public, tmp_path, reason=reason, busy=False)
    calls = []
    wrapper = PublicResultReflector(inner_case(calls), store)
    with engine.begin() as conn:
        jobs = wrapper.resume_deferred_exports(conn, 'case_1', 'exec_last_ocr')
    if reason == 'LOCAL_CONCURRENT':
        assert [job.kind for job in jobs] == ['REPORT_VIDEO_EXPORT', 'PLATE_IMAGE_EXPORT']
        assert export_admissions(engine) == [['report', 'plate']]
        assert state(engine) is None  # The visible deferral notice disappears with the admission.
        # Nothing is pending any more: a later reflection does not ask Case again.
        with engine.begin() as conn:
            assert wrapper.resume_deferred_exports(conn, 'case_1', 'exec_later') == ()
        assert calls == ['case_1']
    else:
        # Limits and stops are not transient capacity; the notice and manual action stay.
        assert jobs == () and calls == []
        assert export_admissions(engine) == []


def test_still_occupied_slots_keep_the_deferral_without_partial_effects(public, tmp_path):  # noqa: F811 (fixture)
    engine, store = public
    deferred_case(public, tmp_path, reason='LOCAL_CONCURRENT', busy=True)
    calls = []
    wrapper = PublicResultReflector(inner_case(calls), store)
    with engine.begin() as conn:
        assert wrapper.resume_deferred_exports(conn, 'case_1', 'exec_last_ocr') == ()
    assert calls == ['case_1']
    assert export_admissions(engine) == []
    assert state(engine) == {'case_rev': 7, 'reason': 'LOCAL_CONCURRENT'}


def compose(db, tmp_path, monkeypatch, inner, stream=None):
    engine, store = db
    values = policy_values(tmp_path, local_work={'case_jobs': 1000, 'ip_daily_jobs': 1000, 'global_concurrent': 2})
    policy_file = tmp_path / 'policy.private.json'
    policy_file.write_text(json.dumps(values), encoding='utf8')
    policy_file.chmod(0o600)
    config = RuntimeConfig.from_mapping('worker', {'DAESINGO_RUNTIME_PUBLIC_MODE': 'internal',
        'DAESINGO_RUNTIME_DB_URL': 'mysql+pymysql://test:secret@127.0.0.1:1/fixture_test',
        'DAESINGO_RUNTIME_MEDIA_ROOT': str(tmp_path / 'media'), 'DAESINGO_RUNTIME_WORKER_TEMP_ROOT': str(tmp_path / 'temp'),
        'DAESINGO_RUNTIME_PUBLIC_POLICY_FILE': str(policy_file)})
    return composition.compose_worker(engine=engine, startup=Startup(config, MappingProxyType({}),
        configure_logging('worker', stream=stream), '1' * 40), registry=KindRegistry({}), stop=Event(), reflector=inner)


@pytest.mark.parametrize('status', ['APPLIED', 'ALREADY_APPLIED', 'NOT_APPLIED'])
def test_direct_reflection_resumes_in_a_separate_transaction_after_commit(public, tmp_path, monkeypatch, status):  # noqa: F811 (fixture)
    engine, store = public
    deferred_case(public, tmp_path, reason='LOCAL_CONCURRENT', busy=False)
    seen, enqueued = [], []
    sa.event.listen(engine, 'commit', lambda conn: seen.append('commit'))
    def resume_auto_exports(conn, case_id, *, admit_auto_exports):
        seen.append('resume')
        return inner_case([]).resume_auto_exports(conn, case_id, admit_auto_exports=admit_auto_exports)
    def reflect(conn, incoming):
        seen.append('reflect')
        return ReflectionResult(status, reason='STOPPED_WAITING' if status == 'NOT_APPLIED' else None)
    inner = SimpleNamespace(reflect=reflect, resume_auto_exports=resume_auto_exports)
    monkeypatch.setattr(composition, 'reflect_terminal', lambda conn, incoming, reflector, trace: reflector.reflect(conn, incoming))
    monkeypatch.setattr(composition, 'enqueue', lambda conn, records, trace: enqueued.append((records, trace)))
    loop = compose(public, tmp_path, monkeypatch, inner)
    result = loop.reflect(ExecutionContext('exec_last_ocr', 'ocr', 'case_1', 'PLATE_READ', 1, 'trace'), HandlerResult())
    assert result.status == status
    if status == 'APPLIED':
        # T2 commits first; the resume and its enqueue are a second, separate transaction.
        assert seen == ['reflect', 'commit', 'resume', 'commit']
        assert enqueued == [([{'job_id': 'report', 'case_id': 'case_1', 'kind': 'REPORT_VIDEO_EXPORT'},
                              {'job_id': 'plate', 'case_id': 'case_1', 'kind': 'PLATE_IMAGE_EXPORT'}], 'trace')]
    else:
        # Replays and refused results change nothing that could have freed or needed a slot.
        assert seen == ['reflect', 'commit'] and enqueued == []


@pytest.mark.parametrize('reason', [None, 'LOCAL_LIMIT'])
def test_applied_reflection_without_capacity_deferral_opens_no_extra_transaction(public, tmp_path, monkeypatch, reason):  # noqa: F811 (fixture)
    """Most reflections defer nothing: no second transaction, so no extra global control lock."""
    engine, store = public
    deferred_case(public, tmp_path, reason=reason, busy=False)
    transactions = []
    original = composition.run_worker_transaction
    def counted(engine, operation, **kw):
        transactions.append(operation)
        return original(engine, operation, **kw)
    def resume_auto_exports(conn, case_id, *, admit_auto_exports):
        raise AssertionError('Case must not be asked')
    inner = SimpleNamespace(reflect=lambda conn, incoming: ReflectionResult('APPLIED'),
                            resume_auto_exports=resume_auto_exports)
    monkeypatch.setattr(composition, 'reflect_terminal', lambda conn, incoming, reflector, trace: reflector.reflect(conn, incoming))
    monkeypatch.setattr(composition, 'run_worker_transaction', counted)
    loop = compose(public, tmp_path, monkeypatch, inner)
    assert loop.reflect(ExecutionContext('exec_last_ocr', 'ocr', 'case_1', 'PLATE_READ', 1, 'trace'),
                        HandlerResult()).status == 'APPLIED'
    assert len(transactions) == 1  # the T2 only


@pytest.mark.parametrize('sink', ['ok', 'broken'])
def test_resume_failure_is_logged_and_never_turns_a_committed_reflection_into_a_failure(public, tmp_path, monkeypatch, sink):  # noqa: F811 (fixture)
    from io import StringIO
    from daesingo.common.logging import catalog
    engine, store = public
    deferred_case(public, tmp_path, reason='LOCAL_CONCURRENT', busy=False)
    def resume_auto_exports(conn, case_id, *, admit_auto_exports):
        raise RuntimeError('TEST_ONLY_PRIVATE_RESUME_FAILURE')
    inner = SimpleNamespace(reflect=lambda conn, incoming: ReflectionResult('APPLIED'),
                            resume_auto_exports=resume_auto_exports)
    monkeypatch.setattr(composition, 'reflect_terminal', lambda conn, incoming, reflector, trace: reflector.reflect(conn, incoming))
    monkeypatch.setattr(composition, 'run_worker_transaction',
        lambda engine, operation, **kw: _once(engine, operation))
    if sink == 'broken':
        def broken(*a, **kw):
            raise RuntimeError('TEST_ONLY_LOG_SINK_FAILURE')
        monkeypatch.setattr(composition, 'log_event_best_effort', broken)
    output = StringIO()
    loop = compose(public, tmp_path, monkeypatch, inner, stream=output)
    assert loop.reflect(ExecutionContext('exec_last_ocr', 'ocr', 'case_1', 'PLATE_READ', 1, 'trace'),
                        HandlerResult()).status == 'APPLIED'
    # The deferral (and its notice/manual action) remains for the user.
    assert state(engine) == {'case_rev': 7, 'reason': 'LOCAL_CONCURRENT'}
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    failed = [e for e in events if e['event'] == 'runtime.reflect.resume_failed']
    assert 'PRIVATE' not in output.getvalue()
    if sink == 'ok':
        assert len(failed) == 1
        catalog.validate_event(failed[0])
        assert failed[0]['status'] == 'FAILED' and failed[0]['error_type'] == 'RuntimeError'
        assert failed[0]['case_id'] == 'case_1' and failed[0]['execution_id'] == 'exec_last_ocr'
    else:
        assert failed == []


def _once(engine, operation):
    with engine.begin() as conn:
        return operation(conn)
