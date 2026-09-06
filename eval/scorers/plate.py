"""Plate 단계 지표.

A tier 는 번호판이 비식별 처리되어 문자 정답이 없다
(harness-v1-design.md §4-3). C tier 가 들어오기 전까지 전부 null 이다.
0 으로 적지 않는다 — 데이터가 없는 것과 성능이 나쁜 것은 다른 사실이다.
"""

NO_DATA = ("NO_C_TIER_DATA — plate text GT 부재. "
           "A tier 는 번호판 마스킹(harness-v1-design.md §4-3)")


def score(normalized, gt):
    if not gt or not gt.get("items"):
        return {"exact_accuracy": None, "wrong_accept_rate": None,
                "abstention_recall": None, "n": 0, "coverage": NO_DATA}

    total = correct = wrong_accept = 0
    abstain_total = abstain_correct = 0
    by_id = {n["sequence_id"]: n for n in normalized}
    for item in gt["items"]:
        truth = item.get("plate_text")
        pred = by_id.get(item["sequence_id"], {}).get("plate_value")
        if truth is None:
            abstain_total += 1
            if pred is None:
                abstain_correct += 1
            continue
        total += 1
        if pred == truth:
            correct += 1
        elif pred is not None:
            wrong_accept += 1

    return {
        "exact_accuracy": (correct / total) if total else None,
        "wrong_accept_rate": (wrong_accept / total) if total else None,
        "abstention_recall": (abstain_correct / abstain_total) if abstain_total else None,
        "n": total + abstain_total,
        "coverage": None,
    }
