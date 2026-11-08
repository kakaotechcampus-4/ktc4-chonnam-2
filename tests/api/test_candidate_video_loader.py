from io import BytesIO
from types import SimpleNamespace

import pytest

from tests.preview_writer_fixture import final_preview_writer  # noqa: F401

from daesingo.api.composition import ApiComposition, compose_api
from daesingo.recording import OpenedAnalysisSource, RecordingCapabilityError
from tests.case.test_candidate_video import request
from tests.case.test_observation_chain import _after_coarse, _reflect


@pytest.fixture
def loader(api_startup, monkeypatch):
    from daesingo.api import composition as module
    store, cid, _, _ = _after_coarse()
    job = request(store, cid, 'cand_2').appended_job_records[0]
    _reflect(store, cid, job, {'incident_clip_ref': 'clip'})
    state = {'owns': True, 'missing': False, 'opened': [], 'transaction': False, 'reads': 0}
    class Recording:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def get_incident_clip(self, ref):
            state['reads'] += 1
            if state['missing']: raise RecordingCapabilityError('NOT_FOUND', 'private')
            return SimpleNamespace(source_provenance=SimpleNamespace(asset_spans=[SimpleNamespace(source_asset_ref='source')]))
        def owns_asset(self, case_id, ref):
            assert case_id == cid and ref.kind == 'source_asset' and ref.ref == 'source'
            return state['owns']
        def open_incident_video(self, ref):
            assert state['transaction'] and ref == 'clip'
            stream = BytesIO(b'video')
            state['opened'].append(stream)
            return OpenedAnalysisSource(stream, 'video/mp4', 5)
    def transaction(engine, callback):
        state['transaction'] = True
        try: return callback(store.conn)
        finally: state['transaction'] = False
    monkeypatch.setattr(module, 'run_api_transaction', transaction)
    monkeypatch.setattr(module, 'MySQLRecordingRepository', lambda *args, **kwargs: None)
    monkeypatch.setattr(module, 'RecordingService', lambda *args: Recording())
    monkeypatch.setattr(ApiComposition, '_store', lambda *args: store)
    composition = compose_api(api_startup[0])
    yield composition, store, cid, state
    composition.close()


def test_loader_returns_detached_bytes_and_closes_stream_inside_transaction(loader):
    composition, _, cid, state = loader
    for _ in range(2):
        assert composition.load_candidate_video(cid, 'clip') == (b'video', 'video/mp4')
        assert not state['transaction']
        assert all(s.closed for s in state['opened'])


def test_unknown_or_previous_generation_ref_is_denied_before_recording_read(loader):
    composition, store, cid, state = loader
    with pytest.raises(RecordingCapabilityError) as failure: composition.load_candidate_video(cid, 'foreign')
    assert failure.value.code == 'UNKNOWN_REF' and state['reads'] == 0
    case = store.load_for_update(cid)
    case.candidates[1].span['end_ms'] += 1
    store.save(case)
    with pytest.raises(RecordingCapabilityError) as failure: composition.load_candidate_video(cid, 'clip')
    assert failure.value.code == 'UNKNOWN_REF' and state['reads'] == 0


def test_foreign_source_is_denied_before_opening_bytes(loader):
    composition, _, cid, state = loader
    state['owns'] = False
    with pytest.raises(RecordingCapabilityError) as failure: composition.load_candidate_video(cid, 'clip')
    assert failure.value.code == 'UNKNOWN_REF' and state['opened'] == []


def test_current_ref_with_missing_recording_media_is_unavailable(loader):
    composition, _, cid, state = loader
    state['missing'] = True
    with pytest.raises(RecordingCapabilityError) as failure: composition.load_candidate_video(cid, 'clip')
    assert failure.value.code == 'UNAVAILABLE'
