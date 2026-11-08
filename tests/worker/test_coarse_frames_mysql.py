"""Current Coarse issuance, real Recording/MySQL T1/T2, offline provider HTTP."""
import pytest
import sqlalchemy as sa

from daesingo.common.jobs.produced import produced_objects
from daesingo.common.jobs.schema import job_execution
from daesingo.recording.frames import FfmpegFrameExtractor
from daesingo.worker.case_composition import stored_case_store
from daesingo.worker.produced_reader import worker_produced_reader
from test_incident_clip_mysql import prepare
from test_worker_mysql import queue  # noqa: F401

pytestmark = pytest.mark.mysql


@pytest.mark.parametrize('fine', ['not_observed', 'failed'])
@pytest.mark.parametrize('fault', ['none', 't1_rollback'])
def test_coarse_frames_survive_fine_without_clip_and_t1_retry(queue, tmp_path, monkeypatch, fine, fault):  # noqa: F811
    from daesingo.case.view import build_case_view
    from daesingo.common import db
    decoded, injected = [], []
    worker_engines = []
    original = FfmpegFrameExtractor.extract
    def extract(self, *args):
        assert worker_engines and all(e.pool.checkedout() == 0 for e in worker_engines)
        decoded.append(True)
        return original(self, *args)
    monkeypatch.setattr(FfmpegFrameExtractor, 'extract', extract)
    def rollback(conn, cursor, sql, *args):
        if fault == 't1_rollback' and not injected and sql.upper().startswith('INSERT INTO PRODUCED_OBJECTS'):
            injected.append(True)
            raise sa.exc.OperationalError('test', {}, Exception(1213, 'deadlock'))
    actual_engine = db.create_worker_engine
    def engine(settings):
        value = actual_engine(settings)
        assert value.url.database == queue.url.database
        worker_engines.append(value)
        sa.event.listen(value, 'after_cursor_execute', rollback)
        return value
    monkeypatch.setattr(db, 'create_worker_engine', engine)
    try:
        case_id, root, _, _ = prepare(queue, tmp_path, monkeypatch, frame_candidates=4,
            coarse_frames=True, fine_scenario='fine_failed' if fine == 'failed' else 'success')
    finally:
        for value in worker_engines:
            sa.event.remove(value, 'after_cursor_execute', rollback)
    assert bool(injected) == (fault == 't1_rollback')
    assert len(decoded) == 3  # No repeated frame issuance inside the T1 retry.
    with queue.begin() as conn:
        rows = conn.execute(sa.select(job_execution)).mappings().all()
        coarse, = [r for r in rows if r['kind'] == 'COARSE_SEARCH']
        assert coarse['status'] == 'SUCCEEDED' and coarse['case_applied_at'] is not None
        payload = worker_produced_reader()(conn, coarse['kind'], tuple(coarse['produced']))
        refs = payload['candidate_frame_refs']
        assert len(refs) == 3 and all(refs.values())
        assert conn.scalar(sa.select(sa.func.count()).select_from(produced_objects).where(
            produced_objects.c.job_kind == 'COARSE_SEARCH')) == 1
        case = stored_case_store(conn, storage_root=root).get_case(case_id)
        view = build_case_view(case)
        assert {c['candidate_id']: c['thumb_ref'] for c in view['candidates'] if c['thumb_ref']} == refs
        assert len(view['candidates']) == 4 and view['candidates'][3]['thumb_ref'] is None
        fine_job, = [r for r in rows if r['kind'] == 'FINE_VERIFY']
        assert fine_job['case_applied_at'] is not None
        assert fine_job['status'] == ('FAILED' if fine == 'failed' else 'SUCCEEDED')
        if fine == 'not_observed':
            result = worker_produced_reader()(conn, fine_job['kind'], tuple(fine_job['produced']))
            assert result['visual_evidence']['verification'] == 'NOT_OBSERVED'
        assert not any(r['kind'] == 'INCIDENT_CLIP_BUILD' for r in rows)
    from fastapi.testclient import TestClient
    from daesingo.api.app import create_app
    from daesingo.api.bootstrap import bootstrap
    from io import StringIO
    def forbidden(*args, **kwargs):
        raise AssertionError('durable HTTP view decoded a frame')
    monkeypatch.setattr(FfmpegFrameExtractor, 'extract', forbidden)
    with TestClient(create_app(startup=bootstrap(revision='test', stream=StringIO()))) as client:
        other = client.post('/cases').json()['case_id']
        for ref in refs.values():
            response = client.get(f'/cases/{case_id}/frames/{ref}')
            assert response.status_code == 200 and response.content.startswith(b'\x89PNG\r\n\x1a\n')
            assert client.get(f'/cases/{other}/frames/{ref}').status_code == 404
        assert client.get(f'/cases/{case_id}/view').status_code == 200
    assert len(decoded) == 3 and queue.pool.checkedout() == 0
