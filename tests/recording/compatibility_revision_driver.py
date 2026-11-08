"""Test-only subprocess: imports exactly one release's real package from PYTHONPATH.

URL and synthetic fixtures arrive on stdin; no product env or external services.
"""
import base64
import json
from pathlib import Path
import sys

import sqlalchemy as sa

from daesingo.recording import models
from daesingo.recording.mysql_repository import MySQLRecordingRepository


def run(data):
    source = Path(sys.modules[MySQLRecordingRepository.__module__].__file__).resolve()
    assert source.is_relative_to(Path(data['source_root']).resolve())
    if data['action'] == 'preview_api':
        return preview_api(data)
    if data['action'] == 'migrate':
        from daesingo.common.db.migrate import upgrade_all
        upgrade_all(sa.engine.make_url(data['url']))
        return {'migrated': True}
    engine = sa.create_engine(data['url'], isolation_level='READ COMMITTED', hide_parameters=True)
    try:
        if data['action'].startswith('job_') or data['action'] == 'case_roundtrip':
            return jobs(engine, data)
        kind = data['kind']
        model = getattr(models, 'AnalysisSource' if kind == 'analysis_source' else 'IncidentClip')
        item = model.model_validate(data['media'])
        ref = getattr(item, kind+'_ref')
        with engine.begin() as conn:
            repository = MySQLRecordingRepository(conn, storage_root=data['media_root'])
            if data['action'] == 'write':
                if data.get('metadata_only'):
                    getattr(repository, 'add_'+kind)(item)
                else:
                    repository.add_prepared_media(item, base64.b64decode(data['content']))
            restored = getattr(repository, 'get_'+kind)(ref)
            result = {'media': None if restored is None else restored.model_dump(mode='json')}
            stored = repository.get_prepared_content(models.ContractRef(kind=kind, ref=ref))
            result['content'] = None if stored is None else base64.b64encode(stored[0]).decode()
            return result
    finally:
        engine.dispose()


def preview_api(data):
    """Use the exact release's real API composition and repository defaults."""
    import hashlib
    import os
    from io import StringIO
    from fastapi.testclient import TestClient
    from daesingo.api.app import create_app
    from daesingo.api.bootstrap import bootstrap
    os.environ['DAESINGO_ENV_FILE'] = data['env_file']
    with TestClient(create_app(startup=bootstrap(revision='compat-preview', stream=StringIO()))) as client:
        if data.get('operation') == 'health':
            return {'live': client.get('/health/live').status_code,
                    'ready': client.get('/health/ready').status_code}
        cid = data['case_id']
        view = client.get(f'/cases/{cid}/view')
        assert view.status_code == 200
        if data.get('operation') == 'request':
            response = client.post(f'/cases/{cid}/commands', json={
                'case_id': cid, 'expected_case_rev': view.json()['case_rev'],
                'kind': 'REQUEST_CANDIDATE_VIDEO_PREVIEW',
                'payload': {'candidate_id': data['candidate_id']}})
        elif data.get('operation') == 'clip':
            response = client.get(f"/cases/{cid}/candidate-videos/{data['clip_ref']}")
            return {'status': response.status_code, 'bytes': len(response.content),
                    'sha256': hashlib.sha256(response.content).hexdigest()}
        else:
            response = view
        module = sys.modules.get('daesingo.case.candidate_video')
        return {'status': response.status_code, 'body': response.json(),
                'writer_enabled': None if module is None else getattr(module, 'PREVIEW_REQUESTS_ENABLED', True)}


def jobs(engine, data):
    from daesingo.case.domain import CaseAggregate
    from daesingo.case.store_mysql import MySQLCaseRepository
    from daesingo.case.analysis_start import InitialSearchBudget, issue_initial_search
    from daesingo.case.timeline_source import CaseTimeline
    from daesingo.common.jobs.repository import enqueue, claim_one, finish
    from daesingo.common.jobs.produced import ProducedObject, ProducedReader, prepare_objects, append_objects
    from daesingo.common.jobs.reflection import ReflectionInput, reflect_terminal
    from daesingo.common.jobs.execution import HandlerResult
    from daesingo.worker.case_reflector import CaseReflector

    class Timeline:
        def timeline_for(self, sources):
            return CaseTimeline(timeline_id='tl-transition', revision=1, duration_ms=10_000)

    cases = MySQLCaseRepository()
    if data['action'] == 'job_seed':
        case = CaseAggregate.empty(data['case_id'])
        case.start_search()
        case.extra_state['future_key'] = {'kept': [1, 2]}
        job = issue_initial_search(case, timelines=Timeline(), budget=InitialSearchBudget())
        with engine.begin() as conn:
            cases.insert(conn, case)
            execution, = enqueue(conn, [job], 'trace-transition')
        return {'execution_id': execution, 'budget': case.analysis_scopes[job['scope_ref']]['budget']['max_latency_sec']}
    if data['action'] == 'job_finish':
        claimed = claim_one(engine, 'transition-worker')
        assert claimed is not None and claimed.case_id == data['case_id']
        obj = ProducedObject(kind='analysis_run', payload={'outcome': 'SUCCEEDED', 'candidate_events': []})
        prepared = prepare_objects(claimed.execution_id, (obj,))
        refs = [p.reference.model_dump() for p in prepared]
        with engine.begin() as conn:
            append_objects(conn, case_id=claimed.case_id, execution_id=claimed.execution_id,
                           job_kind=claimed.kind, objects=prepared)
            assert finish(conn, claimed.execution_id, 'transition-worker', status='SUCCEEDED', produced=refs) == 1
        return {'terminal': 'SUCCEEDED'}
    if data['action'] == 'job_reflect':
        with engine.begin() as conn:
            query = 'SELECT execution_id,job_id,kind,attempt,status,produced,trace_id FROM job_execution WHERE case_id=%s'
            values = (data['case_id'],)
            if data.get('job_kind'):
                query += ' AND kind=%s'
                values += (data['job_kind'],)
            row = conn.exec_driver_sql(query, values).mappings().one()
            terminal = HandlerResult(status=row['status'], produced=json.loads(row['produced']))
            incoming = ReflectionInput(row['execution_id'], row['job_id'], data['case_id'], row['kind'], row['attempt'], terminal)
            result = reflect_terminal(conn, incoming, CaseReflector(reader=ProducedReader(), timelines=Timeline()), row['trace_id'])
        return {'reflection': result.status}
    with engine.begin() as conn:
        case = cases.load(conn, data['case_id'], lock='update')
        if data['action'] == 'case_roundtrip':
            cases.save(conn, case)
        scope = next(iter(case.analysis_scopes.values()))
        return {'budget': scope['budget']['max_latency_sec'], 'future_key': case.extra_state['future_key'],
                'processed': len(case.processed_executions), 'stage': case.stage}


if __name__ == '__main__':
    try:
        print(json.dumps({'ok': True, 'result': run(json.load(sys.stdin))}))
    except Exception as error:
        print(json.dumps({'ok': False, 'error': type(error).__name__}))
        raise
