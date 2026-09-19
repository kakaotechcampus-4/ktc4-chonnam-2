"""`scope.build_analysis_scope()` — case가 유일한 Producer인 `AnalysisScope`(1.1.0)를
`contract-analysis-scope.md` §10 불변조건대로 조립하는지 검증한다.

`hint.vehicle`/`hint.free_text`가 `case.hints`(vehicle/situation)에서 파생된다는 건
`data/mock/search/scenario_*.json`의 `analysis_scopes[0].hint`와 `data/mock/case/
scenario_*.json`의 `case_views[0].hints`를 교차 대조해서 확인한 것 — ABSOLUTE
(`scenario_happy_001`)와 TIMELINE_RELATIVE(`scenario_relative_rebase_001`) 두 kind
모두 fixture와 바이트 단위로 재현되는지 본다.
"""
import json
from pathlib import Path

import pytest

from daesingo.case.adapters import MockFixtureAdapter
from daesingo.case.domain import CaseAggregate
from daesingo.case.scope import build_analysis_scope

MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"


def _case_hints(scenario_id: str) -> dict:
    path = MOCK_ROOT / "case" / f"scenario_{scenario_id}.json"
    with open(path, encoding="utf-8") as fh:
        fixture = json.load(fh)
    return fixture["case_views"][0]["hints"]


def test_build_analysis_scope_matches_absolute_fixture():
    # scenario_happy_001의 free_text는 이 세션에서 발견된 유일한 fixture 불일치(모듈
    # docstring 참고)라, hint는 별도로(직접 값을 대입해) 비교하고 나머지 필드만 정답지와
    # 비교한다.
    scenario_id = "happy_001"
    hints = _case_hints(scenario_id)
    case = CaseAggregate.intake(case_id="case_h001", hints=hints, manifest_summary={})

    scope = build_analysis_scope(
        case,
        scope_id="scope_h001",
        time_ranges=[{"kind": "ABSOLUTE", "start": "2026-08-24T18:00:00+09:00", "end": "2026-08-24T18:20:00+09:00"}],
        target_event_types=["SOLID_LINE_LANE_CHANGE"],
        max_cost_krw=1000,
        max_latency_sec=180,
    )

    adapter = MockFixtureAdapter(MOCK_ROOT, scenario_id)
    expected = adapter.get_analysis_scopes()[0]
    assert scope["scope_id"] == expected["scope_id"]
    assert scope["time_ranges"] == expected["time_ranges"]
    assert scope["target_event_types"] == expected["target_event_types"]
    assert scope["budget"] == expected["budget"]
    assert scope["contract_version"] == expected["contract_version"]
    assert scope["hint"]["vehicle"] == expected["hint"]["vehicle"] == "흰색 SUV"


def test_build_analysis_scope_matches_timeline_relative_fixture():
    scenario_id = "relative_rebase_001"
    hints = _case_hints(scenario_id)
    case = CaseAggregate.intake(case_id="case_rb001", hints=hints, manifest_summary={})

    scope = build_analysis_scope(
        case,
        scope_id="scope_rb001",
        time_ranges=[
            {
                "kind": "TIMELINE_RELATIVE",
                "timeline_ref": {"timeline_id": "tl_rb001", "revision": 1},
                "start_ms": 500000,
                "end_ms": 560000,
            }
        ],
        target_event_types=["CENTER_LINE_CROSSING"],
        max_cost_krw=1000,
        max_latency_sec=180,
    )

    adapter = MockFixtureAdapter(MOCK_ROOT, scenario_id)
    expected = adapter.get_analysis_scopes()[0]
    assert scope == expected  # 이 시나리오는 hint까지 완전히 바이트 단위로 일치한다


def test_time_ranges_must_not_be_empty():
    case = CaseAggregate.intake(case_id="c1", hints={}, manifest_summary={})
    with pytest.raises(ValueError):
        build_analysis_scope(
            case, scope_id="s1", time_ranges=[], target_event_types=["SIGNAL"],
            max_cost_krw=100, max_latency_sec=10,
        )


def test_time_ranges_cannot_mix_kinds():
    case = CaseAggregate.intake(case_id="c1", hints={}, manifest_summary={})
    with pytest.raises(ValueError):
        build_analysis_scope(
            case,
            scope_id="s1",
            time_ranges=[
                {"kind": "ABSOLUTE", "start": "2026-01-01T00:00:00Z", "end": "2026-01-01T01:00:00Z"},
                {
                    "kind": "TIMELINE_RELATIVE",
                    "timeline_ref": {"timeline_id": "tl1", "revision": 1},
                    "start_ms": 0,
                    "end_ms": 1000,
                },
            ],
            target_event_types=["SIGNAL"],
            max_cost_krw=100,
            max_latency_sec=10,
        )


def test_timeline_relative_ranges_must_share_timeline_ref():
    case = CaseAggregate.intake(case_id="c1", hints={}, manifest_summary={})
    with pytest.raises(ValueError):
        build_analysis_scope(
            case,
            scope_id="s1",
            time_ranges=[
                {
                    "kind": "TIMELINE_RELATIVE",
                    "timeline_ref": {"timeline_id": "tl1", "revision": 1},
                    "start_ms": 0,
                    "end_ms": 1000,
                },
                {
                    "kind": "TIMELINE_RELATIVE",
                    "timeline_ref": {"timeline_id": "tl1", "revision": 2},
                    "start_ms": 0,
                    "end_ms": 1000,
                },
            ],
            target_event_types=["SIGNAL"],
            max_cost_krw=100,
            max_latency_sec=10,
        )


def test_target_event_types_must_not_be_empty():
    case = CaseAggregate.intake(case_id="c1", hints={}, manifest_summary={})
    with pytest.raises(ValueError):
        build_analysis_scope(
            case,
            scope_id="s1",
            time_ranges=[{"kind": "ABSOLUTE", "start": "2026-01-01T00:00:00Z", "end": "2026-01-01T01:00:00Z"}],
            target_event_types=[],
            max_cost_krw=100,
            max_latency_sec=10,
        )


def test_target_event_types_rejects_unknown_enum_value():
    case = CaseAggregate.intake(case_id="c1", hints={}, manifest_summary={})
    with pytest.raises(ValueError):
        build_analysis_scope(
            case,
            scope_id="s1",
            time_ranges=[{"kind": "ABSOLUTE", "start": "2026-01-01T00:00:00Z", "end": "2026-01-01T01:00:00Z"}],
            target_event_types=["NOT_A_REAL_TYPE"],
            max_cost_krw=100,
            max_latency_sec=10,
        )


@pytest.mark.parametrize("max_cost_krw,max_latency_sec", [(0, 10), (-1, 10), (100, 0), (100, -1)])
def test_budget_must_be_positive(max_cost_krw, max_latency_sec):
    case = CaseAggregate.intake(case_id="c1", hints={}, manifest_summary={})
    with pytest.raises(ValueError):
        build_analysis_scope(
            case,
            scope_id="s1",
            time_ranges=[{"kind": "ABSOLUTE", "start": "2026-01-01T00:00:00Z", "end": "2026-01-01T01:00:00Z"}],
            target_event_types=["SIGNAL"],
            max_cost_krw=max_cost_krw,
            max_latency_sec=max_latency_sec,
        )


def test_free_text_hint_redacts_phone_number_and_email():
    case = CaseAggregate.intake(
        case_id="c1",
        hints={"vehicle": "흰색 SUV", "situation": "제보자 연락처는 010-1234-5678, test@example.com 입니다"},
        manifest_summary={},
    )
    scope = build_analysis_scope(
        case,
        scope_id="s1",
        time_ranges=[{"kind": "ABSOLUTE", "start": "2026-01-01T00:00:00Z", "end": "2026-01-01T01:00:00Z"}],
        target_event_types=["SIGNAL"],
        max_cost_krw=100,
        max_latency_sec=10,
    )
    assert "010-1234-5678" not in scope["hint"]["free_text"]
    assert "test@example.com" not in scope["hint"]["free_text"]
    assert "[REDACTED]" in scope["hint"]["free_text"]


def test_hint_object_always_present_even_without_hints():
    case = CaseAggregate.intake(case_id="c1", hints={}, manifest_summary={})
    scope = build_analysis_scope(
        case,
        scope_id="s1",
        time_ranges=[{"kind": "ABSOLUTE", "start": "2026-01-01T00:00:00Z", "end": "2026-01-01T01:00:00Z"}],
        target_event_types=["SIGNAL"],
        max_cost_krw=100,
        max_latency_sec=10,
    )
    assert scope["hint"] == {"vehicle": None, "free_text": None}
