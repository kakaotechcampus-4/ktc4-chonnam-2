"""Explicit synthetic public-policy facts; none are operational approvals."""
from pathlib import Path
import sqlalchemy as sa


def policy_values(root: Path, **changes):
    return {"approval_ref": "TEST_ONLY_NOT_AUTHORIZED", "release_revision": "1" * 40,
        "origin": "https://testserver", "session_key": "test-secret-" * 4,
        "manifest_file": str(root / "manifest.json"), "manifest_sha256": "0" * 64,
        "samples_root": str(root / "official"), "max_input_bytes": 10000,
        "session_ttl_sec": 3600, "case_ttl_sec": 3600, "source_ttl_sec": 1800,
        "session_daily": 3, "ip_daily": 10, "case_repeats": 2,
        "session_concurrent": 1, "global_concurrent": 2,
        "case_budget_micros": 50, "daily_budget_micros": 100, "total_budget_micros": 200,
        "bounds": [{"operation": "SEARCH_COARSE", "provider_label": "fake:test",
                    "reserve_micros": 10, "evidence_ref": "TEST_FIXED_CALL_CEILING"}], **changes}


def sqlite_engine(path):
    # SQLite tests serialize callbacks explicitly. This is not proof of InnoDB locking.
    engine = sa.create_engine("sqlite+pysqlite:///" + str(path),
                             connect_args={"check_same_thread": False}, hide_parameters=True)
    @sa.event.listens_for(engine, "connect")
    def connect(dbapi, record):
        dbapi.isolation_level = None
    @sa.event.listens_for(engine, "begin")
    def begin(conn):
        conn.exec_driver_sql("BEGIN IMMEDIATE")
    return engine
