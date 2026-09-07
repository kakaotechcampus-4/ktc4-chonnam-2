"""팀 공용 Mock Pack 산출물을 읽는 impl.

`fake:` 접두어를 쓰지 않는다 — 정답지를 몰래 읽는 치트가 아니라 다른 Owner 가
만든 계약 산출물을 읽는다. 실제 구현이 붙기 전까지 그 자리를 대신한다.

납작한 eval fixture(data/mock/eval/prediction_*.json)가 아니라 **계약 산출물**
(data/mock/search/candidate_events.*.json)을 읽는다. eval fixture 에는 구간이
없어 IoU 매칭이 성립하지 않는데, 계약 쪽에는 span 이 있기 때문이다.

`eval` 은 `case`·`search` 의 코드를 import 하지 않는다. 파일만 읽는다.
"""
import json
import os

from eval import paths
from eval.runners import normalize

IMPL_VERSION = "v1"

# Seed Mock v0 이 담은 시나리오. Mock Pack 이 v1 로 재생성되면 여기를 본다.
SCENARIO = "scenario_happy_001"

_MOCK = os.path.join(paths.REPO_ROOT, "data", "mock")


def _read(*parts):
    with open(os.path.join(_MOCK, *parts), encoding="utf-8") as f:
        return json.load(f)


def run(scope):
    """계약 산출물을 candidate 단계 raw 로 옮긴다.

    scope 는 {"manifest", "stage"} 만 담는다 — 정답지는 넘어오지 않고,
    이 impl 도 정답지를 열지 않는다.

    clip_id 자리에 scenario_id 를 쓴다. 계약은 timeline_id + 밀리초 offset 으로
    위치를 말하고 정답지는 clip_id 로 말하는데 그 대응을 아직 어느 계약도
    정하지 않았다 (Consumer 검수 항목). 시나리오 1건이므로 시나리오를
    clip 으로 취급하는 것이 지금 할 수 있는 가장 덜 지어내는 선택이다.
    """
    if scope["stage"] != "candidate":
        raise ValueError(
            "mock_pack:contracts 는 stage=candidate 만 지원한다 (받은 값: %r). "
            "Mock Pack 에 classification 정답지가 없다." % scope["stage"]
        )

    suffix = SCENARIO.replace("scenario_", "")
    events = normalize.from_candidate_events(
        _read("search", "candidate_events.%s.json" % suffix))

    return [{
        "clip_id": SCENARIO,
        "candidates": [{
            "rank": e["rank"],
            "t_start_sec": e["t_start_sec"],
            "t_end_sec": e["t_end_sec"],
            "event_type": e["event_type"],
            "score": e["score"],
        } for e in events],
    }]
