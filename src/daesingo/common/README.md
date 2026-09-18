# `common` — runtime 기반 (도메인 모듈이 아니다)

**Owner:** 김준영 (공통 기반/운영) · **경계:** `docs/architecture/module-architecture.md` §6-2 · §2 원칙 6 · §5-13

여덟 번째 도메인 모듈이 아니다. 「이 작업이 왜 필요한가」를 판단하지 않고 **실제로 실행만** 한다.

```text
db        MySQL 8.4 / InnoDB 연결
jobs      DB Queue · JobRecord lifecycle (QUEUED → RUNNING → SUCCEEDED / FAILED / STALE) · lease · heartbeat · retry timing
usage     UsageRecord — 외부 API 호출 단위 사용량·비용·pricing snapshot
logging   마스킹 로거 — 번호판·정확한 GPS·원본 frame·외부 API payload 전문·사용자 free text 전문은 남기지 않는다 (§8-5)
config
storage   storage adapters
```

- 작업 **발주 의도와 부분 재실행 정책**은 `case`가 소유한다. 여기는 execution lifecycle만 소유한다 (§4-모듈5 ④).
- `case`가 Worker 구현을 import하고 Worker가 다시 `case`/`search`를 import하는 **순환을 만들지 않는다.** 연결은 `api/`·`worker/` composition root가 한다.

## 현재 구현

1차 Mock E2E 범위로 `JobExecution` v1.1 모델, 공용 fixture loader와 in-memory lifecycle을 구현했다. `InMemoryJobExecutionStore`는 attempt 증가와 허용 상태 전이를 검증하며 실제 DB Queue, lease, heartbeat는 후속 통합 대상이다.
