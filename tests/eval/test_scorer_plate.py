"""plate 교차표.

정답 판정은 abstained × GT legibility 다.

                 GT READABLE                    GT UNREADABLE
 abstained=false exact_match: value==true_text  wrong_accept
 abstained=true  놓친 판독                       abstention_recall 적중
"""
import pytest

from eval.scorers import plate


def _gt(*items):
    return {"meta": {"gt_version": "mp1"}, "items": list(items)}


def _truth(readout_id, legibility, true_text=None):
    out = {"readout_id": readout_id, "legibility": legibility,
           "derived_from_pack": True}
    if true_text is not None:
        out["true_text"] = true_text
    return out


def _pred(readout_id, value, abstained):
    return {"readout_id": readout_id, "scenario_id": "s", "source_profile": "p",
            "value": value, "status": "OK", "abstained": abstained}


def test_reading_a_readable_plate_correctly_is_an_exact_match():
    out = plate.score([_pred("r1", "12가3456", False)],
                      _gt(_truth("r1", "READABLE", "12가3456")))
    assert out["exact_accuracy"] == 1.0


def test_misreading_a_readable_plate_is_not_an_exact_match():
    out = plate.score([_pred("r1", "12가3457", False)],
                      _gt(_truth("r1", "READABLE", "12가3456")))
    assert out["exact_accuracy"] == 0.0


def test_abstaining_on_an_unreadable_plate_is_correct():
    """초판독의 abstain 은 실패가 아니라 정답이다."""
    out = plate.score([_pred("r1", "17나28??", True)],
                      _gt(_truth("r1", "UNREADABLE")))
    assert out["abstention_recall"] == 1.0
    assert out["wrong_accept_rate"] == 0.0


def test_confidently_reading_an_unreadable_plate_is_a_wrong_accept():
    """이 지표가 잡아야 할 오류다 — 판독 불가인데 확정값을 냈다."""
    out = plate.score([_pred("r1", "17나2867", False)],
                      _gt(_truth("r1", "UNREADABLE")))
    assert out["wrong_accept_rate"] == 1.0
    assert out["abstention_recall"] == 0.0


def test_prediction_with_unknown_readout_id_is_skipped_not_scored():
    """GT 에 없는 readout_id 로 온 예측은 채점 대상에서 조용히 빠져야 한다.

    KeyError 없이 건너뛰고, n 과 지표는 GT 와 매칭된 예측만 반영한다.
    """
    out = plate.score(
        [_pred("r1", "12가3456", False), _pred("unknown", "99하9999", False)],
        _gt(_truth("r1", "READABLE", "12가3456")),
    )
    assert out["n"] == 1
    assert out["exact_accuracy"] == 1.0


def test_no_gt_returns_null_not_zero():
    """데이터가 없는 것과 성능이 나쁜 것은 다른 사실이다."""
    out = plate.score([_pred("r1", "x", False)], None)
    assert out["exact_accuracy"] is None
    assert "NO_PLATE_GT" in out["coverage"]


def test_circularity_and_zero_numerator_are_written_into_coverage():
    """mock tier 에서 exact_match 는 구조상 만점이고 wrong_accept 는 분자가 0이다.

    이 두 사실이 결과 파일에 없으면 다음 사람이 숫자를 성능으로 읽는다.
    """
    out = plate.score(
        [_pred("r1", "12가3456", False), _pred("r2", "17나28??", True)],
        _gt(_truth("r1", "READABLE", "12가3456"), _truth("r2", "UNREADABLE")),
    )
    assert "순환" in out["coverage"]
    assert "분자" in out["coverage"]


# --- 기권만 하는 모델 (멘토 피드백 2026-09-20) ---
#
# 「번호판 판독은 기권만 하는 모델이 점수가 높을 수 있겠다는 생각이
# 드네요. 각 점수에 가중치를 잘 설정하셔야겠습니다.」
#
# 가중 합산 점수는 여기서 만들지 않는다 — 「기권 1건이 오답 몇 건 값이냐」는
# 제품 결정이지 채점기 결정이다. 대신 기권만 하면 반드시 나빠 보이는
# 숫자를 둬서, 세 숫자를 따로 떼어 읽을 수 없게 만든다.


def test_a_model_that_only_abstains_cannot_look_good():
    """읽을 수 있었는데 기권한 비율이 1.0 이어야 한다."""
    out = plate.score(
        [_pred("r1", None, True), _pred("r2", None, True), _pred("r3", None, True)],
        _gt(_truth("r1", "READABLE", "12가3456"),
            _truth("r2", "READABLE", "34나5678"),
            _truth("r3", "UNREADABLE")))

    # 기존 세 숫자는 여전히 「좋아」 보인다 — 그래서 이것이 필요했다
    assert out["wrong_accept_rate"] == 0.0
    assert out["abstention_recall"] == 1.0
    assert out["exact_accuracy"] is None

    assert out["readable_abstention_rate"] == 1.0
    assert out["n_readable"] == 2
    assert "ANSWERED_NOTHING" in out["coverage"]


def test_answering_every_readable_plate_leaves_the_abstention_rate_zero():
    out = plate.score(
        [_pred("r1", "12가3456", False), _pred("r2", "34나5678", False)],
        _gt(_truth("r1", "READABLE", "12가3456"),
            _truth("r2", "READABLE", "34나5678")))

    assert out["readable_abstention_rate"] == 0.0
    assert "ANSWERED_NOTHING" not in (out["coverage"] or "")


def test_partial_abstention_is_a_rate_not_a_flag():
    """절반만 기권한 모델과 전부 기권한 모델이 같아 보이면 안 된다."""
    out = plate.score(
        [_pred("r1", "12가3456", False), _pred("r2", None, True)],
        _gt(_truth("r1", "READABLE", "12가3456"),
            _truth("r2", "READABLE", "34나5678")))

    assert out["readable_abstention_rate"] == 0.5
    assert out["exact_accuracy"] == 1.0        # 답한 것만 놓고는 만점이다
    assert "ANSWERED_NOTHING" not in (out["coverage"] or "")


def test_exact_accuracy_null_says_which_kind_of_null_it_is():
    """「정답지가 없다」와 「모델이 답을 안 했다」는 다른 사실이다."""
    no_readable = plate.score([_pred("r1", None, True)],
                              _gt(_truth("r1", "UNREADABLE")))
    refused = plate.score([_pred("r1", None, True)],
                          _gt(_truth("r1", "READABLE", "12가3456")))

    assert no_readable["exact_accuracy"] is None
    assert refused["exact_accuracy"] is None
    assert no_readable["coverage"] != refused["coverage"]
    assert "NO_READABLE_GT" in no_readable["coverage"]
    assert "ANSWERED_NOTHING" in refused["coverage"]
    assert no_readable["readable_abstention_rate"] is None   # 분모가 0이다


def test_not_run_keeps_the_new_keys():
    """키가 사라지면 결과 파일을 기계로 비교할 수 없다."""
    block = plate.not_run("NOT_RUN — 테스트")
    assert block["readable_abstention_rate"] is None
    assert block["n_readable"] is None
