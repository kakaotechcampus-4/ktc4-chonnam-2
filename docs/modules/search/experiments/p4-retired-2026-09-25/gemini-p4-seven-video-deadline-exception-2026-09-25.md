# Gemini p4: deadline·예외 처리 통합 후 7개 영상 재실행

실행일: 2026-09-25. 사건 구간은 소유자가 원본 영상을 직접 보고 확인한 결과를 사용했다. 호출별 후보·판정·고정 오류 코드·enum 상태·프롬프트 fingerprint·사용량·입력 SHA-256은 [구조화 결과](./gemini-p4-seven-video-deadline-exception-2026-09-25-results.json)에 기록했다.

## 방법

- 기존 OpenAI 호환 프록시와 `gemini-3.8-flash`로 p4를 명시 선택했다. p3 기본값은 유지했다. 영상별 180초 deadline, 재시도 0회, Coarse 1 fps/최대 360p, Fine 2 fps/최대 720p, 후보 앞뒤 4초를 사용했다.
- 영상 확인으로 정한 사건 유형만 Coarse에 요청하고, 생성된 후보를 모두 Fine으로 검증했다. p4 의미 검증 오류는 해당 후보의 `FAILED / PROVIDER_PAYLOAD`로 기록하고 다음 후보·영상을 처리했다. 오류 후보에는 `VisualEvidence`가 없다.
- 영상 확인 구간과 후보 구간이 1 ms 이상 겹칠 때만 Coarse 구간 겹침으로 계산했다. 모델의 자유 서술형 관찰, 원본 영상, API 키는 결과에 저장하지 않았다.

## 결과

| 영상 | 영상 확인 | Coarse 후보 (초) | Fine 결과 |
| --- | --- | --- | --- |
| `20260620_141628_EVT_1.avi` | 실선 변경 없음 | 0–3.5 | `NOT_OBSERVED` |
| `20260620_141927_EVT_1.avi` | 실선 변경 4–9 | 12–16 | `FAILED`: 반증 불일치 |
| `20260620_141956_EVT_1.avi` | 점선 변경 10–14, 위반 없음 | 1–5 | `FAILED`: 표시 종류와 상태 불일치 |
| `20260620_150504_EVT_1.avi` | 차로변경 없음 | 0–4, 6–10 | `NOT_OBSERVED`, `FAILED`: 표시 종류와 상태 불일치 |
| `youtube_clip_01.mp4` | 실선 변경 2–5 | 0–4.5 | `NOT_OBSERVED` |
| `YT_0003_C05.mp4` | 실선 변경 10–13 | 2–7, 29–34, 13–19, 53–58, 21–26 | `NOT_OBSERVED`, 실패 4건 |
| `YT_0002_C00.mp4` | 중앙선 침범 11–14 | 11–15 | `FAILED`: 반증 불일치 |

Coarse는 7개 영상 모두 완료했고 후보 12개를 냈다. 양성 4개 중 영상 확인 구간과 겹친 후보가 있는 영상은 2개다. Fine 12회 중 `NOT_OBSERVED` 4회, `PROVIDER_PAYLOAD` 실패 8회, `OBSERVED` 0회다. 오류는 차선 표시 종류와 상태 불일치 5회, `NOT_OBSERVED` 반증 불일치 3회였다. **양성 4개 중 최종 위반 검출은 0개**다. 총 모델 호출은 19회이고 보고된 토큰은 45,523개다.

중앙선 사례의 구조화 진단에는 `crossing_extent=NONE`과 허용 가능한 반증 키 `crossing_extent`가 있었으나, 모델의 반증 목록에 `contact_state`도 포함됐다. 차선 표시 오류 사례에는 `marking_type_at_crossing=UNCERTAIN`과 `marking_at_crossing=NOT_OBSERVED`가 함께 기록됐다. 둘 다 p4의 엄격한 상태 규칙에 맞지 않아 판정을 생성하지 않았다.

이 회차는 [이전 7영상 결과](./gemini-p4-seven-video-probe-2026-09-25.md)와 별개 실행이다. 후보 수와 상태는 모델 호출마다 달라질 수 있다. 이번 결과는 오류 격리와 안전한 기록을 확인했지만 검출 성능 개선 근거가 아니다. 재시도는 0회였으므로 deadline 재시도 동작은 회귀 테스트로 검증했다.
