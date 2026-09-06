"""GT 를 그대로 되돌려주는 치트 구현.

지표 계산이 「정답일 때 만점」을 내는지 확인하는 용도다.
GT 를 스스로 읽는다 — runner 가 넘겨주지 않는다.
"""
from eval import manifests_io

IMPL_VERSION = "v1"


def run(scope):
    gt = manifests_io.load_gt(scope["manifest"], scope["stage"])
    out = []
    for item in gt["items"]:
        cands = [
            {"rank": i + 1,
             "t_start_sec": t["t_start_sec"],
             "t_end_sec": t["t_end_sec"],
             "event_type": t["violation_type"],
             "score": 1.0 - i * 0.01}
            for i, t in enumerate(item["targets"])
        ]
        out.append({"clip_id": item["clip_id"], "candidates": cands})
    return out
