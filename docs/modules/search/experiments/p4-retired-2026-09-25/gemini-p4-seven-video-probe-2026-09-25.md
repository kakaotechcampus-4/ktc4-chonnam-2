# Gemini p4: Search 영상 7개 라이브 재실행

실행일: 2026-09-25. 사건 구간은 소유자가 원본 영상을 직접 보고 확인한 결과다. 호출별 후보·판정·프롬프트 fingerprint·토큰·지연시간과 입력 SHA-256은 [구조화 결과](./gemini-p4-seven-video-2026-09-25-results.json)에 기록했다. 영상 파일이나 API 키, 모델의 자유 서술형 관찰은 결과에 저장하지 않았다.

## 방법

- 현재 Search의 OpenAI 호환 프록시로 `gemini-3.8-flash`를 실제 호출했다. 실행 메모리에서 `prompt_revision=p4`를 선택했고 저장된 p3 기본값은 바꾸지 않았다. Coarse는 `coarse-p4`, Fine은 `fine-p4`와 사건별 지시문을 사용했다.
- 7개 원본 모두 ffprobe로 길이를 확인한 뒤 Search의 미디어 준비 경로를 거쳤다. Coarse는 1 fps/최대 360p, Fine은 2 fps/최대 720p, 후보 앞뒤 여유 4초다. 재시도는 0회, 영상별 실행 시간 상한은 180초다.
- 영상 확인으로 정한 사건 유형으로 Coarse를 제한했다. 중앙선 영상은 `CENTER_LINE_CROSSING`, 나머지는 `SOLID_LINE_LANE_CHANGE`를 요청했다. 차로변경 없음·점선 변경 3개는 실선 위반에 대한 음성 영상으로 평가했다. Coarse 후보 **전부** Fine으로 검증했다.
- 양성 영상의 후보 구간과 영상 확인 구간이 1 ms라도 교차하고 사건 유형이 같으면 Coarse 구간 겹침으로 센다. 이것은 핵심 시각 정확도나 Fine 위반 판정의 성공을 뜻하지 않는다. 각 영상은 이번에 1회 실행했다.

## 영상별 결과

| 영상 | 영상 확인 | p4 Coarse 후보 (초) | 영상 확인 구간 겹침 | p4 Fine |
| --- | --- | --- | --- | --- |
| `20260620_141628_EVT_1.avi` | 실선 변경 없음 | 0–3.5 | 해당 없음 | `NOT_OBSERVED` |
| `20260620_141927_EVT_1.avi` | 실선 변경 4–9초 | 11–15 | **누락** | `ProviderPayloadError`: `p4 lane marking contradicts predicate state` |
| `20260620_141956_EVT_1.avi` | 점선 변경 10–14초, 실선 위반 없음 | 후보 없음 | 해당 없음 | 실행 안 함 |
| `20260620_150504_EVT_1.avi` | 차로변경 없음 | 후보 없음 | 해당 없음 | 실행 안 함 |
| `youtube_clip_01.mp4` | 실선 변경 2–5초 | 0–3.5 | **겹침** | `UNCERTAIN` (`ROAD_MARKING_IDENTITY_AMBIGUITY`) |
| `YT_0003_C05.mp4` | 실선 변경 10–13초 | 2–7, 30–36, 53–58 | **누락** | 순서대로 `NOT_OBSERVED`, `ProviderPayloadError`, `ProviderPayloadError`; 두 오류는 `p4 lane marking contradicts predicate state` |
| `YT_0002_C00.mp4` | 중앙선 침범 11–14초 | 11–15 | **겹침** | `ProviderPayloadError`: `p4 NOT_OBSERVED lacks a visible contradiction` |

Coarse는 7개 영상에서 모두 정상 종료했고 후보 7개를 냈다. 양성 4개 중 영상 확인 구간과 겹친 후보는 2개였다. Fine 호출 7회의 결과는 `NOT_OBSERVED` 2개, `UNCERTAIN` 1개, 응답 상태 검증 오류 4개, `OBSERVED` 0개다. **양성 영상 4개 중 최종 위반 검출에 성공한 영상은 0개**다. 음성 영상 3개에서는 최종 `OBSERVED`가 없었지만, `141628`은 Coarse 후보 1개를 Fine이 기각했다.

총 실제 모델 호출은 14회, 보고된 토큰은 32,669개다. 토큰 단가가 로컬 설정에 완비되지 않아 비용은 산출하지 않았다. Fine 응답이 검증에서 거부된 호출도 모델 사용량에는 포함했다.

## 해석과 한계

- `141927`과 `YT_0003_C05`는 Coarse가 영상 확인 구간을 놓쳤다. `youtube_clip_01`은 후보 구간이 일부 겹쳤지만 Fine이 실선 종류를 확정하지 못했다. `YT_0002_C00`은 후보를 찾았으나 Fine 응답이 상태 검증을 통과하지 못했다.
- `lane marking contradicts predicate state` 3회와 `NOT_OBSERVED lacks a visible contradiction` 1회는 실제 모델 응답을 받은 뒤 Search의 p4 의미 검증에서 거부된 경우다. 자유 서술형 원응답은 저장하지 않아 모델의 필드 선택과 검증 규칙 중 어느 쪽을 고쳐야 할지는 이 기록만으로 단정하지 않는다.
- `141628`은 영상 확인에도 잔여 불확실성이 있다. YouTube 3개는 프레임 단위 점검 전이다. 이 7개 단회 결과로 전체 성능이나 p3 대비 우열을 추정할 수 없다.
- p4 기본값 채택 근거로 사용하지 않는다. 다음 실험에서는 실패 응답의 개인정보를 제외한 구조화 상태를 일시적으로 점검하고, Coarse 누락과 Fine 상태 검증 오류를 각각 재현한 뒤 동일 영상으로 재측정한다.
