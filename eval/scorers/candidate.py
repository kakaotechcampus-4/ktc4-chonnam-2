"""Candidate 단계 지표.

지표 정의의 원문은 module-architecture.md §9-3 과
modules/eval/initial-evaluation-plan.md §2 다. 여기서 새로 만들지 않는다.

단, span_error_sec 는 두 문서 모두 이름만 있고 정의가 없어 여기서 정한다:
recall_at[max(ks)] 계산에서 실제로 적중(matched)한 예측만을 대상으로, GT
시작 시각과의 절대 오차를 잰다. 표본 수는 예측 개수가 아니라 「적중한 사건
수」다 — 매칭되지 않은 예측의 구간 오차는 무엇과 비교해야 할지 정의되지
않으므로 넣지 않는다.
"""
import statistics


def _iou(a_start, a_end, b_start, b_end):
    """두 구간의 IoU.

    union<=0(두 구간이 모두 길이 0으로 겹치는 경우)이면 0.0을 반환해 0-나눗셈을
    피한다. GT 쪽 구간은 t_start_sec < t_end_sec 불변식
    (manifests_io.check_invariants)이 보장하므로 이 분기는 예측(a)이 길이 0일
    때만 닿을 수 있다 — 그런 예측은 겹침(inter)이 항상 0이라 이 분기가 없어도
    iou==0이 나오므로 실측 매칭에는 등장하지 않는다. 그래도 0/0을 1.0으로
    "고쳐" 길이 0인 예측이 매칭에 성공한 것처럼 보이게 만들지 않도록 0.0을
    명시적으로 유지한다.
    """
    inter = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    if union <= 0:
        return 0.0
    return inter / union


# mock tier GT target 은 구간(t_start_sec/t_end_sec) 없이 onset 만 가진다
# (GT target 모양: event_id·scoring·violation_type·t_onset_sec). 그런 GT 를
# 상대할 때는 IoU 를 잴 구간이 없으므로 대표 시점 오차로 적중을 잰다. 이
# tolerance 는 점 오차 매처(Task 4)가 정식 지표로 다듬기 전까지 쓰는 값이다.
ONSET_TOLERANCE_SEC = 2.0


def _hit(c, t, iou_threshold):
    """예측 c 가 정답 t 에 적중하는지 잰다.

    t 에 구간이 있으면(B/A tier) 기존대로 IoU 로 잰다. t 에 구간이 없으면
    (mock tier, onset 만 있음) 예측의 representative_sec 가 GT onset 에서
    ONSET_TOLERANCE_SEC 이내인지로 잰다.
    """
    if "t_start_sec" in t and "t_end_sec" in t:
        return _iou(c["t_start_sec"], c["t_end_sec"],
                     t["t_start_sec"], t["t_end_sec"]) >= iou_threshold
    return abs(c["representative_sec"] - t["t_onset_sec"]) <= ONSET_TOLERANCE_SEC


SCORING_VALUES = ("INCLUDED", "EXCLUDED", "BOUNDARY_EXCLUDED")


def _partition(targets, where):
    """채점 대상과 제외 사유별 개수로 가른다.

    scoring 이 없으면 INCLUDED 로 본다 — 없다고 빼면 분모가 조용히 줄어
    recall 이 부풀려진다. 모르는 값은 채우지 않고 예외로 올린다.
    """
    included = []
    excluded = {}
    for t in targets:
        scoring = t.get("scoring", "INCLUDED")
        if scoring not in SCORING_VALUES:
            raise ValueError("%s: 알 수 없는 scoring %r" % (where, scoring))
        if scoring == "INCLUDED":
            included.append(t)
        else:
            excluded[scoring] = excluded.get(scoring, 0) + 1
    return included, excluded


def score(normalized, gt, ks=(1, 3, 10), iou_threshold=0.5):
    by_clip = {n["clip_id"]: n["candidates"] for n in normalized}

    events = []          # (clip_id, target)
    negative_clips = []
    excluded_by_reason = {}
    for item in gt["items"]:
        if item.get("not_applicable"):
            # 예측을 만들 입력 자체가 없었다. 음성(=후보를 냈어야 하는데
            # 안 냈다)과 다르므로 fp_per_clip 의 분모에 넣지 않는다.
            continue
        included, excluded = _partition(item["targets"], item["clip_id"])
        for reason, n in excluded.items():
            excluded_by_reason[reason] = excluded_by_reason.get(reason, 0) + n
        if item["targets"]:
            for t in included:
                events.append((item["clip_id"], t))
        else:
            negative_clips.append(item["clip_id"])

    loosest_k = max(ks)
    hits = {k: 0 for k in ks}
    span_errors = []
    by_type = {}

    for clip_id, t in events:
        vt = t["violation_type"]
        slot = by_type.setdefault(vt, {"hits": {k: 0 for k in ks}, "n": 0})
        slot["n"] += 1
        cands = by_clip.get(clip_id, [])
        matched_at_loosest = None
        for k in ks:
            topk = [c for c in cands if c["rank"] <= k]
            matched = next(
                (c for c in topk
                 if c["event_type"] == vt and _hit(c, t, iou_threshold)),
                None,
            )
            if matched is not None:
                hits[k] += 1
                slot["hits"][k] += 1
                if k == loosest_k:
                    matched_at_loosest = matched
        # 적중한 예측만 span error에 반영한다 — 모듈 docstring의 정의 참고.
        # GT 에 구간이 없으면(mock tier) 시작 시각 대신 onset 기준으로 잰다.
        if matched_at_loosest is not None:
            if "t_start_sec" in t:
                span_errors.append(abs(matched_at_loosest["t_start_sec"] - t["t_start_sec"]))
            else:
                span_errors.append(abs(matched_at_loosest["representative_sec"] - t["t_onset_sec"]))

    n_events = len(events)
    fp = 0
    for clip_id in negative_clips:
        fp += len(by_clip.get(clip_id, []))

    reasons = []
    if n_events == 0:
        reasons.append("NO_EVENTS — GT 에 채점할 사건이 없다")
    if not negative_clips:
        reasons.append("NO_NEGATIVE_CLIPS — fp_per_clip 을 낼 수 없다")
    if n_events > 0 and not span_errors:
        reasons.append("NO_MATCHED_EVENTS — span_error_sec 를 낼 수 없다")
    for reason, n in sorted(excluded_by_reason.items()):
        # 이걸 적지 않으면 결과의 n_events 와 GT 의 clips_with_events 가
        # 어긋난 이유를 결과 파일만 보고는 알 수 없다 (스펙 §5).
        reasons.append("%s — %d건을 채점에서 제외했다" % (reason, n))

    return {
        "recall_at": {str(k): (hits[k] / n_events if n_events else None) for k in ks},
        "span_error_sec": {
            "mean": statistics.fmean(span_errors) if span_errors else None,
            "median": statistics.median(span_errors) if span_errors else None,
        },
        "fp_per_clip": (fp / len(negative_clips)) if negative_clips else None,
        "n_events": n_events,
        "n_negative_clips": len(negative_clips),
        "excluded_by_reason": excluded_by_reason,
        "by_type": {
            vt: {"recall_at": {str(k): v["hits"][k] / v["n"] for k in ks}, "n": v["n"]}
            for vt, v in sorted(by_type.items())
        },
        "coverage": "; ".join(reasons) if reasons else None,
    }


def not_run(reason, ks=(1, 3, 10)):
    """이번 실행에서 돌지 않은 stage 의 결과 블록.

    키를 빼지 않고 값만 null 로 둔다 — results/*.json 을 모으는 쪽이 「키가
    없는 모양」과 「키가 null 인 모양」을 따로 처리해야 하는 일이 없도록,
    plate 의 무데이터 블록과 같은 규칙을 쓴다. by_type 도 {} 가 아니라 null
    이다: 빈 dict 는 「세어 봤더니 유형이 하나도 없었다」로 읽힌다.
    """
    return {
        "recall_at": {str(k): None for k in ks},
        "span_error_sec": {"mean": None, "median": None},
        "fp_per_clip": None,
        "n_events": None,
        "n_negative_clips": None,
        "excluded_by_reason": None,
        "by_type": None,
        "coverage": reason,
    }
