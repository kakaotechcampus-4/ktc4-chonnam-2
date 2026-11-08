import pytest

from a1_support import sqlite_engine, policy_values
from daesingo.common.public_runtime import schema
from daesingo.common.public_runtime.policy import PublicPolicy, PublicDenied
from daesingo.api.public_control import control


def test_operator_open_requires_verified_catalog_and_stop_survives_missing_policy(tmp_path):
    engine = sqlite_engine(tmp_path / "operator.sqlite")
    schema.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(schema.control.insert().values(id=1, accepting=False, policy_hash=None))
    policy = PublicPolicy.model_validate(policy_values(tmp_path))
    with pytest.raises(PublicDenied):
        control(engine, policy, "open")
    def damaged_catalog():
        raise PublicDenied("INPUT")
    with pytest.raises(PublicDenied):
        control(engine, policy, "open", verify_catalog=damaged_catalog)
    assert control(engine, policy, "status")["accepting"] is False
    assert control(engine, policy, "open", verify_catalog=lambda: None)["policy_matches"] is True
    assert control(engine, None, "stop")["accepting"] is False
    engine.dispose()
