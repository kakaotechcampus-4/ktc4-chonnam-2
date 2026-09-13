"""비용 집계.

정본 집계 키는 case_id 다 (usage-record/v1.2 §9-2). run_ref 로 묶으면
run 이 산출되지 않은 attempt(run_ref=null, RUN_NOT_PRODUCED)가 통째로
빠져 비용이 과소 보고된다.
"""
import pytest

from eval.scorers import cost


def _row(case_id, amount, currency="KRW", run_ref=None, reason=None):
    return {"case_id": case_id, "cost": {"amount": amount, "currency": currency},
            "run_ref": run_ref, "run_ref_reason": reason}


def test_aggregates_by_case_id_not_by_run_ref():
    rows = [
        _row("case_a", "100", run_ref={"kind": "analysis_run", "ref": "run_a"}),
        _row("case_a", "50", run_ref=None, reason="RUN_NOT_PRODUCED"),
        _row("case_b", "30", run_ref=None, reason="DIRECT_NO_RUN"),
    ]
    out = cost.score(rows, processed_duration_sec=3600.0, scenarios=["s1"])

    assert out["cost_per_case"] == {"case_a": 150.0, "case_b": 30.0}
    assert out["total"] == 180.0
    assert out["currency"] == "KRW"


def test_cost_per_source_video_hour_uses_the_given_denominator():
    rows = [_row("case_a", "1200")]
    out = cost.score(rows, processed_duration_sec=3600.0, scenarios=["s1"])
    assert out["cost_per_source_video_hour"] == pytest.approx(1200.0)


def test_zero_cost_case_is_kept_not_dropped():
    """0원 case 를 빼면 분포가 왜곡된다 — 평균만 보면 안 보인다."""
    rows = [_row("case_a", "100"), _row("case_x", "0")]
    out = cost.score(rows, processed_duration_sec=3600.0, scenarios=["s1"])
    assert out["cost_per_case"]["case_x"] == 0.0


def test_mixed_currency_is_refused_not_converted():
    """환율은 pricing_context 에 귀속되지 eval 이 정할 값이 아니다."""
    rows = [_row("case_a", "100", "KRW"), _row("case_b", "1", "USD")]
    out = cost.score(rows, processed_duration_sec=3600.0, scenarios=["s1"])

    assert out["total"] is None
    assert "MIXED_CURRENCY" in out["coverage"]


def test_no_usage_rows_returns_null_not_zero():
    out = cost.score([], processed_duration_sec=3600.0, scenarios=[])
    assert out["total"] is None
    assert "NO_USAGE_RECORDS" in out["coverage"]


def test_no_duration_leaves_the_hourly_rate_null():
    rows = [_row("case_a", "100")]
    out = cost.score(rows, processed_duration_sec=None, scenarios=["s1"])
    assert out["total"] == 100.0
    assert out["cost_per_source_video_hour"] is None
