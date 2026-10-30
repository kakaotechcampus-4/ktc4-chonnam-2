# RT-15(a) Runtime quality gate

Status: IN_PROGRESS · Refs #301 · Related #287 · PR / merge SHA pending.

## Implementation plan

Spec: Runtime Implementation Plan RT-15 · §12; Ops §19; Issue #301.
현재 checkout을 유지하고 commit/staging/push/PR/외부 댓글 없이 구현한다.

- [x] 시작 상태와 근거 확인: clean index/tree, HEAD = fetched origin/develop
  `7bab60bc173603c43abf8a9dff6d99bb4dcec13c`, Issue 댓글 0개.
- [x] 변경 전 Ruff/mypy 진단 조사, 공식 문서와 기존 타입 구조 비교.
- [x] 잠금 의존성, 공통 로컬/CI 실행기, 최소 타입 정리 구현.
- [x] negative controls, focused regression, boundary/Contract/workflow 검증.
- [x] fresh read-only review와 같은 reviewer의 필요 delta 확인.
- [x] README/Implementation Notes/Log 갱신, 소유 scratch 정리.

제약: Runtime 네 경로만 검사한다. 다른 Owner lint/type 정리, 포맷 일괄 변경,
RT-15(b)/(c), AWS/provider 실행, 운영진 workflow/CODEOWNERS 변경은 범위 밖이다.
기존 timeout/inventory/skip/xfail/strict/transaction/취소/오류 매핑을 유지한다.

## 도구 선택과 규칙

| 후보 | 도입·기존 코드와의 관계 | 선택 |
| --- | --- | --- |
| mypy | Python wheel과 uv extra/lock으로 관리 가능. 기존 Pydantic·SQLAlchemy 타입을 읽으며 미타입 함수 본문도 검사 가능. import된 타 Owner 코드는 분석하되 진단 부과를 제한 가능 | 채택 |
| Pyright | include와 basic/standard/strict 지원. Node 기반 실행기 또는 Python wrapper의 실행 환경 관리가 추가됨. 현재 Python/uv gate에는 mypy가 더 단순 | 미채택 |

근거: [mypy existing code](https://mypy.readthedocs.io/en/stable/existing_code.html),
[import 처리](https://mypy.readthedocs.io/en/stable/running_mypy.html),
[Pyright configuration](https://github.com/microsoft/pyright/blob/main/docs/configuration.md),
[Ruff configuration](https://docs.astral.sh/ruff/configuration/). 2026-10-30 확인.
속도 우열을 실측한 비교는 아니다.

Ruff `E4/E7/E9/F`는 기본 오류 중심 규칙을 명시한다. import 정렬·줄 길이·전체
포맷 강제는 이번 범위가 아니다. mypy는 기본 오류 검사와 `check_untyped_defs`,
`warn_unused_ignores`, `warn_redundant_casts`를 켠다. 전역 strict/미타입 함수 금지는
기존 동적 composition/JSON 경계를 대량 재작성하므로 도입하지 않는다.
`follow_imports=silent`는 다른 Owner 진단만 제한하며 해당 public 타입은 계속 읽는다.
검사 경로 내부의 파일 exclude/진단 일괄 ignore는 추가하지 않는다. `paddleocr` 단일 모듈의 누락 타입만
예외로 둔다. 선택 설치 OCR이며 가짜 stub 없이 기존 runtime/preflight 검증을 유지한다.

초기 조사: Ruff F401 1건. mypy Windows 기본 기준 71 errors / 29 files,
87 source files. 플랫폼 전용 API, 빈 container/None 추론, union narrowing,
SQLAlchemy RowMapping, Pydantic 생성 입력과 공개 인자 타입 등이 포함됐다.
Linux 기준은 71 errors / 28 files였다. 둘 다 87 source files를 검사했다.
플랫폼 API 진단은 `os.name` 조건을 mypy가 인식하는 `sys.platform` 조건으로 바꿔
Windows/지원 POSIX 실행 경로를 유지했다.

### 정확한 타입 경계 예외

- `paddleocr` missing import: 선택 설치 native OCR을 정적 quality 환경에 설치하거나
  가짜 stub을 만들지 않는다. 기존 초기화·preflight·Docker acceptance는 그대로 유지한다.
- `worker/search_handlers.py`의 `search.verify_visual(max_latency_sec=...)` 인자 하나에만
  `type: ignore[arg-type]`를 둔다. Search public annotation은 `int | None`이지만
  Runtime/Case 입력은 finite positive int/float이고, SearchService는 그 값을 1000과
  곱해 budget으로 사용한다. int 변환은 기존 fractional deadline을 바꾸므로 하지 않는다.
  `warn_unused_ignores`로 향후 Search annotation 수정 시 남은 예외도 실패시킨다.
  0.125초를 그대로 전달하는 focused 회귀를 추가했다. Search Owner의 공개 annotation
  정합화는 별도 후속이며 다른 모듈 소스는 이번에 수정하지 않았다. 실행 결함으로 단정하지 않는다.

## Implementation Notes

### 구현 결과

- `quality` extra의 Ruff 0.17.3/mypy 2.4.1과 transitive dependency를 `uv.lock`에 잠근다.
  검사 대상 OCR warmup의 실제 import 타입을 읽기 위해 NumPy도 quality에 포함하며
  lock 버전은 2.3.5다. PaddleOCR·OpenCV·test extra는 quality 설치에 포함하지 않는다.
  기존 package 버전은 변경하지 않았다. resolver가 기존 `cuda-bindings`의
  `cuda-pathfinder` 조건에 Python `<3.15`를 명시하는 metadata 정규화도 만들었다.
- 실제 검사 경로는 `src/daesingo/{common,api,worker}/`, `migrations/runtime/`다.
  Python 파일 87개를 재귀 검사하며 특정 파일의 고정 inventory로 제한하지 않는다.
- 공통 명령:

  ```bash
  uv sync --locked --extra quality
  uv run --no-sync python scripts/check_runtime_quality.py
  ```

  실행기는 Ruff와 mypy Linux/win32를 차례로 모두 실행하고 하나라도 nonzero면 실패한다.
  제품 import/provider 호출은 없고 Ruff cache와 mypy incremental/cache 저장은 사용하지 않는다.
- `python-tests/quality`는 경로 필터·조건·continue-on-error 없이 실행된다.
  기존 `test`의 `always()`와 정확한 dependency 집합을 유지하는 방식으로
  `needs=[quality, regression, mysql]`를 요구한다. 실패/취소/skip/누락은 성공이 아니다.
  regression에 quality extra를 더해 실제 negative-control pytest도 실행 가능하게 했다.
- 타입 수정은 container/optional/lock/callback 타입, RowMapping 입력, Literal/Enum narrowing,
  지역변수 이름 분리에 집중했다. `api.health.storage_available`은 explicit re-export로 보존한다.
  multipart callback 집합은 동일한 7개를 vendor TypedDict에 맞게 명시했다.
- 기존 검증 이후 이미 성립하는 invariant를 assert로 표현했다(finite Decimal exponent,
  RUNNING started_at, driver IntegrityError cause, Worker heartbeat/reflector, API cleanup).
  DB sweep 시각 조회는 같은 SELECT에 `scalar_one()`을 사용해 반드시 한 행인 조회를 표현한다.
  transaction/SQL 조건/잠금/commit/rollback/취소/UsageError/T1/T2/직렬화 정책은 바꾸지 않는다.
  비정상적으로 조립된 객체/driver cause None에서 assertion 예외가 먼저 날 수 있는 제한은
  남긴다. 이 경우를 지원하는 동작 변경은 이번 범위로 확대하지 않는다.

### Plan 대비 변경
없음. RT-15(a)만 구현하며 RT-15 전체 완료는 주장하지 않는다.

### 새로 고정된 implementation detail
위 도구·규칙·검사 범위 참조.

### Contract / Decision / Baseline 영향
- Contract 변경: 없음.
- Decision 변경: 없음.
- Baseline 변경: 없음.

### Owner 확인 포인트
Runtime 범위와 strictness, 선택 OCR 타입 경계. repo 전체 확대는 팀 합의 후 별도.

### Verification

| 검사 | 작성자 직접 실행 결과 |
| --- | --- |
| `uv lock --check` | 132 packages, PASS |
| 공통 quality 명령 | Ruff 0 errors, mypy Linux/win32 각각 87 source files, 0 errors |
| quality 전용 clean 환경 | test/httpx/PaddleOCR/OpenCV 없이 동일 명령 PASS. NumPy 누락 RED → 실제 의존성 추가 후 GREEN |
| 실제 실행기 negative controls | clean fixture 통과, F401 및 미타입 함수 내 assignment 위반은 nonzero로 거부 |
| boundary | 위반 0건 |
| Contract fixture | 문서 62 / JSON 26 / 의미 104 검사, 실패 0건 |
| workflow | 공식 actionlint 1.7.12 SHA256 대조 후 변경 workflow 오류 0건. shellcheck/pyflakes는 비활성화, YAML/Actions expression 검사 |
| focused regression | 747 passed, 1 Starlette deprecation warning, 70.14s. 실패/skip/xfail 0 |
| fresh reviewer | 초기 지적 수정 후 같은 reviewer delta 확인 완료. 미해결 blocking 지적 없음. 아래 직접 실행/작성자 evidence 구분 참조 |

테스트 gate RED: quality dependency와 workflow가 없을 때 새 테스트 4건 실패를 확인한 뒤
추가했다. 실제 실행기 fixture도 실행기가 없을 때 실패를 확인했다.
초기 F401 제거는 기존 health re-export 사용을 깨뜨려 focused collection에서 검출됐으며
explicit re-export로 복원했다. Windows sandbox에서 focused 실행이 asyncio socketpair
`accept`에서 정체됨을 py-spy stack으로 확인했다. 해당 작업 PID만 종료하고 같은 범위를
샌드박스 밖에서 다시 실행하여 747 passed를 확인했다. 제품 실패로 간주하거나 skip/timeout 완화로 우회하지 않았다.

전체 pytest/전체 MySQL/Docker build는 실행하지 않는다. 원격 regression/mysql/test와
Docker acceptance의 최종 결과는 향후 push 후 CI 조건이다. AWS/provider 호출,
RT14 실행 변수/배포환경 변경은 없다. RT14의 true opt-in 조건을 그대로 보존했다.
GitHub Actions 변수는 읽기 전용 조회로 `RT14_EXECUTION_ENABLED=false`를 확인했다.

### Fresh review와 수정

구현 대화 이력을 상속하지 않는 read-only reviewer가 전체 diff를 확인했다.
초기 P1: quality-only 설치에 NumPy가 없는데 검사 대상 OCR warmup에서 import한다.
작성자의 기존 test-populated `.venv` 결과만으로 clean CI 성공을 추론한 것이 원인이었다.
작성자는 전용 quality 환경 한 개에서 실제 공통 명령으로 양쪽 플랫폼의
`numpy [import-not-found]` 각 1건과 exit 1을 재현했다. `quality` extra에 실제 NumPy를
추가하고 uv.lock을 갱신한 뒤 같은 환경·명령으로 양쪽 87 files / 0 errors를 확인했다.
별도 fake stub/ignore는 추가하지 않았다. 임시 환경은 공유 uv cache와 hardlink로 설치했다.
README의 기존 “두 성공” 설명도 실제 세 dependency로 바로잡았다.

Reviewer 초기 직접 실행: 기존 `.venv`의 공통 Ruff/mypy PASS,
quality·CI 테스트 55 passed (13.35s), `git diff --check` PASS.
Reviewer의 NumPy 문제 재현은 `--no-site-packages`의 정확한 import body와 lock graph 확인이다.
작성자의 clean 환경 RED/GREEN·747 focused 결과와 구분한다.
같은 reviewer의 delta 재확인 완료: quality 전용 환경에서 reviewer가 직접 Ruff PASS,
mypy Linux/win32 각각 87 files PASS, exit 0을 확인했다. NumPy/도구 버전과
test/httpx/PaddleOCR/OpenCV 부재도 직접 확인했다. NumPy P1과 README 설명 지적은
해결됐고 추가 blocking 지적은 없다. 747 focused/Contract/boundary/actionlint 및 clean
환경 RED는 작성자 evidence 검토이며 reviewer의 직접 실행으로 표현하지 않는다.
의존성 수정 후 작성자 quality/CI 회귀는 55 passed (12.28s), lock check와 actionlint도 PASS다.

### 미실행 검증과 잔여 위험

- Linux 실제 실행·최종 전체 regression/mysql/test/Docker acceptance는 push 후 원격 CI 조건이다.
  Windows에서의 Linux 타입 분석은 Linux runtime 실행 증거가 아니다.
- 기존 동적 JSON/composition 코드의 전역 strict/모든 함수 annotation 완비를 뜻하지 않는다.
  미타입 호출의 값은 mypy가 추론하지 못할 수 있다. 새 광범위 Any/cast/ignore는 없다.
- 선택 PaddleOCR missing import와 Search 공개 latency annotation 예외는 위 정확한 경계만 남긴다.
- source의 invariant assert와 sweep 조회 방식 변경은 실제 MySQL에서 재실행하지 않았다.
  기존 SQL/잠금/transaction 조건은 보존했으며 원격 canonical MySQL gate에서 확인해야 한다.
- Starlette/httpx deprecation warning 1건은 기존 의존성 범위의 경고로 이번에 의존성을 바꾸지 않았다.

### 정리와 전달 상태

작업 소유 테스트 temp, quality 전용 환경, actionlint 다운로드, 최소 JUnit/log 및 초기 mypy
cache를 정리했다. 공유 uv 다운로드 cache나 기존 타 작업 scratch는 정리 대상이 아니다.
변경은 모두 미커밋·미스테이징으로 남기며 commit/push/PR/외부 댓글/merge는 하지 않는다.

## 후속

RT-15(b)는 Runtime import boundary·위반 fixture·ownership 통지를 다룬다.
RT-15(c)는 secret scan 배치·오탐률·PR gate 편입 판단을 다룬다.
repo 전체 lint/type 확대는 팀 합의 뒤 별도다. RT-15 Status는 IN_PROGRESS를 유지한다.

## Focused regression 범위

테스트 명령은 Python 3.12에서 `python -B -X utf8 -m pytest`에 아래 경로와
`-q -p no:cacheprovider`를 전달했다. 실행기/required gate, 설정·로그·DB 오류,
Usage 금액·상태, T1/T2/취소·sweep lifecycle, filesystem·multipart, Worker 입력/배선을
다루는 기존 회귀와 새 negative control이며 전체 pytest/MySQL 실행이 아니다.

```text
tests/test_runtime_quality.py
tests/test_ci_orchestration.py
tests/common/config
tests/common/logging
tests/common/test_module_factory_keys.py
tests/common/usage/test_amount.py
tests/common/usage/test_usage_sink.py
tests/common/db/test_transactions.py
tests/common/jobs/test_produced.py
tests/common/jobs/test_validation_privacy.py
tests/common/jobs/test_cancel.py
tests/common/jobs/test_sweep_thread.py
tests/common/jobs/test_redelivery.py
tests/common/jobs/test_reflection.py
tests/common/storage
tests/api/test_app.py
tests/api/test_sources.py
tests/api/test_api_cleanup.py
tests/worker/test_worker_loop.py
tests/worker/test_usage_worker.py
tests/worker/test_search_handlers.py
tests/worker/test_incident_clip_inputs.py
tests/worker/test_export_inputs.py
tests/worker/test_entrypoint.py
```

## 변경 파일 전체 목록

- `.github/workflows/python-tests.yml`
- `README.md`
- `docs/runtime/rt15a-runtime-quality.md`
- `docs/runtime/runtime-implementation-log.md`
- `pyproject.toml`
- `scripts/check_runtime_quality.py`
- `src/daesingo/api/__main__.py`
- `src/daesingo/api/app.py`
- `src/daesingo/api/composition.py`
- `src/daesingo/api/events.py`
- `src/daesingo/api/health.py`
- `src/daesingo/api/storage.py`
- `src/daesingo/api/upload.py`
- `src/daesingo/common/bootstrap.py`
- `src/daesingo/common/config/__init__.py`
- `src/daesingo/common/db/errors.py`
- `src/daesingo/common/jobs/cancel.py`
- `src/daesingo/common/jobs/execution.py`
- `src/daesingo/common/jobs/read_port.py`
- `src/daesingo/common/jobs/redelivery.py`
- `src/daesingo/common/jobs/reflection.py`
- `src/daesingo/common/jobs/repository.py`
- `src/daesingo/common/jobs/sweep.py`
- `src/daesingo/common/jobs/worker_loop.py`
- `src/daesingo/common/logging/__init__.py`
- `src/daesingo/common/storage/_filesystem.py`
- `src/daesingo/common/storage/cleanup.py`
- `src/daesingo/common/usage/amount.py`
- `src/daesingo/common/usage/repository.py`
- `src/daesingo/common/usage/sink.py`
- `src/daesingo/worker/__main__.py`
- `src/daesingo/worker/composition.py`
- `src/daesingo/worker/export_inputs.py`
- `src/daesingo/worker/incident_clip_inputs.py`
- `src/daesingo/worker/search_handlers.py`
- `tests/ci_orchestration.py`
- `tests/test_ci_orchestration.py`
- `tests/test_runtime_quality.py`
- `tests/worker/test_search_handlers.py`
- `uv.lock`
