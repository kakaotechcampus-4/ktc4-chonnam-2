"""Candidate 단계 지표.

지표 정의의 원문은 module-architecture.md §9-3 과
modules/eval/initial-evaluation-plan.md §2 다. 여기서 새로 만들지 않는다.
"""
import statistics


def _iou(a_start, a_end, b_start, b_end):
    inter = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    if union <= 0:
        return 0.0
    return inter / union


def score(normalized, gt, ks=(1, 3, 10), iou_threshold=0.5):
    by_clip = {n["clip_id"]: n["candidates"] for n in normalized}

    events = []          # (clip_id, target)
    negative_clips = []
    for item in gt["items"]:
        included = [t for t in item["targets"] if t.get("scoring") != "BOUNDARY_EXCLUDED"]
        if item["targets"]:
            for t in included:
                events.append((item["clip_id"], t))
        else:
            negative_clips.append(item["clip_id"])

    hits = {k: 0 for k in ks}
    span_errors = []
    by_type = {}

    for clip_id, t in events:
        vt = t["violation_type"]
        slot = by_type.setdefault(vt, {"hits": {k: 0 for k in ks}, "n": 0})
        slot["n"] += 1
        cands = by_clip.get(clip_id, [])
        for k in ks:
            topk = [c for c in cands if c["rank"] <= k]
            matched = next(
                (c for c in topk
                 if c["event_type"] == vt
                 and _iou(c["t_start_sec"], c["t_end_sec"],
                          t["t_start_sec"], t["t_end_sec"]) >= iou_threshold),
                None,
            )
            if matched is not None:
                hits[k] += 1
                slot["hits"][k] += 1
        # span error 는 rank1 후보 기준. 폭이 0 인 예측(Mock Pack 유래)은 제외한다.
        if cands:
            top = cands[0]
            if top["t_end_sec"] > top["t_start_sec"]:
                span_errors.append(abs(top["t_start_sec"] - t["t_start_sec"]))

    n_events = len(events)
    fp = 0
    for clip_id in negative_clips:
        fp += len(by_clip.get(clip_id, []))

    return {
        "recall_at": {str(k): (hits[k] / n_events if n_events else None) for k in ks},
        "span_error_sec": {
            "mean": statistics.fmean(span_errors) if span_errors else None,
            "median": statistics.median(span_errors) if span_errors else None,
        },
        "fp_per_clip": (fp / len(negative_clips)) if negative_clips else None,
        "n_events": n_events,
        "n_negative_clips": len(negative_clips),
        "by_type": {
            vt: {"recall_at": {str(k): v["hits"][k] / v["n"] for k in ks}, "n": v["n"]}
            for vt, v in sorted(by_type.items())
        },
        "coverage": None if n_events else "NO_EVENTS — GT 에 채점할 사건이 없다",
    }
