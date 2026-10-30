"""SecureString collection and exclusive file publication, no AWS calls."""
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


def module():
    path = ROOT / "deploy/configure.py"
    assert path.is_file(), "protected config fetch tool missing"
    sys.path.insert(0, str(ROOT / "deploy"))
    try:
        spec = importlib.util.spec_from_file_location("rt14_configure", path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    finally:
        sys.path.pop(0)


def params():
    return [{"Name": "/approved/runtime/" + name, "Type": "SecureString", "Value": "PRIVATE-CANARY"}
            for name in ("runtime-env", "mysql-password", "mysql-root-password")]


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "plaintext", "outside", "empty"])
def test_config_fetch_rejects_incomplete_unexpected_or_plaintext(mutation):
    m = module()
    values = params()
    if mutation == "missing": values.pop()
    if mutation == "duplicate": values.append(values[0])
    if mutation == "plaintext": values[0]["Type"] = "String"
    if mutation == "outside": values[0]["Name"] = "/other/runtime-env"
    if mutation == "empty": values[0]["Value"] = ""
    with pytest.raises(m.HostError) as error:
        m.select_parameters(values, "/approved/runtime/")
    assert "PRIVATE-CANARY" not in str(error.value)


def test_config_fetch_accepts_exact_three_files():
    m = module()
    assert m.select_parameters(params(), "/approved/runtime/") == {
        "runtime.env": "PRIVATE-CANARY", "mysql-password": "PRIVATE-CANARY", "mysql-root-password": "PRIVATE-CANARY"}


def test_instance_calls_drop_operator_and_ci_credentials():
    m = module()
    result = m.instance_environment({"AWS_ACCESS_KEY_ID": "PRIVATE-CANARY", "AWS_SECRET_ACCESS_KEY": "PRIVATE-CANARY",
        "AWS_SESSION_TOKEN": "PRIVATE-CANARY", "AWS_PROFILE": "operator", "PATH": "tools"})
    assert "PRIVATE-CANARY" not in str(result)
    assert "AWS_PROFILE" not in result
    assert result["AWS_SHARED_CREDENTIALS_FILE"] == "/dev/null"


def test_config_cli_invalid_args_do_not_echo_values(capsys):
    m = module()
    assert m.main(["--config-id", "config-1", "--PRIVATE-CANARY"]) == 1
    assert "PRIVATE-CANARY" not in str(capsys.readouterr())
