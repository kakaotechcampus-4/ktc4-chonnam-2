# evidence/reviews

evidence/common-runtime Owner 관점에서 수행한 Mock fixture와 모듈 접합부 검수 보고서를 둔다.

- `06_kim-junyoung_mock_contract_review_2026-09-09.md` — Mock Pack 1차 계약 검수
- `07_kim-junyoung_mock_round2_review_2026-09-09.md` — Mock Pack 2차 검수
- `08_kim-junyoung_mock_round3_review_2026-09-10.md` — Mock Pack 3차 검수와 이슈 #30 B-1 추가 검토
- `09_kim-junyoung_mock_round4_review_2026-09-11.md` — Mock Pack v4 4차 검수와 공지의 PR #27·#28 확인 요청 답변
- `10_first-completion_decisions_and_integration_2026-09-13.md` — evidence 1차 Mock 통합 이후의 Owner 논의, 김준영 즉시 결정, 실제 통합 단계 작업 분류
- `11_plate-image-generation-and-size-handoff_issue-draft_2026-09-13.md` — `PLATE_IMAGE` 생성 입력과 `AssetFacts.byte_size` 전달이 기존 Contract로 충분한지 묻는 이슈의 원본 초안과 재검토 기록(게시 완료 — 이슈 #47)
- `12_u-package-location-nullability_issue-draft_2026-09-13.md` — 위치를 확보하지 못한 사건에서 `ReportPackage`를 발행할 것인지 묻는 이슈의 원본 초안과 재검토 기록(`10_...` D1(Q1) 후속, 게시 완료 — 이슈 #48)
- `13_adr-002-003-implementation_2026-09-14.md` — K1~K4·D1 코드/정책/계약/Artifact 구현과 검수, 공용 관찰 fact 부재에 따른 지시 간 불일치 기록
- `14_instruction-conflict-analysis-and-doc-fixes_2026-09-14.md` — `13_...`의 불일치 두 건에 대한 원인 분석, 구현 판단 평가, Owner 결정 대기 항목과 추천값, ADR 문서 정정안. **처리 완료** — ②③④ 채택, ①(I4 범위 확장)은 기각되고 `ADR-EVIDENCE-005`(세 rule 제거)로 대체됐다
- `15_adr-005-implementation_2026-09-14.md` — ADR-EVIDENCE-005 D2의 v4 catalog·코드·테스트·Artifact 반영, H/U Package 복구 증빙, I2·I4·recording 미결 경계 검수

공용 Mock의 canonical 설명과 fixture 규칙은 `../../../mock/`이 소유한다. 이 폴더의 보고서는 evidence/common-runtime 담당자의 검수 기록이며 공용 Mock 계약을 대신하지 않는다.
