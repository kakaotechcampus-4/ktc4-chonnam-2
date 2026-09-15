"""readout이 쓰는 등재값 목록.

값 자체를 여기서 정하지 않는다. 원문은 아래 두 문서가 소유하고 이 파일은 옮겨 적은 것이다.
  - docs/modules/readout/decisions/failure-taxonomy.md
      failure.kind 5 · failure.code 3 · abstain_reason 4 · overlay reason.code 3
  - docs/architecture/contracts/contract-plate-overlay-readout.md
      §3 source_profile 2 · §5 observation.status · target_association.status 5

닫힌 목록이 아닌 것은 주석으로 표시했다. 새 값은 위 문서에 등재한 뒤 여기에 옮긴다.
"""

OPERATIONS = frozenset({"PLATE_READ", "OVERLAY_TIME_READ"})
OUTCOMES = frozenset({"SUCCEEDED", "PARTIAL", "FAILED"})

# failure-taxonomy.md — 런타임 kind 5종. OVERCONFIDENT는 eval의 사후 분류라 여기 없다.
FAILURE_KINDS = frozenset({
    "PLATE_TARGET_ASSOCIATION",
    "PLATE_DETECTION",
    "PLATE_RECOGNITION",
    "OVERLAY_VALIDATION",
    "INFRA",
})
FAILURE_CODES = frozenset({
    "READOUT_PROVIDER_TIMEOUT",
    "READOUT_FRAME_ACCESS_FAILED",
    "READOUT_PIPELINE_ERROR",
})

# 열린 목록 — 등재 후 사용
ABSTAIN_REASONS = frozenset({
    "TARGET_AMBIGUOUS",
    "FRAME_DISAGREEMENT",
    "LOW_RESOLUTION",
    "OCR_LOW_CONFIDENCE",
})
SOURCE_PROFILES = frozenset({"readout-native", "readout-native-hires"})

# OCR 근거는 Source-derived여야 한다(계약 §3-2·§3-3). 사후 Timestamp가 삽입된 Report Video를
# 근거로 삼는 경로를 값 층위에서 막는다. fixture 5개가 전부 이 한 값을 쓴다.
PROVENANCES = frozenset({"SOURCE_DERIVED_INCIDENT_CLIP"})

OBSERVATION_STATUSES = frozenset({
    "OK",
    "NEEDS_REVIEW",
    "UNKNOWN",
    "NOT_APPLICABLE",
    "ERROR",
})
ASSOCIATION_STATUSES = frozenset({
    "ASSOCIATED",
    "LOW_CONFIDENCE",
    "AMBIGUOUS",
    "FAILED",
    "NOT_PROVIDED",
})

# overlay 4갈래 중 값이 붙는 3종. OK는 reason 키 자체가 없다.
OVERLAY_REASON_CODES = frozenset({
    "readout.overlay.not_present",
    "readout.overlay.presence_undetermined",
    "readout.overlay.ocr_failed",
})

OBSERVATION_SOURCE_KINDS = frozenset({"readout.plate_ocr", "readout.overlay_ocr"})
