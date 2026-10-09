# 운영 경로 검증: gemini-search-v3 (Coarse 2 fps / Fine 4 fps 늘린 영상)

실행일: 2026-10-01. 구조화 결과: [JSON](./search-v3-production-verify-2026-10-01-results.json)(후보 구간·판정·토큰·provider 지연만 있음). 실행: `scripts/gemini_coarse_fine_slowdown_trace.py --transport provider --conditions 0.5:0.25 --repeats 3 --profiles p3`.

## 질문

[최종 구조 제안](../decisions/search-final-structure-2026-10-01.md) §5-3: 코드 반영(`7761639`) 후 운영 경로 그대로 라벨 7클립에서 기대치(위반 1–2/4, 오탐 0/3, 회차당 약 5.7만 토큰)가 재현되는가.

## 방법

- 실험용 invoker가 아니라 **운영 `GeminiProvider`**를 진단 실행기(`run_case`)에 끼웠다. 준비는 운영 `MediaPreparer`(Coarse 360p·2 fps → 0.5x, Fine 360p·4 fps → 0.25x)이고, 배속 안내와 시각 환산은 provider가 한다. 프롬프트는 운영 p3, `fine_padding_sec=4`, 재시도 0.
- 7클립 × 3회. 판정 기준은 [느린 영상 트레이스](./gemini-coarse-fine-slowdown-trace-2026-09-29.md)와 같다(위반 클립은 정답 구간과 겹친 후보의 Fine이 `OBSERVED`면 HIT). `141927` 정답은 4–10초.

## 결과

| 회차 | 위반 검출 | 위반 없음 정답 | 총 토큰 | Coarse provider 지연 p50 / 최대 | Fine p50 / 최대 |
| --- | --- | --- | --- | --- | --- |
| 1 | 2/4 | 3/3 | 63,059 | 3.4초 / 5.2초 | 5.5초 / 10.1초 |
| 2 | 1/4 | 3/3 | 45,863 | 3.2초 / 5.1초 | 5.0초 / 6.2초 |
| 3 | 1/4 | 3/3 | 56,614 | 3.3초 / 5.9초 | 4.7초 / 20.3초 |

| 클립 | 정답 | 3회 결과 |
| --- | --- | --- |
| `youtube_clip_01` | 실선 2–5초 | HIT, MISS(Fine 기각), MISS(Fine 기각) |
| `YT_0002` | 중앙선 11–14초 | HIT ×3 |
| `141927` | 실선 4–10초 | 후보 0–4초·0–2초 → 기각 ×3 |
| `YT_0003` | 실선 10–13초 | 후보 2.5–7.5초 부근 → MISS ×3 (2회는 Fine `OBSERVED`, 정답 밖) |
| 위반 없는 3클립 | — | 오탐 0 ×3 |

## 해석

- **기대치 범위 안이다.** 위반 1–2/4, 오탐 0, 회차 평균 55,179토큰(9/29 실험 경로 57,484).
- **배속 환산 경로는 운영에서 동작한다.** 후보 구간이 모두 원본 길이 안의 원본 초로 돌아왔다(아래 1건 제외). 시각 형식 오류는 없었다.
- **provider 지연은 짧다.** 20초 클립 Coarse p50 약 3.3초, Fine p50 약 5초. Fine 최대 20.3초 1회. 로컬 전처리를 포함한 wall 시간과 5분 클립 지연은 이번에 재지 않았다.
- **영상 밖 후보 1건**: 3회차 `YT_0003`(60초)에서 74.5–77.25초 후보가 나왔다(늘린 영상 기준 149–154.5초로, 늘린 길이 120초도 넘는다). 진단 실행기는 그 후보만 버렸지만, 운영 `coarse.py`는 영상 밖 후보 하나에 `InvalidCoarseSpanError`를 내 그 클립의 후보 전체를 잃는다(#181, 1x 지연 baseline에서도 Coarse 23%). 늘린 영상이 이 빈도를 바꾸는지는 21호출로 알 수 없다.
- `youtube_clip_01`은 3회 중 2회 Fine이 기각했다. 9/29 같은 조건에서도 MISS·HIT로 갈렸다.

## 한계

- 3회, 7클립이다. 반복 정책은 [#158](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/158) 답변 대기다.
- 20초·60초 클립뿐이다. 5분 클립의 준비 크기·업로드 시간·wall 지연은 [지연 baseline](./latency-baseline-2026-09-28.md) 조건으로 다시 재야 한다.
