"""Elice ML API 호출 어댑터.

Elice가 세 후보 모두 **OpenAI SDK 호환 인터페이스**로 중계한다는 걸 확인했다(사용자가
모델 카드에서 직접 확인):

- 인증: `Authorization: Bearer <Serverless API Key>` — OpenAI SDK가 `api_key=`로 자동 처리
- 호출: `client.chat.completions.parse(model=..., messages=[...], response_format=<PydanticModel>)`
  (Claude Haiku 4.5 모델 카드 예시로 확인 — GPT-5 Nano/Gemini도 같은 패턴 사용 확인 필요, 아래 참고)
- base_url: 계정별 실제 엔드포인트 문자열로 교체해야 함 (모델 카드는 `<your-mlapi-endpoint>` placeholder)

세 모델 다 같은 클래스(model_name만 다름)로 처리한다 — 벤더별 서브클래스가 필요 없어졌다.

**아직 확인 안 된 것:**
- `MODEL_IDS`의 `gpt-5-nano`/`gemini-3.1-flash-lite` 문자열은 `claude-haiku-4-5`와
  같은 명명 규칙일 거라고 가정한 값이다. 실행 전 각 모델 카드에서 정확한 문자열 확인 필요.
- `response_format=<PydanticModel>` structured output이 Claude/Gemini 백엔드에도
  동일하게 강제되는지(Elice가 내부적으로 어떻게 relay하는지)는 실제로 호출해봐야 안다 —
  `schema_valid`가 계속 False로 나오면 이 가정이 깨진 것이니 `runner.py` 출력을 먼저 본다.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

from openai import OpenAI

from pricing import estimate_cost_krw
from schema import (
    CANDIDATE_SYSTEM_PROMPT,
    CANDIDATE_USER_TEMPLATE,
    JUDGE_SYSTEM_PROMPT,
    JUDGE_USER_TEMPLATE,
    IntentHintExtraction,
    JudgeVerdict,
)

MODEL_IDS = {
    "gpt-5-nano": "gpt-5-nano",
    "gemini-3.1-flash-lite": "gemini-3.1-flash-lite",
    "claude-haiku-4-5": "claude-haiku-4-5",  # 사용자가 모델 카드에서 직접 확인한 값
}


def _client() -> OpenAI:
    return OpenAI(
        api_key=os.environ["ELICE_API_KEY"],
        base_url=os.environ["ELICE_BASE_URL"],
    )


@dataclass
class CandidateResult:
    model_name: str
    raw_text: str | None
    parsed: dict | None
    latency_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_krw: float | None
    error: str | None


class CandidateAdapter:
    """세 후보 모두 이 클래스 하나로 처리한다 — `model_name`만 다르게 인스턴스화."""

    def __init__(self, model_name: str):
        self.model_name = model_name

    def extract(self, input_sentence: str, prior_hints: dict | None) -> CandidateResult:
        user_prompt = CANDIDATE_USER_TEMPLATE.format(
            prior_hints_json=json.dumps(prior_hints, ensure_ascii=False),
            input_sentence=input_sentence,
        )
        start = time.monotonic()
        try:
            response = _client().chat.completions.parse(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": CANDIDATE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=IntentHintExtraction,
            )
        except Exception as exc:  # noqa: BLE001 — 호출 실패도 결과로 기록해야 함
            return CandidateResult(
                model_name=self.model_name,
                raw_text=None,
                parsed=None,
                latency_ms=(time.monotonic() - start) * 1000,
                prompt_tokens=None,
                completion_tokens=None,
                cost_krw=None,
                error=str(exc),
            )
        latency_ms = (time.monotonic() - start) * 1000

        message = response.choices[0].message
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else None
        completion_tokens = usage.completion_tokens if usage else None
        parsed_model = getattr(message, "parsed", None)

        return CandidateResult(
            model_name=self.model_name,
            raw_text=message.content,
            parsed=parsed_model.model_dump() if parsed_model is not None else None,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_krw=estimate_cost_krw(self.model_name, prompt_tokens, completion_tokens),
            error=(
                None
                if parsed_model is not None
                else (getattr(message, "refusal", None) or "structured output 파싱 실패")
            ),
        )


class JudgeAdapter:
    """채점용 어댑터. 비교 대상 3개 중 하나를 재사용하지 않는다(자기 채점 편향 방지) —
    실행 시점에 `JUDGE_MODEL` 환경변수로 어떤 모델을 쓸지 확정한다."""

    def __init__(self, model_name: str):
        self.model_name = model_name

    def judge(
        self,
        input_sentence: str,
        prior_hints: dict | None,
        expected_notes: str,
        candidate_output: dict | None,
    ) -> CandidateResult:
        user_prompt = JUDGE_USER_TEMPLATE.format(
            input_sentence=input_sentence,
            prior_hints_json=json.dumps(prior_hints, ensure_ascii=False),
            expected_notes=expected_notes,
            candidate_output_json=json.dumps(candidate_output, ensure_ascii=False),
        )
        start = time.monotonic()
        try:
            response = _client().chat.completions.parse(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=JudgeVerdict,
            )
        except Exception as exc:  # noqa: BLE001
            return CandidateResult(
                model_name=self.model_name,
                raw_text=None,
                parsed=None,
                latency_ms=(time.monotonic() - start) * 1000,
                prompt_tokens=None,
                completion_tokens=None,
                cost_krw=None,
                error=str(exc),
            )
        latency_ms = (time.monotonic() - start) * 1000

        message = response.choices[0].message
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else None
        completion_tokens = usage.completion_tokens if usage else None
        parsed_model = getattr(message, "parsed", None)

        return CandidateResult(
            model_name=self.model_name,
            raw_text=message.content,
            parsed=parsed_model.model_dump() if parsed_model is not None else None,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_krw=estimate_cost_krw(self.model_name, prompt_tokens, completion_tokens),
            error=(
                None
                if parsed_model is not None
                else (getattr(message, "refusal", None) or "structured output 파싱 실패")
            ),
        )
