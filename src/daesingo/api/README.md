# `api` — FastAPI composition root

**Owner:** 김준영 (공통 기반/운영) · **경계:** `docs/architecture/module-architecture.md` §1-5 · §8-1 · §8-2

- 배포 단위 「API 1」. 긴 작업은 HTTP 요청 안에서 끝내지 않는다 — `case`가 만든 `JobIntent`를 queue에 넣고 `202 Accepted`를 반환한다.
- 즉시 처리하는 것(§8-1): `CaseView` 조회 · hint 수정 · candidate 선택 · pure evidence recompute · requirement recompute · 상태 전이.
- 인증은 MVP 최소 수준이며 방식은 미결(§1-7 A2).
- `web`이 부르는 유일한 read endpoint는 `case.get_view()`를 노출하는 것 하나다 (§4-모듈6 ③).

## 상태

**아직 코드가 없다.** 데이터 계약(`docs/architecture/contracts/`)이 확정된 뒤 Owner가 채운다. 이 README는 자리를 잡아두기 위한 것이며, 폴더의 범위는 위 문서가 정한다 — 여기에 규칙을 복제하지 않는다.
