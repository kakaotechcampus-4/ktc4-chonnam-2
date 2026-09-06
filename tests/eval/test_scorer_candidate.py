from eval import manifests_io
from eval.runners import registry, normalize
from eval.scorers import candidate


def _run(impl_name):
    raw = registry.get(impl_name)({"manifest": "b_youtube", "stage": "candidate"})
    return normalize.normalize_candidate(raw)


def test_always_correct_gets_perfect_recall():
    gt = manifests_io.load_gt("b_youtube", "candidate")
    r = candidate.score(_run("fake:always_correct"), gt)
    assert r["recall_at"]["1"] == 1.0
    assert r["recall_at"]["3"] == 1.0
    assert r["fp_per_clip"] == 0.0


def test_always_wrong_gets_zero_recall_and_positive_fp():
    gt = manifests_io.load_gt("b_youtube", "candidate")
    r = candidate.score(_run("fake:always_wrong"), gt)
    assert r["recall_at"]["3"] == 0.0
    assert r["fp_per_clip"] > 0.0
    # 적중이 하나도 없으므로 span_error_sec 은 0 이 아니라 null 이어야 한다
    # (측정했는데 0인 것과 잴 수 없는 것을 구분한다).
    assert r["span_error_sec"]["mean"] is None
    assert r["span_error_sec"]["median"] is None


def test_boundary_excluded_targets_are_not_counted():
    gt = manifests_io.load_gt("b_youtube", "candidate")
    n_included = sum(1 for i in gt["items"] for t in i["targets"]
                     if t.get("scoring") != "BOUNDARY_EXCLUDED")
    r = candidate.score(_run("fake:always_correct"), gt)
    assert r["n_events"] == n_included
    # 재계산값과 별개로 리터럴 값도 고정한다 — C47(BOUNDARY_EXCLUDED) 처리
    # 회귀를 간접적으로(fp_per_clip 등을 통해서)가 아니라 직접 잡는다.
    assert r["n_events"] == 4
    assert r["n_negative_clips"] == 50


def test_by_type_breakdown_lists_only_present_types():
    gt = manifests_io.load_gt("b_youtube", "candidate")
    r = candidate.score(_run("fake:always_correct"), gt)
    assert set(r["by_type"]) == {"SIGNAL", "SOLID_LINE_LANE_CHANGE"}
    # 키 집합뿐 아니라 값도 고정한다 — by_type 분모가 전체 사건 수로 새는
    # 회귀(예: 전역 n_events 를 나눠 쓰는 버그)를 여기서 잡는다.
    assert r["by_type"]["SIGNAL"]["n"] == 2
    assert r["by_type"]["SIGNAL"]["recall_at"]["1"] == 1.0


def test_zero_span_predictions_report_null_span_error():
    gt = {"meta": {"coverage": {}},
          "items": [{"clip_id": "C0", "source_video_id": "V", "targets": [
              {"event_id": "E", "violation_type": "SIGNAL", "t_start_sec": 1.0,
               "t_end_sec": 2.0, "t_onset_sec": 1.5, "scoring": "INCLUDED"}]}]}
    norm = [{"clip_id": "C0", "candidates": [
        {"rank": 1, "t_start_sec": 0.0, "t_end_sec": 0.0,
         "event_type": "SIGNAL", "score": 1.0}]}]
    r = candidate.score(norm, gt)
    assert r["span_error_sec"]["mean"] is None


def test_wrong_span_right_type_is_a_miss():
    # 유형은 맞지만 구간이 전혀 겹치지 않는 예측 — and 를 or 로 잘못 바꾸면
    # 유형 일치만으로 적중 처리되어 이 테스트가 깨진다.
    gt = {"meta": {"coverage": {}},
          "items": [{"clip_id": "C0", "source_video_id": "V", "targets": [
              {"event_id": "E", "violation_type": "SIGNAL", "t_start_sec": 1.0,
               "t_end_sec": 2.0, "t_onset_sec": 1.5, "scoring": "INCLUDED"}]}]}
    norm = [{"clip_id": "C0", "candidates": [
        {"rank": 1, "t_start_sec": 10.0, "t_end_sec": 12.0,
         "event_type": "SIGNAL", "score": 1.0}]}]
    r = candidate.score(norm, gt)
    assert r["recall_at"]["3"] == 0.0


def test_wrong_type_right_span_is_a_miss():
    # 구간은 완전히 겹치지만 유형이 다른 예측 — and 를 or 로 잘못 바꾸면
    # 구간 일치만으로 적중 처리되어 이 테스트가 깨진다.
    gt = {"meta": {"coverage": {}},
          "items": [{"clip_id": "C0", "source_video_id": "V", "targets": [
              {"event_id": "E", "violation_type": "SIGNAL", "t_start_sec": 1.0,
               "t_end_sec": 2.0, "t_onset_sec": 1.5, "scoring": "INCLUDED"}]}]}
    norm = [{"clip_id": "C0", "candidates": [
        {"rank": 1, "t_start_sec": 1.0, "t_end_sec": 2.0,
         "event_type": "CENTER_LINE_CROSSING", "score": 1.0}]}]
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
         "event_type": "CENTER_LINE_CROSSING", "score": 1.0},
        {"rank": 2, "t_start_sec": 1.0, "t_end_sec": 2.0,
         "event_type": "SIGNAL", "score": 0.5},
    ]}]
    r = candidate.score(norm, gt)
    assert r["recall_at"]["1"] == 0.0
    assert r["recall_at"]["3"] == 1.0


def test_iou_disjoint_identical_and_zero_length():
    assert candidate._iou(0.0, 1.0, 5.0, 6.0) == 0.0
    assert candidate._iou(1.0, 2.0, 1.0, 2.0) == 1.0
    assert candidate._iou(0.0, 0.0, 0.0, 0.0) == 0.0


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
