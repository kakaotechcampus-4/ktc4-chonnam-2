# `case` — Workflow / Orchestration — 유일한 지휘자

**Owner:** 유소연 (`docs/management/ownership.md`) · **경계:** `docs/architecture/module-architecture.md` §4-모듈5 · **문서 작업공간:** `docs/modules/case/`

## 이 폴더가 하는 일 (요약 — 원문은 §4-모듈5)

자연어 단서 구조화·상태 기계·Candidate selection·**`JobIntent` 생성**·rerun_policy·`EvidenceNeeds` → JobIntent·stale 결과 적용 여부·`CaseView` projection·`USER_REVIEWED`·correction 로그 export

## 이 폴더가 알면 안 되는 것 (§4-모듈5 「알면 안 되는 것」)

130MB 등 규정 숫자 / OCR threshold / prompt 내용 / Overlay가 왜 우선인지 같은 evidence 정책 / codec·ffmpeg / Worker lifecycle 구현(그건 `common/`)

## 공개 함수

§4-모듈5 「Public Capability」의 함수 이름은 예시다. 실제 시그니처는 데이터 계약에서 확정한 뒤 여기에 적는다. 다른 모듈은 **공개 함수만** 호출한다.

## 상태

**아직 코드가 없다.** 데이터 계약(`docs/architecture/contracts/`)이 확정된 뒤 Owner가 채운다. 이 README는 자리를 잡아두기 위한 것이며, 폴더의 범위는 위 문서가 정한다 — 여기에 규칙을 복제하지 않는다.
