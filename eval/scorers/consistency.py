"""반복 실행 일관성 지표 (candidate stage).

비결정적 모델은 같은 클립을 다시 돌리면 다른 답을 낸다. 1회 실행의 recall
은 그 회차의 운을 섞어 낸다. 같은 설정으로 n회 돌린 예측을 묶어, 정답
사건마다 n회 중 몇 번 맞혔는지를 센다 (2026-10-02 멘토 리뷰 #213, #226).

적중 정의는 candidate.py 와 같다 — 같은 배정(_assign)·같은 채점 대상
분할(_partition)·같은 허용 오차를 쓴다. 여기서 적중을 새로 정의하면 1회
결과와 반복 결과가 다른 잣대로 재게 된다.

**하나로 합친 점수는 아직 내지 않는다.** 정확도와 일관성을 어떻게 합칠지는
search 와 합의 중이다(#226 미결). 재료(사건별 적중 횟수, 회차별 recall·오탐)
만 낸다.
"""
import statistics

from eval.scorers import candidate
from eval.scorers.interval import wilson95

SCORER_VERSION = "r1"   # 2026-10-02 처음 정의


def _targets_and_negatives(gt):
    """candidate.score 와 같은 규칙으로 클립별 채점 대상과 음성 클립을 고른다."""
    targets_by_clip = {}
    negative_clips = []
    for item in gt["items"]:
        if item.get("not_applicable"):
            continue
        included, _ = candidate._partition(item["targets"], item["clip_id"])
        if item["targets"]:
            if included:
                targets_by_clip.setdefault(item["clip_id"], []).extend(included)
        else:
            negative_clips.append(item["clip_id"])
    return targets_by_clip, negative_clips


def score(runs, gt, k=3, tolerance_sec=candidate.DEFAULT_TOLERANCE_SEC):
    """runs 는 회차별 normalized 목록이다 (같은 설정으로 돌린 것)."""
    n_runs = len(runs)
    targets_by_clip, negative_clips = _targets_and_negatives(gt)

    events = []                         # (clip_id, target) — 정규 순서
    for clip_id in sorted(targets_by_clip):
        for t in targets_by_clip[clip_id]:
            events.append((clip_id, t))
    hits = [0] * len(events)
    recall_by_run = []
    fp_by_run = []

    for normalized in runs:
        by_clip = {n["clip_id"]: n["candidates"] for n in normalized}
        idx = 0
        run_hits = 0
        for clip_id in sorted(targets_by_clip):
            targets = targets_by_clip[clip_id]
            assigned = candidate._assign(by_clip.get(clip_id, []), targets, k,
                                         tolerance_sec)
            for i in range(len(targets)):
                if i in assigned:
                    hits[idx + i] += 1
                    run_hits += 1
            idx += len(targets)
        recall_by_run.append(run_hits / len(events) if events else None)
        fp_by_run.append(sum(len(by_clip.get(c, [])) for c in negative_clips))

    n_events = len(events)
    always = sum(1 for h in hits if h == n_runs)
    never = sum(1 for h in hits if h == 0)
    flaky = n_events - always - never

    reasons = []
    if n_runs < 2:
        reasons.append("SINGLE_RUN — 회차가 1개라 일관성을 잴 수 없다")
    if n_events == 0:
        reasons.append("NO_EVENTS — GT 에 채점할 사건이 없다")
    if not negative_clips:
        reasons.append("NO_NEGATIVE_CLIPS — 회차별 오탐을 낼 수 없다")

    def _ratio(x):
        return x / n_events if n_events else None

    return {
        "k": k,
        "tolerance_sec": tolerance_sec,
        "n_runs": n_runs,
        "n_events": n_events,
        "n_negative_clips": len(negative_clips),
        # 사건 단위: n회 중 몇 번 top-k 에 맞혔나
        "always_hit": always,
        "always_hit_ratio": _ratio(always),
        "always_hit_ratio_ci95": wilson95(always, n_events),
        "flaky": flaky,
        "flaky_ratio": _ratio(flaky),
        "never_hit": never,
        "never_hit_ratio": _ratio(never),
        "hit_count_histogram": {str(c): sum(1 for h in hits if h == c)
                                for c in range(n_runs + 1)},
        # 회차 단위
        "recall_at_k_by_run": recall_by_run,
        "recall_at_k_mean": (statistics.fmean(recall_by_run)
                             if events and recall_by_run else None),
        "fp_per_negative_clip_by_run": [
            (fp / len(negative_clips)) if negative_clips else None for fp in fp_by_run],
        "per_event": [
            {"clip_id": clip_id, "event_id": t.get("event_id"),
             "violation_type": t["violation_type"], "hits": h}
            for (clip_id, t), h in zip(events, hits)
        ],
        "coverage": "; ".join(reasons) if reasons else None,
    }
