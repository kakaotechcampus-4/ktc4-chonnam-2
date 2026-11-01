import json
from copy import deepcopy

import pytest

from daesingo.evidence import ContractInputError, PolicyConfigurationError, attachment_constraint
from daesingo.evidence import attachments, policy_catalog


def test_plate_image_constraint_exposes_only_current_per_file_requirement():
    policy = policy_catalog.load_attachment_policy()

    assert attachment_constraint("PLATE_IMAGE") == {
        "max_byte_size": policy["limits"]["image_each_bytes"],
        "policy_ref": policy["policy_ref"],
    }


def test_constraint_reads_changed_policy_limit_from_source(monkeypatch, tmp_path):
    policy = policy_catalog.load_attachment_policy()
    policy["limits"]["image_each_bytes"] += 17
    (tmp_path / "attachment_policy_v1.json").write_text(json.dumps(policy), encoding="utf-8")
    monkeypatch.setattr(policy_catalog, "_POLICY_DIR", tmp_path)

    assert attachment_constraint("PLATE_IMAGE")["max_byte_size"] == policy["limits"]["image_each_bytes"]


def test_constraint_preserves_loaded_policy_reference_and_returns_fresh_values(monkeypatch):
    policy = policy_catalog.load_attachment_policy()
    policy["policy_ref"] += "/test-revision"
    monkeypatch.setattr(attachments, "load_attachment_policy", lambda: deepcopy(policy))

    first = attachment_constraint("PLATE_IMAGE")
    assert first["policy_ref"] == policy["policy_ref"]
    first["max_byte_size"] = 1
    assert attachment_constraint("PLATE_IMAGE")["max_byte_size"] == policy["limits"]["image_each_bytes"]


@pytest.mark.parametrize("derived_role", ["REPORT_VIDEO", "UNKNOWN", "", None, []])
def test_unsupported_role_is_an_explicit_input_error(derived_role):
    with pytest.raises(ContractInputError, match="unsupported attachment derived_role"):
        attachment_constraint(derived_role)


def test_invalid_policy_is_not_hidden(monkeypatch, tmp_path):
    monkeypatch.setattr(policy_catalog, "_POLICY_DIR", tmp_path)

    with pytest.raises(PolicyConfigurationError):
        attachment_constraint("PLATE_IMAGE")
