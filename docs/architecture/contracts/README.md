# cross-module contracts

여러 모듈이 함께 합의해야 하는 **canonical 데이터 계약**을 둔다.

- 팀 합의 전 초안은 각 module의 `contracts/`에서 작업할 수 있다.
- 합의된 계약은 이 폴더로 이동하고, 원래 module 폴더에 중복 사본을 남기지 않는다.
- 계약의 의미와 경계는 `architecture/module-architecture.md`를 따른다.
- 아직 합의되지 않은 필드를 빈칸 채우기 식으로 확정하지 않는다.
- 계약 1건은 `contract-<slug>.md`(현재 규칙)와 `adr/adr-<slug>.md`(확정 근거) 한 짝으로 둔다.

## 감사 후속 상태 (2026-09-06)

현재 종결·Pending 구분은 [후속 보정 ADR](adr/adr-consistency-followup-2026-09-06.md)을 먼저 확인한다. 그 판단의 근거가 된 외부 감사 결과는 [계약 정합성 외부 감사](../../management/contract-consistency-audit-2026-09-06.md)에 있다. 기존 Final 헤더는 문서의 수락 기록이며 개별 접합 Pending까지 완료됐다는 뜻이 아니다. 계약 14개 중 CorrectionRecord는 Draft이고, B01/B02·B03/B05·B06~B09는 Owner 합의 대기다.
