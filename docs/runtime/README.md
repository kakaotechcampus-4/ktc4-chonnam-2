# Runtime Documentation

대신고의 `common/runtime` 실행 인프라 문서 진입점이다.

> `common/runtime`은 여덟 번째 도메인 모듈이 아니다. `case`가 작업의 이유와 발주 의도를 소유하고, Runtime은 그 Intent를 실제 실행으로 옮긴다.

## Source of Truth 우선순위

```text
Product Policy
→ docs/architecture/module-architecture.md
→ Final Data Contract
→ module decisions
→ module research / experiments
→ docs/runtime/*
→ implementation
```

Runtime 문서는 Architecture나 Final Contract schema를 다시 정의하지 않는다.

## 문서 구조

| 문서 | 역할 |
| --- | --- |
| [`runtime-tech-spec.md`](./runtime-tech-spec.md) | DB Queue, claim, JobExecution persistence, retry, lease/heartbeat, STALE recovery, Usage persistence, Worker dispatch |
| [`ops-spec.md`](./ops-spec.md) | EC2/Docker Compose, logging, monitoring, health 운영, storage/cleanup/retention, capacity, CI/CD |
| `decisions/` | 장기 영향을 주는 실제 Runtime 결정이 생겼을 때만 ADR 추가 |

빈 ADR 폴더를 미리 만들지는 않는다.

## 핵심 경계

```text
Browser
  ↓
API composition root
  ↓
case
  └─ JobRecord = Job Intent
       ↓
common/runtime
  ├─ DB Queue / claim
  ├─ JobExecution
  ├─ retry / lease / heartbeat
  └─ UsageRecord
       ↓
Worker composition root
  └─ recording / search / readout / evidence public capability
```

- `case = orchestrator`
- `common/runtime = executor`
- JobRecord와 Queue row는 같은 개념이 아니다.
- 사용자 재실행은 새 JobRecord / 새 `job_id`.
- 자동 인프라 retry는 같은 `job_id` + 새 `execution_id` + `attempt+1`.
- STALE은 Worker 소멸 실행 상태이며 old `case_rev`와 다른 개념이다.
- 비용/사용량의 authoritative ledger는 UsageRecord다.

## Final Contract

Runtime 구현 시 다음 문서를 직접 참조한다.

- [JobRecord / CaseView](../architecture/contracts/contract-job-record-case-view.md)
- [JobExecution](../architecture/contracts/contract-job-execution.md)
- [UsageRecord](../architecture/contracts/contract-usage-record.md)
- [AnalysisSource / RemoteCopy / DerivedAsset](../architecture/contracts/contract-analysis-source-derived.md)

schema, enum, 불변조건을 Runtime 문서로 복사해 별도 SoT를 만들지 않는다.

## 현재 구현 상태 — 2026-09-19

### 확인된 구현

- 여러 domain module Python 구현과 pytest
- `JobExecution v1.1` in-memory lifecycle
- recording fixture/in-memory public capability + `purge_case`
- Mock Pack / contract validator / boundary checker
- boundary-check GitHub Action
- root `pyproject.toml` / `uv.lock`

### 아직 구현되지 않은 Runtime

- MySQL DB Queue / claim
- lease / heartbeat / stale sweep
- API composition root
- Worker composition root
- UsageRecord DB persistence
- live / ready endpoint
- Runtime Docker Compose deployment

따라서 Runtime Tech/Ops 문서의 일부는 **현재 동작 설명이 아니라 구현 acceptance criteria**다.

## Recording / Search Benchmark와의 관계

Runtime 문서가 실측 원본을 소유하지 않는다.

```text
recording
→ media/profile/ffmpeg/storage 사실

search
→ provider compatibility / recall / cost / latency

runtime
→ 위 결과가 실행/저장/배포에 미치는 영향만 반영
```

Issue #41에서 이미 합의된 경계:

- recording은 측정 가능한 media 속성을 보장
- search는 recall/provider 적합성을 검증
- H.265 direct/copy 확인 → AnalysisSource 조건 고정 → A~D 분할 비교

참조:

- [Recording architecture input](../modules/recording/research/architecture-input-memo.md)
- [Search architecture input](../modules/search/research/architecture-input-memo.md)

## 현재 열린 Runtime/Ops 결정

### Runtime Tech

- queue/execution 물리 schema
- claim transaction
- retry max/backoff/jitter
- lease duration
- heartbeat interval
- STALE threshold
- Worker polling/sweep interval
- UsageRecord persistence / pricing config

### Ops

- Docker/Compose exact command
- log transport/retention
- disk working-set guardrail
- Object Storage 범위
- managed asset retention
- UsageRecord retention
- scaling threshold
- deployment workflow

정확한 수치는 실제 Runtime integration과 Recording/Search benchmark 결과 없이 임의 확정하지 않는다.

## Baseline Non-goals

현재 기본 구조에는 다음을 넣지 않는다.

```text
Redis / Celery / RabbitMQ / SQS / Kafka
Kubernetes / Microservices / Service Mesh
별도 DLQ
Auto Scaling
복잡한 Circuit Breaker
WebSocket/SSE progress
Prometheus/Grafana/OpenTelemetry full stack
```

관측된 failure mode가 필요성을 증명할 때 확장한다.

## Update Rule

Runtime 관련 변경 시:

1. Architecture/Final Contract 변경인지 먼저 확인한다.
2. Contract 변경이 아니라 구현 선택이면 Runtime Tech Spec에 기록한다.
3. 배포·운영 선택이면 Ops Spec에 기록한다.
4. recording/search 실험값은 Owner 문서에 남기고 Runtime에는 결정 영향만 링크한다.
5. 같은 설정값을 두 문서가 동시에 소유하지 않게 한다.

## Related

- [Architecture v4](../architecture/module-architecture.md)
- [common runtime code README](../../src/daesingo/common/README.md)
- [Pre-deploy security review](../management/pre-deploy-security-review.md)
