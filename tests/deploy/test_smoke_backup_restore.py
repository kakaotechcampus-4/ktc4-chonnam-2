import importlib.util
import ast
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def scripts_path(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))


def load(relative):
    path = ROOT / relative
    assert path.is_file(), "RT-13(b) acceptance component missing"
    spec = importlib.util.spec_from_file_location("rt13b_component", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_snapshot_compares_identity_values_binary_and_table_inventory():
    probe = load("tests/deploy/backup_probe.py")
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE durable (identity int primary key, payload text, content blob)"
        )
        conn.exec_driver_sql(
            "INSERT INTO durable VALUES (7, 'private-canary', X'0102')"
        )
        initial = probe.durable_snapshot(conn)
        assert initial["durable"]["count"] == 1
        assert "private-canary" not in str(initial)
        for statement in [
            "UPDATE durable SET identity=8",
            "UPDATE durable SET payload='changed'",
            "UPDATE durable SET content=X'0304'",
            "CREATE TABLE extra (id int)",
        ]:
            conn.exec_driver_sql(statement)
            current = probe.durable_snapshot(conn)
            assert current != initial
            initial = current
    engine.dispose()


def test_negative_restore_does_not_accept_a_success_exit():
    module = load("scripts/smoke_backup_restore.py")
    with pytest.raises(AssertionError):
        module.must_fail(lambda: None)


def test_negative_restore_accepts_only_backup_errors(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    module = load("scripts/smoke_backup_restore.py")
    from backup_compose import BackupError

    def rejected():
        raise BackupError("expected")

    module.must_fail(rejected)

    def interrupted():
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        module.must_fail(interrupted)


def test_reset_refuses_unowned_or_media_volume_before_docker(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    module = load("scripts/smoke_backup_restore.py")
    for volume in [
        "other_mysql_data",
        "daesingo-rt13-smoke-0123456789ab_media",
        "../../shared",
    ]:
        with pytest.raises(ValueError):
            module.reset_owned_database(
                "daesingo-rt13-smoke-0123456789ab",
                volume,
                lambda *a, **k: pytest.fail("must not touch Docker"),
                lambda *a, **k: None,
            )


def binary_runner(run):
    # Exercise the actual nested adapter without starting its Docker scenario.
    path = ROOT / "scripts/smoke_backup_restore.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "binary_run"
    )
    from smoke_compose import assert_no_secrets

    namespace = {
        "subprocess": SimpleNamespace(run=run),
        "ROOT": ROOT,
        "context": {"env": {}, "secrets": ["private-canary"]},
        "assert_no_secrets": assert_no_secrets,
    }
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace
    )
    return namespace["binary_run"]


def test_actual_smoke_adapter_accepts_file_transport_without_recapture(tmp_path):
    def run(command, **kwargs):
        assert "capture_output" not in kwargs and "input" not in kwargs
        assert kwargs["stderr"] == subprocess.DEVNULL
        kwargs["stdout"].write(b"synthetic SQL")
        return subprocess.CompletedProcess(command, 0, stdout=None, stderr=None)

    with (tmp_path / "sql").open("w+b") as output:
        result = binary_runner(run)(
            ["fake-only"], stdout=output, stderr=subprocess.DEVNULL, timeout=600
        )
        assert (
            result.returncode == 0 and result.stdout is None and result.stderr is None
        )
        output.seek(0)
        assert output.read(1024 * 1024) == b"synthetic SQL"


@pytest.mark.parametrize("field", ["stdout", "stderr"])
def test_actual_smoke_adapter_keeps_captured_secret_guard(field):
    def run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            **{
                field: b"private-canary",
                "stderr" if field == "stdout" else "stdout": b"",
            },
        )

    with pytest.raises(ValueError, match="secret_disclosure"):
        binary_runner(run)(["fake-only"], capture_output=True, timeout=600)
