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
