from eval.scorers import classification, plate

GT = {"meta": {"gt_version": "g1", "tier": "A", "stage": "classification"},
      "items": [
          {"sequence_id": "S1", "label": "SIGNAL", "target_bbox": [0, 0, 10, 10],
           "distractor_count": 1, "source_tier": "A"},
          {"sequence_id": "S2", "label": "CENTER_LINE_CROSSING", "target_bbox": None,
           "distractor_count": 0, "source_tier": "A"},
          {"sequence_id": "S3", "label": "NONE", "target_bbox": None,
           "distractor_count": 0, "source_tier": "B"},
      ]}


def test_perfect_prediction_scores_one():
    norm = [{"sequence_id": "S1", "predicted": "SIGNAL", "target_bbox": [0, 0, 10, 10]},
            {"sequence_id": "S2", "predicted": "CENTER_LINE_CROSSING", "target_bbox": None},
            {"sequence_id": "S3", "predicted": "NONE", "target_bbox": None}]
    r = classification.score(norm, GT)
    assert r["recall_macro"] == 1.0
    assert r["precision_macro"] == 1.0


def test_confusion_matrix_is_five_by_five():
    norm = [{"sequence_id": "S1", "predicted": "SIGNAL", "target_bbox": None},
            {"sequence_id": "S2", "predicted": "SIGNAL", "target_bbox": None},
            {"sequence_id": "S3", "predicted": "NONE", "target_bbox": None}]
    r = classification.score(norm, GT)
    assert len(r["confusion"]) == 5
    assert all(len(row) == 5 for row in r["confusion"].values())
    assert r["confusion"]["CENTER_LINE_CROSSING"]["SIGNAL"] == 1


def test_target_correctness_is_null_when_no_gt_bbox():
    norm = [{"sequence_id": "S2", "predicted": "CENTER_LINE_CROSSING", "target_bbox": [1, 1, 2, 2]}]
    gt = {"meta": GT["meta"], "items": [GT["items"][1]]}
    r = classification.score(norm, gt)
    assert r["target_correctness"] is None


def test_plate_without_gt_reports_null_not_zero():
    r = plate.score([], None)
    assert r["exact_accuracy"] is None
    assert r["wrong_accept_rate"] is None
    assert r["abstention_recall"] is None
    assert "NO_C_TIER_DATA" in r["coverage"]


def test_plate_ignores_gt_items_v1_has_no_c_tier():
    # v1은 plate text GT가 없다 — GT에 items가 들어와도(향후 C tier
    # 연동 실수를 가정) 검증되지 않은 계산 경로를 타지 않고 그대로 null이다.
    gt = {"meta": {"gt_version": "g1"},
          "items": [{"sequence_id": "S1", "plate_text": "12가3456"}]}
    r = plate.score([], gt)
    assert r["exact_accuracy"] is None
    assert r["wrong_accept_rate"] is None
    assert r["abstention_recall"] is None
    assert "NO_C_TIER_DATA" in r["coverage"]


def test_out_of_enum_prediction_is_folded_into_none_not_dropped():
    # baseline enum 밖의 예측("GARBAGE")은 confusion에서 사라지지도,
    # NONE보다 유리하게 채점되지도 않는다 — NONE 열로 접혀 똑같이 미스로 잡힌다.
    gt = {"meta": {"gt_version": "g1"}, "items": [
        {"sequence_id": "S1", "label": "SIGNAL", "target_bbox": None},
        {"sequence_id": "S2", "label": "SIGNAL", "target_bbox": None},
        {"sequence_id": "S3", "label": "NONE", "target_bbox": None},
    ]}
    norm = [
        {"sequence_id": "S1", "predicted": "GARBAGE", "target_bbox": None},
        {"sequence_id": "S2", "predicted": "SIGNAL", "target_bbox": None},
        {"sequence_id": "S3", "predicted": "NONE", "target_bbox": None},
    ]
    r = classification.score(norm, gt)
    assert r["confusion"]["SIGNAL"]["NONE"] == 1
    assert r["n_invalid_predictions"] == 1
    assert "INVALID_PREDICTIONS" in r["coverage"]
    # 명시적으로 "NONE"이라고 예측했을 때와 정확히 같은 값이어야 한다 —
    # 쓰레기 라벨을 내면 정밀도가 부풀려지는 유인이 없어야 한다.
    assert r["precision_macro"] == 0.75
    assert r["recall_macro"] == 0.75


def test_invalid_gt_label_is_excluded_from_metrics_not_scored():
    # baseline enum 밖의 GT 라벨("BOGUS")은 진실을 지어낼 수 없으므로
    # 채점 대상에서 완전히 제외한다 — 나머지만으로 조용히 점수를 내지 않는다.
    gt = {"meta": {"gt_version": "g1"}, "items": [
        {"sequence_id": "S1", "label": "SIGNAL", "target_bbox": None},
        {"sequence_id": "S2", "label": "BOGUS", "target_bbox": None},
    ]}
    norm = [
        {"sequence_id": "S1", "predicted": "SIGNAL", "target_bbox": None},
        {"sequence_id": "S2", "predicted": "SIGNAL", "target_bbox": None},
    ]
    r = classification.score(norm, gt)
    assert r["n"] == 1
    assert r["n_invalid_gt_labels"] == 1
    assert "INVALID_GT_LABELS" in r["coverage"]
    assert sum(v for row in r["confusion"].values() for v in row.values()) == 1


def test_target_correctness_uses_iou_not_exact_equality():
    # bbox가 한 픽셀만 밀려도 완전 일치가 아니면 실패 처리되던 문제 —
    # IoU>=0.5인 근접 bbox는 correct로 잡혀야 한다.
    gt = {"meta": {"gt_version": "g1"}, "items": [
        {"sequence_id": "S1", "label": "SIGNAL", "target_bbox": [0, 0, 10, 10]},
    ]}
    norm = [{"sequence_id": "S1", "predicted": "SIGNAL", "target_bbox": [1, 1, 11, 11]}]
    r = classification.score(norm, gt)
    assert r["target_correctness"] == 1.0


def test_target_correctness_denominator_excludes_no_bbox_items():
    gt = {"meta": {"gt_version": "g1"}, "items": [
        {"sequence_id": "S1", "label": "SIGNAL", "target_bbox": [0, 0, 10, 10]},
        {"sequence_id": "S2", "label": "SIGNAL", "target_bbox": [0, 0, 10, 10]},
        {"sequence_id": "S3", "label": "SIGNAL", "target_bbox": None},
    ]}
    norm = [
        {"sequence_id": "S1", "predicted": "SIGNAL", "target_bbox": [0, 0, 10, 10]},  # 적중
        {"sequence_id": "S2", "predicted": "SIGNAL", "target_bbox": [50, 50, 60, 60]},  # 미스
        {"sequence_id": "S3", "predicted": "SIGNAL", "target_bbox": [5, 5, 6, 6]},  # GT bbox 없음 → 분모 제외
    ]
    r = classification.score(norm, gt)
    assert r["target_correctness"] == 0.5
