"""Mandatory shared MySQL counters; synthetic receipts, no actual media/provider."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import hashlib

import pytest
import sqlalchemy as sa

from a1_support import policy_values
from daesingo.common.jobs.repository import enqueue
from daesingo.common.jobs.schema import job_execution
from daesingo.common.public_runtime.policy import PublicPolicy, PublicDenied
from daesingo.common.public_runtime import schema as t
from test_public_mysql import public_db, bind  # noqa: F401

pytestmark = pytest.mark.mysql


@pytest.mark.mysql_check("public_a1", "local_work")
@pytest.mark.parametrize("mode", [pytest.param(mode, marks=pytest.mark.mysql_check("public_a1", "local_work", parameter=mode))
    for mode in ("repeat", "concurrent", "ip_limit")])
def test_local_receipt_races_do_not_exceed_separate_limits(public_db, tmp_path, mode):
    engine, store = public_db
    store.policy = PublicPolicy.model_validate(policy_values(tmp_path, local_work={
        "case_jobs": 1 if mode == "repeat" else 4,
        "ip_daily_jobs": 1 if mode == "ip_limit" else 8,
        "global_concurrent": 1 if mode == "concurrent" else 4}))
    bind(engine, store)
    with engine.begin() as conn:
        store.pause_analysis(conn)
    barrier = Barrier(2)
    def request(number):
        cid = "case_1" if mode == "repeat" else f"case_{number}"
        records = [{"job_id": f"local-{number}", "case_id": cid, "kind": "REPORT_VIDEO_EXPORT"}]
        barrier.wait(timeout=5)
        try:
            with engine.begin() as conn:
                store.admit_local(conn, cid, hashlib.sha256(str(number).encode()).digest(), records)
                enqueue(conn, records, "TEST_ONLY_LOCAL")
            return "ACCEPTED"
        except PublicDenied as denied:
            return denied.code
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(request, (1, 2)))
    assert sorted(results) == ["ACCEPTED", "LOCAL_CONCURRENT" if mode == "concurrent" else "LOCAL_LIMIT"]
    with engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(t.admissions)) == 0
        assert conn.scalar(sa.select(sa.func.sum(t.local_admissions.c.job_count))) == 1
        assert conn.scalar(sa.select(sa.func.count()).select_from(job_execution)) == 1
