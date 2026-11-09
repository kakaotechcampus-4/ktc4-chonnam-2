"""Actual intermediate release defaults; final-reader fixtures do not enable them."""
from copy import deepcopy

import pytest

from daesingo.case import candidate_video
from daesingo.case.view import build_case_view
from tests.case.test_candidate_video import request
from tests.case.test_observation_chain import _after_coarse, _reflect


def test_bridge_release_disables_new_preview_by_default(monkeypatch):
    monkeypatch.setenv('DAESINGO_PREVIEW_REQUESTS_ENABLED', 'true')
    assert getattr(candidate_video, 'PREVIEW_REQUESTS_ENABLED', True) is False
    store, cid, _, _ = _after_coarse()
    before = deepcopy(store.get_case(cid))
    result = request(store, cid, 'cand_2')
    assert result.response['error']['code'] == 'case.command.not_allowed'
    assert result.appended_job_records == []
    assert result.cancelled_job_ids == []
    assert store.get_case(cid) == before
    assert all(c['video_preview']['status'] == 'UNAVAILABLE'
               for c in build_case_view(store.get_case(cid))['candidates'])


def test_direct_request_cannot_issue_or_bump_in_bridge():
    store, cid, _, _ = _after_coarse()
    case = store.load_for_update(cid)
    before = deepcopy(case)
    with pytest.raises(ValueError, match='disabled'):
        candidate_video.request_preview(case, case.candidates[1])
    assert case == before


def test_public_preview_request_scope_enables_only_the_active_request():
    store, cid, _, _ = _after_coarse()
    token = candidate_video.public_preview_requests.set(True)
    try:
        assert request(store, cid, "cand_2").appended_job_records[0]["kind"] == "CANDIDATE_VIDEO_PREVIEW"
    finally:
        candidate_video.public_preview_requests.reset(token)
    assert not request(store, cid, "cand_1").appended_job_records


@pytest.mark.parametrize('status', ['PENDING', 'SUCCEEDED', 'FAILED'])
def test_bridge_reads_existing_final_preview_without_creating_new_jobs(monkeypatch, status):
    store, cid, _, _ = _after_coarse()
    # Synthetic persisted C data; production default remains disabled outside this scope.
    with monkeypatch.context() as seed:
        seed.setattr(candidate_video, 'PREVIEW_REQUESTS_ENABLED', True, raising=False)
        job = request(store, cid, 'cand_2').appended_job_records[0]
    if status != 'PENDING':
        _reflect(store, cid, job, {'incident_clip_ref': 'existing-clip'} if status == 'SUCCEEDED' else None,
                 status=status)
    before = deepcopy(store.get_case(cid))
    view = build_case_view(before)
    card = view['candidates'][1]['video_preview']
    assert card['status'] == {'PENDING': 'PREPARING', 'SUCCEEDED': 'READY', 'FAILED': 'FAILED'}[status]
    assert card['clip_ref'] == ('existing-clip' if status == 'SUCCEEDED' else None)
    result = request(store, cid, 'cand_2')
    assert result.appended_job_records == []
    assert result.response['ok'] is (status != 'FAILED')
    assert store.get_case(cid) == before
    assert getattr(candidate_video, 'PREVIEW_REQUESTS_ENABLED', True) is False
