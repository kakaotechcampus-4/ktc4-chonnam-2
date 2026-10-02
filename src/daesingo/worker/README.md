# `worker` — Worker composition root

**Owner:** 김준영 (공통 기반/운영) · **경계:** `docs/architecture/module-architecture.md` §1-5 · §6-2 · §8-2

- 배포 단위 「Worker 1」. `common/jobs`에서 row를 claim → RUNNING + heartbeat → 도메인 모듈의 **public capability**를 dispatch → 결과 ref + usage 기록.
- `STALE`은 실행 중 Worker가 살아 있지 않다고 Runtime이 판정한 terminal 실행 상태다. 오래된 `case_rev`의 결과와는 다른 개념이다 — 그런 실행은 `SUCCEEDED`를 유지하고, `case`가 그 `produced`를 domain state에 반영하지 않아 현재 `CaseView`를 덮지 않는다 (`docs/architecture/contracts/contract-job-execution.md` §6 · §9-8).
- Background로 가는 것(§8-1): 큰 source/proxy 준비 · RemoteCopy upload · Coarse/Fine 외부 AI · 장시간 OCR · Incident Clip / Report Video export.

## 상태

**아직 코드가 없다.** 데이터 계약(`docs/architecture/contracts/`)이 확정된 뒤 Owner가 채운다. 이 README는 자리를 잡아두기 위한 것이며, 폴더의 범위는 위 문서가 정한다 — 여기에 규칙을 복제하지 않는다.
