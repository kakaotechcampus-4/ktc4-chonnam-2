# 로컬 Runtime/Ops·Recording 실행환경

**Refs #460 · Related #429, #450, #452, #465, #468**

2026-10-30 KST, 코드 기준 `d66fab9c47b84d6391232c866a7e73c5ac6b8f6b`
(당시 최신 `origin/develop`). 팀원이 최근 PR을 추적하지 않고 로컬
Compose/API/Worker를 구성하기 위한 현재 실행환경 안내다. Notion 게시 가능한
저장소 원문이며 외부 게시를 수행한 문서는 아니다.

이 문서의 **코드 기본값**, **Owner 결정**, **측정값**, **테스트값**, **미확정**은
서로 대체하지 않는다. Runtime 정책의 원문은 [Provisional Baseline](./provisional-baseline-v0.1.md),
실행 구현은 현재 코드, 과거 검증은 각 Notes가 소유한다. 새 기본값이나 제품 계약을 정하지 않는다.

## 1. 지원 범위와 버전

| 항목 | 현재 구성·근거 | 검증 범위 |
| --- | --- | --- |
| Python | `pyproject.toml` 허용 `>=3.12`; 배포 Dockerfile은 digest 고정 `python:3.12-slim-bookworm` | Docker/Linux amd64 경로. 모든 Python 상위 버전 지원을 검증했다는 뜻은 아님 |
| uv | Docker build input `0.11.15`, digest 고정 | build stage만 설치; runtime image 안에는 uv 없음 |
| Python 설치 | `uv.lock`, `uv sync --locked --no-dev --extra eval-gemini --extra readout-paddle` | Search client 및 production OCR 포함. pytest는 runtime에 없음 |
| MySQL | Compose `mysql:8.4`, DB/user `daesingo` | 8.4 계열 태그이며 patch/digest 고정 아님; Notes의 8.4.13은 당시 관측값 |
| FFmpeg / ffprobe | **동일 build의 정확히 8.1** (#465 Owner 결정) | 공식 source checksum·고정 Debian snapshot으로 함께 build; `8.1 이상`이나 다른 배포판 binary 혼합 지원 아님 |
| PaddleOCR / PaddlePaddle / OpenCV | `3.7.0` / `3.3.1` / `opencv-contrib-python 4.10.0.84` | `readout-paddle` extra 및 startup 버전 검증; PaddleX lock은 `3.7.2` |
| OCR 모델 | `PP-OCRv5_mobile_det`, `korean_PP-OCRv5_mobile_rec` | #468 Readout Owner 확정 사전학습 모델, CPU, `enable_mkldnn=False`; 모델 artifact hash는 build별 manifest |
| 시스템 라이브러리 | Dockerfile의 media/font 라이브러리, `libgl1`, `libglib2.0-0`, `libgomp1` | Debian slim OCR import 및 기존 report drawtext에 필요 |

새 환경은 Linux container Compose를 우선 사용한다. Native API CLI는 있지만,
기본 Worker는 아래 고정 OCR cache까지 필요하므로 `uv sync`만으로 준비가 끝나지 않는다.
Windows native Paddle, Windows pinned 8.1, 비-amd64 Linux는 현재 Notes의 검증 범위 밖이다.
로컬 Compose는 API 1 + Worker 1 + migration one-shot + MySQL이며 Web은 포함하지 않는다.
EC2/OIDC/SSM·registry·production restart/alert·Worker heartbeat 노출·rollback은
[#450](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/450)의 미결 배포 범위다.

## 2. 설정 파일과 secret 소비 경계

| 이름 | 소비자·설정 위치 | 필수/기본값 | 용도·secret 여부 |
| --- | --- | --- | --- |
| `DAESINGO_RUNTIME_ENV_FILE` | Compose **호스트 shell** 보간 | Compose 필수, 기본 없음 | repo 밖 runtime 파일 경로. 컨테이너 `/run/secrets/runtime.env`에 read-only bind; 값 자체는 경로이고 내용은 secret 포함 |
| `DAESINGO_ENV_FILE` | API/Worker bootstrap의 **process env**, migrate adapter | API/Worker 미지정 시 `cwd/.env`; **migrate adapter는 명시 필수**; Compose는 `/run/secrets/runtime.env` 지정 | 앱이 읽을 파일 선택자. 앱 설정값을 shell에서 병합하는 스위치가 아님 |
| `DAESINGO_MYSQL_ROOT_PASSWORD_FILE` | Compose 호스트 shell → MySQL `/run/secrets/mysql-root-password` | Compose 필수 | root password 전용 파일 경로; 파일 내용 secret |
| `DAESINGO_MYSQL_PASSWORD_FILE` | Compose 호스트 shell → MySQL `/run/secrets/mysql-password` | Compose 필수 | app password 파일 경로; DB URL의 decoded password와 동일한 내용, secret |
| `MYSQL_ROOT_PASSWORD_FILE`, `MYSQL_PASSWORD_FILE` | MySQL container env, Compose가 지정 | 위 컨테이너 파일 경로 | MySQL 공식 `_FILE` 입력. 앱 env 파일 parser와 별개 |
| `DAESINGO_REVISION` | Compose build arg `REVISION` → image env | 선택, `local` | 비secret revision identity. API `--revision`에 전달; Worker 시작 로그는 현재 `unknown` |
| `DAESINGO_API_PORT` | Compose 호스트 shell | 선택, `8000` | 비secret. `127.0.0.1:<port>:8000`만 공개; MySQL host port 없음 |

`DAESINGO_RUNTIME_ENV_FILE`을 앱 파일 안에 넣어도 그 파일을 자동 선택하지 않는다.
Compose의 프로젝트 `.env` 보간과 앱의 `load_env_file()`은 별개다.
앱은 선택한 파일의 `KEY=VALUE`만 읽고 shell의 DB/API key 등을 병합하지 않는다.
이 parser는 shell 문법(`export`, 변수 치환, inline comment)을 처리하지 않는다.
값 뒤 주석은 별도 줄에 쓴다. Compose `env_file:`로 secret을 전달하지 않는다.

runtime 파일은 **비secret 설정과 앱 credential/DB URL을 함께** 담는다.
MySQL password 두 파일은 **password 원문만** 담으며 `KEY=VALUE` 파일이 아니다.
실제 key/URL/password/개인 절대경로를 문서·Git·argv·로그에 기록하지 않는다.
아래 `/media`, `/app`, `/opt`, `/run/secrets`는 이미지의 고정 경로다.

## 3. runtime 파일에 넣는 키

[`.env.example`](../../.env.example)을 repo 밖 보호 파일로 복사하고 빈 필수값을 채운다.
빈 값은 미완성 표시이며 그대로 부팅 가능한 preset이 아니다.
필수 그룹을 일부만 채우면 parser가 거부한다. 그룹 전체를 삭제해 부팅되더라도
capability가 빠질 수 있으므로 전체 기능 구성 확인은 §8을 따른다.

### 필수 Runtime 및 credential

| 실제 키 | 필수/기본값 | 용도 | Secret |
| --- | --- | --- | --- |
| `DAESINGO_RUNTIME_DB_URL` | API/Worker/migrate 필수, 없음 | `mysql+pymysql://daesingo:<url-encoded-password>@mysql/daesingo` 형태. host `mysql`은 Compose 내부 DNS | **예** |
| `DAESINGO_RUNTIME_MEDIA_ROOT` | API/Worker 필수, 없음 | Compose `/media`, 두 프로세스가 같은 durable 파일을 봄 | 아니오 |
| `DAESINGO_RUNTIME_API_TEMP_ROOT` | API 필수, 없음 | Compose `/media/api-temp` | 아니오 |
| `DAESINGO_RUNTIME_WORKER_TEMP_ROOT` | Worker 필수, 없음 | Compose `/media/worker-temp` | 아니오 |
| `GEMINI_API_KEY` | **현재 Worker bootstrap 필수**, 없음 | Search/Intent Bearer credential; API 자체 bootstrap은 요구하지 않음 | **예** |
| `ELICE_ML_API_KEY` | Search 공용/eval에서는 우선 이름, 없음 | 공용 `api_key_from_env()`는 ELICE→GEMINI alias 순. **Worker는 이 함수를 쓰지 않고 GEMINI만 읽음** | **예** |

migrate는 이 중 DB URL만 읽는다. URL password의 예약 문자는 URL encoding한다.
DB URL을 CLI 옵션에 직접 쓰지 않는다. 기존 DB가 있는 경우 migration 전 논리 backup과
schema 호환성 판단은 [backup/restore Notes](./rt13b-backup-restore.md)를 따른다.
이미 초기화된 MySQL volume의 password는 `_FILE` 교체만으로 변경된다고 가정하지 않는다.

### Recording: 명시적 encoding이 필요한 두 그룹

| 실제 키 | 필요 여부·코드 기본값 | 용도·허용값 | 대표값/secret |
| --- | --- | --- | --- |
| `DAESINGO_RECORDING_ANALYSIS_PROFILE_REF` | Analysis 4개 함께 필요, 없음 | 분석 profile 식별자(공백 아닌 문자열); height/preset/CRF와 함께 관리 | **미확정**, 비secret |
| `DAESINGO_RECORDING_ANALYSIS_HEIGHT` | 위 그룹, 없음 | 양의 짝수, 출력 높이 | **미확정**, 비secret |
| `DAESINGO_RECORDING_ANALYSIS_PRESET` | 위 그룹, 없음 | `ultrafast`, `superfast`, `veryfast`, `faster`, `fast`, `medium`, `slow` | **미확정**, 비secret |
| `DAESINGO_RECORDING_ANALYSIS_CRF` | 위 그룹, 없음 | 정수 `0..51` | **미확정**, 비secret |
| `DAESINGO_RECORDING_INCIDENT_HEIGHT` | Incident 3개 함께 필요, 없음 | 양의 짝수, 판독·신고 영상의 바탕인 IncidentClip 높이 | **미확정**, 비secret |
| `DAESINGO_RECORDING_INCIDENT_PRESET` | 위 그룹, 없음 | Analysis와 같은 preset 허용 집합 | **미확정**, 비secret |
| `DAESINGO_RECORDING_INCIDENT_CRF` | 위 그룹, 없음 | 정수 `0..51` | **미확정**, 비secret |
| `DAESINGO_RECORDING_FILENAME_OFFSET` | 선택, 없음 | 파일명 시각 관찰의 명시적 `±HH:MM`; 예 `+09:00`은 사용 파일의 실제 offset일 때만 선택 | 팀 대표값 미확정, 비secret |

근거: `recording/factory.py`, `materialization.AnalysisProfile`, `time_sources.py`.
현재 코드는 Analysis 그룹이 전부 없으면 `HINT_EXTRACT`만 Search registry에 남기고
`COARSE_SEARCH`·`FINE_VERIFY`를 등록하지 않는다. Incident 그룹이 없으면
`INCIDENT_CLIP_BUILD`가 빠진다. 일부 키 존재/빈 값은 startup 검증 실패다.
과거 #460 댓글의 “Coarse/Fine 등록 후 실행 실패” 설명을 현재 동작으로 복사하지 않는다.
`FILENAME_OFFSET`은 필수 encoding 키가 아니며 Readout 화면시각 timezone과 별개다.

**대표 profile 미확정**: [#460 임시 실행값](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/460#issuecomment-6495668489)의
Analysis `480 / veryfast / 23`, Incident `240 / veryfast / 23`은 운영 권장값이 아니다.
테스트에서 쓰는 작은 출력값도 품질·성능 합의가 아니다. Recording Owner가 Runtime 머신에서
분석 정확도/번호판·화면시각 가독성/신고 export 품질, 저장 bytes, 준비·처리시간을 함께 측정해
두 profile과 식별자를 정해야 한다. 그 전에는 사용자가 검증할 profile을 명시적으로 선택해야 한다.

### Search Coarse/Fine과 Intent

| 실제 키 | 필수/코드 기본값 | 용도·secret |
| --- | --- | --- |
| `DAESINGO_GEMINI_MODEL` | 선택, `gemini-4-argon` | Coarse/Fine, 비secret |
| `DAESINGO_GEMINI_BASE_URL` | 선택, `https://mlapi.run/e1febb2a-0530-4f93-9ff4-ef844e185639/v1` | argon tenant, 비secret |
| `DAESINGO_GEMINI_MEDIA_RESOLUTION` | 선택, `low` | Search media 설정, 비secret |
| `DAESINGO_INTENT_MODEL` | 선택, `gemini-3.8-flash` | `HINT_EXTRACT` 전용, 비secret |
| `DAESINGO_INTENT_BASE_URL` | 선택, `https://mlapi.run/a90d8545-f100-4276-bf86-eb774596b91d/v1` | Flash tenant, 비secret |
| `DAESINGO_GEMINI_INPUT_USD_PER_MILLION` | 선택, `0.0` | 입력 단가 설정, 비secret; 실단가로 확정한 값 아님 |
| `DAESINGO_GEMINI_OUTPUT_USD_PER_MILLION` | 선택, `0.0` | 출력 단가 설정, 비secret |
| `DAESINGO_GEMINI_MAX_COST_USD` | 선택, `0.0` | 비용 한도 설정, 비secret; 운영 예산 추천 아님 |

모델·경로는 [Search Owner 결정](../modules/search/decisions/search-argon-model-2026-10-27.md)과
`search/config.py`, `search/intent.py`의 현재 값이다. override하지 않으려면 키를 **생략/주석**으로 둔다.
Search에 빈 문자열을 넣으면 기본값 복구가 아니므로 주의한다(Intent는 빈 값을 fallback 처리).
과거 Flash model/base URL을 함께 제거하거나 위 argon 쌍으로 함께 교체한다.
Intent에는 argon 경로를 복사하지 않는다. [#429 확인 댓글](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/429#issuecomment-6495668950)은
새 runtime 파일에서 Search argon/Intent Flash 사용량 기록을 관측했다. 이는 개인/시연 PC의 적용 증거가 아니다.
실제 Run의 `config_version=gemini-search-v4`, 모델 및 `usage_record.provider_label`로 확인한다.
startup `process.started`만으로 모델 적용을 증명할 수 없다.

## 4. 선택 Runtime 키 전체 목록

아래는 `common/config/__init__.py`의 **코드 기본값**이다. 모두 비secret이며 생략 가능하다.
값의 정책 근거·잠정성은 Baseline 원문을 따른다. 단위는 이름에 표시한 초/bytes다.
서비스가 소비하지 않는 다른 서비스 키는 공유 파일에 있어도 허용된다.

| 실제 키 | 소비 서비스 | 기본값 | 용도 |
| --- | --- | --- | --- |
| `DAESINGO_RUNTIME_LOG_LEVEL` | API/Worker | `INFO` | DEBUG/INFO/WARNING/ERROR/CRITICAL |
| `DAESINGO_RUNTIME_DB_POOL_SIZE` | API/Worker | API `5`, Worker `2` | 일반 DB pool |
| `DAESINGO_RUNTIME_DB_MAX_OVERFLOW` | API/Worker | API `5`, Worker `2` | pool 추가 연결 |
| `DAESINGO_RUNTIME_DB_LOCK_WAIT_TIMEOUT_SEC` | API/Worker | `5` | DB lock 대기 |
| `DAESINGO_RUNTIME_DB_POOL_TIMEOUT_SEC` | API/Worker | `5` | pool 대기 |
| `DAESINGO_RUNTIME_DB_POOL_RECYCLE_SEC` | API/Worker | `1800` | 연결 재활용 |
| `DAESINGO_RUNTIME_DB_CONNECT_TIMEOUT_SEC` | API/Worker | `5` | 연결 timeout |
| `DAESINGO_RUNTIME_DB_READ_TIMEOUT_SEC` | API/Worker | `30` | 읽기 timeout |
| `DAESINGO_RUNTIME_DB_WRITE_TIMEOUT_SEC` | API/Worker | `30` | 쓰기 timeout |
| `DAESINGO_RUNTIME_HEARTBEAT_DB_CONNECT_TIMEOUT_SEC` | Worker | `2` | heartbeat 별도 연결 |
| `DAESINGO_RUNTIME_HEARTBEAT_DB_READ_TIMEOUT_SEC` | Worker | `5` | heartbeat 읽기 |
| `DAESINGO_RUNTIME_HEARTBEAT_DB_WRITE_TIMEOUT_SEC` | Worker | `5` | heartbeat 쓰기 |
| `DAESINGO_RUNTIME_WORKER_IDLE_POLL_SEC` | Worker | `2` | idle poll |
| `DAESINGO_RUNTIME_WORKER_ERROR_BACKOFF_SEC` | Worker | `5` | 오류 뒤 대기 |
| `DAESINGO_RUNTIME_HEARTBEAT_INTERVAL_SEC` | Worker | `10` | heartbeat 주기 |
| `DAESINGO_RUNTIME_LEASE_DURATION_SEC` | Worker | `60` | execution lease |
| `DAESINGO_RUNTIME_STALE_SWEEP_INTERVAL_SEC` | Worker | `15` | STALE scan |
| `DAESINGO_RUNTIME_STALE_RETRY_MAX` | Worker | `1` | STALE 재시도 수 |
| `DAESINGO_RUNTIME_STALE_RETRY_BACKOFF_BASE_SEC` | Worker | `5` | 재시도 backoff 시작 |
| `DAESINGO_RUNTIME_BACKOFF_MAX_SEC` | Worker | `60` | 재시도 backoff 상한(이 이름이 실제 키) |
| `DAESINGO_RUNTIME_API_UPLOAD_MAX_BYTES` | API | `1073741824` | upload 상한 |
| `DAESINGO_RUNTIME_API_JSON_MAX_BYTES` | API | `1048576` | JSON body 상한 |
| `DAESINGO_RUNTIME_API_UPLOAD_IDLE_TIMEOUT_SEC` | API | `60` | upload idle |
| `DAESINGO_RUNTIME_API_UPLOAD_MAX_DURATION_SEC` | API | `1800` | upload 전체 시간 |
| `DAESINGO_RUNTIME_API_FRAME_MAX_AGE_SEC` | API | `3600` | frame cache max-age |
| `DAESINGO_RUNTIME_API_FRAME_CONCURRENCY` | API | `2` | frame 생성 동시성 |
| `DAESINGO_RUNTIME_CLEANUP_TEMP_AGE_SEC` | API/Worker | `3600` | 오래된 소유 temp |
| `DAESINGO_RUNTIME_CLEANUP_INTERVAL_SEC` | API/Worker | `3600` | cleanup 주기 |
| `DAESINGO_RUNTIME_CLEANUP_STAGING_AGE_SEC` | API | `3600` | 오래된 upload staging; Worker는 소비 안 함 |
| `DAESINGO_RUNTIME_CLEANUP_ORPHAN_AGE_SEC` | API config | `86400` | 현재 orphan publish 삭제 미구현; 설정 수용과 삭제 실행을 구분 |
| `DAESINGO_RUNTIME_READY_DB_TIMEOUT_SEC` | API | `2` | readiness DB probe |
| `DAESINGO_RUNTIME_READY_STORAGE_TIMEOUT_SEC` | API | `1` | readiness storage probe |

제약: Worker lease > heartbeat 주기, 일반 DB lock wait < heartbeat 주기,
heartbeat DB의 고정 lock wait `2` < read timeout. API staging age >= upload 최대 시간의 2배,
ready DB+storage timeout <= 고정 전체 budget `3`초. `pool_pre_ping=True`, heartbeat lock wait,
ready budget에는 별도 env key가 없다. Case는 별도 env/config 없음
([Case Owner 확인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/460#issuecomment-6498226226)).
`DAESINGO_EVAL_DATA_ROOT`, `DAESINGO_EVAL_PRIVATE_ROOT`는 eval 전용 선택 경로로 Runtime 필수 설정이 아니다.

## 5. media·temp·cleanup 경계

Compose의 같은 named volume `/media`를 API/Worker가 공유한다. 이미지가 UID/GID
`10001:10001`, mode `0750`으로 `/media`, `/media/api-temp`, `/media/worker-temp`를 준비한다.
빈 volume copy-up 경로 기준이며 기존 잘못된 권한의 volume을 자동 보정하지 않는다.

| 위치 | 용도·삭제 경계 |
| --- | --- |
| `/media/source` | durable publish 원본/asset. temp cleanup 대상으로 지정할 수 없음; retention/purge 아님 |
| `/media/staging` | API streaming upload; API cleanup만 담당 |
| `/media/api-temp` | API Frame/미디어 작업 temp; API cleanup |
| `/media/worker-temp` | Worker AnalysisSource/IncidentClip/export 미디어 작업 temp; Worker cleanup |
| Python 기본 `/tmp` | 별도 spool 등 시스템 temp, Compose tmpfs 없음. Runtime temp scanner가 전부 청소하는 곳 아님 |

cleanup은 startup scan 후 완료 시점부터 interval을 기다린다. 허용된 소유 prefix/형식과
age보다 오래된 항목만 대상으로 하고 활성 upload/reader/materializer는 filesystem lease로 보호한다.
publish·원본·모델 cache·다른 서비스 temp를 임의로 지우지 않는다. orphan age가 설정돼도
DB 등록 조회·orphan publish 삭제·제품 retention은 구현 완료가 아니다.
자세한 lease/경로 pinning/종료 join은 [cleanup Notes](./rt12a-cleanup.md)와 현재
`common/storage/cleanup.py`, `media.py`를 따른다. Native 경로는 배포자가 먼저 준비해야 하며
Windows의 특수 Volume GUID 경로 대신 도구가 읽을 수 있는 일반 경로를 확인한다.

입력은 API upload와 공개 Recording registration/timeline을 통해 등록한다. 원본 불변,
소유권·VIDEO stream·실제 frame coverage·gap/overlap·decode 검증을 만족해야 한다.
시간/stream/timeline을 env로 만들어내지 않는다. 여러 원본의 지원 조건은
[multi-span AnalysisSource](../modules/recording/multi-span-analysis-source.md)와
[실영상 경계](../modules/recording/real-video-edge-cases.md)를 따른다.

## 6. production Readout과 offline startup

현재 기본 `python -m daesingo.worker`는 `production_readout_factory()`를 호출한다.
dependency 정확한 버전 → `models.json`과 모델 artifact SHA-256/읽기 권한 → 엔진 로드/예열을
**loop/claim 전에** 검증하고 `recording_ocr_factory()`를 조립한다. 실패하면 exit 1과
기존 `runtime.worker.failed` 경계로 종료한다. 모델명/env enable flag를 새로 지정할 필요 없다.
낮은 계층의 `compose_registry(..., readout_provider_factory=None)`는 여전히 Readout 미등록이다.
테스트 injection과 기본 production main의 의미를 혼동하지 않는다.

| 항목 | 현재 동작 |
| --- | --- |
| cache | **고정** `/opt/daesingo/paddlex/official_models/<model>/`; `models.json`은 cache root |
| 공급 | image `readout-build` stage에서 두 모델 사전 다운로드, inference artifact와 manifest만 runtime에 복사 |
| 권한 | 모델 파일 `0444`, 하위 모델 디렉터리 `0555`; cache root는 UID10001 소유 `0750`, PaddleX 임시/lock 허용 |
| 라이브러리 env | `PADDLE_PDX_CACHE_HOME=/opt/daesingo/paddlex`, `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True`; Dockerfile 및 loader가 지정, 앱 `.env` 선택 키 아님 |
| 화면시각 | Readout 기본 timezone `+09:00`, filename offset과 독립 |
| offline 검증 | Dockerfile `RUN --network=none ... readout-preflight`, UID10001; 정확한 local model directory를 전달하여 runtime 다운로드를 피함 |

`PADDLE_PDX_CACHE_HOME`만 다른 곳으로 바꿔도 production loader의 고정 `CACHE_ROOT`가 바뀌지 않는다.
Native Worker도 정확한 dependency와 위 디렉터리/manifest/권한을 따로 준비해야 한다.
PaddleX 일반 `~/.paddlex` 첫 호출 다운로드 설명은 현재 production 경로의 설치 절차가 아니다.
일반 import/collection은 Paddle을 로드하지 않는다. offline preflight 성공은 외부 Search 연결,
실제 영상 OCR 정확도나 8종 handler 등록 전체의 성공을 의미하지 않는다.

## 7. 준비·migration·실행·readiness

Linux Docker host에서 repo 밖 보호 파일을 준비한다. runtime 파일은 UID/GID
`10001:10001`, mode `0400`. MySQL password 두 파일은 **사용할 mysql image의 mysql
numeric UID/GID**, mode `0400`으로 준비한다. 다음 명령으로 UID/GID를 확인한다.
Compose bind는 소유권을 대신 보장하지 않으며 Docker daemon도 source 파일에 접근 가능해야 한다.
Windows/WSL은 Linux host/volume의 소유권 의미를 확인한다.

```sh
docker run --rm --entrypoint sh mysql:8.4 -c 'id -u mysql; id -g mysql'
```

아래 `<...>`는 운영자가 자신의 **파일 경로**로 바꾼다. password/key는 shell에 넣지 않는다.
설정은 §3 및 `.env.example`대로 파일 편집기로 채운다.

```sh
export DAESINGO_RUNTIME_ENV_FILE='<protected-runtime-env-file>'
export DAESINGO_MYSQL_ROOT_PASSWORD_FILE='<protected-root-password-file>'
export DAESINGO_MYSQL_PASSWORD_FILE='<protected-app-password-file>'
export DAESINGO_REVISION="$(git rev-parse HEAD)"
python scripts/check_compose.py
docker compose config --format json > /tmp/daesingo-compose-config.json
python scripts/check_compose.py /tmp/daesingo-compose-config.json
docker compose build api
docker compose run --rm --no-deps api python /app/docker/runtime.py media-preflight
docker compose run --rm --no-deps worker python /app/docker/runtime.py readout-preflight
docker compose up -d api worker
docker compose ps --all
docker compose exec -T api python /app/docker/runtime.py ready
```

`build api`는 같은 application image를 만들며 **기존 Docker cache를 재사용**한다.
새 build의 모델 다운로드에는 네트워크가 필요하다. 위 standalone `run`은 dependency를 시작하지 않는
preflight 전용이다. 실제 service 시작에 `--no-deps`를 사용하지 않는다.
Compose 순서는 **MySQL TCP healthy → migrate exit 0 → API/Worker 시작**이다.
migrate는 `docker/runtime.py migrate`가 파일에서 읽은 URL을
`python -m daesingo.common.db.migrate --database-url-stdin`의 stdin으로 전달한다.
API/Worker startup에서 migration을 자동 수행하지 않는다. migrate nonzero이면 조사/repair하고
API/Worker를 우회 시작하지 않는다. MySQL 부분 DDL을 자동 rollback했다고 가정하지 않는다.

API `/health/live`는 생존, `/health/ready`는 제한 시간 내 DB와 media mount 검사다.
기본 ready budget `3`초, adapter HTTP timeout `4`초, Compose healthcheck timeout `5`초다.
DB 단절 시 live 200/ready 503은 가능하다. mount metadata/access probe는 쓰기·fsync·전체 용량 시험이 아니다.
API healthy는 Worker/OCR/provider/queue 건강이나 8종 등록 증거가 아니다.
Worker에 별도 Compose healthcheck는 없으며 종료/안전한 로그와 execution/heartbeat 사실을 별도 확인한다.
30초 stop grace는 모든 handler 완료 보장이 아니며 초과 시 lease→STALE 복구 경계다.

native API/Worker는 선택 파일의 DB host/port를 실제 접근 가능한 MySQL로 바꾸고, 같은 media와
서비스별 temp root를 먼저 준비한다. Compose는 MySQL port를 host에 열지 않는다.
MySQL이 준비된 후 migration 성공을 확인하고 API와 Worker를 **별도 프로세스**로 실행한다.
아래 POSIX shell 예시는 CLI 경로 설명이며 Windows native OCR 지원 검증을 뜻하지 않는다.

```sh
uv sync --python 3.12 --locked --no-dev --extra eval-gemini --extra readout-paddle
export DAESINGO_ENV_FILE='<protected-runtime-env-file>'
uv run --no-sync python docker/runtime.py migrate
# 터미널 1 (API host/port 기본 127.0.0.1:8000)
uv run --no-sync python -m daesingo.api --revision "$(git rev-parse HEAD)"
# 터미널 2: 같은 DAESINGO_ENV_FILE 선택 및 고정 production OCR cache 준비 후
uv run --no-sync python -m daesingo.worker
```

native 직접 CLI는 container adapter의 media manifest preflight를 자동 호출하지 않는다.
정확한 동일 8.1 binary pair와 기능 검증은 별도로 필요하다. 권장 재현 경로는 고정 Docker image다.
`docker compose down`은 named volumes를 보존한다. 기존 프로젝트에 `down -v`/prune을 하지 않는다.
runtime 파일 교체 후에는 recreate가 필요하며 단순 restart만으로 새 bind inode를 보장하지 않는다.
DB backup은 media volume 전체 backup을 대신하지 않는다.

## 8. 필수 8종 handler를 확인하는 현재 수단

필수 목록은 `HINT_EXTRACT`, `COARSE_SEARCH`, `FINE_VERIFY`, `INCIDENT_CLIP_BUILD`,
`PLATE_READ`, `OVERLAY_TIME_READ`, `REPORT_VIDEO_EXPORT`, `PLATE_IMAGE_EXPORT`다.
현재 운영 startup 로그/health에는 등록 목록 전용 관측 API가 없다.

구성 확인은 기존 조립 함수를 별도 진단 프로세스에서 호출하고 테스트에서도 사용하는 내부
`registry._handlers` snapshot을 읽는 방법이다. 아래는 **현재 파일로 새로 조립한 결과**이며
이미 실행 중인 Worker의 메모리를 읽는 기능이 아니다. OCR을 다시 예열하므로 자원이 필요하다.
파일 교체 후에는 Worker recreate와 실제 작업 결과도 대조한다. 실제 DB 작업을 발주하지 않는다.

```sh
docker compose exec -T worker python - <<'PY'
from daesingo.worker.bootstrap import bootstrap
from daesingo.common.db import create_worker_engine
from daesingo.worker.readout_composition import production_readout_factory
from daesingo.worker.composition_root import compose_registry
startup = bootstrap(revision="registry-check")
engine = create_worker_engine(startup.config.db)
try:
    factory = production_readout_factory(engine=engine, startup=startup)
    registry = compose_registry(engine=engine, startup=startup, readout_provider_factory=factory)
    expected = {"HINT_EXTRACT", "COARSE_SEARCH", "FINE_VERIFY", "INCIDENT_CLIP_BUILD",
                "PLATE_READ", "OVERLAY_TIME_READ", "REPORT_VIDEO_EXPORT", "PLATE_IMAGE_EXPORT"}
    registered = set(registry._handlers)
    print("registered:", ",".join(sorted(registered)))
    if registered != expected:
        raise SystemExit(1)
finally:
    engine.dispose()
PY
```

별도로 `tests/worker/test_entrypoint.py`, `test_production_readout.py`,
`test_readout_composition.py`가 main/factory/등록 경계를 검증한다. 테스트 대역 결과를 실제 Paddle 성공으로 세지 않는다.
기존 Compose smoke의 의도적 미등록 test kind 재시도 검사는 8종 등록 acceptance가 아니다.
#468 실제 OCR acceptance는 두 판독/T1/T2 증거이며 8종 전체의 운영 관측 기능이 아니다.
등록 목록 startup log/smoke와 배포 차단 조건은 **#450 RD-12h 후속**이며 이번 문서 작업에서 기능을 추가하지 않는다.

## 9. #452 용량·처리시간 제약과 미확정 판단

[#452 전체 논의](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452)의
64 MiB는 당시 MySQL `max_allowed_packet` 관측값이다. LONGBLOB의 제품 지원 상한이나
“약 5분까지 지원”이라는 보장이 아니다. CRF 출력은 내용에 따라 달라진다.
22개 원본/1,166.13초 범위의 AnalysisSource `234,566,319 bytes`, 준비 누적 `285.2초`는
해당 Windows 직접 호출의 측정값이고 Linux/현재 profile 보장값이 아니다.
Search 5분 입력의 15.7 MB/17초도 480p 조건의 별도 1회 측정값이다.

| 결정/제약 | 현재 상태와 필요한 판단 |
| --- | --- |
| MVP 저장 | DB 한 행 유지; packet 상한만 올려 해결했다고 하지 않음 |
| 사전/변환 중 거부 | Owner 합의: 명시적 prepared-media byte 한도 및 별도 지원 길이를 정하고, 변환 전/누적·최종 byte 검사로 DB write 전 중단 |
| 오류 전달 합의 | `ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED` → Runtime `RECORDING_ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED`, Case는 재시도 없는 “분석 범위가 너무 김” notice 방향 |
| 현재 구현 여부 | 현재 `RecordingSettings`에는 그 상한 env가 없음. 이 문서가 해당 거부/mapping/notice 구현 완료를 주장하지 않음 |
| 지원 길이/bytes/encoding | **미확정**. Recording Owner가 실제 runtime profile·DB packet/driver overhead·Search inline 상한과 함께 측정/확정 필요 |
| Search 상한 | 코드 inline media `40 MiB`, request `56 MiB`; Recording 저장 상한과 다른 단계, runtime env knob 아님 |
| 시간 예산 | Case 요청 시점 + Search `150초` + 큐 여유 `30초` 유지 합의. Recording 준비/큐는 Case 대기에 포함되며 Search RunDeadline은 Search 호출부터 시작 |
| 재측정 | Runtime 머신에서 준비·큐·Search를 나눠 측정한 뒤 Case 대기 기준 판단. 범위 분할은 MVP 밖 #168 |

지원 분 수·운영 encoding 수치·byte 한도를 임의로 정하거나 미구현 env 이름을 만들지 않는다.
이 미결과 무관하게 위 파일 경계·DB/migration·Readout·실제 parser 키로 환경을 준비할 수 있다.

## 10. 검증된 명령과 증거의 범위

| 명령/경로 | 확인된 증거 | 확대하지 않는 범위 |
| --- | --- | --- |
| `docker build`, `python /app/docker/runtime.py media-preflight` | [#465 Notes](./issue465-mp4-toolchain.md)의 pinned 8.1 image·MP4/AVI/MKV/chain/export 실제 검사 | 이번 문서 변경에서 rebuild/실영상 전체 성공 주장 없음 |
| `python /app/docker/runtime.py readout-preflight` (`--network none`) | [#468 Notes](./issue468-production-readout.md)의 최종 image/UID10001·offline 두 모델 로드/예열 | native/Paddle 모든 플랫폼·실영상 OCR 정확도 보장 아님 |
| `python -m daesingo.worker` | #468 최종 image의 실제 기본 Worker·별도 API·Paddle 두 판독 T1/T2·SIGTERM exit0 | 선행 Search 응답은 offline 대역; 외부 provider 전체 E2E 아님 |
| `docker compose up`, migrate/ready | #465 Notes의 전용 Compose smoke 10단계·cleanup PASS | 기존 개인 env/운영 배포 검증 완료 아님 |
| `python scripts/check_compose.py` | 현재 source 구조 검사 | migration/실행 검증을 대신하지 않음 |
| §7 일반 cache build/native 예시, §8 진단 | 현재 CLI/조립 코드와 대조한 재현 절차 | 이번 변경에서 full Compose/native OCR/실제 credential 실행은 하지 않음 |

이번 #460 검증 결과와 fresh reviewer 판정은 [Implementation Log](./runtime-implementation-log.md)의
2026-10-30 #460 항목에 별도로 기록한다. 기존 #465/#468 실행 결과를 이번 실행으로 집계하지 않는다.
