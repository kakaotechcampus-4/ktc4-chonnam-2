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
    # #597/#616: happy_001 already has Package assets, so that branch stays
    # READY with +2 (correction +1, READY +1), even without a situation response.
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


def _resumable(monkeypatch):
    """보류된 자동 내보내기가 남은 `EVIDENCE_REVIEW` case — Package는 없어 READY gate는 열리지 않는다."""
    store, cid = _store()
    adapter = store.adapter_for(store.get_case(cid))
    monkeypatch.setattr(adapter, "get_report_package", lambda: None)
    # 반영 경로 gate는 내보내기 요청을 줄 수 있는 adapter에서만 돈다(stored adapter는 항상 준다).
    monkeypatch.setattr(adapter, "get_export_requests", lambda: {}, raising=False)
    def automatic(case, adapter, view):
        # 실제 `issue_missing_exports`처럼 같은 입력 fingerprint는 다시 발주하지 않는다.
        if not any(r["input_fingerprint"] == "TEST_ONLY_EXPORT" for r in case.job_records):
            jobs.issue_job(case, "REPORT_VIDEO_EXPORT", input_fingerprint="TEST_ONLY_EXPORT",
                export_input={"incident_clip_ref": "clip", "post_stamp": {"needed": False, "value": None}})
    monkeypatch.setattr(exports, "issue_missing_exports", automatic)
    return store, cid


@pytest.mark.parametrize("accepted", [False, True])
def test_resume_reissues_deferred_auto_exports_through_same_admission(monkeypatch, accepted):
    """#674: 반영 커밋 뒤 슬롯이 비면 같은 gate로 보류분을 다시 발주한다. 거절되면 아무것도 바꾸지 않는다."""
    from daesingo.case import reflection
    store, cid = _resumable(monkeypatch)
    original = store.get_case(cid)
    seen = []
    def admit(records):
        seen.extend(records)
        return accepted
    appended = reflection.resume_auto_exports(cid, store=store, admit_auto_exports=admit)
    saved = store.get_case(cid)
    assert [record["kind"] for record in seen] == ["REPORT_VIDEO_EXPORT"]
    if accepted:
        assert [record["kind"] for record in appended] == ["REPORT_VIDEO_EXPORT"]
        assert saved.job_records == original.job_records + appended
        # 반영 경로의 자동 발주와 같다 — 사용자 의도가 아니므로 revision을 올리지 않는다.
        assert saved.case_rev == original.case_rev
        assert saved.stage == "EVIDENCE_REVIEW"
        # 다시 불러도(재전달·다음 반영) 같은 입력은 발주하지 않고 admission도 다시 묻지 않는다.
        assert reflection.resume_auto_exports(cid, store=store, admit_auto_exports=admit) == []
        assert len(seen) == 1
        assert store.get_case(cid) == saved
    else:
        assert appended == []
        assert saved == original


@pytest.mark.parametrize("stage", ["CANDIDATE_REVIEW", "READY"])
def test_resume_outside_evidence_review_issues_nothing(monkeypatch, stage):
    """후보를 다시 고르는 중이거나 이미 READY면 이전 후보의 보류분을 발주하지 않는다."""
    from daesingo.case import reflection
    store, cid = _resumable(monkeypatch)
    case = store.get_case(cid)
    case.stage = stage
    store.save(case)
    def admit(records):
        raise AssertionError("admission must not be asked")
    assert reflection.resume_auto_exports(cid, store=store, admit_auto_exports=admit) == []
    assert store.get_case(cid) == case


def test_worker_bridge_resumes_on_the_caller_connection(monkeypatch):
    """Worker의 Case bridge는 호출자 connection의 store로 같은 함수를 부르고 Runtime 레코드로 돌려준다."""
    from daesingo.common.jobs.reflection import RuntimeJobRecord
    from daesingo.worker.case_reflector import CaseReflector
    store, cid = _resumable(monkeypatch)
    bridge = CaseReflector(reader=lambda *a: None, timelines=object(), store_factory=lambda conn: store)
    jobs_ = bridge.resume_auto_exports(None, cid, admit_auto_exports=lambda records: True)
    record = store.get_case(cid).job_records[-1]
    assert jobs_ == (RuntimeJobRecord(record["job_id"], cid, "REPORT_VIDEO_EXPORT"),)
    with pytest.raises(ValueError):
        bridge.resume_auto_exports(object(), cid, admit_auto_exports=lambda records: True)
