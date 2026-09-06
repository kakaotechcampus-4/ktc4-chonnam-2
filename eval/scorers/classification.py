"""Classification 단계 지표 (v4 §9-3).

confusion matrix 는 4종 + NONE 의 5×5 다.
"""
import collections

from eval.enums import CLASS_LABELS


def _macro(per_label):
    vals = [v for v in per_label.values() if v is not None]
    return sum(vals) / len(vals) if vals else None


def score(normalized, gt):
    gt_by_id = {i["sequence_id"]: i for i in gt["items"]}
    pred_by_id = {n["sequence_id"]: n for n in normalized}

    confusion = {a: {b: 0 for b in CLASS_LABELS} for a in CLASS_LABELS}
    tp = collections.Counter()
    fp = collections.Counter()
    fn = collections.Counter()
    by_cond = collections.defaultdict(lambda: {"correct": 0, "n": 0})

    target_hits = 0
    target_total = 0

    for sid, item in gt_by_id.items():
        truth = item["label"]
        # 예측이 없는 GT 항목은 "NONE" 을 예측한 것으로 취급한다 — 조용히
        # 사라지지 않고 명시적으로 미탐(miss)으로 채점된다.
        pred = pred_by_id.get(sid, {}).get("predicted", "NONE")
        if truth in confusion and pred in confusion[truth]:
            confusion[truth][pred] += 1
        if pred == truth:
            tp[truth] += 1
        else:
            fn[truth] += 1
            fp[pred] += 1

        cond = item.get("condition") or {}
        dn = cond.get("day_night")
        if dn:
            by_cond[dn]["n"] += 1
            if pred == truth:
                by_cond[dn]["correct"] += 1

        # target_bbox 가 없는 GT 항목(원본 라벨에 위반 차량 bbox 부재)은
        # target_correctness 분모에서 제외한다 — 미탐으로 세지 않는다.
        gt_box = item.get("target_bbox")
        if gt_box:
            target_total += 1
            if pred_by_id.get(sid, {}).get("target_bbox") == gt_box:
                target_hits += 1

    recall = {}
    precision = {}
    for label in CLASS_LABELS:
        denom_r = tp[label] + fn[label]
        denom_p = tp[label] + fp[label]
        recall[label] = tp[label] / denom_r if denom_r else None
        precision[label] = tp[label] / denom_p if denom_p else None

    return {
        "recall_macro": _macro(recall),
        "precision_macro": _macro(precision),
        "recall_by_label": recall,
        "confusion": confusion,
        "target_correctness": (target_hits / target_total) if target_total else None,
        "by_condition": {
            "day_night": {k: {"accuracy": v["correct"] / v["n"], "n": v["n"]}
                          for k, v in sorted(by_cond.items())}
        },
        "n": len(gt_by_id),
        "coverage": None if gt_by_id else "NO_SEQUENCES — GT 가 비어 있다",
    }
