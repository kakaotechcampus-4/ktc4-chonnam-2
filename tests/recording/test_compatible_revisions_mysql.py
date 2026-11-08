"""Pinned e50 -> pinned B -> current C -> pinned B on one disposable test DB."""
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from test_prepared_metadata_mysql import media, snapshot
from test_ownership_reads import MP4
from daesingo.recording.mysql_repository import _key

pytestmark = pytest.mark.mysql
ROOT = Path(__file__).parents[2]
REVISIONS = {'e50': 'e50b2976ef4edc3a030cfc5b03a5206340dd917b',
             'bridge': 'ce0750d5a3317ad1c810783d67f8a05ba88bce08',
             'preview_source': '70f1c47cbc7c08fa848d057687f7130047f1126c',
             'preview_bridge': 'b915808898077509e6f499b7be197310e5045b7a',
             'preview_final': 'bb29d750d23765a73b7b6853b22086648684a392'}


@pytest.fixture(scope='session')
def releases(tmp_path_factory):
    roots = {'final': ROOT}
    prepared = os.environ.get('DAESINGO_COMPAT_SNAPSHOT_ROOT')
    for name, sha in REVISIONS.items():
        if prepared:
            target = Path(prepared) / name
            manifest = json.loads((target / 'identity.json').read_text())
            assert manifest['revision'] == sha
            import hashlib
            for member, digest in manifest['files'].items():
                path = (target / member).resolve()
                assert path.is_relative_to(target.resolve())
                assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        else:
            archive = subprocess.run(['git', '-c', f'safe.directory={ROOT}', 'archive', '--format=zip', sha, 'src', 'migrations'],
                                     cwd=ROOT, check=True, capture_output=True).stdout
            target = tmp_path_factory.mktemp(name)
            with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
                for member in zipped.infolist():
                    assert (target / member.filename).resolve().is_relative_to(target.resolve())
                zipped.extractall(target)
        roots[name] = target
    return roots


def invoke(releases, release, url, root, action, **values):
    env = {**os.environ, 'PYTHONPATH': str(releases[release] / 'src')}
    env.pop('DAESINGO_ENV_FILE', None)
    payload = {'url': url.render_as_string(hide_password=False), 'media_root': str(root),
               'source_root': str(releases[release]), 'action': action, **values}
    result = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('compatibility_revision_driver.py'))],
                            input=json.dumps(payload), text=True, capture_output=True, env=env, timeout=60)
    response = json.loads(result.stdout)
    if response['ok']:
        assert result.returncode == 0
    return response


@pytest.mark.parametrize('kind', [pytest.param(kind, marks=pytest.mark.mysql_check(
    'recording', 'compatible_release', parameter='revision_'+kind))
    for kind in ('analysis_source', 'incident_clip')])
def test_actual_revisions_preserve_media_and_schema(mysql_engine, tmp_path, releases, kind):
    url, root = mysql_engine.url, tmp_path
    assert invoke(releases, 'e50', url, root, 'migrate')['ok']
    with mysql_engine.connect() as conn:
        assert conn.exec_driver_sql('SELECT version_num FROM recording_alembic_version').scalar_one() == 'recording_0001'
    item = media(kind, 100.25)
    args = {'kind': kind, 'media': item.model_dump(mode='json'), 'content': base64.b64encode(MP4).decode()}
    assert invoke(releases, 'e50', url, root, 'write', **args)['ok']
    assert invoke(releases, 'bridge', url, root, 'migrate')['ok']
    with mysql_engine.connect() as conn:
        assert conn.exec_driver_sql('SELECT version_num FROM recording_alembic_version').scalar_one() == 'recording_0002'
    assert invoke(releases, 'final', url, root, 'migrate')['ok']
    for revision in ('bridge', 'final', 'bridge', 'e50'):
        result = invoke(releases, revision, url, root, 'read', **args)
        assert result['ok'], result
        assert result['result'] == {'media': args['media'], 'content': args['content']}
    # B's genuinely new registration remains readable by actual e50.
    ref_field = kind+'_ref'
    args['media'][ref_field] += '-b'
    assert invoke(releases, 'bridge', url, root, 'write', **args)['ok']
    assert invoke(releases, 'e50', url, root, 'read', **args)['result']['content'] == args['content']
    with mysql_engine.connect() as conn:
        raw, blob = conn.exec_driver_sql(
            'SELECT payload,content FROM recording_entry WHERE kind=%s AND entry_key=%s',
            (kind, _key(args['media'][ref_field])),
        ).one()
        assert json.loads(raw) == args['media'] and blob == MP4
        before_legacy = snapshot(conn)
    # Current C must replay the real B row without converting its representation.
    assert invoke(releases, 'final', url, root, 'write', **args)['ok']
    assert invoke(releases, 'bridge', url, root, 'read', **args)['result']['content'] == args['content']
    with mysql_engine.connect() as conn:
        assert snapshot(conn) == before_legacy
    # Metadata-only B registration is a separate write path used by facades.
    args['media'][ref_field] += '-metadata'
    assert invoke(releases, 'bridge', url, root, 'write', metadata_only=True, **args)['ok']
    metadata = invoke(releases, 'e50', url, root, 'read', **args)
    assert metadata['ok'] and metadata['result'] == {'media': args['media'], 'content': None}
    with mysql_engine.connect() as conn:
        before_metadata = snapshot(conn)
    assert invoke(releases, 'final', url, root, 'write', metadata_only=True, **args)['ok']
    with mysql_engine.connect() as conn:
        assert snapshot(conn) == before_metadata
    # C creates a new exact-float envelope/chunk ref. B must never rewrite it.
    args['media'] = media(kind).model_dump(mode='json')
    args['media'][ref_field] += '-c'
    assert invoke(releases, 'final', url, root, 'write', metadata_only=True, **args)['ok']
    with mysql_engine.connect() as conn:
        raw = conn.exec_driver_sql(
            'SELECT payload FROM recording_entry WHERE kind=%s AND entry_key=%s',
            (kind, _key(args['media'][ref_field])),
        ).scalar_one()
        assert set(json.loads(raw)) == {'__recording_prepared_metadata__'}
        before_metadata = snapshot(conn)
    assert invoke(releases, 'bridge', url, root, 'read', **args)['result'] == {'media': args['media'], 'content': None}
    assert invoke(releases, 'bridge', url, root, 'write', metadata_only=True, **args)['ok']
    with mysql_engine.connect() as conn:
        assert snapshot(conn) == before_metadata
    assert invoke(releases, 'final', url, root, 'write', **args)['ok']
    with mysql_engine.connect() as conn:
        assert conn.exec_driver_sql(
            'SELECT content FROM recording_entry WHERE kind=%s AND entry_key=%s',
            (kind, _key(args['media'][ref_field])),
        ).scalar_one() is None
        assert conn.exec_driver_sql(
            'SELECT COUNT(*) FROM recording_media_chunk WHERE kind=%s AND entry_key=%s',
            (kind, _key(args['media'][ref_field])),
        ).scalar_one() > 0
        before = snapshot(conn)
    assert invoke(releases, 'bridge', url, root, 'write', metadata_only=True, **args)['ok']
    assert invoke(releases, 'bridge', url, root, 'write', **args)['ok']
    assert invoke(releases, 'bridge', url, root, 'read', **args)['result']['media'] == args['media']
    with mysql_engine.connect() as conn:
        assert snapshot(conn) == before
    incompatible = invoke(releases, 'e50', url, root, 'read', **args)
    assert not incompatible['ok'] and incompatible['error'] == 'ValidationError'


@pytest.mark.parametrize('origin,finisher,reflector,budget', [
    pytest.param('e50', 'bridge', 'final', 150, marks=pytest.mark.mysql_check('recording', 'compatible_release', parameter='job_e50_bridge_final')),
    pytest.param('bridge', 'e50', 'e50', 600, marks=pytest.mark.mysql_check('recording', 'compatible_release', parameter='job_bridge_e50_e50')),
    pytest.param('bridge', 'final', 'bridge', 600, marks=pytest.mark.mysql_check('recording', 'compatible_release', parameter='job_bridge_final_bridge')),
    pytest.param('final', 'bridge', 'bridge', 600, marks=pytest.mark.mysql_check('recording', 'compatible_release', parameter='job_final_bridge_bridge')),
])
def test_actual_revisions_job_t1_t2_and_receipt(mysql_engine, tmp_path, releases, origin, finisher, reflector, budget):
    url = mysql_engine.url
    assert invoke(releases, 'e50', url, tmp_path, 'migrate')['ok']
    case_id = 'case-transition'
    seeded = invoke(releases, origin, url, tmp_path, 'job_seed', case_id=case_id)
    assert seeded['ok'] and seeded['result']['budget'] == budget
    assert invoke(releases, 'bridge', url, tmp_path, 'migrate')['ok']
    assert invoke(releases, finisher, url, tmp_path, 'job_finish', case_id=case_id)['ok']
    applied = invoke(releases, reflector, url, tmp_path, 'job_reflect', case_id=case_id)
    assert applied['ok'] and applied['result']['reflection'] == 'APPLIED'
    replay = invoke(releases, 'bridge', url, tmp_path, 'job_reflect', case_id=case_id)
    assert replay['ok'] and replay['result']['reflection'] == 'ALREADY_APPLIED'
    loaded = invoke(releases, 'bridge', url, tmp_path, 'case_roundtrip', case_id=case_id)
    assert loaded['result'] == {'budget': budget, 'future_key': {'kept': [1, 2]},
                                'processed': 1, 'stage': 'CANDIDATE_REVIEW'}


@pytest.mark.mysql_check('candidate_video', 'compatible_bridge')
def test_actual_preview_writer_reader_bridge(mysql_engine, tmp_path, monkeypatch, releases):
    """Pinned 70f reads bridge data; pinned C emits; actual bridge processes and reuses."""
    import hashlib
    from daesingo.case import candidate_video
    from daesingo.common.db.migrate import upgrade_all
    from test_incident_clip_mysql import prepare
    from test_candidate_video_mysql import _client, _request, _run, _settle_evidence, _view
    assert candidate_video.PREVIEW_REQUESTS_ENABLED is False
    upgrade_all(mysql_engine.url)
    cid, root, _, startup = prepare(mysql_engine, tmp_path, monkeypatch,
                                    frame_candidates=3, coarse_frames=True)
    _settle_evidence(mysql_engine, startup, root, cid)
    env_file = str(tmp_path / 'peer.env')
    args = {'case_id': cid, 'env_file': env_file}

    def call(release, **options):
        response = invoke(releases, release, mysql_engine.url, root, 'preview_api', **args, **options)
        assert response['ok'], response
        return response['result']

    def state():
        with mysql_engine.connect() as conn:
            return (conn.exec_driver_sql('SELECT case_rev,CAST(state AS CHAR) FROM cases WHERE case_id=%s', (cid,)).one(),
                    conn.exec_driver_sql('SELECT execution_id,kind,status,case_applied_at FROM job_execution WHERE case_id=%s ORDER BY execution_id', (cid,)).all(),
                    conn.exec_driver_sql('SELECT * FROM usage_record ORDER BY usage_id').all())

    with _client(monkeypatch, tmp_path) as client:
        view = _view(client, cid)
        target = next(c['candidate_id'] for c in view['candidates'] if c['rank'] == 2)
        before = state()
        rejected = _request(client, cid, target)
        assert rejected.status_code == 409
        assert rejected.json()['error']['code'] == 'case.command.not_allowed'
        assert state() == before
        assert all(c['video_preview']['status'] == 'UNAVAILABLE' for c in view['candidates'])
    # Actual old source, not a test-mode flag: read new Coarse thumbs and existing chunked clip data.
    old = call('preview_source')
    assert old['status'] == 200
    assert [c['thumb_ref'] for c in old['body']['candidates']] == [c['thumb_ref'] for c in view['candidates']]
    assert any(c['thumb_ref'] for c in view['candidates'])
    # Exact immutable C uses its actual default API producer, no flag or mocked repository.
    emitted = call('preview_final', operation='request', candidate_id=target)
    assert emitted['writer_enabled'] is True and emitted['status'] == 202 and emitted['body']['ok']
    with mysql_engine.connect() as conn:
        rows = conn.exec_driver_sql('SELECT kind,status FROM job_execution WHERE case_id=%s AND kind=%s',
                                  (cid, 'CANDIDATE_VIDEO_PREVIEW')).all()
    assert rows == [('CANDIDATE_VIDEO_PREVIEW', 'QUEUED')]
    pending = state()
    reused = call('final', operation='request', candidate_id=target)
    assert reused['writer_enabled'] is False and reused['status'] == 200 and reused['body']['ok']
    assert state() == pending
    # Bridge's unchanged real default Worker builds/stores the clip and commits T1/T2.
    assert _run(mysql_engine, startup, root, {'CANDIDATE_VIDEO_PREVIEW'}, 1) == ['CANDIDATE_VIDEO_PREVIEW']
    assert candidate_video.PREVIEW_REQUESTS_ENABLED is False
    ready = call('final')
    card = next(c for c in ready['body']['candidates'] if c['candidate_id'] == target)
    assert card['video_preview']['status'] == 'READY'
    clip_ref = card['video_preview']['clip_ref']
    b_clip = call('final', operation='clip', clip_ref=clip_ref)
    c_clip = call('preview_final', operation='clip', clip_ref=clip_ref)
    assert b_clip == c_clip and b_clip['status'] == 200 and b_clip['bytes'] > 0
    with mysql_engine.connect() as conn:
        payload, content = conn.exec_driver_sql('SELECT payload,content FROM recording_entry WHERE kind=%s AND entry_key=%s',
                                               ('incident_clip', _key(clip_ref))).one()
        assert set(json.loads(payload)) == {'__recording_prepared_metadata__'} and content is None
        assert conn.exec_driver_sql('SELECT COUNT(*) FROM recording_media_chunk WHERE kind=%s AND entry_key=%s',
                                    ('incident_clip', _key(clip_ref))).scalar_one() > 0
        heads = {name: conn.exec_driver_sql('SELECT version_num FROM '+name+'_alembic_version').scalar_one()
                 for name in ('case', 'recording', 'runtime')}
    # The current source adds A-1 tables; old-reader data compatibility is
    # tested here, not old-image readiness/rollback approval at the new head.
    assert heads == {'case': 'case_0001', 'recording': 'recording_0002', 'runtime': 'runtime_0008'}
    before = state()
    redelivery = invoke(releases, 'final', mysql_engine.url, root, 'job_reflect',
                        case_id=cid, job_kind='CANDIDATE_VIDEO_PREVIEW')
    assert redelivery['ok'] and redelivery['result']['reflection'] == 'ALREADY_APPLIED'
    assert call('final', operation='request', candidate_id=target)['body']['ok']
    assert state() == before
    c_view = call('preview_final')['body']
    assert next(c for c in c_view['candidates'] if c['candidate_id'] == target)['video_preview'] == card['video_preview']
    assert hashlib.sha256((releases['preview_final']/'src/daesingo/case/candidate_video.py').read_bytes()).digest() != \
           hashlib.sha256((ROOT/'src/daesingo/case/candidate_video.py').read_bytes()).digest()
