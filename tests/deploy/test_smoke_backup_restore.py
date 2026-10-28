import importlib.util
from pathlib import Path

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
        conn.exec_driver_sql("CREATE TABLE durable (identity int primary key, payload text, content blob)")
        conn.exec_driver_sql("INSERT INTO durable VALUES (7, 'private-canary', X'0102')")
        initial = probe.durable_snapshot(conn)
        assert initial["durable"]["count"] == 1
        assert "private-canary" not in str(initial)
        for statement in ["UPDATE durable SET identity=8", "UPDATE durable SET payload='changed'",
                          "UPDATE durable SET content=X'0304'", "CREATE TABLE extra (id int)"]:
            conn.exec_driver_sql(statement)
            current = probe.durable_snapshot(conn)
            assert current != initial
            initial = current
    engine.dispose()


def test_negative_restore_does_not_accept_a_success_exit():
    module = load("scripts/smoke_backup_restore.py")
    with pytest.raises(AssertionError): module.must_fail(lambda: None)


def test_negative_restore_accepts_only_backup_errors(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    module = load("scripts/smoke_backup_restore.py")
    from backup_compose import BackupError
    def rejected(): raise BackupError("expected")
    module.must_fail(rejected)
    def interrupted(): raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt): module.must_fail(interrupted)


def test_reset_refuses_unowned_or_media_volume_before_docker(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    module = load("scripts/smoke_backup_restore.py")
    for volume in ["other_mysql_data", "daesingo-rt13-smoke-0123456789ab_media", "../../shared"]:
        with pytest.raises(ValueError):
            module.reset_owned_database("daesingo-rt13-smoke-0123456789ab", volume,
                lambda *a, **k: pytest.fail("must not touch Docker"), lambda *a, **k: None)
