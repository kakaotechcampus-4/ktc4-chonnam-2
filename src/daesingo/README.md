# daesingo

대신고 백엔드 Python 패키지. 물리적으로는 FastAPI 애플리케이션 1개 + Worker 1개 + MySQL 1개로 배포한다 (`docs/architecture/module-architecture.md` §1-5 · §10-1).

| 폴더 | 무엇 | v4 절 | Owner (`docs/management/ownership.md`) |
| --- | --- | --- | --- |
| `recording/` | 블랙박스 파일·stream·시간축·구간·프레임·파생영상 | §4-모듈1 | 정철원 |
| `search/` | 긴 영상에서 사건 구간 후보 탐색 + visual verification | §4-모듈2 | 서어진 |
| `readout/` | 번호판·화면 시각 판독 (값을 확정하지 않는다) | §4-모듈3 | 신유민 |
| `evidence/` | 관찰값 확정 · 신고 규정 · Package | §4-모듈4 | 김준영 |
| `case/` | 진행 상태 · 사용자 선택 · 작업 발주 의도 · CaseView | §4-모듈5 | 유소연 |
| `common/` | DB queue · job lifecycle · usage · logging · config · storage adapters | §6-2 | 김준영 |
| `api/` | FastAPI composition root | §1-5 · §8-2 | 김준영 |
| `worker/` | Worker composition root | §1-5 · §8-2 | 김준영 |

**호출 방향** (§6-1) — 이 방향을 어기는 import는 만들지 않는다.

```text
api/worker → case → { recording, search, readout, evidence }
search → recording        readout → recording
evidence → (도메인 모듈 아무것도 호출하지 않음)
common/runtime은 바깥쪽 실행 인프라. 도메인 규칙이 common을 의존하지 않는다
```

## 상태

**아직 코드가 없다.** 데이터 계약(`docs/architecture/contracts/`)이 확정된 뒤 Owner가 채운다. 이 README는 자리를 잡아두기 위한 것이며, 폴더의 범위는 위 문서가 정한다 — 여기에 규칙을 복제하지 않는다.
