"""단일 정의 소스: 추출 스키마 + 후보/judge 프롬프트.

스키마는 `research/llm-model-comparison-hint-extraction.md` §3과 동일해야 한다.
바꿀 일이 있으면 그 문서도 같이 갱신한다 (규칙 원문 중복 금지 — 여기 값이 실행에 쓰는 사본).
"""

from __future__ import annotations

FIELDS = (
    "time_hint",
    "vehicle_hint",
    "situation_hint",
    "location_hint",
    "correction_target",
    "confidence",
)

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "time_hint": {"type": ["string", "null"]},
        "vehicle_hint": {"type": ["string", "null"]},
        "situation_hint": {"type": ["string", "null"]},
        "location_hint": {"type": ["string", "null"]},
        "correction_target": {
            "type": ["string", "null"],
            "description": "정정 대상 필드명. 새 정보면 null",
        },
        "confidence": {"type": "string", "enum": ["high", "low"]},
    },
    "required": list(FIELDS),
    "additionalProperties": False,
}

CANDIDATE_SYSTEM_PROMPT = """\
너는 교통위반 신고 준비를 돕는 시스템의 일부다. 사용자가 자연어로 말한 사고 상황 설명에서
아래 스키마의 필드만 추출한다.

규칙:
- 문장에 없는 내용을 지어내지 않는다. 언급 안 된 필드는 null로 둔다.
- 상대 시간 표현("30분 전" 등)은 절대 시각으로 임의 변환하지 말고 원문 표현을 그대로 담는다.
- 애매하거나 불확실한 진술은 confidence를 low로 표시한다. 되묻지 않는다(1회 호출).
- 이전 단서(prior_hints)가 주어지면, 이번 발화가 그중 하나를 정정하는지 판단해서
  correction_target에 정정 대상 필드명을 넣는다. 정정이 아니면 null.
- 이번 발화에서 언급되지 않은 필드는 prior_hints 값을 복사하지 말고 null로 둔다
  (병합은 이 호출의 책임이 아니다).
"""

CANDIDATE_USER_TEMPLATE = """\
prior_hints: {prior_hints_json}

사용자 발화: "{input_sentence}"
"""

VERDICTS = ("correct", "partial", "hallucinated", "missed")
"""필드별 judge 판정값. hallucinated/missed를 나누는 이유는
`README.md`의 "채점 방식을 정한 이유" 참고 — hallucination rate와
null/UNKNOWN 처리 비율을 하나의 'wrong'에서 분리해서 보기 위함."""

JUDGE_SYSTEM_PROMPT = """\
너는 자연어 단서 추출 결과를 채점하는 평가자다. 비교 대상 모델 중 하나가 아니다.
아래 정보를 보고 필드별로 다음 네 가지 중 하나를 매기고 한 줄 근거를 남긴다.

- correct: 원문 내용과 expected_notes 기준에 맞게 값을 뽑았거나, 없어야 할 값을 null로 뒀다.
- partial: 방향은 맞지만 일부만 맞다(예: 정정 필드는 맞았지만 confidence가 틀림).
- hallucinated: 원문에 없거나 애매하다고만 한 내용을 모델이 구체적인 값으로 지어냈다
  (값이 그럴듯해도 원문 근거가 없으면 hallucinated). correction 케이스에서 언급 안 된
  필드에 이전 값을 그대로 복사해 넣은 것도 hallucinated다(병합은 이 호출의 책임이 아님).
- missed: 원문에 명확히 있는 내용을 모델이 null로 빠뜨렸다.

채점 기준:
- expected_notes는 정답 문자열이 아니라 사람이 쓴 판정 기준이다. 문자열 완전일치를 요구하지 않는다.
- hallucinated와 missed는 방향이 반대다 — 헷갈리면 "모델이 원문보다 더 많이 말했는가(hallucinated)
  아니면 더 적게 말했는가(missed)"로 구분한다.

출력은 반드시 JSON:
{{"time_hint": "correct|partial|hallucinated|missed", "vehicle_hint": "...",
  "situation_hint": "...", "location_hint": "...", "correction_target": "...",
  "confidence": "...", "notes": "한두 문장 근거"}}
"""

JUDGE_USER_TEMPLATE = """\
[원문 발화]
{input_sentence}

[prior_hints]
{prior_hints_json}

[판정 기준 (expected_notes)]
{expected_notes}

[모델 출력]
{candidate_output_json}
"""


def validate_schema(obj: dict) -> tuple[bool, list[str]]:
    """EXTRACTION_SCHEMA에 대한 최소 수동 검증. 외부 jsonschema 의존성을 새로 추가하지 않기 위함
    (pyproject.toml에 pydantic만 있고, 이 실험은 case 공유 의존성에 손대지 않는다).
    """
    errors: list[str] = []
    if not isinstance(obj, dict):
        return False, ["출력이 JSON object가 아님"]

    extra = set(obj.keys()) - set(FIELDS)
    if extra:
        errors.append(f"스키마에 없는 필드: {sorted(extra)}")

    for field in FIELDS:
        if field not in obj:
            errors.append(f"필수 필드 누락: {field}")
            continue
        value = obj[field]
        if field == "confidence":
            if value not in ("high", "low"):
                errors.append(f"confidence 값이 enum 밖: {value!r}")
        else:
            if value is not None and not isinstance(value, str):
                errors.append(f"{field}는 string 또는 null이어야 함, 실제: {type(value).__name__}")

    return (len(errors) == 0), errors
