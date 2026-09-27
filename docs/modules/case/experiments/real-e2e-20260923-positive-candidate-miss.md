# Real E2E 실행 기록 — Positive 후보 영상 (`YT_0002_C00.mp4`)

**날짜:** 2026-09-23 · **실행자:** 유소연(Claude Code 보조) · **브랜치:** `fix/case-search-stream-context-wiring`

**목적:** PM 피드백(2026-09-22 회신) — "Negative Real E2E(`20260620_141956_EVT_1`, NOT_OBSERVED)는
통과했지만, Positive Real E2E(실제 위반이 명확히 보이는 영상 1개 → OBSERVED → CaseView →
Web 렌더 → 스크린샷)가 아직 안 닫혔다." 이번 실행은 그 Positive 시도다.

**입력 영상:** `YT_0002_C00.mp4` (로컬 경로 `doc/`, git 미커밋, 유튜브 출처·번호판 기 모자이크).
팀 확인상 실제 위반(중앙선 침범 후 좌회전, 추정 구간 11~14초)이 촬영된 영상.

**결론 먼저 — Positive Real E2E는 이번에도 닫히지 않았다.** 파이프라인은 요청받은
정확한 시간대를 스스로 찾아냈지만, Fine이 그 구간에서 실제 위반을 확인하지 못했다
(`NOT_OBSERVED`). 코드 버그가 아니라 **AI 탐지 자체의 miss**다. 대신 그 과정에서 실제
코드 버그 2건을 발견·수정했고, 이 영상은 **두 번째 negative Real E2E regression case**로
확보됐다.

## 사전 준비 / 환경 문제

- **ffmpeg 버전 문제 발견.** 이 PC의 PATH에 잡히는 ffmpeg는 anaconda3의 4.3.1인데,
  `LocalAnalysisMaterializer.materialize()`(`src/daesingo/recording/materialization.py`)가
  쓰는 `-fps_mode` 옵션은 ffmpeg 5.1+에서 옛 `-vsync`를 대체한 옵션이라 4.3.1엔 없다.
  → 재현: `Unrecognized option 'fps_mode'`. 이 PC에서는 **어떤 영상을 넣어도** Recording
  materialize 단계에서 막힌다는 뜻 — 영상 선택과 무관한 환경 gap.
  - `tests/case/test_real_video_pipeline.py` 상단 주석이 이미 "ffmpeg 빌드에 따라 결과가
    갈린다"고 경고해뒀던 바로 그 문제(6회차 때는 `static_ffmpeg`로 우회했었다).
  - **처리:** conda 환경은 건드리지 않고, ffmpeg 9.0.2 essentials 빌드(gyan.dev)를 세션
    스크래치패드에 받아 실행 시 PATH 맨 앞에만 얹었다. 레포·conda 어디에도 영구 반영 안 됨
    — **이 PC에서 이 계열 스크립트를 다시 돌리려면 매번 PATH에 최신 ffmpeg를 얹어야 한다**
    (6회차 문서가 이미 남긴 경고와 동일 패턴).

## 발견·수정한 실제 버그 2건

### 버그 1 — `progress[]`가 READY에서 무조건 DONE으로 덮어써서 미실행 단계를 숨김

`src/daesingo/case/view.py`의 `_build_progress()`가:

```python
if stage_rank == 4:  # READY
    progress = {s: "DONE" for s in _PROGRESS_STEPS}
```

바로 위 코드는 `evidence_record`/`report_package`/`requirement_report_evidence`가 실제로
있는지 보고 단계별 DONE/PENDING을 정교하게 계산하는데, `stage_rank==4`가 되는 순간 이
계산을 통째로 무시하고 8단계 전부를 DONE으로 덮어썼다. 그 결과 `scripts/dump_real_video_caseview.py`가
Fine의 `NOT_OBSERVED`로 `evidence`가 `null`인 채 `case.mark_ready()`를 부르면,
`evidence_assembly`/`requirement_check`/`package_assembly`가 실행된 적도 없는데 CaseView엔
DONE으로 찍혔다.

**왜 지금까지 안 드러났나:** `tests/case/test_real_video_pipeline.py`를 포함한 기존
fixture 시나리오는 전부 "READY면 evidence가 이미 있다"는 상태만 다뤘다 — READY + evidence
없음(오늘 이 영상의 NOT_OBSERVED) 조합이 실제 코드 경로를 탄 건 이번이 처음이었다.

**수정:** `case.stage == "EVIDENCE_REVIEW" and evidence_record is None`일 때 이미 있던
같은 패턴(§315 기존 규칙 — "밟을 계획이 없는 step은 목록에서 아예 뺀다")을 `READY`에도
동일 적용 — `case.stage == "READY" and evidence_record is None`이면 `file_intake`/
`coarse_search`/`candidate_review` 3단계만 DONE으로 싣고 나머지는 배열에서 뺀다.

**검증:** `pytest tests/case -q` — 96 passed (fix 전 2 failed는 ffmpeg 환경 문제였고, 환경
고친 뒤엔 fix 여부와 무관하게 통과 — fix 자체가 기존 fixture 경로를 깨지 않는다는 건
전체 스위트 재통과로 확인).

### 버그 2 — `target_event_types`가 "월요일 대표 영상" 값으로 하드코딩되어 있었음

`src/daesingo/case/real_e2e.py`:

```python
_MONDAY_TARGET_EVENT_TYPES = ["SOLID_LINE_LANE_CHANGE"]
```

`prepare_real_video_context()`가 이 값을 그대로 써서, `dump_real_video_caseview.py`로 어떤
영상을 넣든 Coarse/Fine에게 "백색 실선 진로변경만 찾아라"고 시키고 있었다. 이 영상의 실제
위반(중앙선 침범)은 애초에 찾아보라는 지시 자체를 받지 못했다 — 그래서 최초 실행에서
Coarse가 엉뚱한 진로변경 후보를 찾아왔던 것이다.

**이게 의도된 설계인지 확인함.** `src/daesingo/case/scope.py` 자체 docstring(§"1차 구현
범위")이 이미 명시하고 있다 — *"target_event_types는 이 모듈이 스스로 판단해서 만들어내지
않는다 — case 내부 어디에도 아직 어떤 이벤트 유형으로 검색할지 결정하는 로직이 없다(intake
시점 UI 흐름이 아직 범위 밖). 그래서 이 값들은 호출자가 그대로 공급한다."* 즉 하드코딩은
architecture가 요구하는 게 아니라, "월요일 대표 영상 1건"짜리 스모크 테스트용 임시값(변수명
자체가 `_MONDAY_...`)이 다른 호출자에게도 새 나간 것 — 영구히 유지할 이유가 없었다.

**수정:** `prepare_real_video_context()`/`build_real_video_evidence_bundle()`/
`RealVideoAdapter.__init__()`에 `target_event_types` 매개변수를 추가하고(생략 시 기존
`_MONDAY_TARGET_EVENT_TYPES`로 fallback — 기존 호출자 하위호환 유지),
`scripts/dump_real_video_caseview.py`에 `--target-event-types`(쉼표구분) CLI 옵션을 추가했다.

**검증:** `pytest tests/case -q` — 96 passed (기존 `test_real_video_pipeline.py`는 매개변수
생략 경로를 쓰므로 그대로 통과).

## 실행 이력 (오늘, `YT_0002_C00.mp4`)

| 회차 | 조건 | 결과 |
| --- | --- | --- |
| 1 | ffmpeg 4.3.1(구버전) | ❌ `RecordingCapabilityError` — 환경 문제로 Recording materialize 단계 진입도 못함 |
| 2 | ffmpeg 9.0.2로 교체, `target_event_types` 기본값(`SOLID_LINE_LANE_CHANGE`), 버그 1 수정 전 | ✅ 실행은 성공, `stage=READY`·`candidates=1`이지만 `evidence`/`package` 전부 `null`인데 `progress`는 8단계 전부 DONE으로 찍힘(버그 1) — Coarse가 엉뚱한 진로변경 후보를 찾음 |
| 3 | 버그 1 수정 후 재실행(같은 target_event_types) | ✅ `progress`가 정직하게 3단계만 DONE으로 표시됨(버그 1 수정 확인). disposition 진단 추가 — `decision=NOT_ASSEMBLED, verification=NOT_OBSERVED`. 이때 target_event_types 하드코딩 문제(버그 2) 발견 |
| 4 | 버그 2 수정 후 `--target-event-types CENTER_LINE_CROSSING`으로 재실행 | ✅ **Coarse가 `start_ms=9500 end_ms=14500`(9.5~14.5초)로 정확히 사용자가 지목한 11~14초 구간을 짚음.** 그러나 **Fine 최종 판정은 여전히 `NOT_OBSERVED`.** |

**4회차가 이번 세션의 최종 결과다.** 이후 진단(span/uncertainties/visual_evidence 전체
필드)을 위해 같은 조건으로 2회 더 재실행했고 — 매번 같은 구간(9.5~14.5초), 같은
`NOT_OBSERVED` — 재현성 확인됨. 오늘 이 영상에 대한 유료 Coarse+Fine 호출은 총 4쌍.
비용은 이전 회차들과 마찬가지로 로그 기준 사실상 $0 수준으로 추정되나, 이 스크립트가
공용 `real-e2e-usage-log.jsonl`에 자동 기록되지 않아(`SearchLedger` writer 미연결 — 알려진
gap, 이번엔 고치지 않음) 정확한 토큰/latency 숫자는 남기지 못했다.

### Fine이 실제로 본 것 (4회차, 최종)

```
verification: NOT_OBSERVED
target: track_ref=white_sedan_ahead, association_confidence=0.95
primitives:
  lateral_movement            PRESENT  (0.95)
  crossing_dashed_lane_line   PRESENT  (0.92)
  crossing_solid_lane_line    ABSENT   (0.90)
uncertainties: []
```

Fine이 짚은 대상은 **본 차량(ego)이 아니라 전방의 다른 흰색 승용차**이고, 그 차량이 넘은
것도 **점선(dashed)이지 실선/중앙선이 아니라고(`crossing_solid_lane_line: ABSENT`)** 명시적으로
판정했다. temporal_facts(원문 한국어, 터미널 콘솔 인코딩 문제로 원문 자체는 유실 — 구조는
보존됨)는 "전방에 흰색 차량 발견 → 2차로에서 1차로로 변경 시작 → 점선 구간을 넘어감 →
1차로 변경 완료"라는 시간 순서였다. 즉 **사용자가 짚은 "본 차량의 중앙선 침범 후 좌회전"은
이번 Fine 판정에서 확인되지 않았다** — 앞차의 정상적인(점선·방향지시등) 진로변경으로 판정됨.

**원인은 확인되지 않았다(추정만 가능, 검증 안 함):**
1. 앞차(흰색 세단)가 프레임을 크게 가려서 본 차량 자체의 중앙선 관계가 덜 두드러졌을 가능성
2. Coarse가 잡은 9.5~14.5초가 사용자가 말한 11~14초와 겹치지만 정확히 일치하진 않아, 실제
   침범 순간이 이 구간 경계 밖(또는 안이지만 Fine이 주목 못한 지점)에 있었을 가능성
3. 480p로 다운스케일된 분석용 영상이라 중앙선을 넘는 순간의 디테일이 소실됐을 가능성

이 셋 중 어느 것도 이번 세션에서 검증하지 않았다 — 다음 시도에서 확인이 필요하면 별도
조사가 있어야 한다.

## PM 프로토콜(`doc/real-e2e-protocol.md`, 로컬 전용) 10번 — 성공 기준 체크리스트

```
[x] 실제 영상 파일 등록
[x] ffprobe/ffmpeg 실제 실행                — 환경 fix 후(세션 로컬 ffmpeg 9.0.2)
[x] AnalysisSource 실제 생성
[x] Elice ML API Coarse 실제 호출           — gemini-3.8-flash 추정(모델명 미기록, 아래 참고)
[x] Candidate 실제 생성 (1건)               — 9.5~14.5초, 사용자 지목 구간과 겹침
[x] Elice ML API Fine 실제 호출             — 실제 응답 수신, 구조화 근거 포함
[x] VisualEvidence 실제 생성                — verification=NOT_OBSERVED
[ ] IncidentClip 실제 생성                  — NOT_OBSERVED라 설계상 스킵(정상)
[ ] Recording 실제 frame 추출               — 〃
[ ] PaddleOCR 실제 실행                     — 〃
[ ] 번호판 Readout 생성                     — 〃
[ ] Overlay time Readout 생성               — 〃
[ ] 실제 TimeSourceCandidate 연결           — 〃
[ ] TimeResolution 생성                     — 〃
[ ] EvidenceRecord 생성                     — NOT_OBSERVED라 정상적으로 안 만들어짐(정상 결말)
[ ] Requirement 평가                        — 〃
[x] CaseView 생성                           — `data/real/case/real_e2e_yt0002.json`(READY,
                                                candidates=1, evidence=null — 정직하게 표시됨)
[ ] Web에서 Real CaseView 렌더              — 안 함(이번 세션 범위 밖)
[ ] UI 육안 확인                            — 안 함
[ ] UI 스크린샷 저장                        — 안 함
```

**모델명·latency·token usage를 이 문서에 정확히 남기지 못한 것은 gap이다** — 진단 출력에
`decision`/`verification`/`primitives`/`temporal_facts`는 담았지만 `fine_run`(`AnalysisRun`,
모델명·latency·usage_refs 포함)은 이번 스크립트 수정에서 로그로 빼지 않았다. 다음 실행 때
`scripts/dump_real_video_caseview.py`가 `bundle.fine_run`도 같이 남기도록 보완하면 좋겠다.

## 결론

- **Negative Real E2E는 이번에도 안전하게 처리됨** — `NOT_OBSERVED`가 예외 없이 정상
  종료했고, 이 영상은 `20260620_141956_EVT_1`에 이은 **두 번째 negative regression case**로
  쓸 수 있다.
- **Positive Real E2E는 여전히 미완료.** 실제 위반이 찍힌 영상(팀 확인)을, 정확한 시간대를
  찾아서(파이프라인 정상 동작) 넣었는데도 AI가 위반을 확인하지 못했다 — PM이 요구한
  "실제 OBSERVED → CaseView → Web 렌더 → 스크린샷" 기준을 이번 영상으로는 만족시키지 못했다.
- 코드 버그 2건(progress 허위 DONE, target_event_types 하드코딩)은 실제 배선 문제였고
  수정·검증(전체 테스트 96 passed) 완료 — 다음 시도부터는 최소한 "엉뚱한 이벤트 타입을
  찾고 있었다"는 원인은 배제된 상태에서 재시도할 수 있다.
- 다음 후보: (1) 같은 영상을 더 좁은 구간으로 재시도, (2) 별도로 받은 2번 영상(백색 실선
  진로변경, 화질 낮음)으로 시도, (3) 이번 miss를 PM에게 그대로 보고하고 판단을 구한다 —
  세 옵션 다 이번 세션에서 결정되지 않았다.

## 변경된 파일

- `src/daesingo/case/view.py` — `_build_progress()`: READY + evidence 없음 분기 추가
- `src/daesingo/case/real_e2e.py` — `prepare_real_video_context()`/
  `build_real_video_evidence_bundle()`에 `target_event_types` 매개변수 추가
- `src/daesingo/case/adapters.py` — `RealVideoAdapter.__init__()`에 `target_event_types` 매개변수 추가
- `scripts/dump_real_video_caseview.py` — `--target-event-types` CLI 옵션 + disposition/span
  진단 출력 추가
- `data/real/case/real_e2e_yt0002.json` — 이번 4회차 실행 산출물(CaseView, evidence=null)
