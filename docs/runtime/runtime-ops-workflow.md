# Runtime/Ops 작업 워크플로우

**Status:** Working — work process guide  
**Owner:** common/runtime — 김준영  
**Date:** 2026-10-02  
**Runtime router:** [Runtime Documentation](./README.md)

> 이 문서는 Runtime/Ops 작업을 **어떤 순서로 진행할지**만 정한다. 결정·값·threshold를 담지 않으며, 결정은 [`runtime-tech-spec.md`](./runtime-tech-spec.md) · [`ops-spec.md`](./ops-spec.md) · [`deployment-runbook.md`](./deployment-runbook.md) 또는 상위 Contract/ADR에 기록한다.

## 0. 현재 상태 정합성 검수

가장 먼저 현재 문서·코드·CI·공지 사이의 불일치를 전수 확인한다.

- [Runtime README](./README.md)
- [Runtime Tech Spec](./runtime-tech-spec.md)
- [Ops Spec](./ops-spec.md)
- [Deployment Runbook](./deployment-runbook.md)
- Final Contract — [`docs/architecture/contracts/`](../architecture/contracts/README.md)
- 현재 develop 코드
- GitHub Actions — `.github/workflows/`
- 카테캠 공식 공지

발견 항목은 다음처럼 분류한다.

```text
STALE DOC
→ 문서가 현재 구현보다 뒤처짐

CONTRACT / SPEC MISMATCH
→ 문서끼리 의미가 충돌

IMPLEMENTATION GAP
→ 설계는 확정됐지만 구현되지 않음

OPEN DECISION
→ 구현 전에 결정을 내려야 함
```

단순 문서 위생 문제는 묶어서 처리하고, 구현 방향을 잘못 유도할 수 있는 정합성 문제는 즉시 별도 Issue로 만든다.

---

## 1. 공식정보·외부 제약 리서치

설계 브레인스토밍 전에 외부에서 이미 확인할 수 있는 사실을 최대한 수집한다.

### 카테캠 / AWS

```text
EC2 제공 사양
자원 증설 가능 범위
EBS
RDS
S3
ECR
Elastic IP
ALB
GPU
CloudWatch
SSM
GitHub OIDC / IAM 정책
비용 및 사용 제한
```

### ML API / Provider

```text
지원 API
media 전달 방식
최대 입력 크기
timeout
rate limit / concurrency
지원 codec / container
비용
retention / logging / delete 정책
```

### 외부 기술 사례

현재 Open Decision을 닫는 데 필요한 범위에서 조사한다.

```text
MySQL DB Queue 사례
SKIP LOCKED
영상 처리 서버 resource 특성
ffmpeg working set
base64/JSON memory overhead
Object Storage 사용 패턴
Worker scaling 사례
```

리서치는 결정을 대신하는 것이 아니라 **Baseline과 실험 설계를 더 현실적으로 만드는 입력**으로 사용한다.

카테캠 AWS/ML API 공지처럼 공식성이 높은 자료는 [`official-inputs/`](./official-inputs/README.md)에 보존한다.

---

## 2. Open Decision 전수 수집

Runtime Tech / Ops / Runbook에 남아 있는 미결정 사항을 하나의 Decision Register로 모은다.

각 항목에는 최소 다음을 기록한다.

```text
Decision
현재 상태
관련 문서
Owner
Consult
현재 근거
결정 시점
Issue 필요 여부
ADR 필요 여부
실험 필요 여부
```

---

## 3. 결정 유형 분류

모든 결정을 같은 회의에 올리지 않는다.

### Runtime 단독 결정

Runtime 구현 내부에서 닫을 수 있는 항목.

```text
queue physical schema
claim transaction
polling interval
retry/backoff
lease/heartbeat
stale sweep
Docker service command
```

### 공동 결정

다른 모듈과 계약이 맞물리는 항목.

```text
HTTP API Contract
pricing SSOT
provider config/key naming
AnalysisSource storage/reuse
retention
```

필요한 Owner만 호출해서 Issue에서 빠르게 결정한다.

### 제품/정책 결정

```text
사용자 자산 보관기간
삭제 정책
외부 공개 endpoint
사용자 flow와 연관된 retention
```

### 실측 후 결정

현재 숫자를 확정하면 안 되는 항목.

```text
Worker 수
EC2 증설
disk guardrail
Object Storage
RDS
전용 Queue
GPU
capacity threshold
```

---

## 4. Provisional Baseline v0.1 확정

구현에 필요한 값이 TBD로 남아 구현자가 임의 결정하지 않도록 초기값을 정한다.

단, 최종값이 아님을 다음 라벨로 명시한다.

```text
Provisional Baseline
Initial Default
```

예:

```text
worker concurrency
retry max
backoff
polling interval
lease duration
heartbeat interval
STALE threshold
stale sweep interval
```

각 값에는 반드시 다음을 붙인다.

```text
값
근거
왜 지금 이 값을 쓰는가
어떤 실험으로 검증하는가
변경 가능 조건
```

### 구분

```text
Implementation Baseline
→ 시스템을 실행하기 위해 지금 필요한 숫자
→ 구현 전 결정

Operational Threshold
→ 실제 성능/운영 데이터를 보고 정할 숫자
→ 실험 후 결정
```

임의의 CPU 70%, Disk 80% 같은 운영 threshold는 아직 만들지 않는다.

---

## 5. 결정·후속 작업 Issue화

Decision Register를 정리한 뒤 필요한 Issue를 일괄 생성한다.

Issue는 대략 다음 종류로 나눈다.

```text
A. 정합성 수정
B. 공동 계약 결정
C. Runtime 구현
D. 실험
E. 문서 반영
```

공동 결정 Issue에는 필요한 담당자만 호출한다.

이미 확정된 사항은 다시 토론하지 않고 바로 구현 Issue로 넘긴다.

---

## 6. Runtime Implementation Plan 작성

위 결정 결과를 기준으로 실제 구현 담당자에게 넘길 플래닝 문서를 만든다.

우선순위는 대략:

```text
1. MySQL Runtime persistence
   - DB Queue
   - JobExecution
   - UsageRecord

2. Worker
   - claim
   - retry
   - lease
   - heartbeat
   - stale recovery

3. API composition root
   - HTTP API Contract
   - Case command
   - Runtime dispatch
   - 202 Accepted

4. Docker / Compose
   - api
   - worker
   - mysql
   - volume
   - config

5. Runtime configuration / secret injection

6. Structured logging
   - trace_id
   - case_id
   - job_id
   - execution_id

7. /health/live
   /health/ready

8. Runtime integration tests
```

Deployment automation은 이 실행 단위가 만들어진 뒤 별도 단계로 붙인다.

---

## 7. CI 확장

현재 boundary/contract CI에 deterministic test를 점진적으로 추가한다.

```text
boundary / fixture
+
repo-wide pytest
+
Mock validator
+
Ruff
+
type checker
+
secret scan
```

pytest 내부에서도 성격을 구분한다.

```text
Unit
Contract
Integration
Runtime Integration
External / Real E2E
```

일반 PR CI에는 다음을 넣는다.

```text
Unit
Contract
deterministic Integration
필요 시 MySQL Runtime Integration
```

실제 ML API 호출, 긴 영상, P2 Capacity Smoke는 일반 PR gate와 분리한다.

---

## 8. Baseline 기반 구현

이미 확정된 Architecture/Contract와 Provisional Baseline을 기준으로 develop 구현을 진행한다.

```text
확정된 것
→ 바로 구현

공동 결정이 필요한 것
→ Issue 결과 반영

실측이 필요한 것
→ Baseline으로 먼저 구현
```

완벽한 연구가 끝날 때까지 구현을 멈추지 않는다.

---

## 9. 구현과 동시에 관측 가능하게 만들기

각 구현 Task를 단순히 "기능 구현"으로 끝내지 않는다.

가능하면 다음을 함께 정의한다.

```text
Implementation
Acceptance Test
Observability
Experiment
Evidence location
Decision affected
```

예:

```text
Worker claim 구현

→ duplicate claim integration test
→ queue wait / claim latency 기록 가능
→ P2에서 Worker resource 측정
→ Worker scaling 판단 근거로 사용
```

---

## 10. Runtime 실험 수행

구현된 Baseline을 기준으로 실제 실험을 진행한다.

우선 다음 조건에서 확인한다. P2 계획은 [`experiments/elice-runtime-capacity-smoke-plan.md`](./experiments/elice-runtime-capacity-smoke-plan.md)에 있다.

```text
P2 Runtime Capacity Smoke
Worker concurrency = 1
```

확인 항목:

```text
CPU
RAM
Worker RSS
MySQL contention
disk working set
ffmpeg temp
base64/JSON construction
provider latency
cleanup
failure recovery
restart/reuse
```

그 뒤 필요하면 다음 실험으로 확장한다.

```text
concurrency >= 2
30분~1시간 P3
Object Storage
EC2 증설
RDS
전용 Queue
GPU
```

---

## 11. 실험 결과 기록

실험은 실행만 하고 끝내지 않는다.

최소한 다음을 남긴다.

```text
executed_at
commit SHA
환경
입력
Baseline config
측정값
결과
known limitation
```

Raw 결과와 반복 가능한 결론을 분리한다.

```text
실험 결과
→ docs/runtime/experiments/

반복 가능한 운영 결론
→ Runtime Tech / Ops Spec
```

---

## 12. Baseline 및 설계 갱신

실험 결과에 따라 다음 중 하나를 결정한다.

```text
Baseline 유지
Baseline 수정
Architecture 변경 검토
Infrastructure 확장
```

장기적으로 여러 구현에 영향을 주는 구조 결정이면 ADR로 승격한다.

단순 tuning 값 변경까지 ADR을 만들지는 않는다.

---

## 전체 흐름

```text
정합성 검수
      ↓
공식정보 / 외부 제약 리서치
      ↓
Open Decision 전수 수집
      ↓
Runtime 단독 / 공동 / 정책 / 실측 분류
      ↓
필요한 결정 Issue 처리
      ↓
Provisional Baseline v0.1
      ↓
Runtime Implementation Plan
      ↓
CI 확장 + Runtime 구현
      ↓
관측 가능한 상태 확보
      ↓
Runtime Integration / P2 / Real E2E
      ↓
결과 기록
      ↓
Tech / Ops / ADR 갱신
      ↓
다음 Baseline
```

## 핵심 원칙

**추측으로 인프라를 늘리지 않고, 그렇다고 모든 값을 TBD로 남겨 구현자가 임의 결정하게 두지도 않는다.**

```text
공식정보와 기존 실측으로
가장 합리적인 초기 Baseline을 잡는다.

↓

일단 구현한다.

↓

실제 환경에서 측정한다.

↓

결과를 기록한다.

↓

필요한 부분만 설계와 인프라를 확장한다.
```
