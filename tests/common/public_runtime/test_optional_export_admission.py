"""#675: a refused report+plate pair may be re-asked as report-only under the same request key.

Case's gate (`exports.gate_auto_exports`) relies on a refused admission leaving no
row behind (caller savepoint), so the second, smaller request is a fresh admission.
"""
from types import SimpleNamespace
import hashlib

import pytest
import sqlalchemy as sa

from a1_support import policy_values
from test_admission import public, setup_case  # noqa: F401
from daesingo.common.jobs.reflection import ReflectionResult, RuntimeJobRecord
from daesingo.common.public_runtime import schema
from daesingo.common.public_runtime.policy import PublicDenied, PublicPolicy
from daesingo.worker.public_reflection import PublicResultReflector

REPORT = {'job_id': 'report', 'case_id': 'case_1', 'kind': 'REPORT_VIDEO_EXPORT'}
PLATE = {'job_id': 'plate', 'case_id': 'case_1', 'kind': 'PLATE_IMAGE_EXPORT'}


def one_slot_left(db, tmp_path):
    """Eleven of twelve case jobs are used; the earlier work is finished (no concurrency pressure)."""
    engine, store = db
    store.policy = PublicPolicy.model_validate(policy_values(tmp_path,
        local_work={'case_jobs': 12, 'ip_daily_jobs': 1000, 'global_concurrent': 12}))
    setup_case(db)
    with engine.begin() as conn:
        store.admit_local(conn, 'case_1', hashlib.sha256(b'earlier').digest(),
            [{'job_id': f'ocr_{i}', 'case_id': 'case_1', 'kind': 'PLATE_READ'} for i in range(11)])
        conn.exec_driver_sql("UPDATE job_execution SET status = 'SUCCEEDED', case_applied_at = CURRENT_TIMESTAMP")


def admissions(engine):
    with engine.connect() as conn:
        return conn.execute(sa.select(schema.local_admissions.c.request_hash, schema.local_admissions.c.job_ids)
                            .where(schema.local_admissions.c.job_ids.not_like('%ocr_%'))).all()


def test_command_key_accepts_report_only_after_pair_refusal_and_final_replay(public, tmp_path):  # noqa: F811 (fixture)
    """API command path: Case asks twice inside the command, then API admits the result with the same key."""
    engine, store = public
    one_slot_left(public, tmp_path)
    key = hashlib.sha256(b'command-payload').digest()
    with engine.begin() as conn:
        with pytest.raises(PublicDenied) as refused:
            with conn.begin_nested():
                store.admit_local(conn, 'case_1', key, [REPORT, PLATE])
        assert refused.value.code == 'LOCAL_LIMIT'
        with conn.begin_nested():
            store.admit_local(conn, 'case_1', key, [REPORT])
        # `PublicAPI.admit_result` replays the command result (report only) under the same key.
        store.admit_local(conn, 'case_1', key, [REPORT])
    assert admissions(engine) == [(key, ['report'])]


def test_reflection_admits_report_only_and_remembers_the_plate_deferral(public, tmp_path):  # noqa: F811 (fixture)
    engine, store = public
    one_slot_left(public, tmp_path)
    asked = []
    def reflect_with_admission(conn, incoming, *, admit_auto_exports, on_auto_exports_deferred):
        # Same order as Case `gate_auto_exports`: the pair, then the required report video alone.
        accepted = None
        for records in ([REPORT, PLATE], [REPORT]):
            asked.append([r['kind'] for r in records])
            if admit_auto_exports([dict(r) for r in records]):
                accepted = records
                break
        on_auto_exports_deferred(9)
        return ReflectionResult('APPLIED', jobs=tuple(RuntimeJobRecord(**r) for r in accepted))
    wrapper = PublicResultReflector(SimpleNamespace(reflect_with_admission=reflect_with_admission), store)
    with engine.begin() as conn:
        result = wrapper.reflect(conn, SimpleNamespace(case_id='case_1', execution_id='exec_last_ocr'))
    assert asked == [['REPORT_VIDEO_EXPORT', 'PLATE_IMAGE_EXPORT'], ['REPORT_VIDEO_EXPORT']]
    assert [job.kind for job in result.jobs] == ['REPORT_VIDEO_EXPORT']
    assert [ids for _, ids in admissions(engine)] == [['report']]
    with engine.connect() as conn:
        # The plate deferral stays visible (#676 owns how it is worded).
        assert conn.scalar(sa.select(schema.cases.c.local_work_state)) == {'case_rev': 9, 'reason': 'LOCAL_LIMIT'}
