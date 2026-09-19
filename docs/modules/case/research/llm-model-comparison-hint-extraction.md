# [Case] 자연어 단서 구조화용 LLM 모델 비교

> **성격:** 자연어 단서 구조화("사용자 자연어 단서를 구조화한다", `phase1-completion-checklist.md` 74번 항목) 호출에 어떤 LLM을 쓸지에 대한 조사 문서다. **2026-09-19 실측 완료 — 결정은 `docs/modules/case/decisions/intent-llm-model-selection.md`에 있다.** 이 문서는 실측 이전 조사·가설을 그대로 보존하고(§9에 실측 결과 요약·링크만 추가), 규칙 원문을 결정 문서와 중복하지 않는다.

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
    "confidence": {"type": "string", "enum": ["high", "low"]},
    "reasoning": {"type": "string", "description": "왜 이 값들을 뽑았는지 한두 문장 근거"}
  },
  "required": ["time_hint", "vehicle_hint", "situation_hint", "location_hint", "correction_target", "confidence", "reasoning"],
  "additionalProperties": false
}
```

`reasoning`은 2026-09-19 실측 직전 멘토 피드백으로 추가됐다("결과만 있으면 틀린 케이스를 정성적으로 이해하기 어렵다") — 채점 대상 6개 필드에는 안 들어가고, 사람이 나중에 오답을 정성적으로 읽을 때만 참고한다.

Structured Outputs(JSON Schema strict mode)로 강제 호출하는 걸 전제로 했다 — **2026-09-19 실측으로 세 후보 모두 실제로 지원함을 확인**(스키마 위반 0건, §9).

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

## 7. 다음 단계

- [x] 최소 1개 벤더 API 키 확보 — Elice ML API 경유로 3개 다 확보(2026-09-19). 팀 공유 크레딧(`search`와 동일 계정)이라 벤더별 개별 키는 필요 없었다.
- [ ] §4 테스트 문장을 실제 사용자 로그(또는 팀이 합의한 현실적 샘플)로 교체 — **아직 미결.** v1 실측(§9)은 §4의 직접 작성한 예시 그대로 썼다. 실사용자 로그 확보는 case가 아직 런칭 전이라 v2 데이터셋 작업으로 남긴다.
- [x] 3개 후보 모델에 동일 프롬프트+스키마로 실측 — 스키마 준수율 비교(§9, 2026-09-19)
- [x] 실측 결과를 바탕으로 `docs/modules/case/decisions/`에 확정 문서 작성 → `intent-llm-model-selection.md`
- [x] judge 판정 20% 스팟체크(사람이 직접 확인, harness README "검증" 절) — 2026-09-20 완료. 126개 중 5개(4%) 불일치, GPT-5 Nano와는 무관 — `decisions/intent-llm-model-selection.md` §9.

## 9. 실측 결과 요약 (2026-09-19)

전체 상세 수치·필드별/카테고리별 분해는 `experiments/intent-llm-model-comparison/results/summary.md`(judge_run_id로 원본 채점 파일까지 추적 가능)에 있다 — 여기서는 §6 "임시 추천"과 대조되는 지점만 남긴다.

- 3개 후보 전부 `schema_compliance_rate` 100%(스키마 위반 0건) — §3의 "실측 미확인" 각주가 실측으로 닫혔다.
- §6이 1순위로 추천했던 GPT-5 Nano가 실측에서도 전 지표 최고치(field 정확도 100%, hallucination/missed 0%)를 기록했다 — 추천이 결과로 확인됨.
- 다만 §5/§6엔 없던 축(latency)에서 GPT-5 Nano가 나머지 둘보다 3.7~4.8배 느렸다(약 12.7초 vs 2.7~3.4초) — 후보 비교표(§5)에 latency가 아예 없었다는 것 자체가 이번에 드러난 조사 공백이다.
- 최종 선택·latency 트레이드오프 판단 근거는 `decisions/intent-llm-model-selection.md` 참고 — 이 문서(research)는 그 결정을 다시 적지 않는다.

## 8. 원본 자료 Reference

- `docs/modules/case/research/architecture-input-memo.md` §2, §3 열린 결정 표 "intent 멀티턴 확장"
- `docs/modules/case/tech-spec.md` §1
- `docs/modules/case/checklists/phase1-completion-checklist.md` 74번 항목
- 가격 조사(2026-09-16 웹 검색):
  - [Gemini API Pricing: Full Breakdown of Costs (Sep 2026)](https://developer.puter.com/tutorials/gemini-api-pricing/)
  - [Gemini 3.1 Flash Lite Preview API Pricing 2026](https://pricepertoken.com/pricing-page/model/google-gemini-3.1-flash-lite-preview)
  - [GPT 5 Nano API Pricing 2026](https://pricepertoken.com/pricing-page/model/openai-gpt-5-nano)
  - [GPT 5 Mini API Pricing 2026](https://pricepertoken.com/pricing-page/model/openai-gpt-5-mini)
