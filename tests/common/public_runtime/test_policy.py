import json
from types import SimpleNamespace
import pytest

from a1_support import policy_values
from daesingo.common.public_runtime.policy import load_policy


def test_read_access_timestamp_does_not_randomly_disable_valid_protected_policy(tmp_path, monkeypatch):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy_values(tmp_path)), encoding="utf-8")
    path.chmod(0o600)
    original = type(path).lstat
    counter = [0]
    def stat(self):
        result = original(self)
        fields = {key: getattr(result, key) for key in (
            "st_dev", "st_ino", "st_mode", "st_uid", "st_size", "st_nlink", "st_mtime_ns", "st_ctime_ns")}
        counter[0] += 1
        return SimpleNamespace(**fields, st_atime=counter[0])
    monkeypatch.setattr(type(path), "lstat", stat)
    assert load_policy(path, revision="1" * 40) is not None


@pytest.mark.parametrize("field", ["case_budget_micros", "daily_budget_micros", "total_budget_micros", "reserve_micros"])
def test_zero_approval_or_invocation_ceiling_cannot_open_public_analysis(tmp_path, field):
    values = policy_values(tmp_path)
    if field == "reserve_micros":
        values["bounds"][0][field] = 0
    else:
        values[field] = 0
    path = tmp_path / "zero-policy.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    path.chmod(0o600)
    assert load_policy(path, revision="1" * 40) is None
