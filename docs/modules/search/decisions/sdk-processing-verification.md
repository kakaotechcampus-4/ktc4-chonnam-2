# SDK processing 전달·검증 규칙

확정: 2026-09-12 · Owner: 서어진

Gemini Interactions API로 영상 구간을 질의할 때, 설정한 `processing`(해상도·fps·offset)이 **실제 요청 body에 전송됐는지**를 강제·검증하는 규칙. 이 모듈의 모든 Coarse/Fine 탐침과 제품 구현이 단일 출처로 이 페이지를 따른다.

근거 실험: [`../experiments/coarse-fine-probe-summary-2026-09-12.md`](../experiments/coarse-fine-probe-summary-2026-09-12.md) §6 (smoke vs smoke2).

## 왜 필요한가

`google-genai < 2.13`은 `VideoContent.processing`이 Python 객체에 남아 있어도 **실제 HTTP body에서 조용히 제거**한다. 에러·경고가 없어 8초 구간 요청이 304초 클립 전체 처리로 바뀌고 비용이 약 10배 커진다. 따라서 "설정 플래그가 켜져 있음"은 적용 증거가 아니다. 실제 토큰량으로 검증해야 한다.

## 규칙

1. `google-genai >= 2.13.0`을 강제한다. Coarse/Fine 실행 진입에서 최소 버전을 검사하고 미만이면 차단한다.
2. 각 실행 row에 실제 SDK 버전(`sdk_version`)을 기록한다.
3. `input`은 raw dict가 아니라 `VideoContent` / `TextContent` 객체로 전달한다.
4. `start_offset` / `end_offset`은 정수 ms가 아니라 duration 문자열(`"33.000s"`)로 보낸다.
5. 설정 플래그를 믿지 않고 **video token / 요청 구간초(token density)**로 실제 적용 여부를 검증한다.

## 검증 기준값 (video token density)

| 설정 | 예상 밀도 |
| --- | --- |
| low / 1fps | 약 100 tok/s |
| high / 1fps | 약 290 tok/s |
| high / 2fps | 약 553 tok/s |

측정 density가 요청 설정의 기대값과 맞지 않으면 `processing`이 전송되지 않은 것으로 간주하고 결과를 채택하지 않는다. Fine `run1`은 high/2fps에서 중앙값 553 tok/s가 나와 전달이 확인됐다.

## 현재 적용 상태

- Fine: 반영됨 (`MIN_SDK = (2, 13, 0)`).
- Coarse: **미반영**. 같은 최소 버전 검사와 `sdk_version` 기록을 추가해야 한다 — [`gemini-change-application-plan-2026-09-12.md`](gemini-change-application-plan-2026-09-12.md) §3.2 P0.
