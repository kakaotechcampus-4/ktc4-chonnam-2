import re

import pytest

from eval.runners import normalize


def test_normalize_candidate_passes_through_shape():
    raw = [{"clip_id": "C1",
            "candidates": [{"rank": 1, "t_start_sec": 1.0, "t_end_sec": 2.0,
                            "representative_sec": 1.5, "timeline_revision": None,
                            "event_type": "SIGNAL", "score": 0.9}]}]
    out = normalize.normalize_candidate(raw)
    assert out == raw


def test_normalize_candidate_sorts_and_renumbers_rank():
    raw = [{"clip_id": "C1",
            "candidates": [{"rank": 9, "t_start_sec": 3.0, "t_end_sec": 4.0,
                            "representative_sec": 3.5,
                            "event_type": "SIGNAL", "score": 0.2},
                           {"rank": 4, "t_start_sec": 1.0, "t_end_sec": 2.0,
                            "representative_sec": 1.5,
                            "event_type": "SIGNAL", "score": 0.8}]}]
    out = normalize.normalize_candidate(raw)
    ranks = [c["rank"] for c in out[0]["candidates"]]
    assert ranks == [1, 2]
    assert out[0]["candidates"][0]["score"] == 0.8


def test_normalize_classification_shape():
    raw = [{"sequence_id": "S1", "predicted": "SIGNAL", "target_bbox": [1, 2, 3, 4]}]
    out = normalize.normalize_classification(raw)
    assert out[0]["sequence_id"] == "S1"
    assert out[0]["predicted"] == "SIGNAL"
    assert out[0]["target_bbox"] == [1, 2, 3, 4]


def test_normalize_classification_missing_target_bbox_is_none():
    raw = [{"sequence_id": "S1", "predicted": "SIGNAL"}]
    out = normalize.normalize_classification(raw)
    assert out[0]["target_bbox"] is None


def test_normalize_candidate_empty_candidates_list_is_valid():
    raw = [{"clip_id": "C1", "candidates": []}]
    out = normalize.normalize_candidate(raw)
    assert out == [{"clip_id": "C1", "candidates": []}]


def test_normalize_candidate_multi_item():
    raw = [{"clip_id": "C1",
            "candidates": [{"rank": 1, "t_start_sec": 1.0, "t_end_sec": 2.0,
                            "representative_sec": 1.5,
                            "event_type": "SIGNAL", "score": 0.9}]},
           {"clip_id": "C2", "candidates": []}]
    out = normalize.normalize_candidate(raw)
    assert len(out) == 2
    assert out[0]["clip_id"] == "C1"
    assert out[1] == {"clip_id": "C2", "candidates": []}


def test_normalize_candidate_raw_entry_not_dict_raises():
    with pytest.raises(ValueError, match=re.escape("normalize_candidate: raw[0]가 dict 가 아님")):
        normalize.normalize_candidate(["not-a-dict"])


def test_normalize_candidate_missing_clip_id_raises():
    raw = [{"candidates": []}]
    with pytest.raises(ValueError, match=re.escape("normalize_candidate: raw[0]에 필드 'clip_id' 없음")):
        normalize.normalize_candidate(raw)


def test_normalize_candidate_missing_candidates_raises():
    raw = [{"clip_id": "C1"}]
    with pytest.raises(ValueError, match=re.escape("normalize_candidate: raw[0]에 필드 'candidates' 없음")):
        normalize.normalize_candidate(raw)


def test_normalize_candidate_candidate_missing_score_raises():
    raw = [{"clip_id": "C1",
            "candidates": [{"t_start_sec": 1.0, "t_end_sec": 2.0, "event_type": "SIGNAL"}]}]
    with pytest.raises(ValueError,
                        match=re.escape("normalize_candidate: raw[0].candidates[0]에 필드 'score' 없음")):
        normalize.normalize_candidate(raw)


def test_normalize_candidate_candidate_missing_event_type_raises():
    raw = [{"clip_id": "C1",
            "candidates": [{"t_start_sec": 1.0, "t_end_sec": 2.0, "score": 0.9}]}]
    with pytest.raises(ValueError,
                        match=re.escape("normalize_candidate: raw[0].candidates[0]에 필드 'event_type' 없음")):
        normalize.normalize_candidate(raw)


def test_normalize_classification_raw_entry_not_dict_raises():
    with pytest.raises(ValueError,
                        match=re.escape("normalize_classification: raw[0]가 dict 가 아님")):
        normalize.normalize_classification(["not-a-dict"])


def test_normalize_classification_missing_sequence_id_raises():
    raw = [{"predicted": "SIGNAL"}]
    with pytest.raises(ValueError,
                        match=re.escape("normalize_classification: raw[0]에 필드 'sequence_id' 없음")):
        normalize.normalize_classification(raw)


def test_normalize_classification_missing_predicted_raises():
    raw = [{"sequence_id": "S1"}]
    with pytest.raises(ValueError,
                        match=re.escape("normalize_classification: raw[0]에 필드 'predicted' 없음")):
        normalize.normalize_classification(raw)


def test_normalize_plate_extracts_fields():
    raw = [{"readout_id": "r1", "scenario_id": "s1",
            "input_ref": {"source_profile": "p1"},
            "observation": {"value": "12가3456", "status": "OK"},
            "abstained": False}]
    out = normalize.normalize_plate(raw)
    assert out == [{"readout_id": "r1", "scenario_id": "s1", "source_profile": "p1",
                     "value": "12가3456", "status": "OK", "abstained": False,
                     "abstain_reason": None, "target_association_status": None}]


def test_normalize_plate_optional_fields_default_to_none_when_absent():
    """scenario_id·input_ref·observation.value·observation.status 는 선택 필드다."""
    raw = [{"readout_id": "r1", "observation": {}, "abstained": True}]
    out = normalize.normalize_plate(raw)
    assert out == [{"readout_id": "r1", "scenario_id": None, "source_profile": None,
                     "value": None, "status": None, "abstained": True,
                     "abstain_reason": None, "target_association_status": None}]


def test_normalize_plate_raw_entry_not_dict_raises():
    with pytest.raises(ValueError, match=re.escape("normalize_plate: raw[0]가 dict 가 아님")):
        normalize.normalize_plate(["not-a-dict"])


def test_normalize_plate_missing_readout_id_raises():
    raw = [{"observation": {}, "abstained": False}]
    with pytest.raises(ValueError,
                        match=re.escape("normalize_plate: raw[0]에 필드 'readout_id' 없음")):
        normalize.normalize_plate(raw)


def test_normalize_plate_missing_observation_raises():
    raw = [{"readout_id": "r1", "abstained": False}]
    with pytest.raises(ValueError,
                        match=re.escape("normalize_plate: raw[0]에 필드 'observation' 없음")):
        normalize.normalize_plate(raw)


def test_normalize_plate_missing_abstained_raises():
    raw = [{"readout_id": "r1", "observation": {}}]
    with pytest.raises(ValueError,
                        match=re.escape("normalize_plate: raw[0]에 필드 'abstained' 없음")):
        normalize.normalize_plate(raw)


# --- 판단 근거 보존 (멘토 피드백 2026-09-20) ---
#
# 「각 LLM 판단 결과를 저장할 때 reasoning도 저장하시면 좋습니다. 결과만
# 있을 때에는 모델의 판단이 이해가 안가는 경우가 있거든요.」
#
# abstain_reason 은 plate-readout/v1.3 이 이미 두고 있고(§abstained,
# authoritative), 예측 파일 raw 에도 그대로 들어온다. normalize 가 버려서
# 채점 결과까지 못 올라오던 것을 잇는다.


def test_normalize_plate_keeps_the_abstain_reason():
    raw = [{"readout_id": "r1", "observation": {"value": None, "status": "NEEDS_REVIEW"},
            "abstained": True, "abstain_reason": "FRAME_DISAGREEMENT"}]
    out = normalize.normalize_plate(raw)
    assert out[0]["abstain_reason"] == "FRAME_DISAGREEMENT"


def test_normalize_plate_keeps_the_target_association_status():
    """어느 차를 읽었다고 판단했는지도 판단 근거다."""
    raw = [{"readout_id": "r1", "observation": {}, "abstained": False,
            "target_association": {"status": "LOW_CONFIDENCE"}}]
    out = normalize.normalize_plate(raw)
    assert out[0]["target_association_status"] == "LOW_CONFIDENCE"


def test_normalize_plate_missing_reason_is_none_not_a_made_up_value():
    raw = [{"readout_id": "r1", "observation": {}, "abstained": True}]
    out = normalize.normalize_plate(raw)
    assert out[0]["abstain_reason"] is None
    assert out[0]["target_association_status"] is None
