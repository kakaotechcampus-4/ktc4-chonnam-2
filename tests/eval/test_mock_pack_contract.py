"""팀 공용 Mock Pack fixture 를 eval 이 읽을 수 있는지 확인한다.

W4 §17 이 eval 에 요구하는 것은 "공개 Contract/Mock 결과를 읽어 기본 검증"이고,
04_mock_validation_report.md §22 는 eval fixture 검수 담당을 김대원으로 지정했다.
이 파일이 그 두 가지의 증빙이다.

성능 지표를 내는 것이 아니다. Mock 은 성능 자료가 아니며(01_mock_dataset_overview.md),
여기서 확인하는 것은 "eval 이 팀 산출물을 읽고 맞고 틀림을 구분하는가" 하나다.
"""
import json
import os

import pytest

from eval import paths
from eval.runners import normalize

MOCK = os.path.join(paths.REPO_ROOT, "data", "mock")
SCENARIO = "scenario_happy_001"


def _load(*parts):
    with open(os.path.join(MOCK, *parts), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def expected():
    """사람이 라벨링한 정답지. Mock Runtime Output 이 아니다."""
    return _load("expected", "%s.expected.json" % SCENARIO)["ground_truth"]


# --- eval fixture (내가 검수 담당인 파일) ---------------------------------

def test_correct_fixture_matches_every_expected_field(expected):
    pred = _load("eval", "prediction_correct.happy_001.json")["prediction"]
    assert pred["candidate_id"] == expected["correct_candidate_id"]
    assert pred["rank"] == expected["correct_rank"]
    assert pred["visual_event_type"] == expected["correct_visual_event_type"]
    assert pred["plate_value"] == expected["correct_plate_value"]
    assert pred["occurred_at"] == expected["correct_occurred_at"]


def test_wrong_fixture_differs_in_exactly_three_fields(expected):
    """오답 fixture 가 실제로 틀려야 채점기 검증에 쓸 수 있다.

    02_mock_scenario_catalog.md 는 rank/visual_event_type/plate 세 곳이
    어긋난다고 적었다. 그 주장이 파일과 일치하는지 확인한다.
    """
    pred = _load("eval", "prediction_wrong.happy_001.json")["prediction"]
    pairs = {
        "candidate_id": (pred["candidate_id"], expected["correct_candidate_id"]),
        "rank": (pred["rank"], expected["correct_rank"]),
        "visual_event_type": (pred["visual_event_type"], expected["correct_visual_event_type"]),
        "plate_value": (pred["plate_value"], expected["correct_plate_value"]),
        "occurred_at": (pred["occurred_at"], expected["correct_occurred_at"]),
    }
    differing = sorted(k for k, (a, b) in pairs.items() if a != b)
    assert differing == ["plate_value", "rank", "visual_event_type"]


# --- 실제 계약 산출물 (Consumer 경로) --------------------------------------

def test_from_candidate_events_translates_names_and_units():
    """계약과 eval 뷰의 이름·단위 차이를 경계에서 흡수하는지 확인한다.

    CONTRACT_CONFLICTS.md §4 가 기록했듯 계약마다 이름이 다르고
    Mock Pack 은 일부러 통일하지 않았다. 통일은 이 경계의 일이다.
    """
    raw = _load("search", "candidate_events.happy_001.json")
    out = normalize.from_candidate_events(raw)

    assert len(out) == 1
    c = out[0]
    assert c["candidate_id"] == "cand_h001"
    assert c["rank"] == 1
    # event_type_hint -> event_type
    assert c["event_type"] == "SOLID_LINE_LANE_CHANGE"
    # ranking_score -> score
    assert c["score"] == 0.86
    # span.start_ms(밀리초) -> t_start_sec(초)
    assert c["t_start_sec"] == 690.0
    assert c["t_end_sec"] == 708.0


def test_contract_artifacts_agree_with_expected(expected):
    """search·readout 의 실제 계약 산출물이 정답지와 맞는지 확인한다.

    eval fixture 는 eval 을 위해 따로 만든 납작한 요약본이고, 이쪽이
    다른 Owner 가 실제로 생산하는 형태다. Consumer 검수의 근거가 된다.
    """
    events = normalize.from_candidate_events(
        _load("search", "candidate_events.happy_001.json"))
    top = min(events, key=lambda c: c["rank"])
    assert top["candidate_id"] == expected["correct_candidate_id"]
    assert top["rank"] == expected["correct_rank"]
    assert top["event_type"] == expected["correct_visual_event_type"]

    plate = _load("readout", "plate_readout.happy_001.json")
    assert plate["abstained"] is False
    assert plate["observation"]["value"] == expected["correct_plate_value"]


def test_candidate_event_type_stays_inside_baseline_enum():
    """계약이 내는 event_type_hint 가 baseline 4종 안에 있는지 확인한다.

    벗어나면 채점기의 혼동행렬에 자리가 없어 조용히 miss 로 집계된다.
    Consumer 검수에서 서어진(search) 에게 확인해야 할 항목이다.
    """
    from eval.enums import VIOLATION_TYPES

    events = normalize.from_candidate_events(
        _load("search", "candidate_events.happy_001.json"))
    for c in events:
        assert c["event_type"] in VIOLATION_TYPES
