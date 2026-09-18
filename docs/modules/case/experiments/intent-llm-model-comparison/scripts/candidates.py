"""벤더별 호출 어댑터.

주의: 이 파일 작성 시점에는 세 후보(GPT-5 Nano / Gemini 3.1 Flash-Lite / Claude Haiku 4.5)의
정확한 API 요청 문법을 실측하지 못했다(research 문서 §7 미결). 아래 `_TODO_call` 부분은
실행 전 각 벤더 최신 문서로 채워야 한다 — 여기 있는 endpoint/파라미터 이름은 자리표시자다.

새 SDK 의존성을 pyproject.toml(공유 자원)에 미리 추가하지 않는다. 실제 실행 시점에
어떤 SDK를 쓸지(공식 SDK vs 순수 HTTP) 정하고 그때 추가한다 — 지금은 표준 라이브러리
(urllib)만으로 골격을 갖춘다.
"""

from __future__ import annotations

import abc
import json
import os
import time
import urllib.request
from dataclasses import dataclass

from schema import (
    CANDIDATE_SYSTEM_PROMPT,
    CANDIDATE_USER_TEMPLATE,
    EXTRACTION_SCHEMA,
    JUDGE_SYSTEM_PROMPT,
    JUDGE_USER_TEMPLATE,
)


@dataclass
class CandidateResult:
    model_name: str
    raw_text: str | None
    parsed: dict | None
    latency_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: float | None
    error: str | None


class CandidateAdapter(abc.ABC):
    model_name: str

    def extract(self, input_sentence: str, prior_hints: dict | None) -> CandidateResult:
        prior_hints_json = json.dumps(prior_hints, ensure_ascii=False)
        user_prompt = CANDIDATE_USER_TEMPLATE.format(
            prior_hints_json=prior_hints_json, input_sentence=input_sentence
        )
        start = time.monotonic()
        try:
            raw_text, prompt_tokens, completion_tokens, cost_usd = self._call(
                CANDIDATE_SYSTEM_PROMPT, user_prompt
            )
        except Exception as exc:  # noqa: BLE001 — 실측 실패도 결과로 기록해야 함
            latency_ms = (time.monotonic() - start) * 1000
            return CandidateResult(
                model_name=self.model_name,
                raw_text=None,
                parsed=None,
                latency_ms=latency_ms,
                prompt_tokens=None,
                completion_tokens=None,
                cost_usd=None,
                error=str(exc),
            )
        latency_ms = (time.monotonic() - start) * 1000

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            return CandidateResult(
                model_name=self.model_name,
                raw_text=raw_text,
                parsed=None,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost_usd,
                error=f"JSON 파싱 실패: {exc}",
            )

        return CandidateResult(
            model_name=self.model_name,
            raw_text=raw_text,
            parsed=parsed,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            error=None,
        )

    @abc.abstractmethod
    def _call(
        self, system_prompt: str, user_prompt: str
    ) -> tuple[str, int | None, int | None, float | None]:
        """(raw_text, prompt_tokens, completion_tokens, cost_usd) 반환. 실패 시 예외를 던진다."""
        raise NotImplementedError

    def _post_json(self, url: str, headers: dict, body: dict) -> dict:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))


class GPT5NanoAdapter(CandidateAdapter):
    model_name = "gpt-5-nano"

    def _call(self, system_prompt, user_prompt):
        api_key = os.environ["OPENAI_API_KEY"]
        # TODO(실행 전): 현재 OpenAI API의 structured output 엔드포인트/파라미터로 교체.
        # 자리표시자 — strict json_schema 모드로 EXTRACTION_SCHEMA를 강제해야 한다.
        raise NotImplementedError(
            "GPT5NanoAdapter._call: 실행 전 OpenAI 최신 문서 기준으로 구현 필요"
        )


class Gemini31FlashLiteAdapter(CandidateAdapter):
    model_name = "gemini-3.1-flash-lite"

    def _call(self, system_prompt, user_prompt):
        api_key = os.environ["GEMINI_API_KEY"]
        # TODO(실행 전): responseSchema로 EXTRACTION_SCHEMA를 강제하는 현재 Gemini API 문법으로 교체.
        raise NotImplementedError(
            "Gemini31FlashLiteAdapter._call: 실행 전 Gemini 최신 문서 기준으로 구현 필요"
        )


class ClaudeHaiku45Adapter(CandidateAdapter):
    model_name = "claude-haiku-4-5"

    def _call(self, system_prompt, user_prompt):
        api_key = os.environ["ANTHROPIC_API_KEY"]
        # TODO(실행 전): output_config.format으로 EXTRACTION_SCHEMA를 강제하는 현재 Anthropic API
        # 문법으로 교체.
        raise NotImplementedError(
            "ClaudeHaiku45Adapter._call: 실행 전 Anthropic 최신 문서 기준으로 구현 필요"
        )


ALL_CANDIDATES: tuple[type[CandidateAdapter], ...] = (
    GPT5NanoAdapter,
    Gemini31FlashLiteAdapter,
    ClaudeHaiku45Adapter,
)


class JudgeAdapter(CandidateAdapter):
    """채점용 어댑터. 비교 대상 3개 중 하나를 재사용하지 않는다(자기 채점 편향 방지) —
    실행 시점에 JUDGE_MODEL 환경변수로 어떤 어댑터를 쓸지 확정한다.
    """

    model_name = "judge"

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
            raw_text, prompt_tokens, completion_tokens, cost_usd = self._call(
                JUDGE_SYSTEM_PROMPT, user_prompt
            )
        except Exception as exc:  # noqa: BLE001
            return CandidateResult(
                model_name=self.model_name,
                raw_text=None,
                parsed=None,
                latency_ms=(time.monotonic() - start) * 1000,
                prompt_tokens=None,
                completion_tokens=None,
                cost_usd=None,
                error=str(exc),
            )
        latency_ms = (time.monotonic() - start) * 1000
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            parsed = None
            error = f"JSON 파싱 실패: {exc}"
        else:
            error = None
        return CandidateResult(
            model_name=self.model_name,
            raw_text=raw_text,
            parsed=parsed,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            error=error,
        )

    def _call(self, system_prompt, user_prompt):
        raise NotImplementedError(
            "JudgeAdapter._call: JUDGE_MODEL 확정 후 해당 벤더 호출로 구현 필요"
        )
