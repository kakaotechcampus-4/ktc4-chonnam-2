"""Plate 단계 지표.

정답 판정은 abstained × GT legibility 교차표다.

                 GT READABLE                    GT UNREADABLE
 abstained=false exact_match: value==true_text  wrong_accept
 abstained=true  놓친 판독                       abstention_recall 적중

wrong_accept_rate 의 분모는 「정답이 UNREADABLE 인 항목」이다 —
abstained=true 인 예측이 아니다(harness-v1-design.md §9 F6, ADR §4.10).
판독 불가 번호판에 확신을 담아 값을 내는 것이야말로 이 지표가 잡을 오류다.

A tier 는 번호판이 비식별 처리되어 문자 정답이 없다. GT 가 없으면 0 이
아니라 null 이다 — 데이터가 없는 것과 성능이 나쁜 것은 다른 사실이다.
"""

SCORER_VERSION = "p1"   # 2026-09-14 plate 채점 경로 신설 (abstained x legibility 교차표)

NO_GT = ("NO_PLATE_GT — 이 manifest 에 plate 정답지가 없다. "
         "A tier 는 번호판 마스킹(harness-v1-design.md §4-3)")

CIRCULARITY = ("순환 경고 — mock tier 의 true_text 는 판독 결과에서 유도한 "
               "값이라 exact_accuracy 는 구조상 만점이다. 성능 근거가 아니다")

ZERO_NUMERATOR = ("wrong_accept_rate 분자 0건 — pack 에 「확신에 차서 틀리게 "
                  "읽은」 케이스가 없다. 안전하다는 증거가 아니다")


def not_run(reason):
    return {"exact_accuracy": None, "wrong_accept_rate": None,
            "abstention_recall": None, "n": None, "coverage": reason}


def score(normalized, gt):
    if gt is None:
        return not_run(NO_GT)

    truth = {t["readout_id"]: t for t in gt["items"]}
    n_exact_den = n_exact_hit = 0
    n_unreadable = n_abstained = n_wrong_accept = 0
    n_scored = 0
    circular = False

    for pred in normalized:
        t = truth.get(pred["readout_id"])
        if t is None:
            continue                      # 정답지에 없는 판독은 채점 대상이 아니다
        n_scored += 1
        circular = circular or bool(t.get("derived_from_pack"))
        if t["legibility"] == "READABLE":
            if not pred["abstained"]:
                n_exact_den += 1
                if pred["value"] == t["true_text"]:
                    n_exact_hit += 1
        else:
            n_unreadable += 1
            if pred["abstained"]:
                n_abstained += 1
            else:
                n_wrong_accept += 1

    reasons = []
    if circular:
        reasons.append(CIRCULARITY)
    if n_unreadable and not n_wrong_accept:
        reasons.append(ZERO_NUMERATOR)
    if not n_scored:
        reasons.append("NO_SCORED_READOUTS — 정답지와 겹치는 판독이 없다")

    return {
        "exact_accuracy": (n_exact_hit / n_exact_den) if n_exact_den else None,
        "wrong_accept_rate": (n_wrong_accept / n_unreadable) if n_unreadable else None,
        "abstention_recall": (n_abstained / n_unreadable) if n_unreadable else None,
        "n": n_scored,
        "coverage": "; ".join(reasons) if reasons else None,
    }
