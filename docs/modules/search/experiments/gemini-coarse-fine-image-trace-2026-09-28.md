# Coarse→Fine 이미지 전송 트레이스: 영상(1fps) 대비 검출·비용

실행일: 2026-09-28. 호출·판정·토큰은 [구조화 결과](./gemini-coarse-fine-image-trace-2026-09-28-results.json)에 기록했다. 영상·API 키는 저장하지 않았다. 실행 스크립트: `scripts/gemini_coarse_fine_image_trace.py`.

## 질문

[영상 샘플링](./gemini-proxy-video-sampling-2026-09-28.md)은 프록시가 영상을 1fps·low로 강제함을 보였고, [이미지 프레임 probe](./gemini-image-frame-probe-2026-09-28.md)는 이미지가 프레임 밀도·프레임당 토큰을 올릴 수 있음을 보였다. 그렇다면 **실제 coarse→fine 구조를 이미지 전송(Coarse 2fps / Fine 4fps)으로 돌리면 영상(1fps) 대비 검출과 비용이 어떻게 달라지는가.**

## 방법

- 실제 파이프라인 로직을 재구현하지 않았다. 진단 러너 `diagnostic.run_case`(Coarse가 후보를 만들고 score 정렬 후 각 후보를 Fine으로 넘기는 구조)의 `provider` seam에 **프레임을 `image_url`로 보내는 invoker**를 주입했다. 프롬프트·응답 스키마·후보 핸드오프·`fine_padding_sec`·clamp는 그대로다.
- profile은 비교군과 같은 **p3**(운영 `COARSE_PROMPT`·`fine_prompt_for`). 변경점은 전송(이미지)과 fps(`coarse_fps=2`·`fine_fps=4`)뿐. `MediaPreparer`가 그 fps로 MP4를 만들고 invoker가 그 프레임을 전량 전송한다(Coarse 360p·Fine 720p, 해상도는 토큰에 무관).
- 대상은 `video/정답지.md`의 7클립. clip별로 정답 사건 하나를 검증 event로 지정했다.
- 비교군: [decision-trace-seven-video](./decision-trace-seven-video-2026-09-26-results.json)의 **p3 run**(영상, coarse 1fps·fine 2fps → 프록시가 1fps·low로 강제).

## 결과

| clip | 정답 사건 | 정답 | Coarse 후보 | Fine 판정 | 클립 정오 |
| --- | --- | --- | --- | --- | --- |
| `20260620_141628` | SOLID_LINE | NOT_OBSERVED | 2 | NOT_OBSERVED ×2 | ✅ |
| `20260620_141927` | SOLID_LINE | OBSERVED | 1 | NOT_OBSERVED | ❌ 놓침 |
| `20260620_141956` | SOLID_LINE | NOT_OBSERVED | 1 | NOT_OBSERVED | ✅ |
| `20260620_150504` | SOLID_LINE | NOT_OBSERVED | 1 | NOT_OBSERVED | ✅ |
| `youtube_clip_01` | SOLID_LINE | OBSERVED | 1 | OBSERVED | ✅ |
| `YT_0003_C05` | SOLID_LINE | OBSERVED | 3 | OBSERVED ×2, NOT ×1 | ✅ |
| `YT_0002_C00` | CENTER_LINE | OBSERVED | 1 | OBSERVED | ✅ |

**클립 단위 6/7 정확, 위반 3/4 포착, 오탐 0.**

## 비교

| | 영상 baseline (coarse 1 / fine 2 · p3) | 이미지 (coarse 2 / fine 4 · p3) |
| --- | --- | --- |
| 호출 수 | 16 | 17 |
| verification (fine 호출 기준) | OBSERVED 2 / NOT_OBSERVED 7 | **OBSERVED 4** / NOT_OBSERVED 6 |
| 총 토큰 | **28,607** | **864,947 (약 30배)** |

## 해석

- **검출은 늘었다.** OBSERVED가 2→4. 이미지 전송으로 프레임 밀도·프레임당 토큰이 올라가고 Coarse가 후보를 여러 개 제안한 결과다.
- **Fine 단독 실험과 갈린다.** [Fine 정확도 실험](./gemini-fine-image-accuracy-2026-09-28.md)에서 `YT_0003`은 정답 구간을 고정해 넣었을 때 fps 1/2/4 모두 놓쳤다. 그런데 전체 파이프라인에선 Coarse가 후보 3개를 만들고 Fine이 2개를 OBSERVED로 확인해 잡았다. 즉 **핵심은 fps 자체보다 "Coarse가 맞는 구간을 제안"하는 것**이었다.
- **단, fps 단독 효과로 단정할 수 없다.** 이 실행은 전송(이미지)·fps(2/4)·Coarse 다중후보가 동시에 바뀌었다. "fps를 올려서 좋아졌다"고 분리 귀속할 수 없다.
- **비용이 약 30배다.** 864,947 vs 28,607 토큰. 대부분 Coarse가 클립 전체를 이미지(프레임당 1,100토큰)로 훑기 때문이고, 특히 60초 `YT_0003`은 2fps에서 120프레임이다.
- **`20260620_141927`(교량 백색 실선)은 모든 구성에서 놓쳤다** — 영상, Fine 단독 이미지, 전체 파이프라인 이미지 전부. 지속적 사각지대이며, 원인은 시간 밀도가 아니라 먼 거리 선 종류의 공간 해상도로 보인다(프록시가 이미지를 고정 그리드로 눌러 올릴 수 없음).

## 한계

- **통제 비교가 아니다.** 비교군 영상 run의 manifest event_type을 복구하지 못해 clip별 단일 event로 재구성했고, 비교군의 응답은 보관본에서 redact되어 clip별 대조가 불가능하다. verification 카운트는 clip이 아니라 fine 호출 단위다.
- 원본 7클립·조건당 1회. 다른 클립·모델 버전에서 재확인하지 않았다.
- 검출이 늘어난 것이 실제 정답과 맞는 OBSERVED인지(위 표의 clip 대조로는 3/4)와 fine 호출 카운트(4)는 다른 층위다.

## 결론

이미지 전송 + Coarse 2fps/Fine 4fps는 이번 7클립에서 검출을 2→4로 늘렸으나 **비용이 약 30배**이고, 통제된 fps 단독 실험은 아니며, 가장 어려운 실선 케이스(141927)는 여전히 놓친다. 채택 여부는 이 트레이드오프(검출 +N vs 비용 30×)와 141927류 공간 해상도 한계를 함께 두고 결정한다.
