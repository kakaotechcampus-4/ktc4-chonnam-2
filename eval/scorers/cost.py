"""비용 지표.

정본 집계 키는 case_id 다 (contract-usage-record.md §9-2). run_ref 는
per-run 감사용이며, run 이 산출되지 않은 attempt(run_ref=null,
RUN_NOT_PRODUCED)는 run_ref 로 묶으면 통째로 빠져 비용이 과소 보고된다.

분모(processed_duration_sec)는 호출부가 넘긴다. 이 모듈은 파일을 읽지
않는다 — 분자와 분모가 같은 시나리오 집합에서 나왔는지는 넘기는 쪽이
보장한다.
"""

NO_ROWS = "NO_USAGE_RECORDS — 이 실행에 비용 기록이 없다"
MIXED = ("MIXED_CURRENCY — 통화가 섞여 합산하지 않는다. 환율은 "
         "pricing_context 에 귀속되며 eval 이 정할 값이 아니다")


def score(usage_records, processed_duration_sec, scenarios):
    if not usage_records:
        return {"cost_per_case": None, "cost_per_source_video_hour": None,
                "total": None, "currency": None, "n_rows": 0,
                "scenarios": list(scenarios), "coverage": NO_ROWS}

    currencies = {r["cost"]["currency"] for r in usage_records}
    if len(currencies) > 1:
        return {"cost_per_case": None, "cost_per_source_video_hour": None,
                "total": None, "currency": sorted(currencies),
                "n_rows": len(usage_records), "scenarios": list(scenarios),
                "coverage": MIXED}

    per_case = {}
    for r in usage_records:
        case_id = r["case_id"]
        per_case[case_id] = per_case.get(case_id, 0.0) + float(r["cost"]["amount"])

    total = sum(per_case.values())
    hourly = None
    if processed_duration_sec:
        hourly = total / (processed_duration_sec / 3600.0)

    reasons = []
    zero_cases = sorted(c for c, v in per_case.items() if v == 0.0)
    if zero_cases:
        # 평균만 보면 안 보인다. 0원 case 가 있다는 사실을 파일에 남긴다.
        reasons.append("ZERO_COST_CASES — %s" % ", ".join(zero_cases))
    if processed_duration_sec is None:
        reasons.append("NO_PROCESSED_DURATION — 시간당 환산치를 낼 수 없다")

    return {
        "cost_per_case": per_case,
        "cost_per_source_video_hour": hourly,
        "total": total,
        "currency": currencies.pop(),
        "n_rows": len(usage_records),
        "scenarios": list(scenarios),
        "coverage": "; ".join(reasons) if reasons else None,
    }
