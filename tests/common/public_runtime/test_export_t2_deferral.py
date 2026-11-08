"""Real Case + SQL persistence focused regression; SQLite is not InnoDB evidence."""
import pytest
import sqlalchemy as sa
from a1_support import sqlite_engine
from public_export_t2_support import scenario
from daesingo.case.store_mysql import metadata as case_metadata
from daesingo.common.jobs.schema import job_execution
from daesingo.common.public_runtime.schema import metadata as public_metadata
from daesingo.common.public_runtime.schema import control
from daesingo.common.usage.schema import usage_record


@pytest.mark.parametrize('mode', ['capacity', 'repeat', 'stop'])
def test_completed_exports_survive_refused_automatic_followup(tmp_path, monkeypatch, mode):
    engine = sqlite_engine(tmp_path / 't2.sqlite')
    @sa.event.listens_for(engine, 'connect')
    def configure(dbapi, _):
        dbapi.create_collation('ascii_bin', lambda a, b: (a > b) - (a < b))
    try:
        for meta in (case_metadata, public_metadata):
            meta.create_all(engine)
        job_execution.create(engine)
        usage_record.create(engine)
        with engine.begin() as conn:
            conn.exec_driver_sql('CREATE TABLE usage_inflight (case_id TEXT, observed_at DATETIME)')
            conn.execute(control.insert().values(id=1, accepting=False))
        scenario(engine, tmp_path, monkeypatch, mode)
    finally:
        engine.dispose()
