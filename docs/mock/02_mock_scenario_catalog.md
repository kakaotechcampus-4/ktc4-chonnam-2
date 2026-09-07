# 02. Mock Scenario Catalog

| Scenario ID | 목적 | 핵심 상황 | 통과 Contract | 기대 최종 상태 |
| --- | --- | --- | --- | --- |
| `scenario_happy_001` | 주요 Contract 전체 연결 + 정상 Case lifecycle + web 최종 CaseView 표현 + eval 정상 출력 읽기 검증 | 대상 차량·번호판·시각 모두 확정, 위치는 사용자 기억 단서라 review 필요 | RecordingTimeline·TimeSourceCandidate·SpanResolution·AnalysisScope·AnalysisRun·CandidateEvent·VisualEvidence·ReadoutRun·PlateReadout·OverlayTimeReadout·Observation·TimeResolution·EvidenceRecord·EvidenceNeeds·RequirementReport·ReportPackage·JobRecord·JobExecution·UsageRecord·CaseView | `CaseView.stage=READY`, `readiness=WARN`, `package` 존재 |
| `scenario_partial_001` | Partial Success(시간 성공/번호판 ABSTAIN/GPS 없음) + SpanResolution PARTIAL + AnalysisRun PARTIAL 검증. 전체 Case가 실패하지 않고 나머지 정보가 유지되는지 확인 | 신호위반 목격, 대상 차량 특정 모호, 번호판 판독 ABSTAIN, 위치 정보 없음 | 위와 동일 (ReportPackage 제외 — BLOCK이라 미생성) | `CaseView.stage=EVIDENCE_REVIEW`, `readiness=BLOCK`, `package=null`, notices에 `PLATE_ABSTAINED`/`LOCATION_UNKNOWN` |

두 Scenario는 검증해야 할 상황 유형(A~I) 중 다음을 대표로 커버한다:

- A. Happy Path → `scenario_happy_001`
- E. Partial Success (시간 성공/번호판 ABSTAIN/위치 없음) → `scenario_partial_001`
- C. UNKNOWN/근거 부족 (GPS Observation UNKNOWN, `plate_display.info_state=INFO_UNKNOWN`) → `scenario_partial_001`
- D. ABSTAIN (`PlateReadout.abstained=true`, `ReadoutRun.outcome=SUCCEEDED`인데도 abstain) → `scenario_partial_001`
- G. Evidence 부족 (`EvidenceNeeds.items=[PLATE_REREAD]`, `RequirementReport.overall=BLOCK`) → `scenario_partial_001`
- H. 값 충돌에 준하는 상황 (`VisualEvidence.target.association_status=AMBIGUOUS`) → `scenario_partial_001`

B(결과 없음)/F(사용자 확인·수정)/I(재실행)는 이번 Seed에서 대표 Scenario로 만들지 않았다 — F/I는 `CorrectionRecord`가 Draft라 근거 계약이 아직 Final이 아니고(`CONTRACT_CONFLICTS.md` §3), B는 두 대표 Scenario 모두 Candidate가 1개 이상 발견되는 경우라 별도로 다루지 않았다(필요 시 v1에서 `scenario_no_candidate_001` 추가 권장).

---

## `scenario_happy_001`

### 목적

recording부터 case까지 5개 모듈 체인 전체가 하나의 Case로 연결되는지, 그리고 `readiness=WARN`이어도 `ReportPackage`가 생성될 수 있다는 불변조건(`contract-job-record-case-view.md` B§10-3)이 실제로 성립하는지 확인한다.

### 시작 조건

블랙박스 영상 42개 파일 업로드(2개 실패), 사용자 힌트: "18:30 전후, 흰색 SUV, 백색 실선 crossing 가능성, 미금역 근처".

### 예상 흐름

```
사용자 업로드 + 힌트
→ case: AnalysisScope 생성 (scope_h001)
→ search: AnalysisRun(run_h001_search, SUCCEEDED) → CandidateEvent(cand_h001, rank1) → VisualEvidence(ve_h001, OBSERVED)
→ case: JobRecord(job_h001_plate) 발주 → common/runtime: JobExecution(exec_h001_plate, SUCCEEDED)
→ readout: ReadoutRun ×2(rr_h001_plate/overlay, 둘 다 SUCCEEDED) → PlateReadout(비abstain, OK) + OverlayTimeReadout(OK, 검증 4항목 모두 true)
→ evidence: Observation(GPS, UNKNOWN — 이 대시캠엔 GPS 없음) + TimeResolution(OK, overlay VERIFIED 채택) → EvidenceRecord(ev_h001, 번호판/시각 확정, 위치는 `user_hint`로 보존) → EvidenceNeeds(items=[], 추가 요청 없음) → RequirementReport(FINAL_PACKAGE, overall=WARN) → ReportPackage(pkg_h001) 생성
→ case: CaseView(stage=READY, readiness=WARN, package=pkg_h001)
→ eval: ground truth와 정답 prediction 비교(항상 일치), 오답 prediction으로 채점기 오류 탐지 확인
```

### 주요 기대 결과

- `AnalysisRun.outcome=SUCCEEDED`이고 `CandidateEvent`가 1개 이상 존재한다(Candidate 0개 정상도 별도 시나리오 대상이나 이번엔 1개로 진행)
- `PlateReadout.abstained=false`이고 `ReadoutRun.outcome=SUCCEEDED`다
- `RequirementReport.overall=WARN`이어도 `ReportPackage`가 생성된다(`readiness ∈ {PASS,WARN}`이면 package 허용, CaseView B§10-3)
- `CaseView.stage=READY`이고 `package`가 non-null이다
- eval의 `prediction_correct`는 `expected` ground truth와 완전히 일치하고, `prediction_wrong`은 rank/visual_event_type/plate 세 곳에서 의도적으로 어긋난다

### 이 Scenario가 검증하는 Contract

RecordingTimeline · TimeSourceCandidate · SpanResolution · AnalysisScope · AnalysisRun · CandidateEvent · VisualEvidence · ReadoutRun · PlateReadout · OverlayTimeReadout · Observation · TimeResolution · EvidenceRecord · EvidenceNeeds · RequirementReport · ReportPackage · JobRecord · JobExecution · UsageRecord · CaseView

### 사용 담당자

Producer 순서대로 정철원(recording) → 서어진(search) → 신유민(readout) → 김준영(evidence/common) → 유소연(case) → 김대원(eval). 각자 자기 모듈 fixture가 실제 자기 구현이 만들 수 있는 형태인지 검수한다(`04_mock_validation_report.md` §22 참고).

---

## `scenario_partial_001`

### 목적

"일부만 성공해도 전체 Case가 실패하지 않는다"는 v4 원칙이 실제로 여러 계약에 걸쳐 일관되게 표현되는지 확인한다. 특히 `PlateReadout.abstained=true`이어도 `ReadoutRun.outcome=SUCCEEDED`라는, 실무에서 가장 헷갈리기 쉬운 불변조건(ReadoutRun §9 「abstain은 실패가 아니다」)을 Mock으로 못 박는다.

### 시작 조건

블랙박스 영상 12개 파일 업로드(1개 실패), 사용자 힌트: "아침 출근길, 신호위반 목격" (차량·위치 힌트 없음).

### 예상 흐름

```
사용자 업로드 + 힌트(차량/위치 정보 없음)
→ case: AnalysisScope 생성 (scope_p001)
→ recording: RecordingTimeline(tl_p001) → SpanResolution(PARTIAL, 자산 1건 SOURCE_UNAVAILABLE)
→ search: AnalysisRun(run_p001_search, PARTIAL, issue 1건) → CandidateEvent(cand_p001, rank1, ranking_score 낮음) → VisualEvidence(ve_p001, OBSERVED이지만 target AMBIGUOUS)
→ case: JobRecord(job_p001_plate) 발주 → JobExecution(exec_p001_plate, SUCCEEDED — abstain은 실패가 아니므로 실행 자체는 성공)
→ readout: ReadoutRun ×2(둘 다 SUCCEEDED) → PlateReadout(abstained=true, FRAME_DISAGREEMENT) + OverlayTimeReadout(OK)
→ evidence: Observation(GPS, UNKNOWN) + TimeResolution(OK, overlay 채택 — 시간은 성공) → EvidenceRecord(ev_p001, vehicle_number/location 필드 자체가 부재) → EvidenceNeeds(items=[PLATE_REREAD]) → RequirementReport(EVIDENCE scope, overall=BLOCK — 번호판 미확정)
→ ReportPackage 생성 안 함(BLOCK이므로 의도된 부재)
→ case: CaseView(stage=EVIDENCE_REVIEW, readiness=BLOCK, package=null, notices=[PLATE_ABSTAINED, LOCATION_UNKNOWN])
```

### 주요 기대 결과

- `SpanResolution.status=PARTIAL`이고 `spans`·`missing_ranges`가 모두 비어있지 않다
- `AnalysisRun.outcome=PARTIAL`이고 `issues.length>=1`이다(불변조건 §6-1 7번)
- `PlateReadout.abstained=true`인데도 `ReadoutRun.outcome=SUCCEEDED`다 — **이게 이 Scenario의 핵심 검증 지점**
- `EvidenceRecord`에 `vehicle_number`/`location` 키 자체가 없다(placeholder/null이 아니라 필드 부재로 표현 — 계약 §10 불변조건)
- `EvidenceNeeds.items`에 `PLATE_REREAD`가 있다
- `RequirementReport.overall=BLOCK`이라 `ReportPackage`가 생성되지 않는다
- Case 전체는 실패 상태가 아니다 — `CaseView.stage=EVIDENCE_REVIEW`(에러 화면 아님)이고 `candidates`/`evidence.event_time_display` 등 확보된 정보는 그대로 유지된다

### 이 Scenario가 검증하는 Contract

RecordingTimeline · TimeSourceCandidate · SpanResolution(PARTIAL) · AnalysisScope · AnalysisRun(PARTIAL) · CandidateEvent · VisualEvidence(AMBIGUOUS) · ReadoutRun · PlateReadout(ABSTAIN) · OverlayTimeReadout · Observation(UNKNOWN) · TimeResolution · EvidenceRecord(필드 부재) · EvidenceNeeds · RequirementReport(BLOCK) · JobRecord · JobExecution · UsageRecord · CaseView

이 Scenario는 eval fixture를 포함하지 않는다(Seed v0 범위 — `data/mock/manifest.json`의 `excluded_from_seed_v0` 참고 아님, 단순히 이번엔 안 만듦).

### 사용 담당자

Happy와 동일한 순서. 특히 신유민(readout)의 abstain 표현과 유소연(case)의 notices 매핑을 우선 검수 대상으로 표시한다(`04_mock_validation_report.md` §22).
