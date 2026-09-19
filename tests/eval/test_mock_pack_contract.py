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

# manifest.json 이 등재한, search fixture 가 있는 시나리오. infra_failure_001 은
# search fixture 자체가 없어(대상 아님) 여기 들어가지 않는다. 새 시나리오가
# 추가되면 여기에 넣는다.
SCENARIOS = (
    "scenario_happy_001",
    "scenario_empty_001",
    "scenario_plate_reread_001",
    "scenario_correction_rerun_001",
    "scenario_unknown_abstain_partial_001",
    "scenario_relative_rebase_001",
)

scenarios = pytest.mark.parametrize("scenario", SCENARIOS)


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
    """eval 소유 정답지(schema eval-expected/v2). 값을 복제하지 않고 ref 로
    실제 계약 산출물(candidate_id·readout_id)을 가리킨다."""
    return _load_or_skip(
        "%s 용 eval 정답지 없음" % scenario,
        "expected", "%s.expected.json" % scenario,
    )


def _search_candidates(scenario):
    """search fixture 의 candidates 를 계약 모양 그대로 모은다 (mock_pack impl 과 동일)."""
    doc = _load("search", "%s.json" % scenario)
    out = []
    for ev in doc.get("analysis_run_candidate_events", []):
        out.extend(ev.get("candidates", []))
    return out


# --- 실제 계약 산출물 (Consumer 경로) --------------------------------------

def test_from_candidate_events_translates_names_and_units():
    """계약과 eval 뷰의 이름·단위 차이를 경계에서 흡수하는지 확인한다.

    CONTRACT_CONFLICTS.md §4 가 기록했듯 계약마다 이름이 다르고
    Mock Pack 은 일부러 통일하지 않았다. 통일은 이 경계의 일이다.
    단정값은 scenario_happy_001 의 것이라 이 테스트만 파라미터화하지 않는다.
    """
    out = normalize.from_candidate_events(_search_candidates("scenario_happy_001"))

    assert len(out) == 1
    c = out[0]
    assert c["candidate_id"] == "candidate_h001"
    assert c["rank"] == 1
    # event_type_hint -> event_type
    assert c["event_type"] == "SOLID_LINE_LANE_CHANGE"
    # ranking_score -> score
    assert c["score"] == 0.86
    # span.start_ms/end_ms(밀리초) -> t_start_sec/t_end_sec(초) — coarse 창이다
    assert c["t_start_sec"] == 300.0
    assert c["t_end_sec"] == 420.0
    # span.representative_ms(밀리초) -> representative_sec(초) — 매칭에 쓰는 값
    assert c["representative_sec"] == 312.48
    assert c["timeline_revision"] == 1


@scenarios
def test_contract_artifacts_agree_with_expected(scenario):
    """search·readout 의 실제 계약 산출물이 eval 정답지(v2)와 맞는지 확인한다.

    v2 정답지는 값을 복제하지 않고 candidate_id/readout_id 를 ref 로
    가리킨다. 그 ref 가 실제로 가리키는 계약 값이 ref 옆에 적힌
    onset_ms/violation_type/true_text 와 일치하는지 여기서 확인한다.
    """
    expected = _expected_or_skip(scenario)
    targets = expected["metric_targets"]

    onset_target = next(
        (t for t in targets if t["metric"] == "candidate_onset"), None)
    if onset_target is not None:
        events = normalize.from_candidate_events(_search_candidates(scenario))
        matched = next(
            c for c in events if c["candidate_id"] == onset_target["ref"]["ref"])
        assert matched["representative_sec"] == onset_target["onset_ms"] / 1000.0
        # scoring이 EXCLUDED인 항목(참값 유형 미확정)은 event_type_hint가
        # 확정 유형과 다를 수 있다 — 그래서 그 값을 비교하지 않는다.
        if onset_target["scoring"] != "EXCLUDED":
            assert matched["event_type"] == onset_target["violation_type"]

    plate_target = next(
        (t for t in targets
         if t["metric"] == "plate_readout" and t.get("legibility") == "READABLE"),
        None)
    if plate_target is not None:
        readout = _load("readout", "%s.json" % scenario)
        plate = next(
            p for p in readout["plate_readouts"]
            if p["readout_id"] == plate_target["ref"]["ref"])
        assert plate["abstained"] is False
        assert plate["observation"]["value"] == plate_target["true_text"]

    if onset_target is None and plate_target is None:
        # scenario_empty_001 은 candidate_onset·plate_readout 이 둘 다 없다 —
        # 아무것도 확인하지 않고 조용히 통과하는 대신, 이 시나리오의 유일한
        # metric_target 이 실제로 negative_clip 하나뿐인지 적극적으로 확인한다.
        assert scenario == "scenario_empty_001"
        assert len(targets) == 1
        assert targets[0]["metric"] == "negative_clip"


@scenarios
def test_candidate_event_type_stays_inside_baseline_enum(scenario):
    """계약이 내는 event_type_hint 가 baseline 4종 안에 있는지 확인한다.

    벗어나면 채점기의 혼동행렬에 자리가 없어 조용히 miss 로 집계된다.
    Consumer 검수에서 서어진(search) 에게 확인해야 할 항목이다.
    정답지가 필요 없으므로 모든 시나리오를 확인한다. scenario_empty_001 은
    candidate event 가 0건인 것이 정상이라 빈 목록도 통과해야 한다.
    """
    events = normalize.from_candidate_events(_search_candidates(scenario))
    assert events or scenario == "scenario_empty_001"
    for c in events:
        assert c["event_type"] in VIOLATION_TYPES


def test_plate_abstain_is_visible_and_value_is_not_a_confirmation():
    """ABSTAIN 을 eval 이 볼 수 있고, 남아 있는 값이 확정이 아님을 고정한다.

    scenario_plate_reread_001 의 초판독(readout_p001_plate) 은
    abstained=true 인데 observation.value 에 '17나28??' 이 남아 있다.
    계약상 정상이다 — contract-plate-overlay-readout.md 는 `readout` 이
    번호판을 최종 확정하지 않고 관찰만 제공하며 확정/보류는 evidence 가
    판단한다고 한다 (§ Consumer 표). abstained=true 는 "확정 보류"이지
    "값 없음"이 아니다.

    **그래서 eval 은 이 값을 확정 판독으로 채점해서는 안 된다.** 채점하면
    정직하게 보류한 구현을 오답으로 세게 되고, 무리해서 읽는 쪽이 유리해진다.
    """
    readout = _load("readout", "scenario_plate_reread_001.json")
    plate = next(
        p for p in readout["plate_readouts"]
        if p["readout_id"] == "readout_p001_plate")

    assert plate["abstained"] is True
    assert plate["abstain_reason"]  # 보류 사유가 비어 있지 않다
    assert plate["observation"]["status"] == "NEEDS_REVIEW"
    # 값이 남아 있다 — 관찰이지 확정이 아니다
    assert plate["observation"]["value"]
