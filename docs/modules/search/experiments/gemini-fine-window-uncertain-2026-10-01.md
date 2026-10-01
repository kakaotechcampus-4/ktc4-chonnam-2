# Fine 고정 구간 실험: 불확실성 보고 규칙(`diagnostic-uncertain-v1`)

실행일: 2026-10-01. 호출별 판정·불확실성 수·관찰 시각(원본 초)·토큰은 [구조화 결과](./gemini-fine-window-uncertain-2026-10-01-results.json)에 기록했다. 관찰 문장 원문과 영상·API 키는 저장소에 두지 않았다. 실행 스크립트: `scripts/gemini_fine_window_trace.py`.

## 질문

9/26 Fine 응답 14개 중 13개가 `uncertainties`를 비운 채 primitive confidence 0.9 이상으로 기각했다. p3에는 confidence·`ABSENT`·`uncertainties` 작성 기준이 없다. **그 보고 규칙(`fine-uncertain-v1.txt`)을 주면 근거 없는 확신 기각이 줄고 정답 구간 판정이 바뀌는가.** 근거는 [handoff 실험 결정](../decisions/fine-coarse-handoff-experiment-2026-09-28.md)의 `diagnostic-uncertain-v1` 항목이다.

## 방법

- Coarse 없이 정답지의 고정 구간을 Fine에 직접 준다. padding은 없다. 양성 4구간(`141927` 4–9초, `youtube_clip_01` 2–5초, `YT_0003` 10–13초, `YT_0002` 11–14초 중앙선), 음성 4구간(`YT_0003` 3–8초 정상 주행, `141956` 10–14초 점선, `141628` 0–7초, `150504` 0–8초).
- 전송은 이미지 720p·4 fps(9/28 이미지 실험과 같은 프레임 추출). 프롬프트·응답 스키마는 진단 실행기 `_fine_spec`을 그대로 쓴다. 대상 힌트는 "없음".
- profile은 `diagnostic-v1`(대조)과 `diagnostic-uncertain-v1`. 구간당 3회, 같은 프레임을 두 profile에 번갈아 보냈다. 총 48호출, 약 109만 토큰.

## 결과

| profile | 양성 OBSERVED | 음성 정답 | 불확실성 기록한 응답 |
| --- | --- | --- | --- |
| diagnostic-v1 | 6/12 | 12/12 | 7/24 |
| diagnostic-uncertain-v1 | 6/12 | 12/12 | 8/24 |

구간별(3회, 두 profile 같음):

| 구간 | 기대 | 결과 |
| --- | --- | --- |
| `141927` 4–9초 실선 | OBSERVED | NOT_OBSERVED ×6, 불확실성 0 ×6 |
| `youtube_clip_01` 2–5초 | OBSERVED | OBSERVED ×6 |
| `YT_0003` 10–13초 실선 | OBSERVED | NOT_OBSERVED ×6, 원거리 불확실성 1개씩 |
| `YT_0002` 11–14초 중앙선 | OBSERVED | OBSERVED ×6 |
| 음성 4구간 | NOT_OBSERVED | NOT_OBSERVED ×24 |

## 해석

- **불확실성 보고 규칙은 판정을 바꾸지 못했다.** 판정은 48호출 중 한 건도 두 profile 사이에 다르지 않았고, 불확실성 기록도 7 → 8로 차이가 없다.
- **규칙이 겨냥한 행동도 그대로다.** `141927`에서는 규칙을 준 3회 모두 `uncertainties`가 비었고 횡단 부재를 0.95–0.98로 보고했다. `YT_0003`에서는 원거리 제한을 적으면서도 "차선 횡단 부재는 명확함"이라고 쓰고 기각했다.
- **두 실패 구간의 원인은 다르다.**
  - `YT_0003`: 위반 차량은 오른쪽 차로의 검은색 승용차다(사용자 확인). Fine은 6회 모두 "전방 2차로(오른쪽 차로)의 붉은 후미등 검은색·어두운 승용차"를 대상으로 골랐다. **대상은 맞게 잡고 횡이동·횡단을 `ABSENT`(0.8–0.95)로 봤다.** 대상 연결이 아니라 원거리 차량의 횡이동을 보지 못한 실패다(`FINE_FALSE_NEGATIVE`, 원거리 해상도). 대상 힌트로는 고쳐지지 않는다.
  - `141927`: 정답지의 위반 차량은 앞 회색 SUV다. Fine은 "우측 차로를 주행하다 화면 우측으로 빠져나가는 흰색 SUV" 등을 대상으로 골랐고 회색 SUV를 지목한 응답은 없었다. 4–9초 1 fps 프레임을 확인하니 흰색 SUV는 촬영 차량 바로 오른쪽에서 추월당해 화면 밖으로 빠지는 **다른 차량**이고, 회색 SUV는 그 앞 멀리 작게 보인다. Fine은 가깝고 큰 차량을 대상으로 잡았다(`TARGET_ASSOCIATION`).
  - 두 위반 차량 모두 **화면에서 멀고 작다.** `YT_0003` 10–13초 프레임에서 검은색 승용차는 터널 소실점 근처의 붉은 후미등 정도로만 보인다.
- **음성은 안정적이다.** `YT_0003` 3–8초 정상 주행을 포함해 음성 24회가 모두 정답이다. 9/29 트레이스의 `YT_0003` 정답 밖 `OBSERVED`는 정상 주행 구간만 봐서 나온 것이 아니라, padding으로 넓어진 구간이나 Coarse 단계 조건 때문일 수 있다.
- 정답 구간을 줘도 `141927`·`YT_0003`은 Fine이 놓친다. Coarse recall을 고쳐도 이 두 클립은 Fine에서 막힌다.

## 한계

- 구간당 3회, 양성 4구간이다. 반복 정책은 [#158](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/158) 답변 대기다.
- padding 없는 구간이라 운영 입력(후보 ± 4초)과 다르다.
- 이 기록은 운영 `fine-p3`와 설정을 바꾸지 않는다.
