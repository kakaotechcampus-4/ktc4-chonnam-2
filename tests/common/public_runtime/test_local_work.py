"""Explicit local resource ceilings; no prices, providers or operational approvals."""
import hashlib

import pytest
import sqlalchemy as sa

from a1_support import policy_values
from daesingo.common.public_runtime.policy import PublicPolicy, PublicDenied
from daesingo.common.public_runtime import schema as t
from test_admission import public, setup_case  # noqa: F401


def configured(public, tmp_path, **changes):
    engine, store = public
    values = policy_values(tmp_path, local_work={"case_jobs": 3, "ip_daily_jobs": 8,
        "global_concurrent": 2, **changes})
    store.policy = PublicPolicy.model_validate(values)
    setup_case(public)
    with engine.begin() as conn:
        conn.exec_driver_sql("UPDATE job_execution SET status='SUCCEEDED', case_applied_at=CURRENT_TIMESTAMP")
        store.pause_analysis(conn)
    return engine, store


def job(name="local1", kind="REPORT_VIDEO_EXPORT"):
    return {"job_id": name, "case_id": "case_1", "kind": kind}


def admit(public, key="one", jobs=None):
    engine, store = public
    with engine.begin() as conn:
        store.admit_local(conn, "case_1", hashlib.sha256(key.encode()).digest(), jobs or [job()])


def test_analysis_pause_allows_bounded_export_without_analysis_receipt(public, tmp_path):
    engine, store = configured(public, tmp_path)
    admit(public)
    admit(public)  # retry is the same receipt, not another quota charge
    with engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(t.admissions)) == 0
        assert conn.scalar(sa.select(sa.func.sum(t.local_admissions.c.job_count))) == 1
    with engine.begin() as conn, pytest.raises(PublicDenied) as denied:
        store.admit(conn, "case_1", b"x"*32, initial=False)
    assert denied.value.code == "STOPPED"


def test_missing_local_limits_is_not_unlimited(public):
    setup_case(public)
    with pytest.raises(PublicDenied) as denied:
        admit(public)
    assert denied.value.code == "LOCAL_UNCONFIGURED"


def test_local_limit_counts_actual_jobs_and_does_not_consume_analysis_repeats(public, tmp_path):
    engine, store = configured(public, tmp_path, case_jobs=2)
    admit(public, jobs=[job("report"), job("plate", "PLATE_IMAGE_EXPORT")])
    with pytest.raises(PublicDenied) as denied:
        admit(public, key="two", jobs=[job("preview", "CANDIDATE_VIDEO_PREVIEW")])
    assert denied.value.code == "LOCAL_LIMIT"
    with engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(t.admissions)) == 0


def test_emergency_stop_blocks_even_previously_allowed_local_job(public, tmp_path):
    engine, store = configured(public, tmp_path)
    admit(public)
    with engine.begin() as conn:
        store.set_open(conn, False)
    with pytest.raises(PublicDenied) as denied:
        admit(public, key="new")
    assert denied.value.code == "JOBS_STOPPED"


def test_batch_export_counts_two_concurrent_jobs_not_one_receipt(public, tmp_path):
    configured(public, tmp_path, global_concurrent=1)
    with pytest.raises(PublicDenied) as denied:
        admit(public, jobs=[job("report"), job("plate", "PLATE_IMAGE_EXPORT")])
    assert denied.value.code == "LOCAL_CONCURRENT"


@pytest.mark.parametrize("kind", ["FINE_VERIFY", "INCIDENT_CLIP_BUILD", "PLATE_READ", "FUTURE_JOB"])
def test_local_receipt_cannot_authorize_other_handlers(public, tmp_path, kind):
    configured(public, tmp_path)
    with pytest.raises(PublicDenied):
        admit(public, jobs=[job(kind=kind)])
