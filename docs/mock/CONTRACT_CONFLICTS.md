# CONTRACT_CONFLICTS.md

이 파일은 Mock Pack 생성 지침이 요구하는 "Contract 충돌 기록 파일(CONTRACT_CONFLICTS.md 또는 동급)"이다. 전체 상세 내용과 근거는 `04_mock_validation_report.md` §3에 있고, 여기서는 그 절의 항목만 인덱스로 모았다 — 이 작업 중 발견한 어떤 설계 문제도 임의로 고치지 않았고, 전부 아래 목록 + `04_mock_validation_report.md`에만 기록했다.

## Contract 충돌

없음. (`04_mock_validation_report.md` §3.1)

## 불명확한 Contract (4건)

1. `TimeResolution.resolved.verification`과 `computation.mode=USER_OVERRIDE`의 대응 관계 미명시
2. 순수 사용자 입력 값의 `EvidenceValue.source.observability`/`user_corrected` 판정 기준 미명시
3. `CaseView.evidence.review_needed`의 파생 규칙 미명시
4. `EvidenceRecord.event.safety_report_type`의 실제 값 공간(등록된 enum) 부재

→ 상세: `04_mock_validation_report.md` §3.2

## Architecture 확인 필요 (2건)

1. `JobRecord.kind`에 Report Video export / `purge_case()` 발주용 값 미등재
2. `contract-visual-evidence.md` 예시의 stale non-opaque frame ref 형식

→ 상세: `04_mock_validation_report.md` §3.3

## Fixture 생성 불가 (1건)

1. `contract-correction-record.md`가 아직 Draft라서 `CorrectionRecord` 자체 필드 fixture를 생성하지 않음(opaque ref만 사용)

→ 상세: `04_mock_validation_report.md` §3.4
