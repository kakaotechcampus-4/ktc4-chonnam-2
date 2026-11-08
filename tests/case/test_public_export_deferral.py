"""Admission may defer automatic exports without undoing an accepted correction."""
from copy import deepcopy

import pytest

from daesingo.case import command, exports, jobs
from test_input_commands import _store


@pytest.mark.parametrize("accepted", [False, True])
def test_correction_survives_local_export_admission_decision(monkeypatch, accepted):
    store, cid = _store()
    original = deepcopy(store.get_case(cid).job_records)
    rev = store.get_case(cid).case_rev
    seen = []
    def automatic(case, adapter, view):
        jobs.issue_job(case, "REPORT_VIDEO_EXPORT", input_fingerprint="TEST_ONLY_EXPORT",
            export_input={"incident_clip_ref": "clip", "post_stamp": {"needed": False, "value": None}})
    monkeypatch.setattr(exports, "issue_missing_exports", automatic)
    def admit(records):
        seen.extend(records)
        return accepted
    result = command.execute_command({"case_id": cid, "expected_case_rev": rev,
        "kind": "MANUAL_PLATE_INPUT", "payload": {"value": "34나5678"}}, store=store, admit_auto_exports=admit)
    assert result.response["ok"] is True
    assert result.response["case_view"]["evidence"]["plate_display"]["value"] == "34나5678"
    # #597 B안: happy_001은 Fine OBSERVED라 상황 응답 없이 evidence가 조립되고, mock adapter에
    # 묶음 자산이 이미 있어 같은 command 안에서 READY로 넘어간다(정정 +1, READY 전이 +1).
    assert store.get_case(cid).stage == "READY"
    assert store.get_case(cid).case_rev == rev + 2
    assert len(store.get_case(cid).correction_records) == 1
    assert [record["kind"] for record in seen] == ["REPORT_VIDEO_EXPORT"]
    if accepted:
        assert len(result.appended_job_records) == 1
    else:
        assert result.appended_job_records == []
        assert store.get_case(cid).job_records == original


@pytest.mark.parametrize('running', [False, True])
def test_first_deferred_export_has_visible_action_only_without_running_export(monkeypatch, running):
    from types import SimpleNamespace
    from daesingo.case import service
    from daesingo.case.domain import CaseAggregate
    from test_report_video_notice import _responded_view_without_video
    view = _responded_view_without_video()
    if running:
        view['running_jobs'] = [{'kind': 'REPORT_VIDEO_EXPORT'}]
    monkeypatch.setattr(service, '_inputs_for', lambda *a: service.AdapterSnapshot(None, None, None, None))
    monkeypatch.setattr(service, 'build_case_view', lambda *a, **kw: deepcopy(view))
    case = CaseAggregate.empty('first-order')
    adapter = SimpleNamespace(get_export_requests=lambda: {'REPORT_VIDEO_EXPORT': {'incident_clip_ref': 'clip'}})
    result = service.build_view_from_adapter(case, adapter)
    notice = next(n for n in result['notices'] if n['code'] == 'case.report_video_not_generated')
    assert notice['actions'] == ([] if running else ['GENERATE_REPORT_VIDEO'])
