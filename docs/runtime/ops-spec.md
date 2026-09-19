# Runtime Ops Spec

**Status:** Working — operations spec  
**Owner:** common/runtime — 김준영  
**Deployment baseline:** EC2 1대 + Docker Compose + MySQL  
**Architecture SoT:** [`docs/architecture/module-architecture.md`](../architecture/module-architecture.md)  
**Logical Data Model:** [`docs/architecture/erd-draft.md`](../architecture/erd-draft.md)  
**Alignment ADR:** [ERD ↔ Runtime 정합화](../architecture/contracts/adr/adr-erd-runtime-alignment-2026-09-19.md)

> 이 문서는 배포된 Runtime을 **어떻게 운영·관찰·복구·확장할지** 정한다. Final Contract와 Logical ERD가 정의한 논리 의미·관계를 바꾸지 않으며, JobExecution/UsageRecord persistence와 queue algorithm은 [`runtime-tech-spec.md`](./runtime-tech-spec.md)이 소유한다.

## 1. 문서 경계

### 이 문서가 소유한다

- 배포 topology
- api / worker / mysql 운영 경계
- logging / privacy guardrail
- monitoring / alert 방향
- health/readiness의 운영 사용
- disk working set과 storage guardrail
- cleanup / retention 운영
- Object Storage 도입 기준
- capacity / scaling trigger
- CI/CD 및 pre-deploy validation
- 운영 장애 시 확장 기준

### 이 문서가 소유하지 않는다

- DB Queue claim/retry/lease algorithm — [Runtime Tech Spec](./runtime-tech-spec.md)
- JobExecution/UsageRecord schema — Final Data Contract
- cross-domain logical relationship / cardinality — [Logical ERD](../architecture/erd-draft.md)
- JSON vs 관계 테이블 같은 Runtime 물리 persistence — [Runtime Tech Spec](./runtime-tech-spec.md)
- Recording/Search benchmark 원본 — 각 module Owner
- 제품 workflow — Product / case
- Search/Readout 품질 threshold — 각 module/eval

## 2. 배포 Baseline

카테캠 현재 환경 제약 기준 baseline:

```text
Region      ap-northeast-2
EC2         t3.medium
CPU         2 vCPU
RAM         4GB
Disk        50GB SSD
OS          Ubuntu 24.04 LTS

EC2 1대
└─ Docker Compose
   ├─ api
   ├─ worker
   └─ mysql
```

API와 Worker는 같은 repository/image 계열을 사용하는 modular monolith의 두 composition root다.

RDS, ALB, Elastic IP, 추가 EC2는 기본 제공으로 가정하지 않는다.

## 3. 현재 상태와 목표 상태

### 현재 develop에서 확인된 것

- domain module 구현 및 Mock integration
- `JobExecution` in-memory lifecycle
- `recording` fixture/in-memory capability
- boundary / contract fixture GitHub Action
- `api/`, `worker/` 책임 README

### 아직 없는 것

- 실제 api composition root
- 실제 worker composition root
- MySQL DB Queue
- Runtime Docker Compose
- 배포 workflow
- live/ready endpoint
- 운영 log pipeline
- queue/lease/heartbeat metric

따라서 이 문서의 배포/monitoring 절은 **현재 동작 설명이 아니라 구현 목표와 운영 acceptance criteria**다.

## 4. Docker / Process 운영

목표 process:

```text
api
→ FastAPI request / case command / Runtime dispatch

worker
→ Runtime claim / domain public capability 실행

mysql
→ product state + Runtime persistence
```

원칙:

- API와 Worker가 서로 private implementation을 import해 orchestration loop를 만들지 않는다.
- Worker crash가 API process crash로 이어지지 않아야 한다.
- MySQL은 single EC2 baseline이지만 volume을 container ephemeral layer와 분리한다.
- api/worker image는 가능한 같은 dependency/runtime baseline을 사용하고 command만 분리한다.
- secret은 image나 repository에 bake하지 않는다.

정확한 Dockerfile/Compose service command는 composition root 구현 후 그 entrypoint에 맞춰 닫는다.

## 5. Python / Dependency Runtime

팀 문서 기준 목표는 Python 3.12 + root `pyproject.toml` + `uv.lock`이다.

다만 2026-09-19 현재 repository는 아직 불일치가 있다.

```text
root pyproject.toml   requires-python >=3.10
uv.lock               requires-python >=3.13
boundary CI           Python 3.11
목표                  Python 3.12
```

따라서 “Python 3.12 통일 완료”로 보지 않는다.

구현 체크:

- [ ] root `pyproject.toml`을 3.12 기준으로 정합
- [ ] `.python-version` 정합
- [ ] `uv.lock` 3.12 기준 재생성
- [ ] `uv sync --locked` 재현
- [ ] GitHub Actions Python 3.12 통일
- [ ] repo-wide type checker 한 개로 수렴

Python version의 executable SoT는 prose가 아니라 실제 config/workflow다.

## 6. Structured Logging

Runtime 운영 로그는 key-value structured log를 기본으로 한다.

권장 correlation:

```text
trace_id
case_id
job_id
execution_id
module
event
duration_ms
status
```

예:

```json
{
  "level": "INFO",
  "event": "job.execution.completed",
  "trace_id": "tr_...",
  "case_id": "case_...",
  "job_id": "job_...",
  "execution_id": "exec_...",
  "module": "search",
  "duration_ms": 81231,
  "status": "SUCCEEDED"
}
```

## 7. Logging / Privacy Guardrail

실제 사용자 데이터가 들어가는 운영 단계에서는 다음 원문을 일반 운영 로그에 남기지 않는다.

- 번호판 문자열
- 정확한 GPS 좌표 / 상세 위치 원문
- 원본 영상 / frame bytes
- 불필요한 전체 filesystem path
- 외부 AI request/response payload 전문
- 사용자 free text 전문
- API key / access token / secret

`UsageRecord` 역시 raw provider payload를 보존하지 않는다.

현재 `docs/management/pre-deploy-security-review.md` 정책대로 Mock/합성 데이터 중심 개발 중에는 전역 masking logger를 별도 merge blocker로 보지 않는다.

하지만 실제 사용자 데이터/외부 provider/배포 단계 전에는 해당 security review를 다시 실행해야 한다.

## 8. Monitoring Baseline

초기에는 Prometheus/Grafana/OpenTelemetry full stack을 baseline으로 두지 않는다.

1차 관측 수단:

```text
structured stdout
→ AWS log collection

+
Runtime DB query
+
UsageRecord
+
EC2 기본 CPU/RAM/disk 지표
```

최소 운영 질문:

- queue wait이 얼마나 되는가
- oldest queued Job이 얼마나 오래됐는가
- SUCCEEDED / FAILED / STALE / CANCELLED 비율은 어떤가
- retry가 얼마나 발생하는가
- execution latency가 얼마나 되는가
- provider invocation 비용/latency가 얼마인가
- Worker heartbeat/lease가 정상인가
- local disk working set이 얼마나 되는가
- OOM/swap/CPU saturation이 반복되는가

현재 DB Runtime이 없으므로 queue/lease/heartbeat 지표는 아직 실제 운영 metric이 아니다.

## 9. Health / Readiness 운영

Runtime Tech Spec의 endpoint 의미:

```text
/health/live
→ API process가 살아 있는가

/health/ready
→ 필수 Runtime dependency가 준비됐는가
```

운영 원칙:

- liveness failure는 process restart 후보
- readiness failure는 신규 traffic/처리 준비 불가 신호
- 외부 AI provider 하나의 장애를 API 전체 liveness failure로 취급하지 않음
- Worker는 Runtime DB의 heartbeat/lease 기반으로 별도 관측 가능

실제 restart/alert threshold는 deployment 환경이 생긴 뒤 정한다.

## 10. Storage Lifecycle

Final recording Contract의 lifecycle 용어를 따른다.

```text
External Source Reference
Managed Source Copy
AnalysisSource
RemoteCopy
IncidentClip
DerivedAsset
```

### External Source

사용자 원본은 서비스가 overwrite/delete하지 않는다.

`purge_case()`는 서비스 내부 reference를 제거할 수 있지만 사용자 기기/외부 source 자체를 물리 삭제하지 않는다.

### Managed / Derived Assets

서비스 관리 사본과 파생물은 retention/cleanup 대상이다.

### RemoteCopy

provider delete를 지원하면 삭제 요청할 수 있다. 즉시 삭제를 보장할 수 없으면 `DeletionReport`에 `PENDING_EXPIRY`를 남긴다.

provider delete API 호출의 구현 경계는 provider adapter가 소유한다.

## 11. Local Disk Guardrail

50GB local disk를 장시간 원본의 영구 저장소로 설계하지 않는다.

동시에 local disk는 다음이 경쟁한다.

```text
MySQL data
Docker image/layer
temp transform output
AnalysisSource
IncidentClip / DerivedAsset
logs
OS working space
```

따라서 “50GB가 있으니 영상 X시간 저장” 같은 단일 계산을 하지 않는다.

필요한 것은 Real Recording Benchmark를 통한 **실행 working set** 측정이다.

관측 대상:

- source ingest byte
- transform temp byte
- proxy/AnalysisSource byte
- peak simultaneous disk
- cleanup 이후 steady-state disk

## 12. Recording / Search Benchmark Dependency

Runtime/Ops가 benchmark 원본을 소유하지 않는다.

### recording Owner가 제공할 것

- media/profile/ffmpeg/storage 측정
- transform time
- peak disk
- AnalysisSource materialization 특성

### search Owner가 제공할 것

- provider compatibility
- H.265 direct/copy 여부
- recall
- token/cost/latency
- A~D strategy experiment

Issue #41로 이미 닫힌 경계:

```text
recording → measurable media property 보장
search    → recall/provider suitability 검증
```

또한 합의된 실험 순서:

```text
H.265 direct/copy 확인
→ 실험용 AnalysisSource 조건 고정
→ A~D 분할 비교
```

Runtime/Ops에는 **benchmark 결과로 결정된 운영 영향만** 남긴다.

## 13. Object Storage 도입 기준

Object Storage를 baseline 의무로 두지 않는다.

다음이 확인되면 도입 범위를 결정한다.

- 50GB local working set이 안전하지 않음
- 여러 실행 간 재사용을 위해 local-only storage가 부족
- instance 교체/재배포 시 보존해야 할 managed asset 존재
- upload/download overhead보다 persistence 이점이 큼
- lifecycle/retention을 object store 정책으로 관리하는 편이 단순

도입 시에도 domain Contract에 provider/storage locator를 노출하지 않고 storage adapter 뒤에 둔다.

## 14. Retention / Cleanup

현재 exact retention 일수는 미결이다.

금지:

- 근거 없이 “7일”, “30일” 같은 숫자 선결
- video asset retention과 UsageRecord retention 자동 동일시
- 사용자 External Source까지 서비스 purge 대상처럼 취급

결정해야 할 축:

```text
Managed Source Copy retention
AnalysisSource retention
IncidentClip retention
DerivedAsset retention
RemoteCopy expiry/delete
UsageRecord retention
log retention
```

각 값은 개인정보/재현성/비용/사용자 flow를 함께 보고 결정한다.

## 15. Provider 장애 운영

Circuit Breaker는 현재 baseline이 아니다.

초기 대응:

```text
provider failure taxonomy
+ retry policy
+ terminal JobExecution
+ structured log
+ UsageRecord
+ queue wait 관측
```

다음 현상이 반복되면 Circuit Breaker를 검토한다.

```text
provider 장기 장애
→ retry 반복
→ queue 적체
→ 정상 작업도 지연
```

threshold를 미리 invent하지 않는다.

## 16. DB Queue → 전용 Queue 확장 기준

MySQL Queue를 유지하다 다음이 실제 문제로 반복되면 Redis/SQS/RabbitMQ 등 전용 queue를 검토한다.

- Worker 다중화로 claim contention
- queue workload가 제품 DB latency 악화
- scheduling/delay/redrive 요구가 DB 구현 복잡도를 크게 증가
- DB 장애와 queue 장애를 분리해야 함

도입 여부는 기술 선호가 아니라 관측된 failure mode로 결정한다.

## 17. Worker 1 → Worker Pool 확장 기준

다음 두 조건이 함께 필요하다.

```text
queue wait가 실제 UX 문제
+
provider rate limit / CPU/RAM/I/O에 병렬 여유
```

CPU-bound ffmpeg/OCR와 network-bound provider call을 구분해 병목을 측정한다.

Worker 수를 늘리기 전에 DB claim/lease가 concurrent-safe함을 integration test로 확인한다.

## 18. 카테캠 자원 확장 기준

### EC2 사양 상향

같은 workload에서 반복적으로:

- OOM
- swap thrashing
- 지속 CPU saturation
- Runtime queue wait 증가

가 재현될 때 요청한다.

### Disk 확장

cleanup/retention/Object Storage 분리를 적용한 뒤에도 **실행 working set** 때문에 50GB가 부족할 때.

단순 장기 영상 보관을 위해 EBS만 계속 늘리는 방향은 baseline이 아니다.

### RDS

- MySQL과 ffmpeg/OCR/Worker가 CPU/RAM/I/O를 지속 경쟁
- managed backup/recovery가 필요
- DB를 EC2 lifecycle에서 분리해야 함

일 때 검토한다.

### Elastic IP

demo/domain endpoint의 IP 안정성이 실제 요구일 때.

### ALB

API server 2대 이상 또는 load balancing/health routing이 필요할 때.

### GPU

자체 inference가 실험이 아니라 제품 Runtime 필수 경로가 됐고 CPU/provider 대안이 없을 때.

## 19. CI Quality Gate — 현재와 목표

### 현재 실제 CI

`.github/workflows/boundary-check.yml`:

```text
pull_request → develop/main
push         → develop
workflow_dispatch

Python 3.11
python scripts/check_boundaries.py
python scripts/check_contract_fixtures.py
```

따라서 현재 CI가 이미 repo-wide pytest/Ruff/type/gitleaks까지 수행한다고 쓰지 않는다.

### 목표 확장 순서

1. Python 3.12 정합
2. `uv sync --locked`
3. boundary / contract fixture
4. repo-wide pytest
5. Mock validator
6. root Ruff
7. 선택한 repo-wide type checker
8. pre-deploy secret scan

외부 AI 실제 호출은 일반 PR CI의 deterministic gate에서 분리한다.

## 20. Test / Validation 운영

테스트 층:

| 계층 | 목적 |
| --- | --- |
| Unit | pure/domain/runtime state logic |
| Contract / Boundary | Final Contract + import boundary |
| Integration | module public capability 접합 |
| Runtime Integration | FastAPI + MySQL Queue + Worker |
| Real E2E | 실제 media/provider 성능·비용 |

Real E2E는 비용·rate limit·외부 장애 때문에 일반 PR CI와 분리한다.

coverage는 미검증 경로를 찾는 보조지표로 사용하며 근거 없는 특정 percentage gate를 먼저 두지 않는다.

## 21. Pre-deploy Review

실제 사용자 데이터/외부 provider/배포 전에는 최소 다음을 재검토한다.

- logging에 민감 원문이 남는가
- secret이 repo/image/log에 노출되는가
- provider upload/delete/expiry가 문서와 일치하는가
- cleanup/retention이 실제 adapter에 구현됐는가
- health/readiness가 deployment에서 동작하는가
- disk peak가 baseline 환경을 넘지 않는가
- Runtime queue recovery가 실제 MySQL에서 검증됐는가
- UsageRecord와 실제 비용 발생이 정합하는가

상세 security checklist는 [`docs/management/pre-deploy-security-review.md`](../management/pre-deploy-security-review.md)를 따른다.

## 22. Non-goals

현재 baseline에서 일부러 만들지 않는다.

```text
Redis / Celery / RabbitMQ / SQS / Kafka
Kubernetes / Service Mesh / Event Bus
Microservices
Auto Scaling
별도 DLQ infrastructure
WebSocket/SSE progress
복잡한 Circuit Breaker
Prometheus/Grafana/OpenTelemetry full stack
```

영구 금지가 아니라 현재 증거가 없는 복잡도다.

## 23. Open Ops Decisions

- [ ] Dockerfile / Compose exact service command
- [ ] MySQL volume/backup baseline
- [ ] production log transport
- [ ] log retention
- [ ] health alert/restart threshold
- [ ] disk working-set guardrail
- [ ] Object Storage 사용 범위
- [ ] Managed asset retention
- [ ] UsageRecord retention
- [ ] provider RemoteCopy cleanup 운영
- [ ] capacity/scaling threshold
- [ ] deployment workflow
- [ ] secret scan gate

Recording/Search benchmark와 실제 Runtime implementation이 생기기 전까지 수치를 임의 확정하지 않는다.

## References

- [Architecture v4](../architecture/module-architecture.md)
- [Logical ERD](../architecture/erd-draft.md)
- [ERD ↔ Runtime 정합화 ADR](../architecture/contracts/adr/adr-erd-runtime-alignment-2026-09-19.md)
- [Runtime Tech Spec](./runtime-tech-spec.md)
- [AnalysisSource / Derived Asset Contract](../architecture/contracts/contract-analysis-source-derived.md)
- [UsageRecord Contract](../architecture/contracts/contract-usage-record.md)
- [Recording architecture input](../modules/recording/research/architecture-input-memo.md)
- [Search architecture input](../modules/search/research/architecture-input-memo.md)
- [Pre-deploy security review](../management/pre-deploy-security-review.md)
