import importlib.util
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects.mysql import dialect

from a1_support import sqlite_engine
from daesingo.common.public_runtime import schema


def test_frozen_migration_matches_live_mysql_ddl_and_always_starts_closed(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[3]
    path = root / "migrations/runtime/versions/0007_public_admission.py"
    spec = importlib.util.spec_from_file_location("public_migration_frozen", path)
    frozen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(frozen)
    assert frozen.revision == "runtime_0007" and frozen.down_revision == "runtime_0006"
    assert set(frozen.metadata.tables) == set(schema.metadata.tables)
    for name, live in schema.metadata.tables.items():
        assert str(CreateTable(live).compile(dialect=dialect())) == str(CreateTable(frozen.metadata.tables[name]).compile(dialect=dialect()))
    # MySQL3818 forbids CHECK(id=1) on an AUTO_INCREMENT primary key.
    assert "AUTO_INCREMENT" not in str(CreateTable(schema.control).compile(dialect=dialect()))
    engine = sqlite_engine(tmp_path / "migration.sqlite")
    with engine.begin() as conn:
        monkeypatch.setattr(frozen.op, "get_bind", lambda: conn)
        monkeypatch.setattr(frozen.op, "execute", conn.execute)
        frozen.upgrade()
        assert conn.execute(sa.select(schema.control.c.accepting)).scalar_one() is False
        assert conn.execute(sa.select(schema.control.c.policy_hash)).scalar_one() is None
    engine.dispose()
