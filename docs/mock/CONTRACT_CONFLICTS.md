# CONTRACT_CONFLICTS.md

이 파일은 Mock Pack 생성 지침이 요구하는 "Contract 충돌 기록 파일(CONTRACT_CONFLICTS.md 또는 동급)"이다. 전체 상세 내용과 근거는 `04_mock_validation_report.md` §3에 있고, 여기서는 그 절의 항목만 인덱스로 모았다 — 이 작업 중 발견한 어떤 설계 문제도 임의로 고치지 않았고, 전부 아래 목록 + `04_mock_validation_report.md`에만 기록했다.

## Contract 충돌 (1건, 표현력 gap — 서로 부정하는 충돌은 없음)

4. `EvidenceNeeds`(v1)가 "AI가 사건 유형 자체를 확정하지 못했다"는 상황을 표현하지 못함 — 신규(2026-09-09, 유소연). `EvidenceRecord.event`는 필수라 `verification=UNCERTAIN`이면 레코드 자체를 못 만들고, `EvidenceNeeds`/`RequirementReport`는 둘 다 그 레코드를 전제로 요구해 발행 통로가 없음. `scenario_unknown_abstain_partial_001`(2026-09-09 재설계)이 이 gap을 그대로 fixture화(`evidence_records=[]` 등). case Owner 단독 해소 범위 밖 — `evidence`/PM 확인 필요.

→ 상세: `04_mock_validation_report.md` §3.1

## 불명확한 Contract (2건 잔여 · 2건 종결)

1. `TimeResolution.resolved.verification`과 `computation.mode=USER_OVERRIDE`의 대응 관계 미명시
2. 순수 사용자 입력 값의 `EvidenceValue.source.observability`/`user_corrected` 판정 기준 미명시
3. ~~`CaseView.evidence.review_needed`의 파생 규칙 미명시~~ → **종결(2026-09-09, 유소연)**: 여섯 `*_display.needs_review`의 OR 집계로 확정, `contract-job-record-case-view.md` B절 §6·§7 등재
4. `EvidenceRecord.event.safety_report_type`의 실제 값 공간(등록된 enum) 부재 — 김준영이 이슈 #19에서 **명시적으로 반려**(placeholder일 뿐 canonical enum 아님). evidence 소유 versioned artifact 필요, mock이 임의로 채울 수 없음

→ 상세: `04_mock_validation_report.md` §3.2

## Architecture 확인 필요 (1건 잔여 · 1건 종결)

1. ~~`JobRecord.kind`에 Report Video export / `purge_case()` 발주용 값 미등재~~ → **종결(2026-09-09, 유소연)**: `FINE_VERIFY`·`REPORT_VIDEO_EXPORT` 등재, `purge_case()`는 Job 밖 관리 동작으로 확정. `contract-job-record-case-view.md` A절 §7·§12·§13
2. `contract-visual-evidence.md` 예시의 stale non-opaque frame ref 형식

→ 상세: `04_mock_validation_report.md` §3.3

## Fixture 생성 불가 (1건)

1. `contract-correction-record.md`가 아직 Draft라서 `CorrectionRecord` 자체 필드 fixture를 생성하지 않음(opaque ref만 사용)

→ 상세: `04_mock_validation_report.md` §3.4
