"""No fake prices: explicit funding policy, same admission and usage guards."""
import hashlib
import json

import pytest
import sqlalchemy as sa

from a1_support import policy_values, supported_policy_values as supported_values
from daesingo.common.public_runtime.policy import PublicDenied, PublicPolicy
from daesingo.common.public_runtime.repository import PublicStore
from daesingo.common.public_runtime import schema as t
import test_admission
from test_admission import setup_case, admit, reserve

public = test_admission.public


def supported(public, tmp_path):
    engine, _ = public
    store = PublicStore(PublicPolicy.model_validate(supported_values(tmp_path)),
                        require_public=True, worker_id="test-worker")
    result = engine, store
    setup_case(result)
    admit(result)
    return result


def test_default_krw_policy_and_fingerprint_are_backward_compatible(tmp_path):
    policy = PublicPolicy.model_validate(policy_values(tmp_path))
    assert policy.funding_mode == "krw"
    original = policy_values(tmp_path)
    original["local_work"] = None
    expected = hashlib.sha256(json.dumps(original, sort_keys=True, separators=(",", ":")).encode()).digest()
    assert policy.fingerprint() == expected
    assert policy.bound("SEARCH_COARSE", "fake:test") == 10


@pytest.mark.parametrize("change", [
    {"funding_mode": "unknown"}, {"support_ref": " "}, {"supported_calls": []},
    {"case_budget_micros": 50}, {"daily_budget_micros": 100}, {"total_budget_micros": 200},
    {"bounds": [{"operation": "SEARCH_COARSE", "provider_label": "elice:m",
                 "reserve_micros": 10, "evidence_ref": "TEST_ONLY"}]},
    {"supported_calls": [{"operation": "SEARCH_COARSE", "provider_label": "google:model"}]},
    {"supported_calls": [{"operation": "EXPORT", "provider_label": "elice:model"}]},
    {"supported_calls": [{"operation": "SEARCH_COARSE", "provider_label": "elice:"}]},
    {"supported_calls": [{"operation": "SEARCH_COARSE", "provider_label": "elice:m"}] * 2},
])
def test_supported_requires_explicit_scope_and_excludes_monetary_inputs(tmp_path, change):
    values = supported_values(tmp_path)
    values.update(change)
    with pytest.raises(ValueError):
        PublicPolicy.model_validate(values)


def test_krw_still_requires_actual_positive_caps_and_bounds(tmp_path):
    values = supported_values(tmp_path)
    values.pop("funding_mode")
    values.pop("support_ref")
    values.pop("supported_calls")
    with pytest.raises(ValueError):
        PublicPolicy.model_validate(values)
    for extra in ({"support_ref": "ref"}, {"supported_calls": [{"operation": "SEARCH_COARSE", "provider_label": "elice:m"}]}):
        with pytest.raises(ValueError):
            PublicPolicy.model_validate(dict(policy_values(tmp_path), **extra))


def test_internal_untagged_case_retains_existing_no_public_reservation_behavior(public, tmp_path):
    engine, _ = public
    store = PublicStore(PublicPolicy.model_validate(supported_values(tmp_path)), require_public=False)
    with engine.begin() as conn:
        assert store.reserve(conn, {"case_id": "internal-case"}) is False
        assert conn.execute(sa.select(sa.func.count()).select_from(t.reservations)).scalar_one() == 0


def test_supported_no_monetary_row_and_preserves_old_liability(public, tmp_path):
    result = supported(public, tmp_path)
    engine, store = result
    with engine.begin() as conn:
        from daesingo.common.public_runtime.repository import now
        conn.execute(t.reservations.insert().values(usage_id="old", execution_ref="exec_case_1", case_id="case_1",
            operation="SEARCH_COARSE", provider_label="elice:test-model", amount_micros=999999999,
            created_at=now(conn)))
    for identity in ("new", "new", "old", "retry"):
        reserve(result, identity, provider_label="elice:test-model")
    with engine.begin() as conn:
        rows = conn.execute(sa.select(t.reservations)).mappings().all()
        assert len(rows) == 1 and rows[0]["usage_id"] == "old" and rows[0]["amount_micros"] == 999999999
        store.settle(conn, "old", {"amount": "0.00001", "currency": "KRW"})
        assert conn.execute(sa.select(t.reservations.c.settled_at)).scalar_one() is not None


@pytest.mark.parametrize("guard,code", [("stop", "JOBS_STOPPED"), ("close", "STOPPED"),
    ("cancel", "CANCELLED"), ("claim", "CLAIM_LOST"), ("provider", "UNSUPPORTED"), ("identity", "CONFLICT")])
def test_supported_still_blocks_before_provider(public, tmp_path, guard, code):
    result = supported(public, tmp_path)
    engine, store = result
    provider = "elice:test-model"
    with engine.begin() as conn:
        if guard == "stop":
            store.set_open(conn, False)
        elif guard == "close":
            conn.execute(t.control.update().values(accepting=False))
        elif guard == "cancel":
            conn.exec_driver_sql("UPDATE job_execution SET cancel_requested_at=CURRENT_TIMESTAMP")
        elif guard == "claim":
            conn.exec_driver_sql("UPDATE job_execution SET lease_owner='other'")
        elif guard == "provider":
            provider = "elice:other"
        else:
            from daesingo.common.public_runtime.repository import now
            conn.execute(t.reservations.insert().values(usage_id="blocked", execution_ref="exec_case_1", case_id="case_1",
                operation="SEARCH_FINE", provider_label=provider, amount_micros=1, created_at=now(conn)))
    with pytest.raises(PublicDenied) as error:
        reserve(result, "blocked", provider_label=provider)
    assert error.value.code == code
