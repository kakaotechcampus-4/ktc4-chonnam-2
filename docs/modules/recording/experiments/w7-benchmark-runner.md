# W7 Recording Benchmark 실행기 v1

## 분리 범위 실행 v2

기존 `--start/--end`는 동일 범위를 사용하는 smoke/micro baseline으로 유지하며
`recording-benchmark/v1`을 그대로 출력한다. 기존 FROZEN bundle을 변환/수정하지 않는다.
실제 흐름에 가까운 넓은 분석/좁은 incident 측정은 네 범위를 모두 명시한다.

```powershell
$env:DAESINGO_RECORDING_VIDEO='C:\normal\20260620_141956_EVT_1.avi'
.venv/Scripts/python.exe examples/recording_benchmark.py --video-index 0 --analysis-start 0 --analysis-end 10 --incident-start 1 --incident-end 2
```

이 모드는 `recording-benchmark/v2`를 출력한다.

| v1 | v2 |
| --- | --- |
| requested_range | requested_ranges.analysis / requested_ranges.incident |
| results.resolution | results.resolutions.analysis / results.resolutions.incident |
| resolve_span 시간 | resolve_analysis_span / resolve_incident_span 시간 |
| 공통 span 사용 | AnalysisSource는 analysis span, IncidentClip·Frame은 incident span |

`context`와 각 resolution에 같은 timeline_ref/revision 및 media_stream_ref를 기록한다.
두 해소를 모두 수행하여 각각 COMPLETE/PARTIAL/FAILED를 기록한다. 반환된 resolution 없이
capability 자체가 예외를 내면 해당 stage.failure만 기록하고 가짜 resolution을 만들지 않는다.
한쪽이라도 usable 단일 span이 없으면 두 해소 결과까지 보존하고 materialization은 SKIPPED다.
PARTIAL은 기존처럼 실제 해소된 span으로 진행하며 요청 범위와 missing_ranges를 보존한다.
예상 오류 코드와 원본 최종 검사는 기존과 같다.

단일/분리 범위 혼용, 일부만 지정, 잘못된 숫자·순서는 INVALID_INPUT이다.
incident가 analysis에 포함되는지를 새로운 계약 정책으로 강제하지는 않는다.
Candidate 자동 선택은 없으며 실행자가 incident 범위를 지정한다.

아래는 기존 v1 단일 범위 설명이다.

G5의 실행별 JSON·도구 버전·fingerprint·단계별 시간·실패 위치·비노출과
G6의 합성 media/정상·relative-only·경계·손상 입력 검증을 위한 첫 기능 단위다.
실행기는 `examples/recording_benchmark.py`이며 기존 Recording public capability만 호출한다.
Canonical Contract, public API, profile registry를 추가/변경하지 않는다.

## 실행

루트 Python 3.12 환경과 ffmpeg/ffprobe가 필요하다. 원본 경로는 실행 입력에만 사용한다.
VIDEO index는 audio를 제외한 VIDEO 목록의 0 기반 순번으로 실행자가 명시한다.

```powershell
$env:DAESINGO_RECORDING_VIDEO='C:\normal\20260620_141956_EVT_1.avi'
.venv/Scripts/python.exe examples/recording_benchmark.py --video-index 0 --start 1 --end 2
```

직접 경로를 positional argument로 전달할 수도 있다. stdout은 JSON report만 출력한다.
저장 시 stdout을 원본과 다른 `.json` 파일로 리다이렉트한다. 원본은 복사하거나 변경하지 않는다.
실제 영상 자동 검증은 다음처럼 opt-in한다.

```powershell
$env:DAESINGO_RECORDING_VIDEO_INDEX='0'
.venv/Scripts/python.exe -m pytest tests/recording/test_recording_benchmark.py -q -s -p no:cacheprovider
```

## Report 의미

schema_version은 Benchmark 자체의 `recording-benchmark/v1`이다.

| 필드 | 의미 |
| --- | --- |
| run_id | 무작위 실행 identity, 경로나 시각 미인코딩 |
| status | SUCCESS / FALLBACK / FAILED |
| failure | 최초 실패 stage와 code. 오류 메시지·stderr·명령줄은 제외 |
| stages[] | name/status/elapsed_sec/failure, fallback이면 reason 추가 |
| input_before/input_after | SHA-256, byte_size, mtime_ns |
| original_unchanged | 전후 비교 true/false. 조사 불가 시 null |
| tools | Python/ffmpeg/ffprobe 숫자 버전. vendor build 식별은 제외 |
| settings | 명시적 VIDEO index, encoding 시험 설정 |
| requested_range | Timeline 요청 범위 |
| results.resolution | 해소 상태, 실제 AssetSpan 범위, missing_ranges와 reason |
| results.analysis_source | 실제 읽은 byte_size/SHA-256, duration, 실제 timeline_range |
| results.incident_clip | producer가 측정한 byte_size/duration/timeline_range |
| results.frame | 요청/실제 source offset, 읽은 bytes 크기와 SHA-256 |
| total_elapsed_sec | 버전 조회·fingerprint·cleanup을 포함한 실행 총 시간 |

`register_probe`는 등록에 포함된 probe·fingerprint 시간을 합쳐 측정한다.
`analysis_source`는 준비·open·전체 stream 읽기/hash를 포함한다.
`incident_clip`은 생성·공개 조회, `frame`은 resolve_frame·read_frame을 포함한다.
입출력 fingerprint 검사는 별도 단계다. 시간은 perf_counter 경과시간이며 CPU time이 아니다.
필요한 span을 얻기 위해 resolve_span을 AnalysisSource 준비보다 먼저 실행한다.

신뢰된 anchor를 주입하지 않으므로 정상 단일 파일도 Timeline 단계가
`FALLBACK / RELATIVE_ONLY_NO_TRUSTED_ANCHOR`이며 전체 status는 FALLBACK이다.
실패가 없는 SUCCESS/FALLBACK은 종료 코드 0, FAILED는 1이다.
PARTIAL 해소는 사용 가능한 단일 span으로 계속 진행하고 missing_ranges를 보존한다.
해소할 span이 없거나 복수이면 resolve_span 단계 실패로 이후 단계는 SKIPPED다.
어떤 단계가 실패해도 최초 fingerprint가 있으면 마지막 원본 검사를 시도한다.
추가 원본 검사 실패는 original_integrity 단계에 남고 최초 실패를 덮지 않는다.

실행기 자체의 INVALID_INPUT/TOOL_TIMEOUT/ORIGINAL_CHANGED 등의 code는 진단용이다.
Canonical failure taxonomy에 추가하지 않는다. 알려진 capability code는 보존하고,
알 수 없는 예외·code는 고정된 안전한 code로 변환한다.
Report에는 basename·절대경로·시각 후보·픽셀·인증정보·환경변수 dump를 넣지 않는다.

## 검증 범위와 한계

- 합성 영상: 전체/부분 구간, relative-only, 경계 밖 PARTIAL, 해소 불가,
  손상 원본, 명시적 stream 검증, 실패 위치, timeout, 원본 변경 탐지, 비노출.
- 실제 영상: env opt-in이며 1–2초 요청을 기존 공개 capability로 실행한다.
- 기본 시험 설정은 480p H.264/veryfast/CRF23/yuv420p/faststart/audio off다.
  최종 Canonical profile이 아니다. 테스트는 처리비용을 줄이기 위해 48p로 실행한다.
- IncidentClip open API가 없으므로 clip bytes를 내부 저장소에서 직접 꺼내지 않는다.
- 원본 전체 hash와 단일 실행 비용을 포함한다. 반복 통계와 baseline bundle 동결은
  [Baseline 실행기](w7-baseline-bundle.md)를 사용한다. RSS·peak temp disk·동시성 측정은 아직 없다.
- JobExecution 시간, CI workflow, 외부 dataset manifest, 전후 개선 비교는 후속이다.
- cache/TTL/retention·proxy 최적화·stitching·복수 VIDEO 기본 선택·export는 이번 범위에 없다.
- 이 리포트는 처리·계약 경계 측정이며 탐지율·OCR·시각 정확도 성능 근거가 아니다.
