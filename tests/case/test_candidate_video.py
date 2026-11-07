from copy import deepcopy

import pytest

from tests.preview_writer_fixture import final_preview_writer  # noqa: F401

from daesingo.case import command, jobs, observation
from daesingo.case.view import build_case_view
from tests.case.test_observation_chain import _after_coarse, _event, _reflect

KIND = "CANDIDATE_VIDEO_PREVIEW"


def request(store, case_id, candidate_id):
    case = store.get_case(case_id)
    return command.execute_command({"case_id": case_id, "expected_case_rev": case.case_rev,
        "kind": "REQUEST_CANDIDATE_VIDEO_PREVIEW", "payload": {"candidate_id": candidate_id}}, store=store)


@pytest.mark.parametrize("count", [0, 1, 2, 3, 5])
def test_candidate_count_limits_preview_targets_without_padding(count):
    store, cid, _, _ = _after_coarse([_event(f"c{i}", i) for i in range(1, count + 1)])
    cards = build_case_view(store.get_case(cid))["candidates"]
    assert len(cards) == count
    assert [c["video_preview"]["status"] for c in cards] == [
        "NOT_REQUESTED" if i <= 3 else "UNAVAILABLE" for i in range(1, count + 1)]
    for i in range(1, count + 1):
        result = request(store, cid, f"c{i}")
        assert result.response["ok"] is (i <= 3)
    assert len([r for r in store.get_case(cid).job_records if r["kind"] == KIND]) == min(count, 3)


def test_request_only_appends_preview_and_does_not_change_report_or_selection():
    store, cid, _, _ = _after_coarse()
    before = store.get_case(cid)
    result = request(store, cid, "cand_2")
    after = store.get_case(cid)
    assert result.response["ok"]
    assert [r["kind"] for r in result.appended_job_records] == [KIND]
    assert after.stage == before.stage and after.selection_rev == before.selection_rev
    assert after.candidates == before.candidates
    assert after.situation_response == before.situation_response
    assert after.correction_records == before.correction_records
    assert after.case_rev == before.case_rev + 1


def test_repeated_pending_or_ready_request_reuses_job_and_other_candidates_stay_pending():
    store, cid, _, _ = _after_coarse()
    first = request(store, cid, "cand_1").appended_job_records[0]
    second = request(store, cid, "cand_2").appended_job_records[0]
    assert request(store, cid, "cand_1").appended_job_records == []
    assert store.get_case(cid).awaits_result(first["job_id"])
    assert store.get_case(cid).awaits_result(second["job_id"])
    reflected = _reflect(store, cid, first, {"incident_clip_ref": "clip_1"})
    assert reflected.appended_job_records == []
    assert request(store, cid, "cand_1").appended_job_records == []
    cards = build_case_view(store.get_case(cid))["candidates"]
    assert cards[0]["video_preview"] == {"status": "READY", "clip_ref": "clip_1"}
    assert cards[1]["video_preview"]["status"] == "PREPARING"


@pytest.mark.parametrize("mode", ["stale", "span", "rank", "generation"])
def test_invalid_candidate_keeps_card_and_does_not_fill_from_rank_four(mode):
    store, cid, _, _ = _after_coarse([_event(f"c{i}", i) for i in range(1, 5)])
    case = store.load_for_update(cid)
    if mode == "stale": case.candidates[0].stale_revision = True
    if mode == "span": case.candidates[0].span = None
    if mode == "rank": case.candidates[0].rank = None
    if mode == "generation":
        for record in case.job_records:
            if record["kind"] == "COARSE_SEARCH": case.settled_jobs[record["job_id"]] = "SUPERSEDED"
    store.save(case)
    assert not request(store, cid, "c1").response["ok"]
    cards = build_case_view(store.get_case(cid))["candidates"]
    assert len(cards) == 4
    assert next(c for c in cards if c["candidate_id"] == "c1")["video_preview"]["status"] == "UNAVAILABLE"
    assert next(c for c in cards if c["candidate_id"] == "c4")["video_preview"]["status"] == "UNAVAILABLE"


def test_failure_is_local_and_can_be_requested_again():
    store, cid, _, _ = _after_coarse()
    job = request(store, cid, "cand_2").appended_job_records[0]
    _reflect(store, cid, job, status="FAILED")
    assert build_case_view(store.get_case(cid))["candidates"][1]["video_preview"]["status"] == "FAILED"
    again = request(store, cid, "cand_2")
    assert len(again.appended_job_records) == 1
    assert again.appended_job_records[0]["job_id"] != job["job_id"]


def test_preview_wait_does_not_block_selected_candidates_missing_fine():
    store, cid, _, fine = _after_coarse()
    request(store, cid, "cand_1")
    case = store.load_for_update(cid)
    case.settle_job(fine["job_id"], "REFLECTED")
    observation.record_outcome(case, fine["job_id"], status="FAILED")
    assert [r["kind"] for r in observation.issue_missing_for_selected(case)] == ["FINE_VERIFY"]


def test_previous_generation_or_changed_span_never_projects_ready_video():
    store, cid, _, _ = _after_coarse()
    job = request(store, cid, "cand_2").appended_job_records[0]
    _reflect(store, cid, job, {"incident_clip_ref": "old_clip"})
    case = store.load_for_update(cid)
    case.candidates[1].span = {**case.candidates[1].span, "end_ms": 9999}
    store.save(case)
    assert build_case_view(store.get_case(cid))["candidates"][1]["video_preview"]["clip_ref"] is None
    case = store.load_for_update(cid)
    case.candidate_generation += 1
    jobs.issue_coarse_search(case, scope_ref="new_scope", input_fingerprint="new")
    store.save(case)
    assert all(c["video_preview"]["clip_ref"] is None for c in build_case_view(store.get_case(cid))["candidates"])


def test_unknown_target_does_not_append_or_mutate():
    store, cid, _, _ = _after_coarse()
    before = deepcopy(store.get_case(cid))
    result = request(store, cid, "foreign")
    assert result.response["error"]["code"] == "case.command.unknown_target"
    assert store.get_case(cid) == before
