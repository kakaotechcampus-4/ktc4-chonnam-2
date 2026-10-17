# Runtime durable timestamp ordering 진단 — Owner 판단 전 중단

> **역사적 진단 snapshot.** 아래 중단·미실행 상태는 #370 Owner 승인 전의 기록이다. [2026-10-17 승인 댓글](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/370#issuecomment-6227886934) 이후 구현을 재개했다. 현재 구현/검증 결과는 [구현 보고서](./durable-timestamp-ordering-implementation-2026-10-17.md)가 추적한다. 외부 보존 JSON/RAW/archive는 이 문서 갱신과 별개로 변경하지 않는다.

작성일: 2026-10-17 KST. 상태: 진단/설계 비교/실제 MySQL RED 완료, 제품 수정과 GREEN 미실행.

## 작업 경계

- fetch로 확인한 develop: `ae9288226901b7e551595400dcb53c453c01d38e`.
- 별도 managed worktree: `C:/Users/cheol/.codex/worktrees/rt-clock/ktc4-chonnam-2`.
- 별도 branch: `codex/runtime-durable-timestamp-ordering`.
- 원래 `C:/ktc4-chonnam-2`의 `feature/runtime-api-cases-view`와 미커밋 변경에는 쓰기 작업을 하지 않았다. 시작/종료 시 status 목록이 같았다. 시작 시 파일별 content hash는 기록하지 않았으므로 완전한 전후 byte 비교를 했다고 주장하지 않는다.
- 현재 채팅의 초기 detached worktree도 수정하지 않았다. 첫 managed worktree 생성은 Windows filename length로 실패했고, 짧은 이름 `rt-clock`으로 성공했다.
- 커밋/푸시/PR/Issue/외부 댓글을 생성하지 않았다.
- 기존 RAW/archive는 읽기 전용으로 사용했다. 두 assessment JSON의 전후 SHA256은 아래와 같고 일치했다. 전체 archive를 다시 hash한 것은 아니다.
  - final-report.json: `989E179500934EDBBC1061B72DF90CEABAC0FA8AA78330100C83D33D7D97BE8B`
  - persisted-order-violation.json: `D3FC7B2FA827458259F77BEE6848A0F5364338DBD25B4011010852798B0EADF4`

## 읽은 지침과 authority

루트 CLAUDE.md, docs/README.md, Runtime README, Implementation Plan §0/RT-03~RT-07/§12, JobExecution Contract, Baseline B-L/B-R/§6, Tech Spec claim/lease/sweep/T1/T2, 관련 implementation와 migration/harness/workflow/gate를 확인했다.

GitHub에서 #244, #245, #248, #250의 Accepted Decision 및 댓글과 #289/#290/#292/#293/#294/#295를 조회했다. 결정 핵심은 STALE만 자동 retry, STALE+다음 QUEUED의 원자성, caller-owned transaction, first committed terminal wins, status+owner fencing, durable receipt 기반 COMMIT 불명 복구다. timestamp clamp를 승인한 결정은 확인하지 못했다.

중단 근거는 스킬이 새로 만든 승인 절차가 아니라 사용자 요청과 저장소 Plan §12.3이다. Plan은 Contract가 애매해 선택에 따라 외부 동작이 달라지는 경우에도 Owner 확인을 요구한다. 관련 원문:

- `docs/runtime/runtime-implementation-plan.md` §12.3: Contract 의미 또는 외부 동작이 달라지는 애매함이면 멈추고 Contract Owner 확인. Baseline 의미 변경이면 김준영 확인.
- `docs/architecture/contracts/contract-job-execution.md` §5: started_at = RUNNING 진입 시각, ended_at = 종료 시각.
- 같은 Contract §8: 관측하지 못한 STALE 종료 시각을 만들어내지 않음, ended_at=null 허용.
- `docs/runtime/provisional-baseline-v0.1.md` B-L2/B-L6: lease = DB NOW(6)+duration. §6: execution duration = ended_at-started_at, stale detect latency = STALE 기록 시각-last heartbeat.

## 확정 원인과 미확정 범위

**직접 재현으로 확정:** SQL writer가 UTC wall-clock을 statement/transaction 사이에서도 시간 순서가 보장되는 시각처럼 사용한다. DB session UTC 고정은 timezone 혼합을 막지만 역행을 막지 않는다. T1은 해당 결과를 모델 validator에서 거부하고 sweep/QUEUED cancel은 모델 검증 없이 durable하게 저장한다. 이후 같은 JobExecution projection은 validator에서 실패한다. terminal writer 간 규칙도 일관되지 않다.

MySQL NOW는 statement 시작 시각이며 transaction 전체의 고정/monotonic 시계가 아니다. SET timestamp로 NOW를 통제할 수 있다. 공식 자료: [MySQL 8.4 date/time functions](https://dev.mysql.com/doc/refman/8.4/en/date-and-time-functions.html), [server variables](https://dev.mysql.com/doc/refman/8.4/en/server-system-variables.html#sysvar_timestamp).

**보존 증거:** STALE started_at `2026-10-16 16:37:38.313184 UTC`, ended_at `16:37:37.106510 UTC`, 차이 `-1.206674 s`. binlog chain에서 fixture는 heartbeat/lease만 바꿨다. 기존 assessment는 같은 boot journal/WSL realtime 역행과 DB 샘플의 연결을 기록한다. 이는 이번에 자연 발생 clock step을 다시 관측했다는 뜻이 아니다.

**미확정:** 과거 finish ValidationError 각각이 같은 원인이었는지는 그 실패의 정확한 pair가 없어 확정할 수 없다. 이번 재현은 동일 오류를 유발할 수 있는 메커니즘을 증명한다. RT-08(b)가 원인이라는 증거도 없다. 변경 전 develop에서 재현되므로 RT-08(b) 없이도 성립하는 결함이다. WSL step 자체의 시스템 원인을 이번 조사에서 새로 규명하지 않았다.

## Runtime SQL 경로 전수 확인 결과

대상 필드와 NOW/UTC_TIMESTAMP/TIMESTAMPDIFF를 src와 runtime migrations에서 검색했다. readout/search 자체 Run 시각은 별도 Owner surface이며 이번 JobExecution writer가 아니다.

| 경로 | 시각 생성/비교 | 역행 영향과 fence |
|---|---|---|
| repository.enqueue | UTC_TIMESTAMP(6) → queued_at=available_at | UTC wall-clock이며 enqueue 순서와 실제 시간 순서는 별개. 호출자 transaction 참여 |
| repository.claim SELECT/UPDATE | available_at<=NOW; started_at=heartbeat_at=NOW; lease=NOW+duration | SELECT 뒤 역행 시 최종 UPDATE가 0 rows가 되어 ClaimLostError 가능. 정상 available_at>=queued_at이면 UPDATE eligibility가 start>=queue를 간접 보장한다. SKIP LOCKED/조건부 status/receipt 유지 |
| claim COMMIT 불명 복구 | 고정 PK locking read, token/owner/status, lease<=NOW 검사 | 역행은 lease의 real elapsed 해석/회복 admission에 영향. receipt mismatch를 timestamp로 대체하지 않음 |
| heartbeat.LeaseConnection | heartbeat=NOW; expiry=NOW+duration, status RUNNING+owner | heartbeat 및 기존 expiry보다 뒤로 이동 가능. 관측한 DB 시각+duration이라는 현 Baseline에는 부합하므로 monotonic heartbeat가 이미 승인된 불변조건이라고 단정하지 않는다. 0 rows ownership loss 유지 |
| heartbeat cancel 관찰 | NOW-cancel_requested_at + process monotonic read/ACK 경과 | DB 차이는 음수가 될 수 있고 현재 max(0,...)로 0 보정. 실제 monotonic 요청→관찰 latency로 해석할 수 없음 |
| repository.finish: 성공/실패/RUNNING 취소 | SELECT NOW → 모델 검증 → 조건부 terminal UPDATE | start보다 과거면 ValidationError, terminal 미기록/호출자 rollback. validator를 제거하지 않음. 만료 자체는 소유 상실로 보지 않고 status+owner가 기준 |
| cancel.request_cancel: QUEUED | cancel_requested_at=COALESCE(...,NOW), ended_at=NOW | queue보다 과거인 terminal 저장 가능, projection 실패. 전체 attempt 잠금과 caller transaction 유지 |
| cancel.request_cancel: RUNNING/STALE | 취소 표식 최초 NOW만 보존 | 시작보다 앞선 표식 가능. terminal writer는 아님 |
| sweep candidate scan/locked recheck/final UPDATE | expiry<NOW; ended_at=NOW | statement 사이 clock 변경 시 후보 여부가 달라질 수 있으나 최종 predicate가 재확인. terminal은 검증 없이 저장해 순서 위반 가능 |
| sweep retry | UPDATE에 저장한 ended_at을 reread → child queued_at, available_at=queued+backoff | 같은 transaction과 UNIQUE로 중복 방지. terminal clamp를 여기에 전파하면 raw NOW+backoff보다 claim 지연이 늘어날 수 있음 |
| sweep COMMIT 불명 복구 | PK lock + status/ended_at receipt + pinned child id | ended_at 정책 변경 시 receipt를 동일한 durable 값으로 유지해야 함. replay 때 clock 재계산으로 receipt를 바꾸면 안 됨 |
| T1 COMMIT ACK 유실 | terminal status/owner/produced/failure_kind를 잠금 reread | 기존 terminal의 ended_at을 재작성하지 않음. 역행이 있었다는 이유로 committed를 rollback으로 간주해서는 안 됨 |
| T2/reflection/redelivery | SUCCEEDED/FAILED scan; case-first lock; case_applied_at=UTC_TIMESTAMP; followup enqueue | ended_at writer 아님. marker는 terminal보다 과거가 될 수 있으나 현재 non-null receipt로 사용, timestamp 비교로 dedup하지 않음. redelivery는 timestamps를 JobExecution으로 검증하지 않으므로 성공을 projection 정합성 증거로 쓰면 안 됨 |
| usage reconciliation | terminal 상태 선택; finalized_at=NOW, in-flight age는 GREATEST(0,NOW-oldest) | 위 네 timestamp를 쓰지 않음. usage sink 관측 시각은 기본 app UTC clock이고 provider latency는 전달값. JobExecution DB duration과 혼동 금지 |

모든 terminal SQL writer는 T1 finish, sweep STALE, QUEUED cancel의 세 군데다. 현재 동일 ordering 규칙을 따르지 않는다. retry insertion과 T2 marker는 terminal writer가 아니다.

## 설계 비교 — 채택하지 않고 Owner에게 제시

wall-clock이 역행한 경우 raw 관측 종료 시각 보존과 ended_at>=started_at은 동시에 만족할 수 없다. 어떤 값을 authoritative로 정의할지 먼저 정해야 한다.

| 대안 | 장점 | 의미/안전성 문제 | 판단 |
|---|---|---|---|
| validator 삭제/완화 | T1 rejection 감소 | invalid durable row와 음수 duration을 허용하고 소비자 정합성 약화. 요구사항 미충족 | 제외 |
| app UTC 시각 사용 | SQL 변경 적음 | app realtime도 역행 가능, process clock skew 추가, lease B-L6 변경 | 제외 |
| terminal SQL clamp: max(DB now, started_at 또는 queued_at) | 가장 작은 terminal ordering 수정 후보. 세 writer에 공통 적용 가능 | ended_at이 raw 관측 종료가 아닌 causal lower bound가 되고 duration은 역행 구간에서 0으로 축소. sweep retry queued/backoff와 stale detection metric에도 전파 영향. heartbeat 이전 종료도 허용할지 별도 결정 필요 | **Owner 명시 확인 후 우선 검토 후보**, 현재 미채택 |
| heartbeat/lease도 max(old,DB now)/max(old expiry,new expiry) | 필드 단조성과 기존 lease 하한 보존 | B-L2의 마지막 성공 DB 시각+duration과 다르고 lease 만료를 늦출 수 있음. heartbeat를 logical clock으로 바꾸면 stale latency도 변함 | Baseline Owner 판단 필요 |
| STALE만 ended_at=null | Contract가 허용하는 미관측 값 보존 | T1/QUEUED cancel 미해결. sweep receipt/retry 기준/metric 구현을 분리해야 함 | 전체 결함의 단독 해결안 아님 |
| DB raw timestamp와 causal timestamp/monotonic duration 분리 | 관측값과 ordering 모두 표현 가능 | schema/contract/metric 설계 범위가 커짐. process monotonic은 재시작/다른 host 사이 durable clock 대체가 아님 | 별도 설계 후보 |
| clock 회복까지 write 보류 | raw timestamp 의미 유지 가능 | 즉시 취소·terminal persistence·retry 가용성에 영향, 영구/큰 역행의 대기 정책 필요 | 단순 구현 detail로 채택 불가 |

Owner 확인 사항: (1) 공개 ended_at을 raw 관측 시각 또는 DB 기반 causal timestamp 중 무엇으로 볼지, clamp 시 DB duration과 STALE 기록 metric을 어떻게 해석할지, (2) heartbeat/lease는 raw NOW+duration을 유지할지, monotonic 보존이 필요한지. 김준영(Runtime/Contract/Baseline) 판단이 필요하며 latency 소비 의미 변경이면 eval, retry queued_at 의미 변경이면 #248 consumer 확인도 필요하다.

## 실제 실행 RED와 기준 검증

독립 MySQL 8.4.7, port 13348, 새 `/tmp/runtime-clock-01a145b6/data`. 기존 data/RAW/archive를 서버 datadir로 사용하지 않았다. host/WSL realtime은 변경하지 않았다. 세션 checkout의 SET timestamp로 enqueue/claim 이후 transaction 시각을 고정했다. 테스트 별 임시 schema는 기존 MySQL harness가 생성/정리했다.

| 직접 실행 | 결과 | 증거 |
|---|---|---|
| 최초 진단 | 6 failed, 예상 결함 | red-mysql.json / red-junit.xml |
| 추가 반례 포함 최종 진단 | **7 failed**, setup/teardown 통과, skip/xfail 없음 | red-v2-mysql.json / red-v2-junit.xml |
| 기존 MySQL 기준 회귀 subset | **24 passed, 106 deselected** | baseline-mysql.json / baseline-junit.xml |
| gate unit subset | **25 passed, 3424 deselected** | gate-junit.xml |
| 부분 MySQL 보고서를 전체 gate에 입력 | exit 1, incomplete/invalid evidence로 거부(예상) | check_mysql_test_report CLI 직접 출력 |
| boundary | PASS, 위반 0 | scripts/check_boundaries.py 직접 실행 |
| Contract fixture | 구조 62/JSON 26/의미 104 PASS | scripts/check_contract_fixtures.py 직접 실행 |
| workflow | 실제 YAML 읽기 확인. full pytest 뒤 strict gate 유지 | workflow 실제 CI 실행/검증은 하지 않음 |
| git diff --check | PASS | 제품 코드 변경 없음. 보고서 추가 후에도 재확인 |

진단 최초 호출의 --mysql-report plugin 초기 로드 오류는 -p mysql_harness로 수정했다. gate subset 최초 호출은 sandbox 기본 temp directory 생성 실패로 20 passed/5 setup errors였고, 허용된 전용 basetemp로 재실행해 25 passed였다. 이 두 환경/실행 문제를 제품 결함이나 RED 성공에 포함하지 않았다.

최종 RED 세부:

- claim `16:37:38` 후 terminal NOW `16:37:36.750000`으로 통제, 차이 -1.25s.
- sweep STALE: invalid row가 commit됨. repository `_execution_model`과 public `read_executions` 모두 ValidationError. `sweep.json`.
- T1 SUCCEEDED/FAILED/CANCELLED: 각 ValidationError로 rollback, 저장된 행은 RUNNING/ended_at=null이고 그 행의 projection은 유효함. 저장된 invalid terminal을 관측했다고 주장하지 않는다. `finish_*.json`.
- heartbeat: heartbeat가 `16:37:38`→`16:37:36.75`, lease가 `16:38:38`→`16:38:36.75`. 공개 모델은 heartbeat/lease를 검증하지 않아 통과한다. `heartbeat.json`.
- QUEUED cancel: queue `16:37:36`, end `16:37:34.75`; invalid row commit 후 projection/model 실패. `queued_cancel.json`.
- 추가 sweep 반례: enqueue→claim→heartbeat(NOW=T-120)→sweep(NOW=T-1.25). 직접 row timestamp UPDATE 없이 실제 API만으로 invalid STALE commit 및 projection/model 실패. 이는 큰 역행/회복 시퀀스의 가능성을 증명하며 보존 사건과 동일한 1.221s step을 재현한 것은 아님. `sweep_no_fixture_edits.json`.
- heartbeat 단조성 assertion은 수정 후보 invariant 진단이다. 현 Baseline이 이미 이를 약속한다고 주장하지 않는다.

24개 기준 회귀에는 claim ACK 유실의 recovered/token/owner/terminal/expired/missing, 실제 1213 terminal deadlock, 1205 claim lock timeout, sweep commit/rollback atomicity, sweep ACK 유실, 자연 lease 만료 뒤 old owner fence, T1 성공/실패 ACK 유실, T2 followup/stopped ACK 유실, heartbeat zero-row 및 commit 실패 fencing이 포함된다. 이는 **수정 전 기준 결과**이고 clock-step과 ACK 유실을 조합한 수정 후 회귀 결과가 아니다.

## 남은 일과 RT-08(b) 반영 순서

1. 별도 timestamp defect Issue에서 위 Owner 판단을 기록. 현재 Issue를 생성하지 않았다. #295는 관련 추적 링크이며 원인 Issue로 단정하지 않는다.
2. 승인된 semantics를 Contract/Baseline/Decision의 적절한 SoT에 기록한 뒤 이 별도 branch에서 설계를 확정.
3. 외부 진단 test를 승인된 기대값으로 repository acceptance에 편입. 정상·실패·취소·STALE·QUEUED cancel 모두 동일 terminal ordering, heartbeat/lease 필요 invariant, exact equality/NULL/boundary/large backward step을 RED로 고정.
4. 최소 writer 수정. timestamp source를 바꾸더라도 status/owner predicate, final conditional UPDATE, case-first lock, 동일 tx atomicity, pinned receipt/idempotency를 유지.
5. clock-step + COMMIT ACK 유실(커밋 성공/실제 rollback), 1205/1213 callback replay, 동시 heartbeat/sweep/finish/cancel, ownership 교체/late result, T2/recovery 회귀를 실제 MySQL에서 GREEN 확인. 장애 후 handler/provider 재호출 없음 확인. 로그/예외 privacy는 원문 SQL/row/credential을 로그에 추가하지 않는 회귀로 확인.
6. gate role/scenario/parameter를 새 acceptance에 추가하고, 수집/선택/setup/call/teardown/JUnit 중 누락 또는 skip/xfail/실패를 각각 거부하는 검증 추가. 현재 gate는 이번 외부 진단의 필수 실행을 강제하지 않는다.
7. targeted와 실제 MySQL acceptance/gate가 통과한 뒤 full pytest 실행 여부 결정. 현재 RED이므로 full pytest는 실행하지 않음. boundary/Contract fixture/workflow/diff check 재확인.
8. 별도 timestamp PR로 먼저 검토·병합(이번 요청에서는 PR/commit/push 금지). 그 후 기존 RT-08(b) 미커밋 변경을 보존한 상태에서 사용자가 정한 통합 방식으로 해당 fix를 가져오고 /view projection 및 기존 RT-08(b) acceptance를 재검증. 기존 작업을 reset/stash/rebase하지 않음.

별도 defect Issue와 별도 수정 PR을 권고한다. Contract 의미 확정은 같은 Issue의 Owner 결정으로 추적할 수 있으며 자동으로 새 ADR이 필요하다고 단정하지 않는다. 현재 제품 수정, GREEN, 전체 MySQL acceptance PASS, full pytest PASS, workflow CI PASS는 주장할 수 없다.
