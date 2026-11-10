from datetime import timedelta
import hashlib

import pytest
import sqlalchemy as sa

from a1_support import policy_values, sqlite_engine
from daesingo.common.public_runtime import schema as t
from daesingo.common.public_runtime.policy import PublicPolicy
from daesingo.common.public_runtime.repository import PublicStore, now
from daesingo.api.public_retention import PublicRetention


@pytest.fixture
def retention(tmp_path):
    root, temp = tmp_path / "media", tmp_path / "temp"
    root.mkdir(); temp.mkdir(); (root / "source").mkdir()
    source = root / "source" / ("a" * 32)
    source.write_bytes(b"DISPOSABLE")
    canonical = tmp_path / "official.mp4"
    canonical.write_bytes(b"KEEP_OFFICIAL")
    engine = sqlite_engine(tmp_path / "state.sqlite")
    t.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(t.control.insert().values(id=1, accepting=False, policy_hash=None))
        conn.exec_driver_sql("CREATE TABLE job_execution(case_id TEXT,status TEXT,case_applied_at DATETIME)")
        conn.exec_driver_sql("CREATE TABLE usage_inflight(case_id TEXT,state TEXT,observed_at DATETIME)")
    store = PublicStore(PublicPolicy.model_validate(policy_values(tmp_path)), require_public=True)
    owner = store.fingerprint("session")
    with engine.begin() as conn:
        store.set_open(conn, True)
        store.create_session(conn, owner, store.fingerprint("ip"))
        store.claim_case(conn, "case_1", owner)
        token = conn.execute(sa.select(t.cases.c.temp_token)).scalar_one()
    from daesingo.common.public_runtime.temporary import case_temp_scope
    with case_temp_scope(temp, token) as directory:
        (directory / "export-crashed").write_bytes(b"TEMP")
    plan = {"case_id": "case_1", "entries": [], "files": [{"locator": "source/"+"a"*32,
        "sha256": hashlib.sha256(b"DISPOSABLE").hexdigest(), "byte_size": 10}], "shared_entries": 0}
    def finish(conn, saved):
        assert saved == plan
    service = PublicRetention(engine=engine, store=store, media_root=root, temp_root=temp,
        plan=lambda conn, cid: plan, apply=finish)
    yield service, store, owner, engine, source, canonical, directory
    engine.dispose()


def test_owned_delete_physically_removes_files_and_temps_but_retains_ledger(retention):
    service, store, owner, engine, source, official, temporary = retention
    with engine.begin() as conn:
        store.begin_delete(conn, "case_1", owner)
    result = service.purge("case_1")
    assert result["state"] == "DELETED" and not source.exists() and not temporary.exists()
    assert official.read_bytes() == b"KEEP_OFFICIAL"
    with engine.connect() as conn:
        row = conn.execute(sa.select(t.cases)).mappings().one()
        assert row["state"] == "DELETED" and row["session_hash"] == owner and row["sources"] == []


def test_live_job_is_not_cancelled_or_deleted(retention):
    service, store, owner, engine, source, official, temporary = retention
    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO job_execution VALUES ('case_1','RUNNING',NULL)")
        store.begin_delete(conn, "case_1", owner)
    result = service.purge("case_1")
    assert result["state"] == "DELETING" and result["reason"] == "BUSY"
    assert source.exists() and temporary.exists() and official.exists()


def test_recovered_unobserved_http_prevents_purge_and_quota_release(retention):
    service, store, owner, engine, source, official, temporary = retention
    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO usage_inflight VALUES ('case_1','FINALIZED',NULL)")
        store.begin_delete(conn, "case_1", owner)
    result = service.purge("case_1")
    assert result == {"state": "DELETING", "reason": "BUSY"}
    assert source.exists() and temporary.exists() and official.exists()


def test_file_mismatch_is_partial_and_retry_reuses_persisted_plan(retention):
    service, store, owner, engine, source, official, temporary = retention
    with engine.begin() as conn:
        store.begin_delete(conn, "case_1", owner)
    source.write_bytes(b"CHANGED")
    assert service.purge("case_1")["state"] == "DELETING"
    with engine.connect() as conn:
        assert conn.execute(sa.select(t.cases.c.deletion_plan)).scalar_one() is not None
    source.write_bytes(b"DISPOSABLE")
    assert service.purge("case_1")["state"] == "DELETED" and official.exists()


@pytest.mark.parametrize("deadline", ["source_expires_at", "expires_at"])
def test_expiry_scanner_preserves_live_data_then_removes_expired_case(retention, deadline):
    service, store, owner, engine, source, official, temporary = retention
    before = service.scan()
    assert before.count == before.failed == 0
    assert source.exists() and temporary.exists()
    with engine.begin() as conn:
        conn.execute(t.cases.update().values({deadline: now(conn)-timedelta(seconds=1)}))
    result = service.scan()
    assert result.count == 1 and result.failed == 0
    assert not source.exists() and not temporary.exists()
    assert official.read_bytes() == b"KEEP_OFFICIAL"
    with engine.connect() as conn:
        assert conn.scalar(sa.select(t.cases.c.state)) == "DELETED"


def test_db_failure_after_physical_removal_keeps_plan_and_retries_without_restoring_files(retention):
    service, store, owner, engine, source, official, temporary = retention
    original = service.apply
    def failed(conn, plan):
        raise RuntimeError("TEST_ONLY failure after unlink")
    service.apply = failed
    with engine.begin() as conn:
        store.begin_delete(conn, "case_1", owner)
    assert service.purge("case_1")["state"] == "DELETING"
    assert not source.exists() and not temporary.exists() and official.exists()
    with engine.connect() as conn:
        row = conn.execute(sa.select(t.cases)).mappings().one()
        assert row["state"] == "DELETING" and row["deletion_plan"] is not None
    service.apply = original
    assert service.purge("case_1")["state"] == "DELETED"


def test_case_deletion_never_resets_same_day_creation_quota(retention):
    from daesingo.common.public_runtime.policy import PublicDenied
    service, store, owner, engine, *_ = retention
    with engine.begin() as conn:
        store.begin_delete(conn, "case_1", owner)
    assert service.purge("case_1")["state"] == "DELETED"
    with engine.begin() as conn:
        store.claim_case(conn, "case_2", owner)
        store.claim_case(conn, "case_3", owner)
    with engine.begin() as conn, pytest.raises(PublicDenied) as error:
        store.claim_case(conn, "case_4", owner)
    assert error.value.code == "LIMIT"
