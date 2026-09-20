"""비율 지표의 신뢰구간.

B tier 사건이 10건뿐이라 recall 한 값이 얼마나 흔들리는지를 결과가 스스로
말해야 한다. by_type 은 더 심하다 — SIGNAL 이 2건이면 나올 수 있는 값이
0 · 0.5 · 1 셋뿐이다.
"""
import pytest

from eval.scorers import interval


def test_no_denominator_means_no_interval():
    """0 으로 나눌 수 없다. 구간도 없다 — 0.0 이 아니라 null 이다."""
    assert interval.wilson95(0, 0) is None


def test_the_interval_brackets_the_point_estimate():
    lo, hi = interval.wilson95(5, 10)
    assert lo < 0.5 < hi


def test_two_events_leave_the_interval_almost_useless():
    """SIGNAL 2건에서 1건 적중 — 사실상 아무것도 말하지 않는다."""
    lo, hi = interval.wilson95(1, 2)
    assert lo == pytest.approx(0.09, abs=0.01)
    assert hi == pytest.approx(0.91, abs=0.01)
    assert hi - lo > 0.8


def test_more_samples_narrow_the_interval():
    narrow = interval.wilson95(15, 30)
    wide = interval.wilson95(5, 10)
    assert (narrow[1] - narrow[0]) < (wide[1] - wide[0])


def test_a_perfect_score_does_not_claim_certainty():
    """Wald 근사는 여기서 [1.0, 1.0] 을 낸다 — 2건 맞혔다고 확실하지 않다."""
    lo, hi = interval.wilson95(2, 2)
    assert hi == 1.0
    assert lo < 0.5          # 2/2 로는 절반 이하일 가능성도 못 배제한다


def test_a_zero_score_does_not_claim_certainty():
    lo, hi = interval.wilson95(0, 2)
    assert lo == 0.0
    assert hi > 0.5


def test_the_interval_never_leaves_zero_to_one():
    for k, n in [(0, 1), (1, 1), (0, 3), (3, 3), (1, 100)]:
        lo, hi = interval.wilson95(k, n)
        assert 0.0 <= lo <= hi <= 1.0
