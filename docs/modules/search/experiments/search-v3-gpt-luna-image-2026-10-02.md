# 운영 구조 모델 비교: gpt-5.6-luna (이미지 전송)

실행일: 2026-10-02. 구조화 결과: [JSON](./search-v3-gpt-luna-image-2026-10-02-results.json)(후보 구간·판정·primitive 상태·토큰·지연만 있음. 응답 원문은 저장소 밖 `.superpowers/`). 실행: `scripts/gemini_coarse_fine_slowdown_trace.py --transport image --conditions 0.5:0.25 --repeats 3 --profiles p3 --env <임시 env>`.

## 질문

[운영 경로 검증 v3](./search-v3-production-verify-2026-10-01.md)와 같은 Coarse→Fine 구조에서 모델을 `gpt-5.6-luna`로 바꾸면 결과가 어떻게 달라지는가. 같은 날 [3.1-pro 비교](./search-v3-pro-model-verify-2026-10-02.md)의 후속이다.

## 방법

- 임시 env 파일에서만 `DAESINGO_GEMINI_MODEL=gpt-5.6-luna`와 `DAESINGO_GEMINI_BASE_URL`(별도 `mlapi.run` 엔드포인트)을 바꿨다. 저장소 `.env`·코드 기본값은 그대로다.
- **이 엔드포인트는 영상을 받지 않는다.** `type: file`에 `video/mp4`를 보내면 400 `Expected ... application/pdf MIME type`이 돌아온다. 텍스트 요청은 성공했다. 그래서 운영 영상 전송 대신 **이미지 전송**(`--transport image`)으로 돌렸다. `MediaPreparer`가 Coarse 360p 2 fps·Fine 4 fps로 프레임을 뽑고, 그 프레임 전량을 `image_url`로 보낸다. 늘린 영상과 같은 원본 프레임 밀도다.
- p3, `fine_padding_sec=4`, `reasoning_effort=low`, 재시도 0. 7클립 × 3회. 판정 기준은 v3 검증과 같다.

## 결과

| 모델 · 전송 | 위반 검출 (3회) | 위반 없음 정답 | 회차 평균 토큰 | Coarse / Fine 지연 p50 |
| --- | --- | --- | --- | --- |
| 3.8-flash · 늘린 영상 (10/01) | 2·1·1/4 | 9/9 | 55,179 | 약 3.3초 / 5초 |
| 3.1-pro · 늘린 영상 (같은 날) | 3·2·3/4 | 2/9 | 55,906 | 약 5.0초 / 6.9초 |
| **gpt-5.6-luna · 이미지** | 2·1·2/4 | **9/9** | 138,074 | 약 5.1초 / 7.3초 |

| 클립 | 정답 | luna 3회 |
| --- | --- | --- |
| `youtube_clip_01` | 실선 2–5초 | HIT ×3 (대상 "흰색 세단") |
| `YT_0002` | 중앙선 11–14초 | HIT, MISS(Fine 기각), HIT |
| `141927` | 실선 4–10초 | Coarse 후보 0 ×3 |
| `YT_0003` | 실선 10–13초 | Coarse 후보 0 ×3 |
| 위반 없는 3클립 | — | 오탐 0 ×3 (`150504` 후보 2건은 Fine이 기각) |

## 해석

- **검출은 flash와 같은 수준이고 오탐도 0이다.** 잡는 클립도 `youtube_clip_01`·`YT_0002`로 같다. pro처럼 모든 차로 변경을 위반으로 보는 경향은 없었다.
- **Coarse가 보수적이다.** 21회 Coarse 중 후보를 낸 것은 8회뿐이다. 점선 음성 `141956`과 놓치던 두 클립에서는 후보 자체가 없었다. flash·pro는 `141927`에서 틀린 차량(흰색 SUV) 후보라도 냈는데, luna는 아무것도 내지 않았다.
- `youtube_clip_01`은 3/3으로 flash(1/3)보다 안정적이다. 3회뿐이라 차이라고 말하기는 어렵다.
- **비용:** 토큰은 flash 영상의 약 2.5배다. 이미지 전송이라 영상과 단가 구조가 다르다(9/28 Gemini 이미지 전송은 회차 약 86만 토큰). 토큰 단가는 재지 않았다.

## 결론

luna는 flash와 비슷한 결과(위반 1–2/4, 오탐 0)를 내지만, 놓치던 `141927`·`YT_0003`은 여전히 못 잡는다. 영상을 받지 않아 운영 provider를 그대로 쓸 수 없고 토큰도 더 든다. 바꿀 근거는 없다.

## 한계

- 3회, 7클립. flash 대조는 전날 실행이다.
- 전송 방식(이미지 대 늘린 영상)이 비교군과 달라 모델 효과와 전송 효과가 섞여 있다.
- `reasoning_effort=low`만 시험했다.
- HIT 기준이 대상 차량을 보지 않는다. `youtube_clip_01`·`YT_0002` HIT의 대상이 정답 차량인지는 확인하지 않았다.
