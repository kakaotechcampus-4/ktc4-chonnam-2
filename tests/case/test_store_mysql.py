"""MySQL 전용 — `DAESINGO_MYSQL_URL`이 있을 때만 돈다(`decisions/case-store-mysql.md` §8)."""

from __future__ import annotations

import pytest

sa = pytest.importorskip("sqlalchemy")


def test_migration_creates_case_tables_with_ascii_bin_ids(mysql_engine):
    with mysql_engine.connect() as conn:
        tables = {r[0] for r in conn.exec_driver_sql("SHOW TABLES")}
        assert {"cases", "job_records", "correction_records", "analysis_scopes", "case_alembic_version"} <= tables
        coll = conn.exec_driver_sql(
            "SELECT COLLATION_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'cases' AND COLUMN_NAME = 'case_id'"
        ).scalar_one()
        assert coll == "ascii_bin"
