# Search 모델 argon 전환 (Owner 결정)

작성·결정: 2026-10-27 · 서어진(search Owner)

적용 대상: Search Coarse · Fine (`src/daesingo/search`). **자연어 단서 추출(intent, `HINT_EXTRACT`)은 바꾸지 않는다.** intent 모델은 case 결정(`gemini-3.8-flash`)을 그대로 따른다.

이 결정은 [Gemini 3.8 프록시 baseline](gemini-3.8-proxy-baseline-2026-09-18.md)의 모델·경로 항목을 대체한다. 그 문서의 나머지 항목(프록시 경유, `.env` 설정 방식)은 유지된다.

## 결정

| 항목 | 이전 | 이후 |
| --- | --- | --- |
| Coarse · Fine 모델 | `gemini-3.8-flash` | `gemini-4-argon` |
| 기본 base URL | Flash tenant 경로 | argon tenant 경로 (`mlapi.run/e1febb2a-…/v1`) |
| Fine 프롬프트 | `fine-p3` | `fine-p3+fine-gore-v1` — 유형별 지시 뒤에 분기부 안전지대 문장 한 단락 |
| 설정 버전 | `gemini-search-v3` | `gemini-search-v4` |
| intent 모델 · 경로 | Search 설정의 경로를 공유 | `gemini-3.8-flash` · 기존 Flash 경로로 고정(`DAESINGO_INTENT_BASE_URL`로 덮어씀) |

전송 구조(Coarse 원본 2 fps → 0.5배속, Fine 후보 ± 4초 · 원본 4 fps → 0.25배속), `coarse-p3`, `reasoning_effort=low`는 바꾸지 않는다.

## 근거

같은 15영상(위반 12 · 정상 3), 정답 유형 1개 입력, 1회 ([E1 15영상](../experiments/search-structure-confirmation-plan-2026-10-26.md#67-e1--15영상-1회-2026-10-27)):

| 조건 | 위반 검출 /12 | 정상 기각 /3 | 비용 |
| --- | --- | --- | --- |
| Flash v3 (이전 운영) | 2 | 3 | ₩256 |
| argon + `fine-gore-v1` (이 결정) | 7 | 3 | ₩653 |
| argon + CV 후보 합집합 | 7 | 3 | 추가 호출 없음 |

- 7클립 2회(2026-10-26)에서도 argon + `fine-gore-v1`이 위반 4 · 3/4, 정상 기각 3 · 3/3으로 가장 좋았다. Flash는 2 · 2/4였다.
- `fine-gore-v1` 없이 argon만 쓰면 정상 영상 오탐(분기부 안전지대 · 촬영 차량)이 나왔다(2026-10-26 P1, 정상 기각 1 · 2/3). 그래서 문장을 함께 넣는다.
- CV 후보를 합쳐도 검출이 늘지 않았다. 이 결정은 CV를 포함하지 않는다.

## 알려진 한계

- 15영상은 CV 개선에 써 온 개발 표본이고 1회 결과다. 새 영상 성능 판정(E5)은 하지 않았다.
- 비용이 Flash의 약 2.6배다(7클립 회차 ₩270 대 ₩100, 15영상 ₩653 대 ₩256). 30분 영상 1개 예상 약 ₩2,000–3,000(캐시 할인 전 추정).
- argon은 점선 차로 변경의 횡이동을 보지 못했다(2026-10-26 §6.5, 12/12 ABSENT). 점선 기각이 판별 근거를 가진 것은 아니다.
- argon tenant 경로가 Flash 요청을 받는지는 확인하지 않았다. 그래서 intent 경로를 따로 고정했다.

## 운영 반영 시 확인할 것

- 배포 `.env`에 `DAESINGO_GEMINI_MODEL` · `DAESINGO_GEMINI_BASE_URL`이 Flash 값으로 남아 있으면 코드 기본값보다 우선한다. 지우거나 argon 값으로 바꿔야 한다.
- Fine 입력이 바뀌므로 eval Owner에게 사전 통보한다(원칙 8).
