# `common` — runtime 기반 (도메인 모듈이 아니다)

**Owner:** 김준영 (공통 기반/운영) · **Architecture 경계:** `docs/architecture/module-architecture.md` §6-2 · §2 원칙 6 · §5-13  
**Runtime 문서:** [`docs/runtime/README.md`](../../../docs/runtime/README.md)

여덟 번째 도메인 모듈이 아니다. 「이 작업이 왜 필요한가」를 판단하지 않고 **실제로 실행만** 한다.

```text
db        MySQL 8.4 / InnoDB 기반 Runtime persistence
jobs      DB Queue · JobExecution lifecycle · retry · lease · heartbeat · stale recovery
usage     UsageRecord — 외부 capability/provider invocation 단위 사용량·비용 원장
logging   structured operational logging 기반
config    Runtime configuration
storage   storage adapters
```

- **JobRecord는 case가 소유하는 append-only Intent**다. Queue row나 execution lifecycle과 동일시하지 않는다.
- **JobExecution은 common/runtime이 소유하는 실행 1회분 기록**이다.
- 사용자 재실행은 새 JobRecord / 새 `job_id`, 자동 인프라 retry는 같은 `job_id` + 새 `execution_id` + 증가한 `attempt`를 사용한다.
- 작업 **발주 의도와 부분 재실행 정책**은 `case`가 소유한다. 여기는 execution lifecycle만 소유한다.
- `case`가 Worker 구현을 import하고 Worker가 다시 `case`/domain module을 import하는 순환을 만들지 않는다. 연결은 `api/`·`worker/` composition root가 한다.
- Runtime 구현 세부는 [`docs/runtime/runtime-tech-spec.md`](../../../docs/runtime/runtime-tech-spec.md), 배포·운영 기준은 [`docs/runtime/ops-spec.md`](../../../docs/runtime/ops-spec.md)를 따른다.

## 현재 구현

1차 Mock E2E 범위로 `JobExecution` v1.1 모델, 공용 fixture loader와 in-memory lifecycle을 구현했다. `InMemoryJobExecutionStore`는 attempt 증가와 허용 상태 전이를 검증한다.

아직 실제 구현되지 않은 범위:

- MySQL DB Queue / claim
- lease / heartbeat / stale sweep
- Runtime UsageRecord DB persistence
- API / Worker composition root
- Runtime health endpoint

따라서 README의 Runtime 항목을 구현 완료로 해석하지 않는다.
