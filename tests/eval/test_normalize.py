from eval.runners import normalize


def test_normalize_candidate_passes_through_shape():
    raw = [{"clip_id": "C1",
            "candidates": [{"rank": 1, "t_start_sec": 1.0, "t_end_sec": 2.0,
                            "event_type": "SIGNAL", "score": 0.9}]}]
    out = normalize.normalize_candidate(raw)
    assert out == raw


def test_normalize_candidate_sorts_and_renumbers_rank():
    raw = [{"clip_id": "C1",
            "candidates": [{"rank": 9, "t_start_sec": 3.0, "t_end_sec": 4.0,
                            "event_type": "SIGNAL", "score": 0.2},
                           {"rank": 4, "t_start_sec": 1.0, "t_end_sec": 2.0,
                            "event_type": "SIGNAL", "score": 0.8}]}]
    out = normalize.normalize_candidate(raw)
    ranks = [c["rank"] for c in out[0]["candidates"]]
    assert ranks == [1, 2]
    assert out[0]["candidates"][0]["score"] == 0.8


def test_from_mock_pack_reads_team_fixture_shape():
    obj = {"scenario_id": "scenario_happy_001",
           "prediction": {"candidate_id": "cand_h001", "rank": 1,
                          "visual_event_type": "SOLID_LINE_LANE_CHANGE",
                          "plate_value": "12가 3476",
                          "occurred_at": "2026-08-24T18:31:30+09:00"}}
    out = normalize.from_mock_pack(obj)
    assert len(out) == 1
    assert out[0]["clip_id"] == "scenario_happy_001"
    c = out[0]["candidates"][0]
    assert c["rank"] == 1
    assert c["event_type"] == "SOLID_LINE_LANE_CHANGE"


def test_normalize_classification_shape():
    raw = [{"sequence_id": "S1", "predicted": "SIGNAL", "target_bbox": [1, 2, 3, 4]}]
    out = normalize.normalize_classification(raw)
    assert out[0]["sequence_id"] == "S1"
    assert out[0]["predicted"] == "SIGNAL"
    assert out[0]["target_bbox"] == [1, 2, 3, 4]
