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
