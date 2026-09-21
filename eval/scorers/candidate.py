"""Candidate 단계 지표.

지표 정의의 원문은 module-architecture.md §9-3 과
modules/eval/initial-evaluation-plan.md §2 다. 여기서 새로 만들지 않는다.

단, onset_error_sec 는 두 문서 모두 이름만 있고 정의가 없어 여기서 정한다:
recall_at[max(ks)] 계산에서 실제로 적중(matched)한 예측만을 대상으로,
예측의 대표 시점(representative_sec)과 GT onset 의 절대 오차를 잰다.
표본 수는 예측 개수가 아니라 「적중한 사건 수」다 — 매칭되지 않은 예측의
오차는 무엇과 비교해야 할지 정의되지 않으므로 넣지 않는다.

2026-09-10 계약 v1.1 §4-1 이 span 을 coarse 후보 창으로 확정하면서 IoU
매칭을 폐기했다. 창은 containment_rate 로만 남는다.

후보와 사건은 클립 단위로 1:1 배정한다 (_assign). 예측 하나가 두 사건의
적중으로 중복 계수되면 recall 이 조용히 부풀어 오르기 때문이다.

**시간 축과 유형 축을 갈라 잰다** (2026-09-20 멘토 피드백). recall_at 은
유형과 시간이 둘 다 맞아야 적중이라, 「순간은 정확히 찾았는데 유형을
잘못 불렀다」와 「아예 못 찾았다」가 똑같이 0 으로 나온다 — 고쳐야 할
곳이 완전히 다른 두 실패다. localization_recall_at 은 시간만 보고,
type_accuracy_given_localized 는 시간이 맞은 사건 중 유형까지 맞은
비율이다.

**두 축은 서로 다른 배정에서 나온다.** 유형을 요구하면 그래프가 달라지고
최대 매칭도 달라지므로, recall_at 은 localization_recall_at 과
type_accuracy_given_localized 의 곱이 아니다. 곱으로 검산하지 않는다.
"""
import statistics

from eval.enums import VIOLATION_TYPES

SCORER_VERSION = "s4"   # 2026-09-20 시간 축(localization)과 유형 축 분리
DEFAULT_TOLERANCE_SEC = 2.0

CIRCULARITY = ("순환 경고 — mock tier 의 onset 은 채점 대상인 예측과 같은 fixture "
               "(span.representative_ms)에서 유도한 값이라 recall·onset_error_sec 는 "
               "구조상 순환적이다. 성능 근거가 아니다")


def _contains(c, onset_sec):
    """coarse 창이 정답 시점을 품는가. 매칭 조건이 아니라 보조 신호다."""
    return c["t_start_sec"] <= onset_sec <= c["t_end_sec"]


def _assign(cands, targets, k, tolerance_sec, require_type=True):
    """top-k 후보와 사건을 1:1 로 배정한다. 반환은 {사건 인덱스: 후보}.

    require_type=False 면 유형을 보지 않고 시간만으로 잇는다 —
    localization 축이 쓴다. 이때도 같은 거리라면 유형이 맞는 후보를 먼저
    본다. 아니면 유형 정확도가 동률 배정 운에 휘둘린다.

    예측 하나가 두 사건의 적중으로 중복 계수되지 않게 한다 (F7).

    탐욕이 아니라 최대 매칭(Kuhn)을 쓴다. 탐욕은 먼저 나온 사건이 후보를
    삼켜 뒤의 사건이 굶을 수 있고, 그러면 recall 이 정답지의 사건 나열
    순서에 따라 달라진다. 최대 매칭의 크기는 그 순서와 무관하다.

    **크기만 유일하고 어느 쌍으로 맺는지는 유일하지 않다.** recall 은 크기만
    쓰지만 onset_error_sec·containment_rate 는 선택된 쌍을 쓰므로, 배정이
    정답지 줄 순서를 타면 같은 예측·같은 사건인데 containment 가 뒤집힌다.
    그래서 두 가지를 고정한다:

    - 사건을 (onset, event_id) 정규 순서로 처리한다 — 파일 줄 순서가 아니다
    - 각 사건의 간선을 (onset 오차, rank) 오름차순으로 본다 — 자유로운
      배정에서는 가까운 후보에 붙는다

    후보는 같은 event_type 하고만 이어지므로 그래프가 유형별로 쪼개진다 —
    by_type 집계가 전체 집계와 저절로 일치한다.
    """
    topk = [c for c in cands if c["rank"] <= k]

    def _edges(t):
        hits = []
        for j, c in enumerate(topk):
            same_type = c["event_type"] == t["violation_type"]
            if require_type and not same_type:
                continue
            err = abs(c["representative_sec"] - t["t_onset_sec"])
            if err > tolerance_sec:
                continue
            hits.append((0 if same_type else 1, err, c["rank"], j))
        return [j for _, _, _, j in sorted(hits)]

    adj = [_edges(t) for t in targets]
    owner = {}                      # 후보 인덱스 -> 사건 인덱스

    def _augment(i, seen):
        for j in adj[i]:
            if j in seen:
                continue
            seen.add(j)
            if j not in owner or _augment(owner[j], seen):
                owner[j] = i
                return True
        return False

    order = sorted(range(len(targets)),
                   key=lambda i: (targets[i]["t_onset_sec"],
                                  str(targets[i].get("event_id") or "")))
    for i in order:
        _augment(i, set())
    return {i: topk[j] for j, i in owner.items()}


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
        if scoring == "INCLUDED" and t.get("violation_type") is None:
            raise ValueError(
                "%s: violation_type 이 없는 target 은 채점할 수 없다. 참값 유형이 "
                "없으면 scoring='EXCLUDED' 여야 한다 (event_id=%r)"
                % (where, t.get("event_id")))
        if scoring == "INCLUDED":
            included.append(t)
        else:
            excluded[scoring] = excluded.get(scoring, 0) + 1
    return included, excluded


def score(normalized, gt, ks=(1, 3, 10), tolerance_sec=DEFAULT_TOLERANCE_SEC):
    by_clip = {n["clip_id"]: n["candidates"] for n in normalized}

    # 배정은 클립 단위다 — 후보는 자기 클립의 사건하고만 이어진다.
    # 같은 clip_id 가 GT 항목 여럿으로 쪼개져 있어도 한 번만 배정해야 한다.
    # 항목별로 배정하면 _assign 이 따로 돌아 같은 후보가 양쪽에서 적중으로
    # 세어진다 — 1:1 배정이 막으려는 바로 그 중복 계수다.
    targets_by_clip = {}            # clip_id -> [target, ...] (등장 순서 유지)
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
            if included:
                targets_by_clip.setdefault(item["clip_id"], []).extend(included)
        else:
            negative_clips.append(item["clip_id"])
    clips_with_events = list(targets_by_clip.items())

    loosest_k = max(ks)
    hits = {k: 0 for k in ks}
    loc_hits = {k: 0 for k in ks}
    n_localized = n_type_correct = 0
    onset_errors = []
    contained = []
    by_type = {}

    n_events = 0
    for clip_id, targets in clips_with_events:
        cands = by_clip.get(clip_id, [])
        n_events += len(targets)
        for t in targets:
            slot = by_type.setdefault(t["violation_type"],
                                      {"hits": {k: 0 for k in ks}, "n": 0})
            slot["n"] += 1
        for k in ks:
            assigned = _assign(cands, targets, k, tolerance_sec)
            hits[k] += len(assigned)
            for i in assigned:
                by_type[targets[i]["violation_type"]]["hits"][k] += 1
            if k == loosest_k:
                for i, c in assigned.items():
                    onset = targets[i]["t_onset_sec"]
                    onset_errors.append(abs(c["representative_sec"] - onset))
                    contained.append(_contains(c, onset))

            # 시간 축은 따로 배정한다. 유형 제약을 풀면 그래프가 달라져
            # 최대 매칭도 달라지므로 위 배정을 재활용할 수 없다.
            localized = _assign(cands, targets, k, tolerance_sec, require_type=False)
            loc_hits[k] += len(localized)
            if k == loosest_k:
                n_localized += len(localized)
                n_type_correct += sum(
                    1 for i, c in localized.items()
                    if c["event_type"] == targets[i]["violation_type"])
    fp = 0
    for clip_id in negative_clips:
        fp += len(by_clip.get(clip_id, []))

    cov = (gt.get("meta") or {}).get("coverage") or {}
    circular = bool(cov.get("derived_from_mock_pack")) or cov.get("independent_ground_truth") is False

    reasons = []
    if circular:
        reasons.append(CIRCULARITY)
    if n_events == 0:
        reasons.append("NO_EVENTS — GT 에 채점할 사건이 없다")
    if not negative_clips:
        reasons.append("NO_NEGATIVE_CLIPS — fp_per_clip 을 낼 수 없다")
    if n_events > 0 and not onset_errors:
        reasons.append("NO_MATCHED_EVENTS — onset_error_sec 를 낼 수 없다")
    if n_events > 0 and not n_localized:
        # 유형 정확도의 분모가 0 이다. 「유형을 다 틀렸다」가 아니라
        # 「유형을 따질 만큼 시간을 맞힌 사건이 없다」이므로 0 이 아닌 null.
        reasons.append("NO_LOCALIZED_EVENTS — 허용 오차 안에 든 사건이 없어 "
                       "type_accuracy_given_localized 를 낼 수 없다 (0 이 아니다)")
    missing_types = [t for t in VIOLATION_TYPES if t not in by_type]
    if missing_types:
        # by_type 에 키가 없는 것과 값이 0 인 것을 결과 파일만 보고는 구분할
        # 수 없다. 적지 않으면 baseline 4종 중 몇 종을 아예 못 쟀다는 사실이
        # 조용히 사라진다 (B tier 의 안전모가 지금 그 상태다).
        reasons.append(
            "NO_EVENTS_FOR_TYPE — %s 유형의 사건이 정답지에 없다. 이 유형의 "
            "recall 은 측정되지 않았다 (0점이 아니다)" % ", ".join(missing_types))
    for reason, n in sorted(excluded_by_reason.items()):
        # 이걸 적지 않으면 결과의 n_events 와 GT 의 clips_with_events 가
        # 어긋난 이유를 결과 파일만 보고는 알 수 없다 (스펙 §5).
        reasons.append("%s — %d건을 채점에서 제외했다" % (reason, n))

    return {
        "recall_at": {str(k): (hits[k] / n_events if n_events else None) for k in ks},
        "localization_recall_at": {
            str(k): (loc_hits[k] / n_events if n_events else None) for k in ks},
        "type_accuracy_given_localized": (
            (n_type_correct / n_localized) if n_localized else None),
        "onset_error_sec": {
            "mean": statistics.fmean(onset_errors) if onset_errors else None,
            "median": statistics.median(onset_errors) if onset_errors else None,
            "tolerance_sec": tolerance_sec,
        },
        "containment_rate": (sum(contained) / len(contained)) if contained else None,
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
        "localization_recall_at": {str(k): None for k in ks},
        "type_accuracy_given_localized": None,
        "onset_error_sec": {"mean": None, "median": None, "tolerance_sec": None},
        "containment_rate": None,
        "fp_per_clip": None,
        "n_events": None,
        "n_negative_clips": None,
        "excluded_by_reason": None,
        "by_type": None,
        "coverage": reason,
    }
