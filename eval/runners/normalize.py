"""impl 원문 → scorer 가 읽는 얇은 뷰.

scorer 는 계약을 직접 읽지 않는다. 계약 간 필드명이 갈리는 문제
(docs/mock/CONTRACT_CONFLICTS.md §4)를 이 경계에서 흡수한다.
"""

NORMALIZER_VERSION = "n3"   # 2026-09-20 candidate 판단 근거(summary·uncertainties) 보존


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

    **판단 근거를 같이 옮긴다** (2026-09-20 멘토 피드백). CandidateEvent
    계약이 이미 summary(「짧은 시각 관찰 요약」)와 uncertainties(「Coarse
    단계에서 남은 불확실성」)를 두고 있다. 지표는 이 값을 쓰지 않지만,
    「왜 이 구간을 이 유형이라고 봤나」가 예측 파일에 남아야 나중에 틀린
    결과를 사람이 읽을 수 있다 — plate 의 abstain_reason 과 같은 자리다.

    없으면 null 이다. 근거를 주지 않는 impl 도 있으므로 빈 문자열을
    지어내지 않는다.
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
            _require_field(c, "representative_sec", cwhere)
        cands = sorted(candidates, key=lambda c: -c["score"])
        out.append({
            "clip_id": clip_id,
            "candidates": [
                {"rank": k + 1,
                 "t_start_sec": float(c["t_start_sec"]),
                 "t_end_sec": float(c["t_end_sec"]),
                 "representative_sec": float(c["representative_sec"]),
                 "timeline_revision": c.get("timeline_revision"),
                 "event_type": c["event_type"],
                 "score": float(c["score"]),
                 "summary": c.get("summary"),
                 "uncertainties": c.get("uncertainties")}
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


def normalize_plate(raw):
    """PlateReadout 계약 목록을 판독 단위 뷰로 옮긴다.

    legibility 는 계약에 없다 — 「사람이 보면 읽히는가」는 eval 이 새로
    만드는 참값이고 정답지에만 있다. 여기서는 예측 쪽 사실만 옮긴다.

    **판단 근거를 같이 옮긴다** (2026-09-20 멘토 피드백). 결과값만 있으면
    모델이 왜 그렇게 판단했는지 나중에 알 수 없다. abstain_reason 은
    plate-readout/v1.3 이 authoritative 로 둔 필드이고(§abstained),
    target_association.status 는 「어느 차를 읽었다고 봤는가」다. 둘 다
    계약이 이미 주는 값이라 여기서 지어내는 것이 없다.

    frame_results[]·samples 는 옮기지 않는다 — 계약 §9 가 eval 의 기본
    제공 범위를 consensus·best_frame·abstained·target_association·
    validation 으로 두고, 상세 진단이 필요할 때만 쓰라고 한다. 원문은
    예측 파일 raw 에 그대로 남아 있다.
    """
    out = []
    for i, p in enumerate(raw):
        where = "normalize_plate: raw[%d]" % i
        _require_dict(p, where)
        obs = _require_field(p, "observation", where)
        _require_dict(obs, "%s.observation" % where)
        out.append({
            "readout_id": _require_field(p, "readout_id", where),
            "scenario_id": p.get("scenario_id"),
            "source_profile": (p.get("input_ref") or {}).get("source_profile"),
            "value": obs.get("value"),
            "status": obs.get("status"),
            "abstained": _require_field(p, "abstained", where),
            "abstain_reason": p.get("abstain_reason"),
            "target_association_status": (
                (p.get("target_association") or {}).get("status")),
        })
    return out


def from_candidate_events(raw):
    """CandidateEvent 계약 목록의 이름과 단위를 eval 뷰로 옮긴다.

    계약은 event_type_hint · ranking_score · span.start_ms(밀리초)를 쓰고
    eval 뷰는 event_type · score · t_start_sec(초)를 쓴다. 이 차이를
    여기서 한 번만 흡수한다 — CONTRACT_CONFLICTS.md §4 가 기록했듯
    계약마다 이름이 갈리며 Mock Pack 은 일부러 통일하지 않았다.

    span.start_ms/end_ms 는 coarse 후보 창이고 사건 외연이 아니다. 매칭에
    쓰는 값은 representative_ms 이며(계약 v1.1 §4-1), 창은 containment
    보조 신호로만 쓴다.

    **clip 단위로 묶지 않는다.** 계약은 timeline_id 와 밀리초 offset 으로
    위치를 말하고 B tier 정답지는 clip_id 로 말한다. 그 대응은 아직 어느
    계약도 정하지 않았으므로 여기서 지어내지 않고 원문 식별자를 그대로
    실어 보낸다. clip 단위 채점이 필요해지는 시점에 정해야 할 항목이다.
    """
    out = []
    for i, ev in enumerate(raw):
        where = "from_candidate_events: raw[%d]" % i
        _require_dict(ev, where)
        span = _require_field(ev, "span", where)
        _require_dict(span, "%s.span" % where)
        out.append({
            "candidate_id": _require_field(ev, "candidate_id", where),
            "run_id": ev.get("run_id"),
            "timeline_id": span.get("timeline_id"),
            "rank": _require_field(ev, "rank", where),
            "t_start_sec": _require_field(span, "start_ms", "%s.span" % where) / 1000.0,
            "t_end_sec": _require_field(span, "end_ms", "%s.span" % where) / 1000.0,
            "representative_sec": _require_field(
                span, "representative_ms", "%s.span" % where) / 1000.0,
            "timeline_revision": span.get("timeline_revision"),
            "event_type": _require_field(ev, "event_type_hint", where),
            "score": _require_field(ev, "ranking_score", where),
            # 계약의 선택 필드다. 없으면 null — 지어내지 않는다.
            "summary": ev.get("summary"),
            "uncertainties": ev.get("uncertainties"),
        })
    return out
