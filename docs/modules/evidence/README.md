# Evidence

**Owner** 김준영

Evidence는 선택된 사건의 관찰값과 사용자 정정을 조립해 신고에 쓸 증거를 확정한다. Case에서 사건 후보, 영상 관찰, 번호판·시각 판독, 원본 시각 후보·GPS, 정정 기록을 받아 `TimeResolution`과 `EvidenceRecord`를 만든다. 필요하면 추가 판독 요청(`EvidenceNeeds`)을 반환한다.

조립된 기록으로 신고문 초안을 만들 수 있다. 최종 요건 평가(`RequirementReport`)와 신고 묶음(`ReportPackage`) 발행에는 자산과 정책 조건이 별도로 적용된다.

Search는 사건 관찰, Readout은 번호판·시각 판독, Recording은 원본·시간축·신고용 자산 생성을 맡는다. Case는 정정 기록과 사용자 진행 상태를 관리하고 작업을 발주한다. Worker는 발주된 작업을 실행한다. [모듈 아키텍처](../../architecture/module-architecture.md) · [소유권](../../management/ownership.md)

## 읽는 순서

- [소스 README](../../../src/daesingo/evidence/README.md)에서 처리 조건, 공개 함수, 활성 정책, 테스트 실행 방법을 확인한다. 테스트는 [`tests/evidence/`](../../../tests/evidence/)에 있다.
- 확정 필드와 발행 조건은 [TimeResolution](../../architecture/contracts/contract-time-resolution.md), [EvidenceRecord·EvidenceNeeds](../../architecture/contracts/contract-evidence-record-needs.md), [RequirementReport·ReportPackage](../../architecture/contracts/contract-requirement-report-package.md) 계약을 따른다. [계약 검토 기록](contracts/README.md)은 초안과 검토 이력을 보존한다.
- 정책의 결정과 근거는 [결정 목록](decisions/README.md), [ADR](adr/README.md), [조사](research/README.md), [실험](experiments/README.md)에서 확인한다.
- [1차 Mock 통합 결과](first-completion-result.md), [체크리스트](first-completion-checklist.md), [실행 산출물](artifacts/first-completion/)은 당시의 검증 기록이다. [검수 보고서](reviews/README.md)와 [작업 지시문](prompts/README.md)도 이력을 보존한다.
