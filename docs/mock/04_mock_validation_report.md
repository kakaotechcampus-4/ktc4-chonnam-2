# 04. Mock Validation Report

`data/mock/validate_mock_pack.py` 실행 결과: **36개 JSON 파일, 5개 시나리오 스캔 — 오류 0건, 경고 0건 (VALIDATION PASSED)**.

> **2026-09-08 갱신.** 심층 검토(`05_mock_deep_review_report.md`) 이후 검증 스크립트를 강화하고 그때 잡힌 17건을 수정했다 — 미등록 사건 유형 10건(P0-1), `VisualEvidence` 필수 필드 누락 6건(P0-2), `disagree_positions` off-by-one 1건(P1-4). 추가로 overlay `samples[].offset_sec` 좌표계, `manifest_summary.range`, `processed_duration`, happy의 `deletion_reports` 분리, `CaseView` 스냅샷 3종(처리중·최종확인·정정 전) 추가를 반영했다. **P0-3(`VISUAL_VERIFY` run 부재)과 P0-4(「화면 시각 없음」 모델링)는 Owner 답변 대기로 미해소 상태다.**
>
> **2026-09-09 갱신 (case Owner 유소연 2차 검수).** §12에서 유소연에게 배정됐던 case 담당 항목 4건을 전부 결정·반영했다 — `JobRecord.kind`에 `FINE_VERIFY`·`REPORT_VIDEO_EXPORT` 등재(+`purge_case`는 Job 밖 관리 동작으로 확정, §3.3-1), u001 `scope_u001`을 timeline과 일치하도록 축소(P1-8 잔여 종결), `evidence.review_needed` OR 파생 규칙 확정(§3.2-3). 검수 중 `CaseView.requirements_evidence/package.checks[]`가 계약이 요구하는 `RequirementReport` 원형(`category`·`subject_refs`·`measurement`)을 담지 않고 있던 것을 새로 발견해 4개 시나리오 전부 수정했다(P1-13, `05` §8 참고). **P0-3의 나머지(서어진의 `input_ref.kind` 결정)와 P3-1(예산 통화, 유소연+김준영 공동)은 이 시점엔 여전히 미해소였다 — 둘 다 2026-09-09 2라운드(이슈 #15·#19 반영)에서 도메인 판단은 종결되고 fixture 반영만 남았다.**
>
> **2026-09-09 2차 갱신 (case Owner 유소연 · 팀 리뷰 이슈 #15~#19 5건 종합 반영).** 팀원 5명이 GitHub 이슈로 남긴 §12/§13 회신을 전부 읽고 반영했다 — P0-3 완전 해소(서어진, `input_ref.kind` 결정), P1-12 taxonomy 확정(신유민), P2-2 `category=VEHICLE` 확정(김준영), P0-4 재정의: `OverlayTimeReadout`의 「화면 시각 없음」은 `outcome=FAILED`가 아니라 `outcome=SUCCEEDED` + `observation.status=NOT_APPLICABLE`(결과 객체는 생성됨)로 정정(신유민). 아울러 `scenario_unknown_abstain_partial_001`이 C·D·E·G·H·I 6개 유형을 한 fixture에 몰아넣으면서 "사건 유형 자체가 불확실"(EvidenceRecord를 만들 수 없음)과 "사건 유형은 확정, 번호판만 abstain"(EvidenceRecord가 있어야 함)이라는 두 전제가 충돌하고 있던 것을 발견해(김준영 제안, §3.1-4) `scenario_unknown_abstain_partial_001`(E·H)과 신규 `scenario_plate_reread_001`(C·D·G·I)로 분리했다. 분리 과정에서 **`EvidenceNeeds`(v1)가 "AI가 사건 유형 자체를 확정하지 못했다"는 상황을 표현할 계약상 메커니즘이 없다는 새 Contract Gap**을 발견해 §3.1-4에 기록했다(이 gap 자체는 새 계약/필드 신설이 필요할 수 있어 case Owner 단독으로 해소하지 않았다). 이 분리로 `ReadoutRun.outcome=FAILED`와 `JobExecution.status=FAILED`가 fixture에서 사라져 새 커버리지 갭이 됐다 — §1 표에 반영.
>
> **2026-09-09 3차 갱신 (이슈 #15~#19 전량 원문 재대조).** 2라운드 요약의 일부 오류(김준영 ①④·P3-1·P1-3 오독)를 사용자가 지적해 5개 이슈 전문을 다시 대조했다. `scenario_correction_rerun_001`의 `OverlayTimeReadout` "NOT_RUN(레코드 자체 부재)" 설계가 정철원이 확인한 "오버레이 OCR은 선택된 후보마다 무조건 디스패치"라는 v1 정책과 모순됨을 발견해 u001과 동일한 "실행됨+NOT_APPLICABLE"로 재구성했다(§1·§2 표 갱신). `readout.overlay_not_present`(밑줄) reason.code를 신유민이 지정한 `readout.overlay.not_present`(점 표기)로 통일하고 `validation.*_ok`를 `false`→`null`로 정정했다. P1-11(eval 채점 모델 근본원인·metric 개명표)·P2-9(비용 분모 3단 설명)는 `05_mock_deep_review_report.md` §8에서 김대원 원문 그대로 재작성했다(수치 자체는 이미 정정돼 있어 이 파일 변경 없음).

스크립트가 기계적으로 확인하는 항목:

- JSON parse · 파일 wrapper(`scenario_id`/`module`) · 모듈별 필수 top-level 배열
- **닫힌 enum 30여 종** — `VisualEventType`(4종), `verification`, `association_status`, `primitives[].state`, `Observation.status`, `target_association.status`, `timeline_status`, `TimeSourceCandidate.source_kind`, `SpanResolution.status`, `DeletionReport.status`/`items[].result`, `derived_role`, `availability`, `asset_kind`, `AnalysisRun.operation`/`outcome`, `AnalysisScope.time_ranges[].kind`, `RequirementCheck.category`/`outcome`, `EvidenceNeeds.kind`/`would_fill`, `CaseView.stage`/`progress[].state`/`notices[].severity`/`running_jobs[].status`/`info_state`, `UsageRecord.run_ref.kind` 등 (각 세트에 소유 계약을 주석으로 명시)
- **계약별 필수 키** — `VisualEvidence` 11키(`legal_status` 포함), `AnalysisRun` 11키, `Observation` 6키, `JobExecution` 10키, `UsageRecord` 12키, `CaseView` 14키, `SpanResolution.failure` 등
- **참조 해석** — 같은 시나리오 안의 `{kind, ref}` ContractRef + **평문 문자열 ref**(`thumbnail_ref`·`frame_ref`·`usage_refs[]`·`job_id`·`evidence_refs[]`·`package_ref` 등), 그리고 **ref의 `kind`가 실제 대상 객체의 종류와 일치하는지**
- **조건부 불변조건** — `legal_status is null`, `verification≠OBSERVED ⇒ visual_event_type=null`, `abstained ⇒ observation.status=NEEDS_REVIEW`, `availability=AVAILABLE ⇒ byte_size≠null`, `timeline_ref/timeline_range` 쌍, `BASE_PLUS_OFFSET ⇒ base_input_ref+source_offset_ms`, `EvidenceValue`의 `user_corrected`/`needs_review` 상호배타, `RequirementReport.overall == precedence(checks)`, `SpanResolution` 완전성, `ReadoutRun`/`JobExecution`의 outcome↔failure/ended_at
- **시간축 파생값 재계산** — `base 시각 + source_offset_ms == resolved.value`, overlay `samples[].offset_sec`가 clip 구간 안인지, `validation.sample_count == len(samples)`, `AssetSpan`의 timeline 길이 == source 길이, candidate span의 `start_ms<=end_ms`와 `thumbnail_ref` 위치
- **번호판 마스킹 정합** — `disagree_positions`가 `frame_results` 간 실제 불일치 위치·`observation.value`의 `?` 위치와 일치하는지
- **manifest 정합** — 상위 `manifest.json`의 시나리오/eval 경로 실존과 목록 일치, scenario manifest의 `artifacts`·`shared_ids`가 실제 fixture와 일치하는지
- **eval fixture** — `provisional_non_contract_schema` 선언, `actual_ref` 해석, `ALWAYS_CORRECT`/`DELIBERATELY_WRONG`의 `expect_match` 일관성, 오답 fixture에 `actual_ref`가 없는지
- **시나리오 간 ID 유일성**(경고)

## 1. Contract × Variant Coverage

| Contract | Normal | Empty | Unknown | Abstain | Partial | 기타(Failed/NotRun/Conflict/Supersede) |
| --- | --- | --- | --- | --- | --- | --- |
| `SourceAsset`/`MediaStream`/`FrameRef` | ✅ happy | N/A | N/A | N/A | N/A | — |
| `RecordingTimeline`/`AssetSpan`/`SpanResolution` | ✅ happy(USABLE, COMPLETE) | N/A | N/A | N/A | ❌ 미커버(SpanResolution PARTIAL/failure 없음) | — |
| `TimeSourceCandidate` | ✅ happy | N/A | N/A | N/A | N/A | ✅ 충돌 2건(unknown_abstain_partial) |
| `AnalysisSource`/`IncidentClip`/`DerivedAsset`/`RemoteCopy` | ✅ happy | N/A | N/A | N/A | N/A | ❌ export 실패 미커버 |
| `DeletionReport` | ❌ | N/A | N/A | N/A | ❌ | ❌ **전면 미커버** — happy에 있던 `PARTIAL` 예시는 「AVAILABLE 자산과 DELETED 결과가 같은 스냅샷에 공존」 문제(05 P1-1) 때문에 제거했다. 별도 `scenario_purge_001`로 다시 만들어야 한다(05 §10-4) |
| `AnalysisScope`/`AnalysisRun`/`CandidateEvent` | ✅ happy | ✅ empty(candidates=[], outcome=SUCCEEDED) | N/A | N/A | N/A | — |
| `VisualEvidence` | ✅ happy | N/A(빈 결과 시나리오는 애초에 생성 안 됨) | N/A | N/A | N/A | ✅ 낮은 confidence(unknown_abstain_partial) · ✅ `verification=UNCERTAIN`/`visual_event_type=null`(unknown_abstain_partial) |
| `PlateReadout` | ✅ happy(OK, abstain 없음) | N/A | N/A | ✅ plate_reread | — | ✅ 프레임 간 인식 불일치(plate_reread) |
| `OverlayTimeReadout` | ✅ happy(OK) | N/A | N/A | N/A | — | ✅ NOT_APPLICABLE(unknown_abstain_partial, correction_rerun 둘 다 — 오버레이 없음이지만 결과 객체는 생성됨·`outcome=SUCCEEDED`) |
| `ReadoutRun` | ✅ happy(SUCCEEDED×2) | N/A | N/A | (abstain은 `PlateReadout.abstained`가 가짐, `ReadoutRun.outcome`은 계속 SUCCEEDED) | ❌ PARTIAL outcome 미커버 | ❌ **FAILED 신규 미커버** — 2026-09-09 P0-4 재정의로 이전에 유일했던 FAILED 예시(unknown_abstain_partial overlay)가 SUCCEEDED+NOT_APPLICABLE로 바뀌면서, 현재 fixture 중 `outcome=FAILED` 실사례가 없다. 규칙(§6/§8, 완전 실패 시 결과 객체 자체가 없음) 자체는 유효하나 fixture 증거가 없다. |
| `TimeResolution` | ✅ happy(status=OK) | N/A | ❌ status=UNKNOWN(시각 자체 없음) 미커버 | — | — | ✅ conflict.exists=true · ✅ NEEDS_REVIEW · ✅ supersede/USER_OVERRIDE |
| `EvidenceRecord` | ✅ happy(모든 필드 confirmed) | N/A | ✅ vehicle_number 필드 부재(plate_reread) | — | — | ✅ supersede(correction_rerun) · ❌ **완전 미생성 사례가 새로 생김(unknown_abstain_partial, `evidence_records=[]`)** — `event`가 필수 필드라 `verification=UNCERTAIN`일 때 아예 만들 수 없음을 이 fixture가 직접 증명한다 |
| `EvidenceNeeds` | ✅ happy(items=[]) | N/A | — | — | ✅ PLATE_REREAD 요청(optional=false, plate_reread) | ❌ **"사건 유형 자체 미확정" 상황을 표현 못 함(신규 Gap, §3.1-4)** — v1 kind가 `OVERLAY_TIME_OCR`/`PLATE_REREAD`뿐이고 기존 `EvidenceRecord`를 `basis_record_ref`로 요구하므로 구조적으로 표현 불가 |
| `RequirementReport` | ✅ happy(PASS×2) | N/A | ✅ overall=UNKNOWN(plate_reread) | — | ✅ overall=WARN(correction_rerun v1) | ✅ supersede · ❌ 완전 미생성 사례(unknown_abstain_partial, `requirement_reports=[]` — evidence_record_ref 기준 자체가 없음) |
| `ReportPackage` | ✅ happy | N/A | ✅ 미생성(overall≠PASS/WARN인 시나리오는 `report_packages=[]`) | — | — | — |
| `JobRecord` | ✅ happy | ✅ empty(1건만 발주) | — | — | ✅ force_rerun=true(재판독, plate_reread) | — |
| `CaseView` | ✅ happy(stage=READY) | ✅ empty(stage=CANDIDATE_REVIEW) | ✅ plate_display.info_state=INFO_UNKNOWN(plate_reread) | — | ✅ EVIDENCE_REVIEW + running_jobs(plate_reread) | ✅ notices(WARN/INFO) · ✅ 처리중(SEARCHING + progress RUNNING/PENDING + running_jobs RUNNING) · ✅ `user_reviewed=true` · ✅ 정정 전/후 스냅샷 · ✅ `evidence=null` + `blocking=true` notice(unknown_abstain_partial, 신규) · ❌ `INTAKE`·`INFO_AI_ESTIMATED` 미커버 |
| `JobExecution` | ✅ happy(SUCCEEDED) | ✅ empty | — | — | ✅ QUEUED(재판독 대기, plate_reread) | ❌ **FAILED 신규 미커버** — `ReadoutRun`과 동일한 이유(P0-4 재정의로 유일한 FAILED 예시가 없어짐) |
| `UsageRecord` | ✅ happy | ✅ empty | — | — | — | ✅ token_usage=null(로컬 OCR provider) |

**커버리지 갭(정직하게 미커버로 남긴 것)**: `SpanResolution`의 `PARTIAL`/`failure≠null` 케이스, `DeletionReport` 전체, `ReadoutRun.outcome=PARTIAL`, **`ReadoutRun.outcome=FAILED`/`JobExecution.status=FAILED`(신규, 2026-09-09 P0-4 재정의의 부산물)**, `TimeResolution.status=UNKNOWN`(시각을 전혀 알 수 없는 경우), `RequirementReport.overall=BLOCK`, `info_state=INFO_AI_ESTIMATED`, GPS/좌표 Observation, `JobExecution.STALE`/재시도, `AnalysisScope`의 `TIMELINE_RELATIVE`와 `timeline_status=USABLE_RELATIVE_ONLY`. (`VisualEvidence.verification`의 `UNCERTAIN`은 2026-09-09 시나리오 분리로 `unknown_abstain_partial`이 커버하게 되어 이 목록에서 제외했다 — `NOT_OBSERVED`는 여전히 미커버.) 5개 시나리오 안에 억지로 욱여넣기보다 갭으로 남기고 기록하는 편이 "절대 조용히 결정하지 않는다" 원칙에 맞다고 판단했다. 이 갭들을 메울 신규 시나리오 후보는 `05_mock_deep_review_report.md` §10에 근거와 함께 정리돼 있다.

## 2. Scenario × Contract Coverage

| Scenario | recording 계약군 | search 계약군 | readout 계약군 | evidence 계약군 | case/common 계약군 |
| --- | --- | --- | --- | --- | --- |
| `scenario_happy_001` | ✅ 전체 | ✅ 전체 | ✅ 전체 | ✅ 전체 | ✅ 전체 |
| `scenario_empty_001` | ✅ 최소 구성(SourceAsset·MediaStream·RecordingTimeline·TimeSourceCandidate) | ✅ AnalysisScope/AnalysisRun | — | — | ✅ JobRecord/JobExecution/UsageRecord/CaseView |
| `scenario_unknown_abstain_partial_001` | ✅ (충돌 시각 포함) | ✅ (`verification=UNCERTAIN`) | ✅ (overlay NOT_APPLICABLE) | ✅ (완전 미생성 — 신규 Contract Gap 증거) | ✅ (`evidence=null` + blocking notice) |
| `scenario_plate_reread_001` | ✅ | ✅ (`verification=OBSERVED`) | ✅ (plate abstain) | ✅ (UNKNOWN + Needs) | ✅ (자동 재판독 발주 포함) |
| `scenario_correction_rerun_001` | ✅ | ✅ | ✅ (overlay NOT_APPLICABLE — 실행됨, 화면에 시각 없음) | ✅ (supersede chain) | ✅ |

## 3. 발견한 문제

### 3.1 Contract 충돌

서로 다른 두 Final Contract가 같은 대상에 대해 값을 부정하는 치명적 충돌은 없다. 다만 아래 1건은 두 Final Contract의 개별 규칙은 각각 옳은데, 그 둘을 동시에 만족하는 "AI가 사건 유형 자체를 확정하지 못한 경우"를 표현할 방법이 없다는 **표현력 gap**이다.

4. **`EvidenceNeeds`(v1)가 "AI가 사건 유형 자체를 확정하지 못했다"는 상황을 표현하지 못한다.** (2026-09-09 발견, case Owner 유소연 · 팀 리뷰 이슈 #19 김준영 제안으로 시나리오 분리하던 중 확인)
   - `contract-evidence-record-needs.md` §3에서 `EvidenceRecord.event`(`visual_event_type`/`safety_report_type`/`violation_expression` 3개 `EvidenceValue<T>`)는 **필수(non-optional)** 최상위 키이고, 각 `EvidenceValue<T>.value`도 non-nullable이다. 즉 `VisualEvidence.verification=UNCERTAIN`(`visual_event_type=null`)인 경우 `EvidenceRecord` 자체를 만들 수 없다 — `occurred_at`/`vehicle_number`/`location`처럼 필드 단위로 값을 비워둘 방법이 없다.
   - 그런데 `contract-evidence-record-needs.md` §7-8은 `EvidenceNeeds`(v1) kind를 `OVERLAY_TIME_OCR | PLATE_REREAD` 둘로 닫아뒀고, "v1은 confirmed Evidence를 보강하기 위한 추가 관찰/판독 작업에만 사용"한다고 스코프를 제한한다 — `basis_record_ref`로 **이미 존재하는** `EvidenceRecord`를 요구한다.
   - 두 규칙을 겹쳐보면: 사건 유형이 불확실하면 `EvidenceRecord`가 없고, `EvidenceRecord`가 없으면 `EvidenceNeeds`를 발행할 근거(`basis_record_ref`)도 없다. `RequirementReport`도 `basis.evidence_record_ref`가 필수라 마찬가지로 생성될 수 없다. 결과적으로 "사용자에게 사건 유형 확인을 부탁해야 하는 경우" 자체를 표현하는 계약상 통로가 **없다**.
   - `scenario_unknown_abstain_partial_001`(2026-09-09 재설계)에서 이 gap을 그대로 fixture화했다 — `evidence_records=[]`·`evidence_needs=[]`·`requirement_reports=[]`, `CaseView.evidence=null`·`requirements_evidence=null`이며, 등록되지 않은 임시 notice 코드(`evidence.visual_event_unconfirmed`, WARN·`blocking=true`)로만 "사용자 개입 필요"를 표시했다. **이 notice 코드는 계약에 등록된 값이 아니라 gap을 눈에 보이게 남기기 위한 placeholder다.**
   - **case Owner 단독으로 해소하지 않았다.** 새 `EvidenceNeeds` kind(예: `EVENT_TYPE_CONFIRM`) 신설이나 `EvidenceRecord.event`를 선택적 필드로 완화하는 것 모두 `evidence`(김준영) 소유 Final Contract를 바꾸는 결정이라 case Owner 권한 밖이다. `evidence`/PM 확인이 필요하다.

### 3.2 불명확한 Contract

1. **`TimeResolution.resolved.verification`(`AGREED`/`VERIFIED`/`UNVERIFIED`)와 `computation.mode=USER_OVERRIDE`의 대응 관계 미명시.** §4 조건표는 `status=OK`를 "검증된 Video Overlay 또는 명시적 사용자 확정"에 준다고만 하고, 사용자 확정일 때 `verification`이 셋 중 무엇인지 명시하지 않는다. `scenario_correction_rerun_001`에서는 `AGREED`("사용자가 동의/확정")로 해석해 사용했다. Owner(`evidence`, 김준영) 확인이 필요하다.
2. **한 번도 AI를 거치지 않은 순수 사용자 입력 값의 `EvidenceValue.source.observability`/`user_corrected` 판정 기준 미명시.** `EvidenceRecord.location.user_hint`/`search_keyword`처럼 처음부터 사용자가 직접 입력한 값에 대해, `observability=OBSERVED`로 볼지, `user_corrected`를 어떻게 셀지(교정된 적이 없으므로 `false`로 뒀다) 계약이 정하지 않는다. `scenario_happy_001`에서 `observability=OBSERVED`·`user_corrected=false`로 해석해 사용했다.
3. ~~`CaseView.evidence.review_needed`(object-level)의 파생 규칙 미명시.~~ **→ 종결(2026-09-09, case Owner 유소연).** 여섯 개 `*_display.needs_review`(`case_type_display`·`report_type_display`·`violation_display`·`plate_display`·`event_time_display`·`location_display`)의 OR 집계로 확정했다. `reason_code`는 원인이 하나면 해당 필드 코드, 둘 이상이면 `evidence.multiple_fields_need_review`. `contract-job-record-case-view.md` B절 §6·§7에 등재했고, 4개 시나리오 fixture 전부 이 규칙과 일치함을 재확인했다(`scenario_unknown_abstain_partial_001`·`scenario_correction_rerun_001`에서 `true`).
4. **`EvidenceRecord.event.safety_report_type`의 실제 값 공간(안전신문고 신고유형 enum/코드)이 어느 Final Contract에도 등재돼 있지 않다.** `SafetyReportType`이라는 타입 이름만 있고 값 목록 출처가 없다. Mock은 `UNSAFE_LANE_CHANGE`/`UNSAFE_SIGNAL_VIOLATION`/`UNSAFE_HELMET_NON_USE` 형태로 임시 코드를 붙였다 — **이 값들은 등록된 enum이 아니라 Mock 편의 placeholder이며, 실제 값 공간이 확정되면 반드시 교체해야 한다.**

### 3.3 Architecture 확인 필요

1. ~~`JobRecord.kind`에 Report Video export / `purge_case()` 발주용 값이 없다.~~ **→ 종결(2026-09-09, case Owner 유소연).** `FINE_VERIFY`(Fine/시각 검증 발주 — P0-3과 별개로 함께 결정)와 `REPORT_VIDEO_EXPORT`(Report Video export 발주)를 등재했다. `purge_case()`는 `contract-analysis-source-derived.md` §8이 `purge_case(case_id) -> DeletionReport` 직접 호출로 이미 정의했고 `DeletionReport`에 `job_id`가 없으므로, **`JobRecord`/`JobExecution` 비동기 흐름 밖의 관리 동작**으로 확정하고 별도 `kind`를 만들지 않기로 했다. `contract-job-record-case-view.md` A절 §7·§12·§13에 반영했다. `scenario_happy_001`의 `da_h001_report_video` fixture 자체(값)는 변경하지 않았다 — 이 항목은 발주 kind 이름 확정이지, Report Video export 흐름 자체를 이번에 새로 fixture화하는 것은 아니다.
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

**조건부 가능.** 이유: §1의 커버리지 갭(`SpanResolution` 부분실패, `DeletionReport` COMPLETE/FAILED, `ReadoutRun.PARTIAL`, `ReadoutRun.outcome=FAILED`/`JobExecution.status=FAILED` 신규, `TimeResolution.UNKNOWN`)과 §3.1의 신규 Contract Gap(`EvidenceNeeds`가 "사건 유형 자체 미확정"을 표현 못 함) 1건, §3.2~§3.4의 5건은 통합을 막는 치명적 결함이 아니라 "지금 상태를 알고 시작하라"는 조건이다. 5개 시나리오·36개 실제 JSON(모듈 fixture 28 + scenario manifest 5 + manifest.json 1 + eval 2)·검증 스크립트 통과(0 오류)로 각 모듈이 병렬 개발·1차 통합을 시작하기에 충분한 골격이 갖춰졌다.
