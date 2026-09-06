"""Classification 단계 지표 (v4 §9-3).

confusion matrix 는 4종 + NONE 의 5×5 다.

target_correctness 는 이 문서 체계 어디에도 정의가 없어 여기서 정한다:
예측 bbox 와 GT bbox(둘 다 [x1, y1, x2, y2], 픽셀)의 2-D IoU 가
_TARGET_BBOX_IOU_THRESHOLD 이상이면 correct 다. bbox 한 픽셀 밀림까지
완전 일치를 요구하면 실제 탐지기는 전부 0점을 받는다 — "측정했고 0"과
"애초에 잴 게 없다"를 구분하려던 null 규율이, 이번엔 정의 자체의
과도한 엄격함 때문에 무너지지 않도록 느슨한 임계값을 쓴다.
"""
import collections

from eval.enums import CLASS_LABELS

_LABEL_SET = set(CLASS_LABELS)

# bbox 매치 판정 임계값. candidate.score 의 iou_threshold(시간 구간)와
# 별개다 — 여기는 2-D 공간 IoU.
_TARGET_BBOX_IOU_THRESHOLD = 0.5


def _macro(per_label):
    vals = [v for v in per_label.values() if v is not None]
    return sum(vals) / len(vals) if vals else None


def _iou_2d(a, b):
    """두 bbox의 2-D IoU. bbox = [x1, y1, x2, y2] (x1<x2, y1<y2 가정).

    형태가 다르면(길이 4가 아니면) 매치 실패로 취급해 0.0 을 반환한다 —
    normalize.py 가 target_bbox 의 형태를 검증하지 않으므로 여기서 크래시
    시키지 않는다. 교차 폭·높이는 candidate._iou 와 같은 이유로 0 미만을
    0 으로 클램프한다. 합집합 넓이가 0 이하(두 bbox 모두 넓이 0)이면 0/0
    을 피하려고 0.0 을 반환한다 — 넓이 0인 bbox 가 매치된 것처럼 보이지
    않도록 명시적으로 유지한다.
    """
    if len(a) != 4 or len(b) != 4:
        return 0.0
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    iw = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


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
    n_invalid_predictions = 0
    n_invalid_gt_labels = 0
    n_scored = 0

    for sid, item in gt_by_id.items():
        truth = item["label"]
        if truth not in _LABEL_SET:
            # GT 라벨 자체가 baseline enum 밖이면 진실을 지어낼 수 없다 —
            # 나머지 항목만으로 조용히 점수를 내지 않고 채점에서 제외한다.
            n_invalid_gt_labels += 1
            continue
        n_scored += 1

        # 예측이 없는 GT 항목은 "NONE"을 예측한 것으로 명시적으로 채점한다
        # — 조용히 사라지지 않고 미탐(miss)으로 잡힌다.
        raw_pred = pred_by_id.get(sid, {}).get("predicted", "NONE")
        if raw_pred in _LABEL_SET:
            pred = raw_pred
        else:
            # baseline enum 밖의 예측("어떤 위반 유형도 아니다"로 해석 불가)은
            # 의미상 NONE과 같다 — NONE 열로 접어서 사라지지도, NONE보다
            # 유리하게 채점되지도 않게 한다.
            pred = "NONE"
            n_invalid_predictions += 1

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

        # target_bbox 가 없는(None) GT 항목(원본 라벨에 위반 차량 bbox 부재)은
        # target_correctness 분모에서 제외한다 — 미탐으로 세지 않는다.
        # 빈 리스트([])는 None 과 다른 값이므로 별도로 구분해 둔다.
        gt_box = item.get("target_bbox")
        if gt_box is not None:
            target_total += 1
            pred_box = pred_by_id.get(sid, {}).get("target_bbox")
            if pred_box is not None and _iou_2d(pred_box, gt_box) >= _TARGET_BBOX_IOU_THRESHOLD:
                target_hits += 1

    recall = {}
    precision = {}
    for label in CLASS_LABELS:
        denom_r = tp[label] + fn[label]
        denom_p = tp[label] + fp[label]
        recall[label] = tp[label] / denom_r if denom_r else None
        precision[label] = tp[label] / denom_p if denom_p else None

    reasons = []
    if not gt_by_id:
        reasons.append("NO_SEQUENCES — GT 가 비어 있다")
    if n_invalid_gt_labels:
        reasons.append(
            "INVALID_GT_LABELS — baseline enum 밖의 GT 라벨 %d건을 채점에서 제외했다"
            % n_invalid_gt_labels
        )
    if n_invalid_predictions:
        reasons.append(
            "INVALID_PREDICTIONS — baseline enum 밖의 예측 %d건을 NONE으로 접어 채점했다"
            % n_invalid_predictions
        )

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
        "n": n_scored,
        "n_invalid_predictions": n_invalid_predictions,
        "n_invalid_gt_labels": n_invalid_gt_labels,
        "coverage": "; ".join(reasons) if reasons else None,
    }
