# ADR — 데이터 계약 감사 후속 보정 (2026-09-06)

**Status:** Accepted — PM 권한의 복원·종결 철회·기록 정정에 한정
**Decider:** 김준영 (PM / evidence / common/runtime)
**Date:** 2026-09-06
**Supersedes in part:** `adr-consistency-2026-09.md` C1-6·C1-13·R-6·R-7 및 미해결 0건/통합 가능 결론; `adr-job-execution.md`·`adr-usage-record.md`의 신규 결정 범위·소비자 확인 단정

**감사 보고:** `../../../management/contract-consistency-audit-2026-09-06.md` — 이 ADR이 처리하는 지적의 원문

> **현재 결정 원장은 이 문서가 아니다 (2026-09-07 이후).** §3의 BLOCK/Pending 8건은 CALL-8~CALL-11 회차에서 Owner 결정을 받았고, 그 결정·계약 반영·검증 상태·남은 Pending은 **`adr-data-contract-call-closure-2026-09-07.md`**가 갖는다(§9 폐쇄 매트릭스). 이 문서 본문은 2026-09-06 시점의 보정·철회 기록으로 보존하며 고치지 않는다. 아래 §3·§5의 「Pending」·「불가」는 당시 상태다.

## 1. 범위와 적용

추가 CALL 없이 기존 canonical 근거로 유일하게 정해지는 보정과 PM의 임의 확정 철회만 수행한다. **이 ADR의 Accepted는 §3 Pending 접합부의 수락을 뜻하지 않는다.** 계약의 현재 필드·규칙은 각 계약이 소유하고 이 문서는 근거와 처리 상태만 기록한다.

수락된 과거 ADR의 결정 본문은 보존하고 머리말에 후속 정정 포인터를 붙인다. 미확인 회신 의도·통보·날짜를 새 사실로 만들지 않는다. 기존 2026-09-06 회신의 실제 답변 범위는 유지한다. 이번 보정은 기존 규칙 복원·예시/기록 수정이므로 계약 버전 문자열을 올려 새 설계가 수락된 것처럼 표현하지 않는다.

## 2. 직접 보정한 항목

| 감사 ID | 처리 | 유일한 근거와 한계 |
|---|---|---|
| B04 | JobExecution 정상 produced 예시를 공통 ContractRef 객체 배열로 복원 | 해당 계약 §4·§5의 선언 + `contract-observation.md` §3 및 §12의 analysis_run ref 예시. 새 ref 종류를 만들지 않음 |
| B10 | JobRecord A§7의 case_id·kind·input_fingerprint 재사용 범위를 복원하고 다른 현재 문장은 이를 참조 | `adr-job-record-case-view.md` A§7의 기존 tuple. fingerprint 알고리즘·scope 정규화는 새로 정하지 않음 |
| B11 | PM 추가 작업 순서의 확정 상태 철회 | C1-6이 스스로 회의 결정이 아니라 PM 판단이라고 기록. ownership의 두 문장을 제안/정철원 확인 대기로 변경. 기존 구현 담당 배정은 유지 |
| B12 | 같은 회차라는 이유로 채운 날짜 추정 제거 | AnalysisScope·JobRecord/CaseView 최초 Accepted 날짜는 확인 대기. Status는 본문 종결 근거를 유지. recording 날짜는 짝 ADR의 9/4와 09-06 재확인 근거를 명시 |
| W01 | 헤더·현재 계약 포인터·Draft 제목·Consumer 표기 정리 | AnalysisRun/VisualEvidence의 Related ADR와 짝 ADR의 9/4 수락일, AnalysisScope fixture Producer, plate의 현재 경유 경로, CorrectionRecord의 Draft. 역사 ADR 식별자는 재번호하지 않음 |
| W02 | 베이스·회신 의도·회귀 등급 관련 사실 단정 철회 | 아래 §4 참조. 기존 계약을 유지하는 것과 Owner의 삭제 의도를 판정하는 것은 별개 |
| W03 | 미해결 0건·5NOTE뿐·모든 카드 회신 완료를 최종 상태에서 철회 | §3이 현재 Pending 원장. 과거 계획·카드·공지는 당시 기록/미발송 초안으로 구분하며 실제 발송 증거로 쓰지 않음 |
| W04 | PM 신규 결정/소비자 리뷰 범위의 축소 서술 정정 | JobExecution §10 및 UsageRecord §9. 기존 PM 소유 규칙은 보존하되 소비자 확인·접합 완료를 주장하지 않음 |
| W05 | 현행 규칙 중복을 포인터로 정리 | 캐시·runtime→CaseView 매핑은 CaseView 계약, ref 작업 규약은 v4 §5-3, taxonomy는 readout 소유 문서. report 선택은 RequirementReport §5.2-1의 **검토 제안**으로만 보존 |
| W06 | v4 개정 이력과 실제 수정 절을 맞춤 | 09-06 USER_REVIEWED 체크의 원래 수정도 이력에 포함. 이후 통합 완료 선언은 철회 |
| W07 | 자산 종류가 명확한 ref 예시의 접두어·role 인코딩 정리 | 기존 v4 §5-3의 작업 규약만 적용. thumb_ref의 자산 종류와 FrameRef 필드 계약은 Pending으로 유지 |

B11/B12의 '보정 완료'는 **무근거 확정의 제거 완료**다. 정철원이 새 순서를 수락했거나 최초 수락일을 확인했다는 의미가 아니다. W02/W04/W07도 기록·표기 정리는 완료하되 관련 Owner의 의도·소비자 확인·자산 종류 결정은 아래에 남긴다.

## 3. BLOCK / Pending — 이번에 닫지 않은 것

| ID | 현재 상태·필요한 결정 | 담당 경계 |
|---|---|---|
| B01 | BLOCK/Pending. needs_review 원천, occurred_at 입력 변환, 위치 대표값, info_state/source label 전달과 검토 boolean 관계 | case(유소연) ↔ evidence(PM) ↔ web(신유민) |
| B02 | BLOCK/Pending. PM scope 확정 철회. report current basis·동일 scope 이력·세 gate 표시·nullable 및 실제 스키마 선택 | case ↔ evidence ↔ web |
| B03 | BLOCK/Pending. 판독 결과→ReadoutRun 연결 위치·공통 Observation.run_ref 표현 | readout(신유민) ↔ case ↔ eval(김대원) |
| B05 | BLOCK/Pending. UsageRecord가 ReadoutRun을 참조하는 방식·원장 역추적 | common/runtime(PM) ↔ readout ↔ eval |
| B06 | BLOCK/Pending. SpanResolution 요청 범위의 완전성·FAILED 원인 표면. 예시의 미설명 10초를 임의 보정하지 않음 | recording(정철원) ↔ search(서어진) ↔ evidence |
| B07 | BLOCK/Pending. 실제 evidence 함수에 필요한 자산 사실·lookup/주입 표면, FrameRef/Fine input/selector 계약 | recording ↔ search/readout ↔ evidence/case |
| B08 | BLOCK/Pending. 상대 전용 timeline과 ISO8601 AnalysisScope의 접합 | recording ↔ case ↔ search |
| B09 | BLOCK/Pending. 기존 Candidate/Run에서 사용 timeline revision 추적 | recording ↔ search ↔ case/evidence |
| B11 잔여 | 제안/확인 대기. resolve_span 뒤 JobExecution 구현이라는 순서 | PM ↔ 정철원 |
| B12 잔여 | 최초 수락일·closure 판본 관계 확인 대기. 추정 날짜를 다시 넣지 않음 | PM ↔ 유소연 |
| W02 잔여 | v1.1의 네 evidence 필드 삭제 의도·필드 수준 승인 범위 | case ↔ evidence/web |
| W04 잔여 | PM 추가 규칙의 실제 소비자 확인, domain PARTIAL과 runtime status 접합 | common/runtime ↔ case/search/eval |
| W07 잔여 | thumb_ref의 자산 종류, recording 자산 계약 두 건 | recording ↔ case/web |
| N02 | CorrectionRecord Draft 리뷰·target_field/전후 값·현재값 선택, taxonomy Owner 확정 및 eval 지표 정의 | case ↔ evidence; readout ↔ eval |

**BLOCK 8건은 아래 4묶음으로 확인한다 (2026-09-06 카드 작성 완료 · 발송 전).**

| 카드 | 대상 | 결정해 줄 사람 | 같이 볼 사람 |
| --- | --- | --- | --- |
| `CALL-8` | B01 · B02 | 유소연 (`case`) | 김준영 (`evidence`) · 신유민 (`web`) |
| `CALL-9` | B03 | 신유민 (`readout`) | 유소연 (`case`) · 김대원 (`eval`) |
| `CALL-10` | B05 | 김준영 (`common/runtime`) · 신유민 (`readout`) | 김대원 (`eval`) |
| `CALL-11` | B06 · B07 · B08 · B09 | 정철원 (`recording`) | 서어진 (`search`) · 유소연 (`case`) · 김준영 (`evidence`) · 신유민 (`readout`, B07) |

카드 원문은 `management/secret/calls/`에 있고 노션으로 올린다. **카드는 결정만 받는다 — 레포 파일 수정은 PM이 한다**(§7 규칙 1). 확인 대기 중 담당자가 겹치는 B12 잔여·W02 잔여는 `CALL-8` 부록에, W07 잔여는 `CALL-11` 부록에 한 줄씩 실었다. W04 잔여와 N02는 카드에 싣지 않았다.

**이번 작업에서 카드 발송·추가 회신·Owner 수락을 만들지 않았다.** 원천 결정 문서가 이미 있으면 새 CALL 대신 그 원문 확인으로 닫을 수 있지만 현재는 Pending이다.

**Canonical Contract v1의 최종 Freeze는 위 4건이 반영된 뒤로 둔다.** 계약 14건은 그때까지 현행대로 사용하며, 접합부만 확정 전이다.

## 4. 이전 보고·원인 진단의 정정

이 절이 이전 ADR §6 R-6·§7의 단정보다 우선한다.

- 회신 v1.1 머리말에는 **v1: 2026-09-04 Accepted 기준**이 적혀 있다. '베이스 판본을 적지 않았다'가 아니라 **정확한 closure snapshot을 식별할 수 없다**가 확인 가능한 사실이다.
- 개인 사본 사용·비의도적 삭제·베이스 착오는 작성자 확인 전 추측이다. 문서에서 차이를 찾았다는 것만으로 삭제 의도를 확정하지 않는다.
- 12건을 모두 BLOCK 4/WARN 8로 고정하지 않는다. runtime Consumer 헤더 누락은 경로 변경 증거가 없으면 표기 문제다. progress/severity/package 타입/range nullable 후퇴는 실제 소비 형태에 영향을 주므로 단순 WARN이라고 할 수 없다.
- Product Spec §7은 사용자에게 유형·근거를 확인/수정 가능하게 하는 약속이다. case_type_display/report_type_display/violation_display/preview_ref라는 네 필드가 유일한 구현이라고 고정한 조항이 아니다. 기존 표현은 비교 기준으로 보존하되 유지·삭제의 최종 합의는 Pending이다.
- 이전 '공지가 나갔다/이견 없음/소비자 확인'은 로컬 공지 초안만으로 독립 확인되지 않는다. 실제 발송·수신·수락은 확인 대기다.
- 회신으로 파일 작성 주체가 정해졌다는 것과 그 파일이 완성됐다는 것은 다르다. recording 두 계약의 부재와 CorrectionRecord의 Draft를 완료로 세지 않는다.

## 5. 현재 진행 범위와 검사 결과의 의미

확정된 값 공간·참조 모양을 사용하는 **개별 Mock fixture 생성은 가능**하다. Pending 입력을 요구하지 않는 고정 scenario의 제한적 연결 확인도 가능하다. B01/B02나 recording 자산 사실을 임의 하드코딩한 경로는 해당 계약 검증의 PASS로 세지 않는다.

`ownership.md` §7-④의 전체 E2E 6기준 통과는 아직 불가하다. 특히 실제 evidence의 final package 판정·세 gate 표시·revision/상대 입력 경로와 Tool Trajectory Review 실행 증거가 남는다. 단일 mock 화면 렌더와 실제 evidence를 사용하는 통합을 구분한다.

경계 스크립트의 PASS는 구현된 문자열·헤더 검사 결과다. 코드 없는 boundary 7경로와 schema 부재 coverage 5타입의 NOTE를 지우지 않는다. 이 스크립트는 계약 의미·예시 직렬화 전체·Owner 수락을 검증하지 않는다. 상세 지원 범위는 `../../../../scripts/README.md`를 따른다.

## 6. 후속 변경 규칙

§3 항목은 해당 Owner 결정과 필요한 fixture 검증 후 변경 ADR로 닫는다. 본문의 Accepted나 계약의 기존 Final 헤더를 Pending을 우회하는 근거로 쓰지 않는다. 과거 감사 보고와 회신 원본은 수정하지 않는다.

## 7. 2026-09-07 — 변경 ADR 포인터

§6의 「변경 ADR」이 `adr-data-contract-call-closure-2026-09-07.md`다. 그 문서가 §3의 각 행을 어떻게 닫았는지(또는 왜 아직 열려 있는지)를 §9 표 한 곳에 적는다. 요약만 적으면 — B01·B02·B03·B05·B09는 결정·반영·fixture 검증 완료, B06·B08은 직렬화 결정 회차(CALL-14·15) 대기, B07은 recording 자산 계약 대기, B11·B12 잔여는 무근거 확정 제거 상태 유지(수락일은 확인 불가), W02·W07 잔여 종결, W04 잔여는 `UsageRecord` 부분만 종결. 이 절은 포인터이며 상태의 원본은 그 문서다.
