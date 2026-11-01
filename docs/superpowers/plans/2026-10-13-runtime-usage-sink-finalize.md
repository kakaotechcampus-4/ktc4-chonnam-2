<a id="rt-07b-usagesink-and-explicit-finalize-implementation-plan"></a>

# RT-07(b) UsageSink와 명시적 finalize 구현 계획

> **에이전트 작업자 지침:** 현재 branch에서 superpowers:executing-plans를 사용한다. 사용자는 commit, push, PR 금지를 명시했으며 모든 기존 untracked 파일을 보존한다.

**목표:** 각 호출의 STARTED와 OBSERVED 사실을 영속화하고 호출자가 논리적 Run 관계를 확인한 뒤 Final 하나를 원자적으로 추가한다.

**아키텍처:** 표준 라이브러리만 사용하는 UsageSink Protocol은 common/usage/port.py에 둔다. execution 범위 영속 구현은 Worker 조합에서 DB 전용 transaction runner를 받는다. 각 메서드는 반환 전에 트랜잭션을 닫으며 provider I/O는 전적으로 호출자 소유다.

**기술 스택:** 기존 Python, SQLAlchemy Core, MySQL 8.4, pytest, runtime_0003.

**명세:** runtime-tech-spec.md §3.3/4.5/11, contract-usage-record.md §4–8, Accepted #244 최종 댓글 5979576799, implementation-plan.md §6 RT-07/§12. PR #349는 fa5a0fcbd5f88e70e7a4c9ba0a457b42a65a27a1로 병합됐으며 현재 HEAD는 51683e0b다.

<a id="global-constraints"></a>

## 전역 제약

- Search/provider 수정, recovery, sweep 등록, 늦은 관측 정책, usage_refs projection, 가격/FX, retention, budget 변경은 없다.
- append_final, DECIMAL(65,30), 동결된 마이그레이션, DB CHECK 의미를 보존한다.
- Runtime은 식별자/execution/case를 제공하고 호출자는 실제 FAILED Run을 포함한 관측 사실과 확인된 Run 관계를 제공한다.
- 알 수 없는 amount는 null로 남는다. retry callback에는 HTTP가 없다. 소유권 손실 뒤 이미 관측한 usage를 fencing으로 차단하지 않는다.
- RT-07은 IN_PROGRESS로 유지하며 Refs #294 (RT-07(b)); PR과 merge SHA는 pending이다.

<a id="choices-and-failure-modes"></a>

## 선택과 실패 양상

| 선택 | 대안 | 선택 / 방지하는 실패 |
| --- | --- | --- |
| 영속화 | sink 내부 engine / transaction runner 주입 | runner 주입; DB 정책을 격리하고 Protocol의 의존성 없음 유지 |
| 식별자 | 재시도마다 신규 / callback 전 고정 | 고정 ID와 typed 스냅샷; 불명확한 COMMIT 후 중복 STARTED 방지 |
| 상태 전이 | 무조건 upsert / locking read + 조건부 UPDATE | locking read와 기대 상태 predicate; 관측 사실 덮어쓰기 방지 |
| 동시 스냅샷 | 마지막 writer 우선 / 비교와 충돌 | 같은 데이터는 no-op, 다른 데이터는 충돌; tracker lock으로 직렬화 |
| Final 순서 | 별도 트랜잭션 / 같은 트랜잭션에서 append 후 marker | append_final 후 FINALIZED; marker 실패 시 둘 다 롤백 |
| 주입 | 공유 sink / claim별 factory | dispatch 전 execution별 factory; 공유 tracker cache 없음 |
| 오류 | provider 형태 오류 / 정제된 UsageError 계층 | 명시적 영속화, 검증, 식별자/상태 오류; HTTP 재dispatch 없이 Worker FAILED |

<a id="review-focus"></a>

## 검토 초점

- begin COMMIT 불명확 및 재시도 소진: 명시적 begin 재실행을 위해 정제된 영속화 오류에 Runtime 발급 식별자를 유지한다. 호출자는 재실행을 이미 보낸 HTTP의 반복 허가로 해석하면 안 된다.
- 변경 가능한 입력: transaction callback 진입 전에 typed 비공개 스냅샷으로 정규화한다.
- finish/finalize 경쟁: Final은 OBSERVED에서만 유효하다. 정상 최종화 뒤에도 동일 finish는 no-op으로 남으며 충돌 관측은 덮어쓰지 않는다.
- 소유권 손실: finish/finalize는 ownership admission guard를 사용하지 않으며 recovery 처리는 연기한다.
- 예외 privacy: UsageError 문구, cause, 구조화 로그, Pydantic ValidationError에 원시 입력/SQL/driver 오류를 포함하지 않는다.

<a id="task-1-durable-port-and-tracker"></a>

## 작업 1: 영속 port와 tracker

파일: common/usage/{port,sink}.py; tests/common/usage/test_usage_sink{,_mysql}.py.

인터페이스: begin(operation, provider_label, pricing_context, *, usage_id=None) -> str; finish(usage_id, *, token_usage, processed_duration_sec, latency_ms, pricing_context, cost, outcome, failure_kind=None) -> None; finalize(usage_id, *, run_ref, run_ref_reason) -> None. begin 재실행은 이 execution의 sink가 보유한 이전 Runtime 발급 식별자만 사용하며 recovery 조회 인터페이스를 도입하지 않는다.

- [x] 동결된 식별자/스냅샷, 실패한 begin HTTP=0, 실패한 finish HTTP total=1, 검증 privacy, Protocol typing에 대한 RED unit 테스트를 작성한다.
- [x] 대상 pytest를 실행하고 RED 출력을 보존한다.
- [x] typed 정규화, 정제된 오류, DB 전용 callback을 구현한다. begin은 이후 상태에서도 불변 STARTED context를 비교한다. finish는 모든 관측 필드를 비교한다. finalize는 잠긴 tracker에서 Contract projection을 구성하고 FINALIZED 표기 전에 추가한다.
- [x] N회 호출, 재실행/충돌, 누락/start-only 식별자, 동시 finish/finalize, Final/marker 양쪽 경계 롤백, 1205/1213, 각 메서드의 실제 proxy COMMIT ACK 손실에 대한 실제 MySQL RED 후 GREEN 테스트를 추가한다.

<a id="task-2-worker-execution-isolation"></a>

## 작업 2: Worker execution 격리

파일: common/jobs/{execution,worker_loop}.py, worker/composition.py; tests/worker/test_usage_worker_mysql.py.

- [x] execution별 factory, dispatch 전 취소 usage=0, usage 영속화 terminal 오류, execution 두 개 격리의 RED 테스트를 작성한다.
- [x] ExecutionContext.usage_sink 타입을 UsageSink | None으로 지정하고 주입된 WorkerLoop factory로 각 claim에 새 sink를 만든다. 운영 조합은 ownership guard 없이 run_worker_transaction을 usage 영속화에 bind한다.
- [x] Runtime usage 오류가 RUNTIME_USAGE_* FAILED가 되는지 검증한다. record 재시도는 terminal 사실을 재사용하며 HTTP를 재dispatch하지 않는다.
- [x] worker unit 및 실제 MySQL 테스트를 실행한다.

<a id="task-3-fail-closed-gate-and-review-evidence"></a>

## 작업 3: 안전하게 거부하는 gate와 검토 증거

파일: tests/usage_acceptance.py, scripts/check_mysql_test_report.py; 기존 gate 테스트는 독립 인수 목록을 자동 소비한다; Runtime Log와 README.

- [x] 독립 usage_sink 인수 family/매개변수를 추가하고 운영 요구사항 추가 전에 gate 테스트 RED를 확인한다.
- [x] 같은 필수 목록을 운영 gate에 추가하고 순수 gate 및 실제 JSON/JUnit 매개변수 제거 검사를 실행한다(수집/선택/phase/JUnit).
- [x] require-MySQL 모음(skip/xfail=0), 전체 pytest, 경계, Contract fixture, workflow 정적 검사, git diff --check를 실행한다.
- [x] diff를 검토하고 구현 차이, 선택, 정확한 직접 검증, 남은 위험을 RT-07 Log에 갱신한다. 이 실행의 스키마/계정/연결/서버를 정리하고 .codex-scratch 아래 증거를 보존한다.
- [x] 로컬에서 검토 가능한 변경으로 마무리한다. staging/commit/push/PR은 없다.
