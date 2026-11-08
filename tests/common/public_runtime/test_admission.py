from concurrent.futures import ThreadPoolExecutor
import hashlib

import pytest
import sqlalchemy as sa

from a1_support import policy_values, sqlite_engine
from daesingo.common.public_runtime.policy import PublicPolicy, PublicDenied
from daesingo.common.public_runtime import schema as tables
from daesingo.common.public_runtime.repository import PublicStore


@pytest.fixture
def public(tmp_path):
    engine = sqlite_engine(tmp_path / "public.sqlite")
    tables.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(tables.control.insert().values(id=1, accepting=False, policy_hash=None))
        conn.exec_driver_sql("CREATE TABLE job_execution (execution_id TEXT PRIMARY KEY, case_id TEXT, status TEXT, "
                            "case_applied_at DATETIME, lease_owner TEXT, lease_expires_at DATETIME, cancel_requested_at DATETIME)")
        conn.exec_driver_sql("CREATE TABLE usage_inflight (usage_id TEXT PRIMARY KEY, case_id TEXT, observed_at DATETIME, state TEXT)")
    policy = PublicPolicy.model_validate(policy_values(tmp_path))
    store = PublicStore(policy, require_public=True, worker_id="test-worker")
    yield engine, store
    engine.dispose()


def setup_case(public, name="case_1", token="session", ip="ip"):
    engine, store = public
    owner = store.fingerprint(token)
    with engine.begin() as conn:
        store.set_open(conn, True)
        store.create_session(conn, owner, store.fingerprint(ip))
        store.claim_case(conn, name, owner)
        store.bind_sample(conn, name, "synthetic", [{"source_asset_ref": "sa_1", "sha256": "a" * 64,
            "byte_size": 12, "duration_ms": 1000}])
        from datetime import timedelta
        from daesingo.common.public_runtime.repository import now
        conn.exec_driver_sql("INSERT INTO job_execution VALUES (?, ?, 'RUNNING', NULL, 'test-worker', ?, NULL)",
                            ("exec_" + name, name, now(conn) + timedelta(hours=1)))
    return owner


def admit(public, name="case_1", key="command1", initial=True):
    engine, store = public
    with engine.begin() as conn:
        store.admit(conn, name, hashlib.sha256(key.encode()).digest(), initial=initial)


def reserve(public, identity, name="case_1", **changes):
    engine, store = public
    with engine.begin() as conn:
        store.reserve(conn, {"usage_id": identity, "case_id": name, "execution_ref": "exec_" + name,
            "operation": "SEARCH_COARSE", "provider_label": "fake:test", **changes})


def test_missing_policy_and_closed_control_refuse_before_any_admission(public):
    engine, store = public
    for closed in (store, PublicStore(None, require_public=True)):
        with engine.begin() as conn, pytest.raises(PublicDenied):
            closed.admit(conn, "case_1", b"a" * 32, initial=True)
    with engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(tables.admissions)).scalar_one() == 0


def test_shared_owner_not_case_identifier_is_required(public):
    owner = setup_case(public)
    engine, store = public
    with engine.begin() as conn:
        store.require_owner(conn, "case_1", owner)
        with pytest.raises(PublicDenied) as error:
            store.require_owner(conn, "case_1", store.fingerprint("other"))
        assert error.value.code == "NOT_FOUND"


def test_duplicate_admission_and_begin_reservation_do_not_double_charge(public):
    setup_case(public)
    admit(public)
    admit(public)
    reserve(public, "usage1")
    reserve(public, "usage1")
    engine, _ = public
    with engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(tables.admissions)).scalar_one() == 1
        assert conn.execute(sa.select(sa.func.sum(tables.reservations.c.amount_micros))).scalar_one() == 10


def test_concurrent_initial_requests_share_session_and_global_gate(public):
    setup_case(public)
    def attempt(number):
        try:
            admit(public, key=str(number))
            return True
        except PublicDenied:
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(attempt, range(8))).count(True) == 1


def test_each_real_attempt_reserves_again_and_exhaustion_blocks_before_http(public):
    setup_case(public)
    admit(public)
    calls = []
    for n in range(6):
        try:
            reserve(public, "usage" + str(n))
            calls.append("HTTP")
        except PublicDenied as error:
            assert n == 5 and error.code == "BUDGET"
    assert len(calls) == 5


def test_failed_begin_transaction_rolls_back_reservation_and_retry_is_exact(public):
    setup_case(public)
    admit(public)
    engine, store = public
    with pytest.raises(RuntimeError), engine.begin() as conn:
        store.reserve(conn, {"usage_id": "usage", "case_id": "case_1", "execution_ref": "exec_case_1",
            "operation": "SEARCH_COARSE", "provider_label": "fake:test"})
        raise RuntimeError("simulated STARTED failure")
    with engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(tables.reservations)).scalar_one() == 0
    reserve(public, "usage")


def test_stop_blocks_next_queued_attempt_and_new_command_but_keeps_reads(public):
    owner = setup_case(public)
    admit(public)
    reserve(public, "first")
    engine, store = public
    with engine.begin() as conn:
        store.set_open(conn, False)
        store.require_owner(conn, "case_1", owner)
    with pytest.raises(PublicDenied):
        reserve(public, "second")
    with pytest.raises(PublicDenied):
        admit(public, key="next", initial=False)


def test_unknown_provider_and_unbound_public_case_cannot_bypass(public):
    setup_case(public)
    admit(public)
    with pytest.raises(PublicDenied):
        reserve(public, "unknown", provider_label="not-approved")
    with pytest.raises(PublicDenied):
        reserve(public, "unbound", name="case_other")


def test_deleting_case_refuses_new_attempt_and_tombstone_is_idempotent(public):
    owner = setup_case(public)
    admit(public)
    engine, store = public
    with engine.begin() as conn:
        store.begin_delete(conn, "case_1", owner)
        store.begin_delete(conn, "case_1", owner)
    with pytest.raises(PublicDenied):
        reserve(public, "after-delete")


def test_midnight_does_not_discard_an_unsettled_prior_day_liability(public):
    from datetime import timedelta
    from daesingo.common.public_runtime.repository import now
    engine, original = public
    store = PublicStore(original.policy.model_copy(update={"daily_budget_micros": 10}), require_public=True, worker_id="test-worker")
    public = engine, store
    setup_case(public)
    admit(public)
    reserve(public, "pending")
    with engine.begin() as conn:
        conn.execute(tables.reservations.update().values(created_at=now(conn) - timedelta(days=1)))
    with pytest.raises(PublicDenied) as error:
        reserve(public, "new-day")
    assert error.value.code == "BUDGET"


@pytest.mark.parametrize("change", ["missing", "stale", "cancelled", "owner", "expired"])
def test_no_new_http_after_claim_loss_cancellation_or_lease_expiry(public, change):
    setup_case(public)
    admit(public)
    engine, _ = public
    with engine.begin() as conn:
        if change == "missing":
            conn.exec_driver_sql("DELETE FROM job_execution")
        elif change == "stale":
            conn.exec_driver_sql("UPDATE job_execution SET status='STALE'")
        elif change == "cancelled":
            conn.exec_driver_sql("UPDATE job_execution SET cancel_requested_at=CURRENT_TIMESTAMP")
        elif change == "owner":
            conn.exec_driver_sql("UPDATE job_execution SET lease_owner='different-worker'")
        else:
            conn.exec_driver_sql("UPDATE job_execution SET lease_expires_at='2000-01-01 00:00:00'")
    with pytest.raises(PublicDenied):
        reserve(public, "after-loss")


def test_settlement_today_of_yesterdays_unknown_cost_stays_in_today_cap(public):
    from datetime import timedelta
    from daesingo.common.public_runtime.repository import now
    engine, original = public
    store = PublicStore(original.policy.model_copy(update={"daily_budget_micros": 10}),
                        require_public=True, worker_id="test-worker")
    public = engine, store
    setup_case(public)
    admit(public)
    reserve(public, "old")
    with engine.begin() as conn:
        conn.execute(tables.reservations.update().values(created_at=now(conn)-timedelta(days=1)))
        store.settle(conn, "old", {"amount": "0.00001", "currency": "KRW"})
    with pytest.raises(PublicDenied):
        reserve(public, "new")


def test_preparation_gate_precedes_expensive_probe_and_reuse_is_free(public):
    owner = setup_case(public)
    engine, store = public
    with engine.begin() as conn:
        assert store.begin_preparation(conn, "case_1", owner, "synthetic", "token1") is False
        conn.execute(tables.cases.update().values(sample_id=None, sources=[]))
        assert store.begin_preparation(conn, "case_1", owner, "synthetic", "token1") is True
    with engine.begin() as conn, pytest.raises(PublicDenied):
        store.begin_preparation(conn, "case_1", owner, "synthetic", "token2")
    with engine.begin() as conn:
        store.finish_preparation(conn, "token1")
        store.set_open(conn, False)
    with engine.begin() as conn, pytest.raises(PublicDenied):
        store.begin_preparation(conn, "case_1", owner, "synthetic", "token3")


@pytest.mark.parametrize("field,value", [("daily_budget_micros", 0), ("approval_ref", ""),
    ("session_key", "short"), ("total_budget_micros", True), ("bounds", []),
    ("origin", "http://testserver"), ("manifest_sha256", "bad")])
def test_missing_or_invalid_operational_values_are_not_defaulted(tmp_path, field, value):
    with pytest.raises(ValueError):
        PublicPolicy.model_validate(policy_values(tmp_path, **{field: value}))


def test_recovered_job_does_not_release_slot_while_old_http_is_unobserved(public):
    setup_case(public)
    setup_case(public, name="case_2")
    admit(public)
    engine, store = public
    with engine.begin() as conn:
        conn.exec_driver_sql("UPDATE job_execution SET status='FAILED', case_applied_at=CURRENT_TIMESTAMP")
        # Recovery/finalization is not proof the previous leased HTTP returned.
        conn.exec_driver_sql("INSERT INTO usage_inflight VALUES ('uncertain','case_1',NULL,'FINALIZED')")
    with pytest.raises(PublicDenied) as error:
        admit(public, name="case_2")
    assert error.value.code == "CONCURRENT"
    with engine.begin() as conn:
        conn.exec_driver_sql("UPDATE usage_inflight SET observed_at=CURRENT_TIMESTAMP")
    admit(public, name="case_2")
