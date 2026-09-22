# Intent LLM 비교 결과

judge_run_id: `20260922T120348Z` — 이 채점 결과의 raw 파일은 `predictions/<model>/<case_id>.judge.20260922T120348Z.json`에 있다(필드별 판정 근거는 여기서 직접 읽는다).

| model | schema 준수율 | field 정확도 | hallucination rate | missed rate | 평균 latency(ms) | 총 비용(KRW) | 실패 케이스 | judge 실패 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude-haiku-4-5 | 100% | - | - | - | 3417 | 34.21 | 0/7 | 0 |
| gemini-3.1-flash-lite | 100% | - | - | - | 2676 | 2.38 | 0/7 | 0 |
| gemini-3.8-flash | 100% | 100% | 0% | 0% | 3298 | - | 0/7 | 0 |
| gpt-5-nano | 100% | - | - | - | 12745 | 8.34 | 0/7 | 0 |

## 필드별 정확도

| model | time_hint | vehicle_hint | situation_hint | location_hint | correction_target | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| claude-haiku-4-5 | - | - | - | - | - | - |
| gemini-3.1-flash-lite | - | - | - | - | - | - |
| gemini-3.8-flash | 100% | 100% | 100% | 100% | 100% | 100% |
| gpt-5-nano | - | - | - | - | - | - |

## 카테고리별 정확도

(애매 표현 3종·correction 카테고리가 여기서 따로 보임 — README 「채점 방식 — 1차 가설, 실측 전 잠정」)

| model | 정상_단서 | 일부_누락 | 전부_모호 | 상대시간_표현 | 차량_애매 | 위치_애매 | 잘못_입력_후_correction |
| --- | --- | --- | --- | --- | --- | --- | --- |
| claude-haiku-4-5 | - | - | - | - | - | - | - |
| gemini-3.1-flash-lite | - | - | - | - | - | - | - |
| gemini-3.8-flash | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| gpt-5-nano | - | - | - | - | - | - | - |

## 애매 3종 — confidence:low 인정 비율

(정답을 맞혔는가가 아니라 애매함을 스스로 인정했는가. `decisions/intent-llm-eval-target-thresholds.md` §1 참고 — n이 3뿐이라 퍼센트보다 옆의 원본 건수를 우선 본다.)

| model | confidence:low 인정 비율 | (건수) |
| --- | --- | --- |
| claude-haiku-4-5 | 100% | 3/3 |
| gemini-3.1-flash-lite | 67% | 2/3 |
| gemini-3.8-flash | 100% | 3/3 |
| gpt-5-nano | 100% | 3/3 |
