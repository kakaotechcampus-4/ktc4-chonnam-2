"""impl 원문 → scorer 가 읽는 얇은 뷰.

scorer 는 계약을 직접 읽지 않는다. 계약 간 필드명이 갈리는 문제
(docs/mock/CONTRACT_CONFLICTS.md §4)를 이 경계에서 흡수한다.
"""

NORMALIZER_VERSION = "n1"


def _require_dict(obj, where):
    """obj 가 dict 가 아니면 위치(where)를 담아 ValueError."""
    if not isinstance(obj, dict):
        raise ValueError("%s가 dict 가 아님 (got %s)" % (where, type(obj).__name__))


def _require_field(d, key, where):
    """d[key] 를 꺼낸다. 없으면 위치(where)와 필드명을 담아 ValueError.

    누락된 값에 기본값을 채워 넣지 않는다 — score 같은 필드가 조용히
    0.0 등으로 대체되면 하류 지표가 잘못된 신호 없이 오염되기 때문.
    """
    if key not in d:
        raise ValueError("%s에 필드 '%s' 없음" % (where, key))
    return d[key]


def normalize_candidate(raw):
    """clip 단위 후보 목록. score 내림차순으로 rank 를 1부터 다시 매긴다.

    입력의 rank 값은 무시하고 정렬 순서로 재계산한다.
    candidates 가 빈 리스트인 항목은 정상이다 (해당 clip 에서 후보를
    하나도 찾지 못한 경우 — B tier 의 negative clip 이 여기 해당한다).
    """
    out = []
    for i, item in enumerate(raw):
        where = "normalize_candidate: raw[%d]" % i
        _require_dict(item, where)
        clip_id = _require_field(item, "clip_id", where)
        candidates = _require_field(item, "candidates", where)
        for j, c in enumerate(candidates):
            cwhere = "%s.candidates[%d]" % (where, j)
            _require_dict(c, cwhere)
            _require_field(c, "score", cwhere)
            _require_field(c, "event_type", cwhere)
        cands = sorted(candidates, key=lambda c: -c["score"])
        out.append({
            "clip_id": clip_id,
            "candidates": [
                {"rank": k + 1,
                 "t_start_sec": float(c["t_start_sec"]),
                 "t_end_sec": float(c["t_end_sec"]),
                 "event_type": c["event_type"],
                 "score": float(c["score"])}
                for k, c in enumerate(cands)
            ],
        })
    return out


def normalize_classification(raw):
    """시퀀스 단위 분류 결과. target_bbox 가 없으면 None (선택 필드)."""
    out = []
    for i, item in enumerate(raw):
        where = "normalize_classification: raw[%d]" % i
        _require_dict(item, where)
        sequence_id = _require_field(item, "sequence_id", where)
        predicted = _require_field(item, "predicted", where)
        out.append({
            "sequence_id": sequence_id,
            "predicted": predicted,
            "target_bbox": item.get("target_bbox"),
        })
    return out


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
