"""Admission may defer automatic exports without undoing an accepted correction."""
from copy import deepcopy

import pytest

from daesingo.case import command, exports, jobs, service
from test_input_commands import _store


@pytest.mark.parametrize("accepted", [False, True])
@pytest.mark.parametrize("package_ready", [False, True], ids=["no-package", "existing-package"])
def test_correction_survives_local_export_admission_decision(monkeypatch, accepted, package_ready):
    store, cid = _store()
    original = store.get_case(cid)
    assert original.stage == "EVIDENCE_REVIEW"
    assert original.settled_jobs  # The existing Coarse completion is not an empty fixture.
    if not package_ready:
        # Explicitly test a missing Package, rather than relying on the old
        # requirement that OBSERVED results also need a situation response (#618).
        monkeypatch.setattr(store.adapter_for(original), "get_report_package", lambda: None)
    before = service.get_view(cid, store=store)
    assert (before["package"] is not None) == package_ready
    rev = original.case_rev
    seen = []
    def automatic(case, adapter, view):
        jobs.issue_job(case, "REPORT_VIDEO_EXPORT", input_fingerprint="TEST_ONLY_EXPORT",
            export_input={"incident_clip_ref": "clip", "post_stamp": {"needed": False, "value": None}})
    monkeypatch.setattr(exports, "issue_missing_exports", automatic)
    def admit(records):
        seen.extend(records)
        return accepted
    request = {"case_id": cid, "expected_case_rev": rev,
        "kind": "MANUAL_PLATE_INPUT", "payload": {"value": "34나5678"}}
    result = command.execute_command(request, store=store, admit_auto_exports=admit)
    assert result.response["ok"] is True
    assert result.response["case_view"]["evidence"]["plate_display"]["value"] == "34나5678"
    saved = store.get_case(cid)
    # Contract §5: one correction revision, plus one only for a real READY
    # transition. Admission rejection must not undo either accepted effect.
    expected_stage = "READY" if package_ready else "EVIDENCE_REVIEW"
    assert saved.stage == result.response["case_view"]["stage"] == expected_stage
    assert saved.case_rev == result.response["case_view"]["case_rev"] == rev + 1 + int(package_ready)
    assert len(saved.correction_records) == 1
    assert saved.correction_records[0]["new_value"] == "34나5678"
    assert saved.settled_jobs == original.settled_jobs
    assert [record["kind"] for record in seen] == ["REPORT_VIDEO_EXPORT"]
    if accepted:
        assert len(result.appended_job_records) == 1
        assert saved.job_records == original.job_records + result.appended_job_records
        export_id = result.appended_job_records[0]["job_id"]
        assert saved.export_inputs == {**original.export_inputs, export_id: {
            "incident_clip_ref": "clip", "post_stamp": {"needed": False, "value": None}}}
    else:
        assert result.appended_job_records == []
        assert saved.job_records == original.job_records
        assert saved.export_inputs == original.export_inputs  # No orphan input from refused automatic work.
    if package_ready:
        assert result.response["case_view"]["package"]["artifact_ref"] == before["package"]["artifact_ref"]
    else:
        assert result.response["case_view"]["package"] is None
    # A transport redelivery cannot save a second correction or issue another export.
    replay = command.execute_command(request, store=store, admit_auto_exports=admit)
    assert replay.response["error"]["code"] == "case.command.stale_revision"
    assert replay.appended_job_records == []
    assert store.get_case(cid) == saved
    assert len(seen) == 1


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
