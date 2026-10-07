# Runtime Implementation Log

**Status:** workflow §8 Implementation Log — 구현이 진행되며 누적하는 living record**Owner:** Runtime/Ops 김준영(@flosure23) · Primary Implementer 정철원(@cheol1203)**Plan:** [Runtime Implementation Plan](./runtime-implementation-plan.md) — 구현 **전** 계획. 이 Log는 **실제로** 구현된 것이다(Plan §12.5)**Started:** 2026-10-06 · 기준 `origin/develop` `960a046`

> 이 문서는 무엇이 만들어졌고 Plan에서 무엇이 달라졌는지를 한곳에 남겨, Runtime/Ops Owner가 PR마다 따라가지 않고 나중에 이 문서와 PR Implementation Notes만으로 확인(Plan §12.6 Audit)할 수 있게 한다. **규칙을 만들지 않는다.** Contract · Accepted Decision · Baseline이 바뀌면 그 결정은 각 SoT에 있고 여기에는 「바뀌었다 + 어디」만 적는다. 실행 모델(merge authority · 멈춰야 하는 경우 · PR Notes 형식)의 원문은 Plan §12다.

## 사용 규칙

- **언제** — PR 단위 순서는 Plan §12.8 체크리스트다. RT Task의 구현 PR이 merge될 때, 가능하면 **같은 PR에서** 해당 Task 절을 갱신한다. merge 전이라 SHA가 없으면 `pending`으로 두고 다음 PR이나 정리 PR에서 채운다. Log 갱신을 이유로 구현 PR merge를 막지 않는다.
- **최소 기록** — Task · Issue · PR · Merge SHA · 구현 요약 · Plan 대비 변경 · Owner 확인 포인트 · Tests · 남은 위험.
- **출처** — PR 본문의 Implementation Notes(Plan §12.4)를 Task 단위로 요약해 옮긴다. 상세는 PR이 원문이다.
- **Plan을 고치지 않는다** — Plan과 다르게 구현했으면 Plan을 다시 쓰지 않고 아래처럼 「Plan 대비 변경」에 적는다.

  ```text
  (예시)
  Plan:          heartbeat.py + cancel.py 분리 예상
  Actual:        execution_lifecycle.py로 통합
  Reason:        공유 state · fencing 경계가 하나라 분리하면 순환 dependency 발생
  Contract 영향: 없음
  ```

- **implementation detail** — 나중에 중요해질 수 있는 구현 선택(값 · 구조)은 Task 절과 함께 아래 「Implementation detail 색인」에 한 줄 남긴다. 별도 RD Issue를 만들지 않는다(Plan §12.3).
- **Baseline 조정 후보** — 실측으로 Baseline 값을 바꿀 근거가 생기면 구현 PR에서 바꾸지 않고 「Baseline revisit 후보」에 적는다. 결정은 workflow §10 → §11 경로다.
- **Status 값** — `NOT_STARTED` · `IN_PROGRESS` · `DONE`(Task의 PR 전부 merge · acceptance 통과 — Issue close와 같은 시점, Plan §12.8) · `AUDITED`(Plan §12.6 Audit 확인 뒤).
- 비어 있는 항목은 `—`로 둔다.

## Implementation detail 색인

Plan §0.1이 Task PR로 넘긴 선택은 미리 행을 둔다. 그 밖의 선택은 구현하며 추가한다.

| 항목 | 선택 | Task · PR | 근거 위치 |
| --- | --- | --- | --- |
| Baseline 밖 config key 이름 — DB 접속 · 공유 mount root · service별 temp root (Plan P-8) | `DAESINGO_RUNTIME_DB_URL` · `DAESINGO_RUNTIME_MEDIA_ROOT` · `DAESINGO_RUNTIME_API_TEMP_ROOT` · `DAESINGO_RUNTIME_WORKER_TEMP_ROOT` — 필수, 기본값 없음 | RT-01 · PR pending | 아래 RT-01 · `common/config/` |
| RuntimeConfig · startup module 검증 경계 | frozen Runtime snapshot + frozen Pydantic 설정 묶음 · service별 defaults · read-only mapping 1회 전달 · `ModuleFactory` registry | RT-01 · PR pending | 아래 RT-01 |
| structured log · revision · correlation | 전용 stdout JSON logger · 안전한 event 필드 허용 목록 · `revision` 명시적 인자 · contextvars + thread 제출 helper | RT-01 · PR pending | 아래 RT-01 · `common/logging/` |
| `DECIMAL` precision/scale (Plan P-10) | pending | RT-07 | — |
| type checker 도구 (Plan RT-15) | pending | RT-15 | — |
| secret scan 배치 — PR gate 편입 여부 (Plan RT-15) | pending | RT-15 | — |
| Compose smoke의 CI 편입 여부 (Plan RT-13) | pending | RT-13 | — |

## Baseline revisit 후보

| Baseline ID | 관측 | Evidence | 처리 (workflow §10 → §11) |
| --- | --- | --- | --- |
| 없음 | — | — | — |

## Owner 확인 기록

Plan §12.3에서 「멈추고 확인」에 해당해 Owner에게 확인한 건만 남긴다.

| 날짜 | Task · PR | 확인 내용 | 확인처 | 결과 · 기록 위치 |
| --- | --- | --- | --- | --- |
| 없음 | — | — | — | — |

## Milestone audit

묶음 정의는 Plan §12.6이다. workflow gate가 아니다.

| Audit | Task | 상태 | 확인일 | 결과 · 후속 |
| --- | --- | --- | --- | --- |
| A — Runtime Core | RT-01 ~ RT-06 | 대기 | — | — |
| B — Integration | RT-07 ~ RT-11 (+ REC-1 소비 surface) | 대기 | — | — |
| C — Operations | RT-12 ~ RT-15 | 대기 | — | — |

---

## RT-01 — Runtime config · composition bootstrap · structured log 기반

Status: DONE · Issue: #288 · Audit: A

완료 근거: 최종 common/api/worker 121 passed · 신규 회귀 22 passed · 전체 pytest 1826 passed / 44 skipped · boundary / Contract fixture / diff 검사 PASS. 사용자에게 전달받은 독립 재리뷰 결과는 병합 차단 문제 없음 · RT-01 전체 완료 PR 생성 가능이다. 사용자 요청에 따라 구현 완료 상태를 `DONE`으로 기록하며, PR 생성·merge 및 Owner Audit 완료를 뜻하지 않는다(PR·Merge SHA는 pending 유지).

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| pending (로컬, PR 미생성) | RT-01 config/bootstrap + structured logging 한 단위 | pending |

### 구현 결과

- `common/config/`: api·worker 공용 불변 `RuntimeConfig`와 DB/heartbeat/worker/upload/frame/cleanup/ready 묶음. API와 Worker의 key 집합·pool 기본값을 분리하고, Baseline §2 Config 표 후보 이름(P-8)·기본값·§9 불변조건을 검증한다. Baseline에 config가 아닌 값은 새 knob으로 열지 않았다. heartbeat I/O timeout 합을 interval과 비교하지 않는다.
- `api/bootstrap.py` · `worker/bootstrap.py` → `common/bootstrap.py`: composition root만 shell의 `DAESINGO_ENV_FILE`을 읽어 명시적 경로를 전달한다. 파일은 한 번 읽고 같은 read-only mapping으로 Runtime 및 module factory/validator를 검증한다. shell의 다른 값과 병합하지 않고 `load_env_file()` 무인자 동작은 그대로다.
- Worker는 현재 Search의 `GeminiSearchConfig.from_dotenv(mapping)`를 실제 호출하고 현재 credential key를 검증한다. api에는 현재 파일 기반 module config가 없어 기본 registry가 비어 있다. 추가 module factory는 service 조립 시 등록한다. factory 결과를 `Startup.modules`에 보관하여 후속 조립에 재사용한다. Search key rename/alias, pricing/FX 필수화, 타 Owner 코드는 변경하지 않았다.
- `common/logging/`: stdout JSON line · `trace_id/case_id/job_id/execution_id/module` contextvars · trace 생성 · nested reset · asyncio 격리 · thread 제출 시 명시적 context 복사. event helper는 허용 필드·안전한 코드/ID·유한 숫자만 받으며 raw message/exception/stack/arbitrary extra를 JSON으로 내보내지 않는다.
- 검증된 Runtime 설정 오류와 모듈 factory 예외는 `runtime.config.invalid`에 key 이름만 기록하고 `SystemExit(1)`로 종료한다. 모든 `ModuleFactory.keys` 선언은 factory 실행 전에 검사한다. 잘못된 선언은 원문 없이 `keys=[]`, 고정 `status=INVALID_MODULE_FACTORY_KEYS` 진단과 종료 코드 1을 남긴다. 미지의 Runtime key는 `runtime.config.unknown` 경고만 남긴다. 검증 성공 뒤 `process.started`에 service·명시적 revision을 남긴다. 이 설명은 아래 회귀 테스트로 확인한 경로의 보장이며 임의의 모든 startup 예외에 대한 포괄 보장이 아니다.

### Plan 대비 변경

- Plan의 1~2 PR 허용 범위에서 config와 log를 한 단위로 구현했다. startup 오류의 안전한 관찰까지 함께 검증하기 위함이다. Task 범위·dependency 변경 없음.
- 공통 startup mechanics는 `common/bootstrap.py`, 파일 경로 선택과 실제 module factory 등록은 api·worker에 둔다. 파일/class 배치에 해당하는 implementation detail이다.
- HTTP app·Worker 실행 조립은 각각 RT-08/RT-10 이후다. RT-01은 config/bootstrap 기반과 실제 Search config factory 검증까지 제공한다. DB engine/transaction·migration·route·loop·배포는 추가하지 않았다.
- Contract 변경 없음 · Accepted Decision 변경 없음 · Provisional Baseline 값/의미 변경 없음. SoT 모순 없음.

### 새 implementation detail

- 필수 key: `DAESINGO_RUNTIME_DB_URL`(SQLAlchemy `mysql+pymysql` URL, host/user/database 필요) · `DAESINGO_RUNTIME_MEDIA_ROOT` · 해당 service의 `DAESINGO_RUNTIME_API_TEMP_ROOT` 또는 `DAESINGO_RUNTIME_WORKER_TEMP_ROOT`. 배포 경로·접속값은 임의 default를 만들지 않았다. 경로 존재/쓰기 가능 probe는 후속 health/storage 단계다.
- Baseline B-R2의 후보 `…_BACKOFF_MAX_SEC`는 P-8대로 `DAESINGO_RUNTIME_BACKOFF_MAX_SEC`로 고정했다. Python 내부 필드명은 `worker.stale_retry_backoff_max_sec`다. 별도 heartbeat lock-wait/ready-budget/concurrency key는 만들지 않는다.
- `DbSettings.url`은 `SecretStr`이며 RT-02에서 `get_secret_value()`로 소비한다. pool과 I/O timeout은 검증된 필드로 전달한다. engine 생성은 하지 않는다. heartbeat lock wait와 ready budget은 해당 Baseline 고정값이며 별도 key가 아니다.
- `ModuleFactory(name, keys, factory)`: 의미 해석은 모듈 factory 소유다. `keys`는 선언된 `tuple[str, ...]` 형태와 프로젝트 기존 환경변수 key 형식 `[A-Z][A-Z0-9_]*`를 startup에서 검증한다. 전체 registry 검증이 끝나기 전에는 어떤 factory도 실행하지 않는다. opaque 예외에서 key를 추측하지 않고 검증된 관련 key 목록만 기록한다. 잘못된 선언의 원문·factory 이름·예외 원문은 진단에 넣지 않는다. credential은 Search의 현재 `GEMINI_API_KEY`를 사용하며 `Startup` repr에서 module 설정을 제외한다.
- `bootstrap(revision=...)`: revision은 호출자가 commit SHA 등 안전한 식별자로 명시한다. 새 revision 환경변수는 만들지 않는다. startup 진단과 started event를 먼저 기록한 뒤 설정된 log level을 적용해 ERROR 설정에서도 시작 진단이 사라지지 않게 했다.
- 전용 `daesingo.runtime.api/worker` logger의 root 전파는 끈다. formatter는 거대 숫자 등 잘못된 metadata를 안전한 event로 치환하고, 출력 stream 실패에서는 표준 logging의 raw traceback 대신 고정된 `log.write.failed` JSON만 stderr에 기록한다. correlation/thread helper는 process 내부용이며 durable trace column 연결은 RT-03이다. event 이름·ID/코드 필드는 신뢰된 metadata 전용이다.

### Owner 확인 포인트

- 김준영 deferred Audit A: api/worker schema 분리와 필수 key 명칭, `DbSettings` 소비 형태, startup 진단 순서와 안전한 event 필드 API.
- RT-02에서 실제 engine·heartbeat/probe 연결에 검증된 설정이 그대로 전달되는지 확인. RT-08/RT-10에서 사용하는 모듈의 factory 등록 및 반환 config 재사용을 확인.
- `process.started`는 RT-01 bootstrap 검증 완료 이벤트다. HTTP readiness·claim 가능성·provider 연결 성공을 의미하지 않는다. 후속 composition이 완료된 시점으로 호출 위치를 연결해야 한다.
- 정본 의미나 타 Owner surface 변경이 없어 사전 Owner 확인 대상은 없었다. Owner acceptance와 CI/E2E를 이번 local unit 검증으로 대체하지 않는다.

### Verification

- RED: 새 config/logging/bootstrap import 부재 3 collection error 확인 후 구현. 이후 잘못된 DB URL 예외·subprocess stderr 경로 4 failed / 69 passed 확인 → SQLAlchemy `ArgumentError`를 key-only 오류로 정규화하여 GREEN.
- 기존 common baseline: 14 passed. key 선언 검증 수정 전 RT-01 targeted unit: 85 passed · common/api/worker 회귀: 99 passed. 수정 후 common/api/worker 회귀: **121 passed** (`.venv/Scripts/python.exe -X utf8 -m pytest -q tests/common tests/api tests/worker -p no:cacheprovider --basetemp=.codex-scratch/rt01-keys-regression-001 --tb=short`). Baseline §2 표를 직접 파싱해 모든 canonical key와 P-8 추가 key가 실제 registry와 일치하는 대조 테스트를 포함한다.
- 초기 독립 코드 리뷰: Important 1건 — 거대 숫자 formatter 오류 시 표준 logging의 stderr 진단이 원문을 노출. 실제 venv에서 실패 재현 후 수정했고, 같은 위험이 있는 출력 stream 실패도 별도 RED→GREEN으로 검증했다. 이후 독립 리뷰가 `ModuleFactory.keys` 미검증에 따른 추가 병합 차단 문제를 발견했고, 아래 회귀 테스트로 수정했다.
- 추가 병합 차단 수정 RED→GREEN: `tests/common/test_module_factory_keys.py`에서 **21 failed · 1 passed → 22 passed**. 혼합 None/정수/unhashable 항목 · `bad-key` · 민감 문자열/로컬 경로 · 잘못된 container를 검사하며, api·worker에서 앞선 정상 factory까지 실행되지 않음, 코드 1, 안전한 고정 `runtime.config.invalid` 진단을 확인한다. subprocess에서는 stderr가 비어 있고 stdout JSON에 잘못된 key/예외/secret/경로 원문이 없음을 확인한다. 정상 key의 factory 예외 비노출도 유지됨을 확인한다.
- 독립 재리뷰 통과: 사용자 확인 — 병합 차단 문제 없음 · RT-01 전체 완료 PR 생성 가능 판정. 위 최종 검증 결과와 재리뷰 통과를 근거로 사용자 요청에 따라 `DONE`으로 변경했다. 이번 문서 갱신에서는 테스트를 재실행하지 않고 `git diff --check`만 최종 확인한다.
- key 선언 검증 수정 후 최종 전체 pytest: **1826 passed · 44 skipped**, 실패 0 (`.venv/Scripts/python.exe -X utf8 -m pytest -q -p no:cacheprovider --basetemp=.codex-scratch/rt01-keys-full-001 --tb=short`) — MySQL URL 미지정 · 로컬 실영상/평가 미디어 없음 · 선택 의존성 `typer` 없음에 따른 기존 skip이다. 신규 회귀에는 skip이 없다. 수정 전 전체 결과는 1804 passed · 44 skipped였다.
- `scripts/check_boundaries.py`: `python -X utf8`로 PASS, 위반 0건. Windows 기본 cp949 출력에서는 UnicodeEncodeError가 있어 UTF-8 모드로 실행했다(스크립트 수정 없음).
- `scripts/check_contract_fixtures.py`: PASS — 문서 구조 62 · JSON 파싱 26 · 의미 fixture 104 검사, 실패 0.
- `git diff --check`: PASS. Commit/push/PR 미실행. `recording-baseline-negative-001.json`과 기존 사용자 파일은 수정하지 않았다.
- 기존 venv에 정본 의존성이 없어 `uv sync --locked --extra test --extra eval-gemini` 실행. `pyproject.toml`/`uv.lock` 변경 없음. Windows sandbox/기존 pytest temp ACL 문제로 pytest는 승인된 권한과 새 전용 basetemp, `-p no:cacheprovider` 사용. 기존 pytest/user 파일은 변경하지 않았다.
- integration · CI · 수동/E2E: 미실행(RT-01 unit only, commit/push/PR 없음).

### 남은 위험

- Search factory가 현재 제공하는 검증 범위만 사용한다. 모듈 내부의 추가 의미 검증/rename은 해당 Owner 소유이며 Runtime에서 복제하지 않는다. 실제 서비스 조립에서 추가 factory 등록을 빠뜨리지 않아야 한다.
- 전역/타사 logger masking·log transport·rotation/retention은 구현하지 않았다. event helper의 허용 문자열에 실제 secret/free text를 ID로 잘못 넘기지 않아야 한다(Ops §7). 실사용/provider/배포 전 security review는 별도다.
- MySQL 연결·filesystem mount probe·queue 경유 trace 전파·module handler 실행은 후속 Task 검증이다. 이 기록은 배포 준비 완료나 Owner acceptance를 뜻하지 않는다.
- 비차단 후속 후보: logger handler 소유권/재설정 시 공유 handler 처리. 현재 `src`/`tests` 검색에서 실제 공유 handler 사용처는 확인되지 않아 이번 수정에 포함하지 않았다. `common/logging/`의 handler 동작 변경 없음.

---

## RT-02 — DB access 기반 · Alembic 배치 · MySQL integration harness · CI

Status: NOT_STARTED · Issue: #289 · Audit: A

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-03 — `job_execution` schema · queue repository

Status: NOT_STARTED · Issue: #290 · Audit: A

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-04 — Worker core: claim loop · kind registry · dispatch · T1/T2 (E2E-0)

Status: NOT_STARTED · Issue: #291 · Audit: A

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-05 — Lease · heartbeat · fencing · 협력적 중단

Status: NOT_STARTED · Issue: #292 · Audit: A

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-06 — STALE sweep · 자동 retry · T2 재전달

Status: NOT_STARTED · Issue: #293 · Audit: A

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-07 — Usage ledger: in-flight · Final UsageRecord · reconciliation

Status: NOT_STARTED · Issue: #294 · Audit: B

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-08 — API composition root: `/cases` · `/commands` · `/view` · `/health/*`

Status: NOT_STARTED · Issue: #295 · Audit: B

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-09 — 첫 비동기 E2E (integration acceptance)

Status: NOT_STARTED · Issue: #296 · Audit: B

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-10 — Worker composition root: 실제 kind handler 등록 · cross-process E2E

Status: NOT_STARTED · Issue: #297 · Audit: B

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-11 — Media HTTP: `POST /sources` · frames · assets

Status: NOT_STARTED · Issue: #298 · Audit: B

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-12 — 운영 위생: cleanup · 관측 집계

Status: NOT_STARTED · Issue: #299 · Audit: C

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-13 — Docker / Compose local runtime

Status: NOT_STARTED · Issue: #300 · Audit: C

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-14 — EC2 배포 · 운영 (Issue는 RT-13 착수 때 생성)

Status: NOT_STARTED · Issue: — (RT-13 착수 때 생성) · Audit: C

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-15 — CI 품질 gate · Runtime import 경계

Status: NOT_STARTED · Issue: #301 · Audit: C

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## REC-1 — recording 영속화 · HTTP/Worker용 capability (recording Owner)

Status: NOT_STARTED · Issue: #302 · Audit: B (Runtime이 소비하는 surface만)

recording Owner(정철원) 작업이다. 여기에는 Runtime이 소비하는 surface(RT-10 · RT-11 · RT-12 입력)만 기록하고, recording 내부 결정은 `docs/modules/recording/`이 원문이다.

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## Change log

| 날짜 | 변경 | 기준 |
| --- | --- | --- |
| 2026-10-06 | 생성 — Plan §12 Single Implementer + Deferred Owner Review 실행 모델의 기록 문서. RT-01 ~ RT-15 · REC-1 절 · implementation detail 색인 · Baseline revisit · Owner 확인 · Milestone audit 표 | PR #305 |
| 2026-10-06 | 사용 규칙에 Plan §12.8 체크리스트 pointer · `DONE` = Issue close 연결 | PR #307 |
