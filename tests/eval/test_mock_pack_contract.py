"""팀 공용 Mock Pack fixture 를 eval 이 읽을 수 있는지 확인한다.

W4 §17 이 eval 에 요구하는 것은 "공개 Contract/Mock 결과를 읽어 기본 검증"이고,
04_mock_validation_report.md §22 는 eval fixture 검수 담당을 김대원으로 지정했다.
이 파일이 그 두 가지의 증빙이다.

성능 지표를 내는 것이 아니다. Mock 은 성능 자료가 아니며(01_mock_dataset_overview.md),
여기서 확인하는 것은 "eval 이 팀 산출물을 읽고 맞고 틀림을 구분하는가" 하나다.

**시나리오별로 파라미터화한다.** 그래야 pytest 출력에 어느 시나리오를 확인했는지
그대로 남고, 확인하지 못한 시나리오는 skip 사유와 함께 같은 화면에 보인다.
"happy 만 통과"보다 "무엇을 못 했고 왜"가 함께 보이는 것이 증빙으로 정직하다.
"""
import json
import os

import pytest

from eval import paths
from eval.enums import VIOLATION_TYPES
from eval.runners import normalize

MOCK = os.path.join(paths.REPO_ROOT, "data", "mock")

# manifest.json 이 등재한 두 시나리오. 새 시나리오가 추가되면 여기에 넣는다.
SCENARIOS = ("scenario_happy_001", "scenario_partial_001")

scenarios = pytest.mark.parametrize("scenario", SCENARIOS)


def _suffix(scenario):
    """scenario_happy_001 -> happy_001 (fixture 파일명 관례)."""
    return scenario.replace("scenario_", "")


def _load(*parts):
    with open(os.path.join(MOCK, *parts), encoding="utf-8") as f:
        return json.load(f)


def _load_or_skip(reason, *parts):
    """없으면 사유를 남기고 skip. 사유가 그대로 증빙이 된다."""
    path = os.path.join(MOCK, *parts)
    if not os.path.exists(path):
        pytest.skip(reason)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _expected_or_skip(scenario):
    """사람이 라벨링한 정답지. Mock Runtime Output 이 아니다."""
    return _load_or_skip(
        "%s 용 eval 정답지 없음 — Partial Success 채점은 v1 로 이월"
        " (04_mock_validation_report.md §23)" % scenario,
        "expected", "%s.expected.json" % scenario,
    )["ground_truth"]


def _eval_prediction_or_skip(scenario, which):
    return _load_or_skip(
        "%s 용 eval prediction fixture 없음 — v1 로 이월"
        " (04_mock_validation_report.md §23)" % scenario,
        "eval", "prediction_%s.%s.json" % (which, _suffix(scenario)),
    )["prediction"]


# --- eval fixture (내가 검수 담당인 파일) ---------------------------------

@scenarios
def test_correct_fixture_matches_every_expected_field(scenario):
    expected = _expected_or_skip(scenario)
    pred = _eval_prediction_or_skip(scenario, "correct")
    assert pred["candidate_id"] == expected["correct_candidate_id"]
    assert pred["rank"] == expected["correct_rank"]
    assert pred["visual_event_type"] == expected["correct_visual_event_type"]
    assert pred["plate_value"] == expected["correct_plate_value"]
    assert pred["occurred_at"] == expected["correct_occurred_at"]


@scenarios
def test_wrong_fixture_differs_in_exactly_three_fields(scenario):
    """오답 fixture 가 실제로 틀려야 채점기 검증에 쓸 수 있다.

    02_mock_scenario_catalog.md 는 rank/visual_event_type/plate 세 곳이
    어긋난다고 적었다. 그 주장이 파일과 일치하는지 확인한다.
    """
    expected = _expected_or_skip(scenario)
    pred = _eval_prediction_or_skip(scenario, "wrong")
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
    단정값은 scenario_happy_001 의 것이라 이 테스트만 파라미터화하지 않는다.
    """
    out = normalize.from_candidate_events(
        _load("search", "candidate_events.happy_001.json"))

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


@scenarios
def test_contract_artifacts_agree_with_expected(scenario):
    """search·readout 의 실제 계약 산출물이 정답지와 맞는지 확인한다.

    eval fixture 는 eval 을 위해 따로 만든 납작한 요약본이고, 이쪽이
    다른 Owner 가 실제로 생산하는 형태다. Consumer 검수의 근거가 된다.
    """
    expected = _expected_or_skip(scenario)
    suffix = _suffix(scenario)

    events = normalize.from_candidate_events(
        _load("search", "candidate_events.%s.json" % suffix))
    top = min(events, key=lambda c: c["rank"])
    assert top["candidate_id"] == expected["correct_candidate_id"]
    assert top["rank"] == expected["correct_rank"]
    assert top["event_type"] == expected["correct_visual_event_type"]

    plate = _load("readout", "plate_readout.%s.json" % suffix)
    assert plate["abstained"] is False
    assert plate["observation"]["value"] == expected["correct_plate_value"]


@scenarios
def test_candidate_event_type_stays_inside_baseline_enum(scenario):
    """계약이 내는 event_type_hint 가 baseline 4종 안에 있는지 확인한다.

    벗어나면 채점기의 혼동행렬에 자리가 없어 조용히 miss 로 집계된다.
    Consumer 검수에서 서어진(search) 에게 확인해야 할 항목이다.
    정답지가 필요 없으므로 두 시나리오 모두 확인한다.
    """
    events = normalize.from_candidate_events(
        _load("search", "candidate_events.%s.json" % _suffix(scenario)))
    assert events, "%s 에 candidate event 가 없다" % scenario
    for c in events:
        assert c["event_type"] in VIOLATION_TYPES


def test_plate_abstain_is_visible_and_value_is_not_a_confirmation():
    """ABSTAIN 을 eval 이 볼 수 있고, 남아 있는 값이 확정이 아님을 고정한다.

    scenario_partial_001 의 PlateReadout 은 abstained=true 인데
    observation.value 에 '12나 34?6' 이 남아 있다. 계약상 정상이다 —
    contract-plate-overlay-readout.md 는 `readout` 이 번호판을 최종
    확정하지 않고 관찰만 제공하며 확정/보류는 evidence 가 판단한다고 한다
    (§ Consumer 표). abstained=true 는 "확정 보류"이지 "값 없음"이 아니다.

    **그래서 eval 은 이 값을 확정 판독으로 채점해서는 안 된다.** 채점하면
    정직하게 보류한 구현을 오답으로 세게 되고, 무리해서 읽는 쪽이 유리해진다.
    채점 규칙 구현은 v1 이지만, 그때 이 구분을 잃지 않도록 여기서 고정한다.
    """
    plate = _load("readout", "plate_readout.partial_001.json")

    assert plate["abstained"] is True
    assert plate["abstain_reason"]  # 보류 사유가 비어 있지 않다
    assert plate["observation"]["status"] == "NEEDS_REVIEW"
    # 값이 남아 있다 — 관찰이지 확정이 아니다
    assert plate["observation"]["value"]
