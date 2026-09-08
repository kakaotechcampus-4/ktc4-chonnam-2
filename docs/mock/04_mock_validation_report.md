# 04. Mock Validation Report

`data/mock/validate_mock_pack.py` 실행 결과: **28개 JSON 파일, 4개 시나리오 스캔 — 오류 0건, 경고 0건 (VALIDATION PASSED)**. 이 스크립트가 기계적으로 확인하는 항목: JSON parse, 필수 top-level 키 존재, 닫힌 enum 값 검사(`ReadoutRun.outcome/operation`, `JobExecution.status`, `RequirementReport.overall`, `TimeResolution.status`, `CaseView.stage`), 같은 Scenario 내 모든 `{kind, ref}` ContractRef의 참조 해석(dangling ref 검사), Scenario manifest의 `artifacts` 경로 실존 여부, `ReadoutRun`/`JobExecution`의 outcome↔failure/ended_at 정합성, `AnalysisRun` candidate span의 `start_ms<=end_ms`와 `thumbnail_ref`가 해당 candidate 구간 안의 offset을 가리키는지(시간/구간 일관성).

## 1. Contract × Variant Coverage

| Contract | Normal | Empty | Unknown | Abstain | Partial | 기타(Failed/NotRun/Conflict/Supersede) |
| --- | --- | --- | --- | --- | --- | --- |
| `SourceAsset`/`MediaStream`/`FrameRef` | ✅ happy | N/A | N/A | N/A | N/A | — |
| `RecordingTimeline`/`AssetSpan`/`SpanResolution` | ✅ happy(USABLE, COMPLETE) | N/A | N/A | N/A | ❌ 미커버(SpanResolution PARTIAL/failure 없음) | — |
| `TimeSourceCandidate` | ✅ happy | N/A | N/A | N/A | N/A | ✅ 충돌 2건(unknown_abstain_partial) |
| `AnalysisSource`/`IncidentClip`/`DerivedAsset`/`RemoteCopy`/`DeletionReport` | ✅ happy | N/A | N/A | N/A | ✅ DeletionReport=PARTIAL(happy) | ❌ DeletionReport COMPLETE/FAILED 미커버 |
| `AnalysisScope`/`AnalysisRun`/`CandidateEvent` | ✅ happy | ✅ empty(candidates=[], outcome=SUCCEEDED) | N/A | N/A | N/A | — |
| `VisualEvidence` | ✅ happy | N/A(빈 결과 시나리오는 애초에 생성 안 됨) | N/A | N/A | N/A | ✅ 낮은 confidence(unknown_abstain_partial) |
| `PlateReadout` | ✅ happy(OK, abstain 없음) | N/A | N/A | ✅ unknown_abstain_partial | — | — |
| `OverlayTimeReadout` | ✅ happy(OK) | N/A | N/A | N/A | — | ✅ NOT_RUN(correction_rerun, 레코드 자체 부재) · ✅ 완전 실패로 결과 미생성(unknown_abstain_partial) |
| `ReadoutRun` | ✅ happy(SUCCEEDED×2) | N/A | N/A | (abstain은 `PlateReadout.abstained`가 가짐, `ReadoutRun.outcome`은 계속 SUCCEEDED) | ❌ PARTIAL outcome 미커버 | ✅ FAILED(unknown_abstain_partial overlay) |
| `TimeResolution` | ✅ happy(status=OK) | N/A | ❌ status=UNKNOWN(시각 자체 없음) 미커버 | — | — | ✅ conflict.exists=true · ✅ NEEDS_REVIEW · ✅ supersede/USER_OVERRIDE |
| `EvidenceRecord` | ✅ happy(모든 필드 confirmed) | N/A | ✅ vehicle_number 필드 부재 | — | — | ✅ supersede(correction_rerun) |
| `EvidenceNeeds` | ✅ happy(items=[]) | N/A | — | — | ✅ PLATE_REREAD 요청(optional=false) | — |
| `RequirementReport` | ✅ happy(PASS×2) | N/A | ✅ overall=UNKNOWN | — | ✅ overall=WARN(correction_rerun v1) | ✅ supersede |
| `ReportPackage` | ✅ happy | N/A | ✅ 미생성(overall≠PASS/WARN인 시나리오는 `report_packages=[]`) | — | — | — |
| `JobRecord` | ✅ happy | ✅ empty(1건만 발주) | — | — | ✅ force_rerun=true(재판독) | — |
| `CaseView` | ✅ happy(stage=READY) | ✅ empty(stage=CANDIDATE_REVIEW) | ✅ plate_display.info_state=INFO_UNKNOWN | — | ✅ EVIDENCE_REVIEW + running_jobs | ✅ notices(WARN/INFO) |
| `JobExecution` | ✅ happy(SUCCEEDED) | ✅ empty | — | — | ✅ QUEUED(재판독 대기) | ✅ FAILED |
| `UsageRecord` | ✅ happy | ✅ empty | — | — | — | ✅ token_usage=null(로컬 OCR provider) |

**커버리지 갭(정직하게 미커버로 남긴 것)**: `SpanResolution`의 `PARTIAL`/`failure≠null` 케이스, `DeletionReport`의 `COMPLETE`/`FAILED` 케이스, `ReadoutRun.outcome=PARTIAL`, `TimeResolution.status=UNKNOWN`(시각을 전혀 알 수 없는 경우). 4개 시나리오 안에 억지로 욱여넣기보다 갭으로 남기고 여기 기록하는 편이 이 작업의 "절대 조용히 결정하지 않는다" 원칙에 맞다고 판단했다. 필요하면 5번째 시나리오로 후속 추가할 수 있다.

## 2. Scenario × Contract Coverage

| Scenario | recording 계약군 | search 계약군 | readout 계약군 | evidence 계약군 | case/common 계약군 |
| --- | --- | --- | --- | --- | --- |
| `scenario_happy_001` | ✅ 전체 | ✅ 전체 | ✅ 전체 | ✅ 전체 | ✅ 전체 |
| `scenario_empty_001` | — (의도적 미포함, 시나리오 manifest에 사유 기록) | ✅ AnalysisScope/AnalysisRun | — | — | ✅ JobRecord/JobExecution/UsageRecord/CaseView |
| `scenario_unknown_abstain_partial_001` | ✅ (충돌 시각 포함) | ✅ | ✅ (abstain + 완전실패) | ✅ (UNKNOWN + Needs) | ✅ (자동 재판독 발주 포함) |
| `scenario_correction_rerun_001` | ✅ | ✅ | ✅ (overlay NOT_RUN) | ✅ (supersede chain) | ✅ |

## 3. 발견한 문제

### 3.1 Contract 충돌

**없음.** 서로 다른 두 Final Contract가 같은 대상에 대해 값을 부정하는 치명적 충돌은 발견하지 못했다.

### 3.2 불명확한 Contract

1. **`TimeResolution.resolved.verification`(`AGREED`/`VERIFIED`/`UNVERIFIED`)와 `computation.mode=USER_OVERRIDE`의 대응 관계 미명시.** §4 조건표는 `status=OK`를 "검증된 Video Overlay 또는 명시적 사용자 확정"에 준다고만 하고, 사용자 확정일 때 `verification`이 셋 중 무엇인지 명시하지 않는다. `scenario_correction_rerun_001`에서는 `AGREED`("사용자가 동의/확정")로 해석해 사용했다. Owner(`evidence`, 김준영) 확인이 필요하다.
2. **한 번도 AI를 거치지 않은 순수 사용자 입력 값의 `EvidenceValue.source.observability`/`user_corrected` 판정 기준 미명시.** `EvidenceRecord.location.user_hint`/`search_keyword`처럼 처음부터 사용자가 직접 입력한 값에 대해, `observability=OBSERVED`로 볼지, `user_corrected`를 어떻게 셀지(교정된 적이 없으므로 `false`로 뒀다) 계약이 정하지 않는다. `scenario_happy_001`에서 `observability=OBSERVED`·`user_corrected=false`로 해석해 사용했다.
3. **`CaseView.evidence.review_needed`(object-level)의 파생 규칙 미명시.** 개별 `*_display.needs_review`/`info_state`와 별개 축이라는 것만 알 수 있고, 언제 `true`가 되는지 파생 규칙이 없다. Mock에서는 "개별 `needs_review` 중 하나라도 true"를 잠정 기준으로 삼았다(`scenario_unknown_abstain_partial_001`에서 `true`).
4. **`EvidenceRecord.event.safety_report_type`의 실제 값 공간(안전신문고 신고유형 enum/코드)이 어느 Final Contract에도 등재돼 있지 않다.** `SafetyReportType`이라는 타입 이름만 있고 값 목록 출처가 없다. Mock은 `UNSAFE_LANE_CHANGE`/`UNSAFE_SIGNAL_VIOLATION`/`UNSAFE_SIDEWALK_PARKING` 형태로 임시 코드를 붙였다 — **이 값들은 등록된 enum이 아니라 Mock 편의 placeholder이며, 실제 값 공간이 확정되면 반드시 교체해야 한다.**

### 3.3 Architecture 확인 필요

1. **`JobRecord.kind`에 Report Video export / `purge_case()` 발주용 값이 없다.** `kind`는 열린 enum이라 등재만 하면 되지만, 현재 등록된 값(`COARSE_SEARCH`/`PLATE_READ`/`OVERLAY_TIME_READ`)만으로는 신고용 파생영상(Report Video) 생성이나 사건 삭제(`purge_case`)를 어떤 Job으로 발주하는지 알 수 없다. `contract-analysis-source-derived.md`의 `DerivedAsset`(`derived_role=REPORT_VIDEO`)이 생성되는 경로가 Job Intent 레벨에서 아직 이름이 없다. 이 Mock Pack은 새 `kind` 값을 임의로 만들지 않았다 — `scenario_happy_001`의 `da_h001_report_video`는 recording fixture 안에 이미 만들어진 상태로 등장시켜 이 갭을 우회했다.
2. **`contract-visual-evidence.md`의 예시가 stale.** 계약 본문 §의 JSON 예시가 `"frame:incident-17@6400"` 같은 위치 인코딩 문자열을 그대로 쓰고 있다. 이후 `contract-source-asset-media-stream.md`(2026-09-08 Consumer Review 종결)가 `FrameRef`를 `fr_<opaque-id>` 형식으로 확정했으므로, 이 예시는 최신 관례와 형식이 다르다. **이 Mock Pack은 계약 본문을 고치지 않았고**, 대신 이 Mock에서는 확정된 `fr_<opaque-id>` 형식만 사용했다(`ve_h001.target.evidence_refs = ["fr_h001_thumb"]` 등). `visual-evidence` 계약 예시 자체의 갱신은 Owner(서어진/search 또는 evidence Owner 김준영)의 판단이 필요하다.

### 3.4 Fixture 생성 불가

1. **`CorrectionRecord`의 필드 스키마 fixture.** `contract-correction-record.md`는 아직 `Status: Draft`다(다른 13개는 `Final — Accepted`). `TimeResolution.considered[].input_kind=USER_INPUT`과 `EvidenceRecord.provenance.correction_refs[]`가 구조적으로 `{kind:"correction_record", ref:...}` opaque reference를 요구하므로, `scenario_correction_rerun_001`에서 그 **참조(ref)** 는 사용했지만 `CorrectionRecord` 자신의 필드 모양을 가진 별도 fixture 파일은 만들지 않았다. Draft 계약의 필드를 이 작업에서 임의로 확정해 Mock을 생성하는 것은 "Contract를 Mock 편의로 만들어내지 않는다"는 원칙에 위배되기 때문이다. `contract-correction-record.md`가 Final로 승격되면 이 부분을 채워야 한다.

## 4. Owner 검수 배정

Producer/Consumer는 각 Contract 문서 헤더와 `docs/management/ownership.md`(R&R)에서 그대로 가져왔다 — 임의로 정하지 않았다.

| 영역 / Contract 군 | Producer Owner | Consumer Owner | Mock 검수 담당 |
| --- | --- | --- | --- |
| `SourceAsset`~`DeletionReport` (recording) | 정철원 | 서어진(search)·신유민(readout)·김준영(evidence)·유소연(case, projection) | 정철원(Producer 1차) → 서어진·신유민·김준영 |
| `AnalysisScope`/`AnalysisRun`/`CandidateEvent`/`VisualEvidence` (search) | 서어진 | 유소연(case, direct)·김준영(evidence)·김대원(eval) | 서어진 → 유소연·김준영·김대원 |
| `PlateReadout`/`OverlayTimeReadout`/`ReadoutRun` (readout) | 신유민 | 유소연(case, direct)·김준영(evidence, projection)·김대원(eval) | 신유민 → 유소연·김준영·김대원 |
| `TimeResolution`/`EvidenceRecord`/`EvidenceNeeds`/`RequirementReport`/`ReportPackage` (evidence) | 김준영 | 유소연(case, direct)·신유민(web, projection) | 김준영 → 유소연·신유민 |
| `JobRecord`/`CaseView` (case) | 유소연 | 신유민(web)·김대원(eval, 간접) | 유소연(본인) → 신유민 |
| `JobExecution`/`UsageRecord` (common/runtime) | 김준영(계약 Owner)·정철원(구현 담당) | 유소연(case)·신유민(web, projection)·김대원(eval)·서어진(search, UsageRecord만)·신유민(readout, UsageRecord만) | 김준영·정철원 → 유소연·김대원 |
| Eval Harness fixture (`expected/*.json`, provisional) | (이 Mock Pack 작성자 — eval 소유 계약 아님) | 김대원(eval) | 김대원이 정식 Ground Truth Contract 확정 후 전면 재검토 필요 |

### Owner별 리뷰 체크리스트

**Producer 관점 (자기 모듈이 생산하는 Contract)**

- 이 Mock 출력이 실제로 내 모듈이 이 모양으로 만들어낼 수 있는 값인가?
- 확정된 Final Contract와 필드 이름·타입·nullable 여부가 정확히 일치하는가?
- 비현실적인 값 조합(예: `abstained=true`인데 `observation.status=OK`)이 섞여 있지 않은가?
- `03_mock_artifact_templates.md`·`04_mock_validation_report.md` §3.2·§3.3에 내 계약과 관련된 불명확한 지점이 있다면 그 해석이 내가 의도한 것과 같은가?

**Consumer 관점 (다른 모듈이 생산한 것을 내가 소비)**

- 이 fixture 하나만 보고 내 모듈 개발을 시작할 수 있는가?
- 내가 처리해야 하는 실패/부분성공/UNKNOWN/ABSTAIN 상태가 최소 1건씩 fixture에 있는가?
- 내가 참조하는 ID가 같은 Scenario의 다른 모듈 fixture 안에서 실제로 정의돼 있는가(dangling 아님)?
- 내가 재계산하면 안 되는 값(예: `RequirementReport.overall`, `CaseView.info_state`)을 이 Mock이 이미 계산해서 주고 있는가?

## 5. 1차 Mock E2E 통합 가능 여부

**조건부 가능.** 이유: §1의 4개 커버리지 갭(`SpanResolution` 부분실패, `DeletionReport` COMPLETE/FAILED, `ReadoutRun.PARTIAL`, `TimeResolution.UNKNOWN`)과 §3.2~§3.4의 5건은 통합을 막는 치명적 결함이 아니라 "지금 상태를 알고 시작하라"는 조건이다. 4개 시나리오·26개 실제 fixture·검증 스크립트 통과(0 오류)로 각 모듈이 병렬 개발·1차 통합을 시작하기에 충분한 골격이 갖춰졌다.
