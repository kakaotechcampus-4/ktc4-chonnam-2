from copy import deepcopy
from importlib import import_module
from types import SimpleNamespace

import pytest

from daesingo.case.domain import CaseAggregate
from daesingo.case import jobs
from daesingo.case.store import CaseStore
from daesingo.case.store_state import from_row, to_row


def requests():
    return {"REPORT_VIDEO_EXPORT": {"incident_clip_ref": "clip", "post_stamp": {"needed": False, "value": None}},
        "PLATE_IMAGE_EXPORT": {"incident_clip_ref": "clip", "frame_ref": "frame", "plate_bbox_xywh": [1, 2, 3, 4],
            "max_byte_size": 30_000_000}}


def eligible():
    return {"evidence": {"record_id": "record"}, "candidates": [{"selected": True, "situation_confirmation": "CONFIRMED"}],
        "requirements_package": {"checks": [{"code": "package.asset.report_video.exists", "outcome": "UNKNOWN"}]}}


def test_same_input_issues_once_then_retry_preserves_fixed_input_through_restart():
    module = import_module("daesingo.case.exports")
    case = CaseAggregate.empty("case")
    adapter = SimpleNamespace(get_export_requests=requests)
    module.issue_missing_exports(case, adapter, eligible())
    assert [r["kind"] for r in case.job_records] == ["REPORT_VIDEO_EXPORT", "PLATE_IMAGE_EXPORT"]
    first = deepcopy(case.job_records)
    module.issue_missing_exports(case, adapter, eligible())
    assert case.job_records == first
    restored = from_row(to_row(case))
    prior = restored.job_records[1]
    fresh = jobs.issue_same_input(restored, prior)
    store = CaseStore(); store.register(restored)
    assert store.export_input("case", fresh["job_id"]) == requests()["PLATE_IMAGE_EXPORT"]
    assert fresh["input_fingerprint"] == prior["input_fingerprint"]


@pytest.mark.parametrize("field,value", [("frame_ref", "different"), ("max_byte_size", 20),
    ("plate_bbox_xywh", [2, 2, 3, 4]), ("incident_clip_ref", "other")])
def test_every_plate_input_participates_in_identity(field, value):
    module = import_module("daesingo.case.exports")
    case = CaseAggregate.empty("case")
    data = requests()
    adapter = SimpleNamespace(get_export_requests=lambda: deepcopy(data))
    module.issue_missing_exports(case, adapter, eligible())
    original = case.job_records[-1]["input_fingerprint"]
    data["PLATE_IMAGE_EXPORT"][field] = value
    module.issue_missing_exports(case, adapter, eligible())
    assert len(case.job_records) == 3 and case.job_records[-1]["input_fingerprint"] != original


@pytest.mark.parametrize("condition", ["no_evidence", "partial", "unanswered", "no_requirements"])
def test_no_orders_before_351_gate(condition):
    module = import_module("daesingo.case.exports")
    view = eligible()
    if condition == "no_evidence": view["evidence"] = None
    if condition == "partial": view["evidence"]["record_id"] = None
    if condition == "unanswered": view["candidates"][0]["situation_confirmation"] = "NOT_ASKED"
    if condition == "no_requirements": view["requirements_package"] = None
    case = CaseAggregate.empty("case")
    module.issue_missing_exports(case, SimpleNamespace(get_export_requests=requests), view)
    assert not case.job_records


@pytest.mark.parametrize("mutation", ["change", "remove"])
def test_persisted_export_input_cannot_be_changed_or_removed(mutation):
    from daesingo.case.store import AppendOnlyViolation
    module = import_module("daesingo.case.exports")
    case = CaseAggregate.empty("case")
    module.issue_missing_exports(case, SimpleNamespace(get_export_requests=requests), eligible())
    store = CaseStore(); store.register(case)
    case = store.get_case("case")
    if mutation == "change": case.export_inputs[case.job_records[0]["job_id"]]["incident_clip_ref"] = "changed"
    else: case.export_inputs.clear()
    with pytest.raises(AppendOnlyViolation): store.save(case)


@pytest.mark.parametrize("failure,actions", [("PLATE_IMAGE_EXPORT_FAILED", ["GENERATE_PLATE_IMAGE"]),
    ("PLATE_IMAGE_OUTPUT_LIMIT_UNSATISFIABLE", [])])
def test_plate_failure_notice_has_retry_only_for_ordinary_failure(failure, actions):
    module = import_module("daesingo.case.exports")
    case = CaseAggregate.empty("case")
    module.issue_missing_exports(case, SimpleNamespace(get_export_requests=requests), eligible())
    job = case.job_records[-1]
    view = {"notices": [], "running_jobs": []}
    module.export_notices(case, [{"job_id": job["job_id"], "attempt": 1, "status": "FAILED", "failure_kind": failure}],
        view, requests())
    assert view["notices"] == [{"code": "recording.plate_image_export_failed", "severity": "ERROR", "blocking": False,
        "message_key": "notice.plate_image_export_failed", "actions": actions}]


def test_plate_order_allowed_when_report_already_exists_and_no_plate_readout_means_no_plate_order():
    module = import_module("daesingo.case.exports")
    case = CaseAggregate.empty("case")
    view = eligible(); view["requirements_package"]["checks"][0]["outcome"] = "PASS"
    module.issue_missing_exports(case, SimpleNamespace(get_export_requests=requests), view)
    assert [r["kind"] for r in case.job_records] == ["PLATE_IMAGE_EXPORT"]
    case = CaseAggregate.empty("other")
    module.issue_missing_exports(case, SimpleNamespace(get_export_requests=lambda: {"REPORT_VIDEO_EXPORT": requests()["REPORT_VIDEO_EXPORT"]}), eligible())
    assert [r["kind"] for r in case.job_records] == ["REPORT_VIDEO_EXPORT"]


@pytest.mark.parametrize("kind,code,action", [("PLATE_IMAGE_EXPORT", "recording.plate_image_export_failed", "GENERATE_PLATE_IMAGE"),
    ("REPORT_VIDEO_EXPORT", "case.report_video_not_generated", "GENERATE_REPORT_VIDEO")])
def test_notice_command_after_a_b_a_retries_the_visible_current_input(monkeypatch, kind, code, action):
    """A failed, B was ordered later, selection returns to A: button must retry A."""
    from daesingo.case import command
    from daesingo.recording.exports import export_fingerprint
    data = requests()
    first = deepcopy(data[kind])
    other = {**first, "incident_clip_ref": "clip-B"}
    case = CaseAggregate.empty("case")
    for request in (first, other):
        job = jobs.issue_job(case, kind, input_fingerprint=export_fingerprint({"kind": kind, "input": request}), export_input=request)
        case.settle_job(job["job_id"], "REFLECTED")
    store = CaseStore(); store.register(case, SimpleNamespace(get_export_requests=lambda: deepcopy(data)))
    view = {"notices": [{"code": code, "actions": [action]}], "running_jobs": []}
    monkeypatch.setattr(command, "build_view_from_adapter", lambda *a, **kw: deepcopy(view))
    result = command.execute_command({"case_id": "case", "expected_case_rev": case.case_rev, "kind": "RUN_NOTICE_ACTION",
        "payload": {"notice_code": code, "action": action}}, store=store)
    assert result.response["ok"] is True
    appended, = result.appended_job_records
    assert store.export_input("case", appended["job_id"]) == first
