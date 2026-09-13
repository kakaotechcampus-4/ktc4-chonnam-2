# `evidence` — 증거 확정 / 신고 정책 / Package

**Owner:** 김준영 (`docs/management/ownership.md`) · **경계:** `docs/architecture/module-architecture.md` §4-모듈4 · **문서 작업공간:** `docs/modules/evidence/`

## 이 폴더가 하는 일 (요약 — 원문은 §4-모듈4)

Observation → confirmed Evidence·Timestamp 최종 resolution·사용자 correction 적용·`EvidenceNeeds`·Visual Event → Report Type 매핑·신고 요건 검사(PASS/WARN/BLOCK)·신고문 Template·`ReportPackage`·handoff

## 이 폴더가 알면 안 되는 것 (§4-모듈4 「알면 안 되는 것」)

AI model/prompt / OCR library / ffmpeg / Worker lease·heartbeat / 사용자가 어느 화면에 있는지 / 외부 시스템에 직접 작업 발주. **순수 함수 모듈** — 다른 도메인 모듈을 호출하지 않는다

## 공개 함수

§4-모듈4 「Public Capability」의 함수 이름은 예시다. 실제 시그니처는 데이터 계약에서 확정한 뒤 여기에 적는다. 다른 모듈은 **공개 함수만** 호출한다.

## 상태

**아직 코드가 없다.** 데이터 계약(`docs/architecture/contracts/`)이 확정된 뒤 Owner가 채운다. 이 README는 자리를 잡아두기 위한 것이며, 폴더의 범위는 위 문서가 정한다 — 여기에 규칙을 복제하지 않는다.
