# Runtime durable timestamp ordering — #370 구현/재리뷰 기록

Status: **독립 재리뷰 준비 완료** — 제품 수정과 targeted/unit/전체 MySQL acceptance·gate 검증 완료. merge 전이므로 Implementation Log는 `IN_PROGRESS` 유지. 커밋·푸시·PR 없음.

## Authority와 격리

- [#370 Runtime/Contract/Baseline Owner 승인](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/370#issuecomment-6227886934): terminal B안 + heartbeat/lease B안. 댓글의 author `flosure23`, created/updated `2026-10-17T01:20:50Z`를 GitHub API로 직접 확인했다.
- [승인 전 진단](./durable-timestamp-ordering-2026-10-17.md)은 역사적 snapshot으로 보존한다. 근본 원인은 UTC DB wall-clock의 비단조성과 writer별 validation 차이다. 과거 개별 finish 장애의 정확한 timestamp pair와 WSL correction의 시스템 원인은 여전히 미확정이다.
- Base `ae9288226901b7e551595400dcb53c453c01d38e`, branch `codex/runtime-durable-timestamp-ordering`, worktree `C:/Users/cheol/.codex/worktrees/rt-clock/ktc4-chonnam-2`를 재사용했다. RT-08(b)는 별도 원본 checkout에 유지한다. 시작 시 원본 tracked diff hash `4b81684a4a909cf9f7b52f305534626a89ec0468`을 기록했다.
- 새 evidence는 `C:/Users/cheol/.codex/visualizations/2026/10/16/01a145b6-b1ea-78a3-9962-30874bae0f3a/runtime-clock-fix/`. 이전 clockdiag RAW/archive와 진단 evidence를 수정하지 않는다.

## 최종 SQL 의미

### 변경 파일 전체 (19개)

| 범위 | 파일 |
|---|---|
| SQL 구현 | `src/daesingo/common/jobs/timestamps.py` (신규), `repository.py`, `heartbeat.py`, `sweep.py`, `cancel.py` (동일 디렉터리) |
| 실제 MySQL acceptance | `tests/common/jobs/test_timestamp_order_mysql.py` (신규), `tests/common/jobs/test_sweep_mysql.py` |
| gate/증거 검증 | `scripts/check_mysql_test_report.py`, `tests/timestamp_acceptance.py` (신규), `tests/common/db/test_mysql_gate.py`, `tests/common/db/integration/test_migration_gate.py` |
| 승인 의미/구현 기록 | `docs/architecture/contracts/contract-job-execution.md`, `docs/runtime/provisional-baseline-v0.1.md`, `docs/runtime/runtime-tech-spec.md`, `docs/runtime/runtime-implementation-log.md`, `src/daesingo/common/README.md` |
| 운영 확인 절차 | `docs/runtime/deployment-runbook.md` |
| 재리뷰 자료 | `docs/runtime/reviews/durable-timestamp-ordering-2026-10-17.md` (이전 진단 snapshot/cutoff), `docs/runtime/reviews/durable-timestamp-ordering-implementation-2026-10-17.md` (현재 보고서) |

`Q=queued_at`, `S=COALESCE(started_at,Q)`, `H=COALESCE(heartbeat_at,Q)`, `C=COALESCE(cancel_requested_at,Q)`, `N=DB NOW(6)`:

| writer | 저장 규칙 |
|---|---|
| T1 SUCCEEDED/FAILED/CANCELLED, sweep STALE, QUEUED cancel | `ended_at = GREATEST(N,Q,S,H,C)` |
| 성공 heartbeat | `Hnew = GREATEST(N,Q,S,H)` |
| 성공 lease renewal | `expirynew = GREATEST(COALESCE(old_expiry,Hnew+duration), Hnew+duration)` |
| claim | 기존 DB NOW 기반 start/heartbeat/expiry 생성·eligibility 유지 |
| sweep eligibility | 기존 `RUNNING AND lease_expires_at < NOW(6)` 유지 |

SQL 표현식은 `common/jobs/timestamps.py`가 소유한다. NULL metadata는 필수 queued_at으로 대체해 MySQL GREATEST의 NULL 전파를 막는다. 미래 lease expiry는 terminal 하한이 아니다. 앱 clock으로 대체하지 않는다. T1의 public model 검증을 유지하고, 최종 조건부 UPDATE에서 현재 row의 하한을 재평가하므로 validation snapshot 뒤 성공한 heartbeat/cancel을 반영한다.

## Transaction·ownership·복구

- status/owner predicates, claim token과 PK receipt, first-commit-wins, case-first T2 locking, UNIQUE(job_id,attempt), caller-owned commit/rollback을 유지한다.
- sweep은 실제 저장한 causal ended_at을 다시 읽어 같은 transaction에서 retry queued_at과 backoff를 만든다. retry ID는 callback replay 사이 고정한다.
- T1 ACK 유실 복구는 기존 terminal status/owner/produced/failure_kind의 locking reread를 유지하고 ended_at을 재샘플링해 덮어쓰지 않는다. sweep은 저장된 ended_at+child ID receipt를 유지한다.
- 단순 timestamp 재대입이 unchanged row여도 MySQL matched-row 의미로 renewal 성공을 반환하는지 검사했다. heartbeat 0 rows의 ownership loss 의미는 바꾸지 않는다.
- 이 변경은 기존 invalid historical row를 backfill하거나 원본 증거를 수정하지 않는다. 그런 row의 정리는 별도 데이터 판단이 필요하다.

## 파생 지표

- execution duration은 causal `ended_at-started_at`: 역행 중 0 근처 허용, 실제 monotonic elapsed 보장 없음.
- STALE detect latency는 causal ended_at − 마지막 durable heartbeat. heartbeat가 null이면 측정 생략, 미래 heartbeat가 하한이면 0 가능. 기존 future-heartbeat fixture의 기대값도 이 승인 의미에 맞췄다.
- retry queued_at은 같은 transaction의 STALE ended_at, available_at은 queued_at+backoff다. raw NOW+backoff보다 늦어질 수 있다. claim 이후 queue wait에는 승인된 backoff가 포함된다.
- heartbeat attempt/lag, transaction·worker scheduling은 기존 process monotonic 측정이다. provider UsageRecord latency는 전달된 관측값이며 JobExecution duration과 구분한다. cancellation 관측/ACK metric의 기존 DB marker-age+monotonic 경계는 변경하지 않았다.
- raw clock correction을 새 custom metric으로 배포하지 않았다. ended_at을 raw rollback 증거로 사용하지 않는다.

## RED → GREEN 및 evidence

실제 MySQL 8.4.7, 별도 port 13349, 새 `/tmp/runtime-clock-fix-01a145b6/data`. 테스트는 session-local `SET timestamp`만 사용하며 host/WSL realtime을 바꾸지 않는다. 자연 발생 clock step을 통과 조건으로 삼지 않는다.

| 직접 실행 | 결과 | evidence |
|---|---|---|
| 이전 진단 7 + 정식 acceptance 7, 제품 수정 전 | 14 failed(각 7), 예상 순서/validator 실패 | red-mysql.json, red-junit.xml, red-output.txt |
| 최소 SQL 수정 직후 정식 7 | 7 passed | green-initial-mysql.json / green-initial-junit.xml |
| 추가 조합 + sweep 최초 | 62 passed / 2 failed. claim·QUEUED cancel에서 줄바꿈 때문에 proxy arm hook가 동작하지 않은 테스트 오류 | targeted-mysql.json / targeted-junit.xml |
| proxy hook 보정 뒤 7 경로 실제 ACK 유실 | 7 passed, 26 deselected, 실제 COMMIT OK 폐기 확인 | ack-fixed-mysql.json / ack-fixed-junit.xml |
| 최종 timestamp 35 + 기존 claim/heartbeat 회귀 | 82 passed | targeted-final-mysql.json / targeted-final-junit.xml |
| 새 gate inventory 적용 전 RED | required timestamp role 제거를 놓쳐 DID NOT RAISE | 직접 pytest 출력 |
| gate role 및 기존 bypass subset GREEN | 16 passed | gate-green-junit.xml |
| timestamp role/scenario/parameter metadata 누락 | 105 passed | gate-metadata-junit.xml |
| 관련 unit/privacy/lifecycle/gate 전체 | 3982 passed, 357 deselected | unit-junit.xml |
| 전체 MySQL acceptance | **626 passed / 1878 phases**, skip0 / xfail0 / failure0. 독립 CLI strict gate PASS | actual-gate-final-tmp/test_actual_report_rejects_eac0/mysql.json, mysql.xml |
| 실제 보고서 evidence mutation | **3521 전부 거부**, timestamp35 parameter ×13 = **455 전부 거부**. outer acceptance 1 PASS / 954.45초(15분54초) | 같은 디렉터리 parameter-mutations.json, actual-gate-final-junit.xml |
| boundary / Contract fixture | PASS: 위반0, 구조62/JSON26/의미104 | 직접 scripts 실행 |
| workflow | 원본 파일 무변경 확인 + static content/order PASS | check_workflow.py. YAML parser 미설치, 원격 CI 미실행 |
| git diff --check / 새 파일 whitespace | PASS | 직접 git 및 final_verify.py 실행 |

35개 parameter는 terminal5 / renewal4 / causal bounds3 / metric1 / retry10 / unknown-COMMIT7 / concurrency5다. retry는 각 terminal 종류의 MySQL SIGNAL 1205/1213 주입과 별개로 실제 InnoDB deadlock 및 lock timeout도 clock-step과 결합한다. concurrency에는 heartbeat/sweep/finish/cancel 경합 및 T1 validation snapshot 뒤 별도 connection heartbeat commit이 포함된다.

전체 acceptance의 실행 문제도 별도 보존한다. 첫 `/tmp` datadir 실행은 nested 900초 timeout으로 끝났고 완성 JSON/JUnit gate evidence가 없어 전체 PASS로 인정하지 않는다(`actual-gate-junit.xml`). RAM datadir 비교 실행에는 test-only phase observer를 붙였고 API shutdown fixture의 실패를 확인해 실행을 중단했다(`ram-progress-*.jsonl`, `ram-fixture-processes.json`). 이 fixture는 Windows에서 `DAESINGO_MYSQL_TEST_BASEDIR`와 `DAESINGO_MYSQL_TEST_LIBDIR`가 필요한데 실행자가 설정하지 않은 오류였다. 단일 직접 실행으로 누락 시 KeyError와 설정 후 PASS를 확인했다(`fixture-env-red-junit.xml`, `fixture-env-green-junit.xml`). 단일 진단 최초 호출은 기본 temp 권한 실패였고 전용 basetemp로 바로잡았다(`fixture-missing-env-junit.xml`). 제품/fixture source·timeout·assertion을 변경해 우회하지 않았다.

최종 clean 실행은 별도 `/dev/shm/runtime-clock-fix-final-01a145b6/data`, port13351과 올바른 fixture 환경을 사용했다. 각 테스트 phase만 기록하는 observer는 SQL/fixture/결과를 바꾸지 않는다. 저장 위치 비교의 30회 commit 측정에서 RAM이 짧았지만 그것만으로 첫 전체 timeout의 단일 원인을 확정하지 않는다(`storage-comparison.json`). **첫 900초 초과의 정확한 지연 위치·원인은 미확정**이고, 후속 PASS로 이를 소급 해결됐다고 주장하지 않는다. Windows 관측 hook의 scheduling/I/O 영향과 원격 CI 실행시간 한계는 남는다. 중단/제한 실패의 잔여 process는 이번 정확한 명령/parent tree를 확인해 정리했으며 관련 없는 process를 종료하지 않았다.

gate 구현과 별개의 `tests/timestamp_acceptance.py` inventory를 unit 및 실제 보고서 mutation이 사용한다. 수집·선택·setup/call/teardown·전체 node·JUnit 누락, skip/xfail/failure, JUnit skipped/failure/error를 거부한다. 필수 parameter를 일부만 실행한 보고서는 전체 gate PASS로 인정하지 않는다.

## 문서/Decision/운영 경계

- Contract §5.1과 STALE 설명: 승인된 DB causal terminal 의미를 명시. schema/enum/version 변경이나 validator 완화 없음.
- Baseline B-L2/B-L6·§3.1·retry/metric/validation 항목: successful renewal은 기존 lease를 단축하지 않음, clock rollback 중 raw NOW+duration보다 만료가 늦을 수 있음을 명시. 기존 숫자/timeout/retry 상한 유지.
- Accepted Decision은 #370 Owner 댓글이 authority이고 기존 구조/ownership 모델을 새로 고르지 않으므로 임의 ADR을 만들지 않았다. Tech Spec과 implementation log가 이 결정을 가리킨다.
- 저장소의 AWS 환경 snapshot(2026-10-02, Ubuntu 24.04.4 LTS), Ops Spec, deployment runbook과 scripts/workflow를 읽기 전용으로 조사했다. 저장소에서 현재 time source/chrony 설정의 증거는 확인하지 못했다. Ubuntu라고 chrony가 활성이라는 추론을 하지 않는다.
- 실제 AWS/EC2/SSM/host 상태는 조회·변경하지 않았다. runbook에 time source·makestep·tracking/sources·correction journal의 읽기 전용 확인 절차를 추가했다. 현재 운영 상태의 확인은 Runtime/Ops follow-up으로 남기며 Issue 분리를 권고한다. CloudWatch custom metric/agent, IAM, SSM 또는 host 변경이 필요한지는 아직 미확정이고, 필요성이 확인되면 별도 Issue/결정으로 분리한다. 제품 수정의 선행조건으로 두지 않는다.

## 독립 재리뷰와 통합

requesting-code-review 스킬로 별도 읽기 전용 에이전트가 production SQL, NULL/assignment semantics, concurrent final UPDATE, fences/receipts, privacy 및 gate inventory를 검토했다. actionable code/test-gate finding은 없었고, 과거 진단 문서의 cutoff를 명시하라는 의견을 반영했다. 리뷰 에이전트는 테스트를 실행하지 않았으며 이 기록을 사용자 독립 재리뷰의 대체로 주장하지 않는다.

최종 PR 본문은 `Closes #370`, `Related #295`로 준비한다. #295는 이 수정에서 닫지 않는다. 이 branch를 독립 재리뷰한 뒤 timestamp 수정이 먼저 통합되도록 하고, 이후 RT-08(b)의 미커밋 변경을 보존한 채 사용자 선택 방식으로 fix를 가져와 /view와 기존 acceptance를 다시 확인한다.

잔여 위험: raw clock의 실제 elapsed 왜곡, rollback 중 lease/retry의 지연, 기존 historical invalid row, 현재 EC2 clock discipline 미확인, 원격 Linux CI 실행 시간·결과 미검증. sweep의 raw NOW predicate는 유지하므로 큰 forward step도 실제 경과시간에 비해 이른 STALE 판정에 영향을 줄 수 있다. 이번 ordering 방어를 monotonic lease deadline 보장으로 확대하지 않는다.

**전체 pytest 판단:** targeted82·unit3982·추가metadata105·전체 실제 MySQL626 및 strict gate/evidence mutation 통과 뒤 C: 여유 16,063,348,736 bytes(약15 GiB)를 확인했다. 공간 부족으로 막힌 것은 아니다. 변경한 SQL/gate와 그 consumer인 Runtime/Case의 전체 MySQL inventory를 검증했고, 전체 pytest는 변경하지 않은 capability 회귀 및 같은 MySQL inventory의 큰 중복 실행을 더하므로 이번 독립 재리뷰 범위에서는 추가 실행하지 않기로 판단했다. 따라서 전체 capability 회귀 PASS나 원격 CI PASS는 주장하지 않는다.

재실행 entry point는 `tests/common/jobs/test_timestamp_order_mysql.py`와 `tests/common/db/integration/test_migration_gate.py`다. disposable MySQL 8.4 test URL, `DAESINGO_REQUIRE_MYSQL=1`, UTF-8 console, 전용 `--basetemp`가 필요하다. Windows의 실제 shutdown fixture는 `DAESINGO_MYSQL_TEST_BASEDIR`(MySQL binary basedir의 WSL 경로)와 `DAESINGO_MYSQL_TEST_LIBDIR`(의존 library WSL 경로)도 설정한다. 이번 확인 경로는 각각 `/mnt/c/ktc4-chonnam-2/.codex-scratch/rt02a-mysql/mysql-8.4.7-linux-glibc2.28-x86_64-minimal`, `/mnt/c/ktc4-chonnam-2/.codex-scratch/rt02a-mysql/libs/usr/lib/x86_64-linux-gnu`였다. 테스트 자료와 hash manifest는 외부 evidence 디렉터리의 `final-checks.json`에 보존한다. 이전 assessment 두 JSON hash와 RT-08(b) tracked diff hash가 시작/종료 때 일치했다. 전체 RAW archive 재hash는 수행하지 않았다.

**정리:** 최종 서버에서 fixture schema0 / fixture 계정0 / 다른 client connection0을 직접 확인하고 datadir와 PID가 일치하는 이번 서버만 정상 종료했다(`cleanup-before-shutdown.json`). 앞선 두 비교 서버도 종료했다. datadir를 삭제하지는 않았지만 `/dev/shm` 데이터는 WSL 재시작에 보존되는 archive가 아니다. 재리뷰 evidence는 Windows 외부 artifact 디렉터리의 JSON/JUnit/phase 기록으로 보존한다. PR 본문은 같은 디렉터리 `PR-draft.md`로만 준비했으며 GitHub PR은 만들지 않았다.
