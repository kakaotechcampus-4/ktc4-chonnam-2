"""Focused real Case/admission fixture; synthetic evidence and protected bytes, no provider."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from types import SimpleNamespace

import sqlalchemy as sa
import pytest

from a1_support import policy_values
from daesingo.case import command, exports, reflection
from daesingo.case.domain import CaseAggregate
from daesingo.case.store import CaseStore
from daesingo.case.store_mysql import MySQLCaseRepository
from daesingo.api.public_access import PublicAPI
from daesingo.common.jobs.execution import HandlerResult
from daesingo.common.jobs.read_port import read_executions
from daesingo.common.jobs.reflection import ReflectionInput, reflect_terminal
from daesingo.common.jobs.repository import enqueue
from daesingo.common.jobs.schema import job_execution
from daesingo.common.public_runtime import schema as t
from daesingo.common.public_runtime.policy import PublicPolicy, PublicDenied
from daesingo.common.public_runtime.repository import PublicStore
from daesingo.worker.case_reflector import CaseReflector
from daesingo.worker.public_reflection import PublicResultReflector


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def scenario(engine, tmp_path, monkeypatch, mode):
    policy = PublicPolicy.model_validate(policy_values(tmp_path, local_work={
        'case_jobs': 2 if mode == 'repeat' else 12, 'ip_daily_jobs': 40, 'global_concurrent': 2}))
    public = PublicStore(policy, require_public=True)
    cid = 'case_export_deferral'
    requested = {'REPORT_VIDEO_EXPORT': {'incident_clip_ref': 'clip', 'post_stamp': {'needed': False, 'value': None}},
        'PLATE_IMAGE_EXPORT': {'incident_clip_ref': 'clip', 'frame_ref': 'frame', 'plate_bbox_xywh': [1, 2, 3, 4], 'max_byte_size': 100}}
    adapter = SimpleNamespace(get_export_requests=lambda: deepcopy(requested))
    view = {'notices': [{'code': 'case.report_video_not_generated', 'actions': ['GENERATE_REPORT_VIDEO']}], 'running_jobs': [],
        'evidence': {'record_id': 'record'}, 'candidates': [{'selected': True, 'situation_confirmation': 'CONFIRMED'}],
        'requirements_package': {'checks': [{'code': 'package.asset.report_video.exists', 'outcome': 'UNKNOWN'}]}}
    # Evidence/package production is outside this fixture. Actual Case export identity and persistence are used.
    monkeypatch.setattr('daesingo.case.service.build_view_from_adapter', lambda *a, **kw: deepcopy(view))
    monkeypatch.setattr(reflection, 'mark_ready_if_package_ready', lambda *a: False)
    monkeypatch.setattr(command, 'build_view_from_adapter', lambda *a, **kw: deepcopy(view))
    monkeypatch.setattr(command, 'mark_ready_if_package_ready', lambda *a: False)
    def store(conn):
        return CaseStore(repository=MySQLCaseRepository(), conn=conn, executions=read_executions,
            adapter_factory=lambda case, connection: adapter)
    def queue(conn, records):
        if conn.dialect.name == 'mysql':
            return enqueue(conn, records, 'test-export')
        # SQLite cannot reproduce MySQL UTC clock/locking; canonical MySQL uses real enqueue/T2 below.
        stamp = now()
        ids = ['exec_' + r['job_id'] for r in records]
        for identity, r in zip(ids, records):
            conn.execute(job_execution.insert().values(execution_id=identity, job_id=r['job_id'], case_id=cid,
                kind=r['kind'], trace_id='test-export', status='QUEUED', attempt=1, produced=[], queued_at=stamp, available_at=stamp))
        return ids
    with engine.begin() as conn:
        public.set_open(conn, True)
        owner = public.fingerprint('TEST_SESSION')
        public.create_session(conn, owner, public.fingerprint('TEST_IP'))
        public.claim_case(conn, cid, owner)
        public.bind_sample(conn, cid, 'TEST_SAMPLE', [{'source_asset_ref': 'sa_test', 'sha256': 'a'*64, 'byte_size': 10, 'duration_ms': 1000}])
        case = CaseAggregate.empty(cid)
        case.stage = 'EVIDENCE_REVIEW'
        exports.issue_missing_exports(case, adapter, view)
        old_records = deepcopy(case.job_records)
        old_inputs = deepcopy(case.export_inputs)
        assert len(old_records) == 2
        public.admit_local(conn, cid, sha256(b'old-exports').digest(), old_records)
        store(conn).repository.insert(conn, case)
        executions = queue(conn, old_records)
        conn.execute(job_execution.update().values(status='SUCCEEDED', started_at=job_execution.c.queued_at, ended_at=now()))
        conn.execute(t.reservations.insert().values(usage_id='protected-usage', execution_ref=executions[0], case_id=cid,
            operation='TEST_ONLY', provider_label='TEST_ONLY', amount_micros=10, created_at=now()))
    protected = tmp_path / 'existing-download.bin'
    protected.write_bytes(b'TEST_ONLY_EXISTING_DOWNLOAD')
    old_hash = sha256(protected.read_bytes()).hexdigest()
    # A different post-stamp represents the input after an accepted time correction; command validation is tested separately.
    requested['REPORT_VIDEO_EXPORT']['post_stamp'] = {'needed': True, 'value': '2026-01-01T01:02:03+09:00'}
    with engine.begin() as conn:
        case = store(conn).load_for_update(cid)
        case.bump_revision()
        store(conn).save(case)
        if mode == 'stop':
            public.set_open(conn, False)
    reflector = PublicResultReflector(CaseReflector(reader=lambda *a: None, timelines=object(), store_factory=store), public)
    incoming = [ReflectionInput(e, r['job_id'], cid, r['kind'], 1, HandlerResult()) for e, r in zip(executions, old_records)]
    def deliver(value):
        with engine.begin() as conn:
            public.locked(conn)
            if conn.dialect.name == 'mysql':
                return reflect_terminal(conn, value, reflector, 'test-export')
            result = reflector.reflect(conn, value)
            queue(conn, [{'job_id': j.job_id, 'kind': j.kind} for j in result.jobs])
            conn.execute(job_execution.update().where(job_execution.c.execution_id == value.execution_id).values(case_applied_at=now()))
            return result
    # Before the fix this raises LOCAL_CONCURRENT/JOBS_STOPPED and rolls back each completion.
    for value in incoming:
        assert deliver(value).status == 'APPLIED'
    with engine.begin() as conn:
        public.refresh_active(conn)
        persisted = store(conn).get_case(cid)
        assert persisted.job_records == old_records
        assert all(persisted.settled_jobs[r['job_id']] == 'REFLECTED' for r in old_records)
        assert persisted.export_inputs == old_inputs
        assert len(persisted.processed_executions) == 2
        assert conn.scalar(sa.select(sa.func.count()).select_from(job_execution).where(job_execution.c.case_applied_at.is_(None))) == 0
        assert conn.scalar(sa.select(sa.func.count()).select_from(t.local_admissions).where(t.local_admissions.c.active.is_(True))) == 0
        state = conn.scalar(sa.select(t.cases.c.local_work_state).where(t.cases.c.case_id == cid))
        assert state['reason'] == ('JOBS_STOPPED' if mode == 'stop' else 'LOCAL_LIMIT' if mode == 'repeat' else 'LOCAL_CONCURRENT')
        assert conn.scalar(sa.select(sa.func.sum(t.reservations.c.amount_micros))) == 10
        public.set_open(conn, True)
    for value in incoming * 2:
        assert deliver(value).status == 'ALREADY_APPLIED'
    assert sha256(protected.read_bytes()).hexdigest() == old_hash
    # A new explicit action can retry generation; replay of old terminals cannot create it.
    def retry():
        with engine.begin() as conn:
            current = store(conn)
            payload = {'case_id': cid, 'expected_case_rev': current.get_case(cid).case_rev,
                'kind': 'RUN_NOTICE_ACTION', 'payload': {'notice_code': 'case.report_video_not_generated', 'action': 'GENERATE_REPORT_VIDEO'}}
            result = command.execute_command(payload, store=current)
            assert result.response['ok'] is True
            fresh = result.appended_job_records
            assert len(fresh) == 1
            PublicAPI.admit_result(SimpleNamespace(store=public), conn, payload, result)
            identity, = queue(conn, fresh)
            return payload, identity, fresh[0]
    if mode == 'repeat':
        with pytest.raises(PublicDenied) as refused:
            retry()
        assert refused.value.code == 'LOCAL_LIMIT'
        with engine.connect() as conn:
            assert len(store(conn).get_case(cid).job_records) == 2
    else:
        payload, identity, record = retry()
        # Same intent replay is stale and cannot charge/enqueue another export.
        with engine.begin() as conn:
            duplicate = command.execute_command(payload, store=store(conn))
            PublicAPI.admit_result(SimpleNamespace(store=public), conn, payload, duplicate)
            assert duplicate.response['ok'] is False
            assert duplicate.response['error']['code'] == 'case.command.stale_revision'
            assert conn.scalar(sa.select(sa.func.count()).select_from(job_execution)) == 3
            conn.execute(job_execution.update().where(job_execution.c.execution_id == identity).values(status='FAILED',
                started_at=job_execution.c.queued_at, ended_at=now(), failure_kind='REPORT_VIDEO_EXPORT_FAILED'))
        failed = ReflectionInput(identity, record['job_id'], cid, record['kind'], 1,
            HandlerResult(status='FAILED', failure_kind='REPORT_VIDEO_EXPORT_FAILED'))
        assert deliver(failed).status == 'APPLIED'
        second, _, _ = retry()
        assert second['expected_case_rev'] > payload['expected_case_rev']
        assert deliver(failed).status == 'ALREADY_APPLIED'
    if mode != 'repeat':
        with engine.begin() as conn:
            case = store(conn).load_for_update(cid)
            exports.issue_missing_exports(case, adapter, view)
            assert len(case.job_records) == 4
            store(conn).save(case)
            assert conn.scalar(sa.select(sa.func.count()).select_from(job_execution)) == 4
    with engine.connect() as conn:
        final = store(conn).get_case(cid)
        assert all(final.export_inputs[k] == v for k, v in old_inputs.items())
        assert conn.scalar(sa.select(sa.func.sum(t.reservations.c.amount_micros))) == 10
    assert sha256(protected.read_bytes()).hexdigest() == old_hash
