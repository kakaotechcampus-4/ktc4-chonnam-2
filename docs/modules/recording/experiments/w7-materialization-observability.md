# W7 materialization 내부 비용 관찰 v3

전후 비교 결과: [source inspection 재사용 v3 baseline 비교](w7-source-inspection-comparison.md).

목적은 [분리 범위 baseline](w7-baseline-negative-001.md)에서 크게 측정된 AnalysisSource와
IncidentClip의 비용을 분해하는 것이다. 최적화나 encoder/profile 변경을 하지 않는다.
LocalIncidentMaterializer가 재사용하는 LocalAnalysisMaterializer의 실제 실행 지점을 측정한다.
중복 ffprobe/ffmpeg 실행은 없으며 RecordingService public capability와 Canonical Contract는 그대로다.

## 실행과 버전

프로젝트 루트 Python 3.12 환경에서 실행한다. 영상 경로는 환경변수 또는 positional 인자로만 전달한다.

```powershell
$env:DAESINGO_RECORDING_VIDEO='C:\normal\20260620_141956_EVT_1.avi'
.venv/Scripts/python.exe examples/recording_benchmark.py --video-index 0 --analysis-start 0 --analysis-end 20.024656 --incident-start 1 --incident-end 2 --materialization-trace
```

반복 동결은 기존 익명 dataset ID와 새 output 디렉터리를 사용한다.

```powershell
.venv/Scripts/python.exe examples/recording_baseline.py --dataset-id ds_2818d7a1ad144c948f8000803b71c9f4 --output C:\normal\baseline-bundles\trace-001 --repeats 3 --video-index 0 --analysis-start 0 --analysis-end 20.024656 --incident-start 1 --incident-end 2 --materialization-trace
```

| 모드 | 단일 실행 | 반복 bundle |
| --- | --- | --- |
| trace 없음 + 단일 범위 | recording-benchmark/v1 | recording-baseline/v1 |
| trace 없음 + 분리 범위 | recording-benchmark/v2 | recording-baseline/v2 |
| --materialization-trace + 어느 범위 모드든 | recording-benchmark/v3 | recording-baseline/v3 |

기존 옵션의 결과에는 trace 필드를 추가하지 않는다. 기존 FROZEN bundle/raw JSON은 수정·변환하지 않는다.
v3도 단일 범위이면 requested_range, 분리 범위이면 requested_ranges를 유지하고
settings.materialization_trace=true를 추가해 동결 설정 비교에 포함한다.

## Phase 경계

| name | 실제 측정 범위 |
| --- | --- |
| source_snapshot | 원본 snapshot/hash와 등록 원본 불변 확인 |
| source_probe | source ffprobe 실행·JSON 파싱·frame coverage 조사 |
| frame_prepare | 출력 폭 계산·frame 선택·실제 시작/끝 계산 |
| encode | 기존 ffmpeg encode 호출 |
| output_probe | 출력 ffprobe 실행·JSON 파싱 |
| output_validate | 출력 frame coverage·codec/해상도/pixel format·frame 수·시각·duration 검증 |
| bytes_read | 출력 파일 read_bytes |
| bytes_validate | 빈 출력·MP4 box·faststart 검증 |
| source_verify | 변환 후 snapshot/hash와 원본 불변 확인 |

각 phase는 perf_counter 경과시간을 초로 기록한다. 생성/검증 순서와 기존 예외 변환,
TemporaryDirectory cleanup을 유지한다. read 비용과 검증 비용을 혼동하지 않도록 bytes_validate를 별도로 둔다.

## v3 schema 추가분

```text
materialization_trace
  analysis_source[]               실제 materialize 호출별 trace
  incident_clip[]
    status                        SUCCESS / FAILED
    failure                       null 또는 {phase, code}
    elapsed_sec                   전체 materialize 호출 경과시간
    phases[]
      name
      status                      SUCCESS / FAILED / SKIPPED
      elapsed_sec                 실행하지 않으면 null
      failure                     null 또는 {code}
```

두 공개 capability 호출을 독립적인 context-local collector로 감싼다. 엔진을 부르기 전에
실패하거나 엔진 호출이 없으면 배열은 비어 있으며, 측정하지 않은 phase 값을 만들지 않는다.
raw trace에는 고정 phase 이름·숫자·상태·허용된 code만 수집한다.
경로·파일명·명령 전체·stderr·예외 원문·인증정보는 수집하지 않는다.

내부 failure code는 관찰 전용이며 Canonical failure taxonomy 변경이 아니다.
예: encode TimeoutExpired는 trace에서 TOOL_TIMEOUT, 기존 공개 capability에서는
기존대로 TEMPORARY_FAILURE 또는 INCIDENT_CLIP_BUILD_FAILED가 될 수 있다.
phase 밖(profile 확인·작업공간 생성/정리 등)의 실패는 outside_phases로 기록한다.
실패 뒤 phase는 SKIPPED이며 원래 예외를 그대로 다시 발생시킨다.

v3 bundle의 `summary.materialization_trace.analysis_source/incident_clip`에는 invocation_count와
phase별 status_counts, elapsed_sec의 count/min/median/max, failed_elapsed_sec의 동일 통계를 기록한다.
SUCCESS 시간과 FAILED 시간을 섞지 않으며 SKIPPED는 0초 표본이 아니다.
기존 freeze_checks에 materialization_trace_complete를 추가하여 두 종류 모두 실행별
1회 성공 trace와 전 phase 성공이 확인돼야 FROZEN이 된다. raw JSON/hash 보존 규칙은 동일하다.

## 검증과 해석 한계

```powershell
.venv/Scripts/python.exe -m pytest tests/recording/test_materialization_observability.py tests/recording/test_recording_benchmark.py tests/recording/test_recording_baseline.py -q -p no:cacheprovider
$env:DAESINGO_RECORDING_VIDEO_INDEX='0'
.venv/Scripts/python.exe -m pytest tests/recording/test_materialization_observability.py -k opt_in -q -s -p no:cacheprovider
```

합성 영상으로 trace on/off 파생 bytes·metadata 동일성, 도구 호출 수 불변, 9개 phase 각각의
실패 주입, 공개 오류 동일성, 이후 phase 미실행, 임시 파일 정리, 비노출과 집계를 검사한다.
실제 opt-in은 analysis 0–20.024656초/incident 1–2초를 2회 실행하며 출력은 pytest 임시 디렉터리다.

trace 자체에도 clock/context 수집 오버헤드가 있다. phase 합은 전체 materialization 시간과
정확히 같지 않다(작업공간 생성·cleanup·반환 처리 등 포함 차이).
Benchmark 바깥 analysis_source 시간에는 Service 검증과 open/stream 읽기/hash 비용도 있어
내부 trace 합과 같지 않다. source_probe는 ffprobe와 coverage를 함께 측정하며 더 세분하지 않는다.
CPU time, RSS, I/O 대역폭, OS cache 초기화 또는 병목 원인을 확정하는 기능은 아니다.
cache/TTL/frame index 재사용·preset/proxy 최적화·stitching·JobExecution·CI는 후속 범위다.
