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

## 상태

**아직 코드가 없다.** 데이터 계약(`docs/architecture/contracts/`)이 확정된 뒤 Owner가 채운다. 이 README는 자리를 잡아두기 위한 것이며, 폴더의 범위는 위 문서가 정한다 — 여기에 규칙을 복제하지 않는다.
