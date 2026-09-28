# Intent LLM 비교 결과

judge_run_id: `20260922T124511Z` — 이 채점 결과의 raw 파일은 `predictions/<model>/<case_id>.judge.20260922T124511Z.json`에 있다(필드별 판정 근거는 여기서 직접 읽는다).

| model | schema 준수율 | field 정확도 | hallucination rate | missed rate | 평균 latency(ms) | 총 비용(KRW) | 실패 케이스 | judge 실패 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-haiku-4-5 | 98% | 89% | 8% | 2% | 2656 | 232.80 | 1/48 | 0 |
| gemini-3.1-flash-lite | 100% | 87% | 8% | 0% | 1709 | 17.10 | 0/48 | 0 |
| gemini-3.8-flash | 100% | 93% | 4% | 1% | 3853 | - | 0/48 | 0 |
| gpt-5-nano | 100% | 85% | 9% | 0% | 16892 | 69.64 | 0/48 | 0 |

## 필드별 정확도

| model | time_hint | vehicle_hint | situation_hint | location_hint | correction_target | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| claude-haiku-4-5 | 94% | 90% | 90% | 92% | 94% | 73% |
| gemini-3.1-flash-lite | 90% | 94% | 96% | 94% | 88% | 60% |
| gemini-3.8-flash | 98% | 90% | 94% | 94% | 96% | 85% |
| gpt-5-nano | 90% | 90% | 90% | 92% | 85% | 65% |

## 카테고리별 정확도

(애매 표현 3종·correction 카테고리가 여기서 따로 보임 — README 「채점 방식 — 1차 가설, 실측 전 잠정」)

| model | 무관한_질문_잡담 | 여러_사건_혼합 | 모순_정보 | 구조적_경계_입력 | 프롬프트_인젝션 | 비한국어_언어혼합 | 욕설_유효신고_혼합 | correction_target_오염_시도 | 새사고_정정오인_방지 | 정보_위치순서_편향 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-haiku-4-5 | 83% | 77% | 93% | 100% | 90% | 100% | 100% | 53% | 93% | 100% |
| gemini-3.1-flash-lite | 100% | 83% | 83% | 100% | 90% | 100% | 100% | 47% | 70% | 100% |
| gemini-3.8-flash | 97% | 93% | 93% | 100% | 97% | 100% | 100% | 53% | 97% | 100% |
| gpt-5-nano | 80% | 73% | 93% | 93% | 93% | 100% | 100% | 53% | 70% | 100% |

## 애매 3종 — confidence:low 인정 비율

(정답을 맞혔는가가 아니라 애매함을 스스로 인정했는가. `decisions/intent-llm-eval-target-thresholds.md` §1 참고 — n이 3뿐이라 퍼센트보다 옆의 원본 건수를 우선 본다.)

| model | confidence:low 인정 비율 | (건수) |
| --- | --- | --- |
| claude-haiku-4-5 | - | -/0 |
| gemini-3.1-flash-lite | - | -/0 |
| gemini-3.8-flash | - | -/0 |
| gpt-5-nano | - | -/0 |
