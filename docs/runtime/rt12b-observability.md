# RT-12(b) 관측 집계 · event catalog

**IN_PROGRESS · Refs #299 (RT-12(b))** · PR/merge SHA 대기 중.

구현 기준은 사용자가 승인한 `42ddea72bb927e7adedf352ba53d160bda1aa049`다.
시작 시 branch는 `codex/rt12b-observability`, tracked/untracked/index 변경은 없었다.

## 구현 권위와 경계

원문은 Baseline v0.1 §6/§9, Runtime Plan RT-12, Ops §6/§7/§8/§14,
Runtime Tech Spec과 #370 durable timestamp 의미다.
[Runtime Owner 확정 답변](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/299#issuecomment-6367448332)을
구현 권위로 사용한다. 이번에 명시적으로 닫힌 구현 semantics는 다음과 같다.

- nearest-rank: 정렬된 N개 표본의 `ceil(p*N)`번째 실제 관측값, 보간 없음.
- 전역 분포는 항상 반환한다. 무표본이면 count=0, p50/p95/max=None이다.
- attempt 1/2+ 고정 group은 항상 반환한다. kind/status 동적 group은 무표본이면 생략한다.
- oldest는 `QUEUED AND available_at <= DB NOW(6)`만 대상으로,
  `max(GREATEST(TIMESTAMPDIFF(MICROSECOND, queued_at, NOW(6)),0))/1e6`이다.

이 규칙은 eval을 자동 상속한 것이 아니라 Owner가 내부 precedent를 근거로
채택한 구현 convention이다. Contract/Accepted Decision/Baseline 문구는 변경하지 않는다.

새 HTTP endpoint/CLI/dashboard, scheduler/정기 기록, retention/purge,
disk guard, CloudWatch, orphan publish/P-6, RT-10 handler는 추가하지 않는다.
기준 이후 병합된 API asset response/ASGI 관측 경로는 그대로 사용한다.

## DB query와 계산

`common/jobs/metrics.py:read_metrics(conn, retry_max=1)`은 caller transaction에서
단일 SELECT/CTE를 실행한다. DB NOW(6), 표본, window rank와 counter가 같은
statement snapshot에 속한다. begin/commit/rollback/SET/row lock/제품 행 변경이 없다.
caller는 MySQL READ ONLY transaction 또는 SELECT-only 권한 연결을 사용할 수 있다.
UTC 세션은 기존 engine factory의 책임이다. 시간 구간을 임의로 추가하지 않으며
보존된 Runtime 행 전체의 현재 snapshot을 반환한다.

| DB metric | 표본/계산 · grouping | 빈 값 |
| --- | --- | --- |
| runtime.queue.wait_ms | started_at이 있는 행의 `(started_at-queued_at)` ms. attempt=1/attempt>=2 분리, backoff 포함. p50/p95/max/count | 두 고정 group 유지, count=0/분포 None |
| runtime.queue.oldest_queued_age_s | 위 승인된 available_at 필터와 queued_at 기준 DB age의 max | None |
| runtime.execution.duration_ms | terminal SUCCEEDED/FAILED/STALE/CANCELLED 중 started_at/ended_at이 모두 있는 행의 causal 차이 ms. kind/status별 p50/p95/max/count. QUEUED 취소의 NULL started_at은 duration 표본 아님 | 동적 group 생략 |
| runtime.stale.count | status=STALE 행 수. RUNNING→STALE의 retained terminal facts | 0 |
| runtime.stale.detect_latency_s | STALE의 ended_at-heartbeat_at 초. NULL heartbeat 생략. #370 causal 값 0은 유효. p50/p95/max/count | count=0/분포 None |
| runtime.retry.auto_count | attempt>=2 행 수, 현재 QUEUED/RUNNING/terminal 모두 포함 | 0 |
| runtime.retry.exhausted_count | STALE AND attempt>retry_max AND cancel_requested_at IS NULL. observed sweep와 같은 retry_max를 전달, 기본 B-R1=1 | 0 |
| runtime.cancel.terminal_latency_ms | CANCELLED AND cancel_requested_at/ended_at not NULL, ended_at-cancel_requested_at ms. QUEUED 취소도 포함. p50/p95/max/count | count=0/분포 None |
| runtime.usage.recovered_count | 기존 tracker의 recovered_at IS NOT NULL 행 수 | 0 |
| runtime.usage.inflight_count | 기존 tracker state!=FINALIZED 행 수 | 0 |
| runtime.usage.inflight_oldest_age_s | 기존 `_metrics()`와 같은 min(pending occurred_at), DB NOW(6) 차이 초, 0 하한 | None |

timestamp 차이는 MySQL TIMESTAMPDIFF(MICROSECOND)로 계산한다. DB 원본은 수정하지
않는다. oldest와 기존 usage age 이외 duration에 새 clamp를 추가하지 않는다.
causal duration은 raw wall-clock/monotonic elapsed가 아니다. retry cap 변경 이력은
기존 schema에 없으므로 exhausted는 전달한 sweep policy 기준 snapshot이며,
서로 다른 과거 cap을 자동 복원하는 역사 분석 기능은 아니다.

## Event catalog와 실제 emitter 검증

`common/logging/catalog.py`는 metric→event 대응, 필수 필드, 허용 status,
producer와 의미를 명시한다. common structured formatter의 필드 allowlist는 유지한다.
API readiness는 기존 completion event를 사용하고, view는 실패도 포함하는 route
request/latency event를 추가한다. upload throughput은
trace_id로 대응하는 기존 bytes/duration 관측 쌍으로 표현한다. 새로운 transport나
rate field/기록 주기는 만들지 않는다. request 413은 완료 event status=413을
한 번 세며 route별 보조 count와 더하지 않는다.

누락 emitter는 false STALE, view request/latency, source 전용 upload 실패다.
view의 기존 success completion은 보존한다. upload 실패는 기존 error handler,
선언 body-limit 및 access 예외 경계에서 status만 emit하며 abort와 구분한다.
false STALE은 기존 terminal attempt가 0 rows이고
기존 locking re-read가 원래 lease_owner와 STALE을 확인한 경우, callback이
끝난 뒤 count=1을 emit한다. 다른 owner/terminal/QUEUED/missing은 제외한다.
ownership fence 때문에 시도 자체를 안 한 경우도 이 지표에 넣지 않는다.
로그가 Worker 생존 전체나 false STALE의 완전한 census를 보장하지 않는다.

`tests/observability_capture.py`는 nested MySQL acceptance에서 실제 formatter 출력을
검사한다. event 문자열 검색으로 producer 존재를 대체하지 않는다. 실제 출력의
필수 필드/타입/상태를 validate하고 catalog 전체 event coverage와 violation=0을
검증한다. 보존 자료는 event 이름/위반 건수뿐이며 private context 값은 저장하지 않는다.

<a id="privacy"></a>

## 개인정보 보호

번호판, GPS/상세 위치, 영상/frame bytes, 전체 path, 외부 AI request/response,
사용자 free text, API key/access token/secret, raw provider payload canary를
raw log message/args/exception/extra 및 실제 HTTP 입력으로 전달해 비노출을 검사한다.
허용하지 않는 structured field는 emit 전에 거부한다. token 모양 ID의 내용이
secret인지 판별하는 전역 masking 기능을 새로 주장하지 않는다. 호출자는 기존대로
신뢰한 식별자만 correlation에 넣어야 한다.

PR #390 cleanup의 empty Context 의미를 유지한다. 실제 cleanup emitter와
기존 lifecycle 회귀가 request/case/execution/private context 없는 count-only
schema를 검증한다. 원래 generic 로그/경로/raw payload는 출력하지 않는다.

## 검증 기록

검증 진행 중. RED·GREEN·실패 원본은 PR 제외 `.codex-scratch/rt12b-20261026/`에
서로 다른 파일로 보존한다. 실패/skip/중단은 이후 성공으로 소급 변경하지 않는다.

과거 증거: PR #390 merge SHA는 `1c876620d71f8c6f323a3e920139c0dc444a82c7`.
PR 본문에 기록된 원격 boundary PASS, pytest 10,794 passed/33 skipped,
MySQL execution gate 911 PASS(skip=0/xfail=0)는 RT-12(a)의 과거 결과다.
이번 실행 수치에 합산하지 않는다.

<a id="implementation-notes-초안"></a>

## 구현 기록 초안

IN_PROGRESS · Refs #299 (RT-12(b)). Runtime Owner comment 6367448332에 따라
read-only DB 집계의 percentile/empty/group/oldest 의미를 구체화했다.
기존 API 이벤트와 cleanup privacy 경계를 유지하며 catalog 실제 emit 검증과
strict MySQL inventory/mutation 검증을 추가한다. 새 정책·공개 surface는 없다.
직접 실행 결과와 reviewer 결과는 아래 후속 검증 기록에서 구분한다.

## PR 제외 자료

scratch 실행 계획/runner/MySQL binary·datadir/CA, RAW·JSON·JUnit, source hash,
mutation inventory와 독립 reviewer 자료는 PR 대상이 아니다. 자원 정리와
최종 검증·변경 파일 목록은 완료 시 여기에 기록한다.

## 전체 log metric 대응

| Metric | 실제 event | 의미 |
| --- | --- | --- |
| runtime.heartbeat.attempt_ms | runtime.heartbeat.attempt_ms | 매 attempt를 밀리초로 측정. 고정 상한 없음 |
| runtime.heartbeat.lag_ms | runtime.heartbeat.lag_ms | 성공 간격에서 cadence를 뺀 값, 밀리초 |
| runtime.heartbeat.skipped_tick_count | runtime.heartbeat.skipped_tick_count | status에 음이 아닌 정수로 기록. 기존 schema 유지 |
| runtime.heartbeat.consecutive_failures | runtime.heartbeat.consecutive_failures | status에 음이 아닌 정수로 기록. 기존 schema 유지 |
| runtime.stale.detect_latency_s | runtime.stale.detect_latency_s | COMMIT 이후 인과관계가 성립하는 ended_at-heartbeat_at; duration_ms / 1000; NULL heartbeat는 생략 |
| runtime.stale.false_count | runtime.stale.false_count | 원래 owner의 terminal 쓰기에서 영향받은 행이 없고 영속 상태가 STALE인 경우; count=1 |
| runtime.retry.after_case_stopped_count | runtime.retry.after_case_stopped_count | commit된 attempt>=2의 T2 NOT_APPLIED(STOPPED_WAITING)만 해당 |
| runtime.cancel.observe_latency_ms | runtime.cancel.observe_latency_ms | commit된 DB marker 관측과 monotonic 신호 전달 간격의 합 |
| runtime.db.claim_latency_ms | runtime.db.claim_latency_ms | transaction 시작부터 결과까지. claim latency에는 commit 성공 결과 사용 |
| runtime.db.lock_wait_timeout_count | runtime.db.lock_wait_timeout_count | 관측된 DB 실패/재시도 한 건. 정제된 DB taxonomy를 사용하고 예외 원문은 제외 |
| runtime.db.deadlock_count | runtime.db.deadlock_count | 관측된 DB 실패/재시도 한 건. 정제된 DB taxonomy를 사용하고 예외 원문은 제외 |
| runtime.db.pool_timeout_count | runtime.db.pool_timeout_count | 관측된 DB 실패/재시도 한 건. 정제된 DB taxonomy를 사용하고 예외 원문은 제외 |
| runtime.db.error_count | runtime.db.error_count | 관측된 DB 실패/재시도 한 건. 정제된 DB taxonomy를 사용하고 예외 원문은 제외 |
| runtime.db.tx_retry_count | runtime.db.tx_retry_count | 관측된 DB 실패/재시도 한 건. 정제된 DB taxonomy를 사용하고 예외 원문은 제외 |
| runtime.reflect.redelivery_count | runtime.reflect.redelivery_count | commit된 T2 redelivery 결과 |
| api.upload.bytes | api.upload.bytes | publish 후 수신 upload bytes. body 원문 제외 |
| api.upload.duration_ms | api.upload.duration_ms | upload 수신부터 publish까지의 시간 |
| api.upload.aborted_count | api.upload.aborted_count | DB 행을 만들지 않은 abort 한 건. 사유는 status에 기록 |
| api.upload.rejected_413_count | api.upload.rejected_413_count | 원본 upload 한도 거부 |
| api.frame.latency_ms | api.frame.latency_ms | 바깥 ASGI 응답 수명 |
| api.frame.wait_ms | api.frame.wait_ms | frame permit 진입 대기 시간 |
| api.frame.request_rate | api.frame.request_rate | frame 진입 한 건 |
| api.asset.download_latency_ms | api.asset.download_latency_ms | 바깥 ASGI send 수명 |
| api.asset.bytes | api.asset.bytes | downstream send가 성공 반환한 bytes. client 수신 bytes를 의미하지 않음 |
| api.view.request_rate | api.view.request_rate | 운영자가 선택한 로그 구간의 라우팅된 GET view 시도 수 |
| api.view.latency_ms | api.view.latency_ms | 실패를 포함한 view route의 duration_ms |
| api.request.latency_ms | api.request.completed | 응답 status별 duration_ms |
| api.request.rejected_413_count | api.request.completed | status=413을 요청당 한 번 집계 |
| api.upload.throughput_bps | api.upload.bytes / api.upload.duration_ms | trace_id별 byte/duration 관측을 짝지음. rate field나 정기 기록은 emit하지 않음 |
| api.upload.failures | api.upload.failed | status·요청 trace별 원본 요청 실패 |
| api.ready.duration_ms | api.ready.completed | 각 readiness 검사의 duration_ms |
| api.ready.unavailable_count | api.ready.completed | readiness 검사당 status=UNAVAILABLE을 한 번 집계 |

## 전체 event schema와 producer

모든 event의 공통 envelope는 timestamp/level/service/event다. correlation은 신뢰한 ID만 허용한다.

| Event | 필수 관측 필드 | 허용 status | 실제 producer |
| --- | --- | --- | --- |
| runtime.heartbeat.attempt_ms | duration_ms, status | RENEWED / FAILED / OWNERSHIP_LOST | common/jobs/heartbeat.py:Heartbeat._observe |
| runtime.heartbeat.lag_ms | duration_ms, status | RENEWED | common/jobs/heartbeat.py:Heartbeat._observe |
| runtime.heartbeat.skipped_tick_count | status | 0 / [1-9][0-9]* | common/jobs/heartbeat.py:Heartbeat._observe |
| runtime.heartbeat.consecutive_failures | status | 0 / [1-9][0-9]* | common/jobs/heartbeat.py:Heartbeat._observe |
| runtime.stale.detect_latency_s | duration_ms, status | STALE | common/jobs/sweep.py:sweep_once |
| runtime.stale.false_count | case_id, count, execution_id, job_id, status, trace_id | STALE | worker/composition.py:compose_worker.record |
| runtime.retry.after_case_stopped_count | status | STOPPED_WAITING | common/jobs/redelivery.py:observe_reflection |
| runtime.cancel.observe_latency_ms | duration_ms, status | REQUESTED | common/jobs/heartbeat.py:LeaseConnection.renew |
| runtime.db.claim_latency_ms | duration_ms, status | CLAIMED / EMPTY / COMMIT_UNKNOWN / LOCK_WAIT_TIMEOUT / DEADLOCK / DISCONNECT / FAILED | common/jobs/repository.py:claim_one.observe |
| runtime.db.lock_wait_timeout_count | status | LOCK_WAIT_TIMEOUT | common/db/transactions.py:_emit; common/jobs/worker_loop.py:WorkerLoop._db_error |
| runtime.db.deadlock_count | status | DEADLOCK | common/db/transactions.py:_emit; common/jobs/worker_loop.py:WorkerLoop._db_error |
| runtime.db.pool_timeout_count | status | POOL_TIMEOUT | common/db/transactions.py:_emit; common/jobs/worker_loop.py:WorkerLoop._db_error |
| runtime.db.error_count | status | LOCK_WAIT_TIMEOUT / DEADLOCK / POOL_TIMEOUT / DISCONNECT / CONNECT_FAILURE / CLEANUP / DB_FAILURE | common/db/transactions.py:_emit; common/jobs/worker_loop.py:WorkerLoop._db_error |
| runtime.db.tx_retry_count | status | LOCK_WAIT_TIMEOUT / DEADLOCK / DISCONNECT | common/db/transactions.py:_emit; common/jobs/worker_loop.py:WorkerLoop._db_error |
| runtime.reflect.redelivery_count | status | APPLIED / ALREADY_APPLIED / NOT_APPLIED | common/jobs/redelivery.py:redeliver_once |
| api.view.completed | duration_ms, status | 200 | api/composition.py:ApiComposition.get_view |
| api.view.request_rate | count | status 없음 | api/routes_view.py:view_router.view |
| api.view.latency_ms | duration_ms | status 없음 | api/routes_view.py:view_router.view |
| api.request.completed | duration_ms, status | [1-5][0-9]{2} | api/app.py:create_app.access |
| api.request.rejected_413_count | count | status 없음 | api/routes_commands.py:commands_router |
| api.upload.bytes | count | status 없음 | api/upload.py:receive_source |
| api.upload.duration_ms | duration_ms | status 없음 | api/upload.py:receive_source |
| api.upload.aborted_count | count, status | idle / duration / disconnect | api/app.py:create_app.access |
| api.upload.rejected_413_count | count | status 없음 | api/upload.py:SourceBodyLimitMiddleware; api/errors.py:install_error_handlers |
| api.request.failed | status | [1-5][0-9]{2} | api/errors.py:install_error_handlers; api/app.py:create_app.access |
| api.upload.failed | status | 400 / 404 / 405 / 409 / 413 / 415 / 422 / 500 / 503 | api/errors.py:install_error_handlers; api/upload.py:SourceBodyLimitMiddleware; api/app.py:create_app.access |
| api.frame.latency_ms | duration_ms, status | [1-5][0-9]{2} / CANCELLED / FAILED | api/frame_lifetime.py:FrameLifetimeMiddleware.__call__ |
| api.frame.wait_ms | duration_ms | status 없음 | api/frame_lifetime.py:FrameLifetimeMiddleware.__call__ |
| api.frame.request_rate | count | status 없음 | api/frame_lifetime.py:FrameLifetimeMiddleware.__call__ |
| api.asset.download_latency_ms | duration_ms, status | [1-5][0-9]{2} / CANCELLED / FAILED | api/asset_lifetime.py:AssetLifetimeMiddleware.__call__ |
| api.asset.bytes | count, status | [1-5][0-9]{2} / CANCELLED / FAILED | api/asset_lifetime.py:AssetLifetimeMiddleware.__call__ |
| api.ready.completed | duration_ms, status | OK / UNAVAILABLE | api/health.py:Readiness.check |

## 직접 실행과 실패 보존 — 2026-10-26

| 실행 | 직접 결과 | 판정 범위 |
| --- | --- | --- |
| 최초 local RED | 5 failed / 9 MySQL opt-in skipped | module 부재 unit RED; DB 증거 아님 |
| 실제 MySQL RED | 9 failed | MySQL 8.4.7에서 module 부재 |
| catalog RED | 2 failed / 22 passed | catalog 부재, 기존 formatter privacy는 통과 |
| false STALE RED | 1 failed / 6 passed / 10 deselected | 실제 원래 owner zero-row terminal emitter 부재 |
| gate RED | 5 failed | 신규 family 생략을 기존 gate가 허용하던 상태 |
| API 누락 RED | 1 failed | 실패 view 관측과 source별 upload 실패 미관측 |
| 최종 query/unit/HTTP focused | 49 passed | query-final, source hash 불변 |
| API/asset/upload/Worker/usage/logging 회귀 | 511 passed | related-api-worker-valid, source hash 불변 |
| 단위 evidence mutation | 6,193 passed / 2,203 deselected | 기존과 신규 21 parameter 시점; 전체 pytest 아님 |
| 최초 mandatory | testcase 1,021 passed / 498 non-MySQL deselected, process exit 1 | JSON/JUnit strict gate는 PASS; catalog 위반 6으로 전체 실행은 FAIL |
| claim catalog RED | testcase 1 passed / 19 deselected, process exit 1 | 실제 claim 실패 outcome을 catalog가 누락해 위반 3 재현 |
| catalog 보완 focused | 22 passed / 19 deselected | 기존 claim failure 상태 반영, command 413와 실제 pool timeout 관측; 위반 0 |

첫 집계 GREEN 시도의 8 passed/1 failed는 STALE 초 단위 기대값을 ms로 적은
테스트 오류였고 원본을 유지한다. READ ONLY 증명을 강화한 실행에서는
`SET TRANSACTION READ ONLY` 뒤 COMMIT이 다음 transaction 특성을 소비하는
fixture 오류를 재현했다. `START TRANSACTION READ ONLY`를 fresh connection에서
시작하도록 수정한 후 실제 UPDATE가 MySQL 1792로 거부되는 것을 확인했다.
capture env 미설정 실행도 실패로 보존한다. 어떤 실패도 PASS로 소급하지 않는다.

초기 관련 회귀 911개 중 1개는
`test_fatal_hook_process_boundary_preserves_db_cleanup_and_hides_original[startup-exit-logger]`
30초 timeout이었다. cleanup receipt는 joined/disposed/stop=true, checkedout=0,
runtime thread=[]였다. 단독 진단은 1 passed(1.67s)였지만 원인은 미확정이다.
이 초기 실행은 source 변경과도 겹쳐 final acceptance 증거로 사용하지 않는다.
고정 source 회귀의 다른 911개 실행은
`test_precommit_disconnect_then_same_worker_foreign_token_is_not_returned`에서
foreign claim이 None이라 실패했다. 단독 진단은 1 passed(0.83s)였으나 원인은
확정하지 않았고 원본 실패를 유지한다. ownership/claim 구현과 기존 테스트는
이를 피하려고 변경하지 않았다.

Windows sandbox 기본 temp numbered-dir 생성 오류로 중단한 mutation 실행과
그 오류를 재현한 진단을 보존한다. 작업 전용 basetemp로 실행 환경만 바로잡았다.
존재하지 않는 health test 경로를 지정한 no-tests 오류도 별도 보존한다.
boundary 최초 cp949 출력 오류는 UTF-8 실행으로 확인했으며 소스는 바꾸지 않았다.

catalog claim 상태는 기존 repository 실제 emitter의 실패 outcome까지 명시한다.
claim latency 분포를 보는 소비자는 CLAIMED/EMPTY 성공 outcome을 선택한다.
미관측 2종은 기존 emitter를 직접 실행하는 command 413/실제 DB pool 고갈
테스트로 보완했다. 필수 inventory는 scenario 17 유지, check 277→282,
parameter 845→867의 추가만 있으며 Case inventory는 동일하다.
workflow 파일 byte 의미와 30분/nested 900초 제한을 보존했다.

최종 nested MySQL·actual evidence mutation, 독립 reviewer 및 자원 정리는 진행 중이다.
전체 pytest는 아직 실행하지 않았다. 변경된 Runtime/API 경로의 focused 회귀와
mandatory 실제 MySQL·strict gate·actual mutation을 먼저 평가한다. unrelated
domain/eval/media 전체 회귀를 이 결과로 대체했다고 주장하지 않는다.

<a id="fresh-reviewer-p2와-수정"></a>

### Fresh 리뷰er P2와 수정

구현 대화 이력을 상속하지 않는 fresh reviewer가 읽기 전용으로 source/test/증거를
검토했다. P1은 없고 P2 1건을 발견했다: mutation 순회에 신규 22개 parameter를
포함했지만 총건수 기대식의 13-layer 묶음에 빠져 있었다. 독립 산술 probe가
선택 8,415 / 기대 8,129 / 차이 286으로 RED였고, 실제 첫 nested 실행도
같은 assertion에서 1 failed(597.27s)로 끝났다. 그 child의 1,022 tests 및
strict JSON/JUnit gate, catalog 32 event/0 violation은 통과했지만 parent 실행은
FAIL로 유지한다. 이 지점 뒤 metadata/family omission은 해당 실행에서 미실행이다.

기대식에 len(OBSERVABILITY_PARAMETERS)를 추가한 후 산술 probe는 8,415=8,415로
GREEN이다. 모든 기존 inventory와 mutation layer는 유지한다. 수정된 source로
전체 nested 검증을 다시 실행하며 이전 실패를 성공으로 재분류하지 않는다.
신규 최종 parameter 22개의 metadata/skip/xfail 단위 검증은 137 passed다.

## 최종 보고 상태 — 통합 gate 차단

구현과 source review는 완료했으나 **통합 검증 완료/merge 가능 상태는 아니다.**
상태는 계속 **IN_PROGRESS · Refs #299 (RT-12(b))**다.

| 최종 증거 | 직접 결과와 정확한 범위 |
| --- | --- |
| final-focused-all | 현재 product/test source의 신규 전체 50 passed, exit 0, 실행 중 hash 불변 |
| obs-gate-final | 신규 22 parameter의 metadata/skip/xfail 및 family 단위 137 passed |
| 첫 정상 nested child | 1,022 passed, skip=0/xfail=0, strict JSON/JUnit PASS, 실제 catalog 32/32·위반 0. parent는 산식 P2로 FAIL인 별개 사실 |
| 수정 후 nested-verified | parent exit 1; child 1,021 passed/1 failed, strict gate FAIL. 원인은 아래 30초 timeout으로 미확정 |
| actual-mutation-replay | 정상 child 원본의 SHA를 전후 확인하고 현 validation tail 자체를 실행. execution mutation 8,415건 모두 거부, 신규 관측 286건 포함. 신규 metadata/family 누락 93건 모두 거부. exit 0 |
| fresh read-only reviewer | 구현 이력 상속 없음. P2 산식 1건 발견→RED/GREEN 수정→해소 재확인. 코드의 미해결 P1/P2 없음. 통합 readiness는 nested 실패로 차단 |

수정 후 nested 실패의 정확한 testcase는
`test_fatal_hook_process_boundary_preserves_db_cleanup_and_hides_original[periodic-exit-logger]`다.
기존 30초 한도에서 timeout됐고 child cleanup receipt는 없었다. 파일 전용
faulthandler/phase 진단을 추가한 단독 실행은 1 passed(1.65s), code entry /
before main / after main을 기록했으며 timeout은 재현되지 않았다. 이번 코드 원인인지
환경 문제인지 단정하지 않는다. 이 진단을 원래 실패의 PASS로 대체하지 않는다.

actual-mutation-replay는 **새 DB 실행이 아니다.** 실제 완료된 정상 child의
JSON/JUnit/catalog를 수정하지 않고 현 검증 코드의 tail만 다시 실행한 별도 범위다.
child 시점과 달라진 Python 파일은 자기 자신을 제외했던 parent gate의 건수 산식
수정 파일 하나다. 원본 SHA와 code provenance를 replay metadata에 보존했다.
수정 후 실패한 nested와 이 재생의 성공을 합쳐 전체 nested PASS로 만들지 않는다.

전체 pytest는 **미실행**이다. 변경 영향 경로 직접 회귀 511건과 현재 신규 focused,
실제 mandatory child, strict gate, actual mutation을 확인했지만 알려진 nested 실패가
남아 있다. 이 상태에서 unrelated domain/eval/media 전체 실행을 추가해도 실패 gate를
해소하지 못하므로 실행을 확장하지 않았다. 원격 CI도 이번에는 실행하지 않았다.

### 기존 capability와 index 조사

| 기존 surface | 재사용/보존한 경계 |
| --- | --- |
| jobs repository/read_port | enqueue/claim/finish 및 execution read는 집계가 아니며 writer 그대로 유지 |
| jobs sweep/heartbeat/cancel | STALE/retry, lease/ownership, 중단 기록의 source; writer와 ordering 그대로 유지 |
| usage reconciliation._metrics | recovered marker, non-FINALIZED, oldest occurred_at/DB NOW/0 하한 의미 유지 |
| structured formatter/ApiEvents | allowlist와 bounded asynchronous sink 유지, raw payload/exception 미전달 |
| cleanup_emitter | 기존 6개 staging/temp count/bytes/failed_count 및 empty Context 보존 |
| job_execution index | PK execution_id, UNIQUE(job_id,attempt), ix_job_execution_claim(status,available_at,execution_id), ix_job_execution_job_id 보존 |
| usage index | tracker/final PK usage_id와 execution_ref index 보존 |

집계용 index/migration은 추가하지 않았다. 분포/전체 retained counter는 scan/window
집계이며 대규모 retained 데이터의 성능은 실측하지 않았다. 정기 수집/retention을
구현 편의로 추가하지 않는다. 과거 cap 변경별 exhausted 이력 복원과 전역 secret
masking은 구현하지 않으며 각각 기존 schema와 trusted ID 경계의 한계로 남긴다.

### 자원 정리 · PR 제외 자료

소유 MySQL 8.4.7/helper가 종료됐다. system 4+base 1 schema와 기본 account 4개,
감사용 연결 외 client 없음, transaction/data lock 0을 확인했다. 정확한 UUID datadir
부재, Linux/Windows port 폐쇄, 이번 작업의 Python/WSL 잔여 process 0을 감사했다.
소유 test temp 18개를 제거했고 텍스트 증거 4,628개는 CRC 검사한 ZIP으로 보존했다.
정상/실패 child의 원본 JSON/JUnit/catalog는 별도 evidence 폴더에도 복사해 읽기
전용으로 다시 확인할 수 있다. archive SHA는 temp-cleanup.json에 있다.

scratch 계획·runner·진단 plugin·source hash·RAW/JSON/JUnit·mutation 목록·CA·ZIP·
review 자료는 모두 PR 제외다. 공유 WSL/기존 서비스·다른 작업 scratch는 건드리지
않았다. staging/commit/push/PR 생성 및 Issue 상태 변경은 수행하지 않았다.

### 변경 파일 전체

- `docs/runtime/rt12b-observability.md`
- `docs/runtime/runtime-implementation-log.md`
- `scripts/check_mysql_test_report.py`
- `src/daesingo/api/app.py`
- `src/daesingo/api/errors.py`
- `src/daesingo/api/routes_view.py`
- `src/daesingo/api/upload.py`
- `src/daesingo/common/jobs/metrics.py`
- `src/daesingo/common/logging/catalog.py`
- `src/daesingo/worker/composition.py`
- `tests/api/test_event_catalog_mysql.py`
- `tests/common/db/integration/test_migration_gate.py`
- `tests/common/db/test_mysql_gate.py`
- `tests/common/jobs/test_metrics.py`
- `tests/common/jobs/test_metrics_mysql.py`
- `tests/common/logging/test_event_catalog.py`
- `tests/observability_acceptance.py`
- `tests/observability_capture.py`

### 최종 정적 확인

최종 source에서 boundary PASS, Contract fixture 62/26/104 PASS, 기존 actionlint의 Python/boundary workflow PASS, git diff --check PASS를 직접 확인했다. 현재 Python 변경 파일 16개는 final-focused-all의 SHA와 일치한다. 전체 변경은 18개이며 HEAD/branch는 승인 기준 그대로, staging은 비어 있다. 문서 후속 기록만 focused 실행 뒤 추가했다.

## Nested 30초 실패의 systematic debugging 후속 조사 — 2026-10-26

상태는 **IN_PROGRESS · Refs #299**, 통합 gate 차단 유지다. 이번 조사는 원인
분리를 위한 것이며 제품 코드·기존 테스트·timeout·sleep·inventory를 바꾸지 않았다.
RT-12(b) 인과관계가 확인되지 않아 수정용 RED/수정 단계에는 진입하지 않았다.

### 원본 실패와 확인 가능한 경계

대상은 `test_fatal_hook_process_boundary_preserves_db_cleanup_and_hides_original[periodic-exit-logger]`다.
기존 nested-verified의 대상 JUnit time은 30.608s이며 원본 RAW/JUnit 및 child
JSON/JUnit을 SHA로 봉인하고, 기존
ZIP의 cleanup receipt 부재를 확인했다. 원래 child의 별도 stdout/stderr, deadline
시점의 실제 native child/launcher PID 및 kill 전 poll/exit 상태는 보존되지 않았다.
RAW:136의 Popen repr에는 returncode1이 남아 있다. 그러나 현재 동일 경로
subprocess.py:551–560은 timeout 뒤 kill/communicate 재수집을 수행하고, Windows
terminate는 code1을 사용한다. 따라서 이 repr은 원래 정상 exit1인지 강제 종료인지,
실제 underlying child가 deadline에 살아 있었는지를 구별하지 못한다.
**출력 미보존은 빈 출력이나 child 생존의 증거가 아니다.**

원래 traceback의 설치된 CPython `subprocess.py:1630`은 Windows stdout reader
thread를 기존 30초 deadline까지 join했으나 살아 있어 TimeoutExpired를 던지는
지점이다. 따라서 stdout reader thread가 deadline에 완료되지 않았다는 경계만 확인한다.
EOF 미도달인지 close/스케줄링 지연인지, child가 import/본문/cleanup/atexit 중
어디에 있었는지 또는 이미 종료했는지는 확정하지 못한다. 초기의 EOF 미도달
표현은 이보다 강한 해석이어서 정정했다. 원본 실행 시 stdlib hash는 없으므로 현재 동일 경로의 구현과
대조했다는 한계도 남긴다. 이번 정상 실행에서는 venv launcher PID와 실제 Python
child PID가 달랐으나, 이를 원래 실패의 원인으로 단정하지 않는다.

### 비교 설계와 직접 실행

Git ref/working tree를 바꾸지 않고 승인 HEAD `42ddea72bb927e7adedf352ba53d160bda1aa049`
(local origin/develop 동일)의 `git archive`로 깨끗한 기준을 내보냈다. 같은 archive에
기존 18개 변경만 overlay한 candidate와 비교했다. 대상 테스트 bytes는 동일하다.
동일한 venv Python 3.12.14, 소유 MySQL 8.4.7 및 fixture 설정을 사용했고, 각
실험은 사전에 정한 범위별 한 차례 실행이다. 성공할 때까지 재시도하지 않았다.

| 이번 실행 | 직접 결과 | 관측 범위 |
| --- | --- | --- |
| baseline-alone-control | 1 passed, pytest 2.34s | child 계측 없는 단독 |
| current-alone-control-valid | 1 passed, 1.98s | 같은 단독 조건 |
| baseline-alone-trace | 1 passed, 3.17s | 파일 전용 phase/EOF 계측 |
| current-alone-trace | 1 passed, 2.05s | 같은 계측 조건 |
| baseline-common-prefix | 921 passed, 438.42s | 원래 순서의 공통 prefix |
| current-common-prefix-valid | 921 passed, 500.97s | 위와 같은 921개·순서·probe |
| current-original-prefix-context | 942 passed, 628.73s | 원래 942개 prefix·전체 수집 경로·catalog probe |

원래 대상까지 prefix는 942개이고 기준에 없는 신규 21개를 빼면 공통 921개다.
공통 비교에서는 양쪽 모두 catalog probe를 제외했다. node-list/test-source/
diagnostic script SHA와 DB-before fingerprint가 같은 것을 확인했다. 마지막
직전 parameter는 periodic-exit-healthy이고 그 앞 startup fatal 12개도 보존했다.

942개 별도 진단은 신규 21개뿐 아니라 원래 nested의 전체 collection 경로와
catalog probe도 포함한다. 따라서 여러 추가 조건 각각의 효과를 독립 추정하는
실험은 아니다. prefix 진단 모두 outer nested900s 검증 자체가 아니며, prefix
선택·새 base schema/port/temp·계측이라는 차이가 있다. 단독 control도 parent
선택 probe는 사용한다. 어떠한 진단 성공도 원래 실패의 PASS 전환이나 전체
mandatory/strict JSON·JUnit gate 통과로 사용하지 않는다.

### 단계 계측과 자원

파일 전용 marker로 child 진입/import/config/main/cleanup/thread shutdown/atexit와
parent Popen/communicate/stdout·stderr EOF를 구분했다. main thread의 선택 함수
call/return만 기록하고, 5초 file-only faulthandler는 모든 thread stack을 남기도록
했다. 출력 파이프를 진단 로그로 사용하지 않았고 기존 test timeout30은 유지했다.
관측 자체가 timing과 thread 구성을 바꾸므로 원래 상황을 그대로 재현했다는
주장은 하지 않는다. 단조 시계는 Windows tick 해상도 한계가 있어 근사치다.

| 공통 prefix의 단계 (Popen 시작 후 약 초) | 기준 | 현재 |
| --- | --- | --- |
| child code 진입 | 0.094 | 0.094 |
| worker import 시작 / 완료 | 0.438 / 0.719 | 0.438 / 0.750 |
| main 반환, cleanup 완료 | 0.922 | 0.922 |
| thread shutdown / atexit 마지막 marker | 0.922 | 0.922 |
| stdout·stderr EOF / communicate 반환 | 0.984 | 1.016 |

계측한 대상은 예상 child exit1, stdout428 bytes(같은 SHA), stderr0을 확인했다.
join/stop_and_join/dispose/logging.shutdown 경계의 profile exit event와 atexit
marker가 모두 있다. profile return은 예외 unwind도 포함하며 정상 반환의 단독
증명으로 사용하지 않는다. 테스트 자체가 cleanup receipt의 기대값을 검증했다. 또한
thread shutdown 때 MainThread만 관측했다. 두 대상의 5초 stack 파일은 비어 있다.
942개 진단에서도 main/atexit 마지막 marker 약0.968s, 두 EOF 약1.031s, 예상
child exit1/stdout428/stderr0 및 stack0이었다. catalog probe는 31 event/위반0이며,
뒤쪽 테스트를 생략했으므로 전체32 coverage 수락 증거로 쓰지 않는다.
이는 이 실행들의 사실이며 원래 30초 정체 단계의 증거로 소급하지 않는다.

DB snapshot은 시간 제한 child 바깥에서 채집했다. 공통 비교의 target 전/후 fixture
pool checkedout=0, 관련 engine/dialect/pool listener fingerprint 동일이었다.
전/teardown 후 audit 연결 이외 client0, transaction0, lock0이었다. 본문 후 유휴
fixture connection1은 teardown 뒤 사라졌다. 이 경계에서 잔여 문제가 없었다는
의미이며 관측하지 않은 원본의 순간적 자원 문제를 배제하지 않는다.

서버 종료 전 system4+base1 schema, 기본 account4, audit/event scheduler 이외
client0, transaction0/lock0을 확인했다. MySQL/helper 종료와 정확한 UUID datadir
제거, Linux port/proc 잔여0, 기록한97개 PID 및 scope 명령 잔여0을 감사했다.

Windows port 검증은 별도로 한계를 남긴다. 종료 직후 connect_ex=0(접속 수락)으로
첫 assertion은 FAIL이었다. 이어 읽은 native listener/owner 목록은 비었고 Linux도
port/proc/datadir가 없었다. 이 새 관측 후 한 차례 최종 확인은 connect_ex=10035로,
Windows의 즉각적인 connection-refused 증명은 확보하지 못했다. 최초 수락 원인은
미확정이며 원래30초 timeout에 귀속하지 않는다. 반복 확인이나 공유 WSL/relay의
강제 종료는 하지 않았다. 실제 소유 서버/child 잔여는 관측되지 않았다.

소유 per-arm test temp7개만 경계 검증 후 제거했다. JSON 등 bounded text67개
(cleanup receipt46개)를 CRC 검사한 ZIP으로 보존했고 SHA는 temp-cleanup.json에
있다. 실행 RAW/JSON/JUnit/child phase·출력과 frozen source export/manifest는
독립 재검토용 자료로 남겼다. 공유 서비스와 이전 evidence는 변경하지 않았다.

setup 오류도 따로 보존했다: 최초 current 단독의 scratch audit SQL percent
처리 오류, current 공통 순서의 권한 미적용 WinError10013(둘 다 pytest 진입 전),
제한된 문맥의 CIM 읽기 실패다. 수정된 scratch audit/동일 허용 권한으로 명시적
valid 실험을 실행했으며 제품이나 테스트 재시도를 통한 우회가 아니다. baseline
단독 무계측 arm은 per-arm DB audit 추가 전 실행이라 해당 감사 자료가 없다.

### 판정과 남은 한계

RT-12(b) 코드가 원인이라는 인과관계, 깨끗한 develop도 같은 실패를 낸다는 근거,
특정 환경 원인은 이번 관측에서 확정하지 못했다. 원본의 import/startup/body/
cleanup/atexit/EOF 중 정체 단계도 미확정이다. 무근거 timeout 증가·sleep 추가·
retry·skip/xfail과 제품 변경을 하지 않았다. **미재현은 해결 판정이 아니다.**

전체 pytest 및 새 전체 nested/strict gate/mutation 실행은 이번 조사에서는 하지
않았다. 알려진 실패의 원인 분리를 위해 정한 단독·predecessor 비교만 수행했다.
이전 정상 child/strict/mutation과 이번 진단은 서로 다른 증거로 유지한다.

구현/대화 이력을 상속하지 않은 새 read-only reviewer가 원본 RAW/JUnit/phase,
Git blob/manifest 및 ZIP을 독립 대조했다. 깨끗한 기준의 Python590개와 Git blob
일치, product/test16개 불변, 실제 실행 결과/순서/receipt·보존 hash를 확인했다.
**이번 조사 범위에서 확정 코드 P1/P2는 없으나 원본 실패는 미해결이고 통합/병합은
차단 유지**라고 판정했다. 기존 구현 전체의 신규 승인으로 확대하지 않는다.
리뷰는 파일 수정·테스트·DB접속·네트워크·프로세스 제어 없이 수행됐다.

리뷰가 지적한 추가 한계도 남긴다: 초기 단독 arm의 diagnostic script SHA는
보존되지 않았으며 후속 공통 prefix의 동일 SHA가 이를 소급 보완하지 않는다.
앞서 명시한 baseline 단독 DB audit 부재도 유지한다. 읽기 전용 리뷰 자료는
`fresh-review.md`에 별도 보존했다.

증거는 PR 제외 `.codex-scratch/rt12b-debug-20261026`에 보존한다. 주요 항목은
`original-evidence.json`, `initial-source.json`, `snapshots.json`, `environment.json`,
`summary.json`, 각 `runs/*`의 RAW/JSON/JUnit/phase/child stdout·stderr/stack,
`server-final.json`과 자원 감사다. 기존 `.codex-scratch/rt12b-20261026`의 실패·
정상 원본은 변경하지 않았다. 이번 tracked 수정은 이 Notes와 implementation log
후속 기록뿐이며, product/test 16개 hash는 조사 시작과 같다. staging/commit/
push/PR 생성은 하지 않았다.
