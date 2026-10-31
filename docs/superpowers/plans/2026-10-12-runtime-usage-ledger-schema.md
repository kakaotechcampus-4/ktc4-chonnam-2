<a id="rt-07a-usage-ledger-schema-implementation-plan"></a>

# RT-07(a) Usage ledger 스키마 구현 계획

> **에이전트 작업자 지침:** superpowers:executing-plans와 TDD로 현재 세션에서 실행한다. 사용자는 의미를 보존하는 권고 후 계속 진행하도록 명시적으로 승인하고 commit, staging, push, PR 생성을 금지한다.

**목표:** sink나 reconciliation을 구현하지 않고 Runtime usage 영속화와 호출자 트랜잭션 Final 추가 primitive를 도입한다.

**아키텍처:** 동결된 `runtime_0003`는 `runtime_0002` 다음에 온다. 독립 in-flight 및 Final 테이블은 FK 없이 `usage_id` PK를 공유한다. Final 삽입 시 식별자 중복이면 기존 불변 스냅샷을 비교하고 갱신하지 않는다. Amount binding은 MySQL 변환 전에 정확한 십진 표현을 검증한다.

**기술 스택:** SQLAlchemy Core, Alembic, Decimal, 실제 MySQL 8.4, pytest JSON/JUnit 인수 gate.

**명세:** `docs/runtime/runtime-implementation-plan.md` §6 RT-07 / §12; `runtime-tech-spec.md` §3.3 / §4.5 / §11; UsageRecord Final Contract §4–8; #244 최종 결정; #294; Baseline B-G1 / §2.12. 제공된 AGENTS.md가 적용되며 저장소 AGENTS.md 파일은 발견되지 않았다.

<a id="global-constraints"></a>

## 전역 제약

- RT-07(a)만 해당한다. sink/Worker 주입, reconciliation/늦은 관측/sweep, Search 연결, 가격/FX, retention/purge, budget은 제외한다.
- Contract, Accepted Decision, Baseline 의미는 변경하지 않는다. 외부 의미에 권한 있는 결정이 필요하면 중단한다.
- 현재 `feature/runtime-usage-ledger-schema`를 유지하고 최초 untracked 파일은 그대로 둔다. staging, commit, push, PR은 없다. `Refs #294 (RT-07(a))`로 연결하며 RT-07은 `IN_PROGRESS`로 유지한다.
- 필수 실제 MySQL 증거: skip=0, xfail=0, JSON/JUnit 양쪽의 모든 필수 매개변수.

<a id="design-choices-and-failure-modes"></a>

## 설계 선택과 실패 양상

| 선택 | 대안과 위험 | 선택한 구현 상세 |
| --- | --- | --- |
| DECIMAL | (20,6)은 소수 여섯 자리 초과를 거부하거나 반올림해야 함; (38,18)은 양자화하지 않은 producer 값을 소수 18자리로 제한; (65,30)은 저장 비용 증가 | (65,30), 정수 35자리 / 소수 30자리, binding 전 명시적 거부; 반올림 없음 |
| 식별자 | execution+usage 복합 고유성은 전역 ID 재사용 허용; surrogate PK만으로는 중복 Final 허용 | 양쪽 테이블 모두 `usage_id` ascii_bin PK; execution_ref는 nullable/indexed |
| 참조 | FK Final→in-flight는 영속 ledger를 추적 lifecycle에 결합; cascade는 Final 삭제 위험; FK가 없으면 내부 참조 책임 필요 | FK 없는 공유 ID, 독립 저장 Final Contract 스냅샷; 모듈 간 FK 없음 |
| 재실행 | 새 ID는 과금 중복; upsert는 이력 덮어쓰기; ignore는 스냅샷 불일치 은폐 | 고정 ID INSERT; duplicate-key 오류만 locking read와 전체 typed 비교 수행; 동일하면 false/no-op, 불일치면 명시적 충돌 |

**Amount 근거:** Search `ProviderUsage.cost_with_rates`는 양자화 없이 Decimal(str(rate)), 정수 token 곱셈, 1,000,000으로 나눗셈을 사용한다. Contract 예에는 184.20과 0이 있다. 향후 KRW 출력 경계를 고정한 Accepted Decision은 없다. 65/30은 가격 반올림 정책을 지어내지 않기 위해 MySQL 지원 최댓값을 사용한다. 임의의 미래 producer 값이 모두 들어간다고 약속하지 않는다. 범위 밖 또는 선언된 소수 자릿수가 30을 초과하는 값(뒤의 영 포함)은 양자화하지 않고 실패시킨다. 지어낸 가격 정책으로 음의 유한 amount를 금지하지 않는다.

MySQL 참고 자료: [DECIMAL 특성](https://dev.mysql.com/doc/refman/8.4/en/precision-math-decimal-characteristics.html), [반올림](https://dev.mysql.com/doc/refman/8.4/en/precision-math-rounding.html). 원시 SQL은 애플리케이션 binder를 우회하고 MySQL이 CHECK 평가 전에 반올림할 수 있다. CHECK가 원래 원시 정밀도를 탐지할 수 있다고 주장하지 않는다.

**COMMIT 불명확:** 이 primitive는 잠정적인 트랜잭션 로컬 결과를 반환한다. ID를 생성하거나 트랜잭션을 소유하거나 provider를 호출하지 않는다. 호출자는 재시도 전반에 같은 식별자와 전체 스냅샷을 유지한다. INSERT는 경쟁 트랜잭션을 기다린다. duplicate-key locking read는 커밋된 스냅샷을 검증하며 첫 writer가 롤백하면 삽입이 가능하다. 호출자 트랜잭션의 다른 효과를 복구하려면 해당 효과가 독립적으로 재실행 안전해야 한다. 이 primitive는 무관한 전체 트랜잭션의 커밋을 증명하지 않는다.

**In-flight 형태:** typed 호출 식별자/context, 관측값, 선택적 안전 실패 범주, pending/durable run 관계, STARTED/OBSERVED/FINALIZED 상태, 관측/최종화 시각. Final에는 typed 열로 평탄화한 Contract 필드만 있다. Pending run 관계는 in-flight에서만 허용한다. TTL이나 복구 자격 정책은 도입하지 않는다.

<a id="review-focus"></a>

## 검토 초점

- Decimal context precision이 65자리 검증/직렬화를 반올림하면 안 된다.
- Nullable token/run CHECK는 SQL UNKNOWN 우회와 부분 객체를 거부해야 한다.
- 같은 식별자의 다른 amount/null, run, pricing, context는 Final을 바꾸지 않고 실패해야 한다.
- 경쟁 삽입 롤백과 실제 COMMIT response 손실은 고정 식별자로 해소해야 한다.
- family를 유지한 채 필수 매개변수 하나를 제거해도 JSON/JUnit gate가 실패해야 한다.

<a id="tasks"></a>

## 작업

<a id="task-1-exact-amount-boundary"></a>

### 작업 1: 정확한 amount 경계

파일: `src/daesingo/common/usage/amount.py`, `tests/common/usage/test_amount.py`.

- [x] `parse_amount(Decimal | str | None) -> Decimal | None`, `amount_string(...) -> str | None`의 RED를 작성하고 실행한다. float/int/bool 거부, 유한값, 35/30 경계와 overflow, null 대 zero, 작은 context precision을 다룬다.
- [x] 연산/quantize 없이 tuple/exponent 검증을 구현하고 SQLAlchemy Decimal 타입은 검증된 문자열만 bind한다.
- [x] GREEN을 실행한다.

<a id="task-2-schema-and-final-append"></a>

### 작업 2: 스키마와 Final 추가

파일: 동결된 `migrations/runtime/versions/0003_usage.py`; live `common/usage/schema.py`; `common/usage/repository.py`; `tests/common/usage/test_usage_repository_mysql.py`.

인터페이스: `append_final(conn, record: Mapping) -> bool` (삽입 여부 대 동일 여부); `read_final(conn, usage_id) -> dict | None`; `UsageIdentityConflict`.

- [x] 실제 MySQL RED 테스트를 작성한다. 기존 행이 있는 이전 head upgrade, 스키마/메타데이터 동등성, typed CHECK 거부, 직접 PK 거부, 정확한 amount 왕복, 호출자 커밋/롤백, 전체 중복 스냅샷 비교, 동시성, 실제 COMMIT OK 폐기 proxy를 다룬다.
- [x] 독립 동결 마이그레이션과 메타데이터, 엄격한 허용 목록 검증/projection, INSERT 전용 append/replay를 구현한다.
- [x] GREEN을 실행하고 테스트를 약화하지 않고 기존 마이그레이션 목록/head 기대값을 갱신한다.

<a id="task-3-gate-and-documentation"></a>

### 작업 3: Gate와 문서

파일: `scripts/check_mysql_test_report.py`, `tests/common/db/test_mysql_gate.py`, `tests/common/db/integration/test_migration_gate.py`, common README, Implementation Log.

- [x] usage family 누락과 각 필수 매개변수 누락 RED를 작성하며 부분 family 증거와 JUnit 누락을 포함한다.
- [x] 인수 목록 및 실제 MySQL 중첩 실행/변이 커버리지를 확장한다.
- [x] 실제 MySQL 필수 조건으로 전체 pytest 모음을 실행하고 JSON/JUnit, boundary checker, diff 검사를 독립 검증한다.
- [x] 정확한 명령/결과와 Implementation Notes를 보존하고 검토 manifest/diff를 준비하며 미커밋/unstaged로 둔다. 증거 없이 원격 CI나 독립 검토를 주장하지 않는다.

최종 증거: Runtime Implementation Log RT-07 및 `.codex-scratch/rt07a-20261012/implementation-notes.md`. 전체 실행에는 기존 API blocker-rollback 연결 실패 하나가 남았다. 소스를 변경하지 않은 재검사에서는 이미 통과한 중첩 보고서 변이 테스트만 제외하고 5,022개 테스트가 통과했으며 비 MySQL skip 26개가 있었다. 실제 중첩 모음과 회귀 재검사는 각각 skip=0/xfail=0으로 445-test MySQL gate를 통과했다. usage 80×7=560을 포함한 실제 보고서 매개변수 변이 2,093개를 모두 거부했다. 읽기 전용 검토자가 독립 SELECT probe와 기존 GREEN 증거로 PAD SPACE 보정을 확인했다. 검토자 pytest 실행은 주장하지 않는다.
