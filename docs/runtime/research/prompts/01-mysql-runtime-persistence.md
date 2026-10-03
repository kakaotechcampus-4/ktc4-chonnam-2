# Research Prompt 01 — MySQL Runtime Persistence

> **추적 정보** — 이 블록은 조사 대상이 아니다. 결과 문서에서 근거를 Decision ID에 연결하는 데만 쓴다. 아래 문서명은 조사자가 열람할 수 없고 열람할 필요도 없다.
>
> - Source: 대신고 `decision-classification.md` §6 External Research Queue
> - R1 · RD-01b — claim transaction · lock semantics
> - R1 · RD-01c · RD-01d · RD-01g — JSON column vs 관계형 구조
> - R2 · RD-01j — DB 접근 계층 · migration 도구
>
> 사용법: 이 파일 전체를 새 웹 리서치 대화에 그대로 붙여 넣는다.

---

다음 기술 조사를 수행하세요. 주제는 **MySQL 8.4 LTS / InnoDB를 작업 queue와 실행 원장 저장소로 쓸 때의 lock semantics, 구조 값 저장 방식, Python 3.12 DB 접근 계층 · migration 도구 선택지**입니다.

이 조사는 결정을 내리는 작업이 아닙니다. 아래 Decision의 **선택지 · 제약 · failure mode · 검증 항목을 현실화하는 근거**를 모으는 작업입니다. 최종 선택은 별도 단계에서 팀이 합니다.

## 1. 프로젝트 맥락

**대신고**는 블랙박스 영상을 받아 교통법규 위반 신고 자료 준비를 보조하는 서비스입니다. 사용자가 영상을 올리면 서버가 비동기로 영상 변환, 외부 AI API 호출을 통한 후보 구간 탐색, 번호판 판독 등을 실행합니다. 6명 팀의 10주 MVP입니다.

현재 Runtime baseline(이미 정해짐):

- AWS EC2 1대 (t3.medium — 2 vCPU · OS 기준 약 3.7 GiB usable RAM · Ubuntu 24.04 · gp3 50 GiB root EBS)
- Docker Compose로 `api` · `worker` · `mysql` 세 service를 따로 띄운다
- FastAPI API process 1 · Worker process 1. Worker concurrency 초기값은 1이다
- **MySQL 8.4 LTS / InnoDB 테이블을 작업 queue로 쓴다(DB Queue).** Redis · Celery · RabbitMQ · SQS · 별도 DLQ는 baseline이 아니다
- Python 3.12. 현재 의존성에 DB driver · ORM · migration 도구가 하나도 없다
- 배포는 GitHub Actions OIDC → AWS role · SSM Run Command 방향으로 확정됐다

실행 기록의 논리 모델(이미 정해짐 — 조사로 다시 열지 않는다):

- **JobRecord** — 사용자가 요청한 작업 의도(Intent). queue row와 같은 개념이 아니며 status · attempt · lease · cost를 갖지 않는다.
- **JobExecution** — 작업 1회 실행분. status는 `QUEUED` · `RUNNING` · `SUCCEEDED` · `FAILED` · `STALE` · `CANCELLED` 6값이다. 자동 재시도는 같은 `job_id` + 새 `execution_id` + `attempt+1`로 **새 row**를 만들고, 기존 row를 되살리지 않는다.
- **queue scheduling metadata** — 다음 실행 가능 시각(`available_at`), claim owner, lease. Runtime 내부 구현이며 JobExecution 논리 필드가 아니다.
- **UsageRecord** — 외부 AI provider 호출 원장. 실제로 시작된 호출 1건당 1 row, append-only, raw payload를 남기지 않는다.
- STALE recovery: lease가 만료된 RUNNING execution은 `STALE`로 terminal 처리한다. Worker 시작 시 1회 + 주기적으로 stale sweep을 하고, Worker가 여러 개여도 sweep 중복 실행이 안전해야 한다.
- 재시도 backoff 동안 Worker가 `sleep()`으로 실행 슬롯을 붙잡지 않는다. 다음 실행 가능 시각을 기록하고 queue에서 기다린다.

**claim 요구사항(이미 정해짐)** — claim 방식은 다음 다섯 가지를 만족해야 합니다.

1. 동시에 둘 이상의 Worker가 같은 queue item을 정상 claim하지 않는다.
2. claim과 `JobExecution(RUNNING)` 시작 사이의 불일치를 transaction 경계에서 최소화한다.
3. 다음 실행 가능 시각 이전의 item을 잡지 않는다.
4. lease가 유효한 다른 Worker의 실행을 빼앗지 않는다.
5. Worker를 여러 개로 늘려도 claim 알고리즘을 바꾸지 않고 concurrency만 늘릴 수 있어야 한다.

현재 우선 후보는 `SELECT … FOR UPDATE SKIP LOCKED`이지만 **확정이 아닙니다.** exact query와 transaction 경계는 아직 열려 있습니다.

## 2. 이 조사가 근거를 제공할 Decision

| ID | 열린 질문 | 우선순위 |
| --- | --- | --- |
| RD-01b | claim transaction의 exact query · lock 범위 · ORDER BY/LIMIT · commit 시점, claim과 `JobExecution(RUNNING)` 생성의 transaction 경계 | R1 |
| RD-01c | `JobExecution.produced`(이 실행이 만든 산출물 참조 목록)의 물리 저장 — JSON column vs 별도 child table | R1 |
| RD-01d | `JobExecution.usage_refs`(이 실행에 연결된 UsageRecord ID 목록)를 별도로 저장할지, `UsageRecord.execution_ref`에서 조회로 만들지(projection) | R1 |
| RD-01g | UsageRecord row의 물리 shape — `pricing_context` · `token_usage` · `Money`(금액 정밀도, column 분리 vs JSON) | R1 |
| RD-01j | DB 접근 계층(driver · sync/async · ORM 사용 여부)과 migration 도구 · 실행 방식 | R2 |

R1이 먼저입니다. 조사 분량이 부족하면 R1 질문의 깊이를 우선하세요.

## 3. 조사 질문

필요한 경우 인접 질문까지 확인하되, **위 Decision을 닫는 데 필요한 범위로 제한**하세요.

### Q1 (R1 · RD-01b) — MySQL 8.4 InnoDB `SELECT … FOR UPDATE SKIP LOCKED`

1. **lock 종류와 범위.** locking read가 record lock · gap lock · next-key lock 중 무엇을 어느 index record에 거는가. `SKIP LOCKED`가 건너뛰는 대상은 정확히 무엇인가(record lock만인가, gap lock도 영향을 받는가). `SKIP LOCKED` 자체가 gap lock을 거는가.
2. **isolation level 영향.** 기본 `REPEATABLE READ`와 `READ COMMITTED`에서 lock 범위 · gap lock 사용 · 결과 집합이 어떻게 달라지는가. 같은 transaction 안에서 consistent read와 locking read가 섞이면 무엇을 보게 되는가.
3. **WHERE · ORDER BY · LIMIT · index 조합.** status 계열 column + 시각 column으로 필터 · 정렬하고 `LIMIT 1`로 하나를 집을 때:
   - 적절한 composite index가 있을 때와 없을 때 lock이 걸리는 row 범위(반환하지 않은 scan row도 lock되는가)
   - filesort가 개입하면 lock 범위가 어떻게 되는가
   - 정렬 순서가 공정성 · starvation에 주는 영향
4. **여러 Worker의 concurrent claim.** 둘 이상의 session이 같은 query를 동시에 실행할 때 중복 claim · deadlock · lock wait · 빈 결과가 생길 수 있는 조건. `innodb_lock_wait_timeout`과 deadlock detection이 이 패턴에서 어떻게 작동하는가.
   - claim만 같은 row를 건드리는 것이 아니다. **실행 중 heartbeat · lease 갱신 UPDATE, stale sweep UPDATE(RUNNING → STALE), 사용자 중단에 따른 QUEUED → CANCELLED UPDATE**가 claim과 같은 row · 같은 index 범위에서 동시에 일어날 수 있다. 이 writer들과 claim이 lock으로 서로 막거나 deadlock을 만드는 조건, `SKIP LOCKED` 때문에 claim이 「방금 취소된 row」나 「sweep 중인 row」를 어떻게 보게 되는지 확인하세요.
5. **비교 대상 claim 패턴.** `SELECT … FOR UPDATE SKIP LOCKED` 후 `UPDATE`, 조건부 단일 `UPDATE … WHERE … LIMIT`(claim token 기록 후 조회), version column 기반 optimistic claim 등 대표 패턴의 semantics 차이와 failure mode. 어느 것이 좋다고 결론 내리지 말고 차이만 정리하세요.
6. **claim과 `JobExecution(RUNNING)` INSERT를 한 transaction에 둘 때.**
   - INSERT가 거는 lock(insert intention lock · unique check · foreign key 검사 시 부모 row lock · AUTO_INCREMENT lock mode)이 claim lock과 상호작용해 deadlock을 만들 수 있는 조건
   - commit 전 Worker crash · connection 끊김 시 server 측 rollback 동작
   - commit 요청 후 응답을 받기 전에 연결이 끊긴 경우 — client가 commit 성공 여부를 모르는 상황과 그 처리 패턴
   - commit 후 실제 작업 시작 전에 Worker가 죽는 경우 — lease 만료로만 회복된다는 점의 의미
   - 실제 작업(수 분 이상 걸릴 수 있음)이 끝날 때까지 transaction을 열어 두는 방식과, claim만 짧게 commit하는 방식의 semantics 차이
7. **공식 문서의 주의사항.** MySQL 공식 문서가 `SKIP LOCKED` · `NOWAIT`에 대해 적은 제약(일관되지 않은 view, replication 관련 주의 등)이 있으면 원문 근거와 함께 정리하세요.
8. **실제 구현 사례.** MySQL(가능하면 8.x)을 backend로 쓰는 공개 DB-backed job queue 구현(예: Rails Solid Queue 등 — 예시이며 다른 구현도 가능)이 claim query · transaction 경계 · index를 어떻게 구성했는지, 그 프로젝트의 공식 issue · changelog에 보고된 lock · deadlock · 성능 문제와 해결을 정리하세요. 그 구현의 설정값(polling 주기 · batch 크기 등)은 **그 환경의 숫자**로만 적으세요. PostgreSQL 기반 구현은 lock semantics가 다르므로, 인용한다면 차이를 명시하세요.

### Q2 (R1 · RD-01c · RD-01d · RD-01g) — MySQL 8.4에서 JSON column vs 관계형 구조

대상 값의 성격(논리 의미는 정해졌고 물리 저장만 열려 있음):

| 값 | 성격 |
| --- | --- |
| `produced` | 실행 1건이 만든 산출물 참조의 배열. 각 원소는 종류 + 식별자 정도의 작은 참조 객체 |
| `usage_refs` | 실행 1건에 연결된 UsageRecord ID 배열. 같은 관계를 UsageRecord 쪽 `execution_ref`로도 표현할 수 있으며, **두 방향을 독립된 authoritative 원장으로 이중 관리하지 않는다**는 원칙은 정해졌다 |
| `Money` | 금액 + 통화. 저장 전 KRW로 정규화한다. 정밀도와 표현 방식(column 분리 / JSON)이 미정 |
| `pricing_context` · `token_usage` | 비용 계산 맥락(opaque한 가격표 식별자 · 단위 등)과 token 사용량. 일부 모양은 다른 모듈이 넘겨주며 앞으로 바뀔 수 있다 |

각 값에 대해 JSON column과 관계형 구조(별도 column · child table · projection)를 다음 축으로 비교하세요.

1. **조회** — 실행 단위 · 사건 단위 · 기간 단위 집계 query 작성 난이도와 성능 특성. JSON 경로 함수 · `JSON_TABLE` 사용 시 제약.
2. **제약 검증** — `NOT NULL` · `CHECK` · foreign key · unique를 어디까지 걸 수 있는가. JSON에 schema 검증(`JSON_SCHEMA_VALID` 등)을 `CHECK`로 거는 것이 MySQL 8.4에서 가능한가와 그 한계. JSON 안 참조에는 foreign key를 걸 수 없다는 점의 영향.
3. **indexing** — generated column + index, multi-valued index의 지원 범위와 제약(MySQL 8.4 기준).
4. **수치 정밀도** — JSON 안 숫자가 MySQL에서 어떤 타입으로 저장 · 비교되는가. 금액을 `DECIMAL` column에 둘 때와 JSON에 둘 때 정밀도 · 반올림 차이. 정수 최소 단위(minor unit) 저장 방식과의 비교.
5. **migration · schema evolution** — JSON 내부 모양이 바뀔 때와 column/table을 바꿀 때의 migration 비용. MySQL 8.4의 online DDL(`ALGORITHM=INSTANT` 등)이 어떤 변경에 적용되는가.
6. **integrity** — append-only 원장에서 부분 갱신 · 중복 append 방지(unique key)를 어떤 구조가 더 직접 표현하는가.
7. **운영 · debuggability** — 운영자가 SQL로 직접 조회 · 진단할 때의 차이, ORM · driver의 JSON 지원 차이.

### Q3 (R2 · RD-01j) — Python 3.12 + MySQL 8.4 DB 접근 계층 · migration 도구

**특정 라이브러리를 정답으로 두지 마세요.** 비교 근거를 모으는 것이 목적입니다. 아래 이름은 조사 출발점 예시일 뿐이며, 더 적절한 후보가 있으면 포함하세요.

- driver 예시: PyMySQL · mysqlclient · MySQL Connector/Python · aiomysql · asyncmy
- 접근 방식 예시: raw SQL · query builder / SQL toolkit · ORM
- migration 도구 예시: Alembic · yoyo-migrations · Flyway · Liquibase · Atlas · 순수 SQL 파일 + 자체 version table

대신고 측 조건(사실):

- Worker 코드는 대부분 동기다 — ffmpeg를 `subprocess.run`으로 실행하고, 외부 AI API를 동기 HTTP client로 호출한다.
- API는 FastAPI다.
- Worker는 장시간 살아 있는 process이고, 한 작업이 수 분 이상 걸릴 수 있다.
- 6명이 병렬 branch로 작업한다.

확인 항목:

1. **driver** — Python 3.12 · MySQL 8.4 지원 상태, 유지보수 상태, 순수 Python vs C extension(빌드 의존성 · Docker image 영향), 인증 plugin(`caching_sha2_password`) 지원, license.
2. **sync vs async** — 동기 Worker와 FastAPI API가 같은 DB 계층을 공유할 때의 선택지와 제약. async driver를 동기 코드에서 쓰거나 그 반대일 때의 문제.
3. **ORM 사용 여부** — Q1의 claim query(`FOR UPDATE SKIP LOCKED` · 명시적 transaction 경계)와 Q2의 JSON column을 각 접근 방식이 어떻게 표현 · 지원하는가.
4. **장시간 process의 connection 관리** — MySQL `wait_timeout` · 끊긴 connection 감지 · pool 재사용 시 동작.
5. **migration version 관리** — version 기록 방식, 여러 branch에서 동시에 migration을 만들 때의 충돌(분기 head 등)과 해결 방식, downgrade 지원 여부.
6. **MySQL DDL 특성과 migration** — MySQL DDL의 implicit commit과 MySQL 8.x atomic DDL이 각각 무엇을 보장하고 무엇을 보장하지 않는지(statement 하나 단위인가, 여러 statement로 된 migration 전체인가) 확인하세요. 그 결과 migration이 도중에 실패하면 어떤 상태가 남을 수 있고, 각 도구가 그 상황을 어떻게 다루는가.
7. **Docker Compose 환경에서 migration 실행 방식** — 별도 one-off 실행(`docker compose run` 등), 별도 migration service + `depends_on` 조건, application startup 안에서 실행하는 방식의 차이. api · worker가 둘 다 startup에서 migration을 시도할 때의 경쟁 조건. application startup과 migration을 분리할지에 대한 근거.

배포 순서(새 image 배포와 migration 중 무엇을 먼저 하는가, 실패 시 rollback)는 별도 조사 대상입니다. 여기서는 **도구가 제공하는 실행 방식과 그 semantics**까지만 다루세요.

## 4. 범위 밖

다음은 조사하지 마세요.

- Redis · RabbitMQ · SQS 등 다른 queue 기술로의 전환 추천
- RDS · 다른 DB 엔진으로의 전환 추천
- lease duration · heartbeat 주기 · retry 횟수 같은 값
- 여러 Worker로 늘릴 때의 capacity · scaling 판단

## 5. 조사 방법

자료 우선순위:

1. 기술 자체의 최신 공식 문서 (MySQL 8.4 Reference Manual 등)
2. 공식 Python · 각 라이브러리 문서
3. 신뢰할 수 있는 engineering / architecture 자료
4. 해당 OSS의 공식 GitHub issue · discussion · source
5. 커뮤니티 글은 보조 근거로만

- 현재 시점 기준 최신 정보를 확인하세요.
- **버전을 반드시 구분하세요.** MySQL 8.0 · 8.4 · 9.x 동작이 다르면 차이를 적고, 대신고 기준은 **MySQL 8.4 LTS · Python 3.12**입니다. 구버전 동작을 현재 동작처럼 쓰지 마세요.
- 라이브러리는 확인한 버전과 확인일을 적으세요.
- 공식 문서가 명시하지 않은 동작은 「문서에 명시 없음」으로 표시하고 추정하지 마세요.

## 6. 출력 원칙

**사실 · 해석 · 적용을 섞지 마세요.** 각 주장에 다음 중 하나를 표시하세요.

- **Verified fact** — 공식 문서 등이 직접 말하는 사실. 출처 필수
- **Interpretation** — 여러 근거를 종합한 해석. 근거 목록 필수
- **Daesingo implication** — 위 대신고 구조에 적용했을 때의 의미

**최종 선택을 하지 마세요.** 「따라서 SKIP LOCKED를 써야 한다」 「따라서 SQLAlchemy/Alembic을 써야 한다」 「따라서 JSON column이 최선이다」 같은 결론을 쓰지 않습니다. 선택지와 trade-off까지만 정리합니다.

**외부 숫자를 대신고 baseline으로 쓰지 마세요.** 다른 서비스나 글이 「lock wait timeout N초」 「worker N개」 「pool size N」을 쓴다면, 그 숫자는 **그 환경의 숫자이며 대신고에 직접 적용할 수 없다**고 구분해서 적으세요.

**작성 언어와 기준일.** 결과는 한국어로 쓰고, 기술 용어 · 설정 이름 · 원문 인용은 영어 그대로 둡니다. 결과 맨 위에 조사 기준일을 적으세요.

**제출 전 자기 점검.** 결과를 내기 전에 「~해야 한다」 「~가 최선이다」 「권장한다」처럼 선택을 확정하는 문장이 남아 있는지 확인하고, 있으면 조건과 trade-off를 설명하는 문장으로 바꾸세요. 출처가 없는 Verified fact가 있으면 Interpretation으로 내리거나 9절(Unresolved)로 옮기세요.

## 7. 결과 형식

다음 구조로 작성하세요.

```markdown
# Research Result — MySQL Runtime Persistence

## 1. Executive Summary
- 조사 결과의 핵심 사실만
- 최종 Decision 추천은 하지 않음

## 2. Questions Investigated
- Q1 · Q2 · Q3 질문별 실제 조사 범위

## 3. Verified Technical Facts
| Fact | Version / Condition | Evidence |

## 4. Options / Patterns
- 각 선택지 또는 구현 패턴 (Q1 claim 패턴 · Q2 저장 구조 · Q3 도구 조합)
- 각 항목에 trade-off

## 5. Failure Modes / Operational Risks
| Failure mode | 발생 조건 | 영향 | 완화 가능성 |

## 6. Daesingo-specific Implications
- 현재 대신고 구조에 직접 적용되는 제약
- 어떤 RD / sub-decision(RD-01b · 01c · 01d · 01g · 01j)에 영향을 주는지

## 7. What External Research Cannot Decide
- 대신고 내부 합의가 필요한 것
- 실험이 필요한 것
- External Input이 필요한 것

## 8. Suggested Pre-implementation Checks
- 필요 시 작은 spike / integration test (예: 동시 claim 중복 없음 검증 시나리오)
- 실제 production baseline 숫자를 만들지는 않음

## 9. Unresolved / Unverified
- 확인하지 못한 사실
- 문서 간 불일치
- 추가 확인 필요사항

## 10. Sources
- URL
- 문서명
- 버전 / 게시일 또는 확인일
```

## 8. Research Completion Criteria

이 조사는 다음에 답할 수 있을 때 완료입니다.

- MySQL 8.4 InnoDB에서 `SELECT … FOR UPDATE SKIP LOCKED`가 실제로 어떤 lock을 어디에 거는지, isolation level · index · ORDER BY/LIMIT에 따라 어떻게 달라지는지 설명할 수 있는가?
- claim과 `JobExecution(RUNNING)` INSERT를 한 transaction에 둘 때와 나눌 때의 commit · rollback · crash 경계별 결과를 설명할 수 있는가?
- `produced` · `usage_refs` · `Money` · `pricing_context` 각각에 대해 JSON과 관계형 구조의 핵심 trade-off를 설명할 수 있는가?
- DB driver · 접근 방식 · migration 도구 후보별 핵심 차이와, Compose 환경에서 migration을 실행하는 방식별 semantics를 설명할 수 있는가?
- 대표 failure mode(중복 claim · deadlock · commit 불확실성 · 부분 적용된 migration 등)를 설명할 수 있는가?
- 대신고에서 실험 · spike로 확인해야 할 조건을 구분했는가?
- 외부 조사만으로 결정할 수 없는 부분을 식별했는가?
- 각 결과가 RD-01b · RD-01c · RD-01d · RD-01g · RD-01j 중 어디에 영향을 주는지 연결했는가?
- 핵심 주장에 출처가 붙어 있는가?
