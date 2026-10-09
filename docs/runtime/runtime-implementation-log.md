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
| DB 역할별 engine · callback transaction | API/Worker QueuePool · heartbeat/ready/migration NullPool · `Connection` callback과 내부 context manager · B-D8 최초 포함 총 3회 | RT-02(a) · PR #319 · `4a513c0` | 아래 RT-02 · `common/db/` |
| MySQL 실제 장애 · CI 실행 증거 | 테스트별 schema · COMMIT OK 폐기 proxy · 실제 1205/1213/KILL · JSON/JUnit 대조 · 기존 Case 18개 실행 목록 | RT-02(a) · PR #319 · `4a513c0` | 아래 RT-02 · `tests/mysql_harness.py` · `scripts/check_mysql_test_report.py` |
| Alembic runner · 빈 Runtime env | frozen registry `case → runtime` · 명시 URL API/stdin CLI · 모듈별 transaction connection · 빈 Runtime version table · 첫 실패 중단 · process 내부 중복 거부 | RT-02(b) · 로컬, PR 미생성 | 아래 RT-02(b) · `common/db/migrate.py` |
| 실행 원장 schema · enqueue · read model | `runtime_0001` · 내부 시각 표식 column · ascii_bin ID · DB UTC microseconds · 단일 batch INSERT · Contract allowlist projection · usage_refs 비저장 | RT-03(a) · 로컬, PR 미생성 | 아래 RT-03 · `common/jobs/` |
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
| 2026-10-08 확인 | RT-02(b), PR 미생성 | Case env 입력 우선순위 최소 수정·외부 transaction 참여. Case fixture/revision/metadata/version table 의미 변경 없음, 공통 helper 의무 없음 | 유소연 @yuusoyeon | [Issue #289 승인 댓글](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/289#issuecomment-6055765577). Consult 결과이며 Case env는 향후 PR에서 Owner 리뷰 예정 |

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

Status: DONE · Issue: #289 · Audit: A

**RT-02(a)는 PR #319, `4a513c0`으로 병합됐다. RT-02(b)는 최종 독립 리뷰에서 병합 차단 문제 없음·완료 처리·커밋·PR 생성 가능 판정을 받았다(사용자 전달).** 사용자 요청에 따라 구현 완료 상태를 `DONE`으로 기록한다. RT-02(b) PR 번호와 merge SHA는 아직 `pending`이며, 원격 GitHub Actions는 PR 생성 후 확인한다. RT-02(b)는 Task의 마지막 PR이므로 PR 본문에 `Closes #289`를 사용한다. 이번 문서 갱신에서는 커밋·push·PR 생성을 하지 않는다. 아래 (a)의 최초 구현·검증 기록은 당시 결과이며, (b)의 현재 상태는 별도 절을 따른다. 향후 PR Implementation Notes에도 B-D8의 `max_attempts=3 = 초회 포함 총 3회` 명확화를 유지한다.

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| [#319](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/319) | RT-02(a) DB factory · callback transaction helper · MySQL harness · CI | `4a513c0` |
| pending (로컬, PR 미생성) | RT-02(b) Alembic env · runner · migration acceptance · 기존 gate 보강 | pending |

### 구현 결과

- `common/db/engines.py`: RT-01 `DbSettings`를 소비하는 API·Worker engine(RC · B-D1 · B-D2~D7), heartbeat 전용 engine(B-D9), ready 전용 engine(B-H1), 명시적 URL/timeout을 받는 migration engine 기반. engine 생성은 연결·migration을 실행하지 않는다. 물리 connection의 `connect` event로 lock wait를 적용하여 recycle/disconnect 교체에도 유지한다.
- `transactions.py` · `errors.py`: `Callable[[Connection], T]` 외부 interface와 내부 context manager. Worker는 1205·1213·SQLAlchemy가 invalidation으로 판정한 disconnect에 전체 DB transaction을 정리한 뒤 처음부터 재실행한다. API는 한 번만 실행하고 pool/초기 연결/COMMIT 전 장애와 COMMIT transport 결과 불명을 구분한다. domain·기타 SQL 오류는 원래 의미를 유지한다. rollback의 2차 오류가 domain 오류를 재시도로 바꾸지 않게 원래 오류를 보존하고 해당 connection을 폐기한다.
- `tests/mysql_harness.py`: 테스트별 빈 schema · 공용 `mysql_engine` · opt-in/require 모드 · MySQL 8.4 실제 연결과 CREATE/DROP 권한 preflight. 기존 Case fixture·테스트는 변경하지 않고 MySQL 대상 marker만 루트 hook에서 식별한다. 기존 Case migration/repository와 공용 factory의 호환성은 별도 integration으로 확인한다. 공용 migration fixture/env/runner는 RT-02(b)에 남긴다.
- 기존 `python-tests.yml`: MySQL 8.4 service, require flag, 전체 pytest JSON/JUnit 보고서, MySQL 대상 skip/xfail 0·필수 시나리오·기존 Case MySQL 18개 실행 검증. 기존 media smoke와 의존성 설치 절차를 유지한다.

### Plan 대비 변경

- §6의 (a)/(b) 분할 그대로다. `migrations/runtime/`, Alembic 재배치·runner·모든 모듈 upgrade acceptance는 (b)에 남긴다. Runtime table·HTTP status 매핑·startup migration·배포 실행 위치를 구현하지 않았다.
- harness는 세션 공유 schema 대신 테스트마다 schema를 생성한다. Case child fixture의 기존 동작은 그대로 유지하고, 공용 engine 참여를 독립 테스트로 검증한다. 타 Owner의 코드/의무 변경 없음.
- 새 의존성이 필요하지 않아 `uv.lock`과 의존성 선언을 변경하지 않았다. `pyproject.toml`은 pytest marker 등록만 추가했다. 루트·common README의 사실 문구를 갱신했다.
- Contract 변경 없음 · Accepted Decision 변경 없음 · Provisional Baseline 값/의미 변경 없음. B-D8 카운팅은 아래 PM 명확화에 따른다.

### 새 implementation detail

- **B-D8:** `max_attempts=3`, 1회차는 최초 시도이며 추가 재시도 최대 2회다. 총 3회 모두 실패하면 소진이고 재시도 사이 대기는 1초다. Baseline의 기존 「최대 3회」 카운팅 의미 명확화이며 값 변경이 아니다. [Issue #289 PM 확인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/289#issuecomment-6036679371). future PR Implementation Notes에도 동일하게 기록한다.
- API/Worker pool 값은 전달된 service별 RuntimeConfig.db를 사용한다(Worker는 Worker config의 2+2). heartbeat/ready/migration은 각각 별도 `NullPool`이며 일반 checkout 대기를 공유하지 않는다. heartbeat thread의 connection 보관·재연결 tick·겹침 금지는 RT-05 소유다.
- ready 기본 connect/read/write=1/1/1초. 단계별 I/O timeout은 end-to-end 2초 deadline 증명이 아니며 `/health/ready` 전체 budget은 RT-08에서 검증한다. migration은 app의 5/30/30초를 복사하지 않고 인자가 없으면 driver 기본값을 유지한다.
- URL의 timeout query는 역할 정책으로 대체하고 autocommit/init_command/default-file 등 session 정책 우회 option은 거부한다. TLS 등의 일반 접속 option은 유지한다.
- callback은 시도마다 상태를 다시 읽고 stable identity로 이미 반영된 결과를 판정해야 한다. COMMIT 응답 유실 후 재시도가 이전 성공을 rollback하지는 못한다. exhaustion은 이전 시도 중 COMMIT 결과 불명이 있었는지 보존한다. helper는 domain의 idempotency를 대신 구현하지 않는다.
- capability/provider/file publish는 callback 밖에서 호출한다. 일반 `Connection.commit()/rollback()` 오용은 event guard가 탐지하지만 raw SQL/DBAPI/DDL/stored procedure로 transaction을 끝내는 것은 callback 계약 위반이며 임의 Python의 외부 부작용 차단을 보장하지 않는다. handler 전체 sandbox를 구현했다고 주장하지 않는다.
- test proxy는 local TLS-disabled sequential MySQL packet만 중계한다. callback 진입 후 arm하여 driver 초기화 COMMIT은 제외하고, 실제 server COMMIT OK packet을 소비한 뒤 EOF를 보낸다. 별도 connection으로 실제 반영을 확인한다. 운영 proxy가 아니다.
- CI gate는 collected/selected/각 실행 phase/JUnit을 대조하고 17개 scenario group, 명시적인 role/scenario 32개 조합과 기존 Case 5개+13개를 요구한다. skip/xfail/deselection/수집 오류/보고서 누락을 실패시킨다. mock unit과 실제 integration을 별도 파일로 두며 실제 fault 경로에는 mock을 사용하지 않았다.

### Owner 확인 포인트

- 김준영 deferred Audit A: DB-only callback 조립 경계, unknown commit 후 read/idempotency, 세 역할별 timeout 및 후속 heartbeat/ready lifecycle 연결. B-D8 총 시도 수는 위 PM 확인으로 명확하다.
- Case Owner의 새 callback/fixture 의무를 만들지 않았다. Plan의 Consult 대상인 공용 interface와 기존 저장소 참여 호환성은 코드·테스트·Notes에서 검토할 수 있다. Contract·Decision·Baseline 재결정이나 추가 Owner 승인이 필요한 의미 변경은 없다.
- 전체 acceptance의 권한 실패 시나리오는 schema CREATE/DROP·자기 connection KILL 외에 테스트 사용자 CREATE/GRANT SELECT/DROP 권한도 요구한다. 폐기 가능한 관리자 계정 전용이며 app 계정 권한 요구가 아니다.

### Verification — 최초 구현 기록(2026-10-07)

- TDD: factory 10 RED → 10 GREEN; transaction 15 RED → 15 GREEN. callback commit 정리 누수·rollback 오류 마스킹·API 초기 연결 실패·preflight URL option 원문 노출·부분 Case 누락을 각각 RED로 확인하고 수정했다. proxy import 부재 3 RED → 실제 MySQL proxy 3 GREEN; 권한 실패까지 포함한 focused fault 재검증 4 PASS.
- 실제 MySQL: 기존 Windows MySQL 8.0은 사용하지 않고 workspace의 ignored scratch에 공식 MySQL 8.4.7 배포본을 추출해 WSL에서 독립 port로 실행했다. 프로젝트/시스템 패키지를 설치하지 않았고 Python은 기존 venv를 사용했다. sandbox DLL 제한 때문에 승인된 권한과 새 basetemp·`-B -p no:cacheprovider`를 사용했다.
- 중간 전체 common DB+Case: **413 passed · 2 skipped**, MySQL 대상 **36 passed · skip 0 · xfail 0**, JSON/JUnit gate PASS. skip은 기존 Case 실영상 2개다. 이후 API replacement/초기 연결 실패와 gate 회귀를 추가했다.
- 최종 전체 pytest: **1935 passed · 26 skipped · 실패 0**, 253.67초. `DAESINGO_REQUIRE_MYSQL=1`과 실제 MySQL 8.4.7을 사용했다. 명령: `.venv/Scripts/python.exe -B -X utf8 -m pytest -q -p no:cacheprovider --basetemp=.codex-scratch/rt02a-final-full --mysql-report=.codex-scratch/rt02a-final-full.json --junitxml=.codex-scratch/rt02a-final-full.xml --tb=short`.
- 최종 MySQL gate: **40 passed · skip 0 · xfail 0**, 17개 필수 scenario group, setup/call/teardown 120개 phase PASS. 기존 Case MySQL 18개(전용 5 + repository 계약 13), 신규 integration 22개(session 11 + 실제 transaction fault 7 + COMMIT proxy 3 + Case 호환 1). `scripts/check_mysql_test_report.py .codex-scratch/rt02a-final-full.json .codex-scratch/rt02a-final-full.xml` PASS.
- skip 26개는 MySQL 외 기존 opt-in이다: 선택 의존성 `typer` 부재의 Search collection skip 4 · Case 실영상 없음 2 · eval 로컬 미디어 없음 5 · Recording 실영상/VIDEO_INDEX/연속 원본 opt-in 없음 15. 신규 테스트 skip 없음. 실제 MySQL acceptance를 mock/skip으로 대체하지 않았다.
- boundary PASS(위반 0) · Contract fixture PASS(문서 62 · JSON 26 · 의미 104) · `git diff --check` PASS. Case 코드/fixture/테스트, migration, Baseline/Contract/Decision, `uv.lock`, `recording-baseline-negative-001.json`은 수정하지 않았다. 커밋·push·PR 없음.
- 최초 read-only 리뷰에서는 API 획득 실패 분류·preflight 진단 수정 뒤 차단 finding 없음으로 평가받았으나, 이후 독립 리뷰에서 아래 3건이 재현됐다. 최초 평가를 현재의 무결성 보장으로 해석하지 않는다. 이 최초 기록 당시에는 해당 수정의 독립 재리뷰를 받기 전이었다.
- GitHub Actions 자체는 미실행(커밋·push·PR 없음). 로컬에서 실제 MySQL과 동일한 report gate를 실행했다. service image/Ubuntu runner 검증은 향후 CI 실행이 필요하다.
- 검증 뒤 port/version/datadir로 작업 소유를 확인하고 격리 MySQL을 종료했다. 기존 Windows MySQL service는 변경하지 않았다. 보조 YAML parser 검사는 로컬 PyYAML 부재로 미실행이며 설치하지 않았다; workflow는 diff·독립 리뷰로 확인했고 실제 Actions 실행은 위와 같이 남아 있다.

### 2026-10-08 독립 리뷰 finding 수정 · 재검증

| Finding | 원인과 최소 수정 | RED → GREEN 근거 |
| --- | --- | --- |
| 테스트 schema 격리 우회 | SQLAlchemy가 URL query를 path 접속 인자에 덮어쓴다. PyMySQL의 database/db, init_command, read_default_file/group, endpoint/account 재지정 및 미지 option을 공용 harness의 query 허용 목록으로 fail-closed 거부한다. URL 검증·control engine 생성·schema CREATE 전에 검사하며 값/URL/경로 없는 고정 UsageError만 낸다 | 단위 41 RED → 41 GREEN. 실제 MySQL override 3 RED → schema identity 포함 4 GREEN. SELECT DATABASE()가 생성 UUID schema와 정확히 일치하고, 거부 경로 SQL 0건·기존 sentinel DDL/row/table 목록 불변 확인 |
| COMMIT 결과 불명이 cleanup에 덮임 | connection context 바깥까지 원래 transaction failure를 보존한다. COMMIT 오류 처리 중 SQLAlchemy checkin이 덮어쓴 DBAPIError도 예외 체인에서 복원한다. 우선순위는 확인된 COMMIT 성공 > 원래 transaction 오류 > cleanup 오류다. 실패한 invalidate도 원래 body/domain 오류를 덮지 못한다 | 신규 8 RED → 8 GREEN; 기존 transaction/proxy 합계 29 PASS. 실제 COMMIT OK 폐기 뒤 context 종료와 pool checkin TimeoutError를 각각 주입하고 독립 observer row 1개·최종 CommitOutcomeUnknown·안전한 오류/event 확인 |
| 역할별 필수 검사 누락 허용 | scenario 합집합에 더해 mysql_check(role, scenario) metadata를 수집하고 필수 32개 조합을 별도로 요구한다. API가 Worker의 session/recycle/disconnect/wait_timeout 검사를 대신 충족할 수 없으며 초기 연결 거부·heartbeat/ready·각 실제 fault도 필수다. 기존 Case 18개 목록은 유지한다 | 메모리 report 복사본에서 각 필수 조합의 node를 collected/selected/execution에서 제거: 기존 gate 32 RED → 수정 gate 32 GREEN. gate 회귀 합계 52 PASS |

- 기존 `.codex-scratch/`와 `recording-baseline-negative-001.json`을 변경하지 않았다. 서버·검증 도구·pytest basetemp·JSON/JUnit은 별도의 OS 임시 디렉터리 `rt02a-review-20261008-*`를 사용했다. 당시에는 독립 재리뷰 전이어서 차단 문제가 모두 없다고 단정하지 않았다.
- 로컬 opt-in에서도 기존 Case child fixture가 engine을 만들기 전에 pytest_configure에서 URL을 검증한다. require=0에서 위험 URL을 허용하던 경로를 추가 RED로 확인했고 require=0/1 두 subprocess 회귀를 포함한 schema 단위 43 PASS를 확인했다. Case fixture·테스트는 수정하지 않았다.
- 실제 MySQL 8.4.7 require 모드의 DB+Case 회귀: **509 passed · 2 skipped**(기존 Case 실영상 없음). MySQL 대상 **46 passed · skip 0 · xfail 0**, 기존 Case 18개 포함, role/scenario 32개·JSON/JUnit gate PASS. 실제 실행 report의 메모리 복사본에서도 필수 조합별 node를 하나씩 제거한 32가지가 모두 거부됐다.
- workflow 검사: 공식 release의 actionlint **1.7.12** + ShellCheck **0.11.0**, YAML parse/actionlint 오류 0건. Ubuntu Python의 기존 YAML parser로 service·require flag·gate 연결을 검사하고 5개 run step의 `bash -n`·ShellCheck PASS. repo workflow·프로젝트 의존성·lockfile은 이번 finding 수정에서 변경하지 않았다. 원격 Actions 실행을 뜻하지 않는다.
- 최종 전체 pytest(추가 opt-in 경로 수정 포함): **2022 passed · 26 skipped · 실패 0**, 222.75초. 실제 MySQL 8.4.7 · `DAESINGO_REQUIRE_MYSQL=1` 사용. 최종 JSON/JUnit gate도 **46 passed · skip 0 · xfail 0**, role/scenario 32개·기존 Case 18개·실행 phase 138개 PASS다. 보고서는 작업 전용 OS 임시 디렉터리의 `final-complete.json/xml`에 보관했다.
- skip 26개는 기존 Search 선택 의존성 typer 부재 4 · Case 실영상 없음 2 · eval 로컬 미디어 없음 5 · Recording 실영상/VIDEO_INDEX/연속 원본 opt-in 없음 15다. 신규 회귀에 skip/xfail이 없으며 실제 MySQL 검증을 mock/skip으로 대체하지 않았다.
- boundary PASS(위반 0) · Contract fixture PASS(문서 62 · JSON 26 · 의미 104) · `git diff --check`와 미추적 신규 소스 18개 diff 공백 검사 PASS. Case 코드/fixture/테스트, runtime migration·table, HTTP 매핑, Baseline/Contract/Decision, `uv.lock`은 수정하지 않았다. 커밋·push·PR 생성 없음.
- 최종 검증 뒤 version/port/datadir로 이번 작업 소유임을 확인하고 임시 MySQL 서버를 종료했다. 기존 MySQL service와 `.codex-scratch/`는 변경하지 않았고 JSON/JUnit 증거는 OS 임시 디렉터리에 남겼다.

### 2026-10-08 독립 재리뷰 P2 — ambient 예외의 COMMIT 분류 유입

- Finding: 앞선 cleanup 우선순위 수정의 예외 체인 순회가 현재 `_attempt()`에서 발생하지 않은 과거 DBAPIError까지 선택했다. 실제 MySQL 1205를 처리하는 `except` 안에서 새 API transaction의 COMMIT OK를 proxy로 폐기하면, 독립 observer에 INSERT 1건이 있는데도 `BeforeCommitFailure(lock_wait_timeout)`을 반환했다. 앞선 세 finding의 검증이 이번 결함까지 증명한 것은 아니다.
- 수정: 예외 체인 순회를 제거했다. SQLAlchemy의 공개 `handle_error` event에서 disconnect invalidation/checkin **전**의 COMMIT DBAPIError를 직접 보존한다. `ContextVar`로 이번 시도와 정확한 Connection을 식별하고 COMMIT 구간의 non-query 오류만 기록하므로, 이전 `__cause__`/`__context__`, 다른 connection, commit listener에서 처리된 query 오류는 분류 근거가 되지 않는다. 특정 MySQL 오류 코드에 대한 예외 처리는 추가하지 않았다.
- event observer는 한 번 등록하고 오류를 재작성하거나 로그에 원문을 남기지 않는다. 시도별 token은 `finally`에서 복원하고 connection context 종료 전에 관찰을 끝낸다. body/domain 원래 오류와 직접 발생한 오류를 유지하며, 확인된 COMMIT 성공 > 현재 transaction 원래 오류 > cleanup 오류의 우선순위도 유지한다. cleanup 자체가 DBAPIError인 경우에도 현재 COMMIT 오류를 덮지 못한다.
- RED → GREEN: 기존 구현에서 ambient context/cause 단위 **8 FAIL**, 실제 MySQL 1205 + COMMIT 응답 유실의 cleanup 없음/TimeoutError/DBAPIError **3 FAIL**을 확인했다. 세 실제 재현 모두 최종 오류를 검사하기 전에 observer row 1건을 확인했다. 오류 포착 범위를 보완할 때 처리된 query 오류의 오인도 **1 RED → GREEN**으로 검증했다. 관련 unit/proxy 최종 **66 PASS**(unit 58 + 실제 MySQL proxy 8)다.
- 실제 MySQL **8.4.7 require 모드**의 전체 MySQL 대상 **49 PASS · skip 0 · xfail 0**. 기존 Case MySQL **18개**, 역할/시나리오 **32개 조합**, 수집/선택/실행 **49/49/147 phase**의 JSON/JUnit gate PASS. `-m mysql` 실행 시 별도의 Search collection skip 4개는 선택 의존성 typer 부재이며 MySQL 대상 skip이 아니다.
- 중단된 전체 pytest 프로세스의 정상 종료(exit 0)와 최종 JSON/JUnit을 회수해 결과를 확정했다. **2059 passed · 26 skipped · failed 0 · error 0**, 184.37초다. 실제 MySQL 8.4.7 · `DAESINGO_REQUIRE_MYSQL=1`로 실행한 기존 `ambient-full` 결과를 사용했으며 구현을 다시 시작하거나 pytest를 중복 실행하지 않았다. 이 수치는 재리뷰 이전의 최종 전체 실행 결과이며, 최종 독립 재리뷰에서는 전체 pytest를 재실행하지 않았다. 최종 JSON/JUnit gate 재실행도 **49 PASS · skip 0 · xfail 0**, Case 18개·필수 조합 32개·실행 phase 147개 PASS다.
- 전체 skip 26개: Search의 typer 부재 collection 4 · Case 실영상 없음 2 · eval 로컬 미디어 없음 5(B tier 1 + VL.zip 4) · Recording opt-in 없음 15(영상 지정 없음 8 + VIDEO_INDEX/영상 조건 없음 5 + 연속 원본 pair/placement 없음 2). MySQL 대상과 신규 회귀의 skip/xfail은 없다.
- 최종 정리에서 actionlint 1.7.12 · YAML parse/policy · 5개 workflow run step의 Ubuntu bash 구문/ShellCheck 0.11.0을 다시 실행해 PASS를 확인했다. boundary 위반 0 · Contract fixture 문서 62/JSON 26/의미 104 PASS. `git diff --check` 및 P2 신규 소스의 diff 공백 검사 PASS.
- 임시 MySQL의 version/port/datadir 소유 정보와 `rt02a_test_` schema **0개**를 확인한 뒤 해당 서버만 SHUTDOWN했다. 서버 프로세스 exit 0 · port 13307 닫힘 · PID 파일 제거 · 정상 종료 로그를 확인했다. 기존 Windows MySQL80은 종료 전후 Running/동일 PID/Auto로 유지됐다. 검증은 격리 서버와 작업용 DB에서만 수행했으며 기존 Windows service나 사용자 DB에는 변경 작업을 하지 않았다. 검증용 배포본과 JSON/JUnit 증거는 OS 임시 디렉터리에 남긴다.
- `git status`/`git ls-files`/staged diff로 `recording-baseline-negative-001.json`은 미추적, `.codex-scratch/`는 기존 `.gitignore` 규칙으로 제외되고 두 경로 모두 추적·staging·tracked diff에 없음을 확인했다. 두 경로나 ignore 규칙은 변경하지 않았다. 검증 재개에서는 이 Log의 결과 기록만 갱신했다.
- 이번 수정 파일은 `transactions.py`, transaction unit test, COMMIT proxy integration test, 이 Log뿐이다. schema 격리와 CI gate, Case 소유 코드/fixture/테스트, RT-02(b), Contract/Decision/Baseline, 의존성/lockfile은 변경하지 않았다. `.codex-scratch/`와 `recording-baseline-negative-001.json`도 변경하지 않았다. 검증 증거는 OS 임시 디렉터리의 `ambient-*` 파일에 보관한다.
- 최종 독립 재리뷰 결과(사용자 전달): **RT-02(a) 병합 차단 문제 없음 · P2 수정 재리뷰 통과**. transaction targeted unit **58 passed**, 실제 MySQL 통합 **62 passed**, MySQL 필수 대상 **49 passed · skip 0 · xfail 0**를 확인했다. 기존 Case MySQL **18개**, COMMIT proxy **8개**, 필수 role/scenario **32개 조합**, 실행 phase **147개**를 포함한다. 동일 Engine의 **8-thread 상태 격리** 확인 및 `git diff --check` PASS도 기록했다.
- RT-02(a) P2 재리뷰 당시에는 RT-02(b)가 남아 있었다. P2 수정은 **독립 재리뷰 통과** 판정이었으며, 당시 원격 GitHub Actions 실행·커밋·push·PR 생성은 없었다.

### 2026-10-08 RT-02(b) — Alembic env · runner (최종 독립 리뷰 통과)

**구현 결과**

- `common/db/migrate.py`: frozen registry의 `case → runtime`만 실행한다. 디렉터리 탐색은 미등록/누락 env 검증에만 쓴다. API `upgrade_all(url, *, migrations_root, connect_timeout, read_timeout, write_timeout)`는 명시 URL을 받아 migration engine 하나를 만들고, 모든 DB revision을 읽기 전용 connection으로 사전 검사한 뒤 모듈마다 새 `engine.begin()` connection을 전달한다.
- registry 중복 module/경로/version table, 경로 누락·미등록 env, ini의 version table/script 경로 불일치, script multiple heads를 DB 작업 전에 거부한다. DB unknown revision/multiple version rows는 모든 모듈의 DDL 전에 거부한다. 이것은 version graph 검사이며 수동 schema drift 전체를 탐지하는 기능은 아니다.
- `migrations/runtime/`: env·ini·forward-only template·revision 없는 `versions/`. `upgrade head`는 `runtime_alembic_version`을 생성하지만 0행이다. `job_execution`·usage 등 **Runtime 업무 schema/revision은 추가하지 않았다**(RT-03·RT-07).
- Case Owner 승인에 따라 `migrations/case/env.py`만 최소 수정했다. online `connection → sqlalchemy.url → DAESINGO_MYSQL_URL`, offline `sqlalchemy.url → DAESINGO_MYSQL_URL`. 외부 connection이 있으면 URL 환경변수를 조회하지 않는다. 기존 Case fixture·`test_case_compatibility.py`·revision·metadata·업무 테이블·version table 의미는 그대로다.
- stdin CLI: `python -m daesingo.common.db.migrate --database-url-stdin`. argv에는 credential을 넣지 않는다. API/runner는 URL 환경변수·RuntimeConfig·`.env`·URL 파일·secret manager를 읽지 않는다. 입력 resolver와 배포 실행 위치는 RT-14/RD-12f다. caller도 stdin 공급 과정에서 credential을 argv/로그로 노출하지 않아야 한다.
- CLI는 URL·username·host·query·SQL·경로·exception 원문·traceback을 출력하지 않는다. 고정 메시지만 출력하며 exit는 성공 0/실행 실패 1/사용법·입력 오류 2/interrupt 130이다. terminal의 echo 입력은 허용하지 않는다.

**새 implementation detail · Plan 대비 변경**

- Plan P-1·RT-02(b) 범위대로 구현했다. 새 Architecture Decision, Contract, Accepted Decision, Baseline 값/의미 변경은 없다. authoritative Implementation Plan은 수정하지 않았다.
- process 내부 비재진입 lock으로 중첩/thread 동시 호출을 즉시 거부하고 성공·실패·interrupt 후 상태를 복원한다. **단일 실행 전제이며 cross-process 동시 실행 안전성은 보장하지 않는다.** advisory lock은 이번 범위 밖이다.
- 첫 실패에서 즉시 중단한다. 완료 module은 예외에 안전한 식별자로 남긴다. retry·stamp·downgrade·resume-from 기능은 없다. 앱 startup에서 호출하지 않는다.
- 성공한 module은 재실행 시 version 기준 no-op이다. MySQL DDL implicit commit 때문에 실패한 revision의 부분 DDL은 남을 수 있다. caller의 transaction은 전체 DDL rollback 보장이 아니며, 부분 적용 실패는 검사·복구 없이 자동 재시도하지 않는다. migration은 (a)의 Worker retry helper를 사용하지 않는다.
- timeout은 명시 옵션만 factory에 전달하며 생략 시 driver 기본값을 유지한다. 앱 B-D7 제한을 복사하지 않는다. 기본 migration 경로는 cwd와 독립적이다. 소스 checkout 밖 배포 artifact/wheel의 migration 동봉은 이번 검증 범위가 아니다.
- 기존 MySQL 8.4 workflow/service를 재사용하여 JSON/JUnit gate만 보강했다. (a)의 필수 role/scenario 32개와 기존 Case MySQL 18개를 유지하고 migration check 11개를 추가했다. 의존성·lockfile·workflow·CODEOWNERS 변경은 없다.
- 기존 `mysql_schema_url` fixture를 그대로 재사용하고 임시 migration env 생성 helper는 `tests/migration_support.py`에 뒀다. 새 conftest나 Case fixture 전환 없이 production runner를 직접 호출해 검증한다. Expected files/modules와의 차이는 test helper 배치뿐인 implementation detail이다.

**Owner 확인**

- [유소연 승인 댓글](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/289#issuecomment-6055765577)을 실제 조회했다. `engine.begin()`으로 열린 외부 transaction에서 Alembic이 독자 commit/close하지 않고 caller에게 맡기는 것을 실제 MySQL·SQLAlchemy commit event·새 observer로 확인한다. config URL 테스트는 `%`를 `%%`로 escape하고 percent-encoded 비밀번호도 실제 인증한다. Case에 공통 helper/fixture 전환 의무를 추가하지 않았다.
- 김준영 deferred Audit A: registry/배포 artifact, 단일 실행 전제, 부분 DDL 실패 후 복구, stdin 공급 경계. 배포 시점·secret source는 RT-14/RD-12f에서 정한다.

**구현 단계 RED → GREEN · Verification**

- runner unit RED: 구현 부재 20 failed. 실제 MySQL RED: 외부 connection/config URL 우선순위·runner 부재 12 failed, 기존 환경변수 경로 2 passed. 첫 GREEN: unit+실제 migration 34 passed.
- gate RED: 새 check 11개 제거 시 각각 DID NOT RAISE. 실제 MySQL 전체 보고서에서 항목 제거 테스트도 RED. GREEN: gate unit+실제 보고서 회귀 64 passed. 실제 보고서 회귀는 별도 폐기 schema에서 기존 (a)·Case·(b) MySQL 테스트를 실행하고 각 신규 필수 check의 수집/선택/실행 증거를 제거하여 모두 거부하는지 검사한다.
- 추가 RED→GREEN: `python -m`의 `__main__`과 canonical import가 lock을 따로 만들던 문제를 실제 MySQL로 재현하고 parent package의 process lock을 공유하도록 수정했다. malformed graph의 중복 revision warning도 RED로 재현해 경로를 출력하기 전에 안전한 실패로 바꿨다. 최종 targeted 검증은 **101 passed**다.
- 첫 전체 회귀는 **2124 passed · 2 failed · 26 skipped**였다. 새 테스트 계정명이 MySQL의 32자 제한을 넘긴 fixture 오류와 이를 실행하는 실제 report 테스트의 연쇄 실패였다. 계정명을 줄이고 percent-encoded 비밀번호 실제 인증 테스트를 통과시킨 뒤 아래 최종 전체 회귀로 재검증했다.
- Runtime revision template도 별도 임시 경로에서 실제 revision 생성·downgrade 거부를 확인했다. production `migrations/runtime/versions/`에는 Python revision이 없다.
- 구현 단계 최종 전체 pytest: **2128 passed · 26 skipped · failure/error 0**, 245.34초. 실제 **MySQL 8.4.7**, `DAESINGO_REQUIRE_MYSQL=1`, `-B -X utf8 -m pytest -q -p no:cacheprovider`로 실행했다. 최종 보고서는 OS 임시 경로의 `full-final.txt/json/xml`이다. 전체 pytest는 최종 독립 리뷰에서 재실행하지 않았다.
- 최종 JSON/JUnit gate: **66 MySQL tests · skip 0 · xfail 0 · 198 phases · collection error 0**. 기존 Case **18개**, (a) 필수 check **32개**를 유지하고 (b) check **11개**를 더해 총 **43개**다. 신규 migration 관련 실제 MySQL 테스트는 **17개**이며 기존 (a)·Case를 mock/skip으로 대체하지 않았다. 원격 GitHub Actions 실행 결과는 아니다.
- 전체 skip **26개**는 Search `typer` 선택 의존성 4, Case 로컬 실영상 2, Eval 로컬 B-tier 미디어 1·VL.zip 4, Recording 로컬 영상/명시 opt-in 15다. 모든 개별 node/reason을 OS 임시 경로의 `skips.json` 및 `full-final.txt`에 보관했다. MySQL 대상에는 skip이 없다.
- 빈 별도 schema에서 production runner를 두 번 실행한 후 **새 observer connection**으로 직접 조회했다(`acceptance-state.json`). 테이블은 `cases`, `job_records`, `correction_records`, `analysis_scopes`, `case_alembic_version`, `runtime_alembic_version` 여섯 개다. Case version은 `case_0001` 한 행, Runtime version은 0행이며 공용 `alembic_version`·Runtime 업무 테이블은 없다. 해당 inspection schema는 조회 뒤 정리했다.
- boundary PASS(위반 0), Contract fixture PASS(문서 62·JSON 26·의미 104), actionlint PASS, YAML/MySQL require 정책·Ubuntu bash syntax·ShellCheck PASS(기존 workflow run step 5개).
- `git diff --check` PASS. authoritative Plan·Case fixture/revision·기존 `test_case_compatibility.py`·workflow는 변경하지 않았다.
- 증거는 OS 임시 경로 `C:/Users/cheol/AppData/Local/Temp/rt02b-20261008/`에 보관한다. `.codex-scratch/`·`recording-baseline-negative-001.json`은 변경하지 않았다.

**최종 독립 리뷰 결과 — 사용자 전달**

- **병합 차단 문제 없음**. 완료 처리·커밋·PR 생성 가능 판정을 받았다. 아래 수치는 사용자가 전달한 최종 독립 리뷰 결과이며 이번 문서 갱신에서 테스트를 재실행한 결과가 아니다.
- runner·gate·MySQL integration·Case **163 passed**. 실제 MySQL 필수 대상 **66개 · skip 0 · xfail 0**, 기존 Case MySQL **18개**를 포함한다.
- 필수 check **43개**, 실행 phase **198개**. 실제 보고서에서 신규 check의 수집·선택·실행 증거를 제거한 **33가지 모두 gate가 거부**했다.
- actionlint·YAML·Ubuntu bash·ShellCheck·boundary·Contract·diff **PASS**.
- 전체 pytest **2128 passed / 26 skipped**는 위 구현 단계 결과이며 최종 독립 리뷰에서는 전체 pytest를 재실행하지 않았다.
- Case env 최소 수정의 Owner 확인 근거는 [Case Owner 승인 댓글](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/289#issuecomment-6055765577)이다.
- 원격 GitHub Actions는 **PR 생성 후 확인 예정**이다. RT-02(b) PR 번호·merge SHA는 `pending`을 유지하며, Task 마지막 PR의 본문에는 `Closes #289`를 사용한다.

### 남은 위험 · 비차단 후속 후보

- RT-02 구현과 최종 독립 리뷰는 완료됐으며 원격 CI 확인은 PR 생성 후 진행한다. 후속 Runtime domain transaction·heartbeat lifecycle·HTTP probe budget/E2E는 후속 Task 범위로 남아 있으며, RT-02 완료가 배포 준비 완료를 뜻하지 않는다.
- caller가 외부 작업이나 transaction 탈출을 callback에 넣지 않아야 한다. unknown COMMIT의 재실행 안전성은 각 domain callback이 stable identity/read 조건으로 검증해야 하며 이번 helper만으로 모든 중복을 차단하지 않는다.
- 로컬 gate는 검증됐지만 원격 GitHub Actions 결과는 아직 없다. Case의 의도된 테스트 rename/parametrization 변경 시 gate의 기존 실행 목록도 함께 검토해야 한다.
- cross-process runner 중첩과 부분 DDL 실패의 자동 복구를 지원하지 않는다.
- 테스트 계정 생성 후 GRANT 실패·interrupt에서도 `DROP USER`가 실행되도록 테스트 cleanup 보호 범위를 넓히는 개선은 **비차단 후속 후보**다. production migration 차단 문제는 아니며 이번 문서 갱신에서 코드·테스트를 수정하지 않는다.

---

## RT-03 — `job_execution` schema · queue repository

Status: IN_PROGRESS · Issue: #290 · Audit: A

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| pending (로컬, PR 미생성) | RT-03(a) schema · enqueue · read port — `Refs #290` | pending |

### 구현 결과

- `migrations/runtime/versions/0001_job_execution.py` → `runtime_0001`: `job_execution` 하나가 실행 원장과 queue를 맡는다. 기존 RT-02 runner `case → runtime`을 그대로 사용하며 모듈 간 FK는 없다. claim index `(status, available_at, execution_id)`, `job_id` index, UNIQUE `(job_id, attempt)`, 양수 attempt·닫힌 status CHECK를 둔다.
- `common/jobs/{schema,repository,read_port}.py`: `enqueue(conn, job_records, trace_id) -> list[str]`는 attempt 1 `QUEUED`를 생성한다. 호출자의 열린 transaction이 필요하며 commit·rollback·close·retry를 하지 않는다. batch metadata 전체를 쓰기 전에 검증하고 한 INSERT로 기록하여 중복이 있으면 해당 statement의 새 row 전체가 거부된다. 호출자 transaction의 실패 처리는 호출자가 소유한다.
- `read_executions(conn, job_ids) -> list[dict]`: 요청한 Job의 모든 attempt를 `job_id, attempt` 순서로 반환한다. 기존 JobExecution validator를 통과한 JSON 호환 Contract projection이며 대표 execution 선택은 case 소유다. 내부 column은 SELECT allowlist로 제외하고 `usage_refs=[]`를 반환한다. usage_refs column·usage ledger는 만들지 않았다.
- claim_one·finish·Worker·heartbeat/cancel·retry attempt 생성·usage projection·HTTP API는 구현하지 않았다. RT-03 전체 완료나 Issue close가 아니다. 커밋·push·PR 생성 없음. 후속 PR 본문 연결은 `Refs #290 (RT-03(a))`를 사용한다.

### Plan 대비 변경

- Plan §9가 나눈 (a) schema/enqueue/read port만 구현했다. (b)의 claim/finish acceptance는 후속 검증 대상이다. authoritative Implementation Plan은 변경하지 않았다.
- RT-02 migration acceptance의 빈 Runtime schema 기대값을 `job_execution`/`runtime_0001`로 갱신했다. 미래 revision 테스트는 새 첫 revision을 parent로 잇는다. 기존 Case-owned fixture·revision·repository·test 파일과 RT-02 helper/runner 동작은 변경하지 않았다.
- 기존 MySQL JSON/JUnit gate에 RT-03(a) 필수 check 5개를 추가하고 실제 보고서 누락 회귀에 jobs 경로를 포함한다. workflow·의존성·lockfile 변경 없는 검증 보강이다. 실행 세부 계획은 `docs/superpowers/plans/2026-10-08-rt03a.md`다.
- Contract·Accepted Decision·Baseline 값/의미 변경 없음. 다른 Owner에게 새 의무를 만들지 않았다.

### 새 implementation detail

- 내부 column 이름: `available_at`, `lease_owner`, `lease_expires_at`, `heartbeat_at`, `cancel_requested_at`, `case_applied_at`, `trace_id`, `kind`, `case_id`. lease/heartbeat/중단/반영 시각은 최초 enqueue에서 null이다. `available_at=queued_at`이며 첫 attempt에는 backoff가 없다.
- UTC `DATETIME(6)` 저장. enqueue 시 MySQL `UTC_TIMESTAMP(6)`를 한 번 읽어 batch의 queued/available 시각을 일치시킨다. session timezone이나 API/container 시계에 의존하지 않는다. read에서 UTC aware 시각으로 변환한다. B-L6의 lease SQL은 이번에 구현하지 않았다.
- `produced`는 native JSON `ContractRef[]`; Contract envelope/version은 read에서 구성한다. ID는 기존 Case storage와 같은 `ascii_bin`을 사용한다. `job_id` 191, `case_id`/`execution_id`/`trace_id`/`lease_owner` 128, `kind` 64, status 16, failure_kind 191자다. consumed metadata의 빈 값/길이/ASCII 등을 입력에서 검증한다. kind registry를 import하거나 등록 여부를 enqueue에서 거부하지 않는다.
- execution ID는 `exec_`+UUID hex다. 반환 순서는 입력 순서이며 DB unique 오류는 그대로 전파한다. unknown COMMIT 뒤 무조건 재호출해도 성공하는 idempotent callback이 아니므로 composition root의 domain read 조건이 필요하다(RT-02 helper와 같은 경계).
- frozen migration은 live metadata를 import하지 않는다. 미래 metadata 수정으로 과거 revision이 바뀌지 않게 한다.

### Owner 확인 포인트

- 김준영 deferred Audit A: 내부 column 명칭·길이, UTC 저장/Contract 변환, enqueue 반환 ID 순서와 batch atomicity, read port가 모든 attempt를 반환하는 경계.
- claim/finish는 (b)에서 기존 전이표·조건부 UPDATE·lease owner·B-W3/B-L2/B-L6·RC locking을 검증해야 한다. 이번 schema의 lease column이 존재하는 것을 해당 lifecycle 구현 완료로 해석하지 않는다.

### Verification

- 실제 MySQL 8.4.7 별도 임시 서버/폐기 schema를 사용한다. 기존 검증 서버가 응답하지 않아 기존 MySQL 배포 파일과 임시 libaio/libnuma로 준비했다. 시스템 설치나 사용자 DB 변경은 하지 않았다. `DAESINGO_REQUIRE_MYSQL=1`로 실행한다.
- schema/enqueue RED **15 failed**(table/repository 부재) → GREEN **15 passed**. read port RED **10 failed**(read_port 부재) → 신규 jobs 합계 **25 passed**. 첫 RED 수집 전 잘못된 transaction helper import를 바로잡았다. 수집 오류는 기능 RED 근거로 세지 않았다.
- gate RED: 신규 필수 check 5개 각각을 뺐을 때 **DID NOT RAISE 5건** → gate unit·jobs·migration targeted GREEN **109 passed**. migration 기대값 갱신 전 **4 failed / 37 passed**, 갱신 후 위 targeted GREEN에 포함된다.
- 독립 리뷰 P2: 기존 Case가 허용하는 ASCII `case_id`의 끝 공백/탭을 enqueue가 `rstrip()` 검사로 새로 거부했다. 실제 `CaseAggregate`·`issue_job`·`MySQLCaseRepository`를 거친 회귀 **2 failed**를 확인하고 추가 제한만 제거했다. 신규 jobs 실제 MySQL 전체 **27 passed**. 독립 재리뷰에서 해당 P2 해결·추가 actionable finding 없음(최종 전체 회귀 조건부 통과)을 확인했다.
- 첫 전체 회귀 **2227 passed · 26 skipped · 1 failed**: 실제 보고서 생성용 하위 pytest에서 production runner가 한 번 `migration: execution_failed`로 실패했다. 예외 원문을 숨기는 runner의 정책은 바꾸지 않았다. OS 임시 진단 plugin으로 실패 코드/context 유형만 수집하며 해당 report 회귀와 migration test를 다시 실행했고 **2 passed**(실제 하위 MySQL 회귀·신규 check 누락 거부 포함), 오류는 재현되지 않았다. 최초 실패의 원인은 확인하지 못했으며 transient 원인이라고 단정하지 않는다.
- 최종 전체 pytest **2230 passed · 26 skipped · failure/error 0**, 391.40초. Case ID 수정까지 포함한 전체 재실행이며 `DAESINGO_REQUIRE_MYSQL=1`, `-B -X utf8 -m pytest -q -p no:cacheprovider`를 사용했다. `full-final.txt/json/xml`에 증거를 저장했다.
- MySQL JSON/JUnit execution gate **PASS — 실제 MySQL 8.4.7 · 93 tests · skip 0 · xfail 0 · 279 phases · collection error 0**. 기존 Case MySQL **18개**, 신규 jobs **27개**를 포함하며 필수 role/check **48개**를 확인했다. 실제 보고서 회귀는 기존 migration check 11개와 신규 jobs check 5개를 각각 제거해 누락을 거부한다. mock·skip·xfail로 대체하지 않았다.
- 전체 skip 26개는 Search 선택 의존성 `typer` 4개, Case 로컬 영상 2개, Eval 로컬 미디어/VL.zip 5개, Recording 영상/명시 opt-in 15개다. 개별 node/reason은 `skips.json`, 집계는 `summary.json`에 보관한다. MySQL 대상에는 skip이 없다.
- boundary PASS(위반 0), Contract fixture PASS(문서 62 · JSON 26 · 의미 104), `git diff --check` PASS. 원격 GitHub Actions 실행·PR 생성은 하지 않았다. 독립 source 재리뷰는 P2 해결 뒤 추가 actionable finding 없음이며, 최종 전체 회귀·gate는 구현자가 위 수치로 실행 검증했다.
- 변경 파일 15개 목록은 OS 임시 `changed-files.txt`다. HEAD·index는 시작 상태 그대로이며 커밋·push 없음. `recording-baseline-negative-001.json`은 미추적 상태와 SHA-256 `27BA6EE8F681F2DF93C4E147589DD932D4632D71631A77EDE194317D42247D99`를 유지했다. authoritative Plan·Contract·Decision·Baseline·Case-owned 파일은 변경하지 않았다.
- 증거 경로: OS 임시 `C:/Users/cheol/AppData/Local/Temp/rt03a-20261008/`. 최종 검증 뒤 이번에 시작한 임시 MySQL 서버만 종료하며 증거와 배포 파일은 보관한다.

### 2026-10-09 독립 리뷰 P2 — 필수 MySQL parameter 누락 거부

- 기존 gate는 `(role, scenario)` 집합만 확인했다. `read_states` 6개 중 한 상태 또는 `enqueue_duplicate` 2개 중 한 경로를 수집·선택·실행·JUnit에서 함께 제거해도 같은 family의 다른 parameter가 남으면 통과했다. 기존 검증은 family 전체 누락을 검사했으며 개별 parameter 필수 실행까지 보장하지 못했다.
- RED: 개별 parameter 누락 unit 검사 **8 failed / 48 passed**. 이전 실제 MySQL `full-final.json/xml`에서 `FAILED`와 중복 `[True]`를 각각 제거해도 JSON/JUnit gate가 통과하는 것을 별도로 재현했다. 해당 RED JSON/XML과 출력은 OS 임시 `C:/Users/cheol/AppData/Local/Temp/rt03a-p2-20261009/`에 보관한다.
- 수정: 기존 필수 check 48개와 Case MySQL inventory는 유지하고 별도 필수 `(role, scenario, parameter)` 8개를 추가했다. 기존 pytest parameter에 명시적 `mysql_check(..., parameter=...)` marker를 붙여 harness가 식별자를 기록한다. 상태는 6개 enum 값, 중복 경로는 `separate_batch`/`same_batch`다. gate 정책은 pytest 함수명이나 node ID 전체/suffix를 파싱하지 않는다. node ID와 JUnit 주소는 수집·선택·실행 증거를 연결하는 데만 사용한다.
- 기존 선택 집합 일치·setup/call/teardown 완전성·JUnit 대조를 그대로 유지한다. 수집에서 parameter 전체가 사라지면 새 필수 tuple 검사가, 선택/실행/JUnit 중 한 곳만 사라지면 기존 연결 검사가 거부한다.
- 신규 mutation은 8개 parameter × 수집·선택·setup·call·teardown·전체 JSON/JUnit·JUnit의 7가지 누락, 총 **56개**다. 나머지 parameter를 남긴 채 하나씩 제거하며 실제 MySQL 보고서에도 동일하게 적용한다. 기존 family/migration 누락 검사도 유지한다.
- 구현 단계 targeted gate GREEN **124 passed**, 10.70초. 첫 일반 sandbox 실행의 4개 실패는 SQLAlchemy DLL 접근 거부였으며, sandbox 밖 재실행으로 위 결과를 확인했다. 테스트 의미나 skip 조건을 바꾸지 않았다.
- 구현 단계 실제 MySQL 8.4.7 targeted **93 passed / 13 deselected**, 120.75초. 13개는 선택 범위 밖의 비-MySQL Case parameter다. JSON/JUnit gate **PASS — 93 tests · skip 0 · xfail 0**이며 `DAESINGO_REQUIRE_MYSQL=1`로 실행했다. 실제 하위 보고서의 개별 parameter 누락 mutation **56/56 거부**를 `mysql-targeted/test_actual_report_rejects_eac0/parameter-mutations.json`으로 확인했다. 기존 migration/jobs family 누락 검사 16개도 통과했다.
- 구현 단계 최종 전체 pytest **2286 passed · 26 skipped · failure/error 0**, 329.69초. `DAESINGO_REQUIRE_MYSQL=1`, 실제 MySQL을 연결한 채 `-B -X utf8 -m pytest -q -p no:cacheprovider`로 실행했다. skip 26개는 기존 비-MySQL 선택 의존성/로컬 미디어 검사다. `full-final.txt/json/xml`에 증거를 저장했다.
- 구현 단계 전체 실행의 JSON/JUnit gate도 **PASS — MySQL 93 collected/selected · 279 passed phases · skip 0 · xfail 0 · collection error 0**, jobs 27개·Case 18개를 확인했다. 전체 회귀가 생성한 실제 하위 보고서에서도 **56/56 parameter mutation 거부**, 각 필수 parameter당 7개 거부를 확인했다(`full-final/test_actual_report_rejects_eac0/parameter-mutations.json`, 집계 `summary.json`).
- 구현 단계 boundary **PASS — 위반 0**, Contract fixture **PASS — 문서 62 · JSON 26 · 의미 104**, 최종 `git diff --check` **PASS**. 당시 독립 source 재리뷰는 추가 차단/비차단 finding 없이 통과했다. 위 구현 단계의 실제 테스트 실행 수치는 구현자가 검증했다.
- 이번 P2 변경은 gate script, harness, marker 설명(`pyproject.toml`), jobs MySQL test 2개의 parameter marker, gate unit/실제 보고서 mutation test, 이 Log의 **8개 파일**로 한정한다. schema/enqueue/read port source와 migration revision의 수정 전후 SHA-256은 동일하다. 검증 증거는 OS 임시 `C:/Users/cheol/AppData/Local/Temp/rt03a-p2-20261009/`에 보관한다.
- schema·enqueue·read port production 동작, migration runner, Case-owned 파일, Contract·Decision·Baseline 의미 변경 없음. 동시 enqueue 추가 실험과 schema assertion 확대는 포함하지 않았다. RT-03 `IN_PROGRESS`, PR 연결 `Refs #290`을 유지하며 커밋·push·PR 생성은 하지 않는다.
- 검증 뒤 port `13310`·datadir `/tmp/rt03a-p2-20261009/data/`·version `8.4.7`로 작업 소유를 확인하고 이번 임시 MySQL 서버만 종료했다(exit 0). 기존 사용자 변경과 `recording-baseline-negative-001.json`을 보존했으며 보호 JSON의 SHA-256·HEAD·index는 시작 상태와 동일하다. 증거 파일과 임시 배포 파일은 보관한다.

### RT-03(a) 독립 재리뷰 — P2 해소 및 검증 주체 구분

- 독립 재리뷰에서 이전 필수 MySQL parameter 누락 P2가 해소됐으며, RT-03(a)에 남은 병합 차단 문제가 없음을 확인했다.
- 재리뷰에서 targeted gate test를 직접 재실행하여 **124 passed**를 확인했다. 보존된 실제 MySQL JSON/JUnit 보고서를 대상으로 필수 parameter 8개 × 누락 위치 7개의 개별 누락 실험을 직접 재실행했고 **56/56 거부**를 확인했다.
- 재리뷰에서 boundary·Contract fixture·`git diff --check`를 직접 실행하여 모두 **PASS**를 확인했다.
- 전체 pytest **2286 passed / 26 skipped**와 실제 MySQL **93 passed · skip 0 · xfail 0**는 위 구현 단계에서 실행한 결과다. 재리뷰에서는 보존된 출력·JSON/JUnit 증거를 확인했으며, 전체 pytest나 실제 MySQL suite를 새로 실행한 결과로 기록하지 않는다.
- 이 판정은 RT-03(a) 범위다. RT-03은 **IN_PROGRESS**, 이번 PR 연결은 **Refs #290**을 유지한다. 최초 migration 실패 **104.502초**와 원인 미확정 위험은 아래 남은 위험 기록 그대로 유지한다.

### 남은 위험

- (b)의 동시 claim/finish·lease·locking과 RT-04 이후 lifecycle은 아직 검증되지 않았다. usage_refs는 RT-07 전까지 의도적으로 빈 목록이다.
- MySQL migration DDL의 부분 적용 실패는 runner 자동 retry/rollback으로 복구되지 않는다. 기존 RT-02 운영 경계 그대로다.
- ID/metadata column 상한과 UTC 저장 규칙을 후속 writer도 지켜야 한다. unknown COMMIT 결과의 idempotency와 command 원자성 실제 HTTP 배선은 후속 composition에서 다룬다.
- 첫 전체 회귀의 단발 migration 실패 검사는 하위 JUnit(`rt03a-20261008/full/test_actual_report_rejects_eac0/mysql.xml`)에 **104.502초**로 기록돼 있다. 2026-10-09 해당 testcase의 `time="104.502"`를 직접 확인했다. 원인은 미확정이며 network·timeout·파일 접근 등 특정 원인으로 단정하지 않는다. 실패를 skip/mock/retry 코드로 우회하지 않았고 진단 재실행은 통과했다. 이번 P2를 이유로 migration runner 등 production 동작은 변경하지 않았다.

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
