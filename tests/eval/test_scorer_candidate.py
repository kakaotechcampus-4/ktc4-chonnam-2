import pytest

from eval import manifests_io
from eval.runners import registry, normalize
from eval.scorers import candidate


def _run(impl_name):
    raw = registry.get(impl_name)({"manifest": "b_youtube", "stage": "candidate"})
    return normalize.normalize_candidate(raw)


def _gt(onset, violation_type="SIGNAL"):
    return {"items": [{"clip_id": "c1", "targets": [
        {"event_id": "E1", "scoring": "INCLUDED",
         "violation_type": violation_type, "t_onset_sec": onset},
    ]}]}


def _pred(rep, start, end, event_type="SIGNAL", score=0.9):
    return [{"clip_id": "c1", "candidates": [
        {"rank": 1, "t_start_sec": start, "t_end_sec": end,
         "representative_sec": rep, "timeline_revision": 1,
         "event_type": event_type, "score": score},
    ]}]


def test_match_is_decided_by_onset_point_error_not_overlap():
    """창이 넓어도 대표 시점이 멀면 적중이 아니다.

    구 IoU 매처는 창이 넓을수록 유리해 「아무 데나 넓게 잡기」를 보상했다.
    """
    out = candidate.score(_pred(rep=500.0, start=0.0, end=1000.0), _gt(100.0))
    assert out["recall_at"]["1"] == 0.0


def test_match_succeeds_within_tolerance_even_if_window_is_narrow():
    out = candidate.score(_pred(rep=101.5, start=101.0, end=102.0), _gt(100.0))
    assert out["recall_at"]["1"] == 1.0
    assert out["onset_error_sec"]["mean"] == pytest.approx(1.5)


def test_containment_is_reported_separately_from_the_match():
    """점 오차는 맞는데 창이 onset 을 안 품는 경우를 따로 본다.

    coarse 창 생성이 의심스러운 신호이므로 매칭 성패와 섞지 않는다.
    """
    out = candidate.score(_pred(rep=100.5, start=100.4, end=100.6), _gt(100.0))
    assert out["recall_at"]["1"] == 1.0
    assert out["containment_rate"] == 0.0


def test_span_error_sec_key_is_gone():
    """이름이 구간 오차를 뜻하는 채로 점 오차를 담으면 반드시 오해된다."""
    out = candidate.score(_pred(rep=100.0, start=90.0, end=110.0), _gt(100.0))
    assert "span_error_sec" not in out
    assert "onset_error_sec" in out


def test_always_correct_gets_perfect_recall():
    """치트 구현은 K 가 한 조각의 사건 수를 덮을 때만 만점이다.

    한 조각에 사건이 2건이면(YT_0003_C05) 두 번째 사건은 rank 2 로만 나오므로
    recall@1 은 구조적으로 1.0 이 못 된다. 그래서 K=1 기대값은 「rank 1 에 오는
    사건 수 / 채점 사건 수」로 계산한다 — 리터럴로 굳히면 조각 구성이 바뀔 때마다
    지표 버그와 데이터 변경을 구분할 수 없다.
    """
    gt = manifests_io.load_gt("b_youtube", "candidate")
    r = candidate.score(_run("fake:always_correct"), gt)
    assert r["recall_at"]["3"] == 1.0
    assert r["recall_at"]["10"] == 1.0
    assert r["fp_per_clip"] == 0.0
    scored = [[t for t in i["targets"] if t.get("scoring") != "BOUNDARY_EXCLUDED"]
              for i in gt["items"]]
    at_rank_1 = sum(1 for i in gt["items"]
                    for idx, t in enumerate(i["targets"])
                    if idx == 0 and t.get("scoring") != "BOUNDARY_EXCLUDED")
    assert r["recall_at"]["1"] == at_rank_1 / sum(len(ts) for ts in scored)


def test_always_wrong_gets_zero_recall_and_positive_fp():
    gt = manifests_io.load_gt("b_youtube", "candidate")
    r = candidate.score(_run("fake:always_wrong"), gt)
    assert r["recall_at"]["3"] == 0.0
    assert r["fp_per_clip"] > 0.0
    # 적중이 하나도 없으므로 onset_error_sec 은 0 이 아니라 null 이어야 한다
    # (측정했는데 0인 것과 잴 수 없는 것을 구분한다).
    assert r["onset_error_sec"]["mean"] is None
    assert r["onset_error_sec"]["median"] is None


def test_boundary_excluded_targets_are_not_counted():
    gt = manifests_io.load_gt("b_youtube", "candidate")
    n_included = sum(1 for i in gt["items"] for t in i["targets"]
                     if t.get("scoring") != "BOUNDARY_EXCLUDED")
    r = candidate.score(_run("fake:always_correct"), gt)
    assert r["n_events"] == n_included
    # 재계산값과 별개로 리터럴 값도 고정한다 — C47(BOUNDARY_EXCLUDED) 처리
    # 회귀를 간접적으로(fp_per_clip 등을 통해서)가 아니라 직접 잡는다.
    assert r["n_events"] == 10
    assert r["n_negative_clips"] == 113


def test_by_type_breakdown_lists_only_present_types():
    gt = manifests_io.load_gt("b_youtube", "candidate")
    r = candidate.score(_run("fake:always_correct"), gt)
    assert set(r["by_type"]) == {"SIGNAL", "SOLID_LINE_LANE_CHANGE",
                                "CENTER_LINE_CROSSING"}
    # 키 집합뿐 아니라 값도 고정한다 — by_type 분모가 전체 사건 수로 새는
    # 회귀(예: 전역 n_events 를 나눠 쓰는 버그)를 여기서 잡는다.
    assert r["by_type"]["SIGNAL"]["n"] == 2
    assert r["by_type"]["SIGNAL"]["recall_at"]["1"] == 1.0


def test_far_representative_point_is_a_miss_even_with_the_right_type():
    """구 test_wrong_span_right_type_is_a_miss 의 점 오차판.

    miss 를 만드는 것은 창이 아니라 대표 시점이다.
    """
    gt = {"items": [{"clip_id": "c1", "targets": [
        {"event_id": "E", "violation_type": "SIGNAL", "t_onset_sec": 1.5,
         "scoring": "INCLUDED"}]}]}
    normalized = [{"clip_id": "c1", "candidates": [
        {"rank": 1, "t_start_sec": 10.0, "t_end_sec": 12.0,
         "representative_sec": 11.0, "timeline_revision": 1,
         "event_type": "SIGNAL", "score": 0.9}]}]

    r = candidate.score(normalized, gt)
    assert r["recall_at"]["1"] == 0.0
    assert r["onset_error_sec"]["mean"] is None


def test_zero_length_prediction_is_not_special_under_point_error():
    """구 test_zero_span_predictions_report_null_span_error 의 대체.

    IoU 체계에서는 길이 0 예측이 0/0 나눗셈 위험이었다. 점 오차는 대표
    시점만 보므로 길이 0 자체는 더 이상 문제가 아니다 — 대표 시점이
    맞으면 적중이다.
    """
    gt = {"items": [{"clip_id": "c1", "targets": [
        {"event_id": "E", "violation_type": "SIGNAL", "t_onset_sec": 1.5,
         "scoring": "INCLUDED"}]}]}
    normalized = [{"clip_id": "c1", "candidates": [
        {"rank": 1, "t_start_sec": 1.5, "t_end_sec": 1.5,
         "representative_sec": 1.5, "timeline_revision": 1,
         "event_type": "SIGNAL", "score": 0.9}]}]

    r = candidate.score(normalized, gt)
    assert r["recall_at"]["1"] == 1.0
    assert r["onset_error_sec"]["mean"] == 0.0
    assert r["containment_rate"] == 1.0


def test_wrong_type_right_span_is_a_miss():
    # 구간·대표 시점은 완전히 맞지만 유형이 다른 예측 — and 를 or 로 잘못
    # 바꾸면 시점 일치만으로 적중 처리되어 이 테스트가 깨진다.
    gt = {"meta": {"coverage": {}},
          "items": [{"clip_id": "C0", "source_video_id": "V", "targets": [
              {"event_id": "E", "violation_type": "SIGNAL", "t_start_sec": 1.0,
               "t_end_sec": 2.0, "t_onset_sec": 1.5, "scoring": "INCLUDED"}]}]}
    norm = [{"clip_id": "C0", "candidates": [
        {"rank": 1, "t_start_sec": 1.0, "t_end_sec": 2.0,
         "representative_sec": 1.5, "event_type": "CENTER_LINE_CROSSING",
         "score": 1.0}]}]
    r = candidate.score(norm, gt)
    assert r["recall_at"]["3"] == 0.0


def test_correct_rank2_is_caught_by_recall_at_3_not_recall_at_1():
    # rank1 은 틀리고 rank2 가 맞는 경우 — rank 필터를 topk = cands 로
    # 잘못 바꾸면(순위를 안 보면) recall@1 도 1.0 이 되어 이 테스트가 깨진다.
    gt = {"meta": {"coverage": {}},
          "items": [{"clip_id": "C0", "source_video_id": "V", "targets": [
              {"event_id": "E", "violation_type": "SIGNAL", "t_start_sec": 1.0,
               "t_end_sec": 2.0, "t_onset_sec": 1.5, "scoring": "INCLUDED"}]}]}
    norm = [{"clip_id": "C0", "candidates": [
        {"rank": 1, "t_start_sec": 10.0, "t_end_sec": 12.0,
         "representative_sec": 11.0, "event_type": "CENTER_LINE_CROSSING",
         "score": 1.0},
        {"rank": 2, "t_start_sec": 1.0, "t_end_sec": 2.0,
         "representative_sec": 1.5, "event_type": "SIGNAL", "score": 0.5},
    ]}]
    r = candidate.score(norm, gt)
    assert r["recall_at"]["1"] == 0.0
    assert r["recall_at"]["3"] == 1.0


def test_boundary_excluded_is_explained_in_coverage():
    # 제외 사실이 결과 파일에 남아야 한다 — 남기지 않으면 n_events=4 와 GT 의
    # clips_with_events=5 가 어긋난 이유를 결과만 보고 알 수 없다 (스펙 §5).
    gt = manifests_io.load_gt("b_youtube", "candidate")
    r = candidate.score(_run("fake:always_correct"), gt)
    assert "BOUNDARY_EXCLUDED — 1건을 채점에서 제외했다" in r["coverage"]


def test_not_run_block_has_the_same_keys_as_a_scored_block():
    # NOT_RUN 이라고 키를 빼면 results/*.json 집계 쪽이 모양을 특수 처리해야 한다.
    gt = manifests_io.load_gt("b_youtube", "candidate")
    scored = candidate.score(_run("fake:always_correct"), gt)
    blank = candidate.not_run("NOT_RUN — 테스트")
    assert set(blank) == set(scored)
    assert set(blank["recall_at"]) == set(scored["recall_at"])
    leaves = []
    for k, v in blank.items():
        if k == "coverage":
            continue
        leaves.extend(v.values() if isinstance(v, dict) else [v])
    assert all(v is None for v in leaves)


def test_two_exclusion_reasons_are_counted_separately():
    """제외 사유를 합산하지 않는다.

    BOUNDARY_EXCLUDED(클립 경계에 걸침)와 EXCLUDED(참값 유형 자체가 없음)는
    다른 사실이다. 결과 파일만 보고 n_events 가 GT 와 어긋난 이유를 읽을 수
    있어야 하므로 사유별로 남긴다.
    """
    gt = {"items": [{"clip_id": "c1", "targets": [
        {"violation_type": "SIGNAL", "t_start_sec": 10.0, "t_end_sec": 12.0,
         "t_onset_sec": 10.5, "scoring": "INCLUDED"},
        {"violation_type": None, "t_start_sec": 20.0, "t_end_sec": 22.0,
         "t_onset_sec": 20.5, "scoring": "EXCLUDED"},
        {"violation_type": "SIGNAL", "t_start_sec": 30.0, "t_end_sec": 32.0,
         "t_onset_sec": 30.5, "scoring": "BOUNDARY_EXCLUDED"},
    ]}]}
    normalized = [{"clip_id": "c1", "candidates": []}]

    out = candidate.score(normalized, gt)

    assert out["n_events"] == 1
    assert out["excluded_by_reason"] == {"EXCLUDED": 1, "BOUNDARY_EXCLUDED": 1}


def test_scoring_defaults_to_included_when_absent():
    """scoring 이 없는 target 은 채점 대상이다.

    기존 정답지에 scoring 이 없을 수 있고, 없다고 조용히 빼면 분모가 줄어
    recall 이 부풀려진다.
    """
    gt = {"items": [{"clip_id": "c1", "targets": [
        {"violation_type": "SIGNAL", "t_start_sec": 10.0, "t_end_sec": 12.0,
         "t_onset_sec": 10.5},
    ]}]}
    out = candidate.score([{"clip_id": "c1", "candidates": []}], gt)

    assert out["n_events"] == 1
    assert out["excluded_by_reason"] == {}


def test_unknown_scoring_value_raises_instead_of_silently_excluding():
    """오타가 조용한 제외로 둔갑하지 않게 한다."""
    gt = {"items": [{"clip_id": "c1", "targets": [
        {"violation_type": "SIGNAL", "t_start_sec": 10.0, "t_end_sec": 12.0,
         "t_onset_sec": 10.5, "scoring": "EXCLUDE"},
    ]}]}
    with pytest.raises(ValueError, match="EXCLUDE"):
        candidate.score([{"clip_id": "c1", "candidates": []}], gt)


def test_derived_gt_surfaces_the_circularity_warning():
    """mock tier 처럼 GT 가 pack 에서 파생됐으면 결과가 그 사실을 말해야 한다.

    plate.score 는 이미 이 경고를 coverage 에 적는다 — candidate 도 같은
    규칙을 따라야 recall·onset_error 를 성능 근거로 잘못 읽지 않는다.
    """
    gt = _gt(100.0)
    gt["meta"] = {"coverage": {"derived_from_mock_pack": True,
                                "independent_ground_truth": False}}
    out = candidate.score(_pred(rep=100.0, start=99.0, end=101.0), gt)
    assert "순환" in out["coverage"]


def test_independent_gt_does_not_surface_the_circularity_warning():
    gt = _gt(100.0)
    gt["meta"] = {"coverage": {"derived_from_mock_pack": False,
                                "independent_ground_truth": True}}
    out = candidate.score(_pred(rep=100.0, start=99.0, end=101.0), gt)
    assert "순환" not in (out["coverage"] or "")


def test_included_target_without_violation_type_raises():
    """violation_type 이 없는 INCLUDED target 을 조용히 by_type 에 흘리지 않는다.

    scoring='INCLUDED' 인데 violation_type 이 None 이면 by_type 집계에서
    문자열 키와 섞여 sorted() 가 TypeError 로 죽는다 — 그 크래시 지점이 아니라
    원인이 결정되는 여기서 막는다. 참값 유형이 없으면 scoring 은
    'EXCLUDED' 여야 한다.
    """
    gt = {"items": [{"clip_id": "c1", "targets": [
        {"event_id": "EV_X", "violation_type": None, "t_onset_sec": 10.5,
         "scoring": "INCLUDED"},
    ]}]}
    with pytest.raises(ValueError, match="EV_X"):
        candidate.score([{"clip_id": "c1", "candidates": []}], gt)


def _gt_two_events(onset_a, onset_b, violation_type="SIGNAL"):
    """한 클립에 사건 2건. F7 이 다루는 모양이다."""
    return {"items": [{"clip_id": "c1", "targets": [
        {"event_id": "EA", "scoring": "INCLUDED",
         "violation_type": violation_type, "t_onset_sec": onset_a},
        {"event_id": "EB", "scoring": "INCLUDED",
         "violation_type": violation_type, "t_onset_sec": onset_b},
    ]}]}


def _preds(*cands):
    """(representative_sec, score) 들을 한 클립의 후보 목록으로."""
    return [{"clip_id": "c1", "candidates": [
        {"rank": i + 1, "t_start_sec": rep - 1.0, "t_end_sec": rep + 1.0,
         "representative_sec": rep, "timeline_revision": 1,
         "event_type": "SIGNAL", "score": score}
        for i, (rep, score) in enumerate(sorted(cands, key=lambda c: -c[1]))
    ]}]


def test_one_candidate_cannot_hit_two_events(): 
    """예측 하나가 사건 2건의 적중으로 중복 계수되지 않는다 (F7).

    tolerance 2.0 안에 사건 둘(10.0 · 11.0)이 있고 후보는 하나(10.5)다.
    1:1 배정이 없으면 recall 이 2/2 로 부풀어 오른다.
    """
    out = candidate.score(_preds((10.5, 1.0)), _gt_two_events(10.0, 11.0))
    assert out["n_events"] == 2
    assert out["recall_at"]["10"] == 0.5


def test_assignment_finds_the_maximum_number_of_hits():
    """배정이 최대 적중을 찾는다 — 사건 순서·rank 순서에 지지 않는다.

    EB(13.0)는 후보 11.5 하고만 맞고, EA(10.0)는 11.5·10.0 둘 다와 맞는다.
    EA 가 rank 1 인 11.5 를 먼저 집어 삼키면 EB 가 굶어 1/2 이 된다.
    맞는 답은 EA←10.0 · EB←11.5 로 2/2 다.

    중복 계수를 막는 코드(F7)를 탐욕 배정으로 짜면 이 테스트가 깨진다.
    지금은 1:1 배정 자체가 없어 통과하므로, 이 테스트는 잘못된 고침을
    막는 가드다.
    """
    out = candidate.score(_preds((11.5, 1.0), (10.0, 0.9)),
                          _gt_two_events(10.0, 13.0))
    assert out["recall_at"]["10"] == 1.0


def test_by_type_recall_uses_the_same_assignment():
    """유형별 집계도 같은 배정을 쓴다 — 전체와 어긋나면 둘 중 하나가 거짓이다."""
    out = candidate.score(_preds((10.5, 1.0)), _gt_two_events(10.0, 11.0))
    assert out["by_type"]["SIGNAL"]["recall_at"]["10"] == 0.5
    assert out["by_type"]["SIGNAL"]["n"] == 2


def _gt_ordered(pairs):
    """(event_id, onset) 순서를 그대로 정답지 줄 순서로 쓴다."""
    return {"items": [{"clip_id": "c1", "targets": [
        {"event_id": eid, "scoring": "INCLUDED",
         "violation_type": "SIGNAL", "t_onset_sec": onset}
        for eid, onset in pairs]}]}


def test_error_metrics_do_not_depend_on_gt_line_order():
    """정답지 줄 순서를 바꿔도 모든 지표가 같아야 한다.

    최대 매칭은 크기만 유일하고 어느 쌍으로 맺는지는 유일하지 않다.
    recall 은 크기만 쓰므로 순서 무관이지만 onset_error_sec·containment_rate
    는 선택된 쌍에 의존한다 — 배정 순서가 정답지 줄 순서를 타면
    같은 예측·같은 사건인데 containment 가 0.0 ↔ 1.0 으로 뒤집힌다.
    """
    pred = _preds((10.0, 1.0), (10.5, 0.9))
    a = candidate.score(pred, _gt_ordered([("EA", 10.0), ("EB", 10.5)]))
    b = candidate.score(pred, _gt_ordered([("EB", 10.5), ("EA", 10.0)]))
    assert a["recall_at"] == b["recall_at"]
    assert a["onset_error_sec"] == b["onset_error_sec"]
    assert a["containment_rate"] == b["containment_rate"]


def test_assignment_prefers_the_closer_candidate_for_each_event():
    """배정이 자유로울 때는 오차가 작은 쪽으로 붙는다.

    크기가 같은 최대 매칭이 여럿이면 어느 것을 골라도 recall 은 같지만,
    아무거나 고르면 onset_error_sec 가 실제보다 나쁘게 나온다.
    """
    out = candidate.score(_preds((10.0, 1.0), (10.5, 0.9)),
                          _gt_ordered([("EA", 10.0), ("EB", 10.5)]))
    assert out["recall_at"]["10"] == 1.0
    assert out["onset_error_sec"]["mean"] == 0.0
    assert out["containment_rate"] == 1.0


def test_duplicate_clip_id_items_share_one_assignment():
    """같은 clip_id 가 GT 항목 두 개로 쪼개져 있어도 후보는 한 번만 쓰인다.

    클립별로 배정하지 않고 항목별로 배정하면 _assign 이 두 번 따로 돌아
    같은 후보가 양쪽에서 적중으로 세어진다 — F7 이 막으려던 바로 그것이다.
    """
    gt = {"items": [
        {"clip_id": "c1", "targets": [
            {"event_id": "A", "scoring": "INCLUDED",
             "violation_type": "SIGNAL", "t_onset_sec": 10.0}]},
        {"clip_id": "c1", "targets": [
            {"event_id": "B", "scoring": "INCLUDED",
             "violation_type": "SIGNAL", "t_onset_sec": 10.5}]},
    ]}
    out = candidate.score(_preds((10.2, 1.0)), gt)
    assert out["n_events"] == 2
    assert out["recall_at"]["10"] == 0.5


def test_types_with_no_events_are_named_in_coverage():
    """by_type 에 키가 없는 유형은 「측정하지 않았다」는 뜻이다.

    키가 없는 것과 0점인 것을 결과 파일만 보고 구분할 수 없으면, baseline
    4종 중 1종을 못 쟀다는 사실이 조용히 사라진다 (B tier 의 안전모).
    """
    out = candidate.score(_preds((10.0, 1.0)), _gt_ordered([("EA", 10.0)]))
    assert "SIGNAL" in out["by_type"]
    assert "NO_EVENTS_FOR_TYPE" in out["coverage"]
    assert "MOTORCYCLE_HELMET_NON_USE" in out["coverage"]


# --- 시간과 유형을 갈라 잰다 (멘토 피드백 2026-09-20) ---
#
# 「장면의 '시간을 맞춘 것'과 '유형이 맞는지' 는 구분해서 평가해주세요.」
#
# recall_at 은 유형과 시간이 **둘 다** 맞아야 적중이라, 「순간은 정확히
# 찾았는데 신호위반을 중앙선침범이라 불렀다」와 「아예 못 찾았다」가 똑같이
# 0 으로 나온다. 둘은 고쳐야 할 곳이 완전히 다르다.


def test_right_moment_wrong_type_is_not_the_same_as_finding_nothing():
    out = candidate.score(_pred(rep=100.5, start=100.0, end=101.0,
                                event_type="CENTER_LINE_CROSSING"),
                          _gt(100.0, violation_type="SIGNAL"))

    assert out["recall_at"]["1"] == 0.0            # 합산 지표는 여전히 0
    assert out["localization_recall_at"]["1"] == 1.0
    assert out["type_accuracy_given_localized"] == 0.0


def test_right_moment_right_type_scores_on_both_axes():
    out = candidate.score(_pred(rep=100.5, start=100.0, end=101.0),
                          _gt(100.0))

    assert out["recall_at"]["1"] == 1.0
    assert out["localization_recall_at"]["1"] == 1.0
    assert out["type_accuracy_given_localized"] == 1.0


def test_finding_nothing_leaves_the_type_axis_null_not_zero():
    """시간을 못 맞혔으면 유형 정확도는 「0점」이 아니라 「잰 적 없음」이다."""
    out = candidate.score(_pred(rep=500.0, start=490.0, end=510.0),
                          _gt(100.0))

    assert out["recall_at"]["1"] == 0.0
    assert out["localization_recall_at"]["1"] == 0.0
    assert out["type_accuracy_given_localized"] is None
    assert "NO_LOCALIZED_EVENTS" in out["coverage"]


def test_localization_recall_is_never_below_recall():
    """시간만 맞으면 되는 쪽이 더 느슨하다. 뒤집히면 배정이 잘못된 것이다."""
    gt = {"items": [{"clip_id": "c1", "targets": [
        {"event_id": "E1", "scoring": "INCLUDED",
         "violation_type": "SIGNAL", "t_onset_sec": 10.0},
        {"event_id": "E2", "scoring": "INCLUDED",
         "violation_type": "CENTER_LINE_CROSSING", "t_onset_sec": 20.0},
    ]}]}
    pred = [{"clip_id": "c1", "candidates": [
        {"rank": 1, "t_start_sec": 9.0, "t_end_sec": 11.0, "representative_sec": 10.2,
         "timeline_revision": 1, "event_type": "SIGNAL", "score": 0.9},
        {"rank": 2, "t_start_sec": 19.0, "t_end_sec": 21.0, "representative_sec": 20.4,
         "timeline_revision": 1, "event_type": "SIGNAL", "score": 0.5},
    ]}]
    out = candidate.score(pred, gt)

    assert out["recall_at"]["3"] == 0.5               # E2 는 유형이 틀렸다
    assert out["localization_recall_at"]["3"] == 1.0  # 두 순간 다 찾았다
    assert out["type_accuracy_given_localized"] == 0.5


def test_a_matching_type_wins_over_a_mistyped_candidate_at_the_same_distance():
    """같은 거리면 유형이 맞는 후보에 붙인다 — 아니면 유형 정확도가 배정 운에 휘둘린다."""
    pred = [{"clip_id": "c1", "candidates": [
        {"rank": 1, "t_start_sec": 9.0, "t_end_sec": 11.0, "representative_sec": 10.5,
         "timeline_revision": 1, "event_type": "CENTER_LINE_CROSSING", "score": 0.9},
        {"rank": 2, "t_start_sec": 9.0, "t_end_sec": 11.0, "representative_sec": 10.5,
         "timeline_revision": 1, "event_type": "SIGNAL", "score": 0.5},
    ]}]
    out = candidate.score(pred, _gt(10.0, violation_type="SIGNAL"))

    assert out["localization_recall_at"]["3"] == 1.0
    assert out["type_accuracy_given_localized"] == 1.0


def test_not_run_keeps_the_new_axes(ks=(1, 3, 10)):
    block = candidate.not_run("NOT_RUN — 테스트")
    assert block["localization_recall_at"] == {"1": None, "3": None, "10": None}
    assert block["type_accuracy_given_localized"] is None


# --- 신뢰구간 (2026-09-21) ---
#
# B tier 채점 대상 사건이 10건이고 by_type 은 유형당 2~6건이다.
# 「Recall 0.5」가 실제로는 0.24~0.76 인데 결과 파일이 그걸 말하지 않으면
# 사람들이 소수점을 믿는다.


def test_recall_carries_its_interval():
    out = candidate.score(_pred(rep=100.5, start=100.0, end=101.0), _gt(100.0))

    lo, hi = out["recall_at_ci95"]["1"]
    assert hi == 1.0
    assert lo < 1.0, "사건 1건으로 「확실히 100%」라고 말하면 안 된다"


def test_no_events_leaves_the_interval_null_not_zero():
    gt = {"items": [{"clip_id": "c1", "targets": []}]}
    out = candidate.score(_pred(rep=1.0, start=0.0, end=2.0), gt)

    assert out["recall_at"]["1"] is None
    assert out["recall_at_ci95"]["1"] is None


def test_the_localization_axis_carries_an_interval_too():
    out = candidate.score(_pred(rep=100.5, start=100.0, end=101.0,
                                event_type="CENTER_LINE_CROSSING"),
                          _gt(100.0, violation_type="SIGNAL"))

    assert out["localization_recall_at_ci95"]["1"] is not None
    assert out["type_accuracy_given_localized_ci95"] is not None


def test_type_accuracy_interval_is_null_when_nothing_was_localized():
    out = candidate.score(_pred(rep=500.0, start=490.0, end=510.0), _gt(100.0))

    assert out["type_accuracy_given_localized"] is None
    assert out["type_accuracy_given_localized_ci95"] is None


def test_by_type_carries_intervals_because_that_is_where_n_is_smallest():
    """유형당 사건이 2건이면 recall 값이 사실상 아무것도 말하지 않는다."""
    gt = {"items": [{"clip_id": "c1", "targets": [
        {"event_id": "E1", "scoring": "INCLUDED",
         "violation_type": "SIGNAL", "t_onset_sec": 10.0},
        {"event_id": "E2", "scoring": "INCLUDED",
         "violation_type": "SIGNAL", "t_onset_sec": 40.0},
    ]}]}
    pred = [{"clip_id": "c1", "candidates": [
        {"rank": 1, "t_start_sec": 9.0, "t_end_sec": 11.0, "representative_sec": 10.2,
         "timeline_revision": 1, "event_type": "SIGNAL", "score": 0.9},
    ]}]
    out = candidate.score(pred, gt)

    slot = out["by_type"]["SIGNAL"]
    assert slot["recall_at"]["3"] == 0.5
    lo, hi = slot["recall_at_ci95"]["3"]
    assert hi - lo > 0.8, "2건짜리 구간은 거의 전 구간이어야 한다"


def test_containment_rate_carries_an_interval():
    out = candidate.score(_pred(rep=100.5, start=100.0, end=101.0), _gt(100.0))
    assert out["containment_rate_ci95"] is not None


def test_not_run_keeps_every_interval_key():
    block = candidate.not_run("NOT_RUN — 테스트")
    assert block["recall_at_ci95"] == {"1": None, "3": None, "10": None}
    assert block["localization_recall_at_ci95"] == {"1": None, "3": None, "10": None}
    assert block["type_accuracy_given_localized_ci95"] is None
    assert block["containment_rate_ci95"] is None
