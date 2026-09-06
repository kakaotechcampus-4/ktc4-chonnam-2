"""위반유형 baseline enum.

정답지는 docs/architecture/module-architecture.md §3-5이다.
이 파일은 그 목록의 코드 사본이며, 어긋나면 문서가 이긴다.
"""

VIOLATION_TYPES = (
    "SIGNAL",
    "CENTER_LINE_CROSSING",
    "SOLID_LINE_LANE_CHANGE",
    "MOTORCYCLE_HELMET_NON_USE",
)

# Classification confusion matrix는 4종 + NONE의 5×5다 (v4 §9-3).
CLASS_LABELS = VIOLATION_TYPES + ("NONE",)
