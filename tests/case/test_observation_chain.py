"""관찰 job 입력 고정 · 발주 순서 — 8-6 2단계 · RT-10(b), `decisions/incident-clip-observation-input.md`.

선택된 후보 → `FINE_VERIFY` → (`NOT_OBSERVED`가 아니면) `INCIDENT_CLIP_BUILD` → 성공하면 `PLATE_READ` ·
`OVERLAY_TIME_READ`(같은 clip). Coarse T2가 rank=1을 자동 선택하고 첫 Fine을 발주한다(W12:C2). 관찰 job의 입력은
발주할 때 case state에 append-only로 남고
`CaseStore.observation_input`으로 읽는다. 후속 발주는 입력의 후보가 현재 선택 · 현재 세대일 때만 한다(§4-4).
"""
from __future__ import annotations

from typing import Any

import pytest

from daesingo.case import command, jobs, service
from daesingo.case.domain import InvalidTransition
from daesingo.case.reflection import ExecutionOutcome, reflect_execution
from daesingo.case.store import CaseStore
from daesingo.case.timeline_source import CaseTimeline
from daesingo.case.view import JOB_LABEL_KEYS


def _event(candidate_id: str, rank: int) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "summary": f"{candidate_id} 실선 변경",
        "thumbnail_ref": f"fr_{candidate_id}",
        "rank": rank,
        "span": {
            "timeline_id": "tl_1",
            "timeline_revision": 1,
            "start_ms": 1_000 * rank,
            "end_ms": 1_000 * rank + 3_000,
            "representative_ms": 1_000 * rank + 1_500,
        },
    }


EVENTS = [_event("cand_1", 1), _event("cand_2", 2)]
def _fine(verification: str | None) -> dict[str, Any]:
    """`FINE_VERIFY` reader 결과 — search `verify_visual` 반환과 같은 모양(`AnalysisRun` + `VisualEvidence`)."""
    visual = None if verification is None else {"candidate_id": "cand_1", "verification": verification}
    return {"analysis_run": {"operation": "VISUAL_VERIFY", "outcome": "SUCCEEDED"}, "visual_evidence": visual}


SPAN_1 = {"timeline_id": "tl_1", "timeline_revision": 1, "start_ms": 1_000, "end_ms": 4_000}


class FakeTimelines:
    def timeline_for(self, sources):
        return CaseTimeline(timeline_id="tl_1", revision=1, duration_ms=10_000)


class FakeReader:
    """kind별 결과 내용. 읽은 kind를 남긴다."""

    def __init__(self, contents: dict[str, dict[str, Any]]):
        self.contents = contents
        self.calls: list[str] = []

    def __call__(self, conn: Any, kind: str, produced: tuple) -> dict[str, Any]:
        self.calls.append(kind)
        return self.contents[kind]


class NoDownstream:
    """선택 뒤 CaseView · READY gate가 adapter를 조회한다 — downstream 값이 없는 adapter."""

    def get_candidate_events(self): return []
    def get_candidate_search_outcome(self): return None
    def get_analysis_scopes(self): return []
    def get_evidence_record(self): return None
    def get_evidence_records(self): return []
    def get_requirement_report(self, scope): return None
    def get_requirement_reports(self, scope): return []
    def get_evidence_needs(self): return []
    def get_report_package(self): return None
    def get_plate_readouts(self): return []
    def get_overlay_time_readouts(self): return []
    def get_plate_read_status(self): return None
    def get_visual_evidence_decision(self): return None
    def get_independent_facts(self): return None
    def get_job_executions(self): return []


_counter = iter(range(1, 10_000))


def _reflect(store: CaseStore, case_id: str, job: dict[str, Any], content: dict[str, Any] | None = None, *,
             status: str = "SUCCEEDED", reader: FakeReader | None = None):
    outcome = ExecutionOutcome(
        execution_id=f"exec_{next(_counter)}",
        job_id=job["job_id"],
        case_id=case_id,
        kind=job["kind"],
        attempt=1,
        status=status,
        produced=({"kind": "result", "ref": f"ref_{job['job_id']}"},) if status == "SUCCEEDED" else (),
        failure_kind=None if status == "SUCCEEDED" else "PROVIDER_FAILED",
    )
    reader = reader or FakeReader({job["kind"]: content or {}})
    return reflect_execution(outcome, store=store, reader=reader, timelines=FakeTimelines())


def _searching() -> tuple[CaseStore, str]:
    store = CaseStore(conn=object())
    case_id = service.create_case(store=store)
    service.record_source_registered(
        case_id,
        {"source_asset_ref": "sa_0", "availability": "AVAILABLE", "duration_sec": 10.0},
        media_streams=[{"media_stream_ref": "ms_0", "media_type": "VIDEO"}],
        store=store,
    )
    start = {"case_id": case_id, "expected_case_rev": 1, "kind": "START_ANALYSIS", "payload": {"description": ""}}
    assert command.execute_command(start, store=store, timelines=FakeTimelines()).response["ok"] is True
    return store, case_id


def _after_coarse(events=EVENTS) -> tuple[CaseStore, str, dict[str, Any], dict[str, Any] | None]:
    """Coarse 반영 → (반영기가) rank=1 선택 → 첫 Fine 발주."""
    store, case_id = _searching()
    store.adapters.put(case_id, NoDownstream())
    coarse = jobs.latest_job_record(store.get_case(case_id), "COARSE_SEARCH")
    _reflect(store, case_id, coarse, {"outcome": "SUCCEEDED", "candidate_events": events})
    return store, case_id, coarse, jobs.latest_job_record(store.get_case(case_id), "FINE_VERIFY")


def _latest(store: CaseStore, case_id: str, kind: str) -> dict[str, Any]:
    return jobs.latest_job_record(store.get_case(case_id), kind)


def _after_fine(verification: str = "OBSERVED"):
    store, case_id, coarse, _ = _after_coarse()
    fine = _latest(store, case_id, "FINE_VERIFY")
    result = _reflect(store, case_id, fine, _fine(verification))
    return store, case_id, coarse, fine, result


def _move_selection(store: CaseStore, case_id: str, candidate_id: str) -> None:
    """선택만 옮긴다. 준비 중 재선택은 command가 막지만(6.6순위 조건 1, `test_reselect_while_preparing.py`) 후속 발주는
    그것과 따로 「현재 선택 · 세대」를 다시 확인한다 — 그 확인을 직접 시험한다."""
    case = store.load_for_update(case_id)
    for c in case.candidates:
        c.selected = c.candidate_id == candidate_id
    store.save(case)


# ── kind 등재 ─────────────────────────────────────────────────────────────


def test_incident_clip_build_is_a_job_kind_with_its_label():
    assert "INCIDENT_CLIP_BUILD" in jobs.JOB_KINDS
    assert JOB_LABEL_KEYS["INCIDENT_CLIP_BUILD"] == "job.incident_clip_build"


# ── 선택 후보 → FINE_VERIFY ──────────────────────────────────────────────


def test_fine_for_selected_candidate_has_fixed_input():
    store, case_id, coarse, fine = _after_coarse()

    assert fine == _latest(store, case_id, "FINE_VERIFY")
    # scope_ref는 JobRecord에 싣는다(§4-1) — 그 세대 COARSE_SEARCH의 scope_ref 그대로.
    assert fine["scope_ref"] == coarse["scope_ref"]
    # Fine 후보당 상한은 case가 발주 때 고정한다(`timeout-fallback.md`, #407 결정 (a)) — Coarse scope 150초가 아니다.
    assert store.observation_input(case_id, fine["job_id"]) == {
        "candidate_id": "cand_1",
        "generation_job_id": coarse["job_id"],
        "span": SPAN_1,
        "max_latency_sec": 70,
    }


def test_no_selection_issues_no_fine():
    store, case_id, _, fine = _after_coarse(events=[])

    assert fine is None
    assert store.get_case(case_id).job_records[-1]["kind"] == "COARSE_SEARCH"


def test_candidate_without_full_span_issues_no_fine():
    partial = {**_event("cand_1", 1), "span": {"representative_ms": 1_500, "timeline_revision": 1}}
    store, case_id, _, fine = _after_coarse(events=[partial])

    assert [c.candidate_id for c in store.get_case(case_id).candidates if c.selected] == ["cand_1"]
    assert fine is None


def test_coarse_reflection_selects_top_ranked_and_issues_first_fine():
    # W12:C2 — 가장 유력한 후보를 자동으로 고르고 첫 Fine을 발주한다(#168 결정 1, core-user-flow §8-1).
    store, case_id = _searching()
    coarse = jobs.latest_job_record(store.get_case(case_id), "COARSE_SEARCH")

    result = _reflect(store, case_id, coarse, {"outcome": "SUCCEEDED", "candidate_events": EVENTS})

    case = store.get_case(case_id)
    fine = _latest(store, case_id, "FINE_VERIFY")
    assert [j["job_id"] for j in result.appended_job_records] == [fine["job_id"]]
    assert case.stage == "EVIDENCE_REVIEW"
    assert [c.candidate_id for c in case.candidates if c.selected] == ["cand_1"]
    assert store.observation_input(case_id, fine["job_id"]) == {
        "candidate_id": "cand_1",
        "generation_job_id": coarse["job_id"],
        "span": SPAN_1,
        "max_latency_sec": 70,
    }


def test_auto_selected_fine_blocks_reselect_while_preparing():
    # 자동 선택 뒤 첫 Fine을 기다리는 동안은 「준비 중」이다(`decisions/reselect-while-preparing.md`).
    store, case_id, _, _ = _after_coarse()

    with pytest.raises(InvalidTransition):
        store.get_case(case_id).check_reselect("cand_2")


def test_coarse_reflection_without_candidates_stays_in_candidate_review():
    store, case_id = _searching()
    coarse = jobs.latest_job_record(store.get_case(case_id), "COARSE_SEARCH")

    result = _reflect(store, case_id, coarse, {"outcome": "SUCCEEDED", "candidate_events": []})

    assert result.appended_job_records == []
    assert store.get_case(case_id).stage == "CANDIDATE_REVIEW"


def test_coarse_reflection_without_top_rank_selects_nothing():
    # rank=1이 없으면 가장 유력한 후보를 임의로 정하지 않는다(`select_top_ranked`).
    store, case_id = _searching()
    coarse = jobs.latest_job_record(store.get_case(case_id), "COARSE_SEARCH")

    result = _reflect(store, case_id, coarse, {"outcome": "SUCCEEDED", "candidate_events": [_event("cand_2", 2)]})

    assert result.appended_job_records == []
    assert store.get_case(case_id).stage == "CANDIDATE_REVIEW"


def test_observation_input_of_non_observation_job_is_key_error():
    store, case_id, coarse, _ = _after_coarse()

    with pytest.raises(KeyError):
        store.observation_input(case_id, coarse["job_id"])


# ── FINE_VERIFY → INCIDENT_CLIP_BUILD ─────────────────────────────────────


@pytest.mark.parametrize("verification", ["OBSERVED", "UNCERTAIN"])
def test_fine_not_not_observed_issues_clip_build(verification):
    store, case_id, coarse, fine, result = _after_fine(verification)

    clip = _latest(store, case_id, "INCIDENT_CLIP_BUILD")
    assert [j["job_id"] for j in result.appended_job_records] == [clip["job_id"]]
    assert clip["scope_ref"] == coarse["scope_ref"]
    # Fine 상한은 Fine 입력에만 둔다 — clip 입력으로 옮기지 않는다.
    assert store.observation_input(case_id, clip["job_id"]) == {
        "candidate_id": "cand_1",
        "generation_job_id": coarse["job_id"],
        "span": SPAN_1,
        "fine_job_id": fine["job_id"],
    }
    assert store.get_case(case_id).settled_jobs[fine["job_id"]] == "REFLECTED"


def test_fine_not_observed_issues_nothing():
    store, case_id, _, fine, result = _after_fine("NOT_OBSERVED")

    assert result.appended_job_records == []
    assert store.get_case(case_id).settled_jobs[fine["job_id"]] == "REFLECTED"


def test_fine_without_visual_evidence_issues_nothing():
    store, case_id, _, _, result = _after_fine(None)

    assert result.appended_job_records == []


def test_failed_fine_issues_nothing_and_reads_nothing():
    store, case_id, _, _ = _after_coarse()
    fine = _latest(store, case_id, "FINE_VERIFY")
    reader = FakeReader({})

    result = _reflect(store, case_id, fine, status="FAILED", reader=reader)

    assert result.appended_job_records == []
    assert reader.calls == []


def test_late_fine_of_previous_candidate_issues_nothing():
    store, case_id, _, _ = _after_coarse()
    fine = _latest(store, case_id, "FINE_VERIFY")
    _move_selection(store, case_id, "cand_2")

    result = _reflect(store, case_id, fine, _fine("OBSERVED"))

    assert result.status == "APPLIED"
    assert result.appended_job_records == []
    # 재선택 뒤에도 이미 발주한 job의 입력은 그대로다(append-only).
    assert store.observation_input(case_id, fine["job_id"])["candidate_id"] == "cand_1"


def test_late_fine_of_previous_generation_issues_nothing():
    store, case_id, _, _ = _after_coarse()
    old_fine = _latest(store, case_id, "FINE_VERIFY")
    # 다른 scope로 재탐색 — 같은 candidate_id가 다시 나와도 다른 세대다.
    case = store.load_for_update(case_id)
    case.regress_to_searching()
    new_coarse = jobs.issue_coarse_search(case, scope_ref="scope_again", input_fingerprint="sha256:again")
    store.save(case)
    _reflect(store, case_id, new_coarse, {"outcome": "SUCCEEDED", "candidate_events": EVENTS})

    result = _reflect(store, case_id, old_fine, _fine("OBSERVED"))

    assert result.status == "APPLIED"
    assert result.appended_job_records == []


# ── INCIDENT_CLIP_BUILD → PLATE_READ · OVERLAY_TIME_READ ────────────────────


def test_clip_build_issues_both_readouts_with_the_same_clip():
    store, case_id, coarse, _, _ = _after_fine()
    clip = _latest(store, case_id, "INCIDENT_CLIP_BUILD")

    result = _reflect(store, case_id, clip, {"incident_clip_ref": "clip_1"})

    plate = _latest(store, case_id, "PLATE_READ")
    overlay = _latest(store, case_id, "OVERLAY_TIME_READ")
    assert [j["job_id"] for j in result.appended_job_records] == [plate["job_id"], overlay["job_id"]]
    expected = {"candidate_id": "cand_1", "generation_job_id": coarse["job_id"], "incident_clip_ref": "clip_1"}
    assert store.observation_input(case_id, plate["job_id"]) == expected
    assert store.observation_input(case_id, overlay["job_id"]) == expected
    assert plate["scope_ref"] == overlay["scope_ref"] == coarse["scope_ref"]


def test_failed_clip_build_issues_nothing():
    store, case_id, _, _, _ = _after_fine()
    clip = _latest(store, case_id, "INCIDENT_CLIP_BUILD")

    result = _reflect(store, case_id, clip, status="FAILED", reader=FakeReader({}))

    assert result.appended_job_records == []
    assert store.get_case(case_id).settled_jobs[clip["job_id"]] == "REFLECTED"


def test_late_clip_of_previous_candidate_issues_nothing():
    store, case_id, _, _, _ = _after_fine()
    clip = _latest(store, case_id, "INCIDENT_CLIP_BUILD")
    _move_selection(store, case_id, "cand_2")

    result = _reflect(store, case_id, clip, {"incident_clip_ref": "clip_1"})

    assert result.appended_job_records == []


# ── 다른 후보 선택 뒤 첫 빠진 단계부터 발주(§4-6) ─────────────────────────────


def _select_other(store: CaseStore, case_id: str, candidate_id: str) -> list[dict[str, Any]]:
    request = {
        "case_id": case_id,
        "expected_case_rev": store.get_case(case_id).case_rev,
        "kind": "SELECT_OTHER_CANDIDATE",
        "payload": {"candidate_id": candidate_id},
    }
    result = command.execute_command(request, store=store, timelines=FakeTimelines())
    assert result.response["ok"] is True, result.response
    return result.appended_job_records


def _complete_chain(store: CaseStore, case_id: str, *, verification: str = "OBSERVED", clip: str = "SUCCEEDED",
                    plate: str = "SUCCEEDED", overlay: str = "SUCCEEDED") -> None:
    """선택 후보의 기다리던 Fine부터 판독까지 반영한다. 앞 단계가 멈추면 거기서 끝난다."""
    _reflect(store, case_id, _latest(store, case_id, "FINE_VERIFY"), _fine(verification))
    if verification == "NOT_OBSERVED":
        return
    clip_job = _latest(store, case_id, "INCIDENT_CLIP_BUILD")
    clip_ref = f"clip_{store.observation_input(case_id, clip_job['job_id'])['candidate_id']}"
    _reflect(store, case_id, clip_job, {"incident_clip_ref": clip_ref}, status=clip)
    if clip == "FAILED":
        return
    _reflect(store, case_id, _latest(store, case_id, "PLATE_READ"), status=plate)
    _reflect(store, case_id, _latest(store, case_id, "OVERLAY_TIME_READ"), status=overlay)


def _inputs(store: CaseStore, case_id: str, jobs_: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    return [(j["kind"], store.observation_input(case_id, j["job_id"])) for j in jobs_]


def test_reselect_issues_fine_for_the_new_candidate():
    store, case_id, coarse, _ = _after_coarse()
    _complete_chain(store, case_id)

    appended = _select_other(store, case_id, "cand_2")

    assert _inputs(store, case_id, appended) == [("FINE_VERIFY", {
        "candidate_id": "cand_2",
        "generation_job_id": coarse["job_id"],
        "span": {"timeline_id": "tl_1", "timeline_revision": 1, "start_ms": 2_000, "end_ms": 5_000},
        "max_latency_sec": 70,
    })]


def test_reselect_back_reuses_completed_observations():
    # A→B→A · B→A→B: 같은 탐색 결과 안에서 끝난 관찰은 다시 내지 않는다(`reselect-observation-reuse.md` (b)).
    store, case_id, _, _ = _after_coarse()
    _complete_chain(store, case_id)
    _select_other(store, case_id, "cand_2")
    _complete_chain(store, case_id, verification="NOT_OBSERVED")

    assert _select_other(store, case_id, "cand_1") == []
    assert _select_other(store, case_id, "cand_2") == []


def test_reselect_back_resumes_from_failed_clip():
    store, case_id, _, _ = _after_coarse()
    fine_1 = _latest(store, case_id, "FINE_VERIFY")
    _complete_chain(store, case_id, clip="FAILED")
    _select_other(store, case_id, "cand_2")
    _complete_chain(store, case_id, verification="NOT_OBSERVED")

    appended = _select_other(store, case_id, "cand_1")

    assert [(kind, source["fine_job_id"]) for kind, source in _inputs(store, case_id, appended)] == [
        ("INCIDENT_CLIP_BUILD", fine_1["job_id"])
    ]


def test_reselect_back_reissues_only_the_failed_readout_with_the_same_clip():
    store, case_id, _, _ = _after_coarse()
    _complete_chain(store, case_id, overlay="FAILED")
    _select_other(store, case_id, "cand_2")
    _complete_chain(store, case_id, verification="NOT_OBSERVED")

    appended = _select_other(store, case_id, "cand_1")

    assert [(kind, source["incident_clip_ref"]) for kind, source in _inputs(store, case_id, appended)] == [
        ("OVERLAY_TIME_READ", "clip_cand_1")
    ]


def test_reselect_does_not_reuse_observations_of_a_previous_generation():
    store, case_id, _, _ = _after_coarse()
    _complete_chain(store, case_id)
    _select_other(store, case_id, "cand_2")
    _complete_chain(store, case_id, verification="NOT_OBSERVED")
    # 재탐색 — 같은 candidate_id가 다시 나와도 다른 세대다. 반영기가 cand_1을 다시 고르고 Fine을 낸다.
    case = store.load_for_update(case_id)
    case.regress_to_searching()
    new_coarse = jobs.issue_coarse_search(case, scope_ref="scope_again", input_fingerprint="sha256:again")
    store.save(case)
    _reflect(store, case_id, new_coarse, {"outcome": "SUCCEEDED", "candidate_events": EVENTS})
    _complete_chain(store, case_id)

    appended = _select_other(store, case_id, "cand_2")

    assert _inputs(store, case_id, appended)[0][0] == "FINE_VERIFY"
    assert _inputs(store, case_id, appended)[0][1]["generation_job_id"] == new_coarse["job_id"]


# ── 같은 입력으로 다시 발주 ─────────────────────────────────────────────────


def test_reread_copies_scope_ref_and_observation_input_of_prior_readout():
    store, case_id, _, _, _ = _after_fine()
    clip = _latest(store, case_id, "INCIDENT_CLIP_BUILD")
    _reflect(store, case_id, clip, {"incident_clip_ref": "clip_1"})
    prior = _latest(store, case_id, "PLATE_READ")

    case = store.load_for_update(case_id)
    (reread,) = jobs.issue_needed_jobs(case, {"items": [{"kind": "PLATE_REREAD"}]})
    store.save(case)

    assert reread["job_id"] != prior["job_id"]
    assert (reread["scope_ref"], reread["input_fingerprint"]) == (prior["scope_ref"], prior["input_fingerprint"])
    assert store.observation_input(case_id, reread["job_id"]) == store.observation_input(case_id, prior["job_id"])


# ── INCIDENT_CLIP_BUILD 실패 표시(#297 후속) ───────────────────────────────


CLIP_FAILED = "recording.incident_clip_build_failed"


def _clip_failed() -> tuple[CaseStore, str]:
    store, case_id, _, _, _ = _after_fine("OBSERVED")
    _reflect(store, case_id, _latest(store, case_id, "INCIDENT_CLIP_BUILD"), status="FAILED")
    return store, case_id


def test_clip_failure_shows_notice_and_no_running_readouts():
    store, case_id = _clip_failed()

    view = service.get_view(case_id, store=store)

    notice = next(n for n in view["notices"] if n["code"] == CLIP_FAILED)
    assert notice == {"code": CLIP_FAILED, "severity": "ERROR", "blocking": True,
                      "message_key": "notice.incident_clip_build_failed", "actions": []}
    assert view["running_jobs"] == []
    # 발주되지 않은 판독을 진행 중으로 보이지 않는다(#297 수락 기준 2).
    assert {s["step"]: s["state"] for s in view["progress"]}.get("plate_read") != "RUNNING"
    assert {s["step"]: s["state"] for s in view["progress"]}.get("overlay_time_read") != "RUNNING"


def test_clip_success_has_no_clip_failed_notice():
    store, case_id, _, _, _ = _after_fine("OBSERVED")
    _reflect(store, case_id, _latest(store, case_id, "INCIDENT_CLIP_BUILD"), {"incident_clip_ref": "clip_1"})

    assert CLIP_FAILED not in [n["code"] for n in service.get_view(case_id, store=store)["notices"]]


def test_clip_failure_of_other_candidate_is_not_shown():
    # 실패한 clip은 cand_1 것이다. 다른 후보로 옮기면 그 후보의 실패가 아니라 notice가 없다.
    store, case_id = _clip_failed()
    _move_selection(store, case_id, "cand_2")

    assert CLIP_FAILED not in [n["code"] for n in service.get_view(case_id, store=store)["notices"]]
