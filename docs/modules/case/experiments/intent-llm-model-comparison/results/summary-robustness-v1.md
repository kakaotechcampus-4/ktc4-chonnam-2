# Intent LLM 비교 결과

judge_run_id: `20260922T105457Z` — 이 채점 결과의 raw 파일은 `predictions/<model>/<case_id>.judge.20260922T105457Z.json`에 있다(필드별 판정 근거는 여기서 직접 읽는다).

| model | schema 준수율 | field 정확도 | hallucination rate | missed rate | 평균 latency(ms) | 총 비용(KRW) | 실패 케이스 | judge 실패 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-haiku-4-5 | 100% | 82% | 11% | 1% | 2994 | 134.63 | 0/27 | 0 |
| gemini-3.1-flash-lite | 100% | 85% | 9% | 0% | 1865 | 9.73 | 0/27 | 0 |
| gpt-5-nano | 100% | 85% | 10% | 1% | 17479 | 41.20 | 0/27 | 0 |

## 필드별 정확도

| model | time_hint | vehicle_hint | situation_hint | location_hint | correction_target | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| claude-haiku-4-5 | 81% | 81% | 81% | 89% | 96% | 63% |
| gemini-3.1-flash-lite | 93% | 93% | 93% | 89% | 85% | 59% |
| gpt-5-nano | 96% | 89% | 89% | 93% | 81% | 63% |

## 카테고리별 정확도

(애매 표현 3종·correction 카테고리가 여기서 따로 보임 — README 「채점 방식 — 1차 가설, 실측 전 잠정」)

| model | 무관한_질문_잡담 | 여러_사건_혼합 | 모순_정보 | 구조적_경계_입력 | 프롬프트_인젝션 | 비한국어_언어혼합 | 욕설_유효신고_혼합 | correction_target_오염_시도 | 새사고_정정오인_방지 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-haiku-4-5 | 83% | 39% | 78% | 100% | 78% | 100% | 100% | 67% | 94% |
| gemini-3.1-flash-lite | 100% | 67% | 83% | 100% | 94% | 100% | 100% | 44% | 78% |
| gpt-5-nano | 100% | 72% | 89% | 100% | 94% | 100% | 100% | 50% | 61% |

## 애매 3종 — confidence:low 인정 비율

(정답을 맞혔는가가 아니라 애매함을 스스로 인정했는가. `decisions/intent-llm-eval-target-thresholds.md` §1 참고 — n이 3뿐이라 퍼센트보다 옆의 원본 건수를 우선 본다.)

| model | confidence:low 인정 비율 | (건수) |
| --- | --- | --- |
| claude-haiku-4-5 | - | -/0 |
| gemini-3.1-flash-lite | - | -/0 |
| gpt-5-nano | - | -/0 |
