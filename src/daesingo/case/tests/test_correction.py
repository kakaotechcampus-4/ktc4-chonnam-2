"""`correction.edit_time_hint()`/`reselect_candidate()` — `TIME_HINT_EDIT`/`OTHER_CANDIDATE`
`CorrectionRecord` 제출과 domain state 반영(`regress_to_searching()`/`reselect_candidate()`)을
한 번에 묶는 orchestration 레이어. `docs/modules/case/doc-research/부분 재실행 정책 표 초안
v1...md`(연구 메모, decisions/로 승격되지 않은 초안) 1·2행 그대로 구현했다 — 실제 fixture는
없으므로 이 테스트가 유일한 검증이다.
"""
from daesingo.case import correction
from daesingo.case.domain import Candidate, CaseAggregate


def _case_at_evidence_review() -> CaseAggregate:
    case = CaseAggregate.intake(
        case_id="case_hint001",
        hints={"time": "18시쯤", "vehicle": "흰색 SUV"},
        manifest_summary={"file_count": 2},
    )
    case.start_search()
    case.receive_candidates([
        Candidate(candidate_id="c1", at="t1", at_provenance="p1", observed="obs1", thumb_ref="fr1"),
        Candidate(candidate_id="c2", at="t2", at_provenance="p2", observed="obs2", thumb_ref="fr2"),
    ])
    case.select_candidate("c1")
    return case


def test_edit_time_hint_regresses_to_searching_and_records_only_changed_fields():
    case = _case_at_evidence_review()
    rev_before = case.case_rev

    record = correction.edit_time_hint(case, {"time": "19시쯤", "vehicle": "흰색 SUV"})

    assert record is not None
    assert record["kind"] == "TIME_HINT_EDIT"
    assert record["target_field"] == "hints"
    # vehicle은 기존과 동일값이라 변경분에서 빠진다 — time만 담긴다.
    assert record["previous_value"] == {"time": "18시쯤"}
    assert record["new_value"] == {"time": "19시쯤"}

    assert case.stage == "SEARCHING"
    assert case.candidates == []
    assert case.hints["time"] == "19시쯤"
    assert case.hints["vehicle"] == "흰색 SUV"  # 안 건드린 힌트는 그대로
    assert case.case_rev == rev_before + 1  # 정확히 한 번만 오른다


def test_edit_time_hint_with_no_actual_change_creates_nothing():
    case = _case_at_evidence_review()
    rev_before = case.case_rev
    stage_before = case.stage

    record = correction.edit_time_hint(case, {"time": "18시쯤"})  # 기존과 완전히 동일

    assert record is None
    assert case.case_rev == rev_before
    assert case.stage == stage_before  # 역행도 하지 않는다
    assert case.correction_records == []


def test_edit_time_hint_rejects_unknown_field():
    case = _case_at_evidence_review()
    import pytest
    with pytest.raises(ValueError):
        correction.edit_time_hint(case, {"nonexistent_field": "x"})


def test_edit_time_hint_supersede_chain_for_repeated_edits():
    case = _case_at_evidence_review()
    first = correction.edit_time_hint(case, {"time": "19시쯤"})
    # 두 번째 편집을 하려면 다시 EVIDENCE_REVIEW까지 가야 한다(SEARCHING으로 역행했으므로).
    case.receive_candidates([Candidate(candidate_id="c3", at=None, at_provenance=None, observed="obs3", thumb_ref="fr3")])
    case.select_candidate("c3")
    second = correction.edit_time_hint(case, {"time": "20시쯤"})

    assert second["supersedes_id"] == first["correction_id"]


def test_reselect_candidate_submits_other_candidate_correction_and_bumps_case_rev():
    case = _case_at_evidence_review()
    rev_before = case.case_rev

    record = correction.reselect_candidate(case, "c2")

    assert record["kind"] == "OTHER_CANDIDATE"
    assert record["target_field"] == "candidate.selected_id"
    assert record["previous_value"] == "c1"
    assert record["new_value"] == "c2"
    assert case.stage == "EVIDENCE_REVIEW"  # 제자리
    assert case.case_rev == rev_before + 1  # apply_correction()이 한 번 올린다
    assert [c.candidate_id for c in case.candidates if c.selected] == ["c2"]
