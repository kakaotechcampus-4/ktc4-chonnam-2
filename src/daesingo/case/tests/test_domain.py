import pytest

from daesingo.case.domain import Candidate, CaseAggregate, InvalidTransition


def _make_case() -> CaseAggregate:
    return CaseAggregate.intake(
        case_id="case_t001",
        hints={"time": "18시쯤"},
        manifest_summary={"file_count": 2},
    )


def test_intake_starts_at_intake_stage():
    case = _make_case()
    assert case.stage == "INTAKE"
    assert case.case_rev == 1
    assert case.selection_rev == 0


def test_forward_transitions_bump_case_rev():
    case = _make_case()
    case.start_search()
    assert case.stage == "SEARCHING"
    # scenario_happy_001의 case_views[0]이 SEARCHING에서도 case_rev:1인 것과 일치시킨다 —
    # INTAKE->SEARCHING은 아직 "요청 시점 리비전"이 바뀔 내용이 없어 case_rev를 올리지 않는다.
    assert case.case_rev == 1

    case.receive_candidates([Candidate(candidate_id="c1", at=None, at_provenance=None, observed="obs", thumb_ref="fr1")])
    assert case.stage == "CANDIDATE_REVIEW"
    assert case.case_rev == 2

    case.select_candidate("c1")
    assert case.stage == "EVIDENCE_REVIEW"
    assert case.case_rev == 3
    assert case.selection_rev == 1  # candidate 선택 1회 = selection_rev 1회 증가

    case.mark_ready()
    assert case.stage == "READY"
    assert case.case_rev == 4


def test_empty_candidates_does_not_advance_stage():
    """빈 배열(candidates=[])은 실패가 아니다 — CANDIDATE_REVIEW로 전진하지 않고 머문다."""
    case = _make_case()
    case.start_search()
    case.receive_candidates([])
    assert case.stage == "SEARCHING"
    assert case.case_rev == 1  # 빈 배열은 전이도, case_rev 증가도 일으키지 않는다


def test_invalid_forward_jump_raises():
    case = _make_case()
    with pytest.raises(InvalidTransition):
        case.select_candidate("nope")  # INTAKE에서 바로 select_candidate는 금지


def test_selecting_unknown_candidate_raises():
    case = _make_case()
    case.start_search()
    case.receive_candidates([Candidate(candidate_id="c1", at=None, at_provenance=None, observed="obs", thumb_ref=None)])
    with pytest.raises(InvalidTransition):
        case.select_candidate("does-not-exist")


def test_job_ids_are_always_unique_even_for_same_kind():
    """case는 STALE 자동재시도(같은 job_id)를 만들지 않는다 — 매번 새 job_id.
    (STALE 재시도는 common/runtime의 책임이라 case 코드에는 그 분기가 없다.)"""
    case = _make_case()
    ids = {case.next_job_id("PLATE_READ") for _ in range(20)}
    assert len(ids) == 20
