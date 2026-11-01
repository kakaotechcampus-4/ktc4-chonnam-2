"""Real INSERT/rollback boundary with small generated input and test-only budgets."""
import subprocess

import pytest
import sqlalchemy as sa

from daesingo.recording import AnalysisProfile, LocalAnalysisMaterializer, RecordingCapabilityError, RecordingService
from daesingo.recording.analysis_limits import AnalysisSourceLimits
from tests.recording.test_recording_repository_mysql import db, adapter
from tests.recording.test_local_analysis_source import fingerprint

pytestmark = pytest.mark.mysql


@pytest.mark.parametrize("mode", ["reject", "rollback", "commit"])
def test_analysis_limit_insert_and_caller_transaction(db, tmp_path, mode):
    engine, root = db
    path = root / "synthetic.avi"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "lavfi", "-i",
                    "color=c=blue:s=64x48:r=10:d=1", "-c:v", "mpeg4", str(path)],
                   check=True, capture_output=True, timeout=30)
    before = fingerprint(path)
    work = tmp_path / "work"
    work.mkdir()
    materializer = LocalAnalysisMaterializer({"test": AnalysisProfile(48, "veryfast", 23)}, temp_root=work)
    with engine.begin() as conn:
        with RecordingService(adapter(conn, root)) as seed:
            registered = seed.register_local_source(path, case_id="case-test")
            timeline = seed.create_relative_timeline(registered.source_asset.source_asset_ref)
            resolution = seed.resolve_span(dict(timeline_id=timeline.timeline_id, revision=timeline.revision),
                dict(start_sec=0, end_sec=1), media_stream_ref=registered.media_streams[0].media_stream_ref)
            span, = resolution.spans
            prepared = materializer.materialize(adapter(conn, root).get_local_source(span.source_asset_ref), 0, span, "test")
    inserts = []
    def observe(conn, cursor, statement, params, context, many):
        if statement.lstrip().upper().startswith("INSERT"):
            inserts.append(True)
    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        with engine.connect() as conn:
            aborted = conn.exec_driver_sql("SHOW GLOBAL STATUS LIKE 'Aborted_clients'").one()[1]
            with RecordingService(adapter(conn, root), analysis_materializer=materializer,
                    analysis_limits=AnalysisSourceLimits(len(prepared.content) - (mode == "reject"), 1000),
                    durable_prepared=True, case_id="case-test") as service:
                if mode == "reject":
                    with pytest.raises(RecordingCapabilityError) as caught:
                        service.prepare_analysis_source_from_resolution(resolution, "test")
                    assert caught.value.code == "ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED"
                    assert inserts == []
                    assert conn.exec_driver_sql("SHOW GLOBAL STATUS LIKE 'Aborted_clients'").one()[1] == aborted
                else:
                    source = service.prepare_analysis_source_from_resolution(resolution, "test")
                    assert inserts == [True]
                    assert service.open_analysis_source(source.analysis_source_ref).stream.read() == prepared.content
                assert conn.in_transaction() and conn.get_transaction().is_active
                if mode == "rollback":
                    conn.rollback()
                else:
                    conn.commit()
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT COUNT(*) FROM recording_entry WHERE kind='analysis_source'").scalar_one() == (mode == "commit")
            assert conn.exec_driver_sql("SELECT COUNT(*) FROM recording_entry WHERE kind='prepared_content'").scalar_one() == (mode == "commit")
            if mode == "commit":
                with RecordingService(adapter(conn, root)) as restarted:
                    with restarted.open_analysis_source(source.analysis_source_ref).stream as stream:
                        assert stream.read() == prepared.content
            else:
                assert [a for a in adapter(conn, root).get_case_assets("case-test") if a.kind == "analysis_source"] == []
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)
    assert fingerprint(path) == before and not list(work.iterdir())
