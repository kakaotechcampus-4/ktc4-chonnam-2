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
    # F6 해소로 plate.score 는 이제 GT 가 있으면 실제로 채점한다. GT 자체가
    # 없는 경우(None)에는 여전히 0 이 아니라 null + 사유다 — 데이터가 없는
    # 것과 성능이 나쁜 것은 다른 사실이다.
    r = plate.score([], None)
    assert r["exact_accuracy"] is None
    assert r["wrong_accept_rate"] is None
    assert r["abstention_recall"] is None
    assert "NO_PLATE_GT" in r["coverage"]


def test_plate_with_no_predictions_at_all_reports_null_not_zero():
    # v1은 plate GT가 없어 이 함수가 gt를 통째로 무시했었다. 지금은 GT를
    # 실제로 쓰므로(F6 해소), gt 형식은 새 계약(readout_id/legibility)을
    # 따르되 예측이 아예 하나도 없으면(normalized=[]) 채점 대상 0건을
    # null + 사유로 정직하게 보고해야 한다. 예측이 비어 있으므로
    # `for pred in normalized` 본문 자체가 돌지 않는다 — GT 에 없는
    # readout_id 를 건너뛰는 경로는 test_scorer_plate.py 쪽에서 별도로
    # 검증한다.
    gt = {"meta": {"gt_version": "g1"},
          "items": [{"readout_id": "r1", "legibility": "READABLE",
                     "true_text": "12가3456"}]}
    r = plate.score([], gt)
    assert r["exact_accuracy"] is None
    assert r["wrong_accept_rate"] is None
    assert r["abstention_recall"] is None
    assert r["n"] == 0
    assert "NO_SCORED_READOUTS" in r["coverage"]


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


def test_malformed_predicted_bbox_is_counted_not_silently_zero():
    """형식이 깨진 예측 bbox 를 「틀렸다」와 섞지 않는다 (F11).

    _iou_2d 는 길이가 4가 아니면 조용히 0.0 을 낸다. 그러면 「대상 차량을
    잘못 짚었다」와 「bbox 가 망가져서 잴 수 없었다」가 같은 실점이 된다.
    라벨 쪽 n_invalid_gt_labels 와 같은 모양의 카운터로 드러낸다.
    """
    norm = [{"sequence_id": "S1", "predicted": "SIGNAL", "target_bbox": [0, 0, 10]}]
    gt = {"meta": GT["meta"], "items": [GT["items"][0]]}
    r = classification.score(norm, gt)
    assert r["n_invalid_bboxes"] == 1
    assert r["target_correctness"] == 0.0
    assert "INVALID_BBOXES" in r["coverage"]


def test_wellformed_but_wrong_bbox_is_not_counted_as_malformed():
    """틀린 bbox 는 형식 오류가 아니다 — 둘을 가르는 게 이 카운터의 목적이다."""
    norm = [{"sequence_id": "S1", "predicted": "SIGNAL", "target_bbox": [90, 90, 99, 99]}]
    gt = {"meta": GT["meta"], "items": [GT["items"][0]]}
    r = classification.score(norm, gt)
    assert r["n_invalid_bboxes"] == 0
    assert r["target_correctness"] == 0.0


def test_not_run_block_carries_the_invalid_bbox_key():
    """돌지 않은 stage 도 키를 빼지 않는다 (§7 규율)."""
    assert classification.not_run("NOT_RUN — x")["n_invalid_bboxes"] is None


def test_excluded_denominators_are_explained_in_coverage():
    """분모에서 뺀 항목을 결과가 스스로 말해야 한다 (§7 규율 3).

    n 은 150인데 target_correctness 분모가 115, by_condition 합이 120이면
    결과 파일만 보고는 그 차이를 복원할 수 없다. 지표가 전부 null 이
    아니어도 「무엇을 왜 뺐는가」는 실린다.
    """
    gt = {"meta": GT["meta"], "items": [
        {"sequence_id": "A1", "label": "SIGNAL", "target_bbox": [0, 0, 10, 10],
         "condition": {"day_night": "주간"}, "source_tier": "A"},
        {"sequence_id": "B1", "label": "NONE", "target_bbox": None,
         "condition": None, "source_tier": "B"},
        {"sequence_id": "B2", "label": "NONE", "target_bbox": None,
         "condition": None, "source_tier": "B"},
    ]}
    norm = [{"sequence_id": "A1", "predicted": "SIGNAL", "target_bbox": [0, 0, 10, 10]},
            {"sequence_id": "B1", "predicted": "NONE", "target_bbox": None},
            {"sequence_id": "B2", "predicted": "NONE", "target_bbox": None}]
    r = classification.score(norm, gt)

    assert r["n"] == 3
    assert "NO_TARGET_BBOX_GT" in r["coverage"]
    assert "NO_CONDITION" in r["coverage"]
    # 몇 건을 뺐는지가 적혀야 복원된다.
    assert "2건" in r["coverage"]


def test_nothing_excluded_means_no_denominator_reason():
    """뺀 게 없으면 사유도 없다 — 없는 경고를 만들지 않는다."""
    gt = {"meta": GT["meta"], "items": [
        {"sequence_id": "A1", "label": "SIGNAL", "target_bbox": [0, 0, 10, 10],
         "condition": {"day_night": "주간"}, "source_tier": "A"}]}
    norm = [{"sequence_id": "A1", "predicted": "SIGNAL", "target_bbox": [0, 0, 10, 10]}]
    assert classification.score(norm, gt)["coverage"] is None


def test_inverted_predicted_bbox_is_counted_as_malformed():
    """넓이가 0 이하인 예측 bbox 는 IoU 가 구조적으로 0 이라 영원히 오답이다.

    GT 쪽에는 이 검사를 넣어 두고 예측 쪽에만 없으면, 「대상을 잘못 짚었다」와
    「bbox 가 망가졌다」가 다시 같은 0점으로 섞인다.
    """
    gt = {"meta": GT["meta"], "items": [GT["items"][0]]}
    for box in ([10, 0, 10, 20], [10, 10, 5, 5]):
        r = classification.score(
            [{"sequence_id": "S1", "predicted": "SIGNAL", "target_bbox": box}], gt)
        assert r["n_invalid_bboxes"] == 1, box
        assert "INVALID_BBOXES" in r["coverage"], box
