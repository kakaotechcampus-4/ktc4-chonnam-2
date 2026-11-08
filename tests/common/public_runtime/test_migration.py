import importlib.util
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects.mysql import dialect
from alembic.migration import MigrationContext
from alembic.operations import Operations

from a1_support import sqlite_engine
from daesingo.common.public_runtime import schema


def test_frozen_migration_matches_live_mysql_ddl_and_always_starts_closed(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[3]
    path = root / "migrations/runtime/versions/0007_public_admission.py"
    spec = importlib.util.spec_from_file_location("public_migration_frozen", path)
    frozen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(frozen)
    assert frozen.revision == "runtime_0007" and frozen.down_revision == "runtime_0006"
    # MySQL3818 forbids CHECK(id=1) on an AUTO_INCREMENT primary key.
    assert "AUTO_INCREMENT" not in str(CreateTable(schema.control).compile(dialect=dialect()))
    engine = sqlite_engine(tmp_path / "migration.sqlite")
    with engine.begin() as conn:
        monkeypatch.setattr(frozen.op, "get_bind", lambda: conn)
        monkeypatch.setattr(frozen.op, "execute", conn.execute)
        frozen.upgrade()
        assert conn.execute(sa.select(schema.control.c.accepting)).scalar_one() is False
        assert conn.execute(sa.select(schema.control.c.policy_hash)).scalar_one() is None
        from datetime import datetime
        retained = {"usage_id": "TEST_RETAINED", "execution_ref": "TEST_EXEC", "case_id": "TEST_CASE",
                    "operation": "TEST_OPERATION", "provider_label": "TEST_PROVIDER", "amount_micros": 123,
                    "created_at": datetime(2026, 11, 8)}
        conn.execute(schema.reservations.insert().values(**retained))
        path8 = root / "migrations/runtime/versions/0008_local_work.py"
        spec8 = importlib.util.spec_from_file_location("public_local_migration_frozen", path8)
        frozen8 = importlib.util.module_from_spec(spec8)
        spec8.loader.exec_module(frozen8)
        assert frozen8.revision == "runtime_0008" and frozen8.down_revision == "runtime_0007"
        monkeypatch.setattr(frozen8, "op", Operations(MigrationContext.configure(conn)))
        frozen8.upgrade()
        combined = sa.MetaData()
        for table in frozen.metadata.tables.values():
            table.to_metadata(combined)
        combined.tables["public_control"].append_column(sa.Column("jobs_stopped", sa.Boolean, nullable=False, server_default=sa.true()))
        combined.tables["public_case"].append_column(sa.Column("local_work_state", sa.JSON))
        frozen8.local_admissions.to_metadata(combined)
        assert set(combined.tables) == set(schema.metadata.tables)
        for name, live in schema.metadata.tables.items():
            assert str(CreateTable(live).compile(dialect=dialect())) == str(CreateTable(combined.tables[name]).compile(dialect=dialect()))
        assert conn.execute(sa.select(schema.control.c.jobs_stopped)).scalar_one() is True
        assert conn.execute(sa.select(schema.control.c.accepting)).scalar_one() is False
        record = dict(conn.execute(sa.select(schema.reservations)).mappings().one())
        assert all(record[key] == value for key, value in retained.items())
    engine.dispose()
