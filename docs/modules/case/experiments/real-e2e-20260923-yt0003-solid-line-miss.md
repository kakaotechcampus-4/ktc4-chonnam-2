# Real E2E 실행 기록 — Positive 후보 영상 2 (`YT_0003_C05.mp4`, 실선 진로변경)

**날짜:** 2026-09-23 · **실행자:** 유소연(Claude Code 보조) · **브랜치:** `fix/case-search-stream-context-wiring`

**관련 문서:** `real-e2e-20260923-positive-candidate-miss.md`(같은 날, 후보 영상 1 —
`YT_0002_C00.mp4`, 중앙선 침범 — 도 NOT_OBSERVED로 끝났다)

**목적:** 후보 영상 1(`YT_0002_C00.mp4`)이 NOT_OBSERVED로 끝난 뒤, PM이 요구한 Positive
Real E2E 증빙을 위해 두 번째 후보 영상으로 재시도.

**입력 영상:** `YT_0003_C05.mp4` (로컬 경로 `doc/`, git 미커밋). 640x360·25fps·60초,
백색 실선 구간 진로변경 위반이 19~23초에 있다고 사용자가 확인. 화질이 낮다는 점을
후보 선정 단계에서부터 우려로 짚었던 영상.

**결론 먼저 — 이 영상도 Positive Real E2E를 만들지 못했다.** 원본(60초)을 그대로 쓰지
않고 세 단계로 점점 더 좁게 잘라가며 시도했지만(0~30초 → 14~28초 → 18~24초), 매번
`NOT_OBSERVED`였다. 마지막 시도는 위반 구간(19~23초)을 거의 정확히 감싸는 6초짜리
클립이었는데도 대상 차량조차 특정하지 못했다 — 처음 후보 선정 때 우려했던 "화질"이
실제로 발목을 잡은 것으로 보인다.

## 왜 원본(60초) 그대로 쓰지 않고 직접 잘랐는가

`src/daesingo/search/factory.py::build_gemini_search_service()`가 만드는
`SearchService`엔 다음이 고정돼 있다.

```python
RunDeadline(time.monotonic, budget_ms=60_000)
```

이 `RunDeadline`은 `prepare_real_video_context()` 안에서 **한 번만 만들어져 Coarse와
Fine 호출이 같이 나눠 쓴다** — `AnalysisScope.budget.max_latency_sec`(case가 넘기는
180초)를 넘겨도 `coarse.py`의 `deadline.narrowed_to(scope.budget.max_latency_sec * 1000)`가
"narrowing만 허용, 더 큰 값은 무시"라 실효 상한은 여전히 60초다.

전날(2026-09-22) 20초짜리 영상(`20260620_141956_EVT_1.avi`)은 Coarse+Fine 합쳐 12~21초
정도로 여유 있게 끝났다(`real-e2e-usage-log.jsonl` 기준). 60초짜리 영상은 업로드되는
media bytes가 대략 3배라 Coarse 한 번만으로도 그 60초 예산을 다 써버려 Fine이 시작도
못 하고 `DeadlineExceededError`로 끊길 위험이 있다고 판단했다.

**이 60초 값 자체를 고치지 않은 이유:** `factory.py`는 `case`가 아니라 `search` 모듈
소유 코드다(`CLAUDE.md` 「다른 모듈의 문서·폴더를 고치지 않는다」). 값을 늘리는 게
정말 필요하다면 search Owner(서어진) 확인이 필요한 사안이라 이번엔 건드리지 않고,
**입력 영상 자체를 이미 검증된 길이(20~30초대) 안으로 잘라서** 우회했다.

## 시도 1 — 0~30초로 절반만 자르기

**명령:**
```
ffmpeg -y -ss 0 -to 30 -i doc/YT_0003_C05.mp4 -c copy doc/YT_0003_C05_00-30.mp4
```
`-c copy`(재인코딩 없음)로 30.08초 클립 생성, 문제 없이 실행됨.

**실행:** `--target-event-types SOLID_LINE_LANE_CHANGE`

**결과: NOT_OBSERVED.**

```
coarse span: start_ms=3800 end_ms=7200 (절대시간 3.8~7.2초 — 19~23초와 무관)
```

**핵심 문제 발견:** 19~23초를 노렸는데 Coarse가 완전히 다른 구간(3.8~7.2초)을 스스로
골라서 그것만 Fine에 넘겼다 — **19~23초는 이 실행에서 Fine이 아예 보지도 못했다.**
Coarse에 "몇 초를 봐라"를 지정할 방법이 없어서, 넓은 범위를 주면 Coarse가 임의로
가장 그럴듯해 보이는 후보를 고른다는 것을 확인.

Fine이 실제로 본 3.8~7.2초 구간 판정(구조화 필드 원문, 자유서술 필드는 한글이 터미널
콘솔 인코딩으로 깨져 파라프레이즈):

| 필드 | 값 |
| --- | --- |
| target.track_ref | `black_sedan` |
| target.association_confidence | 0.85 |
| primitives.tunnel_lane_marking | PRESENT (0.95) |
| primitives.solid_white_line | PRESENT (0.95) |
| primitives.lateral_lane_change_across_solid_line | **ABSENT (0.9)** |
| uncertainties | `view_angle_limitation` — 터널 진입부 시야 제한으로 1차로→2차로 이동인지, 다른 차량 진입인지, 반사·조명 때문에 실선/점선 여부를 명확히 판별하기 어렵다는 취지 |

## 시도 2 — 14~28초로 좁히기 (19~23초 ±5초)

**목적:** 시도 1에서 드러난 문제(Coarse가 엉뚱한 구간을 고름)를 막기 위해, 위반 구간을
중심으로 앞뒤 5초 여유만 남기고 잘라 Coarse가 고를 수 있는 후보 자체를 좁혔다.

**1차 시도(실패) — `-c copy`:**
```
ffmpeg -y -ss 14 -to 28 -i doc/YT_0003_C05.mp4 -c copy doc/YT_0003_C05_14-28.mp4
```
파일 자체는 만들어졌지만 실행 시 다음 에러로 Recording 단계에서 막힘:
```
daesingo.recording.materialization._FrameCoverageError: 불연속 frame coverage는 지원하지 않습니다
```
**원인:** `-c copy`는 재인코딩 없이 가장 가까운 keyframe에서 자르는데, `14~28`처럼
파일 앞부분이 아닌 임의 지점부터 자르면 B-frame 재정렬 등으로 결과 스트림의 프레임
타임스탬프가 불연속해질 수 있다. `LocalAnalysisMaterializer._frames()`
(`materialization.py`)는 프레임 커버리지가 완전히 연속적인지 엄격히 검증하는데
(`a + length != b`이면 실패), 시도 1(0초부터 자름 — 항상 keyframe)에서는 안 걸렸던 문제가
여기서 처음 걸렸다.

**수정 — 재인코딩으로 재시도:**
```
ffmpeg -y -ss 14 -to 28 -i doc/YT_0003_C05.mp4 -map 0 \
  -c:v libx264 -preset veryfast -crf 18 -c:a aac \
  -avoid_negative_ts make_zero -fflags +genpts \
  doc/YT_0003_C05_14-28.mp4
```
14.02초 클립 생성, 이후 정상 실행됨. **이후 시도 3도 처음부터 재인코딩 방식을 사용.**

**결과: NOT_OBSERVED.**

```
coarse span: start_ms=8000 end_ms=11000 (절대시간 22~25초 — 19~23초의 뒷부분만 겹침, 19~22초는 여전히 못 봄)
```

| 필드 | 값 |
| --- | --- |
| target.track_ref | `target_sedan_1` |
| target.association_confidence | 0.9 |
| primitives.solid_lane_boundary | PRESENT (0.95) |
| primitives.lane_change_across_boundary | **ABSENT (0.95)** |
| uncertainties | 없음 — 이번엔 화질 문제 언급 없이 확신 있게 "안 넘었다"고 판정 |

## 시도 3 — 18~24초로 최대로 좁히기

**목적:** 시도 2도 여전히 2~3초 어긋났으므로, 19~23초 위반 구간을 거의 그대로 감싸는
6초짜리 클립으로 Coarse가 고를 수 있는 다른 후보 자체를 사실상 없앴다.

```
ffmpeg -y -ss 18 -to 24 -i doc/YT_0003_C05.mp4 -map 0 \
  -c:v libx264 -preset veryfast -crf 18 -c:a aac \
  -avoid_negative_ts make_zero -fflags +genpts \
  doc/YT_0003_C05_18-24.mp4
```
6.02초 클립. 처음부터 재인코딩이라 프레임 커버리지 문제 없이 바로 실행됨.

**결과: NOT_OBSERVED — 가장 약한 결과.**

```
coarse span: start_ms=0 end_ms=2000 (절대시간 18~20초 — 6초 클립 중에서도 앞 1/3만, 20~24초는 못 봄)
```

| 필드 | 값 |
| --- | --- |
| target.association_status | **NOT_FOUND** — 추적할 대상 차량 자체를 특정하지 못함 |
| target.track_ref | `null` |
| primitives.solid_lane_marking | PRESENT (0.95) |
| primitives.lane_crossing_motion | **ABSENT (0.95)** |
| uncertainties | 없음 |

6초로 거의 위반 장면만 남을 때까지 좁혔는데도 Coarse가 그 안에서마저 앞쪽 2초만 골랐고,
Fine은 대상조차 못 찾았다.

## 세 시도 비교

| 시도 | 잘라낸 범위(절대시간) | Coarse가 실제로 본 구간(절대시간) | 19~23초 커버 여부 | Fine 판정 |
| --- | --- | --- | --- | --- |
| 1 | 0~30초 | 3.8~7.2초 | 전혀 안 겹침 | NOT_OBSERVED (view_angle_limitation 우려 있음) |
| 2 | 14~28초 | 22~25초 | 뒷부분만 살짝 겹침 | NOT_OBSERVED (확신 있게 "안 넘었다") |
| 3 | 18~24초 | 18~20초 | 앞부분만 살짝 겹침 | NOT_OBSERVED (대상 자체를 못 찾음) |

세 번 다 Coarse가 클립 안에서도 위반 구간의 일부만 걸치거나 아예 비껴간 지점을 골랐고,
Fine은 그 지점에서 확신 있게(대부분 confidence 0.9~0.95) "실선을 넘는 움직임 없음"으로
판정했다. 클립을 좁힐수록 오히려 판정이 더 확신에 차서 부정적으로 나온 점(시도 2·3의
`ABSENT` confidence가 시도 1보다 높고 uncertainty가 사라짐)도 특이하다 — 화질/시야
문제로 모델이 아예 판단을 피하기보다, 짧고 좁은 클립에서 "이건 아니다"라고 더 단정적으로
답하는 경향으로 보인다(검증 안 된 추정).

## 결론

- **Positive Real E2E는 이 영상으로도 닫히지 않았다.** 세 번의 서로 다른 크롭 시도 전부
  NOT_OBSERVED — `20260620_141956_EVT_1`(6회차), `YT_0002_C00`(오늘 1차 시도)에 이어
  **이 영상 자체도 세 개의 추가 negative regression case**로 볼 수 있다.
- Coarse가 좁은 클립 안에서도 목표 구간을 정확히 못 짚는 패턴이 반복됐다 — search 쪽
  실험 문서에서 이미 알려진 "coarse 후보 품질" 문제(`search-design-advancement-2026-09-18.md`
  §5.3)와 같은 종류로 보인다.
- 처음 후보 선정 때 우려했던 "화질이 좀 떨어짐"이 실제로 원인 중 하나였을 가능성이 높다
  — 특히 시도 1의 `view_angle_limitation` uncertainty가 그 정황.
- **다음 단계는 사용자 판단 대기** — 새 영상으로 전환할지, 이 두 영상(YT_0002/YT_0003)의
  negative 결과를 그대로 PM에게 보고할지 결정 필요.

## 변경/생성된 파일

- `doc/YT_0003_C05_00-30.mp4` / `doc/YT_0003_C05_14-28.mp4` / `doc/YT_0003_C05_18-24.mp4`
  — 이번에 만든 크롭 파일 3개 (로컬 전용, `doc/`는 git 미커밋)
- `data/real/case/real_e2e_yt0003.json` — 같은 경로로 세 번 덮어써서 **시도 3(마지막)의
  CaseView만 남아 있다.** 시도 1·2의 산출물은 이 문서의 표·필드 값으로만 보존된다.
