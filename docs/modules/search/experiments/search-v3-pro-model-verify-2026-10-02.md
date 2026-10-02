# 운영 경로 모델 비교: gemini-3.1-pro-preview

실행일: 2026-10-02. 구조화 결과: [JSON](./search-v3-pro-model-verify-2026-10-02-results.json)(후보 구간·판정·primitive 상태·토큰·지연만 있음. 응답 원문은 저장소 밖 `.superpowers/`). 실행: `scripts/gemini_coarse_fine_slowdown_trace.py --transport provider --conditions 0.5:0.25 --repeats 3 --profiles p3 --env <임시 env>`.

## 질문

[운영 경로 검증 v3](./search-v3-production-verify-2026-10-01.md)와 같은 구조에서 모델만 `gemini-3.8-flash` → `gemini-3.1-pro-preview`로 바꾸면 결과가 나아지는가.

## 방법

- 운영 `GeminiProvider`·`MediaPreparer` 그대로: Coarse 360p 2 fps → 0.5x, Fine 360p 4 fps → 0.25x, p3, `fine_padding_sec=4`, `reasoning_effort=low`, 재시도 0. 7클립 × 3회.
- 바꾼 것은 이 실행의 임시 env 파일뿐이다: `DAESINGO_GEMINI_MODEL=gemini-3.1-pro-preview`, `DAESINGO_GEMINI_BASE_URL`=별도 `mlapi.run` 엔드포인트. 저장소 `.env`·코드 기본값은 바꾸지 않았다.
- 판정 기준은 v3 검증과 같다(정답 구간과 겹친 후보의 Fine이 `OBSERVED`면 HIT).

## 결과

| 모델 | 위반 검출 (3회) | 위반 없음 정답 (3회) | 회차 토큰 평균 | Coarse 지연 p50 | Fine 지연 p50 |
| --- | --- | --- | --- | --- | --- |
| 3.8-flash (10/01) | 2/4 · 1/4 · 1/4 | 3/3 · 3/3 · 3/3 | 55,179 | 약 3.3초 | 약 5초 |
| **3.1-pro** | 3/4 · 2/4 · 3/4 | **1/3 · 0/3 · 1/3** | 55,906 | 약 5.0초 | 약 6.9초 |

| 클립 | 정답 | 3.1-pro 3회 |
| --- | --- | --- |
| `youtube_clip_01` | 실선 2–5초 | HIT ×3 (flash는 1/3) |
| `YT_0002` | 중앙선 11–14초 | HIT ×3 |
| `141927` | 실선 4–10초 | HIT, MISS, HIT |
| `YT_0003` | 실선 10–13초 | MISS ×3 (정상 주행 0–7초 구간을 `OBSERVED`) |
| `141628` (위반 없음) | — | 오탐 ×3 (10.5–13초 짙은 세단) |
| `141956` (점선 정상 변경) | — | 오탐 ×3 (13–17초 흰 세단을 "실선 횡단"으로) |
| `150504` (위반 없음) | — | 정답, 오탐, 정답 |

Coarse 지연 최대 96.9초 1회(3회차).

## 해석

- **`141927` HIT 두 번은 틀린 차량이다.** Fine 대상이 두 번 모두 "흰색 SUV"다. 정답은 먼 회색 SUV다. 회색 SUV는 14–20초 후보에서 찾았지만, 그 시각은 점선 변경(14–18초)이고 Fine은 그것도 실선으로 봤다. [Coarse 4 fps](./gemini-coarse-4fps-2026-10-02.md)와 같은 가짜 적중이다.
- **Pro는 차로 변경을 거의 다 "실선 위반"으로 본다.** Fine 27호출 중 21건 `OBSERVED`였고, 오탐 7건 모두 횡이동·경계 횡단·실선이 전부 `PRESENT`였다. 점선 음성 `141956`은 flash에서 오탐 0이었는데 pro는 3/3 오탐이다. 검출이 오른 것은 판별력이 좋아져서가 아니라 기준이 느슨해진 결과로 보인다.
- 진짜 개선은 `youtube_clip_01`(flash 1/3 → 3/3) 하나다. 대상 차량까지 맞는 위반 검출은 2/4로 flash 최고 회차와 같다.
- 토큰 수는 거의 같다(영상 토큰은 재생 길이로 정해진다). 토큰 단가는 이 실험에서 재지 않았다. 지연은 약 1.4–1.5배.

## 결론

`gemini-3.1-pro-preview`로 바꿀 근거는 없다. 위반 없음 정답이 9/9 → 2/9로 무너졌고, 놓치던 두 클립(`141927`·`YT_0003`)은 여전히 실제로 잡지 못했다.

## 추가: 추론 강도 high (같은 날)

- pro `high`를 7클립 × 3회 돌렸다. 구조화 결과: [JSON](./search-v3-pro-model-high-2026-10-02-results.json).
- 운영 `GeminiProvider`(non-streaming)로는 첫 Coarse 호출부터 `LengthFinishReasonError`(출력 1,986토큰 중 reasoning 약 1,920)로 멈춰, [추론 강도 실험](./gemini-reasoning-effort-2026-10-01.md)의 flash high와 같은 스트리밍 invoker(`--transport video`)로 돌렸다. 영상 준비·프롬프트·배속·시각 환산은 같고 호출 방식만 다르다.
- flash high는 다시 돌리지 않고 2026-10-01 기록을 인용한다.

| 모델 · 추론 | 위반 검출 (3회) | 위반 없음 정답 | 회차 평균 토큰 | Fine 지연 p50 |
| --- | --- | --- | --- | --- |
| flash · low (10/01) | 2·1·1/4 | 9/9 | 55,179 | 약 5초 |
| flash · high (10/01) | 0·1·2/4 | 9/9 | 168,431 | 약 30–45초 |
| pro · low | 3·2·3/4 | 2/9 | 55,906 | 약 6.9초 |
| **pro · high** | 2·3·2/4 | **0/9** | 81,898 | 약 21초 |

- **pro high는 위반 없는 클립 9회 모두 오탐이다.** Fine 25호출 중 24건이 `OBSERVED`였다. 점선 정상 변경 `141956`도 3/3 오탐이다.
- `141927` HIT 1회(2회차)도 대상이 "흰색 SUV"(3–7.5초)라 틀린 차량이다. 회색 SUV는 매회 14–20초(점선 변경)에서 찾았고 Fine은 실선으로 봤다.
- `youtube_clip_01`·`YT_0002`는 3/3이다. `YT_0003`은 0/3.
- pro는 추론을 올려도 판별력이 늘지 않고, 오히려 모든 차로 변경을 위반으로 보는 쪽으로 더 기운다. flash는 high에서 검출이 늘지 않았지만 오탐은 0이었다.

## 한계

- 3회, 7클립. flash 대조는 전날 실행이다.
- pro high는 스트리밍 invoker로 돌려 low(운영 provider)와 호출 경로가 다르다.
- HIT 기준이 대상 차량을 보지 않는다. 이번에도 `141927`에서 틀린 대상이 HIT로 셌다.
