# `search` — 사건 탐색

**Owner:** 서어진 (`docs/management/ownership.md`) · **경계:** `docs/architecture/module-architecture.md` §4-모듈2 · **문서 작업공간:** `docs/modules/search/`

## 이 폴더가 하는 일 (요약 — 원문은 §4-모듈2)

Coarse 후보 구간 생성·Fine/Classification visual verification·4종 event routing·`AnalysisRun` 실행 기록·실패 taxonomy 기록·`providers/`(외부 AI API 호출은 여기서만)

## 이 폴더가 알면 안 되는 것 (§4-모듈2 「알면 안 되는 것」)

신고 규정·Report Type / case stage / 확정 Evidence / 사용자 개인정보 / eval의 존재 / 신고용 mp4 생성 / `if eval_mode`

## 공개 함수

§4-모듈2 「Public Capability」의 함수 이름은 예시다. 실제 시그니처는 데이터 계약에서 확정한 뒤 여기에 적는다. 다른 모듈은 **공개 함수만** 호출한다.

## 상태

**아직 코드가 없다.** 데이터 계약(`docs/architecture/contracts/`)이 확정된 뒤 Owner가 채운다. 이 README는 자리를 잡아두기 위한 것이며, 폴더의 범위는 위 문서가 정한다 — 여기에 규칙을 복제하지 않는다.
