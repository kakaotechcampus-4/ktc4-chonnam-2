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
    # 2026-09-14 정정: candidate 선택 자체는 case_rev를 올리지 않는다(`scenario_correction_rerun_001`/
    # `scenario_plate_reread_001` fixture로 확인 — 이전엔 이 전이도 case_rev를 올린다고 잘못 가정했었다).
    assert case.case_rev == 2
    assert case.selection_rev == 1  # candidate 선택 1회 = selection_rev 1회 증가

    case.mark_ready()
    assert case.stage == "READY"
    assert case.case_rev == 3


def test_empty_candidates_still_advances_to_candidate_review():
    """빈 배열(candidates=[])은 실패가 아니다 — 검색 자체는 성공이므로 CANDIDATE_REVIEW로
    전진한다(2026-09-14, `scenario_empty_001` fixture로 정정 — 예전엔 SEARCHING에 머문다고
    잘못 가정했었다)."""
    case = _make_case()
    case.start_search()
    case.receive_candidates([])
    assert case.stage == "CANDIDATE_REVIEW"
    assert case.candidates == []
    assert case.case_rev == 2  # SEARCHING(1, 안 오름) -> CANDIDATE_REVIEW(2, 오름)


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


def test_mark_reviewed_sets_flag_and_bumps_case_rev():
    """`user_reviewed`는 §3-C의 별도 workflow 상태(evidence.user_edited/INFO_USER_CONFIRMED와
    합치지 않는다, §3-C-8) — `mark_reviewed()`가 그 상태를 True로 세우고, 사용자의 명시적
    "확인함" 액션 자체가 새 요청이므로 case_rev도 오른다(`scenario_happy_001`의 rev3(case_rev:3,
    user_reviewed:false)→rev4(case_rev:4, user_reviewed:true) — 두 revision이 이 두 필드
    말고는 완전히 동일하다는 데서 역산해 확인, 2026-09-14)."""
    case = _make_case()
    case.start_search()
    case.receive_candidates([Candidate(candidate_id="c1", at=None, at_provenance=None, observed="obs", thumb_ref="fr1")])
    case.select_candidate("c1")
    case.mark_ready()
    assert case.user_reviewed is False
    assert case.case_rev == 3

    case.mark_reviewed()
    assert case.user_reviewed is True
    assert case.case_rev == 4


def test_job_ids_are_always_unique_even_for_same_kind():
    """case는 STALE 자동재시도(같은 job_id)를 만들지 않는다 — 매번 새 job_id.
    (STALE 재시도는 common/runtime의 책임이라 case 코드에는 그 분기가 없다.)"""
    case = _make_case()
    ids = {case.next_job_id("PLATE_READ") for _ in range(20)}
    assert len(ids) == 20


def _case_at_evidence_review() -> CaseAggregate:
    case = _make_case()
    case.start_search()
    case.receive_candidates([
        Candidate(candidate_id="c1", at="t1", at_provenance="p1", observed="obs1", thumb_ref="fr1"),
        Candidate(candidate_id="c2", at="t2", at_provenance="p2", observed="obs2", thumb_ref="fr2"),
    ])
    case.select_candidate("c1")
    return case


def test_regress_to_searching_from_each_later_stage_clears_candidates():
    """`TIME_HINT_EDIT` 역행 전이 — `부분 재실행 정책 표 초안` 1행: `CANDIDATE_REVIEW`/
    `EVIDENCE_REVIEW`/`READY` 어디서든 `SEARCHING`으로 돌아가고 candidates는 전부 폐기된다."""
    for reach_stage in ("CANDIDATE_REVIEW", "EVIDENCE_REVIEW", "READY"):
        case = _make_case()
        case.start_search()
        case.receive_candidates([Candidate(candidate_id="c1", at=None, at_provenance=None, observed="obs", thumb_ref="fr1")])
        if reach_stage in ("EVIDENCE_REVIEW", "READY"):
            case.select_candidate("c1")
        if reach_stage == "READY":
            case.mark_ready()
        assert case.stage == reach_stage

        case.regress_to_searching()
        assert case.stage == "SEARCHING"
        assert case.candidates == []


def test_regress_to_searching_rejects_intake_and_searching():
    case = _make_case()
    with pytest.raises(InvalidTransition):
        case.regress_to_searching()  # INTAKE — 아직 SEARCHING에도 못 갔다

    case.start_search()
    with pytest.raises(InvalidTransition):
        case.regress_to_searching()  # SEARCHING — 이미 거기라 "역행"할 데가 없다


def test_regress_to_searching_does_not_bump_case_rev_by_itself():
    """전이 자체는 case_rev를 안 올린다 — `correction.edit_time_hint()`가 `apply_correction()`으로
    이미 한 번 올리는 게 원칙(한 사용자 요청 = 한 case_rev 증가)."""
    case = _case_at_evidence_review()
    rev_before = case.case_rev
    case.regress_to_searching()
    assert case.case_rev == rev_before


def test_reselect_candidate_stays_in_evidence_review():
    case = _case_at_evidence_review()
    assert case.stage == "EVIDENCE_REVIEW"
    rev_before = case.case_rev
    selection_rev_before = case.selection_rev

    case.reselect_candidate("c2")
    assert case.stage == "EVIDENCE_REVIEW"  # 표 2행: 제자리
    assert case.case_rev == rev_before  # 여기서는 안 올림(correction.reselect_candidate()가 올림)
    assert case.selection_rev == selection_rev_before + 1
    assert [c.candidate_id for c in case.candidates if c.selected] == ["c2"]


def test_reselect_candidate_rejects_outside_evidence_review():
    case = _make_case()
    case.start_search()
    case.receive_candidates([Candidate(candidate_id="c1", at=None, at_provenance=None, observed="obs", thumb_ref="fr1")])
    with pytest.raises(InvalidTransition):
        case.reselect_candidate("c1")  # CANDIDATE_REVIEW에선 아직 선택 이후 정정 대상이 없다


def test_reselect_candidate_rejects_unknown_candidate_id():
    case = _case_at_evidence_review()
    with pytest.raises(InvalidTransition):
        case.reselect_candidate("does-not-exist")
