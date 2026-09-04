# `readout` — 번호판·화면값 판독

**Owner:** 신유민 (`docs/management/ownership.md`) · **경계:** `docs/architecture/module-architecture.md` §4-모듈3 · **문서 작업공간:** `docs/modules/readout/`

## 이 폴더가 하는 일 (요약 — 원문은 §4-모듈3)

대상 차량 association·번호판 detection·multi-frame·best frame·OCR·consensus·abstain·Overlay Timestamp OCR과 검증·근거 frame refs

## 이 폴더가 알면 안 되는 것 (§4-모듈3 「알면 안 되는 것」)

최종 발생시각 source 우선순위 / 신고 요건·기한 / Report Type / 확정 번호판 값 / 사용자 workflow stage / Report Video에 사후 삽입된 Timestamp를 근거로 OCR

## 공개 함수

§4-모듈3 「Public Capability」의 함수 이름은 예시다. 실제 시그니처는 데이터 계약에서 확정한 뒤 여기에 적는다. 다른 모듈은 **공개 함수만** 호출한다.

## 상태

**아직 코드가 없다.** 데이터 계약(`docs/architecture/contracts/`)이 확정된 뒤 Owner가 채운다. 이 README는 자리를 잡아두기 위한 것이며, 폴더의 범위는 위 문서가 정한다 — 여기에 규칙을 복제하지 않는다.
