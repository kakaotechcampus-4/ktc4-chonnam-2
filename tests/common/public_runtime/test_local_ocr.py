"""Local OCR is a claimed, bounded job, never an Elice/price-label exemption."""
from datetime import timedelta
import hashlib
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from a1_support import policy_values, supported_policy_values
from daesingo.common.public_runtime import schema as t
from daesingo.common.public_runtime.policy import PublicDenied, PublicPolicy
from daesingo.common.public_runtime.repository import PublicStore, now
import test_admission
from test_admission import setup_case

public = test_admission.public


@pytest.fixture(params=["PLATE_READ", "OVERLAY_TIME_READ"])
def ocr(public, tmp_path, request):
    engine, store = public
    store.policy = PublicPolicy.model_validate(supported_policy_values(tmp_path,
        local_work={"case_jobs": 3, "ip_daily_jobs": 8, "global_concurrent": 2}))
    setup_case(public)
    kind = request.param
    record = {"job_id": "ocr-job", "case_id": "case_1", "kind": kind}
    snapshot = {"usage_id": "local-usage", "case_id": "case_1", "execution_ref": "exec_case_1",
        "operation": "READOUT_PLATE" if kind == "PLATE_READ" else "READOUT_OVERLAY_TIME",
        "provider_label": "ocr-local", "pricing_id": "local-2026-09", "unit": "per_second",
        "planned_run_kind": "readout_run", "planned_run_ref": "rr_local", "direct_no_run": False}
    with engine.begin() as conn:
        conn.exec_driver_sql("UPDATE job_execution SET job_id=?, kind=?", (record["job_id"], kind))
    return SimpleNamespace(engine=engine, store=store, record=record, snapshot=snapshot, root=tmp_path)


def admit(ocr, key="local"):
    with ocr.engine.begin() as conn:
        ocr.store.admit_local(conn, "case_1", hashlib.sha256(key.encode()).digest(), [ocr.record])


def reserve(ocr):
    with ocr.engine.begin() as conn:
        return ocr.store.reserve(conn, ocr.snapshot)


def test_paused_analysis_allows_exact_ocr_without_monetary_reservation(ocr):
    before, fingerprint = ocr.store.policy.model_dump(mode="json"), ocr.store.policy.fingerprint()
    with ocr.engine.begin() as conn:
        ocr.store.pause_analysis(conn)
        conn.execute(t.reservations.insert().values(usage_id="old-liability", execution_ref="old-exec",
            case_id="case_1", operation="SEARCH_COARSE", provider_label="elice:old", amount_micros=99,
            created_at=now(conn)))
    admit(ocr)
    assert reserve(ocr) is True
    assert reserve(ocr) is True
    with ocr.engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(t.admissions)) == 0
        assert conn.scalar(sa.select(sa.func.sum(t.local_admissions.c.job_count))) == 1
        rows = conn.execute(sa.select(t.reservations)).mappings().all()
        assert len(rows) == 1 and rows[0]["usage_id"] == "old-liability" and rows[0]["amount_micros"] == 99
    assert ocr.store.policy.model_dump(mode="json") == before
    assert ocr.store.policy.fingerprint() == fingerprint


@pytest.mark.parametrize("mutation,code", [
    ("operation", "UNSUPPORTED"), ("provider", "UNSUPPORTED"), ("pricing", "UNSUPPORTED"),
    ("unit", "UNSUPPORTED"), ("run", "UNSUPPORTED"), ("direct", "UNSUPPORTED"),
    ("claimed_kind", "UNSUPPORTED"), ("receipt_job", "INPUT"), ("receipt_inactive", "INPUT"),
    ("claim", "CLAIM_LOST"), ("expired", "CLAIM_LOST"), ("cancel", "CANCELLED"),
    ("stopped", "JOBS_STOPPED"), ("missing_limits", "LOCAL_UNCONFIGURED"), ("expired_source", "INPUT"),
])
def test_ocr_identity_receipt_and_live_claim_are_required_before_usage(ocr, mutation, code):
    admit(ocr)
    with ocr.engine.begin() as conn:
        if mutation in {"operation", "provider", "pricing", "unit", "run", "direct"}:
            key, value = {"operation": ("operation", "CANDIDATE_SEARCH"),
                "provider": ("provider_label", "elice:test-model"),
                "pricing": ("pricing_id", "not-local"), "unit": ("unit", "per_token"),
                "run": ("planned_run_kind", "analysis_run"), "direct": ("direct_no_run", True)}[mutation]
            ocr.snapshot[key] = value
        elif mutation == "claimed_kind":
            conn.exec_driver_sql("UPDATE job_execution SET kind='FINE_VERIFY'")
        elif mutation == "receipt_job":
            conn.execute(t.local_admissions.update().values(job_ids=["another-job"]))
        elif mutation == "receipt_inactive":
            conn.execute(t.local_admissions.update().values(active=False))
        elif mutation == "claim":
            conn.exec_driver_sql("UPDATE job_execution SET lease_owner='other'")
        elif mutation == "expired":
            conn.exec_driver_sql("UPDATE job_execution SET lease_expires_at=?", (now(conn) - timedelta(seconds=1),))
        elif mutation == "cancel":
            conn.exec_driver_sql("UPDATE job_execution SET cancel_requested_at=CURRENT_TIMESTAMP")
        elif mutation == "stopped":
            ocr.store.set_open(conn, False)
        elif mutation == "missing_limits":
            ocr.store.policy = ocr.store.policy.model_copy(update={"local_work": None})
            conn.execute(t.control.update().values(policy_hash=ocr.store.policy.fingerprint()))
        else:
            conn.execute(t.cases.update().values(source_expires_at=now(conn) - timedelta(seconds=1)))
    with pytest.raises(PublicDenied) as denied:
        reserve(ocr)
    assert denied.value.code == code
    with ocr.engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM usage_inflight").scalar_one() == 0
        assert conn.scalar(sa.select(sa.func.count()).select_from(t.reservations)) == 0


def test_paid_receipt_alone_does_not_authorize_unmetered_ocr(ocr):
    with ocr.engine.begin() as conn:
        ocr.store.admit(conn, "case_1", b"a" * 32, initial=True)
    with pytest.raises(PublicDenied) as denied:
        reserve(ocr)
    assert denied.value.code == "INPUT"


def test_local_ocr_keeps_external_krw_bounds_and_existing_policy(ocr):
    ocr.store.policy = PublicPolicy.model_validate(policy_values(ocr.root,
        local_work={"case_jobs": 3, "ip_daily_jobs": 8, "global_concurrent": 2}))
    with ocr.engine.begin() as conn:
        ocr.store.set_open(conn, True)
    admit(ocr)
    assert reserve(ocr) is True
    assert ocr.store.policy.bound("SEARCH_COARSE", "fake:test") == 10
    with pytest.raises(PublicDenied) as denied:
        ocr.store.policy.bound("CANDIDATE_SEARCH", "fake:test")
    assert denied.value.code == "UNPRICED"
    with ocr.engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(t.reservations)) == 0


def test_untagged_internal_usage_keeps_existing_no_execution_lock_path(public):
    engine, store = public
    store = PublicStore(store.policy, require_public=False)
    statements = []
    def observe(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())
    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        with engine.begin() as conn:
            assert store.reserve(conn, {"case_id": "internal-case"}) is False
        assert not any("from job_execution" in s for s in statements)
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)


def test_ocr_retry_uses_finite_local_quota_without_resetting_analysis_repeats(ocr):
    with ocr.engine.begin() as conn:
        owner = conn.execute(sa.select(t.cases)).mappings().one()
        for number in range(2):
            conn.execute(t.admissions.insert().values(case_id="case_1", request_hash=bytes([number]) * 32,
                session_hash=owner["session_hash"], ip_hash=owner["ip_hash"], created_at=now(conn),
                initial=False, active=False))
    admit(ocr)
    assert reserve(ocr) is True
    with ocr.engine.begin() as conn, pytest.raises(PublicDenied) as denied:
        ocr.store.admit(conn, "case_1", b"r" * 32, initial=False)
    assert denied.value.code == "LIMIT"
    with ocr.engine.begin() as conn:
        conn.execute(t.local_admissions.update().values(active=False))
        limits = ocr.store.policy.local_work.model_copy(update={"case_jobs": 1})
        ocr.store.policy = ocr.store.policy.model_copy(update={"local_work": limits})
        conn.execute(t.control.update().values(policy_hash=ocr.store.policy.fingerprint()))
    with pytest.raises(PublicDenied) as refused:
        admit(ocr, key="next-local-intent")
    assert refused.value.code == "LOCAL_LIMIT"
    with ocr.engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(t.admissions)) == 2
        assert conn.scalar(sa.select(sa.func.sum(t.local_admissions.c.job_count))) == 1


def test_ocr_pair_counts_two_local_slots_and_rejects_a_third_job(ocr):
    pair = [ocr.record, {"job_id": "ocr-second", "case_id": "case_1", "kind": "OVERLAY_TIME_READ"}]
    with ocr.engine.begin() as conn:
        ocr.store.admit_local(conn, "case_1", b"p" * 32, pair)
    with ocr.engine.begin() as conn, pytest.raises(PublicDenied) as denied:
        ocr.store.admit_local(conn, "case_1", b"n" * 32,
            [{"job_id": "report-third", "case_id": "case_1", "kind": "REPORT_VIDEO_EXPORT"}])
    assert denied.value.code == "LOCAL_CONCURRENT"


def test_portable_failed_clip_retry_command_receipt_and_rollback(tmp_path):
    from a1_support import sqlite_engine
    from daesingo.case.store_mysql import metadata as case_metadata
    from daesingo.common.jobs.schema import job_execution
    from daesingo.common.usage.schema import usage_record
    from tests.worker.test_public_local_ocr_mysql import _retry_failed_plate_scenario
    engine = sqlite_engine(tmp_path / "retry-command.sqlite")
    @sa.event.listens_for(engine, "connect")
    def configure(dbapi, _):
        dbapi.create_collation("ascii_bin", lambda a, b: (a > b) - (a < b))
    try:
        case_metadata.create_all(engine)
        t.metadata.create_all(engine)
        job_execution.create(engine)
        usage_record.create(engine)
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE usage_inflight (case_id TEXT, observed_at DATETIME)")
            conn.execute(t.control.insert().values(id=1, accepting=False))
        _retry_failed_plate_scenario(engine, tmp_path)
    finally:
        engine.dispose()
