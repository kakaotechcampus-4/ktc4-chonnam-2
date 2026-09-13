"""팀 공용 Mock Pack 산출물을 읽는 impl.

`fake:` 접두어를 쓰지 않는다 — 정답지를 몰래 읽는 치트가 아니라 다른 Owner 가
만든 계약 산출물을 읽는다. 실제 구현이 붙기 전까지 그 자리를 대신한다.

`eval` 은 `case`·`search`·`readout` 의 코드를 import 하지 않는다. 파일만 읽는다.
"""
import json
import os

from eval import paths
from eval.runners import normalize

IMPL_VERSION = "v2"

SCENARIOS = (
    "scenario_happy_001",
    "scenario_empty_001",
    "scenario_plate_reread_001",
    "scenario_correction_rerun_001",
    "scenario_unknown_abstain_partial_001",
    "scenario_infra_failure_001",
    "scenario_relative_rebase_001",
)

_MOCK = os.path.join(paths.REPO_ROOT, "data", "mock")


def _read(*parts):
    """없으면 None. 「파일이 없다」와 「내용이 비었다」는 다른 사실이다."""
    path = os.path.join(_MOCK, *parts)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _candidate_events(scenario):
    """search fixture 의 candidates 를 계약 모양 그대로 모은다."""
    doc = _read("search", scenario + ".json")
    if doc is None:
        return None
    out = []
    for ev in doc.get("analysis_run_candidate_events", []):
        out.extend(ev.get("candidates", []))
    return out


def run(scope):
    """계약 산출물을 stage 별 raw 로 옮긴다.

    scope 는 {"manifest", "stage"} 만 담는다 — 정답지는 넘어오지 않고,
    이 impl 도 정답지를 열지 않는다.

    clip_id 자리에 scenario_id 를 쓴다. 계약은 timeline_id + 밀리초 offset
    으로 위치를 말하고 정답지는 clip_id 로 말하는데, mock tier 는 시나리오당
    timeline 이 하나라 1:1 이 성립한다. 이 규약은 정답지 meta 에 적혀 있다.
    """
    if scope["stage"] == "candidate":
        return _run_candidate()
    if scope["stage"] == "plate":
        return _run_plate()
    raise ValueError(
        "mock_pack:contracts 는 stage=candidate|plate 만 지원한다 (받은 값: %r)."
        % scope["stage"]
    )


def _run_candidate():
    out = []
    for scenario in SCENARIOS:
        events = _candidate_events(scenario)
        if events is None:
            # search fixture 가 없다 = 「대상 아님」. 「후보 없음」과 구분한다.
            # 뭉개면 음성 클립 수가 늘어 fp_per_clip 이 조용히 희석된다.
            continue
        cands = normalize.from_candidate_events(events)
        out.append({
            "clip_id": scenario,
            "candidates": [{
                "rank": e["rank"],
                "t_start_sec": e["t_start_sec"],
                "t_end_sec": e["t_end_sec"],
                "representative_sec": e["representative_sec"],
                "timeline_revision": e["timeline_revision"],
                "event_type": e["event_type"],
                "score": e["score"],
            } for e in cands],
        })
    return out


def _run_plate():
    out = []
    for scenario in SCENARIOS:
        doc = _read("readout", scenario + ".json")
        if doc is None:
            continue
        for p in doc.get("plate_readouts", []):
            item = dict(p)
            item["scenario_id"] = scenario
            out.append(item)
    return out
