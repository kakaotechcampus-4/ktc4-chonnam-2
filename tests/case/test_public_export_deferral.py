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
    def automatic(case, adapter, view, *, skip=frozenset()):
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
    def automatic(case, adapter, view, *, skip=frozenset()):
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


def _pair(monkeypatch, *, report_issued=False):
    """신고영상 · 번호판 이미지가 모두 빠진(또는 신고영상만 이미 발주된) `EVIDENCE_REVIEW` case — #675."""
    store, cid = _store()
    adapter = store.adapter_for(store.get_case(cid))
    monkeypatch.setattr(adapter, "get_report_package", lambda: None)
    monkeypatch.setattr(adapter, "get_export_requests", lambda: {}, raising=False)
    def automatic(case, adapter, view, *, skip=frozenset()):
        for kind in ("REPORT_VIDEO_EXPORT", "PLATE_IMAGE_EXPORT"):
            if kind in skip or any(r["input_fingerprint"] == "TEST_" + kind for r in case.job_records):
                continue
            jobs.issue_job(case, kind, input_fingerprint="TEST_" + kind, export_input={"test": kind})
    monkeypatch.setattr(exports, "issue_missing_exports", automatic)
    if report_issued:
        case = store.get_case(cid)
        jobs.issue_job(case, "REPORT_VIDEO_EXPORT", input_fingerprint="TEST_REPORT_VIDEO_EXPORT",
                       export_input={"test": "REPORT_VIDEO_EXPORT"})
        store.save(case)
    return store, cid


def _run(path, store, cid, admit):
    from daesingo.case import reflection
    if path == "resume":
        return reflection.resume_auto_exports(cid, store=store, admit_auto_exports=admit)
    request = {"case_id": cid, "expected_case_rev": store.get_case(cid).case_rev,
        "kind": "MANUAL_PLATE_INPUT", "payload": {"value": "34나5678"}}
    result = command.execute_command(request, store=store, admit_auto_exports=admit)
    assert result.response["ok"] is True  # The correction itself is never undone by admission.
    return result.appended_job_records


@pytest.mark.parametrize("path", ["resume", "command"])
@pytest.mark.parametrize("free", [0, 1, 2], ids=["no-slot", "one-slot", "two-slots"])
def test_required_report_video_is_admitted_without_optional_plate_image(monkeypatch, path, free):
    """#675: 번호판 이미지는 READY 조건이 아니다 — 묶음이 거절되면 신고영상만 다시 묻는다."""
    store, cid = _pair(monkeypatch)
    original = store.get_case(cid)
    asked = []
    def admit(records):
        asked.append([r["kind"] for r in records])
        return len(records) <= free
    appended = _run(path, store, cid, admit)
    saved = store.get_case(cid)
    if free == 2:
        assert asked == [["REPORT_VIDEO_EXPORT", "PLATE_IMAGE_EXPORT"]]
        assert [r["kind"] for r in appended] == ["REPORT_VIDEO_EXPORT", "PLATE_IMAGE_EXPORT"]
    else:
        assert asked == [["REPORT_VIDEO_EXPORT", "PLATE_IMAGE_EXPORT"], ["REPORT_VIDEO_EXPORT"]]
        assert [r["kind"] for r in appended] == (["REPORT_VIDEO_EXPORT"] if free == 1 else [])
    # Only what admission accepted is persisted: no orphan plate record or input.
    assert saved.job_records[len(original.job_records):] == appended
    assert set(saved.export_inputs) - set(original.export_inputs) == {r["job_id"] for r in appended}


@pytest.mark.parametrize("path", ["resume", "command"])
def test_plate_image_alone_is_asked_once_when_report_video_already_issued(monkeypatch, path):
    store, cid = _pair(monkeypatch, report_issued=True)
    original = store.get_case(cid)
    asked = []
    def admit(records):
        asked.append([r["kind"] for r in records])
        return False
    assert _run(path, store, cid, admit) == []
    assert asked == [["PLATE_IMAGE_EXPORT"]]
    assert store.get_case(cid).job_records == original.job_records
