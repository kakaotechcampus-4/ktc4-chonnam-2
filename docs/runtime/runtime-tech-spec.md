# Runtime Tech Spec

**Status:** Working — implementation spec  
**Owner:** common/runtime — 김준영 · 구현 담당 정철원  
**Scope:** 대신고 modular monolith의 실행 인프라  
**Architecture SoT:** [`docs/architecture/module-architecture.md`](../architecture/module-architecture.md)  
**Logical Data Model:** [`docs/architecture/erd-draft.md`](../architecture/erd-draft.md)  
**Alignment ADR:** [ERD ↔ Runtime 정합화](../architecture/contracts/adr/adr-erd-runtime-alignment-2026-09-19.md)

> 이 문서는 Final Data Contract를 재정의하지 않는다. `JobRecord`, `JobExecution`, `UsageRecord`, `CaseView`의 필드·enum·불변조건은 각 Contract가 authoritative하다. Logical ERD는 cross-domain 관계·cardinality·저장 후보의 입력이다. 이 문서는 그 상위 논리 의미를 유지하면서 **DB Queue·Worker·실행 lifecycle의 물리 구현**을 정한다.

## 1. 문서 경계

### 이 문서가 소유한다

- DB Queue의 물리 구조와 claim 방식
- `JobExecution` persistence
- retry scheduling
- lease / heartbeat / STALE recovery
- Worker polling / dispatch
- `UsageRecord` persistence 접합
- Runtime configuration
- API/Worker composition root의 실행 경계
- Runtime health endpoint의 기술 의미
- Runtime integration test acceptance criteria

### 이 문서가 소유하지 않는다

- 작업이 필요한 이유와 부분 재실행 정책 — `case`
- cache/reuse 정책 결정 — `case`
- Search/Readout/Recording 내부 알고리즘
- Final Contract schema
- Logical ERD에 이미 확정된 cross-domain 의미·cardinality
- 배포·모니터링·disk/retention 운영 정책 — [`ops-spec.md`](./ops-spec.md)
- Recording/Search benchmark 원본

### 설계 입력 우선순위

Runtime 관련 저장/실행 설계가 충돌할 때는 다음 순서로 판정한다.

```text
Product / Module Architecture
→ Final Data Contract / Accepted Owner Decision · ADR
→ Logical ERD
→ Runtime Tech Spec
→ code / migration
```

Final Contract에서 이미 닫힌 의미를 ERD나 Runtime이 다시 결정하지 않는다. 반대로 `produced`의 JSON/관계 테이블 선택처럼 상위 문서가 물리 저장을 열어둔 경우에는 Runtime 구현에서 결정할 수 있다. 양쪽 모두 미결이면 임의 확정하지 않는다.

## 2. 상위 경계

```text
HTTP request
→ API composition root
→ case가 JobRecord(Intent) 발주
→ common/runtime 실행 경계
→ 202 Accepted + 조회 가능한 식별자

이후

Worker composition root
→ Runtime queue claim
→ JobExecution 생성/전이
→ 대상 domain public capability 호출
→ produced refs / UsageRecord 연결
→ case가 현재 case_rev 기준으로 결과 반영 여부 판단
```

`common/runtime`은 여덟 번째 도메인 모듈이 아니다. `case`가 **왜 실행하는지**를 소유하고 Runtime은 **어떻게 실행됐는지**만 소유한다.

API와 Worker는 별도 프로세스일 수 있지만 같은 repository와 Final Contract를 사용하는 modular monolith의 composition root다.

## 3. Contract 접합

### 3.1 JobRecord = Intent

Authoritative source: [`contract-job-record-case-view.md`](../architecture/contracts/contract-job-record-case-view.md)

Runtime은 JobRecord를 Queue row와 동일시하지 않는다.

Runtime이 필요로 하는 Intent 정보는 예를 들면 다음과 같다.

```text
job_id
case_id / case_rev
kind
scope_ref
input_fingerprint
force_rerun
requested_at
```

`status`, `attempt`, lease, heartbeat, retry timing, produced result, failure, cost를 JobRecord에 다시 추가하지 않는다.

### 3.2 JobExecution = 실행 1회분

Authoritative source: [`contract-job-execution.md`](../architecture/contracts/contract-job-execution.md)

닫힌 status는 다음 여섯 값이다.

```text
QUEUED
RUNNING
SUCCEEDED
FAILED
STALE
CANCELLED
```

같은 `job_id`의 자동 인프라 retry는 **새 `execution_id`와 증가한 `attempt`**를 만든다.

사용자가 “이어서 찾기”, 재검색, 재판독을 요청하는 것은 retry가 아니라 새 Intent이므로 **새 JobRecord / 새 job_id**다.

### 3.3 UsageRecord = 호출 단위 원장

Authoritative source: [`contract-usage-record.md`](../architecture/contracts/contract-usage-record.md)

실제 capability/provider invocation이 시작된 호출만 UsageRecord를 남긴다. queue에서 기다리다 dispatch 전에 취소·실패한 execution에는 UsageRecord를 만들지 않는다.

금액의 authoritative source는 UsageRecord이며 JobRecord/JobExecution에 비용 필드를 복제하지 않는다.

## 4. DB Queue

### 4.1 Baseline

Architecture baseline은 **MySQL 8.4 LTS / InnoDB 기반 DB Queue**다.

Redis, Celery, RabbitMQ, SQS는 baseline에 넣지 않는다.

### 4.2 Logical ERD와 Queue row의 분리

Logical ERD는 `JobRecord 1 → N JobExecution`, `JobExecution → UsageRecord.execution_ref` 같은 **논리 관계**를 제공한다. 하지만 queue scheduling 자체의 `available_at`, claim owner, lease 같은 Runtime metadata까지 독립 domain record로 확정하지 않는다.

권장 물리 모델은 다음 의미를 분리한다.

```text
case-owned JobRecord
    │
    └── Runtime dispatch/queue metadata
            │
            └── JobExecution row(s)
```

Queue scheduling을 위해 필요한 `available_at`, claim owner, lease expiry 같은 필드는 Runtime persistence에 둘 수 있지만 **Final JobExecution Contract 필드로 승격하지 않는다.**

실제 table 분할 여부와 column 이름은 첫 DB 구현에서 migration과 함께 고정한다.

### 4.3 Claim 요구사항

claim은 다음을 만족해야 한다.

1. 동시에 둘 이상의 Worker가 같은 queue item을 정상 claim하지 않는다.
2. claim과 `JobExecution(RUNNING)` 시작 사이의 불일치를 transaction 경계에서 최소화한다.
3. 다음 실행 가능 시각 이전의 item을 잡지 않는다.
4. lease가 유효한 다른 Worker의 실행을 빼앗지 않는다.
5. 여러 Worker로 확장되더라도 claim 알고리즘 자체를 바꾸지 않고 concurrency만 늘릴 수 있어야 한다.

MySQL에서는 `SELECT ... FOR UPDATE SKIP LOCKED`를 사용한다. 다음 규칙은 확정이다(RD-01b 핵심 규칙, [#250](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/250), 2026-10-03).

- Runtime DB session isolation은 **`READ COMMITTED`**다. 기본값 `REPEATABLE READ`에서는 `SKIP LOCKED` claim이 첫 실행 가능 index entry 앞의 gap을 잠가, claim transaction이 끝날 때까지 다른 row의 `FAILED` · `CANCELLED` 전이와 이른 `available_at` enqueue를 막는 것이 관찰됐다([spike S1](./experiments/pre-implementation-spike-2026-10-03.md#s1--claim-lock-footprint-rd-01b)).
- claim transaction은 `ORDER BY`를 그대로 만족하는 covering index 위의 `LIMIT 1 FOR UPDATE SKIP LOCKED` + 조건부 UPDATE로 끝내고 **INSERT를 넣지 않는다.** commit한 뒤에 실제 작업을 시작하며, provider 호출 · ffmpeg 같은 작업 동안 DB transaction을 열어 두지 않는다.
- 모든 terminal 전이는 현재 status를 조건으로 한 UPDATE다. 같은 execution에 두 전이가 겹치면 먼저 commit한 쪽이 남고 다른 쪽은 0 rows다([spike S2](./experiments/pre-implementation-spike-2026-10-03.md#s2--conditional-update-경합-rd-19b--rd-02a)).
- claim 순서는 다음 실행 가능 시각 → 고유 tiebreaker의 best-effort다. `SKIP LOCKED`는 잠긴 앞 row를 건너뛰므로 strict FIFO를 보장하지 않는다.

queue 항목을 어느 table의 어떤 row로 둘지와 exact index(RD-01a · RD-01b 모양)는 RD-02 · RD-06 결정 뒤에 고정한다 — 추천안은 [#250](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/250). 최종 query는 integration test로 검증한다.

### 4.4 DB 접근 계층 · Migration

확정(RD-01j, [#250](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/250), 2026-10-03):

- driver는 **PyMySQL**(sync, pure Python), 접근 계층은 **SQLAlchemy Core 2.x**(connection pool · transaction)이고 ORM은 쓰지 않는다. API와 Worker는 같은 **sync DB access stack**을 쓴다. claim처럼 lock · transaction 경계가 정합성의 일부인 query는 명시적 textual SQL로 둘 수 있다.
- idle connection 끊김은 pool pre-ping · recycle로 다룬다(값은 Provisional Baseline).
- 이 결정은 DB access stack만 정한다. **FastAPI route를 `def`로 둘지 `async def`로 둘지는 정하지 않는다** — HTTP/API 구현에서 I/O 경계(예: upload의 `UploadFile` 수신)를 보고 정한다. `async def` route가 sync DB service를 부르면 event loop를 막지 않도록 threadpool 등의 adapter 경계를 구현 단계에서 둔다.
- migration 도구는 **Alembic**이다. 운영 계약은 forward-only이며 schema 변경은 expand → contract 순서로 나눈다. downgrade script를 운영 rollback 경로로 쓰지 않는다 — MySQL DDL은 statement 단위로만 atomic하다.
- migration은 api · worker 시작 전 **단일 실행 단계**로만 돌린다. application startup에서 migration을 실행하지 않는다. 실행 명령과 위치는 Ops/Runbook(RD-12f)이 정한다.

근거: [Research 01](./research/01-mysql-runtime-persistence-2026-10-03.md) §4.8 ~ §4.13 · Review notes.

### 4.5 결과 · 원장 물리 표현

확정(RD-01c · 01d, RD-01g는 물리 표현까지 — [#250](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/250), 2026-10-03). 필드 의미는 각 Contract가 authoritative하다.

- **`JobExecution.produced`** — execution row의 JSON column에 `ContractRef[]` 그대로 저장한다. 별도 child table을 두지 않는다. produced ref로 execution을 찾는 요구가 생기면 다시 연다.
- **`JobExecution.usage_refs`** — 저장하지 않는다. `UsageRecord.execution_ref`(index)로 projection한다. 두 방향을 독립 원장으로 두지 않는다(ERD↔Runtime ADR D6).
- **UsageRecord** — Contract 필드를 typed column으로 둔다. `token_usage` 세 값은 nullable 정수이고 「전부 null 또는 전부 존재」 · 「total = input + output」을 DB 제약으로 건다(Contract §8-3 · §8-4). `pricing_context`는 `pricing_id` · `unit` column. `cost`는 nullable `DECIMAL` 계열 exact numeric amount + 별도 typed currency column이다. 애플리케이션은 금액을 `Decimal` ↔ 문자열 경계로만 다루고 float를 쓰지 않으며, 저장 scale보다 자릿수가 많은 값은 DB에 넣을 때 조용히 반올림하지 않고 거부한다. Contract에 없는 opaque 확장 column은 두지 않는다.
  - **아직 고정하지 않은 것:** `DECIMAL` precision · scale 값. 새 Open Decision이 아니라 RD-01g 안의 구현 세부로, **첫 migration에서** cost 생산자 출력 범위([#244](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/244) U-2)와 Contract 예시를 기준으로 고정한다.

UsageRecord의 append 시점 · in-flight 추적 · 중복 방지(RD-01e · 01f)는 Search → Runtime 전달 모양([#244](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/244)) 결정 뒤에 닫는다(§11.1 · §11.4).

## 5. Idempotency / Cache Reuse 접합

cache/reuse 여부의 Owner는 `case`다.

현재 Final Contract 기준 재사용의 핵심 조건은 다음 의미다.

```text
same case_id
+ same kind
+ same input_fingerprint
+ force_rerun = false
+ reusable prior SUCCEEDED result
→ case may reuse
```

Runtime은:

- fingerprint를 임의로 다시 계산하지 않는다.
- domain module의 model/prompt/version 내부를 해석하지 않는다.
- FAILED/STALE execution을 성공 cache처럼 취급하지 않는다.
- `force_rerun=true`의 의미를 무시하지 않는다.

`input_fingerprint`의 canonical serialization/hash algorithm은 case 접합 구현이 고정한다. Runtime Contract로 SHA-256 같은 algorithm을 선결하지 않는다.

## 6. Retry

### 6.1 사용자 재실행과 자동 retry

```text
사용자 Intent
→ new JobRecord
→ new job_id

자동 인프라 retry
→ same job_id
→ new execution_id
→ attempt + 1
```

기존 execution row를 되살리거나 attempt를 in-place 수정하지 않는다.

### 6.2 Retry 대상

기본 원칙:

- timeout, 일시적 network/provider 장애, rate limit 등 **재호출로 회복 가능성이 있는 실패**만 retry 후보
- invalid input, unsupported media, 인증/설정 오류처럼 **동일 입력의 즉시 반복으로 회복되지 않는 실패**는 자동 retry하지 않음

상세 failure code는 각 provider/module taxonomy가 소유한다. Runtime은 그 taxonomy를 retryable/non-retryable 실행 정책에 매핑한다.

### 6.3 Scheduling

Worker가 backoff 동안 `sleep()`으로 실행 슬롯을 붙잡지 않는다.

```text
retry 필요
→ 현재 execution terminal 기록
→ queue metadata.available_at 계산
→ claim 대상에서 대기
→ 시간이 된 뒤 새 JobExecution 생성
```

> **Open Decision:** retry backoff 동안 다음 attempt의 생성 시점과 CaseView 대표 상태 계약([JobRecord/CaseView Contract](../architecture/contracts/contract-job-record-case-view.md) A절 §10-6)의 정합을 구현 전에 닫아야 한다. 위 순서는 그 결정 전까지 확정된 구현 순서가 아니다. 근거는 [2026-10-02 검수](./reviews/runtime-ops-consistency-audit-2026-10-02.md) B-02. 결정 카드: [#248](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/248)(추천안 단계).

### 6.4 아직 열려 있는 Runtime 값

다음 값은 Final Contract가 의도적으로 정하지 않았다.

- retry max
- backoff curve
- jitter
- retryable failure mapping의 runtime override 여부
- `available_at` 계산 규칙

기존 working 문서에 있던 “최대 3회”, “2s→4s→8s” 같은 값은 확정값으로 사용하지 않는다.

## 7. Lease / Heartbeat / STALE Recovery

### 7.1 상태 의미

`JobExecution.STALE`은 **실행 중 Worker가 더 이상 살아 있지 않다고 Runtime이 판정한 terminal execution 상태**다.

오래된 `case_rev` 결과와 STALE을 혼동하지 않는다.

```text
SUCCEEDED + old case_rev
→ execution은 SUCCEEDED 유지
→ case가 produced 적용을 거부
```

### 7.2 Recovery

lease 만료된 RUNNING execution을 같은 execution의 QUEUED로 되돌리지 않는다.

```text
attempt 1 RUNNING
→ heartbeat/lease 만료
→ attempt 1 STALE

retry 허용
→ attempt 2 QUEUED
→ RUNNING ...
```

### 7.3 Sweep

현재 Worker 1 baseline의 recovery 주체는 별도 reaper process가 아니다.

```text
Worker startup
→ stale RUNNING sweep 1회

Worker loop
→ periodic stale sweep
```

다중 Worker로 확장할 때 sweep의 중복 실행이 안전하도록 DB transaction/idempotency를 보장해야 한다.

### 7.4 아직 열려 있는 Runtime 값

- lease duration
- heartbeat interval
- STALE threshold
- periodic sweep interval
- heartbeat persistence 방식

이 값은 첫 실제 DB Queue/Worker integration에서 config로 고정하고 테스트 근거를 남긴다.

값을 정할 때의 입력: Job timeout과 「진행 중 Job은 강제 취소하지 않는다」는 정책은 `case`가 소유한다([`timeout-fallback.md`](../modules/case/decisions/timeout-fallback.md), 잠정값). Runtime 문서에 그 값을 복제하지 않는다.

## 8. 실패 이력과 DLQ

MVP에서는 별도 DLQ infrastructure를 두지 않는다.

```text
JobRecord       → Intent history
JobExecution    → FAILED / STALE / CANCELLED execution history
UsageRecord     → 실제 invocation 사용량/비용 history
```

운영자가 terminal execution을 조회하고 재현할 수 있으면 현재 규모에서 충분하다.

향후 전용 message queue를 도입하고 redrive 운영 요구가 생기면 DLQ를 함께 재검토한다.

## 9. 진행 상태와 CaseView

Web은 JobExecution을 직접 소비하지 않고 CaseView projection을 본다.

현재 Contract mapping:

```text
QUEUED     → PENDING
RUNNING    → RUNNING
SUCCEEDED  → DONE
FAILED     → FAILED
STALE      → FAILED
CANCELLED  → PARTIAL
```

같은 `job_id`에 여러 attempt가 있으면 가장 큰 `attempt`가 그 job의 대표 execution 상태다. 같은 kind의 JobRecord가 여러 개라면 Final JobRecord/CaseView Contract A절 §10-7에 따라 **`requested_at`이 가장 늦은 JobRecord**가 그 kind의 대표 job이다. `case_rev`는 발주 순서 정렬 키로 쓰지 않는다. 이 선택 규칙은 Runtime이 새로 판단하는 정책이 아니라 case projection Contract를 따르는 것이다.

모든 가능한 stage를 미리 채우거나 근거 없는 percentage를 만들지 않는다.

MVP UI의 polling은 baseline이지만 polling interval은 Runtime Contract가 아니다.

## 10. 부분 실패

Runtime은 domain dependency graph를 스스로 추론하지 않는다.

원칙은:

> 이미 성공한 domain artifact를 하위 단계 실패 때문에 불필요하게 무효화하지 않는다.

예:

```text
CandidateEvent 확보
→ IncidentClip 생성
→ Plate Readout 실패

CandidateEvent 유지
유효한 IncidentClip 유지
case가 필요한 readout Job만 새로 발주
```

재실행 범위는 `case`가 결정하고 Runtime은 발주된 Job만 실행한다.

## 11. UsageRecord Persistence

### 11.1 기록 대상과 persistence 시점

Final UsageRecord Contract가 확정하는 것은 **기록 대상 조건**이다.

```text
실제 capability/provider invocation 시작
→ 해당 호출은 UsageRecord 기록 대상

dispatch 전 CANCELLED/FAILED
→ UsageRecord 없음
```

호출 시작 순간에는 token/cost/latency/실패 정보가 완성되지 않을 수 있다. 따라서 Runtime은 관측 가능한 사용량·결과·실패 정보를 Contract 규칙에 맞게 채울 수 있는 시점에 호출 1건당 append-only UsageRecord 1건을 남긴다.

**아직 확정하지 않는 것:** 호출 시작 순간 incomplete row를 먼저 INSERT할지, 완료/실패 관측 뒤 final row를 append할지, worker 소멸 시 in-flight invocation을 어떻게 복구할지, 중복 append를 어떻게 방지할지는 Runtime persistence 구현 결정이다.

### 11.2 집계

- execution 단위: `execution_ref`
- logical run 단위: `run_ref`
- 사건 단위: `case_id`

Run contract의 `usage_refs[]`와 ledger가 어긋나면 `UsageRecord.run_ref`가 authoritative하다.

### 11.3 Pricing

실행 시점 cost를 이후 가격표로 덮어쓰지 않는다.

Runtime이 확정적으로 소유하는 것은 **Final `UsageRecord`에 실행 시 사용한 `pricing_id`, usage, 실행 시점 cost snapshot을 보존하는 책임**이다.

가격표 숫자 자체의 SSOT를 Runtime config가 독점하지 않는다. Issue #153에서 Search·Runtime Owner가 합의한 현재 경계(2026-09-26)는 다음과 같다.

- 현재 MVP에서는 Search가 rate를 주입받아 cost를 계산한다.
- 공용 versioned pricing catalog는 지금 만들지 않는다. Search/Eval/Runtime이 가격표를 직접 소비해야 하는 요구가 실제로 생기면 다시 검토한다.
- `pricing_id`는 지금 추가하는 방향이다. 의미는 「실행 시 cost 계산에 실제로 사용된 가격표의 opaque stable identifier」이고, Runtime은 내부 구조를 파싱하지 않고 전달받은 값을 그대로 보존한다. Search → Runtime 접합에는 `pricing_context.unit`과 cost도 함께 전달한다.
- provider invocation → Search가 usage/cost/pricing context 확정 → Runtime이 Final UsageRecord append.

통화는 별도 결정이다. budget 대상 `UsageRecord.cost`는 저장 전에 KRW로 정규화하고 `currency="KRW"`로 기록하며, provider-native 통화와 환율 provenance는 `pricing_id`가 가리키는 versioned artifact가 보존한다([`budget-krw-normalization.md`](../modules/case/decisions/budget-krw-normalization.md), 2026-09-09, #19).

아직 닫히지 않은 것은 정책이 아니라 구현 세부다.

- `pricing_id`가 가리킬 versioned pricing/FX artifact의 위치와 schema
- KRW 환산에 쓰는 FX source
- provider/model 가격 변경 이력 보존 방식
- provider별 실제 정산 기준(원화 크레딧과 표시 가격의 관계, [`mlapi.md`](./official-inputs/mlapi.md))

공용 catalog가 나중에 채택되더라도 Search의 실행 중 cost estimate와 Runtime의 authoritative ledger는 서로 다른 목적의 소비자일 수 있다. **SSOT는 가격표 데이터에 하나만 두고, 사용 주체를 하나로 제한하지 않는다.**

### 11.4 아직 열려 있는 값

- UsageRecord DB table/migration
- invocation 시작 → final append 사이의 in-flight 추적/복구 방식
- 호출 1건당 중복 append 방지/idempotency
- `pricing_id`가 가리킬 pricing/FX artifact 형식·위치와 history 보관 (§11.3)
- UsageRecord retention
- `purge_case()`와 ledger 삭제 관계

마지막 두 항목은 Ops/정책과 함께 닫는다.

## 12. Worker Dispatch

Worker composition root가 Runtime과 domain public capability를 연결한다.

금지:

- `case`가 Worker 구현을 직접 import
- Worker가 orchestration 결정을 새로 만듦
- Runtime이 domain 내부 private service를 호출
- module별 provider detail을 common/runtime에 흡수

Worker handler는 Job kind를 **등록된 public capability invocation**으로만 매핑한다.

Readout 계열은 Final JobExecution Contract의 “1 execution : public readout 1회” 불변조건을 지켜야 한다.

## 13. API Boundary

FastAPI `BackgroundTasks`를 긴 영상 처리 queue로 사용하지 않는다.

API request의 책임:

1. 요청 validation
2. case command 호출
3. JobRecord 발주
4. Runtime dispatch 요청
5. 202 Accepted와 조회 정보 반환

실제 media transform/search/readout은 request lifecycle 밖에서 Worker가 실행한다.

## 14. Runtime Health

구현 시 최소 두 endpoint를 둔다.

```text
/health/live
→ API process가 요청을 받을 수 있는가

/health/ready
→ 현재 요청 처리에 필수인 Runtime dependency(DB 등)를 사용할 수 있는가
```

외부 AI provider 전체의 실시간 성공 여부를 `ready`에 묶어 provider 장애가 곧 API process down으로 해석되게 하지 않는다.

Worker는 public health endpoint 대신 Runtime DB의 heartbeat/lease 관측으로 상태를 볼 수 있다.

운영에서 health를 어떻게 alert에 사용할지는 Ops Spec이 소유한다.

## 15. Runtime Configuration

환경별 변경 가능성이 있는 Runtime 값은 코드 상수보다 config로 둔다.

후보:

```text
DB connection
worker polling interval
retry max/backoff/jitter
lease duration
heartbeat interval
STALE threshold
stale sweep interval
pricing catalog/reference (채택 시)
log level
```

### 15.1 Module / Provider configuration 주입 경계

Worker composition root는 domain module이 실행에 필요한 config와 secret을 **주입**할 수 있어야 하지만, common/runtime이 provider-specific 의미를 해석하지 않는다.

```text
deployment / Worker composition root
→ module config · secret 주입
→ search public capability / provider adapter

common/runtime
→ 전달 경계와 secret 비노출 책임

search
→ Elice base_url, model, reasoning_effort,
   OpenAI-compatible schema, media transport 등 provider 의미 해석
```

따라서 Runtime이 Elice request schema나 `reasoning_effort` 같은 provider semantics를 별도 설정 모델로 복제하지 않는다.

provider label · provider config 의미와 validation은 Search가 소유한다(Issue #153 합의, 2026-09-26). key naming은 `GEMINI_API_KEY → ELICE_ML_API_KEY` rename 방향으로 합의됐고, 기존 `.env` 호환 alias는 `common/env.py`가 아니라 **Search config 내부**에 둔다. alias 제거는 팀 `.env`와 deployment secret migration이 끝난 뒤다. rename 자체는 Search 작업이며 develop에 아직 반영되지 않았다. Runtime은 구현 편의를 이유로 Search보다 먼저 rename하거나 별도 가격표를 복제하지 않는다. pricing 경계는 §11.3을 따른다.

secret은 repository config에 저장하지 않는다.

Python/dependency의 executable SoT는 root `pyproject.toml`, `uv.lock`, CI workflow다.

## 16. Test Acceptance Criteria

### Unit

- JobExecution state transition
- attempt 증가
- invalid transition rejection
- retry scheduling pure logic
- stale detection pure logic

### Contract / Boundary

- Final Contract fixture validation
- module import boundary
- Job kind → public capability dispatch registration
- CaseView projection 정합

### Runtime Integration

실제 MySQL을 사용해 최소 다음을 검증한다.

1. concurrent claim에서 동일 job 중복 claim 없음
2. `available_at` 이전 claim 없음
3. RUNNING worker 소멸 → STALE
4. retry 시 same job_id + new execution_id + attempt+1
5. startup/periodic stale sweep idempotent
6. 실제 invocation이 시작된 호출은 UsageRecord 기록 대상이 되며, 호출 1건당 최종 원장 row가 정확히 1건 남음
7. dispatch 전 cancel에는 UsageRecord 없음
8. old case_rev SUCCEEDED execution이 STALE로 바뀌지 않음

실제 외부 AI provider 호출은 일반 PR CI의 결정론적 gate에서 분리한다.

## 17. 현재 구현 상태 — 2026-10-02 (`develop` `9c204ee` 기준)

현재 `develop`에서 확인된 것:

- `src/daesingo/common/job_execution.py`
  - JobExecution v1.1 model
  - 허용 상태 전이
  - in-memory attempt 연속성 (`InMemoryJobExecutionStore`)
  - STALE/CANCELLED
- 여러 domain module pytest / Mock Pack / contract validator
- CI: repo-wide pytest · Recording media smoke · boundary / contract fixture 검사 (Python 3.12, [Ops Spec](./ops-spec.md) §5 · §19)
- 동기 real 경로: case adapter가 Search·Fine·Readout public capability를 같은 프로세스에서 직접 호출한다. Runtime queue와 JobExecution을 거치지 않으며, case가 남기는 JobRecord는 in-memory case store에만 있다
- Search 내부 usage ledger (Final `UsageRecord` Contract 원장이 아니다)
- API/Worker 책임 README

아직 구현되지 않은 것:

- MySQL Runtime persistence · migration
- 실제 MySQL DB Queue / claim
- lease / heartbeat
- stale sweep
- API composition root
- Worker composition root
- case → Runtime 발주 경로
- Final UsageRecord persistence
- Runtime health endpoint

따라서 이 문서는 **구현 완료 설명서가 아니라 다음 Runtime 구현의 acceptance 기준**이다.

## 18. Open Runtime Decisions

첫 DB Queue/Worker 구현에서 닫아야 한다.

- [ ] queue table / execution table의 물리 schema — 추천안 [#250](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/250), RD-02 · RD-06 대기
- [x] `JobExecution.produced` 물리 저장 — JSON column으로 닫힘 (§4.5)
- [x] `JobExecution.usage_refs` materialization — `UsageRecord.execution_ref` projection으로 닫힘 (§4.5)
- [ ] UsageRecord final append timing / in-flight recovery / duplicate prevention — 추천안 [#250](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/250), [#244](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/244) 대기
- [ ] claim transaction / locking query — isolation · transaction 규칙은 닫힘(§4.3), exact table · index는 위 schema와 함께
- [x] DB 접근 계층 · migration 도구 — sync DB access stack · Alembic으로 닫힘 (§4.4). FastAPI route `def`/`async def`는 이 항목이 정하지 않음
- [ ] retry backoff 동안 다음 attempt 생성 시점 ↔ CaseView 대표 상태 계약 정합 (§6.3 Open Decision)
- [ ] retry max
- [ ] backoff + jitter
- [ ] lease duration
- [ ] heartbeat interval
- [ ] STALE threshold
- [ ] stale sweep interval
- [ ] worker polling interval
- [ ] Runtime configuration shape — 추천안 [#249](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/249)
- [x] UsageRecord persistence shape — 물리 표현(typed column · exact numeric · float 금지)으로 닫힘 (§4.5). `DECIMAL` precision/scale은 첫 migration에서 고정
- [ ] `pricing_id`가 가리킬 versioned pricing/FX artifact 위치·schema · FX source — 정책은 §11.3에서 닫힘 (Search rate 주입 유지 · KRW 정규화)
- [x] provider config/key naming boundary — Issue #153 합의로 닫힘 (§15.1). rename 구현은 Search 작업으로 남음

결정이 여러 구현에 장기 영향을 주면 `docs/runtime/decisions/`에 ADR을 추가한다. 단순 config 튜닝값마다 ADR을 만들지는 않는다.

## References

- [Architecture v4](../architecture/module-architecture.md)
- [Logical ERD](../architecture/erd-draft.md)
- [ERD ↔ Runtime 정합화 ADR](../architecture/contracts/adr/adr-erd-runtime-alignment-2026-09-19.md)
- [JobRecord / CaseView Contract](../architecture/contracts/contract-job-record-case-view.md)
- [JobExecution Contract](../architecture/contracts/contract-job-execution.md)
- [UsageRecord Contract](../architecture/contracts/contract-usage-record.md)
- [AnalysisSource / Derived Asset Contract](../architecture/contracts/contract-analysis-source-derived.md)
- [Runtime Ops Spec](./ops-spec.md)
- [Runtime experiments router](./experiments/README.md)
- [Issue #95 — Elice ML API migration tracker](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/95)
- [Issue #153 — provider usage · pricing · runtime config boundary review](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/153)
- [common runtime README](../../src/daesingo/common/README.md)
