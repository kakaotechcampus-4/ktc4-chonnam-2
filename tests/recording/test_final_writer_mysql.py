"""Real production composition repositories write with no format overrides.

Only Case/provider/encoding boundaries are replaced. The actual API/Worker
repository constructors, transaction facades and MySQL writes remain real.
This checks composition defaults, not the complete HTTP or handler pipeline.
"""
import json
from types import SimpleNamespace

import pytest

from daesingo.recording.mysql_repository import MySQLRecordingRepository, _key
from daesingo.recording.prepared_metadata import decode_prepared_payload
from test_prepared_metadata_mysql import db as _db, media
from test_ownership_reads import MP4

pytestmark = pytest.mark.mysql
db = _db


class _CapturedRepository(Exception):
    """Stop before encoding/provider work after the real repository wrote."""


@pytest.mark.parametrize('entrypoint,metadata_only', [
    pytest.param(path, flag, marks=pytest.mark.mysql_check(
        'recording', 'compatible_release',
        parameter='default_' + path + '_' + ('metadata' if flag else 'content')))
    for path in ('api', 'worker_analysis', 'worker_incident') for flag in (False, True)
])
def test_production_composition_defaults_write_chunked_envelopes(db, monkeypatch, entrypoint, metadata_only):
    engine, root = db
    items = {kind: media(kind) for kind in ('analysis_source', 'incident_clip')}
    published = []

    def publish(repository):
        for kind, item in items.items():
            if metadata_only:
                getattr(repository, 'add_' + kind)(item)
            else:
                repository.add_prepared_media(item, MP4, case_id='c-default')
        published.append(repository)

    def transaction(callback):
        with engine.begin() as conn:
            return callback(conn)

    if entrypoint == 'api':
        from daesingo.api import composition

        def command(payload, *, store, timelines, admit_auto_exports=None):
            # execute_command itself constructs RecordingService and its
            # ConnectionRecordingRepository; no injected Recording override.
            assert admit_auto_exports is None  # This composition is internal.
            publish(timelines._recording._repository)
            return SimpleNamespace(cancelled_job_ids=(), appended_job_records=())

        monkeypatch.setattr(composition.case_api, 'execute_command', command)
        monkeypatch.setattr(composition.ApiComposition, '_store', lambda self, conn: None)
        api = composition.ApiComposition(
            startup=SimpleNamespace(config=SimpleNamespace(media_root=root)),
            engine=engine, ready_engine=engine, readiness=SimpleNamespace(),
        )
        api.execute_command({}, 'trace-c-default')
    else:
        from daesingo.worker import production_media, incident_clip_composition

        def capture(repository, *args, **kwargs):
            publish(repository)
            raise _CapturedRepository()

        if entrypoint == 'worker_analysis':
            monkeypatch.setattr(production_media, 'build_recording_service', capture)
            factory = production_media.ProductionMediaFactory(
                transaction=transaction, storage_root=root, temp_root=root,
                settings=SimpleNamespace(), search_settings=SimpleNamespace(),
            )
        else:
            monkeypatch.setattr(incident_clip_composition, 'build_incident_recording_service', capture)
            factory = incident_clip_composition.IncidentRecordingFactory(
                transaction=transaction, storage_root=root, temp_root=root, settings=SimpleNamespace(),
            )
        with pytest.raises(_CapturedRepository):
            with factory(SimpleNamespace(case_id='c-default', checkpoint=lambda: None)):
                pytest.fail('provider/encoding boundary must not execute')

    assert len(published) == 1
    with engine.connect() as conn:
        reader = MySQLRecordingRepository(conn, storage_root=root)
        for kind, item in items.items():
            ref = getattr(item, kind + '_ref')
            payload, blob = conn.exec_driver_sql(
                'SELECT payload,content FROM recording_entry WHERE kind=%s AND entry_key=%s',
                (kind, _key(ref)),
            ).one()
            value = json.loads(payload)
            assert set(value) == {'__recording_prepared_metadata__'}
            assert decode_prepared_payload(value) == item.model_dump(mode='json')
            assert blob is None
            count = conn.exec_driver_sql(
                'SELECT COUNT(*) FROM recording_media_chunk WHERE kind=%s AND entry_key=%s',
                (kind, _key(ref)),
            ).scalar_one()
            assert (count == 0) if metadata_only else (count > 0)
            assert getattr(reader, 'get_' + kind)(ref) == item
            if not metadata_only:
                from daesingo.recording import ContractRef
                assert reader.get_prepared_content(ContractRef(kind=kind, ref=ref)) == (MP4, 'video/mp4')
