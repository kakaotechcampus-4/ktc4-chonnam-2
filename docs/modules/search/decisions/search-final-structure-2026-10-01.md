# Search 최종 구조 제안: 느린 영상 Coarse→Fine, p3 프롬프트

날짜: 2026-10-01. 상태: **제안 — 운영 코드 반영 전.** 2026-09-12 이후 Search 실험 전체에서 성능 근거가 있는 선택만 남긴다. 근거가 없거나 효과가 없었던 선택은 넣지 않는다.

## 1. 최종 구조

```
원본 클립 (최대 약 5분, 인라인 12 MiB 상한)
  │
  ▼
[Coarse]  360p · 원본 2 fps 추출 → 0.5x로 늘린 영상(type: file) · 프롬프트 coarse-p3 + 배속 안내
  │        응답 시각 × 0.5 → 원본 시각
  ▼  후보 span (사건 유형별)
[Fine]    후보 span ± 4초 · 원본 4 fps 추출 → 0.25x로 늘린 영상 · 프롬프트 fine-p3(사건별 지시) + 배속 안내
  │        target_hint = 사용자 힌트(있으면 그대로) · 응답 at_offset_ms × 0.25 → clip 기준
  ▼
VisualVerificationResult (OBSERVED / NOT_OBSERVED / UNCERTAIN)
```

| 항목 | 현재 운영 | 최종 구조 | 바뀌는가 |
| --- | --- | --- | --- |
| 모델·추론 | `gemini-3.8-flash`, `reasoning_effort=low` | 같음 | 아니오 |
| Coarse 전송 | 1 fps·360p 영상 → 프록시가 1 fps·low로 처리 | **원본 2 fps를 0.5x로 늘린 영상** | 예 |
| Fine 전송 | 2 fps·720p 영상 → 프록시가 **1 fps·low**로 처리 | **원본 4 fps를 0.25x로 늘린 영상** | 예 |
| 시각 환산 | 없음 | 응답 시각 × 배속 | 예 |
| Coarse 프롬프트 | `coarse-p3` | 같음 + 배속 안내 한 단락 | 안내만 추가 |
| Fine 프롬프트 | `fine-p3` + 사건별 지시 | 같음 + 배속 안내 한 단락 | 안내만 추가 |
| Fine 구간 | 후보 span ± 4초 | 같음 | 아니오 |
| 대상 힌트 | 사용자 `target_hint` | 같음 | 아니오 |
| 의미 없는 설정 | `fine_fps=2.0`, `fine_media_resolution="high"`, Fine 720p 전처리 | 정리(프록시가 무시함) | 예 |

## 2. 채택 근거

### 전송: 느린 영상 (Coarse 0.5x / Fine 0.25x)

- **프록시는 영상을 1 fps·프레임당 66토큰으로 강제한다.** `fps`·`media_resolution`은 전달되지 않는다([프록시 샘플링](../experiments/gemini-proxy-video-sampling-2026-09-28.md)). 현재 `fine_fps=2`·720p는 모델 입력을 바꾸지 않는다. 늘린 영상만이 영상 단가로 프레임 밀도를 올리는 경로다(토큰 = 재생 초 × 66, [토큰 probe](../experiments/gemini-video-slowdown-token-probe-2026-09-29.md)).
- **7클립 결과(p3, 2회)**: 1x는 위반 검출 0/4·2/4로 흔들렸고, 0.5x/0.25x는 1/4·2/4(구간 일치), 클립 단위 2/4·2/4, 오탐 0이다([느린 영상 트레이스](../experiments/gemini-coarse-fine-slowdown-trace-2026-09-29.md)). 2026-10-01 Coarse 단독 0.5x 3회는 위반 클립 적중 2/4로 매회 같았다([Coarse recall](../experiments/gemini-coarse-recall-prompt-2026-10-01.md)).
- **단, 1x 대비 검출 이득은 통계적으로 구분되지 않는다.** 원 기록도 "2회로는 배속 효과를 말할 수 없다"고 적었고, 배속과 안내 단락 효과도 분리하지 않았다. 채택 이유는 검출 이득이 아니라 (1) 이미지보다 훨씬 싸게 프레임 밀도를 올리는 유일한 영상 경로이고, (2) 1x보다 회차 간 흔들림이 작았으며(0/4·2/4 대 1/4·2/4), (3) 오탐이 늘지 않았다는 점이다.
- **시각 환산은 0.5초 이내로 맞다.** 영상 변환과 모델 응답 모두 확인했다([시각 환산 검증](../experiments/gemini-slow-video-time-probe-2026-10-01.md)). 단 클립 2개와 화면 전체의 빨간 사각형으로 잰 값이라, 작은 차량의 느린 움직임에서 시점 판단 정확도는 이 검증 범위 밖이다.
- **비용**: 7클립 회차 평균 57,484토큰으로 1x(30,301)의 약 2배, p3 이미지 전송(864,947)의 약 1/15이다.

### 이미지 전송을 택하지 않은 이유

- 이미지(Coarse 2 / Fine 4 fps)는 클립 단위 3/4였지만([이미지 트레이스](../experiments/gemini-coarse-fine-image-trace-2026-09-28.md)) 후보 구간을 기록하지 않아 구간 일치 기준으로 다시 셀 수 없다. 9/29 이미지 실행(Coarse 프롬프트 `coarse-diagnostic-v1`, p3 아님)의 구간 일치는 4회 모두 1/4였다. 날짜·프롬프트가 달라 직접 비교는 아니다.
- 정답 구간을 준 Fine 단독에서 이미지 fps를 1→4로 올려도 정확도가 오르지 않았다([Fine 이미지 정확도](../experiments/gemini-fine-image-accuracy-2026-09-28.md)). 2026-10-01 Fine 고정 구간 이미지 4 fps는 양성 6/12, 음성 12/12였다. 놓친 `141927`은 이미지·느린 영상, 전체·crop, 힌트 유무, 구간 4–9·4–10초 모든 조건에서 놓쳤다. `YT_0003`은 고정 구간에서 이미지(전체·crop·힌트)로만 시험했고 모두 놓쳤다.
- 정확도 이득이 확인되지 않은 채 토큰이 13–15배다(p3 기준 약 15배, 9/29 diagnostic 기준 약 13배).

### 프롬프트: p3 유지

| 시험한 변형 | 결과 | 기록 |
| --- | --- | --- |
| `coarse-diagnostic-v1` (구간별 검토) | p3보다 후보가 적고 검출 낮음 | [handoff 트레이스](../experiments/gemini-handoff-trace-2026-09-29.md) |
| `coarse-subject-v1`·`coarse-multi-v1` | recall 6/12로 p3와 같음, 후보만 늘어남 | [Coarse recall](../experiments/gemini-coarse-recall-prompt-2026-10-01.md) |
| `fine-handoff-v1` (Coarse 관찰 인계) | 효과 구분 안 됨, 음성 끌림 0 | [handoff 트레이스](../experiments/gemini-handoff-trace-2026-09-29.md) |
| `fine-uncertain-v1` (불확실성 보고 규칙) | 48호출 판정 차이 0 | [Fine 고정 구간](../experiments/gemini-fine-window-uncertain-2026-10-01.md) |
| `fine-crop-v1` + 원본 해상도 crop | 대상 연결은 고쳐지나 검출 0 | [crop × 힌트](../experiments/gemini-fine-crop-hint-2026-10-01.md) |

효과가 확인된 변형이 없으므로 운영 p3를 유지한다. 진단 profile은 실험 도구로만 남긴다.

### 대상 힌트: 운영 입력 그대로

`141927`에서 `target_hint`를 주면 Fine이 가까운 다른 차량 대신 지목한 차량을 대상으로 잡았다(이미지 전송 3/3, [crop × 힌트](../experiments/gemini-fine-crop-hint-2026-10-01.md)). 이것은 대상 선택이 맞았다는 뜻이고 검출은 여전히 0/3이다. 한 클립 결과다. 운영은 이미 사용자 힌트를 넘긴다. 진단 실행기만 "없음"으로 고정한다. 바꿀 것이 없다.

## 3. 넣지 않은 것

| 선택 | 이유 |
| --- | --- |
| 이미지 전송 | 정확도 이득 미확인, 토큰 13–15배 |
| 공간 crop 기본 적용 | 검출 이득 0. 화면 가장자리(옆 차로·신호등·이륜차)를 잘라낼 위험 |
| Coarse 관찰 인계(handoff) | 효과 미확인. 넣으면 Eval의 Fine 단독 측정 조건이 바뀐다(원칙 8) |
| Fine padding 확대 | Coarse 시각이 정답과 몇 초씩 어긋난 사례가 있으나 padding을 바꾼 측정이 없다 |
| super resolution | 측정 전. 7클립 중 저화질 원본은 `YT_0003`(640×360) 하나다(2026-10-01 ffprobe: `YT_0002` 1280×720, 나머지 1920×1080) |
| ADAS/CV 후보 생성기(Cerberus식) | `product-spec.md` §5 보류. [challenger 정책](challenger-policy.md) 절차 필요 |

## 4. 이 구조로 기대하는 성능과 남는 실패

- 라벨 7클립 기준 기대치: 위반 **1–2/4**(구간 일치, 9/29 두 회차 1/4·2/4. 잡히는 쪽은 `youtube_clip_01`·`YT_0002`), 위반 없는 클립 오탐 0/3, 회차당 약 5.7만 토큰. 1x에서는 회차 간 0/4와 2/4로 갈렸으므로 반영 후 반복 측정으로 범위를 다시 확인한다.
- **풀지 못한 두 클립**:
  - `141927` (1080p, 먼 앞 SUV의 실선 변경): 운영 `coarse-p3`의 Coarse는 2026-10-01 3회 모두 가까운 흰색 SUV의 0–3초를 골랐다. 9/29 같은 조건에서는 정답과 겹치는 2–6.5초 후보가 나온 회차도 있었다. 실험 변형 프롬프트에서는 위반 SUV를 찾았지만 시각을 정답 구간 뒤(10초 이후)로 잡았다. Fine은 정답 구간·대상 힌트·확대·느린 영상을 모두 줘도 "같은 차로 유지"로 본다. 실패 분류 후보: `PRIMITIVE_FAILURE`(차선 대비 위치 변화 인식, 가설).
  - `YT_0003` (360p 원본, 터널 원거리): Coarse는 정상 주행 구간(4–7초)을 고르고, Fine은 맞는 차량을 보고도 횡이동을 보지 못한다. 실험 기록은 `FINE_FALSE_NEGATIVE`(원거리 해상도)로 적었다. 원본 화질 한계까지 포함하면 `PRIMITIVE_FAILURE`일 수도 있어, 분류는 Eval 채점 때 정한다.
- 표본은 7클립·회차당 2–3회다. 반복 정책·공식 매칭 기준은 [#158](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/158) 답변 대기다.

## 5. 운영 반영 경로

1. **Eval에 먼저 알린다.** Fine 입력 프레임 밀도와 시각 환산이 바뀐다(`module-architecture.md` 원칙 8: 제품과 Eval이 같은 Fine capability를 쓴다).
2. 코드 변경 범위(Search 내부): `media.py` Coarse·Fine 준비에 배속 적용, `provider.py` 프롬프트 안내 단락과 응답 시각 환산, `config.py`의 `fine_fps`·`fine_media_resolution`을 배속 설정으로 정리. Recording·Case 계약(`CandidateEvent`, `VisualVerificationResult`)은 바뀌지 않는다.
3. 반영 후 확인: 라벨 7클립 3회 재실행으로 위 기대치를 재현하고, [지연 baseline](../experiments/latency-baseline-2026-09-28.md) 조건으로 Coarse 지연을 다시 잰다. 늘린 영상은 재생 길이가 2배라 provider 응답 시간이 늘 수 있다(미측정).
4. 풀지 못한 두 클립은 eval 실패 분류 통계에 넣어 challenger 개방 근거로 쓴다.

## 미결

- Fine 전송을 느린 영상과 이미지로 같은 고정 구간에서 직접 비교한 측정은 없다(2026-10-01 느린 영상 Fine은 `141927`·`141956`만).
- 늘린 영상의 Coarse 지연 증가량: 미측정.
- 5분 클립을 0.5x로 늘렸을 때 인라인 12 MiB 상한 여유: 미측정(재생 길이 2배이나 프레임 수는 원본 2 fps 기준).
