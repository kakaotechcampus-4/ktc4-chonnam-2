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
| 실행 원장 schema · enqueue · read model | `runtime_0001` · 내부 시각 표식 column · ascii_bin ID · DB UTC microseconds · 단일 batch INSERT · Contract allowlist projection · usage_refs 비저장 | RT-03(a) · PR #332 · `7872c7aa989d0907e5a71608136de5196c230ac0` | 아래 RT-03 · `common/jobs/` |
| claim receipt · unknown COMMIT 복구 | nullable 내부 `claim_token`의 `runtime_0002` · 공개 호출의 ID/token 고정 · 같은 PK durable receipt만 복구 · Contract validation 입력 allowlist | RT-03(b) · 로컬, PR 미생성 | 아래 RT-03(b) · `common/jobs/repository.py` |
| application/worker UTC checkout | connection 생성·checkout에서 UTC session 복원 · B-L6 `NOW(6)` 유지 | RT-03(b) · 로컬, PR 미생성 | 아래 RT-03(b) · `common/db/engines.py` |
| attempt observer · claim latency | sanitized outcome/duration · transaction 시작 → COMMIT acknowledgement · checkout/checkin/retry 대기 제외 · 관측 실패와 retry 분리 | RT-03(b) · 로컬, PR 미생성 | 아래 RT-03(b) · `common/db/transactions.py` |
| Worker invocation · T1 replay | 불변 kind registry · execution context/result · claim/handler/T1 분리 · 결과 보존 재시도 · durable terminal facts 재조회 | RT-04(a) · 로컬, PR 미생성 · `Refs #291` | 아래 RT-04 · `worker/composition.py` · `common/jobs/worker_loop.py` |
| heartbeat lifecycle · commit fencing | 실행별 전용 thread/NullPool connection · monotonic fixed-rate/skip · 내부 ownership fence · B-D8 매 시도/COMMIT 직전 guard · BaseException 소유 thread 전파 | RT-05(a) · 로컬 미커밋 · `Refs #292` | 아래 RT-05 · `common/jobs/heartbeat.py` · `common/db/transactions.py` |
| `DECIMAL` precision/scale (Plan P-10) | `DECIMAL(65,30)` · 정수 35/소수 30자리 · Decimal/문자열 bind · 초과 precision/scale 거부 | RT-07(a) · PR #349 · `fa5a0fcbd5f88e70e7a4c9ba0a457b42a65a27a1` | 아래 RT-07 · `common/usage/amount.py` |
| usage identity · Final replay · 참조 | 양 table `usage_id` 단독 PK · FK 없이 snapshot 보존 · 고정 ID INSERT/1062 locked read · 동일 snapshot no-op/상이하면 conflict · caller tx | RT-07(a) · PR #349 · `fa5a0fcbd5f88e70e7a4c9ba0a457b42a65a27a1` | 아래 RT-07 · `common/usage/{schema,repository}.py` |
| UsageSink · explicit finalize | execution별 sink · DB-only runner 주입 · 고정 begin identity/snapshot · locked read/조건부 전이 · append+FINALIZED 원자성 · sanitized UsageError | RT-07(b) · PR #353 · `95dfff8b3ba11f95b76a168dd18ccc1573c02b39` | 아래 RT-07(b) · `common/usage/{port,sink}.py` |
| cancel 잠금 · signal · 지연 측정 | 전체 입력 검증 후 sorted job별 unique index 순회 잠금 · 최초 marker 유지 · heartbeat commit 후 signal 한 번 전달 · DB 요청→terminal/추가 monotonic checkpoint→commit 지연 | RT-05(b) · 로컬 미커밋 · `Refs #292` | 아래 RT-05(b) · `common/jobs/cancel.py` |
| STALE sweep · retry · hook lifecycle | 후보 scan 후 execution별 짧은 tx · PK SKIP LOCKED 재확인 · retry ID 고정/unknown COMMIT 복구 · startup gate + 독립 주기 thread · connection 반환 뒤 immutable hooks | RT-06(a) · 로컬 미커밋 · `Refs #293` | 아래 RT-06 · `common/jobs/{sweep,retry_policy}.py` |
| attempt별 queue 대기 관측 | claim receipt 내부 queued_at · DB queued_at→started_at · INITIAL/RETRY 묶음 · heartbeat 시작 뒤 sink 호출 | RT-06(a) · 로컬 미커밋 · `Refs #293` | 아래 RT-06 · `repository.py` · `worker_loop.py` |
| STALE 관측 · fatal hook 비노출 | DB STALE ended_at − 마지막 heartbeat_at · post-commit 측정/누락 fallback 없음 · fatal cleanup 후 process 경계에서 원문 비노출·고정 코드 1 | RT-06(a) 후속 P2 · 로컬 미커밋 · `Refs #293` | 아래 RT-06 · `sweep.py` · `worker/__main__.py` |
| T2 재전달 · Case adapter · kill 복구 | 비잠금 후보/receipt 조회 → 후보별 기존 T2 · Case→Runtime 잠금 · startup admission gate · 주입형 Case 8-8 bridge · 실제 spawned process kill/DB 상태 관측 | RT-06(b) · PR/merge SHA pending · `Refs #293` | 아래 RT-06(b) · `common/jobs/redelivery.py` · `worker/case_reflector.py` |
| PR CI job timeout | `python-tests` test job 30분 · nested 900초 및 strict gate 유지 | 로컬 미커밋 · `Refs #368` · PR/merge SHA pending | 아래 「Issue #368 — CI 실행시간·timeout 후속」 |
| type checker 도구 (Plan RT-15) | mypy 2.4.1 · Runtime 네 경로 · 미타입 본문 검사 · Linux/Windows 분기 검사. Ruff 0.17.3과 quality extra/uv.lock 고정 | RT-15(a) · PR #483 · `e3fec617dc75b2cf21141a110bd8e81e816970b8` | [RT-15(a) Notes](./rt15a-runtime-quality.md) |
| Runtime Python import 검사 | 기존 문자열/Contract 검사를 보존하고 AST로 common 6경로 → domain 7개, domain → api/worker 검사. alias·상대 import·정확한 namespace 비교 | RT-15(b) · PR #484 · `6b116e4a1317dc8e5c13e34b05481107bc00ca21` | [RT-15(b) Notes](./rt15b-import-boundaries.md) · ownership §6 |
| produced object 저장 · T1 receipt | `runtime_0005` · 해석 없는 JSON snapshot · execution/ordinal 무ID ref · caller-owned append batch · terminal과 같은 tx · COMMIT 불명 payload 검증 · 기존 ProducedReader callable | RT-10(a) · PR/merge SHA pending · Refs #297 (RT-10(a)) | [RT-10(a) note](./rt10a-produced-store.md) |
| secret scan 배치 — PR gate 편입 여부 (Plan RT-15) | Gitleaks 8.30.1·archive/실행 파일/rules SHA-256 고정, 현재 Git 파일+전체 HEAD ancestry. develop 수동/배포 선행, A01/A02 정확한 지문 예외, 일반 PR 편입 보류(cold CI 비용 미측정) | RT-15(c) · 미커밋 · 원격 CI pending | [RT-15(c) Notes](./rt15c-secret-scan.md) |
| Compose smoke의 CI 편입 여부 (Plan RT-13) | opt-in local smoke; 일반 PR에는 기존 pytest의 구조/negative-control 검사. 실제 Docker 결과와 구분 | RT-13(a) · PR pending | [RT-13(a) Notes](./rt13a-docker-compose.md) |
| local image/migration/media/secret 경계 | single image · 10001:10001 · `/media` named volume · read-only host env · 기존 stdin migration CLI · success dependency | RT-13(a) · PR pending | [RT-13(a) Notes](./rt13a-docker-compose.md) |
| API factory · readiness · safe telemetry | dedicated NullPool + deadline/in-flight 공유 · metadata-only mount · bounded daemon events · workers=1 CLI | RT-08(a) · PR #366 | 아래 RT-08 · `api/{app,composition,errors,health,storage,events,__main__}.py` |
| API Case 생성·조회 transaction | 요청별 CaseStore(conn, executions) · 생성 commit 후 공개 read · postcommit read 실패 500 · bounded event만 사용 | RT-08(b) · PR #373 · `3ea6f09084f7396eb980f53d5afa69da7043c83c` | 아래 RT-08(b) · `api/{composition,routes_cases,routes_view}.py` |
| API command/enqueue transaction | 실제 수신 byte 제한 · opaque JSON · Case 저장+append batch enqueue 한 commit · append/응답 표 status · 요청 trace 전달 | RT-08(c) · PR #375 · `da7e5e613b21fda02211aa9f47f8c61b94835d13` · `Refs #295 (RT-08(c))` | 아래 RT-08(c) · `api/{composition,routes_commands,app}.py` |
| API 중단 transaction | Case가 정한 cancelled_job_ids → 같은 Connection의 request_cancel · Case 선잠금 · ACK 뒤 응답 · 기존 retry/오류 의미 유지 | RT-08(d) · 미커밋 · `Refs #295 (RT-08(d))` | 아래 RT-08(d) · `api/composition.py` |
| 첫 비동기 E2E 테스트 조립 | HTTP 생성 Case + 실패 검색 fixture · RETRY_SEARCH · 별도 Worker thread/engine · 기존 CaseReflector · T1/T2 barrier와 독립 plain read | RT-09 · 미커밋 · `Refs #296 (RT-09)` | 아래 2026-10-18 RT-09 후속 · `tests/async_e2e_support.py` |
| 저장 FrameRef HTTP · 승인된 DB 경계 | semaphore2 획득 뒤 짧은 caller tx에서 Recording 소유+이미지 복원 · 반환 뒤 header/bytes · 취소된 read도 cleanup 후 permit 반환 · bounded wait/latency/count 관측 | RT-11(b) · 미커밋 · Refs #298 (RT-11(b)) | [RT-11(b) note](./rt11b-frame-read.md) |
| staging/temp cleanup · filesystem lease | 명시 root·mtime 나이·no-follow/handle 삭제·shared producer/exclusive scan·startup/주기 thread·stop/join·cleanup count/bytes/privacy | RT-12(a) · PR/merge SHA pending · Refs #299 (RT-12(a)) | [RT-12(a) note](./rt12a-cleanup.md) |
| IncidentClip 순차 원본 선택 | Case 명시 VIDEO tuple → 공개 Recording plural resolve; Fine 사용 stream provenance/전체 선택 ownership 검증, T1/T2 의미 유지 | #486 §8 · 미커밋 · PR/merge pending | [Multi-source IncidentClip Notes](./multisource-incident-clip.md) |

## Baseline revisit 후보

| Baseline ID | 관측 | Evidence | 처리 (workflow §10 → §11) |
| --- | --- | --- | --- |
| 없음 | — | — | — |

## Owner 확인 기록

Plan §12.3에서 「멈추고 확인」에 해당해 Owner에게 확인한 건만 남긴다.

| 날짜 | Task · PR | 확인 내용 | 확인처 | 결과 · 기록 위치 |
| --- | --- | --- | --- | --- |
| 2026-10-08 확인 | RT-02(b), PR 미생성 | Case env 입력 우선순위 최소 수정·외부 transaction 참여. Case fixture/revision/metadata/version table 의미 변경 없음, 공통 helper 의무 없음 | 유소연 @yuusoyeon | [Issue #289 승인 댓글](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/289#issuecomment-6055765577). Consult 결과이며 Case env는 향후 PR에서 Owner 리뷰 예정 |
| 2026-10-14 직접 조회 | RT-07(c), PR #360 | Search에는 durable Run 저장소가 없고 최초 영속화는 T1 produced. 예정 Run ref 대조로 복구하며 명시적 DIRECT_NO_RUN 허용 | 김준영 @flosure23 · 서어진 @kong2488-star · 정철원 최종 확인 | [Runtime 답변](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/294#issuecomment-6145102027) · [Search 답변](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/294#issuecomment-6148574716) · [최종 확인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/294#issuecomment-6150512406). 이 세션은 댓글을 작성하지 않고 직접 읽었다 |
| 2026-10-27 직접 조회 | RT-13(a), PR 미생성 | RD-12a/g local slice와 Compose health/grace M4 provisional 승인. timeout 5s는 B-H3에서 DERIVED; interval10s/retries3/start_period10s/grace30s는 CONSERVATIVE_DEFAULT | Runtime/Ops Owner 김준영 @flosure23 | [결정 요청](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/300#issuecomment-6430017764) · [Owner 승인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/300#issuecomment-6433879506). Issue 본문/최신 두 댓글 직접 조회; 댓글 작성 없음 |

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

Status: DONE · Issue: #290 · Audit: A

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| [#332](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/332) | RT-03(a) schema · enqueue · read port — `Refs #290` | `7872c7aa989d0907e5a71608136de5196c230ac0` |
| pending | RT-03(b) claim · worker terminal finish · UTC session · durable receipt · P2 수정/독립 재리뷰 통과 — `Closes #290` | pending |

### 구현 결과

- `migrations/runtime/versions/0001_job_execution.py` → `runtime_0001`: `job_execution` 하나가 실행 원장과 queue를 맡는다. 기존 RT-02 runner `case → runtime`을 그대로 사용하며 모듈 간 FK는 없다. claim index `(status, available_at, execution_id)`, `job_id` index, UNIQUE `(job_id, attempt)`, 양수 attempt·닫힌 status CHECK를 둔다.
- `common/jobs/{schema,repository,read_port}.py`: `enqueue(conn, job_records, trace_id) -> list[str]`는 attempt 1 `QUEUED`를 생성한다. 호출자의 열린 transaction이 필요하며 commit·rollback·close·retry를 하지 않는다. batch metadata 전체를 쓰기 전에 검증하고 한 INSERT로 기록하여 중복이 있으면 해당 statement의 새 row 전체가 거부된다. 호출자 transaction의 실패 처리는 호출자가 소유한다.
- `read_executions(conn, job_ids) -> list[dict]`: 요청한 Job의 모든 attempt를 `job_id, attempt` 순서로 반환한다. 기존 JobExecution validator를 통과한 JSON 호환 Contract projection이며 대표 execution 선택은 case 소유다. 내부 column은 SELECT allowlist로 제외하고 `usage_refs=[]`를 반환한다. usage_refs column·usage ledger는 만들지 않았다.
- RT-03(a) 당시 claim_one·finish·Worker·heartbeat/cancel·retry attempt 생성·usage projection·HTTP API는 구현하지 않았다. 당시 RT-03 전체 완료나 Issue close가 아니었고 PR 연결은 `Refs #290 (RT-03(a))`였다. claim/finish 구현과 최종 판정은 아래 RT-03(b) 기록을 따른다.

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

### RT-03(b) — 승인된 설계의 구현 (2026-10-09)

- `feature/runtime-job-claim-finish`, 기준 HEAD는 RT-03(a) PR #332 merge SHA다. 설계 승인 뒤 직접 TDD로 구현했다. 구현 당시 독립 재리뷰 전까지 `IN_PROGRESS`였고 마지막 PR의 `Closes #290` 여부는 미확정이었다. 최종 판정은 아래 독립 재리뷰 기록을 따른다. 커밋·push·PR 생성은 하지 않았다.
- `claim_one(engine, worker_id, *, lease_duration_sec, logger=None) -> ClaimedExecution | None`: 공용 RC/UTC engine과 RT-02 Worker helper를 사용한다. covering ID SELECT `(status, available_at, execution_id)` + `LIMIT 1 FOR UPDATE SKIP LOCKED`, 조건부 RUNNING/lease UPDATE, PK snapshot, 확인된 commit 후 frozen DTO 반환이다. callback에는 INSERT·handler·외부 I/O가 없다. 기본 lease 값은 기존 WorkerSettings에서 받고 설정 주입을 허용한다.
- 공개 호출마다 token을 만들고 최초 선택 ID와 함께 재시도 사이에 유지한다. 첫 선택 뒤 재시도는 같은 PK의 locking read로 미해결 transaction을 기다리고 durable 상태를 확인한다. 자기 token/owner의 RUNNING이면서 lease가 유효하면 기존 snapshot을 반환하며 lease를 연장하지 않는다. rollback되어 QUEUED/token null이면 같은 row의 eligibility를 재확인한다. token/owner 불일치·terminal·만료·missing/eligibility 상실은 `ClaimLostError`이며 빈 queue로 바꾸거나 다른 row를 claim하지 않는다. helper 소진은 기존 `outcome_unknown`을 보존한다.
- `finish(conn, execution_id, owner, *, status, produced=(), failure_kind=None) -> int`: caller transaction만 사용한다. 대상 snapshot/ref/model 검증 후 `RUNNING ∧ lease_owner=owner` 조건부 UPDATE가 승패를 정한다. commit·rollback·close·retry를 하지 않는다. SUCCEEDED/FAILED/CANCELLED만 허용하고 CANCELLED produced는 `[]`다. 기존 전이표는 public `validate_transition`으로 재사용하며 STALE 허용 전이 자체는 바꾸지 않는다. STALE 판정/sweep·다음 attempt 생성은 RT-06에 남긴다. terminal 이후 lease/heartbeat/token은 감사 근거로 남긴다.
- `runtime.db.claim_latency_ms`는 monotonic transaction 시작 → COMMIT 응답 확인이다. checkout/checkin/retry 대기/handler를 제외한다. EMPTY·CLAIMED·실패·COMMIT_UNKNOWN을 구분하고 receipt read 복구는 `runtime.db.claim_recovery_latency_ms`로 분리한다. RT-02 선택적 attempt observer는 sanitized outcome/duration만 받으며 sink/운영 logger 오류는 DB 결과나 retry 여부를 바꾸지 않는다.

#### Plan 대비 변경 · implementation detail

- 내부 nullable `claim_token`을 새 forward-only `runtime_0002` revision으로 추가한다. 기존 `runtime_0001`은 불변이다. token index나 별도 receipt/queue table은 만들지 않으며 PK 조회를 사용한다. read port allowlist와 Contract envelope는 그대로여서 token은 비노출이다.
- 공용 application/worker session을 생성·checkout 시 UTC로 고정한다. SET SESSION은 rollback으로 복원되지 않으므로 checkout에서도 복원한다. B-L6은 DB server `NOW(6)` 그대로이며 UTC_TIMESTAMP로 lease 기준을 대체하지 않는다. 기존 enqueue UTC 생성은 변경하지 않는다.
- 기존 migration 테스트의 head 기대값/미래 revision parent를 runtime_0002로 갱신한다. Case-owned 파일·runner 정책·Contract·Accepted Decision·Baseline 값/의미·다른 Owner surface는 변경하지 않는다. authoritative Plan은 구현에 맞춰 고치지 않는다.
- gate에 신규 lifecycle/UTC family와 개별 parameter inventory를 추가한다. 실제 보고서 mutation은 parameter가 포함된 marker에서도 role/scenario family를 찾는다. workflow·dependency·lockfile 변경은 없다.

#### Owner 확인 포인트

- 김준영 deferred Audit A: durable receipt와 동일 PK 재시도, session UTC 복원, finish target의 Worker/recovery 구분, commit acknowledgement/latency 경계. 새 사전 Owner 승인 gate를 만들지 않는다.
- RT-04 이후 composition은 공용 engine과 WorkerSettings lease 값을 사용하고, 공개 claim에서 반환된 snapshot 이후에만 handler를 실행한다. 임의 engine이나 transaction 중 timezone 변경은 지원 경계 밖이다.

#### Verification

- 실 MySQL 8.4.7 별도 임시 서버(port 13311, 폐기 schema), 서버 기본 timezone `+09:00`, `DAESINGO_REQUIRE_MYSQL=1`로 검증한다. 재부팅으로 기존 WSL 임시 배포가 없어 보관 archive와 임시 라이브러리를 이번 작업 디렉터리에 풀었다. 시스템 설치나 사용자 DB 변경은 없다.
- UTC/session/migration RED **7 failed** → foundation GREEN **61 passed**. 새 session/reused/replacement에서 NOW(6)=UTC 시각, runtime_0001의 기존 row를 보존한 token nullable upgrade를 확인했다.
- claim/finish 기능 부재 RED **26 failed**; 최초 fixture assertion 오류는 기능 RED로 세지 않고 테스트 본문 실패로 다시 실행했다. 공용 validator RED **11 failed** → lifecycle·전이 모델 GREEN **51 passed**.
- attempt observer RED **5 failed**, 실제 claim latency RED **1 failed / 18 passed** → observer·기존 transaction 정책·실 COMMIT proxy·queue fault 합계 GREEN **90 passed**. 정상 metric endpoint는 실제 commit acknowledgement 이전에 출력되지 않으며, sink가 DBAPIError를 던져도 재시도가 되지 않는다.
- 재시도마다 queue ID를 다시 선택하는 sensitivity mutation에서 receipt 복구/같은 worker 다른 token 검사 **2 failed**를 확인했다. 즉시 원본을 복원했으며 최종 전체 회귀가 복원본을 검증한다.
- 신규 gate inventory RED **63 failed / 358 passed** → GREEN **421 passed**. 기존 필수 checks·Case inventory와 JSON/JUnit 연결 검사는 유지한다.
- 첫 MySQL require 실행 **144 passed / 1 failed**: 실제 누락 mutation에서 UTC parameter marker를 bare dict와 비교한 테스트 오류였다. actual report에서 실행된 UTC parameter를 확인하고 family 비교만 role/scenario로 수정했다. 수정 뒤 MySQL targeted **145 passed / 571 deselected**, 206.53초, gate **PASS — 145 tests · skip 0 · xfail 0**. deselected는 선택 범위 밖의 비-MySQL tests이며 필수 MySQL 누락이 아니다.
- boundary **PASS — 위반 0**, Contract fixture **PASS — 문서 62 · JSON 26 · 의미 104**, workflow **actionlint 오류 0 + YAML policy/bash -n/ShellCheck 5 run steps PASS**. 보관 검사 binary가 없어 공식 고정 release를 이번 임시 디렉터리에 받았으며 시스템 설치는 없다.
- 최초 전체 회귀 **2656 passed / 26 skipped / 1 failed**, 624.13초. 저장소 밖 임시 진단 plugin의 전역 PYTEST_ADDOPTS가 PYTHONPATH를 교체하는 기존 dependency 부재 검사에 전파돼 plugin import가 실패했다. production/test 코드를 바꾸지 않고 임시 runner의 plugin 전파를 실제 migration child suite로 한정했다. dependency 검사 + 실제 MySQL 하위 gate 재검증 **2 passed**, 157.16초. 최초 전체 보고서의 MySQL gate도 **145 tests · skip 0 · xfail 0 PASS**였다. 실패 증거는 보존한다.
- 실제 보고서의 parameter 누락 mutation **329/329 거부**(47 parameter × 7 layer). 신규 family 전체 누락도 독립 inventory로 검사한다.
- 최종 전체 pytest **2657 passed / 26 skipped**, 712.83초, pytest exit **0**(`full-verified.exit`). 최종 JSON/JUnit gate **PASS — 145 tests · skip 0 · xfail 0**, setup/call/teardown **435 passed**. 하위 재귀 방지 suite도 **144 tests · skip 0 · xfail 0 PASS**다.
- 전체 skip 26건은 기존 선택적 검사다: Search `typer` 부재 4, Case 로컬 영상 부재 2, Eval 로컬 미디어/zip 부재 5, recording 영상/pair/VIDEO_INDEX opt-in 미지정 15. MySQL 대상 skip은 없다.
- 이번 targeted/전체 회귀에서 예기치 않은 migration 실패는 재발하지 않았다(임시 진단 JSON 0건). 과거 단발 실패의 원인 미확정 위험은 유지한다. 재발 대비 진단 plugin은 module·classification·DB errno·완료 모듈·허용 table/version 상태만 보존하며 URL/credential/SQL/exception 원문을 기록하지 않는다. 전역 plugin 환경 전파 오류는 위에 별도로 기록했다.
- 최종 self-review에서 README의 초기 lease 설정과 후속 lease 갱신 범위를 구분했다. 기존 `runtime_0001`과 보호 JSON의 SHA-256은 시작 시점과 같고 기존 pytest scratch 폴더는 건드리지 않았다. HEAD/index는 불변이며 커밋·push·PR 생성은 하지 않았다.
- 증거는 OS 임시 `C:/Users/cheol/AppData/Local/Temp/rt03b-20261009/`의 RED/GREEN 출력, JSON/JUnit, `summary.json`, workflow 결과에 보존한다. 이번 MySQL 서버의 port/datadir/version을 확인하고 해당 서버만 SHUTDOWN했으며 process exit 0이다. 증거·임시 DB data는 삭제하지 않았다.

### RT-03(b) 독립 리뷰 P2 — validation 입력의 내부 column 누수 수정

- RUNNING row의 `finish(status="FAILED")`에서 failure_kind를 생략하면 기존 model validator가 실패하고, Pydantic ValidationError의 보존 input에 DB row의 claim_token/lease/운영 metadata까지 포함됐다. read port의 출력 allowlist만으로 오류 입력 누수를 막을 수 없었다.
- `_execution_model`은 DB row 및 변경값에서 Contract 필드만 새 dict로 투영한 뒤 기존 UTC 변환과 JobExecution 검증을 실행한다. 내부 column은 model 입력에 전달하지 않는다. ValidationError를 그대로 유지하고 catch/wrapping/문자열 치환은 하지 않는다. claim receipt 소유권 복구, DTO, finish의 조건부 UPDATE와 caller transaction 동작은 변경하지 않는다.
- 새 단위 회귀는 원본 read-only row와 내부 override의 누수를 모두 검증한다. 실제 MySQL 회귀는 claim으로 생성된 실제 token과 합성 secret/path를 가진 RUNNING row에서 failure_kind 생략을 재현한다. `str(error)`, `repr(error)`, `error.json()`, `repr(error.errors())` 및 이 표현들을 기록한 일반 로그에 내부 column/value가 없고, input은 Contract 필드뿐임을 검사한다. 검증 실패 뒤에도 caller transaction은 열려 있고 row는 바뀌지 않는다.
- 비차단 의견은 이 Log 색인에만 반영했다: RT-03(a) PR #332 merge SHA, RT-03(b) claim receipt·UTC checkout·attempt observer. authoritative Plan·Contract·Decision·Baseline·runtime_0001은 바꾸지 않는다.
- 수정 전 RED **3 failed / 1 passed**, 2.11초 → P2 targeted GREEN **4 passed**, 1.45초. RT-03 전체 회귀 **83 passed**, 67.63초. 실제 MySQL require **146 passed / 437 deselected**, 302.90초, exit 0. JSON/JUnit gate **146 tests · skip 0 · xfail 0 PASS**, setup/call/teardown **438 passed**. 실제 parameter 누락 mutation **329/329 거부**. deselected는 이 command 선택 범위 밖의 비-MySQL 검사다.
- 구현 단계 최종 전체 pytest **2661 passed / 26 skipped**, 568.30초, exit 0. 구현 단계 최종 JSON/JUnit MySQL gate도 **146 tests · skip 0 · xfail 0 PASS**, phase **438 passed** 및 parameter 누락 **329/329 거부**다. 전체 skip은 기존 선택적 검사(Search typer 4 · Case 영상 2 · Eval 로컬 미디어/zip 5 · recording 영상/pair/VIDEO_INDEX opt-in 15)이며 MySQL skip은 없다. Boundary/Contract fixture/workflow 및 git diff --check PASS. 이번 증거는 `C:/Users/cheol/AppData/Local/Temp/rt03b-p2-20261009/`의 RED/GREEN·전체 출력, JSON/JUnit, mutation, summary에 별도로 보존한다.
- 이번 수정 중 예기치 않은 migration 실패는 재발하지 않았다(진단 JSON 0건). 과거 단발 실패 원인 미확정 위험은 유지한다. runtime_0001·보호 JSON의 SHA-256과 HEAD/index는 수정 시작 시점과 같으며 기존 pytest scratch 폴더는 건드리지 않았다. P2 전용 MySQL 8.4.7의 port 13312/datadir/version을 확인하고 해당 서버만 정상 종료했다. DB data와 증거는 삭제하지 않았다.
- P2 수정 당시 독립 재리뷰 전까지 RT-03은 **IN_PROGRESS**였고 `Closes #290`은 미사용이었다. 이후 최종 판정과 PR 연결은 아래 기록으로 갱신한다. 커밋·push·PR 생성은 하지 않았다.

### RT-03(b) 최종 독립 재리뷰 — P2 해소 및 DONE 판정

- 최종 갱신 요청으로 전달받은 독립 재리뷰 결과를 기록한다. token 오류 데이터 노출 P2는 Contract 필드 allowlist의 새 validation 입력으로 수정됐으며 독립 재리뷰를 통과했다. 이번 문서 갱신에서 테스트를 재실행한 결과로 기록하지 않는다.
- 독립 재리뷰에서 실제 MySQL suite를 **직접 실행**하여 **146 passed · skip 0 · xfail 0**을 확인했다.
- 전체 pytest **2661 passed / 26 skipped**는 위 **구현 단계 실행 결과**다. 재리뷰에서는 보존된 출력·JSON/JUnit 증거를 대조했으며, 전체 pytest를 새로 실행한 결과와 구분한다.
- gate parameter 누락 검사는 위 구현 단계의 실제 보고서에서 **329/329 거부**(47 parameter × 7 layer)로 확인된 기록을 유지한다.
- RT-03 최종 상태는 **DONE**이다. 최종 PR 연결은 **`Closes #290`**이며 PR 번호와 merge SHA는 **pending**으로 유지한다. PR 생성·merge 또는 Issue close가 이미 실행됐다는 의미는 아니다. 이번 문서 갱신에서는 커밋·push를 하지 않는다.
- 과거 migration 단발 실패의 **104.502초** 기록과 **원인 미확정 위험**은 아래 남은 위험 그대로 유지한다.

### 남은 위험

- 독립 재리뷰는 통과했으며 deferred Owner Audit A는 별도 기록 대상이다. RT-04 이후 lifecycle은 이번 검증 범위가 아니며 usage_refs는 RT-07 전까지 빈 목록이다.
- MySQL migration DDL의 부분 적용 실패는 runner 자동 retry/rollback으로 복구되지 않는다. 기존 RT-02 운영 경계 그대로다.
- ID/metadata column 상한과 UTC 저장 규칙을 후속 writer도 지켜야 한다. unknown COMMIT 결과의 idempotency와 command 원자성 실제 HTTP 배선은 후속 composition에서 다룬다.
- 첫 전체 회귀의 단발 migration 실패 검사는 하위 JUnit(`rt03a-20261008/full/test_actual_report_rejects_eac0/mysql.xml`)에 **104.502초**로 기록돼 있다. 2026-10-09 해당 testcase의 `time="104.502"`를 직접 확인했다. 원인은 미확정이며 network·timeout·파일 접근 등 특정 원인으로 단정하지 않는다. 실패를 skip/mock/retry 코드로 우회하지 않았고 진단 재실행은 통과했다. 이번 P2를 이유로 migration runner 등 production 동작은 변경하지 않았다.

---

## RT-04 — Worker core: claim loop · kind registry · dispatch · T1/T2 (E2E-0)

Status: DONE · Issue: #291 · Audit: A

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| [#336](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/336) | RT-04(a) loop · registry · T1 — `Refs #291` | `d08b29a` |
| pending | RT-04(b) T2 · E2E-0 · 최종 PR — `Closes #291` | pending |

### 구현 결과

- `python -m daesingo.worker` entrypoint가 RT-01 bootstrap과 RT-02 Worker engine을 연결한다. concurrency knob 없이 한 main thread가 실행하며, SIGINT/SIGTERM은 다음 idle 지점에서 반영한다. 실행 중 handler와 T1 기록은 중단하지 않는다.
- 단일 `KindRegistry`는 kind→invocation mapping의 불변 snapshot이다. 실제 Recording/Search handler 등록은 비어 있으며 fake handler로 경로를 검증한다. 미등록 kind는 invocation 없이 `RUNTIME_UNREGISTERED_KIND`로 `FAILED`, 비정상 반환값·handler/dispatch 예외는 `RUNTIME_` failure로 기록한다.
- `ExecutionContext`는 execution/job/case/kind/attempt/trace와 cancel·usage injection 자리를 갖는다. cancel·usage 동작은 구현하지 않는다. `HandlerResult`는 성공/실패 및 produced만 담고 모듈 failure taxonomy를 재해석하지 않는다.
- claim commit 뒤 connection을 반환하고 handler를 실행한다. T1은 기존 `finish`와 `run_worker_transaction`을 재사용한다. B-D8 소진 뒤 B-Q3 간격으로 같은 결과만 재기록하며 handler를 재호출하지 않는다. 조건부 전이 0 rows는 현재 owner·status·produced·failure를 잠금 재조회해 unknown COMMIT의 동일 결과인지 구분한다.
- started/completed와 DB 오류 event는 RT-01 structured logging으로 기록한다. execution DB 오류에는 trace/case/job/execution correlation을 연결한다. 예외 원문, produced ref, failure taxonomy 원문, 경로, provider/user payload와 claim token은 로그에 전달하지 않는다.

### Plan 대비 변경

- Plan의 두 PR 경계 중 RT-04(a)만 구현했다. T2 `ResultReflector`·후속 enqueue·Case 반영·E2E-0 최종 연결은 RT-04(b)에 남긴다. Expected files/modules에 `common/jobs/execution.py`를 추가해 Runtime이 Worker registry에 의존하지 않게 했다. 구현 구조의 선택이며 Contract·Accepted Decision·Baseline 의미 변경은 없다.
- 기존 MySQL JSON/JUnit gate에 Worker 필수 role/scenario와 parameter를 추가하고 실제 보고서 mutation 검증의 child suite에 Worker MySQL 경로를 포함한다. child timeout의 여유만 늘리며 운영 interval은 바꾸지 않는다. workflow·의존성·migration 변경 없음.

### 새 implementation detail

- scheduler의 idle wait와 T1 DB backoff sleep을 분리한다. idle은 signal event로 깨어나지만 T1 재시도는 종료 요청에도 결과를 유지한다. stop flag는 다음 claim 앞에서만 확인한다.
- terminal completion log는 commit 또는 동일 owner의 동일 durable terminal 결과를 확인한 뒤에만 기록한다. 다른 owner/status/result 또는 missing row는 `runtime.execution.finish_rejected`로 관측하고 성공을 단정하지 않는다. RT-05의 lease 보유 확인·heartbeat는 아직 붙이지 않는다.
- entrypoint의 revision은 build revision 공급 경로가 없는 현재 상태를 `unknown`으로 기록한다. RT-01의 config 파일·Search credential validation은 유지한다.
- job ID의 event token 상한을 기존 DB 저장 경계인 191자에 맞춘다. storage-valid ID라도 경로·제어문자가 있으면 로그에서만 SHA-256 기반 `id_` alias로 일관되게 연결하고 DB/handler의 원래 ID는 유지한다. correlation 오류가 dispatch를 중단하거나 경로 원문을 노출하지 않게 하는 구현 선택이다.

### Owner 확인 포인트

- RD-09a Gate: [Issue #334의 Runtime Owner 승인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/334#issuecomment-6081077166)을 확인했다. 실제 handler 연결 시 RecordingService mutable cache/working state는 execution마다 새 service + `finally: close()`로 제한한다. durable repository/persistence를 execution마다 새로 격리한다는 의미는 아니다. 이 PR에서는 domain service를 만들거나 lifecycle을 확장 구현하지 않는다.
- RT-04(b)의 T2 공개 반영 port는 Case Owner와 Consult 뒤 연결한다. 이번 작업에서 다른 Owner에게 새 공개 surface 의무를 만들지 않았다.

### Verification

- 초기 unit RED 22 failed → GREEN 22 passed. entrypoint RED 3 failed와 실제 MySQL composition RED 10 failed를 확인한 뒤 Worker 전체 GREEN **42 passed**, 19.43초(실제 MySQL 신규 10개, skip/xfail 없음)를 확인했다.
- Worker 필수 MySQL check 누락 RED **6 failed** → gate GREEN **469 passed**. ID logging 경계 RED **2 failed** → unit/structured logging GREEN **33 passed**. 종료 시 dispose 오류 원문 노출 RED **1 failed**도 확인해 고정된 cleanup failure event로 처리했다.
- 최종 관련 회귀 **540 passed**, 32.43초. Worker 47개(실제 MySQL 12개 포함), structured logging 9개, gate unit 484개이며 skip/xfail 없음.
- 실제 MySQL require `pytest -m mysql`: **158 passed / 4 skipped / 2628 deselected**, 247.33초, exit 0. JSON/JUnit gate **158 tests · MySQL skip 0 · xfail 0 PASS**. 명령의 skip 4개는 `typer` 부재로 수집되지 않은 비-MySQL Search 테스트이며, deselected는 선택 범위 밖 검사다.
- 전체 pytest(MySQL require): **2764 passed / 26 skipped**, 429.12초, exit 0. JUnit **2790 tests / failures 0 / errors 0 / xfail 0**. skip 사유는 Search `typer` 부재 4, Case 로컬 영상 부재 2, Eval 로컬 미디어/zip 부재 5, Recording 실영상·pair·VIDEO_INDEX opt-in 미지정 15다. MySQL test skip은 없으며 Recording synthetic media smoke도 실제 실행 PASS다.
- 전체 실행의 최종 JSON/JUnit MySQL gate도 **158 tests · skip 0 · xfail 0 PASS**, setup/call/teardown **474 passed**. 전체 실행 안의 실제 보고서 parameter 누락 mutation도 **385/385 거부**다. evidence는 이번 작업 전용 `C:/Users/cheol/AppData/Local/Temp/rt04a-20261009/`의 `focused-final.{json,xml}`, `mysql-require.{txt,json,xml}`, `full.{txt,json,xml}`이며 기존 pytest scratch 폴더를 재사용하거나 수정하지 않았다.
- MySQL server **8.4.7**, parent setup/call/teardown **474 passed**. 실제 보고서를 만드는 child suite는 **157 MySQL tests**이며, parameter 누락 mutation **385/385 거부**(Worker 신규 8 parameters × 7 evidence layers = **56/56** 포함)를 확인했다. child 실행 수는 parent 실행 수와 분리해 기록한다.
- boundary PASS(위반 0), Contract fixture PASS(구조 62 / JSON 26 / 의미 104 검사), 저장소 전체 workflow 5개 Actionlint·ShellCheck PASS(0 errors), Python CI YAML policy·Ubuntu `bash -n`·ShellCheck PASS(5 run steps), `git diff --check` PASS. Actionlint의 pyflakes 검사 미실행은 기존 검사 방식과 같으며 여기서 Python type/lint gate 완료를 주장하지 않는다.
- 읽기 전용 독립 코드 리뷰에서 RT-04(a)의 수정 필요 P1/P2/P3 결함 없음. reviewer는 테스트를 재실행하지 않았고, 실제 실행 결과의 검증 주체는 이 작업이다. 최종 gate 통과 조건부 판단이며 RT-04 전체 완료나 Owner acceptance를 뜻하지 않는다.
- 기준 HEAD와 최신 fetch `origin/develop`은 `c319275e482a74974b434f0b2515878517d4d0b4`로 동일했다. HEAD/index 변경 없이 구현했다. 보호 대상 `recording-baseline-negative-001.json`의 SHA-256은 `27BA6EE8F681F2DF93C4E147589DD932D4632D71631A77EDE194317D42247D99`로 유지한다.

### 남은 위험

- heartbeat·lease 갱신·cancel·STALE/sweep·다음 attempt 생성·usage 영속·실제 handler는 제외했다. DB 장기 장애 때 T1은 B-Q3 재시도를 계속하므로 종료 신호 반영도 지연된다. RT-05의 소유 상실 관찰과 RT-06 복구가 필요하다.
- 이번 결과는 RT-04(a)의 T1 경로 검증이며 E2E-0 전체 완료를 뜻하지 않는다. RT-04 상태는 `IN_PROGRESS`, PR 연결은 `Refs #291`이다. 커밋·push·PR 생성 및 Issue close는 하지 않는다.

### 2026-10-09 후속 독립 리뷰 P2 — Worker logging sink 장애 격리

- 후속 독립 리뷰에서 아래 P2 두 건이 발견됐다. 위의 최초 “수정 필요 P1/P2/P3 결함 없음” 기록은 당시 읽기 전용 리뷰 결과로 보존하며, 이번 결함까지 없다는 보장으로 해석하지 않는다. 전달된 finding을 코드와 별도 RED로 검증한 뒤 순서대로 수정했다.

| Finding | RED 재현 | 수정과 GREEN |
| --- | --- | --- |
| loop의 직접 logging 호출에서 filter/handler 예외가 dispatch·T1 또는 DB 회복을 중단 | 실제 MySQL에서 started/completed/claim DB/T1 DB × filter/handler **8 failed**. claim_lost/finish_rejected도 별도 RED **4 failed** | Worker loop의 event 호출만 `log_event_best_effort`로 변경. 실제 commit·terminal facts·produced와 handler 1회, claim B-Q3, T1 B-D8 3회 소진 뒤 B-Q3를 검증. 관련 logging/loop/MySQL/observer **63 passed** |
| main 오류·cleanup 로그의 sink 예외가 원래 오류 위에 전파되어 stderr에 원문 노출 | 실제 subprocess에서 loop/cleanup/동시 오류 × filter/handler **6 failed**, 정상 sink 및 정상 실행 **6 passed**. stderr traceback에 테스트용 secret·경로·payload가 포함됨 | main의 두 오류 event도 같은 helper로 변경. 정상/loop/cleanup/동시 오류 × healthy/filter/handler **12 passed**, stderr 비어 있음·기존 종료 코드·dispose·signal 복원 보존. cleanup 자체 실패의 기존 code 1 정책도 유지 |

- 중앙 `log_event()` 전체의 sink 예외를 삼키는 방식은 기존 API와 다른 모듈의 동작까지 바꾼다. Worker 호출 전체를 `try/except`로 감싸면 event/correlation 검증 오류도 숨긴다. 따라서 검증 코드를 공유하는 별도 helper를 추가하고 Worker만 선택적으로 사용한다. 기존 `log_event()`의 sink 예외 전파 계약은 filter/handler 회귀로 유지 확인했다.
- event/field/context 검증은 sink `try` **밖**에서 수행한다. unsafe name·payload field·경로 ID·NaN duration·미등록 field는 계속 `ValueError`이며 sink 호출 전 거부된다. 같은 `ValueError`라도 filter/handler 호출에서 발생하면 일반 sink 장애로 격리한다. logger 내부의 임의 버그와 transport 장애를 예외 타입만으로 완전히 구분한다는 의미는 아니다.
- 격리는 기존 transaction `_emit`·observer처럼 일반 `Exception`에만 적용한다. `KeyboardInterrupt`/`SystemExit`는 전파되며 fallback traceback·원문·추가 stderr 진단을 출력하지 않는다. 기존 stream `OSError`의 고정 `log.write.failed` event와 정상 structured correlation은 유지한다.
- 실제 MySQL 신규 8개에서 T1 observer에도 DBAPI 형태 예외를 동시에 주입한다. transaction 자체는 기존 helper로 실행하고 실제 `KILL CONNECTION`으로 3회 disconnect를 만든다. DB/queue/transaction mock 또는 skip으로 대체하지 않으며 결과·produced·retry·sleep·observer attempt 횟수를 확인한다.
- JSON/JUnit gate에 `worker_core/logger_isolation`과 8개 필수 parameter를 추가했다. 독립 inventory로 family 또는 개별 parameter 전체 누락을 거부하지 못하는 gate RED **9 failed**를 확인한 뒤 필수 목록을 갱신했다.
- 최종 targeted: Worker·entrypoint·structured logging·gate·observer **640 passed**, 69.98초, skip/xfail 없음. Worker 실제 MySQL **20 tests / 60 passed phases**를 포함한다.
- 실제 MySQL require 필수 경로: **166 passed / 16 deselected / skip 0 / xfail 0**, 371.01초, exit 0. MySQL **8.4.7**, 최종 JSON/JUnit gate **166 tests / 498 passed phases PASS**. child는 **165 MySQL tests**이며 parent 실행 수와 분리한다. 실제 보고서 parameter 누락 mutation **441/441 거부**(Worker 16 parameters × 7 layers = **112/112**, 신규 logger 8 parameters × 7 layers = **56/56** 포함).
- 전체 pytest(MySQL require, 2026-10-10 완료): **2859 passed / 26 skipped**, 718.87초, exit 0. JUnit **2885 tests / failures 0 / errors 0**, MySQL 최종 JSON/JUnit gate **166 tests / 498 passed phases / skip 0 / xfail 0 PASS**. 전체 실행의 child **165 tests**, parameter 누락 mutation도 **441/441 거부**(Worker **112/112**, 신규 logger **56/56**). skip 사유는 Search `typer` 부재 **4**, Case 로컬 영상 부재 **2**, Eval 로컬 미디어/zip 부재 **5**, Recording 실영상·pair·VIDEO_INDEX opt-in 미지정 **15**이며 MySQL skip은 없다. Recording synthetic media smoke도 실제 실행 PASS다.
- evidence는 별도 `C:/Users/cheol/AppData/Local/Temp/rt04a-p2-20261009/`의 `loop-red`, `main-red`, `main-green-gate-red`, `targeted`, `mysql-require`, `full` 보고서이며 pytest basetemp도 새 `rt04a-p2-*` 경로만 사용한다. 기존 보호 JSON과 pytest scratch 폴더는 변경·staging하지 않았다. 보호 JSON SHA-256은 위 최초 기록과 동일하다. 검증 뒤 port/version/datadir로 작업 소유를 확인한 MySQL만 정상 종료했다.
- boundary **PASS — 위반 0**, Contract fixture **PASS — 구조 62 / JSON 26 / 의미 104**, 전체 workflow **5개 Actionlint/ShellCheck PASS — 오류 0**, Python CI YAML policy·`bash -n`·ShellCheck **5 run steps PASS**. 기존 방식과 같이 Actionlint pyflakes는 실행하지 않았다.
- 후속 읽기 전용 source 리뷰에서 이번 P2 수정 범위의 추가 actionable P1/P2/P3 finding 없음. reviewer는 테스트를 재실행하지 않고 RED/targeted artifact와 소스를 확인했으며 당시 require/full은 진행 중이었다. 최종 실제 실행 검증 주체는 구현자다. 이 source 리뷰는 RT-04 전체 완료나 merge/Owner 승인 판정이 아니다.
- 최종 `git diff --check` **PASS**. 변경된 untracked Python 파일의 trailing whitespace도 별도 확인했다. HEAD/index 불변이며 커밋·push·PR 생성은 하지 않았다. 이번 P2 수정 결과는 사용자 독립 재리뷰 요청 가능 상태다.
- Contract·Decision·Baseline 의미, queue/transaction 정책, RD-09a 경계, RT-04(b)의 T2/Case 반영/E2E 범위는 변경하지 않았다. sink 장애 동안 일부 event가 유실될 수 있으며 log delivery 보장은 이번 수정 범위가 아니다. 상태는 계속 `IN_PROGRESS`, PR 연결은 `Refs #291`이다.

### 2026-10-10 RT-04(a) 독립 재리뷰 통과 — P2 해소 및 검증 주체 구분

- 사용자에게 전달받은 독립 재리뷰 통과 결과를 후속 기록한다. 이전 P2 두 건, 즉 logger 장애가 dispatch·T1·B-Q3·B-D8 흐름을 중단하던 문제와 entrypoint 오류·cleanup 로그 실패가 traceback·예외 원문을 노출하던 문제가 해소됐음을 확인했다. 앞선 최초 리뷰 및 P2 발견·수정 기록은 당시 이력으로 보존한다.
- `log_event_best_effort`는 event/field 검증 **이후** sink 호출에서 발생하는 일반 `Exception`만 격리한다. unsafe 입력 검증 오류와 `KeyboardInterrupt`·`SystemExit` 등 `BaseException` 전파는 유지한다. 기존 `log_event()`의 계약은 변경하지 않았다.

**독립 재리뷰 직접 실행 결과 — 사용자 전달**

| 검증 | 결과 |
| --- | --- |
| 비-MySQL 관련 회귀 | **620 passed** |
| 실제 MySQL require | **166 passed · skip 0 · xfail 0** |
| Worker MySQL (위 MySQL 대상에 포함) | **20 passed** |
| entrypoint subprocess (위 비-MySQL 대상에 포함) | **12 passed** |
| gate setup/call/teardown execution phase | **498 passed** |
| parameter 누락 mutation | **441/441 거부** |
| `git diff --check` | **PASS** |

- 전체 pytest **2859 passed / 26 skipped**는 위 **구현 단계 직접 실행 결과**다. 독립 재리뷰에서는 전체 pytest를 다시 실행하지 않고 보존된 증거를 대조했다. boundary·Contract fixture·workflow 정적 검사는 구현 단계에서 통과했으며 이번 독립 재리뷰에서는 반복 실행하지 않았다. 이번 문서 갱신에서도 테스트나 위 정적 검사를 재실행하지 않고 `git diff --check`와 `git status --short`만 확인한다.
- event sink 장애 중 해당 event가 유실될 수 있음은 허용된 한계다. 원격 CI는 미실행이며, T2·Case 반영·E2E-0 최종 연결은 RT-04(b)에 남아 있다.
- RT-04 상태는 계속 **`IN_PROGRESS`**다. RT-04(a)의 PR 연결은 **`Refs #291`**, **PR 번호 `pending` · merge SHA `pending`**이며 Issue를 닫지 않는다. 이번 갱신에서 다른 코드·테스트·문서는 수정하지 않고 커밋·push·PR 생성도 하지 않는다.

---

### 2026-10-10 RT-04(b) — T2 port · 원자적 전달 · fake E2E-0

Status: **IN_PROGRESS** · PR 연결: **`Refs #291`** · RT-04(b) PR 번호 **pending** · merge SHA **pending**. RT-04 전체 독립 재리뷰와 Owner acceptance 전이며, 최종 PR 후보지만 `Closes #291`은 확정하지 않는다. 기존 RT-04(a) 구현·리뷰·P2 이력은 당시 기록 그대로 보존한다.

**기준과 Owner 합의**

- 시작 시 현재 branch는 `feature/runtime-worker-t2-e2e0`, HEAD와 최신 fetch한 `origin/develop`은 `a3e4162afd6850baec4e727cf530d891f8dd4dcd`였다. RT-04(a)는 [PR #336](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/336), merge `d08b29a2701456fabeeee8a9082dc3a5b5f9ef3d`의 구현을 재사용한다. 앞선 (a) 절의 PR pending은 당시 기록이며 현재 기준 상태와 구분한다.
- [Case Owner 합의](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/291#issuecomment-6087010126), [Runtime Owner 승인·metric 정의](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/291#issuecomment-6091819255), [PR #337 이후 진행 승인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/291#issuecomment-6092077761)을 확인했다. 호출자 Connection · Case 먼저 잠금 · execution_id idempotency · reflector 내부 commit/rollback/retry 금지 · 정상 반환 세 종류 모두 전달 완료라는 경계를 따른다.
- [PR #337](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/337), merge `a3e4162afd6850baec4e727cf530d891f8dd4dcd`로 동기화된 최신 Baseline §6에 따라 metric은 **attempt >= 2 AND NOT_APPLIED AND STOPPED_WAITING**만 집계한다. attempt 1 · CANCELLED · SUPERSEDED · ALREADY_APPLIED · reflector 예외는 제외한다. Tech Spec §12.2 및 Plan §6 RT-04 · §12가 나머지 기준이다.

**구현과 transaction 경계**

- `common/jobs/reflection.py`에 `ResultReflector.reflect(Connection, ReflectionInput)` Protocol과 frozen/slots 입력·출력·후속 `RuntimeJobRecord`를 추가했다. 입력은 execution/job/case/kind/attempt와 terminal snapshot, 후속 JobRecord는 기존 `enqueue`가 소비하는 job_id/case_id/kind projection이다. Case intent/payload/JobRecord schema를 Runtime이 새로 소유하지 않는다.
- `APPLIED`만 같은 Case의 후속 JobRecord를 반환할 수 있다. ALREADY_APPLIED 및 NOT_APPLIED의 후속 JobRecord, 잘못된 reason/status, extra key/value, 객체 변조, 중복 job_id, 다른 Case의 후속 JobRecord를 정적 오류 메시지로 거부한다. mutable 입력 목록은 tuple snapshot으로 보존한다. 잘못된 반환은 T2 rollback 대상이다.
- Worker는 기존 T1 `finish` commit이 확인된 뒤 T2를 호출한다. 종료 신호가 handler 중 설정돼도 T1/T2까지 진행하고 다음 idle 지점에서 반영한다. handler 중 DB connection/transaction이 열리지 않는 보장을 유지한다. T1 거부 시 T2를 실행하지 않는다.
- T2는 기존 Worker engine과 `run_worker_transaction`을 재사용한다. reflector가 Case를 잠금·반영한 후 Runtime이 execution을 잠금 조회하여 terminal status/produced/failure 및 execution/job/case/kind/attempt/trace를 대조한다. 이후 **같은 Connection/transaction**에서 후속 `enqueue`와 조건부 `case_applied_at=UTC DB 시각` UPDATE를 수행한다. Case lock → Runtime lock/write 순서이며 T1 transaction과 분리된다.
- APPLIED · ALREADY_APPLIED · NOT_APPLIED(STOPPED_WAITING/CANCELLED/SUPERSEDED)의 정상 반환은 모두 표식을 남긴다. UPDATE 0 rows는 단순 성공으로 보지 않고 durable terminal facts와 이미 기록된 표식을 잠금 재조회해 확인한다. missing/mismatch/미기록 표식은 rollback한다.
- COMMIT 응답 유실 재실행은 먼저 Case의 execution_id 중복 판정을 받고 Runtime 표식을 확인한다. 이미 완료된 표식은 ALREADY_APPLIED로 복구하여 후속 execution을 다시 생성하지 않는다. 이미 표식이 있는데 APPLIED를 반환하면 Case idempotency 충돌로 안전하게 거부한다. Case 변경·후속 enqueue·표식 중 하나라도 실패하면 T2 전체 rollback하고 기존 T1 SUCCEEDED/FAILED는 유지한다.
- B-D8은 초회 포함 총 3회 · 재시도 간 1초다. retryable DB 오류만 기존 helper가 재시도하며 소진·reflector 예외 이후 안전한 `runtime.reflect.failed`를 기록하고 다음 claim을 계속한다. 표식 없는 terminal은 향후 RT-06 재전달 대상이다. 기존 observer/DB `_emit` 격리 정책과 `log_event_best_effort`를 그대로 사용하여 일반 sink/observer Exception이 DB 결과·retry·sleep 판단을 바꾸지 않는다. BaseException 및 unsafe log 검증 오류를 무조건 삼키는 변경은 없다.
- metric은 T2 commit 확인 후 위 조건에만 기록한다. rollback과 ALREADY_APPLIED 복구/중복 전달은 집계하지 않는다. trace/case/job/execution correlation을 연결하며 내부 token · SQL · 원문 예외 · 경로 · provider/user payload는 event에 전달하지 않는다.

**TDD 및 source 리뷰**

- immutable port/taxonomy/반환 불변조건 **20 RED**, Worker T1→T2 순서·실패 격리 **7 RED**, 실제 MySQL T2 acceptance **35 RED**를 각각 실제 실행한 후 구현했다. 첫 MySQL GREEN은 34 passed / 1 failed였으며 missing execution 전에 fake 확인 코드가 먼저 실패하는 테스트 문제를 수정한 뒤 모델·loop·실제 MySQL 합계 **81 passed**를 확인했다. extra-field 이름 자체의 비밀/경로 노출도 **3 RED**로 재현하고 generated dataclass 오류 대신 정적 검증 오류를 사용했다.
- 실제 MySQL에 B-D8 disconnect 소진 · 다음 Job 진행 · 동시 중복 전달 3개를 추가했다. 최초 assertion의 기존 event 이름/seed 순서 가정 오류를 바로잡았으며 이는 새 production 결함 RED로 집계하지 않는다. T2 신규 MySQL은 총 **38개**다.
- 독립 inventory로 신규 T2 role/scenario 9개 및 parameter 38개 누락을 거부하지 못하는 gate **47 failed / 749 passed** RED를 확인했다. JSON/JUnit gate 필수 목록과 실제 보고서 mutation child suite에 T2를 연결했다.
- fresh 읽기 전용 source 리뷰는 terminal 재검증의 P2 1건을 발견했다: Pydantic serializer warning이 변조 원문을 노출하고 `model_copy` extra 저장 필드를 조용히 제거했다. 입력·Worker의 produced/terminal extra/nested ref extra/type 변조 **8 RED**로 재현했다. `validated_terminal`이 저장 필드 shape를 먼저 검사하고 `warnings="error"`를 정적 ValueError 경계 안에서 처리하도록 수정했으며 관련 **54 passed** GREEN을 확인했다. 기존 Contract reference 파서·extra 정책은 바꾸지 않았다. reviewer는 DB suite를 직접 실행하지 않았고 수정 후 별도 재리뷰를 하지 않았으며 최종 회귀는 구현자 실행이다. Critical/Minor finding은 없었다.

**최종 검증 — 구현자 직접 실행**

- 수정 후 Worker·jobs·structured logging·observer·gate targeted **1075 passed**, 157.55초. 이 command의 실제 MySQL **138 passed · skip 0 · xfail 0**, execution phase **414 passed**이며 T2 신규 **38 passed**가 포함된다.
- 실제 MySQL require **204 passed / 44 deselected**, 443.32초, exit 0. deselected는 해당 command 범위의 비-MySQL 테스트다. JSON/JUnit gate **204 tests · skip 0 · xfail 0 PASS**, execution phase **612 passed**. nested 실제 보고서 suite도 **203 passed · skip 0 · xfail 0**, phase **609 passed**로 검증했다(상위 204와 별도 실행이며 두 수를 하나의 고유 test 수로 합산하지 않는다).
- 실제 보고서 parameter 누락 mutation **707/707 거부**(101 parameter × 7 layer), 신규 T2 **266/266 거부**(38 × 7). 신규 `worker_t2` role 전체 및 scenario 9개 개별 누락도 실제 보고서에서 **10/10 거부**했다. T2 신규 **38 passed**에 metric 포함/제외 · 두 sink 종류 · 실제 Connection kill/COMMIT 응답 유실 · 동시 전달이 포함된다.
- **E2E-0 PASS**: enqueue → claim → transaction 없는 dummy handler → T1 SUCCEEDED → fake reflector 1회 호출/1회 반영 → 후속 QUEUED enqueue 및 case_applied_at → read port SUCCEEDED를 실제 MySQL에서 확인했다.
- 첫 전체 pytest는 **1 failed / 3210 passed / 26 skipped**, 554.36초였다. 하위 실제 suite의 기존 `test_api_real_precommit_failure_never_reexecutes_callback[kill]`에서 blocker rollback이 MySQL 2013/Windows 10053 TLS socket abort로 실패하여 상위 `test_actual_report_rejects_each_missing_migration_check`가 실패했다(하위 **202 passed / 1 failed**). 이 실패 보고서는 JSON/JUnit gate도 정상적으로 거부했다. 같은 설정의 해당 실제 MySQL test를 **5회 직접 재실행해 5/5 passed · skip 0 · xfail 0**였으며 원인은 미확정이다. 실패를 skip/mock/자동 test retry로 우회하거나 DB helper·기존 test 동작·TLS 설정을 바꾸지 않았다. 첫 실패 증거는 보존하고 전체 회귀를 같은 코드/설정으로 새 폴더에서 다시 실행한다.
- 최종 전체 재검증은 **3211 passed / 26 skipped**, 563.91초, exit 0이다. 전체 실행의 MySQL JSON/JUnit gate도 **204 tests · skip 0 · xfail 0 PASS**, phase **612 passed**이며 nested suite **203 passed**, phase **609 passed**, parameter 누락 **707/707 거부**(신규 T2 266)를 다시 대조했다. skip 사유는 기존 선택적 검사 **Search typer 미설치 4 · Case 로컬 영상 없음 2 · Eval 로컬 미디어/zip 없음 5 · Recording 영상/pair/VIDEO_INDEX opt-in 미지정 15**이며 MySQL skip은 없다. gate unit 전체 **816 passed**도 targeted JUnit으로 대조했다.
- Boundary **위반 0**, Contract fixture **구조 62 · JSON 26 · 의미 104 PASS**. workflow **Actionlint 5 files · YAML policy · bash -n/ShellCheck 5 run steps PASS**이며 Python pyflakes는 이 정적 검사에서 비활성이다. 원격 CI는 실행하지 않았다.
- 증거는 이번 작업의 새 폴더 `C:/Users/cheol/AppData/Local/Temp/rt04b-20261010/`에 보존한다. 보호 JSON hash와 HEAD/index를 확인했고 기존 `.pytest-*` 폴더를 테스트 basetemp로 사용하지 않았다. 커밋·staging·push·PR 생성 없음.

**Plan 대비 차이와 남은 위험**

- Plan의 넓은 “case가 반영하지 않았을 때” metric 문구를 수정하지 않고, Owner 승인과 PR #337의 정확한 조건을 따른 차이를 여기 기록한다. `common/jobs/reflection.py`의 port/transaction primitive와 기존 `execution.py`의 안전 terminal snapshot을 추가한 것은 구현 구조 선택이며 Contract·Decision·Baseline 의미 변경은 없다.
- 실제 Case와 8-8 execution_id 영속 연결은 수정하지 않았다. `compose_worker(reflector=...)` 주입이 없으면 기존 entrypoint에는 T2가 연결되지 않으며 실제 Case wiring까지 표식은 남기지 않는다. 테스트 전용 Case/receipt table과 fake 형태는 실제 Case 구현의 새 schema 의무가 아니다. E2E-0은 dummy handler와 fake 반영 경로다.
- Startup/periodic T2 재전달은 RT-06, heartbeat/cancel·lease fencing은 RT-05, usage 영속은 RT-07, 실제 handler는 RT-10에 남긴다. RD-09a의 execution-scope mutable service/close 경계는 보존하며 실제 Recording lifecycle을 확장하지 않았다.
- sink 장애 시 해당 event 유실, COMMIT 응답 유실 후 ALREADY_APPLIED 복구 시 metric 미기록이 가능하다. log 전달·crash 시 exactly-once metric은 보장하지 않는다. B-D8 소진 시 COMMIT 결과 불명은 기존 helper 의미 그대로이며 이미 저장됐을 수 있는 표식을 임의로 지우지 않는다. 임의 raw DBAPI/DDL을 실행하는 Python reflector를 sandbox하는 기능은 없고 기존 Connection commit/rollback guard를 재사용한다.
- 첫 전체 회귀의 기존 API pre-commit kill test에서 blocker rollback TLS socket abort(2013/10053)가 단발 발생했다. 같은 실제 test 5회 재실행은 통과했으나 원인은 미확정이며 특정 network/보안 software 원인으로 단정하지 않는다. RT-04(b)나 기존 DB helper의 결함이 해소됐다는 근거로 해석하지 않고 실패·재검증 증거를 남긴다.
- RT-04 전체는 독립 재리뷰 전까지 **IN_PROGRESS**이며 Owner Audit A·원격 CI·merge 승인을 뜻하지 않는다.
- 구현·최종 검증 증거를 갖춘 독립 재리뷰 요청 가능 상태다. source 리뷰 P2는 위 RED→GREEN 및 최종 회귀로 검증했으며 사용자 독립 재리뷰 통과 판정을 대신하지 않는다. 최종 `git diff --check` **PASS**, 새 untracked Python의 syntax/whitespace **PASS**, HEAD/index 불변을 확인했다. 보호 JSON SHA-256은 시작 시점과 같고 기존 pytest scratch 폴더는 수정·staging하지 않았다. 작업 전용 MySQL의 port/datadir/version을 확인하고 해당 서버만 정상 종료했으며 DB data·증거는 보존했다. 커밋·staging·push·PR 생성 없음.

### 2026-10-11 RT-04(b) 후속 — 독립 리뷰 P2: T2 DB 오류 소진 뒤 B-Q3 누락

Status: **IN_PROGRESS** · PR 연결: **`Refs #291`** · PR 번호 **pending** · merge SHA **pending**. 앞선 구현·리뷰·검증 기록은 당시 결과 그대로 보존하며, 이번 발견과 수정·검증을 별도 후속 기록으로 추가한다. 사용자 독립 재리뷰 전이다.

**발견 · RED → GREEN · 최소 수정**

- 현재 코드에서 독립 리뷰 P2를 먼저 재현했다. T2 `_DB_ERRORS`도 일반 reflector 예외와 같은 분기에서 처리하여 `runtime.reflect.failed`만 남기고 B-Q3 없이 다음 claim으로 진행했다. 실제 MySQL에서 두 Job을 enqueue하고 첫 T2 연결을 3회 끊은 결과 B-D8 대기는 **`[1, 1]`**뿐이었다. 필요한 순서는 **`[1, 1, 5]`**다. 첫 T1 terminal과 T2 rollback 상태는 유지되지만 DB 장애 중 다음 claim을 즉시 시작하는 결함이었다.
- 수정 전 단위 **20 failed / 1 passed / 26 deselected**, 실제 MySQL **2 failed / 37 deselected**로 대기 누락 RED를 확인했다. 단위는 DBAPIError · SQLAlchemy TimeoutError · TransactionRetryExhausted, 두 terminal 상태, 정상/filter/handler sink, stop 경계를 포함한다. MySQL은 기존 소진 검사와 두 Job 검사를 각각 실패시켰으며 두 Job이 실제 처리됐음에도 관측값이 `[1, 1]`임을 확인했다.
- WorkerLoop의 T2 처리에 `except _DB_ERRORS`를 일반 `Exception`보다 먼저 추가했다. 기존 `_db_error`의 안전한 DB event → best-effort `runtime.reflect.failed` → claim 오류와 같은 `idle_wait(settings.error_backoff_sec)` 순서로 다음 claim 전 interruptible B-Q3를 적용한다. B-D8 내부 1초 두 대기와 소진 후 B-Q3 5초는 별개다. T2 자체를 loop에서 다시 실행하지 않으며 T1 결과·produced·failure_kind를 수정하지 않는다. 일반 reflector/domain 예외에는 B-Q3를 적용하지 않고 `BaseException`은 계속 전파한다.
- filter/handler 일반 Exception이 두 event sink에서 모두 발생해도 B-Q3와 다음 claim 판단을 유지한다. B-Q3 중 stop이면 다음 claim을 시작하지 않는다. `log_event_best_effort`의 검증/sink 분리, `log_event()` API, 기존 `_emit`·observer 실패 격리 정책은 변경하지 않았다. 첫 수정 후 회귀는 **85 passed / 1 failed**였으며 기존 enqueue DB 오류 검사에서 테스트 도우미가 빈 queue의 2초 대기만 허용해 새 B-Q3 5초를 거부했다. 종료가 이미 요청된 도우미에는 실제 interruptible `stop.wait` 경계를 적용했고 최종 targeted에서 모두 통과했다.
- 비차단 보강은 테스트만 변경했다. 외부 Case 행 lock을 잡은 채 두 T2의 도착과 MySQL `performance_schema.data_lock_waits`의 **서로 다른 요청 thread 2개**를 확인한 뒤 lock을 해제해 실제 경합을 강제한다. 후속 execution INSERT가 같은 Connection에서 성공한 사실을 확인한 뒤 표식 UPDATE 0 rows를 주입해 Case 변경·후속 execution·표식의 전체 rollback을 검증한다. 두 Job 소진 테스트도 INSERT 뒤 연결 kill을 3회 주입하여 rollback을 확인하고 B-Q3 후 두 번째 Job의 정상 처리와 표식 기록을 검증한다. 이 보강의 실제 MySQL 집중 검사는 **5 passed / 35 deselected**였다. 실제 Case 구현의 의무나 production 정책은 추가하지 않았다.
- 새 `recovery/exhausted_next_job`, `zero_guard/insert_then_marker_failure` parameter를 gate 단위 inventory에 먼저 추가했다. 개별 누락 **2 failed / 719 passed / 109 deselected** RED는 전체 증거 삭제(`all`)가 기존 gate에서 통과하는 문제를 확인한다. gate와 하위 실제 보고서 inventory에 두 parameter를 추가해 GREEN으로 고정했다. README에는 DB 실패의 B-Q3와 domain 예외의 대기 없음만 명시했다. Contract·Decision·Baseline·Plan 의미 및 공용 DB helper는 변경하지 않았다.

**검증 — 이번 후속에서 직접 실행**

- Worker·jobs·structured logging·gate targeted **1107 passed**, 208.74초, exit 0. 실제 MySQL **140 passed · skip 0 · xfail 0**, phase **420 passed**, 신규 T2 전체 **40 passed**, gate unit **830 passed**가 포함된다.
- 실제 MySQL require **206 passed / 44 deselected**, 383.93초, exit 0. deselected는 선택 범위의 비-MySQL 테스트다. JSON/JUnit gate **206 tests · skip 0 · xfail 0 PASS**, phase **618 passed**. 하위 실제 보고서 suite도 별도 **205 passed · skip 0 · xfail 0**, phase **615 passed**로 gate를 통과했다. 상위/하위 수는 서로 다른 실행이며 고유 test 수로 합산하지 않는다.
- 실제 보고서의 필수 parameter **721/721 누락 거부**(103 × 7 layer), T2 **280/280 누락 거부**(40 × 7)를 확인했다. `worker_t2` role 전체와 scenario 9개 개별 누락도 **10/10 거부**했다. 이번 수정 전 gate RED와 수정 후 실제 JSON/JUnit 증거를 모두 보존한다.
- 전체 pytest **3248 passed / 26 skipped**, 633.13초, exit 0. 전체 실행의 MySQL JSON/JUnit gate도 **206 tests · skip 0 · xfail 0 PASS**, phase **618 passed**이며 하위 실제 suite **205 passed**, phase **615 passed**, parameter 누락 **721/721 거부**(T2 280)를 다시 대조했다. skip은 기존 선택적 검사 **Search typer 미설치 4 · Case 로컬 영상 없음 2 · Eval 로컬 미디어/zip 없음 5 · Recording 영상/pair/VIDEO_INDEX opt-in 미지정 15**이며 MySQL skip은 없다. 기존 Recording synthetic media smoke도 전체 실행에서 통과했다.
- Boundary **위반 0**, Contract fixture **구조 62 · JSON 26 · 의미 104 PASS**. workflow **Actionlint 5 files · YAML policy · bash -n/ShellCheck 5 run steps PASS**이며 Python pyflakes는 이 정적 검사에서 비활성이다. 원격 CI는 실행하지 않았다.
- 요청된 코드 리뷰 스킬의 읽기 전용 source 검토에서 새 Critical/Important/Minor 지적은 없었다. 해당 reviewer가 직접 실행한 집중 단위는 **26 passed / 21 deselected**이며 MySQL은 source만 검토했다. 단위 대기 순서 테스트의 B-D8 두 대기는 주입값이므로 실제 B-D8의 3회 소진·전체 `[1, 1, 5]` 증거는 구현자의 실제 MySQL 실행이다. 이 검토는 사용자 독립 재리뷰를 대체하지 않는다.

**남은 위험 · 상태**

- 이전 전체 회귀의 단발 MySQL **2013/10053** 오류는 **원인 미확정 위험으로 유지**한다. 이번 수정이 해당 socket 오류의 원인을 규명하거나 해소했다는 의미가 아니다. sink 장애 시 해당 event 유실 가능성, COMMIT 결과 불명에 대한 기존 helper/idempotency 한계도 유지한다.
- RT-06의 T2 startup/periodic 재전달과 실제 Case 8-8 연결은 여전히 제외한다. 이번 변경은 기존 B-Q3 적용 누락의 수정이며 새 retry 정책이나 즉시 T2 재실행을 추가하지 않는다. RT-04 전체는 재리뷰 전까지 **IN_PROGRESS**, `Refs #291`, PR 번호·merge SHA **pending**을 유지한다.
- 검증 증거는 기존 폴더를 재사용하지 않은 `C:/Users/cheol/AppData/Local/Temp/rt04b-p2-20261010/`에 보존한다. 보호 JSON의 SHA-256과 HEAD/index가 시작 시점과 동일함을 확인했고 기존 `.pytest-*` 폴더는 수정·staging하지 않았다. 작업 전용 MySQL의 port/datadir/version을 확인하고 해당 서버만 정상 종료했다(exit 0). 커밋·staging·push·PR 생성 없음. 최종 `git diff --check`와 status를 확인하고 독립 재리뷰를 요청할 수 있는 상태이며, 이번 검증은 사용자 재리뷰 통과 판정을 대신하지 않는다.

### 2026-10-11 RT-04(b) 최종 독립 재리뷰 — P2 해소 및 DONE 판정

- 사용자가 전달한 독립 재리뷰 통과 결과를 후속 완료 기록으로 추가한다. 기존 리뷰·P2 발견·수정·검증 이력과 당시 IN_PROGRESS/Refs/pending 기록은 그대로 보존하며, 현재 상태와 최종 PR 연결은 이 기록과 위 상태/PR 표를 따른다. 이번 문서 갱신에서 아래 테스트를 새로 실행한 것으로 기록하지 않는다.
- 이전 P2인 **T2 DB 오류 B-D8 소진 뒤 B-Q3 대기 누락은 해소**됐다. 수정 전 실제 MySQL 관측은 **`[1,1]`**, 수정 후는 **`[1,1,5]`**다. B-D8 두 재시도 대기 뒤 interruptible B-Q3를 거쳐 다음 claim을 시작한다. 이미 확정된 T1과 T2 rollback 경계를 보존하고 일반 reflector 예외에는 B-Q3를 적용하지 않으며, T2 즉시 재실행은 추가하지 않았다.

**독립 재리뷰 — 직접 실행 결과**

- Worker 단위 **47 passed**.
- 실제 T2 MySQL **40 passed · skip 0 · xfail 0**.
- 신규 gate parameter 단위 **14 passed**.
- T2 JSON/JUnit **40 tests · 120 phases PASS**.
- 신규 parameter 2개의 증거 제거 **14/14 거부**(2 × 7 layer).
- 보존된 전체 MySQL 보고서에 **현재 gate를 적용하여 206 tests PASS**. 이는 전체 MySQL suite 206건을 재리뷰에서 새로 실행했다는 의미가 아니다.
- `git diff --check` **PASS**.

**구현 단계 실행 결과 — 재리뷰에서는 보존 증거 대조**

- targeted **1107 passed**, 실제 MySQL require **206 passed**, 하위 실제 suite **205 passed**는 위 구현 단계에서 직접 실행한 결과다. 상위/하위는 별도 실행이며 고유 test 수로 합산하지 않는다.
- 전체 pytest **3248 passed / 26 skipped**도 구현 단계 실행 결과이며, 재리뷰에서는 보존된 출력·JSON/JUnit 증거를 대조했다. 전체 pytest를 재리뷰에서 다시 실행한 결과와 구분한다.
- parameter 누락 **721/721**, T2 **280/280**, role/scenario **10/10 거부**는 구현 단계 실행 결과를 대조한 것이다. 재리뷰가 새로 실행한 신규 parameter 증거 제거 **14/14**와 구분한다. 기존 boundary·Contract fixture·workflow 통과 기록도 구현 단계 증거로 보존한다.

**최종 판정 · 합의 · 후속 범위**

- **T2 · E2E-0 최종 판정 PASS**, RT-04 최종 상태는 **DONE**이다. 위에 기록한 Issue #291의 Case Owner·Runtime Owner 합의와 [PR #337](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/337)의 metric 정의를 반영했다. `runtime.retry.after_case_stopped_count`는 **attempt >= 2 AND NOT_APPLIED AND STOPPED_WAITING**만 기록하며 attempt 1 · CANCELLED · SUPERSEDED · ALREADY_APPLIED · reflector 예외는 제외한다.
- RT-04(a)는 **PR #336 · merge SHA `d08b29a`**다. RT-04(b) PR 번호·merge SHA는 **pending**, 최종 PR 연결은 **`Closes #291`**이다. 최종 PR 생성·merge 또는 Issue close가 이미 실행됐다는 의미는 아니다.
- 실제 Case 8-8의 execution_id 영속 연결과 RT-06 startup/periodic 재전달 scan은 후속 범위다. fake reflector로 검증한 T2/E2E-0 판정이 실제 Case 연결 완료를 뜻하지 않는다.
- event sink 장애 중 해당 event 유실 가능성은 허용된 한계로 유지한다. 단발 **MySQL 2013 / Windows 10053** 오류는 해결됐다고 단정하지 않고 **원인 미확정 위험으로 유지**한다.
- **원격 GitHub Actions 미실행**. 이번 갱신은 RT-04 절만 수정하며 커밋·push·PR 생성은 하지 않는다.

## RT-05 — Lease · heartbeat · fencing · 협력적 중단

Status: DONE · Issue: #292 · Audit: A · 최종 PR 연결 문구: `Closes #292` · PR 번호 / Merge SHA: pending

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| pending | RT-05(a) heartbeat · lease · fencing (독립 재리뷰 통과) | pending |
| pending | RT-05(b) cancel · checkpoint (P2 해소·최종 독립 재리뷰 통과, `Closes #292`) | pending |

아래 구현 단계의 IN_PROGRESS / `Refs #292` 및 미구현 범위 표기는 당시 이력으로 보존한다. RT-05의 현재 최종 상태와 검증 주체 구분은 이 절 마지막의 「최종 독립 재리뷰 통과」 기록을 따른다. DONE은 이번 최종 판정이며 PR 생성·merge·Issue close가 이미 실행됐다는 의미는 아니다.

### 구현 결과

- claimed execution마다 `common/jobs/heartbeat.py`의 전용 thread를 생성한다. main thread는 claim → handler → T1을 수행하고, heartbeat thread는 B-D9 engine의 Connection 하나를 보관하여 B-L1 주기로 조건부 lease UPDATE를 실행한다. DB 시간은 `NOW(6)`이며 lease duration은 기존 WorkerSettings를 소비한다.
- thread는 monotonic clock의 `T0 + k × interval`을 따른다. 동기 DB 시도가 interval보다 길면 완료 뒤 해당 시도 중 지나간 tick을 집계하고 다음 미래 tick을 기다린다. 중첩 시도·밀린 tick 몰아 실행·transaction helper 재시도는 없다. 실패한 연결은 닫고 다음 tick에서 새 연결을 연다.
- 갱신 0행은 observer/logger 호출 전에 `ExecutionContext.ownership`의 내부 fence에 기록한다. WorkerLoop의 T1 재기록, B-D8 매 시도 진입, callback 진입, 최종 COMMIT 경계가 fence를 확인한다. 기존 finish의 `RUNNING ∧ lease_owner=owner` UPDATE 조건은 유지한다. ownership 상실은 handler taxonomy FAILED로 바꾸지 않고 `runtime.execution.finish_rejected`로 기록한다.
- handler 성공·모듈 실패·일반 예외·BaseException·종료 신호 이후 모든 실행 종료 경로에서 heartbeat stop + join을 finally로 보장하고 전용 connection/소유 engine을 정리한다. 일반 logger/filter/handler·observer 예외는 격리하고 unsafe logging 검증 오류와 BaseException 정책은 유지한다.

### Plan 대비 변경

- RT-05(a)만 구현한다. cancel port, CancelSignal, checkpoint, 중단 표식 읽기·Case cancel 연결은 RT-05(b)에 남긴다. 기존 reserved cancel injection 필드는 유지한다.
- 갱신 SQL·연결 lifecycle은 별도 repository public API 대신 `LeaseConnection` 내부에 둔다. 후속 cancel이 같은 연결/갱신 경계를 확장할 수 있다. Contract·Decision·Baseline 변경 없이 선택한 implementation detail이다.
- 실행별 factory로 B-D9 NullPool engine을 소유하고 finally dispose한다. 테스트는 별도 heartbeat engine을 주입할 수 있다. Worker 업무 engine의 QueuePool checkout을 공유하지 않는다.

### 새 implementation detail

- `OwnershipFence`의 commit lock은 최종 check부터 DB COMMIT까지 유지한다. 로컬 ownership 상실 표식과 COMMIT의 순서를 직렬화하고, DB owner 이전과 T1 경합은 기존 조건부 UPDATE·InnoDB row lock으로 판정한다. heartbeat DB 호출 전체를 이 lock 안에 넣으면 T1 row lock과 교착할 수 있어 DB 갱신은 밖에서 실행한다.
- `run_worker_transaction`에 선택적 `before_attempt` / `commit_guard` 경계를 추가했다. helper는 Runtime ownership을 import하지 않으며 claim·T2·기존 호출은 기존 동작이다. 모든 T1 DB 재시도에 같은 fence가 적용된다. API transaction 경계는 변경하지 않는다.
- heartbeat thread의 BaseException은 raw threading traceback으로 노출하지 않고 보관·fence 후 소유 main thread의 join에서 재전파한다. cleanup의 추가 BaseException이 기존 primary BaseException을 덮지 않게 한다.
- 관측값은 immutable `HeartbeatObservation`에 attempt_ms·성공 간격 기준 lag_ms·skipped_tick_count·consecutive_failures로 전달한다. 기존 안전한 logging field 계약을 확장하지 않고 duration은 `duration_ms`, 숫자 count는 안전한 `status` 숫자 token으로 기록한다. skip 관측은 느린 시도 완료 뒤에 남는다.
- observer/logger에 시간이 걸려 다음 tick을 놓친 경우도 다음 시도 전에 미래 tick으로 이동하고 누락 tick을 집계한다. 0행 표식은 empty COMMIT 이전에 설정하여 COMMIT 오류에도 유지한다. commit guard 진입의 예외를 transaction helper의 primary 보존 범위에 포함하며 connection close 이후 engine dispose 오류가 첫 BaseException을 덮지 않게 한다. 독립 리뷰에서 재현한 경계 문제를 TDD로 보정한 implementation detail이다.
- 전체 회귀에서 실제 MySQL 하위 suite가 test harness의 300초 subprocess 제한에 걸렸다. migration fixture를 포함한 확대 inventory의 느린 로컬 실행을 허용하기 위해 이 테스트 제한만 900초로 늘렸다. Runtime timeout·Contract·Decision·Baseline이나 gate의 증거 판정 조건을 바꾸지 않는다.

### Owner 확인 포인트

- 김준영 Audit A: 0행 fencing 및 T1 commit 직전 경합, B-D8/loop 재시도 진입 fence, B-L1 skip 계산·관측 지연, B-D9 전용 연결 재사용·재연결, BaseException 보존 경계. Contract·Accepted Decision·Baseline 값/의미 변경 없음. 다른 Owner에 새 의무 없음.

### Verification

- 구현 전 WorkerLoop·claim_one/finish·transaction helper·역할별 engine·기존 테스트와 Issue #292, Plan §6/§12, Baseline을 직접 확인했다.
- 초기 RED: heartbeat lifecycle/composition 부재로 unit 6 + 실제 MySQL 17 = **23 failed**. 추가 gate RED: heartbeat family 누락을 허용하는 **7 failed**. cleanup 중 BaseException이 primary를 덮는 회귀 **1 failed**를 확인한 뒤 수정했다.
- 독립 리뷰 지적과 추가 장애 회귀: 느린 observer의 off-cadence 실행 **1 RED**, 0행 UPDATE 뒤 empty COMMIT 실패 **실제 MySQL 1 RED**, guard loss/KeyboardInterrupt + rollback 실패 **2 RED**, connection close SystemExit + engine dispose 오류 **1 RED**, renewal SQL SystemExit + rollback 오류 **1 RED**를 각각 확인해 수정했다. 신규 gate family 누락(zero_commit_failure/owned_cleanup)도 각각 **1 RED**를 확인했다. 보정 후 core **117 passed**, heartbeat MySQL **27 passed**, 추가 B-D8/B-Q3 retry fence **2 passed**.
- 첫 MySQL require 실행은 실행 도중 소스를 수정하여, 먼저 import된 구버전 LeaseConnection과 뒤에 import된 신버전 composition이 섞였다. traceback의 `unexpected keyword argument 'fence'` 등 **83 failed / 146 passed**를 최종 검증 근거에서 제외하고 원출력을 보존한다(`require.txt`). 이후 고정된 코드로 `require-final`을 실행했으며, 재개 시 해당 실행의 종료 코드와 보존 보고서를 먼저 확인했다.
- 실제 MySQL 8.4.7 작업 전용 서버(port 13329, `/tmp/rt05-20261011/data`)와 `rt05_test`/harness 일회 schema를 사용한다. 기존 Windows MySQL service와 사용자 DB는 변경하지 않는다. 증거는 `C:/Users/cheol/AppData/Local/Temp/rt05-20261011/`에 보관한다.
- **재개 시 보존 증거 대조:** 실행 중이던 `require-final` session의 완료 응답은 **exit 0**, 최종 **234 passed / 4 skipped / 3271 deselected**다. skip 4개는 `typer`가 없는 비-MySQL Search 수집 항목이다. JSON/JUnit의 실제 MySQL **234 tests / 702 phases passed / skip 0 / xfail 0**, heartbeat **28 passed**를 대조했다. 하위 실제 MySQL suite **233 passed / skip 0 / xfail 0**, JSON/JUnit gate PASS, parameter 증거 누락 **896/896 거부**(heartbeat **175/175**), heartbeat role/scenario 누락 **11/11 거부**도 보존 보고서로 확인했다. 기존 standalone heartbeat 27개와 달리 최종 inventory는 transaction/loop retry fencing parameter를 분리하여 28개다.
- **반복하지 않은 검증:** 고정된 구현·테스트·gate·README 11개 SHA-256이 중단 시 manifest와 일치하여 core **117 passed**, gate unit **1025 passed**, boundary **위반 0**, Contract fixture **62/26/104 검사 PASS**, workflow YAML policy·bash syntax·ShellCheck **5 run steps PASS** 및 actionlint **5 files / 0 errors**의 기존 실행 증거를 재사용했다. 독립 source 리뷰에서 지적된 네 경계 수정과 재리뷰 통과도 보존 근거이며, 재개 후 구현·리뷰를 다시 수행하지 않았다.
- **보호 파일 대조:** 기존 manifest에 포함된 미추적 pytest/recording 파일 **1052개**의 SHA-256 변경 0건. 이전 manifest에 빠진 dotfile `.env` 17개는 과거 해시 대조 대상이라고 주장하지 않는다(확인된 최종 수정 시각은 2026-10-07). 재개 시 별도 해시를 보관했으며 해당 경로를 수정·삭제·staging하지 않았다.
- **재개 후 첫 전체 실행:** `full`은 **exit 1 / 3482 passed / 26 skipped / 1 failed**다. 실패는 `test_actual_report_rejects_each_missing_migration_check`의 하위 실제 MySQL subprocess **300초 TimeoutExpired** 한 건이며 원출력·JSON/JUnit을 보존한다. 이전 통과 하위 suite의 JUnit 실행 시간은 **217.049초**다. 실패 뒤 Python 하위 프로세스 잔존 없음, 남은 일회 schema 1개와 테스트 계정 0개를 확인하여 해당 schema만 정리했다. 테스트 제한 변경 후 구현·gate 판정·테스트 10개는 이전 해시와 같고, `test_migration_gate.py`만 제한/설명 주석이 변경됐다. 변경 후 11개 해시를 별도 고정하고 `full-final`을 새 임시 경로에서 실행한다.
- **재개 후 직접 실행 GREEN:** 고정한 `full-final` 전체 pytest **exit 0 / 3483 passed / 26 skipped / 990.27초**, 실제 MySQL **234 tests / 702 phases passed / skip 0 / xfail 0**, heartbeat **28 passed**. skip 26개는 비-MySQL `typer`·로컬 미디어·영상 opt-in 미충족 항목이다. 상위 JSON/JUnit gate **PASS**, 하위 실제 MySQL **233 passed / skip 0 / xfail 0 / 297.527초**와 하위 JSON/JUnit gate **PASS**, 새 parameter 누락 증거 **896/896 거부**(heartbeat **175/175**)를 직접 확인했다. 테스트 harness timeout RED → 전체 GREEN을 별도 기록하며 첫 실패 보고서를 덮어쓰지 않는다.
- **최종 해시:** timeout 수정 뒤 고정한 코드·테스트·gate·README **11개 변경 0**, 기존 보호 파일 **1052개 변경 0**, 재개 시 별도 기록한 `.env` **17개 변경 0**. 이전 require 및 정적 검사 증거는 Runtime/판정 코드가 유지된 범위의 보존 근거로 구분한다. 증거 manifest는 `code-hashes.json`, `code-hashes-post-timeout.json`, `preserved-evidence-hashes.json`, `resume-verification.json`, `final-hashes.json`, `verification-summary.json`이다.
- **MySQL 정리:** 최종 pytest 프로세스 잔존 없음. MySQL **8.4.7 / port 13329 / datadir `/tmp/rt05-20261011/data/`**를 확인한 뒤 test schema·계정 **0**, 기타 비시스템 schema·비기본 계정 **0**을 검사하고 `rt05_test`를 제거했다. SQL SHUTDOWN 성공, 소유 server exec session **59725 exit 0**, 기존 PID·pid file·socket 없음, port **13329 연결 거부(10061)**를 확인했다. 종료 뒤 WSL의 Linux log 경로는 존재하지 않아 shutdown log에 근거한 주장은 하지 않는다. Windows에 정리 JSON과 실행 결과를 보존하며 기존 MySQL service는 변경하지 않았다.
- **최종 diff:** `git diff --check` **PASS**, branch `feature/runtime-heartbeat-fencing`, index 변경 **0**. 작업 변경은 tracked 9개 + 신규 구현/테스트 3개 = **12개**이며 보호된 기존 미추적 경로는 그대로다. 커밋·푸시·PR 생성 없이 독립 재리뷰 상태로 남긴다.

### 남은 위험

- B-D9는 I/O 단계별 timeout이며 whole-attempt 상한이 아니다. DB 호출이 길면 stop/join·skip 기록도 지연될 수 있다. 강제 thread kill이나 임의 join timeout은 도입하지 않는다.
- SIGINT/SIGTERM은 기존 정책대로 handler와 T1을 강제 중단하지 않고 다음 idle 경계에 반영한다. ownership이 유지되는 동안의 T1 DB 장기 장애는 종료를 지연시킬 수 있다.
- T1 COMMIT 응답 유실 뒤 heartbeat가 이미 terminal인 row의 0행을 관찰하면 보수적으로 T1 재시도를 차단한다. durable terminal 자체는 유지되며 T2 재전달은 RT-06이 담당한다.
- cancel·checkpoint(RT-05(b)), STALE/sweep·재전달(RT-06), 실제 handler(RT-10)는 미구현이다. RT-05 전체 상태는 IN_PROGRESS다. 원격 CI 미실행. 이번 작업은 커밋·푸시·PR 생성 없이 독립 재리뷰용 변경으로 남긴다.

### RT-05(a) 독립 재리뷰 통과 — 후속 기록

사용자가 전달한 독립 재리뷰 결과를 기존 구현·검증 이력에 추가한다. **병합 차단 문제 없음**으로 판정됐다. 이번 갱신은 이 절의 문서 기록만 추가하며 코드·테스트 수정이나 테스트 재실행은 하지 않는다.

| 상태 | RT-05(a) PR 연결 | PR 번호 | Merge SHA |
| --- | --- | --- | --- |
| RT-05 IN_PROGRESS | `Refs #292` | pending | pending |

**리뷰어 직접 실행 결과:**

| 검증 | 결과 |
| --- | --- |
| 핵심 단위 회귀 | 168 passed |
| gate unit | 1,025 passed |
| 실제 MySQL inventory | 233 passed · skip 0 · xfail 0 |
| heartbeat MySQL | 28 passed |
| parameter 증거 누락 | 896/896 거부 |
| heartbeat parameter 증거 누락 | 175/175 거부 |
| role/scenario 증거 누락 | 68/68 거부 |

**구현 단계 보존 증거:** 아래 수치는 구현 단계에서 실행해 보존한 결과이며, 이번 리뷰어 직접 실행 결과와 구분한다.

| 검증 | 보존 결과 |
| --- | --- |
| 전체 pytest | 3,483 passed / 26 skipped |
| 실제 MySQL | 234 passed · skip 0 · xfail 0 |

- **정책 판정:** monotonic fixed-rate scheduling, Worker 업무 연결과 분리된 heartbeat 전용 DB 연결, ownership 상실 후 T1 commit·재시도 fencing, 실행 종료 경로의 heartbeat thread cleanup 판정이 통과했다.
- **Timeout 한계:** 전체 heartbeat 시도를 묶는 단일 wall-clock deadline은 없다. Baseline의 단계별 connect/read/write **2/5/5초**를 적용하며, 이는 whole-attempt 상한을 보장하지 않는다. 기존 stop/join 지연 위험은 유지한다.
- **900초 변경 범위:** 전체 실제 MySQL 하위 suite를 실행하는 test harness의 subprocess timeout에만 적용된다. production timeout이나 gate의 통과 조건을 완화하지 않는다.
- **비차단 후보:** `Heartbeat.start()` 중복 호출 방지, tick 경계 및 COMMIT 성공 직후 ownership 상실 회귀 보강, 원격 CI 실행 시간 확인을 후속 검토 후보로 남긴다.
- **남은 범위:** RT-05(b) cancel이 남아 있으므로 RT-05 상태는 **IN_PROGRESS**, RT-05(a) 연결은 **`Refs #292`**를 유지한다. PR 번호와 merge SHA는 **pending**이다.

---

### RT-05(b) cancel · checkpoint — 독립 재리뷰 준비 (2026-10-11)

**Status: IN_PROGRESS · Issue: #292 · 연결: `Refs #292` · PR / Merge SHA: pending.** 이번 범위가 RT-05의 마지막 구현 PR에 해당하지만 독립 재리뷰 이전에는 DONE이나 Issue close를 기록하지 않는다. 커밋·푸시·PR 생성 없이 로컬 변경으로 남긴다.

**구현 결과**

- 공개 port는 승인된 `request_cancel(conn: Connection, job_ids: Iterable[str]) -> None`이다. Case caller transaction에 참여하며 commit·rollback·retry·물리 상태 반환이 없다. 전체 iterable의 안전한 ID 검증과 중복 제거를 모든 SQL보다 먼저 수행한다. 미등록 job/terminal은 no-op이다.
- job_id를 정렬하고 `uq_job_execution_job_attempt` index를 강제한 `ORDER BY job_id, attempt, execution_id FOR UPDATE`로 해당 job의 모든 attempt를 먼저 잠근다. 모든 대상 잠금을 확보한 뒤 QUEUED는 NOW(6) marker/ended_at과 빈 produced로 CANCELLED, RUNNING/STALE은 최초 marker만 기록한다. 미래 available_at도 제외하지 않는다. MySQL EXPLAIN으로 filesort 없는 unique index 접근을 검증한다.
- thread-safe CancelSignal은 첫 request만 true를 반환하며 최초 취소 checkpoint monotonic 시각을 보존한다. ExecutionContext에 구체 타입과 checkpoint를 연결하고 KindRegistry는 CancellationRequested를 재전파한다. WorkerLoop는 기존 ownership fence/owner 조건부 finish와 retry 경계에서 내부 CANCELLED 결과를 기록한다. 일반 handler taxonomy와 KeyboardInterrupt/SystemExit 정책은 유지한다. 마지막 checkpoint 뒤 정상 완료를 취소로 덮지 않는다.
- 전용 heartbeat transaction은 lease UPDATE와 owner/status가 일치하는 marker SELECT를 수행한다. 성공한 commit 이후 signal을 설정하고 DB `TIMESTAMPDIFF(MICROSECOND, cancel_requested_at, NOW(6))` marker 나이에 SELECT 시작부터 signal 전달까지 monotonic 경과를 더해 `runtime.cancel.observe_latency_ms`로 한 번 기록한다. host wall-clock과 DB 시각을 빼지 않으며 읽기·COMMIT 대기를 포함한다. DB SELECT의 server 시작과 client 시작 차이만큼 보수적으로 측정될 수 있다.
- Baseline §9의 `runtime.cancel.terminal_latency_ms`는 DB `TIMESTAMPDIFF(MICROSECOND, cancel_requested_at, ended_at)`이다. 성공한 T1 commit acknowledgement 뒤에만 로그를 내고 unknown-COMMIT receipt 복구에서도 같은 DB facts를 사용한다. 요청된 checkpoint부터 T1 commit acknowledgement까지의 monotonic 지연은 **별도 `runtime.cancel.checkpoint_to_terminal_ms`**로 기록하여 Baseline metric 의미를 유지한다. 이 추가 지표는 DB retry 대기를 포함하고 heartbeat join은 제외한다. 일반 logger/filter/handler/observer 장애는 signal/terminal을 바꾸지 않는다. DB 읽기·commit 오류는 signal 전달 없이 다음 tick으로 넘긴다. 0행 ownership loss는 별도 fence다.

**Plan 대비 변경 / 새 implementation detail**

- 갱신 UPDATE 뒤 같은 transaction의 marker SELECT를 사용한다. MySQL UPDATE RETURNING을 전제하지 않고 UPDATE row lock 아래 상태·marker·DB 시간을 읽기 위한 내부 구현 선택이다. transaction이나 B-L1/B-D9 값은 바꾸지 않는다.
- `HandlerResult`와 기존 Case `ReflectionInput`은 성공/실패 전용 surface를 유지한다. checkpoint 취소는 별도 내부 `CancelledExecution`으로 T1에만 전달한다. Case가 같은 transaction에서 이미 CANCELLED 정산한 job에 새 reflector 의무를 만들지 않기 위해 CANCELLED는 기존 T2 reflector에 전달하지 않는다. QUEUED 즉시 취소도 Worker/T2를 거치지 않는다. RT-06은 이 경계를 재전달 설계에 반영해야 한다.
- production sweep이 아직 없으므로 MySQL 테스트의 `sweep_boundary`만 STALE row 잠금 → marker 재확인 → attempt 2 INSERT 경계를 재현한다. RT-06 production scheduler나 retry 정책을 이번에 구현하지 않는다.
- RT-07 Usage ledger table도 아직 없다. QUEUED 취소 후 claim 불가/started_at 없음과 handler/provider 진입 불가를 검증한다. 영속 UsageRecord table에서 0건을 직접 조회했다고 주장하지 않는다.
- 요청문의 checkpoint 구간을 기존 terminal metric 전체 의미로 해석하지 않고 별도 내부 진단 지표로 보완한다. Baseline이 정의한 요청→CANCELLED metric은 DB facts 그대로 유지한다. Baseline 변경이나 새 Owner 의무가 없는 implementation detail이다.
- Contract 변경: 없음. Accepted Decision 변경: 없음. Baseline 값/의미 변경: 없음. Case 코드/Contract/HTTP command 변경: 없음. Plan 수정: 없음.

**Owner 확인 포인트**

- [Case Owner 승인 댓글](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/292#issuecomment-6107446434)의 None 반환·Case 먼저/Runtime 나중 잠금·caller-owned transaction·모든 비terminal attempt 취소 요구를 실제 issue/comments에서 확인했다. 기존 Case repository를 소비해 CANCELLED 정산과 Runtime 전이가 함께 commit/rollback되는 것을 검증한다.
- Runtime/Ops Audit A: ordered index 잠금, claim/sweep/finish commit 경합, ownership/cancel 구분, DB 기반 observe/terminal 지연 및 추가 checkpoint 구간, Case 성공/실패 T2 surface 유지, RT-06 marker 재확인 경계.

**Verification**

- RED: signal/checkpoint/port 부재로 unit **14 failed** (`.codex-scratch/rt05b-red-unit.txt`). heartbeat 연결 전 실제 MySQL **14 failed / 1 passed** (`rt05b-red-heartbeat.txt`, `cancel_observe` 연결 부재). 새 gate 필수 증거 제거를 기존 gate가 허용해 **40 failed / 1199 passed** (`rt05b-gate-red.txt`). 구현 뒤 초기 targeted **146 passed**, 확장 gate unit **1257 passed**, checkpoint→commit metric unit 포함 cancel unit **15 passed**.
- 초기 MySQL 서버 라이브러리 경로 누락, sandbox 접속 실패, 테스트 파일명 충돌, 미구현 Usage table 조회, SQLAlchemy event listener 실행 중 제거 오류는 원출력에 보존한다. 해당 실행을 최종 통과 증거로 사용하지 않는다.
- 읽기 전용 source 사전 검토는 지표 2건을 P2로 지적했다. checkpoint 구간으로 terminal metric 의미가 달라진 문제와 성공 COMMIT 대기를 observe metric에서 빠뜨린 문제를 **3 RED**로 재현했다(`rt05b-latency-red.txt`). 초기 보정 targeted는 **128 passed / 1 failed**로, 남은 실패는 DB Decimal→float와 Python timedelta float 표현의 미세 오차였다. DB microsecond 정밀도보다 작은 0.000001 ms 절대 오차만 테스트에서 허용한다. 실제 경쟁 connection/schema의 `performance_schema.data_lock_waits` 확인을 추가한 경합 테스트 **19 passed**. 이 사전 검토는 최종 독립 재리뷰/acceptance가 아니다.
- 보정 전 전체 MySQL require는 **271 passed / MySQL skip 0 / xfail 0**, 하위 inventory **270 passed**, 7단계 parameter 누락 **1113/1113 거부**(cancel **217/217**). 전체 명령의 비-MySQL 수집 skip 4개는 typer 부재다. 이후 지표 수정/테스트 보강이 있어 이 실행을 최종 소스 전체 검증으로 주장하지 않는다.
- 최종 보정 targeted **129 passed** (`rt05b-corrected-green.{json,xml}`), gate unit **1259 passed**, cancel 단위 **15 passed**. 앞선 넓은 jobs/Worker targeted **346 passed**는 지표 보정 전 결과이며 보정 후 subset/전체 검증과 구분한다.
- 최종 MySQL 8.4.7 require: **272 passed / MySQL skip 0 / xfail 0**, setup/call/teardown **816 phases passed**, JSON/JUnit gate PASS. 명령: `.venv/Scripts/python.exe -B -X utf8 -m pytest -m mysql --ignore=tests/common/db/integration/test_migration_gate.py -q -p no:cacheprovider --basetemp=.codex-scratch/rt05b-require-final --tb=short --mysql-report=.codex-scratch/rt05b-require-final.json --junitxml=.codex-scratch/rt05b-require-final.xml`。`DAESINGO_REQUIRE_MYSQL=1`을 사용했다. 전체 명령의 skip 4개는 typer 부재의 비-MySQL 수집 항목이다. inventory 재실행/7단계 mutation 테스트 자체는 다음 전체 pytest에서 실행하여 acceptance suite를 이 단계에서 중첩 반복하지 않는다.
- 실제 최종 require JSON에서 모든 role/scenario 제거와 각 필수 parameter mark의 role/scenario/parameter 필드 일부 제거 **593/593 거부** (`rt05b-require-final-partial-mutations.json`). 모든 기존 Case acceptance inventory를 유지한다.
- Boundary **PASS — 위반 0**, Contract fixture **구조 62 / JSON 26 / 의미 104 PASS**, workflow **Actionlint 5 files / 오류 0 + YAML policy / bash -n / ShellCheck 5 run steps PASS**(pyflakes 비활성), `git diff --check` PASS. workflow source/의존성은 변경하지 않았다.
- 최종 전체 pytest: **exit 0 / 3771 passed / 26 skipped**, **696.60초**. 명령: `.venv/Scripts/python.exe -B -X utf8 -m pytest -q -p no:cacheprovider --basetemp=.codex-scratch/rt05b-full --tb=short --mysql-report=.codex-scratch/rt05b-full.json --junitxml=.codex-scratch/rt05b-full.xml`。실제 MySQL require 환경이며 26 skip은 비-MySQL optional dependency/로컬 원본 영상 opt-in 항목이다. 실제 MySQL **273 tests / 819 phases passed / skip 0 / xfail 0**, 최종 JSON/JUnit gate PASS.
- 전체 실행 안의 실제 하위 inventory도 **272 passed / skip 0 / xfail 0**다. collection/selection/setup/call/teardown/all/JUnit의 7단계 parameter 증거 누락 **1113/1113 거부**, cancel subset **217/217 거부** (`rt05b-full/test_actual_report_rejects_eac0/parameter-mutations.json`). 최종 전체 JSON의 role/scenario 및 parameter metadata 일부 누락도 **593/593 거부** (`rt05b-full-partial-mutations.json`).
- 최종 검증에 고정한 Python 소스/테스트 **13개 SHA-256 변경 0**, 보호 대상 pytest 폴더/recording JSON **1069개 SHA-256 변경 0** (`protected-before.json`, `protected-final.json`). `recording-baseline-negative-001.json` SHA-256은 `27BA6EE8F681F2DF93C4E147589DD932D4632D71631A77EDE194317D42247D99`다. 해당 경로를 수정·삭제·staging하지 않았다. 변경 파일은 15개, staging 0개다.
- 작업 전용 MySQL은 **8.4.7 / port 13331 / `/tmp/rt05b-20261011/data/`** 소유를 SQL assert로 확인한 뒤 종료했다. 잔여 일회 schema/테스트 계정 **0/0**을 확인했다. 정리 보조 script의 LIKE binding 오류를 고친 뒤 SHUTDOWN은 실행됐으나 SQLAlchemy close-time ROLLBACK에서 2013이 발생했다. 별도로 mysqld session **exit 0**과 port closed를 확인했다. 이후 WSL log 경로는 없어서 log 기반 종료 확인을 주장하지 않는다. 기존 Windows MySQL service/사용자 DB 변경 없음.
- 최종 증거·15개 변경 파일 목록·미추적 신규 파일까지 포함한 diff·source hash는 `.codex-scratch/rt05b-20261011/review-package.md`에 묶는다. 최종 검증 이후 수정은 Log/검토 패키지 기록뿐이며 product/test source는 바꾸지 않았다. RT-05는 **IN_PROGRESS / `Refs #292`**, 커밋·push·PR 생성 없음.

**남은 위험**

- B-X1은 DB 정상 구간 p95 20초 측정 목표다. 테스트 전용 짧은 cadence·DB 시간 검증은 운영 p95나 강제 취소 deadline의 실측 증거가 아니다. 실제 capability checkpoint는 RT-10이며 진행 중 provider HTTP·capability 내부 retry·backoff는 반환까지 계속된다.
- 기존 B-D9 단계별 timeout은 heartbeat 전체 시도/join hard deadline이 아니다. sink 장애 시 metric 유실은 가능하다. 원격 GitHub Actions는 실행하지 않는다.
- 실제 RT-06 sweep과의 통합은 RT-06에서 다시 검증해야 한다. 독립 재리뷰 전까지 RT-05는 IN_PROGRESS다.
- RT-06의 unmarked terminal scan은 성공/실패 전용 현재 reflector에 CANCELLED를 반복 투입하지 않도록 Audit A에서 경계를 확인해야 한다. 현재 cancelled row의 case_applied_at을 Runtime이 임의로 채우지 않는다. 모든 terminal의 재전달 구현이 완료됐다고 주장하지 않는다.

---

### RT-05(b) 독립 리뷰 P2 후속 — cancel 지표의 COMMIT acknowledgement 경계 (2026-10-11)

**Status: IN_PROGRESS · `Refs #292` · 독립 재리뷰 전 DONE / Closes / commit / push / PR 생성 없음.** 앞선 RT-05(b) 기록의 terminal 지표 `ended_at` 계산 설명은 구현 당시 상태이며, 아래 후속 수정으로 정정한다.

**발견과 원인**

- 독립 리뷰 P2에서 terminal UPDATE 직후와 COMMIT acknowledgement 사이의 대기가 `runtime.cancel.terminal_latency_ms`에서 누락됨을 확인했다. 로그 출력은 commit 뒤였지만 계산은 DB `cancel_requested_at → ended_at`으로 끝났다. checkpoint 지표는 record 함수가 terminal logger를 호출하고 반환한 뒤 시간을 읽어 logger 지연도 포함했다.
- 실제 MySQL 8.4.7에 DBAPI COMMIT 직전 400ms 지연을 주입한 RED에서 terminal 지표 **11.793ms**가 380ms 하한에 미달했다. 400ms terminal logger 지연 RED에서 checkpoint 지표 **422ms**가 독립 COMMIT acknowledgement 측정 **16ms**와 불일치했다. terminal UPDATE의 row lock 대기 RED에서도 terminal 지표 **12.633ms**가 지연을 누락했다. 세 parameter가 모두 실패했다 (`red2.json`, `red2.xml`).
- 신규 `terminal_ack / commit_delay` parameter의 collection·selection·모든 phase·JUnit 증거를 함께 제거했을 때 기존 gate가 통과한 RED도 확인했다 (`gate-red.xml`: DID NOT RAISE).

**최소 수정과 implementation detail**

- 기존 ownership commit guard를 composition 안에서 감싼다. transaction helper가 `conn.begin()`을 성공적으로 종료한 직후, ownership guard가 풀리기 전의 monotonic 시각을 고정한다. pool cleanup·transaction observer·terminal logger보다 앞선 경계다. 공통 transaction helper·fencing·잠금 순서·cancel port·상태 전이를 바꾸지 않는다.
- terminal UPDATE 또는 기존 unknown-COMMIT receipt의 locking read로 terminal facts가 확인된 같은 T1 안에서 DB `NOW(6) - 최초 cancel_requested_at`을 읽는다. 이 DB marker 나이에 SELECT 시작부터 고정된 acknowledgement까지 monotonic 경과를 더한다. `ended_at`과 marker의 저장값은 변경하지 않는다. SELECT 이전 lock wait와 retry 대기는 DB 나이에 포함되며, SELECT 이후 COMMIT 대기는 monotonic 구간에 포함된다. DB/monotonic clock 연결에는 SELECT 전송 시간과 clock 해상도에 따른 측정 오차가 있다. 테스트는 별도 DB 시간 sample의 client 전후 시각으로 구간을 만들고 acknowledgement와 30ms 허용 오차 내에서 비교한다.
- 내부 `TerminalCommit` receipt가 동일한 종료 시각을 WorkerLoop로 전달한다. 최초 cancellation checkpoint부터 이 시각까지 별도 지표를 기록하므로 느린 terminal logger·pool cleanup·heartbeat join이 추가되지 않는다. bool record를 사용하는 기존 내부 test adapter는 기존 호환 동작을 유지한다. Case 공개 port의 None 반환은 그대로다.
- 매 transaction attempt에서 이전 sample을 지운다. 실제 COMMIT 응답 유실은 성공 경계를 고정하지 않고, B-D8 재시도에서 owner/status/produced/failure가 일치하는 durable CANCELLED를 잠금 확인한 최종 성공 acknowledgement만 사용한다. checkpoint·signal 중복에도 지표는 한 번만 시도한다. 재시도 테스트는 backoff 호출값 1초를 검증하되 실행 대기는 50ms로 줄였다.
- durable 결과 이후 계산과 logging은 terminal transaction 재시도 경계에서 분리하고 일반 Exception을 격리한다. 계산에 DB 오류 타입을 주입해도 추가 UPDATE/COMMIT/retry가 없다. 일반 handler taxonomy 및 KeyboardInterrupt/SystemExit 정책은 유지한다. late SUCCEEDED·ownership 상실·복구 receipt가 아닌 UPDATE 0행에는 cancel terminal/checkpoint 지표가 없다. sink 장애로 metric 유실은 가능하다.
- Contract·Decision·Baseline 값/의미·Plan·Case Owner surface 변경 없음. 요청→CANCELLED 기록의 종료점을 durable acknowledgement에 정합화한 내부 구현 수정이다. **observe 지표의 SELECT 전 구간 보수적 과대계상은 비차단 의견으로 유지하며 수정하지 않았다.**

**RED → GREEN 및 검증**

- 관련 targeted **1493 passed**. 최종 MySQL 지표 parameter **10 passed**: commit_delay / slow_logger / lock_wait / unknown_commit / retry / logger / filter / handler / calculation / zero_rows. lock_wait는 schema와 writer connection이 일치하는 `performance_schema.data_lock_waits`를 확인한 뒤 400ms 지연을 주입한다.
- 최종 targeted 측정: 400ms COMMIT 지연에서 terminal **469.661ms**, checkpoint와 독립 acknowledgement **453ms**. 400ms logger 지연에서는 checkpoint와 acknowledgement **15ms**, terminal **16.788ms**. 실제 row lock 대기에서 terminal **497.776ms**, checkpoint와 acknowledgement **438ms**. COMMIT OK packet 유실 후 복구에서도 두 지표/성공 acknowledgement가 각 1회다 (`final-target.xml`). 이는 시험 지연 회귀이며 운영 p95 측정이 아니다.
- 실제 MySQL require inventory **282 tests / 846 phases passed / MySQL skip 0 / xfail 0** 및 JSON/JUnit gate PASS. 전체 collection의 비-MySQL optional `typer` module skip 4건은 MySQL target에 속하지 않는다. 기존 cancel·claim·sweep·finish 경합도 포함한다 (`mysql.json`, `mysql.xml`).
- 실제 report의 scenario 전체 및 role/scenario/parameter metadata 일부 누락 **624/624 거부** (`mysql-partial-mutations.json`). 신규 10 parameter를 독립 test inventory와 gate에 모두 추가했다.
- boundary 위반 **0**, Contract fixture 구조/JSON/의미 **62/26/104 PASS**. workflow actionlint **5 files / 0 errors**, YAML 정책·bash -n·ShellCheck **5 run steps PASS** (pyflakes disabled). 원격 workflow 실행을 주장하지 않는다.

**최종 검증 / 독립 재리뷰 상태**

- 전체 pytest **3852 passed / 비-MySQL skip 26 / 1018.11s**. skip은 optional dependency·로컬 미디어 opt-in 항목이다. 최종 실제 MySQL **283 tests / 849 phases passed / skip 0 / xfail 0**, JSON/JUnit gate PASS (`full.json`, `full.xml`, `verification-summary.json`).
- 전체 회귀 안의 실제 하위 inventory **282 tests / 846 phases passed**. collection/selection/setup/call/teardown/all/JUnit의 7단계 parameter 누락 **1183/1183 거부**, cancel subset **287/287**, 신규 terminal_ack **70/70** 거부 (`full-tmp/test_actual_report_rejects_eac0/parameter-mutations.json`). 최종 전체 report의 scenario 전체 및 role/scenario/parameter 일부 누락도 **624/624 거부** (`full-partial-mutations.json`).
- 최종 Python 소스/테스트 **13개 SHA-256 변경 0**. 기존 보호 pytest 폴더·recording JSON·전체 `.codex-scratch/`의 **14372개 항목 목록 변경 0**, 읽을 수 있는 **14334개 내용 SHA-256 변경 0**. Windows에서 내용 해시를 읽을 수 없는 **38개 항목은 경로·크기 보존만 확인**했다 (`protected-before.json`, `protected-current.json`, `protected-final-verification.json`). 보호 경로 수정·삭제·staging 없음.
- 전용 MySQL **8.4.7 / port 13341 / `/tmp/rt05b-p2-20261011/data/`**를 SQL로 확인하고, 잔여 테스트 schema/계정 **0/0**을 확인한 뒤 SHUTDOWN했다. mysqld session exit **0** 및 port closed를 확인했다 (`mysql-cleanup.json`). localhost 전용 바인딩과 임의 비밀번호 계정을 사용했다.
- 이번 P2 수정 파일은 composition / worker_loop / cancel checkpoint MySQL test / gate script / gate unit inventory / 실제 gate integration inventory / Worker README / 본 Log의 **8개**다. 이전 RT-05(b) 작업까지 합친 브랜치 변경은 **15개**, staging **0개**다. 검토 diff는 보호 파일을 제외하고 미추적 신규 파일 4개를 포함한다 (`branch-review.diff`). 커밋·push·PR 생성 없음. RT-05는 **IN_PROGRESS / `Refs #292`**, 독립 재리뷰 대기다.
- boundary·Contract fixture·workflow 정적 검사·`git diff --check` PASS. Plan·Contract·Decision·Baseline·Case surface 변경 없음. observe의 보수적 과대계상·clock 연결 오차·sink 장애 시 metric 유실·운영 p95 미측정 한계는 유지한다.

증거는 새 `C:/Users/cheol/AppData/Local/Temp/rt05b-p2-20261011/`에만 기록했다. 기존 `.codex-scratch/` 및 보호 파일에는 쓰지 않았다.

### RT-05 최종 독립 재리뷰 통과 — P2 해소 및 검증 주체 구분

사용자가 전달한 독립 재리뷰 통과와 「RT-05(b) 리뷰」의 최종 결과를 기록한다. **이전 terminal 지표 P2 해소 · 추가 병합 차단 문제 없음**으로 판정됐다. P2 이후 변경된 8개 파일을 중심으로 검토했으며, RT-05 최종 상태는 **DONE**이다.

**재리뷰 직접 실행 결과**

| 검증 | 리뷰어 직접 실행 결과 |
| --- | --- |
| bool adapter · terminal · T2 단위 회귀 | 4 passed |
| 신규 gate family · 10 parameter × 7단계 누락 검사 | 71 passed |
| 실제 MySQL 신규 지표 10개 · late success · ownership 회귀 | 13 passed · skip 0 · xfail 0 |
| 보존된 실제 보고서에서 신규 parameter 개별 누락 검사 | 110/110 거부 |
| cleanup · observer · logger 시간 제외 및 장애 격리 독립 probe | 3개 통과 |
| `git diff --check` | PASS |

- 실제 MySQL의 400ms COMMIT 지연에서 terminal 약 **442ms**, checkpoint / 독립 ACK **421ms / 421ms**를 측정했다. 실제 row lock wait + 400ms 지연에서는 terminal 약 **486ms**, checkpoint / ACK **437ms / 437ms**였다. 400ms terminal logger 지연에서는 terminal 약 **26ms**, checkpoint / ACK **16ms / 16ms**였다.
- cleanup·observer·logger 합계 600ms 지연으로 기록 함수가 약 625ms 걸려도 receipt의 ACK 종료 시각은 늘어나지 않았다. cleanup·observer·ACK clock에 DB 오류 타입을 주입해도 COMMIT은 한 번이었다. UPDATE 0행·late success·ownership 상실의 지표 미발행, unknown COMMIT 복구 성공 시 각 지표 1회, attempt마다 timestamp/sample 초기화와 기존 bool adapter 호환성을 확인했다.
- 직접 probe 증거: [independent-probe.json](C:/Users/cheol/.codex/visualizations/2026/10/11/01a12ac2-823b-7ab2-80a5-3bc5e29c406b/rt05b-p2-review/independent-probe.json).

**구현 단계 실행 결과 — 재리뷰에서는 보존 증거 대조**

- 전체 pytest **3852 passed / 비-MySQL 26 skipped**는 구현 단계의 직접 실행 결과다. **재리뷰에서 전체 pytest를 다시 실행한 결과가 아니다.** 리뷰어는 보존 JSON/JUnit을 현재 gate로 대조하고 소스/테스트 13개 해시 일치를 확인했다.
- targeted **1493 passed**, MySQL require **282 tests / 846 phases passed**, 전체 실행 MySQL **283 tests / 849 phases passed**도 구현 단계 보존 결과다. 재리뷰 직접 실행의 MySQL 13개와 구분하며 고유 test 수로 합산하지 않는다.
- 증거 대조: [preserved-evidence.json](C:/Users/cheol/.codex/visualizations/2026/10/11/01a12ac2-823b-7ab2-80a5-3bc5e29c406b/rt05b-p2-review/preserved-evidence.json). 이번 Log 갱신에서는 코드·테스트를 수정하거나 재실행하지 않고 `git diff --check`만 확인한다.

**두 지표의 최종 시간 의미**

| 지표 | 시작점 | 공통 종료점 |
| --- | --- | --- |
| `runtime.cancel.terminal_latency_ms` | DB 최초 `cancel_requested_at` | 성공적으로 확인한 durable CANCELLED transaction의 COMMIT acknowledgement |
| `runtime.cancel.checkpoint_to_terminal_ms` | 최초 cancellation checkpoint의 monotonic 시각 | 동일한 COMMIT acknowledgement |

- COMMIT 확인 직후 고정한 monotonic 종료 시각을 공유한다. terminal 지표는 DB sample과 monotonic 구간을 연결한 추정 지연이며, checkpoint 지표는 monotonic 지연이다. lock wait·재시도·COMMIT 대기는 포함하고 종료점 이후 pool cleanup·observer·logger·heartbeat join은 제외한다.
- unknown COMMIT 복구에서는 최초 COMMIT의 미확인 시각을 재사용하지 않고 **durable terminal을 확인한 복구 transaction의 성공 ACK 시각**을 사용한다. 확정된 terminal 이후 지표 계산·Runtime logger 장애는 transaction 재시도를 유발하지 않는다.

**비차단 경계 · 남은 한계 · 최종 PR**

- `observe_latency_ms`의 SELECT 전 구간 보수적 과대계상은 그대로다. terminal 지표의 **DB sample ↔ monotonic 연결에도 SQL 전송 시간·clock 해상도에 따른 오차**가 있다. 이번 재리뷰가 이를 해결했다고 주장하지 않는다. **B-X1 운영 p95는 미측정**이며 시험 지연 회귀는 운영 p95나 강제 중단 deadline의 증거가 아니다.
- **제3자 logger의 원문 비노출은 보장하지 않는다.** 리뷰어가 원문을 가진 pool-reset 예외를 주입했을 때 SQLAlchemy 자체 logger는 traceback·SQL·경로를 stderr에 출력했다. 새 지표 계산·Runtime logger 경로에서는 누수를 발견하지 못했으나, 전역/제3자 logger의 masking까지 구현된 상태는 아니다. 이는 비차단 경계로 남긴다.
- sink 장애 중 metric 유실, B-D9 단계별 timeout의 whole-attempt/join 상한 미보장, 실제 RT-06 sweep·CANCELLED T2 재전달 경계 및 RT-10 capability checkpoint의 후속 검증 한계는 유지한다. 원격 GitHub Actions 실행을 주장하지 않는다.
- RT-05 **DONE**, 최종 RT-05(b) PR 연결은 **`Closes #292`**, **PR 번호와 merge SHA는 pending**이다. 최종 PR의 CI 및 Plan §12 Implementation Notes·Log 요건을 반영한다. 이번 갱신은 RT-05 절만 수정하며 커밋·push·PR 생성은 하지 않는다.

---

## RT-06 — STALE sweep · 자동 retry · T2 재전달

Status: DONE · Issue: #293 · Audit: A

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| [#347](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/347) (`Refs #293`, RT-06(a)) | sweep · retry — 두 P2 해소 · 독립 재리뷰 통과 | `2f046954` |
| pending (`Closes #293`, RT-06(b) 최종 PR) | 병합된 RT-06(a) PR #347에 이어 terminal T2 재전달 · 실제 Case adapter · process kill 복구 완료 — 독립 재리뷰 통과, 병합 차단 문제 없음 | pending |

### 구현 결과

- 최초 RT-06(a) 구현 기준(2026-10-11): 당시 최신 `origin/develop` `184dd3b8be26a96c3b2b5ea7ef66edaf25e0dd76`의 Plan §6 RT-06 · §12 전체/§12.8, Baseline B-L3~B-L5 · B-R1~B-R3 · §2.4 · §3.2 · §9, Tech Spec §6.2 · §6.3 · §7.2 · §7.3 · §12.2, 이 Log와 Issue #293을 확인했다. 당시 브랜치 HEAD도 같은 커밋이었다. 저장소/부모에서 AGENTS.md 파일은 발견되지 않았고 사용자가 제공한 AGENTS 지침을 적용했다.
- **RT-06(a)의 구현 범위:** `retry_policy.py`는 lease 만료·STALE-only retry·상한·중단 표식·지수 backoff/cap을 pure logic으로 분리한다. 실패 횟수와 failure_kind는 STALE/retry 판정에 쓰지 않는다.
- `sweep_expired(conn, execution_id, settings)`는 caller-owned transaction에서 원본 row를 잠그고 DB 시각과 marker를 재확인한다. 조건부 RUNNING→STALE과 허용되는 attempt+1 QUEUED INSERT가 같은 commit이다. 원본/새 attempt의 ended_at/queued_at은 같은 DB sample이며 available_at에 backoff를 더한다. 새 attempt는 job/case/kind/trace만 이어받고 execution ID·lease·cancel·produced는 재사용하지 않는다.
- `sweep_once()`는 후보 scan 뒤 execution별 B-D8 transaction을 실행한다. 중복 sweep은 원본 row 잠금 재확인과 기존 UNIQUE(job_id, attempt)로 차단한다. retry ID는 callback replay 동안 고정하고, unknown COMMIT 뒤에는 같은 원본 PK를 blocking read하여 durable STALE과 자신이 만든 child를 확인한다. 이미 STALE인 row에 추가 attempt를 만들지 않는다.
- `SweepService`는 startup sweep 성공 전 claim을 막고 DB 오류는 B-Q3 대기한다. 이후 handler와 독립적인 단일 `runtime-sweep` thread로 주기 sweep을 실행한다. WorkerLoop finally에서 stop/join하며 기존 handler/heartbeat 종료 경계를 유지한다.
- `compose_worker(sweep_hooks=(...))`가 RT-07 reconciliation 등록 지점이다. immutable hook 목록은 startup/주기 sweep transaction과 connection 반환 뒤 실행하고 일반 hook 예외는 다음 hook과 다음 주기에 영향을 주지 않는다. RT-07 import·usage 구현은 없다.
- commit된 STALE/auto retry/exhausted와 detect latency event를 기록한다. detect latency의 최종 의미는 **durable STALE row의 DB `ended_at` − 같은 row의 마지막 DB `heartbeat_at`**이다(Baseline §6). lease duration과 sweep 지연을 함께 포함하고 retry 생성/상한/중단 여부와 무관하다. 기존 safe logger의 duration_ms 필드를 유지하므로 `runtime.stale.detect_latency_s`의 초 단위 집계는 duration_ms/1000이다. `runtime.queue.wait_ms`는 DB queued_at→started_at을 기록하고 INITIAL/RETRY로 attempt 묶음을 구분한다. retry backoff도 포함한다.

### Plan 대비 변경

- sweep 전체를 큰 transaction으로 묶지 않고 후보별 짧은 transaction으로 나눴다. 각 attempt의 STALE+QUEUED 원자성은 유지하며 긴 handler·다른 job의 cancel/finish가 전체 scan 잠금에 묶이지 않게 한다. 앞 후보가 commit된 뒤 뒷 후보가 실패하면 앞 결과는 유지되고 다음 pass가 나머지를 재평가한다. implementation detail이며 Contract/Decision/Baseline 변경은 없다.
- RT-06(a)에서는 terminal T2 재전달 scan·실제 kill E2E·Case 8-8 배선을 RT-06(b)로 분리했다. CANCELLED의 기존 T2 경계는 변경하지 않았다. 당시 전체 상태는 IN_PROGRESS, 연결은 `Refs #293`이었다. RT-06(b)의 구현·최종 독립 재리뷰 결과는 아래에 기록한다.
- claim receipt에 내부 queued_at을 optional/default 필드로 추가하여 기존 positional adapter를 유지했다. 공개 JobExecution/read-port schema는 바꾸지 않았다.

### 새 implementation detail

- ① 후보 scan→PK 잠금/재확인→원자적 전이를 선택했다. 별도 commit이면 retry 유실/대표 execution의 일시 FAILED 표시, 재확인 없는 INSERT면 cancel 경합/중복 retry가 생긴다.
- ② DB NOW(6)·기존 config 상한/backoff·available_at을 선택했다. host 시계는 조기 판정 위험이 있고 Worker sleep backoff는 다른 QUEUED의 실행 슬롯을 점유한다. B-L/B-R 의미·값은 변경하지 않는다.
- ③ startup gate→독립 thread→post-commit hook을 선택했다. claim 사이 sweep이면 긴 handler 동안 복구가 멈추고, transaction 내부 hook이면 후속 reconciliation의 지연/오류와 row 잠금·retry가 결합한다.
- 주기 thread는 한 pass 종료 뒤 다음 interval을 기다리며 동시 sweep을 겹치지 않는다. startup DB 오류는 B-Q3, 주기 오류는 sanitized event 뒤 다음 주기에서 다시 시도한다. stop/join에 별도의 whole-attempt hard timeout을 만들지 않는다.
- 별도 소스 리뷰가 queue wait logger를 heartbeat 이전에 호출하는 P2를 발견했다. 실제 MySQL에서 lease보다 긴 sink 지연으로 실패를 재현한 뒤 heartbeat.start 이후 try/finally 안으로 옮겼다. heartbeat가 느린 sink 중에도 갱신하고 단일 SUCCEEDED를 유지하는 회귀를 CI gate에 넣었다.
- **후속 독립 리뷰 P2-1(2026-10-12):** 원인은 `now − lease_expires_at`을 detect latency로 써 lease 구간을 제외한 것이다. STALE UPDATE 자체의 `NOW(6)`를 `ended_at`에 저장하고 이를 다시 읽어 receipt·다음 attempt queued_at에 사용한다. immutable receipt에는 계산 대신 원본 heartbeat 시각을 보존하고 측정 계산은 commit/connection 반환 뒤로 옮겼다. 측정·sink 오류는 durable STALE/retry transaction을 rollback/replay하지 않는다.
- schema/migration에서 heartbeat_at은 nullable이고 공개 JobExecution Contract에는 없는 Runtime 내부 column이다. 정상 claim/renew는 DB NOW(6)로 기록한다. NULL·STALE 기록보다 미래인 heartbeat에는 lease/start/host 시각·0 같은 fallback을 만들지 않고 해당 latency 측정만 생략한다. lease 만료만으로 STALE/retry를 처리하는 정책은 유지한다.
- **후속 독립 리뷰 P2-2(2026-10-12):** hook의 BaseException이 cleanup 후 `main()`의 `except Exception`을 통과해 SystemExit 원문 또는 traceback을 인터프리터가 stderr에 출력했다. sweep의 fatal 전파·stop/join은 유지하고 프로세스 경계에서 BaseException을 잡아 Worker stop과 안전한 실패 event, 고정 종료 코드 **1**로 처리한다. SystemExit가 요청한 0/임의 코드는 사용하지 않는다. 실패/cleanup logger·filter·handler가 BaseException을 다시 발생시켜도 원문/traceback을 전파하지 않는다. 일반 hook Exception 격리·다음 hook/주기 실행과 기존 signal graceful stop 의미는 유지한다.

### Owner 확인 포인트

- 사전 Owner 확인이 필요한 Contract·Accepted Decision·Baseline 의미 변경, 다른 Owner의 새 surface/의무, SoT 충돌은 발견하지 않았다. 기존 Runtime cancellation port만 소비하며 case schema/callback을 추가하지 않는다.
- Deferred Audit A: 후보별 commit 경계와 unknown-COMMIT receipt 확인, cancel이 먼저 잠근 row의 skip/다음 pass 재평가, sweep이 먼저 잠근 경우 cancel이 새 QUEUED까지 취소하는 경계, startup DB 장애 claim admission, post-commit hook 배선과 thread shutdown.

### Verification — 구현 단계 보존 결과

- TDD RED: pure policy 19개·thread lifecycle 6개·실제 MySQL sweep 14개·production composition 3개를 미구현 실패로 확인했다. initial/retry queue wait 2개도 누락을 재현했다. 리뷰 P2는 실제 MySQL slow logger 회귀에서 실패한 뒤 수정 후 통과했다.
- MySQL 대상은 실제 MySQL 8.4.7 disposable schema이며 mock/skip 대체는 없다. 자연 lease 만료·late finish fencing, commit/rollback, backoff claim, 상한/중단, 두 sweeper, heartbeat/finish/cancel 재확인, 실제 cancel lock wait, 실제 1213 전체 rollback 재시도, COMMIT OK 폐기 proxy 복구를 검증한다.
- 새 MySQL acceptance family/parameter는 JSON/JUnit CI gate의 필수 목록에 추가했다. family 누락과 collection/selection/setup/call/teardown/all/JUnit 누락이 거부되는 RED를 확인했다. `.github/workflows/`는 변경하지 않았다.
- 최초 RT-06(a) 전체 회귀 내부 MySQL 실행(2026-10-11): 306 tests, skip=0, xfail=0, JSON/JUnit gate PASS. 실제 보고서의 parameter 증거 누락 1,267건 모두 거부(새 sweep parameter 증거 누락 84건 포함). 증거는 `full-verified/test_actual_report_rejects_eac0/{mysql.json,mysql.xml,parameter-mutations.json}`이다.
- 최초 RT-06(a) 검증(2026-10-11): 전체 pytest **4,001 passed, 26 skipped** (1,206.91s). 비-MySQL skip은 선택 의존성 `typer` 미설치 4건과 로컬 미디어/opt-in 조건 22건이다. 실제 **MySQL 307 tests, skip=0, xfail=0**, JSON/JUnit gate PASS(필수 scenario/parameter와 setup/call/teardown 증거 충족). mock/skip으로 대체하지 않았다.
- 실행: `DAESINGO_REQUIRE_MYSQL=1`, 실제 disposable MySQL URL 환경에서 `.venv/Scripts/python.exe -B -m pytest -vv --tb=short -p no:cacheprovider --basetemp=.codex-scratch/rt06a-20261011/full-verified --mysql-report=.codex-scratch/rt06a-20261011/full-verified.json --junitxml=.codex-scratch/rt06a-20261011/full-verified.xml`. 증거는 같은 디렉터리의 `full-verified.txt/json/xml`이다. JSON/JUnit은 `scripts/check_mysql_test_report.py`로 별도 재검증했다.
- `scripts/check_boundaries.py`: PASS, 경계·계약 정합성 위반 0건. `git diff --check`: PASS. 별도 read-only 소스 재리뷰는 P2 수정 후 추가 actionable finding 없음이며, reviewer가 별도 suite를 재실행한 결과는 아니다. 원격 develop SHA도 최종 점검 때 동일했다. 원격 CI 실행은 하지 않았다.
- 후속 두 P2 RED: 실제 MySQL에서 lease 60/7초 × retry/exhausted/cancel 6건·UPDATE 지연·NULL/미래 heartbeat 3건이 잘못된 측정으로 실패했다. 계산의 commit 후 격리 누락도 별도 RED로 확인했다. startup/periodic × SystemExit/KeyboardInterrupt/합성 BaseException 6건은 실제 child process의 stderr 원문/traceback 비노출 assertion에서 실패했다. SystemExit(0/42)의 안전한 종료 코드 테스트도 RED였다. 새 acceptance family 5개 누락 및 parameter 전체 증거 누락이 gate를 통과하는 RED를 확인했다.
- 후속 GREEN/최종 전체 회귀 증거는 `.codex-scratch/rt06a-p2-20261012/`에 별도로 보존한다. 최신 origin/develop `9c2df2f0e962df6fecac2fff4e45e8b5482a4fd2`로 fetch 후 위 네 Runtime 문서가 기존 기준 SHA와 동일함을 확인했다. 현재 HEAD/브랜치는 변경하지 않았다.
- 후속 중간 전체 실행(`full-verified`, TLS-disabled URL)은 기존 `test_explicit_config_url_preserves_percent_encoded_password`의 PyMySQL 인증 오류(`NoneType.is_auth_switch_request`)와 이를 포함한 `test_actual_report_rejects_each_missing_migration_check` 실패로 중단했다. 기존 TLS 사용 URL로 돌려 해당 실제 MySQL 테스트 **1 passed**를 확인하고 전체를 `full-final`로 재실행했다. 제품 source/의존성 수정·skip 대체 없이 테스트 환경 옵션만 복원했으며 중간 결과를 최종 증거로 사용하지 않는다.
- 후속 targeted GREEN: **1,787 passed**. 최종 전체 실행 내부의 실제 MySQL 재실행은 **344 tests, skip=0, xfail=0**, JSON/JUnit gate PASS였다. 실제 parameter 증거 누락 **1,533건 모두 거부**, 새 P2 parameter 증거 누락 **266건** 포함이다. 증거는 `full-final/test_actual_report_rejects_eac0/{mysql.json,mysql.xml,parameter-mutations.json}`이다.
- 재리뷰의 P3(테스트가 Runtime 로그를 event 이름으로만 요약)는 child의 실제 Runtime 로그 본문 비노출 검사로 보완했다. 후속 read-only 재리뷰는 P3 해결·추가 actionable finding 없음이며, reviewer는 별도 suite를 실행하지 않았다.
- 후속 최종 전체 회귀(2026-10-12): **4,312 passed, 26 skipped** (1,565.22s). skip은 비-MySQL 선택 의존성 `typer` 4건·로컬 미디어/opt-in 22건이다. 실제 **MySQL 345 tests, skip=0, xfail=0**, JSON/JUnit gate PASS. startup/periodic × SystemExit/KeyboardInterrupt/합성 BaseException × healthy/logger/filter/handler 24건의 실제 Runtime 로그 본문 검사도 포함한다. boundary 위반 0건·`git diff --check` PASS. 원격 CI는 실행하지 않았다.
- 후속 최종 실행: `DAESINGO_REQUIRE_MYSQL=1`, 실제 disposable MySQL URL, `PYTHONIOENCODING=utf-8` 환경에서 `.venv/Scripts/python.exe -B -m pytest -vv --tb=short -p no:cacheprovider --basetemp=.codex-scratch/rt06a-p2-20261012/full-final --mysql-report=.codex-scratch/rt06a-p2-20261012/full-final.json --junitxml=.codex-scratch/rt06a-p2-20261012/full-final.xml`. `.venv/Scripts/python.exe -B scripts/check_mysql_test_report.py .codex-scratch/rt06a-p2-20261012/full-final.json .codex-scratch/rt06a-p2-20261012/full-final.xml`로 별도 재검증했다. 같은 디렉터리의 `implementation-notes.md`·`review-manifest.json`에 재현 방법·변경 파일/증거 SHA-256을 보존한다.

### RT-06(a) 최종 독립 재리뷰 통과 — 검증 주체 구분

- **사용자 전달 RT-06(a) 최종 판정:** detect latency 의미와 fatal hook 원문 비노출의 두 P2가 해소됐으며 RT-06(a) 독립 재리뷰가 통과했다. 당시 전체 상태는 **IN_PROGRESS**, 연결은 **`Refs #293` (RT-06(a))**, PR 번호·merge SHA는 pending이었다. 이후 **PR #347 / `2f046954`**로 병합됐으며, RT-06(b) 최종 PR이 **`Closes #293`**로 전체 완료를 연결한다.
- **확인된 최종 경계:** detect latency는 durable STALE row의 `ended_at − heartbeat_at`이다. startup/periodic fatal hook은 일반 Exception 격리 경로로 삼키지 않고 stop/join·connection cleanup 후 고정 코드 **1**로 종료한다. 프로세스 경계는 예외 원문·traceback·secret·경로를 stderr나 Runtime 로그에 노출하지 않으며 실패/cleanup logger·filter·handler의 BaseException 재실패도 전파하지 않는다.
- **재리뷰 직접 실행 결과(사용자 전달):** COMMIT 불명 소진, observer 장애, fatal과 cleanup BaseException 동시 발생을 독립 probe로 확인했다. 이 세 probe는 저장소 회귀 테스트에 아직 포함되지 않았다.
- **구현 단계 보존 결과:** 위의 targeted **1,787 passed**, 전체 **4,312 passed / 비-MySQL 26 skipped**, 실제 **MySQL 345 tests / skip=0 / xfail=0**, 내부 MySQL 반복·gate parameter 누락 결과는 구현 단계의 보존 증거다. 이 수치를 독립 재리뷰의 직접 재실행 결과로 기록하지 않는다. 앞선 read-only 재리뷰 기록은 당시 검토 이력으로 유지한다.

### 남은 위험

- RT-06(a) acceptance는 Runtime의 sweep/retry를 증명했다. 당시 후속 범위였던 RT-06(b) T2 재전달·실제 process kill E2E는 아래 구현·독립 재리뷰에서 PASS로 확인됐다. 실제 Case wall timeout/context 적용 여부는 기존 case 소유 판단으로 남긴다(Baseline §3.2).
- **비차단 회귀 보강 후보:** 독립 probe로 확인한 COMMIT 불명 소진·observer 장애·fatal과 cleanup BaseException 동시 발생을 저장소 회귀 테스트로 편입하는 작업은 남아 있다. 독립 probe 확인과 저장소 회귀 커버리지를 구분한다.
- DB stall/B-D8 재시도·느린 hook이 sweep pass를 늦출 수 있고 whole-pass/hook/join의 전체 wall-clock 시간 상한을 보장하지 않는다. fatal 비노출 처리는 강제 kill이나 시간 상한을 추가하지 않는다. 운영 detect latency/false STALE 분포와 Baseline revisit 근거는 실측하지 않았다.
- post-commit 지표는 best effort이며 sink 장애/process 종료/unknown COMMIT 복구가 소진되면 event 유실이 가능하다. durable STALE/retry 원자성은 지표에 의존하지 않는다. 제3자 logger의 전역 masking은 기존 한계다.
- RT-06(a)는 PR #347로 병합됐다. RT-06(b) 최종 PR의 번호·merge SHA는 pending이며 이번 Log 갱신에서 커밋·push·PR 생성은 하지 않는다. 기존 미추적 파일도 수정/staging하지 않는다.

---

### RT-06(b) — terminal T2 redelivery · 실제 Case adapter · process kill (2026-10-12)

**Status: DONE · 최종 PR 연결: Closes #293 · PR 번호 / merge SHA pending.** 사용자 전달 RT-06(b) 독립 재리뷰는 통과했으며 병합 차단 문제 없음으로 판정됐다. 병합된 RT-06(a) PR #347의 sweep/retry에 이어 RT-06(b) 최종 PR이 T2 재전달·실제 Case adapter·process kill 복구를 완성한다. 실제 Issue close는 최종 PR 병합 연결이며, 이번에는 Log만 갱신하고 커밋·푸시·PR 생성은 하지 않는다.

**구현 결과**

- 착수 기준 HEAD/develop `fa5a0fcb`. 사용자 제공 AGENTS.md, Plan §6 RT-06/§12 전체, Tech Spec §6.2/6.3/7.2/7.3/12.2, Baseline B-L3–L5/B-R1–R3/§2.4/3.2/9, Log RT-04/05/06, Issue #293와 병합 PR #342·#343 및 Case 결정/공개 함수·T2 helper·transaction/composition을 확인했다. 저장소 내 AGENTS.md 파일은 발견되지 않았다. #347 merge는 Git history의 `2f046954`로 확인했다.
- `common/jobs/redelivery.py`는 SUCCEEDED/FAILED와 `case_applied_at IS NULL`만 잠금 없이 scan한다. connection 반환 후 후보마다 B-D8 transaction을 사용하고 callback replay마다 비잠금 receipt 조회를 다시 한다. CANCELLED/STALE/이미 receipt가 있는 execution은 Case로 넘기지 않는다.
- 기존 `reflect_terminal`과 Case `reflect_execution`을 그대로 재사용한다. Case lock/실행 ID dedup → Runtime terminal facts/receipt lock → 후속 enqueue + receipt 순서다. Case·후속 JobRecord의 Runtime enqueue·receipt는 같은 commit이며 COMMIT 응답 유실은 durable receipt와 Case 처리 기록으로 복구한다. 별도 delivery lease/schema/새 retry 정책은 없다.
- `worker/case_reflector.CaseReflector`는 reader/timeline과 선택적 store factory/budget을 주입받고 Runtime 모델을 Case 모델로 변환한다. 기본 store는 같은 Connection의 MySQLCaseRepository와 `read_executions`다. 다른 Connection의 store는 거부한다. Case 코드/공개 surface는 수정하지 않는다.
- `SweepService`의 startup pass와 각 periodic pass에 독립 redelivery callback을 연결했다. startup scan DB 실패는 B-Q3 admission 재시도로 첫 claim을 막는다. 후보 reflector/DB 오류는 rollback·기존 retry 뒤 격리하여 다음 후보와 다음 주기를 진행한다. scan 실패는 주기 경계로 올라가며 다음 주기에 다시 수행한다. hook은 여전히 transaction/connection 반환 뒤 호출하며 RT-07 import/reconciliation은 없다.
- commit/recovery 이후 best-effort `runtime.reflect.redelivery_count`를 기록한다. scan/replay 중 이미 완료된 receipt에는 재반영하지 않는다. shared post-commit observer는 기존 `attempt >= 2 AND NOT_APPLIED(STOPPED_WAITING)`만 `runtime.retry.after_case_stopped_count`로 집계한다. CANCELLED/SUPERSEDED/ALREADY_APPLIED/rollback/예외는 제외한다. event는 durable exactly-once ledger가 아니다.
- 실제 spawned Worker process에서 IPC로 T1 commit 뒤 T2 진입 전 또는 handler RUNNING 지점에 정지한다. 부모의 별도 MySQL 연결에서 durable 상태를 확인하고 OS kill/join·nonzero exit를 관측한다. gap 복구는 startup receipt 완료를 첫 claim 전에 확인한다. 실행 중 kill은 새 Worker의 실제 lease 만료→STALE→attempt 2→backoff 후 claim→성공→Case 처리 ID/receipt를 확인한다. 후보 중복/Case 후보 1개와 재전달 no-op도 확인한다. child의 engine/heartbeat/sweep를 별도 process가 소유하며 finally에서 child/pipe를 정리한 후 fixture schema를 drop한다.

**Plan 대비 변경 · 새 implementation detail**

- Plan 예상 `sweep.py`에 T2 persistence를 더하는 대신 `redelivery.py`와 Worker-owned adapter로 분리했다. 기존 T2/Case 공개 함수를 소비하는 implementation detail이며 다른 Owner의 새 surface는 필요하지 않았다. 기본 entrypoint의 실제 module reader/timeline/handler 조립은 RT-10에 남긴다.
- [구현 계획/선택 비교](../superpowers/plans/2026-10-12-runtime-t2-redelivery-kill-recovery.md)에 scan 분할, 동시 sweeper, COMMIT 불명, adapter 위치/DI, kill 동기화, 미지원 kind의 대안 2–3개와 장애를 기록했다. 기존 Case lock/receipt를 선택해 cross-process 중복을 해결하며 Runtime 선잠금이나 process-local mutex를 쓰지 않는다.
- MySQL gate에 독립 `redelivery` 9 families / 32 parameters를 추가하고 nested actual-report suite에도 신규 테스트를 포함한다. collection/selection/setup/call/teardown/all/JUnit의 개별 누락은 기존 fail-closed 검사로 확인한다. workflow require/JSON-JUnit gate 경로는 유지한다.

**Contract / Decision / Baseline 영향:** 모두 없음. test 전용 짧은 heartbeat/lease/sweep/backoff는 P-4이며 production 값을 바꾸지 않는다.

**Owner 확인 포인트**

- PR #343의 「미등록 kind는 T2까지 오지 않는다」는 전제를 사용하지 않는다. 실제 KindRegistry는 FAILED/RUNTIME_UNREGISTERED_KIND로 T1 확정 뒤 T2에 전달한다. Case 지원 kind는 현재 HINT_EXTRACT/COARSE_SEARCH다. PLATE_READ의 실제 durable JobRecord로 missing-applier ValueError를 확인하고 receipt를 남기지 않는다. UNKNOWN은 Case vocabulary 밖의 Runtime kind mismatch를 별도로 확인한다. Worker registry와 Case reflector의 호환성/fail-fast 책임은 **RT-10 후속 비차단 경계**이며 새 Case applier나 무음 APPLIED를 만들지 않았다.
- Deferred Audit A: Case→Runtime 잠금, NOT_APPLIED receipt와 unknown COMMIT, 후보 오류 격리, startup 순서, actual kill 증거를 확인한다. ProducedReader의 실제 module persistence/새 applier는 Case 8-6 2단계·RT-10 선행이다.

**Verification — 구현 단계 보존 증거**

- RED: startup/periodic unit 2 failed, 실제 MySQL 신규 32 failed(미구현), gate family 누락 9 failed. 최초 GREEN 시도는 24 passed/8 failed였고 공용 logger.log test 오염을 monkeypatch 복원으로 수정했다.
- 수정 후 unit/gate 2,513 passed. targeted 실제 MySQL/Case/기존 T2/startup 76 passed. 실제 connection kill→B-D8 3회 소진→다음 후보·다음 주기 1 passed. 첫 targeted 실패는 기존 concurrent T2 관측의 performance_schema SELECT 권한 부족이며 최소 읽기 권한 후 재검증했다.
- read-only 구현 리뷰의 P2: 기존 JobRecord.kind를 메모리에서 바꾼 fixture는 MySQL append-only record를 바꾸지 않아 missing-applier 대신 mismatch를 검증했다. durable kind assertion **2 failed RED** 후 실제 Case `issue_plate_read` 발주·정확한 ValueError 원인 assertion으로 수정했다. production 수정은 없었다. 최종 독립 재리뷰와 구분한다.
- 수정 환경의 nested 실제 MySQL require는 **482 passed / skip 0 / xfail 0**, MySQL **8.4.7**이며 별도 JSON/JUnit CLI gate PASS다. 기존·신규 개별 parameter의 7개 증거 계층 누락 **2,317건**을 모두 거부했다. 그중 redelivery 32 parameters의 **224건**이 포함된다.
- 최종 전체 pytest: **5,363 passed / 26 skipped / exit 0**, 1,684.30초. MySQL 선택 **487 tests / skip 0 / xfail 0**, JSON/JUnit CLI gate PASS. 이 통과 baseline에서 신규 32 parameters × 7 계층 누락 **224건**, 9 family 누락 **9건**을 별도로 거부했다. 전체 skip은 search collection의 기존 `typer` 미설치 4개와 로컬 미디어/opt-in이 없는 Case 2·eval 5·recording 15개다. MySQL skip으로 합산하거나 성공 보고서를 조립하지 않았다.
- 최종 boundary checker PASS(위반 0), Contract fixtures PASS(문서 구조 62 / JSON 26 / 의미 104 검사), 전체 5 workflow actionlint+ShellCheck PASS. 실제 host 파일 기준 코드 11개·기존 미추적 보호 파일 1,069개의 SHA-256 유지, 새 Python source 구문 검사와 `git diff --check` PASS, staging 없음. 원격 CI는 실행하지 않았다.
- 첫 전체 require는 기존 `test_sweep_worker_mysql.py` migration fixture의 TLS authentication read에서 장시간 정지했다. read-only py-spy stack 두 번으로 같은 위치를 확인해 `require-hang-stack.txt`를 보존하고 소유 pytest PID만 종료했다. migration API의 timeout 생략은 기존 의도이며 production/migration helper/TLS 설정은 바꾸지 않았다. 정지한 테스트의 disposable schema 1개를 정리하고 test URL에 `connect_timeout=2&read_timeout=10&write_timeout=10`을 명시했다. transport stall의 원인은 미확정이다.
- 재실행 `require-final`은 **485 passed / 1 failed / 비-MySQL collection skip 4**, 656.28초였다. 유일한 실패는 기존 Case `test_waiting_writer_sees_first_writers_commit_under_read_committed`의 `INNODB_TRX` 조회 권한 **1227 / PROCESS** 부족이다. 별도 실행으로 재현한 뒤 전용 서버 test 계정에 PROCESS 관측 권한을 추가해 해당 test **1 passed**를 확인했다. 실패 보고서는 JSON/JUnit gate가 거부했다. 이 보고서를 전체 require PASS 증거로 사용하거나 새 통과 결과와 합쳐 보고서를 만들지 않는다. 수정 환경의 전체 pytest/require 결과는 별도 `full` 보고서로 남긴다.
- 전체 실행 종료 후 fixture schema/account 잔여 **0**, 활성 test connection **0**을 확인했다. 전용 datadir/loopback/port/version을 검증한 뒤 base schema와 test 계정을 제거해 잔여 test schema/account **0**, SQL SHUTDOWN / 서버 session exit **0**을 확인했다. 소유 MySQL PID/socket/pidfile 소멸·port 닫힘·Worker child process **0**을 확인했다. DB data/log는 검증 증거로 남겼다.
- 구현 단계의 읽기 전용 source 재리뷰에서는 P2 fixture 수정 후 새 actionable finding 없음. 당시 reviewer는 테스트를 재실행하지 않았으며 위 실행 검증은 구현자 증거다. 당시 보류했던 최종 독립 재리뷰 판정은 아래 사용자 전달 결과로 구분해 기록한다.
- 검증 산출물은 `.codex-scratch/rt06b-20261012/`에만 보존하며 commit에서 제외한다. 최초 sandbox local socket 10013은 escalation 뒤 해결했다. 임시 서버의 초기 0.0.0.0/% 광범위 권한 요청은 auto-review가 거부했고 loopback/localhost와 test schema 범위 권한으로 제한했다.

**RT-06(b) 최종 독립 재리뷰 통과 — 검증 주체 구분**

- **사용자 전달 최종 판정:** RT-06(b) 독립 재리뷰 통과, 병합 차단 문제 없음. RT-06(a) PR #347과 RT-06(b)를 합친 **RT-06 상태는 DONE**이며, RT-06(b) 최종 PR 연결은 **`Closes #293`**, **PR 번호·merge SHA는 pending**이다.
- **독립 재리뷰 경계 판정(사용자 전달):** redelivery 대상(SUCCEEDED/FAILED·receipt null, CANCELLED/STALE/기존 receipt 제외), Case→Runtime lock 순서, 후보별 짧은 transaction, 동시 sweeper의 execution_id dedup/receipt, Case·후속 enqueue·Runtime receipt의 원자성 **PASS**. COMMIT 결과 불명 복구와 **exactly-once durable effect PASS**. 실제 process-kill **gap/running E2E 모두 PASS**, startup redelivery 완료→첫 claim 순서 및 **Case adapter PASS**. 미지원 kind의 registry↔reflector 호환성/fail-fast는 **RT-10 후속 비차단 경계**다.
- **독립 리뷰 직접 실행 결과(사용자 전달):** 관련 unit/targeted **2,746 passed**; 실제 MySQL **482 passed / 1,446 phases / skip 0 / xfail 0**; 신규 RT-06(b) parameter **32개 모두 통과**, process-kill **gap/running 모두 통과**; JSON/JUnit gate **PASS**; 신규 parameter 누락 **224/224**, family 누락 **9/9**, metadata 일부 누락 **96/96** 거부; 추가 MySQL·kill probe **6개 통과**; boundary·Contract fixture·`git diff --check` **PASS**. 이 수치는 사용자에게서 전달받은 독립 리뷰의 직접 실행 결과이며, 이번 Log 갱신에서 테스트를 재실행하지 않았다.
- **구현 단계와 구분:** 전체 pytest **5,363 passed / 비-MySQL 26 skipped**, 전체/nested MySQL **487/482**, 전체 누락 검사 **2,317건 거부**는 위 구현 단계의 보존 증거다. 독립 리뷰 직접 실행 결과와 합치거나 독립 리뷰가 전체 pytest를 재실행한 것으로 기록하지 않는다.

**비차단 개선 후보**

- 저장소 process-kill 회귀 테스트에 **HINT_EXTRACT → COARSE_SEARCH 후속 enqueue 경로**를 편입한다.
- **ACK 유실 뒤 transaction retry 소진 경계**를 정식 저장소 회귀 테스트로 편입한다. 독립 probe PASS와 저장소 회귀 커버리지를 구분한다.
- 로컬 전체 실행은 약 **28분**이며 원격 CI의 기존 **20분** 시간 예산 확인이 필요하다. 원격 실행 시간이나 CI 통과를 단정하지 않는다.

**남은 위험**

- 미지원 kind는 receipt 없이 매 pass에 반복 재전달될 수 있다. 오류를 숨기거나 APPLIED 처리하지 않으며 **RT-10 registry↔reflector 호환성/fail-fast 검증**이 필요하다. 이 후속 경계는 최종 독립 재리뷰의 비차단 항목이다.
- 실제 **produced reader/timeline durability**는 후속 범위이며 이번 fixture 결과로 증명하지 않는다.
- 후보 수 제한이나 whole-pass deadline은 도입하지 않았다. DB stall/B-D8·느린 Case reader/hook·join은 sweep/startup을 지연할 수 있으며 운영 분포/production tuning은 측정하지 않았다.
- 전체 pass/join의 **wall-clock 상한은 없다**. 기존 retry/timeout 경계를 전체 시간 상한으로 확대 해석하지 않는다.
- `runtime.reflect.redelivery_count`는 **전달 시도 횟수**를 관측하는 best-effort event이며 **durable effect exactly-once 지표가 아니다**. post-commit 지표는 sink 장애·process kill·unknown COMMIT에서 유실 가능하다. exactly-once 보장은 durable Case/후속 enqueue/Runtime receipt 효과이며 event 전달 횟수에 확대하지 않는다.
- 초기 Windows/WSL **TLS 정지**와 사용자 전달 독립 리뷰의 **서버 shutdown 후 close에서 발생한 2013**은 해결된 것으로 단정하지 않는다. 이후 실제 검증 PASS는 이 transport 경계의 원인 규명이나 해소를 뜻하지 않는다. 이번에 workflow timeout이나 migration helper 정책을 바꾸지 않았다.
- 기존 미추적 4개 항목은 수정·삭제·staging하지 않았다. **RT-06 DONE / 최종 PR Closes #293 / PR 번호·merge SHA pending**을 유지하며, 이번에는 RT-06 Log만 갱신한다. 코드·테스트 수정, 테스트 실행, 커밋·푸시는 하지 않는다.

---

## RT-07 — Usage ledger: in-flight · Final UsageRecord · reconciliation

Status: DONE · Issue: #294 · Audit: B

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| [#349](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/349) | `Refs #294 (RT-07(a))` — schema · DECIMAL · caller transaction Final append | `fa5a0fcbd5f88e70e7a4c9ba0a457b42a65a27a1` |
| [#353](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/353) | `Refs #294 (RT-07(b))` — UsageSink · Worker injection · explicit finalize | `95dfff8b3ba11f95b76a168dd18ccc1573c02b39` |
| [#360](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/360) | RT-07(c) — Owner 확인 후 produced 기반 복구·명시적 DIRECT_NO_RUN·P-7·usage_refs 구현. 최종 연결 예정: `Closes #294` | `505e6ad2c95617569faad1b12a45fa48d3e41919` |

### 구현 결과

- 기존 Runtime head `runtime_0002` 뒤에 frozen `0003_usage.py`(`runtime_0003`)를 추가한다. 기존 revision은 변경하지 않는다. `usage_inflight`는 Runtime 내부 호출 identity·context·관측값·run 관계·STARTED/OBSERVED/FINALIZED 상태·관측/확정 시각을 typed column으로 갖는다. Final `usage_record`는 Contract §4~§8의 필드를 typed column으로 보존하고 내부 outcome/state/failure column을 내보내지 않는다.
- 양 table의 `usage_id` 단독 ascii_bin PK로 호출 identity 재사용과 같은 identity의 Final 중복을 차단한다. nullable `execution_ref`에 index를 두며 `case_id`·run·execution·in-flight/Final 사이의 FK는 없다. Final은 tracker lifecycle과 독립된 snapshot이다. in-flight에는 pending run 관계를 허용하며 Final에는 Contract의 두 null 사유 또는 실제 run 참조만 허용한다.
- nullable BIGINT token 세 값의 전체 null/전체 non-null CHECK와 total=input+output CHECK, KRW CHECK, run-kind/reason 관계 CHECK를 양 table에 둔다. SQL UNKNOWN으로 부분 null이 통과하지 않도록 null 여부를 명시한다.
- MySQL ascii_bin의 PAD SPACE 비교로 enum에 공백 접미사가 허용되지 않도록 run_kind/run_ref_reason/state/outcome CHECK는 `CAST(... AS BINARY)`로 비교한다. frozen migration과 live metadata에 같은 제약을 둔다.
- `common/usage/amount.py`와 live `ExactAmount` Core binder는 Decimal/문자열/None만 받는다. float·int·bool·비유한 값·초과 자릿수는 DB 변환 전에 거부한다. Decimal context precision에 의존하는 quantize/normalize를 쓰지 않으며 `amount=null`과 0을 구분한다. 읽기 금액은 문자열 또는 null이다.
- `append_final(conn, record) -> bool`은 열린 caller transaction에서 전체 Contract 입력을 검증한 뒤 INSERT한다. 새 row=True, 동일 identity/typed snapshot replay=False, 다른 snapshot=`UsageIdentityConflict`다. 1062만 locked read/full comparison으로 처리하고 다른 SQL 오류는 전파한다. commit/rollback/retry·ID 발급·provider 호출·in-flight 변경은 하지 않는다. 결과는 caller commit 전까지 잠정적이다.
- `read_final(conn, usage_id)`는 Final Contract 필드만 projection하며 UTC timestamp·decimal string을 반환한다. JobExecution `usage_refs` read port는 이번 범위에서 연결하지 않는다.

### Plan 대비 변경

- Plan의 예상 migration `0002_usage.py` 대신 이미 존재하는 claim receipt revision 다음의 `0003_usage.py`를 사용한다. 순번/파일 배치만 달라지는 implementation detail이다.
- RT-07(a)에 한정했다. UsageSink begin/finish·Worker injection·Run finalize 배선은 (b), reconciliation·늦은 관측(P-7)·sweep hook은 (c), Search 배선은 SRCH-1에 남긴다. pricing/FX·retention/purge·budget guard·기존 SearchLedger는 변경하지 않는다.
- 새 테스트 파일은 기존 jobs 테스트와 Python module 이름이 충돌하지 않도록 `test_usage_repository_mysql.py`로 둔다. 기존 migration acceptance의 head/table inventory와 future-revision parent만 새 head에 맞춘다. `.github/workflows/`·Case 소유 테스트/fixture는 변경하지 않는다.

### 새 implementation detail

- **DECIMAL(65,30) 근거(P-10):** Contract 예시는 `184.20`과 `0`이고 기존 `search/usage.py:ProviderUsage.cost_with_rates`는 Decimal(str(rate)) × 정수 token / 1,000,000이며 quantization 없이 Decimal을 반환한다. Accepted #244 U-2는 KRW 정규화 책임과 unknown=null을 정했으나 미래 KRW 출력의 숫자 상한/scale을 고정하지 않았다. (20,6)은 작은 소수, (38,18)은 더 긴 계산 결과를 수용하지 못한다. MySQL 지원 최대 65/30을 사용해 별도 가격 반올림 정책을 만들지 않고 35자리 정수와 30자리 소수를 허용한다. 모든 미래 값이 들어간다는 보장은 하지 않는다. 더 긴 fractional suffix(0 포함)도 거부한다. [MySQL DECIMAL](https://dev.mysql.com/doc/refman/8.4/en/precision-math-decimal-characteristics.html).
- **Identity 대안:** composite `(execution_ref, usage_id)` UNIQUE는 서로 다른 execution에 같은 usage_id를 재사용할 수 있고 nullable execution에도 부적합하다. surrogate PK만으로는 Final 중복을 차단하지 못한다. usage_id 단독 PK를 선택하며 별도 중복 UNIQUE는 추가하지 않는다.
- **참조 대안:** Final→in-flight FK는 ledger를 tracking lifecycle에 종속시키고 cascade는 원장 삭제 위험이 있다. 동일 PK의 논리 참조 + 독립 snapshot을 선택한다. 향후 tracker 정리는 삭제 대신 finalize 표시(P-7)이며 이번 primitive는 이를 구현하지 않는다. 내부 context 정합 확인은 후속 tracker/finalize 책임이다.
- **Idempotency/COMMIT 불명:** 새 ID 재발급은 중복 청구, unconditional upsert/ignore는 원장 덮어쓰기/충돌 은폐 위험이다. caller가 identity와 전체 snapshot을 유지하여 replay한다. INSERT는 경쟁 transaction의 commit/rollback을 기다리고 1062 뒤 locked read가 동일 snapshot을 확인한다. 처음 writer가 rollback하면 새 INSERT가 성공한다. 기존 Worker DB callback retry와 조합할 수 있으나 caller transaction의 다른 효과도 각각 replay-safe여야 한다. 단일 Final receipt를 전체 다른 transaction 효과의 commit 증거로 확대하지 않는다.
- 설계 비교·TDD/검증 계획은 [RT-07(a) 구현 계획](../superpowers/plans/2026-10-12-runtime-usage-ledger-schema.md)에 보존한다. 새 Decision·Contract·Baseline 값을 정하지 않는다.

### Contract / Decision / Baseline 영향

- 모두 변경 없음. 다른 Owner의 새 surface/의무, SoT 모순이나 외부 의미가 달라지는 ambiguity는 발견하지 않았다. supplied AGENTS.md를 적용하며 저장소 내 AGENTS.md 파일은 검색에서 확인되지 않았다.

### Owner 확인 포인트

- Deferred Audit B: amount의 명시적 물리 범위, unknown=null/0 구분, pending in-flight/Final run 연결 경계, fixed identity의 snapshot conflict와 caller transaction/COMMIT 불명 경계를 확인한다. §12.3에 따른 사전 Owner 확인 사항은 없다.

### Verification

- **RT-07(a) 독립 재리뷰 최종 판정 — PASS(사용자 전달 결과):** 병합 차단 문제 없음. schema·DECIMAL·caller transaction·idempotency의 최종 판정이 모두 통과했다. 아래 구현 단계의 보존 증거와 구분한다.
- **독립 MySQL 재검증:** **445 passed · skip 0 · xfail 0**, JSON/JUnit gate **PASS**. parameter 누락 **2,093/2,093 거부**, usage parameter 증거 누락 **560/560 거부**다. 독립 재리뷰의 전체 pytest 실행 결과로 아래 **5,022 passed / 26 skipped**를 재인용하지 않는다.
- **구현 단계의 보존 증거:** 아래 TDD·read-only 수정 리뷰·nested suite·전체 회귀·재검증 기록은 구현 당시 실행의 증거다.
- TDD RED: 금액 경계 33개·실제 MySQL schema/append 77개·gate 새 usage family 11개와 필수 parameter 동시 collection/selection/phases/JUnit 누락 74개를 미구현 실패로 확인했다. 극단 exponent의 InvalidOperation 분류도 1개 RED 후 수정했다.
- 기존 Runtime migration/queue real MySQL baseline 33 passed. amount 34 passed, gate unit 2,230 passed. CHECK 위반의 실제 MySQL 3819는 PyMySQL OperationalError로 전달되어 테스트에서 코드까지 확인한다. 테스트 파일명 충돌은 collection error 확인 후 신규 파일명 변경으로 해결했다. 첫 baseline unit의 임시 디렉터리 parent 누락과 boundary stdout cp949 인코딩은 실행 환경을 바로잡았으며 제품 source 변경으로 숨기지 않았다.
- 구현 단계의 독립 read-only 리뷰가 발견한 enum 공백 접미사 P2를 실제 MySQL INSERT **6 failed** RED로 재현하고 수정했다. six suffix + frozen/live DDL **7 passed** GREEN, 새 필수 parameter 누락 **6 failed** gate RED를 확인했다. 당시 수정 재리뷰의 독립 SELECT probe와 기존 GREEN JSON/JUnit 확인에서 P2 해결 및 추가 actionable finding 없음으로 보고됐다. 해당 read-only reviewer는 새 pytest를 실행하지 않았으며, 위 최종 독립 MySQL 재검증과 별개다.
- 중간 전체 실행 `full-verified`는 리뷰 수정 전 증거이므로 중단했다. 최종 source로 `full-final`을 다시 실행하며 필수 usage inventory는 11 families / 80 parameters다.
- 구현 단계 최종 실행의 nested 실제 MySQL suite **445 tests · skip 0 · xfail 0**, JSON/JUnit gate PASS를 별도 CLI로 확인했다. 실제 보고서 parameter 증거 누락 **2,093/2,093 거부**, 신규 usage **80 parameters × 7 layers = 560/560 거부**다. `full-final/test_actual_report_rejects_eac0/{mysql.json,mysql.xml,parameter-mutations.json}`에 보존한다.
- `full-final` 전체 실행은 **5,022 passed / 1 failed / 26 skipped**, 1,515.89초였다. 기존 API kill 테스트의 blocker `lock.rollback()`에서 MySQL 2013 / Windows 10053 연결 중단이 발생했다. 같은 test는 nested suite와 별도 진단 **1 passed**였으며 해당 기존 test/transaction source는 변경하지 않았다. 실패 보고서를 통과 증거로 사용하지 않는다.
- 구현 단계의 코드 변경 없는 `full-recheck`는 **5,022 passed / 26 skipped**, **928.39초 · exit 0**이다. 이 전체 수치는 구현 단계의 보존 증거이며 이번 독립 재검증에서 전체 suite를 다시 실행했다는 의미가 아니다. 이미 통과한 실제 보고서 mutation test 하나(`test_migration_gate.py`)만 중첩 반복에서 제외하며 그 PASS와 실제 nested JSON/JUnit/누락 2,093건 거부 증거를 보존한다. skip 26개는 비-MySQL의 typer 의존성/로컬 미디어 opt-in 항목이며 MySQL skip으로 대체하지 않았다.
- 구현 단계 최종 재검증 JSON/JUnit을 별도 CLI와 evidence 집계 script로 검사했다. 실제 MySQL **445 tests · skip 0 · xfail 0 · 1,335 phases passed**, 신규 usage MySQL **101 passed**다. amount unit **34 passed**, gate unit **2,272 passed**를 포함한다. evidence는 `.codex-scratch/rt07a-20261012/{full-recheck.txt,json,xml,exit,final-evidence-summary.json}`이며 실패한 `full-final` 보고서는 gate가 실제로 거부하는 것도 확인했다.
- 실행: `DAESINGO_REQUIRE_MYSQL=1`, 실제 disposable MySQL URL, `PYTHONIOENCODING=utf-8`에서 `.venv/Scripts/python.exe -B -X utf8 -m pytest -vv --tb=short -p no:cacheprovider --ignore=tests/common/db/integration/test_migration_gate.py --basetemp=.codex-scratch/rt07a-20261012/full-recheck --mysql-report=.codex-scratch/rt07a-20261012/full-recheck.json --junitxml=.codex-scratch/rt07a-20261012/full-recheck.xml`. 보고서는 `scripts/check_mysql_test_report.py`로 검증했다. boundary checker PASS, `git diff --check` PASS. 테스트 서버는 검증 후 PID/datadir 확인 스크립트로 종료했다. 원격 CI 실행은 하지 않았다.

### 남은 위험

- 독립 재리뷰에서 cancel timing 테스트의 단발 경계 초과가 보고됐다. 원인은 미확정이며 timing 안정성 위험을 유지한다. 이를 해소됐다고 기록하지 않으며, 병합 차단 문제 없음이라는 최종 판정과 별도로 보존한다.
- RT-07(b)는 PR #353으로 병합됐다. RT-07(c)는 아래 독립 재리뷰 PASS로 RT-07 전체 DONE이며, 최종 PR 번호는 #360, merge SHA는 `505e6ad2c95617569faad1b12a45fa48d3e41919`이다. SRCH-1 실제 배선은 미구현이다. 실제 recovery·늦은 관측 보존을 RT-07(a)의 schema/append 결과로 검증했다고 주장하지 않는다. B-G1의 terminal 기반 recovery와 P-7 의미는 그대로다.
- raw textual SQL/외부 DB writer는 application amount binder를 우회할 수 있다. MySQL은 column 변환에서 소수를 반올림할 수 있어 CHECK로 원래 입력 scale을 복구할 수 없다([MySQL rounding](https://dev.mysql.com/doc/refman/8.4/en/precision-math-rounding.html)). 공식 append/live Core write 경계의 검증을 보장하며 raw SQL writer까지의 보호나 DB UPDATE/DELETE 권한 차단을 구현하지 않았다. repository는 Final을 수정/삭제하지 않는다.
- tracker와 Final의 context 정합은 후속 finalize가 확인해야 한다. 재시도에 영향을 주는 실제 lock timeout/deadlock은 caller의 기존 transaction 정책 대상이다. 새로운 identity로 재시도하거나 provider를 재호출하면 안 된다.
- RT-07(a) 구현 당시에는 사용자 요청에 따라 기존 미추적 파일을 보존하고 커밋·push·PR 없이 로컬 상태로 남겼다. 이후 병합 상태는 위 PR #349 행이 현재 사실이며, 당시 검증 증거와 요청 이력은 보존한다.

---

### RT-07(b) — execution UsageSink · explicit finalize (2026-10-13)

**현재 병합 상태: PR #353 merged · merge SHA `95dfff8b3ba11f95b76a168dd18ccc1573c02b39`.** RT-07(b) 병합 당시 RT-07 전체는 IN_PROGRESS였다. 아래 구현·검증 기록은 RT-07(b) 당시의 이력이며, 현재 RT-07 전체 DONE 판정은 아래 RT-07(c) 독립 재리뷰 기록을 따른다. RT-07(b) 병합 자체를 RT-07 전체 완료나 Issue close로 해석하지 않는다.

**착수 확인**

- branch `feature/runtime-usage-sink-finalize`, HEAD `51683e0b0f3ebd71664ff8771610cab7df8ef476`. 사용자 제공 AGENTS, Plan §6 RT-07/§12, Tech Spec §3.3/4.5/11.1–11.4, Contract §4–8, Baseline B-G1/§2.12, Plan P-7/P-10, Log RT-03–07, 기존 usage/schema/repository/amount와 ExecutionContext/WorkerLoop/composition/transaction helper를 읽었다. 저장소 AGENTS.md 파일은 검색에서 확인되지 않았다.
- GitHub connector로 Issue #293 CLOSED, Issue #294 OPEN, Accepted #244 U-1–U-4와 최종 결정 댓글 `5979576799`, RT-07(a) PR #349 merged와 위 merge SHA를 직접 확인했다. 처음 gh CLI는 네트워크 오류였으며 connector에서 확인된 정보만 사용했다.

**구현 결과**

- `common/usage/port.py`의 stdlib-only `UsageSink` Protocol은 begin/finish/finalize와 provider 오류와 분리된 `UsageError` taxonomy를 소유한다. `ExecutionContext.usage_sink`는 `UsageSink | None`이며 repr/비교에서 제외한다.
- `DurableUsageSink`는 execution/case context와 DB-only transaction runner를 받는다. Worker composition은 claim별 factory를 WorkerLoop에 전달한다. dispatch 전 checkpoint 뒤 실행마다 새 sink를 주입하며 cache/state를 execution 간 공유하지 않는다. heartbeat의 기존 cancel signal/ownership fence는 같은 객체로 유지한다.
- begin은 callback 밖에서 UUID 기반 Runtime ID와 occurred_at/typed STARTED snapshot을 만든다. INSERT/1062 locked read로 replay하며 원래 begin context가 바뀌면 conflict다. 동일 sink가 이미 발급한 ID만 explicit begin replay에 쓸 수 있다. COMMIT 불명/소진의 `UsagePersistenceError.usage_id`에도 그 ID를 유지한다. 이 ID는 예외 문자열/로그에 넣지 않는다. begin 예외 뒤 호출자는 HTTP를 실행하지 않는다.
- finish는 token 전체/합계, finite duration, integer latency, pricing context, exact KRW cost, outcome/failure 관계를 DB 진입 전에 검증·복사한다. row를 잠그고 STARTED 조건부 UPDATE로 OBSERVED를 보존한다. 동일 typed 관측은 timestamps를 바꾸지 않는 no-op, 다른 값은 conflict다. 실제 FAILED invocation·parsing failure의 token/cost null도 보존한다. ownership 상실을 이유로 관측 저장을 차단하지 않는다.
- explicit finalize는 OBSERVED 이후 caller가 확인한 logical Run 관계만 받는다. FAILED Run도 실제 Run ref로 연결하며 이 execution sink의 null 사유는 RUN_NOT_PRODUCED만 허용한다. tracker lock → 기존 append_final → OBSERVED 조건부 FINALIZED 표시 순서가 하나의 transaction이다. 두 단계 사이 실패와 rollback은 모두 되돌리고, 같은 identity/관계 replay는 no-op, 다른 관계는 conflict다. finish는 정상 finalize 이후 같은 관측 replay만 허용한다. recovery finalize/late observation 처리는 구현하지 않는다.
- 모든 method의 DB resource는 runner가 반환 전에 닫는다. provider/fake caller는 transaction 밖에 있고 callback에는 외부 I/O가 없다. callback retry 동안 ID·snapshot·시각을 유지한다. Worker registry는 UsageError를 loop까지 전달하며 loop는 RUNTIME_USAGE_PERSISTENCE/VALIDATION/CONFLICT/STATE FAILED로 처리한다. T1 retry는 결과만 보존하며 handler/HTTP를 다시 부르지 않는다.
- UsageError 문자열은 정적 메시지다. raw input/response, DB exception/SQL, path, tracker identity/state를 structured log나 ValidationError에 전달하지 않는다. Pydantic 입력 모델을 추가하지 않고 기존 Final validator의 typed normalization을 정적 오류 경계로 감싼다.

**Plan 대비 변경 · 새 implementation detail**

- engine 직접 소유 대신 transaction callback injection, 재시도마다 ID 생성 대신 callback 밖 고정 ID/snapshot, unconditional upsert 대신 locked read+조건부 UPDATE, last writer wins 대신 typed snapshot conflict, 별도 commit 대신 append→marker 원자 transaction, process 공용 sink 대신 claim별 factory를 선택했다. 하지 않으면 각각 DB 정책 결합·중복 invocation·관측 덮어쓰기·Final/tracker 불일치·execution 상태 혼선이 생길 수 있다. 상세 비교와 실행 순서는 [RT-07(b) 계획](../superpowers/plans/2026-10-13-runtime-usage-sink-finalize.md)에 기록한다.
- begin explicit replay를 위한 준비 snapshot은 execution-local cache에만 유지한다. 이 surface는 새 invocation 발급과 이미 발급된 begin의 persistence replay를 구분하기 위한 detail이며 restart/recovery read port가 아니다. caller가 이미 수행한 HTTP를 반복할 권한을 뜻하지 않는다.
- 기존 KindRegistry가 모든 handler Exception을 일반 오류로 바꾸는 것을 실제 MySQL RED로 확인해 UsageError 재전파를 추가했다. 공유 registry가 상태를 갖는 변경은 없다.
- RT-07(b) 당시 P2 리뷰 후 execution sink에 DIRECT_NO_RUN 차단 검증을 추가했다. 당시 OBSERVED tracker의 DID NOT RAISE RED와 차단 GREEN 2개, reviewer의 unit 22개는 그 시점의 증거다. 공유 Final validator·Contract·DB CHECK는 DIRECT_NO_RUN을 허용한 채 유지했다. 이후 Issue #294 Owner 확인에서 job 내부에도 no-Run 호출이 유효하고 이 차단의 계약상 근거가 없음을 확인해 RT-07(c)에서 해제한다. 당시 차단을 이미 허용한 구현으로 읽히게 한 기존 Log 문구를 정정한다.
- 새 acceptance `usage_sink` family/parameter는 기존 독립 test inventory와 production gate에 추가한다. nested actual-report suite에 새 Worker MySQL 경로를 명시했다. workflow/require/JSON-JUnit 판정 정책·Case-owned 파일·migration·DECIMAL·DB CHECK·기존 append_final은 변경하지 않는다.
- 첫 전체 MySQL 실행은 529 passed / 6 failed였다. 새 COMMIT fault proxy 테스트가 base URL의 TLS를 상속한 것이 원인이다. helper는 TLS-disabled client를 요구하며 기존 Final proxy 테스트도 명시적으로 끈다. 새 테스트의 proxy URL에 같은 설정을 추가한 뒤 base URL의 TLS가 활성인 조건에서 6 passed를 확인했다. 제품 DB/TLS 설정은 변경하지 않았다. 실패 JSON/JUnit도 gate가 거부하는 증거로 보존한다.

**Contract / Decision / Baseline 영향:** 모두 없음. Runtime port signature/DI/cache/error taxonomy는 Plan §12.3 implementation detail이다. Search interface에 새 값/새 의무를 추가하거나 실제 adapter를 수정하지 않았다.

**Owner 확인 포인트**

- Deferred Audit B: HTTP 직전 begin 및 이미 완료된 HTTP의 재호출 금지, caller-owned Run identity/usage_refs와 explicit finalize 연결, FAILED Run/실제 미산출의 구분, COMMIT 불명 소진 후 고정 ID replay, atomic Final/tracker 상태를 확인한다.
- 실제 Run 존재 확인은 run owner caller 책임이다. Runtime은 run schema를 읽거나 결과를 추정하지 않는다. 사용 예시/fake caller를 SRCH-1이 소비하되 이번에 실제 Search 배선·provider retry를 구현하지 않는다.
- finish 저장 실패 후 실제 관측값의 durable 복구·terminal reconciliation·recovery finalize·P-7 늦은 관측·read projection은 RT-07(c) 후속이다. 이번 범위에서 해당 정책을 미리 정하지 않는다.

**Verification — 이번 구현자 직접 실행**

- 최초 RED: unit 15 failed, Worker unit 6 failed, actual MySQL 27 failed(미구현). 새 gate family/parameter를 기존 gate가 허용하는 RED 45 failed / 2715 passed, validation family 포함 추가 RED 11 failed / 158 passed를 보존한다.
- 초기 GREEN: unit/Worker 21 passed; 기존 Final append·새 sink·Worker 회귀 targeted 181 passed; actual lock timeout/deadlock stage 6 passed. registry 경계 RED 2 failed / 3 passed 후 actual Worker+unit GREEN 27 passed. mutable caller snapshot 복사도 검증했다.
- 새 sink actual MySQL 47 passed는 DIRECT_NO_RUN 수정 전 증거다. ACK 유실 1회 및 3회 retry 소진 뒤 같은 ID/snapshot replay, begin/finish/finalize 1205/1213, 동시 finish/finalize, append/marker 실패 rollback, 관측 검증을 포함한다. P2 RED DID NOT RAISE 후 no-run GREEN 2 passed를 별도 보존한다.
- gate/unit GREEN 2881 passed는 마지막 DIRECT_NO_RUN parameter 추가 전 증거다. 마지막 소스의 전체 pytest 안에서 별도로 실행한 require-MySQL suite는 **535 tests / 1605 phases, skip 0 / xfail 0**, 실제 서버 **8.4.7**, JSON/JUnit gate PASS다.
- 그 actual require JSON/JUnit을 대상으로 필수 parameter **381개 × 7층 = 2667개** 누락을 모두 거부했다. 새 usage_sink **50개 × 7층 = 350개**가 포함된다. 새 parameter metadata(role/scenario/parameter) 개별 삭제 **150개**, 새 family 전체 삭제 **11개**도 모두 거부했다. nested pytest의 자체 parameter-removal 검사도 PASS이며 별도 구현자 검증 결과는 `mysql-require-final-mutations.json`에 보존한다.
- **최종 전체 pytest: 5800 passed / 26 skipped / 실패 0, 2314.29초, exit 0.** nested gate를 제외하지 않은 전체 실행이다. 26 skip은 비-MySQL typer 미설치 4개 및 실제 영상·로컬 미디어/명시적 opt-in 미제공 22개다. 전체 JSON/JUnit의 실제 MySQL은 **540 tests / 1620 phases, skip 0 / xfail 0**, 별도 CLI gate PASS다. 새 unit **23 passed**(sink 17 / Worker 6), 새 MySQL **53 passed**(sink 48 / Worker 5)는 이 최종 실행에 포함된다.
- 실행 조건: `PYTHONIOENCODING=utf-8`, `DAESINGO_REQUIRE_MYSQL=1`, disposable localhost MySQL URL(connect_timeout=2/read_timeout=10/write_timeout=10), `.venv/Scripts/python.exe -u -B -X utf8 -m pytest -vv --tb=short -p no:cacheprovider --basetemp=.codex-scratch/rt07b-20261013/full --mysql-report=.codex-scratch/rt07b-20261013/full.json --junitxml=.codex-scratch/rt07b-20261013/full.xml`. 마지막 product/test 수정은 proxy 테스트 TLS 명시이며 이후 변경은 검증 산출물과 문서뿐이다.
- boundary checker PASS(위반 0), Contract fixtures PASS(구조 62 / JSON 26 / 의미 104), workflow Actionlint 5 files/오류 0·YAML policy·bash -n/ShellCheck 5 run steps PASS. pyflakes는 기존 검사 방식대로 비활성이다. 원격 CI는 실행하지 않았다.
- 증거: `.codex-scratch/rt07b-20261013/`의 RED/GREEN 출력·actual MySQL JSON/JUnit·정적 검사. 테스트 임시 서버는 localhost 전용 MySQL 8.4.7/port 13332/datadir `/tmp/rt07b-20261013/data/`이며 기존 사용자 DB/서비스를 수정하지 않는다.
- 정리: datadir/port/bind/version을 대조하고 활성 테스트 연결 0을 확인했다. fixture schema/계정 잔여 0, base test schema/계정 삭제 후 남은 테스트 schema/계정 0이다. 전용 서버를 종료한 뒤 workspace 테스트 process 0, MySQL process 0, port closed, pid/socket 없음까지 확인했다. RED/실패 보고서와 서버 로그·datadir는 증거로 남기며 기존 미추적 4개 항목은 보존한다.
- 최종 `git diff --check` 및 새 파일 syntax/공백 검사 PASS, staging 0, branch/HEAD 유지. `review.diff`는 새 파일까지 포함하며 `review-manifest.json`에 변경 19개 파일과 SHA256을 기록한다. 이 산출물과 나머지 `.codex-scratch/`는 커밋 제외다. 사용자 독립 재리뷰·Owner Audit·원격 CI는 아직 실행되지 않았다.

**남은 위험**

- process kill·finish 이후 recovery finalize·late observation·terminal reconciliation·usage_refs projection은 이번에 검증하지 않는다. 아직 전체 RT-07의 완결성을 주장하지 않는다.
- DB callback runner와 caller port 순서는 composition의 신뢰 경계다. Python callable에 외부 I/O를 못 넣도록 sandbox하지 않는다. 실제 Search provider retry가 UsageError를 재시도하지 않는 배선은 SRCH-1에서 검증해야 한다.
- begin ACK 불명 후 STARTED가 이미 durable할 수 있다. 예외 뒤 HTTP는 보내지 않고 같은 발급 ID로 persistence를 재확인해야 한다. finish/finalize 소진도 provider를 재호출할 근거가 아니다.
- existing raw SQL binder 우회·MySQL rounding, 제3자 logger의 전역 masking 미보장, 이전 TLS/2013 timing 실패의 원인 미확정 위험은 유지한다. 이번 검증이 그 원인을 해결했다는 의미는 아니다.
- wall-clock 시각은 invocation/관측 기록용이며 lease 판단은 기존 DB 시간이다. 운영 지연·실제 비용/가격/FX·원격 CI 실행 시간을 측정하지 않았다.

---

### RT-07(b) — 독립 확장 MySQL heartbeat/T1 실패 조사 (2026-10-13)

**조사 당시 기록 · 현재 RT-07(b)는 PR #353 merged · merge SHA `95dfff8b3ba11f95b76a168dd18ccc1573c02b39` · RT-07 전체 IN_PROGRESS.** 독립 재리뷰의 최초 실패를 해결됐다고 기록하지 않는다. 사용자 요청의 systematic-debugging 절차로 traceback → 값 생성 경로 → 후보별 실험 → 새 환경 검증을 수행한다. 이 조사에서 제품·test source는 수정하지 않으며 기존 RT-07(b) 변경을 역적용하지 않는다.

**최초 실패의 확인된 증상**

- 원본 `C:/Users/cheol/AppData/Local/Temp/rt07b-independent-require.xml`은 535 tests / failures 1 / skipped 0, 즉 534 passed / 1 failed다. 대상은 `test_heartbeat_db_error_reconnects_without_retry_or_handler_failure[healthy]`다. 원본 XML/JSON을 새 증거 경로에 복사하고 SHA256을 기록했으며, 현재 gate가 실패 보고서를 거부하는 것도 직접 확인했다.
- 호출 경로는 test line 324 → WorkerLoop `_run_claims` → composition `record`/`operation` → `run_worker_transaction`/`_attempt` → jobs.repository `finish` line 213 → `_execution_model` line 105 → JobExecution `state_fields_are_consistent`다. 에러는 assertion이 아닌 Pydantic model validator의 `ended_at < (started_at or queued_at)`다. SUCCEEDED에서 started_at이 필수이므로 이 실패는 started_at 비교이며 heartbeat_at은 validator 입력/하한이 아니다.
- **확인 가능한 실제 ended_at: `2026-10-13T05:56:29.691520Z`. 최초 started_at / heartbeat_at은 확인할 수 없다.** 원본 XML의 row/payload repr가 `...`로 축약됐고 JSON은 node/phase/outcome만 가진다. cleanup 기록의 원래 datadir `/tmp/rt07b-independent-20261013/data/`도 현재 WSL에서 존재하지 않아 원본 binlog/row를 복원하지 못했다. 축약된 무명 숫자를 heartbeat_at이나 started_at으로 추정하지 않는다. 최초 session 설정과 OS/DB 시각 역행 여부도 확인할 수 없다.

| 값 | 생성 주체·clock | 저장/사용 시점 |
| --- | --- | --- |
| queued_at | enqueue의 DB UTC_TIMESTAMP(6) | 초기 QUEUED insert |
| started_at | claim UPDATE의 DB NOW(6) | RUNNING claim transaction, COMMIT 후 dispatch |
| heartbeat_at | 전용 heartbeat connection UPDATE의 DB NOW(6) | 갱신 transaction COMMIT, 실패 시 connection 반환 후 다음 tick 재접속 |
| ended_at | T1 finish의 SELECT DB NOW(6) | RUNNING snapshot 조회 후·model 검증 전 생성, 검증 후 UPDATE·COMMIT; 최초 실패에서는 UPDATE 전에 validator가 거부 |

- 네 column은 DATETIME(6), PyMySQL datetime은 naive, contract projection은 queued/started/ended에 UTC tzinfo를 부착한다. Python wall clock은 위 JobExecution 비교값에 사용되지 않는다. Worker의 monotonic clock은 metrics/scheduling용이며 UsageSink의 Python UTC clock은 usage method용이다. [MySQL 시간 함수](https://dev.mysql.com/doc/refman/8.4/en/date-and-time-functions.html) 및 [소수초 정밀도](https://dev.mysql.com/doc/refman/8.4/en/fractional-seconds.html)의 공식 의미도 실제 SQL 실험과 대조했다.

**RT-07(b) 변경과의 연결**

- diff와 호출 흐름에서 heartbeat start → 기존 started log → 추가 checkpoint/factory → dispatch → 기존 T1 callback/commit_guard → heartbeat join 순서를 확인했다. T1 transaction 경계와 SQL timestamp 생성은 바뀌지 않았다. factory는 engine/connection을 소유하거나 checkout하지 않고 runner closure·execution/case 문자열·빈 cache·Lock을 준비한다. healthy handler는 UsageSink begin/finish/finalize를 호출하지 않는다.
- `dataclasses.replace`는 execution/job/case/kind/attempt/trace와 같은 cancel signal/ownership fence를 유지하고 usage_sink만 바꾼다. constructor 229회에서 SQL 0, 재현 matrix의 healthy 비교 27건에서 claim/factory/T1 identity 일치·attempt 1·각 실행 identity 고유·candidate ended_at이 해당 DB NOW(6) 결과와 일치함을 확인했다.
- **직접적인 timestamp/DB 경계 변경의 인과관계는 확인되지 않았다.** [추론] factory가 dispatch 이전 Python 작업을 추가해 thread scheduling에 영향을 줄 가능성까지 배제한 것은 아니다. repository/model이 미변경이라는 사실만으로 RT-07(b)와 무관하다고 단정하지 않는다.

**후보별 조사 — 제품 수정 전**

| 후보 | 직접 확인/실험 | 현재 판단과 한계 |
| --- | --- | --- |
| Python/DB clock 혼용 | claim/heartbeat/T1의 생성 SQL 역추적, candidate ended_at과 기존 DB NOW 결과 일치 | 이 JobExecution 비교 경로에 Python wall clock은 들어오지 않음; DB wall clock 역행은 별도 후보 |
| DATETIME 정밀도·반올림 | actual column precision 모두 6, 123456/999999/다음 초 000000/000001 roundtrip 동일 | 검사한 경로에서 정밀도 손실 없음; 최초 실측 하한값은 미복원 |
| transaction 시작 전 생성/COMMIT 시각 | 같은 transaction에서 successive statement NOW 갱신, 한 statement의 두 NOW 동일 | transaction 전체에 고정된 NOW가 아니며 ended_at은 COMMIT 시각이 아닌 검증 전 statement 시각 |
| 이전 row/attempt·context 재사용 | 새 fixture schema/engine, UUID execution, healthy 27건 identity/attempt/DB 값 비교 | 조사 실행에서 혼용 없음; 최초 snapshot의 모든 필드는 미복원 |
| session timezone/연결 복원 | application session 관측 1424건 모두 +00:00; pooled 동일 connection +09:00→checkout +00:00, heartbeat 새 connection +00:00 | 현재 factory/fixture 조건의 복원 확인; 최초 session 설정은 미확인 |
| 실행 순서/격리 | 단독 20회, heartbeat file 28개×3회, 최초 직전 8개+healthy 9개×3회, joint 81개 | 27 runs / 212 passed / skip 0 / xfail 0; 자연 발생 오류 재현 없음. 진단 query/I/O가 timing에 미칠 수 있어 최종 전체 inventory는 제품 monkeypatch·추가 SQL 진단 없이 실행 |
| DB wall clock/session timestamp 역행 | 400.94초·3916 sample에서 DB/Python 역행 0; 별도 connection SET timestamp를 1초 역행시키면 동일 validator 거부 | 통제 실험은 실패 기전만 확인한다. 최초 session override 또는 WSL/OS clock step의 발생 증거는 없으며, 과거/샘플 사이 역행을 배제할 수 없음 |

**근본 원인·수정 판단**

- 근본 원인은 **미확정**이다. 자연 발생 오류나 그 원인에 대한 결정적인 최소 RED를 확보하지 못했으므로 제품·test source 수정, sleep 추가, 허용 오차 확대, assertion 제거를 하지 않는다. 인위적인 session clock 역행을 실제 제품 결함 재현이나 수정 RED로 분류하지 않는다.
- 재실행 통과만으로 해결됐다고 판단하지 않는다. 최초 실패와 비교값 미복원, 원래 session/clock 조건 미확인을 별도 위험으로 유지한다. RT-07(b)의 상태 전이·provider 호출 횟수·UsageSink 의미는 그대로다.

**이번 조사 직접 최종 검증**

- 새 검증은 base table 0 / fixture schema 0을 확인한 별도 MySQL 8.4.7 datadir `/tmp/rt07b-debug-final-20261013/data/`, port 13335에서 시작하며 기존 성공 보고서를 사용하지 않았다. 최초 report의 selected 목록에서 파일 순서를 복원하고 실행 후 **535개 selected node의 순서 완전 일치**를 확인했다. 최초 환경 전체는 복원할 수 없으므로 root account/version/확인된 inventory만 대응하며 port/datadir는 새로 분리했다.
- **최종 require: 535 passed / 15 deselected / 실패 0, 722.08초, exit 0.** 실제 MySQL 535 tests / 1605 phases, skip 0 / xfail 0, 새 JSON/JUnit 및 별도 CLI gate PASS다. 최초 실패 healthy도 이 순서에서 PASS다. 실행은 `run-final-require.py`가 최초 selected에서 고유 파일 순서를 복원하여 `-m mysql -vvv --tb=long --showlocals -p clock_failure_only -p no:cacheprovider --basetemp=.../final-require --mysql-report=.../final-require.json --junitxml=.../final-require.xml`로 수행했다. 실패 후 hook 외에 제품 monkeypatch·추가 SQL 진단은 사용하지 않았다.
- **최종 targeted: 104 passed / 실패 0, 91.22초, exit 0.** heartbeat 28 + Worker unit 6/MySQL 5 + UsageSink unit 17/MySQL 48이다. 실제 MySQL 81개 / 243 phases, skip 0 / xfail 0을 별도 보고서로 확인했다. 안전한 timestamp/session 진단도 새 파일에 보존했다.
- 새 actual require 보고서에서 **필수 381 parameters × 7층 = 2667개** 누락을 모두 거부했다. 새 usage_sink parameter 증거 누락 350개가 포함되며 metadata 삭제 150개·family 전체 삭제 11개도 거부했다. 이전 성공 mutation 보고서를 통과 근거로 쓰지 않았다.
- boundary PASS(위반 0), Contract fixture PASS(구조 62 / JSON 26 / 의미 104), Actionlint 5 files/오류 0·YAML policy·bash -n/ShellCheck 5 run steps PASS. pyflakes는 기존 검사 방식대로 비활성이다. 최종 git diff --check PASS다. 제품/test source 무수정이므로 이번에는 전체 pytest를 반복하지 않았으며, 앞 절의 과거 5800 passed 결과를 이번 조사에서 새로 실행한 검증으로 재인용하지 않는다. 원격 CI도 실행하지 않았다.
- 최종 clock monitor는 1225.16초 / 11954 samples에서 DB/Python 역행 0이었다. 100ms 샘플 간 차이 관측이며 더 작은 clock step 또는 과거 발생의 배제 근거로 확대하지 않는다. 원래 OS/DB clock 조정 여부는 미확정이다.
- 조사/최종 서버 모두 활성 테스트 연결 0, fixture schema/계정 잔여 0, base schema 제거 후 남은 테스트 schema/계정 0을 확인하고 종료했다. 알려진 event_scheduler Daemon 1개는 테스트 연결과 구분했다. 두 port(13334/13335) closed, MySQL process·pid·socket 없음, workspace test process 0을 확인했다. 종료 후 Linux tmp의 server.log 경로가 사라져 error log는 보존하지 못했으며 그 소실 이유는 확정하지 않는다. timestamp diagnostics·clock samples·환경/preflight·JSON/JUnit·cleanup 증거는 Windows workspace에 보존됐다.
- 증거는 `.codex-scratch/rt07b-debug-20261013/`의 initial 원본 복사/SHA·traceback·matrix JSON/JUnit/diagnostics·hypotheses·clock samples·final 새 보고서이며 커밋 제외다. 성공 경로의 값 수집은 test-only plugin에 한정하고 제품 structured logging을 추가하지 않았다. 최종 require의 hook는 실패 후에만 안전한 timestamp/identity hash를 추출하며 제품 monkeypatch·추가 SQL·sleep을 수행하지 않는다.
- 이번 조사에서 변경한 저장소 파일은 **이 Log 하나**다. 착수 baseline manifest와 비교해 RT-07(b) 기존 제품·test·gate/다른 문서의 byte hash 유지, HEAD `51683e0b`/branch 유지, staging 0과 기존 제외 파일 보존을 확인했다. 커밋·push·PR는 실행하지 않았다.
- **재리뷰 준비 판단:** 원인 미확정·비교값 미복원·새 검증 범위/한계를 명시하고 독립 재리뷰를 다시 요청할 수 있다. 로컬 검증상 중간 커밋/PR 준비는 가능하나 원인이 해결됐다거나 최종 병합 차단 문제가 없다는 판정은 아니다. 기존 제외 파일을 일괄 staging하지 않으며, 미확정 위험의 수용·병합 판단은 기존 재리뷰/Deferred Owner Audit 절차를 따른다. 새 Owner 사전 승인 gate를 추가하지 않는다. RT-07 전체 상태/Issue 연결은 위 IN_PROGRESS/Refs를 유지한다.

### RT-07(b) — 독립 재리뷰 최종 통과 후속 기록 (2026-10-13)

- **사용자가 전달한 독립 재리뷰 최종 판정: PASS.** 이전 병합 보류가 해제됐으며 남은 병합 차단 문제는 없다. 앞 절의 재리뷰 미실행/준비 판단은 당시의 기록으로 보존하고, 현재 판정은 이 후속 기록으로 갱신한다.
- 최초 heartbeat 시각 실패는 **근본 원인 미확정 비차단 위험**으로 유지한다. 해결된 것으로 판단하지 않으며 RT-07(b)의 직접 원인이나 외부 환경 문제로도 확정하지 않았다. 최초 실패 이력·복원하지 못한 비교값·조사 범위와 한계는 위 기록 그대로 보존한다.
- 재리뷰 근거인 새 MySQL require inventory는 **535 passed / skip 0 / xfail 0**, targeted는 **104 passed**다. 새 JSON/JUnit gate PASS와 함께 누락 parameter **2,667건**, metadata **150건**, family **11건**이 모두 거부됐음을 위 조사에서 직접 실행한 검증 증거로 유지한다. 이번 Log 갱신에서 테스트를 새로 실행한 것은 아니다.
- 전체 pytest **5,800 passed / 26 skipped**는 구현 단계에서 보존한 검증 증거이며, 실패 조사 또는 이번 독립 재리뷰 후속 갱신에서 전체 pytest를 다시 실행한 결과로 취급하지 않는다.

| 항목 | 현재 기록 |
| --- | --- |
| RT-07 상태 | IN_PROGRESS |
| 중간 PR 연결 | Refs #294 (RT-07(b)) |
| PR 번호 | #353 |
| merge SHA | `95dfff8b3ba11f95b76a168dd18ccc1573c02b39` |

---

### RT-07(c) — durable Run 관계 경계 조사 및 구현 전 중단 (2026-10-13)

**Status: IN_PROGRESS · 최종 연결 예정: Closes #294 · PR 번호 pending · merge SHA pending.** 구현 완료 또는 독립 재리뷰 통과 기록이 아니다. 사용자가 명시한 「새 Search 공개 surface/필수 callback이 필요하면 코드를 진행하지 말 것」에 따라 제품·테스트·gate 구현 전에 중단했다.

**이 절은 2026-10-13의 조사·중단 이력이다.** 이후 Issue #294에서 Search의 durable Run 저장소가 없고 최초 영속화 경계가 T1 produced임이 확인되어 아래 2026-10-14 기록으로 중단 조건이 해소됐다. 이 절의 resolver 필요성·미검증 상태를 현재 구현 상태로 읽지 않는다.

**직접 확인한 근거**

- branch `feature/runtime-usage-reconciliation`, HEAD `95dfff8b3ba11f95b76a168dd18ccc1573c02b39`. 로컬 `origin/develop`도 같은 commit이다. GitHub connector로 Issue #294 OPEN, #244의 Accepted 최종 댓글 `5979576799` 및 Search Owner 댓글 `5969821122`, PR #349/#353 merged 및 각각의 merge SHA를 직접 확인했다. 최신 원격 develop tip을 별도로 조회한 결과로 확대 해석하지 않는다.
- Plan §6 RT-07/§12 전체/P-7/P-10, Tech Spec §3.3/§4.5/§11.1–11.4, Final UsageRecord Contract §4–8, Baseline B-G1/§2.12, RT-06 startup/periodic hook 및 현 usage/Worker/read-port 구현·관련 테스트를 대조했다. 저장소 내 AGENTS.md 파일은 검색에서 확인되지 않았으며 사용자 제공 지침을 적용했다.
- `begin()`은 run 관계가 모두 null인 STARTED를 기록한다. `finish()`의 저장 snapshot에는 Run 관계가 없고 관측값만 OBSERVED에 기록한다. `finalize()`는 caller가 확인한 관계로 Final append와 tracker FINALIZED 표시를 한 transaction에 묶는다. 관계만 먼저 durable하게 저장하는 현 port/callback은 없다. 따라서 finish 뒤 finalize 전 process kill의 pending tracker는 Run 미산출과 이미 산출된 Run의 미전달을 구분할 수 없다.
- Runtime의 `JobExecution.produced`는 execution 단위 ContractRef 목록이며 usage별 관계가 아니다. 특히 STALE 전이는 `produced=[]`를 저장하므로 Run 부재의 증거가 아니다. `ExecutionContext`나 begin replay cache도 process restart에서 durable 관계를 복원하지 않는다.
- 현 Search 공개 함수/서비스는 capability 결과를 반환한다. `AnalysisRun.usage_refs`는 파생값이며 현 구현은 Runtime usage identity 배선 전의 `usage:<source_id>`를 사용한다. 현 `SearchLedger`는 process-local list이고 Final 원장도 durable Run resolver도 아니다. 검토한 공개 API와 Accepted #244에서 execution/usage별 복구 조회 surface 및 확정 미산출 증거 callback은 확인되지 않았다. Runtime이 Search 내부 저장소를 직접 import하거나 terminal/조회 실패를 RUN_NOT_PRODUCED로 바꾸지 않는다.

**대안 비교 · 권장 방향(미승인 제안)**

| 안 | 효과 | 한계/Owner 영향 | 판단 |
| --- | --- | --- | --- |
| 현 Runtime durable 데이터만 사용 | 명시적 관계가 durable하게 있는 경우만 복구하고 불충분한 행은 pending 유지 | 현재 sink가 만든 finish→finalize 공백과 실제 Run 미생성 증거를 닫지 못함 | 안전한 보류 동작은 가능하나 RT-07(c) 전체 acceptance를 만족하지 못함 |
| composition이 주입하는 durable Run resolution port | usage별 PRODUCED / NOT_PRODUCED / UNRESOLVED를 구분하고 FAILED Run도 실제 ref로 연결 | Search의 새 공개 조회/미산출 증거 의무 및 false STALE 이후 판정 안정성 합의 필요 | 전체 acceptance를 위한 조건부 권장. Owner 확인 전 구현하지 않음 |
| 기존 sink에 관계 보존 callback 단계 추가 | Final 전에 Runtime tracker에 관계를 durable 보존 | Search가 Run 저장 후 callback 전에 죽는 공백이 남음. 원자성 또는 복구 가능한 전달·미산출 확정 규칙이 추가로 필요 | callback만 추가하는 안은 불충분. 새 의무 확인 필요 |

- 필요한 interface 제안: `resolve_usage_run(*, execution_ref, case_id, usage_id) -> Produced(run_ref, durable_evidence) | NotProduced(durable_evidence) | Unresolved`. 기존 구현/승인된 signature가 아니다. Produced는 해당 execution/case/usage와 실제 durable Run의 연결, NotProduced는 단순 조회 부재가 아닌 최종 미산출 근거를 의미한다. Unresolved는 pending으로 남긴다. payload·provider 응답을 전달하지 않는다.
- resolution은 Runtime transaction 밖에서 실행해야 한다. 전달된 근거는 transaction 전체 replay 및 이후 sweep에서 안정적이어야 하며, NOT_PRODUCED 판정 뒤 늦은 Worker가 다른 Run을 산출하는 공백을 어떻게 막는지 Owner가 확인해야 한다. Runtime transaction은 terminal execution과 tracker를 다시 검증하고 동일 identity/snapshot으로 짧게 finalize하는 방향이다. 이를 현재 보장이라고 기록하지 않는다.

**P-7 및 read-port 판단 — 미구현 설계 방향**

- RT-07(b)의 FINALIZED finish는 동일 관측 replay만 허용하고 상이한 값은 conflict다. 이 동작을 모든 recovery FINALIZED에 그대로 적용하면 아직 관측이 없던 recovery row에 늦은 실제 관측을 보존하지 못한다. P-7에 따라 Final은 그대로 두고 tracker에 첫 늦은 관측을 durable 보존하며 동일 replay는 no-op, 상이 관측/관계는 conflict로 처리하는 방향을 권장한다. Final UPDATE는 Contract §8-1 위반이므로 배제하고 관측 거부/휘발성 로그만 남기기는 P-7을 만족하지 못한다. 구체 상태/marker와 event 재전달 방식은 아직 구현 선택으로 확정하지 않았다.
- 정상 Final 이후 최초 관측 덮어쓰기는 허용하지 않는다. recovery 이후 관측 저장과 event는 transaction/observer 실패로 Final identity·관계가 바뀌지 않도록 분리해야 한다. 원장과 tracker의 late 관측이 달라져도 Final이 authoritative다.
- 현 read port는 여전히 `usage_refs=[]`다. 최종 구현은 `usage_record.execution_ref`별 Final ID만 중복 없이 결정적으로 projection하고 pending tracker는 제외해야 한다. validator/Case 소비 경계 변경은 불필요하다는 설계 방향이며 구현·검증 결과는 아니다.

**Verification · RED→GREEN · 남은 범위**

- 이번 직접 실행은 자료/코드/Git 조회 및 문서 변경 검증이다. RT-07(c)의 TDD RED→GREEN, 실제 MySQL 20개 요구 scenario, JSON/JUnit gate·누락 mutation, 전체 pytest, boundary/fixture/workflow 검사는 실행하지 않았다. 새 MySQL skip/xfail 결과는 미측정이며 0으로 보고하지 않는다. 위 RT-07(a)/(b)의 수치는 과거 보존 증거다.
- 제품·test·migration·CI gate를 수정하지 않았고 외부 provider/테스트 DB/server/thread/process를 생성하지 않았다. 이번 schema/account/connection 정리 acceptance를 검증했다는 뜻은 아니다. 문서 diff 검증 및 보호 파일 hash 비교 결과는 `.codex-scratch/rt07c-20261013/document-verification.json`에 보존한다.
- 상세 조사·필요 interface·대안·완료 보고 12항목은 `.codex-scratch/rt07c-20261013/design-boundary-review.md`에 보존한다. scratch는 Git ignore 대상이며 커밋 제외다.
- Contract/Accepted Decision/Baseline 변경 없음. 제안한 Search surface는 새 의무일 수 있어 Plan §12.3 확인 대상이며 아직 Owner에 메시지를 보내거나 승인받지 않았다. 사용자가 기존 승인 surface를 지정하거나 새 의무에 대한 Owner 확인을 제공한 뒤 구현을 재개해야 한다.
- RT-07(c) 구현의 독립 재리뷰 요청 가능 상태가 아니다. 설계 경계 검토는 가능하다. process-kill·동시성·COMMIT 불명·P-7·usage_refs 전체 acceptance, SRCH-1 실제 배선과 기존 미확정 timing 위험은 남아 있다. 커밋·push·PR 생성·staging은 하지 않는다.

---

### RT-07(c) — Owner 합의 반영 · produced 기반 reconciliation (2026-10-14)

**Status: DONE · 최종 PR 연결: Closes #294 · PR 번호 #360 · merge SHA `505e6ad2c95617569faad1b12a45fa48d3e41919`.** 독립 재리뷰 PASS 및 남은 병합 차단 문제 없음을 사용자 전달 결과로 기록한다. 로컬 구현·검증·테스트 DB 정리 후 재리뷰 요청 상태였던 기존 이력은 아래 보존한다. 이번 갱신은 RT-07 절의 문서 변경만이며 코드·테스트 수정/재실행, staging·커밋·push·PR 생성은 하지 않는다.

**독립 재리뷰 최종 판정 — PASS(사용자 전달 결과)**

- 남은 병합 차단 문제 없음. Owner 합의에 따른 `JobExecution.produced` 기반 복구, 명시적 `DIRECT_NO_RUN`, 별도 Search resolver를 추가하지 않는 경계를 확인했다. 예정 Run ID 자체를 존재 근거로 삼거나 빈 produced에서 DIRECT_NO_RUN을 추론하지 않는다.
- **재리뷰 직접 실행 결과:** targeted **3,475 passed**; 실제 MySQL **590 passed / 1,770 phases**, 신규 reconciliation **51개 포함**. 아래 구현 단계 보존 증거와 별도로 기록하며, 이번 문서 갱신에서 테스트를 다시 실행한 결과가 아니다.
- **누락 거부 검증:** 신규 parameter 증거 누락 **357건**, metadata 누락 **153건**, family 누락 **13건**을 거부했다. P-7 late observation의 durable 관측 보존·immutable Final·replay/conflict 및 `usage_refs`의 Final-only projection 검증도 통과했다.
- **구현 단계 보존 증거:** 전체 pytest **6,374 passed / 26 skipped / 실패 0**, full MySQL **591개 / 1,773 phases**. 이를 독립 재리뷰에서 전체 pytest를 새로 실행한 수치로 재인용하지 않는다. 상세 RED→GREEN·실제 MySQL·gate·cleanup 기록은 아래 보존한다.
- **비차단 개선 후보:** malformed 후보별 오류 격리. 재리뷰의 병합 차단 finding이 아니며 이번 문서 갱신에서 구현하지 않는다.
- **후속 확인:** 원격 CI의 실제 실행 시간과 기존 **900초 nested timeout** 안의 완료 여부는 확인이 필요하다. 로컬 통과를 원격 CI 통과로 확대하지 않으며 timeout을 완화하지 않는다. 최종 PR은 `Closes #294`, PR 번호는 `#360`, merge SHA는 `505e6ad2c95617569faad1b12a45fa48d3e41919`이다.

**설계 경계 및 기존 사실 정정**

- Issue #294의 Runtime 답변 `6145102027`, Search 답변 `6148574716`, 최종 확인 `6150512406`을 connector로 직접 읽었다. Search의 Run은 provider 호출 전 선발급 ID와 호출 후 메모리 객체이며 별도 Run 저장소가 없고, 최초 durable 관계는 T1의 `JobExecution.produced`다. 따라서 앞 절의 「Search 내부 durable Run + T1 전 kill」은 현재 구조의 실제 gap이 아니다. 새 Search resolver/필수 callback/저장소를 추가하지 않는다.
- 대안은 기존 produced 사용 / 새 resolver / begin 전 durable Run 생성이다. Owner 확인에 따라 기존 produced를 선택했다. 나머지 둘은 현재 조회할 Search durable 상태가 없거나 새 저장소 의무를 만들므로 채택하지 않는다. SRCH-1은 예정 ref 전달과 FAILED AnalysisRun의 produced 반환을 배선한다는 Search의 명시적 확인을 따른다.
- DIRECT_NO_RUN은 job 내부에서도 유효한 기존 Contract 의미다. RT-07(b)의 execution sink만 거부했던 사전 검증을 정합화한다. 기존 Log의 「허용했다」와 실제 차단 코드/테스트 불일치는 위 b 기록을 당시 사실로 고쳐 보존했다. 빈 produced를 DIRECT_NO_RUN으로 추론하지 않는다.

**구현 결과**

- frozen `runtime_0004`는 tracker에 `planned_run_kind/ref`, `direct_no_run`, `recovered_at`, `late_observed_at`를 추가한다. 기존 frozen revision과 Final UsageRecord schema는 변경하지 않는다. legacy 행은 예정 관계 없음/explicit no-run false로 유지해 임의 finalization하지 않는다. 실제 MySQL forward migration 보존 및 live metadata DDL 정합을 검사한다.
- 신규 migration의 7개 ALTER를 한 ALTER로 묶어 추가 DDL round trip 6회를 줄였다. SHOW CREATE 정합과 legacy 보존 검사는 통과했다. require-MySQL 실행은 변경 전 968.98초, 변경 후 682.55초였으나 이 환경의 관측값이며 운영 성능이나 시간 상한을 보장하지 않는다. 기존 중첩 실제-report gate의 900초와 workflow timeout 20분은 완화하지 않았다.
- begin은 optional 예정 Run ref 또는 명시적 null + DIRECT_NO_RUN 선언을 durable STARTED에 저장한다. 예정 ID 자체는 실제 Run 존재 근거가 아니다. 기존 b의 intent 생략/발급 ID replay는 유지하고, 같은 ID의 다른 intent는 conflict이며 begin에서 RUN_NOT_PRODUCED를 선결정하지 않는다.
- 자동 normal T1 및 recovery는 terminal execution과 tracker를 짧은 usage별 transaction으로 잠그고 예정 ref를 produced와 대조한다. 일치하면 FAILED 포함 실제 ref, 불일치하면 RUN_NOT_PRODUCED, 명시적 no-Run이면 DIRECT_NO_RUN이다. RUNNING/QUEUED, missing/cross-case execution, intent 불명 행은 변경하지 않는다. malformed/duplicate produced는 검증 오류이며 단순 부재로 다루지 않는다.
- 정상 T1 commit·connection 반환 뒤 별도 usage transaction을 실행한다. STALE/T2 transaction 뒤 기존 startup/periodic hooks에도 연결한다. transaction callback에는 DB I/O만 있고 기존 B-D8를 사용한다. candidate snapshot·finalized_at은 callback 재시도 밖의 고정 준비 상태로 유지하며 unknown COMMIT은 immutable Final과 대조한다. 일반 post-T1 오류는 handler/provider/T1 재실행을 일으키지 않고 sweep에서 다시 복구한다. 기존 fatal/cleanup/thread lifecycle 및 느린 hook/join의 상한 미보장 정책은 유지한다.
- b의 standalone explicit finalize는 caller가 실제 관계를 확인하는 호환 API로 유지한다. 새로운 자동 Worker 경로는 terminal produced를 사용하고 Search의 세 번째 호출을 요구하지 않는다. 이미 FINALIZED인 identity replay는 늦게 보강된 tracker 관측을 Final과 비교해 덮어쓰지 않고 immutable Final의 context/관계를 확인한다.

**P-7 선택**

- b의 FINALIZED 관측 동일성 검사만 유지하면 미관측 recovery Final 뒤 첫 실제 finish를 거부한다. Final UPDATE는 append-only에 어긋나고 휘발성 로그만 남기면 관측 보존을 못 하므로 둘 다 배제했다.
- recovery 표식이 있는 Final tracker에서 최초 늦은 finish는 관측이 없으면 실제 관측을 보존하고, 이미 관측됐다면 동일성 검사 후 late marker만 남긴다. FINALIZED 상태·Final identity·run 관계·Final snapshot은 바꾸지 않는다. 같은 관측 replay는 durable no-op, 다른 관측/관계는 sanitized conflict다.
- 내부 fresh reviewer가 정상 FAILED T1의 미관측 STARTED 확정에서 recovery 표식이 없어 finish persistence replay가 거부되는 Important 1건을 지적했다. 실제 Worker/MySQL RED 1 failed(UsageConflictError) 후 미관측 자동 T1 fallback도 usage recovery로 표시하도록 수정했다. 정상 관측 완료 T1은 recovery로 세지 않는다. 수정 후 신규 actual MySQL 51 passed에서 해당 regression GREEN을 확인했다. reviewer의 재현은 _locked만 대체한 읽기 전용 Python 검사였고 MySQL 검사는 구현자가 실행했다. 사용자 독립 재리뷰와 구분한다.
- `late_observed_at`는 관측과 같은 transaction의 durable event 표식이다. `runtime.usage.late_observation` logger/observer는 commit 및 connection 반환 후 best effort로 호출한다. 로그 전송의 exactly-once/장애 시 외부 전달 보장은 약속하지 않는다. ACK 불명·logger 장애에서도 durable marker와 실제 관측은 남는다.

**read port 및 관측**

- `read_executions`는 `usage_record.execution_ref`별 Final ID만 PK 중복 없이 정렬해 projection한다. pending tracker/private column은 노출하지 않고 없으면 []다. JobExecution validator와 Case의 대표 execution 선택 경계는 유지한다.
- recovered_count는 recovery marker가 있는 committed 행 수, inflight_count는 non-FINALIZED 행 수다. oldest age는 하나의 DB 집계 snapshot에서 DB NOW(6)를 기준으로 계산한다. metric observer는 typed 숫자만 받으며 structured log의 count는 비음수 정수, age event는 기존 duration_ms 표현을 사용한다. 원시 SQL·URL·path·전체 snapshot을 logger/observer/UsageError 문자열에 전달하지 않는다.

**RED→GREEN 및 최종 검증 — 구현 단계 직접 실행의 보존 증거**

- 기존 unit baseline 23 passed. 새로운 relation/P-7/concurrency/metric/projection actual MySQL 29 failed RED 후 기존 usage 회귀 포함 195 passed GREEN. Worker/T1/startup/periodic/OS kill 5 failed RED → 5 passed GREEN.
- COMMIT OK packet 실제 소비·1회 ACK 유실/3회 소진 후 재실행, actual 1205/1213 및 전체 transaction rollback/retry, begin intent/direct explicit finalize, forward legacy 보존: 15 passed. 첫 실행 4 failed/11 passed는 test SQL이 Final에 없는 finalized_at을 조회한 문제였다. traceback으로 1054 원인을 확인해 tracker JOIN으로 고친 뒤 통과했으며 제품 정책은 바꾸지 않았다.
- malformed produced의 부재 오판을 추가 RED 1 failed(DID NOT RAISE)로 확인해 RuntimeContractRef 구조/중복 검증을 추가했다. 이 변경 이후 최종 targeted 재검증 결과는 아래 최종 evidence에 기록한다.
- independent MySQL inventory 추가 후 기존 gate가 새 family 13개와 parameter 전체 삭제 49개를 허용하는 RED 62 failed/3160 passed를 확인했다. parameter metadata 삭제 추가 RED 49 failed/98 passed도 확인했다. production gate에 별도 필수 inventory를 추가하고 기존 Case/Runtime inventory·timeout·skip/xfail 정책은 유지했다.
- 최종 증거는 ignored `.codex-scratch/rt07c-20261014/`에 보존한다. 이전 a/b 수치는 이전 보존 evidence다. 사용량 한도로 중단된 뒤에는 완료된 구현·RED→GREEN·targeted·require/full pytest를 재실행하지 않고 최종 보고서 gate·집계·정리·Git 상태·문서만 마무리했다.
- 수정 후 신규 actual MySQL `targeted-fixed.json/xml`: 51 passed, skip 0/xfail 0. unit/gate/logging/sweep `unit.json/xml`: 3,475 passed, MySQL 194 deselected. 관련 Worker·RT-06·read-port 회귀는 537 passed/2 failed였고, 실패 원인은 두 기존 migration head 기대값이 runtime_0003에 머문 것이었다. runtime_0004로 기대값만 갱신한 후 실제 MySQL 재검증 2 passed이며 최종 full에도 포함됐다.
- 최종 고정 코드 require-MySQL `require.json/xml`: 실제 MySQL 590 tests/1,770 phases, skip 0/xfail 0/failure 0, gate PASS, 682.55초. pytest 요약의 4 skipped는 MySQL이 아닌 typer 미설치 collection skip이다. 독립 inventory 432 parameters × 7 evidence 층의 누락 3,024건, 그중 신규 51 parameters의 누락 357건, 신규 metadata 누락 153건, family 누락 13건과 실패 보고서를 모두 거부했다(`require-mutations.json`, `require-mutations-final.txt`).
- 최종 전체 pytest `full.json/xml/txt`, exit 0: **6,374 passed / 26 skipped / failure 0**, 1,667.89초. 26 skip은 typer 미설치 4건과 로컬 미디어·명시적 opt-in 조건 22건이며 MySQL skip은 0이다. 중첩 실제-report gate도 기존 900초 제한 안에서 통과했다. 최종 full JSON/JUnit에 현재 gate를 실행해 PASS를 확인했다: **MySQL 591 tests / 1,773 phases(setup/call/teardown 각각 591), skip 0 / xfail 0 / failure 0**. require와의 1건 차이는 full에 포함된 `test_actual_report_rejects_each_missing_migration_check`이며 inventory를 줄이지 않았다.
- boundary PASS(위반 0); Contract fixtures 구조 62/JSON 26/의미 104 PASS; workflow 정적 검사 5 files/5 run steps PASS(Actionlint·YAML policy·bash -n·ShellCheck, 기존 pyflakes 비활성 조건 유지). `git diff --check` 및 신규 6개 파일 공백 검사 PASS. 원격 CI/실제 provider 실행 결과로 해석하지 않는다.
- 중간 concurrent 검증 3개는 출력 진행이 멈춰 이 작업의 process임을 확인 후 종료했으며 완료 증거로 사용하지 않는다. 검증 중 소스 변경이 포함된 중간 실행도 최종 증거와 분리했다. 최종 순차 full의 faulthandler 진단에는 중첩 subprocess.communicate 대기가 기록됐으며 실패나 timeout 완화가 아니다. 중간 지연 원인을 확정하거나 해결됐다고 단정하지 않는다.
- 최종 `cleanup-db.py`는 처음에 MySQL 내부 event_scheduler Daemon을 감지해 안전 중단했다. port/bind/datadir로 전용 서버임을 검증한 뒤 scheduler를 종료하고 기존 스크립트를 재실행해 exit 0으로 완료했다. 테스트 schema 3개 제거 후 schema/계정/기타 connection 잔여 0. 서버 종료 뒤 WSL PID 파일/socket/process/listening port와 Windows 테스트 process/13336 port 잔여 0을 확인했다(`cleanup-db.json`, `cleanup-residual.json`).
- 보호 항목 4개의 1,069 파일은 시작 SHA-256과 경로 집합이 동일하며 추가/삭제/변경 0(`protected-final.json`). HEAD `95dfff8b3ba11f95b76a168dd18ccc1573c02b39`, branch `feature/runtime-usage-reconciliation`, staged diff/미병합 index 항목 없음(`git-final.json`). 변경 26파일(기존 20/신규 6)의 전체 diff·SHA-256 manifest·요약을 `review.diff`, `review-manifest.json`, `changed-files.md`, `review-summary.md`에 남긴다. 제품 코드는 최종 검증 이후 변경하지 않는다.

**남은 위험·범위 밖**

- 정상/복구 관계 판정의 근거는 현재 Search 구조에 관한 Owner 확인이다. 이후 별도 durable Run 저장소가 생기면 T1 전 gap을 다시 검토해야 한다. legacy intent 불명 행은 자동 복구로 관계를 꾸며내지 않으며 명시적 관계 확인/이관이 필요하다.
- 실제 Search adapter 배선(SRCH-1), pricing/FX(RD-08), retention/purge(RD-10c/d), Case budget guard, SearchLedger 정리(#153)는 범위 밖이다. 기존 heartbeat/cancel timing 원인 미확정 위험, raw SQL binder 우회/rounding 한계는 유지한다.
- malformed 후보별 오류 격리는 독립 재리뷰에서 제시된 비차단 개선 후보다. 원격 CI 실행 시간과 기존 900초 nested timeout 내 완료 여부는 후속 확인이 필요하다. 로컬 통과 기록과 timeout 미완화 사실은 보존한다.
- Contract/Accepted Decision/Baseline 변경 없음. 독립 재리뷰 PASS 및 남은 병합 차단 문제 없음은 사용자 전달 결과다. 원격 CI 통과는 아직 확인되지 않았으며, 최종 PR은 `Closes #294`, PR 번호는 #360, merge SHA는 `505e6ad2c95617569faad1b12a45fa48d3e41919`이다. 이번 문서 갱신에서는 RT-07을 DONE으로 기록하고 코드·테스트 재실행, staging·커밋·push·PR 생성 없이 멈춘다.

---

## RT-08 — API composition root: `/cases` · `/commands` · `/view` · `/health/*`

Status: IN_PROGRESS · Issue: #295 · Audit: B

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| #366 | `Refs #295 (RT-08(a))` — app skeleton · envelope · health · single API process | `d436de08f8e16a11a99a322ce7fd1de36e80c05a` |
| pending | `Refs #295 (RT-08(b))` — `/cases` · `/view` · caller transaction · Runtime read port | pending |

### 구현 결과

- RT-01 `Startup`/불변 RuntimeConfig를 재사용하는 `api/app.py:create_app`과 `composition.py:compose_api`를 추가했다. factory에서 설정 검증과 engine 조립을 끝내며 listener 전에 실패한다. DB 접속·migration·provider 호출은 startup에서 하지 않는다. lifespan이 ready helper와 engine을 닫는다.
- 기존 RT-02 API QueuePool과 전용 ready NullPool을 소비한다. `/health/live`는 dependency를 호출하지 않고 Contract §5.7 body를 반환한다. `/health/ready`는 dedicated SELECT 1과 media root metadata만 검사하고 같은 절의 status/body를 반환한다. 실패 dependency는 상수 event에만 남긴다.
- `errors.py`는 Contract §3.3 envelope와 같은 문자열의 code/message_key를 만든다. 기본 404·405·transport validation body/detail을 차단하고 RT-02 BeforeCommitFailure/CommitOutcomeUnknown을 Contract/B-D8의 503/500으로 구분한다. domain validation을 재정의하지 않는다. 아직 command route/transaction은 없다.
- JSON route는 Plan P-9의 sync def다. docs/OpenAPI와 slash redirect는 비활성이다. 각 요청에 서버 trace_id를 발급하고 RT-01 context helper와 allowlist structured logger를 사용한다. request URL/query/body/header, exception 문자열/headers, DB URL, mount path와 Runtime 내부 field를 응답/로그에 담지 않는다.
- `python -m daesingo.api --revision <revision>`이 supported process 경계다. 명시적 workers=1/reload off로 B-W4를 소비하며 WEB_CONCURRENCY를 무시한다. Uvicorn raw access/error/traceback logger는 실행 구간에서 disable하고 원래 상태/handler를 복원하며 application의 안전한 event를 관측 경계로 둔다. composition 예외도 입력/traceback 없이 상수 event와 SystemExit(1)로 처리한다.
- 기존 MySQL JSON/JUnit gate에 api_health ready(normal/pool_exhausted/connection_lost/server_stopped), storage(readonly), process(single_worker)의 독립 필수 identity를 추가했다. nested migration acceptance도 tests/api를 수집하고 동일 identity의 각 evidence layer 누락을 거부한다.

### Plan 대비 변경

- 이번 작업은 RT-08(a) 하나다. Expected files 외에 stdlib metadata-only `storage.py`, bounded telemetry `events.py`, process boundary `__main__.py`를 분리했다. 파일 구조·DI·thread helper 선택은 Plan §12.3의 implementation detail이다.
- 기본 framework validation은 transport 오류 400/http.malformed_request로 차단한다. 이후 commands는 opaque JSON을 Case에 넘기고 Case의 422/응답을 보존해야 한다. generic framework HTTPException의 Contract 밖 status는 internal_error로 끝내며 새 공개 status/code를 만들지 않는다.
- ready에는 media root만 검사한다(Contract §5.7/공유 mount). API temp root·provider·Worker·queue 적체를 새로운 readiness 의무로 추가하지 않는다. B-U2 request limit은 commands가 없는 이 단계에서 전역 middleware로 적용하지 않으며 (c)에서 route별로 연결한다. B-U5의 별도 JSON request timeout은 만들지 않는다.
- 실제 RO mount는 host layout을 가정하지 않고 private namespace에서 RO tmpfs를 생성·검사·unmount한다. 서버 SHUTDOWN은 기존 suite DB와 분리된 독립 MySQL 서버에서 검증한다. mock/skip 대체가 아니다.
- Contract/Accepted Decision/Baseline 의미 변경 및 새 Case/Search 의무: 없음. Runtime Implementation Plan 본문은 바꾸지 않았다.

### 새 implementation detail

- probe별 최대 하나의 in-flight daemon call을 겹치는 요청이 공유한다. 각 caller와 최초 probe의 monotonic deadline 안에서만 성공을 인정한다. 시간 초과한 native call을 강제로 취소하지 않으며, 끝나기 전 새 thread를 누적하지 않는다. 늦게 반환한 연결은 context manager에서 닫는다. 최종 available 판정도 B-H3 deadline을 확인한다.
- `ApiEvents`: app당 daemon consumer 하나, 대기 queue 최대 128 event, 포화 시 새 event drop, correlation은 제출 시 capture, shutdown join 최대 1초. logger exception·지연·thread start failure를 응답으로 전파하지 않는다. 이 수치는 telemetry 내부 자원 상한이며 Baseline 재조정이 아니다. block된 sink를 강제로 중단할 수 없다.
- Windows metadata API에는 statvfs가 없으므로 is_dir/access 검사만 제공한다. 배포 Linux의 read-only flag는 실제 mount acceptance에서 검증한다. 경로를 별도 mountpoint로 강제하는 정책이나 probe file 쓰기는 추가하지 않는다.
- 폐기 가능한 두 번째 MySQL server를 Linux에서는 CI service가 준비한 mysql:8.4 Docker image로, Windows에서는 명시한 WSL 테스트 바이너리/라이브러리 경로로 시작한다. Docker/WSL 또는 mount 기능 부재를 skip으로 숨기지 않는다. 각 helper가 process/port/namespace를 정리한다.
- FastAPI·uvicorn runtime dependency와 HTTP test dependency를 pyproject/uv.lock에 고정했다. 구현 계획과 재현/실행 자료는 `docs/superpowers/plans/2026-10-14-runtime-api-skeleton-health.md`, `.codex-scratch/rt08a-20261014/`에 보존한다.

### Owner 확인 포인트

- 김준영: Contract health 예외 body·default 404/405/validation 차단과 오류 status 표를 확인한다. (b/c/d)의 Case 응답 전달·commit/rollback과 연결할 때 이 transport helper가 domain 응답을 감싸거나 바꾸지 않는지 확인한다.
- 김준영: dedicated probe deadline/in-flight 공유·late close, bounded lossy telemetry와 raw uvicorn diagnostics 억제, shutdown에서 native blocked call을 강제 drain하지 못하는 한계를 Audit B에서 확인한다.
- 김준영: Linux CI의 두 번째 MySQL Docker 서버와 sudo/unshare private RO mount acceptance 실행을 확인한다. workflow source는 바꾸지 않았고 remote CI 결과를 이번 local 검증으로 단정하지 않는다.
- Case/Search 새 공개 capability·의무·Consult 대상 배선 없음. command/view port는 (b/c/d), 실제 Search adapter는 SRCH-1, 전용 metrics 집계는 RT-12에 남는다.

### Verification

- RED: app factory 미구현 ModuleNotFoundError와 신규 evidence 누락 10개 허용을 직접 확인했다. 독립 리뷰 finding의 동시 ready false unavailable, uvicorn raw traceback, slow logger deadline, composition 입력 노출, event thread start failure도 각각 failing test로 보존했다.
- GREEN: 최신 RT-08(a) targeted 49 passed. 실제 MySQL dedicated ready/pool 고갈·transport 단절·독립 server SHUTDOWN·private RO mount·실제 API process를 포함한다. MySQL 대상 skip/xfail 없음. 로그 sink 예외/지연/시작 실패, 유한 queue/context, configuration/composition safe fail-fast와 raw logger 차단을 확인했다.
- 읽기 전용 독립 reviewer가 finding을 제시했고 각 finding은 root 세션에서 RED/GREEN으로 검증했다. reviewer의 sandbox pytest setup 오류와 root의 실행 결과는 구분한다. 아직 외부 Owner acceptance/remote CI PASS를 주장하지 않는다.
- API/common 최종 unit 회귀: `pytest tests/api tests/common -m "not mysql"` → 3,885 passed. MySQL 회귀는 최종 전체 required suite에 포함한다. gate unit 회귀 → 3,449 passed.
- 초회 MySQL 필터 실행은 594 passed/MySQL skip·xfail 0이지만 마지막 process identity 추가 전 수집한 자료여서 현재 gate가 거부한다. 초회 API/common 실행의 3개 실패는 nested MySQL 900초 timeout 및 검증 중 gate inventory 갱신으로 생긴 혼합 snapshot이다. 동시에 실행한 local MySQL 검증을 종료·정리하고, 소스 해시를 고정한 전체 단독 실행으로 재검증한다. 초기 실패 자료는 보존하며 최종 PASS 근거로 사용하지 않는다. 기존 timeout/gate 조건은 완화하지 않았다.
- **최종 단독 전체 pytest:** 6,463 passed · 기존 선택 실행 대상 26 skipped · Starlette/httpx deprecation warning 1. MySQL 대상 skip/xfail은 0이다. 실행 1,748.83초(29분 8초)는 로컬 실측이며 원격 CI의 소요시간을 뜻하지 않는다. 기존 nested 900초 제한을 유지한 채 통과했다.
- **최종 MySQL JSON/JUnit gate:** 596 tests · skip=0 · xfail=0 · failure=0. 전체 JUnit 6,489 testcase · failure/error 0. 별도 nested 실제 acceptance 591개 gate도 PASS이며 기존·신규 parameter mutation 3,066개 중 API 신규 42개가 모두 거부됐다.
- **신규 API evidence 누락:** 최종 full JSON/JUnit을 복사한 6 identity × 10 layer(role/scenario/parameter/collection/selection/setup/call/teardown/all/JUnit) = 60개 삭제 변형을 전부 거부했다. 원본 보고서는 변경하지 않았다.
- **최종 정리:** 소유가 확인된 독립 MySQL 8.4.7 서버에서 테스트 schema 1개를 제거했고, 남은 테스트 schema/계정/연결은 각각 0이다(시스템 daemon은 테스트 연결로 세지 않음). 서버 SHUTDOWN 뒤 PID/process/port 폐쇄, 독립 SHUTDOWN 서버·RO mount 디렉터리 부재, Windows 관련 child process 0을 확인했다. 실제 API process/port와 각 proxy도 fixture 종료 때 정리했다.
- **불변 검증:** 보호된 기존 미추적 4개 항목의 전체 1,069개 파일 inventory/해시 동일. 테스트 대상 소스 18개 해시 동일. HEAD `505e6ad2c95617569faad1b12a45fa48d3e41919` · 현재 feature 브랜치 유지, index empty. staging/commit/push/PR 생성 없음.
- 재리뷰 자료: `.codex-scratch/rt08a-20261014/{review-summary.md,changed-files.md,review.diff,review-manifest.json,full.json,full.xml,full-gate.txt,evidence-mutations.json,full-counts.json,cleanup-db.json,cleanup-wsl.txt,cleanup-processes.json,final-integrity.json}`. 초기 실패 자료도 별도 보존한다.
- boundary checker PASS(위반 0), Contract fixture PASS(문서 구조 62·JSON 26·의미 fixture 104), workflow actionlint/YAML 정책/bash -n/ShellCheck PASS(5 workflow/5 run step, pyflakes disabled), git diff --check PASS를 직접 확인했다. 최종 문서 갱신 후 다시 확인한다.


### 2026-10-14 독립 재리뷰 finding 수정 — 착수 기록

- 이전 RT-08(a) 읽기 전용 reviewer의 추가 finding 없음과 구현자의 전체 6,463 PASS 기록은 당시 검증 범위다. 사용자가 후속 독립 재리뷰에서 전달한 병합 차단 finding은 P1 handler write 정지 시 interpreter logging.shutdown 교착, P2 composition 실패의 동기 sink 종속, P2 CLI 실행 예외 traceback 노출의 세 건이다. 이전 filter 지연 테스트는 handler lock/atexit 경로를 검증하지 않았다. 이 절의 재현·수정·실행 검증 주체는 구현자이며, 수정본 독립 재리뷰 결과와 구분한다.
- P1 구조 선택 사전 검토: (A) daemon + join(timeout) 유지로는 stdlib shutdown이 기다리는 handler lock을 해소하지 못한다. (B) 별도 logging process는 쓰기 강제 중단이 가능하지만 추가 process/IPC/stream 전달 및 B-W4 실행 경계 부담이 생긴다. (C) API 소유 handler의 직렬 I/O lock을 stdlib handler cleanup lock과 분리하고 shutdown에서 sink I/O를 하지 않는 방식을 선택한다. 정상 event emission 자체에서 write/flush를 완료하며, 유한 queue drain은 ApiEvents가 소유한다. 기본 stdout은 unbuffered fd write로 Python buffered stdout의 종료 lock도 잡지 않는다. 제공 TextIO의 close/최종 flush는 caller 소유이며 API가 제3자 handler를 제거하거나 종료하지 않는다. Worker handler, allowlist/formatter, logging 전역 자료구조와 정상 interpreter 종료 정책은 유지한다. 포화·정지 sink 진단 유실 trade-off는 기존 telemetry 정책 안의 implementation detail이다.
- RED/GREEN과 후속 검증 결과는 finding별 실행 후 아래에 추가한다. RT-08 IN_PROGRESS, `Refs #295 (RT-08(a))`, PR/SHA pending, Contract/Accepted Decision/Baseline 의미 및 Case/Search 의무 변경 없음.

| Finding | 수정 근거 및 직접 RED → GREEN | 검증 주체 |
| --- | --- | --- |
| P1 handler write 정지 / interpreter 교착 | 실제 TextIO.write가 release 없이 정지한 subprocess: close 반환 marker 뒤 5초 timeout RED 1. API 소유 handler I/O lock과 stdlib cleanup lock 분리, emission flush / shutdown no sink I/O, 기본 stdout unbuffered fd. 정상 queue drain·포화·context 회귀 포함 P1 GREEN 49 | 구현자 |
| P2 composition fail-fast sink 종속 | composition 예외 + 실제 handler write 정지와 fatal diagnostic 3종 RED 4. 임시 ApiEvents의 유한 drain으로 실패 코드 1을 우선하며 진단 유실 허용. 기존 정상 composition 실패 event 포함 GREEN 5; stderr/traceback/secret/DB URL/경로 비노출 | 구현자 |
| P2 CLI 실행 예외 원문 노출 | 잘못된 port 4종, 서버 Exception/KeyboardInterrupt/SystemExit/BaseException 및 cleanup RED 12. port 0~65535(0은 OS 배정) 선검증, quiet argv 실패 코드 1, 서버 일반/fatal 실패 코드 1·KeyboardInterrupt 코드 0, finally 자원 정리와 signal/서버 logger 복원. API/Worker 회귀 포함 GREEN 67 | 구현자 |

- P1 fatal 정책 보완: 기존 consumer fatal이 thread excepthook으로 끝나 owner에게 전달되지 않는 RED 3, prelaunch fatal 시 미완료 queue task RED 3을 확인했다. 일반 Exception은 best-effort, fatal은 원문을 thread stderr에 출력하지 않고 close에서 owner에게 전달한다. common log_event_best_effort의 strict BaseException 전달 및 Worker handler 정책은 유지한다.
- 이번 읽기 전용 reviewer의 추가 P1: stdout 실패의 고정 fallback이 buffered stderr에서 정지하면 종료가 다시 교착된다. reviewer가 close_returned 뒤 7초 timeout을 직접 재현했고 구현자도 unread stderr subprocess RED 1(9초 timeout) 후 동일 API 소유 unbuffered fd 경계를 적용했다. 고정 JSON fallback/Worker 동작 유지, unread stdout/실제 write 포함 GREEN 4. reviewer의 동일 재현도 코드 0 종료를 확인했다.
- 이번 reviewer의 추가 P2: Uvicorn이 lifespan shutdown 예외를 삼킨 뒤 idempotent close가 실패 정보를 잃어 코드 0이 됐다. 실제 LifespanOn 및 partial Readiness 조립 RED 3, 실제 uvicorn.run/socket bind/shutdown subprocess RED 1(코드 0)을 확인했다. dispose는 한 번만 실행하고 cleanup_failed boolean을 process owner까지 보존하며, 조립 중 실패는 모든 할당 engine을 정리한다. 해당 cleanup GREEN 18. 실제 서버 subprocess에서 코드 1, stderr empty, listener 폐쇄/signal 복원을 확인했고 reviewer도 실제 Uvicorn으로 모든 자원의 once-only close와 코드 1을 재검증했다.
- 이번 reviewer의 추가 P2: 실제 Thread.start는 native launch 뒤 interruptible wait를 하므로 callback을 소비한 뒤 start가 실패할 수 있다. unconditional get_nowait의 Empty가 원래 fatal을 덮고 consumer 소유권이 유실되는 RED 3을 실제 Thread로 확인했다. Empty를 구분하고 public ident로 확인한 시작된 consumer를 close owner에 남겨 정리한다. fatal과 시작된 consumer 실패에서는 추가 제출을 중지하며, ordinary prelaunch start 오류 격리는 유지한다. 기존 start 실패 포함 GREEN 7; reviewer도 fatal 2종/Exception 1종과 미완료 queue task 0을 직접 확인했다.
- 최종 읽기 전용 소스 재리뷰: 이번 reviewer는 추가 actionable blocker 없음으로 보고했다. 위 reviewer 직접 subprocess 검증과 구현자의 실행 결과는 구분한다. 외부 독립 재리뷰/Owner acceptance/원격 CI 승인 판정이 아니다. 최종 전체 실행 결과 및 잔여 정리는 아래에 추가한다.


- 최종 신규 회귀 초회는 40 PASS/1 timeout이었다. 실제 서버 종료 뒤 Windows connect_ex의 default 대기가 포함됐으며, 별도 phase marker/faulthandler 진단에서 main 종료 1.344초 후 probe 대기만 2.031초를 확인했다. listener fd 폐쇄 직접 확인과 probe timeout 0.3초를 추가해 검증 경계를 유한하게 만들었다. stderr/handler shutdown의 5초·9초 회귀 제한은 완화하지 않았다. 진행하던 전체 초회 실행은 중단/보존하고 MySQL 보조 서버·연결 잔여 부재를 확인한 뒤 새 final 경로에서 실행한다. 초기 timeout/부분 실행은 최종 PASS 근거로 사용하지 않는다.

- 첫 전체 final 실행은 6,507 PASS / 기존 26 skipped / 1 failure, 2,330.92초였다. 기존 Worker 실제 MySQL `normal_t1`의 단일 final record/provider 호출 검사는 통과했고 `recovered_at is None`만 실패했다. 해당 file은 단독 실제 MySQL 6 PASS(12.32초), nested 591개 acceptance/gate에서는 통과했다. 정상 T1 뒤 recovery=False finalize와 0.05초 주기 recovery=True reconciliation이 경합할 수 있는 기존 코드 경로를 확인했지만 실패 원인을 단정하거나 Worker 의미를 수정하지 않는다. 실패 보고서는 보존하고 gate 성공으로 처리하지 않으며, 소스 불변인 전체 재실행으로 최종 evidence를 확인한다. RT-07 Owner 재현/판단 대상이며 RT-08(a) 수정과의 관련성은 확인되지 않았다.

### 재리뷰 수정본 최종 직접 검증 / 미통과 항목

- 신규 subprocess/종료/정책 41 PASS; RT-08(a) targeted 90 PASS; 실제 MySQL health 5 tests / 필수 identity 6 / phase 15 PASS, MySQL skip/xfail 0. API/common 최종 unit 회귀 3,930 PASS(377 MySQL deselected). 검증 주체는 구현자다.
- 전체 첫 실행: 6,507 PASS / 기존 26 skipped / 1 Worker normal_t1 recovered_at assertion failure(2,330.92초). 같은 Worker file 단독 실제 MySQL 6 PASS. reviewer 소스 검토는 주기 recovery=True hook과 post-T1 recovery=False 경합을 허용하는 기존 경로 및 Worker/usage/test의 HEAD 대비 불변을 확인했다. 실패 trace에 승자 정보가 없으므로 원인/RT-08 관련성을 단정하지 않는다.
- 전체 두 번째 실행: 6,507 PASS / 기존 26 skipped / 1 nested migration gate failure(2,400.88초). 첫 Worker failure는 통과했고, 실제 MySQL child의 기존 900초 제한에서 TimeoutExpired가 발생했다. timeout이나 mandatory collection/skip/xfail 조건을 완화하지 않았다. 두 full report 각각 MySQL 596개 수집 / skip 0 / xfail 0 / call failure 1이며 최종 JSON/JUnit gate는 둘 다 올바르게 거부했다. **전체 pytest 및 전체 MySQL gate PASS는 미달이다.**
- 첫 전체에 포함된 최신 nested 실제 MySQL 보고서는 591 tests / skip 0 / xfail 0 / failure 0로 JSON/JUnit gate PASS. 필수 parameter 누락 mutation 3,066개(API 42 포함) 모두 거부. 이 유효 보고서로 별도 API 6 identity × 10 layer = 60 evidence 누락 mutation을 모두 거부했으며 실패 full report를 변조하거나 합성하지 않았다.
- boundary PASS(위반 0), Contract fixture PASS(문서 62/JSON 26/의미 104), workflow actionlint/YAML/bash -n/ShellCheck PASS(5 workflow/5 run step, pyflakes disabled), git diff --check 및 신규 파일 whitespace 검사를 최종 확인한다.
- 최종 DB 정리: 검증된 작업 소유 MySQL 8.4.7 / port 13339 / datadir `/tmp/rt08a-rereview-fixes-20261014/data/`에서 남은 schema 3개를 제거하고 계정/connection(시스템 daemon 제외)/schema 각각 0을 확인했다. SHUTDOWN의 process 소멸은 pid 파일 삭제보다 늦어 첫 확인은 실패했고, 종료 완료 후 재검사에서 Linux process/port 및 보조 서버/RO mount 디렉터리 잔여 0, Windows 관련 process 0 / test port 폐쇄를 확인했다. 테스트 thread/handler는 종료한 소유 process와 정상 drain/once-only cleanup 회귀 범위에서 정리됐다.
- 보호된 기존 파일 1,069개와 테스트 소스 21개 해시, HEAD/branch/index 불변을 최종 확인한다. staging/commit/push/PR 생성 없음. RT-08 IN_PROGRESS / `Refs #295 (RT-08(a))` / PR/SHA pending 유지.
- 검증 자료: `.codex-scratch/rt08a-rereview-fixes-20261014/`의 `review-summary.md`, `changed-files.md`, `review.diff`, RED/GREEN별 txt/exit, `subprocess-verified.xml`, `targeted.json/xml`, `api-common-verified.xml`, `full-final.json/xml`, `full-verified.json/xml`, 두 실패 gate 기록, `nested-gate.txt`, `nested-evidence-mutations.json`, `cleanup-db.json`, `cleanup-wsl-final.txt`, `cleanup-processes.json`, `final-integrity.json`. 실패/부분 evidence는 보존하며 성공 근거에서 제외한다.

### Owner 확인 / 선택지와 영향 범위

- 이번 세 finding 및 리뷰 보완 소스의 내부 재리뷰는 actionable blocker 없음이었다. 외부 독립 재리뷰/Owner acceptance/remote CI 승인 또는 전체 검증 PASS를 뜻하지 않는다.
- RT-07 normal-T1 attribution: (A) 현재 의미/검증 assertions를 유지하고 테스트 scheduling을 제어해 normal-T1 경로를 결정적으로 검증하는 별도 test-only 작업, (B) background/normal winner의 recovered_at 의미와 runtime ordering을 Owner가 명시하는 별도 RT-07 작업을 구분한다. (B)는 tracker attribution/metrics 의미와 테스트/문서 영향이 있어 이번 RT-08(a)에서 변경하지 않았다. 재실행 통과가 경합을 해결했다는 의미도 아니다.
- nested 900초 timeout은 현재 환경/성능 원인 재현과 Linux CI 실행 확인이 필요하다. 기존 limit/gate를 유지한 환경 조정과, gate 실행 구조 변경을 검토하는 작업의 영향 범위를 구분해야 한다. 검증 유실·skip/xfail·부분 수집 허용은 선택지로 제시하지 않는다.
- 남은 검증 실패를 해결한 전체/전체 gate 재검증 전 merge 가능 판정을 하지 않는다. 수정본은 원 요청대로 독립 재리뷰 가능한 unstaged 상태이며 native I/O 강제 취소와 포화 시 telemetry 유실, RT-08(b/c/d)/RT-11/auth/CORS/TLS 후속 범위는 유지한다.

### 남은 위험

- Python native filesystem/socket 또는 logger code는 강제 취소할 수 없다. shutdown 뒤에도 최장 probe/sink call이 daemon에서 늦게 반환할 수 있고 Engine.dispose는 checked-out 연결을 강제로 닫지 않는다. 정상/장애 acceptance의 schema·계정·connection·process·port 정리 결과와 구분한다.
- 포화/blocked sink에서 일부 event는 유실된다. full metrics exporter와 과부하 운영 관측은 RT-12 이후이며 새 availability/budget 정책을 이 작업에서 정하지 않는다.
- 설치된 Starlette TestClient가 httpx 호환 경로의 deprecation warning을 내지만 테스트 실패가 아니다. Linux remote CI 실행 시간 및 Docker/sudo namespace 권한은 local PASS로 확정하지 않는다.
- RT-08은 (b) cases/view, (c) commands/enqueue, (d) 중단 배선이 남아 IN_PROGRESS다. media/auth/CORS/TLS, 새 Case/Search surface는 이번 범위 밖이다. staging·commit·push·PR 생성 없이 pending 상태로 남긴다.

---

## 2026-10-15 RT-08(a) 실패 조사 및 중단 검증 재개

RT-08은 `IN_PROGRESS`, 연결은 `Refs #295 (RT-08(a))`, PR 번호와 merge SHA는 `pending`이다. 이전 절의 실패/부분 실행 및 독립 리뷰 기록은 당시 증거로 보존한다. 아래는 구현자의 추가 조사와 직접 실행이며, Owner 승인·외부 독립 재리뷰·원격 CI 판정과 구분한다.

### 이전 Worker / nested 조사 — 최초 사건과 새 재현 구분

- 첫 Worker 실패 node는 `tests/worker/test_usage_reconciliation_worker_mysql.py::test_normal_t1_finalizes_from_committed_produced_without_third_search_call`, 직전은 sweep의 `test_ordinary_hook_exception_isolated_in_startup_and_next_periodic_pass`였다. `recovered_at is None` 기대에 실제 `2026-10-14 12:21:23.090831`이 나왔다. 당시 started_at/heartbeat_at/ended_at/NOW(6)/session timezone/schema UUID/transaction·connection 상태는 원본 stdout/JSON/JUnit에 없고 삭제된 schema에서 복원할 수 없다. **최초 사건의 정확한 winning transaction과 근본 원인은 미확정이다.**
- 단독, 직전 순서, fresh MySQL/schema 반복 이후 별도 실제 DB Event 순서 재현으로 periodic recovery=True가 post-T1 recovery=False보다 먼저 finalize하는 `recovered_at` assertion RED를 확인했다. HEAD Worker/logging 코드 대조도 같은 RED다. 자연 반복에서는 handler의 전역 pool checkedout==0 assertion이 concurrent sweep connection 때문에 실패하고, Worker가 이를 terminal failure로 처리한 뒤 stop에 도달하지 않아 idle을 계속하는 별도 결함을 관측했다. live row/stack/후속 exception trace를 보존했다.
- 확인된 테스트 결함만 수정했다: normal-T1 테스트는 실제 startup/DB/T1/기존 assertions를 유지하며 periodic wait를 cleanup까지 대기시키고 handler stop을 finally에 둔다. 직전+전체 reconciliation file 7 PASS, 별도 fresh instance/schema 10회 PASS다. Worker/usage/jobs 제품 코드는 HEAD 대비 불변이고 handler/formatter/context/event helper 7개 AST도 같다. 이 RED→GREEN은 정상 T1 경로의 결정적 검증이며, 최초 자연 사건을 소급 확정하거나 recovery attribution 의미를 바꾼 것이 아니다.
- 최초 nested timeout은 child 마지막 node/stack/실행 개수/완성 JSON·JUnit/당시 migration 횟수가 미확보다. parent의 60초 faulthandler는 900초 순간 stack으로 취급하지 않는다. 기존 child fatal-hook cleanup 파일은 첫 성공에서 약678초, 두 번째에서 약854초 뒤 작성됐고 thread/connection/dispose 정리를 기록한다. 이 filesystem 단서는 모든 node의 마지막 완료 기록이 아니다. **최초 timeout의 정확한 부하·근본 원인은 미확정이다.**
- 새 disk MySQL 대조는 같은591개 수집 중518개 call을 완료한 채900초에 실패했다. 다음 sweep fatal-hook setup/migration을 진행했고 완료 upgrade_all480회/480.727초를 기록했다. 해당 새 실행은 interpreter shutdown 단계가 아니었다. 실제 MySQL8.4.7의 별도 tmpfs 대조에서는 child591 PASS/약650초, parent gate/누락 검사 PASS/820.47초였다. flush_commit1/sync_binlog1은 유지했고 실제 flush_method disk O_DIRECT vs tmpfs fsync, port/datadir/새 instance 및 idle disk instance 차이를 명시했다. migration5회 평균0.995초 vs0.458초, 공통300번째 node 완료455.722초 vs305.754초는 로컬 환경/storage 비용 기여를 지지하며 최초 사건의 부하를 증명하지 않는다. 900초·workflow20분·필수 inventory를 변경하지 않았다.
- 검증 주체: 위 직접 재현/실행은 구현자. 읽기 전용 내부 reviewer는 test-only isolation/cleanup과 인과 한계를 검토해 source blocker를 발견하지 못했으나 최종 full/gate/cleanup 승인 또는 Owner 판정이 아니다. 자료는 `.codex-scratch/rt08a-failure-investigation-20261014/`의 original-evidence/timeline, investigation.md, RED/GREEN별 txt/XML/JSON, PID별 trace/stack, migration/checkpoint 대조다.

### 남은 clean API/common 실패 조사

- 원본 api-common-clean은3928 PASS/2 failure/377 MySQL deselected,15819.10초였다. BaseException server-failure subprocess call7395.117초, 다음 once-only composition cleanup teardown8102.51초, 후속 KeyboardInterrupt cleanup subprocess call5.044초를 보존했다. 두 killed child stdout/stderr는 비어 있었고 당시 내부 phase/child stack은 없다.
- Windows System/Kernel-Power 원문에서23:15:22 Lid 대기 진입→01:18:34 전환의 약7392초 구간과, 이어03:33:45 Lid 복귀까지의 대기 구간을 확보했다. 수시간 call/teardown에는 실제 시스템 대기가 개입했다. 누적 JUnit으로 재구성한 node 시각은 inter-test overhead를 제외한 근사다. 원본 두 child의 정확한 내부 정지 위치와 각각의 timeout 직접 원인은 미확정으로 남기며, 단순 재실행 PASS로 해결 판정을 하지 않는다.
- 원본 직전 순서7개 관측은7 PASS/12.45초, 더 앞선 잔여를 포함한 첫74개 동일 순서는74 PASS/46.21초다. 별도 scratch plugin은 같은5초 제한에서 parent/child file stack, import/main/atexit marker, phase별 thread/handler/clock 및 child PID를 기록했다. 관련 call/teardown 뒤 MainThread만 남았고 관측 child4개/9개 모두 종료했다. 새 handler 누적이나 부모 reader/runtime thread 잔여는 관측되지 않았다. 정상 service/pytest handler의 process 종료 전 존재를 임의로 제거하거나 모두0이라고 취급하지 않는다.
- 두 failing child는 real create_app/uvicorn.run을 가짜로 대체하므로 real DB/readiness/ApiEvents를 생성하지 않으며 server-failure의 foreign handler는 NullHandler다. 기존 thread가 Windows 새 interpreter에 그대로 이어지는 구조가 아니다. 잔여 자원 인과나 제품 cleanup 결함을 재현하지 못해 이번 재개에서 제품·테스트를 수정하지 않았다. 최초 composition stalled-write의 별도5초 timeout도 이전 진단3회 PASS만으로 원인 확정된 것이 아니며 보존한다.
- 검증 controller는 실행 thread의 idle 대기 방지 요청을 finally에서 복원하고 wall/QueryUnbiasedInterruptTime을 함께 기록한다. 전역 전원 정책이나 테스트 deadline을 변경하지 않는다. QueryUnbiasedInterruptTime은 절전 시간을 제외한다([Microsoft 공식 설명](https://learn.microsoft.com/en-us/windows/win32/sysinfo/interrupt-time)). 실행 요청은 사용자의 lid/power sleep을 차단하는 기능이 아니다([Microsoft 공식 API](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate)).
- source22개 frozen hash를 확인해 이미 완료한 process safety41 PASS/targeted90 PASS를 재사용하고 반복하지 않았다. 새 API/common3930 PASS/377 deselected(364.13초), 실제 MySQL health5 PASS/필수6identity·15phase/skip·xfail0(22.16초)다. controller wall/active는 각각369.9438초/369.9438초,26.5862초/26.5862초로 대기 차이가 없다. 기존 유효 nested591JSON/JUnit gate 재검증 및60 API evidence 누락 거부 PASS다.
- 원본/새 직접 실행 자료는 `.codex-scratch/rt08a-resume-validation-20261015/`의 original-clean-evidence, original-power-events 원문, sequence-observation-summary, reused-evidence, 각 txt/XML/JSON/timing, investigation.md에 분리했다. 최초 Worker/nested/child 내부 phase 미확정 위험을 유지하며 병합 가능 판정을 하지 않는다.

### 최종 직접 검증 및 정리 — 2026-10-15

| 검증 | 결과 | 근거/구분 |
| --- | --- | --- |
| process safety / RT-08(a) targeted | 41 / 90 PASS, exit0 | 이전 동일 source의 subprocess-clean/targeted-clean 보고서 재사용; source22 hash 불변으로 반복하지 않음 |
| 최소 순서 / 원본 prefix | 7 / 74 PASS | 새 file stack·child marker·thread/handler/PID 관측, timeout5초 유지 |
| API/common | 3,930 PASS / 377 MySQL deselected | 새 api-common-final,364.13초; 최초 실패 보고서 보존 |
| 실제 MySQL health | 5 tests / 6 mandatory identities / 15 phases PASS | 새 health-final,22.16초; skip/xfail/failure0 |
| 전체 pytest | 6,508 PASS / 기존 영상 opt-in26 skipped / failure·error0 | 새 full-final,2,075.35초; controller wall/active2,084.149843초 일치, 전원 요청 복원 |
| 전체 MySQL JSON/JUnit gate | 596 collected=selected PASS, skip/xfail/failure0 | full-gate/full-counts; mandatory inventory·3phase·JUnit pair 누락 허용 없음 |
| 전체 내 nested child / gate | 591 PASS, skip/xfail/failure0,JUnit670.137초 | 이번 full의 child JSON/JUnit,900초 정책 유지 |
| evidence 누락 | parameter3,066(API42 포함) / 별도 API60 모두 거부 | 이번 full nested의 parameter-mutations 및 full-omissions; 이전 유효 nested 재검증60도 별도 보존 |
| boundary / Contract / workflow | 위반0 / 62·26·104 PASS / 5 workflows·5 run steps PASS | 새 직접 정적 검사; actionlint/YAML/bash-n/ShellCheck,pyflakes disabled; workflow20분 불변 |

- 최종 schema/account/connection 정리는 작업 소유 MySQL8.4.7/port13341/datadir `/dev/shm/rt08a-failure-investigation-memory-20261014/data/`를 확인한 뒤 수행했다. 마지막 test schema1개 제거, 남은 test schema/계정/다른 connection(시스템 daemon 제외)0. SHUTDOWN 뒤 실제 process/port13340·13341/보조 server·RO mount 잔여0을 확인하고 tmpfs를 회수했다. 소유 Windows child/process 잔여0으로 종료 process의 thread/handler도 남지 않았다. source22 hash와 보호 파일1,069개의 전체 inventory/hash, 원본 실패 artifact, HEAD·branch·index 불변 및 diff/신규 Python whitespace PASS를 마지막 integrity 자료로 확인했다. 재개 시간대의 Kernel-Power standby 전환 기록은0이었다.
- 이번 재개는 제품·테스트 수정이 없으며 source를 고정한 채 남은 순차 검증을 완료했다. 기존 Worker test-only scheduling/stop 수정과 세 API review finding 수정은 유지한다. Contract/Accepted Decision/Baseline 의미·HTTP status/body·Case/Search 의무·900초/20분 정책 변화는 없다. RT-08 IN_PROGRESS / `Refs #295 (RT-08(a))` / PR/SHA pending, staging·commit·push·PR 생성 없음.
- Owner 확인: 최초 Worker/nested와 killed child의 내부 phase 증거 공백은 정확한 원인 미확정으로 남긴다. 이번 Windows full34분35초는 Linux remoteCI20분 준수의 증거가 아니며 원격 CI는 미실행이다. 정책 변경 필요성을 단정하거나 limit을 올리지 않았다. 새 전체/gate PASS와 독립 재리뷰 가능한 artifact를 제공하지만 병합 가능·Owner acceptance·외부 재리뷰/CI 승인 판정은 하지 않는다. RT-08(b/c/d),RT-11,auth/CORS/TLS 및 새 Case/Search surface는 후속 범위다.

---

### RT-08(b) — `/cases` · `/view` (2026-10-16)

**Status: IN_PROGRESS · Refs #295 (RT-08(b)) · PR pending · merge SHA pending.** staging·commit·push·PR 생성 전 구현 기록이다.

#### Implementation Notes

**구현 결과**

- 현재 branch `feature/runtime-api-cases-view`, HEAD `d436de08f8e16a11a99a322ce7fd1de36e80c05a`. GitHub connector에서 확인한 최신 develop tip도 같았다. 직전 RT-08(a) PR #366 merged 및 이 SHA를 PR 표/색인에 반영했다. 저장소 AGENTS.md는 root/하위 검색에서 없었으며 사용자 제공 사실 기반 지침을 적용했다.
- Issue #295, Plan §6 RT-08/§12 전체, HTTP Contract §3/§5.1/§5.4/§7, 최신 HEAD의 Case 공개 interface/관련 테스트와 PR #342/#343/#366 최종 코드·댓글을 대조했다. PR #342의 `CaseStore(conn=connection, executions=read_executions)` 및 Case 행 우선 lock 합의로 소비 가능하다. 새 Case surface/callback·Owner 의무는 없다.
- `POST /cases`: request body를 읽지 않는다. 공개 `case.create_case`가 identity를 발급하며 API composition의 RT-02 transaction이 commit한다. commit ACK 뒤 별도 read transaction에서 공개 `case.get_view`로 응답을 만들고 Contract의 201, `{case_id,case_view}`, 상대 Location을 반환한다.
- `GET /cases/{case_id}/view`: 같은 Connection의 CaseStore/Runtime read port 주입으로 공개 `get_view`를 호출한다. Case가 share lock → job scope 조회 → 대표 attempt/화면 상태를 선택하고 HTTP는 CaseView 필드를 재구성하지 않는다. CaseNotFound만 404 envelope로 바꾸고 임의 KeyError를 missing Case로 숨기지 않는다.
- RT-02 helper의 precommit DB 실패는 503, COMMIT 결과 불명은 500이며 API 자동 재시도는 없다. 생성 commit 뒤 read 실패는 이미 반영된 생성에 대해 안전한 재시도를 뜻하지 않도록 500으로 처리한다. 관계없는 SQL/domain 오류는 기존 generic 500 경계다.
- transaction helper에 동기 logger를 넘기지 않고 RT-08(a)의 bounded ApiEvents만 쓴다. 성공한 Case에서 받은 identity만 safe_correlation으로 view/access event에 연결한다. 실패 요청의 raw path ID, header trace, URL/query/body, SQL/예외 원문/DB URL/경로/secret은 로그에 전달하지 않는다.
- CaseStore와 기본 adapter registry는 transaction 지역 객체다. 빈 Case의 None adapter를 앱 전체 메모리에 계속 보관하지 않는다. 실제 결과 adapter/reader factory는 Case 8-6 2단계/RT-10 후속이다.

**Plan 대비 변경**

- Expected files의 `routes_cases.py`/`routes_view.py`를 그대로 사용하고 transaction/CaseStore factory는 기존 `composition.py`에 모았다. 생성 응답 조회는 명시적으로 두 번째 transaction이다. 생성 후 read 오류의 500 보존, request state의 trusted correlation, 지역 registry는 §12.3 implementation detail이다.
- Contract/Accepted Decision/Baseline 의미 변경 없음. `/commands`·enqueue·cancel·media·인증/CORS/TLS·Case 내부 변경 없음. Runtime Plan 원문 및 workflow timeout 정책을 변경하지 않았다.

**새 implementation detail · 대안 비교**

| 선택 | 대안 | 이유 |
| --- | --- | --- |
| ApiComposition 메서드에 transaction/Store factory 집중 | route별 closure에서 같은 공개 Case 함수와 transaction helper 조립 | 두 안 모두 API-owned transaction이며 선택안은 engine/Store/error 경계를 한곳에서 검토 가능 |
| 생성 commit 뒤 별도 connection scope/read transaction | 같은 Connection에서 ACK 뒤 새 read transaction 시작 | 두 안 모두 commit→get_view 순서를 지키며 선택안은 RT-02 helper를 그대로 재사용하고 Connection을 빨리 반환함(pool의 물리 connection 재사용은 가능) |
| postcommit read 실패 500 | precommit read와 같이 503 반환 | 이미 생성된 요청의 반영 여부를 잘못 알리지 않음 |
| transaction 지역 registry | 앱 전체 빈 adapter 캐시 | 이번 slice에 필요 없는 None 항목 누적 제거 |
| bounded event의 trusted identity | raw path/header ID 및 동기 DB logger | 기존 안전한 logging·correlation 경계 유지 |

**Owner 확인 포인트**

- 김준영 Audit B: 생성 commit 이후 read 장애/ACK 유실의 500 판단과 API 무재시도, 성공 access/view event의 trace+trusted Case identity를 확인한다.
- Case 합의는 PR #342 댓글 `6118676155` 및 공개 결정 `jobexecution-read-port.md`를 따른다. 새 확인 요청/메시지 전송은 하지 않았다. PR #343의 미등록 kind도 T2에 도착한다는 정정 댓글 `6118711293`을 확인했으며 reflector/handler 배선은 이번에 하지 않는다.
- Case 8-6/RT-10 전에는 선택 후보의 실제 모듈 adapter를 API에서 새로 구성하지 않는다. 없는 adapter/지원하지 않는 상태를 성공으로 꾸미지 않고 기존 안전한 500으로 끝낸다.

**Verification — 진행 기록**

- 최초 RED: API 17 failed/1 passed(없는 Case 404는 기존 미등록 route도 만족), 신규 gate의 누락 identity 검사 36 failed/12 passed. 두 종류 실패 원본은 `.codex-scratch/rt08b-20261016/red-api-all.*`, `red-gate.txt`에 보존했다.
- 테스트 fixture 작성 오류(초기 rev 0 가정, terminal을 PENDING으로 가정, Pydantic 설정을 dataclass로 복사, URL SecretStr 검증을 건너뛴 model_copy, fixture INSERT의 available_at 누락)는 Case 결정/타입/schema 대조 후 테스트만 바로잡았다. Case 의미나 RT-02 코드는 바꾸지 않았다.
- 중간 broad `targeted`는 4 failed/3747 passed다. COMMIT proxy용 설정 작성 오류 2건과 실행 중 inventory 보강에 따른 synthetic report 불일치 2건으로, 최종 검증 근거로 사용하지 않는다. 최종 source hash 고정 뒤 전체 실행으로 다시 검증한다.
- view duration RED 1건 후 event 시간 측정 추가. 내부 fresh reviewer의 Critical/Important 없음, Minor 2건(access case_id 누락/빈 registry 보존)은 별도 RED 2건 후 수정했다. 최종 신규 actual MySQL `green-review-final`은 21 passed, skip/xfail 0이다. 내부 리뷰는 외부 독립 재리뷰/Owner acceptance가 아니다.
- broad `targeted-final`(내부 Minor 보완 전 snapshot)은 415 passed/1 failed. 기존 process-safety `test_actual_server_cleanup_failure_exit_and_listener_release`가 child 전체 5초를 넘었다(stdout/stderr 비어 있음). 원본을 보존하며 root cause를 환경 문제로 단정하지 않는다. 동일 테스트의 RT-08(a) 과거 조사 이력도 현재 실패의 원인 증명이 아니다.
- 중간 targeted와 보강 테스트의 실행 시간이 겹쳤으므로 timing 실패의 원인을 분리하지 못했다. 이후 최초 전체 실행에서 해당 종료 테스트가 3.39초로 PASS했고 실패 Worker 함수 4 parameter와 함께 분리 실행한 `failure-targeted`도 5 passed(5.00초)였다. 이는 최초 timeout의 원인 규명이나 수정 증명이 아니다. fresh reviewer도 Case eager import에 추가 비용이 있음을 확인했지만 5초 초과의 원인으로 확정하지 않았다.
- 최초 전체와 이번 별도 환경의 전체 pytest/JSON/JUnit/누락 검사 결과는 아래에 분리한다. 전체 GREEN 근거는 확보하지 못했다.
- boundary/Contract fixture 검사는 UTF-8 실행에서 PASS. workflow actionlint(5개)/YAML 정책/bash -n/ShellCheck(5개 run step) PASS, pyflakes는 설치되지 않아 actionlint 해당 규칙 비활성. nested timeout=900, CI timeout-minutes=20 유지. 원격 CI는 실행하지 않았다.

**중단 전 원본 보존 · Worker 시각 실패 조사**

- 첫 전체 `full`은 **6797 passed / 26 skipped / 2 failed**, 1536.44초였다. 실패는 Worker의 `test_failed_marker_read_or_heartbeat_commit_never_delivers_signal[read]`, `test_hooks_run_after_stale_transactions_and_preserve_live_execution[periodic]`이며 `finish` → `_execution_model` → JobExecution의 `ended_at` 시간 순서 검증에서 발생했다. MySQL 617개 중 2개가 실패했으므로 이 전체 결과는 GREEN이 아니며 strict JSON/JUnit gate도 거부했다. 26 skip은 기존 선택형 의존성·로컬 미디어 조건이고 MySQL skip/xfail은 0이다.
- 같은 실행의 nested 실제 MySQL은 **612 passed / skip·xfail 0**, 498.154초로 기존 900초 이내였다. parameter evidence 누락 **3213건**, 그중 신규 RT-08(b) **147건(21×7 layer)**을 거부했다. 실제 nested 보고서로 별도 role/scenario/parameter metadata까지 검사한 신규 identity 누락 **210건(21×10)** 및 family 누락 **7건**도 거부했다. 이 nested PASS가 부모 전체 실패를 상쇄하지 않는다.
- 재개 시 최초 전체 stdout/JSON/JUnit/exit/timing 5개와 고정 source 479개의 SHA-256을 다시 대조해 변경 0을 확인했다. 원본은 `.codex-scratch/rt08b-20261016/full.*`, 해시 manifest는 `first-full-failure-hashes.json`/`final-source-hashes.json`이다. 신규 구현·완료된 TDD·내부 리뷰는 반복하지 않았다.
- 원본 traceback의 timestamp payload는 축약되어 최초 두 실패의 정확한 started_at/ended_at 쌍은 복구하지 못했다. 두 fixture는 DB 시각으로 원장을 만들며, 정적 추적상 claim의 시작 시각 기록/commit 뒤 handler가 실행되고 finish는 새 DB 시각으로 검증한 뒤 terminal UPDATE를 한다. heartbeat는 시작 시각을 쓰지 않는다. lifecycle 테스트의 세션 `SET timestamp`는 reset/dispose 경계를 확인했으나 실패 connection으로 유출됐다는 증거는 없다.
- 별도 진단에서 **동일 WSL MySQL connection의 NOW(6)·SYSDATE(6)가 약 0.668초 역행**한 표본은 직접 확보했다(`db-clock-samples.json`, 1500회/17.578초). 같은 구간 Windows UTC 표본은 증가했다. 이는 해당 DB 시각 역행의 관측 사실이며 **최초 두 Worker 실패의 직접 원인이라는 결론은 아니다**. RT-08(b)와의 인과관계도 확인하지 못했다.
- 별도 환경 비교는 공식 MySQL **8.4.7 Win64** archive의 공개 MD5와 일치하는 패키지로 새 데이터 디렉터리/loopback 13345를 초기화해 진행했다. 기존 MySQL 8.0 설치와 WSL 서버 설정은 변경하지 않았다. durability 설정 flush-at-commit=1/sync-binlog=1을 유지했다. 새 환경 시각 표본 1500회/18.703초에서는 역행을 관측하지 못했으며, 무발생을 보장하지는 않는다. WSL/Win64·테이블명 대소문자 기본값·전역 timezone 차이는 `environment-comparison.json`에 보존했다. 제품 API/Worker engine의 세션 UTC/READ COMMITTED 정책은 동일 코드로 유지한다.
- 동일 고정 소스·기존과 같은 테스트 선택 명령의 별도 환경 전체 실행은 실패 후 원본 traceback에서 시간 필드만 읽는 scratch pytest 관측기를 사용했다. 제품/테스트 함수 교체·결과 변경·DB 시각 보정은 없다. validator·Worker·Case 의미와 timeout/gate도 변경하지 않았다. 관측기의 timing 영향 및 플랫폼 차이가 있으므로 별도 실행의 개별 PASS를 최초 실패의 근본 원인 확정으로 사용하지 않는다.
- 별도 환경 실행의 nested 검사는 **기존 900초 제한으로 TimeoutExpired**였다. 자식의 최종 JSON/JUnit 보고서는 생성되지 않았으며 완료 수·전체 nested inventory 일치를 확정할 수 없다. timeout 이후 해당 자식 PID가 남지 않은 것은 확인했다. 기존 WSL nested 612 PASS/498.154초 기록과 구분하며, 이번 별도 환경의 strict gate 통과로 대체하지 않는다. 제한이나 durability 설정을 완화하지 않았고, 정확한 지연 원인은 미확정이다.
- 별도 실행에서 의존성 누락 검증 1건도 실패했다. scratch 관측기의 `PYTEST_PLUGINS`가 자식에 상속되는 반면 해당 검증은 `PYTHONPATH`를 자체 sitecustomize 디렉터리로 교체해 관측기 import가 먼저 실패하는 충돌을 최소 collect-only 재현으로 확인했다. 관측기 ON은 `No module named rt08b_failure_probe`/exit 1, OFF는 의도한 `MySQL required dependency unavailable`/exit 4다(`probe-child-comparison.json`, stdout/stderr 보존). 이는 이번 진단 설정의 간섭이며 제품 결함으로 분류하지 않는다. 전체 원본 결과를 수정하지 않고 관측기를 제거한 해당 테스트의 단독 결과를 별도로 기록한다.

**이번 재개 최종 검증 · 판정**

- 직접 별도 환경 전체 `native-full`: **6797 passed / 26 skipped / 2 failed**, pytest 2568.84초(42분 48초), runner wall 2580.791초. 실패는 nested 900초 timeout과 위 관측기 충돌이다. 실제 MySQL **617개 중 616 passed / 1 failed / skip·xfail 0**, 신규 RT-08(b)는 **21/21 passed**다. 관측기를 제거한 해당 의존성 검증만 `observer-isolated`로 **1 passed / 1.39초**를 확인했으며 전체 raw 결과를 6798 passed로 재작성하지 않는다. 최초 종료 timeout 테스트나 이미 완료한 내부 리뷰/TDD를 별도로 반복하지 않았다.
- 최초 두 Worker 실패 노드는 이번 전체에서 모두 PASS했다(JUnit 총시간 각각 1.765초/1.701초). 기존 Uvicorn cleanup 노드도 총시간 4.634초로 PASS했다. 이 사실은 **재발하지 않은 해당 실행의 결과**이며 최초 Worker 시각 실패·targeted 5초 timeout의 원인 확정이나 해결 선언이 아니다. RT-08(b)와 최초 Worker 실패의 인과관계는 계속 미확정이다.
- `final-preservation-inventory.json`: 고정 source 479개와 최초 실패 artifact 5개 해시 변경 0. 두 전체의 **JUnit 6825개 항목/순서 및 MySQL collected/selected 617개 identity가 일치**한다. 새 nested의 최종 보고서는 없어 nested 실제 수집 identity/완료 수 일치까지 주장하지 않는다. 이번 전체 stdout/JSON/JUnit/exit/timing/실패 frame와 관측기/runner 8개 해시는 `native-full-failure-hashes.json`에 별도로 보존했다.
- `final-gate-audit.json`: strict JSON/JUnit CLI는 최초 전체와 별도 전체를 모두 **거부**, 보존된 실제 nested의 **612 tests / skip=0 / xfail=0** 보고서는 PASS다. 해당 정상 실제 보고서를 기준으로 신규 21개 identity의 collection/selection/setup/call/teardown/all/JUnit/role/scenario/parameter 누락 **210건 및 family 누락 7건을 다시 모두 거부**했다(`final-preserved-nested-{counts,omissions}.json`). 실패한 전체 보고서를 정상 기준으로 사용해 누락 검사 PASS를 만드는 방식은 쓰지 않았다. 중단 전의 전체 parameter 누락 3213건/신규 147건은 보존 결과이며 JSON 내용도 다시 대조했다. 새 native nested에서 3213건을 완료했다고 주장하지 않는다.
- 추가 안전 진단: 두 DB의 실제 API/Worker connection 모두 **UTC / READ COMMITTED / lock wait 5초**였다. 두 전체에서 모두 성공한 같은 MySQL testcase 614개의 JUnit 총시간 중앙값은 기존 0.429초/새 환경 1.534초였다. 누적 InnoDB I/O counter도 `final-database-diagnostics.json`에 보존했다. 이는 환경별 지연의 관측이며 집계 범위·플랫폼이 다른 counter와 시간 상관관계만으로 native nested timeout의 정확한 근본 원인을 확정하지 않는다. timeout 뒤 남은 개인 DB schema의 공개 실행 시각/상태 snapshot은 `native-timeout-leftover-schema.json`에 보존했고 특정 test/stack으로 단정하지 않는다.
- boundary, Contract fixture(문서 62/JSON 26/의미 104), workflow actionlint 5개/YAML 정책/bash -n/ShellCheck 5개 run step을 검증했다. pyflakes 미설치 한계를 유지한다. source·필수 evidence inventory·nested 900초·CI 20분을 완화하지 않았다. 이번 Windows 전체는 20분을 초과했고 **원격 Linux CI의 20분 준수는 미검증**이다.
- **병합 보류**: 새 환경의 nested 900초 실패/strict gate 거부가 남았다. 최초 Worker 두 실패와 targeted 5초 timeout도 정확한 원인이 미확정이므로 재리뷰의 판단 항목으로 남긴다. 관측기 충돌은 최소 재현과 관측기 없는 단독 PASS로 분리했지만 실패 전체를 GREEN으로 만들지는 않는다. 현재 자료로 RT-08(b) 자체의 새 기능 결함이 확인됐다고 단정하지도 않는다.
- 구현 13개 변경 파일·설계 선택·원본/직접 재실행·실패와 한계를 갖춘 **독립 재리뷰 요청 가능한 로컬 상태**이며 병합 승인·Owner 수락·원격 CI 통과 판정은 아니다. 상세 파일/증거 색인은 `.codex-scratch/rt08b-20261016/review-summary.md`다. 재개 후 제품/테스트 소스 변경 없이 문서·로컬 진단만 추가했다. **RT-08 IN_PROGRESS / Refs #295 (RT-08(b))**, PR/merge SHA pending을 유지한다.
- 소유한 13345/13344 MySQL은 정확한 datadir·다른 접속 0을 확인한 뒤 SHUTDOWN했고 listener/native PID 종료 및 WSL 소유 pid 파일 제거를 확인했다. 진단을 위한 datadir·로그·잔여 schema snapshot·패키지는 보존했다. 새 테스트 Python process는 남지 않았으며 시작 전부터 있던 PID 22152/22184와 기존 MySQL 8.0 설치는 변경하지 않았다. staging·commit·push·PR 생성은 하지 않았다.
- 최종 worktree audit: tracked 9개/신규 4개, 총 13개 납품 변경을 확인했다. tracked diff와 신규 4개 파일의 no-index whitespace 검사 PASS, 변경 Python 9개 AST 파싱 PASS, 다른 tracked 경계/Contract/Decision/Baseline/Runtime Plan/workflow 변경 0, staged 0, HEAD/branch 유지다. 신규 파일 no-index diff의 정상 exit 1과 whitespace 오류 exit 3은 대조 파일로 구분했다(`final-worktree-audit.json`).

**남은 위험 · 후속**

- 500/응답 유실은 생성 미반영을 보장하지 않는다. 특히 POST /cases identity 응답 자체가 유실되면 이 slice는 idempotency/recovery API를 추가하지 않는다.
- process-safety 최초 실패는 최종 회귀/진단 결과와 구분해 보존한다. 제한을 완화하거나 skip으로 숨기지 않는다.
- bounded logging은 기존대로 포화 시 lossy이며 native block을 강제 종료하지 않는다. Case 실제 adapter/Worker composition은 후속 범위다.
- commands/enqueue는 RT-08(c), cancel 배선은 (d), media는 RT-11, 별도 metrics 집계는 RT-12. RT-08 상태와 Issue #295는 계속 진행 중이다.

---

## RT-09 — 첫 비동기 E2E (integration acceptance)

Status: IN_PROGRESS · Issue: #296 · Refs #296 (RT-09) · Audit: B

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| pending | Refs #296 (RT-09) — 첫 비동기 E2E · 테스트 전용 composition · strict evidence inventory | pending |

### 구현 결과

기존 공개 HTTP/API·Worker·Case T2를 테스트 전용 composition으로 연결한다. 상세 범위·실행 증거·남은 위험은 아래 「2026-10-18 RT-09 — 첫 비동기 E2E」 후속 기록을 따른다. PR·merge SHA pending이며 DONE/Closes 판정은 하지 않는다.

### Plan 대비 변경

Plan §4가 허용한 기존 RETRY_SEARCH command + fixture를 사용한다. 제품 surface 변경 없이 E2E와 필수 evidence inventory/gate 회귀를 추가했다.

### 새 implementation detail

별도 Worker thread/engine, T1/T2 event 장벽과 독립 plain read. 자세한 내용은 아래 후속 Implementation Notes와 색인을 따른다.

### Owner 확인 포인트

두 차례 전체 MySQL 900초 timeout의 원인·fresh 전체 gate·원격 Linux CI가 미확인이다. 최종 독립 재리뷰와 deferred acceptance가 남으며 #295 timeline 후속과 분리한다.

### Verification

단독 E2E1·targeted238(실제 MySQL219/657 phases)·gate unit4595·비MySQL 회귀681 PASS/기존 영상2 skip. fresh 전체 acceptance는 미통과다. 보존683+현재 E2E1의 별도 CLI/mutation 검사를 새 전체 통과로 대체하지 않는다. 원본·건수는 아래 최종 후속 기록을 따른다.

### 남은 위험

두 전체 timeout과 fresh 전체 gate/원격 CI 공백은 병합 검증 차단이다. 비차단으로 T1 장벽/주기 redelivery 경합 가능성과 Log 동시 편집 충돌을 남긴다.

---

## RT-10 — Worker composition root: 실제 kind handler 등록 · cross-process E2E

Status: IN_PROGRESS · Issue: #297 · Audit: B · Refs #297 (RT-10(a))

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| pending | RT-10(a) 결과 저장소 gate · Refs #297 (RT-10(a)) | pending |

### 구현 결과

RT-10(a)의 해석 없는 append-only 저장소·T1 원자 저장·무ID stable ref·기존 ProducedReader callable을 구현했다. [구현·검증·실패 이력](./rt10a-produced-store.md)을 따른다. 실제 handler 등록과 Case stored adapter 배선은 후속 범위다.

### Plan 대비 변경

#346 O-1~O-3 결과 저장소 gate를 실제 handler 등록 전 첫 slice로 분리했다. Contract·Accepted Decision·Baseline·다른 Owner 공개 surface 변경은 없다.

### 새 implementation detail

`runtime_0005`·strict JSON LONGTEXT snapshot·`runtime:{execution_id}:{ordinal}` opaque ref·동일 snapshot replay/no-overwrite·COMMIT 불명 payload 검증. 상세 선택과 근거는 위 note에 있다.

### Owner 확인 포인트

Runtime/Ops deferred review: 저장 identity·T1 receipt·append-only 경계. Case의 다중 객체 의미 조립은 기존 callable을 주입하는 후속 composition이 맡는다.

### Verification

단위6,364 PASS, 실제 MySQL834 PASS/2,502 phases/skip·xfail0, strict JSON/JUnit PASS, 원본 mandatory1 PASS, parameter mutation5,997건 및 신규 omission125건 모두 거부. 기존 checker/inventory·frozen migration·timeout을 보존했다. 전체 pytest/현재 diff 원격CI는 미실행이다.

### 남은 위험

전체 RT-10의 실제 handler·비동기 Real E2E는 미완료다. LONGTEXT의 privileged raw SQL 변경은 repository 보장 밖이다. 앞선 timeout·startup 실패·중단은 note와 원본 증거로 보존한다. 독립 재리뷰용 미커밋·미스테이징 상태로 남긴다.

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

Status: IN_PROGRESS · Issue: #299 · Audit: C · Refs #299 (RT-12(a))

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| pending | RT-12(a) staging/temp cleanup · Refs #299 (RT-12(a)) | pending |

### 구현 결과

API staging 및 API/Worker temp root의 aged 잔여 scanner, producer/scan filesystem
lease, startup 1회 + 기존 주기 scan, 안전한 stop/join과 cleanup 전용 structured
count/bytes/failed_count를 구현했다. upload 생성→close→publish까지 보호하며 DB
등록 순서는 유지한다. 실제 변경 목록·데이터 흐름·검증 원본·인계는
[RT-12(a) note](./rt12a-cleanup.md)를 따른다.

### Plan 대비 변경

P-6 미확인 orphan publish와 RT-12(b) DB 집계·전체 event catalog는 제외한다.
활성 producer 하나가 있으면 root 전체 scan을 미루는 보수적인 lease를 사용한다.
현재 기본 API에는 temp materializer, Worker에는 실제 handler가 없으므로 새
profile/encoding 정책을 만들지 않고 service별 `MediaRoot` 주입 factory까지만
조립했다. 별도 합성 smoke로 API/Worker 주입 factory의 실제 Recording
analysis/incident와 활성 temp 경합·close를 직접 검증했고, 기본 handler 연결의
후속 범위와 미검증을 note에 구분했다.

### 새 implementation detail

기존 tempfile 생성 이름만 인식하고 unknown 항목·hardlink·reparse point를
보존한다. Windows ancestor pin/leaf exclusive handle 삭제, POSIX dir fd/no-follow
삭제와 root lease를 사용한다. bytes는 기존 logger 정수 count 필드의 별도 event로
기록하고 상속 correlation을 제거한다. Contract·Decision·Baseline 의미/값 변경 없음.

### Owner 확인 포인트

실제 materializer 등록 시 주입 factory 사용, 서비스 전용 local root provision,
root 전체 scan 지연과 긴 filesystem I/O의 join 지연, Linux/POSIX 검증 및 독립
재리뷰가 남아 있다. 다른 Owner 공개 surface·새 capability 요청은 추가하지 않았다.

### Verification

보존된 기능상 RED 20/8/14/2/1/4 failed → 최종 focused 51 passed.
관련 API/Worker/upload/logger/config 회귀 363 passed(마지막 두 보강 전), boundary
및 Contract fixture 검사 PASS. workflow30분/nested MySQL900초와 gate/inventory는
불변이다. 현재 소스의 bare 전체 pytest는 정확히 1회 실행해 **9800 passed /
937 skipped / 1 warning**, exit 0(412.20초)이다. MySQL 미설정 911·media opt-in
22·typer collection 4 skip이며 mandatory MySQL gate PASS를 주장하지 않는다.
추가 실제 media smoke는 pytest 재실행 없이 PASS다. 기존/원격 PR CI를 이번 직접
실행으로 사용하지 않았고 소유 test root/process/thread를 정리했다.

### 남은 위험

기본 실제 handler E2E와 Linux/POSIX·원격 CI 미실행, advisory lock에 협력하지 않는
외부 writer, root 단위 보수적 지연 및 기존 sink 한계를 note에 명시했다. 이번 세션은
reviewer/subagent·staging·commit·push·PR 없이 독립 재리뷰 가능한 변경을 준비한다.
RT-12 전체 DONE·Closes #299·merge-ready/Owner acceptance를 주장하지 않는다.

### 2026-10-23 — 독립 리뷰 P1/P2 후속 (원래 이력 보존)

- 시작: reviewer snapshot/구현 manifest의 변경20개·index hash 일치, 기존 JUnit
  hash 일치. 구현/리뷰 RAW의 hash를 별도 보존했다. 앞선 `9800 passed / 937 skipped`
  및 reviewer 결과는 과거 증거이고 이번 수정 GREEN으로 사용하지 않는다.
- P1 직접 재현: Windows와 native Linux에서 temp ancestor에 포함된 publish 파일이
  삭제돼 `count=1, bytes=9, failed=0`이었다. 기존 동일/하위만 검사하는 방향 공백과
  보호 경로 없는 재귀가 원인이다. 각 RED11 failed/7 passed → Windows GREEN69,
  POSIX GREEN57이다. 기존 root 공유 구성을 보존하기 위해 상위 temp는 publish와
  겹치는 가지 전체를 제외하고, 동일/하위 및 링크/확인 불가 구성은 lifecycle
  할당 전에 거부한다. P-6·등록 조회·orphan policy는 추가하지 않았다.
- P2 직접 재현: entries의 전체 metadata 리스트 선적재 때문에 첫/중간/마지막
  PermissionError/OSError/소실이 다른 정상 삭제까지 막았다. 100000개 열거도 미리
  적재했다. Windows/POSIX 각각 RED21 → lazy 항목별 오류 격리와 bounded 이름1개
  empty 검사로 Windows focused90/POSIX focused78 GREEN이다. 소실은 실패/삭제로
  세지 않고 그 밖의 metadata OSError는 항목당 failed1, 원문 예외는 보관하지 않는다.
- 이번 Windows upload/lifecycle/logger/config 관련 회귀407 passed(102.40초).
  공용 순회·startup validation 변경의 소비자 영향 때문에 이번 revision의 bare 전체
  pytest를 새 증거 폴더에서 1회 실행 중이다. 실제 MySQL/원격 CI는 추가하지 않는다.
- P3는 제품을 확장하지 않았다. POSIX 비협력 writer, 멈춘 filesystem I/O의 join
  지연, 예상 밖 비-OSError 뒤 주기 중단, root 전체 보존, wall-clock jump 위험과
  SoT 판단 근거를 note에 추가했다. 해당 실패 상태까지 정상/승인으로 간주하지 않는다.
- 내부 실행 계획은 hash를 유지해 ignored scratch로 옮겨 PR 후보에서 제외했다.
  후보21개(제품9·테스트7·문서5), 이번 제품 수정은 storage2개이며 Log/note에 원래
  결함·RED·수정·GREEN을 시간순으로 추가한다. Log의 기존 줄바꿈 bytes는 유지한다.
- 최종 결과·정적 검사·자원/증거 hash는 아래에 추가한다. 상태는 계속
  IN_PROGRESS · Refs #299 (RT-12(a)), PR/merge SHA pending이다. 별도 reviewer/subagent,
  staging·commit·push·PR 없이 기존 독립 대화의 후속 재리뷰에 인계한다.

- **2026-10-23 최종 직접 결과:** 이번 revision bare 전체1회 exit0,
  9839 passed/937 skipped/1 warning, 501.82초. MySQL911·
  media22·collection4 skip이며 mandatory MySQL gate/
  원격CI는 미실행이다. Windows focused90/관련회귀407, native POSIX focused78 및
  boundary/Contract/workflow30/nested900/gate 불변/diff 검사를 직접 확인했다.
  과거 증거와 분리하고 원래 실패를 재분류하지 않았다. 소유 root/lease를 정리하고
  기존 구현증거37개·리뷰증거10개 hash를 보존했다. PR 후보21개,
  내부plan 제외, staging/commit/push/PR/reviewer/subagent 없음. 기존 독립 대화의
  후속 재리뷰를 기다리며 IN_PROGRESS · Refs #299 (RT-12(a))를 유지한다.


### 2026-10-23 경로 별칭 P1 추가 수정

**IN_PROGRESS · Refs #299 (RT-12(a))**

- 후속 독립 리뷰 이후 21개 후보/branch/HEAD/index hash 일치와 기존 증거100개를
  먼저 확인했다. 기존 P2 해소·일반 경로 P1 GREEN은 보존하며 별칭 실패와 구분한다.
  Windows extended namespace/Linux double-slash 양방향 혼용을 OS samefile로 확인한
  제품 RED는 각각16FAIL/46PASS,16FAIL/38PASS다. 일반/양쪽 같은 표기는 통과했다.
- lexical anchor 불일치가 원인이다. 기존 no-follow pin으로 existing ancestor를
  검증하고 Windows handle의 normalized volume GUID 이름, POSIX 동일 root identity
  확인 뒤 single-root 표현을 사용한다. configuration과 보호 scan 비교가 같은
  canonical 함수를 사용하며 삭제 중 resolve하지 않는다. 미생성 suffix는 검증하고
  UNC/device/reparse/불명확한 이름은 lifecycle 전 거부한다. 8.3 실제 OS alias도
  확인했다. 추가 baseline source copy10FAIL/30PASS는 현재 GREEN과 분리한다.
- 최종 focused Windows156PASS, native POSIX122PASS/Windows전용6SKIP이며 기존
  P2 streaming/소실·집계·privacy 및 안전성·lifecycle 회귀를 포함한다. 관련 broad는
  470PASS/3FAIL(WinError5 exists, disconnect idle 선행, log sink9초 timeout)이다.
  동일 deadline 선별5PASS를 broad PASS나 원인 해소로 재분류하지 않는다. 원본과
  진단·초기 runner/권한/사용 한도 실패도 보존한다. 전체 pytest는 최종 source에서
  정확히1회 실행하며 결과는 후속 추가한다.
- P2 Pinned/_walk는 재작성하지 않았다. 이번 제품2파일+기존 publish test1파일+
  note/Log 총5파일, 전체 후보21개다. 내부plan/scratch/RAW/JUnit/JSON/runner 제외,
  기존 P3와 POSIX mount/비협력 writer 및 Windows local-volume 지원 경계를 남긴다.
  상세 설계·실패·검증은 [RT-12(a) note](./rt12a-cleanup.md)의 별칭 후속 절에 있다.
  staging/commit/push/PR/reviewer/subagent 없이 기존 독립 재리뷰를 기다린다.

- **경로 별칭 최종 직접 감사:** 최종 source bare 전체1회 exit0,
  ========== 9905 passed, 937 skipped, 1 warning in 490.64s (0:08:10) ===========. MySQL911·media22·collection4
  skip이며 실제 MySQL mandatory gate/원격CI는 미실행이다. 코드·테스트 hash를 유지했다.
  Windows focused156PASS/native POSIX122PASS·Windows전용6SKIP와 broad470PASS/3FAIL·
  선별진단5PASS를 분리한다. 앞선 실패를 PASS/해소로 소급하지 않는다. boundary/
  Contract/workflow30·nested900/gate 불변/diff 및 증거100개·index·후보21개/이번5개를
  최종 감사한다. 소유 임시자원/lease만 정리하고 RAW/JUnit/JSON/runner는 제외 보존한다.
  IN_PROGRESS · Refs #299 (RT-12(a)), 미커밋·미스테이징으로 독립 후속 재리뷰 대기다.


### 2026-10-23 RT-12(a) 최종 독립 재리뷰 판정 후속 기록

**IN_PROGRESS · Refs #299 (RT-12(a)) · PR·merge SHA pending**

- 아래는 전달받은 독립 reviewer의 최종 판정과 직접 검증을 기록한 것이다. 이번
  문서 갱신에서 테스트를 재실행하거나 구현자의 자체 승인으로 대체하지 않았다.
  검증한 NTFS·Linux 범위에서 경로 별칭 P1 해소, 기존 metadata 격리 P2 해소 상태
  유지 및 새로운 P1/P2 발견 없음으로 판정받았다. 커밋·중간 PR 준비는 가능하나,
  실제 병합은 현재 revision의 원격 CI와 필요한 mandatory gate 성공 전까지 보류한다.

**경로 별칭 P1 최종 판정**

- Windows 일반 경로와 `\\?\` extended-length 경로의 양방향 혼용,
  실제 NTFS 8.3 subset 8 passed/skip 0, native Linux /tmp·//tmp 혼용에서 publish 보호를 확인했다.
- 동일·하위 cleanup 구성은 거부하고 상위 구성은 publish와 겹치는 보호 가지를
  제외한다. 미존재 suffix 및 구성 후 link 교체 경계도 검증했다. canonicalization
  성공·실패를 각각 100회 실행한 뒤 process handle은 201 → 201 → 201이었다.

**기존 P2 해소 상태 유지**

- metadata 오류의 첫·중간·마지막 위치 및 nested 격리, 동시 소실의 집계 제외,
  iterator close, bounded empty 확인과 privacy 검증을 유지했다. iterator 진행 중
  오류의 직접 결과는 (count=2, bytes=6, failed=1)이며 형제 처리를 계속했다.

**Reviewer 직접 검증과 구현자 보존 증거의 구분**

| 구분 | 검증·보존 결과 |
| --- | --- |
| reviewer 직접 | Windows focused 156 passed |
| reviewer 직접 | 실제 NTFS 8.3 subset 8 passed, skip 0 |
| reviewer 직접 | native Linux focused 122 passed / Windows 전용 6 skipped |
| reviewer 직접 | API·Worker lifecycle·upload staging → publish → DB 호출 순서 144 passed |
| reviewer 직접 | boundary·Contract fixture·workflow·whitespace 검사 통과 |
| 구현자 보존 | alias RED: Windows 16 failed / 46 passed |
| 구현자 보존 | alias RED: POSIX 16 failed / 38 passed |
| 구현자 보존 | 이전 source 복사본의 8.3 검출력 RED: 10 failed / 30 passed |
| 구현자 보존 | 넓은 회귀 470 passed / 3 failed와 이후 선별 5 passed는 별도 실행으로 유지 |
| 구현자 보존 | 전체 pytest 9,905 passed / 937 skipped / warning 1 / 490.64초 |
| 구현자 보존 | JUnit 10,842 cases, failure/error 0 |

- 과거 실패 3건은 비차단 P3로 유지하며 이후 PASS로 소급 변경하지 않는다.
  test_nested_partial_tree_young_child_and_unknown_root_entries의 WinError 5,
  test_receive_abort_sends_no_status_and_never_registers[disconnect]의 disconnect보다
  idle 제한 선행, test_failed_sink_with_unread_stderr_does_not_deadlock_interpreter의
  stderr sink 9초 timeout 각각의 정확한 근본 원인은 미확정이다. 최종 reviewer의
  판정이나 이후 선별·전체 PASS가 당시 원인 해소의 증거를 대신하지 않는다.

**미확인·잔여 위험**

- 실제 UNC 공유 동등성, 다른 Windows filesystem과 case-sensitive namespace,
  POSIX bind mount·mount namespace는 미확인이다. POSIX API·Worker 전체 process/
  signal 경로도 검증하지 않았다. 검증한 NTFS·native Linux 범위 밖으로 판정을
  확대하지 않는다.
- 비협력 writer, 무제한 filesystem I/O에 따른 join 지연, 예상 밖 비-OSError 후
  주기 종료, 활성 producer에 따른 root 전체 보존, wall-clock 변동 위험은 남는다.

**범위·상태**

- PR 후보는 정확히 21개다. 내부 실행 계획·scratch·RAW·JUnit·JSON·runner·이전
  source 복사본·임시 자료는 PR에서 제외한다. 제품·테스트·인계 문서는 이번에
  수정하지 않았고 기존 이력과 Implementation Log의 CRLF bytes를 보존했다.
- 실제 MySQL mandatory gate와 원격 CI는 미실행이다. 보존된 MySQL 911 skip은
  gate 성공이 아니다. 현재 revision의 필요한 gate와 원격 CI 성공 전 병합 보류를
  유지한다. PR·merge SHA는 pending이며 상태는 IN_PROGRESS · Refs #299 (RT-12(a))다.
- 이번 기록에서는 staging·commit·push·PR 생성과 테스트 재실행을 하지 않았다.


### 2026-10-23 PR #390 원격 CI correlation 실패 후속

**IN_PROGRESS · Refs #299 (RT-12(a)) · PR #390 · merge SHA pending**

- 시작 branch/HEAD `09e9fbd83854ce54208dfcc71821d278f48313cf`가 원격 PR과 일치하고
  worktree/index clean, 기존 PR 후보21개였다. remote run39850214180/job120074040208
  failure(2FAIL/10791PASS/33SKIP/1warning·1422.41초), boundary39850214256 success,
  MySQL execution gate skipped를 직접 읽고 원본을 보존했다. flaky로 재분류하지 않는다.
- 실제 격리 MySQL8.4.7/native Linux에서 최초 API trace node를 같은 line431 KeyError로
  RED1FAIL(23.63초) 재현했다. event 이름/trace 존재 여부만 보존했다. startup cleanup6개는
  빈 Context로 trace 없음, request/view4개는 trace 있음이었다. 전체 stream에 trace를
  요구한 테스트 전제가 원인이다. remote migration child도 같은 node1FAIL/905PASS여서
  parent returncode 실패로 이어졌으며 독립 결함 둘로 단정하지 않는다.
- prefix assertion을 명시적 request.completed/view.completed 집합에만 적용했다.
  기존 수/trace 존재·상관·case 검증을 유지하고 field 존재로 거르는 우회는 없다.
  실제 API queue의 cleanup private context 비상속 회귀를 추가했다. 제품 코드는
  수정하지 않았다. 같은 MySQL node+새 회귀 GREEN2PASS(9.67초), 별도 child에서
  Context 격리 제거 negative control1FAIL(15.81초)을 분리 보존한다.
- Windows 실제 SHUTDOWN/private readonly mount2PASS(14.77초), 최초 잘못된 node
  선택 collection 오류도 보존했다. timeout/retry/sleep/skip/xfail/inventory/strict 정책은
  불변이다. 관련 회귀/전체 pytest·parent gate/strict 검사·자원 감사는 후속 추가한다.
- 이번 테스트2+문서2 총4파일, 기존PR21개+새 포함 기존추적 test_cases_view_mysql.py로
  합친 후보22개다. scratch/RAW/JUnit/JSON/runner/negative control/CA/이전 source·
  임시DB/media 제외, 기존 실패/P3와 이력을 유지한다. 상세 근거는 RT-12(a) note의
  PR390 후속 절에 있다. reviewer/subagent/commit/push/PR 수정 없이 독립 재리뷰한다.

- **PR390 최종 직접 검증:** native MySQL 최초 node+privacy2PASS, 관련73PASS
  (47.09초). Windows 관련293PASS/1FAIL(153.61초), 기존5초 process node 단독1FAIL도
  보존한다. 4초 stack 진단은 listener close 뒤 connect_ex였으나 두 timeout의 정확한
  원인은 확정하지 않는다. 전체는 진단 runner 설정을 포함해1회 exit1,
  2 failed, 10815 passed, 26 skipped, 1 warning in 2902.28s (0:48:22). JUnit 10843 cases/failure·error2개,
  실패명: test_actual_server_cleanup_failure_exit_and_listener_release, test_require_missing_dependency_fails_without_skip. 과거 실패를 이후 결과로 소급 변경하지 않는다.
- 전체 dependency guard 실패는 진단 plugin 상속/PYTHONPATH 교체 충돌의 runner
  오류였다. 별도1FAIL 재현→정상 guard1PASS, 저장소 정책/source는 불변이다.
  정상 runner 관련292PASS/3FAIL의 실패명은 test_composition_failure_outranks_stalled_handler_write, test_composition_failure_exits_within_five_seconds_after_ready_trigger, test_actual_server_cleanup_failure_exit_and_listener_release다.
  정확한 process 실패 원인은 미확정이며 flaky로 분류하지 않는다. 정상 옵션의
  전체 재실행은 하지 않았고 남은 실패·전체 PASS 미확인을 독립 재리뷰에 인계한다.
- 실제 parent migration gate 통과=True. fresh MySQL collected/selected
  911/911, phase{'passed': 2733}.
  전체 strict exit0·child strict exit0의 원본을
  보존한다. subset gate와 전체 결과를 합성하지 않는다. 원격 CI failure/gate skipped는
  그대로이고 재실행/PR 수정/commit/push/reviewer/subagent는 없다.
- 소유 MySQL8.4.7 UUID datadir·port 정리, pytest root12개·
  이번 생성 확인 lease2개 정리 및 schema/account/
  transaction/lock 감사는 새 scratch resources.json에 있다. boundary/Contract/
  workflow30·nested900·gate 불변/diff와 source/index hash·Log bytes를 최종 확인한다.
  기존PR21개/합친22개·이번4개, 제외자료 유지, 미커밋·미스테이징으로 독립 재리뷰한다.
  IN_PROGRESS · Refs #299 (RT-12(a)) · PR #390 · merge SHA pending이다.

---

## RT-13 — Docker / Compose local runtime

Status: IN_PROGRESS · Refs #300 (RT-13(a)) · Audit: C

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| pending (미생성) | RT-13(a) Dockerfile/Compose, local one-shot migration·smoke 및 승인 Baseline 반영 | pending |

### 구현 결과

Python 3.12/locked uv/ffmpeg single image, api/worker command 분리, numeric UID/GID 10001:10001, MySQL8.4 data/media 별도 named volumes, read-only env 파일 mount, 기존 stdin migration adapter와 success dependency, ready healthcheck, worker stop grace, B-O1 local rotation을 추가했다. 파일·실행 흐름·근거와 전체 Implementation Notes는 [RT-13(a) Notes](./rt13a-docker-compose.md)가 원문이다.

### Plan 대비 변경

이전 2 PR 예시의 local migration/smoke를 사용자 요청/#300 승인에 따라 (a)에 포함했다. (b)는 logical backup/restore 절차 완성과 실제 restore smoke, 필요시 검증 확장이다. RD-12f/h production 배포·post-deploy 및 EC2/ECR/SSM/registry/CloudWatch/production restart policy/RT-14는 제외다. Plan 문서는 다시 쓰지 않았다. RT-13 전체 DONE/Issue 종료가 아니다.

### 새 implementation detail

YAML JSON subset source/resolved policy validator와 mutation negative controls, stdin CLI adapter, multi-stage editable install(기존 migration 경로 보존), local driver, project 전용 opt-in smoke. smoke는 fake key/무작위 임시 password와 test-only blocking handler로 기존 lease/sweep/retry 경로를 검증하도록 작성했고 application image에 test probe를 넣지 않았다. api/worker/migrate는 root 실행/권한 완화에 의존하지 않는다.

### Owner 확인 포인트

승인된 M4 수치는 [Baseline §2.10](./provisional-baseline-v0.1.md#210-health--readiness--j)에 Evidence/근거/지표/Trigger와 반영했다. timeout=5s는 B-H3 ready3s에서 DERIVED, interval10s/retries3/start_period10s/grace30s 숫자는 CONSERVATIVE_DEFAULT이며 실측값이 아니다. 새 claim 중단+grace 내 정상 종료 시도이고 모든 handler 완료 보장 없음. 초과 kill 뒤 기존 lease→STALE→retry로 복구한다. RT-13 smoke와 이후 Real E2E에 따라 재조정 가능하다.

### Verification

직접 검사와 fresh reviewer 판정의 원문은 [RT-13(a) Notes Verification](./rt13a-docker-compose.md#verification--2026-10-27)이다. `.codex-scratch/rt13a/` 원본은 PR 제외다. 최초 fresh review P1없음/P2두 건(normalized null entrypoint, cleanup 실패 전파·기록)을 TDD로 수정해 deploy79 passed; 같은 reviewer도79개를 독립 실행하고 재리뷰에서 잔여 P1/P2 source defect 없음을 확인했다. 실제 MySQL8.4.7 전체는12683 passed/3 failed/26 skipped/xfail0; MySQL subset1044 passed/1 failed/skip0/xfail0, strict JSON/JUnit FAIL. reviewer는 전체/MySQL suite를 재실행하지 않았다. 기존 API process-safety2건의5초 timeout과 nested gate900초 timeout을 보존하며, API2건 단독 재실행도2 failed다. boundary/Contract104/workflow/diff/lock check PASS. Docker는 CLI를 찾지 못해 preflight FAIL, 생성 자원0이다. MySQL 정리 전 예상 schema 감사는 extra1로 FAIL했지만 finally SHUTDOWN·UUID datadir 삭제·Linux port closed와 후속 Windows listener0/소유 Python0을 확인했다. 미커밋 intermediate 후보 보존 가능이며 merge-ready/전체·mandatory·Docker acceptance/RT-13 DONE을 주장하지 않는다.

### Docker 설치 후 재개 — 2026-10-27

기존 17개 후보 SHA-256/branch/HEAD/index empty를 먼저 확인했다. Engine29.9.2/Compose5.6.1/Desktop Linux에서 실제 smoke9 stages와 cleanup PASS를 확인했다. 최초 NTFS `.pytest_cache` xattr 접근 거부 build 실패와 image 미생성 cleanup 실패는 보존하고, 기존 ACL을 변경하지 않았다. ignored 파일을 제외한 2,188개 파일의 bytes/hash가 일치하는 전용 Linux 사본에서 clean build와 config, migrate exit7 negative control, 새 volumes의 MySQL healthy→migrate0→API ready, 별도 api/worker·동일 image, HTTP command/view, upload 동일 path/bytes, SIGKILL→STALE→attempt2, inspect secret/UID/GID/non-tmpfs/health/grace/log rotation, recreate DB/media persistence를 검증했다. worktree/commit/push/PR/Issue 변경은 없다. `docker-snapshot.json/jsonl`은 ignored 새 scratch에만 보존한다. 직접 NTFS context build 성공이나 provider 성공 분석/restore/production 검증으로 확대하지 않는다.

이전 실패의 Windows 원래5초 재현은 후보/develop 모두1pass/1fail이며 source import I/O stack을 관측했다. 관련 source/test179개는 develop과 바이트 동일하다. Linux API는 양쪽2pass, 같은 DockerMySQL8.4.13의 nested는 양쪽 원래900초 timeout이었다. 실제 DDL 대기 stack/서버 누적비용을 보존하며 과거 timeout의 단일 원인으로 단정하지 않는다.

최종은 실제MySQL8.4.7/Linux, 전용 pytest datadir, durability기본1/1, timeout/sleep불변으로 전체1회/strictCLI1회를 실행했다. 전체 **12678passed/3failed/33skipped/xfail0**, mandatoryMySQL **1045/1045passed·3135phases·skip/xfail0**, strict **PASS**다. 기존 API2건/nested부모는 이번 전체에서PASS, nested자식1027passed·656.449초다. deploy79pass다. 새Search3fail은 저자가검증사본의Git문맥/venv PATH를누락한환경구성오류로대조확인했다. develop원환경3fail, PATH만복구1pass/2fail, 실제읽기전용Git문맥만복구2pass/1fail, 둘다복구후후보/develop각3pass였다. source/test수정없고단독PASS로전체3fail을바꾸지않았다. 전체/strict재실행없음·원격CI시간여유미확정이다. 최초실패6개hash도유지한다. 상세원문과후속정리/리뷰는Notes를따른다.

최종exactcleanup에서containers/volumes0·기본networks3ID불변,소유process/datadir/workspace/Windowslistener부재를확인했다. 진단DockerDB의schema2/transaction1감사FAIL은물리정리PASS와구분보존한다. 같은freshreviewer가최신17개hash/diff/실행·matrix·정리증거를읽기전용대조하여새P1/P2없음·추가수정없음으로판정했다. 이번후속에서테스트/strict/Docker를재실행하지않았다. 미커밋intermediate후보보존가능이며공식전체3FAIL을GREEN/무조건merge-ready로표현하지않는다는판정이다. 실행code/tests불변·문서4개만후속보완했고commit/push/PR/Issue변경없음이다.

### 남은 위험

app image base/apt는 digest snapshot pin이 아니므로 bit-for-bit 재현성을 주장하지 않는다. 공식전체3FAIL은환경대조PASS와별개로남기며원격CI성공·시간여유는미확인이다. 기존 grace는 모든 handler 완료를 보장하지 않는다. RT-13 전체 IN_PROGRESS/Refs #300과 (b) backup/restore 경계를 유지한다.

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

Status: IN_PROGRESS · Issue: #301 · Audit: C

2026-10-30 RT-15(a) 로컬 구현. Ruff·mypy와 required quality job을 추가했다.
상세 구현·선택 근거·예외·검증은 [RT-15(a) Implementation Notes](./rt15a-runtime-quality.md).
PR/merge SHA는 pending이다. RT-15(b) import 경계 확장과 (c) secret scan은 미착수이며
RT-15 전체 완료나 원격 CI 성공을 뜻하지 않는다. 아래 기존 빈 항목은 초기 이력으로 보존한다.

로컬 검증: Ruff·mypy 양 플랫폼 각 87 files 0 error, focused 747 passed,
boundary/Contract/actionlint/lock PASS. Fresh read-only review에서 quality-only NumPy 누락을
찾아 실제 의존성으로 수정했고 같은 reviewer가 격리 환경의 PASS를 직접 재확인했다.
추가 quality/CI 회귀 55 passed. 미해결 blocking 지적 없음. 선택 OCR·Search annotation
타입 경계와 미실행 원격 MySQL/Docker 결과는 Notes의 잔여 위험으로 남긴다.

2026-10-30 PR #483 regression 후속: PR head `1e38d560`에서 deploy Worker 등록 node의
실패를 로컬 재현했다. RT-15(a)의 새 `RecordingSettings` nominal 검사는 타입 목적의
불필요한 동작 변경으로 판단해 검증된 factory 경계의 타입 전용 cast로 대체했다.
기존 세 필수값·registry 검증과 성공 fixture는 보존했다. 해당 node RED→GREEN,
누락 설정 3건 포함 deploy/Worker/Recording 설정 회귀 361 passed, quality 양 플랫폼
87 files 0 error, boundary/Contract/diff 검사 PASS. Fresh read-only delta reviewer도 이전
HEAD의 실패를 독립 재현하고 관련 65 tests 및 quality 양 플랫폼을 직접 통과 확인했다.
blocking 지적 없음. PR 변경/commit/push/merge는 하지 않는다. 상세 및 이번 delta 파일은
위 Notes의 PR #483 후속 절이다.

### 2026-10-30 — RT-15(b) import 경계 로컬 구현

**RT-15 전체 IN_PROGRESS · Refs #301 (RT-15(b)) · Related #287 · PR/merge SHA pending**

위 RT-15(a) 로컬/pending 문장은 당시 실행 이력으로 보존한다. 이번 시작 시 GitHub에서
PR #483 merged와 merge SHA `e3fec617dc75b2cf21141a110bd8e81e816970b8`를 직접 확인했다.
branch `codex/rt15b-import-boundaries`, HEAD/로컬 origin/develop/원격 ls-remote의 develop이
모두 그 SHA이며 시작 tree/index clean, ahead/behind `0/0`이었다. Issue #301 본문과
전체 댓글(0개)을 직접 읽었다. 선행 PR의 원격 CI는 이번 미커밋 diff 검증과 구분한다.

- **구현 결과:** 기존 `check_boundaries.py`의 기본/`--only=boundaries` 진입점에 Python
  AST 검사를 더했다. common의 jobs/usage/db/config/logging/storage는 domain 7개를,
  domain 경로는 `daesingo.api`·`daesingo.worker`를 import하지 않는다. Architecture의
  domain 7개와 실제 경로/namespace(`eval/`, TypeScript `apps/web/` 포함)를
  ownership §6 표와 함께 정합화했다. 현재 scoped Python은 common35/domain143파일,
  web0파일이다. 두 방향 현재 위반은 0건이며 제품 코드를 이동·수정하지 않았다.
- **Plan 대비 변경:** 없음. 기존 문자열/Contract/스캔 제외 경로를 보존한 검사 추가다.
  기존 workflow가 같은 CLI를 실행하고 새 pytest는 기존 regression으로 수집되므로
  workflow/pyproject/lock/inventory/strict/timeout/skip/xfail 변경이 없다.
- **새 implementation detail:** AST Import/ImportFrom의 원래 namespace 및 alias child를
  검사한다. 상대 import는 containing package와 level로 계산하며 `__init__.py`도
  같은 원칙이다. 파싱 실패를 PASS로 넘기지 않는다. `readout.api`와 Runtime `api`,
  비슷한 prefix 및 문자열·주석을 구분한다. 새 예외나 주석 suppression은 없다.
- **Contract / Decision / Baseline 영향:** 모두 없음. public surface·타 Owner 책임 변경
  없음. Runtime/Ops Owner 김준영의 deferred review와 각 domain Owner별 통지 초안을
  Notes에 작성했다. 외부 댓글·메시지 발송이나 Owner acceptance는 하지 않았다.
- **직접 Verification:** 새 fixture 변경 전 **236 failed / 22 passed**(금지 import235와
  파싱 실패1 누락), 수정 후 **258 passed**(48.72초). 변경 전 상대 import 한 사례에서
  실제 CLI exit0/PASS를 별도 재현했다. 허용15/기존 문자열 거부7도 보존했다.
  전체 boundary 및 contracts-only PASS, Contract 구조62/JSON26/의미104 PASS,
  RT-15(a) Runtime Ruff PASS·mypy Linux/win32 각87파일 오류0, quality/CI 회귀
  **55 passed**(13.25초). 최종 boundary-only 및 `git diff --check` PASS, index 비어 있음.
- **추가 범위 밖 진단:** checker까지 임의로 확대한 Ruff에서 기존 Contract 코드의
  `E741` 변수 `l` 1건이 나왔다. HEAD 원본 stdin 검사로 동일 진단을 재현했다.
  Runtime quality gate 대상이 아니며 범위 밖 lint 정리는 하지 않았다. 새 테스트
  파일의 단독 Ruff는 PASS다. 이 실패를 필수 gate 성공으로 바꾸어 기록하지 않는다.
- **Fresh review:** 구현 이력을 상속하지 않은 read-only reviewer가 SoT/diff를 검토했다.
  reviewer 직접 boundary PASS·새 fixture258PASS(48.42초), 독립 CLI 12사례 기대 일치,
  diff check PASS; actionable 지적 없음. 최초 reviewer 실행은 basetemp 부모 디렉터리
  부재로 setup258ERROR였고, 부모 생성 후 새 basetemp로 성공했다. 제품 결함이나
  작성자 RED와 혼동하지 않는다. 같은 reviewer의 최종 문서 delta도 actionable 지적
  없음. 새 파일 수 재집계/diff check와 보존 로그 열람을 이전 suite 직접 실행과 구분했다.
- **남은 한계:** 동적 import·간접 re-export·부모 star 노출 이름·alias 속성 접근·import
  hook/sys.path 변경은 전이 분석하지 않는다. TypeScript import 해석은 AST 보장 밖이다.
  기존 문자열 검사는 주석/문자열에도 적용되는 원래 동작이다. 전체 local pytest·MySQL·
  Docker build 및 이번 diff의 원격 CI는 미실행이며, 향후 push 뒤 boundary/quality/
  regression/mysql/required test 성공이 최종 조건이다. RT-15(b)의 로컬 구현·검증과
  RT-15 전체 완료를 구분한다. **(c) secret scan은 후속**, #301은 종료하지 않는다.

전체 변경 파일·명령·RED/GREEN·review·통지 초안·정리 기록은
[RT-15(b) Implementation Notes](./rt15b-import-boundaries.md)에 있다. 새 worktree,
checkout 전환, staging/commit/push/PR/외부 댓글/merge, AWS/provider/배포,
RT14_EXECUTION_ENABLED 변경은 없다. scratch/로그/credential은 PR에서 제외한다.

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

## 2026-10-15 RT-08(a) 두 번째 독립 재리뷰 후속 조사

- 상태는 `IN_PROGRESS`, 연결은 `Refs #295 (RT-08(a))`, PR 번호·merge SHA는 `pending`이다. 기존 GREEN 이력은 보존한다. 이후 독립 재리뷰에서 composition stalled-write 5초 timeout과 startup KeyboardInterrupt 코드 0이 다시 보고되었으므로 기존 GREEN을 이번 수정의 검증으로 대체 사용하지 않는다.
- 검증 주체: 독립 재리뷰의 재현 횟수·결과는 사용자 제공 증거이며, 아래 직접 관측·RED/GREEN은 현재 implementer가 별도로 실행한다. `receiving-code-review` → `systematic-debugging` → TDD 순서로 진행했다.
- P1 직접 관측: `.codex-scratch/rt08a-second-review-20261015/timed-8.{json,phases,stack}`에서 stdout `write_entered`, stderr 공백의 5초 timeout을 재현했다. 2초 stack은 consumer의 실제 sink `write()` → `Event.wait()`와 main의 `ApiEvents.close()` → `Thread.join(timeout=1)`이다. child 기준 import 완료 1.741796초, close 진입 1.745496초, 반환 2.749820초, 예외 전파 2.750438초, atexit marker 2.751222초를 기록했다. parent Popen 생성 2.039605초와 communicate 약 4.999108초를 별도 측정했다. 두 clock의 원점은 다르며 이 숫자를 직접 빼서 interpreter startup/최종 종료 시간을 확정하지 않는다. 이 재현에서는 close가 반환했고 atexit에도 도달했으므로 무기한 logging shutdown 교착의 증거로 해석하지 않는다. 확인한 불필요한 sink 의존은 확정된 composition 실패에 정상 종료용 1초 drain을 추가하는 경로이다. 독립 재리뷰 실행 자체의 정확한 시간 분해는 확보하지 못했다.
- P1 선택지 검토(제품 수정 전): (a) 5초 테스트 또는 CI 정책 확대는 실패 전파의 불필요한 대기를 남기므로 선택하지 않는다. (b) composition 진단 자체 삭제는 정상 sink의 진단 기회까지 없애므로 선택하지 않는다. (c) API 소유 event queue는 닫되 **확정된 composition 실패에서만 drain을 기다리지 않는 방식**을 선택한다. 정상 lifespan/CLI cleanup의 1초 drain·correlation·fatal handoff는 그대로 둔다. 이 실패 경로의 진단은 유실될 수 있지만 startup 코드 1보다 우선하지 않는다. daemon/join만으로 shutdown 교착을 해결했다고 주장하지 않으며, 기존 API handler의 shutdown-lock 분리와 unbuffered 기본 출력 경계는 유지한다. logging 전역 registry·외부 handler·`os._exit()`는 사용하지 않는다.
- P2 직접 RED: `p2-red.{txt,xml,exit}`에서 실제 bootstrap/composition KeyboardInterrupt 각각 기대 1/실제 0으로 2 FAIL, serving interrupt 기대 0으로 1 PASS를 확인했다. 원인은 startup과 uvicorn 실행을 하나의 `except KeyboardInterrupt`가 성공으로 처리하는 것이다. 실제 API engine의 부분 생성 보상, 전체 composition disposal, signal 및 외부 logger handler 복원을 함께 검사하는 subprocess 회귀를 추가했다. 서버 호출에 진입했는지를 분리한 최소 수정 뒤 `p2-green` 3 PASS를 확인했다.
- 최초 Worker `recovered_at`, 최초 nested 900초 timeout, 수시간 subprocess 지연의 **정확한 근본 원인은 계속 미확정**이다. 이번 P1 시간 관측을 그 사건들의 원인으로 소급하지 않는다. 900초 nested gate, workflow 20분, 필수 evidence inventory, Contract·Accepted Decision·Baseline 의미를 변경하지 않는다.

### 이번 수정의 직접 RED → GREEN

| 대상 | 수정 전 RED | 최소 수정 후 직접 결과 |
| --- | --- | --- |
| P1 composition + 실제 stalled write | `p1-red.{txt,xml,exit}` 1 FAIL: 5초 timeout, stdout `write_entered`, stderr 공백. 실제 write 진입을 Event handshake로 보장했으며 release는 주지 않았다. 진단 관측 `timed-8`도 같은 signature의 timeout이다. | `p1-green` 1 PASS. `p1-repeat.{json,txt,exit}` 같은 5초 제한의 단독 12/12 PASS. composition 실패에서만 `events.close(drain=False)`; 정상 close의 1초 drain은 유지. |
| P2 startup / serving KeyboardInterrupt 구분 | `p2-red` bootstrap·composition 기대 1/실제 0의 2 FAIL, server 기대 0의 1 PASS | `p2-green` 3 PASS. 서버 호출 진입 전 KeyboardInterrupt는 1, 호출 중 KeyboardInterrupt는 기존 0. 실제 부분 생성 engine 보상·전체 disposal·signals·외부 handler 보존·stderr 비노출을 함께 확인. |

- 기존 `run_child` 5초 제한은 바꾸지 않았다. 테스트를 제외하거나 기존 assertion을 제거하지 않았고, P1 실제 sink 진입 보장과 P2 새 subprocess 3개를 추가했다. 수정 전 순서 관측의 첫 실행은 기본 Windows 임시 폴더 접근 거부로 22 PASS/19 fixture ERROR였으므로 GREEN으로 사용하지 않았다. 새 workspace basetemp의 기존 41개 관측 순서는 41 PASS였다. 이것과 별개로 수정 후 기존 41개 + 신규 3개의 **전체 44개 순서**가 44 PASS(60.81초)이다.
- 실행 코드 고정 후 `targeted-final` 93 PASS(89.42초), `api-common-final` 3933 PASS / MySQL 377 deselected(339.76초)이다. targeted의 실제 MySQL 8.4.7 health는 5 tests / 필수 6 identities / 15 phases, skip·xfail·failure 0이다. 제품·테스트·설정 22개의 고정 hash와 각 실행 stdout·JUnit·JSON·전원 요청 복원 timing을 `.codex-scratch/rt08a-second-review-20261015/`에 보존했다. MySQL 전체 gate와 전체 pytest 결과는 아직 대기 중이며 이 단계의 통과를 미리 기록하지 않는다.

### 첫 전체 재검증의 추가 실패와 별도 정리 helper 수정

- 위 대기 기록 이후 `mysql-final`은 실제 MySQL 596 PASS / MySQL 대상 skip·xfail·failure 0, JSON/JUnit gate PASS였다. MySQL 외 선택 의존성 collection skip 4개를 MySQL skip으로 계산하지 않는다. nested child는 591 PASS / 668.539초, 누락 mutation 3066건(API 42건) 모두 거부했다. 그러나 `full-final`은 **6510 PASS / 1 FAIL / 기존 optional 26 SKIP**, 1021.67초였다. 신규 실패 node는 `tests/api/test_health_mysql.py::test_ready_when_actual_mysql_server_is_shutdown`이고 `/health/ready` 503 검사는 통과했으나 `owned_mysql()` 정리의 단일 `connect_ex()!=0` assertion이 실패했다. 전체 JSON/JUnit gate가 이를 거부하는 것도 직접 확인했다. 이 실패를 GREEN으로 기록하지 않으며 `first-full-failure-hashes.json`으로 원본 6개 artifact를 보존했다.
- 원인 조사: 진단 plugin의 같은 health 5개 순서 15회는 모두 PASS였다(`owned-repeats`, 각 `owned-order-*-tcp.json`). 이 반복에서 실패가 자연 재현되지 않았다. 최초 실패 port·local/peer 주소·그 순간 Linux listener/PID는 원본에 없어 그 사건의 정확한 연결 원인을 복원할 수 없다. 종료 시 observer에는 MainThread만 있었고 API event thread 잔여는 없었다. P1/P2 제품 수정이 이 cleanup TCP 검사로 이어지는 직접 data flow는 없으며, 상대 실행 시간 변화의 영향까지 배제했다는 의미는 아니다.
- 별도 **확정된 검사 결함**: 실제 Windows socket을 listener 없이 자기 주소에 bind/connect하면 local=peer, `connect_ex()==0`으로 연결된다. 기존 1회 TCP 성공은 서버 잔존의 충분한 증거가 아니다. 실제 native socket으로 동일한 유효 source-port 후보를 강제한 회귀에서 기존 검사를 그대로 추출한 helper가 `owned MySQL port remains open` assertion RED였다(`port-red-confirmed`: 1 FAIL/1 PASS). 최초 test double의 미바인딩 `getsockname()` WinError10022는 관측 코드 오류로 별도 보존했고 RED 근거로 사용하지 않는다. 새 회귀는 connect 결과를 mock하지 않으며 MySQL acceptance를 대체하지 않는다.
- 최소 수정: `tests/api/owned_mysql.py`의 정리 probe가 source port를 명시적으로 선택하고, destination과 같으면 첫 후보를 reserve한 채 다른 source를 선택한다. **1초 socket 제한과 열린 listener 거부 assertion을 유지**하고 polling·timeout 증가·조건 완화 없이 self-connect 가능성만 제거했다. `tests/api/test_owned_mysql.py`에서 닫힌 port의 source 충돌 및 실제 listener 거부 2 PASS(`port-green`)를 확인했다. 이것은 확인된 test helper 결함의 RED→GREEN이며, 정보가 없는 최초 전체 실패의 정확한 원인을 소급 확정하는 주장이 아니다. 최초 Worker·nested·수시간 지연 3건의 미확정 구분도 유지한다.
- 제품 API source의 두 finding 수정은 유지한다. 테스트 helper 변경 후에는 새 source 고정본(v2)과 별도 `*-clean` 이름으로 검증 순서를 다시 실행한다. 이전 source hash·실패 보고서·GREEN 기록은 덮어쓰지 않는다. 전체 pytest 실패 0을 아직 달성했다고 판정하지 않는다.

### v2 고정본 최종 직접 검증 및 재리뷰 인계

검증 주체는 현재 implementer다. `verification-v2-results.json`의 순차 controller는 각 단계 전 고정 hash를 검사하고 실패 시 다음 단계로 넘어가지 않는다. 변경 source·테스트·설정 **23개**, 전체 검증 tree **445개**를 고정한 뒤 아래를 직접 실행했다. 이전 GREEN 및 첫 `full-final` 실패와 별개인 새 결과다.

| 검증 | v2 직접 실행 결과 |
| --- | --- |
| composition stalled-write 단독 | 동일 5초 제한, 실제 write 진입·release 없음, **12/12 PASS** (`p1-repeat-v2`) |
| process safety 전체 순서 | 기존 41개 + startup 구분 3개, **44 PASS**, 39.95초 |
| RT-08(a) targeted | 기존 90개 + startup 3개 + native TCP 검사 2개, **95 PASS**, 58.34초 |
| API/common·structured logging | **3935 PASS**, MySQL 377 deselected, 211.40초 |
| 실제 MySQL health | MySQL 8.4.7, 5 tests / 필수 6 identities / 15 phases, skip·xfail·failure 0 |
| 실제 MySQL 전체 acceptance | **596 PASS**, MySQL skip·xfail·failure 0, strict JSON/JUnit gate PASS, 906.89초. 별도 optional collection skip 4개는 MySQL 대상이 아니다. |
| 전체 pytest | **6513 PASS / 기존 optional 26 SKIP / failure·error 0**, 1205.34초. 이전 정상 실행과 skip identity 26개가 동일하다. |
| 전체 실행의 MySQL JSON/JUnit | 596 collected = selected, 1788 phases, skip·xfail·failure 0, strict gate PASS |
| 전체 실행 안의 nested child | **591 PASS**, 368.665초, JSON/JUnit PASS, skip·xfail·failure 0. 별도 MySQL acceptance의 child는 591 PASS / 366.440초. 900초 제한 유지. |
| evidence 누락 거부 | 각 nested parameter mutation **3066건(API 42건)** 모두 거부. 최종 전체·nested 실제 보고서에 API 6 identities × 10 layers = **각 60건** 누락도 모두 거부. 필수 inventory 유지. |
| boundary / Contract fixture | 경계 위반 0 / 문서 62·JSON 26·의미 fixture 104 검사 PASS |
| workflow / diff | actionlint·YAML 정책·bash -n·ShellCheck, 5 workflows / 5 run steps PASS (pyflakes 미실행). `git diff --check`의 Log EOF 빈 줄 1건 정리 후 PASS. 제품·테스트 추가 변경 없음. |

- 자원: 전체 pytest session 종료 직전 Python thread는 MainThread뿐이며 API logging/readiness thread 잔여는 없었다. 당시 API handler 1개는 정상 프로세스 logging 소유로 남아 있었고, interpreter 자체가 코드 0으로 종료했다. API가 global/제3자 handler를 임의 제거·종료하지 않았다. 종료 후 Windows 관련 Python process 0, 테스트 Windows listener 0, Linux의 실제 소유 MySQL PID·보조 서버·listener·보조 디렉터리 0을 별도로 확인했다. DB 정리 전 다른 connection 0, 정리 후 테스트 schema·계정 0이며 정확한 port 13342·datadir를 확인한 해당 서버만 SHUTDOWN했다. OS의 다른 서비스·계정은 변경하지 않았다.
- 정리 evidence 한계: SHUTDOWN 후 확인 시 `/dev/shm/rt08a-second-review-20261015`가 이미 소멸해 server/init log 복사는 실패했다(`cleanup-wsl` exit 1). 경로 소멸의 원인은 확인하지 못했다. 이를 숨기지 않고, 별도 `cleanup-wsl-final`에서 실제 PID·listener·경로 잔여 0을 확인해 exit 0으로 기록했다. stdout·JUnit·MySQL JSON·RED/GREEN·원본 실패 자료는 Windows workspace에 그대로 보존했다. Sandbox socket code 10013은 permission denial이므로 port 부재 증거로 쓰지 않았으며 native Windows listener와 Linux PID/ss 검사를 기준으로 삼았다.
- 불변: 보호된 기존 미추적 **1069개 파일의 path 집합·SHA 전부 동일**, 이전 조사 artifact **408개** 및 이번 첫 전체 실패 원본 **6개** SHA 동일, source 23개·검증 tree 445개 고정 hash 동일. `feature/runtime-api-skeleton-health` / HEAD `505e6ad2c95617569faad1b12a45fa48d3e41919`, index 변경 없음. 전체 변경 파일 **28개**와 전체 diff 및 이전 재리뷰 대비 code/test delta를 새 evidence 디렉터리에 제공한다. staging·commit·push·PR 생성은 하지 않았다.
- Plan 대비·새 implementation detail: 범위는 RT-08(a) 유지다. 확정된 composition 실패의 진단만 drain을 기다리지 않으며, 정상 종료 drain·correlation·queue saturation·sink 예외·thread 시작 실패·fatal handoff 정책은 유지한다. CLI는 startup KeyboardInterrupt 1과 server invocation KeyboardInterrupt 0을 구분하고, cleanup 실패·의도적 SystemExit·기타 BaseException의 기존 API 코드 1 정책은 유지한다. 추가 변경은 native TCP source/destination 충돌을 피하는 테스트 정리 helper와 실제 listener 거부 회귀다. HTTP status·envelope·Contract·Accepted Decision·Baseline 의미·Case/Search 의무 및 공개 surface는 변경하지 않았다.
- Owner 확인·남은 위험: terminal 진단 유실을 허용하는 fail-fast 경계, startup/server interrupt 경계, TCP 정리 검사의 실제 listener 거부를 검토할 수 있다. **최초 Worker recovered_at, 최초 nested 900초, 수시간 subprocess 지연의 정확한 근본 원인은 계속 미확정**이고, 이번 첫 전체 cleanup 실패의 실제 연결 원인도 당시 주소 자료가 없어 미확정이다. 확인된 native self-connect 검사 결함의 수정과 새 GREEN을 그 사건들의 원인 확정으로 소급하지 않는다.
- CI 정책: 이번 Windows 전체 실행은 **20분 05초**로 20분을 넘었다. Linux 원격 job의 20분 준수는 이번 로컬 결과로 확인할 수 없다. 선택지는 (1) 현재 20분 유지 후 실제 Linux CI에서 확인, (2) 초과가 확인되면 수집·필수 evidence를 유지하며 fixture/migration 비용을 별도 측정·개선, (3) 정책 변경이 필요한 경우 Owner에게 근거·CI 비용·timeout 영향을 제시한 별도 결정이다. 이번에는 workflow 20분·nested 900초·inventory를 변경하지 않았다.
- 인계: 수정본·전체 검증·원본 실패·불확실성을 갖춘 **독립 재리뷰 가능한 로컬 상태**다. 병합 승인·Owner 수락·원격 CI 통과를 판정하지 않는다. RT-08은 **IN_PROGRESS**, 연결 **Refs #295 (RT-08(a))**, PR 번호·merge SHA **pending**을 유지한다. RT-08(b)의 POST /cases·GET /view, (c)의 command/enqueue, (d)의 중단, RT-11의 sources/frames/assets, 인증·CORS·TLS는 후속 범위다.

## 2026-10-15 RT-08(a) 잔여 5초 timeout 단계 관측 후속 조사

- 독립 리뷰 입력(사용자 제공): stalled-write 단독 **11/12 PASS, 1 timeout**, 실패 child stdout·stderr 모두 공백. 후속 9회·단계 관측 3회·process 44개·targeted 95개 PASS도 함께 전달됐다. 이 수치는 아래 implementer 직접 실행과 구분하며, 이전 GREEN 이력을 삭제하거나 최초 실패가 해소됐다고 소급하지 않는다.
- 절차·범위: `systematic-debugging`으로 제품 변경 전에 source/hash·process 기준 상태를 보존하고 진단용 재현을 실행했다. **이번 조사에서 제품 코드 변경 없음**. `tests/api/process_probe.py`와 기존 stalled-write 회귀의 child source 공유·trigger 검사 1개만 보강했다. 기존 전체 child 5초 검사와 실제 handler write 무한 정지·release 없음·코드 1·stderr 공백·PRIVATE 비노출 assertion을 유지한다. 기존 process 44개/targeted 95개에 새 검사 1개가 추가돼 수집 기준은 **45개/96개**다.
- 관측 경계: child의 첫 실행 marker, 필수 imports 완료, logger/config 완료, ready, composition 직전, 실제 `write_entered`, SystemExit(1) 포착 직후, atexit 직전·callback을 기록한다. 각 marker와 parent spawn/수신/trigger/exit/timeout에 wall clock(ns)·Windows `QueryUnbiasedInterruptTime`(100ns)·PID를 저장한다. 첫 marker에도 최소 stdlib/clock 준비가 필요하므로 Python bootstrap·그 준비 이전의 정지 stack을 관측했다고 주장하지 않는다. Windows venv launcher PID와 실제 interpreter PID가 다름도 별도로 기록했다.
- 새 경계: parent는 child ready를 별도 **setup/import watchdog 5초** 안에 기다린 뒤 stdin GO를 보낸다. 제품 종료 deadline은 **GO write 직전부터 5초**이며, child ack나 관측 수신으로 재설정하지 않는다. setup/import 실패와 `product_exit_5s`를 구분한다. 정상 marker는 stdout 진단 채널, faulthandler stack은 별도 파일에 저장해 stderr 비노출 검사를 유지한다. deadline 후 DUMP/process 관측은 이미 확정된 FAIL을 PASS로 바꾸지 않는다. 실패한 새 child의 launcher/interpreter tree와 parent pipe reader를 정리하며 다른 process/logger를 종료하지 않는다. Windows 외에는 unbiased clock을 null로 표시하고 실제 wall clock을 유지한다.
- 직접 관측(implementer): 초기 진단 total **12/12**, ready/trigger **20/20**, 보강된 새 회귀 trigger **20/20**, 별도로 유지한 원래 total 검사 **12/12 PASS**. 관측된 trigger→exit 최대 **0.1740451초**, write→exit 최대 **0.1710454초**였다. 초기 spawn 시작→첫 marker 최대 **4.3247166초**, imports 구간 최대 **2.2968275초**는 서로 다른 실행에서의 최대값이므로 합산하지 않는다. 초기 실행 wall/active 차이 최대 약 **0.000002초**, 관측 시점까지 Kernel-Power 506/507 이벤트 0이었다. 이는 해당 실행들의 사실이며, 독립 리뷰의 빈 stdout timeout이 launch/import/scheduling 때문이었다는 확정 증거가 아니다.
- 관측 검사 음성 대조군: 테스트 child에만 실제 표준 StreamHandler를 사용해 실제 write에서 handler lock을 잡고 정지시킨 경우 **trigger 이후 5초 거부**를 확인했다. 당시 main `logging.shutdown → handler.acquire`, consumer 실제 write/Event.wait의 faulthandler stack과 process snapshot을 보존했다. 별도 import 전 Event.wait는 **setup watchdog 5초 거부**와 해당 대기 stack을 남겼다. 두 대조군은 관측 경계의 검출 검증이며, 현재 제품에서 자연 발생한 RED 또는 제품 수정 GREEN으로 포장하지 않는다.
- 다른 process: 시작 전부터 별도 독립 리뷰 pytest launcher/interpreter **PID 22152/22184**가 존재했다(시작 17:18:35). 명령·parent·CPU·thread 대기 상태를 읽기 전용으로 보존했다. 이들의 존재·대기와 이번 timeout 사이의 인과관계는 확인하지 못했으며 임의 종료하지 않았다. 현재 조사에서 실행한 child 및 서버와 소유 경계를 구분한다.
- 검증 중 추가 실패: 첫 고정본 process **45 PASS** 뒤 targeted에서 **95 PASS/1 FAIL**. node `tests/api/test_process_safety.py::test_actual_server_cleanup_failure_exit_and_listener_release`가 기존 total 5초 timeout(stdout·stderr 공백)이었다. 원본 stdout·JUnit·MySQL JSON·exit·timing·resource snapshot 6개 SHA를 별도 보존하고 검증을 중단해 조사했다. 종료 직전 parent Python thread는 MainThread뿐이었으나, 그 사실로 실패 child의 5초 시점 상태를 추정하지 않는다.
- 추가 실패의 같은 순서 관측: source나 5초 제한을 바꾸지 않고 외부 진단 plugin으로 **tests/api 전체 원래 순서 96 PASS**. 해당 실제 Uvicorn child의 imports→composition→bind/main loop→cleanup→CLI 반환→SystemExit/atexit, 코드 1·stdout/stderr 공백·signal/listener 검사를 관측했다. 최초 실패에는 당시 marker·stack이 없고 자연 재현하지 못했으므로 **그 추가 timeout의 정확한 원인도 미확정**이다. 단순 재실행 PASS를 해결로 판정하지 않는다.
- 판정: 사용자 제공 최초 1/12 timeout은 write 진입 전/후를 결정할 원본 phase/stack이 없어 **원인 미확정·병합 보류**를 유지한다. 최초 Worker recovered_at, 최초 nested 900초, 수시간 subprocess 지연, 이전 최초 TCP cleanup 사건의 정확한 근본 원인도 계속 미확정이다. timeout 증가·sleep 우회·검사 제외·필수 inventory 완화·제품 추측 수정은 하지 않았다. 후속 고정 소스 검증 결과와 정리는 아래에 추가한다.

### 후속 고정본 직접 검증·정리 결과

검증 주체는 현재 implementer다. 제품·테스트·설정 source **24개**, 전체 검증 tree **446개**를 hash로 고정해 각 실행 전 확인했다(Log 후속 기록 제외). 첫 targeted 실패와 그 원인 미확정 판정을 보존한 상태에서 같은 소스의 아래 최종 검증을 순차 실행했다. 별도 명시한 순서 관측 실행 외에는 phase 주입 plugin 없이 원래 pytest 검사를 실행했으며, 종료 시점 resource observer는 상태를 읽기만 한다.

| 직접 실행 | 결과 |
| --- | --- |
| 새 trigger 이후 stalled-write / 기존 total 검사 | **20/20 / 12/12 PASS**. 앞선 진단용 marker total 12회·trigger 20회와 별도 자료로 보존. |
| process-safety | **45 PASS**, 51.30초. 기존 44개 모두 유지 + 새 trigger 검사 1개. |
| RT-08(a) targeted 최종 | **96 PASS**, 63.78초. 같은 순서 진단 관측 실행도 96 PASS이나 최초 targeted 95 PASS/1 FAIL 원본은 별도 보존. |
| API/common·structured logging | **3936 PASS**, MySQL 377 deselected, 164.25초. |
| 실제 MySQL health | MySQL **8.4.7**, **5 tests / 6 필수 identities / 15 phases**, skip·xfail·failure 0. |
| 실제 MySQL 전체 acceptance | **596 PASS**, 784.79초, MySQL skip·xfail·failure 0, strict JSON/JUnit gate PASS. 별도 optional collection skip 4개는 MySQL 대상이 아니다. |
| 전체 pytest | **6514 PASS / 기존 optional 26 SKIP / failure·error 0**, stdout 기준 984.71초. optional skip identity 26개가 이전 검증과 동일하다. |
| 전체 MySQL / nested gate | **596 collected=selected / 1788 phases** 및 nested **591 collected=selected**, 모두 skip·xfail·failure 0, 두 JSON/JUnit PASS. 전체 안의 child **313.638초**, 별도 MySQL 실행의 child **384.419초**. |
| evidence 누락 거부 | 각 nested의 parameter mutation **3066건(API 42건)** 거부. 최종 전체·nested 실제 보고서에서 API 6 identities × 10 layers = **각 60건** 누락 거부. |
| boundary / Contract | 경계 위반 **0**, 문서 **62**·JSON **26**·의미 fixture **104** PASS. |
| workflow / diff | actionlint·YAML 정책·bash -n·ShellCheck **5 workflows / 5 run steps PASS**. pyflakes 미실행. `git diff --check` 및 추가 파일 whitespace 검사 PASS. |

- 자원 정리: 정확한 localhost **13343**, datadir `/dev/shm/rt08a-phase-boundary-20261015/data/`, 실제 Linux PID **418**을 대조했다. 서버·init log를 SHUTDOWN **전에** 보존한 뒤 다른 connection **0**, 남은 테스트 schema·계정 **0**을 확인하고 해당 서버만 종료했다. Linux PID·서버·listener·datadir·보조 MySQL/readonly 경로 **0**, 이번 실행 소유 Windows Python process·테스트 listener **0**을 독립 확인했다. unrelated MySQL 서비스와 별도 작업 process는 변경하지 않았다.
- thread/handler 관측: 최종 pytest 종료 직전 Python thread는 **MainThread뿐**이었다. API handler 1개는 당시 정상 logging owner 아래 존재했고 interpreter가 코드 0으로 종료했다. 이를 종료 전 handler 0이라고 표현하지 않는다. 종료 후 이번 실행의 process가 없어 그 소유 logging/readiness/probe thread·handler도 남지 않았다. global/제3자 handler를 임의 제거·종료하지 않았다.
- 별도 process 잔여: 시작 전부터 존재한 독립 리뷰 pytest **PID 22152/22184 두 개는 최종에도 그대로 존재**했고 CPU 수치는 기준 snapshot과 같았다. 이들이 현재 조사에서 새로 누출됐다는 증거는 없으며, 강제 종료하지 않았다. 따라서 이번 실행 소유 자원 0과 **호스트 전체 Python process 0은 구분**한다. 이들의 Python stack과 최초 timeout 간 인과관계는 확인하지 못했다.
- clock·관측 한계: 전체 조사 구간의 Kernel-Power **42/107/506/507**, Power-Troubleshooter **1** 이벤트 관측은 **0**이었다. OS scheduler ETW trace는 수집하지 않았으므로 process scheduling 지연을 배제하거나 원인으로 확정할 수 없다. 기존 total 검사는 원래의 `Popen` 반환 뒤 `communicate(timeout=5)` 의미를 유지하며 spawn 호출 시간은 따로 기록한다. 새 검사는 ready 수신 뒤 GO write 직전부터 제품 종료 5초를 측정한다. phase/관측 thread가 실행 timing에 영향을 줄 수 있어 관측 PASS를 무관측 실패의 원인 증명으로 쓰지 않는다.
- 불변·인계: 보호된 기존 미추적 **1069개 파일의 path·SHA 동일**, 이전 재리뷰 top-level artifact **365개**, 그 이전 evidence **408개**, 이전 첫 전체 실패 **6개**, 이번 첫 targeted 실패 **6개**의 SHA를 확인했다. 현재 조사에서 기존 파일 변경은 **테스트·Log 2개**, 추가는 **test helper 1개**뿐이며 모든 제품 source는 조사 시작 때와 같다. 전체 변경 **29개 파일**과 diff·manifest·직접 실행/원본 실패 자료는 `.codex-scratch/rt08a-phase-boundary-20261015/`에 제공한다. branch/HEAD/index는 유지하고 staging·commit·push·PR 생성은 하지 않았다.
- Owner 확인·남은 위험: trigger 이후 5초와 기존 total 경계를 모두 유지한 진단 설계, 실제 stalled write 및 interpreter 종료 검증, 첫 marker 이전의 blind window, 별도 리뷰 process 보존 범위를 확인할 수 있다. **최초 1/12 timeout과 이번 첫 targeted Uvicorn timeout의 정지 위치·근본 원인은 여전히 미확정이며 병합 보류**다. 이전 Worker recovered_at·nested 900초·수시간 지연·TCP cleanup 사건의 정확한 원인도 새 GREEN으로 소급 확정하지 않는다. 재리뷰 자료는 준비됐지만 병합 가능 판정은 하지 않는다.
- 정책·범위: 새 implementation detail은 테스트용 phase clock·ready/trigger·stack/process 관측과 소유 child 정리뿐이다. **제품 수정, Contract·Accepted Decision·Baseline 의미·HTTP status/envelope·Case/Search 의무 변경 없음**. 이번 Windows 전체는 약 **16분 25초**지만 원격 Linux CI의 20분 준수는 미검증이다. nested **900초**, workflow **20분**, 필수 inventory를 유지한다. **RT-08 IN_PROGRESS / Refs #295 (RT-08(a)) / PR·merge SHA pending** 유지. RT-08(b)의 cases/view, (c)의 command/enqueue, (d)의 중단, RT-11의 sources/frames/assets, 인증·CORS·TLS는 후속 범위다.

## 2026-10-16 RT-08(a) 독립 재리뷰 최종 후속 기록

- 독립 재리뷰 판정: **PASS / 현재 재현 가능한 병합 차단 문제 없음**. 사용자가 전달한 독립 재리뷰 결과를 반영해 앞선 병합 보류 이후의 판정을 추가한다. 기존 실패·조사·GREEN 이력과 원본 증거는 유지한다.
- 검증 주체·증거 구분: 아래 직접 통과는 독립 재리뷰에서 직접 실행한 결과이며, 전체 pytest·MySQL 전체·nested 결과는 보존 증거 대조다. **이번 Log 갱신 작업에서는 테스트를 재실행하지 않았다.**

| 증거 구분 | 검증 | 결과 |
| --- | --- | --- |
| 독립 재리뷰 직접 실행 | ready/trigger 이후 stalled-write | **20/20 PASS** |
| 독립 재리뷰 직접 실행 | 기존 total-process | **12/12 PASS** |
| 독립 재리뷰 직접 실행 | RT-08(a) targeted | **96 PASS** |
| 독립 재리뷰 직접 실행 | process-safety | **45 PASS** |
| 독립 재리뷰 직접 실행 | 실제 MySQL health | **5 tests · 6 identities · 15 phases PASS** |
| 보존 증거 대조 | 전체 pytest | **6514 PASS / 기존 optional 26 SKIP / 실패 0** |
| 보존 증거 대조 | 실제 MySQL 전체 / nested | **596 / 591 PASS**, MySQL skip·xfail·failure 0 |

- 비차단 위험: 최초 **1/12 timeout**과 추가 **Uvicorn timeout**은 정확한 정지 위치·근본 원인이 계속 **미확정**이다. 해결됐다고 단정하지 않고 비차단 위험으로 유지한다. 과거 실패 원본과 앞선 원인 미확정 기록도 그대로 보존한다.
- 관측·CI 한계: **첫 marker 이전 blind window**, phase/관측 thread의 **timing 영향 가능성**, **원격 CI 20분 실행시간 미확인**을 유지한다. 현재 재리뷰 PASS로 이 한계나 과거 사건의 원인을 소급 확정하지 않는다.
- 정책·상태: **timeout·gate·필수 inventory 정책 변경 없음**. 제품 종료 5초, nested 900초, workflow 20분을 유지한다. RT-08 상태는 **IN_PROGRESS**, 연결은 **Refs #295 (RT-08(a))**, PR 번호와 merge SHA는 각각 **pending**이다.
- 이번 수정 범위는 이 Log의 후속 기록 추가뿐이다. Log 외 파일 수정, 테스트 재실행, staging·commit·push·PR 생성은 하지 않았다.

## #370 — durable timestamp ordering (2026-10-17)

- **Status:** `IN_PROGRESS` — 별도 `codex/runtime-durable-timestamp-ordering` branch, base `ae928822`, 커밋/PR/merge SHA pending. 최종 PR 연결은 **Closes #370 / Related #295**이며 #295를 닫지 않는다.
- **Owner 확인:** [Runtime/Contract/Baseline 승인 댓글](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/370#issuecomment-6227886934). terminal B안과 heartbeat/lease B안으로 앞선 승인 대기를 해소했다. 이 기록은 예전 RT-07/RT-08 시각 장애의 미확정 범위를 소급 확정하지 않는다.
- **구현:** `jobs/timestamps.py`의 공통 SQL causal 하한을 T1·STALE·QUEUED cancel에 적용. heartbeat/lease는 DB 시각과 기존 값의 하한을 보존한다. 최종 T1 UPDATE가 현재 row를 재평가한다. validator·app clock·schema·status/owner fence·caller transaction·pinned receipt·COMMIT 불명 복구 정책은 바꾸지 않는다.
- **Contract/Baseline 영향:** 승인된 ended_at causal 의미, renewal non-regression, 역행 중 duration 0 근처·lease/retry 지연·STALE 지표 의미를 명시했다. 기존 시간 간격/상한 숫자는 유지한다. #370을 authority로 기록하며 새 ADR을 만들지 않았다.
- **검증:** 기존 진단7+정식7 RED 확인 뒤 최소 수정. 정식7 GREEN, 최종 timestamp35+claim/heartbeat 관련 MySQL82 PASS. 관련 unit/privacy/lifecycle/gate3982 PASS와 추가 metadata 누락105 PASS. 전체 MySQL acceptance 및 실제 evidence mutation의 최종 결과/실행 증거는 [구현 보고서](./reviews/durable-timestamp-ordering-implementation-2026-10-17.md)가 추적한다.
- **운영 follow-up:** 저장소 snapshot만으로 EC2의 현재 time source/chrony 상태는 확인하지 못했다. runbook에 읽기 전용 확인 절차를 남겼고 실제 AWS 조회/변경은 하지 않았다. host/SSM/IAM/CloudWatch 변경 필요 여부는 별도 Runtime/Ops Issue에서 결정한다. 제품 수정의 선행조건이 아니다.
- **재리뷰:** 별도 읽기 전용 코드 리뷰에서 actionable code/test-gate finding 없음. 사용자 독립 재리뷰 대체가 아니며, 커밋·푸시·PR 없이 diff/evidence를 남긴다. 기존 RT-08(b)의 미커밋 파일은 건드리지 않는다.
- **최종 직접 실행:** 전체 MySQL **626 tests / 1878 phases PASS**, skip0/xfail0/failure0, 독립 strict CLI gate PASS. 실제 evidence mutation **3521/3521 거부**, timestamp35 parameter의 **455/455 거부**. outer acceptance 1 PASS(954.45초). 첫 nested900초 제한 실패, 이후 Windows fixture 환경변수 누락의 직접 RED/GREEN, 최종 clean 실행을 [보고서](./reviews/durable-timestamp-ordering-implementation-2026-10-17.md)에서 구분한다. 최초 timeout 원인 미확정 및 원격 CI 시간 한계를 유지하며 정책 시간을 늘리지 않았다. 디스크 약15 GiB 여유 확인 뒤 전체 pytest는 중복 범위/독립 리뷰 목적을 고려해 추가 실행하지 않기로 판단했다. 전체 pytest/원격 CI PASS로 확대하지 않는다.

### #370 독립 재리뷰 최종 후속 기록 (2026-10-17)

- **독립 재리뷰 판정:** **PASS / 남은 병합 차단 문제 없음**. 구현에 참여하지 않은 fresh reviewer가 미커밋 변경 전체를 읽기 전용으로 검토했고, **Owner 승인 terminal B안·heartbeat/lease B안 준수**를 확인했다. 기존 진단·실패·구현·검증 이력은 보존하며 이 후속 판정으로 과거 사건의 미확정 원인을 소급 확정하지 않는다.
- **검증 주체·증거 구분:** fresh reviewer의 읽기 전용 검토와 재리뷰 부모 검토자의 직접 재실행을 구분한다. 아래 구현 단계 결과는 보존 증거 대조이며, 재리뷰 직접 실행 결과로 대체하거나 합산하지 않는다. **이번 Log 갱신에서는 테스트를 재실행하지 않았다.**

| 증거 구분 | 검증 | 결과 |
| --- | --- | --- |
| 구현 단계 보존 증거 대조 | RED → GREEN / targeted·unit | 진단7 + 정식7 RED, 이후 정식7 GREEN. timestamp35 포함 MySQL82 PASS, 관련 unit3982 PASS, 추가 metadata105 PASS |
| 구현 단계 보존 증거 대조 | 전체 MySQL acceptance / evidence mutation | **626 tests / 1878 phases PASS**, skip0/xfail0/failure0. mutation **3521/3521 거부**, timestamp **455 포함** |
| 독립 재리뷰 직접 실행 | 실제 MySQL | **219 passed — timestamp35 포함**, skip0/xfail0 |
| 독립 재리뷰 직접 실행 | unit/gate subset | **520 passed**. 전체 unit 실행 결과로 확대하지 않음 |
| 독립 재리뷰 직접 실행 | Windows fixture | **1 passed** |
| 독립 재리뷰 직접 실행 | 현재 gate로 보존된 전체 보고서 재검증 | mutation **3521/3521 거부 — timestamp455 포함**. 전체 MySQL626을 이번 리뷰에서 다시 실행한 결과는 아님 |
| 독립 재리뷰 직접 실행 | timestamp evidence 누락 거부 | metadata **105개**, family **7개** 누락 모두 거부 |

- **전체 pytest·CI 한계:** 이번 #370 구현·독립 재리뷰에서는 **전체 pytest를 재실행하지 않았다**. 원격 Linux CI 결과와 기존 workflow **20분 제한 준수는 미확인**이며, **merge 전 기존 CI 통과가 필수**다. 로컬 targeted·gate 통과를 전체 pytest 또는 원격 CI PASS로 확대하지 않는다. timeout·필수 inventory·skip/xfail 정책은 완화하지 않는다.
- **잔여 위험:** 기존 invalid row의 backfill은 수행하지 않았으며 별도 데이터 판단 대상으로 남긴다. 실제 경과시간 왜곡, clock rollback 중 lease/retry 지연, EC2 clock discipline 미확인을 유지한다. **AWS 변경 없음**. 운영 clock discipline 확인은 별도 Runtime/Ops follow-up이며 제품 수정의 선행조건이 아니다.
- **비차단 P3 후속 후보 — 이번 변경에 구현하지 않음:** (1) Baseline의 약82초 예시에 정상 clock 가정을 명시. (2) clock-step + COMMIT 불명 rollback·소진 조합 acceptance 보강. 두 항목은 후속 후보로만 기록한다.
- **PR 연결·상태:** **Closes #370 / Related #295**, **#295는 닫지 않음**. PR 번호·merge SHA는 각각 **pending**이며 merge 전 상태는 `IN_PROGRESS`를 유지한다.
- **이번 갱신 범위:** 이 Log의 #370 후속 기록 추가만 수행했다. 제품 코드·테스트·Baseline 및 다른 문서는 수정하지 않았고, 테스트 재실행·staging·commit·push·PR 생성은 하지 않았다. 확인은 `git diff --check`와 `git status --short`로 한정한다.

### #370 PR 연결·develop 병합 후속 (2026-10-17)

- **현재 연결·상태:** [PR #371](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/371), **Closes #370 / Related #295**, **#295는 닫지 않음**. merge SHA는 **pending**, merge 전 상태는 `IN_PROGRESS`다.
- **이력 구분:** 위 구현·검증·독립 재리뷰 기록 전체와 당시 PR pending·20분 CI 제한 미확인 기록은 역사적 snapshot으로 보존한다. 이후 Issue #368 / PR #372에서 workflow 제한이 **30분**으로 변경됐으며 해당 원격 CI 결과는 아래 #368 기록에서 구분한다. #368의 CI PASS를 #370 PR #371의 CI PASS로 대체하지 않으며, **#370 merge 전 해당 PR의 CI 통과가 필수**다. 기존 검증 수치·잔여 위험·비차단 P3 후보는 유지한다.

## 2026-10-17 Issue #368 — CI 실행시간·timeout 후속

- **구현 당시 연결·상태:** `Refs #368`. 로컬 미커밋, PR/merge SHA `pending`. Issue 전체 완료나 RT-08(b) 구현 완료를 뜻하지 않는다. 최신 `origin/develop` `ae9288226901b7e551595400dcb53c453c01d38e` 기반 별도 worktree/브랜치에서 작업했다.
- **기록 위치:** Plan §12.5와 이 Log의 사용 규칙에 따라 실제 설정 선택·판단 변경 근거·검증·남은 위험을 기록한다. 기존 RT-08 기록은 당시 사실로 보존하며 Plan을 다시 쓰지 않는다.

| 확인한 근거 | 판단에 미치는 영향 |
| --- | --- |
| [PR #352 이전 CI 답변](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/352#issuecomment-6215216824): Ubuntu test job 14분 33초, 전체 pytest 13분 30초 성공을 근거로 20분 유지. 이후 20분 근접·실제 timeout이면 재검토한다고 기록 | 당시 성공 기록은 유지하되 현재 실행시간의 보장으로 일반화하지 않는다 |
| [멘토 리뷰 4번](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/352#pullrequestreview-5520973090): PR CI 약 30분 허용, 협업 지장이 생기면 실패 영향·변경 관련성·실행시간을 기준으로 분리 | [Issue #368](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/368)의 CI 후속과 이번 사용자 지시에 따라 우선 job timeout을 현실화한다 |
| [PR #371 run 39009492969 / test job 117328737070](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39009492969/job/117328737070): GitHub API에서 job/전체 pytest `cancelled`, 후속 MySQL execution gate `skipped` 확인. annotation은 `The job has exceeded the maximum execution time of 20m0s` | 원격 CI의 20분 제한 초과가 실제로 확인되어 이전 유지 판단을 변경한다 |

- **원격 시각(UTC):** 2026-10-17 job 시작 `06:19:45`, 전체 pytest 시작 `06:21:08`, pytest 취소 `06:39:58`, job 완료 `06:40:01`(정리 포함). 시각 차이 직접 계산은 pytest 실행 18분 50초, job 전체 20분 16초다. job timeout은 준비 단계까지 포함하므로 pytest에 20분 전부가 주어지는 것은 아니다. 취소된 실행의 정상 완료 예상시간은 확인할 수 없다.
- **구현 결과·Plan 대비 변경:** `.github/workflows/python-tests.yml`의 `jobs.test.timeout-minutes`만 `20 → 30`으로 조정한다. Runtime Task/Contract/Accepted Decision/Provisional Baseline 변경은 없다. CI 운영 상한 조정이며 테스트 계층화·workflow 분리는 이번 범위 밖이다.
- **유지한 검증 경계:** 전체 pytest inventory·실행 명령, skip/xfail 정책, nested child 900초 제한, MySQL 필수 시나리오·JSON/JUnit strict gate를 그대로 유지한다. test/src/scripts/conftest 및 다른 workflow는 변경하지 않는다.
- **검증:** 변경 전후 actionlint 1.7.12로 해당 workflow 구문·GitHub Actions expression/구조 정적 검사 PASS(ShellCheck·pyflakes 미실행). 기준 workflow와의 byte 비교로 timeout 한 줄 외 동일함을 확인하고, `git diff --check` PASS. 루트 README 사실 절에 이번 timeout 변경으로 어긋난 내용은 없어 수정하지 않는다. 전체 pytest·실제 MySQL·원격 CI는 이번 설정 수정에서 실행하지 않았다.
- **Owner 확인 포인트·남은 위험:** 30분 안에 전체 pytest와 후속 MySQL gate가 완료되는지는 다음 원격 실행에서 확인해야 한다. timeout 증가는 실행시간 증가의 근본 원인이나 기존 nested/개별 subprocess의 미확정 timeout 원인을 해결·규명하지 않는다. 최대 대기시간·runner 점유 상한은 10분 늘며 실제 비용 증가는 이번에 측정하지 않았다. 이후에도 timeout 또는 협업 지연이 관찰되면 단계별 시간·fixture/migration 비용을 근거로 다시 판단하고, 계층화·분리는 별도 변경으로 검토한다.

### PR #372 원격 CI 후속 확인

- **현재 연결·상태:** [PR #372](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/372), `Refs #368`, merge SHA `pending`(조회 시 open·미병합). 실행 대상 head는 `f76322a0ee7baef8ba6d8b82dd85178605fea419`다.
- **이력 구분:** 위 검증·위험 기록은 구현 당시의 snapshot이다. 당시 30분 내 완료는 미확인이었고, 이번 PR #372 원격 실행에서 전체 필수 단계의 PASS를 처음 확인했다. 과거 PR #352 성공과 PR #371 취소, 구현 당시 미확인 사실을 소급 변경하지 않는다.

| 원격 검증 | 직접 확인한 결과 |
| --- | --- |
| [boundary-check / run 39016580841 / job 117349827773](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39016580841/job/117349827773) | PASS · 9초 |
| [python-tests / run 39016580855 / test job 117349827893](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39016580855/job/117349827893) | PASS · 17분 40초(2026-10-17 `08:13:58 → 08:31:38 UTC`) |
| 같은 job의 전체 pytest 단계 | PASS · 16분 33초(`08:15:00 → 08:31:33 UTC`) |
| 같은 job의 MySQL execution gate | PASS · 전체 pytest 이후 필수 JSON/JUnit gate 완료 |

- **판정·비차단 위험:** 이번 원격 실행에서 30분 timeout 안에 전체 필수 단계가 완료되어, 제한으로 검증이 중단되는 상황을 피하려는 조정 목적은 달성했다. 단일 실행 결과가 향후 30분 내 완료를 보장하지는 않으며, 실행시간 변동·기존 개별 timeout 원인의 미확정·runner 점유 상한 증가를 비차단 위험으로 유지한다. 협업 지연이나 timeout이 다시 관찰되면 실행시간 근거로 계층화·workflow 분리를 별도 검토한다. 이번 후속은 테스트·gate·timeout 설정을 변경하지 않는다.
- **이번 후속 검증·범위:** GitHub API 원본을 읽어 결과와 시각을 대조했으며 소요시간은 그 차이로 계산했다. Issue #368의 이 Log 기록만 갱신하고 `git diff --check` PASS를 확인했다. 테스트 재실행·staging·commit·push·PR 생성은 하지 않았다.

### #368 PR #372 병합 후속 (2026-10-17)

- **현재 연결·상태:** [PR #372](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/372), `Refs #368`, merge SHA **`a5d61cc7d1fc9d02c229deca87bd0c2a7aec2ed1`**. 현재 merge 대상 `origin/develop` 및 `MERGE_HEAD`가 이 SHA이며, 로컬 Git commit 제목 `Merge pull request #372`와 대조했다.
- **이력·설정 보존:** 앞선 구현 당시 pending 및 PR 원격 CI 조회 당시 open·merge SHA pending 기록은 당시 snapshot으로 보존한다. PR #372의 원격 검증 수치·비차단 위험과 #368 기록 전체를 유지한다. develop에서 병합된 `.github/workflows/python-tests.yml`의 **`timeout-minutes: 30`**도 유지하며, 이번 충돌 해결에서는 workflow·제품 코드·테스트를 수정하지 않았다.

## 2026-10-17 RT-08(b) — timestamp ordering 수정 이후 develop 통합

- **상태·연결:** **IN_PROGRESS · Refs #295 (RT-08(b)) · PR pending · merge SHA pending**. 현재 Codex managed worktree의 `codex/rt08b-clock-integration`에서 미커밋·미스테이징 상태로 검토한다.
- **확인한 기준:** fetch한 `origin/develop`은 **`4f383c9412593fb8e415598dfa7481fb447a1b2c`**다. #368의 [PR #372](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/372) merge SHA **`a5d61cc7d1fc9d02c229deca87bd0c2a7aec2ed1`**와 #370의 [PR #371](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/371) merge SHA **`4f383c9412593fb8e415598dfa7481fb447a1b2c`**를 포함한다. GitHub 조회에서 두 PR의 merged 상태와 SHA, #370 CLOSED, #295 open을 확인했다. 위 pending·20분·실패 기록은 당시 이력으로 보존한다.
- **원본 보존 감사:** source-only `C:/ktc4-chonnam-2`의 HEAD `d436de08f8e16a11a99a322ce7fd1de36e80c05a`, branch `feature/runtime-api-cases-view`, status, staged/unstaged binary patch, 변경·신규 1065개 파일과 보존 증거 154개의 SHA-256을 현재 worktree의 ignored 감사 폴더에 기록했다. 당시 13개 납품 파일 모두 최종 고정 manifest와 일치한다. 원본 index와 파일은 쓰지 않는다.
- **결합 경계:** API 제품·테스트·문서 13개만 재적용했다. 공통 gate·unit inventory·nested migration gate의 충돌은 timestamp35 및 API21의 합집합으로 병합했다. timestamp의 추가 skip/xfail/failure/JUnit 누락 차단과 nested `timeout=900`을 보존한다. #370의 causal terminal clamp, heartbeat·lease 비감소, status/owner fence 및 COMMIT 불명 복구 코드와 #372 workflow `timeout-minutes: 30`은 기준 그대로다.
- **transaction·오류 의미:** POST 생성 ACK 후 별도 공개 get_view transaction, GET의 Case share lock 선행 및 같은 Connection의 비잠금 Runtime read를 유지한다. CaseNotFound만 404, precommit DB 실패 503, COMMIT 불명·생성 후 read 실패·관련 없는 SQL 오류 500의 원본 의미를 유지한다.
- **과거 사건과 수정의 관계:** #370은 RT-08(b) 없이도 재현된 공통 durable timestamp ordering 결함과 승인된 정책의 수정이다. 과거 Worker timestamp 실패·개별 timeout·nested timeout의 원본 결과를 성공으로 바꾸지 않는다. 과거 사건의 실제 timestamp 쌍이나 정지 위치가 확보되지 않은 경우 #370과 같은 직접 원인이라고 확정하지 않는다. 이후 clock 진단 helper·RAW·archive·datadir는 제품에 재적용하지 않았다.
- **추가 보존 증거:** 원본 `.codex-scratch/rt08b-final-once-20261016/verification-report.md`의 마지막 고정 소스 실행은 6798 passed / 26 skipped / 1 failed였다. nested는 611 passed / 1 failed이며 redelivery periodic의 timestamp validation 실패로 부모 gate가 거부됐다. 해당 실행에서는 900초 timeout이 없었고 mutation 단계에 도달하지 못했다. 이 별도 과거 실행도 앞선 두 전체 실패·timeout과 구분해 보존하며 이번 검증 결과로 합산하지 않는다.
- **이번 직접 검증:** 재적용 경계 검토 후 targeted 및 실제 MySQL 검증을 수행하며, targeted 통과 뒤 전체 pytest는 정확히 한 번만 실행한다. 실행 결과는 아래 후속 기록에 추가한다. 과거 보존 결과를 이번 직접 실행 결과로 대체하지 않는다.

### 통합본 직접 검증 진행 (2026-10-17)

- API 전체·timestamp acceptance·gate unit targeted는 **4327 passed / 실패·skip·xfail 0**이다(427.82초, runner wall 431.885초). MySQL은 **61개 / 183 phases PASS**이며 RT-08(b) **21개**, timestamp **35개**를 포함한다. 기존 의존성 deprecation warning 1개는 테스트 실패와 구분한다.
- 정적 검사는 boundary 위반 0, Contract fixture 문서62/JSON26/의미104 PASS다. workflow5개 actionlint 및 run step5개 YAML 정책/bash 구문/ShellCheck PASS, pyflakes 미설치 한계는 유지한다. 최초 로컬 helper의 trailing CR 종료 오류(exit127)는 원본을 보존하고 LF helper 재실행(exit0)과 구분했다. 제품 workflow는 수정하지 않았다.
- 실제 MySQL **8.4.7**, dedicated port13348, 현재 managed worktree 아래 private memory datadir를 사용한다. flush-at-commit1/sync-binlog1과 API/Worker UTC·READ COMMITTED·lock wait5초를 직접 확인했다. 원본/기존 DB를 시작하거나 원본 datadir를 사용하지 않는다.
- 읽기 전용 fresh 코드 리뷰에서 actionable finding 없음. 이는 실행 검증이나 사용자의 독립 재리뷰를 대체하지 않는다. 제품/API 테스트는 원본과 동일 해시이며 timestamp/fence/recovery·workflow 등 보호 파일9개는 기준 HEAD와 동일하다.
- nested 실제 보고서 gate targeted는 **1 passed / 613.59초**다. 그 child 실제 MySQL은 **647 tests / 1941 phases PASS**, skip0/xfail0, JUnit 470.494초다. strict JSON/JUnit CLI도 직접 PASS했다. 기존 실제 evidence mutation **3668/3668 거부**, API **147건**과 timestamp **455건**을 포함한다. 추가 실제 보고서 metadata 누락 **168건**, family 전체 계층 누락 **14건**도 거부됐다. 추가 감사 helper가 처음 JUnit 대조만 호출해 실패한 실행은 별도로 보존했고, 제품 CLI와 동일하게 inventory 검증과 JUnit 대조를 함께 호출하도록 helper만 고쳐 재실행했다. 제품 gate 변경은 없다.
- 두 targeted 실행 통과 후 전체 pytest 1회를 시작한다. 실행 당시 13개 파일 해시와 명령·시각을 별도로 고정하고 원본 결과를 보존한다. CI30분·nested900초·필수 inventory·skip/xfail 정책은 그대로다.

### 통합본 전체 1회·정리·보존 최종 확인 (2026-10-17)

- **전체 pytest 직접 결과:** 정확히 **1회**, **7297 passed / 26 skipped / 실패0 / warning1**, exit0. pytest **1407.92초(23분27초)**, runner wall **1413.918초**다. 26 skip은 선택형 의존성·로컬 미디어 조건이며 정책·선택을 바꾸지 않았다. 원격 Linux CI 실행 결과로 확대하지 않는다.
- **전체 실제 MySQL·strict gate:** 수집/선택 **652/652**, **1956 phases PASS**, MySQL skip0/xfail0. 전체 원본 JSON/JUnit에 strict CLI를 직접 실행해 PASS했다. 전체 안의 nested도 **647 tests / 1941 phases PASS**, evidence mutation **3668/3668 차단**이다. API21의 transaction·404/503/500 오류 의미와 timestamp35 및 heartbeat·sweep·cancel·T1 회귀가 통과했다. 앞선 targeted 결과와 합산하지 않는다.
- **소스 고정·검사:** 전체 실행 종료 시 시작 때 고정한 13개 파일 해시가 모두 동일함을 확인했다. 이 최종 결과 기록은 실행 후 문서에만 추가한다. 제품·테스트·gate·workflow는 실행본 그대로이며, `git diff --check`와 신규 4개 no-index whitespace 검사를 확인한다. branch `codex/rt08b-clock-integration`, HEAD `4f383c9412593fb8e415598dfa7481fb447a1b2c`, index 비어 있음. 커밋·푸시·PR 생성 없음.
- **자원 정리:** 정확한 전용 datadir/version/port를 재확인한 뒤 테스트 schema를 DROP하고 추가 test 계정0·다른 connection0을 확인한 후 SHUTDOWN했다. 소유 Linux mysqld·socket·fixture datadir·pid, Windows test Python·WSL launcher·port13348 listener 잔여0이다. private memory datadir와 현재 worktree의 빈 datadir 폴더를 정리했고 로그·직접 결과는 보존했다. 기존 Windows MySQL PID5844/7128 및 생성 시각은 그대로다. 원본 datadir나 다른 worktree는 정리하지 않았다.
- **원본 전후 불변:** HEAD/branch, status SHA, staged/unstaged patch SHA, tracked 변경 목록, untracked1056개 목록, 변경·신규1065개 파일 SHA 및 보존 증거154개 SHA가 전후 모두 일치한다. 원본 납품13개도 고정 manifest와 일치한다. source-only checkout을 삭제·정리하거나 파일·index를 수정하지 않았다. `.codex-scratch`의 모든 archive 바이트를 새로 해싱했다는 주장과는 구분한다.
- **재리뷰 인계·남은 위험:** 독립 재리뷰 가능한 **미커밋·미스테이징** 상태다. 전체/실제 MySQL/strict gate의 이번 PASS가 과거 Worker 실패·timeout의 직접 원인을 소급 확정하지 않는다. 원격 CI, 기존 invalid row backfill, clock step의 경과시간·lease/retry 지연, EC2 clock discipline, 생성 후500의 반영 불명 및 기존 후속 slice 범위는 유지한다. **IN_PROGRESS · Refs #295 (RT-08(b)) · PR/SHA pending**.
- **검토 자료·제외:** 현재 worktree의 ignored `.codex-scratch/rt08b-integration-20261017/`에 `integration-report.md`, `final-results.json`, `direct-result-hashes.json`, `full.*`, before/after 감사, source snapshot, mutation·정리·리뷰 근거를 보존한다. 이 폴더 및 `.pytest-*`, baseline negative JSON, clockdiag/RAW/archive/datadir, 외부 visualization/Temp, #370 임시 진단·PR draft/snapshot은 PR 납품에 포함하지 않는다. 실제 재적용 파일은 최초 감사의 13개뿐이다.

### 독립 리뷰 P2 — README HTTP surface 정합성 후속

- **지적·수정:** 독립 리뷰에서 확인된 README 140행의 health-only/Case route 후속 문구가 9·69행의 RT-08(b) 구현 설명 및 실제 route 등록과 불일치했다. 140행에 `GET /health/live`, `GET /health/ready`, `POST /cases`, `GET /cases/{case_id}/view`를 명시하고 후속 route를 command/media로 한정했다. 기존 health·오류 envelope·ready DB·metadata-only mount·MySQL gate 설명은 보존한다.
- **범위·계수:** 제품·테스트·Contract·Decision·Baseline·workflow 및 기존 납품 파일 목록은 변경하지 않는다. `README.md`는 수정 전 delivery manifest의 13개 파일에 이미 포함돼 있으므로, 이번 수정 후에도 고유 납품 파일은 **13개**다. 요청의 「README 추가로 14개」 전제와 실제 목록의 차이를 integration report/manifest에 명시한다. 수정 전 README·Log·report·manifest는 ignored `readme-p2/`에 보존한다.
- **수정 직후 계획·당시 판정:** 실제 등록 route와 README 9·69·140행, 보존 설명·파일 경계, `git diff --check`, conflict marker, boundary·Contract·workflow 정적 검사, 원본 checkout·보존 증거 불변을 확인할 계획이었다. 수정 직후에는 P2 수정본의 검증 결과와 최종 독립 재확인이 미확정 상태였다. 과거 전체 pytest·MySQL 결과를 이번 문서 수정 후 신규 실행 결과로 바꾸지 않는다.
- **상태:** **IN_PROGRESS · Refs #295 (RT-08(b)) · PR/SHA pending**. staging·커밋·푸시·PR 생성 없이 후속 검토한다.
- **이번 직접 검증 결과:** 실제 `create_app`에 등록된 schema의 route 집합이 README의 네 route와 일치함을 DB 연결 없이 확인했다. README 9·69행은 수정 전과 동일하고, 140행의 surface·후속 범위 두 문구만 변경됐으며 나머지 문구와 Log의 기존 이력은 보존됐다. 다른 납품11개 해시 동일, conflict marker0, `git diff --check` 통과. boundary 위반0·Contract 문서62/JSON26/의미104·workflow5개 actionlint 및 run step5개 YAML/bash/ShellCheck 검사가 통과했다. pyflakes 미실행 한계는 유지한다. 원본 HEAD/branch/status/patch/untracked 목록과 변경·신규1065개 및 증거154개 해시가 기존 감사와 동일하다.
- **증거·판정 구분:** 기존 실행 artifact30개와 과거 전체 pytest/MySQL 원본은 그대로 보존한다. 이번에는 문서·route 정합성과 정적 검사를 수행했으며 pytest·MySQL을 재실행하지 않았다. P2 수정 전 report/manifest 및 이번 검증 원본은 ignored `readme-p2/`에 남긴다. **이번 P2 수정본의 최종 독립 재확인은 대기 중**이다.

### README P2 후속 독립 재리뷰 결과

- **기록 근거:** 사용자가 전달한 fresh reviewer의 후속 독립 재리뷰 결과를 아래에 기록한다. 직전 항목의 독립 재확인 대기는 당시 상태이며, 이번 후속 reviewer 결과로 갱신한다. 이번 Log 갱신에서 테스트를 재실행한 결과로 해석하지 않는다.

| 순서 | 단계 | 결과와 근거 구분 |
| --- | --- | --- |
| 1 | 기존 구현 단계 | 보존된 직접 실행 결과는 API acceptance 21 passed, timestamp ordering 35 passed, 전체 pytest 1회 7,297 passed / 26 skipped / 실패 0, 실제 MySQL 652 tests / 1,956 phases passed 및 strict JSON/JUnit gate PASS다. 이번 기록 갱신에서 재실행하지 않았다. |
| 2 | 최초 독립 리뷰 P2 | README 140행의 health-only 및 Case route 후속 설명이 README 9·69행과 실제 Case 생성·조회 route에 모순됨을 지적했다. 이 P2와 당시 독립 재확인 대기 기록은 과거 이력으로 보존한다. |
| 3 | P2 문서 수정·검증 | README 140행에 실제 네 route를 반영하고 후속 HTTP route를 command/media로 한정했다. 기존 health·오류 envelope·ready DB·metadata-only mount·MySQL gate 설명을 보존했다. 당시 직접 수행한 route 대조·정적 검사 결과는 직전 항목과 보존 증거에 기록돼 있다. |
| 4 | fresh reviewer 후속 독립 재리뷰 | README 140행 P2 해소, 실제 `GET /health/live`·`GET /health/ready`·`POST /cases`·`GET /cases/{case_id}/view`와 README 9·69·140행의 일치, command/media 후속 범위 한정을 확인했다. 후속 독립 재리뷰 판정은 PASS이며 남은 병합 차단 문제는 없다. |

- **후속 reviewer의 파일·검증 확인:** 고유 납품 파일은 **13개**다. 후속 재리뷰 시점의 manifest와 실제 13개 파일 해시 불일치는 **0개**, README·Implementation Log를 제외한 제품·테스트·gate **11개** 해시는 불변이었다. boundary·Contract fixture·`git diff --check`는 PASS로 보고됐다. 이 해시 대조는 이번 Log 후속 기록을 추가하기 전의 검토 시점에 대한 결과이며, 이번 Log 변경 후 manifest 재대조 결과를 뜻하지 않는다.
- **현재 진행 판정:** 후속 reviewer 결과에 따라 RT-08(b) 커밋·중간 PR 생성은 가능하다. 실제 병합은 원격 CI 통과 후 가능하며, 원격 Linux CI는 아직 실행되지 않았다. 이번 작업에서는 Implementation Log만 갱신하고 staging·커밋·푸시·PR 생성 및 테스트 재실행을 하지 않는다.
- **남은 비차단 위험:** 생성 후 500 또는 COMMIT ACK 유실 시 생성 반영 여부가 불명일 수 있다. 과거 Worker 실패·timeout의 개별 직접 원인은 미확정이며, 이번 GREEN이나 #370 공통 timestamp ordering 수정으로 소급 확정하지 않는다. invalid historical row·큰 clock step·EC2 clock discipline 위험과 원격 Linux CI 미실행 한계가 남는다.
- **상태·연결:** RT-08 **IN_PROGRESS** · **Refs #295 (RT-08(b))** · PR 번호 **pending** · merge SHA **pending**.

### PR #373 원격 CI 후속 확인

- **기록 근거·실행 구분:** 사용자가 원격에서 직접 확인해 전달한 PR **#373**의 CI 결과를 기록한다. run **39029507171**, test job **117386951933**이다. 이번 Log 갱신에서 원격 조회나 테스트 재실행을 수행한 결과는 아니다.

| 원격 CI 항목 | 결과 | 소요 시간 |
| --- | --- | --- |
| boundary-check | PASS | 6초 |
| test job | PASS | 18분 48초 |
| 전체 pytest 단계 | PASS | 17분 44초 |
| MySQL execution gate | PASS | 별도 소요 시간 미제공 |

- **기존 구현 단계 결과와의 구분:** 로컬에서 보존한 전체 pytest 정확히 1회 **7,297 passed / 26 skipped / 실패 0**, **23분 27초**, 실제 MySQL **652 tests / 1,956 phases passed** 및 strict JSON/JUnit gate PASS는 기존 구현 단계의 결과다. 위 표는 별도의 원격 CI 실행 결과이며, 로컬 수집 건수·phase 수를 원격 결과에 전용하거나 두 실행을 합산하지 않는다. 원격 pytest 건수는 이번 전달 자료에 포함되지 않았다.
- **후속 상태:** 앞선 「원격 Linux CI 미실행」은 당시의 한계로 보존하며, 이번에 전달된 원격 CI PASS 결과로 갱신한다. PR은 **#373**, merge SHA는 **pending**으로 유지한다. CI 통과 기록이 실제 병합 완료를 뜻하지 않는다.
- **남은 위험 유지:** 생성 후 500·COMMIT ACK 유실의 생성 반영 불명, 과거 Worker 실패·timeout의 개별 직접 원인 미확정, invalid historical row·큰 clock step·EC2 clock discipline 위험은 유지한다. 이번 원격 CI PASS도 과거 사건의 직접 원인을 소급 확정하는 근거로 사용하지 않는다.
- **이번 작업 범위·상태:** Implementation Log만 후속 갱신하며 테스트 재실행·staging·커밋·푸시는 하지 않는다. RT-08 **IN_PROGRESS** · **Refs #295 (RT-08(b))** · PR **#373** · merge SHA **pending**.

## 2026-10-17 RT-08(c) — command/enqueue API

**Status: IN_PROGRESS · Refs #295 (RT-08(c)) · PR #375 · merge SHA pending.** 아래는 별도 managed worktree에서의 구현·검증 이력이다. RT-08 전체 종결이나 Owner acceptance 판정이 아니다.

### 기준·범위 확정

- 직접 `git fetch origin develop` 후 기준은 `3ea6f09084f7396eb980f53d5afa69da7043c83c`다. 해당 commit은 PR #373의 merge commit이며 RT-08(b)의 Case 생성·조회와 PR #371/#370 durable timestamp ordering, PR #372 workflow 30분 변경을 포함한다. 앞의 PR #373 pending/사용자 전달 CI 기록은 당시 이력으로 보존한다. 이번에는 로컬 Git ancestry로 병합 포함 여부를 확인했으며 원격 CI를 새로 조회·실행하지 않았다.
- 새 worktree `C:/Users/cheol/.codex/worktrees/rt08c-command-enqueue/ktc4-chonnam-2`, 새 branch `codex/rt08c-command-enqueue`. 기존 checkout과 과거 RAW/scratch/보존 증거를 수정·정리하지 않는다. 테스트 전용 schema와 이번 새 disposable MySQL 서버만 사용한다.
- 확인 입력: root `CLAUDE.md`, docs 운영 규칙, Architecture/ownership, Plan §0.1·§6 RT-08·§9·§12, HTTP Contract §3·§5.3·§7, Tech Spec §12.1/§12.4/§12.5, Baseline B-U2/B-D8 및 #370 의미, Log RT-08 이력, Case의 공개 `execute_command`/`CommandResult`·append 결정·read port 합의다. 저장소에 별도 AGENTS.md는 없으며 사용자 제공 사실 기반 지침을 적용한다.
- acceptance: append 유무의 202/200와 Location, Case 응답 그대로의 404/409/422, 실제 동일 transaction의 Case 저장+enqueue와 실패 rollback, pool/1205/disconnect의 503, COMMIT ACK 유실의 500·API 재실행 없음, 400/413/415의 안전한 envelope, 실제 수신 byte 한도, 요청 trace 전달·내부 필드/민감정보 비노출이다. 필수 MySQL inventory와 JSON/JUnit 누락 차단도 확장한다.
- RT-08(d) cancel 배선, RT-11 media, RT-09 Worker E2E·RT-10 실제 capability 조립, Case/다른 Owner 내부 수정은 제외한다. 이 slice의 실제 발주는 기존 `RUN_NOTICE_ACTION`과 fixture Case를 사용한다(Plan §4 허용 경로).

### 구현·transaction·idempotency·오류 매핑

- `routes_commands.py`: `application/json` 확인 후 stream을 B-U2 config 한도 안에서만 모으고 UTF-8 JSON을 파싱한다. Content-Length가 없거나 실제보다 작아도 실제 byte 수를 검사하며 초과 chunk 뒤 추가 수신하지 않는다. object의 문자열 case_id 불일치만 transport 400이고, 다른 JSON 값·누락 필드·kind/payload 판단은 Case로 그대로 전달한다. 비표준 NaN/Infinity와 파싱 불가는 400이다.
- `composition.execute_command`: transaction별 기존 CaseStore(conn, executions)를 생성하고 공개 Case command를 실행한다. Case 행 잠금·저장 뒤 이번 append 목록만 기존 `enqueue(conn, records, trace)` batch로 넣고 기존 `run_api_transaction`의 ACK 후 결과를 반환한다. 응답 생성 뒤 별도 Case 재조회나 body 보정은 없다. 실행 ID·attempt·lease·JobRecord payload는 HTTP body에 추가하지 않는다.
- status는 Case `ok/error/case_view`와 append 목록만으로 표 조회한다. kind를 보고 200/202를 정하지 않는다. trace는 서버가 요청마다 발급하고 async→threadpool→enqueue/event로 이어진다. payload·URL·query·header·예외 원문·SQL·DB URL·path는 logger에 전달하지 않는다. 413은 기존 bounded events로 건수를 기록한다.
- API는 자동 재시도하지 않는다. 기존 RT-02가 분류하는 precommit dependency 실패는 rollback 후 503, COMMIT 결과 불명은 500, 관련 없는 SQL/예상 밖 예외는 500이다. 실제 MySQL proxy가 COMMIT OK를 유실시킨 경로에서 Case/queue는 함께 저장되고 command가 재실행되지 않음을 검증한다.
- command 중복 제출 의미는 Case가 소유한다. 테스트는 MARK_REVIEWED의 revision 기반 sequential/concurrent 재제출이 200/409이고 추가 실행이 없음을 확인한다. API에 새 dedup key·재전송 정책·Exactly Once를 추가하지 않는다. 같은 `(job_id, attempt)` 중복 거부는 기존 Runtime DB UNIQUE와 acceptance를 유지한다. 새 사용자 intent의 새 job_id를 기존 job과 합치지 않는다.
- `cancelled_job_ids`가 생기면 RT-08(d) 전에는 `NotImplementedError`로 전체 rollback·일반 500이다. Case 절반만 중단 commit되는 것을 막는 미완성 조립 경계이며, 취소 API acceptance 완료를 주장하지 않는다. `request_cancel` 호출·새 status/error code·Case kind 분기는 추가하지 않는다.
- 기존 Case `START_ANALYSIS`에 필요한 `CaseTimelineSource`와 실제 결과 adapter/reader 조립은 아직 없다. 해당 command의 dependency 조립까지 완료됐다고 주장하지 않는다. 이를 채우기 위해 새 recording/Case 공개 capability나 process cache·별도 transaction을 만들지 않았다.

### Plan 대비·authority·리뷰

- Plan P-9의 sync JSON route 대신 bounded receive는 async, 동기 DB callback은 Starlette `run_in_threadpool`에서 실행한다. body 전체를 한도 검사 전에 읽지 않고 event loop를 DB로 막지 않기 위한 구현 상세다. 기존 Case/Runtime 공개 함수와 transaction 경계는 그대로다. authoritative Plan은 고치지 않는다.
- 신규 command 필수 parameter 17개를 gate에 추가하고 독립 test inventory를 별도로 둔다. 기존 역할·parameter·timestamp inventory, JSON/JUnit strict 검사·실제 evidence 누락 mutation과 nested 900초는 유지한다. workflow 30분도 변경하지 않는다.
- Contract/Accepted Decision/Baseline 값·의미 변경 없음. 새 다른 Owner surface/의무 없음. #370의 causal ordering·heartbeat/lease 비감소·fence·retry 시각 계산은 소스 변경 없이 회귀한다. Owner 확인은 통상 Plan §12.6 deferred audit이며 새 의미 결정 요청은 없다.
- 읽기 전용 별도 리뷰에서 actionable 코드 finding은 없었다. 리뷰어는 테스트를 독립 실행하지 않았으며 START_ANALYSIS/cancel 미완성 경로와 README/Log 기록을 요구했다. 이는 사용자 독립 재리뷰·Owner acceptance·원격 CI를 대체하지 않는다.

### 직접 실행과 보존 증거

- 이번 증거 폴더는 새 worktree의 `.codex-scratch/rt08c-20261017/`다. `*-command.json`에 명령/cwd, `*-result.json`에 실제 exit/elapsed, txt와 JUnit·MySQL JSON 원본을 각각 보존한다. 기존 #373/RT-08(b) 결과는 과거 보존 증거이며 아래 이번 직접 결과에 합산하지 않는다.
- 제품 구현 전 HTTP RED: **24 failed**, 실제 MySQL RED: **17 failed**, 모두 route 부재의 404를 확인했다. 신규 gate metadata 누락 RED: **34 failed / 142 passed / 4192 deselected**다. 신규 role/parameter를 함께 지웠을 때 기존 gate가 거부하지 못하는 것을 확인한 뒤 필수 inventory를 추가했다.
- 최초 GREEN 시도에서 신규 fixture가 Runtime FAILED만 만들고 Case의 실패 반영을 빠뜨려 append command가 409였다. 기존 Case의 공개 `record_candidate_search_failure`로 fixture를 수정했다. 미commit 상태 관측도 Case share lock을 추가로 잡지 않는 plain read로 분리했다. 해당 실패 원본과 이후 결과를 합치거나 덮어쓰지 않는다. 제품의 Case/Worker 규칙은 고치지 않았다.
- 이후 신규 실제 MySQL targeted **17 passed**, pytest 23.16초, runner wall 27.156초(`green-mysql-fixture`). boundary **PASS**, Contract fixture **PASS**(62 규칙·26 JSON·104 의미 fixture), workflow30분/nested900초·SoT/다른 Owner 소스 불변·syntax·`git diff --check` **PASS**. 정적 첫 실행 후 runner 출력의 cp949 인코딩 오류가 있었으나 검사 subprocess exit는 0이며 UTF-8 원본과 result JSON은 보존한다. runner stdout을 UTF-8로 고정했다.
- 관련 회귀·실제 전체 MySQL inventory·strict gate·evidence mutation의 최종 결과는 아래 후속 직접 검증 기록에 추가한다. 실행 중 결과를 PASS로 선기록하지 않는다.

### 남은 위험·후속

- RT-08(d)의 중단 transaction 연결과 START_ANALYSIS timeline/결과 adapter 조립, RT-09 E2E, RT-10 실제 handler, RT-11 media는 후속이다. `500`/응답 유실 시 반영 여부를 모르는 기존 계약도 유지한다.
- 전체 pytest 실행 필요성은 이번 변경 경계와 관련 회귀/전체 MySQL inventory 결과로 판단하며, 실행 여부를 아래 최종 기록에 명시한다. 원격 Linux CI·Owner 수락·기존 invalid row backfill·EC2 clock discipline은 이번 로컬 검증의 보장 범위가 아니다.

### 2026-10-18 중단 복구·최종 검증 인계

- **상태·범위:** **IN_PROGRESS · Refs #295 (RT-08(c)) · PR/merge SHA pending**. 같은 `codex/rt08c-command-enqueue`/기준 HEAD에서 재개했다. 제품·테스트·gate 소스 변경은 없고 최종 검증 기록만 추가한다. staging·커밋·푸시·PR 생성은 하지 않는다. RT-08(d)·RT-11·START_ANALYSIS timeline·중단 배선은 추가 구현하지 않는다.
- **중단 시점 복구:** `mysql-acceptance-result.json`의 runner exit **0**, 원본 stdout의 부모 **1 passed / 989.56초**, 부모 JSON의 setup/call/teardown **3 passed**를 확인했다. 해당 실행은 중단 뒤 **2026-10-17 22:17 KST**에 완료되어 있었다. 부모의 989.56초는 DB suite 뒤 mutation까지 포함한 시간이며 nested DB suite 제한과 구분한다. 전체 MySQL을 새로 실행하지 않았다.

| 구분 | 검증 | 결과·근거 |
| --- | --- | --- |
| 이전 직접 실행의 보존 증거 | 최종 targeted | **217 passed**, pytest 31.41초 (`targeted-final.txt/xml`) |
| 이전 직접 실행의 보존 증거 | API·Worker·Case command 비-MySQL 회귀 | **249 passed / 235 deselected**, pytest 108.34초 (`related-regression.txt/xml`) |
| 이전 직접 실행의 보존 증거 | gate unit 전체 | **4368 passed**를 해당 JUnit classname으로 집계. 같은 최초 묶음의 **6 failed / 4403 passed**, exit 1은 유지한다 (`green-targeted.xml/txt`) |
| 완료된 기존 실행을 복구 확인 | 실제 MySQL 8.4.7 전체 필수 inventory | **664 collected = 664 selected = 664 passed**, setup/call/teardown **1992 passed**, collection error·skip·xfail **0**. child JUnit **730.772초**, nested **900초 이내**. RT-08(c) **17개**, timestamp ordering **35개** 포함 |
| 완료된 기존 실행을 복구 확인 | 실제 parameter 누락 mutation | **3787/3787 거부**, RT-08(c) **119/119** 포함. 독립 inventory의 **511개 identity** 및 요구 layer와 Counter가 정확히 일치함을 이번 재개에서 감사. 원본 `parameter-mutations.json` 보존 |
| 이번 재개 직접 실행 | 성공한 실제 JSON/JUnit strict gate | **PASS: 664 tests, skip 0, xfail 0**, exit 0 (`resume-strict-gate.txt/result.json`) |
| 이번 재개 직접 실행 | 실제 RT-08(c) metadata·family 누락 | strict 검증을 먼저 통과한 보고서에서 role/scenario/parameter/all-metadata 누락 **68/68**, family의 collection/selection/phases/JUnit 동시 누락 **6/6 거부** (`resume-mutations.json`) |
| 이전 직접 실행의 보존 증거 | boundary·Contract fixture·workflow | **PASS**. workflow **30분**, nested **900초**, #370/Contract/Baseline/다른 Owner 소스 불변 유지 |

- **증거 불변·소스 동일성:** 재개 직후 변경 파일의 SHA-256을 `resume-source-snapshot.json`에 고정했다. 재개 전후 제품·테스트·gate **9개 소스**의 SHA-256 동일성을 최종 검사하며 문서 3개 중 이번에 바뀌는 것은 이 Log의 후속 기록이다. 성공한 child JSON/JUnit·3787 mutation 원본은 추가 mutation 전후 SHA-256이 동일하다. 이미 통과한 targeted/회귀/gate unit/boundary/Contract 전체 검증을 무조건 반복하지 않았다.
- **실패 이력 보존:** 초기 fixture 실패 **6개**가 들어 있는 `green-targeted`의 exit 1과 원본을 수정하지 않았다. 수정 후 별도 `green-mysql-fixture` **17 passed**와 `targeted-final` **217 passed**를 구분한다. RED·실패 묶음을 최종 성공 수치로 재작성하지 않는다. 과거 #373/RT-08(b)의 전체 pytest·원격 CI도 이번 수치에 합산하지 않는다.
- **정리:** 전용 서버의 port **13349**와 `@@datadir`가 이번 `start-mysql.sh`의 정확한 경로임을 확인했다. 다른 client connection **0**, 테스트 계정 **0**, 잔여 disposable schema **0**을 SQL assertion으로 확인하고 이번 전용 base DB `rt08c_test`만 DROP하여 system schema 4개만 남긴 후 SHUTDOWN했다. observer connection도 닫았다. 다른 checkout·기존 MySQL 서비스·과거 RAW/scratch/증거는 정리하지 않았다.
- **정리 검증의 실패·후속:** 최초 `resume-cleanup` helper는 SQL 확인·DROP·SHUTDOWN·close 이후 Windows connect probe의 **10035 timeout**을 connection refused로 인정하지 않아 exit **1**이다. 이 원본을 보존한다. 이를 listener 부재 증거로 쓰지 않았으며, 별도의 성공한 `Get-NetTCPConnection` 전체 listener inventory에서 해당 port **0**, 소유 WSL launcher **0**, Linux에서 PID/socket/pidfile/listener/테스트 임시 서버 디렉터리 **0**을 직접 확인했다. server.log에도 `Shutdown complete`가 있다 (`resume-cleanup-native-inventory.json`, `resume-cleanup-linux.txt`, `resume-cleanup-processes.json`). 전용 DB 정리 assertion의 완료는 보존된 script의 실패 지점과 server shutdown 로그로 감사한다.
- **최종 인계:** 변경 파일 **12개** 전체와 untracked 4개를 포함한 `review.diff`, SHA-256 `review-manifest.json`, `verification-summary.json`, `review-summary.md`를 새 worktree의 `.codex-scratch/rt08c-20261017/`에 정리한다. 최종 `git diff --check` 및 staging 빈 상태를 직접 확인한다. 전체 pytest는 **미실행**이며, 한정된 API/gate 변경에 대해 필수 MySQL 전체·관련 회귀·gate unit·정적 검사로 검증 범위를 정한 이전 판단을 유지한다.
- **남은 판단:** 현재 로컬 증거에서 미해결 코드/테스트 차단 결함은 확인되지 않았다. 원격 Linux CI·Owner 수락·병합 승인을 뜻하지 않는다. RT-08(d)의 취소 조립과 START_ANALYSIS timeline/결과 adapter/reader, RT-09/10/11 및 `500`/응답 유실의 반영 불명은 후속·기존 한계다. 독립 재리뷰 요청 가능한 미커밋·미스테이징 상태로 인계한다.

### 2026-10-18 PR #374 반영 — 최종 독립 리뷰 P2 후속

**상태·연결: IN_PROGRESS · Refs #295 (RT-08(c)) · RT-08(c) PR/merge SHA pending.** 앞선 구현·복구 기록은 당시 사실로 보존한다. 그 이후 구현에 참여하지 않은 최종 fresh reviewer가 `kind=[]/{}`의 Case TypeError → HTTP 500을 재현하여 P2 통합 acceptance 차단으로 판정했다. 이 후속은 해당 P2만 다룬다.

- **시작 상태 검증·보존:** branch `codex/rt08c-command-enqueue`, HEAD `3ea6f09084f7396eb980f53d5afa69da7043c83c`, staging 0, 변경 12개 및 이전 manifest의 소스 12개/증거 92개 SHA-256이 모두 일치했다. 이전 manifest SHA-256은 `2ef32b62976f759bb23bf5bbe7fcfaff1f7da037968d1a593ad2ee73b8347979`, index SHA-256은 `a0a0257a0baecd51056fb45db2c0acf4c4f8d30a2a308c3ce0f3680de0913a31`였다. 새 `.codex-scratch/rt08c-p2-20261018/pre-merge/`에 미커밋 12개 전체·기존 인계 자료와 binary diff를 보관했다.
- **Owner 결정:** Case Owner 유소연의 [PR #374](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/374) 본문과 GitHub metadata를 직접 조회했다. 선택지 1인 「dict 조회 전에 kind가 str인지 검사하고 기존 invalid_payload로 거부」를 택했으며 새 reason은 만들지 않고 API route 수정도 필요 없다고 명시했다. 이는 기존 HTTP Contract의 422를 충족시키는 Case 검증기 수정이고 Contract/Accepted Decision/Baseline 의미 변경이 아니다.
- **병합 확인:** `git fetch origin` 뒤 최신 `origin/develop`은 전달된 merge SHA **`75d5b7f7fa993061be625dfdb69202b2f928103d`**였다. 현재 RT-08(c) branch에 충돌 없이 fast-forward했다. 새 로컬 commit을 만들거나 stash/staging하지 않았으며 병합 직후 기존 미커밋 12개 파일 byte가 모두 동일함을 확인했다. #373 및 #371/#370은 계속 ancestor다.
- **실제 upstream 범위:** `3ea6f090..75d5b7f7` 변경은 `src/daesingo/case/command.py`의 type guard 1줄과 `tests/case/test_command.py`의 비문자열 kind 4개 parameter 추가뿐이다. 두 파일은 이미 병합된 HEAD에 속하고 RT-08(c) 미커밋 diff에는 포함하지 않는다. API 제품 3개 파일·transaction/queue/worker/timestamp/fence·gate·workflow 소스는 후속 전 SHA 그대로다.
- **원격 CI의 출처 구분:** #374 head `8ce3e2c325d41ad413adef853a9e67d144a51f31`의 PR-triggered workflow를 직접 조회하여 `boundary-check` run **39048882066**, `python-tests` run **39048882063**의 completed/success를 확인했다. 이는 #374의 원격 결과이며 현재 미커밋 RT-08(c) 전체의 원격 CI 결과로 대신 쓰지 않는다.

#### RED 근거와 새 GREEN

- **보존 RED:** 병합 전 fresh reviewer `/root/rt08c_final_fresh_review`의 직접 실행 보고를 `prior-fresh-review-red.md`에 보존했다. 당시 실제 public Case 함수+메모리 CaseStore에서는 `kind=[]/{}`가 Case 72행 membership의 TypeError, 실제 HTTP router+DB 없는 composition bridge에서는 **500 http.internal_error**였다. 기대는 **422 case.command.invalid_payload**다. 이 이전 probe는 실제 MySQL 검증이 아니며 이번 후속에서 예전 코드를 다시 실행한 것으로 기록하지 않는다.
- **회귀 추가:** 기존 HTTP/MySQL domain-invalid acceptance 안에 `kind=[]`와 `{}`를 추가했다. 실제 Case `execute_command`를 감싼 관측만 하고 결과/오류를 바꾸지 않는다. 실제 MySQL repository save, Runtime enqueue, API engine의 쓰기 SQL은 각각 **0건**, Case 전체 row 및 기존 Case/JobRecord/execution snapshot 불변을 확인한다. 잘못된 kind를 정상으로 통과시키거나 HTTP schema/포괄 TypeError catch로 바꾸면 이 회귀가 422/body/무쓰기 조건에서 실패한다.
- **테스트 범위:** 같은 필수 `api_commands/domain/invalid` node 안에서 원래 top-level array 거부와 새 두 kind 거부를 모두 검사한다. 기존 17개 MySQL parameter inventory와 node/layer gate를 변경하거나 삭제하지 않았다. 새 회귀를 위해 RT-08(c) API 제품 코드는 수정하지 않았다.

| 이번 직접 실행 | 결과·원본 |
| --- | --- |
| P2 실제 HTTP/MySQL invalid 회귀 | **1 passed**, pytest **2.73초**, exit 0. top-level array와 kind array/object 모두 422, save/enqueue/쓰기 SQL 0 (`p2-green.txt/json/xml`) |
| API 전체 + Case command + API gate 확장 | **380 passed / 1 failed**, pytest **141.00초**, runner exit 1 (`api-case-gate.*`). HTTP targeted **41개**, Case command **47개**, API gate **176개**는 이 JUnit에서 모두 통과 |
| 확장 실행의 실패 | `tests/api/test_health_mysql.py::test_ready_when_actual_mysql_server_is_shutdown`: 기존 `owned_mysql.assert_port_closed`의 종료 후 native connect가 성공하여 assertion 실패. health 응답 assertions 뒤 cleanup에서 발생했다. P2 또는 #374와의 인과관계는 확인하지 못했다 |
| 같은 health 노드 분리 재실행 | **1 passed**, pytest **9.92초**, exit 0 (`shutdown-isolated.*`). 최초 실패 원인 확정이나 확장 묶음 전체 GREEN으로 해석하지 않는다 |
| 기존 664개 실제 보고서 strict gate | **PASS: 664 tests, skip 0, xfail 0** (`preserved-strict-gate.*`). 과거 3ea6f090 실행의 완전성 재확인이며 새 HEAD에서 664개를 실행한 결과가 아니다 |
| boundary / Contract fixture | PASS / **62 규칙·26 JSON·104 의미 fixture PASS** (`boundary.*`, `contract-fixtures.*`) |

- **반복 판단:** 전체 pytest와 전체 MySQL 664개 및 parameter mutation 3787개는 반복하지 않는다. upstream은 Case type guard 1줄/Owner 테스트뿐이고 API·DB·queue·worker·timestamp·gate는 SHA 동일하다. 새 HEAD에서 실제 HTTP/MySQL P2·기존 command 경로·Case/API/gate를 검증했고, 기존 664/3787·metadata68/family6 원본은 새 결과와 구분해 보존한다. health cleanup 실패는 원본과 단독 PASS를 함께 독립 reviewer의 판단 항목으로 남긴다.
- **검증 환경 이력:** 새 전용 port **13350**/`rt08c_p2_test` 서버만 만들었다. 첫 새 Linux helper가 Windows CRLF 때문에 `set: Illegal option`으로 기동 전에 실패했으며 해당 helper/stderr를 보존하고 새 helper만 LF로 바로잡았다. 제품/기존 helper/과거 RAW는 수정하지 않았다.
- **다음 인계:** 독립 fresh reviewer가 새 P2 회귀·동일 transaction/오류 매핑·gate/범위·health 실패의 병합 영향 및 commit/중간 PR 진행 가능 여부를 다시 판단한다. reviewer의 직접 실행과 위 구현 실행·과거 보존 증거를 분리한다. 최종 결과와 새 review diff/manifest·정리는 이 후속 증거 폴더에서 갱신한다. RT-08(d)·START_ANALYSIS timeline·중단 배선·RT-11은 그대로 후속이며 이 Task 전체를 종결하지 않는다.

#### P2 후속 최종 독립 재리뷰·정리

- **독립성:** 이 후속 구현에 참여하지 않은 새 `/root/rt08c_p2_fresh_review`를 fresh context로 호출했다. reviewer는 변경 12개·upstream Case 2개·Contract와 보존 증거를 읽기 전용으로 검토했다. 구현자의 자체 점검이나 이전 구현 중 리뷰로 대체하지 않았다. 아래 reviewer 보고 전사본과 직접 JUnit은 새 증거 폴더의 `fresh-review-report.md`/`fresh-review-junit.xml`이며, 별도의 stdout 파일은 생성하지 않았고 도구 출력으로 관측했다.
- **reviewer 직접 실행:** `tests/api`, `tests/case/test_command.py`, `tests/common/db/test_mysql_gate.py`에서 `-k 'not actual_report'`로 **4573 passed**, warning 1, **355.03초**, exit **0**. HTTP command 24 / 실제 MySQL command 17 / Case command 47 / health 5 / gate unit 4368을 포함한다. JUnit 원본 SHA-256 **`294d44cf023c2e05c396f6bd4f821270760d89b3559e61495154cc06a7c186b6`**를 복사 전후 확인한다. boundary·Contract 62/26/104·과거 664 보고서 strict gate도 reviewer가 직접 PASS를 확인했다. 전체 pytest/전체 MySQL/전체 mutation/현재 미커밋 원격 CI는 실행하지 않았다.
- **독립 판정:** 실제 HTTP·Case·MySQL의 `kind=[]/{}`는 422 `case.command.invalid_payload`, save/enqueue/쓰기 SQL 0, Case 전체 row/snapshot 불변이다. Case 검증기의 문자열 guard로 처리되며 API schema 복제나 TypeError 우회가 없다. 같은 Connection/transaction의 Case lock→저장→append batch enqueue→COMMIT 확인 뒤 응답, UNIQUE/revision/중복 제출 의미, precommit503·COMMIT불명/예상밖500·자동재실행 없음·원문 비노출과 #370 ordering을 유지한다. RT-08(d)·중단/timeline 조립·RT-11, gate/timeout 정책은 확장·완화하지 않았다.
- **남은 차단·비차단:** reviewer는 P2 해소 및 추가 수정이 필요한 병합 차단 finding 없음으로 판정하고 로컬 커밋·중간 PR 진행 가능하다고 보고했다. 최초 확장 **380 passed / 1 failed**는 그대로 실패 원본으로 보존한다. 동일 helper의 health 단독 및 reviewer의 API 전체가 통과했으므로 현재 P2 차단 결함으로 보지 않되, **원인 미확정 비차단 cleanup 위험**으로 남긴다. 환경 문제라는 단정이나 최초 실패의 성공 재분류를 하지 않는다. 원격 CI/Owner 수락/최종 병합 승인과는 구분한다.
- **반복 필요성의 독립 판단:** reviewer도 Case guard·회귀만 바뀌고 API/transaction/queue/worker/gate 제품 소스가 동일하며 현재 실제 거부 경로·API/Case/gate를 검증했으므로 전체 pytest·전체 MySQL664·전체 mutation의 반복은 P2 후속 검토에 필요하지 않다고 판단했다. 664/3787·metadata68/family6 및 초기 fixture6실패/수정후GREEN을 현재 HEAD 실행으로 합산하지 않는다.
- **정리 직접 결과:** reviewer의 DB 실행 종료 후 port13350과 정확한 `@@datadir`를 검증했다. disposable schema0·테스트 계정0·다른 client connection0을 SQL로 확인하고 이번 `rt08c_p2_test`만 DROP, system schema4 확인, SHUTDOWN ACK와 observer close를 `cleanup-sql.json`에 단계별 저장했다. 성공한 Windows 전체 listener inventory의 해당 port0·launcher0, Linux PID/socket/pidfile/listener/health 임시 서버 디렉터리0을 각각 별도 exit0으로 확인했다 (`cleanup-native.json`, `cleanup-linux.txt`). 다른 서비스·과거 RAW/scratch/보존 증거는 정리하지 않았다.
- **최종 상태:** 새 review diff·변경 파일12 목록·manifest·verification summary를 최종 내용과 일치시키고 이전 증거92 SHA 불변, HEAD75d5b7f7/branch 유지, `git diff --check` PASS 및 staging0을 최종 검증한다. 이 후속에서 바뀐 미커밋 파일은 HTTP/MySQL 회귀와 이 Log 둘뿐이며, upstream Case 두 파일·새 scratch 증거는 RT-08(c) PR 파일에서 제외한다. **IN_PROGRESS · Refs #295 (RT-08(c))**. 커밋·푸시·PR 생성 없이 미스테이징 상태로 인계한다.

#### PR #375 연결·진행 중 CI 상태

- **현재 연결:** PR **#375** · 상태 **IN_PROGRESS** · **Refs #295 (RT-08(c))** · merge SHA **pending**. 앞선 PR 번호 미정·로컬 인계 기록은 당시 이력으로 보존한다.
- **원격 CI:** 사용자 전달 기준 `boundary-check` **PASS**, `python-tests` **실행 중**이다. 최종 CI PASS나 병합 완료로 기록하지 않는다. 이전 로컬 직접 실행·보존 증거·PR #374의 CI 결과와도 구분한다.
- **이번 갱신 범위:** Implementation Log의 RT-08(c) 기록만 수정한다. 코드·테스트·다른 문서·보존 증거는 변경하지 않으며 테스트 재실행·staging·커밋·푸시는 하지 않는다. `git diff --check`와 변경 파일이 이 Log 하나뿐인지 확인한다.


### 2026-10-18 PR #375 최종 병합·CI 후속 정정

- 기존 「PR #375 연결·진행 중 CI 상태」의 `python-tests 실행 중`과 merge SHA pending은 당시 이력으로 그대로 보존한다. 이번 후속에서 GitHub PR metadata와 해당 head `27274a8ab88ec331fb1bdc944f548c6916f4f518`의 PR-triggered workflow를 직접 조회해 최종 사실을 한 번에 정정한다: **PR #375 병합 완료 · merge SHA `da7e5e613b21fda02211aa9f47f8c61b94835d13` · boundary-check PASS · python-tests PASS**.
- 원격 근거: [PR #375](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/375), [boundary-check run 39053929388](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39053929388), [python-tests run 39053929444](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39053929444). 두 run은 completed/success다. 이번 로컬 테스트나 RT-08(d)의 원격 CI로 전용하지 않는다.

## 2026-10-18 RT-08(d) — 승인된 중단/cancel 배선

**Status: IN_PROGRESS · Refs #295 (RT-08(d)) · PR pending · merge SHA pending.** staging·커밋·푸시·PR 생성 없이 독립 재리뷰를 준비하는 구현 기록이다. 독립 재리뷰·acceptance 완료 전 RT-08 전체 DONE 또는 Closes #295로 변경하지 않는다.

### 기준·acceptance·범위

- `git fetch origin develop`로 확인한 최신 기준은 `da7e5e613b21fda02211aa9f47f8c61b94835d13`이다. PR #375, Case 검증 PR #374(`75d5b7f7fa993061be625dfdb69202b2f928103d`), #370 durable timestamp ordering의 PR #371 병합을 포함한다. 새 managed worktree `C:/Users/cheol/.codex/worktrees/rt08d-cancel-wiring/ktc4-chonnam-2`, 새 branch `codex/rt08d-cancel-wiring`에서만 변경한다.
- 입력: root CLAUDE.md·사용자 AGENTS 지침·docs 운영 규칙·Architecture/ownership, Runtime Plan §0.1·§6 RT-08·§9·§12, HTTP Contract §5.3·§7, JobExecution Contract, Accepted RD-06/RD-19(#245)·Case `stop-analysis.md`의 확정 결정, Tech Spec §12.1~§12.5, Baseline B-D8/B-X1 및 #370 ordering, Implementation Log의 RT-05·RT-06·RT-08 이력이다. Case의 공개 `CommandResult.cancelled_job_ids`와 Runtime `request_cancel(conn, ids)`가 이미 맞는 형태로 승인·구현되어 새 interface 판단은 없다.
- acceptance: Case가 정한 대상만 같은 transaction에서 cancel, append 없는 중단은 200·Case body 보존·Location 없음, QUEUED 즉시 CANCELLED/usage 0, RUNNING은 최초 marker·Case 즉시 PARTIAL/대기 제외, STALE marker 및 이미 terminal인 사실 유지. 전체 rollback·API 재시도 없음·COMMIT 불명500, revision 기반 중복/동시 요청, commit 전후 process interruption, heartbeat/checkpoint/fence·늦은 SUCCEEDED 배제·Runtime receipt 기반 재전달 idempotency, 민감정보 비노출과 strict gate를 검증한다.
- 새 공개 surface·다른 Owner callback·Contract/Accepted Decision/Baseline 의미 변경 없음. RT-11 media, START_ANALYSIS timeline 및 실제 adapter/reader 조립, 다른 Owner 내부 구현과 미결 정책은 추가하지 않는다. 기존 checkout·RT-08(a)~(c) worktree·과거 scratch/RAW/보존 증거를 수정·정리하지 않는다.

### Implementation Notes

- **구현 결과:** `api/composition.py`가 기존 Case command 실행 후 `cancelled_job_ids`가 있으면 기존 `request_cancel`을 같은 Connection에서 호출한다. 기존 append enqueue와 caller transaction helper·commit ACK·응답 표는 그대로다. route의 kind 분기, 새 dedup key, 새 취소 status/error, 별도 transaction/강제 thread kill은 없다.
- **Plan 대비·implementation detail:** 승인된 PR(d) 배선 그대로다. 테스트는 요청 transaction 내부 관측·독립 plain read·InnoDB 잠금 검사 및 spawned HTTP process의 IPC로 commit 전후 kill 위치를 고정한다. 관측을 위한 API/public callback은 추가하지 않았다. cancel_deferred의 이전 일반500 guard 검사는 cancel_wired의 실제200/원자적 반영 검사로 전환하고 inventory를 함께 갱신했다. 다른 기존 inventory는 유지한다.
- **transaction/idempotency/ownership/중단:** Case 행 선잠금 → Case 저장 → 동일 tx cancel → 필요 시 기존 enqueue → ACK 뒤 기존 body 반환. request_cancel의 sorted job/attempt 잠금·최초 marker 유지·terminal no-op와 #370 causal timestamps는 기존 코드다. API는 한 번만 시도하고 COMMIT ACK 유실 또는 응답 전 process 사망은 반영 불명이다. 반복 command의 stale_revision/not_allowed는 Case 소유이며 API가 재해석하지 않는다. Runtime cancellation 요청과 ownership loss는 구분하고, capability 내부 retry/비용·반환까지의 지연은 기존 협력적 중단의 한계다. 늦은 SUCCEEDED 사실은 유지하며 Case의 정산 job guard로 결과를 버린다. CANCELLED는 기존 T2 redelivery 후보가 아니며, 늦은 SUCCEEDED의 NOT_APPLIED receipt는 Runtime에 남고 Case 상태를 쓰지 않는다.
- **Contract/Decision/Baseline 영향:** 모두 없음. workflow 30분·nested MySQL 900초·skip/xfail 거부·JSON/JUnit strict 검사 유지. 필수 api_cancel parameter inventory와 실제 report의 parameter/metadata/family 누락 mutation을 추가한다.
- **Owner 확인 포인트:** 통상 Plan §12.6 deferred acceptance와 독립 재리뷰가 남는다. 새 의미 결정이나 다른 Owner 의무의 승인 요청은 없다. 실제 process 내 호출과 DB transaction을 검증하며, 클라이언트 연결 종료가 sync DB thread를 강제 중단한다는 새 보장은 없다.

### RED → GREEN 및 직접 실행

- 이번 증거는 새 worktree의 `.codex-scratch/rt08d-20261018/`에 command/cwd·exit/elapsed·stdout·MySQL JSON/JUnit으로 보존한다. 과거 RT-08(a)~(c)/#370·PR #375 원격 CI는 보존/원격 근거이며 아래 직접 실행 건수에 합산하지 않는다.
- 최초 RED는 20 failed다. 그중 STALE fixture가 Worker finish로 STALE을 만들려는 테스트 오류 1건이 있었다. 첫 GREEN 시도는 12 passed/8 failed이며, 독립 관측의 Case 공유 잠금 충돌 6건, 그 STALE fixture 1건, NOT_APPLIED의 Case processed_executions 쓰기를 잘못 기대한 1건이었다. 제품 의미를 바꾸지 않고 plain read·recovery fixture·기존 Runtime receipt 기대값으로 수정했다. 이 원본은 그대로 보존한다.
- 수정된 테스트에서 제품을 원래 guard로 돌려 **20 failed**를 재확인한 뒤 최소 배선으로 **20 passed**, skip/xfail 0, pytest 18.11초를 확인했다(`red-cancel-corrected.*`, `green-cancel-corrected.*`). process kill 3경계와 실제 COMMIT OK 폐기 proxy를 포함한다.
- gate 최초 RED 시도 252 passed는 독립 inventory의 cancel_wired 전환과 기존 gate cancel_deferred 불일치로 정상 synthetic report부터 거부하던 잘못된 검증이었다. 이를 해소해 정상 report PASS를 함께 확인한 RED는 **38 failed/215 passed**이며, 신규 parameter의 node/parameter 메타데이터 누락을 기존 gate가 놓쳤다(`red-gate-valid-baseline.*`). 이 실패를 확인한 뒤 필수 inventory를 확장했다.
- 최종 targeted·회귀·실제 MySQL·gate·정적 검사 결과는 실행 완료 후 아래 후속으로 기록한다.

- **최종 관측 보강 중 실패·수정:** 전체 Case row 불변 검사로 관측 tuple을 5개로 늘린 뒤 기존 unpack 4개를 고치지 않아 `targeted-final`은 169 passed/5 failed였다. HTTP/DB assertions 뒤 테스트 코드의 ValueError이며 원본을 보존한다. unpack을 수정한 동일 회귀 `targeted-verified`는 **174 passed**, skip/xfail 0, pytest **50.17초**다. 제품 배선은 최초 최소 변경 그대로다.
- **gate unit:** `gate-unit` **4,583 passed**, skip/xfail 0, pytest **167.87초**. 기존 parameter/phase/JUnit 누락·skip/xfail 방어와 새 api_cancel inventory를 함께 검증했다.
- **정적 검사:** boundary 위반0 PASS; Contract 구조62·JSON26·의미fixture104 PASS. workflow 30분 파일 해시 불변, nested `timeout=900`·require MySQL·skip/xfail 금지 유지, 변경 Python7개 AST 파싱 PASS. common/Worker/Case·Contract·Tech Spec·Baseline·Plan **115개** baseline SHA-256 불변(`static-policy.json`). `git diff --check`와 #370 PR #371 merge ancestor도 직접 PASS 확인했다. 최종 문서 갱신 뒤 다시 diff/index 검증한다.

- **관련 비MySQL 회귀:** `tests/api tests/worker tests/case -m 'not mysql'`는 **681 passed / 2 skipped / 281 deselected**, pytest **87.92초**, exit0이다. skip은 기존 Case real-video 2개의 로컬 원본 영상 부재이며 MySQL skip이 아니다. 281 deselected는 이 실행에서 MySQL을 분리한 결과다. `.codex-scratch/rt08d-20261018/regression.xml`과 stdout에 각각 기록한다. 기존 Starlette/httpx deprecation warning 1개를 실패와 구분한다.
- **구현 중 읽기 전용 검토:** 새 context의 `/root/rt08d_readonly_review`가 12개 파일과 승인 문서·transaction/cancel/fence/redelivery/gate를 검토하고 actionable P1/P2 없음으로 보고했다. 테스트·수정은 하지 않았고, 당시 실행 중 전체 MySQL/mutation·관련 회귀 결과 및 원격 CI·Owner acceptance는 판단에서 제외했다. 이번 직접 회귀 결과와 합산하지 않으며, 사용자 후속 독립 재리뷰나 최종 acceptance로 대체하지 않는다(`implementation-review.md`).
- **전체 pytest 판단:** 현재 변경의 제품 동작은 기존 port 한 줄 배선이고, 관련 API·Worker·Case 회귀와 strict gate unit 및 실제 MySQL 전체 acceptance를 검증 범위로 잡았다. 전체 pytest는 이번에 실행하지 않는다. 과거 Log의 전체 pytest PASS는 과거 보존 증거이며 이번 HEAD/미커밋 변경의 직접 실행으로 인용하지 않는다. 원격 Linux CI도 이번 변경으로 실행하지 않았다.


### 최종 직접 검증·인계 (2026-10-18)

| 직접 실행 | 결과 | 원본 근거 (`.codex-scratch/rt08d-20261018/`) |
| --- | --- | --- |
| RT-08(d) corrected RED → GREEN | 20 failed → 20 passed, skip/xfail0 | `red-cancel-corrected.*` · `green-cancel-corrected.*` |
| RT-08(d/c)·Case command/stop·Worker checkpoint·Runtime cancel targeted | 174 passed, skip/xfail0, 50.17초 | `targeted-verified.*` |
| API·Worker·Case 비MySQL 회귀 | 681 passed / 기존 영상 부재 2 skipped / MySQL 281 deselected, 87.92초 | `api-worker-case-regression.txt` · `regression.xml` |
| strict gate unit 전체 | 4583 passed, skip/xfail0, 167.87초 | `gate-unit.*` |
| 실제 MySQL 8.4.7 전체 acceptance | **683 tests / 2049 phases 모두 PASS, skip0/xfail0/failure0**, nested JUnit 395.895초 | `mysql-acceptance-tmp/test_actual_report_rejects_eac0/mysql.json` · `mysql.xml` |
| 실제 JSON/JUnit strict CLI gate | PASS, 683 tests | `mysql-strict-gate.*` |
| 실제 parameter evidence mutation | **4034건 전부 거부**, RT-08(d) 19×13=247 포함 | nested `parameter-mutations.json` · `mutation-audit.json` |
| RT-08(d) 실제 metadata/family 누락 mutation | **76 / 6건 모두 거부** | nested `cancel-omissions.json` · `mutation-audit.json` |
| 전체 MySQL+mutation outer acceptance | **1 passed, exit0**, pytest 496.43초. nested 제한900초 유지 | `mysql-acceptance.txt/json/xml` · command/result |
| boundary·Contract fixture·workflow 정적 검사 | PASS, 구조62/JSON26/의미104, workflow30분 파일 불변·nested900초·require·skip/xfail 거부 유지 | `boundary.*` · `contract-fixtures.*` · `static-policy.json` |

- 위 건수는 서로 겹치는 실행을 합산한 총계가 아니다. 실제 MySQL의 api_cancel parameter19·기존 api_commands17·timestamp_order35를 직접 확인했다. 전체 pytest는 미실행이며 과거 보존 전체 pytest/기존 MySQL664/이전 mutation3787 및 원격 PR #375 CI는 이번 직접 결과에 합산하지 않는다. 원격 develop을 후속 `git ls-remote`로 다시 조회해 기준 SHA 불변도 확인했다.
- **이번 서버 정리:** port13351과 정확한 새 datadir·MySQL8.4를 SQL로 검증하고, system4+이번 base schema1·다른 client0을 확인했다. 이번 `rt08d_test`만 DROP → system schema4 → SHUTDOWN ACK → observer close를 기록했다(`cleanup-sql.json`). 성공한 Windows 전체 listener inventory에서 port13351 listener0·소유 WSL launcher0, WSL socket/pidfile/listener0을 확인했다. 새 scratch의 로그·원본 JSON/JUnit·실패 실행은 보존하며 과거 서버·증거를 정리하지 않는다.
- **보존·범위 감사:** 기존 checkout의 HEAD·branch·status와 추적 파일 **1994개** SHA-256 불변(`original-checkout-audit.json`). baseline 대비 common/Worker/Case·Contract·Tech Spec·Baseline·Plan115개 불변, 최종 검증 전후 제품/테스트/gate 납품9개 소스 SHA 불변이다. 기존 RT-08(a)~(c) worktree와 과거 scratch/RAW/보존 증거는 읽기 또는 미접근 상태이며 쓰기·정리하지 않았다.
- **남은 병합 차단·위험:** 이번 직접 검증에서 미해결 코드/테스트 실패와 구현 중 검토의 actionable P1/P2는 확인되지 않았다. 후속 독립 재리뷰·이 미커밋 변경의 원격 Linux CI·Owner acceptance/최종 병합 판단은 아직 완료되지 않았다. COMMIT/응답 유실의 반영 불명, 협력적 중단 지연·진행 중 호출 비용, 기존 invalid historical row/clock step/EC2 clock discipline, 이전 health cleanup 실패 원인 미확정은 기존 비차단 위험으로 남긴다. 이번 dedicated health 및 전체 acceptance PASS가 과거 원인을 소급 확정하지 않는다.
- **RT-08 전체 판정:** d 배선의 로컬 acceptance 증거는 준비됐지만 독립 재리뷰·최종 acceptance 전이므로 **IN_PROGRESS · Refs #295 (RT-08(d))**를 유지한다. 기존 START_ANALYSIS timeline dependency·실제 adapter/reader 조립 한계도 미해결 후속으로 명시하며 이 slice의 성공으로 RT-08 전체 DONE/Closes #295를 주장하지 않는다. RT-11 media/다른 Owner의 새 의무는 이번에 구현하지 않는다.
- **독립 재리뷰 인계:** 변경 파일 **12개**(수정9·신규3) 전체 목록·미커밋 diff(신규 파일 포함)·SHA-256 manifest·verification summary를 같은 새 scratch에 제공한다. staging·커밋·푸시·PR 생성 없이 **독립 재리뷰 요청 가능한 상태**로 인계하며, merge 승인을 뜻하지 않는다. 최종 `git diff --check`, 신규 파일 whitespace, HEAD/branch·staging0과 manifest를 직접 대조한다.


### 2026-10-18 RT-08(d) 최종 독립 재리뷰 후속

**Status: IN_PROGRESS · Refs #295 (RT-08(d)) · PR pending · merge SHA pending.** 아래는 사용자 요청에 따라 수행한 최종 독립 재리뷰 결과의 후속 기록이다. 앞선 구현·구현 중 리뷰·독립 재리뷰 대기 기록은 당시 이력으로 보존한다.

- **독립성·최종 판정:** 구현과 이전 구현 중 리뷰에 참여하지 않은 fresh reviewer `/root/rt08d_final_independent_review`가 현재 미커밋 12개 전체와 승인 문서·보존 증거를 읽기 전용으로 검토했다. **fresh reviewer PASS — RT-08(d)에 추가 actionable P1/P2 없음. RT-08(d) 커밋·중간 PR 생성 가능**으로 판정했다. 구현자의 자체 점검이나 `/root/rt08d_readonly_review`의 구현 중 검토로 대체하지 않았다. 이는 실제 커밋·PR 생성·원격 CI·병합 완료 또는 RT-08 전체 acceptance 판정이 아니다.
- **transaction·중단·범위:** Case가 반환한 대상만 같은 Connection/transaction의 기존 `request_cancel`에 전달하고, Case 선잠금·저장 → cancel → 기존 enqueue → COMMIT ACK 뒤 응답을 유지한다. revision 기반 중복·동시 요청, 최초 marker·ownership fence·checkpoint·redelivery·늦은 결과 배제 및 #370 timestamp ordering 의미를 보존한다. precommit 의존성 오류503과 COMMIT 불명/예상 밖 오류500·비노출 정책을 유지한다. MySQL inventory·strict JSON/JUnit·evidence 누락 차단·workflow30분·nested900초·skip/xfail 거부에 완화가 없고 RT-11·새 Owner surface/callback 혼입도 없다는 판정이다.
- **reviewer 직접 실행:** 비MySQL API·Worker·Case 회귀 **681 passed / 기존 영상 부재2 skipped / MySQL281 deselected**, exit0, pytest126.44초; gate unit **4583 passed**, skip/xfail0, exit0, pytest412.74초; boundary 위반0 및 Contract 구조62/JSON26/의미104 PASS. 보존 실제 보고서에 현재 gate를 직접 실행해 JSON/JUnit PASS를 확인하고, RT-08(d) parameter247·metadata76·family6의 **329개 mutation을 새로 실행해 모두 거부**했다. 메모리 기반 dependency probe로 START_ANALYSIS의 필수 timeline 누락 RuntimeError도 직접 확인했다. 테스트 출력은 새 OS TEMP에만 생성했으며 저장소·기존 증거를 수정하지 않았다.
- **초기 reviewer 실행 실패 구분:** 초기 sandbox 실행2건은 fixture 오류가 반복되어 중단했고 exit1이었다. 별도 진단도 exit1이며 OS TEMP JUnit 쓰기 `PermissionError`를 확인했다. 완료된 정확한 집계가 없어 PASS 수치로 사용하지 않았고, 권한 문제를 해소한 위 직접 재실행 결과와 구분한다.
- **보존 증거 대조·미실행:** source12개·evidence85개·review.diff 해시가 일치했고, 구현 단계 RED20→GREEN20·targeted174·실제 MySQL683 tests/2049 phases(skip0/xfail0)·parameter mutation4034·metadata76/family6 및 nested395.895초/outer496.43초의 원본을 대조했다. 이는 reviewer가 실제 DB 경합·process interruption을 새 서버에서 다시 실행한 결과가 아니다. reviewer는 동일 소스/증거 해시·직접 관련 회귀·현재 gate 재검사에 근거해 전체 pytest와 fresh 전체 MySQL 반복은 필요하지 않다고 판단했다. **전체 pytest·fresh 전체 MySQL·현재 미커밋 변경의 원격 CI는 미실행**이며, 현재 변경의 원격 CI는 통상 병합 조건으로 남는다. PR #375의 원격 PASS는 현재 미커밋 변경의 CI로 전용하지 않는다.
- **RT-08 전체 완료 차단:** API composition이 START_ANALYSIS의 필수 `timelines`를 주입하지 않아 Case `command.py`139~140행에서 RuntimeError가 발생하는 기존 조립 공백이 있다. Case `start-analysis.md`의 composition root 주입 결정·HTTP Contract §9.1·Plan RT-08 목표/범위를 근거로 **RT-08 전체 DONE을 막는 기존 P2 공백**으로 판정했다. 이번 d diff의 신규 결함은 아니다. timeline 조립 해결 또는 authority가 확인한 범위 처리가 필요하며, 실제 Worker handler/ProducedReader·모듈 결과 persistence 조립은 Plan RT-10/Case 후속으로 구별한다. 이를 이유로 timeline 주입 공백을 자동으로 RT-08 밖으로 넘기지 않는다.
- **비차단 위험 유지:** COMMIT/응답 유실의 반영 불명, 협력적 중단 지연·진행 중 capability 비용, HINT_EXTRACT 중단 뒤 재개 제한, 기존 invalid historical row/clock step/EC2 clock discipline 및 이전 health cleanup 실패 원인 미확정은 유지한다. 이번 PASS가 과거 사건 원인을 소급 확정하거나 해당 한계를 해결했다는 뜻은 아니다.
- **상태·연결·이번 갱신 범위:** **IN_PROGRESS · Refs #295 (RT-08(d)) · PR 번호 pending · merge SHA pending**을 유지한다. 현 상태에서 **DONE·Closes #295 사용 금지**다. 이번에는 이 Log에만 후속 기록을 추가하며 코드·다른 문서·manifest·증거는 갱신하지 않는다. 보존 manifest는 재리뷰 당시 snapshot이며 이번 Log 후속 추가분을 포함한 새 manifest로 바꾸지 않는다. 테스트 재실행·staging·커밋·푸시·PR 생성 없이 `git diff --check`와 Log 외 파일 불변을 확인한다.

### 2026-10-18 PR #376 최종 병합·CI 후속 기록

- 앞선 RT-08(d)의 PR/merge SHA pending과 미커밋·독립 재리뷰 기록은 당시 이력으로 보존한다. 이번 RT-09 착수 시 GitHub metadata를 직접 조회해 **PR #376 병합 완료 · merge SHA `805f155fa9c66d71a290df4eeb4f405236c136b8` · boundary-check PASS · python-tests PASS**를 확인했다.
- 원격 근거: [PR #376](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/376), [boundary-check run 39102848770](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39102848770), [python-tests run 39102848947](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39102848947). 두 workflow는 completed/success다. 이번 RT-09 미커밋 변경의 원격 CI 결과로 전용하지 않는다. metadata 원본은 이번 scratch의 `pr376.json`에 보존했다.
- 이 후속은 PR(d) 병합 사실만 정정한다. START_ANALYSIS timeline 주입 공백과 RT-08 전체 DONE 판단은 Issue #295의 별도 후속으로 남는다.

## 2026-10-18 RT-09 — 첫 비동기 E2E

**Status: IN_PROGRESS · Refs #296 (RT-09) · PR pending · merge SHA pending.** staging·커밋·푸시·PR 생성 없이 독립 재리뷰 가능한 미커밋 상태를 준비한다.

### 기준·선행 조건·범위

- `git fetch origin develop`로 확인한 최신 기준은 `805f155fa9c66d71a290df4eeb4f405236c136b8`이다. PR #376, RT-08(b) PR #373·RT-08(c) PR #375와 #370 durable timestamp ordering(PR #371) ancestry를 직접 확인했다. 별도 managed worktree `C:/Users/cheol/.codex/worktrees/rt09-first-async-e2e/ktc4-chonnam-2`, 새 branch `codex/rt09-first-async-e2e`에서 작업한다.
- 확인 입력: 사용자 AGENTS 사실 기반 지침·root CLAUDE.md·docs 운영 규칙·Runtime Plan §4/RT-09/§6.1/§7/§12, HTTP Contract §5.3/§5.4/§7/§9.1, JobExecution/JobRecord·CaseView Contract, Accepted RD-01/RD-03/RD-05/RD-06/RD-19(#244~#250) 승격 규칙, Tech Spec §12.1~§12.5, Baseline §2.5/§9와 #370 ordering, Ops §6-1, 기존 Log 및 Case의 확정 `result-reflection.md`다.
- 선행 interface는 실제 코드와 기존 테스트로 확인했다: CaseStore MySQL/JobRecord append, Case `CommandResult.appended_job_records`, Runtime enqueue/read port/Worker loop, 기존 Worker `CaseReflector`, Case `reflection.reflect_execution(ExecutionOutcome, store, reader, timelines)` 및 execution_id idempotency가 준비돼 있다. Case 결정은 RT-09의 fake handler/reader 사용을 명시한다. 기존 surface를 그대로 소비하므로 새 Consult 모양·Owner 의무·Contract 변경이 없다.
- 진입은 HTTP `POST /cases`로 만든 Case에 기존 실패 검색 이력 fixture를 준비한 뒤 `RUN_NOTICE_ACTION(RETRY_SEARCH)`를 제출한다. Plan §4가 허용한 기존 append command+fixture 경로이며 START_ANALYSIS는 호출하지 않는다. fixture의 이전 job도 실제 enqueue→claim→FAILED→Case T2를 통해 receipt까지 정산해 startup redelivery와 섞이지 않게 한다.
- API composition·CaseTimelineSource·RecordingSequentialTimelineSource는 수정하지 않는다. 테스트의 `UnusedTimelines`는 timeline을 만들지 않고 호출되면 실패한다. timeline 공백 우회·실제 provider·upload·별도 process·RT-10 실제 handler 조립·RT-11 media·다른 Owner 영역 확장은 없다. Contract/Accepted Decision/Baseline 의미와 제품 소스는 기준 대비 불변이다.
- **동시 편집 충돌:** Issue #295 START_ANALYSIS 후속도 같은 Implementation Log를 수정할 수 있다. 병합 시 양쪽 후속 기록을 모두 보존하고 append 위치·상태 색인 충돌을 검토해야 한다. 기존 RT-08 기록을 삭제·덮어쓰거나 pending 당시 기록을 소급 성공으로 바꾸지 않는다.

### Implementation Notes

- **구현:** `tests/e2e_runtime/test_async_e2e.py` 1건과 테스트 전용 fixture/composition helper를 추가한다. 실제 FastAPI TestClient·API 조립·별도 Worker engine/thread·KindRegistry·기존 CaseReflector를 쓴다. fake capability/ProducedReader만 결과 참조와 후보 내용을 제공하며 결과 persistence/실제 capability의 RT-10 조립을 추가하지 않는다.
- **durable 관측:** HTTP 201 INTAKE → 실패 fixture → command 202 뒤 JobRecord 1개 append와 attempt1 QUEUED가 독립 connection에서 보임 → 별도 Worker claim RUNNING → handler 반환 후 T1 SUCCEEDED/produced/ended_at, Case SEARCHING·receipt 없음·polling 유지 → T2에서 Case 결과/processed_executions와 receipt가 같은 transaction 안에서만 보임 → ACK 뒤 후보/진행 DONE·running_jobs=[]다. 중간·최종 view는 매번 Runtime 내부 필드를 재귀적으로 거부한다.
- **transaction/ownership/trace:** 기존 caller-owned API commit, Case→Runtime T2 lock 순서, handler의 Worker pool connection 미보유, T1과 T2 분리 및 commit 전 Case/receipt 비가시성을 검증한다. queued_at=available_at ≤ started_at ≤ ended_at ≤ case_applied_at, read port attempt1 SUCCEEDED와 usage_refs=[]를 확인한다. 202 API access event·durable trace column·Worker started/completed event의 trace/case/job/execution 식별자가 이어진다. 기존 retry/fencing/협력적 중단/redelivery와 #370 구현은 수정하지 않는다.
- **strict evidence:** 독립 RT-09 check/parameter inventory를 추가하고 기존 checker의 필수 목록에 연결한다. 실제 MySQL nested 실행에 E2E 파일을 포함하고 신규 identity에 13종 JSON/JUnit 누락·실패/skip/xfail mutation과 metadata4종·family 전체 삭제 mutation을 적용한다. 기존 Case inventory·모든 acceptance·900초 nested·workflow30분·require/skip/xfail 거부는 유지한다.
- **Plan 대비:** 승인된 대체 command와 테스트 전용 helper를 사용한다. E2E source 외에 필수 evidence inventory/gate 회귀를 갱신했으며 제품 surface 변경은 없다. 새 정책이나 Baseline 숫자는 고정하지 않았다.
- **RED→GREEN:** corrected E2E RED는 `Worker loop never claimed` assertion(1 failed), Worker thread 시작 뒤 최종 `green-e2e-final`은 1 passed/skip0/xfail0이다. gate RED는 RT-09 family evidence 삭제를 거부하지 못하는 DID NOT RAISE(1 failed)였고 필수 identity를 추가했다. 최초 fixture 설정 타입 오류, 잘못된 candidate_review RUNNING 기대값, 진단기의 stage column 위치 오류에 따른 중간 실패도 원본으로 보존한다. 최종 candidate_review DONE은 기존 projection/fixture 의미다.
- **실행 증거:** 새 `.codex-scratch/rt09/`에 command/result·실패 원본·JSON/JUnit·`durable-stages.json`을 둔다. 아래 최종 직접 검증 표가 이번 실행 범위를 정하며 과거 Log의 전체 pytest/683 acceptance/4034 mutation은 합산하지 않는다.
- **검토:** requesting-code-review 스킬의 별도 읽기 검토자 `/root/rt09_implementation_review`는 핵심 코드/범위·RED/GREEN 원본에서 추가 actionable P1/P2를 확인하지 않았다. 테스트를 직접 재실행하지 않았고 sandbox Git diff 접근 및 이 Log 추가분은 검토하지 못했다. 구현 중 검토이며 최종 독립 재리뷰/원격 CI/Owner acceptance/병합 승인이 아니다.
- **비차단 위험:** 테스트의 T1 장벽은 main-loop reflection을 제어한다. 매우 느린 환경에서는 기본 15초 redelivery sweep이 장벽과 경합할 가능성이 있다(현재 직접 GREEN에서는 재현하지 않음). 기존 COMMIT/응답 유실의 반영 불명·협력적 취소 지연·historical row/clock step/EC2 clock discipline·과거 health cleanup 실패의 원인 미확정도 이 테스트가 해소하지 않는다. 실제 provider·다중 process·모듈 결과 persistence는 RT-10 이후 검증이다.
- **전체 pytest 판단:** 이번에는 제품 소스/Contract/의존성/workflow가 불변이고 테스트 조립·gate만 바뀌므로 관련 API/Worker/Case 회귀·전체 MySQL acceptance·전체 gate unit/실제 evidence mutation을 직접 실행한다. 전체 pytest와 미커밋 변경의 원격 Linux CI는 미실행으로 명시한다. PR #376 원격 PASS나 과거 전체 pytest를 현재 RT-09 직접 실행으로 표시하지 않는다.

### RT-09 직접 검증 중간 기록 — 최초 전체 acceptance timeout

- `green-e2e-final`: 1 passed, skip0/xfail0, pytest3.51초. `targeted`: 238 passed, pytest416.22초. `gate-unit`: 4595 passed, pytest403.49초. `regression`: 681 passed/기존 영상 부재2 skipped/MySQL281 deselected, pytest103.47초. 각 원본은 이번 scratch에만 생성했다.
- `mysql-acceptance`: **1 failed**, nested subprocess가 기존 **900초 timeout**, outer pytest900.54초/runner903.266초. 완전한 nested JSON/JUnit은 생성되지 않았고 실제 보고서 gate·mutation 본문까지 도달하지 않았다. 이 실행을 PASS로 재분류하거나 과거683 보고서로 대체하지 않는다. 종료 뒤 이번 실행의 테스트 자식 프로세스가 남지 않은 것을 확인했다.
- 현재 DB SELECT1 50회 읽기 표본의 median0초(측정 해상도 이내)/max0.016초를 보존했다. 이 표본은 전체 timeout의 원인 증거가 아니다. Python3.12.14·pytest plugin anyio만 있음을 확인했으나 환경 문제/제품 문제로 단정하지 않는다.
- 같은 MySQL inventory를 `-vv --durations=20 -o faulthandler_timeout=60` 진단 출력과 별도 **900초 hard limit**으로 재실행 중이다. 테스트/gate7개 소스 해시는 고정하고 제품/정책/900초/workflow를 변경하지 않는다. 완성된 실행·strict CLI·evidence mutation 결과는 후속에 구분해 기록한다. 현재 전체 acceptance 미완료와 최초 timeout은 병합 판단의 미해결 검증 항목이다.

### RT-09 최종 직접 검증·보존 증거 구분·인계

| 구분 | 실행/증거 | 결과 |
| --- | --- | --- |
| 직접 실행 | corrected E2E RED → GREEN | Worker 미시작1 failed → 1 passed, skip0/xfail0, 최종3.51초 |
| 직접 실행 | 관련 API·Worker·Case T2/read port·redelivery·#370 targeted | 238 passed/skip0/xfail0, 416.22초. 이 중 실제 MySQL8.4.7은219 tests/657 phases 모두 PASS |
| 직접 실행 | JSON/JUnit strict gate unit 전체 | 4595 passed, 403.49초. 최초 gate RED의 RT-09 family 누락 거부 실패를 해소 |
| 직접 실행 | API·Worker·Case 비MySQL 회귀 | 681 passed/기존 영상 부재2 skipped/MySQL281 deselected, 103.47초 |
| 직접 실행 실패 | fresh 전체 MySQL outer acceptance | 900초 nested timeout, outer1 failed/900.54초, 완전한 nested JSON/JUnit 없음 |
| 직접 진단 실행 실패 | 같은684 inventory + verbose/durations/60초 stack 진단 | 별도900초 hard timeout/runner900.157초, 출력상92% 구간까지 진행. 완전한 JSON/JUnit 없음. 최초 실패를 해결·성공으로 재분류하지 않음 |
| 직접 실행 | boundary·Contract fixture·workflow/범위 감사 | 위반0, 구조62/JSON26/의미104 PASS. workflow30분·nested900초·MySQL require·제품/Contract/Plan/Baseline/의존성 불변 |
| 보존 입력을 이용한 별도 직접 검사 | RT-08(d)의 실제683 JSON/JUnit + 이번 RT-09 E2E1 합성 자료의 현재 strict CLI | PASS, 684 records. **fresh 전체684 통과가 아님** |
| 보존 입력을 이용한 별도 직접 검사 | 위 합성 자료에 현재 acceptance 테스트의 동일 mutation 본문 실행 | parameter4047 전부 거부(기존4034+RT-09 13), metadata/family87 전부 거부(기존82+RT-09 metadata4/family1) |

- **보존 출처·정확성:** 이전 RT-08(d) `mysql-acceptance-tmp/test_actual_report_rejects_eac0/mysql.json/xml`의 SHA-256을 원래 `evidence-manifest.json`과 대조해 일치한 사본만 읽었다. 원본은 복사 전후 해시 불변이다. 현재 E2E의 JSON/JUnit1건과 배열/실제 testcase를 합치되 결과를 새로 만들거나 phase를 재분류하지 않았다. `preserved-plus-rt09.json/xml`의 provenance와 `preserved-provenance.json`에 **historical683 + current1 / composite_not_single_current_run**을 명시했다. 원래 manifest 사본도 새 scratch에 둔다. 이 검사와 과거 PR #376 CI는 현재 fresh 전체 acceptance의 대체 증거가 아니다.
- **미완료·차단:** fresh 전체 MySQL의900초 내 통과, fresh 전체 보고서 기반 gate·mutation, 현재 미커밋 diff의 원격 Linux CI는 미확인이다. 두 timeout의 원인을 환경/제품/RT-09로 단정하지 않는다. 이번 진단 재실행은 계속 진행하는 PASSED 출력을 남겼지만 complete phase evidence가 없어 전체 성공 판정은 불가능하다. **병합 보류**다. 제한/필수 inventory를 낮추거나 테스트를 빼지 않았고, 추가 전체 반복 대신 실패 원본과 별도 보존 입력 검사를 인계한다.
- **미실행:** 전체 pytest는 직접 실행하지 않았다. 과거 Log의 전체 pytest 수치를 이번 결과에 합산하거나 현재 source 실행으로 표시하지 않는다. PR #376의 원격 두 CI PASS는 별도 GitHub 조회 사실이다. RT-09 상태는 IN_PROGRESS/Refs #296이며 DONE/Closes를 사용하지 않는다.
- **정리:** 새 MySQL의 정확한8.4.7/datadir, 다른 client0·테스트 계정0, 두 timeout이 남긴 생성형 schema2+이번 base schema를 확인했다. 기존 owned harness의 SHUTDOWN·listener close·자기 UUID datadir 삭제와 launcher 종료가 exit0이다. 기존 서버/다른 worktree/과거 증거는 변경하거나 정리하지 않았다. 정리 관측기 최초 SQL wildcard 바인딩 오류는 실패 원본으로 남기고 parameter binding 수정 후 별도 `pre-cleanup-corrected` PASS를 확인했다.
- **durable·trace 최종 판정:** 승인된 HTTP command 발주→실제 Worker claim/handler1회→T1 SUCCEEDED→Case T2 원자적 반영→후보/진행 DONE·running_jobs=[]가 직접 E2E에서 확인된다. T1 뒤 T2 전 polling은 계속되고 receipt가 없다. T2 commit 전 Case/receipt는 독립 connection에서 모두 과거 상태다. read port attempt1 SUCCEEDED, API202 access와 Worker execution started/completed의 trace 연속성·내부 필드 비노출, 기존 causal timestamp 순서가 확인된다. 이 판정은 단독/targeted 범위이며 fresh 전체 acceptance PASS가 아니다.
- **재리뷰:** 납품8개 전체 목록·신규 파일 포함 `review.diff`·소스/주요 증거 SHA-256·RED/GREEN과 실패/보존 출처·verification summary를 `.codex-scratch/rt09/`에 제공한다. **독립 재리뷰 요청 가능**, 다만 병합 준비 완료·최종 독립 리뷰/Owner acceptance/CI 승인 판정은 아니다. 구현 중 읽기 검토의 한계와 비차단 T1 장벽/redelivery 경합 가능성, #295 START_ANALYSIS 후속 및 이 Log 동시 편집 충돌 가능성은 유지한다.
- **최종 경계:** 종료 시 원격 develop도 `805f155fa9c66d71a290df4eeb4f405236c136b8`로 재확인했다. staging·커밋·푸시·PR 생성 없이 HEAD/branch/index·금지 경로·원래 checkout clean 상태와 소스7개 검증 전후 해시, 최종 `git diff --check`·신규 파일 whitespace를 감사해 인계한다. 기존 기록은 삭제·덮어쓰지 않고 이 후속으로 사실/검증 범위를 정정한다.


### 2026-10-18 RT-09 timeout 조사·최종 독립 재리뷰 후속

- **현재 상태·연결:** **IN_PROGRESS · Refs #296 (RT-09) · PR pending · merge SHA pending.** 앞선 timeout·fresh 전체 미완료·재리뷰 대기 기록은 당시 이력으로 보존한다. 아래는 그 이후 조사·최종 독립 재리뷰에서 확인한 결과이며, 기존 실패를 소급 PASS로 재분류하지 않는다. 현재 변경의 원격 **CI(MySQL) PASS 전에는 실제 merge·DONE·Closes #296 불가**다. DONE·Closes #296를 사용하지 않는다.
- **최종 독립 재리뷰:** 구현과 timeout 조사에 참여하지 않은 fresh reviewer `/root/rt09_final_fresh_readonly_review`를 대화 이력 상속 없이 호출했다. reviewer가 현재 미커밋 납품 8개 전체와 Contract·Accepted Decision·Baseline·Plan, 원본·조사 증거를 읽기 전용으로 검토했으며 **추가 조치가 필요한 P1/P2 코드 결함을 발견하지 못했다**. 구현자의 자체 점검이나 앞선 구현 중 검토로 대체하지 않았다.
- **reviewer 직접 검증:** 소스8·기존 증거110·조사 증거208 SHA-256 및 조사 시작 시 tracked2001개를 직접 대조해 불변을 확인했다. AST7·git diff --check, branch/base·staging0, 현재 checker의 fresh JSON/JUnit strict CLI가 PASS했다. RT-09의 13종 layer + metadata4 + family1, 총18종 변이를 메모리에서 직접 실행해 모두 거부했다. Issue #296도 직접 조회해 CI(MySQL) PASS가 실제 acceptance 조건임을 확인했다. 이 직접 검증과 아래 보존 실행 결과는 구분한다.
- **구현 단계 직접 실행의 보존 증거:** 단독 E2E1·targeted238·gate unit4595·비MySQL 회귀681 PASS/기존 영상 부재2 skip은 구현 단계의 실행 결과다. reviewer가 pytest로 다시 실행한 결과가 아니다. 과거 RT-08(d)683 + RT-09 단독1 composite의 통과는 보존 입력 검사이며, 다음 fresh 전체 실행의 대체 증거로 사용하지 않았다.
- **timeout 조사 단계 직접 실행의 보존 증거:** collection에서 기존683개의 삭제·순서 변경 없이 맨 앞 RT-09 E2E1개만 추가됨을 확인했다. 고정 부분 probe14개가 PASS했고, 기존683개를 신규1개와 분리한 수정 shard228/228/227개가 모두 PASS했다(ordered union683·2049 phases). 진단 runner의 binary/lib 환경 누락으로 첫228개 shard가227 PASS/1 FAIL이었던 원본도 보존하고, 환경만 보완한 동일 shard의 PASS를 별도 기록했다. 이는 제품 수정 RED→GREEN이 아니다.
- **최종 fresh 전체 MySQL·strict gate·mutation:** 환경 대조 뒤 과거 tmpfs 검증 환경을 복원하고 현재 소스에서 최종 전체 acceptance를 **정확히1회** 실행했다. 실제 MySQL8.4.7에서 **684개 / 2,052 phases / JUnit355.625초 PASS**, skip0/xfail0이며 parent pytest466.17초·runner467.907초·exit0이다. 완전한 성공 JSON/JUnit 뒤 **strict gate PASS**, **parameter4,047건·cancel omission82건·async omission5건 모두 거부**를 확인했다. reviewer는 원본 보고서·명령·종료 출력·mutation 배열과 shard 순서를 직접 대조했으며 4,047건 전체를 재실행한 것은 아니다.
- **두 timeout 최종 분류:** 첫 runner903.266초와 두 번째 hard timeout900.157초의 실패 원본은 그대로 보존한다. 첫 실행의 child stdout·정확한 마지막 node는 복구 불가다. 두 번째는 redelivery `test_fault_isolation_next_candidate_and_next_cycle[filter]` 완료(636번째) 후 `[handler]` 진입(637번째)에서 출력이 끝났다. **C형 환경 지연을 재현한 것으로 분류**한다. 동일 API8개의 disk/tmpfs 교차 시간8.644/4.158초, InnoDB log I/O wait 증가량4.090817/0.040553초가 원시 counter와 일치했다. **tmpfs 누락이 과거 두 timeout의 주요 원인이라는 판단은 추정**이며, 당시 node별 timestamp·DB/host counter가 없어 유일한 원인으로 소급 확정하지 않는다. **특정 node 교착·RT-09 누수/오염·제품 결함은 입증되지 않았고, 제품 결함을 수정했다거나 일반 disk에서900초 내 통과한다는 보장도 하지 않는다.**
- **E2E·범위·정책 판정:** POST /cases201 → 승인된 RETRY_SEARCH command202 → durable JobRecord/QUEUED → 별도 engine/thread Worker claim·fake handler1회 → T1 SUCCEEDED → T2 Case/receipt 반영 → progress DONE·running_jobs=[]를 확인했다. T1/T2 사이 polling·T2 commit 전 결과 비가시성·Case→Runtime 잠금/transaction 경계·API→Worker event trace·read port attempt1 SUCCEEDED·외부 Runtime 내부 필드 비노출을 검토했다. 제품/API composition·Case timeline source·Contract 의미는 불변이고 START_ANALYSIS 공백 우회·실제 provider/upload/별도 process·RT-10/11 혼입은 없다. workflow30분·nested900초·필수 inventory·JSON/JUnit metadata/family/parameter 요구·skip/xfail 거부를 완화하지 않았다.
- **CI와 미실행 범위:** 실제 `.github/workflows/python-tests.yml`의 MySQL service에는 tmpfs/mount 설정이 없어 로컬 tmpfs 성공과 **원격 CI 환경 동등성은 미확인**이다. tmpfs 자체가 Contract/Plan의 필수라는 근거는 없으므로 부재 자체를 정책 위반으로 판단하지 않는다. 현재 RT-09 변경의 원격 CI(MySQL) PASS는 아직 미확인이고 PR #376의 CI PASS로 대체할 수 없다. 전체 pytest와 현재 변경의 원격 CI는 미실행이다. reviewer도 전체 MySQL/전체 pytest를 반복하지 않았다. 현재 해시의 완전한 fresh 성공 자료와 독립 검사에 모순이 없고 같은 로컬 반복으로 원격 CI acceptance를 해소할 수 없다는 판단이다. Deferred Owner Review는 merge 전 추가 승인 gate가 아니다.
- **비차단 위험·자원 정리:** 느린 환경에서 T1 장벽과 기본15초 periodic redelivery의 경합 가능성(미재현), #295 START_ANALYSIS 후속과 이 Log의 동시 편집 충돌을 유지한다. 진단 tmpfs helper는 shutdown 뒤 cleanup shell exit32와 일시적 mount 잔여를 남겼으며, 이후 경로 소멸 원인은 미확정이다. 처음부터 자동 정리가 성공했다고 기록하지 않는다. 조사 종료의 독립 관측에서는 생성한 process·connection·schema·test account·lock·mount·directory·listener **잔여0**을 확인했고 기존 native MySQL 서비스는 유지했다. 이는 제품에 포함되지 않는 진단 helper의 비차단 한계다. 이번 Log 갱신에서 테스트나 자원 검사를 재실행한 것은 아니다.
- **커밋·PR 준비와 남은 차단:** 독립 reviewer는 **납품 소스8개를 명시적으로 선별한 커밋과 Refs #296 draft PR 준비 가능**으로 판정했다. PR에는 Implementation Notes와 최신 검증 출처·원격 CI 미확인을 명시하고 `.codex-scratch/rt09/`, `.codex-scratch/rt09-timeout-investigation/`의 보고서·진단 helper·임시 자료는 제외한다. 이는 실제 생성 또는 merge 허가 완료 기록이 아니다. **원격 CI(MySQL) PASS 전까지 merge·DONE·Closes #296는 보류**하며 상태·연결·PR/merge SHA pending을 유지한다.
- **후속 증거·이번 변경 경계:** 조사 자료는 `.codex-scratch/rt09-timeout-investigation/`의 `investigation-report.md`, `final-verification.json`, `storage-crossover.json`, `resource-cleanup.json`과 manifest에 보존돼 있다. 최종 reviewer의 직접 결과는 해당 독립 리뷰 응답이며 별도 파일을 만들지 않았다. 재리뷰 시점까지 납품8개와 원본 증거의 해시 불변을 확인한 사실과, 그 이후 **이 Log에만 추가하는 문서 후속**을 구분한다. 기존 source/evidence manifest는 당시 snapshot으로 보존하며 이 후속의 Log 해시로 덮어쓰지 않는다. 이번 작업은 기존 이력의 바이트를 보존한 append뿐이다. 다른 파일·코드·문서·branch·index를 변경하지 않고 테스트 재실행·staging·커밋·푸시·PR 생성 없이 `git diff --check`와 작업 전후 파일 해시 비교만 수행한다.


## 2026-10-19 RT-08 START_ANALYSIS timeline 후속

**Status: IN_PROGRESS · Refs #295 (RT-08 START_ANALYSIS follow-up) · PR pending · merge SHA pending.** 기존 RT-08/RT-09 기록은 당시 이력으로 보존한다. 이번 기록은 시간순 append이며 DONE 또는 Issue close 판정이 아니다.

### 기준 · 원격 선행 확인 · Owner 합의

- `git fetch origin develop`로 최신 `2703e6d47d997b2534314747958fd1b7901c3cbf`를 확인하고 아래 두 merge SHA의 ancestry를 직접 검사했다. 별도 managed worktree `C:/Users/cheol/.codex/worktrees/rt08-start-analysis-timeline/ktc4-chonnam-2`, 새 branch `codex/rt08-start-analysis-timeline`에서 작업하며 staging·커밋·푸시·PR 생성은 하지 않는다.
- [PR #376](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/376): develop에 MERGED, merge SHA `805f155fa9c66d71a290df4eeb4f405236c136b8`. PR head의 [boundary-check](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39102848770)·[python-tests](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39102848947) 및 merge SHA의 [boundary-check](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39107340108)·[python-tests](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39107340096)가 completed/success다. 같은 merge SHA의 나머지 두 성공 run도 원본에 보존했다.
- [PR #377](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/377): develop에 MERGED, merge SHA `2703e6d47d997b2534314747958fd1b7901c3cbf`. PR head의 [boundary-check](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39124564030)·[python-tests](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39124563959) 및 merge SHA의 [boundary-check](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39126633783)·[python-tests](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39126633749)가 completed/success다. 이전 RT-09 pending/로컬 실패 기록을 소급 덮어쓰지 않으며 두 PR의 원격 성공을 현재 diff의 CI로 전용하지 않는다.
- Issue #295의 [Case Owner 확인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/295#issuecomment-6251422507)과 [Runtime Owner 최종 경계](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/295#issuecomment-6251665965)를 원격 원본으로 확인했다. 기존 CaseTimelineSource/RecordingSequentialTimelineSource를 API에서 주입하고 두 HTTP 분기를 검증한다. Recording 영속·공유는 REC-1, 실제 원본 등록/Case 연결은 RT-11, 실제 Worker capability 조립은 RT-10이다.
- 확인 입력: 사용자 및 상위 `AGENTS.md` 사실 기반 지침(저장소에 별도 tracked AGENTS.md 없음), root CLAUDE.md/docs 운영 규칙, Runtime Plan RT-08/REC-1/§12, HTTP·JobExecution·JobRecord/CaseView Contract, Accepted RD-01/03/05/06/19 승격 문서, Case `start-analysis.md` §3-1/3-3/3-6/3-7 및 case-command 계약, Baseline B-D8/B-L6/§9, Tech Spec §12.1/12.5/13, #370 ordering 및 기존 Implementation Log를 대조했다.

### Implementation Notes

- **구현 결과:** `ApiComposition`이 인스턴스별 기존 `RecordingService`를 보유하고 `execute_command()`의 기존 caller transaction 안에서 `RecordingSequentialTimelineSource(self.recording)`를 `case_api.execute_command(..., timelines=...)`에 전달한다. Case 저장 → 기존 cancel → 기존 enqueue → COMMIT ACK 뒤 응답의 순서는 그대로다. budget 인자를 생략해 Case의 기존 `InitialSearchBudget()`를 사용한다.
- **Plan 대비 변경:** 기존 RT-08(a)~(d)에 누락된 START_ANALYSIS 조립을 Owner 합의에 따른 후속으로 연결한다. 새 공개 port/interface·필수 callback, Case 제품 코드, HTTP schema/예외 매핑, common/Worker 코드, Contract/Accepted Decision/Baseline 의미 변경은 없다.
- **새 implementation detail:** RecordingService 수명은 API composition 인스턴스 단위다. 요청마다 새 service/repository를 만들지 않는다. 테스트만 동일 service에 synthetic source+VIDEO media_stream을 등록하고 기존 Case aggregate에 연결해 MySQL fixture로 저장한다. /sources API나 durable/process-shared 복원은 구현하지 않는다. 이 새 절의 기록을 append-only implementation detail 색인으로 사용하며 앞선 색인은 덮어쓰지 않는다.
- **검증 구성:** 신규 실제 MySQL HTTP acceptance 16건: atomicity2·rollback4·dependency2·COMMIT 불명2·중복/동시4·응답 유실2. 정상 분기는 기존 Case 저장과 enqueue의 같은 Connection, Case 선잠금, caller 내부 가시성 및 독립 connection의 COMMIT 전 비가시성, ACK 뒤 저장·JobRecord/QUEUED·202/Location/Case body를 검증한다. COARSE_SEARCH는 실제 `timeline_for(case.sources)`와 동일 RecordingService의 timeline·기본 budget을 검증한다. HINT_EXTRACT는 timeline 호출0이다.
- **gate:** 독립 acceptance inventory를 추가하고 strict checker의 필수 role/scenario6·parameter16을 확장했다. 기존 inventory 삭제 없이 실제 JSON/JUnit parameter 13-layer(누락·skip·xfail·실패 포함), metadata4 및 family 전체 누락 mutation을 추가한다. workflow30분·nested900초·필수 inventory·skip/xfail 거부는 유지한다. 기존 command spy는 새 optional keyword를 원래 Case 함수로 전달하도록 조정한다.
- **RED→GREEN 직접 실행:** 기존 기준 command/timeline30 PASS. 초기 fixture `manifest_summary` 구성 오류2 ERROR는 `red.*`에 보존하며 제품 RED로 세지 않는다. 초기 신규 HTTP2 FAIL(500 vs202) 뒤 배선과 테스트 관측 오류(stage 별도 column, budget 중첩, get_case API)를 수정했다. 최종 테스트 그대로 주입만 제거→복원한 재검증은 RED2 FAIL → GREEN2 PASS, source bytes 복원 확인(`finalized-red-green.json`). 확장 HTTP16 PASS(`branches.*`). gate 신규 family omission은 RED6 FAIL(DID NOT RAISE) → GREEN6 PASS(`gate-red/green.*`).
- **현재 검증 진행:** 전체 pytest를 실제 MySQL8.4 전용 tmpfs 서버와 실행 중이다. API에서 보유하는 RecordingService 초기화와 gate 확장의 영향을 확인하기 위해 전체 회귀를 선택했다. 1800초 parent·900초 nested를 유지하며 과거 실행 결과를 합산하지 않는다. 전체 결과·strict gate·mutation·독립 재리뷰는 완료 후 시간순 후속에 기록한다. boundary 위반0, Contract 구조62/JSON26/의미104 PASS를 직접 확인했다.
- **남은 차단 · 위험:** 현재 diff의 원격 CI와 최종 독립 재리뷰는 미완료다. RT-08 전체 DONE 및 최종 PR에서 Closes #295 사용은 아직 불가하다. Recording 비영속성/서비스 재생성의 UNKNOWN_REF·VIDEO 스트림 부재 TimelineUnavailable은 기존대로500이며 새4xx를 만들지 않는다. Recording 타임라인은 MySQL Case transaction에 참여하지 않아 rollback 뒤 고아 timeline이 남을 수 있다는 Case 결정 §3-1 한계5는 유지한다. precommit503/COMMIT 불명500/응답 유실의 반영 불명, 협력적 중단·기존 clock/ordering 운영 한계도 해결했다고 주장하지 않는다.
- **증거 위치:** 이번 worktree의 `.codex-scratch/rt08-timeline/`. PR/Owner 원본 JSON, RED/GREEN 원본·JUnit·MySQL JSON, 전체 실행 명령/소스 해시·원본 출력, boundary/fixture 결과를 보존한다. 이전 worktree의 증거는 현재 직접 결과로 재분류하거나 갱신하지 않는다.


### 2026-10-19 RT-08 START_ANALYSIS 직접 검증 완료 후속

**Status: IN_PROGRESS · Refs #295 (RT-08 START_ANALYSIS follow-up) · PR pending · merge SHA pending.** 위 실행 중 기록은 당시 이력으로 보존한다. 아래는 이번 소스에서 직접 완료한 결과이며 과거 RT-08(d)/RT-09 보고서를 재사용한 결과가 아니다.

| 직접 실행 | 결과 | 이번 원본 증거 (`.codex-scratch/rt08-timeline/`) |
| --- | --- | --- |
| 최종 정상 HTTP RED→GREEN | 주입 제거2 FAIL(500 vs202) → 복원2 PASS, source bytes 복원 | `finalized-red/green.txt/xml`, `finalized-red-green.json` |
| 신규 HTTP 경계 전체 | 16 PASS | `branches.txt/json/xml` |
| gate family RED→GREEN | 누락 허용6 FAIL → 필수 목록 확장6 PASS | `gate-red/green.txt/xml` |
| 전체 pytest | **7,980 PASS / 26 SKIP / 실패0 / xfail0**, exit0; pytest1304.70초, runner1310.875초 | `full.txt/json/xml`, `full-command.json`, `full-result.json` |
| 전체 실행의 실제 MySQL | **705 tests / 2,115 phases 전부 PASS**, MySQL8.4.7, skip0/xfail0, strict JSON/JUnit CLI PASS | `full-strict-gate.txt`, `verification-summary.json` |
| nested 전체 MySQL | **700 tests / 2,100 phases 전부 PASS**, MySQL8.4.7, JUnit371.461초, skip0/xfail0, strict JSON/JUnit CLI PASS | `full-tmp/test_actual_report_rejects_eac0/mysql.json/xml`, `nested-strict-gate.txt` |
| 실제 보고서 parameter mutation | **4,255건 모두 거부**, 그중 신규 START_ANALYSIS208건(16×13 layers) | nested `parameter-mutations.json`, `fresh-mutation-summary.json` |
| 실제 보고서 metadata/family omission | 기존 cancel82·async E2E5 및 신규 START_ANALYSIS70(64 metadata+6 family) 전부 거부 | nested `cancel/async-e2e/start-analysis-omissions.json` |
| boundary·Contract fixture | 위반0, 구조62/JSON26/의미104 PASS | `boundary.txt`, `contract-fixtures.txt` |
| 정책·diff | workflow30분/nested900초 유지, 기존 inventory 삭제0, checker 모든 함수 AST 불변, `git diff --check` PASS, staging0 | `static-policy.json`, `gate-policy-delta.json` |

- **집계 범위:** 위 실행은 서로 겹치므로 건수를 합산하지 않는다. 전체 pytest의 API193 PASS·Case502 PASS/영상부재2 SKIP·Worker283 PASS·gate unit4,777 PASS·RT-09 E2E1 PASS를 JUnit에서 확인했다(`scope-regression-summary.json`). 전체 MySQL705는 nested700에 기존 Case read-port2/T2 reflection2와 outer gate1을 더 포함한다(`full-nested-inventory-delta.json`). outer acceptance 자체도520.469초 PASS다. 기존 command17·cancel19·timestamp ordering 및 Worker fence/복구 경계와 신규 START_ANALYSIS16이 현재 실제 보고서에 함께 있다.
- **skip·warning 구분:** 비MySQL SKIP26은 Search CLI collection의 `typer` 미설치4, 기존 Case 영상 부재2, Eval 로컬 미디어/라벨 부재5, Recording 실제 영상·pair·VIDEO_INDEX opt-in 부재15다. 상세 node/reason은 `full.txt/xml`과 `verification-summary.json`에 보존했다. MySQL skip/xfail은 두 보고서 모두0이며 정책을 완화하지 않았다. 기존 baseline에서도 관측된 Starlette TestClient deprecation warning1은 수정 범위 밖으로 유지한다. 미디어·해당 CLI 경로까지 실행됐다고 주장하지 않는다.
- **환경·불변 확인:** Python3.12.14와 주요 의존성9종이 현재 uv.lock 버전과 일치한다(`execution-environment.json`). 검증 전후 제품/테스트/gate7개 SHA-256 불변을 runner가 확인했다. Linux CI와 완전히 같은 환경이라고 주장하지 않는다. 종료 시 `git ls-remote origin refs/heads/develop`도 `2703e6d47d997b2534314747958fd1b7901c3cbf`로 확인했다. HEAD는 같은 기준이고 새 branch를 유지하며 커밋·staging·푸시·PR 생성이 없다.
- **보존 증거와 reviewer 실행 구분:** 구현자가 이번에 직접 실행한 원본을 모두 새 scratch에 보존했다. 초기 fixture/관측 실패는 원본 그대로 남기며 최종 RED→GREEN/전체 PASS로 소급 바꾸지 않는다. 과거 RT-08(d)/RT-09의 MySQL 보고서나 composite를 이번 PASS의 대체로 사용하지 않았다. fresh reviewer는 코드 diff8개를 직접 읽고 현재 nested JSON/JUnit strict CLI·소스 해시·gate AST·inventory 보존을 독립 확인했으며 추가 P1/P2가 없다는 중간 판정을 내렸다. pytest를 다시 실행한 것으로 표시하지 않는다. 전체 결과와 최종 mutation 증거에 대한 reviewer 후속 판정은 다음 기록에 남긴다.
- **전용 자원 정리와 초기 실패:** 전용 MySQL의 정확한8.4.7/datadir/port, 다른 client0·테스트 계정0, system4+이번 base schema1만 남음을 확인하고 init/server 로그를 복사했다(`pre-cleanup.json`, `mysql-init/server.log`). 종료 helper는 cleanup shell exit32로 최종 exit1이었다. 이를 자동 cleanup PASS로 바꾸지 않는다. 후속 별도 WSL 관측에서 UUID 경로·mount·process·listener가 없고, 성공한 Windows 전체 listener inventory에서 port65113 listener0·이번 launcher0임을 확인했다(`cleanup-diagnostic.txt`, `resource-cleanup.json`). **초기 cleanup 오류 및 그 뒤 경로 소멸 원인은 미확정**이며 제품 테스트 실패와 구분한다. 기존 서버·다른 worktree·과거 증거를 정리하지 않았다.
- **남은 병합 차단:** 현재 diff의 원격 CI와 후속 PR 병합/RT-08 전체 acceptance가 남아 있다. 로컬 코드/필수 테스트의 미해결 실패는 확인되지 않았다. 비MySQL 미실행26건과 helper cleanup 초기 실패의 원인 미확정, 기존 Recording 비영속성·고아 timeline·COMMIT/응답 유실 의미는 비차단 한계로 명시한다. **IN_PROGRESS 및 Refs #295를 유지하며 현 상태에서 RT-08 DONE/최종 PR의 Closes #295 사용은 불가**다.


### 2026-10-19 RT-08 START_ANALYSIS 최종 독립 재리뷰 후속

- **현재 상태:** **IN_PROGRESS · Refs #295 (RT-08 START_ANALYSIS follow-up) · PR pending · merge SHA pending.** 구현에 참여하지 않은 fresh reviewer `/root/rt08_timeline_fresh_review`가 대화 이력 상속 없이 코드 diff8개(신규2개 포함), Owner 합의·Contract·Accepted Decision·Baseline·Plan, 이번 직접 실행 원본을 읽기 전용으로 검토했다. **최종 추가 actionable P1/P2 없음, 수정 요청 없음**이다. 앞선 구현 중/실행 중 기록은 그대로 보존한다.
- **판정:** 기존 RecordingService/RecordingSequentialTimelineSource 조립과 두 분기, budget 생략, Case 저장→cancel→enqueue→COMMIT 순서와 오류 의미를 보존한다. Case 제품 코드·새 interface·schema/예외 우회·REC-1/RT-10/RT-11 범위 혼입이 없고, 기존 inventory·checker 함수·workflow30분/nested900초·MySQL skip/xfail 거부 정책에 완화가 없다는 판정이다.
- **reviewer 직접 검증:** 현재 full/nested strict JSON/JUnit checker CLI PASS, 제품/테스트/gate7개 소스 해시·기존 inventory·diff-check·staging0 대조, 실제 nested 보고서의 신규 layer208·metadata64·family6 **총278개 mutation을 직접 실행해 모두 거부**했다. 구현자가 보존한 전체 parameter4255·cancel82·async5·신규 omission70 배열의 결과도 대조했다. reviewer는 전체 pytest/전체 MySQL을 새 서버에서 반복 실행하지 않았다.
- **검증 출처:** reviewer가 구현자의 현재 full 원본에서7980 PASS/26 SKIP/실패0, MySQL705/2115 phases·nested700/2100 phases 전부 PASS와 API193·Case502·Worker283·gate4777·RT-09 E2E1을 직접 대조했다. 이는 reviewer 자신의 pytest 재실행 결과가 아니다. 최종 소스7개는 실행/리뷰 해시와 일치하고, Log만 검증·리뷰 사실을 시간순 append한다. 원본 보고서와 이전 review snapshot은 덮어쓰지 않는다.
- **비차단 한계·제외:** 비MySQL26 skip의 외부 미디어/라벨/opt-in 및 typer 부재, 기존 Recording 비영속성·VIDEO 부재500·rollback 뒤 고아 timeline, COMMIT/응답 유실 의미를 유지한다. cleanup shell32/launcher1 초기 실패와 이후 별도 잔여0 자료도 확인해 제품 밖 진단 helper의 비차단 한계로 분류하는 데 동의했다. reviewer가 OS 자원을 새로 관측한 것은 아니며 원인 미확정도 그대로다. Windows 로컬 결과는 원격 Linux CI를 대체하지 않는다.
- **남은 차단·종료:** 코드와 로컬 필수 검증의 미해결 차단은 없다. **현재 diff의 원격 CI·후속 PR merge·RT-08 전체 acceptance가 남아 있어 지금 RT-08 DONE/최종 PR의 Closes #295 사용은 불가**다. 기존 PR #376/#377 원격 CI를 현재 diff의 CI로 전용하지 않는다. 사용자 지시대로 별도 managed worktree와 새 branch에 변경8파일을 미커밋으로 남기며 staging·커밋·푸시·PR 생성 없이 종료한다.


## 2026-10-19 RT-08 종료 및 REC-1(a) 착수

### RT-08 종료 확인 (후속 기록)

- **RT-08 Status: DONE · PR #378 · merge SHA `1a4f2200a7af7a9ed86299574aaf123548cf58da` · Issue #295 CLOSED.** 기존 pending 기록은 당시 이력으로 보존한다. GitHub 원본을 이번 세션에서 직접 조회해 PR #378의 develop 병합과 boundary-check/python-tests SUCCESS를 확인했다. 이 원격 CI는 REC-1(a) 변경의 CI가 아니다. REC-1·RT-10·RT-11은 RT-08 완료를 막지 않는 후속 범위다.

### REC-1(a) Implementation Notes

**Status: IN_PROGRESS · Refs #302 (REC-1(a)) · PR pending · merge SHA pending.** REC-1 전체 완료 또는 Issue 종료 기록이 아니다.

- **기준:** 현재 checkout `C:/ktc4-chonnam-2`, 기존 branch `codex/rec1a-recording-mysql`, HEAD/원격 develop `1a4f2200a7af7a9ed86299574aaf123548cf58da`, 시작 시 tracked/untracked/staging 변경0을 직접 확인했다. 새 branch/worktree·staging·커밋·푸시·PR 생성 없이 작업한다. 기존 stash와 `.codex-scratch/main-checkout-recovery-20261019`는 수정/적용/삭제하지 않는다.
- **승인 범위:** 사용자 설계 확인과 추가 조건에 따라 SourceAsset·FrameRef·DerivedAsset의 identity/metadata와 기존 case/ref 연결을 이번 slice에서 모두 복원한다. 최종 공개 소유 조회와 DerivedAsset bytes/Content-Type은 REC-1(c), 등록 입력/Case 연결 조립은 REC-1(b)/RT-11이다. [구현 경계](../modules/recording/rec1a-persistence.md)에 acceptance와 대안을 제품 코드보다 먼저 기록했다.
- **구현 결과:** 기존 메서드 집합을 RecordingRepository Protocol로 추출하고 service/spans의 annotation만 바꾼다. 기본 in-memory 동작과 service 공개 함수는 유지한다. MySQLRecordingRepository는 호출자 Connection에서만 SQL을 실행하며 commit/rollback/retry/close를 수행하지 않는다. API/Worker composition은 변경하지 않는다.
- **새 implementation detail 색인:** Recording 소유 `recording_entry`는 kind+SHA-256 identity의 unique key, 순서 보존용 auto-increment ordinal, 기존 Contract JSON payload와 nullable LONGBLOB을 갖는다. ref 문자열의 대소문자/Unicode를 해석하지 않고 opaque identity로 저장한다. JSON에서 새 canonical 필드나 Contract를 만들지 않는다. SourceAsset/MediaStream/locator/stream index의 등록 및 FrameRef/position/bytes 저장은 각각 단일 InnoDB statement여서 후반 row의 SQL 실패에도 일부 row만 남지 않는다.
- **storage/복원:** 원본은 주입한 storage root의 파일을 그대로 읽는다. DB에는 검증된 상대 locator와 private fingerprint/stream index, root 일치 확인용 경로 digest만 저장하고 절대 경로는 저장하지 않는다. traversal/absolute/drive/backslash/escaping symlink·junction/다른 root를 거부한다. FrameRef 이미지 bytes는 metadata와 같은 DB transaction에 저장하며 파일 publication이 없다. DerivedAsset ref·metadata·case 연결은 DB에서 복원하지만 최종 bytes read capability를 추가하지 않는다.
- **transaction/잠금:** 조회를 포함해 transaction 수명은 caller가 소유한다. 같은 stream의 service resolve_frame은 MediaStream row FOR UPDATE로 직렬화하고 caller 종료까지 lock을 유지한다. 다른 stream을 전역 잠금하지 않는다. 오류는 SQLAlchemy DBAPI type·errno·disconnect 표시를 유지하며 SQL/params/driver detail을 제거한다. RT-02가 precommit dependency와 COMMIT 결과 불명을 기존대로 판정한다. COMMIT ACK 유실은 미반영 보장이 아니며 exactly-once를 주장하지 않는다.
- **migration:** 새 `migrations/recording/` 및 recording_alembic_version/recording_0001만 추가하고 공용 runner registry에 case→runtime→recording을 등록한다. 다른 module schema/frozen revision은 변경하지 않는다. MySQL DDL은 implicit commit이므로 forward-only downgrade 거부와 실패 뒤 부분 DDL/이전 revision·기존 데이터 보존을 구분해 검증한다.
- **Plan 대비 변경/Owner 확인:** 내부 schema/interface/FrameRef bytes 방식의 implementation detail 선택이다. Contract·Accepted Decision·Baseline 의미/값, Case/Runtime 새 공개 surface·의무 변경은 없다. 등록 실패 taxonomy·HTTP route·소유 조회 public API·DerivedAsset bytes/형식·retention/purge 정책·Object Storage·P-6·RT-10/11 조립은 제외한다. 기존 local IncidentClip materialization bytes 수명은 이번 adapter로 해결했다고 주장하지 않으며 완전한 media publication의 후속 acceptance로 남긴다.
- **RED→GREEN 직접 증거:** 실제 MySQL8.4.7 신규25건 RED25 FAIL(`red-final.*`) 뒤 adapter/migration을 작성했다. 처음 sandbox 접속 실패와 pytest temp 권한 오류는 별도 `red.*`/`red-actual.*`로 보존하고 제품 RED로 세지 않는다. 신규 adapter의 ordinal DDL 오류, Windows symlink 권한 오류, RemoteCopy 재등록 순서 및 inserted-row alias 오류도 원본을 보존했다. 핵심25+호환성2+기존 migration 회귀37은 targeted64 PASS, 실제 PNG/비커밋/fixture 호환성은 compat-green3 PASS다. 이 실행들은 중복 범위이며 합산하지 않는다.
- **gate:** 독립 Recording inventory와 checker의 필수 role/scenario/parameter를 추가했다. 누락을 허용하던 gate RED58 FAIL 및 추가 parameter RED6 FAIL을 먼저 확인했다. 모든 신규 parameter의 실제 JSON/JUnit13-layer·metadata4·family omission mutation을 nested acceptance에 추가하며 workflow30분/nested900초/기존 inventory/skip·xfail 거부 정책을 유지한다.
- **현재 검증:** boundary 위반0, Contract fixture 구조62/JSON26/의미104 PASS와 diff-check를 직접 확인했다. service 타입 경계와 공용 migration registry 영향 때문에 전체 pytest 및 실제 MySQL strict JSON/JUnit을 선택했다. 최종 gate/전체 회귀/독립 재리뷰/자원 정리 결과는 완료 후 별도 후속에 추가한다. 이전 작업의 PASS/보고서를 현재 결과로 전용하지 않는다.
- **증거:** `.codex-scratch/rec1a-20261019/`에 이번 원격 원본·RED/GREEN·실행 원본을 보존한다. 최종 원격 CI는 미실행이며 독립 리뷰/전체 검증/cleanup은 아직 완료 판정하지 않는다.


### 2026-10-19 REC-1(a) 전체 회귀 중간 결과와 호환성 수정

- 신규 테스트 이름이 기존 Jobs test_repository_mysql과 충돌한 최초 collection2 ERROR를 `full-collection-failure/`에 원본 보존하고 Recording 전용 파일명으로 고쳤다. 이 실패는 제품 RED나 PASS가 아니다.
- 첫 전체 실행은 **3 FAIL / 8,322 PASS / 26 SKIP**, runner1371.453초, 소스 해시 변경0이다(`full.*`, `full-command/result/source-hashes.json`). 두 실패는 Windows shutdown helper 환경변수2개 누락과 그로 인한 nested gate 실패였다. helper 설정 뒤 실제 별도 서버 shutdown/cleanup1 PASS를 직접 확인했다(`health-helper.*`). 정책/테스트를 완화하지 않았다.
- 세 번째 Usage legacy 재업그레이드 실패는 MigrationFailure.execution_failed이며 원래 원인은 이 출력에서 확인되지 않는다. standalone1 PASS와 같은 fault 파일15 PASS, 정상 서버 로그·tmpfs 여유/연결 정리를 관측했으나 **원인 확정이나 해결로 주장하지 않는다**. 최종 실행에서 재발하면 SQL/driver message 없이 exception type/errno/module만 수집하는 scratch 진단 hook을 사용한다. Usage/Runtime 제품 코드는 수정하지 않는다.
- 추가 실제 MySQL RED는 -0.0/0.0 frame 위치 불일치와 동일 instant의 다른 timezone 표현을 timeline 충돌로 오판한 2 FAIL이다(`edge-red2.*`). case ID 대소문자 negative는 PASS다. 정식 compatibility acceptance도 RED1 FAIL 뒤 좌표 key의 signed-zero 정규화와 immutable 모델 동등성 비교를 수정했다. Frame/span의 -0.0, 같은 aware instant, 내용 없는 frame 재등록 및 case ID case-sensitive 부정 검사를 정식28 inventory 안에 고정했다. 수정 후 Recording28 PASS(`final-acceptance.*`), schema/공개 함수/Owner 의무 변경은 없다.
- gate unit은5094 PASS(`gate-green.*`)다. 최종 소스 전체 pytest/실제 JSON·JUnit strict/mutation/독립 리뷰/cleanup은 이어서 실행하고 결과를 별도 후속에 추가한다. 실패한 전체/nested 원본은 삭제·덮어쓰기하거나 성공 자료와 합성하지 않는다.


### 2026-10-19 REC-1(a) 재개 · 독립 리뷰 수정 · 검증 실행 경계

- **Status: IN_PROGRESS · Refs #302 (REC-1(a)) · PR pending · merge SHA pending.** 사용량 중단 뒤 같은 branch/checkout에서 재개했다. 두 번째 전체 실행은 진단용 PYTEST_PLUGINS가 dependency 부재 검증 subprocess에 전파된 설정 실패와 nested Usage fixture의 DROP DATABASE 응답 시간 초과(2013, teardown ERROR)를 남겼다. 후속 서버 관측에서 해당 schema는 이미 없었지만 원래 client cleanup 오류를 PASS로 바꾸지 않는다. 호스트 중단과의 인과관계는 확인되지 않았다.
- **전체 재실행 중단:** 독립 리뷰에서 실제 호환성 결함을 발견했고 이미 실패한 전체 실행을77%에서 전용 PID/명령을 대조해 의도적으로 종료했다. `final-stop.json`, `final-result.json`의 exit4294967295·wall40089.875초·source 변경0, `final.txt`·진단 jsonl·nested 실패 JSON/JUnit을 보존한다. 이 실행은 완료/PASS가 아니며 최종 outer JSON/JUnit이 생성됐다고 주장하지 않는다. 기존 첫 전체 결과와 합성하지 않는다. 세 번째 전체 pytest 대신 수정 범위의 Recording·API·Worker·Case·E2E 회귀 및 기존 전체 필수 MySQL을 포함하는 strict nested gate를 실행한다. 다른 기능 제품 코드는 바뀌지 않았고 중복 전체 실행으로 설정 실패를 해소할 수 없다는 판단이다.
- **fresh reviewer:** 구현에 참여하지 않은 `/root/rec1a_independent_review`가 대화 이력 없이 읽기 전용으로 조사해 GPS signed-zero 중복, GPS optional 필드 생략 보존, timezone-equivalent RemoteCopy 재등록 순서의 P2 세 건을 발견했다. 실제 MySQL scratch 재현3 FAIL(`review-red.*`) 뒤 full-default signed-zero identity와 exclude_unset payload 분리, 기존 RemoteCopy row 잠금/모델 비교/저장 표현 재사용으로 수정했다. 정식 compatibility.fixture acceptance에도 세 항목을 추가했다. 재현3+정식28은31 PASS(`review-green.*`)이며 겹치는 실행을 합산하지 않는다.
- **중간 재리뷰:** reviewer는 수정 코드·정식 assertion과 RED/GREEN 원본을 대조해 세 지적이 해소됐고 추가 코드 차단 사항이 없다고 판정했다. boundary0·Contract62/26/104·diff-check 및 checker 함수 AST/기존 inventory/workflow30분/nested900초/frozen migration 보존은 직접 검증했다. MySQL pytest는 reviewer가 직접 재실행한 것이 아니다. 동시 RemoteCopy 등록 전체의 순서 보장으로 확대하지 않으며 승인한 same-stream frame 경계만 검증한다. 최종 clean gate·소비자 회귀·자원 정리는 아직 완료 판정 전이다.
- **실행 환경 구분:** 별도 non-MySQL 소비자 회귀에서 미디어 예제 TEMPORARY_FAILURE를 관측했다. 같은 기존 예제 테스트의 일반 sandbox 실패(`example-probe.*`)와 권한 확장1 PASS(`example-escalated.*`)를 직접 대조했다. 제품 변경으로 해결했다고 주장하지 않고 해당 회귀 종료 후 필요한 재실행과 결과를 후속 기록한다.


### 2026-10-19 REC-1(a) 필수 검증 완료 · 전체 회귀 한계 · 자원 정리

**Status: IN_PROGRESS · Refs #302 (REC-1(a)) · PR pending · merge SHA pending.** REC-1 전체 DONE 또는 Closes #302가 아니다. 변경20파일 전체 목록과 최종 판정 경계는 `docs/modules/recording/rec1a-persistence.md`에 기록했다.

| 이번 작업 직접 실행 | 결과 · 원본 |
| --- | --- |
| 최종 Recording 실제 MySQL 및 리뷰 재현 | 정식28+재현3 =31 PASS / `review-green.*`; 리뷰 RED3 FAIL은 `review-red.*`로 별도 보존 |
| 전체 필수 실제 MySQL | MySQL8.4.7,728 PASS/2,184 passing phases, skip0/xfail0, JUnit883.700초 / `recovery-gate-tmp/test_actual_report_rejects_eac0/mysql.json+xml` |
| 원본 strict JSON/JUnit CLI | PASS728, 필수 inventory 충족 / `strict-final.txt` |
| 원본 mutation 코드의 별도 실행 | parameter4,619 모두 거부, Recording364 layer·112 metadata·9 family 거부; cancel82/async5/START_ANALYSIS70 유지 / `mutation-recovery/`, `mutation-recovery-command/result.json` |
| 소비자 non-MySQL 회귀 | 1,224 PASS/17 SKIP/2 FAIL, 326 deselected / `regression-clean.*`; Recording544 PASS/15 SKIP, Worker91 PASS, Case475 PASS/2 SKIP, API113 PASS/2 FAIL |
| boundary·Contract·정적 검사 | 위반0,62구조/26JSON/104의미 PASS; old inventory·checker 모든 함수 AST·workflow30분/nested900초·frozen migration·Log 원본 prefix 보존 / `boundary-final.txt`, `contracts-final.txt`, `static-final.json` |

- **집계와 실행 구분:** 위 실행들은 중복되므로 합산하지 않는다. 이번 세션의 이전 gate unit5094 PASS(`gate-green.*`)는 보존 원본으로 대조했고 checker/inventory는 그 뒤 변경하지 않았다. baseline PR #378 CI를 현재 diff의 결과로 사용하지 않는다. 현재 diff의 원격 CI는 미실행이다. 직접 실행한 결과와 reviewer가 원본을 대조한 결과를 구분한다.
- **aggregate timeout을 성공으로 바꾸지 않음:** scratch runner 자체1,200초 guard가 MySQL 성공 뒤 mutation 중 만료돼 exit124/1200.359초/source 변경0이었다(`recovery-gate-result.json`). 이 parent는 PASS가 아니다. 완전한728-test JSON/JUnit을 직접 strict 검증한 뒤 원래 gate 함수235–349행 AST suffix 전체를 기존 globals/기존 count assertions 그대로 실행해325.551초/exit0으로 마쳤다. subprocess 성공을 mock하거나 실행 보고서를 합성하지 않았다. input/source SHA와 AST SHA를 전후 대조했고 reviewer도 동일 AST를 직접 확인했다. workflow30분/nested900초 및 skip/xfail·inventory 정책은 변경하지 않았다. nested의 여유16.3초는 환경 성능 위험이다.
- **transaction·복원·migration 판정:** 호출자 Connection 비커밋/비롤백, rollback/uncommitted 비가시성, failed registration/frame 단일 statement 원자성, same-stream 동시 identity·다른 stream lock 경계, 실제1205/disconnect/비관련SQL 및 COMMIT OK 유실을 검증했다. lost ACK는 결과 불명이며 실제 committed ref가 복원돼도 모순이 아니다. 새 service의 SourceAsset/FrameRef 실제PNG/DerivedAsset metadata/case 관계 복원과 cross-case negative가 모두 정식28 안에 있다. fresh/기존 Case·Runtime revision upgrade/기존 데이터/재실행/metadata 정합성 및 forward-only downgrade 거부·실패한 부분DDL 보존도 포함한다. DB DML rollback을 MySQL DDL rollback 보장으로 확대하지 않는다.
- **전체 소비자 회귀는 GREEN 아님:** 기존5초 total-process API tests가 실패했다. 동일 파일 재검증43 PASS/2 FAIL, 실패 scenario 단독8 PASS/1 FAIL로 실제 server 종료 사례는 여전히5초를 넘었다. 기존 fake fatal case와 stalled composition 실패 대상은 일부 바뀌었다. API 코드·해당 테스트는 HEAD와 같고 새 adapter는 API composition에서 import되지 않는다. 네 변경 모듈만 HEAD 원문으로 읽은 가상 baseline과 현재 코드의 paired3회가 모두5초 timeout이었다(`api-head-comparison.json`). 추가 import loader가 있는 비교이므로 untouched HEAD pytest 결과로 표현하지 않는다. 별도20초 진단에서 원래 listener/port/composition/signal assertions는 현재6.963초·가상HEAD7.025초에 정상 종료했다(`api-lifecycle-timing.json`). 이는 원래5초 acceptance PASS나 정책 변경이 아니다. 환경/실행 시간 영향은 추론이고 정확한 원인은 미확정이다. API 의미/코드/timeout을 이번 slice에서 수정하지 않는다.
- **실패·자료 보존:** 최초 전체3 FAIL/8322 PASS/26 SKIP, 두 번째 전체77% 의도적 중단, sandbox 소비자 회귀의 환경 실패/중단, parent aggregate timeout을 모두 별도로 남겼다. 이들을 합쳐 전체 PASS 보고서를 만들지 않았다. `verification-final.json`도 aggregate/원래5초 acceptance를 false로 명시한다. 영상15+Case2 skip은 기존 외부 파일/opt-in 부재이며 MySQL skip0과 구분한다.
- **cleanup 정정과 최종 자원:** initial pre-cleanup에서 소유 schema2개 잔여를 발견했고 그 검사 실패를 `pre-cleanup-leftovers.json`에 보존했다. aggregate timeout으로 fixture 정리가 끝나지 않았다는 원인 분류는 추론이다. 새로 초기화한 전용 서버에서 생성한 정확한 이름2개만 활성 client0 확인 후 제거했다(`leftover-schema-cleanup.json`). 후속 audit는 system4+base만 남고 other-client/transaction/data-lock/test-account0이다. 실제 PID425의 datadir/port를 대조하고 mysqladmin으로 정상 종료, init/server 로그 복사, pid/socket/process/listener 부재 확인 후 정확한 `/dev/shm/rec1a-20261019-e84d3a`만 삭제했다(`mysql-cleanup.txt`, `mysql-final-*.log`). 기존 tmpfs를 unmount하거나 다른 서버/과거 보존 경로를 정리하지 않았다. 최종 Windows/WSL audit에서 전용 listener/process/mount/data-dir/health-helper 잔여0을 확인했다. 테스트 junction/symlink endpoint9개만 제거하며 primary report117개의 해시 불변도 확인했다(`link-cleanup.json`). 처음부터 자동 cleanup이 성공했다고 소급하지 않는다.
- **SoT·범위·준비 상태:** Contract·Accepted Decision·Baseline 의미/값과 Case/Runtime 의무는 불변이다. Source 등록/조립은 REC-1(b)/RT-11, 최종 공개 소유 조회·DerivedAsset bytes/Content-Type은(c), 기존 IncidentClip bytes의 완전한 publication은 후속이다. REC-1(a) 코드·필수 acceptance와 전체 소비자/원격 CI·병합 판단을 분리한다. 현재 diff의 원격 CI와 원래5초 실패가 남아 있으므로 전체 GREEN/merge-ready를 주장하지 않는다. 커밋·중간 draft PR 준비 가능 여부는 최종 독립 판정을 다음 기록에 남긴다. 실제 staging/커밋/푸시/PR 생성은 하지 않는다.


### 2026-10-19 REC-1(a) 최종 독립 재리뷰 판정

- **Status: IN_PROGRESS · Refs #302 (REC-1(a)) · PR pending · merge SHA pending.** fresh reviewer `/root/rec1a_independent_review`는 최종 **추가 actionable P1/P2 없음, REC-1(a) 코드·필수 acceptance 충족, 범위를 한정한 커밋/draft PR 문안 준비 가능**으로 판정했다. 이는 실제 staging/커밋/푸시/PR 생성 권한이나 REC-1 전체 완료/merge-ready 판정이 아니다.
- **reviewer 직접 검사:** boundary0·Contract62/26/104·diff-check, strict CLI728 PASS, 기존 inventory/checker 함수 AST/frozen migration/workflow30분/nested900초 보존, 원래 mutation AST/source/input SHA·정상 종료0, parameter4,619의 정확한 Counter와 Recording364 layers, omission Recording121/cancel82/async5/START_ANALYSIS70의 정확한 집합과 전부 거부를 확인했다. 변경20파일/문서 목록/manifest delivery20+evidence150의 실제 해시, recovery728 소스 해시 변경0, HEAD/branch/index 및 원래 Log prefix도 직접 대조했다. MySQL pytest를 reviewer가 재실행한 것은 아니다.
- **reviewer의 보존 증거 대조:** MySQL728/2184 phases·Recording31의 실제 실행, source/Frame PNG/Derived metadata·case 연결과 transaction/migration 오류 경계, lifecycle 비교와 cleanup 자료를 검토했다. reviewer의 독립 WSL 상태 조회는 접근 거부였으므로 OS/DB cleanup을 직접 재관측했다고 주장하지 않는다. 구현자의 최종 Windows/WSL 자원 자료와 endpoint9개 제거/primary report117개 해시 보존은 잔여0과 일관된다는 판정이다.
- **한계·병합 차단:** aggregate parent1200초 timeout은 실패로 유지한다. 원래5초 API process test 실패도 그대로 남고 현재 원격 CI는 미확인이다. 따라서 **전체 consumer 회귀·전체 pytest·merge는 GREEN이 아니다**. 가상 HEAD/20초 lifecycle은 비교 진단일 뿐 original5초 PASS로 대체하지 않는다. 해당 실패를 이 diff에 귀속할 코드 근거는 없으며 REC-1(a) draft 준비의 비차단 위험으로 분류하되, 전체 회귀/병합의 미해결 항목으로 명시한다. nested883.700/900초의 작은 여유와 REC-1(b)/(c)/IncidentClip bytes 후속도 유지한다.
- **종료 상태:** 제품/테스트/gate 소스는 검증/리뷰 snapshot과 같고 이 후속은 Log append뿐이다. 최종 manifest를 이 Log 해시로 갱신하고 prefix 보존·diff-check·staging0을 다시 확인한다. 기존 stash·main-checkout-recovery 보존 자료·다른 서버/branch/worktree는 수정하지 않았다. 요청한 동일 checkout/branch에20파일을 미커밋·미스테이징 상태로 남긴다.

## 2026-10-19 REC-1(a) 병합 확인 · REC-1(b) 등록 입력

**REC-1 Status: IN_PROGRESS · Refs #302 (REC-1(b)) · PR pending · merge SHA pending.**

- **선행 병합·원격 CI 확인:** PR #379는 develop에 병합됐으며 merge SHA는 `978fed34d8bedf2cf5cf6d2c7d04e557cd670004`다. PR HEAD `dd2ec4957748af40c6dc9708158c5c03082aea26`의 [boundary-check](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39212568969)와 [python-tests](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39212568964) 및 full pytest/strict MySQL gate step의 SUCCESS를 GitHub 원본에서 직접 확인했다. 앞선 pending/CI 미확인 기록은 당시 이력으로 유지한다. 이 CI는 REC-1(b) 미커밋 diff의 원격 CI가 아니다.
- **시작 상태:** 같은 checkout의 `codex/rec1b-registration-input`, HEAD와 origin/develop이 지정 SHA와 일치, clean worktree·staging0을 확인했다. 원격 develop도 GitHub connector로 같은 SHA를 확인했다. 새 branch/worktree를 만들지 않았다. 저장소·상위 AGENTS.md 실파일은 없으며 사용자 제공 AGENTS 지침, CLAUDE 읽기 라우터와 docs 운영 규칙을 따랐다.
- **SoT 직접 대조:** Plan REC-1/§12, Ops §4-2, RD-17/#246 최종 결정 댓글, HTTP §5.2/§9.1, Baseline B-C3, 현재 Issue #302 본문·댓글0건, REC-1(a) note·Log, Recording model/service/repository/migration/tests와 #379 병합 코드를 확인했다. [REC-1(b) 구현 경계](../modules/recording/rec1b-registration-input.md)에 선택과 제약을 기록했다.

### Implementation Notes

- **구현 결과:** `original_filename`은 내부 LocalSource metadata로 기존 JSON에 보존·복원하며 시각 관찰에 사용한다. canonical 상대 locator와 별개이며 SourceAsset Contract에 필드를 추가하지 않는다. SoT에 없는 trim/basename/Unicode 정규화/길이·확장자 제한을 만들지 않는다. 문자열은 원문 그대로의 비경로 metadata이고 잘못된 타입/비Unicode surrogate 입력은 원문 없는 ValueError로 dependency 접근 전에 거부한다.
- **등록 taxonomy:** 안정된 입력과 ffprobe 구조화 AVERROR_INVALIDDATA 또는 유효한 metadata의 지원 video stream 부재는 UNSUPPORTED_MEDIA다. 도구/읽기/timeout/변경 감지/미확인 오류와 비정상 JSON·metadata는 TEMPORARY_FAILURE다. stderr/경로/확장자 기반 추론은 없다. HTTP422/503 매핑은 기존 Contract를 따르며 route는 구현하지 않는다.
- **transaction·Case 경계:** 선택적 case_id는 기존 Recording case_asset 표현을 등록 행들과 한 SQL 문장에 넣는다. caller Connection·commit/rollback 소유와 COMMIT 결과 불명, 같은 파일 재등록 시 새 logical identity 의미는 유지한다. Case stage·존재·manifest는 판단하지 않는다. 기존 Case 공개 함수 `record_source_registered()`를 같은 Connection에 조립하는 테스트만 추가하며 Case-first lock 순서를 따른다. 새 Case interface/callback/역방향 의존성/schema/Owner 의무가 필요하지 않아 별도 Owner 승인을 기다리지 않고 진행했다. 실제 HTTP 조립은 RT-11이다.
- **schema·Plan 대비 변경:** schema 변경 불필요. 기존 JSON의 선택적 내부 metadata이므로 새 migration을 추가하지 않고 recording_0001과 frozen revision을 보존한다. 과거 JSON에 키가 없어도 원문을 추정해 채우거나 row를 rewrite하지 않는다. REC-1(a) FrameRef MySQL bytes·DerivedAsset metadata·관계·locator·복구 의미를 유지한다. 권장 (b) 범위의 implementation detail이며 Plan/Contract/Accepted Decision/Baseline 의미 변경은 없다.
- **Owner 확인 포인트:** filename의 신규 거부·정규화 정책, 최종 ref→case 공개 조회, Case stage·집계 변경은 이번 slice에서 정하지 않았다. 기존 경계 안의 등록 입력·관계 저장에 남은 Owner blocker는 없다. REC-1(c), RT-10, RT-11 조립과 다른 Owner 제품 코드는 제외한다.
- **Verification 진행:** 기존 구현에서 unit21 FAIL/1 PASS와 실제 MySQL 신규10 FAIL을 보존했다. surrogate1 FAIL, case 입력4 FAIL을 추가 확인한 뒤 최소 구현으로 unit27 PASS를 확인했다. Recording MySQL41 PASS와 기존 Case 공개 함수 조립2 PASS, 등록·시각 관찰 선택110 PASS/외부 사용자 영상 미지정2 SKIP를 직접 실행했다. boundary0·Contract62/26/104·diff-check PASS. 전체 pytest는 필수 MySQL inventory·strict JSON/JUnit·parameter/metadata/family mutation을 포함해 기존 workflow30분/nested900초와 skip/xfail 거부 정책으로 실행 중이며 아직 PASS로 기록하지 않는다.
- **증거·상태:** 실행 증거는 새 ignored `.codex-scratch/rec1b-20261019/`에 분리한다. 초기 tmp 접근 및 서버 준비·sandbox localhost preflight 실패도 별도 유지하며 RED/GREEN으로 오인하지 않는다. 기존 scratch·RAW·archive·pytest 산출물과 관련 없는 untracked 파일은 전달 범위가 아니다. 독립 재리뷰·최종 결과·자원 audit은 후속 기록으로 남긴다. staging/commit/push/PR 생성은 수행하지 않는다.

### 2026-10-19 REC-1(b) 재개 · 리뷰 수정 · 최종 직접 검증

**REC-1 Status: IN_PROGRESS · Refs #302 (REC-1(b)) · PR pending · merge SHA pending.**

- **중단·재개 경계:** 같은 checkout/branch/HEAD와 staging0을 다시 확인했다. 최초 전체 pytest는 76%에서 exit124로 끝났고 최종 JSON/JUnit·nested 완료 증거가 없었다. 상위 guard는1800초였으나 wrapper elapsed는5715.203초였다. 중단과의 인과관계는 미확정이며 timeout 설정을 늘리거나 이를 PASS로 처리하지 않았다. 당시 소스 변화는 후술한 probe 수정·영구 재현 테스트2파일뿐이었다. 원본 진행표시7F와 현재 collection 순서로 추정한 실패 후보7건은 정확한 최초 traceback을 대신하지 않는다.
- **독립 리뷰 수정:** 구현에 참여하지 않은 `/root/rec1b_independent_review`가 잘못된 format duration과 no-video가 함께 있으면 UNSUPPORTED_MEDIA로 먼저 분류되는 P2를2건 재현했다. 구현자도 재현2 FAIL, 영구 테스트2 FAIL/9 PASS를 확인한 뒤 duration 검증을 먼저 완료하게 최소 수정했다. reviewer 원래 재현2 PASS와 최종 등록·시각 선택112 PASS/외부 opt-in2 SKIP를 확인했다. 다른 제품/gate 의미는 변경하지 않았다.

| 직접 실행 | 결과 |
| --- | --- |
| 원본 필수 MySQL inventory | 743 PASS · 2229 passing phases · skip0/xfail0 · JUnit884.009초 |
| 원본 `test_actual_report_rejects_each_missing_migration_check` 전체 함수 | 1 PASS/1092.42초 · wrapper1096.5초/exit0 · 소스 drift0 |
| 원본 JSON/JUnit strict CLI | PASS · reviewer 직접 재실행 PASS |
| parameter mutation | 4814개 전부 거부 · Recording559 layer 변형 포함 |
| Recording omission | metadata172 + family11 전부 거부 · 신규15 parameter/2 family 포함 |
| 나머지 omission | cancel82 · async5 · START_ANALYSIS70 전부 거부 |
| 최종 Recording 전체 | 616 PASS/외부 media·placement opt-in15 SKIP · MySQL Recording43개는 모두 실행·PASS |
| gate unit 전체 | 5261 PASS |
| API process-safety 최초 파일 재실행 | 44 PASS/1 FAIL · GO 전 `setup_import_watchdog_5s` |
| 실패 API node 단독 재실행 | 1 PASS/원래 watchdog 유지 |
| API process-safety idle 파일 재확인 | 45 PASS · 기존 Starlette deprecation warning1 |
| boundary/Contract/static/diff | 위반0 · structure62/JSON26/semantic104 PASS · checker 함수 AST/기존 inventory/frozen migrations/workflow/nested gate 보존 · diff-check PASS |

- **증거 판정:** 위 선택은 서로 겹치므로 unique 테스트 수로 합산하지 않는다. reviewer는 원본743 JSON/JUnit·전체4814 parameter/layer Counter·4 omission 집합·전부 거부 및 원본 해시 before/after 일치를 직접 확인했다. mandatory/focused snapshot의 모든 소스와 현재 코드가 일치한다. 900초 nested 제한 안에서 원본 함수를 완주했으며 JUnit884.009초는 subprocess 시작 비용까지 포함한 정확한 여유 수치가 아니다. 여유가 작은 실행시간 위험은 유지한다.
- **전체 pytest 생략 판단:** reviewer가 최종 Recording 전체·실제 MySQL의 API/Worker/Case/migration 교차 검증·strict/mutation·gate unit·원래 deadline API 검증을 근거로 전체 pytest의 중복 replay 생략을 허용했다. 변경하지 않은 다른 모듈의 전체 unit은 재실행하지 않았다. **완료된 최종 전체 pytest PASS는 없다.** 최초 전체 부분 실행과 API44/1 실패를 후속 PASS로 덮지 않는다. API phase/stack에는 ready/GO 전 timeout이 확인되지만 부하·환경이 원인이라는 판단은 추론이며 확정하지 않는다. 후속 idle45 PASS도 원래 실패의 원인을 확정하지 않는다.
- **보존·자원 audit:** REC-1(a) manifest의 원본 증거150파일과 기존 Log 전체 byte prefix를 재해시해 보존했다. 재개 서버 종료 전 schema는 system+owned base뿐, 계정은 기본 MySQL 계정뿐, test client0/transaction0이었다. 소유 helper의 graceful stop·port closed·datadir 제거를 확인했다. 중단 서버의 명시된 datadir은 이미 없었고 당시 로그는 읽을 수 없어 보존했다고 주장하지 않는다. 재개 서버 로그2개는 stop 전 별도 보존했다. Windows owned Python0/listener0, WSL mysqld0와 두 기록 포트의 잔여 없음을 확인했다. task-owned junction4개만 제거하고 일반 파일은 삭제하지 않았다.
- **현재 범위·남은 한계:** 변경14파일 전체는 [REC-1(b) note](../modules/recording/rec1b-registration-input.md) 「Delivery files」에 있다. 기존 Case 공개 함수 조립만 검증했고 Case/Runtime 제품 코드·schema·Owner 의무·Contract/Decision/Baseline 의미는 바꾸지 않았다. 이 slice에 남은 Owner 판단은 없다. 최종 ownership/media API와 RT-10/RT-11 조립·추가 filename 정책은 후속 경계를 유지한다. 현재 미커밋 diff의 원격 CI는 없고 PR#379의 원격 PASS로 대체하지 않는다. 모든 scratch helper/RAW/media/pytest 산출물은 PR 제외이며 관련 없는 untracked 파일은 보존한다. 제한을 명시한 코드/중간 draft 검토 준비와 전체 회귀/병합 준비를 구분한다. 실제 staging/commit/push/PR 생성은 하지 않는다.

### 2026-10-19 REC-1(b) 최종 독립 재리뷰 판정 · 종료 상태

- **REC-1 Status: IN_PROGRESS · Refs #302 (REC-1(b)) · PR pending · merge SHA pending.** fresh reviewer `/root/rec1b_independent_review`의 최종 판정은 **남은 actionable P1/P2 없음, 새 Owner 승인 blocker 없음, 범위를 한정한 커밋/중간 draft PR 문안 준비 가능**이다. 전체 pytest PASS나 merge-ready 판정은 아니다. 상세 독립 보고서는 ignored `.codex-scratch/rec1b-20261019/reviewer/independent-1/final-review.md`에 보존한다.
- **reviewer 직접 대조:** strict743/2229phases, 전체4814 parameter/layer의 정확한 Counter, Recording omission183을 포함한4 omission 집합·거부 및 원본 before/after 해시, mandatory/focused 소스 drift0, 기존150증거·전달14파일/manifest 증거145파일 해시, branch/HEAD/index·Log byte prefix·frozen migrations·기존 inventory·gate 함수 AST·30분/900초 제한을 확인했다. Recording616/15외부skip·gate5261·API최종45의 원본 실행 자료를 검토했다. OS/DB 자원 정리는 원본 audit를 검토했으며 reviewer가 독립 재관측했다고 주장하지 않는다.
- **생략·위험·병합 경계:** final Recording·cross-module MySQL/migration·strict/mutations·gate unit·원래 deadline API 검증의 중복 범위를 근거로 reviewer가 전체 pytest replay 생략을 허용했다. 최초 전체 부분 실패와 API watchdog 실패, 중단 서버 로그 미보존2건, 작은 nested timeout 여유와 외부 opt-in 미실행을 유지한다. 현재 diff의 원격 CI는 여전히 pending이다. Issue#302를 마지막으로 원격 재조회한 결과 본문 변경 없음/댓글0/open을 확인했다.
- **종료 상태:** 최종 판정 이후 제품/테스트/gate 변경은 없고 이 후속 Log append만 추가했다. manifest를 최신 Log/독립 보고서 해시로 갱신하고 보존·diff-check·빈 staging을 재확인한다. 같은 checkout/branch의14파일을 독립 리뷰 가능한 미커밋·미스테이징 상태로 남기며, staging/commit/push/PR 생성은 수행하지 않았다.


## 2026-10-19 REC-1(b) 병합 확인 · REC-1(c) ownership/read 착수

**REC-1 IN_PROGRESS · Refs #302 · REC-1(c) PR pending · merge SHA pending.**

- PR #380의 develop 병합을 GitHub 원본에서 직접 확인했다. merge SHA는 `e0f2942210fe525a70f42a76f89ccfb45a05dd5b`, PR HEAD는 `bbf38218e3cc84351634bf91061b17f4bc87179b`다. [boundary-check](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39253272871/job/118062094667) PASS와 [python-tests](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39253272877/job/118062095137) PASS를 확인해 **REC-1(b) 병합 완료**를 기록한다. 기존 pending·로컬 timeout 이력은 수정하지 않는다.
- REC-1(b)의 로컬 전체 pytest는 timeout으로 끝났고 최종 전체 PASS가 없었다. 원격 python-tests SUCCESS는 별도의 원격 실행 결과이며 그 로컬 실패를 PASS로 바꾸지 않는다. REC-1(c) 미커밋 변경의 원격 CI도 아니다.
- 시작 branch `codex/rec1c-ownership-reads`, HEAD·origin/develop·실제 원격 develop 모두 위 merge SHA, clean worktree·빈 staging을 확인했다. 새 branch/worktree를 만들지 않았다. 별도 저장소 AGENTS.md는 발견되지 않아 사용자 제공 지침과 CLAUDE.md/docs 운영 규칙을 적용했다.
- Plan REC-1, Ops §4-2, #246 최신 본문·최종 RD-17 댓글, HTTP §3.5/§5.5/§5.6/§9.1, Baseline B-C3, #302 최신 본문(댓글0), (a)/(b) note·기존 Log, model/service/repository/migration/test 및 #379/#380 병합 구현을 대조했다. [REC-1(c) note](../modules/recording/rec1c-ownership-reads.md)에 구현 경계·함수 모양·trade-off를 먼저 기록했다.
- 초기 unit 실행은 33 FAIL/2 ERROR였다. 큰 bytes parameter의 자동 node ID가 Windows 경로 오류를 일으켜 명시 ID로 수정했다. 그 실행은 feature RED로 대체하지 않는다. 수정 후 unit+실제 MySQL 선택은 **41 FAIL/0 ERROR**, 신규 capability 부재/불변 bytes 위반으로 실패했다. 별도 오류 비노출 RED도 2 FAIL로 보존했다. 증거는 ignored `.codex-scratch/rec1c-20261019/`다.


### REC-1(c) TDD·독립 리뷰 수정 이력

- 초기 GREEN 41 PASS 이후, unit 입력 모델 원문 비노출 RED2 FAIL, 실제 MySQL 손상 metadata RED2 FAIL/3 PASS를 거쳐 고정 오류 경계를 보완했다. 첫 Recording 전체 실행은 662 PASS/15 외부 미디어 opt-in SKIP였으나 이후 source 변경이 있어 최종 증거와 분리한다.
- fresh reviewer `/root/rec1c_independent_review`가 실제 형식·Content-Type 불일치와 ownership 손상 metadata 원문 노출 P2 두 건을 지적했다. 실제 형식 RED3 FAIL과 실제 MySQL ownership/source·derived·관계 RED3 FAIL을 먼저 보존한 뒤 수정했다. reviewer도 실제 MySQL3 family의 고정 오류와 실제 MP4의 잘못된 image/png 거부를 독립 확인했다. 초기 보고서는 `.codex-scratch/rec1c-20261019/reviewer/review-initial.md`다.
- bytes adapter는 기존 extractor PNG·materializer isom MP4의 container 형식과 선언 Content-Type을 대조한다. decoder 전체 유효성 검사가 아니며 새 Contract enum이나 role별 codec 정책을 만들지 않는다. 빈 bytes의 형식을 추정하지 않고 거부한다. metadata-only zero-size 모델은 그대로 허용한다. unsupported 형식 확장은 Recording adapter 후속이며 Object Storage 의무와 구분한다.
- gate inventory만 늘리기 전 독립 inventory로 실행한 gate RED는 60 FAIL/5,413 PASS였다. 그 전에 `-k media_read`가 자동 parameter ID와 맞지 않아 선택0(exit5)이었던 시도도 보존하며 RED로 대체하지 않는다. checker 함수는 수정하지 않고 3개 family/25개 parameter 의무만 추가했다.
- 추가 GREEN 두 번째 시도는 packet-limit 드라이버 I/O가 종료되지 않아 소유 Python22232/35548만 중단했다. 해당 schema `rt02a_test_e13c9b97765d4a058d339fdb228ed4e3`만 제거하고 task server의 compiled-default packet 설정을 복원했다. 세 번째 시도는 62 PASS/1 FAIL로, idle control socket의 복구 ACK 오류를 남겼다. 새 연결로 실제 전역값64MiB와 schema 정리를 확인했다. I/O deadline·새 복구 연결·local non-TLS test transport로 수정한 선택은 8 PASS였다. 이들 중단/실패 이력을 최종 PASS로 바꾸지 않는다.
- 제품·test 소스 변경을 마친 뒤 최종 해시를 기록한 Recording/gate unit 전체를 실행 중이다. 원래 MySQL mandatory 함수·900초 제한, workflow30분, skip/xfail 거부, frozen migrations 및 기존 checker 함수 AST는 그대로다. Case/Runtime 제품·Contract 변경이 없고 원본 Log prefix와 (a)150/(b)148개 evidence hash를 재대조해 보존했다.


### 2026-10-20 REC-1(c) 사용량 중단 후 재개 · 최종 focused 검증 확인

**REC-1 IN_PROGRESS · Refs #302 · PR pending · merge SHA pending.**

- 같은 checkout/branch/HEAD와 빈 staging을 재확인했다. 중단 전 최종 Recording 실행은 **682 PASS/15 기존 외부 미디어 opt-in SKIP**(202.53초), gate unit 전체는 **5,539 PASS**(317.80초)로 완료돼 있었다. 두 wrapper 결과는 exit0·changed_sources=[]이고 재개 뒤 기록된 모든 product/test/config 해시도 직접 재대조해 drift0을 확인했다.
- Recording JUnit697건 중 MySQL68건·실행 phase204건이 모두 PASS이며 MySQL skip/xfail은 없다. 외부 사용자 미디어를 요구하는 기존15 skip을 MySQL gate 허용으로 확대하지 않는다. 중단 당시 task server는 살아 있었고 schema는 system+owned base뿐이었다. 재개 probe에서 관측한 transaction1은 일반 Connection을 사용한 자기 조회를 포함한 수치여서 잔여 test transaction으로 단정하지 않는다. 최종 자원 audit는 AUTOCOMMIT 별도 연결로 한다.
- Issue #302를 원격에서 다시 읽었고 본문 변경 없음·댓글0·OPEN이다. 원래 `test_actual_report_rejects_each_missing_migration_check`를 기존 nested900초/outer1800초 guard 그대로 실행 중이다. 결과는 다음 기록으로 구분한다. reviewer는 최종 focused 증거를 재대조 중이며, 전체 pytest 미실행 허용/전체 Acceptance/Closes #302 판정은 mandatory 결과와 자원 정리 후 확정한다.


### 2026-10-20 REC-1(c) Contract 미존재 오류 보정 · mandatory timeout 보존

- 직접 재대조한 HTTP §5.6은 미존재 asset의 Recording 오류를 `UNKNOWN_REF`로 명시한다. 새 open에서 기존 metadata getter의 `NOT_FOUND`를 그대로 전달하던 선택을 root가 발견했고 독립 reviewer가 P2로 확인했다. 기존 metadata API의 `NOT_FOUND` 호환성은 그대로 두고 새 `open_derived_asset`만 `UNKNOWN_REF`로 변환했다. 영구 unit·실제 MySQL legacy 노드에서 **RED2 FAIL → GREEN2 PASS**를 보존했다.
- 수정 전 source/test3파일의 bytes·해시를 별도 snapshot으로 보존했다. AST 변화는 새 open의 missing 변환, 기존 unit의 expected code 및 metadata getter 호환성 확인, 기존 MySQL legacy 노드의 missing assert뿐이다. 함수·test/node identity 추가/삭제는 없고 checker·inventory·workflow·원본 mandatory 함수는 byte 불변이다. reviewer도 이 범위를 독립 확인했다. 이전 5,539 gate unit 증거는 해당 불변 gate/inventory 범위 증거로 보존하며 최종 소스 전체 실행이라고 바꾸지 않는다.
- 첫 원본 mandatory 함수 실행은 **nested900초 TimeoutExpired · outer1 FAIL(904.125초) · source drift0**이었다. inner JSON/JUnit/strict mutation 완료 증거는 없으므로 PASS나 완료된 전체 baseline으로 쓰지 않는다. 종료 후 pytest 자손은 없었으며 소유 task server의 잔여 단일 test schema는 연결0과 migration table을 확인 후 제거했다. 다른 schema/기존 산출물은 변경하지 않았다.
- 같은 loopback server에서8회씩 측정한 연결 합계는 기본 TLS0.547초, 로컬 비TLS0.188초였다. 표본 차이는 관측 사실이지만 최초 timeout 전체 원인이라고 단정하지 않는다. 재시도는 harness가 허용한 `ssl_disabled=true` 로컬 URL만 선택하고 실제 MySQL8.4.7·DDL/DML·durability·기존 함수·inventory·nested900/outer1800·workflow30분·skip/xfail 정책은 유지한다. 제품 TLS/auth 정책 변경이 아니다. 최종 수정 소스 해시를 별도로 고정해 원본 mandatory 함수를 재실행 중이다.


### 2026-10-20 REC-1(c) mandatory 실행 환경 진단

- 두 번째 mandatory도 nested900초 TimeoutExpired·outer1 FAIL(904.765초)·source drift0으로 끝났다. 소유 schema 하나의 연결0과 table 목록을 확인해 정리했고 실패 보고서는 보존했다. 세 번째 실행은 원래 child 인자32개·환경·cwd·900초를 유지하고 실제 stdout/stderr만 별도 파일로 관측한다. reviewer가 이 capture 변경과 원본 인자 일치를 독립 확인했다. 계측 자체를 acceptance 성공으로 간주하지 않는다.
- 수집 순서의160번째 실패를 기존 `test_explicit_config_url_preserves_percent_encoded_password` 단독 비TLS 실행으로 재현했다(1 FAIL/2.00초). 설치된·lock에 고정된 PyMySQL1.2.3의 새 계정 RSA 인증 경로가 packet을 반환하지 않아 `auth_packet=None` AttributeError로 이어지는 코드를 reviewer도 확인했다. cryptography는 설치돼 있다. 의존성·인증 정책·제품·테스트는 수정하지 않는다. 같은 기존 테스트는 기본 TLS의 별도 소유 RAM 서버에서1 PASS/1.58초였다. 비TLS 실패를 기본 TLS PASS로 소급하지 않는다.
- 기존 `/tmp` 서버의 InnoDB CREATE/DROP20쌍은0.781초, 별도 `/dev/shm` 소유 UUID 서버는0.156초였다. 전체 timeout 원인을 이 표본 하나로 단정하지 않는다. scratch에 복사한 owned-server helper의 생성/안전 정리 prefix 두 곳만 바꿨다. MySQL 실행 옵션은 같고 flush_log_at_trx_commit=1/sync_binlog=1이다. 파일시스템에 따른 effective flush_method는 기존 O_DIRECT/RAM fsync로 관측됐다. RAM 임시 서버 증거는 전원 손실 시 디스크 내구성 증명이 아니며 caller transaction/실제 MySQL assertion과 구분한다.
- 원래 mandatory 함수 자체를 기본 TLS·원래 capture_output·nested900초/outer1800초 그대로 RAM 소유 서버에서 추가 실행한다. 기존 서버와 별도 포트/schema/datadir를 사용하고 서로의 전역 packet 설정을 변경하지 않는다. 이전 timeout·비TLS 실패와 각 실행 자료는 모두 별도로 보존한다.
- 관측용 세 번째 실행도 nested900초 TimeoutExpired·outer1 FAIL(904.109초)·source drift0이었다. 이 실행에는 완료된 inner JSON/JUnit/mutation이 없다.160번째 실패는 위 인증 오류로 단독 재현했으며,244번째 기존 lifecycle FAILED parameter의 단독 재실행은1 PASS/3.47초였다. 후자의 원인은 미확정이며 최초 실패를 지우지 않는다. 종료 후 client0·정확한 소유 UUID schema1개를 확인해 제거했다. 최종 수정 이후 Recording 전체는 원래 `/tmp` 서버의 기본 TLS에서 별도로 재실행한다.


### 2026-10-20 REC-1(c) 원본 mandatory 완료 · packet 테스트 정리 보정

- 기본 TLS/RAM 소유 MySQL에서 원본 mandatory 함수 전체가 **1 PASS/1162.06초**로 끝났다(wrapper exit0/1166.782초/source drift0). 실제 child는 **768 selected/2304 PASS phases**, JUnit768·skip/xfail/failure/error0·744.172초로 nested900초 이내였다. 원본 strict CLI를 root와 reviewer가 각각 실행해 PASS를 확인했다. 원래 함수·capture_output·인자·workflow30분/nested900초/outer1800초를 유지했다. 앞선 세 timeout과 비TLS 오류를 이 성공으로 소급하지 않는다.
- 원본 parameter mutation **5139개 전부 거부**, Recording **884 layer/272 metadata/14 family** 거부를 완료했다. reviewer가 Counter/전체 identity·layer 집합을 직접 대조했다. cancel76 metadata+6 family, async4+1, start64+6도 정확히 유지됐다. 실제 JSON/JUnit/omission 원본은 `mandatory-ram-final-tmp/test_actual_report_rejects_eac0/`에 보존한다.
- 그 실행을 기다리는 동안의 Recording 기본 TLS/disk 전체는 **681 PASS/15 기존 opt-in SKIP/1 FAIL**이었다. packet_limit의 기대 DBAPI 오류·비노출 assertion 이후, 서버가 끊은 writer에 test caller가 보낸 rollback에서2013/WinError10053이 발생했다. 이 실패는 보존한다. 종료된 소켓을 caller가 `invalidate()`하고 rollback으로 로컬 SQLAlchemy 상태만 정리하도록 한 문장을 추가했다. 원격 rollback 성공을 주장하지 않으며 새 연결 COUNT0·설정 복구와 기존 정상 rollback 테스트는 그대로다. 독립 reviewer도 assertion/gate 비완화인 test cleanup 수정으로 확인했다.
- 수정 전 snapshot이 mandatory 해시와 같고, `conn.invalidate()` Expr 하나를 제거하면 test 파일 AST 전체가 이전과 동일함을 root/reviewer가 각각 증명했다. mandatory와 현재 소스의 차이는 이 test 파일 하나뿐이다. 수정 후 단독 packet은 **1 PASS/5.81초**였고 최종 Recording 전체를 다시 실행한다. 따라서 mandatory는 정확한 이전 cleanup source의 보존 실행, 현재 Recording은 최신 source의 직접 실행으로 구분한다.


### 2026-10-20 REC-1(c) 최종 현재 소스 재검증 · 자원 잔여 구분

- 최종 `recording-cleanup-final`은 원래 `/tmp` 소유 MySQL·기본 TLS에서 **682 PASS/15 기존 외부 미디어 opt-in SKIP**로 완료됐다(wrapper exit0/299.25초/source drift0). MySQL68개/204 phase 모두 PASS·xfail0, JUnit697개·기존15 skip identity 동일·failure/error0과 현재 source548개 해시 일치를 root/reviewer가 확인했다. gate5539·mandatory768/5139 mutation의 위 보존 실행과 합산하거나 현재 전체 source 재실행으로 바꾸지 않는다.
- fresh reviewer는 변경된 Recording 전체·교차 모듈 실제 MySQL/migrations/strict/mutation·불변 gate5539·boundary/Contract의 중복 검증 범위를 근거로 **전체 pytest 추가 재실행 생략을 명시 승인**했다. 전체 pytest와 현재 diff 원격 CI는 미실행이다. 과거 #380 원격 PASS는 (b) 병합의 별도 증거다.
- 두 서버의 종료 전 DB audit는 system4+owned base1 schema·기본4계정·다른client/trx/data-lock0·packet64MiB였다. init/server 로그를 삭제 전에 보존했다. 종료 후 소유 `/tmp`·`/dev/shm` datadir와 mysqld·Linux MySQL listener 및 Windows 소유 Python helper는 없다. 이번 task 안의 테스트 link endpoint8개만 제거했고 ordinary file 삭제0이다. 기존 scratch/RAW/archive는 건드리지 않았다.
- **자원 정리 전체 PASS/잔여0은 아니다.** 두 owned helper는 마지막 `assert_port_closed`에서 exit1이었다. 기존 공유 Windows `wslrelay.exe` PID36320이127.0.0.1:53333/55890 listener를 유지하며 TCP는 받지만 MySQL handshake는 없고 read timeout이다. 원래 backend·DB·data는 없다. 정확한 RAM port만 일시 재바인드/close해도 잔여는 유지됐다. 공유 relay를 kill/restart하지 않았다. reviewer는 이를 공개된 비차단 OS forwarding 잔여로 판정했다. 공유 WSL 재시작은 다른 연결에 영향을 줄 수 있어 별도 조치하지 않는다.
- 마지막 boundary0·Contract62/26/104·diff-check 및 checker 함수 AST/기존 inventory subset·frozen migrations·원본 mandatory/nested900·workflow30분·다른 Owner 제품 불변을 다시 확인했다. 이전(a)150/(b)148 evidence hash와 기존 Log 전체 prefix도 보존했다. 13 delivery 파일·동일 branch/HEAD·빈 staging을 확인하며 최종 전체 AC/Closes 판정과 manifest는 독립 reviewer 후속으로 남긴다.


### 2026-10-20 REC-1(c) 최종 독립 재리뷰 판정

- fresh reviewer `/root/rec1c_independent_review`는 **Issue #302 전체 Scope와 3개 AC 충족, 남은 actionable P1/P2 없음, 추가 Owner 판단 없음**으로 판정했다. 기존 filename/taxonomy·persistent source/CaseView Frame/derived 복원·caller rollback·cross-case ownership·bytes/Content-Type/PNG 형식·원자성·migration/legacy·privacy·정책/범위를 직접 검토했다. 보고서는 ignored task의 `reviewer/final-review.md`다.
- reviewer는 current Recording682/기존15SKIP/실제MySQL68과 현재548 source 해시, 원본 mandatory child768/strict/정확한5139 mutation 및 Recording884/272/14 집합, 이후 cleanup1Expr의 전체 AST 차이, 보존 gate5539의 불변 checker/inventory/gate/workflow를 각각 대조했다. boundary0·Contract62/26/104·diff-check도 reviewer가 직접 재실행했다. root의 모든 MySQL pytest를 reviewer가 중복 실행한 것으로 표현하지 않는다.
- **전체 pytest 추가 실행 생략 승인·커밋/최종 PR 준비 가능·향후 최종 PR의 Closes #302 사용 가능**이다. 최종 manifest·문서 hash bookkeeping 후의 준비 판정이며, 실제 staging/commit/push/PR 생성은 사용자 요청대로 하지 않는다. 현재 diff 원격 CI는 pending이며 실제 merge 전에는 **REC-1 IN_PROGRESS**, PR 번호·merge SHA pending이다. merge-ready/전체 pytest PASS/DONE을 주장하지 않는다.
- 공유 Windows relay53333/55890·두 helper의 종료 assertion exit1은 남은 비차단 OS 잔여로 그대로 공개한다. 소유 DB/process/datadir/Linux listener 부재·기본계정 및 DB audit·소유 link8개 정리와 구분하며 cleanup 전체 PASS/잔여0이라고 바꾸지 않는다. 저장 형식의 bounded recognition·MySQL packet/용량·RAM의 전원 장애 한계와 Consumer/RT-11 후속 범위도 유지한다.
- 최종 결과는 [REC-1(c) note](../modules/recording/rec1c-ownership-reads.md)의 13파일 전체 목록·실행/보존 구분·AC/위험/PR 제외 목록에 정리했다. 마지막 문서 append 이후 source는 불변이며 static/manifest의 문서 hash를 갱신하고 보존 prefix·원래 branch/HEAD·빈 staging을 다시 대조한다.


### 2026-10-20 REC-1(c) 최종 포트 후속 검사

- 마지막 read-only Windows listener 확인에서53333/55890이 사라진 것을 관측했다. **2026-10-19 18:13:10 UTC** 원래 `assert_port_closed`를 각 포트에 다시 실행해 두 포트 모두 PASS였다(`port-recheck-final.json`). 공유 relay를 kill/restart하지 않았다. 제거 시점·원인을 임의로 단정하지 않는다.
- 앞선 두 helper exit1·당시 OS 잔여·poststop의 all_resources_removed=false는 그 시점의 실패/관측으로 보존한다. 이 후속 성공으로 소급하지 않는다. 소유 DB/process/datadir/Linux listener/Python helper 부재와 최종 Windows 포트 닫힘을 함께 최종 상태로 기록한다. 제품·테스트 소스는 그대로이며 note/Log의 최신 관측 및 static/manifest 문서 hash만 갱신한다.


## 2026-10-20 REC-1(c) PR #381 병합 확인 · REC-1 전체 Acceptance 완료

- GitHub PR #381 MERGED를 직접 확인했다. merge SHA는 `85da60b63e784efcbbfb00369244a133b470688e`이고 [boundary-check](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39301351801/job/118227057033) PASS · [python-tests](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39301351825/job/118227056927) PASS다. Issue #302 CLOSED도 직접 확인했다. 기존 최종 독립 재리뷰와 원격 CI·병합 결과를 근거로 **REC-1 전체 Acceptance 완료 및 DONE**을 후속 기록한다.
- 위 PASS는 PR #381의 원격 결과다. 앞선 로컬 timeout·실패·당시 pending/IN_PROGRESS 이력을 수정하지 않으며 현재 RT-11(a) 미커밋 변경의 CI로 쓰지 않는다.

## 2026-10-20 RT-11(a) source upload 착수 · TDD 및 경계 확인

**RT-11 IN_PROGRESS · Refs #298 (RT-11(a)) · PR pending · merge SHA pending.**

- 현재 checkout/branch `codex/rt11a-source-upload`를 유지했다. HEAD·origin/develop·실제 원격 develop은 위85da60b SHA, 시작 worktree clean·빈 staging을 확인했다. 새 branch/worktree는 만들지 않았다. 저장소 AGENTS.md 파일은 발견되지 않아 사용자 제공 지침과 CLAUDE.md router를 적용했다.
- #298 최신 본문·댓글0/OPEN 및 #302 본문·댓글0/CLOSED를 직접 확인하고 Plan RT-11·Tech13·HTTP3.5/5.2/7-6~9·Baseline B-U1/3/4/2.6·REC-1(a~c)·현재 API/Case/Recording/gate/workflow/Log를 대조했다. 요청의 workflow4-2 포인터는 router가 가리키는 ops-spec4-2로 확인했다.
- HTTP/ASGI/subprocess RED29 FAIL·실제MySQL RED4 FAIL을 먼저 보존했다. 초기 test splice/getter 오류와 첫 GREEN 실패도 별도 보존한다. 이후 기본1GiB·+1 byte/CL 유무·fsync/device·filename·taxonomy·실제timeout·기존API focused59 PASS, 확장 실제MySQL20 PASS를 확인했다. Process kill 최초3 PASS/자원 audit1 FAIL이며 schema/AUTOCOMMIT audit로 보정해 재검증 중이다.
- 구현: async 수신·공유 staging → file fsync → st_dev 확인·atomic publish(POSIX directory fsync 포함) → Case 선잠금·INTAKE 확인 → 같은 caller Connection의 기존 Recording 등록·Case record_source_registered → commit ACK → 별도 공개 view →201. 새 Case/Recording 공개 surface·정책 변경은 없다.
- stock Uvicorn의 response-less return/exception/cancel500을 실제소켓으로 재현했고, 별도 fresh boundary reviewer도 확인한 API 내부 H11 close callback·trusted abort-aware access branch로 기존 no-status close 정책을 구현한다. Plan12.3 구현 상세이며 다른 Owner 의무나 새 status를 만들지 않는다. 지원CLI가 protocol을 명시 선택하고 일반 logging/shutdown/signal 복원을 유지한다.
- 기존 lock Starlette1.8.0을 pin하고 header/CRLF scanning 수정의 streaming parser python-multipart0.0.32 하나만 추가했다. 다른 dependency 버전은 불변이다. 메시지/도구출력 taxonomy 추론·filename 경로화·응답 필드/Location 추가는 없다.
- 신규 독립 upload inventory36개/12family를 추가했다. Gate RED12→GREEN12는 family unit 증거이며 full strict JSON/JUnit·parameter/metadata/family mutation은 후속 기록한다. 기존 inventory·nested900초·workflow30분·MySQL skip/xfail0을 유지한다.
- 상세는 [RT-11(a) note](./rt11a-source-upload.md), 증거는 ignored `.codex-scratch/rt11a-20261020/`다. 전체 검증·fresh 구현 reviewer·최종 자원 audit·현재 diff 원격CI는 pending이며 staging/commit/push/PR 없이 남긴다.


### RT-11(a) fresh 구현 재리뷰 보완 · 전체 검증 진행

- 구현에 참여하지 않은 fresh reviewer `/root/rt11a_fresh_review`가 P2 두 건을 찾았다. 413 뒤 미소비 body의 keepalive/drain 가능성은 RED2 FAIL/2 PASS→Connection:close GREEN4 PASS로 수정했고 reviewer가 실제 CLI의 CL 초과·unfinished chunked 요청에서 Contract413+EOF를 독립 확인했다.
- 초기 composition은 Case lock 안에서 기존 Recording 등록의 전체파일 hash/ffprobe를 수행했다. 공개 FfprobeMediaProbe·RecordingService(media_probe=...) 주입 seam을 확인해 새 공개 surface 없이 probe를 checkout 밖으로 옮겼다. 준비 결과/typed failure를 request-local adapter로 전달하고 dev/ino/size/mtime_ns/ctime_ns를 재확인한다. 실패는 Case 확인 뒤 등록에서 전달해404/409 우선순위를 유지하며, 변경 감지는 TEMPORARY_FAILURE로 row 없이 거부한다. 직접 MySQL RED1+1과 reviewer의 실제AVI/defaultffprobe RED1을 보존했다.
- 보완 후 root 실제MySQL upload38 PASS/65.08초(wrapper exit0/drift0)다. reviewer는 실제AVI 생성·기본ffprobe 중 checkout0·별도 Case NOWAIT lock 성공·201·새RecordingService 복원을 직접 실행해 GREEN1을 확인했다. reviewer 직접 HTTP/API55 PASS와 실제 timeout subprocess2 PASS, boundary/Contract/AST/inventory/workflow/lock 확인은 root 보존59/38 증거와 구분한다.
- 첫 full-regression은 reviewer의 probe 지적 때문에127.766초에 소유 pytest tree만 중단했다(exit1/drift0). full-final은 보완 후 소스를 고정해 실제MySQL과 원본 nested900초 mandatory를 포함한 전체 pytest로 재실행 중이다. 현재 드러난 기존 signal test의 exact kwargs 기대에 새 http protocol 인자가 없음을 단독 재현했다. reviewer는 기존 signal/cleanup/logger assertion을 보존한 기대 인자 추가가 필요하다고 판정했으며, 전체 실행을 보존한 뒤 test-only 보정과 재실행으로 구분한다. 원래 전체 실패를 PASS로 바꾸지 않는다.
- 기존 gate checker3함수 AST·모든 기존 inventory·frozen migrations·workflow30분·nested900초는 불변이다. 신규 upload38개/12family만 추가했다. REC-1(c) 기존16228 evidence와 (a)150/(b)148 파일 해시 mismatch0, 시작 Log 전체prefix 보존을 확인했다.
- native POSIX에서 현재 publish 함수의 정확한 AST를 실행해 filefsync→replace→directoryfsync3회·동일device·최종bytes·소유 임시root 정리를 확인했다. Linux 전체API/DB 실행 또는 전원장애 내구성 증거로 확대하지 않는다. Windows·genericASGI/server-version 및 기존 native filesystem stall 한계는 note/reviewer에 구분한다.
- pyproject 변경에 따른 저장소 update-readme skill로 루트 사실 절을 대조했다. 현재 upload surface·지원CLI protocol과 후속 FrameRef/DerivedAsset 범위 문구만 고쳤다. Node/Python/설치명령·기술 stack·나머지 절은 그대로다. 최종 full/strict/mutation·자원 audit·현재 diff 원격CI는 후속 판정까지 pending이다.


### RT-11(a) 전체 실행 보존 · 기대 인자 보정 · 실제 MySQL strict child 통과

- full-final 전체 pytest는9381 PASS/26 기존 외부 opt-in SKIP/2 FAIL,2714.09초(wrapper2725.875초/exit1/source drift0)로 끝났다. 실패는 기존 signal child의 exact kwargs 기대 누락과 원본 mandatory의 nested900초 TimeoutExpired다. 실패 full JSON/JUnit은 그대로 보존했고 strict CLI가 이를 거부함도 보존했다. 합성·병합 보고서로 원래 실패를 PASS로 만들지 않는다.
- 전체 종료 뒤 signal test의 기존 기대 Dict에 http=cli.UploadH11Protocol 한 항목만 추가했다. 나머지 assertion 삭제0·정확한 bytes 역치환 proof와 full557파일 hash 대조를 보존했다. 바뀐 파일은 그 test 하나이고 제품/gate/config drift0이다. 현재 process-safety/HTTP/ASGI/기본1GiB/실제timeout/기존app104 PASS/84.99초(wrapper exit0/drift0)를 직접 확인했다. fresh reviewer는 이 test-only 보정과 scoped 재실행으로 충분하다고 판정했으며 원래 전체 FAIL은 유지한다.
- 전체 종료 후 소유 RAM MySQL8.4.7은 기본4계정·다른client/transaction/data-lock0·packet64MiB·flush_log_at_trx_commit1/sync_binlog1이었다. timeout에서 남은 정확한 harness UUID schema1개만 연결0·table 목록을 보존한 뒤 제거했다.
- 원본 mandatory 함수를 단독으로 다시 실행했다. 실제 child는806개/2418 phase 모두PASS, JUnit870.196초, skip0/xfail0이며 nested900초 안에 끝났다. unchanged strict JSON/JUnit CLI PASS를 직접 확인했다. 아직 같은 원본 함수의 parameter/metadata/family mutation 단계가 진행 중이므로 parent 전체 PASS·정리 완료를 미리 주장하지 않는다. outer1800초·workflow30분도 유지한다.
- 복사한 scratch runner의 server_ram=false는 이전 --server-ram 대체폴더 selector 미사용이라는 뜻이며 실제 저장 매체 측정값이 아니다. 실제 @@datadir=/dev/shm은 직접 관측했고 clarification JSON을 별도로 남겼으며 원래 command metadata는 고치지 않았다. 로컬 RAM 서버 증거를 전원장애 내구성 증거로 확대하지 않는다.


### RT-11(a) 필수 strict mutation 완료 · 독립 재리뷰 · 소유 자원 정리

- 원본 mandatory 함수 단독 실행1 PASS/1235.87초(wrapper1238.296초,exit0,source drift0). 실제 MySQL8.4.7 child806개/2418phase PASS,skip0/xfail0,870.196초이며 strict JSON/JUnit CLI도 PASS. 기존 nested900초·outer1800초·workflow30분을 유지했다.
- exact parameter mutation5633건=기존5139+upload494(38identity×13layer), upload metadata152+family12=164건을 모두 거부했다. fresh reviewer는 HEAD 대비38추가/12family를 독립 산출하고 prior/current Counter·중복0·all rejected·각 XML evidence를 직접 확인했다. 기존 checker 함수 AST·필수 inventory·workflow·migration을 보존했다.
- 독립 reviewer 직접 실행은 HTTP/app55 PASS,실제 CLI timeout2 PASS,실제 AVI/defaultffprobe/MySQL/Case NOWAIT lock1 PASS,raw413/EOF2 PASS,strict806 CLI PASS 및 boundary/Contract/diff 검사다. 발견된 P2 두 건은 수정 후 재확인했다. 남은 제품 P1/P2·새 Owner 정책 판단은 확인되지 않았다. 원래 전체9381PASS/26SKIP/2FAIL 기록은 그대로 유지하며104PASS 재실행과 단독 mandatory를 합쳐 전체PASS라고 주장하지 않는다.
- REC-1(c)16228·REC-1(a)150·REC-1(b)148 evidence hash 불일치0. 원래 Log raw prefix 보존,동결557 source/config 중 차이는 signal 기대 인자 한 항목뿐이며 제품/gate/config drift0. 현재 boundary/Contract/diff 검사 PASS. POSIX probe는 생산 publish 함수의 filefsync→replace→directoryfsync3 순서를 확인했으며 전체 Linux/전원장애 검증으로 확대하지 않는다.
- 종료 전 전용 DB는 기본4계정·system+base schema·다른client/transaction/lock0. 소유 mysqld·RAM datadir·socket 제거 확인. 소유 upload416파일은 hash 보존 뒤 제거했고 소유 testlink3개는 target을 건드리지 않고 제거했다. timeout 잔여 UUID schema1개만 table/연결0 증거 뒤 제거했으며 비소유 자원은 변경하지 않았다.
- 정리 제한: 기존 helper 종료는 Windows62501 port-open assertion으로exit1이었다. 공유 wslrelay.exe PID25236이62501과 비소유58501을 함께 보유한다. Linux62501 listener·전용mysqld는 없으며 소유 testPython process도 없다. 공유 relay/WSL은 중지하지 않았고 완전한 listener 정리를 주장하지 않는다. reviewer는 제품 병합 차단과 구분되는 비차단 OS 잔여로 판정했다. 원래 실패와 최종 audit/log/hash 증거를 보존했다.
- 비차단 위험: pinned Uvicorn private adapter/지원 CLI 의존,Windows directoryfsync 한계,RAM 검증의 전원장애 한계,기존 storage trust,filesystem stall,870.196/900초 여유와 로컬 전체45분/CI30분 차이. 현재 변경의 원격 CI는pending이며 과거 PR381 성공으로 대체하지 않는다.
- RT-11 IN_PROGRESS. Refs #298 (RT-11(a)). 현재 PR/merge SHA pending. 22파일 미커밋 diff는 결과를 공개한 커밋·중간PR 준비가 가능하나 staging/commit/push/PR은 사용자 지시대로 수행하지 않았다. Scratch/RAW/archive/pytest/media/temp env는 PR 제외. 상세 파일 목록·검증·제한은 docs/runtime/rt11a-source-upload.md와 새 scratch 증거에 기록했다.


### RT-11(a) PR #382 원격 CI duration fixture 실패 조사·수정 (첫 보고)

- 현재 branch codex/rt11a-source-upload/HEAD fd0595def4026605530cc4f31c6613481e2a9746를 유지하고 clean worktree·빈 staging에서 시작했다. PR382 원격 run39418471074/job118613193000 원본 로그와 job/run/PR JSON·hash를 새 .codex-scratch/rt11a-ci382-20261020에 보존했다. boundary-check PASS, python-tests9381PASS/27SKIP/1FAIL/1538.27초이며 실패는 test_receive_abort_sends_no_status_and_never_registers[duration]의400/ASGI3messages다. 후속 MySQL execution gate는SKIPPED였고 성공으로 간주하지 않는다. 원격 CI 재실행은 하지 않았다.
- Ubuntu24.04.1/Python3.12.3/uv0.11.15/동일 lock으로 원래 테스트400을 재현했다(CI Python3.12.15 차이 공개). 최초 exact-Python 설치 불가·missing-basetemp-parent는 setup 오류로 보존하며 테스트 RED로 세지 않는다. 계측상20ms씩 받는 세 번째 b'-'가 upload66.931ms에 parser로 들어가70ms deadline 전에 malformed400/등록0이었다. 같은 실제 지연·상수에서 유효한 open multipart는 duration/ASGI0/등록0이었다. 원격의 실제 chunk별 경과 시간은 로그가 없어 확인할 수 없고 위 수치는 로컬 계측이다.
- 제품 결함을 가정해 parser 오류를 숨기지 않았다. test-local 수신clock을 byte마다20ms씩 진행한 결정적 RED를 먼저 보존하고, duration 입력만 유효한 열린 part+data로 바꿨다. 무응답·등록0에 정확한 종료사유duration·4chunk 소비·staging payload xxx·final0을 추가 확인한다. idle/disconnect와 실제 wall-clock CLI timeout 회귀는 유지한다. sleep 증가·상수 완화·제품/Contract/Baseline/의존성/workflow/DB/gate 변경0이다.
- 직접 실행: Linux focused3 PASS·Windows focused3 PASS. 첫 Linux104 회귀는94PASS/10FAIL/149.52초로 보존했으며10개는 모두5초 child timeout이었다. import 측정은 /mnt/c5.545초/native1.936초였고192개 동일 SHA source snapshot으로 child import만 native로 바꿔 같은4모듈·같은timeout104PASS/skip0/86.34초(wrapper89.734초/exit0/source unchanged)를 확인했다. 단일 benchmark로 모든 timeout 원인을 확정하지 않으며 실패 보고서는 그대로 둔다. 새 Git checkout/worktree를 만들지 않았다.
- fresh reviewer는 수정에 참여하지 않고33 HTTP/실제CLI timeout PASS(기본GiB2건만 제외)를 직접 실행했다. 메모리에서 duration 제거·close 제거·잘못된 종료사유 세 negative control이 각각 의도한 assertion으로 실패함을 확인했다. 원본 remote log hash,192개 source equality,최초10timeout도 독립 대조했다. 제품/DB 코드가 그대로이고 helper 기본 receive 경로·MySQL 소비자가 유지되어 현 단계의 전체 local pytest/새 DB 재실행은 불필요하다고 판정했다. 남은 P1/P2는 확인되지 않았으나 새 head의 원격 전체 pytest와 strict MySQL gate 통과는 이후 필수다.
- boundary/Contract fixture/diff PASS. src192개+gate/harness/inventory/workflow/dependency 등198파일 HEAD 대조 변경0. 원래 Log raw prefix를 보존한다. 새 task의 Linux upload67파일/Windows3파일은 hash 뒤 제거했고 소유 testPython process 잔여0·native process/listener cleanup assertion PASS다. 새 MySQL server/schema/account 생성0,공유 relay 중지0. 새 비활성 env/cache/native snapshot·raw pytest/log는 PR 제외이며 기존 scratch/RAW/archive/pytest 증거는 수정·삭제하지 않았다.
- 수정 전달은 tests/api/test_sources.py 및 Runtime note/log 총3파일이다. RT-11 IN_PROGRESS. Refs #298 (RT-11(a)). PR382는OPEN,merge SHA pending. 사용자가 요청한 첫 보고를 위해 staging/commit/push 없이 멈추며 현재 보정의 원격 CI/MySQL gate 성공·병합 준비 완료는 아직 확인되지 않았다. 후속 새 commit/push의 CI 통과가 최종 목표로 남는다.


- 후속 audit 한계: reviewer 전용 fixture 정리는 파일 제거 뒤 느린 metadata 확인 중 중단되어 메모리의 개별 hash/count를 JSON으로 쓰지 못했다. 정확한 삭제 수·hash 기록을 복원하거나 추정하지 않는다. root의67 Linux/3 Windows hash 기록과 원본 raw log/XML은 보존됐으며 reviewer의 정확한4개 임시 root는 별도 읽기 전용 잔여 검사로 확인한다. 이 제한은 제품/gate 판정 및 원본 실패·성공 기록과 구분한다.


## 2026-10-21 RT-10(a) produced object gate 착수 · TDD 검증

**RT-10 IN_PROGRESS · Refs #297 (RT-10(a)) · PR pending · merge SHA pending.**

- 최신 develop/HEAD 596e8a162b71949e7b3189e994921bb6247aac4b와 Issue #297·#346 본문/댓글, Plan RT-10·12.2/12.3, Case observation-storage, JobExecution Contract, 현재 Worker T1을 대조했다. #346 Implementer 댓글의 O-1~O-3 경계로 구현하며 Search O-4 대기는 유지한다.
- common/jobs/produced.py·runtime_0005가 opaque append-only JSON 객체를 보존하고 Worker T1 terminal·produced와 동일 Connection/transaction에서 쓴다. 무ID ref는 execution/ordinal 고정이며 COMMIT 불명은 payload까지 확인하고 누락을 사후 보충하지 않는다. 기존 ProducedReader callable을 구현하고 다중 객체 의미 조립은 주입한다.
- Plan 대비 결과 저장소 gate를 첫 slice로 분리했다. Contract/Accepted Decision/Baseline 및 다른 Owner 공개 surface 변경 없음. 실제 Search/readout handler·Case StoredObservationAdapter/8-13·recording export·RT-11 변경 없음.
- baseline unit81 PASS; payload unit RED10→GREEN10; MySQL RED22→GREEN22; 직접 T1 receipt RED3→receipt/batch GREEN4; 실제 MySQL 기존 Worker/T2/redelivery/migration 회귀274 PASS/319.66초/drift0를 확보했다. 새 migration의 head/table 기대값만 보정하고 이전 frozen migration을 유지했다.
- 독립 reviewer가 nested ProducedObject의 missing-ref/extra 변조 P2를 재현했다. RED3 FAIL/1 기존 PASS 뒤 exact tuple/type/stored-field 검증을 보완했다. 관련 단위회귀74 PASS 및 최종 새 MySQL26 PASS/30.49초/drift0다. 독립 후속 재리뷰와 원본 strict mandatory 전체·mutation 결과는 진행 중이다.
- strict checker 함수 AST·기존 모든 필수 inventory·frozen migration15·workflow30분·mandatory nested900초를 보존하고 신규26parameter/12family만 추가했다. 최초 gate inventory RED11을 확보했다. 경계위반0·Contract fixture62/26/104 PASS다.
- 최초 temp setup 오류와 WSL 접근 실패, 중간 inventory 확장 중 중단한 gate unit, migration RED8 FAIL/19 PASS와 해당 실행의 별도파일 drift3건은 별도 실패/중단 기록이며 final PASS로 소급하지 않는다. 상세 선택·원본 증거·최종 제한은 RT-10(a) note에 기록한다.
- 소유 전용 MySQL8.4.7을 사용한다. 현재 원격CI 미실행, 전체 RT-10 IN_PROGRESS. 최종 stage/commit/push/PR 없이 독립 재리뷰 가능 상태로 남긴다.


### RT-10(a) 독립 리뷰 P2 보완 · lossless JSON · 전체 gate 진행

- 독립 reviewer는 nested object shape 변조와 native MySQL JSON의 큰 정수 coercion 두 P2를 재현했다. 전자는 exact type/field 검증으로 보완했고, 후자는 실제 MySQL RED2 뒤 strict JSON LONGTEXT binder로 보완했다. 모듈에 새 숫자 범위를 요구하지 않고 JSON primitive/정수를 그대로 보존한다. 새 MySQL28 PASS/32.43초/drift0이며 reviewer 직접 unit14·DDL 일치·binder roundtrip PASS다. 남은 P1/P2는 보고되지 않았다.
- 최종 신규 inventory는28parameter/13family다. gate/payload/Worker unit6364 PASS/711.49초(wrapper717.562초/exit0/drift0)를 확보했다. 기존 checker 함수·기존 inventory·frozen migrations15·workflow30분·nested900/outer1800을 유지한다.
- 첫 완료 mandatory child는834개 중832 PASS/2 FAIL,2502phase,661.778초였고 strict가 거부했다. parent1 FAIL/673.985초/drift0를 보존한다. 실패는 Recording migration head의 runtime_0004 기대값 한 곳과 로컬 비TLS PyMySQL caching_sha2 인증 오류다. Recording 테스트의 기대 문자열만0005로 보정한 원본1 PASS와 기본 TLS 인증 원본1 PASS를 확인했다. 제품/dependency/auth 정책·테스트 identity·gate 조건은 바꾸지 않았다.
- gate unit 이후의 소스 차이는 위 Recording head assert1곳뿐이며 unit 대상 밖이다. 해당 파일의 역치환 SHA와 나머지 source/checker/inventory 해시로 동등성을 확인한다. 현재 원본 mandatory 전체를 기본 TLS로 다시 실행하며 이 결과 전에는 strict 전체 PASS를 주장하지 않는다. 전체 pytest/원격CI 미실행, RT-10 IN_PROGRESS·Refs #297 (RT-10(a)).


### RT-10(a) 원본 mandatory timeout 보존 · 로컬 CA/TLS 비용 확인

- 기본 TLS 원본 mandatory도 nested900초 TimeoutExpired, parent1 FAIL/900.93초(wrapper904.906초/drift0)였다. partial report 합성이나 timeout 증가로 성공 처리하지 않았다. 이번 command line 자식 잔여0을 확인했다.
- 설치 PyMySQL1.2.3/SQLAlchemy2.1.3/cryptography50.0.1/pytest8.4.2는 lock과 같으며 제품/dependency 변경0이다. PyMySQL의 매 연결 default SSLContext 생성과 로컬8회 실측을 확인했다: 기본TLS0.547초, 전용 공개CA 명시TLS0.218초. 이 표본을 전체 timeout의 유일 원인으로 단정하지 않는다.
- 이번 소유 서버의 공개CA만 scratch로 읽어 허용된 ssl_ca/ssl_check_hostname=false URL 옵션을 사용한다. TLS cipher·CA 검증을 유지하고 DB권한/durability·기존 테스트/gate/nested900/outer1800/workflow30분을 유지한다. 처음 잘못 조합한 verify 옵션의 certificate 오류는 별도 보존하고 SQLAlchemy 지원 옵션으로 고쳤다.
- 전용CA/TLS에서 인증 원본+새저장소28개29 PASS/21.62초/drift0다. 현재 원본 mandatory 전체를 다시 실행 중이며 최종 PASS는 아직 판정하지 않는다. RT-10 IN_PROGRESS · Refs #297 (RT-10(a)).


### RT-10(a) 전용 CA/TLS 전체 실행의 기존 startup 실패 보존

- 전용CA/TLS 원본 mandatory child는834 selected/2502phase 중833 PASS/1 FAIL,720.588초였다. parent1 FAIL/732.344초/drift0이며 strict 전체 PASS가 아니다. 유일한 실패는 기존 RT-11 upload interruption before_publish의 API 자식8초 startup deadline이었다. RT-11 제품/fixture/제한은 변경하지 않았다.
- 같은 원본 startup4모드는 재확인에서4 PASS/16.38초(wrapper19.609초/drift0)였다. 같은 소스/CA/TLS/테스트/nested900/outer1800으로 원본 전체를 다시 실행한다. 이 별도4 PASS를 앞선 전체 성공으로 합성하지 않는다.
- 독립 reviewer는 CA 옵션이 기존 허용 목록에 있고 endpoint/account/schema가 같으며 CERT_REQUIRED·CA일치·암호화연결·plaintext fallback 없음·MySQL8.4를 직접 확인했다. 제품/dependency/gate/timeout 변경은 없다. RT-10 IN_PROGRESS · Refs #297 (RT-10(a)).


### RT-10(a) 필수 strict gate 통과 · 최종 인계

**RT-10 IN_PROGRESS · Refs #297 (RT-10(a)) · PR/merge SHA pending.**

- 같은 소스·CA/TLS·원본 테스트·nested900/outer1800으로 실행한 mandatory-owned-ca-retry가1 PASS/1088.23초(wrapper1090.61초/exit0/source drift0)로 끝났다. 실제 MySQL8.4.7 child834 PASS/2502PASS phase,682.994초,skip0/xfail0이며 strict JSON/JUnit CLI PASS다.
- 원본 함수의 parameter mutation5997건(기존5633+신규364)과 신규 metadata/family omission125건이 모두 거부됐다. root 별도 audit는 exact Counter·원본 report before/after SHA·현재 mandatory source hash를 대조했다. 기존 checker 함수 AST/필수 inventory·frozen migration15·workflow30분·900/1800제한을 보존했다.
- 독립 reviewer는 코드 P2두건 보완·unit14·DDL·binder와 actual child834/2502·JSON/JUnit·신규28parameter/13family·563source hash 및 기존 gate 보존을 직접 확인했다. parent 전체 mutation은 root audit이며 reviewer가 원본 전체를 다시 실행한 것으로 표현하지 않는다. gate/payload/Worker unit6364 PASS와 이후 Recording head assert1곳의 별도 PASS/해시 동등성도 유지한다.
- 앞선 전체 실패·timeout·중단은 보존한다. 현재 source의 전체 pytest와 원격CI는 미실행이다. 실제 handler/Case stored adapter/8-13/recording export/RT-11 제품·fixture 변경은 하지 않았다. Contract/Accepted Decision/Baseline·다른 Owner 공개 surface 변경 없음이다.
- 소유 orphan schema3개를 확인·정리했고 종료 전 transaction0·기본schema5개·기본계정을 확인했다. Linux shutdown/datadir 정리 뒤 helper의 Windows relay port assertion exit1을 보존한다. 사용 한도에 따른 자동승인 검토 실패로 마지막 점검이 미실행됐으나 사용자 재개 뒤 완료했다. 현재 Windows54381/Linux listener·임시datadir·검증 자식 잔여0이며 공유relay 강제종료0이다. resource-final.json에 실제 관측과 최초 실패를 함께 남겼다.
- 최종 전달은22파일 미커밋·미스테이징이다. 독립 재리뷰용 note는 docs/runtime/rt10a-produced-store.md, 파일/증거 해시는 ignored .codex-scratch/rt10a-20261021/handoff-manifest.json이다. stage/commit/push/PR 생성은 하지 않는다.


### RT-10(a) 최종 fresh 독립 재리뷰 후속 기록

**IN_PROGRESS · Refs #297 (RT-10(a)) · PR/merge SHA pending**

- 사용자에게 전달된 최종 fresh 독립 reviewer 판정은 **추가 P1/P2 없음**이다. RT-10(a) 22개 파일은 검증 결과와 제한을 공개한 커밋·중간/draft PR 준비가 가능하다는 판정이다. 이번 후속 기록에서는 테스트를 재실행하지 않았으며, 커밋·푸시·PR 생성도 수행하지 않는다.
- reviewer 직접 검증: produced·Worker **74 PASS**, strict JSON/JUnit CLI 재검사 **PASS**, boundary·Contract·diff 검사 **PASS**다. 아래 보존 증거 대조와 구분하며 reviewer가 전체 unit·MySQL·mutation을 새로 실행한 것으로 표현하지 않는다.
- reviewer의 보존 증거 대조: unit **6,364 PASS**, 실제 MySQL **834 PASS / 2,502 phases**, parameter mutation **5,997건 모두 거부**, metadata/family 누락 **125건 모두 거부**다. 기존 필수 inventory와 원본 보고서를 유지하며 이전 실행들을 합성해 새로운 전체 PASS를 만들지 않는다.
- 과거 setup error·실패·900초 timeout·startup deadline 실패는 각각의 별도 원본으로 유지한다. 앞선 이력과 원본 증거를 수정하거나 덮어쓰지 않는다. 전체 pytest와 현재 diff의 원격 CI는 미실행이다.
- 비차단 위험: LONGTEXT에 대한 privileged raw SQL 변조를 DB JSON constraint가 차단하지 못하는 한계, 과거 timeout·startup deadline 실패의 재발 가능성이 남는다. 다중 객체의 의미 조립과 외부 ref 배선은 후속 작업이다.
- 이번 판정은 RT-10(a) 결과 저장소 gate 범위다. 전체 RT-10은 미완료이며 실제 handler·Case adapter 등 후속 범위의 완료를 뜻하지 않는다. **IN_PROGRESS · Refs #297 (RT-10(a)) · PR/merge SHA pending**을 유지한다.

## 2026-10-21 RT-11(b) 착수 · Owner 승인 해석 · RED→GREEN

**RT-11 IN_PROGRESS · Refs #298 (RT-11(b)) · PR pending · merge SHA pending.**

- 현재 `codex/rt11b-frame-read`/HEAD `c491a95b8726377c2eca2ac3dad6bcc6ce416670` 및 clean working tree/빈 staging, 최신 원격 develop 일치를 직접 확인했다. 새 branch/worktree를 만들지 않았다.
- PR #382의 develop 병합 SHA `596e8a162b71949e7b3189e994921bb6247aac4b`, boundary-check/python-tests SUCCESS 및 MySQL gate811/skip0/xfail0를 직접 확인해 후속 기록한다. PR #385의 develop 병합 SHA `c491a95b8726377c2eca2ac3dad6bcc6ce416670`, boundary-check/python-tests SUCCESS 및 MySQL gate839/skip0/xfail0도 선행 상태로 확인했다. 기존 pending·실패·timeout 이력을 수정하지 않으며 이번 diff 검증으로 재사용하지 않는다.
- Issue #298 본문·전체 댓글2개와 제안6292559346/Runtime·HTTP Owner 승인6306955258을 직접 확인했다. 승인대로 semaphore 획득→짧은 ownership+stored FrameImage load→Connection 반환→HTTP header/bytes 전송 순서로 구현한다. Plan/Baseline 원문은 고치지 않으며 새 Gate/Case association/mediation/callback은 없다.
- Recording에 최소 공개 `read_owned_frame_image`를 추가했다. API schema/private 조회 없이 기존 소유 관계와 저장 이미지 capability를 조합하고 caller transaction 소유를 유지한다. 기본2 제한, safe404/typed unavailable, 실제 Content-Type/Length와 B-F1 cache를 적용한다. 관측은 기존 ApiEvents/allowlist의 wait/응답 준비 latency/count 이벤트이며 raw ref/path/예외는 넣지 않는다.
- RED 보존: 초기 sandbox13 ERROR/3 FAIL 및 정지 시도는 환경 실행 실패로 분리했다. 유효 RED13 FAIL/3 PASS→GREEN16 PASS. 신규 frame inventory family 누락6 FAIL도 보존한 뒤 checker에 추가했다.
- 실제 MySQL 첫 실행13 PASS/4 FAIL은 신규 fixture의 SecretStr env 전달 및 전역 checkout assertion 동기화 오류로 확인했다. 제품 코드를 바꾸지 않고 보정 후17 PASS/skip0/xfail0/source drift0다. 두 fresh interpreter 복원·실제 pool/disconnect·소유 격리·caller rollback/uncommitted·대기/느린 전송 checkout0·취소/permit 경계를 포함한다.
- 전체 필수 MySQL 원본 nested900/strict JSON/JUnit·누락 mutation 및 관련 회귀를 진행 중이다. timeout·workflow30분·skip/xfail 정책은 불변이다. 현재 전체 pytest/원격CI/별도 독립 재리뷰는 미실행이며 reviewer/subagent는 사용자 요청대로 호출하지 않는다.
- 상세 Implementation Notes/선택/위험은 [RT-11(b) note](./rt11b-frame-read.md), 원본 증거는 ignored `.codex-scratch/rt11b-20261021/`다. staging/commit/push/PR 없이 미스테이징 상태를 유지한다.

### 2026-10-21 RT-11(b) 직접 검증 완료 · 제한 공개 · 별도 독립 재리뷰 대기

- 같은 제품/test source로 원본 mandatory child851 PASS/2553 phases/484.666초, skip·xfail·JUnit 실패0 및 strict JSON/JUnit CLI PASS851을 확인했다. parent1 PASS/892.62초(wrapper894.672초/exit0/source drift0)이며 nested900과 workflow30분을 유지했다. parameter mutation6218건 모두 거부, 신규 frame221건과 metadata68/family6 누락 거부를 포함한다. gate unit6483 PASS/484.86초/source drift0다.
- 관련 API/Recording 비MySQL 전체는779 PASS/기존 외부 미디어15 SKIP/1 FAIL/201 deselected다. 유일한 실패 node는 test_composition_failure_exits_within_five_seconds_after_ready_trigger이며 phase/stack은 GO 전 setup_import_watchdog_5s와 기존 search/coarse import의 importlib.get_data를 가리켰다. 새 frame route import 전이고 정확한 import 지연 원인은 단정하지 않는다. 모든 무거운 실행 종료 뒤 source/deadline 불변으로 해당 node만1 PASS/3.19초 재확인했다. 원본 broad 실패는 보존하고 합성 전체780 PASS로 바꾸지 않는다.
- boundary0, Contract62구조/26JSON/104의미, 관련 workflow2개 actionlint, diff-check를 직접 확인했다. checker 함수AST·기존 inventory·migration16개·workflow byte는 보존하며 신규frame6 scenarios/17 parameters만 추가했다.
- bare 전체 pytest는 미실행이다. 전체 필수 MySQL이 API/Case/Worker/Recording persistence/공용 DB·jobs·usage·migration을 포함하고 관련 API/Recording 전체 비MySQL 및 gate unit을 별도 실행했으므로 중복되는 전체/nested 재실행을 줄였다. 미변경 Search/readout/evidence 등 untouched suite 위험과 현재 diff 원격CI는 남는다. PR#382/#385의 과거 CI를 대체 증거로 쓰지 않는다.
- 소유 MySQL 마지막 감사는 system4+base1 schema/기본계정4/다른client0/transaction0/data lock0이었다. 첫 감사 helper 자신의 transaction1은 connectionID6689 대조로 확인하고 AUTOCOMMIT 감사로 보정했으며 원본 실패도 유지했다. init/server 로그를 보존한 뒤 SHUTDOWN했다. 소유 mysqld·Linux listener·datadir·Windows Python helper는 없다. 다만 원본 helper 최종 port assertion은exit1이고 Windows 공유 wslrelay PID2736/port62840 listener가 남았다. 공유 WSL/relay를 변경하지 않았으며 전체 정리PASS/잔여0을 주장하지 않는다.
- 비차단 위험은 현재 source의 startup watchdog 실패 이력/재발 가능성, 공유 OS relay 잔여, 큰 bytes의 packet/RSS·기존PNG 식별 범위·RAM 검증의 전원장애 내구성 한계다. 신규 제품/Owner 판단 blocker는 발견하지 않았다. 현재 CI와 사용자 주도의 별도 독립 재리뷰는 대기다.
- 변경18파일 전체 목록과 PR Implementation Notes는 [RT-11(b) note](./rt11b-frame-read.md)에 있다. `.codex-scratch/**`·RAW·JSON/JUnit·runner·임시DB/datadir·media·진단은 PR 제외다. 사용자 요청대로 reviewer/subagent 호출·staging·commit·push·PR 생성 없이 독립 재리뷰 가능한 상태에서 멈춘다. **RT-11 IN_PROGRESS · Refs #298 (RT-11(b))**를 유지한다.

### RT-11(b) 최종 자원 후속 검사

- 원본 assert_port_closed를 같은62840에 다시 실행해 PASS했고 Linux listener0/MySQL handshake 없음/이 작업 소유 Windows Python0을 확인했다. 최종 검사 시 포트 잔여는 해소됐다. 공유 WSL/relay를 변경한 적은 없고 제거 시점·원인은 단정하지 않는다.
- 초기 helper exit1 및 당시 wslrelay listener·감사 실패 원본은 그대로 보존하며 후속 poststop-status.json의 closed=true로 소급하지 않는다. 현재 소유 DB/server/schema/account/connection/datadir/listener/process 잔여는 없으며 OS forwarding 지연의 이력은 위험 설명으로 남긴다.

## 2026-10-21 RT-11(b) 독립 재리뷰 P2 검증·TDD 수정

**RT-11 IN_PROGRESS · Refs #298 (RT-11(b)) · PR/merge SHA pending.**

- 사용자 지정 final-review.md와 reproduce.py를 직접 읽고 새 scratch 복사본으로 재현했다. concurrency2에서 body send3/선행 latency200 세 건, 손상 foreign503 대 unknown404가 재현됐다. 리뷰의 손상 row probe는 live DB가 아니라 row transport 주입임을 구분하며 이번 실제 MySQL 검증을 추가했다. 원본 리뷰·기존 증거는 수정하지 않는다.
- P2-1 RED: 실제 payload/final ASGI send와 정상/cancel/disconnect/OSError/예상 밖 오류10건 및 P3 status4건이 실패(14 FAIL/9 PASS). permit을 outer pure ASGI middleware로 옮긴 뒤 동일23 PASS다. BaseHTTPMiddleware 안의 Response 수명으로 옮기는 방식은 쓰지 않았다. read cancellation은 실제 thread/DB cleanup까지 deferred release하며 모든 경로의 단일 반환/후속 admission을 검사한다.
- P2-2 실제 MySQL RED3 FAIL/2 PASS(손상 frame/stream/link가 foreign503), GREEN5 및 공개 capability 회귀3 PASS다. Recording repository 내부 단일 SELECT가 frame→stream→source→case_asset 관계를 binary identity로 제한하고 같은 statement snapshot에서 owned metadata/bytes만 복원한다. caller connection/transaction과 기존 standalone capability 의미는 유지한다. API의 schema/private query 우회나 새 공개 capability는 없다.
- RC의 여러 SELECT check/read gap을 없애고 단일 statement consistent snapshot을 사용한다. uncommitted 관계 삭제는 보이지 않고 commit 뒤 다음 statement는 UNKNOWN_REF이며 reader/writer transaction은 호출자 소유임을 실제 MySQL로 검사했다. 새 retention/reassociation 정책·row locking·Case callback을 추가하지 않았다.
- 수정된 frame/API/Recording 직접59 PASS. 실제 TCP backpressure/disconnect도1 PASS다. 앞선 TCP2실패는 단일 큰 write에서 두 동시 blocked send가 관측되지 않은 fixture 실패로 보존한다. 실제 Uvicorn send를 합법적인 ASGI chunk로 분할하는 서버 adapter로 drain을 관측했고 timeout/제품 분기는 바꾸지 않았다.
- 신규 parameter17개를 추가해 frame34개/8families다. 새 family 누락 gate RED2도 보존했다. DB 경로와 inventory 변경 때문에 현재 source의 전체 원본 mandatory MySQL/strict/mutation 및 전체 gate unit을 직접 실행 중이다. 기존 function AST/inventory, migration16개, workflow30분과 nested900은 보존했다.
- P3는 P2-1의 실제 전송 수명에 관측을 통합하고 실제 HTTP status를 기록하는 작은 범위에서 수정했다. 새 metric/config/Owner 정책은 만들지 않는다. ASGI send 반환은 client의 수신 ACK를 증명하지 않으며 이 transport 한계는 유지한다.
- 과거 import watchdog의 원인 미확정 위험·원본779/1 실패와 단독1 PASS는 그대로다. reviewer/subagent, staging/commit/push/PR은 수행하지 않는다. 새 증거는 ignored `.codex-scratch/rt11b-p2-20261021/`에 보존하며 상세와 최종 결과는 RT-11(b) note에 후속 기록한다.

### RT-11(b) P2 수정 직접 검증 완료 · 별도 독립 재리뷰 대기

- 현재 source의 전체 필수 MySQL child868 PASS/2604 phases/621.982초, skip·xfail·failure·error0 및 원본 strict JSON/JUnit CLI PASS868이다. parent1 PASS/1216.33초(wrapper1218.719초/exit0/source drift0)이며 nested900과 workflow30분을 바꾸지 않았다. parameter 누락6439건 모두 거부(frame442 포함), frame metadata136/family8 누락144건 모두 거부했다. gate unit6672 PASS/766.81초/exit0/source drift0다.
- API·Recording 전체 비MySQL/process 회귀790 PASS/기존 외부 미디어15 SKIP/218 deselected/262.11초/exit0/source drift0다. 과거 broad779/1 및 단독1 PASS 원본은 보존하고 현재 PASS로 소급하지 않는다. import 지연의 정확한 원인과 재발 위험은 여전히 미확정이다.
- boundary0, Contract62구조/26JSON/104의미, 두 workflow actionlint PASS다. checker 함수AST·기존 inventory·migration16개·workflow bytes 및 strict gate 정책을 유지한다. 별도 ASGI/TCP TDD 원본과 초기 TCP fixture2 FAIL도 보존한다.
- bare 전체 pytest는 미실행이다. 전체 필수 MySQL·누락 mutation·gate unit과 관련 API/Recording/process 비MySQL을 직접 다시 실행했으므로 겹치는 full/nested 반복은 줄였다. 미변경 도메인 비MySQL 전체·현재 diff 원격CI·별도 독립 재리뷰가 남으며 선행PR CI나 최초 구현851/6483을 이번 결과로 재사용하지 않는다.
- 종료 전 소유 MySQL8.4.7 감사는 system4+base1 schema/기본계정4/다른client0/transaction0/data lock0/commit flush1/fsync였다. 로그 보존 후 SHUTDOWN/UUID datadir 정리했다. Linux mysqld/listener/datadir와 소유 Windows Python은 없다. helper 최종 포트 assertion exit1 및 첫 관측의 Windows52571 공유 wslrelay PID30640 listener는 별도 보존한다. 공유 WSL/relay는 변경하지 않았으며 후속 상태는 추가 기록한다.
- 두 P2는 직접 RED→GREEN으로 수정했다. P3도 새 관측 정책 없이 실제 ASGI 수명/status로 바로잡았다. 미해결 제품 blocker는 발견하지 않았으며 별도 독립 재리뷰·현재CI가 필요하다. 과거 watchdog·OS forwarding 지연·큰 bytes/RSS·PNG 식별·RAM 내구성 한계는 남는다. 전체22파일 목록·PR Implementation Notes·원본 위치는 [RT-11(b) note](./rt11b-frame-read.md)에 있다. scratch/RAW/JSON/JUnit/runner/임시DB/진단/외부리뷰는 PR 제외이며 원본을 삭제하지 않는다. reviewer/subagent·staging·commit·push·PR 생성 없이 **RT-11 IN_PROGRESS · Refs #298 (RT-11(b))**를 유지한다.

#### P2 수정 후 최종 자원 확인

- 원본 assert_port_closed를 동일52571에 다시 적용해 PASS했다. Windows listener/소유Python0, Linux listener/소유mysqld0이며 WSL `test ! -e`의 직접 인자로 생성 UUID datadir 부재도 확인했다. `poststop-direct-status.json`은 최초 `poststop-status.json`과 별도로 보존한다. helper exit1/relay 잔여 이력을 소급하지 않으며 해소 시점·원인은 단정하지 않는다. 공유 WSL/relay 변경 없이 현재 소유 테스트 자원 잔여는 없다.

## 2026-10-21 RT-11(b) 후속 독립 재리뷰 P1 검증·TDD 수정

**RT-11 IN_PROGRESS · Refs #298 (RT-11(b)) · PR/merge SHA pending.**

- 후속 reviewer 보고서/실제 MySQL 재현부를 직접 읽고 복사본으로 재현했다. MySQL8.4.7의 utf8mb4_bin PAD SPACE/공백 비교1, 기존 owns_frame=False 대 신규 capability foreign PNG68bytes·HTTP200/unknown404를 확인했다. 기존 P2 후속 판정을 소급 수정하지 않는다.
- 실제 column/index/collation과 길이 없는 CAST AS BINARY/NO PAD 후보를 대조했다. trailing/leading/multiple space·case·비ASCII/정규화 차이·긴 값은 binary cast에서 구분되고 self는 일치했다. 신규 단일 ownership query의 JSON 관계·case/kind identity와 table-kind residual만 정확 비교로 바꿨다. frame의 SHA256 unique index 후보와 기존 FrameRef 복원 validation은 유지한다. EXPLAIN frame const1row와 kind index 후보를 확인했다. schema/migration·모델 허용 범위·공개 surface·caller transaction/lock 계약은 바꾸지 않았다.
- capability RED6 FAIL/12 PASS, 독립 HTTP RED6 FAIL/12 PASS, case-scope RED1 → 첫 GREEN37 PASS다. owned FrameRef metadata의 기존503 의미 회귀RED1을 추가해 과한 후보 predicate를 제거했고 최종 frame/API/Recording/TCP98 PASS/80.98초다. 정상 양방향 bytes200·foreign/unknown404·손상 foreign404·owned503/unavailable, 기존 P2 ASGI 수명/취소/disconnect/전송 예외/checkout0와 transaction 경계를 포함한다.
- 신규 exact_identity family 누락RED1을 보존했다(첫 선택식0건은 유효RED가 아님). inventory는72 parameters/9families이며 이전34/8을 포함한다. 현재 source의 전체 필수 MySQL·strict 원본 JSON/JUnit·누락 mutation·gate unit·관련 process 회귀를 직접 검증 중이다. workflow30분/nested900/skip·xfail 정책과 기존 checker 함수는 유지한다.
- 추가로 기존 get_case_assets가 정확히 존재하지 않는 case_id+공백 alias에 owns_frame=True를 반환하는 관측을 보존했다. 수정된 신규 capability는 UNKNOWN_REF/HTTP404다. 기존 경로로 범위를 확대하지 않으며 별도 Owner/보안 검토 항목으로 보고한다. 기존 전체 surface의 다른 실제 case bytes 노출을 이 probe로 단정하지 않는다.
- 과거 watchdog 실패·기존 리뷰·실패·RAW를 보존한다. 새 원본은 ignored `.codex-scratch/rt11b-p1-20261021/`이며 상세 선택/SQL/검증/위험은 [RT-11(b) note](./rt11b-frame-read.md)에 있다. reviewer/subagent·staging·commit·push·PR 생성 없이 미스테이징 상태를 유지한다.

### 2026-10-22 RT-11(b) 사용한도 중단 후 검증 재개

- 중단 전 mandatory-p1 완료 원본을 확인했다. child906 PASS/2718 phases/761.840초, skip·xfail·failure·error0이며 재개 후 현재 strict JSON/JUnit CLI PASS906이다. parameter 누락 mutation6933건 전부 거부(frame936 포함), frame metadata288/family9 누락297건 전부 거부다. source drift0이고 이전868 PASS를 이번 결과로 재사용하지 않는다.
- parent1 PASS/3453.90초(wrapper3453.063초/exit0)였다. 실행 중 System 절전/복귀 이벤트21:47:50/22:23:01을 관측했다. 원인 기여도를 임의 산정하지 않으며 parent wall time을 workflow30분 충족으로 표시하지 않는다. 설정된 child900/wrapper1800과 workflow30분은 그대로고 현재 원격CI budget은 미검증이다.
- 재개 시 원래 helper/MySQL listener/RAM datadir는 보이지 않았다. 원래 server의 명시적SHUTDOWN/종료전 감사/로그 회수를 완료했다고 주장하지 않는다. 첫 gate-unit-p1은 끊긴DB preflight exit4로 별도 보존했다. 새 UUID server/CA는 resume-20261022/에 분리하고 남은 gate/회귀만 같은 source·900초 runner 제한으로 실행한다.
- 기존 P2 inventory 전부 유지+38 parameters/1family 추가(최종72/9), checker 함수AST 불변, 전체 migration17/workflow5 bytes 불변을 확인했다. boundary0/Contract62구조·26JSON·104의미/두 workflow actionlint PASS다. 기존 code 필터 migration16 집계와 구분한다. watchdog·이전 실패·리뷰 증거는 소급하지 않는다.

### RT-11(b) P1 검증 완료 기록 · 회귀 차단 사항 보존 · 별도 재리뷰 대기

- gate-unit-p1-resumed 전체7091 PASS/447.73초(wrapper452.5초/exit0/source drift0)다. 현재 전체 필수 MySQL906/strict·mutation6933 및 frame metadata/family297건 모두 거부와 구분해 보존한다. 과거 P2의868/6672를 이번 PASS로 재사용하지 않는다.
- 관련 API/Recording 전체 비MySQL/process는788 PASS/15 SKIP/2 FAIL/256 deselected/330.81초(wrapper337.11초/exit1/source drift0)다. 실패는 test_actual_server_cleanup_failure_exit_and_listener_release의5초 child timeout(빈 stdout/stderr), test_receive_abort_sends_no_status_and_never_registers[disconnect]의 expected[] 대 observed['idle']이다. 원본을 삭제하거나 합성 전체PASS로 바꾸지 않는다.
- 제한/clock/assertion 변경 전에 source·call 경계를 조사하고 phase 진단을 보존했다. 실제 cleanup 진단 child는 import 후 server 반환/listener/assertions를 완료했지만 launch포함 wall5.407초이므로 원래5초 deadline PASS로 쓰지 않는다. upload 진단은 실제 request→disconnect16ms/closed[]였다. 원래 두 node 분리 확인은1 FAIL/1 PASS이며 cleanup은 동일5초 timeout 재현, disconnect만PASS다. 원본 순간의 원인은 확정할 수 없고 제품/fixture/환경 원인 미확정의 현재 검증 차단 항목으로 유지한다. upload 의미나 process 제한은 바꾸지 않았다.
- SQL P1 재현은 해소됐고 이전 P2 targeted는 통과했으나 broad 회귀PASS/병합 준비 완료를 선언하지 않는다. 기존 case-id alias는 별도 Owner/보안 검토, 과거 import watchdog은 원인 미확정 위험으로 남는다. bare 전체pytest/현재원격CI/별도독립재리뷰는 미실행이다. 전체 필수MySQL/gate/관련회귀를 직접 실행했고 이미 관련 실패가 재현돼 중복full/nested를 반복해PASS를 만들지 않았다. 원격30분 budget·성공을 로컬/과거CI로 대체하지 않는다.
- 재개 후 소유server 감사는 MySQL8.4.7/system4+base1 schema/기본계정4/다른client0/transaction0/data lock0/commit flush1/fsync였다. 로그 보존 후 SHUTDOWN/생성UUID datadir 정리/helper exit0을 확인했다. 중단 전server의 종료전감사가 없다는 제한은 유지한다. 최종 잔여/파일해시는 후속 감사로 보존한다.
- 현재22개 후보 중 이번수정6개이며 전체목록/PR Implementation Notes/상세 실패·진단은 [RT-11(b) note](./rt11b-frame-read.md)에 있다. scratch·RAW·JSON/JUnit·mutation·runner·DB/CA/임시media·진단·외부리뷰는PR제외다. 기존 증거를 유지하고 reviewer/subagent·staging·commit·push·PR 생성 없이 검증 차단을 공개한 독립 재리뷰 가능 상태로 전달한다. **RT-11 IN_PROGRESS · Refs #298 (RT-11(b))**.

- 최종 poststop-direct-status는 port closed/datadir absent/Windows 소유Python·listener0/Linux 소유mysqld·listener0이다. 공유 WSL/relay 변경0이며 이전 두 server 포트도 closed다. final-audit.json에22파일 해시/이번6파일 차이/source 일치/staging0/이전Log prefix 보존/미해결 broad2 FAIL·단독1 FAIL을 함께 기록했다. 감사PASS를 전체 회귀PASS로 재분류하지 않는다.

### 2026-10-22 RT-11(b) 두 회귀 실패 systematic investigation 후속 기록

**RT-11 IN_PROGRESS · Refs #298 (RT-11(b))**

- 사용자 요청대로 원인 확정 전 제품/테스트를 고치지 않았다. 현재22파일/index hash를 보존하고 같은HEAD/develop c491a95b8726377c2eca2ac3dad6bcc6ce416670을 일반 archive로 추출해 비교했다. branch/worktree/reset/stash는 없었다. 새 scratch는 `.codex-scratch/rt11b-regression-20261022/`다.
- Cleanup 원래5초는 Popen 반환 뒤 communicate budget이며 child import/setup부터 EOF까지 포함하고 별도GO가 없다. 과거 parent stack의 stdout reader join만으로 당시 child phase/근본 원인을 복원할 수 없다. 동일AST/동일deadline 계측에서 current3.141초/base4.547초, cache 없는 snapshot pair current3.094초/base2.500초 모두 expected exit1이었다. Base4.2초 stack은 main 반환 뒤 socket probe/TCP0였다. Current broad는 communicate425873.125→425875.609, main1.969초/atexit2.282초, 종료 tasks0/checkout0/permit2·waiter0/child·TCP0이다. 실제signal 전송 없이 원래 handler 복원 assertion을 검사했다. 이 관측을 과거 timeout 원인 확정으로 부르지 않는다.
- Disconnect 순서 분할: 직전2+target3 PASS, 앞80+target81 PASS, 뒤80+target81 PASS, 전체160+target161 PASS; baseline의 존재하는 같은 묶음138 PASS다. 최소 오염 predecessor는 발견하지 못했다. thread/loop/process/socket/env/signal 복원과 fixture-local 상태를 확인했고 실제 request→disconnect/등록0/closed[]/checkout0/permit2를 관측했다. Native clock15.625ms 해상도와40ms 민감성은 관측일 뿐 과거 원인 확정이 아니다. timeout/sleep/clock/재시도/assertion/skip/xfail 정책은 바꾸지 않았다.
- 외부 phase/timing 관측을 넣은 원래 API/Recording broad790 PASS/기존15 SKIP/256 deselected/184.38초/source drift0, fresh frame/API/Recording/TCP98 PASS/51.55초(실제MySQL72/216 phases/skip·xfail0)다. 계측 child prefix/wrapper를 공개하며 무계측 broad라고 표현하지 않는다. 원래 child를 쓴 선행161/current·138/baseline PASS와 구분한다. 과거2 FAIL/단독1 FAIL 및 import watchdog 실패는 소급하지 않는다. 제품/테스트수정0이며 추측성RED→GREEN은 없다.
- 현재checker로 보존된 전체906/2718-phase 원본 strict PASS, 독립frame parameter936/metadata288/family9 누락1233건 모두 거부, frame gate unit801 PASS/6290 deselected/24.63초다. 기존 전체906/6933 mutation/7091 gate의 source/config 일치를 대조하며 새 전체실행으로 표현하지 않는다. Boundary0/Contract62·26·104/두workflow actionlint PASS다. 제품/test/config 불변이라 전체pytest/MySQL/gate를 반복하지 않았고 현재원격CI는 미실행이다. 기존30분/900초와inventory정책은 불변이다.
- 현재 직접 관련 회귀는GREEN이지만 과거 child/idle 원인과 RT-11(b) 인과관계는 확정하지 못했다. 기준PASS만으로 무관함을 입증했다고 하지 않으며 역사적실패해소/최종병합승인도 선언하지 않는다. 현재GREEN 증거와 재발불확실성을 함께 독립 재리뷰할 수 있다. 별도 기존alias 보안관측/Issue 후보는 PR제외 scratch에 분리하고 기존경로를 수정하지 않았다.
- 이번 round 변경은 note/Log의 추가기록2개뿐이며 전체22개 후보는 그대로다. reviewer/subagent·staging·commit·push·PR/Issue 생성은 하지 않는다. Scratch/archive/원본JSON·JUnit/stack·process/runner/DB·CA/media/별도보안자료는PR제외이며 이전실패·리뷰를 유지한다.

- 이번 조사server는 종료 전 MySQL8.4.7/system4+base1/계정4/다른client0/transaction0/data lock0를 감사하고 로그 보존 뒤SHUTDOWN/helper exit0으로 정리했다. 최종datadir absent/port closed/Windows 소유Python·listener0/Linux mysqld·listener0, 추가 matching Python0이다. 공유 WSL/relay 변경0이며 final-audit.json에 제품/test/config 불변·이번문서2개·index byte/staging0·현재계측GREEN·역사원인미확정을 함께 기록했다. Fresh frame72개만의 부분report는 전체strict gate에서 거부됐다.

### 2026-10-22 RT-11(b) 최종 독립 재리뷰 판정 및 기존 결함 후속 연결

**RT-11 IN_PROGRESS · Refs #298 (RT-11(b)) · PR pending · merge SHA pending**

- 사용자에게 전달받은 최종 독립 재리뷰 판정: 기존 P1 exact identity, P2 ASGI 전송 lifetime, P2 ownership/손상 정보 노출 및 metric P3가 해소되었으며, 현재 RT-11(b) diff에서 새로운 P1/P2는 없다. 커밋·중간 PR 준비가 가능한 상태이며, 실제 병합은 현재 변경의 원격 CI 성공 후 진행한다. 이 기록에서는 staging·commit·push·PR 생성을 수행하지 않았다.
- 최종 reviewer의 직접 검증과 구현 단계 보존 증거를 구분한다. 앞선 구현 단계의 계측 broad 790 PASS는 계측을 포함한 보존 증거이며, 무계측 broad PASS 또는 reviewer가 새로 직접 실행한 결과로 표현하지 않는다. 이번 기록은 전달받은 최종 판정의 후속 기록이며, reviewer 직접 검증의 실행 수치나 상세 결과를 새로 추정하지 않는다. 테스트는 재실행하지 않았다.
- cleanup timeout, disconnect idle, import watchdog의 과거 원인은 여전히 미확정 비차단 위험으로 유지한다. 과거 실패 원본과 이력을 보존하며, 이후 성공이나 최종 재리뷰 판정으로 당시 실패의 원인이 해결되었다고 소급하지 않는다.
- Related #387 — [Recording 소유권 판정에서 후행 공백 식별자를 구분하지 못하는 문제](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/387): 기준 develop에서도 재현되는 기존 결함이다. RT-11(b)의 신규 frame 경로에서는 exact identity로 차단되므로 RT-11(b)의 신규 회귀나 병합 차단으로 분류하지 않는다. RT-11(b)에 수정 범위를 혼입하지 않고 별도 Owner 판단·PR로 처리한다.
- 기존 이력은 수정·삭제하지 않고 이 후속 기록만 추가했다. 상태는 RT-11 IN_PROGRESS, 연결은 Refs #298 (RT-11(b))와 Related #387이며 PR·merge SHA는 pending이다.

### 2026-10-22 RT-11(b) PR #388 원격 CI 시간 초과 조사 및 gate 비용 축소

**RT-11 IN_PROGRESS · Refs #298 (RT-11(b)) · Related #387 · PR #388 · merge SHA pending**

- 작업 시작 시 현재 branch `codex/rt11b-frame-read`, HEAD `1eb319c129ae8682c452c73231e930b4d4bdbae6`, working tree/index clean을 직접 확인했다. 같은 PR을 유지했고 staging·commit·push·PR 수정·CI 재실행·reviewer/subagent 호출은 하지 않았다. 원격 원본 로그와 새 실험 자료는 PR 제외 `.codex-scratch/rt11b-ci388-20261022/`에 보존했다.
- GitHub에서 직접 읽은 PR 현재 상태: boundary-check run `39663616292` success, python-tests run `39663616303`/job `119442752152` cancelled, MySQL execution gate skipped다. Full pytest는 UTC 19:41:06.222부터 20:10:20.520까지 약 1,754.30초 실행되었다. 마지막 완성 progress 줄은 20:09:47.041의 97%이며 약 33.48초 뒤 job 취소 메시지가 나왔다. 명시적인 pytest failure summary는 없고 artifact도 없다. `-q` 로그만으로 취소 순간의 정확한 node/stack 또는 개별 fixture·DB·mutation 시간은 복원할 수 없다. 로컬 collection 순서에 대한 마지막 batch 매핑은 추정일 뿐 특정 테스트 hang의 증거로 쓰지 않는다.
- 기준 develop `c491a95b8726377c2eca2ac3dad6bcc6ce416670`의 원격 run `39555360021`/job `119073755130` 로그도 직접 읽었다. Full pytest는 1,195.88초에 9,755 PASS/27 SKIP, strict MySQL gate는 839 tests PASS였다. 두 원격 실행은 동일 runner image `20261018.339.1` 및 MySQL 8.4.11을 사용했다. PR의 미완료 full step만으로 이미 기준보다 약 558.42초 길지만, 이는 완료한 suite끼리의 비교가 아니다. setup은 약 1분 규모여서 전체 비용의 주원인은 pytest step이다. 기준의 성공을 현재 diff 검증 성공으로 재사용하지 않는다.
- 기존 archive의 관련 5개 source/config가 기준 develop과 일치함을 대조한 뒤 같은 Windows 환경에서 collection만 비교했다. 기준 9,778개와 수정 전 PR HEAD 10,677개로 RT-11(b)는 899개를 추가한다(gate unit 801개 + frame 관련 98개). 기준 원격 9,782개와 로컬 9,778개에는 환경 차이가 있어 서로 섞어 증가분을 계산하지 않는다. 조사 중 최초 895개라는 계산은 이 교차 환경 비교였으며 위 899개로 정정한다. 이번 회귀 테스트 3개는 그 이후 추가분이다.
- 확인된 구조적 비용: 전체 suite 안의 `test_actual_report_rejects_each_missing_migration_check`가 전체 MySQL inventory를 별도 child로 재실행하며 각 fixture의 schema/migration도 반복한다. 해당 node를 포함하는 progress batch 간격은 기준 512.323초, PR 814.096초로 약 301.773초 증가했다. 이 간격은 다른 batch 내 테스트도 포함하므로 child 단독 duration으로 부르지 않는다. 이 재실행의 acceptance 의미와 900초 child 제한은 유지했다. process/network 검증과 등록된 mutation을 제거하거나 broad 조합을 축소하지 않았다. 원격 phase별 세부 증가분과 runner 부하의 기여도는 미확정이다.
- 로컬 프로파일로 반복 계산 두 곳을 확인했다. (1) strict checker는 Case 필수 항목마다 모든 node ID를 다시 분해했다. 기존 판정의 `(path, function)` count를 Counter 한 번으로 집계하도록 바꾸었다. (2) 실제 report parameter mutation은 약 1.2MB report 전체를 6,933번 deepcopy했다. test utility `copy_parameter_evidence`로 해당 node의 metadata/phase와 변경할 목록만 소유하게 했다. 다른 evidence는 읽기 전용 공유한다. 같은 906-node report 100회 복사 실험은 전체 deepcopy 1.339초/parameter copy 0.0149초였고, 100회 validator 실험은 기존 0.444초/수정 0.274초였다. 이는 로컬 실험이며 원격 job 단축 시간이나 30분 내 완료를 보장하는 수치가 아니다. 전체 mutation cProfile 실험은 계측 deepcopy 비용 때문에 중단했고 부분 XML과 중단 기록을 남겼으며 PASS로 분류하지 않는다.
- RED→GREEN: node 재분해 회귀는 기존 14,264회가 881 nodes의 2회 예산을 넘는 assertion으로 RED(1 FAIL), 최소 Counter 변경 뒤 GREEN(1 PASS)이었다. parameter 복사 격리는 원본 evidence가 바뀌는 두 assertion으로 RED(2 FAIL), target만 소유하는 구현 뒤 GREEN(2 PASS)이었다. 전체 gate unit 직접 실행은 7,092 PASS/skip·xfail 0, stdout 506.16초다. 원본 보존·서로 다른 mutation 간 격리와 무관한 evidence 비복사도 검사했다. 제품 코드와 Recording SQL/transaction/ASGI 경계는 수정하지 않았다.
- 현재 integration mutation 코드를 보존된 실제 906-test JSON/JUnit에 적용한 재검사는 124.891초에 완료했다. 6,933 parameter mutation과 metadata/family omission 1,029건(그중 frame 297건)을 모두 거부했고 원본 파일 hash도 유지했다. 현재 checker CLI의 동일 전체 원본 strict JSON/JUnit 재검사도 906 tests PASS다. 이들은 현재 코드의 직접 재검사지만 DB 실행 자체는 구현 단계 보존 증거이며 새로운 전체 MySQL 실행이 아니다. 새 frame-only report는 전체 strict gate에서 의도대로 거부됐다.
- 새 전체 pytest/MySQL 시도는 pytest 진입 전 owned server bootstrap의 기존 60초 제한에서 WSL `sh` stdin 종료 대기로 막혔다. 최소 stdin probe도 10초에 timeout, 명시적 `exit`를 넣은 probe는 3.875초/exit 0이었다. timeout을 늘리지 않고 scratch bootstrap에만 명시적 exit를 사용했다. 이후 frame 실행의 첫 구성은 MySQL preflight에서 CA 검증 오류로 중단했다. 연결 인자와 SSLContext를 대조하니 `ssl_verify_cert` 인자 사용 시 복사한 CA가 context에 없었고, 기존 `ssl_ca`/`ssl_check_hostname` 구성은 해당 CA를 포함하며 CERT_REQUIRED를 유지했다. 이 구성으로 별도 새 evidence 경로에서 실행했다. 실패한 구성의 원본을 덮어쓰거나 PASS로 소급하지 않았다. 최초 bootstrap의 child stdout/stderr·init log 전체는 별도 파일로 수집되지 못한 제한이 있으며 tool traceback/실험 기록과 후속 실패 raw를 보존한다.
- 새 실제 MySQL 8.4.7 frame/API/Recording/process/TCP 회귀는 98 PASS/skip·xfail 0(83.89초), 그중 MySQL 72개/216 phases 전부 passed다. P1 exact identity, P2 ASGI send lifetime·checkout 0·cancel/disconnect/send exception 및 corrupt cross-case 격리를 포함한다. 테스트 소스에 계측 hook을 넣지 않았지만 소유 DB bootstrap의 명시적 exit와 CA 구성은 공개한다. pytest exit 0 뒤 controller의 기존 port-closed assertion이 실패해 controller 전체 성공으로는 부르지 않는다. 당시 port 관측 실패의 원인은 확정하지 않았고 테스트/제품 코드를 고치거나 재실행하지 않았다.
- 종료 전 감사는 system schema 4+소유 base 1, 원래 계정 4개, 감사 connection 외 client 없음, transaction/data lock 0이었다. 종료 후 별도 직접 감사는 소유 datadir 부재, Linux mysqld 없음, 소유 Windows listener/live TCP row 없음, 소유 port 연결 미성립을 확인했다. 한 중간 관측의 PID 0 TIME_WAIT는 최종 감사에서 0개였으며 listener로 분류하지 않았다. 감사 중 현재 Python 자체와 테스트 잔여를 구분했고 공유 WSL/relay를 종료·변경하지 않았다. controller assertion 실패는 이 후속 감사로 지우거나 원인 확정하지 않는다.
- Boundary 직접 PASS(위반 0), Contract fixture 직접 PASS(62/26/104), 두 workflow actionlint 1.7.12 직접 PASS다. 최초 boundary 실행의 Windows cp949 출력 인코딩 오류는 기록하고 UTF-8로 동일 검사 본체를 실행했으며 검사 규칙은 바꾸지 않았다. `.github/workflows/python-tests.yml`, required inventory/skip·xfail/strict JSON·JUnit 정책과 nested 900초, workflow 30분은 불변이다.
- 검증 한계/후속: 전체 bare pytest는 위 bootstrap 실패로 완주하지 못했고 새 전체 MySQL 906개도 반복하지 않았다. 변경은 gate 계산과 fixture 복사에 국한되어 새 전체 gate unit·기존 실제 전체 report의 모든 mutation·새 frame 실제 MySQL을 조합해 검증했다. Linux 원격 전체 실행시간과 이 수정의 원격 효과는 미확인이다. 따라서 원격 CI timeout이 해결되었다고 선언하지 않으며 현재 수정의 fresh reviewer 검토와 이후 승인된 원격 전체 CI/strict gate 성공은 병합 전 남은 조건이다. 과거 cleanup timeout·disconnect idle·import watchdog 원인은 계속 미확정 비차단 위험이며, 이번 WSL/CA/controller 관측과 동일 원인으로 단정하지 않는다. Related #387도 별도 Owner 범위 그대로다.
- 이번 후속 PR 후보 변경은 Log, checker, 기존 gate unit/integration 각 1개, 새 mutation utility/unit 각 1개로 총 6파일이다. scratch·원격 raw·RED/GREEN JSON/JUnit·runner·CA·임시 DB·프로파일·진단 자료는 PR 제외이며 기존 실패·리뷰 이력을 유지한다. 미커밋·미스테이징 상태에서 fresh review를 위해 멈춘다.

- 관측 표현 보정: 새 bootstrap timeout에서 직접 확인한 phase는 WSL child communicate 대기다. stdin EOF 종료 문제는 최소 probe와 명시적 exit 결과가 지지하는 해석이며 최초 실행의 stack·init log 전체가 없어 모든 지연 원인을 확정하지는 않는다. 새 CA/port 관측도 원격 CI 또는 과거 세 실패의 원인으로 확장하지 않는다.

### 2026-10-22 RT-11(b) PR #388 두 번째 원격 timeout · Linux tail 비교 · unit fixture 후속 최적화

**RT-11 IN_PROGRESS · Refs #298 (RT-11(b)) · Related #387 · PR #388 · merge SHA pending**

- 시작 시 현재 branch `codex/rt11b-frame-read`, HEAD `953c9234a13980476ac2420159974305d04b4961`, working tree/index clean을 확인했다. 원격 boundary run `39736631177` success, python-tests run `39736631209`/job `119683741878` cancelled와 MySQL gate skipped를 직접 읽었다. 원격 artifact는 없다. 원본 및 이번 자료는 PR 제외 `.codex-scratch/rt11b-ci388-second-20261022/`에 유지한다.
- 같은 lock/Ubuntu 24.04/Python 3.12 Linux collection은 develop 9,778개, 원격 PR HEAD 10,680개다. 앞선 기록의 원격 9,782 대 로컬 9,778 환경 차이라는 설명을 보정한다. 9,755 PASS+27 SKIP에는 collection skip 4개가 포함되며, 실제 원격 progress의 selected node도 9,778개다. 최신 PR의 추가 902개는 RT-11(b)의 899개와 직전 후속 unit 3개이며 이번 새 unit 2개는 별도다. 이전 이력은 수정하지 않는다.
- 로그의 마지막 완성 줄은 10,512번째 결과/98%(UTC 07:21:02.038541)이고 69.896초 뒤 취소됐다. Linux 순서 및 pytest 8.4.2 terminal 구현과 대조한 마지막 call 결과 node는 `tests/worker/test_redelivery_mysql.py::test_redelivery_metrics_preserve_after_case_stopped_meaning[CANCELLED]`다. 점은 call 이후·teardown 이전에 출력되므로 이 node의 teardown 완료는 미확정이다. 다음 72개(10,513~10,584)는 redelivery 6/reflection 40/sweep 26이며 단일 active node는 확정할 수 없다. 정상 순서·로그 전달을 전제하면 이후 96개는 미도달로 추론한다. 부분 batch에 숨은 실패 여부도 확정하지 않는다. 전체 node 목록과 phase별 monotonic 시간은 scratch `tail-timings.md`/CSV에 있다.
- 원격 API step 시간(develop/이전PR/최신PR): setup smoke 제외 49/60/56초, synthetic smoke 2/4/3초, full pytest 1,202/1,754/1,756초다. develop pytest 내부 summary 1,195.88초와 step 전체 시간을 구분한다. nested 포함 batch는 512.323/814.096/670.406초다. 이전 최적화 뒤 약 143.690초 줄었지만 동일 pure gate-unit batch 7,056개는 293.177→345.686초로 52.509초 길어졌다. 원격 개별 child/fixture/mutation duration은 현재 로그만으로 분리할 수 없으며 batch 시간을 단일 node 시간으로 쓰지 않는다.
- develop/PR의 rank ≥97% 동일 321개를 같은 Linux venv·lock·MySQL 8.4.7·filesystem/cache 조건에서 따로 실행해 각각 321 PASS/663.331초와 321 PASS/664.213초였다. 각각 실제 MySQL 220개/660 phases, skip·xfail 0이다. 첫 97% 표시 줄에 포함된 그 이전 63개도 별도 실행해 각각 63 PASS/13.724초와 63 PASS/13.383초를 보존했다. 이 네 targeted 실행을 전체 suite PASS로 합치지 않는다. 전체 384개 protocol 시간 합은 641.736→634.233초, setup 268.214→257.901, call 354.590→357.447, teardown 15.729→15.651초다. 해당 21개 테스트 파일 Git blob은 동일하다. 새 tail 회귀나 단일 고정 hang의 증거는 없었지만 broad 전체 순서의 영향은 배제하지 않는다. GitHub MySQL 8.4.11·filesystem·CPU/Python patch 차이 때문에 절대시간을 원격 예측으로 그대로 쓰지 않는다.
- 가장 긴 PR node는 기존 process-kill redelivery `[running]` 21.831초(develop 24.880초)였고, 여러 OS process 경계와 DB setup에 비용이 분산됐다. sleep·assertion·timeout·fixture isolation을 바꾸지 않았다. 최초 scratch runner의 multiprocessing main guard 누락은 재귀 계측 실행으로 확인해 소유 자식만 종료했고 원본을 무효 계측으로 보존했다. v2 결과와 합치거나 제품 결함으로 분류하지 않았다.
- 보존된 같은 실제 906-test report로 Linux에서 이전 `1eb319c`/최신 `953c9234` evidence 알고리즘을 직접 재검사했다. 217.026→85.995초, whole report deepcopy 8,213→1,280회와 parameter copy 6,933회다. parameter mutation 6,933건과 metadata/family omission 1,029건은 양쪽 모두 거부했다. validation 횟수도 8,214회로 같으며 원본과 각 실험 archive를 유지했다. 이는 과거 DB 실행 증거에 대한 현재 코드/알고리즘 비교이고 새로운 전체 MySQL 실행은 아니다. 원격 nested batch 감소와 방향은 같지만 그 감소 전부의 원인으로 확정하지 않는다.
- 새로 확인한 unit fixture 병목: 70개 표본 프로파일에서 `good_report` 2.298초와 checker 반복 import 1.682초(inclusive)가 컸다. 무계측 100회 fixture 생성 가설 실험은 1.299→0.199초, report 동일이었다. family마다 모든 parameter를 훑던 분류를 local family set membership으로 바꾸었고, test helper `checker()`만 `@cache`로 읽기 전용 재사용한다. mutable report는 매번 새로 만들고 production validation 결과를 cache하지 않는다. production checker와 제품 코드는 수정하지 않았다.
- 별도 RED→GREEN: family 재탐색 284회로 1 FAIL→2회 이내 1 PASS, checker load 3회로 1 FAIL→최대 1회 1 PASS였다. 후자는 valid→invalid→valid 검증도 수행한다. 동일 깊이의 일반 Git archive 참조 복사본에서 정상 pytest 전체 gate unit 2파일을 비교해 수정 전 7,094 PASS/411.780초, 수정 후 7,096 PASS/199.536초(약 51.5% 단축), 모두 skip·xfail 0이었다. 새 source hash와 모든 JSON/JUnit/RAW를 보존했다. 2개 증가는 새 회귀이며 기존 inventory는 제거하지 않았다. branch/worktree는 만들지 않았다.
- 다음 CI 시간은 보장이 아닌 모델이다. 같은 마지막 call의 develop ordinal 9,610이 progress 9,576~9,648 사이여서 그 뒤 완료까지 65.299~99.721초라는 범위를 얻었다. 같은 tail 속도를 가정한 미수정 job은 1,810~1,845초 추정이다. 실측 unit 비율 0.48457을 원격 unit window에 적용하면 약 178.178초 절감이며 gate/post 가정상 여유 10초 포함 1,642~1,677초(약 27분 22초~27분 57초)다. 원격 변동 52.509초, filesystem·CPU 차이 및 broad-only stall/실패 가능성을 고려하면 실측 완료나 PASS로 표현할 수 없다. 상세 가정은 scratch `budget-model.json`에 있다.
- 대안도 비교했다. DB bootstrap clone/공유는 fresh schema·migration·transaction·concurrency 격리 증명이 필요해 적용하지 않았다. evidence 계산 공유는 이번 unit helper 최소 수정으로 선택했다. outer full(단일 nested module 제외)와 그 nested parent test의 병렬 배정은 중복 검증을 유지하면서 critical path를 줄일 수 있지만 상위 collection manifest의 정확한 합집합/누락·중복, child 900초, artifact/required-check/전체 30분 예산을 설계해야 한다. artifact 뒤 gate는 head·merge SHA/run·attempt/policy·manifest 일치와 원본 JSON/JUnit 필수, upstream 실패/cancel/skip의 명시적 실패 전파가 필요하며 과거 성공 fallback이나 합성 PASS는 금지다. 각 job에 30분씩 줘 workflow 상한을 늘리는 안은 제안하지 않는다. 구체 비교는 scratch `investigation.md`에 남겼다.
- 현재 helper 수정은 Plan §12.3 test-harness implementation detail이며 Contract·Decision·Baseline 의미/다른 Owner surface 변경은 없다. job 분리 자체가 자동으로 Contract Owner 승인 대상이라는 근거는 없지만 required-check·30분 적용·artifact acceptance 의미를 바꾸면 CI policy 판단 항목이다. 사용자 지시대로 workflow 수정 전에 비교만 보고하고 멈춘다. 새 Decision Gate는 만들지 않는다.
- Boundary 직접 PASS(0), Contract fixture 직접 PASS(62/26/104), 두 workflow actionlint 직접 PASS, 현재 checker CLI의 보존된 전체 JSON/JUnit 906개 strict 직접 재검사 PASS다. full pytest/새 전체 MySQL은 실행하지 않았다(Linux Docker/media 도구 부재 및 이번 helper 변경 범위). 새 실제 DB는 위 tail 220개씩이며 보존 evidence와 합쳐 전체 MySQL PASS로 표현하지 않는다. P1/P2 제품 source·frame inventory는 그대로이고 이번 frame 98개 재실행은 하지 않았다. 과거 cleanup timeout/disconnect idle/import watchdog 원인은 여전히 미확정이며 이번 원인으로 소급하지 않는다.
- 소유 DB audit는 system 4+base 1 schema, 기존 account 4개, 감사 외 client 없음, transaction/data lock 0이었다. 무효/v2 두 server 모두 종료 후 datadir 부재·연결 거부, 소유 process/listener 0과 unit/replay 임시 폴더 제거를 최종 감사했다. 진단은 archive에 보존했고 공유 WSL/relay는 변경하지 않았다. 이번 tracked 변경은 Log와 `tests/common/db/test_mysql_gate.py` 2개뿐이다. scratch 전체(uv/venv/cache/reference snapshot/RAW/JSON·JUnit/runner/timer/DB log/진단)는 PR 제외다. staging·commit·push·PR 수정·CI 재실행·reviewer/subagent 호출 없이 미커밋·미스테이징 상태로 멈춘다. 현재 원격 cancelled/skipped는 유지되며 수정 검토와 실제 원격 CI/strict gate 성공 전 병합은 차단된다.

### 2026-10-24 — RT-11(c) DerivedAsset HTTP 구현·독립 재리뷰 인계

- **상태: RT-11 IN_PROGRESS · Refs #298 (RT-11(c)) · Related #387.** reviewer/subagent 호출, staging, commit, push, PR 생성 없이 인계한다. RT-11 전체 acceptance 완료를 주장하지 않는다.
- 시작/재개 기준은 `codex/rt11c-derived-asset-read`이며 HEAD·로컬/원격 develop `2ffd67ebcf62a974a165942c911c27468fb7f0ce` 일치를 직접 확인했다. PR #388 merge `1f830afeac93309e9ef9c8eb90fcfaced0f97ae0` 포함을 확인했고, 그 [boundary-check](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39753758821)·[python-tests](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39753758715) 및 MySQL execution gate 성공은 원격에서 확인한 선행 증거다. PR #394의 [boundary-check](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39993802597)·[python-tests](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39993802621)·MySQL gate 성공과 Issue #387 closed/completed도 직접 조회했다. 이 원격 성공을 현재 미커밋 diff의 CI 성공으로 쓰지 않는다.
- 사용자가 지정한 기존 untracked #387 계획 문서를 내용 열람·재사용·수정 없이 `.codex-scratch/issue387-20261023/2026-10-23-recording-exact-ownership.md`로 이동했다. 전후 SHA-256 `9A43517890F3DCA4306F75464525CF272EF5A0DB83A17993D733FEAE71E7EADD` 동일, 이동 직후 `git status --short` empty였다. 원격 develop은 후반 재확인에서도 같은 SHA였다. 기존 이력을 보존하고 이 항목을 후속 기록한다.
- Issue #298, HTTP Contract §3.5/§5.2/§5.5/§5.6/§7-6~§7-9, Tech Spec §13, Baseline B-U1/B-U3/B-U4/B-F1/B-F2/§2.8, Plan RT-11/REC-1, Recording 공개 capability와 REC-1(a)/(b)/(c), PR #388 경계를 조사했다. PR #394의 exact association residual·asset identity 확인을 코드에서 검토하고 실제 MySQL 8.4.7 prerequisite 33개 PASS(3 deselected)로 선행 차단 해소를 판정했다. 신규 Recording capability·Case·schema·migration·RT-10 변경은 없다.
- `GET /cases/{case_id}/assets/{asset_ref}`를 구현했다. 기존 Case ID validator·CaseStore 존재 조회와 Recording 공개 `owns_asset(derived_asset)`·`open_derived_asset`를 한 caller transaction에서 사용한다. 저장 stream은 transaction 안에서 read/close하고 길이를 검증한다. `run_api_transaction` 종료·connection checkin 뒤에만 header·detached bytes 응답을 구성한다. Recording/콜백은 자체 commit/rollback하지 않는다. API가 Recording 내부 table/schema를 직접 조회하지 않으며 provider·decoder·재생성·새 생성 surface를 추가하지 않는다.
- 실제 PNG/MP4 형식·정확한 Content-Length, 서버 상수 ASCII attachment filename(`daesingo_asset.png`/`.mp4`), `private, no-store`를 제공한다. 사용자 파일명·차량번호·opaque ref·내부 경로를 filename/log에 넣지 않는다. unknown/foreign/종류 불일치는 동일 `404 http.not_found`, owned-unavailable은 `404 http.ref_unavailable`이며 typed dependency/validation/unexpected 매핑과 안전한 envelope을 유지한다. Range는 전체 200 body, frame semaphore는 사용하지 않는다. retention/cleanup 정책은 변경하지 않았다.
- RED→GREEN 직접 실행: route 미구현 unit 9 FAIL/5 PASS, MySQL 11 FAIL/5 PASS/29 deselected를 기록했다. 초기 GREEN 57 PASS/2 FAIL은 Unicode case 입력이 CaseStore ASCII 비교까지 내려가는 문제였고, 신규 loader에 기존 `validate_case_id` 호출을 추가해 처리했다(Case 변경 없음). 확장 69 PASS, 최종 asset HTTP/ASGI/TCP/MySQL 집중 72 PASS이며 그중 MySQL 58개/174 phases, skip·xfail 0이다. 후행·선행·다중 공백, 대소문자, Unicode 표현/공백의 양방향 격리, foreign 손상 metadata 비복원, stream 오류/길이 불일치, caller rollback, header 전 commit/checkin, 실제 send의 start/body/final 모든 종료, read 취소, 실제 TCP disconnect, fresh process 및 두 process-kill 경계를 검증했다.
- gate RED: 이전 checker가 asset family 8개 누락을 허용하는 8 FAIL을 확인한 뒤 independent required inventory 58개·8 family를 checker/unit/실제-report 검증에 확장했다. 8 family+4 valid/최적화 테스트 12 PASS, 전체 pytest 내 gate unit 8,106 PASS다. 기존 fixture/checker cache·parameter evidence copy 최적화, workflow 30분, nested MySQL 900초, skip/xfail 정책과 strict JSON/JUnit 의미를 완화하지 않았다.
- **무선택 전체 pytest 직접 실행:** 11,969 PASS/2 FAIL/26 SKIP, pytest 2,703.03초(무계측 정상 실행). ① `test_default_one_gib_exact_and_next_byte_are_streamed_without_whole_body_buffer[False]` extra byte에서 413 대신 503 ② `test_actual_report_rejects_each_missing_migration_check`의 child 900초 timeout. 전체 report의 MySQL 1,005개/3,015 phases 중 parent call 한 phase가 실패해 strict CLI도 FAIL이다. 전체 PASS로 표현하지 않는다. SKIP 26개는 Typer-dependent collection 4개와 외부 영상/archive 입력 부재 22개다.
- 첫 upload 실패는 동일 단독 실행에서도 1 FAIL/1 PASS로 재현됐다. 약 1 GiB 여유 공간을 관측했고 이번 작업의 완료된 gate RED temp XML만 정리한 뒤 같은 두 parameter가 2 PASS했다. 최초 errno를 확보하지 못했으므로 disk 원인은 추정으로 남긴다. 이후 evidence 디렉터리에만 NTFS 압축을 적용했고 제품·assertion·한도는 바꾸지 않았다.
- **독립 전체 필수 MySQL 직접 실행:** 별도 disposable 서버에서 자기 재실행 module만 제외한 1,004개 PASS/3,012 phases, MySQL skip·xfail 0, strict JSON/JUnit CLI PASS였다(pytest 855.25초). 비-MySQL Typer module collection skip 4개는 분리한다. 이 결과를 실패한 outer/nested report와 합성하지 않는다.
- **nested 단독 재확인도 FAIL:** child는 618.60초에 999 PASS/1 FAIL로 종료했고, `test_owned_process_kill_keeps_file_before_row_order[before_publish]`가 기존 8초 API startup budget을 넘었다(process는 alive). parent는 624.25초 FAIL이며 이 child의 strict CLI도 거부했다. 이후 같은 source·8초 한도의 interruption 네 mode 직접 재확인은 4 PASS였다. 두 nested 실패의 정확한 원인은 미확정이고 nested acceptance는 여전히 병합 차단이다. budget 증가·skip·assertion 완화·upload/startup/CI source 변경은 하지 않았다.
- 실패한 nested가 mutation 전에 끝났으므로 **현재 직접 얻은 1,004-test 원본 JSON/JUnit에 현재 실제 gate test의 mutation/assertion body만 재실행**했다. parameter mutation 8,116건과 metadata/family omission 1,404건 모두 거부, asset subset 754건+240건 모두 거부, source·원본 JSON/JUnit SHA-256 불변이다. 이것은 현재 보고서 재검사이지 nested subprocess acceptance PASS가 아니다. 과거 보존 report를 새 DB 실행으로 표현하지 않는다.
- Boundary PASS(0), Contract fixture PASS(62/26/104), 기존 두 workflow actionlint PASS, `git diff --check` PASS를 직접 확인했다. 현재 diff의 원격 CI, fully passing whole pytest, nested end-to-end PASS와 CI 30분 headroom은 확보하지 못했다. 직전/이번 startup·timeout 원인, 기존 cleanup/disconnect/import-watchdog 불확실성도 해결됐다고 판정하지 않는다. 실제 외부 영상/아카이브 검증과 full codec decodability도 미검증이다. bytes 전체 memory buffering 및 현재 PNG/isom MP4 adapter 범위는 비차단 구현 한계로 기록한다.
- 두 owned MySQL process/helper 종료, 각 generated datadir 제거, Linux 연결 거부와 최종 Windows TCP 항목 0을 확인했다. 초기 Windows 연결 검사 assertion 실패 이력은 보존하며 재확인 원인을 확정하지 않는다. 양쪽 audit는 비-audit client·transaction·data lock 0, 기본 account 4개였다. 첫 서버는 강제 timeout으로 disposable test schema 1개가 남아 clean-schema assertion이 실패했으나 finally가 owned datadir 전체를 제거했다. 둘째 서버의 system 4+base 1 schema audit는 PASS였다. shared WSL/relay를 변경하지 않았고 workspace 테스트 Python process 잔존 조회도 empty였다. 테스트가 만든 root zero-byte lock 두 개는 hash 기록 뒤 제거했다.
- 상세 경계·15개 변경 목록은 [RT-11(c) note](rt11c-asset-read.md), 원본 RAW/JSON/JUnit·현재 report mutation·runner·CA/DB log·source snapshot/hash manifest는 `.codex-scratch/rt11c-20261024/` 및 `.codex-scratch/rt11c-mysql-direct-20261024/`에 보존한다. scratch와 archived #387 계획 문서는 PR 제외다. 미커밋·미스테이징 상태에서 독립 재리뷰를 기다리며, 실패/미실행 항목을 해소하기 전 병합 성공을 주장하지 않는다.


### 2026-10-24 — RT-11(c) P2 재검증·TCP 수정, 관측 의미 확인 대기

- 상태는 **RT-11 IN_PROGRESS · Refs #298 (RT-11(c))**다. 이전 전체/nested 실패·직접 MySQL PASS·mutation replay 이력은 보존하고 이번 실행과 합산하지 않는다.
- P2-1 최소 제품 RED를 직접 확인했다: outer body send를 대기시킨 동안 공통 `api.request.completed(status=200)`가 이미 존재하고, OSError 이후에도 asset 종료 지표 두 개가 없어 1 FAIL이다. 최초 두 제한 실행은 테스트 coroutine 전 Windows asyncio socketpair.accept에서 정지해 원본 stack을 보존하고 해당 프로세스만 종료했다. 이를 제품 RED로 집계하지 않는다.
- Plan/Baseline에는 asset event 이름 두 개만 있으며 bytes/종료 상태 의미는 미확정이다. 사용자의 “확정되지 않았다면 임의로 확대하지 말고 먼저 보고” 지시에 따라 count/duration_ms/status의 제안 의미와 네 종료 상태를 보고·질문했다. 답변 전 제품 관측 의미를 추가하지 않았으며 새 테스트는 의도적으로 RED다. 공통 완료 event의 의미도 변경하지 않았다.
- P2-2는 실제 Uvicorn drain task가 write-paused 상태에서 아직 pending인 조건, outer body-send pending·ASGI 미종료·checkout 0을 server loop snapshot으로 확인하도록 수정했다. disconnect 관측 이후 ASGI 종료 순서와 request task/connection/server thread 정리를 요구한다. scratch plugin으로 drain을 즉시 완료시키는 negative control 1 FAIL, 실제 TCP GREEN 1 PASS, 엄격한 종료 순서 추가 뒤 1 PASS를 각각 보존했다. sleep/용량/timeout 증가나 asset용 Frame permit 도입은 없다.
- Upload 원래 실패 parameter 계측 1회는 1 PASS(7.38초), OSError/errno는 재현되지 않았다. 저장 단계·disk/staging 크기 기록을 보존했다. 과거 errno/원본 traceback은 없으므로 disk 원인을 확정하지 않는다. Startup 원래 before_publish parameter 계측 1회는 1 PASS(5.14초), launcher/interpreter PID·import/bootstrap/composition·stdout/stderr를 보존했다. 과거 900초 child의 마지막/진행 node·PID 및 8초 초과 phase는 원본 자료가 없어 미확정이다. cleanup thread/relay를 모두 계측했다고 주장하지 않는다. 과거 nested JUnit의 asset 58개 합계는 45.957초(전체 testcase 합계 613.385초)이며 원인 입증이 아니다.
- 독립 회귀는 129 PASS(실제 MySQL 58개/174 phases, skip·xfail 0)다. asset HTTP/ASGI/TCP/MySQL, 기존 Frame lifetime·공통 request 관측·API 정리를 포함하되 P2-1의 known-RED 파일은 제외한 독립 실행이다. Boundary 0/Contract 62·26·104/actionlint/diff check PASS다. 두 P2 완료 전이므로 이번 후속 단계의 최종 전체/nested 실행은 각각 0회이며, 최종 strict unit/mutation/JSON/JUnit도 아직 실행하지 않았다.
- 상세 기록은 [RT-11(c) note](rt11c-asset-read.md)의 P2 follow-up. PR 제외 scratch는 `.codex-scratch/rt11c-p2-20261024/`다. owned MySQL/helper 종료·전용 datadir 제거·Linux 연결 거부, Windows owned Python/listener/활성 TCP 0을 확인했다(TIME_WAIT만 잔존). 전용 temp만 정리하고 raw/JSON/JUnit/trace/source snapshot을 보존했다. staging·commit·push·PR·reviewer/subagent 호출은 없다. P2-1과 최종 acceptance는 병합 차단 상태로 남는다.


### 2026-10-24 — RT-11(c) Owner 승인 반영·P2 구현·최종 단일 실행

- **RT-11 IN_PROGRESS · Refs #298 (RT-11(c))** 유지. [Runtime/Ops Owner의 최신 승인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/298#issuecomment-6380891047)을 직접 확인해 의미 차단을 해소했다. 재개 전 branch/HEAD 및 16개 source SHA-256/staging이 이전 manifest와 같았다. 이전 RAW 전체의 aggregate hash는 없으므로 과거 byte 동일성을 과장하지 않고 재개 시 원본 158개 hash를 고정했다. 최종 Python 583개 및 이 원본 158개는 실행 내내 불변이다.
- 순수 outer ASGI AssetLifetimeMiddleware를 추가했다. final downstream body send 반환 또는 예외/취소 종료까지 monotonic latency, 정상 반환 chunk만 bytes에 합산한다. **successfully returned downstream send bytes, not client-received bytes**이며 Content-Length/클라이언트 수신/TCP ACK를 뜻하지 않는다. 부분 전송·오류 body 포함, 실패 chunk 제외다. matched 요청마다 두 metric을 각각 한 번 emit한다. 정상은 실제 HTTP status 문자열, 예외 FAILED, 취소/final 없는 종료 CANCELLED, DISCONNECTED 추가 없음. raw case/ref/filename/locator/error 비노출, 원래 HTTP status 및 공통 api.request.completed 의미 유지다. Frame permit·DB 조회·Case/Recording/schema/migration/retention 변경은 없다.
- TDD 직접 증거: 초기 RED 24 FAIL 중 정상 네 건에는 helper 반환값 오기가 함께 있었고 초기 GREEN은 20 PASS/4 FAIL이었다. assertion 수정 뒤 제품 관측 우회 negative control은 정확히 absent metrics로 24 FAIL, 복원은 24 PASS다. 확장 집중 회귀 166 PASS(실제 MySQL 59개/177 phases, skip·xfail 0), 전체 내 asset 관련 109 PASS다. outer body/final 취소·OSError·ClientDisconnect·unexpected·fatal/incomplete, partial bytes=3, HTTP 오류 status, final-send latency, trace/privacy, caller ownership/commit/checkin/전송 중 checkout 0, exact identity·후행 공백·양방향 격리, 실제 TCP drain/disconnect/종료 정리를 검증했다.
- 신규 partial_failure inventory 누락 RED 3 FAIL/8 PASS → checker 독립 required parameter 확장 뒤 11 PASS. 전체의 strict gate unit 8,117 PASS, 새 실제 보고서 parameter mutation 8,129건과 metadata/family omission 1,408건 모두 거부(asset 767+244). 기존 cache/copy 최적화와 skip/xfail·strict 의미를 보존했다.
- **최종 전체 pytest 정확히 1회:** 12,016 PASS/3 FAIL/26 SKIP, pytest 2,099.93초, runner 2,125.828초. 실패는 test_process_safety의 keyboard_interrupt[server-0], cli_cleanup_failure[RuntimeError], actual_server_cleanup_failure_exit_and_listener_release이며 모두 기존 total child 5초 초과(stdout/stderr empty)다. 내부 import/startup/cleanup 단계와 새 변경의 인과는 미확정이다. 전체 FAIL은 병합 차단이며 단독 재시도·전체 재실행·budget/assertion 완화는 하지 않았다. SKIP은 Typer collection 4+외부 미디어/아카이브·opt-in 22이며 MySQL skip이 아니다.
- **같은 전체 실행의 MySQL:** 1,006개/3,018 phases 모두 PASS, strict JSON/JUnit CLI PASS. **전체 안 nested 정확히 1회:** child 1,001 PASS/3,003 phases, 597.26초(900초 미변경), strict JSON/JUnit CLI PASS. actual-report mutation까지 parent call 819.498782초 PASS다. 이를 과거 900초/8초 nested 실패나 전체 upload 503 실패의 재분류에 쓰지 않는다. 과거 errno/phase 누락과 원인 미확정 상태를 보존한다.
- 이번 full-temp에는 NTFS 압축이 상속돼 미디어 fixture도 영향을 받았다. 텍스트만 압축했다는 runner 주석/초기 설명을 정정한다. 논리 bytes/assertion은 동일하나 과거와 같은 물리 disk-pressure 재현이 아니다. 현재 whole Windows runtime은 30분을 넘었으며 Ubuntu CI headroom 측정은 아니다. Workflow 30분, nested 900초, upload startup 8초, process-safety 5초 및 required inventory를 완화하지 않았다. 현재 diff 원격 CI는 미실행이며 predecessor PR #388/#394 성공은 과거 prerequisite 증거다.
- owned MySQL/helper 종료·전용 datadir 제거·Linux 연결 거부, shutdown audit 정상(기본 schema 4+base 1/account 4/non-audit client·transaction·lock 0), native owned test Python/listener/활성 연결 0을 확인했다(TIME_WAIT 209는 별도). 임시 test tree는 원본 보고서·mutation inventory·JSON interruption 자료 보존 뒤 제거했고 새 root zero-byte lock 두 개를 hash 후 제거했다. source/과거 evidence·#387 archive hash 불변. 상세 결과와 전체 변경 목록은 [RT-11(c) note](rt11c-asset-read.md), PR 제외 증거는 `.codex-scratch/rt11c-owner-20261024/`다. reviewer/subagent·staging·commit·push·PR 없이 독립 재리뷰 상태로 멈춘다.

### 2026-10-24 — RT-11(c) process-safety 3건 systematic investigation, 원인 미확정

- **RT-11 IN_PROGRESS · Refs #298 (RT-11(c))** 유지. 재개 시 branch/HEAD `codex/rt11c-derived-asset-read` / `2ffd67ebcf62a974a165942c911c27468fb7f0ce`, staging 없음, 후보 17개 경로/hash 및 최근 evidence 115개·이전 evidence 158개 hash 일치를 확인했다. 원격 develop은 직접 조회한 `a89a57020f36d7bfef1d62e1af8ba9ef9a28627a`이며 HEAD 대비 Case 결정 문서 2개만 다르다. dirty checkout의 checkout/reset/stash 없이 각각 검증된 snapshot을 생성했다. 현재 snapshot은 frozen Python 583개와 byte hash가 일치하고 두 snapshot은 실행 뒤에도 hash 불변이다.
- 원본 whole RAW/JUnit·순서·기록 환경을 읽었다. 세 timeout은 모두 Windows subprocess.py:1630의 **stdout reader EOF join**에서 발생했고 후속 process.wait timeout이 아니다. kill/reap 뒤 출력은 비어 있다. 당시 `-c` child phase/PID/stack은 없어 내부 import/startup/cleanup/atexit 정지 위치를 복원할 수 없다. traceback의 Popen returncode=1은 사후 cleanup 뒤 표현이므로 kill 이전 실패 exit의 증거로 해석하지 않았다.
- scratch-only side-channel로 spawn→Python/import→composition→serving hook→signal handler/예외→shutdown/cleanup→listener assertion→atexit→stdout/stderr reader→wait를 관측했다. 원래 assertion과 child 5초 제한을 유지했고 stdout/stderr에 계측하지 않았다. 최초 phase 계측의 coroutine call/return은 suspension/resumption도 포함하므로 요청/완료 횟수로 해석하지 않는다. ready handshake나 외부 OS signal이 없는 기존 테스트에 그것을 추가하지 않았다.
- **직접 비교:** 현재/develop에서 각각 A/B/C 단독 각 1 PASS, 원래 순서 immediate predecessor 묶음 6 PASS, process-safety 모듈 45 PASS. 계측 없는 동일 predecessor 대조는 현재 **5 PASS/1 FAIL(C)**, develop 6 PASS다. 추가 C RED 원본 RAW/JUnit은 보존했다. 원래 직전 frame TCP·health·owned MySQL 모듈을 붙인 무계측 묶음은 양쪽 각각 53 PASS(실제 MySQL 6개/18 phases, skip·xfail 없음). 전체/nested strict inventory 실행을 뜻하지 않는다.
- 가설은 “5초 예산이 import/startup에서 소모되는지, shutdown에서 소모되는지” 하나로 제한했다. 제품 profiler 없는 가벼운 phase와 3.5초 파일 전용 stack 관측을 고정한 3쌍 비교에서 양쪽 매번 6 PASS, stack dump 미발생이다. 각 node의 이번 총 관측은 현재 A 0/8·B 0/8·C 1/8 timeout, develop 각각 0/8이다. 서로 다른 진단 mode를 포함하는 관측 수이며 실패 확률 추정/전체 pytest 합산이 아니다. 재현 C도 parent stdout EOF 대기에서만 확인되고 child 내부 정지 phase는 미확정이다.
- 관측된 성공 child는 모두 atexit tail과 pipe EOF/wait 반환까지 도달했다. A/B는 server 대체, C만 실제 bind/shutdown/listener close·연결 거부를 검증한다. C middleware scope는 lifespan이고 asset load/HTTP metric/frame permit/asset DB transaction은 호출되지 않는다. CLI/events/common logging/frame lifetime/storage cleanup은 기준 develop과 byte-identical이며 resource predecessor도 양쪽 PASS다. 그러나 RT-11(c)의 import/router 구성 비용·lifespan dispatch가 timing에 기여하는지 배제할 수 없다. develop에서 재현되지 않아 기존 develop 문제로 확정하거나 RT-11(c)와 무관하다고 단정하지 않는다. 과거 host load/cache/전체 OS 환경은 복원 불가다.
- **제품·fixture·테스트·5초 제한·sleep 수정 없음, RED→GREEN 해결 주장 없음.** 이번 versioned 수정은 이 log와 상세 note의 후속 기록뿐이며 전체 후보는 기존 17개다. 과거 whole **12,016 PASS/3 FAIL/26 SKIP**은 그대로 FAIL, 과거 전체 MySQL 1,006개 및 nested 1,001개 strict PASS는 보존 증거다. 이번 whole/nested/현재 diff 원격 CI는 미실행이며 whole 실패와 원격 CI 부재는 병합 차단으로 유지한다.
- owned 비교 MySQL/helper 종료·정확한 datadir 제거·port 폐쇄, 기본 schema/account만 유지, non-audit client·transaction·lock 0 및 native owned process 잔여 0을 확인했다. snapshot에서 생성된 zero-byte cleanup lock은 hash 보존 뒤 제거한다. 진단 runner/plugin/snapshot/RAW/JUnit/phase/stack/environment/hash/audit는 `.codex-scratch/rt11c-process-safety-20261024/`에 PR 제외로 보존한다. 이전 원본/#387 archive는 불변이다. [상세 조사와 전체 후보 목록](rt11c-asset-read.md)을 독립 재리뷰 자료로 남기며 reviewer/subagent·staging·commit·push·PR 없이 멈춘다.

### 2026-10-24 — RT-11(c) 최종 독립 재리뷰 결과 후속 기록

- **RT-11 IN_PROGRESS · Refs #298 (RT-11(c))** 유지. 사용자가 전달한 최종 독립 재리뷰 결과를 기존 이력 뒤에 기록한다. P2-1(실제 ASGI 전송 종료 관측)과 P2-2(실제 TCP backpressure/disconnect 검증)는 해소됐으며, 새 코드에서 P1/P2 지적은 없다.
- **커밋·중간/draft PR 생성 가능 범위:** 아래의 정확한 17개 파일이다. 이는 해당 후보의 커밋·중간/draft PR 준비가 가능하다는 재리뷰 판정이며 병합 가능 판정이나 이번 기록 작업에서의 실행 지시는 아니다. scratch 진단·계획·원본 증거는 PR 제외로 유지한다.

  1. `docs/runtime/runtime-implementation-log.md`
  2. `scripts/check_mysql_test_report.py`
  3. `src/daesingo/api/README.md`
  4. `src/daesingo/api/app.py`
  5. `src/daesingo/api/composition.py`
  6. `src/daesingo/api/errors.py`
  7. `tests/common/db/integration/test_migration_gate.py`
  8. `tests/common/db/test_mysql_gate.py`
  9. `docs/runtime/rt11c-asset-read.md`
  10. `src/daesingo/api/asset_lifetime.py`
  11. `src/daesingo/api/routes_assets.py`
  12. `tests/api/asset_process.py`
  13. `tests/api/test_asset_lifetime.py`
  14. `tests/api/test_assets.py`
  15. `tests/api/test_assets_mysql.py`
  16. `tests/api/test_assets_network_mysql.py`
  17. `tests/asset_acceptance.py`

- **현재 병합 차단 유지:** process timeout 3건의 원인과 RT-11(c) 인과관계는 미확정이다. 전체 pytest 보존 결과는 **12,016 PASS / 3 FAIL / 26 SKIP**이며, 단독·묶음 PASS나 재리뷰 판정으로 이 전체 FAIL을 성공으로 재분류하지 않는다.
- **병합 조건:** 현재 변경에 대한 원격 CI 전체 성공이 필요하다. 이전 prerequisite PR의 CI 성공이나 보존된 MySQL/nested strict PASS로 현재 변경의 원격 CI 전체 성공을 대체하지 않는다. 현재 변경의 원격 CI 전체 성공은 아직 확보되지 않았다.
- **PR: pending · merge SHA: pending.** 구현 상태와 Issue 참조는 위 IN_PROGRESS/Refs로 유지하며 완료·Issue 종료를 선언하지 않는다. 이번 작업은 Implementation Log append만 수행하고 다른 파일 수정·테스트 재실행·staging·commit·push·PR 생성은 수행하지 않는다.

### 2026-10-24 — RT-11(c) PR #400 원격 30분 timeout 조사 · mutation XML 중복 계산 축소

**RT-11 IN_PROGRESS · Refs #298 (RT-11(c)) · PR #400 · merge SHA pending**

- 시작 조건을 직접 확인했다. branch `codex/rt11c-derived-asset-read`, 로컬 HEAD와 [PR #400](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/400) head는 모두 `3c37564340dd1d7da99c2ccc71f0c6b0ef42a686`, working tree/index는 clean이었다. 최신 develop은 `a89a57020f36d7bfef1d62e1af8ba9ef9a28627a`였다. 읽기 전용 원격 조회와 별도 검증 snapshot으로 조사했고 reviewer/subagent·staging·commit·push·PR 수정·CI 재실행은 하지 않았다.
- 원격 원본: [PR 실패 run 40083152147](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/40083152147), test job `120840652445`; [최신 develop 성공 run 40073525294](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/40073525294), job `120811890904`. 현재 head의 [boundary-check 40083152076](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/40083152076)는 success다. 두 python-tests run 모두 Python 3.12.15/MySQL 8.4.13이며 업로드된 JUnit/durations artifact는 없다. decoded 원본 log·job/step API·PR metadata를 새 scratch에 보존했다.
- **원격 단계 시간(develop / PR):** job 시작부터 setup(서비스·checkout·Python·uv) 35/34초, dependency 설치 2/2초, media tools 22/19초, media smoke 4/3초, full pytest step 1,607/1,756초다. pytest 내부 summary는 **11,230 PASS/33 SKIP/1 warning, 1,600.39초 → 11,996 PASS/33 SKIP/1 warning, 1,748.94초**다. setup 총합은 63→58초로 줄고 pytest 자체가 **148.55초 증가**했다. PR summary UTC 10:14:49.2998758 뒤 2.192초에 cancellation이 기록됐고 해당 step의 정상 종료와 후속 gate 성공은 확인되지 않았다. 후속 MySQL gate는 develop <1초 PASS, PR SKIPPED다. API상 job 경과는 27분54초/30분17초(후처리 포함)이며 설정 상한은 30분 그대로다. 원격 full에서는 기존 process timeout 3건이 재현되지 않았지만 과거 Windows 전체 FAIL을 재분류하지 않는다.
- 같은 Linux collection 순서/수를 원격 progress와 대조했다. selected node는 11,259→12,025이며 각 summary의 skip에는 별도 collection skip 4개가 포함된다. **추가 766개는 asset 109개(ASGI 36·unit 14·MySQL 58·TCP/MySQL 1)와 gate unit 657개**다. gate unit 파일은 7,460→8,117개다. 원격 nested parent를 포함한 72-result 구간은 693.115→788.223초, gate unit 중첩 구간은 157.115→163.192초다. 이는 개별 node/child/mutation 시간이 아니며, metadata가 없는 원격 nested 실행과 mutation 연산 시간을 정확히 분리할 수 없다.
- **중복 실행 의미 확인:** workflow의 후속 MySQL execution gate는 full이 방금 만든 JSON/JUnit을 읽는 validator이며 DB 테스트를 다시 실행하지 않는다. full 내부 actual-report test의 nested fresh MySQL 실행은 요구된 독립 실행/누락 검증이므로 보존했다. 그 subprocess 인자·실제 DB 요구·900초 제한은 AST 대조로 동일하다. 후속 gate 제거, 과거 성공 fallback, 합성 evidence, job 분리·required check·artifact 전달·workflow 의미 변경은 적용하지 않았다.
- **확인한 비용과 한 가설:** 작은 Linux mutation 70개에서 XML write 70회/실제 JUnit 검증 10회였고, XML write가 profiler 0.876초 중 0.444초를 차지했다. JSON에서 먼저 거부될 valid XML의 parse/build/serialize가 불필요하게 반복됐다. #388의 checker Counter·읽기 전용 module cache·family 분류·selective parameter copy를 읽고 비교했으며 해당 최적화는 유지했다. checker 100회 호출은 약 0.000008초, good_report 생성 100회는 약 0.187초였으므로 같은 패턴을 다시 복제하지 않았다.
- **호출 횟수 TDD:** 기존 구현에서 JSON 7회/JUnit 1회에 XML 7회가 발생하는 성능 RED 1 FAIL을 보존했다. 결합된 `all`의 XML 삭제 evidence도 계속 실제 구성하도록 최종 조건을 XML 2회로 정하고 RED(7≠2)→GREEN 1 PASS를 확인했다. JSON이 통과해야 필요한 valid XML만 그 뒤에 구성한다. `all`·JUnit 변형은 이전처럼 eager 구성하여 기존 matching/deletion assertion을 계속 실행한다. JSON 검증이 잘못 통과하면 valid XML 구성과 JUnit 검증을 수행하는 fallback도 유지했다. 초기 더 엄격한 XML 1회 목표 및 /tmp snapshot 부재·명령 인용 오류로 테스트 진입 전 중단된 진단은 별도 원본으로 보존하고 최종 결과와 합산하지 않는다.
- **직접 성능/회귀 비교:** 같은 Linux venv·native filesystem·일반 source snapshot에서 gate unit 두 파일 전체를 develop **7,462 PASS/104.69초**, PR 수정 전 **8,119 PASS/134.96초**, 수정 후 **8,120 PASS/118.98초**로 실행했다. 증가한 1개는 새 비용 회귀다. 모두 skip/xfail 0이다. 이 결과는 whole pytest가 아니다. 이번 최소 코드 변경은 `tests/common/db/test_mysql_gate.py`와 `tests/common/db/integration/test_migration_gate.py`의 mutation fixture XML 생성 시점이며 제품/production checker는 바꾸지 않았다.
- **보존된 실제 evidence의 직접 연산 비교:** 과거 실제 nested 1,001-node 원본 JSON/JUnit(hash 고정)을 대상으로 동일 actual-report mutation suffix 전체를 수정 전/후 실행했다. 이는 새 DB 실행이 아니다. **104.365→66.155초**, XML parse **10,154→4,822회**, write **8,201→2,869회**다. JSON 검증 **9,800회**(정상 1,953/거부 7,847), JUnit 검증 **1,953회**(정상 1/거부 1,952), whole deepcopy **1,670회**, selective parameter copy **8,129회**는 전후 동일하다. parameter mutation **8,129건**과 metadata/family omission **1,408건**의 identity·layer·거부 결과 JSON이 전후 정확히 같다(asset parameter 767건·metadata/family 244건 포함). 남은 mutation XML 2,722개는 수정 전 archive의 같은 파일과 byte hash가 모두 같다. 생략한 것은 JSON에서 이미 거부되어 읽히지 않는 valid XML 계산/파일뿐이다.
- **실패 탐지/strict 직접 검증:** 보존된 whole **1,006개** 및 nested **1,001개** JSON/JUnit에 현재 checker CLI strict PASS다. 원래 whole pytest **12,016 PASS/3 FAIL/26 SKIP**은 보존 FAIL이다. 누락 selection/phase·실패·skip·xfail·duplicate collection/phase·uncollected execution은 각각 거부했다. JSON checker를 의도적으로 약화한 selection negative control은 전후 모두 DID NOT RAISE로 테스트 실패를 탐지했고 fallback XML hash도 같았다. 기존 integration assertion AST와 nested subprocess call AST는 동일하다. production checker·required inventory·skip/xfail 규칙·workflow·deadline·제품 코드 hash는 그대로다.
- **새 실제 MySQL 부분집합:** Linux asset HTTP/ASGI/TCP **109 PASS/56.00초**, 실제 MySQL **59개/177 phases**, skip/xfail/collection error 0이다. fresh report의 asset required parameter 59개가 정확히 일치하고 JUnit 교차 검증 PASS다. 이 부분집합만으로 full required inventory를 충족하지 못하는 것도 기존 checker의 거부로 확인했다. JUnit 시간 합은 ASGI36개 3.153초, unit14개 1.129초, MySQL58개 47.850초, TCP1개 1.146초이며 pytest total과 다르다. 가장 긴 call은 기존 fresh-process read 12.80초와 interruption detached/read 4.82/4.55초였다. 의도된 fresh process·DB/schema bootstrap·assertion·timeout을 비용 때문에 공유/완화하지 않았다.
- **미확정 범위와 예상:** PR 원격 MySQL log에만 redo-capacity wait 경고(UTC 09:52:29, capacity 100MiB)가 있으나 지연 기여/단독 근본 원인은 미확정이다. 로컬 asset에서는 Innodb_log_waits 0→0, redo bytes 434,688→82,881,024였으며 DB 설정은 변경하지 않았다. 로컬 unit 약15.98초+보존 mutation 약38.21초, 합계 **약54.19초**의 중복 계산 절감이 근거다. 같은 절대 절감이 원격에도 적용된다고 가정하면 setup58+full(1756−54.19)+gate/post3 ≈ **1,762.81초(29분22.81초)** 모델이다. 이는 신뢰 구간/원격 실측/30분 성공 보장이 아니다. Linux 로컬 Python3.12.3/MySQL8.4.7과 hosted3.12.15/8.4.13의 CPU/load/filesystem/cache 차이, 원격 nested 개별 시간 부재, redo 영향과 남은 약37초 모델 여유 때문에 새 원격 CI가 필요하다.
- **검증 범위/대안:** 전체 pytest·새 전체 MySQL·nested는 로컬 재실행하지 않았다. 수정은 fixture의 중복 XML 계산뿐이고 관련 unit 전체, 같은 실제 보고서의 모든 mutation/strict, 새 실제 asset 부분집합으로 비용과 실패 탐지력을 분리 검증했기 때문이다. fresh nested 요구는 source/AST 그대로 남으며 보존 replay가 이를 대체하지 않는다. module/fixture import 재사용과 evidence copy는 기존 최적화를 유지했고, DB bootstrap 공유는 격리 의미 때문에 적용하지 않았다. job/step 분리·required-check·artifact/실행 의미 변경은 필요 시 CI policy 판단 항목이며 적용 전에 멈춰야 한다. Boundary 직접 PASS(위반0), Contract fixture 직접 PASS(62/26/104), 팀 소유 두 workflow actionlint PASS, diff check PASS다.
- **자원/인계:** 모든 진단·단위/replay/asset 임시 tree와 native source snapshot은 archive/hash 보존 뒤 정확한 owned 경로만 제거했다. owned MySQL/helper 종료·전용 datadir 제거·port 폐쇄와 기본 schema/account 유지, transaction/data lock 0을 감사한다. 이전 원본/#387 자료와 공유 Linux venv/relay는 수정하지 않았다. 원본 remote log/API·RED/GREEN·profile·collection/order·전후 JSON/JUnit·mutation inventory/archive·budget·audit·source hash는 PR 제외 `.codex-scratch/rt11c-ci400-20261024/`다. 이번 tracked 변경은 **Log와 gate unit/integration 두 파일, 총 3개**이며 기존 PR 전체 후보는 17개다. 기존 원격 cancelled/SKIPPED는 유지되고 **최종 변경에 대한 full pytest와 필수 MySQL strict gate를 모두 마치는 새 원격 CI 전체 성공 전 병합 차단**이다. 미커밋·미스테이징 상태로 멈춘다.

### 2026-10-25 — RT-10(b) Search handler 구현 재개 · failure taxonomy 경계에서 중단

**IN_PROGRESS · Refs #297 (RT-10(b)) · PR pending · merge SHA pending**

- 현재 `codex/rt10b-handler-registry`를 유지했다. HEAD와 직접 읽은 원격 develop은 모두 PR #329 merge `ea580ac6e1f0a035bf0938fcb8a097394f4b20d1`이다. #297 Case/Runtime 입력·produced 합의 및 #303 UsageSink 합의를 다시 읽었다. #303은 open이며 diagnostic 후속은 이번 세 호출의 차단이 아니다. PR #329 head CI boundary `40109830290`/python-tests `40109830291` success, PR #385 merge `c491a95b8726377c2eca2ac3dad6bcc6ce416670` 및 head CI `39552040227`/`39552040245` success를 원격 API로 확인했다. 이는 선행 PR 증거이며 현재 미커밋 diff의 CI가 아니다.
- Search kind 묶음의 HINT_EXTRACT·COARSE_SEARCH·FINE_VERIFY adapter, 공개 CaseStore/ProducedReader 입력 조회, execution UsageSink 전달과 capability 사이 checkpoint를 구현했다. Coarse/Fine은 실제 Run과 opaque object의 ref를 일치시켜 기존 T1/ProducedReader/usage 관계를 보존한다. 고정 Case span의 네 좌표와 CandidateEvent 대표 시각을 구분한다. 기본 Worker는 HINT만 등록하고 미디어 factory가 없으면 Coarse/Fine을 미등록 실패로 유지한다. clip·두 Readout·두 export, Recording 내부와 Case orchestration은 변경하지 않았다. 기본 T2/StoredObservationAdapter/RecordingFacts 조립은 미완료다.
- 직접 TDD: handler 12 FAIL→23 PASS, composition 2 FAIL→50 PASS, 별도 실제 public capability+offline SDK transport 9 PASS. 실제 MySQL 조사에서 Run/object 참조 분리 결함을 발견하여 단위 2 FAIL→33 PASS, Case 고정 interval 비교 1 FAIL→33 PASS를 확인했다. 최종 관련 offline **1,235 PASS/6 SKIP/612 deselected**(59.27초), 새 실제 MySQL 8.4.7 체인 **3 PASS/9 phases**, 기존 produced·usage/reconciliation·cancel·Case reflection **71 PASS/213 phases**, gate 누락/bypass negative control **15 PASS**다. 새 체인은 정상·1213 rollback·실제 COMMIT 응답 유실에서 세 capability를 다시 호출하지 않고 execution별 usage/T1 payload/T2를 검증한다.
- 직접 boundary 위반0·Contract fixture62/26/104·diff check PASS. JSON/JUnit은 각 실제 MySQL 부분집합의 unique selection·setup/call/teardown·skip/xfail0·누락 JUnit 거부를 확인했다. **전체 strict inventory는 두 부분집합을 required role/scenario 부족으로 거부**하며 이를 전체 gate PASS로 표기하지 않는다. checker/inventory·Contract fixture·다른 Owner 코드·workflow30분·nested900초는 동일하다.
- **남은 병합 차단:** Contract §6은 모듈 접두어 failure_kind를 요구하지만 현재 draft는 Search의 PROVIDER_ERROR/CONFIG_ERROR/INFRA를 그대로 전달한다. Search taxonomy는 draft이고 Coarse 인증 오류 구분, 여러/없는 issue 선택, Fine 예외와 실패 Run 경계의 JobExecution 매핑을 확인한 합의에서 찾지 못했다. 임의 prefix/새 taxonomy/exception text 해석이나 다른 Owner public surface 변경을 하지 않고 여기서 제품 구현을 중단한다. Search Owner의 공개 실패 매핑과 Runtime/Contract Owner의 terminal/produced 판단이 필요하다. 정상 경로 PASS로 이 미완료 실패 경계를 해소됐다고 주장하지 않는다.
- Windows sandbox media 실패 **32 FAIL/1,203 PASS/6 SKIP**, Linux 의존성 실패 **12 FAIL/1,199 PASS/30 SKIP**, MySQL preflight 오류·중간 실제 MySQL 실패 및 no-test 실행은 별도 보존한다. 후속 PASS와 합성/재분류하지 않았다. 전체 pytest·전체 MySQL/nested·전체 gate mutation·Recording/Readout standalone·live provider·API/Worker 별도 process E2E·현재 diff 원격 CI는 미실행이다. 관련 범위와 T1 경계만 직접 검증했고, Owner 실패 의미와 production composition 미완료 상태에서 비싼 전체 검증을 중복하지 않았다.
- owned MySQL/helper 종료, 전용 datadir 제거·port 접속 거부를 확인했다. 기본 account/schema 외 잔여 없음·non-audit client0·transaction0·data lock0이다. RAW/JSON/JUnit/runner/cache/temp/DB 증거는 `.codex-scratch/rt10b-20261025/`와 초기 `.codex-scratch/rt10b-red.txt`에 PR 제외로 보존한다. local plan도 PR 제외다. staging·commit·push·PR·새 branch/worktree·독립 reviewer/subagent 없이 미커밋 checkpoint에서 멈춘다. [상세 범위·증거·차단](rt10b-search-handlers.md).
### 2026-10-26 — RT-10(b) 확정 Search helper 경계 재개 · HINT 인증/예산은 pending acceptance

**IN_PROGRESS · Refs #297 (RT-10(b)) · PR pending · merge SHA pending**

- 사용자 지시로 Search Owner 후속 답변을 기다리지 않고 확정 범위를 재개했다. 기존 미커밋 15개 파일의 bytes/hash/patch를 새 scratch에 보존했고 incoming develop과 경로 겹침이 없음을 확인했다. 같은 `codex/rt10b-handler-registry`를 `ea580ac6...`에서 최신 `4a69a292f55ed48b9f679c1016087d3acd11a994`로 fast-forward했다. 직후 기존 15개 hash 동일·index 비어 있음을 검증했다. 최초 sandbox ref write 실패 후 승인된 동일 fast-forward가 성공했다. 새 commit/stash/branch/worktree는 만들지 않았다.
- #297 Runtime 승인 `6387601291`·Search 확정 답변 `6392679689`의 public helper 세 개를 소비하도록 raw 실패 전달을 제거했다. FAILED Run payload/ref를 유지하고 PARTIAL은 성공이다. try block은 Search public capability 호출에만 두며 load/transaction/factory enter·exit/checkpoint/serialization/T1 오류에는 적용하지 않는다. UsageError와 cancellation은 그대로 전파한다. 실패 예외에서 임의 Run/produced를 만들거나 downstream job을 발주하지 않는다.
- PR #403은 마지막 직접 조회에서도 open/unmerged, head `00549ff23d27ac327a9305cb22b4661b68be403f`다. 따라서 최신 develop에는 실제 helper가 없다. 확정된 public 이름 그대로의 structural port를 주입 가능하게 두고, 기본 discovery에서 helper가 없으면 Search kind를 미등록 실패로 유지한다. 성공 fixture의 policy double과 실제 Search/Gemini offline transport를 사용한 현재 workspace 검증, 별도 #403 source snapshot 검증을 구분한다. 다른 Owner 파일·taxonomy 복제·private import·미병합 코드 합류는 없다. helper 설치 뒤 HINT 기본 등록/Coarse·Fine media factory 조건이 적용되며 production media/T2/RecordingFacts composition은 계속 후속이다.
- **직접 RED→GREEN:** 확정 경계23 FAIL→23 PASS, focused64 PASS. 별도 실제 helper/default registry+SDK 실패 검증은 이전 handler로16 FAIL/4 PASS, 복원 뒤 Owner Search test를 포함해95 PASS다. 초기 test-import 실수 RED와 snapshot 명령 경로 오류는 별도 보존하며 기능 RED와 구분한다. 현재 workspace 관련 Search/Worker/Case/jobs/usage/Recording/Readout **2,000 PASS/21 기존 SKIP/713 deselected**, 3 SDK 경고,202.43초. 새 실제 MySQL **74 PASS/222 phases/skip·xfail0**,98.17초. gate negative controls15 PASS, boundary0·Contract62/26/104·diff check PASS다. 이 실행들을 합산해 전체 pytest 성공으로 쓰지 않는다.
- 실제 MySQL JSON/JUnit의 unique selection·완전한 setup/call/teardown·skip/xfail0를 검사하고 실제 JUnit entry 누락을 거부했다. 기존 full strict checker는74개 부분집합을 필수 role/scenario 부족으로 거부한다. 전체 strict PASS가 아니다. Runtime jobs/produced persistence·Contract fixtures·Search/Case/Recording/Readout 코드·checker/inventory/workflow는 HEAD 대비 동일하다. workflow30분/nested900초는 유지한다.
- **HINT pending acceptance 유지:** #403 최신 댓글은 `6398537018`이고 후속 Owner 답변은 아직 없다. 실제 SDK·MockTransport·주입 시계로 401/403/404와500 각각 budget left/spent 8개를 관측했다. 인증+spent는 여전히 SEARCH_DEADLINE_EXCEEDED, 인증+left는 SEARCH_PROVIDER_CONFIG다. 올바르다고 assert하거나 Runtime에서 cause/status/budget을 해석해 보정하지 않았다. observations-only JSON에 pending으로 보존했고 후속 Owner 수정/수락 검증이 필요하다.
- Whole pytest·전체 MySQL/nested mandatory wrapper·전체 gate mutation·paid provider·API/Worker 별도 process 전체E2E·현재 diff remote CI는 미실행이다. 변경 범위 관련 회귀 약202초와 실제 DB약98초를 수행했고, 미병합 helper·pending HINT·미완성 production composition을 전체 실행으로 해결할 수 없어 중복 확대를 하지 않았다. 이전 날짜의 실패/성공·선행 PR CI와 이번 직접 실행은 구분한다.
- owned MySQL/helper 종료, 정확한 전용 datadir 제거·port 폐쇄, 기본 schema/account와 전용 base만 유지·non-audit client0·transaction0·lock0을 확인했다. `.codex-scratch/rt10b-20261026/`의 backup/snapshot/RAW/JSON/JUnit/runner/cache/temp/DB와 local plan은 PR 제외다. 사용자 요청에 따라 다음 단계에서 구현 대화 이력을 상속하지 않는 fresh reviewer를 같은 대화에서 읽기 전용 호출하며, 결과는 시간순으로 추가한다. staging·commit·push·PR는 수행하지 않는다. [상세 기록](rt10b-search-handlers.md).
### 2026-10-26 — RT-10(b) fresh 읽기 전용 독립 재리뷰 결과

**IN_PROGRESS · Refs #297 (RT-10(b)) 유지.** 사용자 요청대로 같은 대화에서 `fork_turns=none`으로 구현 대화 이력을 상속하지 않는 reviewer 1명을 호출했다. 요구사항·base SHA·17개 파일 manifest와 SoT를 전달했고 reviewer는 읽기 전용으로 검토했다. 저자가 결과 기록 전에 17개 hash·HEAD·branch 동일/index empty를 다시 검증했다. reviewer의 직접 실행은 diff check이며 테스트·DB 검증은 하지 않았다.

- 전달된 Search adapter 범위에서 **새 P1/P2 없음**. Runtime 입력/transaction/checkpoint/factory/serialization/T1을 Search error mapping으로 흡수하지 않는 경계, UsageError/cancel 전파, 고정 Fine 입력·명시적 budget, 실패 Run receipt 유지·예외 시 Run 생성 없음, PARTIAL 성공, execution sink와 기존 T1/usage 복구 보존을 확인했다. 이는 독립 정적 리뷰이며 병합 승인·전체 RT-10 acceptance가 아니다.
- **P3 1건 deferred:** helper가 존재할 때 public 속성을 제공하고 `failures=`를 생략해 기본 탐색·등록을 검증하는 저장소 회귀가 부족하다. 현재 성공 tests는 policy port를 주입하고 absence만 기본 discovery로 검사한다. 별도 #403 snapshot은 이번 실제 기본 연결을 검증했지만 유지되는 테스트를 대체하지 않는다. 입증된 현재 기능 결함은 아니므로 minor 추가 구현/재리뷰는 하지 않고 후속 항목으로 기록했다.
- **판단 보류 범위:** 미구현 production Recording/media/T2 수명·별도 process 배선, 명시적 제외 clip/readout/export, reviewer가 직접 실행하지 않은 whole pytest/필수 MySQL/current diff CI. 이들은 완료로 간주하지 않고 후속 dependency/acceptance 제한으로 유지한다.
- **pending 유지:** #403 공개 helper 미병합과 HINT401/403/404+예산 소진 Owner 답변·후속 수락 검증은 남아 있다. Runtime 재매핑·완료 선언은 없다. staging·commit·push·PR 생성 없이 미커밋/미스테이징 상태에서 멈춘다. 원본 증거·snapshot·review 결과·무변경 hash 검증은 PR 제외 scratch에 보존한다. [상세 checkpoint](rt10b-search-handlers.md).

### 2026-10-26 — RT-10(b) durable facts / production media / stored T2 후속

**IN_PROGRESS · Refs #297 (RT-10(b))**. 사용자가 #403·#405 대기와 독립된 composition 구현을 명시적으로 요청했다. 기존 17개 미커밋 파일을 별도 backup/hash/patch로 보존하고 같은 브랜치에서 진행했다. 사용한도 중단 후 원격 develop의 추가 변경은 Case 문서 4개뿐이며 현재 변경과 비중첩이었다. 전체 37개 변경 파일을 추가 backup 후 `4a69a292f55ed48b9f679c1016087d3acd11a994`에서 `42ddea72bb927e7adedf352ba53d160bda1aa049`로 fast-forward했고 hash 동일·index empty를 확인했다. 아래 테스트는 소스 동일한 앞 SHA에서 직접 실행한 결과다.

- Recording에 opt-in prepared media/model/body·시각 관찰의 영속화와 detached facts/source 조회, short transaction/caller Connection facade를 구현했다. 기존 table을 사용하며 legacy ephemeral 기본 수명·lookup 오류를 유지한다. API와 Worker의 CaseStore에 `stored_adapter_factory`·`ProducedReader`·RecordingFacts를 주입하고 기존 T2 reflector를 기본 entrypoint에 연결했다. Coarse/Fine은 명시적인 Recording module profile mapping과 Case가 선택한 VIDEO ref로 공개 Recording→Search media composition을 수행한다. execution마다 RecordingService를 만들고 context 종료에서 닫는다. 공개 clip byte API는 기존 호환성 검사에 따라 추가하지 않는다.
- 실제 Search payload는 기존 RT-10(a) T1 object/terminal 원자 저장을 사용한다. 정상/FAILED/PARTIAL T2 및 rollback/COMMIT 불명·UsageSink·cancellation 회귀를 검증했다. SQLAlchemy persistence 오류도 Search helper로 흡수하지 않는다. 기본 helper 탐색·등록 regression으로 이전 독립 리뷰 P3 공백을 보완했다. 상세 입력·수명·설정 경계는 [production composition checkpoint](rt10b-production-composition.md)를 따른다.
- **직접 RED→GREEN:** durable facts6 FAIL→70 PASS/2 기존SKIP, 실제 MySQL durability4 FAIL→4 PASS, media10 FAIL→33 PASS, stored T2/API4 FAIL→4 PASS, bootstrap2 FAIL→53 PASS, 별도 process E2E4 FAIL(잘못된 요청 fixture)→4 PASS다. compatibility/lineage/no-media T2 추가 RED도 각각 보존했다. 관련 offline 최종 **2254 PASS/21 기존SKIP/970 deselected**,213.45초; 실제 MySQL 최종 **226 PASS**,159.38초; clip API 제거 이후 durable file 별도 **6 PASS**,3.41초다. process4개는226개에 포함되며 합산하지 않는다. 중간 offline1 FAIL(금지 clip API) 및 MySQL1 FAIL(test NameError), collection/fixture/setup 오류도 성공으로 바꾸지 않고 독립 보존했다.
- JSON/JUnit의226/678 phases·6/18·4/12 unique selection/완전 phase/skip·xfail0를 감사했고 실제 JUnit entry 누락을 거부했다. 기존 strict full checker는 각 subset을 필수 role/scenario 부족으로 거부한다. gate negative controls15 PASS, boundary0·Contract62/26/104·diff check PASS다. Contract·Case/Search/Readout/jobs source·gate/inventory/workflow는 base 대비 그대로며 workflow30분/nested900초도 유지한다. whole pytest·전체 필수 MySQL/wrapper·전체 mutation·유료 provider·현재 diff remote CI는 미실행이다. 관련 offline/DB 회귀와 중복 비용을 고려했고 이를 전체 gate PASS로 표시하지 않는다.
- API/Worker는 별도 OS process, 실제 MySQL/ffmpeg/SDK와 offline HTTP transport로 normal/Coarse PARTIAL/Coarse FAILED/Fine FAILED를 검증했다. API child 안의 ASGI TestClient이며 TCP listener acceptance가 아니다. Fine 발주는 test에서 Case 공개 함수를 명시적으로 호출하므로 자동 선택·clip/readout 후속 완료를 의미하지 않는다. #403이 없는 develop에서는 기본 Search registry가 계속 미등록이며 테스트의 confirmed-policy port가 운영 대체 구현은 아니다.
- **pending 유지:** #403 HINT401/403/404+budget taxonomy(최신 확인 댓글6398537018), #405 STALE 최종 소진 terminal 알림·자체 receipt·Case 정책. 기존 T2/`case_applied_at`을 넓히거나 Runtime에서 새 발주·실패 정책을 만들지 않았다. clip/readout/export handler는 계속 제외/미등록이다.
- owned MySQL8.4.7 종료·정확한 datadir 제거·port refusal, 전용 base 외 사용자 schema/account0·non-audit client0·transaction0·lock0을 확인했다. 별도 child는 join했고 새 empty root lock2개는 exclusive 확인·backup 후 제거했다. 기존 backup/evidence·공유 runtime은 보존했다. `.codex-scratch/rt10b-composition-20261026/` 전체와 local plan은 PR 제외다. 다음 단계는 같은 대화의 fresh-context 읽기 전용 reviewer이며, 이번 확장 구현에 대한 결과는 후속 기록한다. stage/commit/push/PR 생성은 없다.

### 2026-10-26 — production composition 독립 리뷰와 P2 후속

**IN_PROGRESS · Refs #297 (RT-10(b))**. 구현 이력을 전달하지 않은 fresh reviewer1명(`fork_turns=none`)이40개 변경 파일·SoT·원격 합의·보존 증거를 읽기 전용으로 검토했다. manifest40개/HEAD/branch/index empty를 확인했고 테스트·DB·validator 실행이나 파일 변경은 없었다. 초기 P2 1건: `TransactionRetryExhausted`가 SQLAlchemyError가 아니어서 capability 아래 Runtime transaction 오류가 Search helper로 들어갈 수 있었다. P1·추가P3는 없었다.

저자가 같은 오류를 재현한 후 명시적 Runtime DB outcome4종만 helper앞에서 재전파하도록 최소 수정했다. 일반 RuntimeError 전체를 제외하거나 DB runner/registry/T1을 바꾸지 않았다. 처음RED21FAIL/4PASS에는 test sleep-injection 오류1개가 포함되며 별도 보존했다. 수정된 RED2는 기대 오분류 **21FAIL/4PASS**, GREEN **25PASS**, 관련 offline focused **167PASS**,12.59초다. 실제 transaction runner의 disconnect3회 소진,6개DB오류×HINT/Coarse/Fine/resolver를 검사한다. 이전2254 offline/226 MySQL은 guard수정 전 실행으로 보존하고 post-fix 결과로 바꾸지 않는다. SQL/transaction/lifecycle 변경이 없는 guard수정이라 추가 전체/DB중복실행 대신167개focused를 수행했다.

같은 reviewer가 원래40개 대비 source/test2개 delta만 읽기 전용으로 재확인하여 **P2해소·새P1/P2없음**으로 판단했다. 나머지38개동일·follow-up40hash일치·HEAD/branch/index empty를 확인했다. 새 reviewer를 추가하지 않았다. 이는 정적 리뷰이며 전체 RT-10 완료/병합 승인이 아니다. #403 실제helper/HINT인증 분류·#405 STALE 통지/자체receipt/Case정책, 제외handler·자동제품orchestration·대용량/liveprovider·Search내부temp/SDK운영수명·전체gate/currentdiffCI는 판단보류/미실행 그대로다. 상세 실행·실패 이력과 범위는 [composition checkpoint](rt10b-production-composition.md)의 후속 기록을 따른다. 최종 문서만 append하고 미커밋·미스테이징 상태로 보고한다.

### 2026-10-26 — PR #403 병합 통합과 PR #407 원격 E2E 재현

**IN_PROGRESS · Refs #297 (RT-10(b))**. clean한 codex/rt12b-observability(`42a4712d…`)를 확인한 뒤 요청한 codex/rt10b-handler-registry(`52629d4b…`)로 전환했다. 두 번째 tree/index도 clean이었다. PR #403 merge `405512cd0c8b74fd602b9557668f8603fd9d286e`와 origin/develop 일치를 확인했다. 공통 base42ddea72 이후 경로 비중첩이며 `--no-commit` merge는 충돌 없이 끝났다. 자동 index 변경은 해제하여 HEAD52629d4b·MERGE_HEAD405512cd·index empty인 미커밋 merge 상태로 보존한다. 새 commit·push는 없다.

- 원격 #403 head8a541310의 python-tests40253669661/boundary40253669630 성공과 HINT 보완 답변6406363557을 확인했다. 이는 선행 head CI이며 현재 미커밋 통합 CI가 아니다. #407 head52629d4b의 python-tests40230798384/test121281892941는 여전히 실패다. 네 process case 모두 HTTP0, 이로 인한 nested report 검사 실패를 포함해 원격전체5FAIL/12182PASS/33SKIP였고 strict gate step은 실행되지 않았다.
- 실제 공개 helper import·기본 discovery는 기존 코드로 동작한다. process test의 임시 ConfirmedPolicyPort를 제거하고 실제 기본 composition을 사용한다. 기본 helper 결과/예외 투영과 Runtime input/transaction/persistence/checkpoint helper 미진입 검사를 추가했다. 초기15개 중3FAIL은 test context/sink 불일치 실수이며 별도 보존했고, 수정된15개는 PASS다. production dispatcher·Search taxonomy는 추가 수정하지 않았다.
- Linux ffmpeg6.1.1에서 원격과 같은 네 HTTP0 실패를 재현했다(4FAIL,203.25초). trace/probe로 Recording 출력의 마지막 frame duration 근거 누락을 확인했다. 생성 H.264 MP42종은 기존 strict check에 실패하고 MPEG-4 AVI는 통과했다. 검증 정책을 완화하지 않고 fixture를 실제 지원되는 AVI로 변경했다. 기존 HTTP1/pool0 검사와 외부 응답 privacy 검사를 유지하고 실제 helper terminal 투영 및 별도 HINT Worker→기존 Case T2→Coarse 경로를 추가했다. Fine 발주 판단은 기존처럼 Case의 공개 함수에 명시적으로 맡긴다.
- 직접 helper/SDK/usage151PASS, 관련 offline2328PASS/21기존SKIP/970deselected(327.87초), 실제 MySQL72PASS(58.99초), Windows default process5PASS(91.22초), gate음성대조14PASS·boundary0/Contract62·26·104/diffPASS다. 실행별 수치는 합산하지 않는다. `linux-process-green` 이름의 중간 실행은5FAIL(472.50초,peer timeout)이며 성공으로 바꾸지 않는다. WSL 공유파일 I/O 지연을 피한 owned Linux-native scratch에서 같은 코드 normal1PASS(92.25초)를 확인했고 전체Linux matrix는 이 기록 시점에 진행 중이다. timeout·workflow30분·nested900초는 그대로다. 상세 증거/한계/후속 결과는 [composition note](rt10b-production-composition.md)에 시간순 추가한다.
- #405 STALE 알림/자체receipt/Case정책은 사용자 지시로 이번 통합에서 제외하고 pending 유지한다. 기존 T2와 case_applied_at 의미, Contract·Accepted Decision·Baseline·다른 Owner surface는 변경하지 않는다.

2026-10-26 최종 직접 검증 후속: Linux-native 전체 matrix는 **5PASS,474.95초**로 끝났다. 원격과 같은 ffmpeg/ffprobe6.1.1-3ubuntu5이며 Windows와 소스는 동일하고 도구/임시 미디어 위치만 변경했다. 이전5FAIL 실행은 실패로 보존한다. DB72개/216phases·Windows5/15·Linux5/15 JSON/JUnit의 unique/complete/all-pass/no-skip-xfail을 감사했고 실제 testcase 누락을 기존 validator가 거부했다. full inventory는 각부분집합을 필수 role 부족으로 거부하므로 전체 strict gate PASS가 아니다. production source·Contract·harness/gate/workflow는 통합 직후 snapshot과 동일하다.

whole pytest·전체 mandatory MySQL/nested wrapper·전체 mutation·live provider·대용량/일반 media·현재diff 원격CI는 미실행이다. 관련2328offline/151focused/72DB와 양OS process 검증의 중복 비용을 고려했고, 미커밋/미푸시diff의 원격CI 성공을 주장하지 않는다. #407 기존원격실패는 그대로다. workflow30분·nested900·peer60·runner880초를 유지했다. owned MySQL8.4.7 종료/정확한datadir제거/port refusal, default계정·전용base외사용자schema0 및 non-auditclient/transaction/lock0을 확인했다. native도구/media와 새패키지cache는hash/evidence보존뒤제거했고 새emptyrootlock2개는exclusive확인/backup후제거했다. 공유runtime/이전증거는보존했다. scratch/RAW/JSON/JUnit/runner/probe/stack/DB는PR제외다. 현재 HEAD52629d4b·MERGE_HEAD405512cd·indexempty·미커밋merge 상태에서 통합delta만 fresh-context읽기전용리뷰를 준비한다. #405pending·IN_PROGRESS · Refs #297 (RT-10(b)) 유지.

2026-10-26 사용한도 후속: fresh reviewer의 첫 turn은 사용한도 오류로 끝나 verdict가 없었다. 사용자 재개 요청 뒤57개hash/HEAD/merge/index 무변경을 확인하고 같은 reviewer를 재개했다. 읽기 전용 결과는 P1/P2없음·P3한건(HINT값 보존검사 공백)이다. 새HINT process 검사에 public hints vehicle/situation literal 보존을 추가했다.

재개 중 원격 develop이 #395 merge `a08d671547a9e1a79deac2464d0d0ae43f34f17f`로 진전됐음을 확인했다. 추가10경로와 작성6개는 비중첩이며 old/new merge-tree 모두 내용충돌0이었다. 전체57개backup후 index stat 미갱신으로 첫 read-tree update가 거부됐고 MERGE_HEAD update-ref도 pseudoref제한으로 거부됐다. 실패를 성공으로 표시하지 않았다. 내용동일 검증·stat refresh뒤 two-tree 갱신은 성공했고 upstream10개동일/작성6개hash유지를 확인했다. guarded atomic metadata update로 pending merge 대상을a08d6715에 맞춘 뒤 index를 비웠다. HEAD52629d4b·기존branch 유지, 새commit/rebase/worktree/push없음이다.

최신source 별도 직접 검증은 focused153PASS(15.14초)·실제MySQL72PASS(52.42초)·Windows process5PASS(95.62초,새HINT값검사포함)·boundary0/Contract62·26·104/diffPASS다. 72/216phases·5/15 JSON/JUnit 완전성/skip-xfail0·실제entry누락거부를 확인했고 fullinventory는 부분집합으로 거부한다. 앞2328offline/Linux5는405512cd source의 보존증거로 구분하며 최신source 결과로 바꾸지 않는다. 추가변경은provider예외/Owner tests이고 media/Runtime core무변경이므로 새153SDK/fault·72DB·5process 검증 후 전체offline/8분Linux재구축은 반복하지 않았다. 전체pytest/mandatorynested/fullmutation/liveprovider/currentdiffCI미실행과 #405pending은 유지한다. 두번째DB는별도evidence로종료하고 같은reviewer의추가delta읽기전용판정을 후속기록한다. IN_PROGRESS · Refs #297 (RT-10(b)).


2026-10-26 최종 독립 재리뷰: 같은 fresh reviewer가 추가 develop delta와 HINT assert2개를 읽기 전용으로 재확인해 **P3해소·새P1/P2/P3없음**으로 판단했다. authored6/전체62hash·integrated2136개·추가upstream10개blob 일치와 HEAD52629d4b/MERGE_HEADa08d6715/indexempty/conflict0을 직접 확인했다. reviewer는 테스트/DB/validator를 실행하거나 파일/ref/index/PR을 바꾸거나 추가agent를 만들지 않았다. 153/72/5는 저자의 JUnit 보존증거를 읽은 결과이며 reviewer 실행 증거가 아니다. 기존판정보류(최신Linux전체/전체pytest·mandatorynested·fullmutation·currentCI/#405/제외handler·media/liveprovider/전체RT10)는 유지한다.

저자는 결과기록 전62개hash동일을 재확인했다. 두번째ownedMySQL8.4.7 종료·정확한root제거·portrefusal·기본계정/schema와전용base외사용자항목0·non-auditclient/transaction/lock0,rootlock/native도구잔여없음을 확인했다. 이전server로그copies/각실행/backup은분리보존했다. 최종작성변경6개와자동upstream56개(총62개)를구분하며scratch/RAW/JSON/JUnit/runner/probe/stack/DB/로컬plan은PR제외다. 내용충돌의미선택·새정책·T2확장없음,미커밋merge/indexempty/commit·push·PR변경없음으로보고한다. **IN_PROGRESS · Refs #297 (RT-10(b))** 유지.

## RT-12(b) 관측 집계 · catalog/privacy — 2026-10-26

- **IN_PROGRESS · Refs #299 (RT-12(b))**. PR/merge SHA pending. 시작 clean,
  승인된 기준 `42ddea72bb927e7adedf352ba53d160bda1aa049`에서 구현한다.
- 구현 권위는 [Runtime Owner 확정 답변](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/299#issuecomment-6367448332)이다.
  nearest-rank/empty 분포 None/고정 group 유지·동적 group 생략/queued_at 기준
  eligible oldest age와 0 하한은 이번 명시적 구현 convention이다. 기존 eval
  규칙을 자동 상속한 것으로 기록하지 않으며 Baseline/Contract는 수정하지 않는다.
- 단일 read-only DB statement로 queue/duration/stale/retry/cancel/usage snapshot을
  반환한다. 기존 UTC, #370 causal timestamp, transaction/ownership/retry/cancel/
  usage recovery writer는 변경하지 않는다. 누락 false STALE 및 view/upload 관측만
  Runtime/API 내부 경계에 추가한다. asset/ASGI 경로와 cleanup empty Context는 보존한다.
- catalog 32 metric/32 event의 실제 producer·필드·status와 privacy를 검증하며,
  필수 MySQL check/parameter를 추가했다. 기존 inventory와 30분/900초를 완화하지 않는다.
- **과거 증거 분리:** PR #390 RT-12(a)의 merge SHA는
  `1c876620d71f8c6f323a3e920139c0dc444a82c7`다. PR 본문이 보고한 원격 boundary
  PASS, pytest 10,794 passed/33 skipped, MySQL gate 911 PASS(skip/xfail 0)는
  RT-12(a) 과거 결과이며 이번 수치에 더하지 않는다.
- 직접 RED→GREEN·실패 원본·정확한 계산/group/empty 의미·전체 event catalog와
  Implementation Notes 초안은 [RT-12(b) Notes](rt12b-observability.md)에 기록했다.
  현재 최종 query focused 49 passed, 영향 경로 회귀 511 passed다. 최초 mandatory는
  testcase 1,021 passed여도 catalog 위반 때문에 process exit 1이어서 FAIL로 보존한다.
  초기 두 회귀 실패/중단/환경 오류 역시 후속 성공으로 소급 변경하지 않는다.
- retention/purge/disk guard/CloudWatch/정기 기록/orphan/P-6/RT-10 handler와
  새로운 HTTP/CLI/dashboard는 제외한다. staging/commit/push/PR 생성은 하지 않는다.
  최종 nested gate/mutation·fresh read-only review·자원 정리 결과는 후속 기록한다.


### RT-12(b) 후속 검증 · fresh review — 2026-10-26

- **IN_PROGRESS · Refs #299 (RT-12(b))** 유지. 최종 신규 focused 50 passed.
  영향 경로 이전 직접 회귀 511 passed, 신규 gate 단위 137 passed는 각각의
  실행 범위로만 기록하며 합산하지 않는다.
- fresh read-only reviewer가 mutation 총건수 산식 누락 P2를 발견했다.
  선택 8,415/기대 8,129의 RED를 보존하고 신규 22×13=286을 포함하도록 수정,
  산술 GREEN과 reviewer 재확인으로 해소했다. 코드 미해결 P1/P2는 없다.
- 최초 nested 정상 child는 실제 MySQL 8.4.7의 1,022 passed/skip0/xfail0,
  strict JSON/JUnit PASS, catalog 32/32·위반0이었다. 그 parent는 산식 오류로
  FAIL이었다. 수정 후 nested도 기존 Worker periodic-exit-logger의 변경하지 않은
  30초 timeout 때문에 child 1,021 passed/1 failed, parent exit1/strict gate FAIL이다.
  단독 파일 전용 진단은 통과했으나 원인은 미확정이며 실패를 소급 변경하지 않는다.
- 정상 child 원본 SHA를 유지해 현 validation tail을 별도 실행한 actual mutation
  재생은 8,415 execution mutation 전부 거부(신규286), 신규 metadata/family 누락93
  전부 거부로 PASS다. 새 DB 실행이나 전체 nested 성공을 뜻하지 않는다.
- 통합 readiness는 차단 상태다. 알려진 gate 실패가 있어 전체 pytest는 확장하지
  않았고 미실행/원격 CI 미실행을 명시한다. 30분/900초/기존 test timeout, sleep,
  retry, inventory, skip/xfail 정책을 변경하지 않았다.
- owned DB/helper 종료·정확한 datadir 제거·양쪽 port 폐쇄·transaction/lock0·잔여
  owned process0 및 test temp18개 제거를 확인했다. 텍스트 evidence4,628개는 ZIP과
  별도 canonical child evidence로 보존했다. [최종 Notes/전체 18개 변경 파일](rt12b-observability.md)에
  계산·catalog·privacy·실패 원본·Implementation Notes 초안·위험과 PR 제외 범위를
  남겼다. 미커밋/미스테이징이며 staging/commit/push/PR/Issue 변경은 없다.

- 최종 정적 확인: boundary PASS, Contract fixture 62/26/104 PASS, Python/boundary actionlint PASS, git diff --check PASS. Python 변경 16개는 최종 focused evidence SHA와 일치하며 전체 변경 18개/승인 HEAD 유지/staging 없음이다. 문서 후속 기록은 검사 실행과 구분한다.

### RT-12(b) periodic-exit-logger 30초 원인 분리 — 2026-10-26

- **IN_PROGRESS · Refs #299 (RT-12(b))** 유지. 제품/test/gate code 수정 없이
  원본 RAW/JUnit/cleanup archive와 child 출력·종료 상태의 관측 공백을 대조했다.
  현재 동일 설치경로의 subprocess.py:1630은 stdout reader thread join deadline
  경계이며, EOF/close/스케줄링 또는 child 정체 단계를 원본에서 구별할 수 없다.
  RAW의 Popen repr returncode1은 timeout 후 kill/재수집 경계 뒤 객체 상태이며
  정상/강제 종료나 deadline 시점 실제 native child 상태를 증명하지 못한다.
- 승인 HEAD42ddea72의 깨끗한 archive와 candidate snapshot을 동일 Python/MySQL
  8.4.7로 비교했다. 기준/현재 단독 무계측 각각1 passed, 계측 각각1 passed,
  동일 선행921개 순서 각각921 passed다. 원래 수집경로/catalog probe/신규 선행을
  포함한 별도942개 prefix도942 passed(628.73s)였다. 이 진단은 outer nested/
  strict 전체 gate가 아니며 원래1021 passed/1 failed/strict FAIL을 대체하지 않는다.
- 계측한 대상은 예상 child exit1/stdout428 동일SHA/stderr0, main/cleanup/atexit/
  두 pipe EOF 완료와 target stack0이었다. timeout30/900와 workflow30분, sleep,
  retry, inventory/skip/xfail 정책을 보존했다. RT12 인과관계·baseline 동일 실패·
  특정 환경 원인은 미확정이므로 추가 RED/수정 단계에 진입하지 않았고 해결 선언도
  하지 않는다. 기존 실패와 이번 직접 관측은 별도 보존한다.
- 전/teardown 후 DB client/transaction/lock0, fixture checkedout0와 관련 listener
  동일, 종료 전 기본 schema/account 유지, 소유 MySQL/helper/97개 관측PID 잔여0,
  UUID datadir와 Linux listener 부재를 확인했다. Windows는 첫 종료후 접속 수락,
  이후 owner/listener 없음, 마지막connect_ex10035로 즉각적 접속 거부 증명 미확보다.
  원인은 미확정이며 공유 WSL/relay를 강제 변경하지 않았다. test temp7개 제거,
  bounded text67개(cleanup receipt46개) CRC/SHA ZIP 보존과 원본 hash 불변을 확인했다.
- 조사 방법·단계별 시간·setup 실패·한계와 fresh read-only 재검토 결과는
  [Notes의 후속 조사](rt12b-observability.md)에 기록한다. 전체 pytest/새 전체 nested/
  strict/mutation은 이번 조사에서 미실행이다. 조사 후 tracked 추가 수정은 Notes와
  이 log뿐이고 product/test16개 hash는 시작과 동일하다. staging/commit/push/PR은 없다.
- 구현/대화 이력 없는 새 read-only reviewer가 RAW/JUnit/phase/Git blob/ZIP을
  독립 대조해 이번 조사 범위의 확정 코드 P1/P2 없음, 원본 미해결 및 병합 차단
  유지를 재확인했다. 기존 구현 전체 재승인이나 새 실행 증거가 아니다. 초기
  단독 arm의 diagnostic SHA 미보존도 추가 명시했다. 현재 source에 diff check를
  실행했고 제품/test16개 불변·전체 후보18개·staging0을 최종 확인한다.


### 2026-10-26 — RT-10(b) PR #407 CI timeout 조사와 evidence-copy 최소 수정

**IN_PROGRESS · Refs #297 (RT-10(b))**. codex/rt10b-handler-registry의
HEADdac940dc2bb638a56df8fa03953c77c6f171ac96·working tree/index clean을 확인하고
시작했다. PR head/base1943cb51e2bd579a02f09d67f104f16c52666c88 동일,
Draft/MERGEABLE/UNSTABLE·boundary SUCCESS·python-tests40321183978/121566213929
CANCELLED·후속 strict SKIPPED를 원격 읽기로 재확인했다. 최신 성공 develop
40320484510/121563856235는 pytest1721.76초, job1789초로 제한에 근접했다.

원격 동일72-node block1081-1152는741.28→783.93초(+42.64), gate-unit 포함
구간은173.45→172.18초였다. 신규 E2E 인접 구간은25.74→81.33초지만 끝5개
node가 달라 개별 테스트 시간으로 단정하지 않는다. Linux 수집12610와 추가135개를
대조한 조건부 취소 후보 범위는12312-12384(redelivery/reflection/첫 Search capability)다.
원격 active node·nested child/mutation 경계와 개별 신규 테스트 증분은 미확정이다.

새 synthetic 전체 mutation에서 반복 report deepcopy 비용을 확인하고 TDD로
목록 필터는 retained evidence를 복사하지 않으며 metadata는 기존 node별 격리 helper를
재사용하도록 최소 수정했다. 기존 알고리즘 재현 RED1 failed/2 passed(0.66초),
GREEN3 passed(0.40초)를 분리 보존했다. Linux 무계측 paired68.014→40.442초,
8415 mutation·2842개 산출물 hash 동일·입력 불변이며 원격 절감 추정치는 아니다.

직접 검증: gate-unit/helper8412 PASS(383.37초), fresh 실제 MySQL nested child
1027/3081phase·skip-xfail0·JUnit838.736초, 부모1 PASS(966.96초),8415 parameter와
1501 metadata/family omission 거부, strict CLI 정상exit0/phase·JUnit 누락 각각exit1,
boundary0/Contract62·26·104 PASS. 전체 outer pytest/전체1045 MySQL 단일 실행은
미실행이다(바뀐 mutation 경로와 mandatory nested를 직접 검증했고 제품 코드 불변).
이전 원격 성공·현재 직접 실행·synthetic 진단을 구분하며 실패/RED를 후속 PASS로
바꾸지 않는다. workflow30분·nested900초·inventory·strict/skip/xfail·제품 의미 불변,
#405 pending 유지다. owned DB 감사·종료/정확한 datadir 제거/Linux port closure를
확인했다. Windows port 및 구현 이력 없는 fresh read-only review 결과는 후속 기록한다.
조사 상세/시간의 한계는 [후속 Notes](rt10b-production-composition.md)에 추가했다.
scratch/RAW/JSON/JUnit/XML/profile/runner/probe/DB는 PR 제외이며 staging·commit·push·
PR 변경·CI 재실행은 없다. 새 원격 full pytest/strict gate 성공 전 병합 가능으로 판단하지 않는다.


DB 후속: 기본계정/전용base 외 schema 없음·auditor/system scheduler 외 client 없음·
transaction/lock0·owned process 종료·UUID datadir 부재·Linux connect_ex111을 확인했다.
Windows는 비승인 probe10013, 승인 probe10035(2초)로 즉시 접속 거부를 증명하지 못했다.
공유 WSL/forwarder는 변경하지 않았으며 잔존 DB process를 발견한 결과는 아니다.


같은 대화의 새 reviewer(`fork_turns=none`)가 HEAD 대비 미커밋5개 delta만 읽기
전용 재검토해 P1/P2/P3 없음으로 보고했다. metadata 격리·retained node 읽기 전용
공유·fresh child/모든 mutation/정책 보존과 문서의 관측/추정 구분을 확인했다.
리뷰어 직접 수행은 파일/Git/hash/보존 JSON·XML·로그 검사이며 테스트/DB/원격CI는
실행하지 않았다. 전후5개 manifest hash·branch/HEAD·index empty가 같았고 저자도
이를 재확인한 뒤 결과만 후속 추가했다. 검토 source snapshot은 ignored scratch에
보존한다. 이는 RT-10 전체 재승인이나 병합 가능 판정이 아니며 새 원격 full pytest와
후속 strict gate 성공이 계속 필요하다. **IN_PROGRESS · Refs #297 (RT-10(b))**,
미커밋/미스테이징·commit/push/PR/CI 변경 없음으로 먼저 보고한다.


### 2026-10-27 — RT-10(b) PR #407 두 번째 CI timeout·tail/fixture 조사

**IN_PROGRESS · Refs #297 (RT-10(b))**. 요청한 codex/rt10b-handler-registry,
HEADbc45925595dd540012432cd6dabd90ddcf06c9b6·working tree/index clean을 먼저 확인했다.
PR40334969445/121613963782는12456 outcome·98% 뒤 final summary 없이 CANCELLED,
strict SKIPPED·boundary SUCCESS다. Linux12611 수집 기준의 조건부 active 후보는
12456 teardown~12528이며 Search 경계/handler/input~sweep/usage 구간이다. 원격
active node 자체는 미확정이다. 마지막 outcome+잔여155개를 동일 순서로 새 Linux/
MySQL 실행해156 PASS(176.86초),468 phase·skip/xfail0과 node별 시간을 보존했다.

최신 성공 develop40331287437/121601052393(4295abff)은 이전1943cb51 이후 Case
문서3개뿐이고 코드/test 동일이다. 이전PR/최신PR/최신develop의 동일 nested 포함
1081-1152 구간은783.926/742.443/720.580초, gate-unit 내부1225-9576 구간은
143.509/163.816/138.776초다. child/mutation 원격 분해 및 나머지 offset 구간의
동일-node 비교는 불가능/부정확하므로 추정으로 남겼다. 원격 이전 최적화 포함
구간의41.483초 절감 관측을 한 함수의 확정 효과로 단정하지 않는다.

직접 전체 unit profile에서 번호 suffix 탐색6077회(28.983초),find_prefixed
재개18425500회와 fresh synthetic report의 중복 deepcopy(23.677초)를 확인했다.
entry 개수와 generator 재개 수를 구분한다. unit 전용 pytest managed 임시base
안에 UUID 경로를 할당하고 이미 fresh인 role report의 두 번째 copy만 제거했다.
outer JSON/JUnit 경로·전달 구조·모든 검사·inventory·strict/skip/xfail·제품 동작·
nested900초/workflow30분은 그대로다. 새 정책/Contract/Decision/Baseline 변경 없고
#405 pending 유지다. 소유 basetemp의 RED2실패(0.96초)→focused3PASS(0.93초),
전체 unit/helper8412→8414PASS(같은 profile167.78→160.73초),기존 모든 case 보존을
확인했다. 두 guard만 추가됐다. 무계측 순차299role+6069parameter/real allocator는
53.123→33.879초,1734XML해시 동일이다. host stat/대기 편차 때문에 원격 절감량이나
30분 해소를 보장하지 않는다. 초기 Windows default temp 준비 실패와 profile 후처리
실패는 별도 보존했으며 성공으로 바꾸지 않았다.

새 실제 MySQL nested child1027/3081phase·JUnit613.169초·skip-xfail0,부모1PASS
(697.52초),8415parameter+1501omission 거부,strict 정상exit0/phase·JUnit 누락 각각
exit1을 직접 확인했다. unit 변경은 nested에 사용되지 않으므로 이 시간은 개선폭이
아니다. 전체 outer pytest/전체1045MySQL 단일 실행 미실행,검증집합 밖14개도 명시한다.
ownedDB system·전용base외schema없음/auditor·system scheduler외client없음/transaction-lock0,종료·정확한UUID root제거·
Linux port111을 확인했다. Windows는 최초accept0→후속10035로 즉시거부 미확인,
공유WSL/service는 변경하지 않았다. scratch/RAW/JSON/JUnit/XML/profile/runner/probe/DB는
PR제외다. 새delta는 unit파일1+후속문서2이며 staging·commit·push·PR변경·CI재실행 없이
fresh read-only review를 준비한다. 상세 한계/근거는 [후속 Notes](rt10b-production-composition.md)에 추가했다.


같은대화fresh reviewer(fork_turns=none)가 새3파일 delta를 읽기전용검토해
P1/P2없음·P3 1건을 보고했다. 비기본 tmp_path_retention_policy=failed에서 표준
case별cleanup을 새fixture가 우회하는 조건부차이다(default all CI는 영향없음).
저자는설치pytest원문확인→실제subprocess보존정책RED1실패(2.55초)→non-all에서
표준tmp_path위임으로focused4PASS(2.43초)했다. 최종Linux무계측전체unit/helper
8415PASS(113.68초),기존8412case전부+guard3개·JUnit비통과0을 확인했다. 이시간은
계측전후167.78/160.73과직접비교하지않는다. 기존순차pair의핵심함수는AST동일하나
측정source는구분보존하며새guard의로컬8.24초비용도원격추정치로쓰지않는다.
actual nested/validator/harness/helper/선택입력은마지막보완전후raw hash동일이고
unit파일은nested미선택이므로새actual재실행으로부르지않고직전fresh검증을유지한다.
이전review3hash/원본snapshot/P3기록은별도보존했다. 최종보완delta의읽기전용후속
재검토후staging·commit·push·PR변경·CI재실행없이먼저보고한다. #405pending·
**IN_PROGRESS · Refs #297 (RT-10(b))** 유지.


같은독립fresh reviewer가retention후속/final3파일을읽기전용재검토해기존P3해소,
새P1/P2/P3없음으로보고했다. 원본8412case전부+guard3/최종8415와의도적child
negativecontrol을직접대조했으며테스트·DB·원격CI를실행하지않았다. 초기/후속3개
manifest hash·branch/HEADbc459255·indexempty보존을저자도결과추가전에재확인했다.
리뷰source snapshot은ignored scratch에구분보존한다. 전체PR/RT-10승인·원격timeout
해소판정은아니며새fullpytest최종summary+후속strict성공/30분·900초유지가계속필요하다.
미커밋/미스테이징·commit/push/PR/CI변경없음,#405pending,
**IN_PROGRESS · Refs #297 (RT-10(b))**로먼저보고한다.

## 2026-10-28 — RT-13(b) local logical backup / restore

**IN_PROGRESS · Refs #300 (RT-13(b))**. 기존 기록을 대체하지 않는 후속 entry다.
착수 전 clean branch `codex/rt13b-backup-restore`, HEAD/GitHub 최신 develop
`071bbcca53fc7381592abcb0df7bcb3060324aa2`, #417 ancestor, #300 본문과 Owner
승인을 직접 확인했다. 구현 범위·새 detail·실행법·제약·검증은
[RT-13(b) Implementation Notes](rt13b-backup-restore.md)에 기록한다.

일반 도구는 `daesingo` 논리 dump의 exclusive artifact·DB identity·length/SHA256·
release heads, container operation lock, writer 정지, clean-target restore와
import 뒤 전체 schema/data 재비교를 구현한다. 일반 DB/volume 삭제는 없다.
전용 acceptance만 이번 project 소유 MySQL data volume을 정확한 이름+label로
검사해 교체하며, 동일 media volume의 metadata/ref/bytes 관계를 검증한다.
DB backup이 media bytes를 포함한다고 주장하지 않는다. 공통 DB/migration,
Contract·Decision·Baseline·workflow·gate 정책 변경은 없다.

신규 tool RED24→GREEN24, helper RED4→deploy107PASS를 직접 실행했다.
actual Docker와 관련 MySQL 회귀·독립 review 결과는 아래에 추가한다. 기존 (a)의
과거/원격 CI 수치는 이번 실행에 합산하지 않는다. 전체 pytest·전체 MySQL·strict
CLI는 변경 영향이 runtime deploy script에 한정되어 미실행, 원격 CI 확인 필요다.
운영 backup 자동화·retention·remote storage·media 운영 backup·production
migration/rollback/post-deploy·EC2/OIDC/SSM은 RT-14다.

staging·commit·push·PR 생성·Issue 변경을 수행하지 않는다. scratch/RAW/dump/
credential/JSON/JUnit/Linux replica는 PR 제외이며 미커밋·미스테이징으로 남긴다.

RT-13(b) 후속 직접 실행: Engine 29.9.2 / Compose 5.6.1의 이번 actual acceptance
한 번에서 (a) 회귀9 + backup/restore10 = stage19 PASS, cleanup PASS/remaining0을
확인했다. 합성 case/upload·recording6행·execution3행·12table을 준비하고, 빈 DB에
복원해 heads/schema/data 전체 re-dump 동일성, 전체 행 fingerprint·CaseView·기존
media/ref/bytes, 복원 DB의 Worker 새 job 처리를 확인했다. bytes/hash 대조한 Linux
사본2198파일에서 실행했으며 NTFS 직접 build 성공이 아니다.

관련 MySQL 직접 실행은 최초 socket권한 preflight 차단(수집0), 권한있는focused
85PASS/1FAIL(Windows helper 환경변수 누락), 실패한1개에 기존binary 경로만 제공한
별도rerun1PASS로 구분한다. 최초 원본 전체를 GREEN으로 바꾸지 않는다. fullpytest/
fullmandatoryMySQL/strict는 미실행, 기존 (a) 과거 증거와 합산 없음. fresh read-only
review가 진행 중이며 최종 판정은 후속 append한다.

동일 대화 fresh reviewer 최초 판정 P1없음/P2한건: routines/events가 기본 dump와
re-dump에서 모두 빠지는 schema 손실. 실제 MySQL procedure/event 재현 각각
잘못된exit0 RED→source unsupported-object fail-closed guard 후 각각exit25 GREEN,
영구회귀RED2→deploy109PASS로 수정했다. 권한/운영정책은 넓히지 않았다. reviewer
직접 deploy는 default-temp89PASS/18setup오류와 전용basetemp107PASS를 구분한다.
최종 code로 별도 actual acceptance2를 실행 중이며 첫19-stage 증거와 합산하지
않는다. 동일 reviewer 후속 확인 전 커밋 준비 완료로 판단하지 않는다.

P2 수정 후 actual acceptance2를 hash검증Linux사본2199파일에서 직접 재실행:
새19stagePASS/cleanupPASS/failure0/remaining0. acceptance1과 합산하지 않는다.
동일 reviewer source후속은 기존P2해결/새P1P2없음, 독립deploy109PASS였다.
두번째report/최종audit증거검토는 마지막에append한다. 최종직접Docker audit는
container0/volume0, 기본network3개만유지. 두smoke의전용image/project자원,
관련MySQL전용container/volume, protectedcredential·dump·env·overlay·Linux사본,
소유pytesttemp8개/reviewertemp를정리했다. 공유baseimage/buildcache/기존binary와
다른작업scratch는건드리지않았다. 최신develop재조회는HEAD071bbcca와동일,
indexempty·미커밋10파일·staging/commit/push/PR/Issue변경없음. 전체pytest/
fullMySQL/strict/원격CI미실행, 잔여cancellation/외부writer/운영범위제약은Notes참조.

동일fresh reviewer 최종증거후속: acceptance2 exit0/별도19PASS/cleanupPASS,
source/test6hash일치·Docker최종audit·소유temp부재·정리script·최종문서/diff를
읽기전용확인하고 **기존P2해결/잔여·신규P1P2없음**으로판정했다. reviewer직접
deploy109PASS와 Docker/MySQL보존report검토는별개다. 실취소fault/fullpytest/
fullMySQL/strict/원격CI미검증 유지. **IN_PROGRESS · Refs #300 (RT-13(b))**,
미커밋·미스테이징으로종료하며 merge-ready/RT-13 DONE을주장하지않는다.
### 2026-10-28 — RT-10(b) #405 HINT_EXTRACT 최종 소진 outbox

`RT-10 IN_PROGRESS · Refs #297 (RT-10(b)) · Related #405`

PR / merge SHA: pending. 시작 branch codex/rt10b-exhaustion-notice,
HEAD=071bbcca53fc7381592abcb0df7bcb3060324aa2. 수정 전 working tree/index clean,
직접 조회한 원격 develop과 일치했고 Case PR #415 병합을 포함했다. #405 본문과
Runtime/Case 합의 댓글, #297 관련 경계, Case 결정/공개 함수를 확인했다.

별도 [Implementation Notes](./rt10b-exhaustion-notice.md)에 schema/port/lock/
recovery/운영 event와 검증 한계를 기록했다. Runtime migration runtime_0006,
job_id UNIQUE의 durable job_exhaustion_notice, 고정 notice identity와 최종
STALE ended_at의 동일 tx INSERT를 구현했다. 전달은 비잠금 scan/receipt 확인 →
Case public service의 Case lock → notice FOR UPDATE 재검증 → 기존 enqueue →
notice 전용 receipt 순서다. Case 저장/후속 enqueue/receipt는 같은 caller tx다.
Case adapter는 기존 service.receive_hint_exhaustion만 호출하고 Case reason을
Runtime DTO로 넘기지 않는다. Startup/periodic 별도 callback과 production
StoredCaseExhaustionReceiver를 연결했고 없는 receiver는 pending을 유지한다.

Contract/Accepted Decision/Baseline 의미 변경 없음. 기존 T2/redelivery,
case_applied_at, Case service, 역사 migration은 수정하지 않았다. 신규 safe
runtime.exhaustion.failed는 식별자/원문/payload 없이 FAILED만 기록하며 기존
Baseline metric 목록을 유지한다. Mandatory checker는 inventory만 추가했고
독립 inventory/nested gate의 신규 file/metadata family도 확장했다. 기존
skip/xfail 금지, nested 900초, workflow 30분 정책은 유지했다.

직접 실행 증거(owned MySQL 8.4.7): 초기 outbox RED 3건, delivery/startup RED
2건, inventory family RED 9건. 신규+Case+entrypoint GREEN 75건, 추가 port/
scan-policy/DTO/정상 Search 별도 process E2E GREEN 31건. Gate unit negative
controls 7160건 통과. 실제 신규 execution evidence 58건/parameter 58개/
family 11개에 scoped checker 적용, mutation 881개 거부. 이는 전체 mandatory
MySQL/strict gate 성공이 아니다. 새 event의 metric 자동 편입 회귀 RED 1건을
수정한 뒤 event catalog 회귀 25건 통과, 실제 emitter catalog 위반 0건.
Boundary와 Contract fixtures(62/26/104), diff check 통과. 기존 Runtime 관련
MySQL 회귀와 fresh read-only review는 이 기록 시점에 진행/대기 중이다.

과거 보존 evidence를 이번 실행 성공으로 재사용하지 않았다. 과거 자료에서는
실행 환경/정책만 확인했고 기존 portable MySQL binary로 새 임시 server와
새 per-test schema를 만들었다. 전체 pytest, 전체 mandatory MySQL와 nested
strict gate는 요청대로 원격 CI에 남긴다. Staging/commit/push/PR/Issue 변경
없음. 최종 reviewer 판정/회귀/cleanup/Git 상태는 이 절 뒤에 append한다.


같은 날 후속 검증: related Runtime MySQL regression 224 passed (one
pre-existing Starlette TestClient deprecation warning); cancellation focused 9
passed / 10 deselected. 실제 STOP_ANALYSIS가 durable notice 뒤 STALE에
cancel marker를 쓰는 경계를 추가해 delivery / unknown-COMMIT recovery 2 RED 확인.
생성 시 cancel 판정은 유지하고 후발 mutable marker를 immutable facts에서 제외했다.
최종 focused pass는 461 passed(신규 MySQL 60, DTO 18, Case 11, gate 372).
이번 직접 실행 증거만으로 scoped checker 60 parameter / 12 family, mutation 912
rejected. 전체 mandatory MySQL / nested strict gate 완료를 뜻하지 않는다.
다음 단계에서 fresh reviewer를 실행하고 판정을 append한다.


#### 2026-10-28 fresh read-only review와 수정 완료

`RT-10 IN_PROGRESS · Refs #297 (RT-10(b)) · Related #405`

구현 이력을 상속하지 않는 reviewer 최초 판정: P1 없음, P2 2건. ① nested
metadata omission 기대 개수에 새 inventory가 빠져 정상 실행도 실패함(당시
60×4=240). ② MySQL ascii_bin PAD SPACE 때문에 최종 execution ID의 뒤 공백
별칭을 FK/WHERE가 수용하고 verify_execution이 원본 ID를 exact 비교하지 않음.
실제 원본 nested omission 단계와 MySQL 컬럼을 사용한 유효 RED를 각각 보존한
뒤 inventory/count/family/output 연결과 execution_id exact 비교를 수정했다.
literal 기본 collation을 쓴 최초 fixture 오류는 유효 제품 RED로 계산하지 않았다.

동일 reviewer 재검토: 두 P2 모두 해소, 새/잔여 P1/P2 없음. 최종 469 passed,
MySQL 8.4.7 61 test/183 phase passed 확인. 최종 실행에는 신규 MySQL61,
DTO18, Case11, gate378, nested omission stage control1이 포함된다.
Nested control은 원래 statements와 마지막 assertion을 제어된 inventory에서
실행해 metadata244+family12 omission을 검증하며 전체 DB child 통과가 아니다.
Checker 계산 함수/정책 변경 없이 inventory를 반영한 범위라는 재검토도 받았다.
그 뒤 구현자가 실제 신규61 parameter/12 family의 scoped checker와 mutation
927건 거부를 직접 재실행했다. reviewer가 이 갱신본까지 봤다고 주장하지 않는다.

전체 pytest/mandatory MySQL/nested strict gate·원격 CI는 미실행이다. Worker
부재 시 전달 기한 없음과 잘못된 notice의 반복 pending은 비차단 운영 위험이다.
새 버전부터 생성하는 outbox이며 과거 STALE backfill/다른 kind/purge는 범위 밖.

정리: 전용 MySQL 8.4.7(pid439/port46713) 정상 종료, listener/datadir/init secret/
credential 제거. 종료 전 잔여 per-test schema 0개. pytest fixture 임시 루트는
workspace 경로 검증 후 제거했다. RED/GREEN evidence와 스크립트는 저장소 밖
work/에 보존하며 공유용 report/summary/evidence bundle은 프로젝트 outputs/에
생성한다. 저장소 변경만 PR 후보이며 실제 PR/staging/commit/push/Issue 변경은
하지 않았다. HEAD 및 원격 develop의 최종 동일 여부와 전체 변경 파일 목록은
공유 보고서에 직접 조회해 기록한다. 이 기록은 RT-10 전체 완료 선언이 아니다.
### 2026-10-28 — CI required 실행 분리와 실제 MySQL 중복 제거

`codex/ci-split-mysql-gate`의 clean worktree/index/untracked 및 fetch 후
HEAD=origin/develop=`daf6d14a6118a89e0ec54daa4280f8c7970e9a0a`를 확인했다.
CLAUDE→docs README→Ops §19–20과 PR #352 멘토 원문을 조사했다.
실제 develop branch protection은404(Branch not protected), 적용 rules는[]다.
설정 변경 없이 기존 `test` check를 보존하고 `regression`/`mysql` 병렬 job의
모든 result가 정확히 success인 경우만 aggregator가 성공하도록 분리했다.
각 job30분·canonical actual900초·제품 source/production checker 판정은 그대로다.

직접 baseline 전체12774/MySQL1045/child1027을 수집했고 중복교집합1027·child밖18
(wrapper1+추가회귀17)을 확인했다. 새 실제 partition 수집은12810=
regression11764+canonical1044+media1+gate1, 누락/중복0이다. 새36개는 orchestration
테스트이며 기존12774 전부와 canonical1044를 보존한다. 기존 child1027+별도 smoke1의
총1028회 반복을 제거했다. wrapper는 같은 job의 새 실제 report를 소비하며 원래
strict/catalog/parameter/metadata/family assertions9개를 유지한다. child returncode
assertion만 runner의 check=True로 옮겼다. 실행별 새 디렉터리·token·checkout/workflow
SHA·run/attempt·JSON/JUnit/catalog/collection digest와 실제 selection을 검증한다.

직접 TDD는 새 orchestration36FAIL→36PASS(5.26초), focused gate/mutation helper/
schema policy/orchestration/Deploy8573PASS(161.10초), 실제 media1PASS(2.86초)다.
36개는8573에 포함되며 합산하지 않는다. boundary0, Contract62/26/104, actionlint0,
diff check PASS다. 최초 miniature fixture root/Windows cp949 출력 오류 및 sandbox DB
preflight 실패도 scratch에 별도 보존하고 config/UTF8/실제 접근 권한으로 재검증했다.

새 실제 MySQL8.4.7/Python3.12.14 canonical은1044PASS,3132phase·JUnit1044일치,
MySQL skip/xfail0, pytest687.53초/runner693.47초다. summary의 unrelated Search collection
skip4(typer 없음)는 별도로 공개한다. strictCLI PASS0.20초·catalog32/위반0,
실제-report wrapper1PASS94.05초/runner95.83초,8415parameter+1501metadata/family omission
모두 거부, 전체orchestration789.81초다. 실제 입력 digest는 후속 재검사에도 동일하다.
새 report 복사본 normalCLIexit0/phase누락exit1/JUnit누락exit1을 확인했다.
보존된10-27 child1027의 strict 재검사PASS는 새 DB 실행과 구분한다.

동일 환경·base와 동일한 공통 MySQL2node 비용 재현: outer+child 모델2회실행
4node/8.516초 → 단일partition2node/4.515초. 전체 suite 시간으로 외삽하지 않는다.
기존 원격 성공40500553791은pytest1398.04초/strict1045PASS, 최신PR취소40637818339는
97%·strictSKIPPED·최종summary없음이다. 8%839.927초 출력 공백의 active node는
원격에 기록되지 않았으며 현재local wrapper1181/12774(9.25%)만으로 원인을 단정하지 않는다.
원격head/merge revision도 이번base와 구분한다. 단계별시간·partition·정책·rollback·
원격 확인 항목은 [CI 실행 구조](ci-test-partitions.md)에 기록했다.

fresh-context 읽기전용 reviewer의 초기 독립 검토는 누락/중복0·새P1/P2/P3없음이다.
최종 실제 실행·시간·문서/README delta는 같은 reviewer에게 후속 재확인을 요청한다.
전체 regression/기존 whole outer/새 Ubuntu 원격CI/live provider/실제Compose 배포는
미실행이며 이번 결과로 원격timeout 해소·merge 가능을 선언하지 않는다.

전용 DB는 기본schema/account+전용base외항목0·non-auditclient0·transaction0·lock0을
확인하고 종료했다. 정확한 소유datadir 제거·Linux포트refusal111·mysqld/helper/소유Python
잔여0,secondary helper directory0을 확인했다. Windows 공유wslrelay PID1312의 TCP
listener는 남지만 MySQLhandshake timeout/접속불가다. 공유WSL은 종료하지 않았으며
Windows TCP 폐쇄로 표현하지 않는다. scratch/RAW/JSON/JUnit/profile/runner/DB/credential은
PR제외이고 staging·commit·push·PR생성 없이 미커밋·미스테이징으로 유지한다.

최종 후속 독립 재검토: 같은 fresh reviewer가 실제1044/3132/JUnit1044·모든입력digest,
8415parameter/1501omission rejection·CLIexit0·693.47/789.81초와 문서·README delta를
읽기전용으로 직접 대조해 **새 P1/P2/P3 없음**으로 판정했다. 기존 Log3506줄 prefix
변경0과 append-only도 확인했다. reviewer는 테스트/DB/프로세스를 실행하지 않았다.
작은subset8.516→4.515초는 전체CI wall개선 증거가 아니며 새 Ubuntu CI/전체regression/
원격timeout 해소·merge준비는 판정보류다. 공유WSL relay listener 잔여를 공개하고
제품/checker 무변경·branch/HEAD동일·indexempty를 다시 확인한 뒤 미커밋으로 보고한다.


## RT-10(b) INCIDENT_CLIP_BUILD 최소 slice — 2026-10-28

**IN_PROGRESS · Refs #297 (RT-10(b))**.

시작 시 `codex/rt10b-incident-clip-handler`와 HEAD/최신 fetch origin/develop
`6764c8f7f6dc5ef284db3c9bff3d4d19e02bfe73` 일치, clean checkout/index를 확인했다.
기존 checkout에서 작업했으며 새 worktree·staging·commit·push·PR 작업은 없다.

[#297 Owner 확정](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/297#issuecomment-6464169000)에 따라
build의 `RecordingCapabilityError.code=INCIDENT_CLIP_BUILD_FAILED`만
FAILED / RECORDING_INCIDENT_CLIP_BUILD_FAILED / produced=[]로 매핑한다.
[Recording taxonomy](../modules/recording/decisions/failure-taxonomy.md)에 등재했다.
알 수 없는 code의 문자열 합성이나 입력/checkpoint/DB/persistence 오류의 Recording
분류를 추가하지 않았다. 원문·경로·locator·credential을 결과/로그에 넣지 않는다.

공개 CaseStore.observation_input으로 고정 candidate/generation/span/fine_job_id를
읽고 JobRecord scope와 Coarse/Fine 성공 produced의 결속을 검증한다. 조회의 짧은
caller transaction이 connection을 반환한 뒤 실행별 Recording context에서 공개
metadata/ownership/resolve_span/build_incident_clip을 호출하고 checkpoint·close한다.
build는 execution당 1회다. 결과 payload는 정확히 {incident_clip_ref: ref}이며
immutable clip ref와 별개인 기존 execution별 produced-object receipt를 사용한다.
T1 원자 저장·COMMIT ACK 유실/rollback retry와 T2 정산/후속 발주/재전달 코드는
바꾸지 않았다. 명시적인 Recording incident height/preset/crf가 없으면 미등록이다.
PLATE_READ/OVERLAY_TIME_READ 및 export handler, Case/Web 표시 변경은 포함하지 않는다.

구현 부재 RED36, composition/config RED8, immutable clip receipt 충돌 RED1,
종료 중 취소 RED1, 소수 프레임 경계 RED1을 보존했다. fresh 읽기전용 reviewer의 P2
(실제 frame coverage를 원래 요청 scope tail로 재제한)를 별도 RED1로 재현해 수정했다.
추가 duration 좌표 우려도 RED1로 재현해 Search와 동일한 start+duration 좌표로
수정했다. scope/run/timeline/revision 결속은 유지하고 Case span은 변경하지 않는다.

최종 코드 직접 실행: focused72PASS(2.09초), 관련 offline1634PASS/기존 opt-in17SKIP/
619deselected(169.36초), 실제 MySQL8.4.13 부분집합59PASS(268.12초)다. 이 실행들은
서로 중복되므로 합산하지 않는다. MySQL59개/177phase/JUnit59개가 정확히 일치하고
skip/xfail/실패0이다. 여기에는 API/Worker 별도 OS process7시나리오(10fps/30fps 실제
clip2종)가 포함된다. 각 clip worker의 build/encode1회·providerHTTP0회·느린 경계의
main pool checkout0을 확인했고 두 readout은 같은 ref로 QUEUED다. 실패 후 새 clip
job의2회 호출은2execution 각각1회이며 Fine/기존 produced는 보존됐다. T1/T2 replay는
추가 호출0이다. 과거57PASS/59PASS 및 이전 RT-10 보존 기록은 이 결과에 더하지 않는다.

중간 import/API202/cleanup lock/Case retry 인자 fixture 오류와 환경별 permission/
Python 시작 메모리 실패는 별도 보존한다. 짧은20frame 원본의 추가 probe는 Coarse
provider 이전에 막혀 clip 성공으로 보고하지 않으며, 지원되는1초30fps 원본의
[33,667]ms clip E2E와 구분한다. timeout/skip으로 우회하거나 Owner 제품 의미를 바꾸지 않았다.

boundary·Contract fixture(62/26/104)·git diff --check PASS. 기존 workflow/mandatory
inventory/timeout/skip·xfail/Contract 정책은 변경0이다. 전체 pytest와 전체 mandatory
MySQL은 로컬에서 재실행하지 않았고 원격 PR CI regression/mysql/test에서 확인해야 한다.
live provider/배포/판독·export/package E2E 및 원격 CI는 미실행이다.

완료된 fresh reviewer는 구현 이력 없이 전체 delta를 읽었고 수정 후 source/test와
보존 RED/GREEN72/XML을 재확인해 남은 제품 P1/P2/P3 없음으로 판정했다. 리뷰는
읽기전용이며 테스트/DB/commit/push/PR 작업을 하지 않았다. 앞선 usage-limit 중단
리뷰 시도는 완료 판정에 포함하지 않는다. merge 준비나 RT-10 전체 완료를 뜻하지 않는다.

최종 DB audit는 system+전용 base 외 schema0, non-audit client0, transaction0,
data lock0이다. 전용 컨테이너·확인한 anonymous volume을 제거했고 검증한 task root
아래 temp21개를 제거했다. media/env/임시DB 잔여 없이 RAW/JSON/JUnit은 ignored scratch로
보존하며 PR 제외다. 제거 endpoint의 Windows probe10035는 접속 미성립이며 즉시
refusal/포트폐쇄 증거로 표현하지 않는다. 공유 Docker/WSL 프로세스는 종료하지 않았다.

전체20개 변경 파일·호출/transaction 경계·검증/제한은
[별도 Implementation Notes](rt10b-incident-clip-handler.md)에 기록했다.


### RT-10(b) Readout handlers — 2026-10-29 KST

**IN_PROGRESS · Refs #297 (RT-10(b))**

Existing checkout `codex/rt10b-readout-handlers` started clean; HEAD and
origin/develop both `debc783266d011ab46b102020c8d696a7dbd818e` (PR #440).
Issue #297 Readout/Runtime Owner usage and A decisions were directly checked.
No new branch/worktree, staging, commit, push, PR or Issue mutation was performed.

PLATE_READ and OVERLAY_TIME_READ now use detached public Case fixed inputs,
validate case/job/kind/candidate/generation/scope/durable clip, open an explicit
execution-local OCR/Recording context and invoke only their matching Readout
public function once. Provider invocation observes zero checked-out main-engine
connections. Recording lookup uses public get_incident_clip and closes per
execution; checkpoints surround input/invocation/resource boundaries.

Each invocation issues a fresh rr_ ID, begins usage with that exact planned
readout_run, passes the same ID to Readout, finishes usage, prepares one contract
JSON ProducedObject and returns it to existing T1/reconciliation. FAILED Runs
are preserved with null result and READOUT_INFRA; PARTIAL, abstain, NOT_APPLICABLE
and both UNKNOWN branches remain successful. Runtime ValueError/DB/checkpoint/
payload/context/cancel/usage errors are not recast as Readout failures. The
ledger remains authoritative; Run usage_refs stays derived. No pre-T1 finalize,
common/runtime port/schema or migration extension was made.

Owner-confirmed usage labels/pricing/zero KRW, clip duration (unknown=null), sink
occurred_at and Run-derived latency are applied. Before T1, terminal recovery
without the planned durable Run resolves RUN_NOT_PRODUCED; after T1 it links
the stored readout_run. T1 deadlock/receipt conflict/lost COMMIT and reconciliation
replay do not invoke OCR or duplicate Final usage. Rollback followed by an
actual STALE new attempt creates a fresh Run. Both Case jobs retain the same
clip; both T2 writes were deliberately rolled back and then redelivered using
durable payloads after provider processes exited. CaseView/StoredObservationAdapter
restore both observations and distinguish all three overlay notice meanings.

Direct RED→GREEN: missing handler25 FAIL→25 PASS; inputs/composition28 FAIL plus
1 pre-existing default PASS→combined57 PASS. Final focused boundary/reselection/
new-generation coverage69 PASS (2.33s). Initial test data enum/OCR fixture errors
were corrected against public contracts and are not product fixes. The initial
MySQL16 PASS/2 FAIL was a test's incorrect already-STALE retry seed; real lease
expiry/sweep produced18 PASS. A process timeout was traced to a test's Plate-first
assumption; the test follows Runtime available_at/execution_id order without
changing timeout or orchestration policy. These failed runs remain in ignored RAW.

Preserved direct evidence from before the usage-limit interruption: new handler
MySQL18 PASS/54 phases (31.31s), existing reconciliation30 PASS/90 phases (60.20s).
Product code remained unchanged across that interruption. Resume direct evidence:
related Worker/Readout/Case/Recording/Search/jobs/usage non-MySQL selection2254
PASS/48 FAIL/21 existing SKIP/831 deselected (231.81s), followed by **only those
48 failures** PASS48/48 with task TEMP/TMP outside sandbox restrictions (57.83s).
This is not one all-green full-suite execution. Existing skips cover missing
typer/private real-video opt-ins; existing TestClient and malformed-usage
serializer warnings are recorded, not suppressed.

Related actual MySQL Search/clip/usage/produced/Case49 PASS/147 phases (123.37s).
Full HINT→COARSE→FINE→CLIP→two Readout separate API/Worker process E2E6 PASS/18
phases (248.37s), including success/abstain/three overlay notice branches/FAILED.
Existing process normal/hint/fractional clip3 PASS/9 phases (56.88s). MySQL8.4.13
preflight and scoped JSON/JUnit setup/call/teardown agreement passed; no skip or
xfail in those subsets. Mandatory inventory validation was not claimed for a subset.

Boundary0; Contract fixtures62/26/104 PASS; diff whitespace check PASS. Existing
workflow/inventory/skip/xfail/30-minute/900-second policies are unchanged. Full
local pytest/full mandatory MySQL/remote CI are not run; final full regression
belongs to remote regression/mysql/test jobs. Live Paddle/model download/Linux
deployment latency and export/package completeness remain unverified. Default
production registration remains absent unless an OCR factory is explicitly supplied.

Initial fresh read-only reviewer inherited no implementation history, rechecked
Owner decisions and ran focused54 PASS independently; no confirmed product
P1/P2/P3. Final evidence/docs/resource recheck is recorded in the follow-up below.
No reviewer finding has been silently downgraded or deferred as fixed.

The exact13-file intended deliverable set, invocation/transaction/payload mapping,
direct versus preserved evidence and remaining operational limits are in
[Readout handler Implementation Notes](rt10b-readout-handlers.md). Internal plan,
RAW/JSON/JUnit, generated media/env and disposable DB material are ignored under
`.codex-scratch/rt10b-readout/`, excluded from PR. Final resource audit and staging
verification follow after closing the test resources.


RT-10(b) Readout resource follow-up: final autocommit audit excluding itself found non-audit transactions0, data locks0, other clients0 and unexpected test schemas0. Dedicated codex-rt10b-readout-mysql and its inspected anonymous volume were removed; nine verified task-child test directories were removed. RAW/JSON/JUnit/internal plan remain ignored; generated media/env/DB material was cleaned. Existing process normal/hint/fractional regression3 PASS (56.88s) and all five scoped MySQL JSON/JUnit evidence sets passed phase agreement. Original log byte prefix remains unchanged. Final same-reviewer recheck pending.


RT-10(b) Readout final same-reviewer recheck: P1/P2/P3 none. Reviewer independently passed focused69 (3.67s), validated all five scoped MySQL JSON/JUnit sets, matched exact48 initial failures to48 passing reruns and verified original718403-byte log prefix/SHA256 against HEAD. No reviewer fix round was required. Final13 changed files/staged0; HEAD and origin/develop remain debc783266d011ab46b102020c8d696a7dbd818e. No commit/push/PR/Issue mutation. Full suites/remote CI/live Paddle remain unrun as documented. IN_PROGRESS · Refs #297 (RT-10(b)).


### 2026-10-29 — RT-10(b) Recording export handlers · provisional wire implementation

**IN_PROGRESS · Refs #297, #47, #351.** Current branch
`codex/rt10b-recording-export-handlers`, start HEAD
`85dd30b91b82711a4d56bbc3ea916a3bd3c2a355`, initially clean tree/index.
User explicitly delegates minimal reversible provisional Runtime wires under PM
approval; #47 Owner review remains deferred. Existing Contract meanings, Evidence
limits and #351 response-before-export timing are not redefined.

Recording adds public report/plate export capabilities, actual MP4/PNG output,
measured size, immutable DerivedAsset refs, source lineage and stored transform
provenance. Plate relays `incident_clip_ref`, `frame_ref`, `plate_bbox_xywh`,
`max_byte_size` (existing Evidence SoT 30_000_000 bytes). No crop_ref or
associated_region. Request and limit are fingerprinted. Bounded in-execution
crop/downscale distinguishes `PLATE_IMAGE_EXPORT_FAILED` from provisional
`PLATE_IMAGE_OUTPUT_LIMIT_UNSATISFIABLE`; the latter has no same-input retry
button. Report keeps `REPORT_VIDEO_EXPORT_FAILED` and Contract notice mapping.

Case fixes input at order time in an append-only export map; command and
observation-T2 READY gates issue once per full input after response/evidence.
Worker detaches Recording metadata/bytes in short caller transactions, returns
connections, invokes one capability with DB checkout0, then publishes the same
immutable output in retryable short DML. Existing T1/ProducedObject,
reconciliation and T2 replay avoid media invocation and duplicate DerivedAssets.
Current-input settled products feed CaseView/Evidence; old assets remain intact.

RED/GREEN: Recording missing-capability10 setup failures → actual media10PASS;
handler/order29FAIL →29PASS; immutable-input2FAIL/12PASS → focused46PASS.
Initial related35FAIL/1739PASS/17skip was not accepted. Product entrypoint and
legacy READY-adapter regressions were fixed; media/default-temp permission
failures were separated. Final relevant module run1774PASS/17existing opt-in
skip/660deselected(134.91s), plus actual MySQL8.4.13 export faults20PASS(56.30s)
and separate API/Worker process2PASS(82.81s). JSON/JUnit scope/identity/phases
match with skip/xfail0. Boundary0 and Contract62/26/104, diff whitespace PASS.
Expanded MySQL and fresh read-only review are pending at this checkpoint.

Full file manifest, exact test scope, failed intermediate attempts, PM rulings,
#47 deferred Owner items and remaining risks are recorded in
[Implementation Notes](rt10b-recording-exports.md). Whole pytest/full mandatory
MySQL/nested mutation/current-diff remote CI/live providers/Linux/large media
remain unrun. Abrupt death after publication and before durable T1 may leave an
orphan and a later execution can encode again; no global crash-proof exactly-once
claim. Scratch/RAW/media/JSON/JUnit/env/DB/credentials are excluded. No staging,
commit, push, PR or Issue mutation. Final results and review are appended below.


RT-10(b) Recording export follow-up: expanded actualMySQL56PASS/206.21s,
MySQL8.4.13, JSON/JUnit56identities/168phases/skip-xfail0 (exports23,process2,
Case4,clip9,Readout18). Direct canonical AssetFacts lookup gap was reproduced
RED1 and fixed only for new export-transform-backed assets; focused102PASS
(31.87s) and exportMySQL23PASS(55.37s,23identities/69phases). Earlier1774/56
results remain explicitly earlier-source executions. Fresh read-only reviewer
(fork_turns=none,whole35-file manifest) found P2 A→B→A retry selected B although
A notice was visible. Both kinds' command regressions RED2 →63PASS(0.46s) after
current-full-request retry binding; same-reviewer recheck/full review pending.


RT-10(b) Recording exports final fresh-review checkpoint: the same fresh
read-only reviewer inspected the whole35-file diff and rechecked the P2 fix with
independent no-file production-command probes for both kinds. UnresolvedP1/P2=0.
A production StoredObservationAdapter bbox-change probe excluded old image and
retained current products. Reviewer did not run pytest/DB/media or audit all raw
execution reports. P3 deferred2: permanent adapter correction/reread projection
regression and stamped-frame pixel/no-stamp preservation assertion. #47 Owner
wire decision, full CI, force-kill-before-T1, Linux/font and large-media checks
remain unverified, explicitly not an RT-10/full acceptance claim.

Post-P2 API/Evidence335PASS/248deselected/95.34s, existingStarlette warning1.
Earlier sandbox attempt stalled at first cleanup test and was stopped using
verified task processIDs; cause unconfirmed. Native rerun passed unchanged.
Two task-created empty root cleanup locks were exclusive-open checked and removed.
Autocommit audit: unexpected schemas0/other clients0/transactions0/data locks0.
Owned MySQL container and inspected anonymous volume removed, inventories absent.
Reports/media/env remain only in ignored task scratch and excluded from delivery.
No source credential, staging,commit,push,PR or Issue mutation. Complete changed
files (35):

- `docs/modules/case/decisions/report-video-export.md`
- `docs/modules/recording/decisions/failure-taxonomy.md`
- `docs/runtime/rt10b-recording-exports.md`
- `docs/runtime/runtime-implementation-log.md`
- `src/daesingo/api/composition.py`
- `src/daesingo/case/command.py`
- `src/daesingo/case/domain.py`
- `src/daesingo/case/exports.py`
- `src/daesingo/case/jobs.py`
- `src/daesingo/case/real_e2e.py`
- `src/daesingo/case/reflection.py`
- `src/daesingo/case/service.py`
- `src/daesingo/case/store.py`
- `src/daesingo/case/store_mysql.py`
- `src/daesingo/case/store_state.py`
- `src/daesingo/case/stored_observation.py`
- `src/daesingo/recording/README.md`
- `src/daesingo/recording/exports.py`
- `src/daesingo/recording/mysql_repository.py`
- `src/daesingo/recording/queries.py`
- `src/daesingo/recording/repository.py`
- `src/daesingo/recording/service.py`
- `src/daesingo/worker/case_composition.py`
- `src/daesingo/worker/composition_root.py`
- `src/daesingo/worker/export_composition.py`
- `src/daesingo/worker/export_handlers.py`
- `src/daesingo/worker/export_inputs.py`
- `tests/case/test_export_ordering.py`
- `tests/e2e_runtime/production_processes.py`
- `tests/e2e_runtime/test_export_process_mysql.py`
- `tests/recording/test_exports.py`
- `tests/worker/export_support.py`
- `tests/worker/test_export_handlers.py`
- `tests/worker/test_export_inputs.py`
- `tests/worker/test_export_mysql.py`


Final same-reviewer documentation delta recheck: no unresolved P1/P2 or evidence
inconsistency. Reviewer verified the exact35-file manifests in both documents,
reviewed source fixes, unchanged HEAD/empty index, original Log byte prefix and
git diff --check. No reviewer file/test/DB mutation. P3 two test-strength items
and #47/CI/operational deferred boundaries remain as stated. Final state is
uncommitted and unstaged; no staging, commit, push, PR or Issue operation.

## 2026-10-30 — Issue #465 MP4 deployment toolchain

**IN_PROGRESS · Refs #465 · Related #460**

Implementation Notes: [exact 8.1 supply, support commands and acceptance](./issue465-mp4-toolchain.md).
Issue body/Owner comment and #467 were directly inspected. Starting branch is
`codex/issue465-mp4-ffprobe-81`; HEAD/local and remote develop were
`177505530cf6bc0f6575d846ae188a0868d4ae3e`, with clean worktree/empty index.

Before image edits, official 8.1 source tarball PGP signature was directly checked
and its SHA-256 pinned. Official n8.1 mirror commit and actual base/uv registry
digests were checked too. Debian package snapshot input is fixed. Both media
binaries are built together; runtime only copies tools and build-identity manifest,
installs runtime libraries and preflights exact release/hash/configuration before
API/worker exec. Strict Recording duration/coverage and #467 fixtures are unchanged.

Author RED: ordinary synthetic 30fps MP4 through public Recording APIs with Ubuntu
6.1.1-3ubuntu5 fails at output missing-tail validation. A preserved same-byte source
is used for pinned-image comparison. Preflight new tests RED14 then GREEN17;
Docker source-policy RED then focused deployment GREEN72. Windows supplementary
9.0.1 media helper passes MP4/AVI/MKV/MP4-chain AnalysisSource and IncidentClip;
focused deploy/workflow/Recording/worker run is **296 PASS, 1 existing real-pair
opt-in SKIP (85.35s)**. Boundary/Contract fixtures/Compose structure/diff checks
pass after correcting Windows console encoding. Actual Linux 8.1 image and Compose
acceptance/review results are pending and will be appended as separate evidence.

Actual private MP4 types were not available in known local source/data folders;
their acceptance and provider first-search completion are not claimed. No DB,
migration or inventory changes, so full mandatory MySQL was not rerun. Full
regression/MySQL strict gate remain post-push remote CI conditions. No staging,
commit/push/PR or external Issue edits; scratch/RAW/JUnit/downloads/private sources
are PR-excluded. Earlier log entries and their historical results are preserved.

Issue #465 author follow-up: final Linux 8.1 image build and same-byte synthetic
MP4 strict GREEN succeeded; the retained input digest is unchanged. Initial
source-build regression (missing drawtext/font libraries) was caught by #467
export tests, reproduced in image media helper, and fixed by explicit font-library
build/runtime inputs. Final helper passes MP4/AVI/MKV/MP4-chain AnalysisSource,
IncidentClip, report stamp and plate crop. Final pinned-image focused selection
is **311 PASS / 1 existing actual-pair opt-in SKIP, 26.14s**. Runtime dependency/
tool/cache audit and six actual container startup negative controls PASS.
Compose JSON omission handling had five direct RED→GREEN cases and preserves
explicit false source policy. Final Windows deployment/workflow checks are
**165 PASS, 17.84s**; supplementary Windows 9.0.1 helper PASS. Full Compose smoke
and fresh review conclusions are still pending at this entry. No original
failure or historical pending result has been rewritten as success.

Issue #465 resume audit: HEAD/branch and unstaged delivery were preserved; local
`origin/develop` independently moved to `1a784b9d1bad14197f8779387be8ef7e4618fa44`.
No rebase/merge/reset. Prior WSL temporary workspace/report/image were unavailable
on resume, so the interrupted Compose run's final result/cleanup is not claimed.
A current-source isolated no-cache Compose smoke was started again under Docker
29.9.2 / Compose v5.6.1 (Linux x86_64), persisting its report in ignored scratch.
A fresh read-only reviewer without inherited implementation conversation directly
passed 165 deploy/workflow checks (10.47s), boundary/Contract/source Compose/diff
checks. Final execution evidence remains pending at this entry.

Issue #465 final resumed author acceptance: isolated Docker29.9.2 / Compose5.6.1
smoke **exit0 / PASS / cleanup PASS**, all ten stages through no-cache build,
migration failure gate, normal migration/readiness, pinned MP4/AVI/MKV/chain and
export materialization, cross-container media, command/view, kill→STALE→attempt2,
secret/settings inspection and recreated DB/media persistence. Cleanup failures/
remaining arrays are empty; separate Docker queries found no project containers,
volumes, network or tagged image. Image tested before cleanup was
`sha256:66ee0bccda379f71bd2948e711d57c2b8a5ed265c8f9e6271d5c8f2722a98883`.

Fresh reviewer execution is distinct from author311/1-skip evidence: first fresh
reviewer directly passed narrow pinned Linux fallback/IncidentClip/#467 **58/58**
and original pinned helper/runtime/preflight. New fresh reviewer after interruption
directly passed Windows deploy/workflow165 plus media146 (**311PASS / 1 existing
actual-pair opt-in SKIP**), boundary/Contract/Compose/diff, and current no-cache
Linux image's media helper (four PASS groups,6.29s) plus preflight exit0. Mounted
helper hash matched checkout; original Log prefix/index integrity passed. Old
image unavailable attempt executed no test, and is not counted as success.
No actionable P1/P2/P3 code findings; final documentation consistency recheck
is requested on the same resumed reviewer after these append-only entries.

Issue completion mapping, exact #460 commands/provenance, twelve-file manifest,
all original failures/pending entries and execution attribution are in
[Implementation Notes](./issue465-mp4-toolchain.md). Actual two-type private MP4,
Windows pinned8.1/non-amd64 Linux and provider first search remain unexecuted.
Full local regression/mandatory MySQL were not rerun; full regression/MySQL
strict gate remain post-push remote CI conditions. Owned source downloads,
checkout and transport archives removed; ignored RAW/reports/test temp/diagnostic
launchers and all scratch remain PR-excluded. No shared-resource prune/cache
export, staging, commit, push, PR or external Issue/Notion operation.

Issue #465 final same-reviewer documentation/report recheck: **P1/P2/P3 없음**.
Reviewer independently confirmed report ten-stage PASS/cleanup PASS with empty
failures/remaining, exact12-file manifest, original Log byte prefix, unchanged
HEAD and empty index. Full Compose run remains author evidence; reviewer-direct
current Linux helper/preflight and Windows165+146 results remain separately
labeled. No source fix or unresolved finding remains. **IN_PROGRESS · Refs #465 ·
Related #460**, actual-source and post-push remote CI boundaries remain unchanged.

Final cleanup follow-up: exact-path-verified owned Linux temporary workspace
removed after review; final `git diff --check` clean, HEAD unchanged/index empty.


## 2026-10-30 — IN_PROGRESS · Refs #468 · Related #460

기본 Worker production Readout 조립을 진행한다. 최초 HEAD/fetched origin/develop은 `b9c74d5e1f2b48c95254f6178e4ce9b9b5fb73b5`, 작업 트리/index 비어 있음. Issue/Owner 댓글 직접 확인, 기본 main 미등록 RED→GREEN 및 명시적 injection 유지. 운영 main은 recording_ocr_factory/PaddleOcrProvider를 조립하고 startup에 cache 검증·로드·예열을 완료한다. 일반 collection에 Paddle 설치는 요구하지 않는다. 정확한 dependency/cache/UID/실행 명령, 로컬 #468/#460 기록 초안과 실패 이력은 [Issue #468 Notes](./issue468-production-readout.md). 기존 로그를 덮어쓰지 않고 실제 acceptance/review 결과를 후속 append한다.


Issue #468 추가 검증: 실제 Paddle synthetic에서 발견한 sample/source 시각 float dust2건과 native signal ownership1건을 각각 RED→GREEN으로 수정했다. Recording strict 기준은 유지했다. 작성자 최종 일반 focused664PASS/338 MySQL deselected (66.04s, 기존 deprecation warning1), 별도 scoped MySQL55PASS/skip0/error0 (476.91s), image OCR plate/overlay PASS/network attempt0/model hash 불변/UID10001. 중간 image에서 source를 mount한 실제 기본 Worker+별도 API/MySQL T1/T2 및 SIGTERM exit0 PASS. source mount 없는 최종 image 재실행은 후속 append한다. fresh read-only reviewer P1/P2/P3 없음, reviewer 직접 focused52PASS/23.59s 및 Paddle 없는 import/diff PASS. Docker/OCR/MySQL 작성자 결과와 reviewer 직접 결과를 구분한다. 정확한 파일20개와 실패 이력/명령은 Issue468 Notes에 있다.


Issue #468 최종 로컬 acceptance: source mount 없는 image `sha256:51c214dba2d1fee50c1092e68c6f09e74e2cc1759a30ded0275c551314c5c0de`에서 실제 기본 Worker/별도 API/실제 Paddle의 PLATE_READ·OVERLAY_TIME_READ T1/T2 및 SIGTERM exit0 PASS. standalone OCR/network none/socket 시도0/cache 불변 PASS. CI Nanum timestamp 공백 손실로 UNKNOWN인 초기 FAIL을 보존하고, 기존 DejaVu 숫자 font로 synthetic 입력만 수정하여 최종 PASS했다. 모델/기준/parser 완화 없음. 같은 fresh reviewer도 최종 image preflight2건과 실제 offline OCR 직접 PASS, P1/P2/P3 없음. reviewer52/작성자664·55 및 process 증거는 Notes에서 분리해 기록했다. DB audit 잔여0 뒤 전용 container/volume/network/images 부재 검사 PASS, task-owned 비공유 cache ID별 정리, task pytest/env/media와 임시 font 삭제. RAW/JSON/JUnit/scratch PR 제외. DB/migration/inventory 불변, 전체 local pytest/mandatory MySQL 미실행, post-push remote CI gate 유지. commit/staging/push/PR/외부 Issue 변경 없음. IN_PROGRESS · Refs #468 · Related #460.


최종 cache 정리 후속 확인: 첫24개 ID만 선택한 검사에서는 preflight/permission 하위 참조가 남아 부재 assertion이 실패했다. 이 작업에서 생성된 비공유 root11개를 추가로 식별하고 child→parent 순서로 정확한35개 ID를 정리한 뒤 잔여0을 확인했다. 공유/이전 cache를 범용 prune하지 않았다. 이 검사는 container/volume/network/image 부재와 별도의 build cache 정리 검증이다.


## 2026-10-30 — IN_PROGRESS · Refs #460 · Related #429, #450, #452, #465, #468

Runtime/Ops·Recording 실행환경을 [canonical guide](./local-runtime-environment.md)로 정리했다.
최초 branch는 `codex/issue460-runtime-environment`, HEAD는
`d66fab9c47b84d6391232c866a7e73c5ac6b8f6b`; working tree/index는 비어 있었다.
`git fetch origin develop` 후 최신 origin/develop과 동일, ahead/behind 0/0,
변경 파일 차이 없음. 기존 파일/HEAD/index를 reset/rebase/merge하지 않았다.

Issue #460/#429/#450/#452/#465/#468 본문과 전체 댓글을 GitHub 읽기 전용 도구로 확인했다.
현재 `.env.example`/Compose/Docker/runtime adapter/Worker bootstrap·main·composition/
Readout runtime/Recording factory/Runtime config/Search 결정·config/배포·Readout·media·cleanup
Notes를 대조했다. 과거 댓글의 기본 Worker Readout 미등록 및 Analysis 그룹 누락 시 동작을
현재 코드와 구분했다. 기본 main의 production Paddle 자동 조립, 정확한 dependency/model/cache/
offline preflight, Worker의 GEMINI_API_KEY 필수와 Search 공용 ELICE alias 차이를 기록했다.

변경 파일 전체(6개): `.env.example`, `README.md`, `docs/runtime/README.md`,
`docs/runtime/rt13a-docker-compose.md`, `docs/runtime/local-runtime-environment.md`,
`docs/runtime/runtime-implementation-log.md`. RT-13(a) Notes에 현재 guide pointer를 추가하고
당시 기록은 유지했다. Log는 원본 bytes prefix를 보존하여 append한다.

확정 근거: #465의 동일 build 정확히 8.1, #468 Owner의 Paddle3.7.0/3.3.1/OpenCV4.10.0.84와
두 사전학습 모델, Search Owner의 Coarse/Fine argon·Intent Flash 분리. Runtime 수치는
코드 기본값 및 Baseline의 잠정 정책으로 구분했다. Recording encoding/profile ref·filename
offset 팀 대표값, 저장 bytes/지원 길이는 미확정이다. #460의 임시480/240·veryfast·23,
#452의 64MiB/285.2초/분 수 추정을 운영 권장값·지원 보장으로 승격하지 않았다.
#452의 DB 한 행 유지·측정 기반 사전/누적 거부 합의와 미구현 env/mapping/notice를 구분했다.

8종 등록 전용 startup log/health 기능은 현재 없다. 기존 조립+내부 registry snapshot을 읽는
별도 진단 절차와 기존 테스트를 문서화하고 #450 RD-12h 후속으로 남겼다. 실행 중 Worker
메모리 관측이라고 표현하지 않는다. 제품 동작/기본값/taxonomy/DB/Contract 변경 없음.

작성자 직접 최소 검증:

- 실제 load_env_file·API/Worker RuntimeConfig·RecordingSettings·Worker bootstrap 수용,
  빈 필수/부분 그룹 거부, shell credential 비병합, Search/Intent 모델·base URL 쌍,
  전체 Runtime/Recording 키 및 문서/예시/로컬 링크 정합성 PASS.
- 문서의 8종 진단 Python block을 그대로 실행하되 OCR load 경계만 대체하여 8종 snapshot 확인 PASS.
  실제 Paddle/DB/provider 실행 증거로 집계하지 않는다.
- boundary 0위반, Contract structure62/JSON26/semantic104 모두 PASS, Compose source 및
  실제 CLI resolved JSON의 구조 검사 PASS, `git diff --check` PASS.
- host Python3.13.0의 기존 최소 회귀 첫 실행: 95PASS/1FAIL(23.85초).
  `test_default_main_registers_both_readouts`의 plate 경로 실패를 보존했다.
  호스트 cv2 미설치 확인 후 작업 전용 ignored 의존성만 보완하여 대조한다.

이 Python3.13 host 검사는 Docker의 locked Python3.12 환경 acceptance를 대신하지 않는다.
실제 runtime secret/개인 env를 읽거나 기록하지 않았고 합성 설정만 썼다.
전체 pytest/전체 MySQL/clean Docker build/기존 smoke를 반복하지 않는다. 기존 Docker inventory만
읽었으며 application image tag는 없었다. 기존 image/build cache를 변경하거나 prune하지 않는다.
실제 #465/#468 과거 실행은 guide의 별도 Notes 근거이고 이번 실행 수치가 아니다.

fresh reviewer 결과·후속 대조·최종 정리는 이후 append한다. 작업 계획·검증 runner·합성 env/
resolved JSON·JUnit·로컬 의존성은 ignored `.codex-scratch/issue460/`로 PR 제외다.
commit/staging/push/PR/Issue 댓글/Notion 변경은 하지 않는다. #460 게시용 요약은
guide의 지원 범위·설정 경계·미결 및 이 Log의 검증 결과로 제공한다.


Issue #460 작성자 후속 검증: 최초 Readout 실패 환경은 numpy2.1.3/cv2 미설치였다.
프로젝트 지정 opencv-contrib-python4.10.0.84를 ignored task 폴더에만 보완 후 같은
실패 node 1PASS(2.05초), 동일 최소 4파일 선택 96PASS(22.83초)/skip0/error0을 확인했다.
초기95PASS/1FAIL을 소급 변경하지 않는다. 문서 parser 체크는 Python3.13.0의 보조 검증이고
locked Docker3.12 acceptance가 아니다. API --help 보조 probe는 호스트의 기존 Starlette에
body_limit 모듈이 없어 import 실패했으며, lock의 API 패키지를 task 폴더에 보완해 대조한다.
uv run --help의 --no-sync 존재는 직접 확인했다.

Issue #460 API CLI 후속: lock의 fastapi0.143.0/starlette1.8.0/uvicorn0.54.0/
python-multipart0.0.32를 ignored task 폴더에만 보완한 뒤 API --help exit0으로
--revision/--host/--port를 직접 확인했다. parser/키/진단/링크 체크 재실행 PASS.
README 상단의 오래된 2026-10-18 후속 작업 설명도 현재 canonical guide로 연결했다.

Issue #460 fresh read-only reviewer 최초 지적 P3 1건: DAESINGO_ENV_FILE의
API/Worker cwd/.env fallback과 migrate adapter의 명시 필수 경계를 표에서 구분하지 않았다.
명령 예시는 이미 export하고 있었지만 표의 필요 여부를 현재 코드대로 수정했다.
구현 이력을 상속하지 않은 같은 reviewer에게 수정 및 최종 기록 재확인을 요청한다.

Issue #460 수정 후 검증: migrate selector 미지정 시 exit1인 경계 직접 확인,
parser/필수키/8종 진단(실제 OCR 대체)/링크 재검사 PASS. 최종 focused JUnit을 읽어
96 tests, failure0/error0/skip0 대조했다. boundary/Contract62·26·104/source Compose/diff
재검사 PASS. 실 credential/provider/DB/OCR이나 전체 suite/build 성공으로 확대하지 않는다.
reviewer는 초기 독립 검사에서 전체 Runtime/Recording 키·기본값·모델쌍·링크·
Log prefix·Compose 구조·diff와 migrate selector 실패를 직접 확인했고 P1/P2는 없었다.

Issue #460 검증 표현 정정: 앞의 OCR load 경계만 대체라는 문구는 정확히
production_readout_factory 경계 전체를 대역(object 반환)으로 바꾼 등록 확인이다.
진단 block의 bootstrap/config와 나머지 registry 조립은 실제지만 production factory 내부의
Recording OCR factory 연결·cache·모델 load/예열은 이 문서용 runner에서 실행하지 않았다.
실제 Paddle acceptance는 별도 #468 과거 Notes 근거로만 제시한다.
Native 예시의 uv sync에는 --python 3.12를 명시해 Docker 기준 Python 계열을 선택했다.
--python/--no-sync 옵션 존재는 uv help로 대조했고 sync 자체는 실행하지 않았다.

Issue #460 동일 fresh reviewer 최종 재확인: 남은 P1/P2/P3 지적 없음.
selector P3 수정, production factory 전체 대역 검증이라는 표현 정정, native Python3.12
명시를 확인했다. reviewer가 원본 Log 741,713bytes SHA-256 prefix, 동일96개 JUnit의
failure/error/skip0, 문서 링크, source/저장된 resolved Compose 구조, diff, branch/HEAD/
빈 index 및 변경6파일을 읽기 전용으로 재검토했다. 실제 OCR/DB/provider 또는 전체
suite/build를 reviewer가 이번에 실행했다고 표현하지 않는다.

작업 자원 정리: 경로를 workspace 아래 task root로 resolve 검증하고 task-local
python-deps와 pytest/final-pytest 디렉터리를 삭제·부재 확인했다. countercheck/config
임시 디렉터리도 남지 않았다. JUnit/검증 runner/계획/합성 resolved JSON과 검증 메모만
ignored scratch에 보존하며 모두 PR 제외다. Docker container/volume/network/image를
이번 문서 작업에서 생성하지 않았고 build/cache/export/prune을 수행하지 않았다.
실제 secret·개인 env·media·DB dump·모델을 새로 보관하지 않았다.

#460 게시용 요약: canonical guide와 .env.example로 실제 키·필수 그룹·secret/file
소비 경계·DB/migration/실행 순서·media/temp/cleanup·고정 media/OCR toolchain·Search와
Intent 분리·8종 구성 진단을 연결했다. encoding 및 용량/길이 대표값은 Owner 측정 후
확정할 미결로 유지하며 #450 운영 관측/배포와 #452 용량/시간 후속을 분리했다.
최소 parser/정합성 및96개 회귀 PASS, 최초 호스트 의존성 실패는 별도 이력으로 보존.
전체 pytest/MySQL/clean Docker build/native OCR/실 credential E2E는 미실행이다.

6파일을 미커밋·미스테이징 상태로 남긴다. HEAD는 시작과 같고 원본 Log bytes prefix를
유지한다. commit/push/PR/Issue 댓글/Notion 수정은 하지 않았다.

## 2026-10-30 — RT-14 deployment preparation (Refs #450)

**IN_PROGRESS · Refs #450 · Related #287, #460, #452**.
기존 기록을 대체하지 않는 후속 entry다. 상세는 [RT-14 runbook / Implementation Notes](rt14-deployment.md).

시작 branch `codex/rt14-deployment`, HEAD/fetched origin/develop
`4876e646171ba9f0195de52d11741f3c39fb51a0`; working tree/index clean.
Issue #450 본문/전체 댓글, #460/#452 현재 댓글, PR #473–#477 merged 상태를
읽기 전용으로 확인했다. 첨부4자료는 환경 입력으로 읽고 명령 실행 승인과 구분했다.
AWS 실계정/role 연결/SSM/agent/registry는 조회하지 않았다.

준비 구현: develop 제한 manual OIDC 인증, amd64 CI image/ECR immutable digest 후보,
query-only SSM 결과 판정, root host controller, versioned protected config,
명시적 단일 migration과 dirty journal, 실제 Worker PID/starttime/8종 등록,
live/ready/read-only Case smoke, atomic known-good과 schema-compatible code rollback.
DB/media 삭제·downgrade·자동 restore는 없다. 결정 refs/retention/restart/용량 budget과
#452 운영 profile/byte/length가 비었으면 운영 준비 완료로 처리하지 않는다. RD-12/13/11은 OPEN 유지.

이번 직접 검증: focused **228 PASS** (Windows Python3.12.14, 41.45초).
source/resolved local/production Compose, boundary, Contract62/26/104, actionlint,
workflow bash 구문, diff, 첨부 식별 후보 비노출 검사 PASS.
독립 subprocess lock 경쟁 거부/해제 후 실행 PASS. 기존 Linux image + read-only source에서
production OCR 초기화/실제 registry8/PID1 marker/cleanup PASS지만 claim loop는 대역이다.
DB/provider/AWS/서비스 deployment 증거가 아니다. 최초 helper pytest 누락 실패와
runtime adapter patch 위치 실패는 수정 후 결과와 구분해 Notes에 보존했다.

fresh read-only reviewer는 구현 이력을 상속하지 않고 schema compatibility 덮어쓰기와
최초 populated-volume 인수 P1을 지적했다. 모두 RED→GREEN으로 수정하고 같은 reviewer가 재확인했다.
최종 credential 격리/region/Worker cleanup delta를 포함해 독립 focused **228 PASS**
(29.99초), 잔여 actionable finding 없음. schema.json 권위와 schema_parent는 code rollback으로
되돌리지 않으며 최초 승인+실제 empty-volume 검사를 요구한다.

새 PR remote CI/새 Dockerfile full build/OIDC/ECR/실EC2 SSM/config/migration/log 수신/
4GB 동시 용량/rollback/DB+media restore는 pending이다. 전체 local pytest/전체 mandatory MySQL은
반복하지 않았다. #452 운영값·22개 원본 측정과 Case notice, #445 orphan, #71 retention을
이 Task에서 완료로 바꾸지 않는다. 전체26파일 manifest와 실행 입력/제공자/복구 경계는 Notes에 있다.
전용 offline container 부재, structure volume/network0, 기존 image4개 보존·shared prune0.
임시 pytest/render/helper는 task 범위로 정리하고 작은 실패 log/최종 요약만 ignored scratch에 보존한다.
commit/staging/push/PR/외부 댓글/Notion/dispatch/AWS 변경·실제 deployment 없이 종료한다.


## 2026-10-30 — RT-15(c) secret scan 로컬 구현

**Status: IN_PROGRESS · Refs #301 · Related #287 · PR/merge SHA pending**

시작 branch `codex/rt15c-secret-scan`, HEAD `6b116e4a1317dc8e5c13e34b05481107bc00ca21`,
working tree/index clean. 최신 `git fetch --no-tags origin develop` 뒤 ahead/behind0/0,
nonshallow HEAD ancestry1,519개였다. PR #483/#484 merged와 merge SHA를 GitHub에서 확인했다.
Issue #301 본문과 댓글 전체(0개)를 읽었다. 위 (a)/(b)의 당시 pending 기록은 역사로 보존하며
최신 색인만 #484 merge로 갱신한다. 상세/전체 파일 manifest는 [RT-15(c) Notes](./rt15c-secret-scan.md).

- **구현 결과:** 공식 Gitleaks8.30.1 archive/실행 파일/rules SHA-256을 고정한다. 현재 Git 관리
  파일과 nonignored 새 파일은 사본 없는 hardlink view로, Git 이력은 전체 HEAD ancestry로
  검사한다. root/side/merge-resolution을 포함하고 shallow/partial/graft는 실패한다.
  비밀값/경로/주변 코드/URL을 출력하지 않고 verified rule ID/건수만 공유한다. custom report
  projection과 capture로 원본 보고서를 생성하지 않는다. suppression/baseline/추가 allowlist0.
- **Plan 대비 변경:** Plan이 위임한 도구/배치 선택이다. 일반 PR 편입은 보류하고 별도 develop
  수동/재사용 workflow 및 RT-14 publish/remote 선행 dependency로 배치했다. 기존 quality/
  regression/mysql/test와 boundary/Contract 실행 의미를 유지한다. 운영진 3workflow/CODEOWNERS
  변경은 없다. app/DB/도메인 코드를 바꾸지 않는다.
- **새 implementation detail:** install만 공식 GitHub download를 허용하며 scan은 offline이다.
  tool hash 재검사, ignore/env/config bypass 차단, --text로 Git -diff 속성 누락 방지,
  child error 진단/누락 보고서/exit 불일치도 fail closed. wrapper exit0 clean/1 findings/2 error.
  Linux/Windows x64, Python>=3.12. scanner 권한은 contents:read만, PR/fork context는 checkout 전
  거부하고 OIDC/secrets는 전달하지 않는다. 전체 fetch의 cold 비용은 원격 CI pending이다.
- **Contract / Decision / Baseline 영향:** 모두 없음. Runtime/Ops Owner 김준영 deferred review:
  탐지 비공개 분류와 향후 일반 PR gate 재검토. 전역 privacy/security review를 대체하지 않는다.
- **실측:** initial snapshot2,314파일 generic-api-key2occurrences/12.98초, HEAD history1,519commits
  generic-api-key24occurrences/69.38초. 두 범위 중복을 고유 credential 수로 합산하지 않는다.
  실제 credential 여부/오탐률은 원문을 열어 분류하지 않아 확인할 수 없다. 승인 예외로 숨기지
  않는다. 현재 pre-deploy gate는 탐지로 실패한다. 담당자의 비공개 분류와 실제 credential이면
  소유자의 폐기/회전 판단이 필요하다. 이 작업은 사용/검증/회전/이력 변경을 하지 않는다.
- **작성자 검증:** test-first script부재 RED와 clone setup오류를 구분했다. hardlink sandbox차단도
  성공 처리하지 않았고 sandbox 밖 합성 검증에서 정상 동작을 확인했다. 실제 binary 합성14controls
  PASS(41.910초): 검출→제거GREEN, safe EXAMPLE, tracked ignored/untracked, text media 확장자,
  root삭제/side/merge-only/-diff이력, shallow/partial 거부, 무결성/도구오류, child stdout/stderr와
  보고서/민감 파일명 sentinel 비노출. -diff 누락 RED→--text GREEN이며 Windows CRLF 테스트 보정도
  기록했다. offline unit12PASS, quality/CI/deploy 경계 포함 focused94PASS(23.80초).
- **미완료:** 최종 boundary/Contract/quality/actionlint/diff 결과와 fresh read-only review는 Notes의
  최종 기록으로 보완한다. 이번 diff의 원격 CI·배포 성공은 확인하지 않았다. 전체 local pytest/
  MySQL/Docker build는 반복하지 않는다. #301 전체는 IN_PROGRESS이며 Issue를 닫지 않는다.

새 worktree/checkout 전환/staging/commit/push/PR/외부 댓글/merge/AWS/provider/배포/
RT14_EXECUTION_ENABLED 변경을 수행하지 않았다. 소유 임시 자원만 정리하고 scratch/RAW/
credential/원본 보고서는 PR 대상에서 제외한다.


### RT-15(c) 후속 검증·fresh review delta

작성자 boundary CLI/Contract 구조62·JSON26·의미104 PASS, import fixture258PASS(88.58초),
Runtime Ruff PASS·mypy Linux/win32 각각87파일 오류0, actionlint1.7.12 변경2workflow PASS,
새 script/test Ruff와 diff check PASS. 최초 boundary 출력은 Windows cp949 em dash 오류였고
UTF-8 환경으로 재실행해 PASS였다. --text/--no-renames 이후 history도1,519commits/
generic-api-key24occurrences/76.41초/exit1로 동일했다. 실제 탐지 분류는 여전히 미완료다.

Fresh read-only reviewer는 unit12PASS와 당시 합성14controls PASS를 직접 실행했다.
local Git log.showSignature/gpg.program이 외부 verifier를 실행하는 P2를 재현해 지적했다.
작성자 marker control RED 후 --no-show-signature로 차단했다. 별도 배포 ancestry 경합도
--require-ancestor + reusable require_target/target_revision input으로 검사 HEAD에 결박했다.
빈/잘못된/미포함 target은 실패한다. 해당 control RED→GREEN1PASS(8.138초) 확인.
Windows/Linux 공식 검증 archive를 응답 대역으로 공급한 실제 installer extraction/hash 재확인도
두 플랫폼 PASS이며 Linux 프로세스 실행/원격 CI 성공 증거와 구분한다.
최종16controls·동일 reviewer delta·임시 자원 정리는 Notes 최종 기록으로 이어서 보완한다.


### RT-15(c) 최종 로컬 검증

작성자 실제 고정 바이너리 최종 합성16controls PASS(59.792초), wrapper unit12PASS(0.59초),
fresh reviewer 직접 기존14controls PASS(65.989초)와 추가2delta PASS(7.345초)를 확인했다.
후자 둘은 별도 실행이며 한 번의 전체16 실행으로 합산하지 않는다. 동일 reviewer의 delta
검토에서 서명 verifier P2 해결·남은 코드/보안 지적 없음. 문서 완료 표기의 로컬 pending
불일치도 수정했다. 최종 snapshot2,315파일/generic-api-key2occurrences/8.47초/exit1.
마지막 전체 history76.41초 기록은 --no-show-signature 추가 전이며 그 flag의 비실행 보장은
합성/reviewer 직접 증거다. 실제 탐지 분류/해결과 Linux 원격 CI는 여전히 미완료다.
#301 전체 IN_PROGRESS 유지, 선행 (a)/(b) 병합/원격 성공과 이번 (c) 로컬 결과를 구분한다.


동일 reviewer 최종 문서 delta도 추가 지적 없음(문서 검토만 수행).
작성자 소유 .codex-scratch/rt15c의 tool/archive/합성 저장소와 실패한 sandbox TEMP 한 경로를
절대 경로 검증 후 정리했다. reviewer 소유 scratch도 reviewer가 정리했다. scanner view잔존0.
다른 작업 scratch/기존 변경은 보존했다. 최종9파일은 미커밋/미스테이징이며 index 비어 있음.
로컬 구현 검증 완료와 미분류 탐지/원격 CI pending을 구분하고 RT-15 전체 IN_PROGRESS를 유지한다.


## 2026-10-31 — RT-15(c) A01/A02 최소 예외·비노출 절차 보강

**IN_PROGRESS · Refs #301 · Related #287 · 미커밋/미스테이징 · 원격 CI pending**

이전 분류 요청의 원문/주변 코드/경로 누출은 임시 조사 helper의 성공 JSON dump에서
발생했다. 제품 counts-only 실행기의 원본 출력 사고가 아니다. 실행 후 파일 변경이 진행 중인
프로세스에도 적용된 것으로 잘못 간주한 채 진단 출력을 읽었고 성공 경로의 출력 schema
검증이 빠졌다. 확인된 탐지 항목이 정상 코드와 합성 fixture였다는 판단과 비노출 절차가
위반됐다는 사실을 구분한다. 원문을 재인용하거나 이미 발생한 출력을 지웠다고 주장하지 않는다.
자세한 원인·출력 경로·차단·검증은 [RT-15(c) Notes 후속 절](./rt15c-secret-scan.md)에 있다.

- A01(current1/history11)은 정상 계측식, A02(current1/history13)는 명시적 합성 privacy fixture.
  두 정확한 rule/위치SHA/도구좌표/값SHA/전체patternSHA만 template 내부에서 허용한다.
  원문·실제 위치는 예외 파일/문서/보고서에 쓰지 않는다. 전체 rule/path/history 제외나 baseline은 없다.
- 새 파일 scripts/secret_scan_exceptions.json은 hash-only 지문2개다. 스캔 자체는 모든 Git 대상과
  전체 HEAD ancestry를 유지한다. raw값은 scanner 메모리에서 비교하고 stdout은 V2 marker,
  rule ID/익명 예외 ID/건수만 반환한다. 누락·손상·미지 ID·exit/report 불일치·도구오류는 실패한다.
- 오류 경계: CLI 인자/ScanError 공개코드 제한, child stdout/stderr/보고서 오류 원문 차단,
  controls 테스트/framework/setup 모두 캡처. 성공도 숫자 요약만 허용하고 빈 suite/skip/
  expected-failure/Python -O는 필수 실행 성공으로 바꾸지 않는다. 제품 잠재 오류 경로 보강을
  실제 조사용 helper 사고의 원인과 혼동하지 않는다.
- 예외 비활성화 통제: current2/history24, exit1,77.84초. 적용 후 current0/예외2,
  history1,519commits0/예외24, exit0,77.09초. A0112/A0214는 발생횟수이며 고유credential 수가 아니다.
  실제 위치 복제 1method/2subtest PASS13.228초: 같은 위치·길이의 새 generic credential은
  두 항목 모두 current/history에서 exit1이며 rule 전체 무력화가 아님을 확인했다.
- RED: 신규7FAIL/13PASS → controls 인자·최적화2FAIL/20PASS → reviewer setup2FAIL/22PASS →
  부적합 성공 payload1FAIL/24PASS → 빈 suite/skip/xfail3FAIL/25PASS. 모두 합성 입력이다.
  최종 단위28PASS3.77초, 관련 focused107PASS44.22초(추가 필수 실행3분기는 최종28에서 재검증).
- 같은 fresh reviewer는 원문/실제 탐지 경로를 보지 않고 합성 경로·값·지문으로 exact/mutation/
  CRLF/출력 비노출/이력 실패 전파를 직접 확인했다. 발견한 P2 두 건은 수정 후 단위28PASS3.66초와
  코드 delta로 재확인했고 남은 기능·보안 지적 없음. actual 분류/재스캔은 작성자 증거로 구분한다.

Contract/Accepted Decision/Baseline 의미·제품 앱/DB·운영진 workflow/CODEOWNERS 변경 없음.
기존 quality/regression/mysql/test와 배포 needs 의미를 보존한다. 일반 PR 편입 보류는 유지하며
배포 전 필수 검사는 새 finding/오류/실패/취소/skip을 통과시키지 않는다. 원격 Linux CI와
#301 전체 완료는 아직 미확인이다. 최종 gate/검사/정리 결과는 이어지는 마감 기록을 따른다.


### RT-15(c) 예외/비노출 보강 마감 검증

최종 합성17controls PASS(실패/오류0), 단위29PASS1.75초(현재 예외-only 후 history 오류 전파
추가 회귀 포함). 관련 focused107과 중복 합산하지 않는다. boundary/Contract62·26·104 PASS,
import258PASS96.70초, Runtime Ruff PASS·mypy Linux/win32 각각87파일 오류0, 새 scripts/test Ruff,
actionlint1.7.12 변경2workflow exit0. 원래 shell두분기6경우의 exit0/1/2 전파와 needs의
failure/cancel/skip 차단을 확인했고 실제 deployment/AWS/provider 호출은 없다.
같은 reviewer는 단위28PASS3.66초 + 추가 orchestration1PASS0.31초를 별도 직접 실행했고
코드/문서 delta 잔여 지적 없음. actual 분류/스캔과 reviewer 합성 검증의 구분을 유지한다.
소유 scratch/tool/hash-only 준비 metadata/helper는 PR에서 제외하고 검증 후 정리한다.
전체10파일(이번보완8 + 기존workflow2 유지)은 미커밋/미스테이징 상태로 남긴다.


마감 후 current2,316files 재검사0finding/예외2/exit0(8.47초), 전체 history는 기존
1,519commits0finding/예외24/exit0(77.09초) 기록 유지. 소유 rt15c-exceptions tool/helper/
hash-only metadata·임시 자원 정리, root scanner view0, 다른 scratch 보존. 최종10파일 공백/
diff PASS, index 비어 있음, branch/HEAD 동일. 이번 요청도 미커밋/미스테이징이며 remote CI/
실제 배포 완료로 해석하지 않는다. #301은 IN_PROGRESS, Issue close/외부 게시 없음.

## 2026-10-31 — #486 §8 sequential multi-source IncidentClip P0

**IN_PROGRESS · Refs #486 §8 · Related #458/#297/#425 · PR/merge SHA pending.**
[Implementation Notes 및 멘토 inline 답변 초안](multisource-incident-clip.md).
시작 시 요청 브랜치 `codex/multisource-incident-clip`/HEAD/origin-develop
`3ec753ef05b110f7765db018d48f4390a9c4dcb9`, divergence0/0, worktree/index clean.
기존 checkout을 사용했고 worktree/checkout 전환은 하지 않았다.

실제 Recording/FFmpeg 제품 경계 RED 3건 보존 후 최소 adapter 수정:
Case의 원본별 명시 VIDEO 선택을 짧은 입력 transaction에서 detached tuple로 읽고,
기존 Recording 복수-ref resolve_span에 전달한다. 사건이 B에만 있어도 전체 timeline
선택으로 해소하며, 실제 사용 span이 Fine VIDEO provenance에 포함되는지 확인한다.
소유권은 모든 선택 source에 공개 capability로 검증한다. Runtime은 Recording 내부
schema/repository나 placement 계산을 읽거나 복제하지 않는다. 단일 경로, 명시 camera,
모호성 안전 거부, checkpoint/context close, 기존 build-only terminal taxonomy와
produced/T1/T2/Readout 후속 의미를 유지한다. Contract/Decision/Baseline 변경 없음.

직접 실행: Windows 초기63/확장71/PTS·timebase14/cancel2 PASS(서로 중복 합산 금지).
Linux Python3.12.16/FFmpeg·ffprobe8.1 기존 image 재사용(재빌드 없음): focused463PASS,
실제 사용자 원본 미지정4skip, 운영 image의 quality tool 부재3실패를 보존했다.
Windows quality tests19PASS, Runtime Ruff PASS·mypy Linux/win32 각각87파일 오류0.
Boundary0위반/Contract62·26·104PASS. 최종 실제 MySQL8.4.13/process17PASS145.16초,
skip/xfail0: 단일/chain의 T1 rollback·COMMIT 불명 receipt 복구·T2 rollback/redelivery,
pre-T1 주입 crash 후 새 attempt, 독립 API/Worker OS process 단일/chain 포함.
정상chain build1/encode2; receipt/T2 추가0. pre-T1 새 attempt는 총build2/encode4,
이후T2 추가0. provider는 offline Coarse1/Fine1/clip0, media 경계 Runtime checkout0,
동일clip ref의 PLATE_READ/OVERLAY_TIME_READ 발주2건을 검증했다.
기존 generic Runtime OS kill2건은 별도 실행 증거이며 clip의 SystemExit 주입과 구분한다.

초기 mixed AVI/MP4의 1/10 대 1/10240은 #425 기존 UNSUPPORTED_MEDIA를 직접 재현했다.
성공fixture는 명시적 동일1/10으로 생성했으며 검증식을 완화하지 않았다. 실제 서로
다른timebase 입력의 안전 거부도 회귀로 보존했다. 이후 계측/Coarse playback좌표
fixture 오류와 수정 이력은 excluded scratch에 남겼다.
이력을 상속하지 않은 read-only reviewer: 초기58+13 직접PASS, delta16 직접PASS,
최종17 MySQL text/XML/JSON은 열람만 수행. P0/P1/P2/P3 지적 없음.
취소검증은 FFmpeg active interruption이 아닌 기존 후속checkpoint 취소/cleanup이다.

최종 전체 회귀·원격CI는 향후push/PR 조건으로 남긴다. 실제 사용자 영상/명시 배치
미제공으로 해당E2E는 미실행이며 합성AVI/MP4 증거와 구분한다. #425 시간축 구현,
#470 preview, #486 §9 사건시각, GPS/새camera정책/운영profile/AWS/provider/배포는 제외.
RT14_EXECUTION_ENABLED는 GitHub API read 결과false, 수정 없음. PM Runtime acceptance
미완료, 12파일 미커밋/미스테이징. 소유DB/container/volume/temp만 정리하고 실패원본·
최소요약은 PR제외scratch에 보존한다. 공유cache/image/다른작업자료는 보존한다.

마감 추가: Linux quality 도구 부재3건은 uv.lock SHA-256 일치wheel7개를 소유scratch에만
오프라인 설치하여 동일quality테스트19PASS30.96초로 해소했다. 기존image 재빌드/변경은
없다. 실패로그는 삭제하지 않고 성공run과 구분한다.

정리 확인: 이번 소유 MySQL/container/anonymous volume/network, 성공media/temp,
qualitywheel/임시설치본, reviewer 소유temp2개 삭제 완료. 공유image/cache 및 타작업자료
보존. Linux pytest symlink에서 Windows정리가 안전중단되어 동일image 내부에서 경로/
linktarget 검증 후 소유root만 정리했다. PR제외scratch에는 실패원본5개(31,302bytes)와
로그/JSON/XML/최소runner·요약만 남았다. 최종12파일/indexempty/branch·HEAD동일.
# 2026-10-31 — RT-14 approved public deployment follow-up

**IN_PROGRESS · Refs #450 · Related #287, #460, #452, #486**

승인 설계 §13.6·§16.1에 맞춰 rollback tip CI 의존만 제거하고 대상 ancestry/push CI/digest,
host exact tuple/schema 및 secret-scan gate를 유지했다. 같은 production image의 Web
revision/manifest, host staging/pointer·phase journal, Caddy host 구성, 보호 DDNS updater,
post-SSM 및 독립 외부 smoke를 추가했다. 첫 deploy 실패·partial promotion은 operator가
데이터/상태를 대조하는 절차이며 자동 rollback/restore/volume 초기화는 없다.

상세 [구현·복구 Notes](rt14-public-deployment.md)에 승인 대응표·26파일 manifest·RED→GREEN·
작성자 직접 검증·fresh reviewer·실제 AWS acceptance 순서·hardening P0를 기록한다.
기존 로그와 #479 Notes는 이력을 보존한다. Gate/실행 변수 승인과 실제 배포 완료를 구분한다.

작성자 Linux 집중106 PASS, Windows focused136 PASS, 후속 guard58 PASS(중복 합산 없음),
실제 Web build·Docker 변경 artifact 경계·loopback Caddy TLS/route·quality·boundary·Contract·
actionlint·diff를 확인했다. 실제 public DNS/ACME·first/second deploy·rollback·DB restore는
미실행이다. full regression/mysql/test와 최종 production Docker acceptance는 push 후 CI 조건이다.

`GPT-6.1 Sol / high`, `fork_turns=none` fresh read-only reviewer가 승인/요구사항/diff를
검토하고 Windows65/Linux38 및 Caddy 검증을 직접 실행했다. product defect 지적 없음;
exact tuple 테스트가 reconciliation에서 먼저 막힌다는 보완 의견을 반영했다.
최종 delta와 환경 실패·추가 검증 상태는 위 Notes §8에 이어 기록한다.

GitHub Variable 한 개 읽기로 `RT14_EXECUTION_ENABLED=false` 확인, 변경 없음.
staging/commit/push/PR/외부 댓글/merge/dispatch/AWS 작업 없음. #450을 종료하지 않는다.


최종 추가 확인: Web 13 files/224 PASS, secret synthetic controls17 PASS 및
현재2331 files/HEAD1535 commits counts-only scan findings0(기존 예외만 적용) PASS.
처음 환경 실패 및 retry 한계는 Notes §8에 구분했다. 같은 fresh reviewer가 delta11 PASS를
직접 확인했고 잔여 product defect 지적 없음. Log EOF 공백 수정 후 diff PASS.
작업 전용 image2개만 제거했으며 공유 cache/base image·다른 scratch는 보존했다.
