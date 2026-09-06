"""GT 를 그대로 되돌려주는 치트 구현.

지표 계산이 「정답일 때 만점」을 내는지 확인하는 용도다.
GT 를 스스로 읽는다 — runner 가 넘겨주지 않는다.

stage 마다 GT 항목의 모양이 다르다 (candidate 는 `targets`, classification
은 `label`). 그래서 stage 별로 갈라서 처리한다.
"""
from eval import manifests_io

IMPL_VERSION = "v1"


def _candidate(gt):
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


def _classification(gt):
    """GT 라벨과 GT bbox 를 그대로 예측으로 돌려준다.

    target_bbox 가 없는(None) GT 항목은 None 그대로 둔다 — 없는 정답을
    지어내지 않는다. scorer 는 그런 항목을 target_correctness 분모에서 뺀다.
    """
    return [
        {"sequence_id": item["sequence_id"],
         "predicted": item["label"],
         "target_bbox": item.get("target_bbox")}
        for item in gt["items"]
    ]


_BY_STAGE = {"candidate": _candidate, "classification": _classification}


def run(scope):
    stage = scope["stage"]
    if stage not in _BY_STAGE:
        raise ValueError(
            "이 구현이 다루지 않는 stage: %r (가능: %s)" % (stage, ", ".join(sorted(_BY_STAGE)))
        )
    gt = manifests_io.load_gt(scope["manifest"], stage)
    return _BY_STAGE[stage](gt)
