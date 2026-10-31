<a id="rt-02a-db-foundation-implementation-plan"></a>

# RT-02(a) DB 기반 구현 계획

> 실행: 현재 세션에서 진행하며 사용자가 승인했다. 각 동작에 TDD를 적용한다. commit, push, PR 생성, worktree 전환은 하지 않는다. 승인된 대화 설계와 Runtime Plan RT-02(a)가 명세다.

**목표:** 역할별 동기 MySQL factory, 호출자 소유 callback 트랜잭션, 실제 MySQL 통합 harness, 안전하게 거부하는 CI 실행 증거.

**아키텍처:** SQLAlchemy Core Connection callback을 사용하고 context manager가 자원 정리를 소유한다. Worker는 완전한 DB callback만 재시도한다. API는 한 번 실행하고 커밋 전 의존성 실패와 불명확한 커밋 결과를 구분한다. 테스트 전용 스키마와 COMMIT-response proxy로 실제 MySQL을 실행한다.

**기술 스택:** 기존 잠금 버전 SQLAlchemy/PyMySQL/Alembic/pytest를 사용하며 추가 지원은 표준 라이브러리만 쓴다.

<a id="constraints-and-review-focus"></a>

## 제약과 검토 초점

- B-D8 max_attempts=3은 최초 시도를 포함하며 추가 시도는 최대 두 회, 간격은 1초다. PM 명확화: Issue #289 댓글 6036679371.
- RT-01 DbSettings와 서비스 기본값, P-5 Connection 참여, Case 소유권, case-first 잠금 순서를 보존한다.
- runtime 테이블, migration env/runner, 시작 시 migration, HTTP 매핑, Case fixture 수정, Baseline/Contract 변경은 없다.
- recording-baseline-negative-001.json과 기존 사용자 파일을 보존한다. RT-02는 IN_PROGRESS로, Issue #289는 열린 상태로 유지한다.
- callback 내부 숨은 커밋, 불명확한 커밋 재실행 안전성, 커밋 결과를 가리는 정리 오류, 역할 정책을 덮어쓰는 URL 옵션, 수집/xfail/deselection 우회를 확인한다.

<a id="task-1-factories"></a>

## 작업 1: Factory

파일: common/db/engines.py 및 __init__.py; tests/common/db/test_engines.py.
산출물: create_api_engine(db), create_worker_engine(db), create_heartbeat_engine(db, heartbeat), create_ready_engine(db, ready), create_migration_engine(url, explicit timeout arguments).

- [x] RED: 역할 정책과 사용자 지정 timeout 전달, URL 정책 우회 거부, 즉시 연결/migration 없음.
- [x] GREEN: RC, 물리 연결 lock wait hook, 애플리케이션 QueuePool, 전용 NullPool, 별도 migration 정책.
- [x] 집중 테스트를 검증한다.

<a id="task-2-transactions"></a>

## 작업 2: 트랜잭션

파일: common/db/transactions.py 및 errors.py; tests/common/db/test_transactions.py.
산출물: run_worker_transaction(engine, operation, *, sleep, logger), run_api_transaction(engine, operation, *, logger); 안전한 실패 타입.

- [x] RED: 성공, 완전한 callback 재시도, 최대 3회 시도 / 2회 sleep, 재시도 불가 오류 전파, API 한 번, 커밋 단계, 정리, callback 소유 커밋 거부.
- [x] GREEN: 재시도 전 완전한 트랜잭션 정리, driver 연결 해제 분류, 안전한 로깅, HTTP 의미나 domain import 없음.
- [x] 집중 모음을 검증한다.

<a id="task-3-harness-and-ci-gate"></a>

## 작업 3: Harness와 CI gate

파일: 루트 conftest.py, tests/mysql_harness.py, scripts/check_mysql_test_report.py, pyproject.toml, tests/common/db/test_mysql_gate.py.

- [x] RED: require mode가 URL/의존성/연결/권한 오류를 숨길 수 없음, 변경하지 않은 Case 테스트의 marker 추론, skip/xfail/deselection/비어 있거나 누락된 시나리오 보고서 실패.
- [x] GREEN: 테스트별 스키마 fixture, 이른 preflight, 수집/실행 보고서, 독립 보고서 checker.
- [x] subprocess gate 테스트를 검증한다.

<a id="task-4-real-integration-tests"></a>

## 작업 4: 실제 통합 테스트

파일: tests/common/db/integration 및 테스트 전용 지원.

- [x] session/교체/pool/heartbeat/ready, 실제 1205/1213/KILL, 롤백/읽기 재실행, API 커밋 경계, 실제 COMMIT-response 손실, Case 저장소 호환성 테스트. proxy 부재는 RED였으며 호환성 assertions는 이미 구현한 factory를 재사용해 바로 통과했다.
- [x] 모든 네트워크/lock 결함을 실제로 유지하고 event/barrier와 제한된 대기로 조정한다. MySQL 8.4.7은 사용자의 기존 MySQL 8.0과 독립적인 격리 WSL scratch에서 실행했다.
- [x] MySQL 8.4에 대해 DAESINGO_REQUIRE_MYSQL=1로 검증한다. mock/skip 대체는 없다.

<a id="task-5-workflow-docs-final-verification"></a>

## 작업 5: Workflow, 문서, 최종 검증

파일: 기존 python-tests.yml; Runtime Implementation Log; common/루트 README 사실.

- [x] MySQL 8.4 service, 테스트 URL / require flag, 전체 모음 보고서, no-skip/no-xfail 및 필수 시나리오 검사를 추가한다. 보호 workflow와 lockfile을 보존한다. 원격 Actions 실행은 pending이며 push/PR은 승인되지 않았다.
- [x] 구현 선택, B-D8 횟수 계산, 검증, 한계를 기록하고 RT-02는 IN_PROGRESS로 유지한다. 향후 PR 메모는 Refs #289 (RT-02(a))를 사용하며 저장소 PR-body 초안 대신 Implementation Log에 내용을 둔다.
- [x] 전체 pytest, 실제 MySQL 모음/보고서 gate, 경계, Contract fixture, git diff --check를 실행한다. 전체 diff를 검토하고 정확한 skip / 남은 인수 조건을 보고한다.

<a id="execution-ledger"></a>

## 실행 기록

- 시작: branch feature/runtime-db-foundation, bcc0730; 기존 untracked recording-baseline-negative-001.json만 있었다. 기존 Python은 DLL 로딩에 sandbox escalation이 필요하며 설치는 수행하지 않았다.
- 판단: 사용자가 지정한 feature branch와 현재 checkout에서 작업하며 두 번째 checkout 생성이나 계획 커밋 대신 승인된 실행 범위를 보존한다.
- 최초 검증 (2026-10-07): 1935 passed / 무관한 opt-in skip 26개; 실제 MySQL 8.4.7 40 passed / skip=0 / xfail=0; report/JUnit gate, 경계, Contract fixture, diff 검사 PASS. 최초 읽기 전용 검토 지적을 처리했으며 이후 독립 검토 지적은 아래를 참조한다. 상세 내용과 정확한 skip은 Runtime Implementation Log RT-02에 있다.
- 프로젝트 의존성 설치나 lockfile 변경은 없다. 실제 통합 서버 실행을 위해 MySQL 바이너리와 공유 라이브러리를 무시되는 scratch에 추출했으며 시스템 패키지와 사용자 MySQL 서비스는 변경하지 않았다. commit/push/PR은 없다.
- 2026-10-08: 독립 검토가 schema query 덮어쓰기, COMMIT 불확실성을 가리는 정리, 역할별 gate 요구 누락을 재현했다. RED 회귀와 최소 수정을 추가했으며 현재 증거는 Implementation Log RT-02에 있다. 앞선 PASS/검토 주장은 과거 기록이며 현재 revision은 독립 재검토 대기 중이다. 기존 scratch/사용자 파일은 그대로 두었고 이 실행은 별도 OS temp 디렉터리를 사용한다.
- 2026-10-08 최종 검증: 2022 passed / 무관한 opt-in skip 26개; 실제 MySQL 8.4.7 46 passed / skip=0 / xfail=0, Case 18개 보존, 역할/시나리오 조합 32개 필수. 실제 보고서 변이 검사, actionlint/ShellCheck/YAML/bash 문법, 경계, Contract fixture, tracked/신규 파일 diff 검사 PASS. 현재 독립 재검토와 원격 Actions 실행은 pending이며 RT-02는 IN_PROGRESS로 유지한다.
