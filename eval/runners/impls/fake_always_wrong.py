"""의도적으로 틀린 답을 내는 치트 구현.

지표 계산이 오류를 실제로 잡아내는지 확인하는 용도다.
심는 오류: 유형 오분류 + 구간을 GT 밖으로 밀기 + negative 클립에 오탐.
"""
from eval import manifests_io
from eval.enums import VIOLATION_TYPES


def _other_type(t):
    for name in VIOLATION_TYPES:
        if name != t:
            return name
    raise AssertionError("baseline 이 1종뿐일 수 없다")


def run(scope):
    gt = manifests_io.load_gt(scope["manifest"], scope["stage"])
    out = []
    for item in gt["items"]:
        if item["targets"]:
            cands = [
                {"rank": i + 1,
                 "t_start_sec": float(t["t_end_sec"]) + 5.0,
                 "t_end_sec": float(t["t_end_sec"]) + 8.0,
                 "event_type": _other_type(t["violation_type"]),
                 "score": 0.5 - i * 0.01}
                for i, t in enumerate(item["targets"])
            ]
        else:
            # negative 클립에 오탐을 심는다 — FP/clip 이 0 이 아니어야 한다.
            cands = [{"rank": 1, "t_start_sec": 1.0, "t_end_sec": 3.0,
                      "event_type": VIOLATION_TYPES[0], "score": 0.5}]
        out.append({"clip_id": item["clip_id"], "candidates": cands})
    return out
