"""impl 원문 → scorer 가 읽는 얇은 뷰.

scorer 는 계약을 직접 읽지 않는다. 계약 간 필드명이 갈리는 문제
(docs/mock/CONTRACT_CONFLICTS.md §4)를 이 경계에서 흡수한다.
"""

NORMALIZER_VERSION = "n1"


def normalize_candidate(raw):
    """clip 단위 후보 목록. score 내림차순으로 rank 를 1부터 다시 매긴다."""
    out = []
    for item in raw:
        cands = sorted(item["candidates"], key=lambda c: -c["score"])
        out.append({
            "clip_id": item["clip_id"],
            "candidates": [
                {"rank": i + 1,
                 "t_start_sec": float(c["t_start_sec"]),
                 "t_end_sec": float(c["t_end_sec"]),
                 "event_type": c["event_type"],
                 "score": float(c["score"])}
                for i, c in enumerate(cands)
            ],
        })
    return out


def normalize_classification(raw):
    """시퀀스 단위 분류 결과."""
    return [
        {"sequence_id": item["sequence_id"],
         "predicted": item["predicted"],
         "target_bbox": item.get("target_bbox")}
        for item in raw
    ]


def from_mock_pack(obj):
    """Mock Pack v1 의 평평한 prediction 객체를 candidate normalized 로 옮긴다.

    data/mock/eval/prediction_*.json 은 `case` Owner 의 산출물이며 형식을
    바꾸라고 요구하지 않는다 (harness-v1-design.md §2-4). 여기서 읽기만 한다.
    시나리오 1건이므로 clip_id 자리에 scenario_id 를 쓴다.
    """
    p = obj["prediction"]
    return [{
        "clip_id": obj["scenario_id"],
        "candidates": [{
            "rank": int(p["rank"]),
            "t_start_sec": 0.0,
            "t_end_sec": 0.0,
            "event_type": p["visual_event_type"],
            "score": 1.0,
        }],
    }]
