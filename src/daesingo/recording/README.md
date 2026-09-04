# `recording` — Source / Media / Timeline 계층

**Owner:** 정철원 (`docs/management/ownership.md`) · **경계:** `docs/architecture/module-architecture.md` §4-모듈1 · **문서 작업공간:** `docs/modules/recording/`

## 이 폴더가 하는 일 (요약 — 원문은 §4-모듈1)

사용자 원본 참조·파일과 stream 사실·시간축·파일 경계 해석(`resolve_span`)·시각 후보·GPS 관찰·분석용 사본·RemoteCopy registry·Incident Clip·Report Video·보관/삭제

## 이 폴더가 알면 안 되는 것 (§4-모듈1 「알면 안 되는 것」)

사건 종류·법적 위반 / 신고 규정 / 어느 Timestamp source가 정답인지 / AI 모델 / case stage / AI provider API 직접 호출(그건 `search/providers/`)

## 공개 함수

§4-모듈1 「Public Capability」의 함수 이름은 예시다. 실제 시그니처는 데이터 계약에서 확정한 뒤 여기에 적는다. 다른 모듈은 **공개 함수만** 호출한다.

## 상태

**아직 코드가 없다.** 데이터 계약(`docs/architecture/contracts/`)이 확정된 뒤 Owner가 채운다. 이 README는 자리를 잡아두기 위한 것이며, 폴더의 범위는 위 문서가 정한다 — 여기에 규칙을 복제하지 않는다.
