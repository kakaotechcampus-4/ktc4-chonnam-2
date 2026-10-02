# Coarse→Fine handoff 트레이스: 이미지·느린 영상, Coarse 2 fps / Fine 4 fps

실행일: 2026-09-29. 호출별 후보 구간(원본 초)·판정·토큰은 구조화 결과 [이미지](./gemini-handoff-image-trace-2026-09-29-results.json)·[느린 영상](./gemini-handoff-slowdown-trace-2026-09-29-results.json)에 기록했다. 영상·API 키는 저장하지 않았다. 실행 스크립트: `scripts/gemini_coarse_fine_slowdown_trace.py`.

## 질문

[handoff 실험 결정](../decisions/fine-coarse-handoff-experiment-2026-09-28.md)의 `diagnostic-handoff-v1`을 처음 실행한다. **Coarse 관찰과 핵심 시각을 검증되지 않은 단서로 Fine에 넘기면 검출이 늘어나는가, 음성 후보가 OBSERVED로 끌려가는가.** 전송은 [이미지 트레이스](./gemini-coarse-fine-image-trace-2026-09-28.md)·[느린 영상 트레이스](./gemini-coarse-fine-slowdown-trace-2026-09-29.md)와 같은 프레임 밀도(Coarse 원본 2 fps / Fine 원본 4 fps)를 쓴다.

## 방법

- 느린 영상 트레이스의 스크립트에 `--profiles`·`--transport image|video`를 추가했다. 기본값(p3·video)은 9/29 실행과 같다.
  - image: `MediaPreparer`가 준비한 Coarse 2 fps(360p)·Fine 4 fps(720p) 프레임을 전량 `image_url`로 보낸다(`gemini_coarse_fine_image_trace.ImageInvoker`).
  - video: Coarse 0.5x·Fine 0.25x로 늘려 `type: file`로 보낸다. 느린 영상 안내 단락은 9/29와 같고, handoff일 때만 "Coarse 핵심 시각도 원본 기준이므로 제공 영상에서는 그 N배 위치" 한 문장을 덧붙였다.
- profile은 `diagnostic-v1`(대조)과 `diagnostic-handoff-v1`이다. 둘은 Coarse 프롬프트(`coarse-diagnostic-v1`)가 같고 Fine 지시문 하나만 다르다. **p3와는 Coarse 프롬프트도 다르므로** 이전 p3 실행과의 차이를 handoff 효과로 읽지 않는다.
- 조건(전송 × profile)당 7클립 × 2회. 클립 판정은 9/29와 같다: 위반 클립은 정답 구간과 겹친 후보의 Fine이 `OBSERVED`일 때 HIT, 위반 없는 클립은 `OBSERVED`가 없으면 정답. 9/28 이미지 트레이스와 맞추려고 클립 단위(`OBSERVED`가 하나라도 있으면 검출)도 함께 적는다.
- 스크립트 수정 중 발견: `DiagnosticCoarseResponse`는 `CoarseResponse` 하위 타입이 아니어서, 기존 invoker로 diagnostic profile을 돌리면 Coarse에 Fine 배속이 적용되고 시각 환산이 빠진다. 실행 전에 고쳤고 `window_reviews`·`decision_basis` 시각도 원본으로 환산한다.

## 결과

| 전송 | profile | 회차 | 위반 검출 (구간 일치) | 위반 검출 (클립 단위) | 위반 없음 정답 | 호출 | 총 토큰 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 이미지 | diagnostic-v1 | 1 | 1/4 | 2/4 | 3/3 | 12 | 632,891 |
| 이미지 | diagnostic-v1 | 2 | 1/4 | 2/4 | 3/3 | 12 | 603,098 |
| 이미지 | handoff | 1 | 1/4 | 3/4 | 3/3 | 13 | 685,095 |
| 이미지 | handoff | 2 | 1/4 | 2/4 | 3/3 | 10 | 505,852 |
| 느린 영상 | diagnostic-v1 | 1 | 1/4 | 2/4 | 3/3 | 9 | 42,847 |
| 느린 영상 | diagnostic-v1 | 2 | 1/4 | 1/4 | 3/3 | 9 | 42,676 |
| 느린 영상 | handoff | 1 | 2/4 | 2/4 | 3/3 | 9 | 44,455 |
| 느린 영상 | handoff | 2 | 1/4 | 1/4 | 3/3 | 10 | 49,170 |

위반 클립별(두 회차, 후보 구간은 원본 초):

| 클립 | 정답 | 이미지 diagnostic-v1 | 이미지 handoff | 느린 영상 diagnostic-v1 | 느린 영상 handoff |
| --- | --- | --- | --- | --- | --- |
| `20260620_141927` | 실선 4–9초 | 후보 없음 ×2 | 후보 없음 ×2 | 후보 없음 ×2 | 후보 없음 ×2 |
| `youtube_clip_01` | 실선 2–5초 | HIT ×2 | HIT ×2 | HIT ×2 | HIT, `UNCERTAIN` |
| `YT_0003_C05` | 실선 10–13초 | 후보 3개 모두 `NOT_OBSERVED` / 5–8초 `OBSERVED`(정답 밖) | 5–10초 `OBSERVED`(정답 밖) / 5–10초 `NOT_OBSERVED` | 4–8초 `OBSERVED`(정답 밖) / `NOT_OBSERVED` | 4–12초 HIT ×2 |
| `YT_0002_C00` | 중앙선 11–14초 | 14.5–17.5초 `OBSERVED`(정답 밖) / 14.5–18초 `NOT_OBSERVED` | 14.5–17.5초 `OBSERVED`(정답 밖) ×2 | 후보 없음 ×2 | 후보 없음 ×2 |
| 위반 없는 3클립 | — | 오탐 0 | 오탐 0 | 오탐 0 | 오탐 0 (141628 후보 1개 `NOT_OBSERVED`) |

진단 issue는 느린 영상 diagnostic-v1 2회차 `YT_0003`의 `TRACE_WINDOW_COVERAGE` 하나다.

## 이전 실행과 비교

| 실행 | profile | 위반 검출 (구간 일치) | 위반 검출 (클립 단위) | 위반 없음 정답 | 회차 평균 토큰 |
| --- | --- | --- | --- | --- | --- |
| 영상 1 fps (9/26) | diagnostic-v1 | — | 0/4 (`OBSERVED` 0) | — | 32,498 |
| 이미지 2/4 fps (9/28) | p3 | 기록 없음 | 3/4 | 3/3 | 864,947 |
| 느린 영상 0.5x/0.25x (9/29) | p3 | 1/4, 2/4 | 2/4, 2/4 | 3/3 ×2 | 57,484 |
| 이미지 2/4 fps (이번) | diagnostic-v1 / handoff | 1/4 ×2 / 1/4 ×2 | 2/4 ×2 / 3/4, 2/4 | 3/3 ×4 | 617,995 / 595,474 |
| 느린 영상 0.5x/0.25x (이번) | diagnostic-v1 / handoff | 1/4 ×2 / 2/4, 1/4 | 2/4, 1/4 / 2/4, 1/4 | 3/3 ×4 | 42,762 / 46,813 |

## 해석

- **handoff의 효과는 이번 반복 안에서 구분되지 않는다.** 같은 전송에서 diagnostic-v1과 handoff의 차이는 회차당 많아야 1클립이고, 두 회차 모두 같은 방향인 조건이 없다.
- **음성 끌림은 관찰되지 않았다.** 결정 문서가 우려한 음성 후보의 `OBSERVED` 전환은 handoff 4회 모두 없었다. 반대 방향으로 `youtube_clip_01`이 한 번 `UNCERTAIN`이 됐다. 지시문이 "Coarse와 다르면 불확실성으로 남기라"고 하므로 예상 범위다.
- **느린 영상 `YT_0003`의 handoff HIT ×2는 handoff 효과로 귀속할 수 없다.** 두 profile은 Coarse 프롬프트가 같은데 handoff 회차의 Coarse만 정답까지 덮는 4–12초 후보를 냈다. 차이는 Coarse 쪽에서 났다. Fine `OBSERVED`가 그 구간의 어느 시각을 가리켰는지는 결과에 남지 않았다.
- **이전 p3 실행보다 나아지지 않았다.** 느린 영상은 p3(9/29) 클립 단위 2/4·2/4 대비 이번 1–2/4, 이미지는 p3(9/28) 3/4 대비 2–3/4다. 차이의 주된 곳은 `YT_0002`로, p3 느린 영상에서는 HIT ×2였는데 `coarse-diagnostic-v1`은 느린 영상에서 후보를 내지 못했다. 9/26에도 diagnostic-v1은 p3보다 Fine 호출이 적었다(4 vs 9). 비용이 p3보다 낮은 것도 후보가 적어서다.
- **병목은 Fine보다 Coarse다.** `141927`은 8회 모두 Coarse 후보가 없어 Fine에 닿지 않았다. handoff는 Coarse가 후보를 낸 뒤에만 작동하므로 이 클립에는 영향을 줄 수 없다.
- **`YT_0002` 이미지 후보는 정답과 겹치지 않는데 Fine이 `OBSERVED`를 냈다.** 후보 14.5–17.5초에 padding 4초가 붙어 Fine 구간(10.5–21.5초)이 정답 11–14초를 포함한다. Fine이 정답 사건을 본 것인지 후보 구간의 다른 움직임을 본 것인지는 결과로 알 수 없다. 구간 일치 기준은 이 경우를 MISS로 센다.
- 이미지와 느린 영상의 차이는 클립 단위로 이미지 쪽이 많아야 1클립 앞서고(`YT_0002`), 토큰은 약 13배다.

## 한계

- 조건당 2회, 7클립이다. 반복 정책과 공식 매칭 기준은 [#158](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/158) 답변 대기다.
- 결과 파일은 Fine `OBSERVED`의 clip 내 시각을 남기지 않는다. `YT_0002`·`YT_0003`의 정답 밖 `OBSERVED`가 정답 사건인지 판별할 수 없다.
- `YT_0003_C05` 라벨은 사용자 제공이며 프레임 교차검증 전이다. 5–10초 부근 `OBSERVED`가 반복되므로 사람 확인이 필요하다.
- 느린 영상 handoff는 안내 문장이 한 줄 더 있다. 그 효과를 분리하지 않았다.
- 이 기록은 운영 설정(`config.py`, `media.py`, `provider.py`)과 `fine-p3`를 바꾸지 않는다.
