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

**기권만 하는 모델을 막는 자리도 여기다** (2026-09-20 멘토 피드백). 위
교차표의 세 숫자만으로는 아무것도 안 읽은 모델이 wrong_accept_rate 0.0 ·
abstention_recall 1.0 을 받고 exact_accuracy 는 null 이 된다 — 만점 두 개와
「데이터 없음」이다. readable_abstention_rate 가 그 자리를 메운다:
읽을 수 있었는데 기권한 비율이고, 전부 기권하면 1.0 이다.

가중 합산 점수는 여기서 만들지 않는다. 「기권 1건이 오답 몇 건 값이냐」는
제품이 정할 값이지 채점기가 정할 값이 아니다.
"""

SCORER_VERSION = "p2"   # 2026-09-20 readable_abstention_rate 신설 + abstain 사유 집계

NO_GT = ("NO_PLATE_GT — 이 manifest 에 plate 정답지가 없다. "
         "A tier 는 번호판 마스킹(harness-v1-design.md §4-3)")

CIRCULARITY = ("순환 경고 — mock tier 의 true_text 는 판독 결과에서 유도한 "
               "값이라 exact_accuracy 는 구조상 만점이다. 성능 근거가 아니다")

ZERO_NUMERATOR = ("wrong_accept_rate 분자 0건 — pack 에 「확신에 차서 틀리게 "
                  "읽은」 케이스가 없다. 안전하다는 증거가 아니다")

ANSWERED_NOTHING = ("ANSWERED_NOTHING — 읽을 수 있는 번호판 %d건에 한 건도 "
                    "답하지 않았다. exact_accuracy 가 null 인 것은 정답지가 "
                    "없어서가 아니라 모델이 기권했기 때문이다 "
                    "(readable_abstention_rate 1.0)")

NO_READABLE_GT = ("NO_READABLE_GT — 정답지에 READABLE 항목이 없다. "
                  "exact_accuracy 와 readable_abstention_rate 는 분모가 0이다")

NO_REASON = ("NO_ABSTAIN_REASON — 기권 %d건에 사유가 없다. 기권률만으로는 "
             "무엇을 고쳐야 하는지 알 수 없다 (plate-readout/v1.3 은 "
             "abstain_reason 을 authoritative 로 둔다)")


def not_run(reason):
    return {"exact_accuracy": None, "wrong_accept_rate": None,
            "abstention_recall": None, "readable_abstention_rate": None,
            "n_readable": None, "abstain_reasons": None,
            "n_abstained_without_reason": None, "n": None, "coverage": reason}


def score(normalized, gt):
    if gt is None:
        return not_run(NO_GT)

    truth = {t["readout_id"]: t for t in gt["items"]}
    n_exact_den = n_exact_hit = 0
    n_unreadable = n_abstained = n_wrong_accept = 0
    n_readable = n_readable_abstained = 0
    n_scored = 0
    circular = False
    abstain_reasons = {}
    n_no_reason = 0

    for pred in normalized:
        t = truth.get(pred["readout_id"])
        if t is None:
            continue                      # 정답지에 없는 판독은 채점 대상이 아니다
        n_scored += 1
        circular = circular or bool(t.get("derived_from_pack"))
        if pred["abstained"]:
            # 기권했다는 사실과 왜 기권했는지는 다른 정보다. 사유별로
            # 세어 두지 않으면 기권률을 보고도 손댈 곳을 모른다.
            why = pred.get("abstain_reason")
            if why:
                abstain_reasons[why] = abstain_reasons.get(why, 0) + 1
            else:
                n_no_reason += 1
        if t["legibility"] == "READABLE":
            n_readable += 1
            if pred["abstained"]:
                # 읽을 수 있는데 기권한 것. exact_accuracy 분모에서 빠지므로
                # 여기서 세지 않으면 「기권만 하는 모델」이 보이지 않는다.
                n_readable_abstained += 1
            else:
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
    if not n_readable:
        reasons.append(NO_READABLE_GT)
    elif n_readable_abstained == n_readable:
        reasons.append(ANSWERED_NOTHING % n_readable)
    if n_no_reason:
        reasons.append(NO_REASON % n_no_reason)

    return {
        "exact_accuracy": (n_exact_hit / n_exact_den) if n_exact_den else None,
        "wrong_accept_rate": (n_wrong_accept / n_unreadable) if n_unreadable else None,
        "abstention_recall": (n_abstained / n_unreadable) if n_unreadable else None,
        "readable_abstention_rate": (
            (n_readable_abstained / n_readable) if n_readable else None),
        "n_readable": n_readable,
        "abstain_reasons": abstain_reasons,
        "n_abstained_without_reason": n_no_reason,
        "n": n_scored,
        "coverage": "; ".join(reasons) if reasons else None,
    }
