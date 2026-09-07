# cross-module contracts

여러 모듈이 함께 합의해야 하는 **canonical 데이터 계약**을 둔다.

- 팀 합의 전 초안은 각 module의 `contracts/`에서 작업할 수 있다.
- 합의된 계약은 이 폴더로 이동하고, 원래 module 폴더에 중복 사본을 남기지 않는다.
- 계약의 의미와 경계는 `architecture/module-architecture.md`를 따른다.
- 아직 합의되지 않은 필드를 빈칸 채우기 식으로 확정하지 않는다.
- 계약 1건은 `contract-<slug>.md`(현재 규칙)와 `adr/adr-<slug>.md`(확정 근거) 한 짝으로 둔다.

## 감사 후속 상태 (2026-09-08)

현재 종결·Pending 구분은 **[접합부 종결 후속 ADR (2026-09-08)](adr/adr-data-contract-call-closure-2026-09-08.md)** §9 폐쇄 매트릭스를 먼저 확인한다. 그 이전 회차는 [접합부 종결 ADR (2026-09-07)](adr/adr-data-contract-call-closure-2026-09-07.md), 보정·철회 기록은 [후속 보정 ADR (2026-09-06)](adr/adr-consistency-followup-2026-09-06.md), 원래 지적은 [계약 정합성 외부 감사](../../management/contract-consistency-audit-2026-09-06.md)에 있다.

- Owner 결정으로 종결·검증된 접합: B01·B02(CaseView 값 상태·요건) · B03·B05(판독 결과↔ReadoutRun↔UsageRecord, 재판독 발주·`usage_refs` 지위 포함) · B06(`SpanResolution` `failure`·`OUT_OF_TIMELINE_RANGE`, `span-resolution/v1.1`) · B08(`AnalysisScope` relative range, `analysis-scope/1.1.0`) · B09(사용 timeline revision).
- **Draft — Consumer Review 대기(수락 아님):** recording 자산 계약 2건 `contract-source-asset-media-stream.md` · `contract-analysis-source-derived.md`(B07의 필드 정의처). 짝 ADR은 `Proposed`. Review 전에는 Accepted로 읽지 않는다.
- 새 결정 회차 대기(`CALL_REQUIRED`): `MissingRange.source_ref` 규칙 · 자산 ref `kind` 표기 · `AssetSpan` identity↔readout `span_ref`. 주제·Owner는 후속 ADR §4.6.
- 기존 Final 헤더는 문서의 수락 기록이며 모든 접합의 완료를 뜻하지 않는다. `CorrectionRecord`는 Draft다. **데이터 계약 감사는 `CONTRACT_AUDIT_PARTIAL`이며 아직 종결 선언 전이다.**

계약 예시의 의미 검증은 `../../../scripts/check_contract_fixtures.py`(fixture: `fixtures/call-closure-2026-09-07/` · `fixtures/call-closure-2026-09-08/`)가 한다. 경계·헤더 검사는 `check_boundaries.py`와 별개다.
