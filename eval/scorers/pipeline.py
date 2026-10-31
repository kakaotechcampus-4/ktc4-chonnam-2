"""Coarse → Fine 전체 경로 지표.

Coarse 후보 지표(candidate.py)는 그대로 두고, Fine 판정이 붙은 후보로 두 가지를 더 잰다.

- **Fine 판정 분포** — 상위 k개 후보를 정답 사건에 1:1 배정(candidate._assign)한 뒤,
  사건에 붙은 후보(참 후보)와 위반 없는 클립의 후보(거짓 후보)가 각각 어떤 판정을
  받았는지 센다. 위반 클립에서 사건에 붙지 못한 후보는 따로 센다.
- **최종 결과** — Fine을 통과한 후보만 남겨 다시 배정한다. 통과 기준은 둘이다.
  `observed`는 OBSERVED만, `not_rejected`는 NOT_OBSERVED가 아닌 것(제품은
  NOT_OBSERVED만 멈추고 UNCERTAIN은 사용자 확인으로 넘긴다, case/real_e2e.py).

Fine을 돌리지 않았거나 실패한 후보(verification=null)는 통과로 치지 않는다.
"""

from eval.scorers.candidate import DEFAULT_TOLERANCE_SEC, _assign, _partition
from eval.scorers.interval import wilson95

SCORER_VERSION = "pl1"
VERDICTS = ("OBSERVED", "UNCERTAIN", "NOT_OBSERVED", None)
GATES = {
    "observed": lambda v: v == "OBSERVED",
    "not_rejected": lambda v: v in ("OBSERVED", "UNCERTAIN"),
}


def _counts():
    return {str(v): 0 for v in VERDICTS}


def has_verification(normalized):
    return any(c.get("verification") for n in normalized for c in n["candidates"])


def score(normalized, gt, k=3, tolerance_sec=DEFAULT_TOLERANCE_SEC):
    by_clip = {n["clip_id"]: [c for c in n["candidates"] if c["rank"] <= k]
               for n in normalized}
    positives = {}
    negatives = []
    for item in gt["items"]:
        if item.get("not_applicable"):
            continue
        included, _ = _partition(item["targets"], item["clip_id"])
        if item["targets"]:
            if included:
                positives.setdefault(item["clip_id"], []).extend(included)
        else:
            negatives.append(item["clip_id"])

    n_events = sum(len(t) for t in positives.values())
    on_events, unmatched_in_positive, on_negatives = _counts(), _counts(), _counts()
    for clip_id, targets in positives.items():
        cands = by_clip.get(clip_id, [])
        matched = {id(c) for c in _assign(cands, targets, k, tolerance_sec).values()}
        for c in cands:
            bucket = on_events if id(c) in matched else unmatched_in_positive
            bucket[str(c.get("verification"))] += 1
    for clip_id in negatives:
        for c in by_clip.get(clip_id, []):
            on_negatives[str(c.get("verification"))] += 1

    final = {}
    for gate, passes in GATES.items():
        hits = sum(
            len(_assign([c for c in by_clip.get(clip_id, []) if passes(c.get("verification"))],
                        targets, k, tolerance_sec))
            for clip_id, targets in positives.items())
        fp = sum(1 for clip_id in negatives for c in by_clip.get(clip_id, [])
                 if passes(c.get("verification")))
        final[gate] = {
            "recall": hits / n_events if n_events else None,
            "recall_ci95": wilson95(hits, n_events),
            "hits": hits,
            "fp": fp,
            "fp_per_negative_clip": fp / len(negatives) if negatives else None,
            "negative_clips_with_fp": sum(
                1 for clip_id in negatives
                if any(passes(c.get("verification")) for c in by_clip.get(clip_id, []))),
        }

    n_true = sum(on_events.values())
    n_neg = sum(on_negatives.values())
    return {
        "k": k,
        "n_events": n_events,
        "n_negative_clips": len(negatives),
        "verdicts_on_event_candidates": on_events,
        "verdicts_on_unmatched_positive_clip_candidates": unmatched_in_positive,
        "verdicts_on_negative_clip_candidates": on_negatives,
        # 참 후보를 OBSERVED로 본 비율 / 거짓 후보(음성 클립)를 NOT_OBSERVED로 기각한 비율
        "fine_confirm_rate": on_events["OBSERVED"] / n_true if n_true else None,
        "fine_confirm_rate_ci95": wilson95(on_events["OBSERVED"], n_true),
        "fine_reject_rate": on_negatives["NOT_OBSERVED"] / n_neg if n_neg else None,
        "fine_reject_rate_ci95": wilson95(on_negatives["NOT_OBSERVED"], n_neg),
        "final": final,
    }
