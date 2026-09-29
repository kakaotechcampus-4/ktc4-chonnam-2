"""`correction.edit_time_hint()`/`reselect_candidate()` — `TIME_HINT_EDIT`/`OTHER_CANDIDATE`
`CorrectionRecord` 제출과 domain state 반영(`regress_to_searching()`/`reselect_candidate()`)을
한 번에 묶는 orchestration 레이어. `docs/modules/case/doc-research/부분 재실행 정책 표 초안
v1...md`(연구 메모, decisions/로 승격되지 않은 초안) 1·2행 그대로 구현했다 — 실제 fixture는
없으므로 이 테스트가 유일한 검증이다.
"""
import pytest

from daesingo.case import correction
from daesingo.case.domain import Candidate, CaseAggregate, InvalidTransition


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

    # hints는 case 전체에 걸린 값이라 후보가 바뀌어도 chain이 이어진다.
    assert second["supersedes_ref"] == {"kind": "correction_record", "ref": first["correction_id"]}


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


# ── 재선택 원자성(#166) · READY 재선택(#173 E-4) ─────────────────────────


def _snapshot(case: CaseAggregate) -> tuple:
    return (
        case.case_rev,
        case.selection_rev,
        case.stage,
        [c.selected for c in case.candidates],
        len(case.correction_records),
    )


@pytest.mark.parametrize("bad_id", ["does-not-exist", "c1"])
def test_rejected_reselect_leaves_no_side_effects(bad_id):
    """#166: 거부된 재선택은 case_rev·CorrectionRecord·선택을 바꾸지 않는다. `c1`은 이미 선택된
    후보라 값이 바뀌지 않는 요청이다(correction-record §8-7: 무변경 입력은 기록하지 않음)."""
    case = _case_at_evidence_review()
    before = _snapshot(case)

    with pytest.raises(InvalidTransition):
        correction.reselect_candidate(case, bad_id)

    assert _snapshot(case) == before


def test_rejected_reselect_outside_allowed_stage_is_atomic():
    case = CaseAggregate.intake(case_id="case_rs001", hints={}, manifest_summary={})
    case.start_search()
    case.receive_candidates([
        Candidate(candidate_id="c1", at=None, at_provenance=None, observed="o1", thumb_ref=None),
        Candidate(candidate_id="c2", at=None, at_provenance=None, observed="o2", thumb_ref=None),
    ])
    before = _snapshot(case)  # CANDIDATE_REVIEW — 아직 최초 선택 전

    with pytest.raises(InvalidTransition):
        correction.reselect_candidate(case, "c2")

    assert _snapshot(case) == before


def test_reselect_from_ready_starts_new_draft():
    """#173 E-4: 결과(READY) 화면에서도 다른 후보를 고를 수 있다. 새 selection context·새 초안이라
    EVIDENCE_REVIEW로 돌아가고, 이전 초안의 최종 검토(USER_REVIEWED)는 새 초안에 쓰지 않는다."""
    case = _case_at_evidence_review()
    case.mark_ready(report_package={"package_ref": {"kind": "report_package", "ref": "pkg_test_001"}})
    case.mark_reviewed()
    rev_before, sel_before = case.case_rev, case.selection_rev

    record = correction.reselect_candidate(case, "c2")

    assert record["kind"] == "OTHER_CANDIDATE"
    assert case.stage == "EVIDENCE_REVIEW"
    assert case.user_reviewed is False
    assert [c.candidate_id for c in case.candidates if c.selected] == ["c2"]
    assert case.selection_rev == sel_before + 1
    assert case.case_rev == rev_before + 1


# ── supersede chain (correction-record/v1.1 `supersedes_ref`) ───────────────


def test_supersede_chain_uses_contract_ref_and_evidence_accepts_it():
    """같은 필드를 한 선택 안에서 두 번 고치면 두 번째가 첫 번째를 `supersedes_ref`로 가리킨다.
    예전엔 `supersedes_id`(문자열)로 적어 evidence가 chain을 못 읽고 두 기록을 모두 head로 봐
    `multiple correction heads`로 실패했다(#173)."""
    from daesingo.evidence.corrections import correction_heads

    case = _case_at_evidence_review()
    first = correction.apply_correction(
        case, kind="PLATE_MANUAL_EDIT", target_field="vehicle_number",
        previous_value="12가3456", new_value="12가3457",
    )
    second = correction.apply_correction(
        case, kind="PLATE_MANUAL_EDIT", target_field="vehicle_number",
        previous_value="12가3457", new_value="12가3458",
    )

    assert first["supersedes_ref"] is None
    assert second["supersedes_ref"] == {"kind": "correction_record", "ref": first["correction_id"]}
    assert "supersedes_id" not in second
    heads = correction_heads(case.correction_records, case_id=case.case_id, selection_rev=case.selection_rev)
    assert heads["vehicle_number"]["correction_id"] == second["correction_id"]


def test_candidate_bound_chain_restarts_in_new_selection():
    """#173 E-1: 후보에 종속된 값의 정정은 선택 context 안에서만 잇는다 — 새 후보의 첫 정정은
    이전 후보의 정정을 supersede하지 않는다."""
    case = _case_at_evidence_review()
    correction.apply_correction(
        case, kind="PLATE_MANUAL_EDIT", target_field="vehicle_number",
        previous_value="12가3456", new_value="12가3457",
    )
    case.candidates.append(Candidate(candidate_id="c9", at=None, at_provenance=None, observed="obs9", thumb_ref="fr9"))
    correction.reselect_candidate(case, "c9")

    fresh = correction.apply_correction(
        case, kind="PLATE_MANUAL_EDIT", target_field="vehicle_number",
        previous_value="34나5678", new_value="34나5679",
    )

    assert fresh["supersedes_ref"] is None
