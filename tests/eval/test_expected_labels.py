"""expected/ 라벨이 스스로 앞뒤가 맞고 pack 과 갈라지지 않았는지 본다.

공용 validator §13 은 metric_targets 가 비어 있는지와 ref 가 해석되는지만
본다. 라벨 '내용'을 검증하는 자리는 여기다 (스펙 §2-1, §12).

**등식 검사는 derived_from_pack=true 인 라벨에만 건다.** 무조건 단언하면
mock impl 이 항상 옳다고 못 박는 꼴이 되어, wrong_accept_rate 의 분자를
메울 「일부러 틀린」 fixture 가 들어오는 순간 이 테스트가 먼저 깨진다.
abstained 도 단언하지 않는다 — 그것은 채점 대상이지 전제가 아니다.
"""
import json
import os

import pytest

from eval import paths
from eval.scorers.candidate import SCORING_VALUES

MOCK = os.path.join(paths.REPO_ROOT, "data", "mock")

SCENARIOS = (
    "scenario_happy_001",
    "scenario_empty_001",
    "scenario_plate_reread_001",
    "scenario_correction_rerun_001",
    "scenario_unknown_abstain_partial_001",
    "scenario_infra_failure_001",
    "scenario_relative_rebase_001",
)

METRICS = ("candidate_onset", "plate_readout", "occurred_at",
           "negative_clip", "not_scored")


def _read(*parts):
    path = os.path.join(MOCK, *parts)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _expected(scenario):
    return _read("expected", scenario + ".expected.json")


def _targets(scenario, metric):
    doc = _expected(scenario)
    return [t for t in doc["metric_targets"] if t["metric"] == metric]


def _plate_readouts(scenario):
    doc = _read("readout", scenario + ".json")
    if doc is None:
        return {}
    return {p["readout_id"]: p for p in doc.get("plate_readouts", [])}


def _candidates(scenario):
    doc = _read("search", scenario + ".json")
    if doc is None:
        return {}
    out = {}
    for ev in doc.get("analysis_run_candidate_events", []):
        for c in ev.get("candidates", []):
            out[c["candidate_id"]] = c
    return out


def _time_resolutions(scenario):
    doc = _read("evidence", scenario + ".json")
    if doc is None:
        return {}
    return {(r.get("resolution_ref") or {}).get("ref"): r
            for r in doc.get("time_resolutions", [])}


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_every_scenario_has_an_expected_file(scenario):
    doc = _expected(scenario)
    assert doc is not None, "%s 의 정답지가 없다" % scenario
    assert doc["schema"] == "eval-expected/v2"
    assert doc["provisional_non_contract_schema"] is True
    assert doc["metric_targets"], "metric_targets 가 비면 공용 validator §13 이 FAIL 한다"
    for t in doc["metric_targets"]:
        assert t["metric"] in METRICS, "알 수 없는 metric %r" % t["metric"]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_plate_label_is_internally_coherent(scenario):
    """READABLE 이면 참값이 있고 UNREADABLE 이면 없다.

    라벨 자신의 앞뒤만 본다. 판독 결과와 맞는지는 별개 테스트다.
    """
    for t in _targets(scenario, "plate_readout"):
        if t["legibility"] == "READABLE":
            assert t.get("true_text"), "%s: READABLE 인데 true_text 가 없다" % t["ref"]["ref"]
        elif t["legibility"] == "UNREADABLE":
            assert "true_text" not in t, \
                "%s: UNREADABLE 인데 true_text 가 있다" % t["ref"]["ref"]
        else:
            pytest.fail("알 수 없는 legibility %r" % t["legibility"])


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_derived_plate_labels_match_the_pack(scenario):
    """pack 에서 유도한 라벨만 원본과 같은지 본다.

    derived_from_pack=false 인 라벨(독립 참값·일부러 틀린 fixture)은
    건너뛴다. 여기서 등식을 강제하면 채점할 오답 자체를 만들 수 없다.
    """
    readouts = _plate_readouts(scenario)
    for t in _targets(scenario, "plate_readout"):
        if not t.get("derived_from_pack"):
            continue
        rid = t["ref"]["ref"]
        assert rid in readouts, "%s: pack 에 그런 판독이 없다" % rid
        if t["legibility"] == "READABLE":
            assert t["true_text"] == readouts[rid]["observation"]["value"], \
                "%s: 파생 라벨이 원본과 갈라졌다" % rid


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_derived_time_labels_match_the_pack(scenario):
    """pack 에서 유도한 시각 라벨만 원본과 같은지 본다.

    derived_from_pack=false 인 라벨은 건너뛴다 — u001 은 fixture 가 값을
    싣고 있는데도 「확정하면 오답」이 정답이라 일부러 다르다.
    """
    resolutions = _time_resolutions(scenario)
    for t in _targets(scenario, "occurred_at"):
        if not t.get("derived_from_pack"):
            continue
        rid = t["ref"]["ref"]
        assert rid in resolutions, "%s: pack 에 그런 시각 해석이 없다" % rid
        assert t["expected"] == resolutions[rid]["resolved"]["value"], \
            "%s: 파생 라벨이 원본과 갈라졌다" % rid


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_candidate_onset_matches_representative_ms(scenario):
    """mock tier onset 은 representative_ms 에서 유도한 값이다.

    성능 검사가 아니라 GT 재생성 누락 검사다 (스펙 §6-2 순환성 경고 참조).
    """
    cands = _candidates(scenario)
    for t in _targets(scenario, "candidate_onset"):
        cid = t["ref"]["ref"]
        assert cid in cands, "%s: pack 에 그런 candidate 가 없다" % cid
        span = cands[cid]["span"]
        assert t["onset_ms"] == span["representative_ms"]
        assert t["timeline_revision"] == span["timeline_revision"]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_scoring_values_are_known(scenario):
    for t in _targets(scenario, "candidate_onset"):
        assert t["scoring"] in SCORING_VALUES, "알 수 없는 scoring %r" % t["scoring"]


def test_old_id_comparison_fixtures_are_gone():
    """ID 비교 채점 모델은 폐기했다.

    「채점기가 오류를 잡는가」는 fake_always_correct / fake_always_wrong 두
    impl 이 실제 파이프라인을 통과시켜 이미 증명한다.
    """
    assert _read("expected", "eval_fixture_correct_001.json") is None
    assert _read("expected", "eval_fixture_wrong_001.json") is None
