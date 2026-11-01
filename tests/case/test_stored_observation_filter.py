"""저장된 관찰 객체 중 CaseView에 쓸 것을 고른다 — 현재 후보 세대 · 선택 후보 · kind별 가장 나중 job
(`decisions/observation-storage.md` §4-4, `reselect-observation-reuse.md`)."""

from __future__ import annotations

import pytest

from daesingo.case import jobs
from daesingo.case.domain import CaseAggregate, Candidate
from daesingo.case.stored_observation import StoredObservation, select_current_observations


def _candidate(candidate_id: str, rank: int) -> Candidate:
    return Candidate(candidate_id=candidate_id, at=None, at_provenance=None, observed="", thumb_ref=None, rank=rank)


def _searched_case(*candidate_ids: str) -> CaseAggregate:
    case = CaseAggregate.empty("case_obs")
    case.start_search()
    _receive(case, *candidate_ids)
    return case


def _receive(case: CaseAggregate, *candidate_ids: str) -> None:
    search = jobs.issue_coarse_search(case, scope_ref=f"scope_{len(case.job_records)}", input_fingerprint="fp")
    case.receive_candidates([_candidate(c, i + 1) for i, c in enumerate(candidate_ids)], job_id=search["job_id"])


def _observe(case: CaseAggregate, kind: str, candidate_id: str | None, tag: str) -> StoredObservation:
    record = jobs.issue_job(case, kind, input_fingerprint=tag)
    return StoredObservation(job_id=record["job_id"], kind=kind, payload={"candidate_id": candidate_id, "tag": tag})


def _tags(selected: dict[str, StoredObservation]) -> dict[str, str]:
    return {kind: obs.payload["tag"] for kind, obs in selected.items()}


def test_latest_object_per_kind_for_selected_candidate():
    case = _searched_case("cand_a", "cand_b")
    case.select_candidate("cand_a")
    observations = [
        _observe(case, "FINE_VERIFY", "cand_a", "fine"),
        _observe(case, "PLATE_READ", "cand_a", "plate_1"),
        _observe(case, "OVERLAY_TIME_READ", "cand_a", "overlay"),
        _observe(case, "PLATE_READ", "cand_a", "plate_reread"),
    ]
    assert _tags(select_current_observations(case, observations)) == {
        "FINE_VERIFY": "fine",
        "PLATE_READ": "plate_reread",
        "OVERLAY_TIME_READ": "overlay",
    }


def test_previous_generation_is_not_used_after_research_returns_same_candidate_id():
    # 재탐색 뒤 같은 candidate_id가 다시 나와도 이전 세대 관찰은 쓰지 않는다(reselect-observation-reuse (c)).
    case = _searched_case("cand_a")
    case.select_candidate("cand_a")
    old = _observe(case, "PLATE_READ", "cand_a", "old_generation")
    case.regress_to_searching()
    _receive(case, "cand_a")
    case.select_candidate("cand_a")
    assert select_current_observations(case, [old]) == {}
    new = _observe(case, "PLATE_READ", "cand_a", "new_generation")
    assert _tags(select_current_observations(case, [old, new])) == {"PLATE_READ": "new_generation"}


def test_reselecting_a_after_b_in_same_generation_reuses_a_observation():
    case = _searched_case("cand_a", "cand_b")
    case.select_candidate("cand_a")
    a_plate = _observe(case, "PLATE_READ", "cand_a", "a")
    case.reselect_candidate("cand_b")
    b_plate = _observe(case, "PLATE_READ", "cand_b", "b")
    case.reselect_candidate("cand_a")
    assert _tags(select_current_observations(case, [a_plate, b_plate])) == {"PLATE_READ": "a"}


def test_late_result_of_previous_candidate_is_not_projected():
    # 6.6순위 조건 2 — B를 위해 발주한 판독이 A로 돌아온 뒤 도착해도 A의 관찰이 쓰인다.
    case = _searched_case("cand_a", "cand_b")
    case.select_candidate("cand_a")
    a_plate = _observe(case, "PLATE_READ", "cand_a", "a")
    case.reselect_candidate("cand_b")
    late_b = _observe(case, "PLATE_READ", "cand_b", "late_b")
    case.reselect_candidate("cand_a")
    assert _tags(select_current_observations(case, [late_b, a_plate])) == {"PLATE_READ": "a"}


def test_object_without_candidate_id_is_not_projected():
    case = _searched_case("cand_a")
    case.select_candidate("cand_a")
    assert select_current_observations(case, [_observe(case, "FINE_VERIFY", None, "no_candidate")]) == {}


def test_nothing_is_selected_without_a_selected_candidate():
    case = _searched_case("cand_a")
    observation = _observe(case, "PLATE_READ", "cand_a", "before_selection")
    assert select_current_observations(case, [observation]) == {}


def test_object_of_a_job_this_case_did_not_issue_is_a_wiring_error():
    case = _searched_case("cand_a")
    case.select_candidate("cand_a")
    stray = StoredObservation(job_id="job_elsewhere", kind="PLATE_READ", payload={"candidate_id": "cand_a"})
    with pytest.raises(ValueError, match="job_elsewhere"):
        select_current_observations(case, [stray])
