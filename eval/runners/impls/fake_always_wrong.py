"""의도적으로 틀린 답을 내는 치트 구현.

지표 계산이 오류를 실제로 잡아내는지 확인하는 용도다.
심는 오류: 유형 오분류 + 구간을 GT 밖으로 밀기 + negative 클립에 오탐.
classification 에서는 유형 오분류 + target bbox 를 화면 밖으로 밀기.

stage 마다 GT 항목의 모양이 다르다 (candidate 는 `targets`, classification
은 `label`). 그래서 stage 별로 갈라서 처리한다.
"""
from eval import manifests_io
from eval.enums import VIOLATION_TYPES

IMPL_VERSION = "v1"

# GT bbox 를 이만큼 밀면 어떤 GT bbox(최대 폭 939px · 높이 1241px)와도
# 겹치지 않아 2-D IoU 가 0 이 된다.
_BBOX_SHIFT_PX = 10000


def _other_type(t):
    for name in VIOLATION_TYPES:
        if name != t:
            return name
    raise AssertionError("baseline 이 1종뿐일 수 없다")


def _shift_far(box):
    """bbox 를 통째로 밀어 GT 와의 교차를 0 으로 만든다. 없으면 None 그대로."""
    if box is None:
        return None
    return [v + _BBOX_SHIFT_PX for v in box]


def _candidate(gt):
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


def _classification(gt):
    return [
        {"sequence_id": item["sequence_id"],
         "predicted": _other_type(item["label"]),
         "target_bbox": _shift_far(item.get("target_bbox"))}
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
