"""B's real MySQL write/read/replay contract; never uses production data."""
import pytest
import sqlalchemy as sa

from daesingo.recording.mysql_repository import MySQLRecordingRepository, _key
from test_prepared_metadata_mysql import db as _db, media, snapshot
from test_ownership_reads import MP4, OTHER_MP4

pytestmark = pytest.mark.mysql
db = _db


def check(parameter):
    return pytest.mark.mysql_check('recording', 'compatible_release', parameter=parameter)


def repo(conn, root, **kwargs):
    return MySQLRecordingRepository(conn, storage_root=root, temp_root=root, **kwargs)


@pytest.mark.parametrize('kind,metadata_only', [
    pytest.param(kind, flag, marks=check('new_'+kind+'_'+('metadata' if flag else 'content')))
    for kind in ('analysis_source', 'incident_clip') for flag in (False, True)
])
def test_b_new_ref_is_e50_native_and_legacy(db, kind, metadata_only):
    engine, root = db
    item = media(kind, 100.25)
    ref = getattr(item, kind+'_ref')
    with engine.begin() as conn:
        repository = repo(conn, root)
        if metadata_only:
            getattr(repository, 'add_'+kind)(item)
        else:
            repository.add_prepared_media(item, MP4, case_id='owner')
    with engine.connect() as conn:
        payload, content = conn.exec_driver_sql(
            'SELECT payload,content FROM recording_entry WHERE kind=%s AND entry_key=%s',
            (kind, _key(ref)),
        ).one()
        import json
        assert json.loads(payload) == item.model_dump(mode='json')
        assert content == (None if metadata_only else MP4)
        assert conn.exec_driver_sql('SELECT COUNT(*) FROM recording_media_chunk').scalar_one() == 0
        assert getattr(repo(conn, root), 'get_'+kind)(ref) == item


@pytest.mark.parametrize('kind', [pytest.param(kind, marks=check('replay_'+kind))
                                for kind in ('analysis_source', 'incident_clip')])
def test_b_replay_c_preserves_envelope_chunks_and_exact_metadata(db, kind):
    engine, root = db
    item = media(kind)
    with engine.begin() as conn:
        repo(conn, root, prepared_write_format='chunked').add_prepared_media(item, MP4)
        before = snapshot(conn)
    with engine.begin() as conn:
        repository = repo(conn, root)
        getattr(repository, 'add_'+kind)(item)  # metadata-only replay
        repository.add_prepared_media(item, MP4)
        assert snapshot(conn) == before
        with pytest.raises(ValueError):
            repository.add_prepared_media(item, OTHER_MP4, case_id='bad-content')
        changed = item.model_copy(update={'profile_ref': 'changed'}) if kind == 'analysis_source' else item.model_copy(update={'duration_sec': 101.0})
        with pytest.raises(ValueError):
            repository.add_prepared_media(changed, MP4, case_id='bad-model')
        assert snapshot(conn) == before
    with engine.begin() as conn:
        ref = getattr(item, kind+'_ref')
        stream, _ = repo(conn, root).open_prepared_stream(__import__('daesingo.recording', fromlist=['ContractRef']).ContractRef(kind=kind, ref=ref))
    with stream:
        assert stream.read() == MP4


@pytest.mark.parametrize('metadata_only', [pytest.param(flag, marks=check('precision_'+('metadata' if flag else 'content')))
                                         for flag in (False, True)])
def test_b_native_precision_mismatch_leaves_no_registration(db, metadata_only):
    engine, root = db
    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO recording_entry(kind,entry_key,payload) VALUES('sentinel','s','{}')")
        with pytest.raises(ValueError, match='immutable identity'):
            repository = repo(conn, root)
            item = media('analysis_source')
            if metadata_only:
                repository.add_analysis_source(item)
            else:
                repository.add_prepared_media(item, MP4, case_id='failed')
    with engine.connect() as conn:
        assert conn.exec_driver_sql('SELECT kind FROM recording_entry').scalars().all() == ['sentinel']
        assert conn.exec_driver_sql('SELECT COUNT(*) FROM recording_media_chunk').scalar_one() == 0


@check('atomic_link')
def test_b_case_link_failure_does_not_leak_blob_after_caller_commit(db):
    engine, root = db
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TRIGGER reject_b_link BEFORE INSERT ON recording_entry FOR EACH ROW BEGIN IF NEW.kind='case_asset' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='rejected'; END IF; END")
    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO recording_entry(kind,entry_key,payload) VALUES('sentinel','s','{}')")
        with pytest.raises(sa.exc.DBAPIError):
            repo(conn, root).add_prepared_media(media('analysis_source', 100.25), MP4, case_id='rejected')
    with engine.connect() as conn:
        assert conn.exec_driver_sql('SELECT kind FROM recording_entry').scalars().all() == ['sentinel']


@check('packet')
def test_b_packet_guard_refuses_before_send_and_preserves_connection(db):
    from test_ownership_reads import padded_mp4
    engine, root = db
    content = padded_mp4(800000)
    item = media('analysis_source', 100.25).model_copy(update={'byte_size': len(content)})
    with engine.begin() as conn:
        identity = conn.exec_driver_sql('SELECT CONNECTION_ID()').scalar_one()
        with pytest.raises(ValueError, match='command exceeds budget'):
            repo(conn, root, command_budget=64*1024).add_prepared_media(item, content, case_id='bad')
        assert conn.exec_driver_sql('SELECT CONNECTION_ID()').scalar_one() == identity
        assert conn.exec_driver_sql('SELECT COUNT(*) FROM recording_entry').scalar_one() == 0


@check('facade_rollback')
def test_b_production_facades_default_to_legacy_and_caller_rollback(db):
    from daesingo.recording import ConnectionRecordingRepository, TransactionalRecordingRepository
    engine, root = db
    item = media('analysis_source', 100.25)
    with engine.begin() as conn:
        ConnectionRecordingRepository(conn, storage_root=root).add_analysis_source(item)
    def transaction(callback):
        with engine.begin() as conn:
            return callback(conn)
    facade = TransactionalRecordingRepository(transaction, storage_root=root, temp_root=root)
    facade.add_prepared_media(item, MP4)
    with engine.connect() as conn:
        assert conn.exec_driver_sql('SELECT content FROM recording_entry WHERE kind="analysis_source"').scalar_one() == MP4
        before = snapshot(conn)
    with engine.connect() as conn:
        other = item.model_copy(update={'analysis_source_ref': 'rolled-back'})
        repo(conn, root).add_prepared_media(other, MP4)
        conn.rollback()
    with engine.connect() as conn:
        assert snapshot(conn) == before


@pytest.mark.parametrize('metadata_format', [pytest.param(value, marks=check('attach_'+value))
                                           for value in ('legacy', 'chunked')])
def test_b_attaches_content_without_rewriting_existing_metadata(db, metadata_format):
    engine, root = db
    item = media('analysis_source', 100.25)
    with engine.begin() as conn:
        repo(conn, root, prepared_write_format=metadata_format).add_analysis_source(item)
        before = conn.exec_driver_sql('SELECT CAST(payload AS CHAR) FROM recording_entry').scalar_one()
    with engine.begin() as conn:
        repo(conn, root).add_prepared_media(item, MP4)
        assert conn.exec_driver_sql('SELECT CAST(payload AS CHAR) FROM recording_entry WHERE kind="analysis_source"').scalar_one() == before
        assert conn.exec_driver_sql('SELECT content FROM recording_entry WHERE kind="analysis_source"').scalar_one() == MP4


@check('corrupt_replay')
def test_b_replay_corrupt_c_chunks_fails_without_new_case_link(db):
    engine, root = db
    item = media('analysis_source')
    with engine.begin() as conn:
        repo(conn, root, prepared_write_format='chunked').add_prepared_media(item, MP4)
        conn.exec_driver_sql("UPDATE recording_media_chunk SET content=CONCAT(content,'x') WHERE chunk_index=0")
        before = snapshot(conn)
    with engine.begin() as conn:
        with pytest.raises(ValueError):
            repo(conn, root).add_prepared_media(item, MP4, case_id='corrupt')
        assert snapshot(conn) == before


@pytest.mark.parametrize('storage_format', [pytest.param(value, marks=check('rr_current_'+value))
                                          for value in ('legacy', 'chunked', 'metadata')])
def test_b_replay_reads_current_chunks_after_repeatable_read_snapshot(db, storage_format):
    engine, root = db
    item = media('analysis_source', 100.25)
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as replay:
        # Pin an empty consistent snapshot before another writer publishes C.
        assert replay.exec_driver_sql('SELECT COUNT(*) FROM recording_entry').scalar_one() == 0
        with engine.begin() as writer:
            if storage_format == 'metadata':
                repo(writer, root, prepared_write_format='chunked').add_analysis_source(item)
            else:
                repo(writer, root, prepared_write_format=storage_format).add_prepared_media(item, MP4)
            before = snapshot(writer)
        # The repository's locking equality read promises current, not snapshot,
        # replay. Integrity reads must use the same view of the immutable ref.
        repo(replay, root).add_prepared_media(item, MP4, case_id='current')
        replay.commit()
    with engine.connect() as conn:
        assert len(repo(conn, root).get_case_assets('current')) == 1
        after = snapshot(conn)
        before_media, = [row for row in before[0] if row[0] == 'analysis_source']
        after_media, = [row for row in after[0] if row[0] == 'analysis_source']
        assert after_media[2] == before_media[2]  # Raw metadata representation.
        assert after[1] == before[1]  # Existing chunks are never rewritten.
        if storage_format != 'metadata':
            assert [row for row in after[0] if row[0] != 'case_asset'] == before[0]
        from daesingo.recording import ContractRef
        restored, content_type = repo(conn, root).get_prepared_content(
            ContractRef(kind='analysis_source', ref=item.analysis_source_ref))
        assert restored == MP4 and content_type == 'video/mp4'
