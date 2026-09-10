# 02. Mock Scenario Catalog

> **2026-09-09 갱신 (Decider 유소연 · 팀 리뷰 이슈 #19 김준영 제안)** — 기존 `scenario_unknown_abstain_partial_001`이 C·D·E·G·H·I 6개 유형을 한 시나리오에 몰아넣으면서, `EvidenceRecord.event`가 계약상 필수 필드라 "사건 유형 자체가 불확실(verification=UNCERTAIN)"한 경우와 "사건 유형은 확정됐지만 번호판만 abstain"인 경우가 하나의 fixture 안에서 논리적으로 충돌했다(전자는 EvidenceRecord를 만들 수 없고, 후자는 만들 수 있어야 한다). 이를 `scenario_unknown_abstain_partial_001`(E·H)과 신규 `scenario_plate_reread_001`(C·D·G·I)로 분리했다. 시나리오 수는 4개→5개.

> **2026-09-09 3라운드 갱신 (Decider 유소연 · 이슈 #16 신유민 답변, P1-12).** 원래 A~I 9개 유형은 evidence 콘텐츠 상태(정상/불확실/abstain/정정 등)를 분류한 것이라 "readout 실행 자체가 인프라 단계에서 실패"하는 경로가 들어갈 자리가 없었다. 이를 **신규 유형 J**로 추가하고 `scenario_infra_failure_001`을 만들었다. 시나리오 수는 5개→6개.

> **2026-09-09 4차 라운드 갱신 (Decider 유소연 · 이슈 #18 정철원 답변, P1-10).** A~J는 모두 evidence 콘텐츠 상태·readout 실행 결과 축이라 "recording timeline 자체의 구성 방식"(절대시각 부재·rebase·구간 일부 해석 불가)이 들어갈 자리가 없었다. 이는 evidence 콘텐츠 상태와 독립적인 축이라 **신규 유형 K**로 추가하고 `scenario_relative_rebase_001`을 만들었다. 시나리오 수는 6개→7개.

시나리오는 7개다(「시나리오를 너무 많이 만들지 않고 시나리오당 Contract coverage를 최대화한다」는 지침에 따르되, 계약상 양립 불가능한 조합은 분리한다). A~I(evidence 콘텐츠 상태) + J(readout 인프라 실행 실패) + K(recording timeline 상대전용/rebase/구간 부분 해석) 11개 유형을 아래 7개 시나리오가 나눠 커버한다.

## 시나리오 목록

| Scenario ID | 커버 타입 | 관련 모듈 fixture | Case ID |
| --- | --- | --- | --- |
| `scenario_happy_001` | A (Happy Path) | recording·search·readout·evidence·case·common | `case_h001` |
| `scenario_empty_001` | B (결과 없음) | search·case·common | `case_e001` |
| `scenario_unknown_abstain_partial_001` | E·H | recording·search·readout·evidence·case·common | `case_u001` |
| `scenario_plate_reread_001` | C·D·G·I | recording·search·readout·evidence·case·common | `case_p001` |
| `scenario_correction_rerun_001` | F·I | recording·search·readout·evidence·case·common | `case_r001` |
| `scenario_infra_failure_001` | J (readout 인프라 실행 실패) | recording·readout·case·common | `case_x001` |
| `scenario_relative_rebase_001` | K (timeline 상대전용·rebase·SpanResolution PARTIAL) | recording·search·case·common | `case_rb001` |

---

## `scenario_happy_001` — Happy Path

**목적**: 등록 → COARSE_SEARCH → 후보 선택 → PLATE_READ/OVERLAY_TIME_READ → Evidence 확정 → RequirementReport(EVIDENCE, FINAL_PACKAGE) → ReportPackage까지 전체 파이프라인을 한 번 완주하는 대표 정상 경로를 제공한다. 다른 모든 것이 깨져도 이 시나리오 하나는 각 모듈이 개발 초기에 "정상일 때 내 입력이 이런 모양이구나"를 확인하는 기준이 된다.

**시작 조건**: 전방/후방 2개 영상 파일이 정상 업로드되고(`AVAILABLE`), filename에서 시각을 파싱할 수 있다.

**예상 흐름**: `COARSE_SEARCH` → 후보 1건(`candidate_h001`, ranking_score 0.86) → 사용자가 그 후보 선택 → `PLATE_READ`/`OVERLAY_TIME_READ` 동시 발주 → 둘 다 `SUCCEEDED`, abstain 없음 → `TimeResolution.status=OK`(검증된 Overlay) → `EvidenceRecord`의 모든 필드 confirmed, `needs_review` 전부 false → `RequirementReport` 둘 다 `PASS` → `ReportPackage` 생성 → `CaseView.stage=READY`.

**기대 결과**: 모든 모듈의 fixture가 존재하고, `ReportPackage`가 실제로 생성되며, `CaseView.stage=READY`.

**검증 Contract**: 전체 14개 Final Contract 중 12개(제외: 이 시나리오는 abstain/충돌이 없어 `EvidenceNeeds.items`가 빈 배열, `RequirementReport`의 BLOCK/UNKNOWN outcome은 다른 시나리오가 담당).

> **2026-09-10 v3 추가 (이슈 #26 B-web-5·5, 신유민 답변).** `stage=READY` 이후 `case_rev:4`에서 신고자료용 `REPORT_VIDEO_EXPORT` `JobRecord`/`JobExecution`(`DerivedAsset` 생성)을 추가했다. 이 rev에서 `location_display`의 대표값이 `user_hint`라 `info_state=INFO_NEEDS_REVIEW`인데, 이전에는 `package.report_fields.location`에 같은 미확정 문장이 그대로 실리면서도 `package.warnings=[]`·`CaseView.evidence.review_needed=false`로 "전부 초록"인 사각지대가 있었다 — `package.unconfirmed_fields=["location"]`을 추가하고 `review_needed`/`reason_code`를 정정해 닫았다. 근거는 `contract-job-record-case-view.md` B절 §7의 `review_needed` 파생 규칙 갱신 참고.

---

## `scenario_empty_001` — 결과 없음

**목적**: `AnalysisRun.outcome=SUCCEEDED`이면서 `candidates=[]`인 경우가 실패가 아님을 보여준다. `search`·`case` 양쪽 모두 "빈 배열"과 "에러"를 구분해서 처리해야 함을 데이터로 증명한다.

**시작 조건**: 영상은 정상 업로드됐지만, 사용자가 지목한 시간대에 해당 사건 유형(`CENTER_LINE_CROSSING`)의 후보가 실제로 없다.

**예상 흐름**: `COARSE_SEARCH` 실행이 정상 종료(`outcome=SUCCEEDED`)하지만 `candidates=[]` → `CaseView.stage=CANDIDATE_REVIEW`에 머물고 `candidates=[]` → 비차단(`blocking=false`) INFO notice로 힌트 수정/재검색 유도.

**기대 결과**: `AnalysisRun`이 실패로 기록되지 않는다. `readout`/`evidence`/`ReportPackage`는 아예 생성되지 않는다(대상 후보가 없으므로).

**검증 Contract**: `AnalysisScope`·`AnalysisRun`·`JobRecord`·`JobExecution`·`UsageRecord`·`CaseView`.

---

## `scenario_unknown_abstain_partial_001` — 화면시각 NOT_APPLICABLE + 시각 소스 충돌 + 사건유형 확정 불가 → WARN 경로로 신고까지 진행

> **2026-09-09 재설계 (Decider 유소연)** — 이전 버전은 이 시나리오에 C·D·E·G·H·I 6개 유형을 몰아넣었으나, `VisualEvidence.verification=UNCERTAIN`(사건 유형 자체가 불확실)인 상태에서는 `EvidenceRecord.event`가 계약상 필수 필드라 `EvidenceRecord`를 아예 만들 수 없다(`contract-evidence-record-needs.md` §3 직접 확인). 반면 C·D·G·I(번호판 abstain narrative)는 사건 유형이 confirmed임을 전제로 `EvidenceRecord`가 존재해야 성립한다 — 두 전제가 한 fixture 안에서 양립할 수 없었다. 이 시나리오는 이제 E·H만 전담하고, C·D·G·I는 [`scenario_plate_reread_001`](#scenario_plate_reread_001--번호판-abstain--evidenceneeds-자동-재판독-확정된-사건유형-위에서)로 이동했다.
>
> **2026-09-10 v3 재설계 (Decider 유소연 · 이슈 #25 A절, 김준영 답변) — "Contract Gap"에서 "WARN 경로로 실제 신고까지" 로 뒤집힘.** 위 재설계 직후 발견했던 gap("사건 유형 자체 미확정을 표현할 계약상 메커니즘이 없음", 아래 문단은 그 **이전 설계를 서술한 것으로 지금은 사실이 아니다**)을 김준영이 `event.visual_event_type.value=null`을 제한적으로 허용하는 것으로 해소했다. `EvidenceRecord`가 **생성되고**(빈 배열이 아님), `RequirementReport`(EVIDENCE·FINAL_PACKAGE 둘 다 WARN)·`ReportPackage`까지 생성돼 `CaseView.stage`가 `EVIDENCE_REVIEW`(rev3, WARN)→`READY`(rev4, WARN)로 진행한다. `CaseView.evidence=null`이 아니라 `case_type_display.info_state=INFO_UNKNOWN`으로 "AI가 확정 못 함"을 표현하고, 신규 `situation_confirmation="UNKNOWN"`(사용자도 "잘 모르겠어요")·`package.unconfirmed_fields=["report_type"]` 등으로 미확정 상태를 구조화해서 내려보낸다. 근거: `docs/modules/case/decisions/generic-warn-package-and-situation-response.md`.

**목적**:
- 화면 시각 판독의 `ReadoutRun`이 `outcome=SUCCEEDED`이면서 화면에 타임스탬프 오버레이 자체가 없어(`NOT_PRESENT`) `OverlayTimeReadout.observation.status=NOT_APPLICABLE`인 결과 객체가 정상적으로 생성되는 규칙을 보여준다(E). **완전 실패(`outcome=FAILED`, 결과 객체 자체가 없음)와 NOT_APPLICABLE(결과는 있으나 관찰 대상이 없다는 정상 관찰)은 다른 개념이다** — 이전 버전은 이를 `outcome=FAILED`로 잘못 모델링했었다(§8.1 P0-4, 신유민 결정으로 정정).
- Filename 시각과 File Metadata 시각이 3분 어긋날 때 `TimeResolution`이 임의로 승자를 정하지 않고 `conflict.exists=true`로 보존하는 것을 보여준다(H). `BASE_PLUS_OFFSET` 상대-절대 시간 계산도 함께 검증한다.
- **(2026-09-10 v3) "AI가 사건 유형 자체를 확정하지 못했다" 상태가 신고 불가가 아니라 WARN + 사용자 확인 요청으로 이어지는 전체 경로의 예시.** `visual_event_type.value=null` → `EvidenceRecord`는 생성되지만 `case_type_display`/`report_type_display`가 `INFO_UNKNOWN`/일반화된 label(`"교통위반(고속도로 포함)"`) → `RequirementReport(EVIDENCE)=WARN` → `package.unconfirmed_fields`에 담아 신고 직전까지 진행 → `CaseView.candidates[].situation_confirmation`으로 "아직 안 물어봄"과 "물어봤는데 모른다고 답함"을 구분한다(현재 스냅샷은 `UNKNOWN`).

**시작 조건**: 영상 1개, filename time과 file metadata time이 서로 다름. 신호 상태가 화면에서 불확실해 사건 유형 자체를 확정할 수 없음.

**예상 흐름**: `COARSE_SEARCH` → 후보 1건(`ranking_score 0.61`, `uncertainties` 포함) → `VisualEvidence.verification=UNCERTAIN`·`visual_event_type=null`(대상 차량은 `MATCHED`이지만 신호 상태 미확정) → `PLATE_READ`는 정상 성공(이 시나리오의 관심사가 아님) → `OVERLAY_TIME_READ`은 `ReadoutRun.outcome=SUCCEEDED` + `OverlayTimeReadout.observation.status=NOT_APPLICABLE` → `evidence.assemble()`이 `event.visual_event_type.value=null`인 채로 `EvidenceRecord`를 생성 → `RequirementReport(EVIDENCE)=WARN`(사건 유형 미확정 WARN 포함 4개 check) → `CaseView rev3`(`stage=EVIDENCE_REVIEW`, `evidence` 채워짐, `situation_confirmation=UNKNOWN`) → `RequirementReport(FINAL_PACKAGE)=WARN`·`ReportPackage` 생성 → `CaseView rev4`(`stage=READY`, `package.unconfirmed_fields`로 미확정 필드 노출).

**기대 결과**: `EvidenceRecord`·`RequirementReport`(EVIDENCE·FINAL_PACKAGE)·`ReportPackage` 전부 생성된다(WARN 등급으로). `CaseView.evidence`는 채워져 있고 `case_type_display.info_state=INFO_UNKNOWN`으로 미확정을 표현하며, `stage=READY`까지 도달한다.

**검증 Contract**: `AnalysisScope`·`AnalysisRun`·`CandidateEvent`·`VisualEvidence`·`ReadoutRun`·`OverlayTimeReadout`(`NOT_APPLICABLE`)·`TimeResolution`·`EvidenceRecord`·`EvidenceNeeds`·`RequirementReport`(EVIDENCE·FINAL_PACKAGE WARN)·`ReportPackage`·`JobRecord`·`JobExecution`·`UsageRecord`·`CaseView`(`situation_confirmation`·`package.unconfirmed_fields`).

---

## `scenario_plate_reread_001` — 번호판 ABSTAIN + EvidenceNeeds 자동 재판독 (확정된 사건유형 위에서)

**신설 (2026-09-09, Decider 유소연 · 팀 리뷰 이슈 #19 김준영 제안)** — `scenario_unknown_abstain_partial_001`에서 C·D·G·I를 분리했다.

**목적**:
- 사건 유형(`SIGNAL`, 적색 신호 위반) 자체는 `VisualEvidence.verification=OBSERVED`로 명확히 관찰되어 `EvidenceRecord.event.*`가 전부 확정됨을 전제로 둔다.
- 번호판 판독이 대상 차량 식별은 확실(`target_association.status=ASSOCIATED`)하지만 프레임 간 OCR 인식이 불일치해 `abstained=true`가 되는 경우, 이것이 Case 전체 실패가 아님을 보여준다(D).
- `vehicle_number`가 `EvidenceRecord`에서 (null이 아니라) **필드 자체 부재**로 표현되고, `RequirementReport(EVIDENCE).overall=UNKNOWN`이 `BLOCK`과 다른 의미(판정 자체가 성립하지 않음)임을 보여준다(C·G).
- `EvidenceNeeds.items`에 `PLATE_REREAD`(`optional=false`)가 담기고, `case`가 이를 받아 새 `JobRecord`(`force_rerun=true`)를 자동 발주하되 이미 확정된 `occurred_at`·`visual_event_type` 값은 리셋하지 않는 것을 보여준다(I) — `occurred_at`은 검증된 Overlay로 이미 `status=OK`다.

**시작 조건**: 영상 1개, 신호 위반 장면은 화면에서 명확히 관찰됨(사건 유형 확정). 번호판만 프레임 간 인식이 갈림.

**예상 흐름**: `COARSE_SEARCH` → 후보 1건(`ranking_score 0.83`, `uncertainties=[]`) → `VisualEvidence.verification=OBSERVED`·`visual_event_type=SIGNAL` → `PLATE_READ` 성공하지만 `target_association=ASSOCIATED`인 채로 `abstained=true`(프레임 간 OCR 불일치) → `OVERLAY_TIME_READ` 정상 성공, `TimeResolution.status=OK` → `evidence.assemble()`이 `EvidenceRecord`에서 `vehicle_number` 필드를 아예 비움, `event`·`occurred_at`은 전부 확정 → `EvidenceNeeds`가 `PLATE_REREAD` 요청 → `case`가 `force_rerun=true`로 새 Job 자동 발주(`QUEUED` 상태로 스냅샷, `occurred_at`·`visual_event_type`은 리셋되지 않음) → `RequirementReport(EVIDENCE).overall=UNKNOWN`(원인은 `vehicle_number` 하나로 명확히 국한).

**기대 결과**: `ReportPackage`가 생성되지 않는다(§8.1 ready-only 규칙). `CaseView.requirements_package=null`. `CaseView.evidence.event_time_display`는 이미 `INFO_SOURCE_VERIFIED`로 확정 표시된다.

**검증 Contract**: `AnalysisScope`·`AnalysisRun`·`CandidateEvent`·`VisualEvidence`·`ReadoutRun`·`PlateReadout`·`OverlayTimeReadout`·`TimeResolution`·`EvidenceRecord`·`EvidenceNeeds`·`RequirementReport`·`JobRecord`·`JobExecution`·`UsageRecord`·`CaseView`.

---

## `scenario_correction_rerun_001` — 사용자 정정 + Supersede 재실행

**목적**:
- 사용자가 사건 발생시각을 명시적으로 정정했을 때 `TimeResolution`이 `USER_OVERRIDE`/`user_corrected=true`로 새 버전을 만들고 `supersedes_ref`로 이전 버전과 연결되는 것을 보여준다(F).
- 이 정정 과정에서 **이미 확정돼 있던 `vehicle_number`는 완전히 동일한 값·provenance로 유지**됨을 보여준다 — 정정이 무관한 값을 리셋하지 않는다는 원칙의 직접적 증거다(I).
- `EvidenceRecord`·`RequirementReport`가 각각 v1→v2로 supersede되는 chain도 함께 보여준다.
- `OverlayTimeReadout`은 실행되지만(`rr_r001_overlay`, `outcome=SUCCEEDED`) 화면에 오버레이 자체가 찍혀 있지 않아 `observation.status=NOT_APPLICABLE`로 관찰된다(`scenario_unknown_abstain_partial_001`과 동일 패턴) — 그 때문에 최초 시각이 filename 기반 추정치(`NEEDS_REVIEW`)로만 남아 사용자 정정이 필요했다는 서사와도 맞아떨어진다.
  - **2026-09-09 2차 재검토 정정**: 이전 버전은 `readout_runs`에 overlay 항목 자체가 없어 "결과 없음(FAILED)"과 다른 NOT_RUN을 배열 부재로 표현하려 했으나, 이는 v1에서 확정된 "오버레이 OCR은 선택된 후보마다 무조건 디스패치된다"는 정책(`contract-plate-overlay-readout.md` §11-4)과 정면으로 모순됨을 정철원(recording Owner, 이슈 #18)의 답변 재확인 과정에서 발견했다. NOT_RUN을 배열 부재로 표현하는 설계 자체를 폐기하고, u001과 동일하게 "실행은 되지만 NOT_APPLICABLE"로 재구성했다.

**시작 조건**: 번호판은 처음부터 명확하게 확정(`OBSERVED`)됐다. 발생시각은 처음엔 Filename+offset 계산값(`NEEDS_REVIEW`)뿐이었다.

**예상 흐름**: `COARSE_SEARCH` → 후보 선택 → `PLATE_READ` 성공(비-abstain) → `OVERLAY_TIME_READ` 실행되나 오버레이 부재로 `NOT_APPLICABLE` → `TimeResolution v1`(`NEEDS_REVIEW`, `BASE_PLUS_OFFSET`) → `EvidenceRecord v1`(`occurred_at.resolution_status=NEEDS_REVIEW`) → 사용자가 정정 제출(`CorrectionRecord`, opaque ref만 사용 — Draft 계약이라 필드 스키마 미생성) → `TimeResolution v2`(`status=OK`, `verification=AGREED`, `user_corrected=true`, `supersedes_ref=v1`) → `EvidenceRecord v2`(`occurred_at`만 갱신, `vehicle_number`는 v1과 완전 동일) → `RequirementReport v1(WARN)`→`v2(PASS)`.

**기대 결과**: `EvidenceRecord v2.vehicle_number`가 `EvidenceRecord v1.vehicle_number`와 값·source·support_refs·needs_review 전부 동일. `CaseView.evidence.user_edited=true`이지만 `plate_display`는 그대로.

**검증 Contract**: `TimeResolution`(supersede)·`EvidenceRecord`(supersede)·`RequirementReport`(supersede)·`ReadoutRun`(overlay NOT_APPLICABLE)·`JobRecord`·`JobExecution`·`UsageRecord`·`CaseView`.

**의도적으로 만들지 않은 것**: `CorrectionRecord`의 실제 필드 fixture. `contract-correction-record.md`가 아직 Draft이기 때문이며, `04_mock_validation_report.md`의 "Fixture 생성 불가"에 기록했다.

---

## `scenario_infra_failure_001` — readout 인프라 실패, STALE 재시도 후 FAILED(신규 유형 J)

**목적**:
- `PLATE_READ` 실행이 워커 레벨 인프라 장애로 실패하는 경로를 표현한다(P1-12, 이슈 #16에서 신유민이 확정한 readout failure taxonomy 중 `INFRA` 종류를 이 pack에서 처음으로 실사용한다).
- `JobExecution`의 STALE 상태(`contract-job-execution.md` §8 — worker가 살아있음을 보고하지 못한 채 사라져 `ended_at=null`, `produced=[]`, `failure_kind=null`로 남는 상태)와, 같은 `job_id`·새 `execution_id`·증가된 `attempt`로 재시도되는 흐름(§9-2)을 처음으로 보여준다.
- 재시도(`attempt 2`)도 다시 실패해 `status=FAILED`, `ReadoutRun.outcome=FAILED`, `failure={kind:INFRA, code:READOUT_PROVIDER_TIMEOUT}`가 되는 것과, "완전 실패 시 결과 객체 자체가 생성되지 않는다"는 규칙에 따라 `plate_readouts=[]`이면서도 `ReadoutRun` 객체 자체(실행이 있었다는 기록)는 남는 것을 보여준다.
- `CaseView`가 진행 중(RUNNING, rev1)과 재시도 소진 후(FAILED, rev2) 두 스냅샷으로 구성되며, rev2에 이 pack 최초로 `severity=ERROR`·`blocking=true`인 notice(`readout.plate_read_failed`, action `RETRY_PLATE_READ`)가 등장한다 — P1-9가 지적했던 "실패/차단 notice 예시 부재" 갭의 일부를 해소한다.

**시작 조건**: candidate 탐색·선정까지는 끝난 상태에서 시작한다(`case_views[].candidates[]`가 CaseView 자체 denormalized 복사본으로 self-contained하며, 그 이전 단계의 `COARSE_SEARCH` `JobRecord`/`AnalysisRun`/`VisualEvidence`는 이 시나리오의 검증 범위가 아니라 의도적으로 만들지 않았다).

**예상 흐름**: candidate 선정 완료 → `PLATE_READ` `JobRecord` 요청 → `JobExecution` attempt 1 디스패치, 워커가 응답 없이 소멸(STALE: `ended_at=null`, `produced=[]`, `failure_kind=null`) → 같은 `job_id`로 `JobExecution` attempt 2 재시도(새 `execution_id`) → 다시 실패(`status=FAILED`) → `ReadoutRun`(`outcome=FAILED`, `failure.kind=INFRA`, `failure.code=READOUT_PROVIDER_TIMEOUT`) 생성, `plate_readouts=[]` 유지 → `CaseView rev1`(`progress[plate_read].state=RUNNING`) → `CaseView rev2`(`progress[plate_read].state=FAILED`, `running_jobs=[]`, blocking ERROR notice 추가).

**기대 결과**: `common/scenario_infra_failure_001.json`에 두 개의 `JobExecution`(attempt 1 STALE, attempt 2 FAILED)이 동일 `job_id`·서로 다른 `execution_id`로 존재. `readout/scenario_infra_failure_001.json`은 `readout_runs`에 `outcome=FAILED` 항목 1개, `plate_readouts=[]`. `case/scenario_infra_failure_001.json`의 rev2 `notices[0]`이 `severity=ERROR`·`blocking=true`.

**검증 Contract**: `JobRecord`·`JobExecution`(STALE→FAILED 재시도)·`ReadoutRun`(`outcome=FAILED`, `failure.kind=INFRA`)·`UsageRecord`·`CaseView`(RUNNING→FAILED, blocking notice)·`FrameRef`/`RecordingTimeline`(thumb_ref 자원용 최소 구성).

**의도적으로 만들지 않은 것**: `search`·`evidence` 모듈 전체(`modules_intentionally_absent`로 명시). candidate 탐색·선정은 이 시나리오의 검증 대상이 아니며, `PLATE_READ`가 인프라 단계에서 실패해 evidence assembly 자체가 시작되지 않는다. `SpanResolution.FAILED`, `EvidenceRecord` 관련 fixture도 이 시나리오에는 없다.

> **2026-09-10 v3 추가 (이슈 #26 B-readout-3·4).** ① attempt 1(STALE)에도 0원 `UsageRecord`를 추가했다 — 실패·재시도분이 비용 분모에서 조용히 빠지는 것을 막기 위한 mock pack 전체 컨벤션(이슈 #22 B-4, `docs/modules/case/decisions/eval-round2-ground-truth-and-usage.md`). 이 fixture가 「1 execution : `ReadoutRun` 1건」 불변조건의 STALE 예외(신유민·유소연 제안, `contract-job-record-case-view.md`·`contract-job-execution.md`에 등재)의 최초 반례이기도 하다. ② 같은 시나리오에 `OVERLAY_TIME_READ` run을 새로 추가해 `observation.status=UNKNOWN`·`reason.code=readout.overlay.presence_undetermined`인 "화면 시각 확인 불가" 갈래를 처음으로 만들었다(신유민이 이슈 #16에서 요청했던 것). `recording/scenario_infra_failure_001.json`에 그동안 없던 `IncidentClip`(`clip_x001`)도 이때 추가했다(정철원 확인 대기, provisional).

---

## `scenario_relative_rebase_001` — Timeline 상대전용(USABLE_RELATIVE_ONLY) + Rebase(revision 2) + SpanResolution PARTIAL(신규 유형 K)

**목적**:
- `contract-recording-timeline-asset-span.md`/`contract-analysis-scope.md`의 2026-09-07~08 최신 계약 변경분(P1-10)이 pack 전체에 0건이던 갭을 메운다: `TIMELINE_RELATIVE` scope, `RecordingTimeline.timeline_status=USABLE_RELATIVE_ONLY`, timeline rebase(revision 증가), `SpanResolution.status=PARTIAL` 네 가지를 한 시나리오로 함께 커버한다(정철원, 이슈 #18에서 전체 메커니즘 확정).
- 절대시각을 파싱할 수 없는 첫 영상으로 `RecordingTimeline` revision 1을 만든다 — `working_anchor.status=UNKNOWN`, `timeline_status=USABLE_RELATIVE_ONLY`, `time_source_candidates=[]`. Search는 `AnalysisScope.time_ranges[0].kind=TIMELINE_RELATIVE`(`timeline_ref={tl_rb001, revision:1}`)로 이 revision 1 좌표계에서 candidate를 만든다 — `가짜 ISO8601로 절대시각을 위장하지 않는다`는 원칙(`contract-analysis-scope.md` §10-7)이 정상 입력 경로로 실증된다.
- 두 번째 영상이 나중에 추가돼 timeline이 `revision 2`로 rebase된다. 기존 candidate의 `span.timeline_revision`은 rebase 후에도 `1`로 불변(B09)이고, `CaseView.candidates[].timeline_revision`/`stale_revision`(case 소유 구현 결정 — `docs/modules/case/decisions/candidate-stale-revision-display.md`)이 rev1→rev2에서 `false`→`true`로 바뀌어 「과거 timeline revision 기준」 표시를 실증한다.
- 두 소스의 usable 구간 사이에 의도적으로 30초 공백(600.0~630.0s)을 남기고(revision 1을 덮어쓰지 않고 보존), 그 공백을 가로지르는 `resolve_span()`(요청 범위 580.0~650.0s)이 `status:PARTIAL`, `failure:null`, `spans[]` 2건(각 소스에서 해석 가능한 edge) + `missing_ranges[]` 1건(`{timeline_range:{start_sec:600.0,end_sec:630.0}, reason:TIMELINE_GAP, source_ref:null}`)이 되는 것을 보여준다 — `TIMELINE_GAP`(내부 결손)과 `OUT_OF_TIMELINE_RANGE`(요청이 timeline 경계 밖)의 구분이 이걸로 실증된다.

**시작 조건**: 절대시각 후보가 전혀 없는(파일명·메타데이터 모두 파싱 불가) 영상 1개(`sa_rb001_a`, 0~600s)만 등록된 상태에서 시작한다.

**예상 흐름**: 영상 A 등록 → `RecordingTimeline revision 1`(`USABLE_RELATIVE_ONLY`) 생성 → `COARSE_SEARCH`(`TIMELINE_RELATIVE` scope, revision 1 좌표) → candidate 생성(`candidate_rb001`, `span.timeline_revision:1`) → `CaseView rev1`(`stale_revision:false`) → 영상 B 추가(`sa_rb001_b`, timeline 630~1230s) → `RecordingTimeline revision 2` 생성(A·B 사이 600~630s 공백 유지) → `CaseView rev2`(`stale_revision:true`) → 문맥 확장 조회가 공백을 가로지르며 `SpanResolution PARTIAL` 1건 생성.

**기대 결과**: `recording/scenario_relative_rebase_001.json`에 동일 `timeline_id`(`tl_rb001`)의 `revision:1`·`revision:2` 두 `RecordingTimeline`이 공존(과거 revision을 덮어쓰지 않음). `search/*.json`의 candidate `span.timeline_revision`은 `1`로 고정. `case/*.json`의 `case_views[1].candidates[0].stale_revision=true`. `span_resolutions[0].status="PARTIAL"`이고 `missing_ranges[0].reason="TIMELINE_GAP"`.

**검증 Contract**: `RecordingTimeline`(revision·`USABLE_RELATIVE_ONLY`·`working_anchor.status=UNKNOWN`)·`AnalysisScope`(`time_ranges[].kind=TIMELINE_RELATIVE`)·`CandidateEvent.span`(`timeline_revision` 보존)·`SpanResolution`(`PARTIAL`+`missing_ranges`+`TIMELINE_GAP`)·`CaseView`(`candidates[].timeline_revision`/`stale_revision`, case 소유 신규 필드).

**의도적으로 만들지 않은 것**: `readout`·`evidence` 모듈 전체(`modules_intentionally_absent`로 명시) — 이 시나리오는 timeline 메커니즘 자체에 집중하며, 완전한 `PLATE_READ`/evidence assembly 파이프라인은 다른 5개 시나리오가 이미 커버한다. `SpanResolution.FAILED`(위치를 특정할 수 없는 전체 실패)는 별도 항목으로 남겼다(P1-10 권장 수정). `PARTIAL` span_resolution은 별도 `IncidentClip`을 만들지 않는다 — `scenario_happy_001`의 `as_h001_fine` 고아 문제(P0-3)를 반복하지 않기 위한 의도적 scope 제한이다.

> **2026-09-10 v3 추가 (이슈 #26 B-web-8, 신유민 답변).** `stale_revision=true`일 표시 문구를 web이 임의로 만들지 않도록 `candidates[].stale_revision_label_key`(등록값 `candidate.stale_timeline_revision`)를 신설했다. `case_rev:1`은 `null`, `case_rev:2`(rebase 후)는 이 값이 채워진다. 세 필드 모두 같은 날 후속으로 나머지 5개 시나리오(`empty`는 `candidates=[]`라 제외)에 backfill했다 — `timeline_revision:1`·`stale_revision:false`·`stale_revision_label_key:null`(전부 단일 revision만 쓰는 시나리오라 값이 자명함). `docs/modules/case/decisions/candidate-stale-revision-display.md` 참고.

---

## Eval Harness 전용 fixture (시나리오 밖, `data/mock/expected/`)

| 파일 | 종류 | 목적 |
| --- | --- | --- |
| `eval_fixture_correct_001.json` | 항상-정답 | actual == expected일 때 metric 계산 코드가 만점(1.0)을 내는지 검증 |
| `eval_fixture_wrong_001.json` | 의도적 오답 | 잘못된 번호판 채택·나쁜 후보 순위·큰 timestamp 편차·false positive abstain을 각각 심어, metric 코드가 실제로 오류를 잡아내는지 검증 |

두 파일 모두 `provisional_non_contract_schema: true`로 표시했다 — eval의 정식 Ground Truth 스키마는 아직 어떤 Final Contract에도 정의돼 있지 않다(`contract-readout-run.md` §2 "정답지... 현재 없으며 eval 소유 후속").

> **2026-09-10 v3 예고 (이슈 #22 B-1, 김대원 답변).** 위 2개 파일은 **폐기 예정**이다 — 채점기가 맞는/틀린 입력에 각각 만점/낮은 점수를 주는지는 하니스 가짜 구현 2종이 실제 파이프라인으로 이미 증명하고, fixture 안에 기대 점수를 적어두는 이 방식은 채점 코드를 안 거쳐서 같은 걸 증명하지 못한다는 게 김대원의 판단이다. 대체품은 `data/mock/expected/<scenario_id>.expected.json` 7개(스키마 `eval-expected/v2`, `readout_ref`/`resolution_ref`/`timeline_ref` **참조** 방식 — fixture 값을 복사하지 않음)이며, **김대원이 자기 PR로 직접 작성**한다. case/mock owner는 이 디렉터리를 손대지 않기로 동의했다(`docs/modules/case/decisions/eval-round2-ground-truth-and-usage.md`). `plate_reread_001`의 실제 번호판(`17나2867`)·`unknown_abstain_partial_001`의 참값 사건 유형(없음, `EXCLUDED`)도 이 문서에서 확정해 eval에 회신했다.
