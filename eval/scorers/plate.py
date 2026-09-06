"""Plate 단계 지표.

A tier 는 번호판이 비식별 처리되어 문자 정답이 없다
(harness-v1-design.md §4-3). C tier 가 들어오기 전까지 전부 null 이다.
0 으로 적지 않는다 — 데이터가 없는 것과 성능이 나쁜 것은 다른 사실이다.

GT가 있을 때의 계산 로직은 아직 없다 — v1에는 검증할 plate text GT가
없어 작성해도 실행되지 않고 검증되지 않는다(task-8 리뷰 Important 2).
C tier 확보 후 재구현 대상이며, 그 follow-up은
docs/modules/eval/harness-v1-design.md §9(F6)에 남겨 둔다.
"""

NO_DATA = ("NO_C_TIER_DATA — plate text GT 부재. "
           "A tier 는 번호판 마스킹(harness-v1-design.md §4-3)")


def score(normalized, gt):
    return {"exact_accuracy": None, "wrong_accept_rate": None,
            "abstention_recall": None, "n": 0, "coverage": NO_DATA}
