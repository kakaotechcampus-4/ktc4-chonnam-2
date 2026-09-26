# G5 Recording Baseline bundle v1

`examples/recording_baseline.py`는 기존 `recording_benchmark.run_benchmark()`를 순차 반복한다.
각 실행은 독립 RecordingService를 사용한다. 기존 `recording-benchmark/v1` 결과를 바꾸거나
media 처리 코드를 복제하지 않는다. Canonical Contract/API에는 변경이 없다.

## 실행 입력과 익명 identity

실제 경로는 positional video 또는 `DAESINGO_RECORDING_VIDEO`로 전달한다.
dataset_id에는 원본 이름 대신 별도로 발급한 `ds_` + UUID hex를 전달한다.
경로·파일명·사람 이름을 ID로 사용하는 것을 막기 위해 자유 문자열은 허용하지 않는다.
한 dataset의 반복/후속 비교에는 같은 ID를 쓰고, 입력 파일 확인은 fingerprint로 한다.
ID와 실제 경로의 대응표는 bundle 밖에서 관리한다.

PowerShell, 프로젝트 루트 Python 3.12 환경:

```powershell
# 한 번 생성한 ID를 이후 동일 dataset 비교에도 사용한다.
$datasetId = 'ds_' + [guid]::NewGuid().ToString('N')
$env:DAESINGO_RECORDING_VIDEO='C:\normal\20260620_141956_EVT_1.avi'
.venv/Scripts/python.exe examples/recording_baseline.py --dataset-id $datasetId --output C:\normal\baseline-bundles\trial-001 --repeats 3 --video-index 0 --start 1 --end 2
```

동일 dataset ID·VIDEO 순번·구간·설정으로 다시 실행할 때는 새 output 디렉터리를 쓴다.
기존 디렉터리에는 쓰지 않고 OUTPUT_EXISTS로 거부한다. 입력 영상을 복사하지 않는다.
output 디렉터리 이름/전체 경로도 JSON에 넣지 않는다. stdout에는 bundle manifest가 출력된다.
영상과 generated bundle은 Git 밖에 보관하고, 팀이 검토한 익명 JSON만 별도로 공유한다.

## Bundle 구조

```text
trial-001/
├─ bundle.json
└─ runs/
   ├─ 0001.json    recording-benchmark/v1 원본 실행 결과
   ├─ 0002.json
   └─ 0003.json
```

| bundle.json 필드 | 내용 |
| --- | --- |
| schema_version | recording-baseline/v1 — Benchmark 전용, Canonical 계약 아님 |
| bundle_id | 무작위 실행 묶음 ID |
| status | FROZEN 또는 INCOMPLETE |
| freeze_checks | 반복 완료, 사용 가능 결과, 원본 불변, fingerprint/설정/버전/기술 metadata 동일성 |
| dataset | 익명 dataset_id, SHA-256·byte_size·mtime_ns, 기술 metadata |
| execution | 요청/완료 반복 수, 설정, requested_range, service_lifetime, warmup_runs |
| tools | 첫 실행의 ffmpeg/ffprobe/Python 버전 |
| runs[] | 순번·고정 상대 JSON 경로·JSON 파일 SHA-256·실행 status |
| summary | 실행 상태별 개수, 단계별 시간 min/median/max/count, 총 실행시간 통계 |

기술 metadata는 기존 공개 Benchmark가 제공하는 원본 byte_size·duration_sec·VIDEO 개수다.
파생 영상 설정(height/codec 등), 크기·실제 범위·duration은 각 raw report에 보존한다.
원본 codec/해상도 같은 추가 metadata를 얻으려고 별도 ffprobe 경로를 만들지 않는다.
bundle의 dataset/settings/tools는 첫 실행 기준이다. 불일치 시 freeze_checks가 false이고
각 실행의 실제 값은 원본 JSON에 그대로 있으므로 첫 값을 모든 실행의 사실로 해석하지 않는다.

## 동결 및 실패 의미

모든 요청 반복을 마치고 각 실행이 SUCCESS/FALLBACK이며, 전후 원본이 같고,
반복 사이 fingerprint(크기·mtime 포함)·설정·요청 범위·버전·기술 metadata가 모두 같을 때만 FROZEN이다.
신뢰된 절대시각 anchor가 없는 relative-only FALLBACK도 동결 가능한 정상 기준선이다.
버전을 숫자로 파싱하지 못한 unparsed 결과는 동결하지 않는다.

실패 실행은 삭제하지 않는다. 입력 조사/원본 불변 검사가 실패하면 추가 반복을 중단하고
이미 생성한 report를 보존한다. 다른 capability 실패도 bundle에 포함하지만 상태는 INCOMPLETE다.
raw 결과를 억지로 SUCCESS로 만들거나 값을 보정하지 않는다.
FROZEN은 종료 코드 0, INCOMPLETE 또는 입력/저장 오류는 1이다.

manifest는 모든 run JSON 저장 후 마지막에 발행한다. 중단/쓰기 오류가 나면 일부 run 파일이나
bundle.pending.json이 남을 수 있으며 bundle.json이 없는 디렉터리는 동결 결과가 아니다.
복구 시 원본 디렉터리를 덮지 말고 새 output을 사용한다. 기존 파일 자동 삭제/정리는 하지 않는다.
JSON 파일 hash는 전달 중 변경 확인용이며 전자서명이나 파일시스템 쓰기 방지는 아니다.

## 통계 해석

- 단계별 elapsed_sec는 SUCCESS/FALLBACK만 합산한다.
- FAILED 시간은 failed_elapsed_sec로 분리하고 상태별 개수를 함께 기록한다.
- SKIPPED는 표본에서 제외한다. 유효 표본 0개이면 min/median/max는 null이다.
- total_elapsed_sec는 실패를 포함한 모든 완료된 단일 실행의 시간이다.
- 단위는 초이며 perf_counter 기반이다. 첫 실행을 제외하지 않는다(warmup_runs=0).
- 매회 fresh service지만 OS 파일 캐시/encoder warm-up 상태까지 초기화하는 cold benchmark는 아니다.

## 자동/실제 검증

```powershell
.venv/Scripts/python.exe -m pytest tests/recording/test_recording_baseline.py tests/recording/test_recording_benchmark.py -q -p no:cacheprovider

$env:DAESINGO_RECORDING_VIDEO='C:\normal\20260620_141956_EVT_1.avi'
$env:DAESINGO_RECORDING_VIDEO_INDEX='0'
.venv/Scripts/python.exe -m pytest tests/recording/test_recording_baseline.py -k opt_in -q -s -p no:cacheprovider
```

합성 영상 테스트는 48p 시험 설정, 실제 opt-in은 기존 480p 설정으로 1–2초 구간을 두 번 실행한다.
원본 JSON 보존/hash·통계·ID/경로 비노출·덮어쓰기 방지·설정/버전/입력 drift·실패 보존·원본 변경 중단을 검사한다.
실제 검증의 output은 pytest 임시 디렉터리다. 장기 보관용 bundle은 위 CLI로 별도 생성한다.

## 남은 범위

W7 cache/TTL/retention, proxy 최적화, stitching, JobExecution 측정, CI 수정은 하지 않는다.
RSS/peak temporary disk/host 사양·도구 build fingerprint·동시성·성능 회귀 기준도 후속이다.
이번 기능은 동결 도구이며 팀의 최종 dataset 선정/기준선 승인, 장기 보관과 이전 baseline 비교는 별도다.
