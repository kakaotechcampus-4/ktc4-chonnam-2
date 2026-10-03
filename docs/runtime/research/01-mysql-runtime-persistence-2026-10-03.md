# Research Result — MySQL Runtime Persistence

**Status:** Evidence — 외부 기술 조사 결과 · **보조 검토 완료 2026-10-03 · Owner 확인 전** — 정정 사항은 [Review notes](#review-notes-2026-10-03)가 본문보다 우선\
**Owner:** common/runtime — 김준영\
**Workflow step:** [`runtime-ops-workflow.md`](../runtime-ops-workflow.md) §4 Decision-driven 외부 기술 조사\
**Prompt:** [`prompts/01-mysql-runtime-persistence.md`](./prompts/01-mysql-runtime-persistence.md)\
**Decisions:** [RD-01](../open-decision-register.md#rd-01--runtime-persistence--queue-physical-design) (01b · 01c · 01d · 01g · 01j)\
**조사 기준일:** 2026-10-03

> 이 문서는 Decision 근거이며 결정이 아니다. 내용은 Owner 검토를 거쳐 Spec · Contract · ADR로 옮겨질 때만 효력이 있다. 외부 자료의 숫자는 대신고 baseline이 아니다.

## Review notes (2026-10-03)

> 이 절이 본문보다 우선한다. 본문은 조사 원문 그대로 두었다. 검토는 Claude Code 보조 검토이며 Owner 최종 확인 전이다. **★** = 검토 뒤 원문(공식 문서 · repo)을 다시 열어 재확인한 항목, 표시 없음 = 검토 단계에서 인용 출처와 대조한 항목.

**판정:** 아래 정정을 반영하면 RD-01b · 01c · 01d · 01g · 01j의 Decision 근거로 쓸 수 있다. 출처 대조 31건 — 일치 24 · 부분 일치 5 · 인용 출처에 없음 1 · 확인 불가 1 · **반대 0**. 최종 선택 문장 · 외부 숫자의 baseline화 · 범위 밖 내용은 없다.

### 정정 · 보완

| Sev | 본문 위치 | 정정 | 근거 |
| --- | --- | --- | --- |
| High | §1 · §3 「`SKIP LOCKED`는 gap locking을 없애지 않는다」 | **Verified fact가 아니다.** 인용한 공식 문서는 `SKIP LOCKED`와 gap · next-key lock의 관계를 명시하지 않는다(WL#8919도 row lock 대상만 말한다). Interpretation · 「문서에 명시 없음」으로 읽고, `performance_schema.data_locks`를 보는 spike(§8 Spike A)로 확인한다. RD-01b 핵심 질문이다 | [innodb-locking-reads](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html) · [innodb-locks-set](https://dev.mysql.com/doc/refman/8.4/en/innodb-locks-set.html) · [WL#8919](https://dev.mysql.com/worklog/task/?id=8919) |
| Med | §1 LIMIT · filesort와 lock 범위 | 출처는 innodb-locks-set이 아니라 limit-optimization이고 그 페이지는 lock을 말하지 않는다 → 두 문서를 합친 Interpretation. 원문은 filesort일 때 「LIMIT 없이 일치하는 모든 row를 select한다」로, 본문의 「넓게 읽을 수 있다」보다 강하다 | [limit-optimization](https://dev.mysql.com/doc/refman/8.4/en/limit-optimization.html) |
| Med | §1 · §3 · §4.2 `READ COMMITTED` | 누락: RC에서는 WHERE 평가 뒤 조건에 맞지 않는 row의 record lock을 해제하고, UPDATE는 semi-consistent read를 쓴다. lock footprint와 Pattern B(조건부 UPDATE)의 대기 동작을 바꾼다. RC 문장의 출처도 isolation-levels 페이지로 바꿔 읽는다 | [innodb-transaction-isolation-levels](https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html) |
| Med | §1 · §4.2 Solid Queue | 누락: README는 MySQL/MariaDB에서 heavy load 시 `READ COMMITTED` 고려를 권하고 Solid Queue 자체 table에는 안전하다고 쓴다 — **그 환경의 사실**이다. §4.2 SQL 예시의 `FOR UPDATE SKIP LOCKED`는 README 원문이 아니다. 공식 deadlock 문서의 「deadlock 가능성은 isolation level의 영향을 받지 않는다」와의 긴장도 함께 본다 | [rails/solid_queue](https://github.com/rails/solid_queue) · [innodb-deadlocks](https://dev.mysql.com/doc/refman/8.4/en/innodb-deadlocks.html) |
| Med | §3 표 | Evidence 열에 URL이 없는 Verified fact 행이 9건이다. 해당 행은 출처가 붙기 전까지 Interpretation 수준으로 읽는다 | prompt 출력 원칙 |
| Med | §1 multi-valued index | 출처는 json-validation-functions가 아니라 create-index다. 누락: 문자열 값은 `utf8mb4_0900_as_cs`(또는 binary) collation만 지원하고, 빈 배열은 index로 찾을 수 없다. `produced` · `usage_refs`의 ID가 문자열이라 RD-01c · 01d에 직결된다 | [create-index](https://dev.mysql.com/doc/refman/8.4/en/create-index.html) |
| Med | §4.8 · §4.9 MySQL Connector/Python | SQLAlchemy 문서가 이 driver에 대해 「frequent, major regressions」 · CI 제외 · server-side cursor 비활성을 경고한다. 본문은 「제한 사항도 기술」로 축소했다 | [SQLAlchemy MySQL dialect](https://docs.sqlalchemy.org/en/21/dialects/mysql.html) |
| Med | §4.7 · §7 `token_usage` · `pricing_context` | **Contract에 이미 고정된 부분이 있다.** `token_usage`는 `input/output/total` 세 필드이고 「객체 전체 null이거나 세 필드 모두 존재」(§8-3), `pricing_context`는 `pricing_id` · `unit` key를 갖는다. 열린 것은 opaque 확장 영역뿐이다 — §7의 해당 항목은 이 범위로 좁혀 읽는다 ★ | [`contract-usage-record.md`](../../architecture/contracts/contract-usage-record.md) §4 · §8 |
| Med | §4.6 · §7 `Money` | Contract는 `amount`를 `"decimal string \| null"`로 두고 예시가 `"184.20"` KRW다. 「소수 KRW 허용 여부」가 이미 닫혔는지는 **확인 필요** — 여기서 채우지 않는다 ★ | 같은 Contract L81 · L130 |
| Med | §2 Q1.6 | AUTO_INCREMENT lock mode를 다루지 않았다 → 아래 「보완 확인」 | prompt Q1.6 |
| Med | §4.11 · §4.13 Alembic | Alembic의 동시 실행 lock 여부를 적지 않았다. 공식 문서에 명시 없음 → api · worker가 동시에 migration을 시도하는 경쟁은 spike(§8 Spike H)로 확인한다 | [Alembic branches](https://alembic.sqlalchemy.org/en/latest/branches.html) |
| Low | 여러 곳 | Solid Queue 「MySQL 8.4 deadlock 사용자 보고」에 issue 링크 없음(§9) · Liquibase 최신은 5.0.4(2026-08-20)이고 5.0부터 Community가 FSL license · Atlas는 확인 가능(v1.3.0, 2026-08-02, repo Apache-2.0 — 배포 binary EULA는 미확인) · yoyo 9.0.0은 2024-08-10, aiomysql 최근 release 2025-10(유지보수 근거) · §4.9 「sync DB layer와 자연스럽게 맞는」은 기울기 표현 · §7 상태 전이 경합은 `QUEUED→CANCELLED`만 다루고 `RUNNING→CANCELLED`는 빠짐 | PyPI · Maven Central · GitHub |

### 보완 확인 (검토 단계 추가)

- **AUTO_INCREMENT lock mode (Q1.6)** ★ — MySQL 8.4 기본값은 `innodb_autoinc_lock_mode=2`(interleaved)다. 이 모드에서는 INSERT 계열 statement가 table-level `AUTO-INC` lock을 쓰지 않고 동시에 실행되며, 값은 unique · 단조 증가지만 statement 안에서 연속적이지 않을 수 있다. statement-based replication에서는 안전하지 않고 row-based · mixed에서는 안전하다. ([innodb-auto-increment-handling](https://dev.mysql.com/doc/refman/8.4/en/innodb-auto-increment-handling.html))
  - Daesingo implication — JobExecution 등의 PK를 AUTO_INCREMENT로 둘지는 RD-01a · 01b에서 열려 있다. 둔다면 기본 설정에서는 claim transaction 안 INSERT가 table-level AUTO-INC lock으로 직렬화되지 않는다. 남는 lock은 본문 §4.1의 insert intention · unique · FK lock이다.

### Decision 입력으로 옮길 때

- prompt에 넣지 않았던 Contract 사실을 함께 본다: UsageRecord row는 append-only(§8-1), 실제 invocation이 시작된 호출에만 row 생성(§8-14), `run_ref`가 `usage_refs`보다 authoritative(§8-11 · 12 — RD-01d의 선례 입력).

---

**기준 환경: MySQL 8.4 LTS / InnoDB · Python 3.12**

---

## 1. Executive Summary

- **Verified fact — RD-01b:** MySQL 8.4의 `SELECT ... FOR UPDATE SKIP LOCKED`에서 `SKIP LOCKED`는 획득할 수 없는 **row-level lock을 기다리지 않고 해당 row를 결과에서 제외**한다. MySQL은 그 결과가 일관된 DB view가 아니므로 일반적인 transactional query에는 적합하지 않을 수 있으나, queue-like table에는 사용할 수 있다고 명시한다.\
  Source: https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html
- **Verified fact — RD-01b:** `SKIP LOCKED`가 gap locking을 없애는 것은 아니다. InnoDB locking read 자체는 검색에 사용된 index record를 잠그며, 기본 `REPEATABLE READ`에서는 범위 검색에 next-key lock이 사용될 수 있다. `READ COMMITTED`에서는 일반 search/index scan의 gap locking이 비활성화되고 FK/duplicate-key 검사는 예외다.\
  Source: https://dev.mysql.com/doc/refman/8.4/en/innodb-locks-set.html
- **Interpretation — RD-01b:** 따라서 `LIMIT 1`이라는 이유만으로 실제 lock footprint가 1 row라고 볼 수 없다. 어떤 index를 어떤 방향으로 scan하는지, filesort가 필요한지까지 claim query의 동시성 semantics 일부가 된다.
- **Verified fact — RD-01b:** MySQL은 locking statement가 일반적으로 **검색 중 scan한 index records**에 lock을 건다고 설명한다. 적절한 index가 없어서 full scan이 되면 사실상 모든 row가 잠길 수 있다. 반대로 `ORDER BY`를 index로 충족하면서 `LIMIT`을 사용할 경우 필요한 row 수만 찾고 scan을 조기에 끝낼 수 있다. filesort가 필요하면 `LIMIT`을 적용하기 전에 matching rows를 넓게 읽고 정렬할 수 있다.\
  Source: https://dev.mysql.com/doc/refman/8.4/en/innodb-locks-set.html
- **Verified fact — RD-01b:** Solid Queue도 MySQL 8+에서 `FOR UPDATE SKIP LOCKED`와 정렬 가능한 covering index를 사용한다. 프로젝트 문서는 MySQL/MariaDB의 기본 `REPEATABLE READ`에서 polling index에 걸리는 gap lock 때문에 enqueue와 claim/dispatch 사이에 간헐적 deadlock이 발생할 수 있다고 설명한다. 이는 Solid Queue 환경에서의 관찰이지 대신고 baseline 값은 아니다.\
  Source: https://github.com/rails/solid_queue/
- **Interpretation — RD-01b:** claim 상태 변경과 `JobExecution(RUNNING)` INSERT를 하나의 DB transaction에 넣으면 두 DB 변경의 commit/rollback 경계는 일치한다. 다만 INSERT가 FK check, unique check, secondary-index update 등을 추가하므로 transaction의 lock graph는 claim row 하나보다 복잡해진다.
- **Daesingo implication — RD-01b:** commit 이후 실제 ffmpeg/API 작업을 시작하기 전에 Worker가 죽는 구간은 DB transaction만으로 제거되지 않는다. 현재 논리 모델에서는 이미 committed 된 `RUNNING` execution이므로 lease expiry → stale sweep이 이 구간의 recovery mechanism이 된다.
- **Verified fact — RD-01c/d/g:** MySQL 8.4 JSON은 `JSON_SCHEMA_VALID()`을 `CHECK`에 활용할 수 있고, generated column index와 multi-valued JSON index도 제공한다. 그러나 JSON 내부 reference에 FK를 거는 일반적인 관계형 제약은 제공하지 않으며 multi-valued index 역시 FK에 사용할 수 없고 covering/range/order index로도 제약이 있다.\
  Source: https://dev.mysql.com/doc/refman/8.4/en/json-validation-functions.html
- **Verified fact — RD-01g:** MySQL `DECIMAL`은 exact numeric type이며 precision은 최대 65 digits까지 지원한다. JSON property가 단순히 numeric이라는 사실만으로 `DECIMAL(M,D)` column과 같은 명시적 금액 scale constraint가 생기는 것은 아니다.\
  Source: https://dev.mysql.com/doc/refman/8.4/en/precision-math-decimal-characteristics.html
- **Verified fact — RD-01j:** MySQL 8.4의 atomic DDL은 **하나의 지원 DDL statement**가 dictionary/storage engine/binlog 사이에서 전부 commit되거나 rollback된다는 의미이다. 여러 DDL로 구성된 migration 전체가 transaction이 되는 것은 아니며 DDL은 implicit commit을 일으킨다.\
  Source: https://dev.mysql.com/doc/refman/8.4/en/atomic-ddl.html
- **Daesingo implication — RD-01j:** migration tool을 고르더라도 `ALTER A` 성공 후 `ALTER B` 실패 같은 MySQL migration의 부분 적용 가능성이 사라지는 것은 아니다. version table, repair, rollback SQL, 실패 후 재실행 semantics가 별도의 비교축이 된다.

이 조사만으로 `SKIP LOCKED`/isolation level/JSON/ORM/migration tool 중 하나를 최종 선택할 수 있는 상태는 아니다. 특히 **실제 claim schema와 index를 사용한 동시성 spike**가 RD-01b의 남은 핵심 입력이다.

---

## 2. Questions Investigated

### Q1 — RD-01b

다음을 확인했다.

1. InnoDB record/gap/next-key lock과 `SKIP LOCKED` 관계
2. `REPEATABLE READ`와 `READ COMMITTED`의 차이
3. `WHERE + ORDER BY + LIMIT`과 index/filesort가 scan·lock 범위에 미치는 영향
4. claim과 heartbeat / stale sweep / cancel UPDATE의 경쟁
5. `SKIP LOCKED`, conditional UPDATE, optimistic CAS claim의 semantics 차이
6. claim + `RUNNING` INSERT transaction과 crash/commit 경계
7. MySQL 공식 `SKIP LOCKED` 주의사항
8. 실제 MySQL-backed queue인 Solid Queue의 query/index/isolation 사례

### Q2 — RD-01c · RD-01d · RD-01g

`produced`, `usage_refs`, `Money`, `pricing_context`, `token_usage`에 대해 다음을 확인했다.

- JSON / scalar columns / child table / projection
- query와 aggregation
- CHECK / FK / UNIQUE
- generated index / multi-valued index
- numeric precision
- schema evolution / online DDL
- append-only ledger integrity
- SQL 운영 진단 가능성

### Q3 — RD-01j

다음을 확인했다.

- Python 3.12 MySQL driver 현황
- sync/async DB layer
- raw SQL / SQL toolkit / ORM
- 장시간 process connection lifecycle
- Alembic / yoyo / Flyway / Liquibase / Atlas / 자체 SQL migration
- MySQL atomic DDL와 implicit commit
- Compose one-off / migration service / application-startup migration

---

## 3. Verified Technical Facts

| Fact | Version / Condition | Evidence |
|---|---|---|
| `FOR UPDATE`는 검색하면서 만난 row/index entry를 update와 유사하게 잠근다. | MySQL 8.4 / InnoDB | **Verified fact.** https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html |
| 검색에 사용할 적절한 index가 없으면 locking statement가 모든 row를 scan/lock할 수 있다. | MySQL 8.4 / InnoDB | **Verified fact.** https://dev.mysql.com/doc/refman/8.4/en/innodb-locks-set.html |
| unique index로 단일 row를 정확히 찾는 경우 record lock만으로 좁아질 수 있다. 범위/비unique 검색에는 next-key locking이 사용될 수 있다. | `REPEATABLE READ` | **Verified fact.** https://dev.mysql.com/doc/refman/8.4/en/innodb-locking.html |
| gap lock은 purely inhibitive하여 주로 해당 gap으로의 INSERT를 막으며 gap S/X끼리는 충돌하지 않는다. | InnoDB | **Verified fact.** https://dev.mysql.com/doc/refman/8.4/en/innodb-locking.html |
| `SKIP LOCKED`는 row lock을 기다리는 대신 locked row를 결과에서 제외한다. | MySQL 8.4 | **Verified fact.** https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html |
| `SKIP LOCKED`는 gap/next-key locking 자체를 disable하는 옵션이 아니다. | RR/RC 차이와 결합 | **Verified fact + interpretation.** Locking rules는 그대로 적용되며 `SKIP LOCKED` 문서는 row-level lock에 대한 skip을 정의한다. |
| `SKIP LOCKED` 결과는 inconsistent view일 수 있다. | MySQL 8.4 | **Verified fact.** MySQL이 queue-like table을 사용 사례로 직접 언급한다. |
| `SKIP LOCKED`/`NOWAIT`는 statement-based replication에 unsafe다. | MySQL 8.4 | **Verified fact.** https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html |
| InnoDB 기본 isolation은 `REPEATABLE READ`. | MySQL 8.4 | **Verified fact.** https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html |
| RR consistent read는 transaction snapshot을 사용할 수 있지만 locking read는 현재 lock 가능한 DB state를 대상으로 한다. | RR | **Verified fact.** 동일 transaction에서 일반 snapshot SELECT와 locking SELECT를 혼합하면 서로 다른 state를 관찰할 수 있다. |
| RC에서는 각 consistent read가 새 snapshot을 얻으며 ordinary search/index scan의 gap locks가 비활성화된다. FK/duplicate-key 검사는 예외다. | RC | **Verified fact.** https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html |
| index가 `ORDER BY`를 충족하면 `LIMIT`과 함께 scan을 조기에 끝낼 수 있다. | Query plan dependent | **Verified fact.** https://dev.mysql.com/doc/refman/8.4/en/limit-optimization.html |
| filesort가 필요하면 LIMIT 이전에 matching rows를 넓게 읽고 정렬할 수 있다. | Query plan dependent | **Verified fact.** https://dev.mysql.com/doc/refman/8.4/en/limit-optimization.html |
| 동일 ORDER BY key끼리의 순서는 추가 unique tiebreaker가 없으면 deterministic하지 않을 수 있다. | MySQL | **Verified fact.** https://dev.mysql.com/doc/refman/8.4/en/limit-optimization.html |
| deadlock detection은 기본적으로 활성화되어 있고 victim transaction을 rollback한다. | InnoDB | **Verified fact.** https://dev.mysql.com/doc/refman/8.4/en/innodb-deadlocks.html |
| deadlock과 달리 일반 lock wait timeout은 기본적으로 waiting statement만 rollback할 수 있으며 transaction 전체 rollback과 동일하지 않다. | default behavior | **Verified fact.** `innodb_rollback_on_timeout` 설정에 따라 달라질 수 있다. |
| INSERT는 insert-intention gap lock과 새 index record X lock을 사용한다. | InnoDB | **Verified fact.** https://dev.mysql.com/doc/refman/8.4/en/innodb-locks-set.html |
| FK 검사에서는 검사 대상 record에 shared record lock이 걸린다. | InnoDB | **Verified fact.** https://dev.mysql.com/doc/refman/8.4/en/innodb-locks-set.html |
| duplicate-key 검사 경로도 lock 및 deadlock의 원인이 될 수 있다. | InnoDB | **Verified fact.** https://dev.mysql.com/doc/refman/8.4/en/innodb-locks-set.html |
| InnoDB lock은 transaction commit/abort 시 해제된다. | InnoDB | **Verified fact.** https://dev.mysql.com/doc/refman/8.4/en/innodb-locks-set.html |
| JSON Schema validation을 `CHECK`와 결합할 수 있다. | MySQL 8.4 | **Verified fact.** Draft 4 기반이며 일부 JSON Schema 기능에는 제한이 있다. |
| `JSON_TABLE()`로 JSON 배열/객체를 typed relational rows로 펼칠 수 있다. | MySQL 8.4 | **Verified fact.** https://dev.mysql.com/doc/refman/8.4/en/json-table-functions.html |
| JSON column 자체를 일반 B-tree처럼 직접 index하지 않고 generated/extracted value를 index하는 패턴을 지원한다. | MySQL 8.4 | **Verified fact.** https://dev.mysql.com/doc/refman/8.4/en/create-table-secondary-indexes.html |
| multi-valued index는 JSON arrays의 membership query를 지원한다. | MySQL 8.4 | **Verified fact.** `MEMBER OF`, `JSON_CONTAINS`, `JSON_OVERLAPS` 등이 대상이다. |
| multi-valued index는 FK에 쓸 수 없고 covering index가 아니며 ordering/range/index-only access에 제약이 있다. | MySQL 8.4 | **Verified fact.** 생성 시 online `ALGORITHM=INPLACE`가 아니라 `COPY`가 필요한 제약도 있다. |
| `DECIMAL`은 exact numeric type이다. | MySQL 8.4 | **Verified fact.** 최대 precision 65 digits. |
| 여러 `ALTER TABLE` 변경 중 일부는 `ALGORITHM=INSTANT`가 가능하지만 type 변경이나 구조에 따라 rebuild/copy가 필요하다. | MySQL 8.4 | **Verified fact.** https://dev.mysql.com/doc/refman/8.4/en/innodb-online-ddl-operations.html |
| atomic DDL은 transactional DDL이 아니다. | MySQL 8.4 / InnoDB | **Verified fact.** DDL은 active transaction을 implicit commit하며 여러 statement를 하나의 transaction으로 묶지 못한다. |

---

## 4. Options / Patterns

### 4.1 RD-01b — Claim patterns

#### Pattern A — `SELECT ... FOR UPDATE SKIP LOCKED` → ownership UPDATE → `JobExecution(RUNNING)` INSERT → COMMIT

**Verified fact**

`SKIP LOCKED`는 다른 worker가 row lock을 잡고 있는 candidate를 기다리지 않고 건너뛸 수 있다. 해당 transaction은 commit/rollback 전까지 획득한 InnoDB lock을 유지한다.

Source: https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html

**Interpretation**

장점이 되는 semantics는 “candidate 선택 → claim metadata 변경 → RUNNING ledger row 생성”을 동일 DB transaction 안에 넣을 수 있다는 것이다. transaction이 commit되지 않으면 세 DB 작업 전체가 확정되지 않는다.

반대쪽 trade-off는 transaction이 다음과 같은 lock을 동시에 보유할 수 있다는 점이다.

- queue candidate record/next-key locks
- claim UPDATE가 변경하는 secondary-index entries
- `JobExecution` INSERT의 record/insert-intention locks
- unique-key 검사 locks
- FK가 있으면 referenced parent locks

따라서 deadlock graph가 단순한 “worker A와 worker B가 queue row 하나를 경쟁”하는 것보다 넓어진다.

**Daesingo implication — RD-01b**

exact transaction 안에서 `queue → execution` 순으로 접근한다면 heartbeat/sweep/cancel 및 다른 code path가 반대 순서인 `execution/job → queue`를 취하는지까지 확인 대상이다.

#### Pattern B — Conditional single UPDATE + claim token

개념적으로 candidate에 `owner/token`을 쓰는 조건부 UPDATE를 먼저 수행하고, 성공한 token을 다시 조회하는 방식이다.

**Interpretation**

- ownership 변경 자체는 하나의 DML statement로 확정할 수 있다.
- `SKIP LOCKED` locking read와 달리 대상 row가 이미 X-locked 되었을 때 우회보다 lock wait가 발생하는 query plan이 가능하다.
- `JobExecution(RUNNING)` 생성이 별도 transaction이면 ownership과 execution ledger 사이에 crash window가 생긴다.
- 둘을 같은 transaction에 넣으면 다시 Pattern A와 유사한 INSERT lock graph가 생긴다.

즉 “SELECT가 없으므로 경쟁이 사라진다”는 의미는 아니다.

#### Pattern C — Optimistic CAS/version claim

1. candidate를 읽고
2. `UPDATE ... WHERE id=? AND version=? AND <still eligible>` 형태로 ownership 획득을 시도하고
3. affected row가 0이면 경쟁에서 진 것으로 처리하는 방식이다.

**Interpretation**

candidate read와 claim write 사이에 row lock을 계속 유지할 필요가 없는 대신, 여러 worker가 같은 candidate를 읽고 CAS에서 경쟁할 수 있다. correctness는 version뿐 아니라 `status`, `available_at`, lease 조건 등 필요한 eligibility predicate가 UPDATE에 다시 포함되는지에 의존한다.

경쟁이 많은 환경에서는 failed CAS/retry 횟수가 늘어날 수 있다.

### 4.2 RD-01b — Isolation level

#### `REPEATABLE READ`

**Verified fact**

범위/비unique locking search에 next-key locking이 사용될 수 있다.

Source: https://dev.mysql.com/doc/refman/8.4/en/innodb-locking.html

**Interpretation**

queue index에서 “현재 실행 가능한 row들”을 range로 찾는 구조라면 claim이 기존 row뿐 아니라 index gap에 영향을 주어 동시에 enqueue되는 새로운 entry의 insert-intention lock과 만날 가능성이 있다.

Solid Queue가 실제 MySQL queue에서 문서화한 문제가 이 유형이다. Solid Queue는 다음 형태의 query를 사용한다.

```sql
SELECT job_id
FROM solid_queue_ready_executions
ORDER BY priority ASC, job_id ASC
LIMIT ?
FOR UPDATE SKIP LOCKED;
```

또는 queue name equality filter를 추가한다. polling query가 covering index를 사용하도록 schema/query를 제한하고 있으며, 기본 RR에서 gap lock에 의해 enqueue와 claim/dispatch가 deadlock될 수 있다고 프로젝트 문서에 명시되어 있다.

Source: https://github.com/rails/solid_queue/

이는 Solid Queue 환경의 근거이며 대신고에서 동일한 발생률이나 load threshold를 의미하지 않는다.

#### `READ COMMITTED`

**Verified fact**

normal search/index scan의 gap locks가 감소하고 각 consistent read가 새로운 snapshot을 얻는다. FK 및 duplicate-key check에는 gap-related locking 예외가 남는다.

Source: https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html

**Daesingo implication — RD-01b**

RD-01b는 “claim SQL”만 결정해서 닫히는 항목이 아니라 다음 묶음으로 검증할 성격이다.

```text
claim predicate + ORDER BY + composite index + isolation level + writer access order
```

### 4.3 RD-01b — `ORDER BY`, `LIMIT`, index

가령 논리적으로 다음 형태를 생각할 수 있다.

```sql
WHERE <eligible predicates>
ORDER BY <eligibility time>, <stable unique tiebreaker>
LIMIT 1
FOR UPDATE SKIP LOCKED
```

이는 exact query 제안이 아니라 조사용 형태다.

**Verified fact**

InnoDB lock 범위는 SQL 결과 row 수보다 **index scan 범위**와 더 직접 연결된다.

Source: https://dev.mysql.com/doc/refman/8.4/en/innodb-locks-set.html

**Interpretation**

- 실제 WHERE와 ORDER BY를 하나의 index scan으로 만족하고 첫 candidate에서 stop하면 lock footprint가 좁아질 여지가 있다.
- 적절한 ordering index가 없어 filesort가 필요하면 더 많은 qualifying rows가 LIMIT 이전에 읽히므로 lock footprint가 커질 가능성이 있다.
- 다만 MySQL 문서는 모든 optimizer plan별 “최종적으로 commit까지 정확히 몇 개의 record lock이 남는다”를 공식 표로 규정하지 않는다.

따라서 최종 schema에서 `EXPLAIN`만 확인하는 것과 실제 `performance_schema.data_locks`를 보는 것은 서로 다른 검증이다.

**Fairness interpretation**

`SKIP LOCKED`는 이미 잠긴 앞쪽 row를 우회한다. 따라서 stable `ORDER BY`를 사용해도 “모든 worker를 통틀어 strict FIFO”를 보장하지는 않는다.

특정 앞쪽 row가 계속 다른 transaction에 의해 잠겨 있다면 뒤 row들이 먼저 소비될 수 있다. starvation의 현실적 발생 가능성은 workload-dependent다.

### 4.4 RD-01c — `JobExecution.produced`

#### JSON array

예:

```json
[
  {"kind": "clip", "ref": "..."},
  {"kind": "overlay", "ref": "..."}
]
```

**Trade-off**

- execution 하나를 읽을 때 한 column으로 가져오기 쉽다.
- element shape가 추가되어도 table DDL 없이 JSON shape를 확장할 수 있다.
- JSON Schema CHECK로 기본 구조 검증을 넣을 수 있다.
- cross-execution `kind/ref` 검색은 `JSON_TABLE`, generated column 또는 MVI 같은 별도 접근법이 필요하다.
- JSON 내부 `ref`마다 일반 FK를 걸 수 없다.
- 동일 ref 중복이나 `(execution_id, kind, ref)` unique 같은 관계형 invariant는 child table보다 간접적이다.

#### Child table

개념:

```text
JobExecutionArtifact(
  execution_id FK,
  kind,
  artifact_ref,
  ...
)
```

**Trade-off**

- FK, NOT NULL, composite UNIQUE, 일반 B-tree index로 관계를 직접 표현할 수 있다.
- 사건/기간/종류별 SQL query가 직접적이다.
- execution 한 건을 읽을 때 join/추가 query 및 row 수가 늘어난다.
- element shape 변경이 실제 schema migration으로 이어질 수 있다.

**Daesingo implication — RD-01c**

외부 조사만으로 남는 핵심 질문은 `produced`가 “execution을 열 때만 읽는 작은 metadata blob”인지, 아니면 향후 “모든 execution에서 특정 artifact를 찾는 관계”인지이다.

### 4.5 RD-01d — `usage_refs`

#### Projection from `UsageRecord.execution_ref`

**Interpretation**

`UsageRecord`가 이미 execution FK를 보유한다면

```sql
SELECT id
FROM usage_record
WHERE execution_ref = ?
```

로 `usage_refs`를 계산할 수 있다.

이 경우 physical relationship의 authoritative copy는 한 방향이다. `execution_ref` index 여부가 조회 특성에 직접 영향을 준다.

#### `JobExecution.usage_refs` JSON array

**Trade-off**

execution 단건 read에서는 list 획득이 단순해질 수 있다. 그러나 `UsageRecord.execution_ref`와 동시에 authoritative state로 취급하면 둘의 drift 가능성이 생긴다.

따라서 이 형태를 사용한다면 JSON array의 성격이 authoritative relationship인지, denormalized cache/snapshot인지가 별도 semantic이다.

JSON 내부 UsageRecord ID 각각에 FK를 걸 수 없다는 제약도 남는다.

#### Link child table

관계형 FK/UNIQUE를 사용할 수 있으나, `UsageRecord.execution_ref`와 동일 관계를 다시 표현한다면 두 physical representations의 authority 규칙이 필요하다.

**Daesingo implication — RD-01d**

이미 정해진 “두 방향을 독립된 authoritative 원장으로 유지하지 않는다”는 원칙 때문에 외부 기술 조사보다 **어느 쪽을 projection으로 볼 것인가**가 내부 Decision이다.

### 4.6 RD-01g — `Money`

#### `DECIMAL` amount + currency column

**Verified fact**

MySQL `DECIMAL`은 exact numeric arithmetic/storage를 제공한다.

Source: https://dev.mysql.com/doc/refman/8.4/en/precision-math-decimal-characteristics.html

**Trade-off**

- precision/scale가 schema에 명시된다.
- SQL `SUM`, comparison, range query가 직접적이다.
- `currency`에 CHECK/별도 constraint를 두기 쉽다.
- scale/maximum amount 변경은 schema change가 될 수 있다.

#### Integer minor unit

**Interpretation**

예를 들어 모든 값을 KRW 최소 단위의 integer로 의미 정의한다면 floating-point rounding 없이 정수 arithmetic을 사용할 수 있다.

다만 “1 DB unit이 정확히 무엇을 의미하는가”, 환산 시 rounding policy가 무엇인가는 데이터베이스가 자동으로 결정하지 않는다.

#### JSON `{amount, currency}`

**Trade-off**

- money object를 한 구조체로 저장하기 쉽다.
- JSON Schema를 통한 shape validation은 가능하다.
- SQL aggregation 시 extraction/cast 단계가 추가된다.
- 일반 `DECIMAL(M,D)` column처럼 precision/scale가 column definition 자체에 직접 드러나지 않는다.

**Daesingo implication — RD-01g**

KRW 정규화가 이미 정해져 있으므로 남은 내부 입력은 실제 금액 범위, 소수 KRW 허용 여부, 환산 rounding contract다.

### 4.7 RD-01g — `pricing_context` / `token_usage`

#### JSON

provider별 shape 변화나 추가 metadata를 DDL 없이 보존할 수 있다.

반면 특정 token field를 기간별로 반복 집계한다면 JSON path/`JSON_TABLE` 또는 generated index가 필요하다.

#### Typed columns

예를 들어 stable한 `input_tokens`, `output_tokens` 등이 확정되면 SQL aggregation과 constraints가 직접적이다.

provider-specific field가 지속적으로 추가되면 nullable columns/schema evolution 비용이 생긴다.

#### Hybrid

stable aggregate fields는 columns, provider/pricing-specific context는 JSON에 두는 물리 모델도 기술적으로 가능하다.

**Daesingo implication — RD-01g**

어떤 token fields가 UsageRecord의 장기적인 contract이고 어떤 fields가 provider-specific opaque context인지가 외부 문서가 정할 수 없는 경계다.

### 4.8 RD-01j — Python driver 후보

**확인일: 2026-10-03**

| Driver | 확인 버전 | Python 3.12 | 구현 / license | 확인된 특징 |
|---|---:|---|---|---|
| PyMySQL | 1.2.3, 2026-09-17 | 지원 | Pure Python · MIT | MySQL LTS 지원 표기. `caching_sha2_password`/`sha256_password` 사용 시 RSA extra가 필요한 경우가 문서화됨. |
| mysqlclient | 2.3.0, 2026-09-14 | 지원 | C extension · GPL-2.0-or-later | Linux build 시 client/dev headers와 compiler/pkg-config 의존 가능. |
| MySQL Connector/Python | 26.7.0, 2026-07-29 | 지원 | Oracle connector · GPLv2 + FOSS exception | pure/native distributions 존재. MySQL 8 authentication plugins 문서 제공. |
| aiomysql | 0.3.2, 2025-10-22 | 지원 | async · Pure Python/PyMySQL 기반 · MIT | asyncio 기반 MySQL driver. |
| asyncmy | 0.2.15, 2026-09-21 | 지원 | asyncio · Cython/native wheels · Apache-2.0 | CPython 3.12 wheels 확인. |

Sources:

- https://pypi.org/project/PyMySQL/1.2.3/
- https://pypi.org/project/mysqlclient/
- https://pypi.org/project/mysql-connector-python/26.7.0/
- https://pypi.org/project/aiomysql/0.3.2/
- https://pypi.org/project/asyncmy/

**Interpretation**

대신고 Worker 자체가 `subprocess.run`과 synchronous HTTP를 중심으로 한다는 사실은 sync DB layer의 코드 모델과 자연스럽게 맞는 측면이 있다. 반대로 FastAPI에서 DB I/O까지 async로 구성하고 싶다면 별도 async engine/driver 경로가 가능하다.

두 경로를 혼합할 경우 “같은 repository/model”과 “같은 DB connection API”는 별개의 문제다. async DB API는 event loop/`await`가 필요하며 synchronous Worker에서 그대로 호출할 수는 없다.

### 4.9 RD-01j — Raw SQL / Toolkit / ORM

#### Raw SQL

**Trade-off**

- claim transaction과 exact SQL이 가장 직접적으로 보인다.
- `FOR UPDATE SKIP LOCKED`, optimizer hint 등이 SQL 그대로 남는다.
- connection pool, transaction helper, mapping, schema metadata 등의 공통 기능을 application layer에서 더 많이 담당한다.

#### SQL toolkit / SQLAlchemy Core

현재 SQLAlchemy 2.1 계열은 Python 3.12를 지원하며 MySQL dialect에 mysqlclient, PyMySQL, asyncmy, aiomysql 등을 제공한다. Connector/Python dialect에 대해서는 upstream driver 변화와 관련한 제한 사항도 공식 문서에 기술되어 있다.

Source: https://docs.sqlalchemy.org/en/21/dialects/mysql.html

**Trade-off**

- connection pool, transaction scope, type conversion, composable SQL을 제공한다.
- queue hot path만 textual/raw SQL로 내리는 혼합도 가능하다.
- 실제 generated SQL이 의도한 claim query와 동일한지는 별도 확인 대상이다.

#### ORM

**Trade-off**

- JobRecord / JobExecution / UsageRecord 관계를 object mapping으로 표현할 수 있다.
- claim처럼 lock/transaction boundary가 correctness의 일부인 code에서는 Session autoflush, implicit query, transaction lifecycle까지 관찰 대상이 된다.
- JSON object의 in-place mutation tracking도 ORM-specific behavior가 추가될 수 있다.

어느 abstraction도 `SKIP LOCKED` correctness 자체를 대신 보장하지는 않는다.

### 4.10 RD-01j — Long-running Worker connection

**Verified fact**

MySQL `wait_timeout`은 noninteractive connection이 idle 상태로 유지될 수 있는 시간을 제한하며 session 값은 global 설정에서 초기화된다.

Source: https://dev.mysql.com/doc/refman/8.4/en/server-system-variables.html

SQLAlchemy의 `pool_pre_ping` 같은 기능은 pool checkout 시 connection viability를 검사하고 끊어진 connection을 교체할 수 있다. 그러나 **transaction 도중** connection이 끊긴 경우 현재 transaction 자체를 복구해 주지는 않는다.

Source: https://docs.sqlalchemy.org/en/21/core/pooling.html

**Daesingo implication — RD-01j**

몇 분짜리 영상 처리를 하는 동안 DB connection을 checkout한 채 둘 필요가 있는지와 “DB transaction이 열린 기간”은 분리해서 볼 필요가 있다.

장시간 작업 자체와 장시간 DB transaction은 같은 개념이 아니다.

### 4.11 RD-01j — Migration tools

| Tool / 방식 | Version / current evidence | Version tracking / branching | Rollback · MySQL failure semantics |
|---|---|---|---|
| Alembic | 1.20.0, 2026-09-11 | revision DAG. multiple heads와 merge revision 지원. `alembic_version`이 current revision을 기록. | upgrade/downgrade functions 제공. 단 MySQL DDL 자체의 implicit commit을 transaction으로 바꾸지는 못함. |
| yoyo-migrations | 9.0.0 | SQL/Python migration과 dependency 제공. `_yoyo_*` metadata/locking 사용. | 공식 문서가 MySQL DDL rollback 제한과 오류 후 manual intervention 가능성을 명시. |
| Flyway | 현재 문서에서 13.9.0 계열 확인 | schema history table에 version/checksum/success 상태 기록. | failed migration 후 leftover user objects는 직접 정리해야 할 수 있으며 `repair`는 schema history 수리에 사용된다. |
| Liquibase | Community 5.0/5.0.3 문서 확인 | `DATABASECHANGELOG`, `DATABASECHANGELOGLOCK`. lock table로 한 DB에 동시에 한 updater만 실행. | rollback 지원. formatted SQL은 rollback SQL을 직접 기술한다. |
| Atlas | versioned migration/revision table 및 DB advisory locking 제공 | linear migration history와 checksum file을 중심으로 branch conflict를 다룸. | MySQL DDL의 비transactional migration 특성은 그대로 존재. 현재 exact release/license는 이번 조사에서 확정하지 못함. |
| SQL files + 자체 version table | 자체 구현 | version/checksum/ordering/branch merge 규칙도 자체 정의 | locking, failure recording, repair, downgrade도 별도 구현 영역 |

**Interpretation**

6명이 병렬 branch를 사용하는 조건에서는 단순히 “migration SQL을 실행할 수 있는가” 외에 **두 branch가 동시에 revision을 추가한 뒤 merge되었을 때 history를 어떻게 표현하는가**가 도구 차이가 된다.

Alembic은 이를 multiple heads + merge revision이라는 명시적 DAG 개념으로 표현한다. Flyway류의 선형 version file은 version ordering/conflict를 merge 단계에서 정리하는 형태다.

이는 어느 모델이 더 적합하다는 결론이 아니라 팀의 branch workflow와 맞물리는 차이다.

### 4.12 RD-01j — MySQL migration atomicity

**Verified fact**

MySQL 8.4 atomic DDL의 의미는 한 DDL statement에 대해 data dictionary, InnoDB operation, binary log write가 함께 commit 또는 rollback된다는 것이다. server crash 중에도 지원되는 atomicity를 제공한다.

Source: https://dev.mysql.com/doc/refman/8.4/en/atomic-ddl.html

동시에 MySQL 문서는 명시적으로 다음을 구분한다.

> atomic DDL ≠ transactional DDL

DDL은 기존 transaction을 implicit commit하며 다른 statement와 하나의 transaction에 포함될 수 없다.

**Interpretation**

따라서 migration이

```text
DDL A
DDL B
DDL C
```

이고 A가 성공한 뒤 B가 실패하면, “A+B+C 전체 rollback”이 기본 semantics가 아니다.

migration tool은 이런 상태를 감지·기록·repair하거나 rollback SQL을 제공할 수 있지만 MySQL 자체를 multi-statement transactional DDL DB로 바꾸지는 않는다.

### 4.13 RD-01j — Docker Compose migration execution

#### A. One-off command

`docker compose run`은 service configuration을 이용해 one-off container/command를 실행하는 Compose 기능이다.

Source: https://docs.docker.com/reference/cli/docker/compose/run/

**Semantics**

```text
migration command exit 0
        ↓
api / worker startup
```

처럼 deployment orchestrator가 migration 결과를 직접 gate할 수 있다.

반면 deploy script가 migration 단계를 생략하지 않도록 별도 workflow contract가 필요하다.

#### B. Dedicated migration service

Compose long syntax의 `depends_on`에는 `service_started`, `service_healthy`, `service_completed_successfully` 같은 dependency condition이 존재한다.

Source: https://docs.docker.com/compose/how-tos/startup-order/

따라서 conceptual graph로

```text
mysql healthy
    ↓
migration completed successfully
    ↓
api + worker
```

를 표현할 수 있다.

#### C. Application startup migration

API 또는 Worker startup hook에서 migration runner를 실행하는 형태다.

**Interpretation**

API와 Worker가 동시에 뜨면 둘 다 migration을 시도할 수 있다. 결과는 migration tool의 cross-process locking semantics에 의존한다.

예를 들어 Liquibase는 `DATABASECHANGELOGLOCK`으로 한 instance만 update하게 한다.

Source: https://docs.liquibase.com/secure/user-guide-5-1-1/what-is-the-database-changelog-lock-table

반면 모든 migration tool이 동일한 방식의 global database lock을 제공한다고 일반화할 수 없다.

---

## 5. Failure Modes / Operational Risks

| Failure mode | 발생 조건 | 영향 | 완화 가능성 |
|---|---|---|---|
| 동일 work의 이중 claim | ownership write가 원자적으로 검증되지 않거나 optimistic UPDATE의 affected rows를 무시 | 두 Worker가 같은 작업을 실행 | lock/CAS 조건 및 concurrent test로 검증 가능 |
| Queue가 순간적으로 empty처럼 보임 | eligible rows가 다른 transaction에 lock되어 있고 `SKIP LOCKED`가 모두 제외 | Worker poll이 빈 결과 반환 | `SKIP LOCKED`의 의도된 semantics. 다음 poll과 구분 필요 |
| 예상보다 넓은 lock | WHERE/ORDER를 지원하지 않는 index, broad range scan | enqueue/update blocking 증가 | final index + query plan + `data_locks` spike |
| filesort와 broad scan | ORDER BY를 index로 해결하지 못함 | LIMIT 1인데도 다수 candidate scan 가능 | final query/index 조합 확인 |
| strict FIFO 위반 / starvation 가능성 | 앞 candidate가 지속적으로 lock됨 | 뒤 row가 먼저 claim | fairness requirement 자체를 내부에서 정의 |
| RR gap-lock contention | claim range와 enqueue insert가 같은 index gap 사용 | wait/deadlock | RC 비교 spike 및 actual index 검증 |
| claim ↔ heartbeat/sweep/cancel contention | 동일 queue/execution row를 동시에 UPDATE/lock | skip, wait, deadlock | 공통 state predicate와 access order 검증 |
| INSERT를 추가한 deadlock | claim lock 후 FK/unique parent 접근, 다른 tx가 반대 순서로 접근 | one transaction deadlock victim | lock acquisition order 및 retry semantics 검증 |
| lock wait timeout 뒤 transaction 계속 살아 있음 | deadlock이 아니라 ordinary timeout | 이전 statement의 lock/state가 남을 수 있음 | error handler가 transaction 전체 상태를 명시적으로 처리 |
| Commit result unknown | client가 COMMIT을 보낸 뒤 response 전 연결 유실 | client는 성공/실패를 단정 못 할 수 있음 | durable execution/request key로 reconnect 후 DB 상태 조회하는 패턴 검토 |
| pre-commit Worker/connection crash | transaction 미commit | DB 변화 rollback | transaction semantics로 처리 |
| post-commit / pre-work crash | RUNNING commit 후 실제 처리 전 process 종료 | committed RUNNING이 실행되지 않음 | 현재 설계에서는 lease expiry + stale sweep 영역 |
| 장시간 transaction | 실제 몇 분짜리 work 동안 claim transaction 유지 | queue/index locks 장시간 유지 | 짧은 claim tx와 long tx의 semantics 비교 |
| stale pooled connection | Worker idle 시간이 `wait_timeout` 초과 | checkout/query failure | ping/recycle/reconnect 동작 integration test |
| mid-transaction disconnect | claim tx 중 DB connection 단절 | transaction 유실/error | transaction 전체 재판단 필요. blind COMMIT retry와 구분 |
| JSON dangling reference | `produced`/`usage_refs` JSON 안 ID가 삭제/오류 | referential integrity 약화 | app validation 또는 relational FK option |
| usage relation drift | `execution_ref`와 copied `usage_refs` 둘 다 authority처럼 갱신 | 서로 다른 관계 표시 | authority/projection contract 필요 |
| Money precision mismatch | JSON number 또는 Python numeric conversion contract 불명확 | 비용 원장 rounding 차이 | DECIMAL/integer/JSON round-trip spike |
| partial migration | 여러 MySQL DDL 중 후속 DDL 실패 | 일부 schema만 변경 | 도구별 history/repair/re-run test |
| concurrent migrators | api/worker 두 process가 동시에 migration 실행 | tool별 wait/error/duplicate behavior | tool-level lock spike 또는 single-invoker topology |
| migration branch divergence | 두 branch가 각각 revision 생성 | merge 후 history ordering/conflict | tool별 DAG/version conflict workflow 확인 |

`commit 요청은 server에 도달했지만 client가 성공 응답을 받지 못한 경우`에 대한 위 설명은 **Interpretation**이다. 이번 조사에서 MySQL 공식 문서의 application-level recovery 지침까지 직접 확인되지는 않았다.

---

## 6. Daesingo-specific Implications

### RD-01b — Claim transaction

**Daesingo implication**

RD-01b의 실제 decision input은 최소 다음 묶음이다.

```text
eligibility predicate
+ ORDER BY / deterministic tiebreaker
+ composite index
+ isolation level
+ transaction 안의 UPDATE/INSERT 순서
+ heartbeat/sweep/cancel access order
```

`SKIP LOCKED` 하나만 선택하는 것으로 lock semantics가 확정되지는 않는다.

또한 현재 JobExecution 모델에서 자동 retry는 새로운 row를 만드는 구조이므로 claim transaction 실패와 “실제 execution 실패 후 retry row 생성”을 서로 다른 failure boundary로 구분할 수 있다.

claim + RUNNING INSERT가 같은 transaction이면 **DB-level claim/RUNNING 불일치**를 줄일 수 있지만, commit 뒤 process가 죽는 구간은 여전히 lease/stale lifecycle의 영역이다.

### RD-01c — `produced`

결정에 필요한 내부 질문은 다음 두 가지다.

- artifact references에 DB-level FK/UNIQUE가 필요한가?
- execution 단건 외에 kind/ref를 기준으로 전체 execution을 검색할 일이 있는가?

두 질문의 답에 따라 JSON의 schema-flexibility와 child table의 relational integrity 가치가 달라진다.

### RD-01d — `usage_refs`

이미 `UsageRecord.execution_ref`가 동일 관계를 표현한다면 projection만으로 list를 생성할 수 있다.

따라서 별도 `usage_refs` 저장 여부는 성능 최적화만이 아니라 **authority semantics**의 문제다.

### RD-01g — UsageRecord physical shape

`Money`와 `pricing_context/token_usage`는 같은 이유로 JSON/relational을 선택할 필요가 없다.

- Money: exact arithmetic, scale, aggregation이 주요 축
- token usage: stable aggregate dimensions가 무엇인지가 주요 축
- pricing context: opaque/versioned context의 schema evolution이 주요 축

서로 다른 physical representation을 조합하는 것도 기술적으로 가능하다.

### RD-01j — DB layer

현재 Worker가 대부분 synchronous라는 조건에서는 DB driver 선택과 API DB execution model을 하나의 질문으로 묶지 않아도 된다.

예를 들어 repository는 동일하더라도 API engine과 Worker engine을 따로 구성할 수 있고, 반대로 한 sync stack을 공유하면서 API의 blocking execution을 별도로 관리할 수도 있다.

두 방식의 실제 복잡도는 FastAPI route 구조와 connection pool topology가 있어야 비교할 수 있다.

### RD-01j — Migration

MySQL의 implicit-commit DDL 때문에 migration tool 선택 시 적어도 다음 semantics가 별도 비교축이 된다.

```text
revision graph
history table
concurrent runner locking
failed migration 표시
partial DDL 정리 방식
re-run semantics
downgrade/rollback 표현
```

단순히 “migration 생성 명령이 있는가”만으로는 MySQL failure model 비교가 되지 않는다.

---

## 7. What External Research Cannot Decide

### 내부 합의가 필요한 항목

- queue ordering이 strict FIFO여야 하는지, best-effort ordering이면 되는지
- 동일 `available_at` row들의 tie-breaker 의미
- claim / cancel / heartbeat / stale sweep의 상태 전이 우선순위
- queue metadata table과 JobExecution table 사이 FK 방향
- commit 결과 불확실성에 사용할 durable business/idempotency key
- `produced` reference에 DB FK가 실제 필요한지
- `usage_refs`를 저장한다면 authoritative인지 projection/cache인지
- Money 최대 크기와 scale
- KRW 정규화 후 소수 KRW를 허용하는지
- token usage 중 장기적으로 stable하다고 보는 fields
- DB abstraction을 API와 Worker가 어디까지 공유할지
- migration downgrade를 실제 운영 contract로 둘지

### 실험으로 확인할 항목

- final claim query의 실제 lock footprint
- RR과 RC에서 claim/enqueue/update contention 차이
- intended composite index와 filesort plan 차이
- heartbeat/sweep/cancel이 claim 중인 row를 만났을 때 실제 결과
- FK/unique INSERT를 포함한 transaction의 deadlock graph
- 각 Python driver의 반환 JSON/DECIMAL type
- long-lived Worker connection recovery
- 각 migration tool의 MySQL partial-DDL failure state

### External Input이 필요한 항목

- 향후 다른 모듈이 제공할 `token_usage` 및 `pricing_context` stable schema
- artifact reference의 lifecycle/deletion contract
- API route의 실제 sync/async architecture
- 팀 차원의 dependency/license 제약

---

## 8. Suggested Pre-implementation Checks

### Spike A — Claim lock matrix

실제 candidate table/schema/index를 만든 뒤 두 개 이상의 DB session을 barrier로 동시에 시작한다.

검증 matrix:

```text
RR / RC
× intended composite index / index 제거 / filesort 유도
× claim / heartbeat / stale sweep / cancel / enqueue
```

관찰값:

- 어느 worker가 어느 row를 claim했는지
- duplicate claim 여부
- empty result 여부
- lock wait / deadlock
- `performance_schema.data_locks`
- `performance_schema.data_lock_waits`
- `SHOW ENGINE INNODB STATUS`
- `EXPLAIN`

이는 Worker 수나 timeout baseline을 정하는 실험이 아니라 **query semantics 검증**이다.

### Spike B — Crash boundary

아래 경계를 각각 fault-injection 한다.

```text
1. SELECT FOR UPDATE 후 kill
2. ownership UPDATE 후, COMMIT 전 kill
3. RUNNING INSERT 후, COMMIT 전 kill
4. COMMIT 완료 직후, 실제 작업 시작 전 kill
5. COMMIT request 송신 뒤 response 유실
```

확인 대상은 queue state, JobExecution 존재 여부, lease/stale recovery 결과다.

5번은 network proxy 또는 connection fault를 이용해 “commit outcome unknown” 상황을 별도 취급하는 것이 가능하다.

### Spike C — Writer contention

한 connection이 다음 중 하나의 UPDATE lock을 hold한 상태에서 다른 connection이 claim한다.

- heartbeat/lease UPDATE
- RUNNING → STALE
- QUEUED → CANCELLED

그 뒤 first transaction을 각각 COMMIT/ROLLBACK하고 claim 결과 변화를 기록한다.

### Spike D — JSON vs relational representative query

실제에 가까운 작은 dataset에서 다음 query를 각각 작성한다.

- execution 하나의 모든 produced
- 특정 artifact kind 검색
- execution별 모든 UsageRecord
- 일별/사건별 token 합계
- 비용 합계

JSON/child/projection별 SQL 및 `EXPLAIN`만 비교하고 production threshold는 정하지 않는다.

### Spike E — Money numeric round trip

Python → driver → MySQL → driver → Python 경로에서

- `DECIMAL`
- integer minor unit
- JSON numeric
- JSON string + explicit decimal conversion

을 같은 값 집합으로 round-trip하여 type/precision 차이를 기록한다.

### Spike F — Long-lived connection

테스트 환경에서 의도적으로 짧은 `wait_timeout`을 사용해

1. Worker pool connection idle
2. 다음 checkout
3. transaction 중 connection kill

을 각각 재현한다.

checkout recovery와 mid-transaction recovery를 분리해서 본다.

### Spike G — Migration failure

각 migration 후보에 다음 migration을 적용한다.

```text
DDL A — 성공
DDL B — 의도적 실패
DDL C — 미실행
```

이후 확인:

- 실제 schema
- migration history/version table
- 다음 실행 결과
- repair 명령 존재 여부
- rollback/downgrade 동작

### Spike H — Concurrent migration

동일 empty schema에 migration runner 두 개를 동시에 실행한다.

관찰:

- DB/tool lock 여부
- 두 번째 process가 wait/error/exit 중 무엇을 하는지
- history table 결과
- application startup에서 두 process가 동시에 뜬 경우와 동등한지

---

## 9. Unresolved / Unverified

1. **Final claim schema에서 filesort가 발생할 때 정확히 어떤 record locks가 commit까지 유지되는가**\
   MySQL 문서는 scan과 locking의 일반 규칙은 제공하지만 모든 optimizer plan별 lock set을 완전히 열거하지 않는다. 실제 schema spike 대상이다.

2. **`SKIP LOCKED`와 gap-only lock의 모든 corner case**\
   공식 문서는 `SKIP LOCKED`를 row-level lock skip으로 설명하며 gap lock을 disable한다고 말하지 않는다. gap lock끼리는 서로 충돌하지 않고 insert를 방해한다는 규칙은 확인됐다. final query/index에서 실제 상태는 lock instrumentation 확인 대상이다.

3. **COMMIT response-loss 후 application recovery**\
   “client가 결과를 모른다”는 distributed transaction boundary 해석은 명확하지만, 이번 조사에서 이를 대신고 형태의 recovery algorithm까지 설명하는 MySQL 8.4 공식 문서는 확인하지 못했다.

4. **Solid Queue MySQL 8.4 개별 issue의 root cause**\
   MySQL 8.4 deadlock 사용자 보고가 존재하고 Solid Queue 공식 문서가 RR gap-lock 문제를 별도로 설명하지만, 개별 GitHub issue의 모든 deadlock이 같은 root cause였다고 확정하지 않았다.

5. **Arbitrary JSON numeric literal의 모든 내부 precision 규칙**\
   MySQL exact numeric과 JSON typed value 기능은 확인했으나, 금액 schema를 결정할 정도로 모든 JSON lexical number case의 precision을 일반화하지 않았다.

6. **`asyncmy`의 현재 `caching_sha2_password` 동작 세부사항**\
   Python 3.12/current package는 확인했으나 인증 plugin별 최신 공식 compatibility matrix를 찾지 못했다.

7. **mysqlclient authentication semantics**\
   mysqlclient 자체보다 linked MySQL/MariaDB client library의 기능에 영향을 받는다. 실제 Docker base image/client library 조합에서 확인 대상이다.

8. **Atlas 최신 exact release/license**\
   migration/revision/advisory-lock semantics는 확인했지만 이번 조사에서는 2026-10-03 기준 exact release/license까지 확정하지 않았다.

9. **SQLAlchemy 2.1.x의 최종 claim expression 생성 SQL**\
   MySQL dialect와 transaction API는 확인했지만 대신고의 exact `FOR UPDATE SKIP LOCKED` query가 ORM/Core에서 어떤 SQL로 compile되는지는 integration spike에서 직접 확인하는 편이 근거 수준이 높다.

---

## 10. Sources

### MySQL 8.4

- MySQL 8.4 Reference Manual — Locking Reads\
  https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html
- MySQL 8.4 Reference Manual — InnoDB Locking\
  https://dev.mysql.com/doc/refman/8.4/en/innodb-locking.html
- MySQL 8.4 Reference Manual — Transaction Isolation Levels\
  https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html
- MySQL 8.4 Reference Manual — Atomic Data Definition Statement Support\
  https://dev.mysql.com/doc/refman/8.4/en/atomic-ddl.html
- MySQL 8.4 Reference Manual — JSON Schema Validation Functions\
  https://dev.mysql.com/doc/refman/8.4/en/json-validation-functions.html
- MySQL 8.4 Reference Manual — JSON_TABLE\
  https://dev.mysql.com/doc/refman/8.4/en/json-table-functions.html
- MySQL 8.4 Reference Manual — Multi-Valued Indexes / CREATE INDEX\
  https://dev.mysql.com/doc/refman/8.4/en/create-index.html
- MySQL 8.4 Reference Manual — Fixed-Point Types / DECIMAL\
  https://dev.mysql.com/doc/refman/8.4/en/fixed-point-types.html
- MySQL 8.4 Reference Manual — ORDER BY Optimization\
  https://dev.mysql.com/doc/refman/8.4/en/order-by-optimization.html
- MySQL 8.4 Reference Manual — LIMIT Query Optimization\
  https://dev.mysql.com/doc/refman/8.4/en/limit-optimization.html
- MySQL 8.4 Reference Manual — InnoDB Deadlocks\
  https://dev.mysql.com/doc/refman/8.4/en/innodb-deadlocks.html
- MySQL 8.4 Reference Manual — InnoDB Error Handling\
  https://dev.mysql.com/doc/refman/8.4/en/innodb-error-handling.html
- MySQL 8.4 Reference Manual — Online DDL Operations\
  https://dev.mysql.com/doc/refman/8.4/en/innodb-online-ddl-operations.html
- MySQL 8.4 Reference Manual — Server System Variables\
  https://dev.mysql.com/doc/refman/8.4/en/server-system-variables.html

### Public DB-backed queue implementation

- Rails Solid Queue\
  https://github.com/rails/solid_queue/

### Python / DB access

- PyMySQL 1.2.3\
  https://pypi.org/project/PyMySQL/1.2.3/
- mysqlclient\
  https://pypi.org/project/mysqlclient/
- MySQL Connector/Python 26.7.0\
  https://pypi.org/project/mysql-connector-python/26.7.0/
- aiomysql 0.3.2\
  https://pypi.org/project/aiomysql/0.3.2/
- asyncmy\
  https://pypi.org/project/asyncmy/
- SQLAlchemy MySQL dialect\
  https://docs.sqlalchemy.org/en/21/dialects/mysql.html
- SQLAlchemy Connection Pooling\
  https://docs.sqlalchemy.org/en/21/core/pooling.html

### Migration / Compose

- Alembic\
  https://pypi.org/project/alembic/
- Alembic — Working with Branches\
  https://alembic.sqlalchemy.org/en/latest/branches.html
- yoyo-migrations\
  https://pypi.org/project/yoyo-migrations/
- Flyway Schema History Table\
  https://documentation.red-gate.com/flyway/flyway-concepts/migrations/flyway-schema-history-table
- Flyway Repair\
  https://documentation.red-gate.com/flyway/reference/commands/repair
- Liquibase DATABASECHANGELOGLOCK\
  https://docs.liquibase.com/secure/user-guide-5-1-1/what-is-the-database-changelog-lock-table
- Liquibase rollback commands\
  https://docs.liquibase.com/community/reference-guide-5-0/init-update-and-rollback-commands/what-are-rollback-commands
- Atlas versioned migrations\
  https://atlasgo.io/versioned/apply
- Docker Compose `run`\
  https://docs.docker.com/reference/cli/docker/compose/run/
- Docker Compose startup order / `depends_on` conditions\
  https://docs.docker.com/compose/how-tos/startup-order/

---

## Research Completion Check

| Completion criterion | 결과 |
|---|---|
| `SKIP LOCKED` lock 종류/범위/isolation/index 설명 | 충족. optimizer-specific exact footprint는 spike로 분리 |
| claim + RUNNING transaction crash boundary | 충족. COMMIT response-loss 공식 recovery는 Unresolved 표시 |
| `produced` JSON vs child table | 충족 |
| `usage_refs` stored vs projection | 충족 |
| `Money` / context / token physical shape | 충족 |
| Python 3.12 driver 후보 비교 | 충족 |
| sync/async · ORM/raw trade-off | 충족 |
| migration 도구 비교 | 충족. Atlas exact current release/license만 Unresolved |
| MySQL atomic DDL vs multi-statement migration | 충족 |
| Compose migration semantics | 충족 |
| duplicate/deadlock/commit ambiguity/partial migration failure modes | 충족 |
| 대신고 spike 대상 구분 | 충족 |
| RD-01b/c/d/g/j 연결 | 충족 |
| 최종 기술 선택 | **의도적으로 하지 않음** |
