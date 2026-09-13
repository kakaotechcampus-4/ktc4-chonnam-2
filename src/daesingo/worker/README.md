# `worker` — Worker composition root

**Owner:** 김준영 (공통 기반/운영) · **경계:** `docs/architecture/module-architecture.md` §1-5 · §6-2 · §8-2

- 배포 단위 「Worker 1」. `common/jobs`에서 row를 claim → RUNNING + heartbeat → 도메인 모듈의 **public capability**를 dispatch → 결과 ref + usage 기록.
- `case_rev`가 현재와 다르면 결과를 STALE로 처리하고 `CaseView`를 덮지 않는다 (§8-2).
- Background로 가는 것(§8-1): 큰 source/proxy 준비 · RemoteCopy upload · Coarse/Fine 외부 AI · 장시간 OCR · Incident Clip / Report Video export.

## 상태

**아직 코드가 없다.** 데이터 계약(`docs/architecture/contracts/`)이 확정된 뒤 Owner가 채운다. 이 README는 자리를 잡아두기 위한 것이며, 폴더의 범위는 위 문서가 정한다 — 여기에 규칙을 복제하지 않는다.
