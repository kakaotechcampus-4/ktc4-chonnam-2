# judge 신뢰도 검증 — robustness v2(48케이스)

**날짜:** 2026-10-04 · **작성:** 유소연(case) · **계기:** 멘토 피드백 Q1(「이 규모에서도 judge 판정을 믿을 수 있는가 — 검증하는 게 좋겠다」)

**대상:** judge_run_id `20260922T124511Z`, judge `anthropic/claude-sonnet-5`(Elice), 4모델 × 48케이스 × 6필드 = 판정 1,152개.

**도구:** `scripts/judge_validation.py`(`sample` · `agree` · `scan`), 산출물 `judge-validation-v2/`.

## 1. 지난 「스팟체크」가 실제로 한 일

이 검증을 시작하기 전에 확인한 사실이다. 이전 문서의 표현과 실제가 달랐다.

- **v1(7케이스)에서만 했다** (`decisions/intent-llm-model-selection.md` §9, 2026-09-20). 판정 126개 중 judge가 `correct`가 아니라고 한 **5개만** 자세히 읽었다. 「20% 스팟체크」라고 적혀 있지만 `correct` 판정 121개의 표본 기록은 없다.
- **사람과 judge의 일치도(kappa 등)는 잰 적이 없다.**
- 48케이스에서 한 점검은 Gemini 3.8 Flash의 `case-15*` 5건뿐이고, 「Claude Code가 원문 · 판정 · 기대값을 대조했고 유소연이 결론을 검토」한 방식이었다 (`research/intent-llm-robustness-test-design.md` §14). judge(Claude Sonnet)와 같은 계열 모델이 본 것이라, 둘이 같은 방식으로 틀리는 경우는 잡지 못한다.

## 2. 방법

| 단계 | 한 일 |
| --- | --- |
| 표본 | 1,152개에서 80개. judge 판정 종류별로 나눠 뽑았다 — `correct` 40, `hallucinated` 22, `partial` 12, `missed` 6. 카테고리 · 모델이 고르게 섞이도록 돌아가며 뽑고 순서를 섞었다(seed `20261004`). 판정을 뺀 항목(`items.jsonl`)과 judge 판정(`key.jsonl`)을 분리했다 |
| AI 1차 판정 | Claude Opus 5.5(Claude Code)가 `items.jsonl`만 보고 80개를 판정한 뒤 `key.jsonl`과 대조했다(`labels/ai-opus-5-5.jsonl`). judge와 같은 판정 기준(`schema.py` `JUDGE_SYSTEM_PROMPT`)을 썼다 |
| 사람 판정 | 판정이 갈린 18개 중 **10개**를 유소연이 판정했다(`labels/human-adjudication.json`). A/B 두 판정과 근거를 나란히 보고 맞는 쪽을 고르는 방식이고, 어느 쪽이 judge인지는 가렸다(`adjudication-map.json`). 10개는 「judge가 기준을 어긴 것으로 보이는 5개」와 「기대값의 『A 또는 B』 해석이 갈린 5개」다 |
| 전체 확인 | 사람이 확인한 judge 오류 유형을 1,152개 전체에서 규칙으로 찾았다(`judge_validation.py scan`) |

처음 계획은 사람이 판정을 보지 않고 38개(갈린 18 + 같은 판정 중 무작위 20)를 판정하는 것이었는데, 시간 때문에 위 10개 비교 판정으로 줄였다. 그래서 아래 §5의 한계가 생긴다.

## 3. 결과

### AI 1차 판정과 judge (80개)

| | 4분류 | correct / 아님 |
| --- | --- | --- |
| 일치율 | 77.5% | 78.8% |
| Cohen's kappa | 0.63 | 0.58 |

표본이 `correct`가 아닌 판정을 일부러 많이 뽑았으므로 이 일치율은 1,152개 전체의 일치율이 아니다.

### 사람 판정 (판정이 갈린 10개)

| 묶음 | 사람이 고른 쪽 |
| --- | --- |
| judge가 기준을 어긴 것으로 보인 5개 | AI 3 (jv-036 · jv-041 · jv-070), judge 2 (jv-008 · jv-028) |
| 기대값 해석이 갈린 5개 | AI 3, judge 2 |

AI가 「judge의 기준 위반」이라고 본 5개 중 2개는 사람이 judge가 맞다고 봤다. AI 1차 판정도 틀릴 수 있다는 뜻이고, 판정이 갈린 곳에 사람 판정을 넣은 이유다.

## 4. 확인된 judge 오류 — 정정 케이스의 올바른 null을 틀렸다고 판정

판정 기준은 「이번 발화에서 언급하지 않은 필드는 prior_hints에 값이 있어도 null이다. 이전 값을 복사하면 `hallucinated`(병합은 이 호출의 책임이 아님)」이다. judge는 반대로 「이전 값을 유지했어야 한다」며 올바른 null에 `missed` · `hallucinated`를 줬다. 사람이 jv-036 · jv-070에서 확인했다.

같은 조건(prior_hints에 그 필드 값이 있음 · 모델이 null · judge가 correct 아님)을 1,152개 전체에서 찾으니 12건이었다. 그중 1건(`gpt-5-nano/case-16c/situation_hint`)은 모델이 원문의 「중앙선 침범」을 실제로 놓친 경우라 뺐고, **11건이 이 오류**다. 2건은 judge 근거에 「null 자체는 맞다」 「올바른 처리다」라고 쓰고도 오답을 줬다. **11건 모두 `correction_target_오염_시도` 카테고리**(`case-15a` · `15d` · `15e`)다.

11건을 correct로 바로잡은 field 정확도:

| 모델 | `correction_target_오염_시도` | 전체 |
| --- | --- | --- |
| claude-haiku-4-5 | 53% → 67% | 88.5% → 89.9% |
| gemini-3.1-flash-lite | 47% → 57% | 86.8% → 87.8% |
| **gemini-3.8-flash (채택)** | 53% → 60% | 92.7% → 93.4% |
| gpt-5-nano | 53% → 60% | 85.1% → 85.8% |

전체 정확도는 호출이 실패한 케이스(claude-haiku-4-5 1건)의 판정까지 포함해 셌기 때문에 `summary-robustness-v2.md`의 89%(haiku)와 조금 다르다.

- **모델 순위와 채택 결정은 바뀌지 않는다.**
- 「4모델 모두 47~53%」는 일부가 judge 오류였다. 바로잡아도 57~67%라, 끼워 넣은 무관한 사실로 vehicle · situation을 덮어쓰는 약점은 실제로 남는다.

사람이 확인한 다른 오류 1건(jv-041)은 다른 필드(correction_target)가 틀렸다는 이유로 confidence까지 낮춘 경우다. 09-20에 추가한 「다른 필드의 오류를 옮기지 않는다」 규칙을 어겼다. 이 유형은 규칙으로 전체를 찾기 어려워 따로 세지 않았다.

## 5. 한계

- 판정이 갈린 18개 중 8개(jv-010 · 016 · 020 · 022 · 026 · 029 · 049 · 071)는 사람이 보지 않았다.
- AI와 judge가 같게 본 62개는 사람이 확인하지 않았다. 그래서 **AI 둘이 함께 틀린 비율은 추정할 수 없다.** AI 1차 판정(Claude Opus 5.5)과 judge(Claude Sonnet 5)가 같은 계열이라 이 위험이 있다.
- 사람 판정은 1명이고, A/B 근거를 보고 고르는 방식이라 블라인드 판정보다 판정자가 끌려갈 수 있다.
- 전체에서 찾은 11건은 사람이 확인한 2건과 같은 유형을 규칙으로 찾은 것이다. 11건을 사람이 하나씩 본 것은 아니다(다만 근거 문장이 모두 「이전 값 유지」 논리다).

## 6. 다음

1. judge 판정 기준에 「정정 케이스에서 언급되지 않은 필드의 null은 correct」를 예시와 함께 더 분명히 쓰고 다시 판정한다. 지금 기준에도 있는 문장인데 judge가 무시했다.
2. 같은 기준으로 **Claude Opus 5.5 judge 재판정**. Opus는 AI 1차 판정과 같은 모델이므로, Opus judge는 사람이 판정한 10개로만 평가한다.
3. 반복 실행 일관성(멘토 피드백 Q2)을 붙일 때 judge 재판정 결과를 기준으로 쓴다.
