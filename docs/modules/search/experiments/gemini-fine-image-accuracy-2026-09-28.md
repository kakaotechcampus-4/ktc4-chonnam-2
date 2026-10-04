# Fine 이미지 정확도: fps를 올리면 실선 판별이 나아지는가

실행일: 2026-09-28. 호출·판정·토큰은 [구조화 결과](./gemini-fine-image-accuracy-2026-09-28-results.json)에 기록했다. 영상·API 키는 저장하지 않았다. 실행 스크립트: `scripts/gemini_fine_image_accuracy.py`.

## 질문

[이미지 프레임 probe](./gemini-image-frame-probe-2026-09-28.md)는 토큰(정보량)까지만 봤다. 이건 정확도다: **정답 구간을 Fine에 직접 주고 fps만 1/2/4로 바꾸면 실선/점선 판별 정확도가 오르는가.** Coarse는 건너뛰고 Fine 판별력만 격리한다.

## 방법

- 실제 `fine_prompt_for(SOLID_LINE_LANE_CHANGE)` + 구조화 `FineResponse`. 전송은 `image_url`(720p, detail=high).
- `video/정답지.md`의 라벨 구간을 그대로 Fine에 넣는다(Coarse 없음). fps 1/2/4로 프레임 수만 바꾼다.
- 6클립(OBSERVED 3: 141927·youtube_clip_01·YT_0003 / NOT_OBSERVED 3: 141956·141628·150504).

## 결과

| fps | 정확도(6클립) |
| --- | --- |
| 1 fps | 4/6 |
| 2 fps | 3/6 |
| 4 fps | 4/6 |

**fps 추세 없음** (4→3→4는 노이즈). 실선 위반 OBSERVED 3개 중:

| 실선 클립 | 1fps | 2fps | 4fps |
| --- | --- | --- | --- |
| `20260620_141927` | ❌ NOT_OBSERVED | ❌ | ❌ |
| `youtube_clip_01` | ✅ OBSERVED | ✅ | ✅ |
| `YT_0003_C05` | ❌ UNCERTAIN | ❌ NOT_OBSERVED | ❌ NOT_OBSERVED |

실선 recall 1/3이 fps와 무관하게 고정. 무변경·점선 3클립은 대체로 정확(141628만 2fps 한 번 오탐).

토큰(median): 1fps 입력 5,300+출력 440 / 2fps 10,300+546 / 4fps 20,200+682.

## 해석과 한계

- **정답 구간을 줘도(best-case) fps를 올려 Fine 정확도가 오르지 않는다.** 병목은 시간 밀도가 아니라 먼 거리 선 종류의 공간 해상도로 보인다 — 프록시가 이미지를 고정 그리드(1,100토큰)로 눌러 올릴 수 없다.
- **단, 이는 Fine 단독·고정 구간 결과다.** 전체 파이프라인에선 Coarse의 구간 선택이 달라 결과가 갈린다 — [Coarse→Fine 트레이스](./gemini-coarse-fine-image-trace-2026-09-28.md)에서 `YT_0003`은 OBSERVED로 잡혔다.
- n=6(실선 3)으로 작다. 다른 클립·모델 버전 미확인.
