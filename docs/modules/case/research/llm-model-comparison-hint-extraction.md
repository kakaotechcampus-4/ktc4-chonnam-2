# [Case] 자연어 단서 구조화용 LLM 모델 비교

> **성격:** 자연어 단서 구조화("사용자 자연어 단서를 구조화한다", `phase1-completion-checklist.md` 74번 항목) 호출에 어떤 LLM을 쓸지에 대한 **조사 결과이지 결정이 아니다.** 실제 API 호출 실측(스키마 준수율 비교)을 아직 하지 못했다 — 키 미확보. 실측 전까지는 `decisions/`로 승격하지 않는다.

**Owner:** 유소연

**관련 모듈:** 없음 (case 내부 결정 — 자연어 단서 구조화는 case의 책임 범위, `tech-spec.md` §1)

**근거 자료:** `docs/modules/case/research/architecture-input-memo.md` §2("intent LLM 호출은 1회로 제한") · `docs/modules/case/tech-spec.md` §1 · `docs/modules/case/checklists/phase1-completion-checklist.md` 74번 항목(AI 모델 호출 필요로 Mock 1차 범위 밖) · 가격 조사(§5 출처 참고, 2026-09-16 웹 검색)

---

## 1. 배경

`case`의 orchestration 흐름(§③, `docs/modules/case/tech-spec.md` §1)은 다음과 같다:

```
web에서 사용자 자연어 답변 → case가 구조화(hints) → Job Intent 결정
→ 결과 도메인 상태 반영 → CaseView로 web에 재투사
```

이 중 "자연어 단서 구조화" 단계는 실제 AI 모델 호출이 필요해 Mock 1차 구현 범위에서 명시적으로 제외되어 있었다(`checklists/phase1-completion-checklist.md` 74번). 이 문서는 그 호출에 쓸 LLM을 고르기 위한 예비 조사다.

## 2. 확인된 제약

| 제약 | 근거 |
| --- | --- |
| intent LLM 호출은 **1회로 제한** — 멀티턴으로 재질문하는 설계 불가 | `architecture-input-memo.md` §2, v3 p.6-7·p.24 |
| case는 다른 모듈의 prompt 내용/OCR threshold/evidence 정책 로직을 알면 안 됨(case 자신의 이 호출용 프롬프트는 해당 없음 — 다른 모듈 프롬프트에 대한 제약) | `tech-spec.md` §1 "알면 안 되는 것" |
| 확정 Evidence 값을 복제 소유하지 않음 — 이 호출의 출력은 `Case.hints`/`Selection`만 갱신, evidence 값에는 관여하지 않음 | `docs/modules/case/README.md` "다루지 않는 범위" |

1회 제한 때문에 애매한 입력을 되묻는 방식은 쓸 수 없다 — 아래 스키마의 `confidence: low`로 애매성을 표시하고, case의 기존 로직(웹 재확인 UI)이 후속 처리를 맡는 방식으로 설계했다.

## 3. 추출 스키마 (초안)

```json
{
  "type": "object",
  "properties": {
    "time_hint":     {"type": ["string", "null"]},
    "vehicle_hint":  {"type": ["string", "null"]},
    "situation_hint":{"type": ["string", "null"]},
    "location_hint": {"type": ["string", "null"]},
    "correction_target": {"type": ["string", "null"], "description": "정정 대상 필드명. 새 정보면 null"},
    "confidence": {"type": "string", "enum": ["high", "low"]}
  },
  "required": ["time_hint", "vehicle_hint", "situation_hint", "location_hint", "correction_target", "confidence"],
  "additionalProperties": false
}
```

Structured Outputs(JSON Schema strict mode)로 강제 호출하는 걸 전제로 한다 — 세 후보 모델 모두 문서상 지원한다(§5, 실측 미확인).

## 4. 테스트 문장 (초안 — 실사용자 로그 아님)

`data/mock/case/scenario_happy_001.json`의 `hints` 필드는 이미 구조화된 결과물이라(`{"time": "18시쯤", ...}`), 파싱 대상인 "원문"이 fixture에 없다. 아래는 직접 작성한 예시이며, **실측 전 실제 사용자 로그로 교체가 필요하다**:

1. 신규: "어제 18시쯤 상무중앙로 사거리에서 흰색 SUV가 백색 실선 구간에서 차로 바꿨어요"
2. 정정: "아 그 차 아니고 바로 옆에 은색 세단이었어요"
3. 애매: "그 근처였던 것 같은데 정확힌 모르겠어요"

## 5. 모델 후보 비교 (스펙 기준 — 실측 아님)

| | GPT-5 Nano | Gemini 3.1 Flash-Lite | Claude Haiku 4.5 |
| --- | --- | --- | --- |
| 비용 (1M 토큰, input/output) | $0.05 / $0.40 | $0.25 / $1.50 | $1.00 / $5.00 |
| 상태 | 종료 공지 없음 | **Preview** | GA, 종료 공지 없음 |
| Structured Output 지원 | 지원(JSON schema) | 지원(responseSchema) | 지원(`output_config.format`) |
| 팀 내 기존 사용 이력 | 없음(evidence 모듈에 GPT 프롬프트 실험 흔적만 존재) | 있음(`search` 모듈이 이미 사용 중) | 없음 |
| 리스크 | 신규 벤더 온보딩 필요 | Preview라 프로덕션 안정성 미검증 | 셋 중 최고가(이 작업 볼륨 기준 절대액은 작을 전망) |

Gemini 2.5 Flash-Lite(현재 최저가 $0.10/$0.40)는 2026-10-16 서비스 종료 예정이라 후보에서 제외했다. GPT-5 Mini($0.25/$2.00)는 2026-12-11 종료 예정이라 마찬가지로 제외했다.

## 6. 임시 추천 (실측 전)

**실측 우선순위: GPT-5 Nano → Claude Haiku 4.5 → Gemini 3.1 Flash-Lite**

- GPT-5 Nano: 최저가 + 종료 공지 없음 — 1순위로 실측할 가치가 있다. 다만 팀에 기존 사용 이력이 없어 벤더 온보딩 비용이 든다.
- Claude Haiku 4.5: 셋 중 최고가지만 GA 상태고 안정적 — 스키마 준수율이 떨어질 경우의 안전한 대안.
- Gemini 3.1 Flash-Lite: `search` 모듈과 벤더를 맞출 수 있다는 장점이 있으나 Preview 상태라 지금 커밋하기엔 이르다. 팀이 이미 Gemini 키·과금 계정을 갖고 있다는 점은 실측 우선순위를 올릴 근거가 될 수 있다 — PM/팀 논의 필요.

## 7. 다음 단계 (미결)

- [ ] 최소 1개 벤더 API 키 확보 (팀 기존 Gemini 키 재사용 가능 여부 확인 포함)
- [ ] §4 테스트 문장을 실제 사용자 로그(또는 팀이 합의한 현실적 샘플)로 교체
- [ ] 3개 후보 모델에 동일 프롬프트+스키마로 실측 — 스키마 준수율 비교
- [ ] 실측 결과를 바탕으로 `docs/modules/case/decisions/`에 확정 문서 작성 (ADR 또는 decision 메모 — 그 시점에 형식 결정)

## 8. 원본 자료 Reference

- `docs/modules/case/research/architecture-input-memo.md` §2, §3 열린 결정 표 "intent 멀티턴 확장"
- `docs/modules/case/tech-spec.md` §1
- `docs/modules/case/checklists/phase1-completion-checklist.md` 74번 항목
- 가격 조사(2026-09-16 웹 검색):
  - [Gemini API Pricing: Full Breakdown of Costs (Sep 2026)](https://developer.puter.com/tutorials/gemini-api-pricing/)
  - [Gemini 3.1 Flash Lite Preview API Pricing 2026](https://pricepertoken.com/pricing-page/model/google-gemini-3.1-flash-lite-preview)
  - [GPT 5 Nano API Pricing 2026](https://pricepertoken.com/pricing-page/model/openai-gpt-5-nano)
  - [GPT 5 Mini API Pricing 2026](https://pricepertoken.com/pricing-page/model/openai-gpt-5-mini)
