# cross-module contracts

여러 모듈이 함께 합의해야 하는 **canonical 데이터 계약**을 둔다.

- 팀 합의 전 초안은 각 module의 `contracts/`에서 작업할 수 있다.
- 합의된 계약은 이 폴더로 이동하고, 원래 module 폴더에 중복 사본을 남기지 않는다.
- 계약의 의미와 경계는 `architecture/module-architecture.md`를 따른다.
- 아직 합의되지 않은 필드를 빈칸 채우기 식으로 확정하지 않는다.
- 계약 1건은 `contract-<slug>.md`(현재 규칙)와 `adr/adr-<slug>.md`(확정 근거) 한 짝으로 둔다.

## 감사 후속 상태 (2026-09-07)

현재 종결·Pending 구분은 **[접합부 종결 ADR (2026-09-07)](adr/adr-data-contract-call-closure-2026-09-07.md)** §9 폐쇄 매트릭스를 먼저 확인한다. 그 이전 단계의 보정·철회 기록은 [후속 보정 ADR (2026-09-06)](adr/adr-consistency-followup-2026-09-06.md), 원래 지적은 [계약 정합성 외부 감사](../../management/contract-consistency-audit-2026-09-06.md)에 있다.

- Owner 결정으로 종결·검증된 접합: B01·B02(CaseView 값 상태·요건) · B03·B05(판독 결과↔ReadoutRun↔UsageRecord) · B09(사용 timeline revision).
- 결정은 있으나 직렬화·필드 계약이 남은 것: B06(`SpanResolution` failure reason) · B07(Asset Facts — recording 자산 계약 2건 대기) · B08(`AnalysisScope` relative range). 남은 결정 회차는 종결 ADR §8.1.
- 기존 Final 헤더는 문서의 수락 기록이며 모든 접합의 완료를 뜻하지 않는다. `CorrectionRecord`는 Draft다. **데이터 계약 감사는 `CONTRACT_AUDIT_PARTIAL`이며 아직 종결 선언 전이다.**

계약 예시의 의미 검증은 `../../../scripts/check_contract_fixtures.py`(fixture: `fixtures/call-closure-2026-09-07/`)가 한다. 경계·헤더 검사는 `check_boundaries.py`와 별개다.
