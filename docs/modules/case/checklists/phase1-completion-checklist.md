# `case` 1차 완료 체크리스트 — Workflow / Orchestration (Owner: 유소연)

> **작성일 2026-09-13 · 작성 담당 유소연(`case`) · 문서 성격: 구현 설계 문서 아님.**
> 이 문서는 `case` 내부를 어떻게 짤지 정하지 않는다. **공용 Mock Pack(`data/mock/`, `docs/mock/01~05`)과 확정된 Final Data Contract(`docs/architecture/contracts/*.md`)를 기준으로, 1차 Mock E2E 통합(로드맵 ④단계) 전에 `case`가 "Merge해도 되는 상태"인지 스스로 확인하는 체크리스트다.**
> 근거: `docs/management/ownership.md`(R&R) §3 유소연 절 · `docs/architecture/module-architecture.md` v4 §4-모듈5 · `docs/mock/01_mock_dataset_overview.md` §3·§8 · `docs/mock/02_mock_scenario_catalog.md` · `docs/mock/04_mock_validation_report.md`.
> **아직 `case` 구현 코드는 없다**(`src/daesingo/case/README.md`: "아직 코드가 없다"). 이 문서는 그 코드를 쓰기 시작할 때 그대로 개발 TODO/Merge 기준으로 쓰라고 만든 것이다 — 지금 시점 체크 항목은 전부 "무엇을 만들어야 완료로 인정하는가"를 정의한 것이지, "이미 됐다"는 보고가 아니다.

---

## 담당 범위

| 항목 | 내용 |
| --- | --- |
| Owner | 유소연 |
| 주 담당 모듈 | `case` — Workflow / Orchestration, 유일한 지휘자(`module-architecture.md` §4-모듈5 ①) |
| 부 담당 | E2E 통합(`ownership.md` §1-1) — 모듈이 아니라 **역할**이다. 5개 모듈 계약이 실제로 맞물리는지 확인하는 책임이 `case`에 있다는 뜻이지, `case` 코드 범위가 넓어진다는 뜻이 아니다(§4-모듈5 ⑦ "알면 안 되는 것" 그대로 유지). |
| 운영 역할(모듈 경계 밖) | Tool Trajectory 통과 판정(C-3) · 학습/평가 데이터 재사용 정책(C-4) · Timeout/Long-running Job Fallback(A-1) — `ownership.md` §1-2 |
| Producer 계약 (내가 만든다) | `JobRecord`(#11) · `CaseView`(#12) · `CorrectionRecord`(#15) · `AnalysisScope`(#4, **case 단독 Producer** — search·eval이 그대로 소비) |
| Consumer 계약 (내가 읽는다, direct) | `AnalysisRun`/`CandidateEvent`(#4, search) · `PlateReadout`/`OverlayTimeReadout`(#6, readout) · `ReadoutRun`(#7, readout) · `TimeResolution`(#8, evidence) · `EvidenceRecord`/`EvidenceNeeds`(#9, evidence) · `RequirementReport`/`ReportPackage`(#10, evidence) · `JobExecution`(#13, common/runtime) · `UsageRecord`(#14, common/runtime) |
| Consumer 계약 (projection만, 직접 노출 안 함) | `SourceAsset`/`MediaStream`/`FrameRef`/`AssetFacts`(#1, recording) · `RecordingTimeline`/`AssetSpan`/`SpanResolution`/`TimeSourceCandidate`(#2, recording) — `CaseView`가 opaque ref·안전 projection으로만 감싸 내보낸다 |
| 절대 만지지 않는 것 | 프롬프트 내용 / OCR 파라미터 / 영상 코덱 / **신고 요건 계산(절대)** / **시각 출처 우선순위(절대)** / 증거 값을 복사해 들고 있기 / Worker lease·heartbeat 구현 (`ownership.md` §3 유소연 절 ⑦) |

**⚠ 담당 범위 확인 필요 (모호한 지점, 팀 확인 전까지 보수적으로 해석):**

1. "부 담당: E2E 통합"이 실제로 `case` PR에 무엇을 요구하는지(다른 5개 모듈 fixture까지 `case` 담당자가 검증해야 하는가, 아니면 각 모듈 fixture가 존재한다는 전제 위에서 접합만 확인하면 되는가) `ownership.md`가 절차를 명시하지 않는다. 이 문서는 후자로 해석한다 — §9 참고.

> **2026-09-13 정정.** `AnalysisScope`(#4) Producer 표기 불일치는 팀 확인 결과 종결됐다 — `AnalysisScope`는 **case 단독 소유(Owner)**이고 search·eval은 그 스키마를 그대로 받아 쓰는 Consumer다(공동 Producer 아님). ERD 초안(`erd-draft.md` §5.1)도 "생산자 case, eval 독립 사용 가능 / 유소연"으로 동일하게 확정했다. 위 담당 범위 표를 이 기준으로 정정했다.
>
> **2026-09-13 정정.** ERD 리뷰 ② 항목(recording 자산에 `case_id` 결합이 없던 gap)도 recording Owner(정철원)의 설계 결정으로 해소됐다 — recording 내부 `case_asset_links` 테이블(`case_id`·`asset_kind`·`asset_ref` 복합키)로 관리 자산의 Case 소속을 추적하고, MVP는 자산 1건당 Case 1개 소속만 허용한다(`erd-draft.md` §4.1). 공개 Contract에 `case_id`를 추가하는 방식이 아니라 recording 내부 등록 테이블 방식으로 해결했다 — 아래 §8·§9·§10에 반영.

---

## 1. 회의에서 먼저 볼 핵심

- `case`는 **유일한 지휘자**다 — 다섯 모듈(recording·search·readout·evidence·web) 전부의 계약을 동시에 안다는 전제로 일한다(`ownership.md` §3 ②). 그래서 이 체크리스트의 절반은 "내 코드"가 아니라 "남의 계약을 내가 맞게 읽고 있는가"다.
- v4의 핵심 분리: **발주 의도(`JobRecord`)는 `case` 소유, 실행 lifecycle(`JobExecution`)은 `common/runtime` 소유**(구현은 recording 담당). `case`는 Worker를 만들지 않는다(`module-architecture.md` §4-모듈5 ④).
- `CaseView`가 `web`의 **유일한 read dependency**다(§4-모듈6 ③). `case`가 잘못 만들면 `web` 전체가 막힌다 — 접합부 리스크가 가장 큰 계약이다.
- 이번 라운드(2026-09-13)에 ERD 리뷰로 `case` 소유 결정 2건이 막 확정됐다: **`selection_rev`는 `case` 내부 단일 현재값으로만 저장**(별도 이력 테이블 없음, `docs/modules/case/decisions/case-selection-revision-persistence.md`), **재개("이어서 찾기")도 새 `job_id`로 발주**(`docs/modules/case/decisions/job-resume-identity-policy.md`). 둘 다 아직 실제 구현/fixture는 없다 — 이 체크리스트의 §10에 반영.
- (2026-09-13 추가) ERD 리뷰에서 열려 있던 case 쪽 질문 2건도 이번에 전부 해소됐다 — `AnalysisScope`는 공동이 아니라 **case 단독 Producer**로 확정됐고, recording 자산-Case 결합도 recording의 `case_asset_links` 내부 테이블로 해결됐다(`erd-draft.md` 2026-09-13 갱신, §4.1). 남은 건 case가 그 등록 경계를 호출하는 방식뿐이다(§10).

---

## 2. 1차 완료 정의

**1차 완료 = "Mock Pack이 이미 증명한 상태 기계·Contract 매핑을 실제 `case` 코드가 그대로 재현하고, `CaseView`를 통해 `web`에 안전하게 넘길 수 있는 상태."**

1차에서 요구하지 않는 것(§11에서 다시 명시):
- 실제 AI/OCR/Search 성능 — Mock Pack 자체의 목적이 아니다(`01_mock_dataset_overview.md` §1).
- Worker lease/heartbeat 등 실행 lifecycle 구현 — `common/runtime` 담당.
- 신고 요건 계산 로직, 시각 출처 우선순위 로직 — `evidence` 담당, `case`는 결과만 read-through.
- `selection_rev` 이력 테이블, "이어서 찾기" 실제 fixture — 이번 ERD 결정으로 방향은 확정됐지만 §10에 "통합 대기"로 남는다.

1차에서 요구하는 것:
1. `CaseView` 5-state 상태 기계(`INTAKE → SEARCHING → CANDIDATE_REVIEW → EVIDENCE_REVIEW → READY`, 역행 포함)가 Mock Pack의 7개 시나리오가 보여주는 전이와 **모순 없이** 동작한다.
2. `JobRecord` 발주 규칙(신규 Intent=새 `job_id`, 자동 인프라 재시도만 같은 `job_id`+`attempt`)이 `contract-job-execution.md`/`contract-job-record-case-view.md`와 이번 ERD 결정 내용대로 구현된다.
3. `CaseView` projection이 evidence/readout/recording 값을 **복사해서 소유하지 않고** 원본 계약을 안전하게 가공해 내보낸다(§4-모듈5 ⑥).
4. `EvidenceNeeds → Job Intent` 변환, stale result 적용 여부 판단이 최소 한 개 실동작 경로로 존재한다(`scenario_plate_reread_001` 재현).

---

## 3. 구현 체크리스트

> 8개 축(A~H) 중 `case`에 실제로 해당하는 것만 남긴다. 각 항목은 "만들었다/아니다"가 아니라 **"이게 Merge 전에 끝나야 완료로 친다"**는 정의다.

### A. Input

- [ ] 사용자 자연어 단서(hints: time/vehicle/situation/location) 구조화 입력을 받아 `CaseView.hints`로 반영하는 경로
- [ ] `AnalysisScope`(case 단독 Producer) 초안 입력 — 탐색 요청의 비식별 파라미터, search·eval 소비 스키마 고정
- [ ] 사용자 명령 API(후보 선택, 정정 제출, 재개/재시도 요청)의 입력 스키마

### B. Core Flow

- [ ] 5-state 상태 기계 전이 규칙 구현 — 전진 전이 + 뒤 단계에서 앞 단계로 돌아가는 역행 전이(`TIME_HINT_EDIT`, major `TIMELINE_REBASE`, candidate 변경)
- [ ] Candidate selection — 사용자가 고른 사건은 `case` 소유(`ownership.md` §6), evidence는 참조만 하고 복사해 갖지 않음
- [ ] `JobRecord`(Job Intent) 생성 — `kind`별(예: `COARSE_SEARCH`, `PLATE_READ`, `OVERLAY_TIME_READ`, `REPORT_VIDEO_EXPORT`) 발주 규칙
- [ ] rerun_policy — `RETRY_PLATE_READ`/`RETRY_SEARCH`/`RESUME_SEARCH`(신규, 이번 ERD 결정)는 새 `job_id`, 자동 인프라 재시도(`STALE`)만 같은 `job_id`+`attempt` 증가
- [ ] `EvidenceNeeds.items` → Job Intent 매핑 (`PLATE_REREAD` 자동 발주, `force_rerun=true`)
- [ ] stale result 적용 여부 판단 — 오래된 `case_rev`/`timeline_revision` 기준 결과를 domain state에 반영할지 결정

### C. Output Contract

- [ ] `CaseView` 조립 — `stage`/`progress`/`hints`/`candidates`/`evidence`/`requirements_evidence`/`requirements_package`/`package`/`running_jobs`/`notices` 전 필드
- [ ] `JobRecord` append-only 기록 — 발주 의도만 담고 실행 상태는 담지 않음
- [ ] `CorrectionRecord` 생성 — `kind`/`target_field`/`previous_value`/`new_value`/`supersedes_ref`/`selection_rev` 스냅샷
- [ ] `USER_REVIEWED` 상태 — `CaseView.stage`가 아니라 `case_view.user_reviewed: boolean`으로 별도 관리(`ownership.md` §7-③ 종결 사항)

### D. Failure / Partial

- [ ] `JobExecution` STALE→재시도→FAILED 체인을 읽어 `CaseView.progress[].state`에 반영(`RUNNING`→`FAILED`, `scenario_infra_failure_001`)
- [ ] `CANCELLED→PARTIAL` 흡수 규칙(`case-view/v1.3` §7/§13, 이슈 #33 A-2) — 새 enum 값 추가 없이 `progress[plate_read].state=PARTIAL`로 처리
- [ ] blocking(`severity=ERROR`,`blocking=true`) vs non-blocking(`severity=INFO`,`blocking=false`) notice 구분 — `readout.plate_read_failed`(ERROR) vs `case.plate_read_cancelled`/`readout.overlay_ocr_failed`(INFO)
- [ ] `AnalysisRun.outcome=SUCCEEDED`+`candidates=[]`(빈 배열)과 실패를 구분해서 `CANDIDATE_REVIEW`에 머무는 경로(`scenario_empty_001`)

### E. State / Lifecycle

- [ ] `case_rev` 증가 규칙 — 요청 시점 케이스 리비전
- [ ] `selection_rev` 내부 저장 — **단일 현재값만, 별도 이력 테이블 없음**(`docs/modules/case/decisions/case-selection-revision-persistence.md`, 2026-09-13 결정). `CorrectionRecord`/`EvidenceRecord` 생성 시점에 스냅샷으로 굳혀 넘기고 `CaseView`로는 노출하지 않음
- [ ] `candidates[].timeline_revision`/`stale_revision`/`stale_revision_label_key` — timeline rebase 후 「과거 revision 기준」 표시(`scenario_relative_rebase_001`, `docs/modules/case/decisions/candidate-stale-revision-display.md`)

### F. Integration (접합부)

- [ ] `web`(신유민)이 `CaseView` 하나만으로 UI를 그릴 수 있는지 — read dependency 단일 계약 원칙 검증
- [ ] `common/runtime`(김준영, 구현 정철원)의 `JobExecution`을 `case`가 어떻게 poll/구독하는지 — 이 부분 구현은 `case` 담당이 아니라 소비 방식만 정의
- [ ] `evidence`(김준영)의 `EvidenceNeeds` → `case`의 Job Intent 번역 규칙(§11-4)
- [ ] 자산 생성/재사용 시 `case_id`를 recording의 `case_asset_links` 등록 경계로 전달하는 호출 방식 확정 — 스키마는 recording이 이미 결정(`erd-draft.md` §4.1), `purge_case()` 삭제 범위가 이 연결에 의존

### G. Test / Evaluation

- [ ] Tool Trajectory 통과 판정(C-3) 규칙의 최소 테스트 케이스
- [ ] `export_learning_log()` — 익명화 규칙 3줄(번호판 문자열 제거/정확 좌표 제거/원본 참조는 로컬 케이스 ID만, `correction-log-reuse.md`) 준수 여부 테스트
- [ ] eval이 소비하는 `case` 산출물(`JobRecord`/`CaseView` 간접)이 `data/mock/expected/*.expected.json`의 참조 방식과 충돌하지 않는지

### H. Operational

- [ ] Timeout / Long-running Job Fallback 정책(A-1) 최소 구현 — `docs/modules/case/decisions/timeout-fallback.md` 기준
- [ ] `purge_case(case_id) -> DeletionReport` 발주 경로 — recording의 `case_asset_links`(§9 접합부 참고, `erd-draft.md` §4.1)가 이 호출의 삭제 대상 조회 근거가 된다

---

## 5. Contract별 완료 조건

| Contract | 방향 | 완료 조건 |
| --- | --- | --- |
| `JobRecord`(#11) | Producer | `kind`별 발주 규칙 전부 구현, append-only 보장, `force_rerun` 플래그가 자동재시도(`false`)와 사용자 재요청(`true`)을 구분해서 세팅됨. 재개(`RESUME_SEARCH`)도 새 `job_id` 발주(2026-09-13 결정) 반영 |
| `CaseView`(#12) | Producer | `case-view/v1.3` 전 필드 채움, `web`이 추론 없이 「정상/후보0개/low confidence/GPS 없음/Timestamp conflict/Plate abstain/Timeout·partial」을 구분할 수 있음(`module-architecture.md` §4-모듈5 ⑥), evidence 값을 원본 그대로 노출하지 않고 안전 projection만 내보냄 |
| `CorrectionRecord`(#15) | Producer | `kind:EVENT_TIME_MANUAL` 등 스키마 준수, `selection_rev` 스냅샷이 "그 정정이 일어난 candidate 선택 context"를 정확히 반영(수정 횟수 카운터 아님 — 이슈 #39 Required-3 버그 패턴 재발 방지), `correction-record/v1.1` Final 스키마 그대로 |
| `AnalysisScope`(#4) | Producer(단독) | case가 스키마를 단독 확정해 발행하고 search·eval이 그대로 소비(2026-09-13 정정 — 공동 Producer 아님), 비식별 규칙 준수, `TIMELINE_RELATIVE`/`TIMELINE_ABSOLUTE` 두 `time_ranges[].kind` 모두 발주 가능 |
| `AnalysisRun`/`CandidateEvent`(#4) | Consumer(direct) | 빈 배열(`candidates=[]`)과 실패를 `case`가 구분해서 처리, `span.timeline_revision` 보존값을 그대로 읽어 `CaseView`에 반영 |
| `PlateReadout`/`OverlayTimeReadout`(#6) | Consumer(direct) | `abstained=true`/`NOT_APPLICABLE`/`UNKNOWN` 세 상태를 `case`가 구분해서 `progress`/`notices`에 반영, 원본 값을 복사 보관하지 않음 |
| `ReadoutRun`(#7) | Consumer | `outcome=FAILED`/`SUCCEEDED` 및 STALE 재시도 attempt 체인을 읽어 `running_jobs`/`progress` 갱신 |
| `TimeResolution`(#8) | Consumer(direct) | `USER_OVERRIDE`/`supersedes_ref` 체인을 읽어 `CaseView.evidence.event_time_display` 갱신, 정정 전후 `candidates[].at`이 바뀌지 않아야 함(이슈 #39 교훈) |
| `EvidenceRecord`/`EvidenceNeeds`(#9) | Consumer(direct) | `EvidenceNeeds.items`를 Job Intent로 정확히 매핑, `EvidenceRecord`의 필드 부재(abstain)와 `null`을 구분 |
| `RequirementReport`/`ReportPackage`(#10) | Consumer(direct) | `PASS`/`WARN`/`UNKNOWN`/`BLOCK` 네 등급을 `CaseView.requirements_evidence`/`requirements_package`로 정확히 분리해서 반영(§4-모듈5 ⑥ 인용 계약) |
| `JobExecution`(#13) | Consumer | `QUEUED→RUNNING→SUCCEEDED/FAILED/STALE` 전이를 읽어 `case`가 domain state를 갱신하되 실행 로직 자체는 만들지 않음 |
| `UsageRecord`(#14) | Consumer | 실패/재시도분도 포함해 비용이 조용히 누락되지 않는지 확인(0원 UsageRecord 포함 컨벤션 인지) |
| `SourceAsset`~`AssetFacts`(#1) | Consumer(projection) | opaque ref로만 노출, 파일 경로/코덱 등 원본 세부 노출 금지 |
| `RecordingTimeline`~`TimeSourceCandidate`(#2) | Consumer(projection) | `timeline_revision`/`stale_revision` 파생 필드만 `CaseView`에 노출, `working_anchor` 등 원본 세부는 노출하지 않음 |

---

## 6. 공통 Mock Scenario별 완료 조건

| Scenario | 내 입력 | 내가 해야 할 처리 | 기대 출력 | 완료 기준 |
| --- | --- | --- | --- | --- |
| `scenario_happy_001`(A) | `AnalysisRun`/`VisualEvidence`/`PlateReadout`/`OverlayTimeReadout`/`EvidenceRecord`/`RequirementReport`/`ReportPackage` 전부 정상 | 5-state 전 단계 전진 전이, `REPORT_VIDEO_EXPORT` Job 발주(`case_rev:4`), `package.unconfirmed_fields`/`report_field_states` 계산 | `CaseView`가 `stage=READY`까지 rev 1→4 생성 | `case_views[]` 각 rev의 `progress`가 전부 `DONE`, `package`가 실제 생성됨을 재현 |
| `scenario_empty_001`(B) | `AnalysisRun.outcome=SUCCEEDED`+`candidates=[]` | 빈 배열≠실패 구분, 비차단 INFO notice로 힌트 수정 유도 | `stage=CANDIDATE_REVIEW`에 머무름, `readout`/`evidence`/`ReportPackage` 생성 안 됨 | `AnalysisRun`이 실패로 기록되지 않고, 후속 모듈 Job이 발주되지 않는 경로를 재현 |
| `scenario_unknown_abstain_partial_001`(E·H) | `event.visual_event_type.value=null`, `OverlayTimeReadout.observation.status=NOT_APPLICABLE`, `TimeResolution.conflict.exists=true` | `case_type_display.info_state=INFO_UNKNOWN`, `situation_confirmation` 상태 구조화(`UNKNOWN`), WARN 등급으로도 `READY`까지 진행 | `stage`가 `EVIDENCE_REVIEW`(rev3, WARN)→`READY`(rev4, WARN) | 사건 유형 미확정이 신고 불가가 아니라 WARN+사용자 확인 경로로 이어지는 전체 흐름 재현, `situation_response=USER_UNSURE` 처리 |
| `scenario_plate_reread_001`(C·D·G·I) | `PlateReadout.abstained=true`(`target_association=ASSOCIATED`), `EvidenceNeeds.items=[PLATE_REREAD]` | `force_rerun=true`로 새 Job 자동 발주, 재판독 성공 후 `EvidenceRecord`/`RequirementReport` supersede 반영 | `RequirementReport(EVIDENCE).overall`이 `UNKNOWN`→`PASS`, `stage`는 `EVIDENCE_REVIEW`에 머묾(`READY` 아님 — 별도 gate) | `EVIDENCE_SUFFICIENT=true`이지만 `PACKAGE_READY`는 아닌 상태를 정확히 구분해서 재현 |
| `scenario_correction_rerun_001`(F·I) | 사용자 `CorrectionRecord`(`EVENT_TIME_MANUAL`) 제출 | `TimeResolution`/`EvidenceRecord`/`RequirementReport` v1→v2 supersede, `vehicle_number`는 완전 동일하게 유지, `selection_rev`/`candidates[].at` 불변 유지 | `RequirementReport` `WARN`→`PASS` | 정정이 무관한 값(번호판, candidate 위치)을 리셋하지 않는 것을 재현(이슈 #39 교훈 반영) |
| `scenario_infra_failure_001`(J) | `JobExecution` STALE(attempt1)→FAILED(attempt2, 같은 `job_id`) | `progress[plate_read].state` RUNNING→FAILED, blocking ERROR notice(`readout.plate_read_failed`) 추가, v5 추가분(`CANCELLED→PARTIAL` 흡수, `overlay_ocr_failed`) 반영 | `case_views` rev1(RUNNING)→rev2(FAILED) | STALE 재시도 체인과 완전 실패(결과 객체 부재) 규칙을 정확히 재현, non-blocking INFO notice와 blocking ERROR notice를 구분 |
| `scenario_relative_rebase_001`(K) | `RecordingTimeline.timeline_status=USABLE_RELATIVE_ONLY`, revision 1→2 rebase, `SpanResolution.status=PARTIAL` | `candidates[].timeline_revision` 불변 보존, `stale_revision` false→true 전환, `stale_revision_label_key` 채움 | `case_views[1].candidates[0].stale_revision=true` | rebase 후에도 과거 candidate의 timeline 좌표를 덮어쓰지 않고 "오래된 기준" 표시로만 처리하는 것을 재현 |

---

## 7. Merge 전 셀프 체크 증빙

Merge PR에 아래 중 **case가 실제로 낼 수 있는 것**을 첨부한다(전부 필수는 아니다 — 코드가 없는 지금은 목록만 정의):

- [ ] `data/mock/validate_mock_pack.py` 통과 로그(전체 22개 fixture 참조 무결성) — 이미 존재, Merge 전 재실행 결과 스크린샷/로그
- [ ] `case` 구현 코드에 대한 단위 테스트 결과(상태 기계 전이 표 기반, §3-B) — **[구현 후 작성]**
- [ ] 7개 Mock Scenario를 실제 `case` 코드에 입력했을 때의 `CaseView` 출력 JSON diff(Mock fixture와 일치하는지) — **[구현 후 작성]**
- [ ] `CaseView`를 소비하는 `web` 쪽 화면 캡처(최소 happy path 1개) — 신유민과 접합 확인 후 첨부, **[구현 후 작성]**
- [ ] 익명화 로그 export(`export_learning_log()`) 결과 샘플 — 3줄 규칙 준수 확인 로그, **[구현 후 작성]**
- [ ] 이번 라운드 ERD 결정 2건(`selection_rev` 단일 저장, 재개 시 새 `job_id`) 반영 커밋 diff — `docs/erd-review-case-decisions` 브랜치, 이미 존재

---

## 8. Merge 전 확인 질문

팀 리뷰/회의에서 실제로 물어야 하는 것 (혼자 결정할 수 없는 것만):

1. ~~`AnalysisScope` 공동 Producer 표기 불일치~~ → **해소(2026-09-13)** — case 단독 Producer로 확정.
2. ~~recording 자산에 `case_id`가 없는 gap~~ → **해소(2026-09-13)** — recording이 `case_asset_links` 내부 테이블로 해결(`erd-draft.md` §4.1). 남는 것은 질문이 아니라 §10의 통합 대기 작업 하나(호출 방식 조율)뿐.
3. "이어서 찾기"를 새 `job_id`로 바꾸는 이번 결정이 이미 ERD PR 코멘트로 반영된 최신본인지 재확인(이전에 같은 `job_id`+`attempt`로 잘못 요청했던 것을 정정한 상태).

---

## 9. 접합부 확인

| 상대 모듈 | 접합 계약 | 확인할 것 |
| --- | --- | --- |
| `web`(신유민) | `CaseView` | `web`이 이 계약 하나만으로 화면을 그리는지 — 다른 원본 계약을 직접 참조하지 않는지 |
| `common/runtime`(김준영, 구현 정철원) | `JobExecution`/`UsageRecord` | `case`가 실행 lifecycle을 만들지 않고 상태만 소비하는지 — lease/heartbeat 침범 여부 |
| `evidence`(김준영) | `EvidenceNeeds`→Job Intent 번역 규칙, `JobRecord` row 모델(§11-4) | 번역 규칙이 한쪽에만 있는지(중복 정의 없는지) |
| `search`(서어진) | `AnalysisScope`(case 단독 Producer) | case가 발행한 스키마를 search가 합의 없이 그대로 소비하는지(스키마 변경 시 case가 일방 공지) |
| `recording`(정철원) | `purge_case(case_id) -> DeletionReport`, `case_asset_links`(recording 내부) | 스키마는 해소됨(§4.1) — 남은 것은 자산 생성/재사용 시 `case_id`를 recording 등록 경계에 전달하는 **호출 방식**(공개 함수 서명 변경 아님) 조율 |

---

## 10. 부분 완료/통합 대기 항목

**"실제 미완료"(case가 아직 안 만든 것)와 "통합 대기"(다른 모듈/결정을 기다리는 것)를 구분한다.**

| 항목 | 분류 | 사유 |
| --- | --- | --- |
| `selection_rev` 단일 현재값 저장 실제 구현 | 실제 미완료 | 방향은 결정됐으나(2026-09-13) 코드/fixture 없음 |
| "이어서 찾기" 새 `job_id` 발주 실제 fixture | 실제 미완료 | 방향은 결정됐으나(2026-09-13, `docs/modules/case/decisions/job-resume-identity-policy.md`) 데모 fixture 없음(Should-1, 비차단) |
| case→recording 자산 등록 호출 방식(`case_id` 전달) | 통합 대기 | 스키마(`case_asset_links`)는 recording이 확정(2026-09-13, `erd-draft.md` §4.1) — 남은 것은 case가 자산 생성/재사용 시점에 `case_id`를 recording 등록 경계로 넘기는 구체 호출 방식 조율뿐, 공개 함수 서명 변경 아님 |
| `CorrectionRecord` 2단계(학습 재사용) 동의 체계 | 통합 대기 | `correction-log-reuse.md` §10-3 `[미결 유지]`와 연결, PM(김준영) 승인 필요 |
| Eval Ground Truth(`expected/*.expected.json`) | 통합 대기(타 담당) | `case`는 이 디렉터리를 손대지 않기로 합의(`eval-round2-ground-truth-and-usage.md`), 김대원 담당 |

---

## 11. 1차 완료 제외 범위

- 실제 AI/OCR/Search 모델 성능 검증 — Mock Pack의 목적이 아니다.
- Worker lease/heartbeat/재시도 타이밍 구현 — `common/runtime` 담당.
- 신고 요건 판정 로직, 시각 출처 우선순위 로직 — `evidence` 담당, `case`는 결과만 read-through.
- `selection_rev` 변경 이력 UI/API — 이번 결정으로 애초에 "단일 현재값"이 확정 방향이라 이력 자체가 범위 밖.
- eval Ground Truth 스키마/파일 — `case`가 손대지 않기로 합의된 영역.
- recording 자산-케이스 결합의 **호출 구현**(`case_asset_links` 연동 코드) — 스키마는 recording이 확정했지만(§4.1) 실제 연동은 §10 통합 대기.

---

## 12. Merge 중단 기준

다음 중 하나라도 해당하면 **Merge하지 않는다**:

- `case/`(또는 `src/daesingo/case/`) 코드/문서 안에서 `130MB`·기한 규정 숫자·프롬프트 내용·`VIDEO_OVERLAY` 우선순위 로직이 발견됨 — `case`가 God Module로 부풀고 있다는 신호(`ownership.md` §3 유소연 절 경고 그대로).
- `CaseView`가 evidence/readout/recording의 원본 값을 **복사해서 그대로** 들고 있음(참조가 아니라 값 자체를 소유) — §4-모듈5 ⑥ 위반.
- `case`가 Worker(lease/heartbeat/실행 재시도 타이밍)를 직접 구현함 — v4 원칙 6 위반.
- 자동 인프라 재시도(`STALE`)가 아닌 사용자 재요청에서 같은 `job_id`를 재사용함 — 이번 ERD 결정(2026-09-13) 위반.
- `data/mock/validate_mock_pack.py`가 실패하는 상태로 fixture/코드가 병합됨.
- `EvidenceNeeds`/`RequirementReport` 판정 로직을 `case`가 자체적으로 재구현함(evidence 판정을 `case`가 다시 계산) — 소유 경계 위반.

---

## 13. 검증 명령

**[구현 후 작성]** — 아직 `case` 실행 코드가 없어 실제 명령은 코드 작성 후 채운다. 지금 존재하는 것과 앞으로 필요한 자리만 명시한다.

```bash
# 이미 존재 — Mock Pack 참조 무결성(모든 모듈 공통, case fixture 포함)
python data/mock/validate_mock_pack.py

# [구현 후 작성] — case 상태 기계 단위 테스트
# pytest tests/case/test_state_machine.py

# [구현 후 작성] — 7개 Scenario를 case 코드에 흘려 CaseView 출력을 Mock fixture와 비교
# pytest tests/case/test_scenario_replay.py

# [구현 후 작성] — export_learning_log() 익명화 규칙 테스트
# pytest tests/case/test_learning_log_export.py
```

---

## 14. 회의에서 말할 한 줄 요약

> "`case`는 Mock Pack이 이미 증명한 5-state 상태 기계·`JobRecord` 발주 규칙·`CaseView` projection을 그대로 코드로 옮기는 것이 1차 완료이고, 실행 lifecycle·신고 판정·recording 자산 소유는 내 범위가 아니다 — 이번 ERD 리뷰로 `AnalysisScope` 단독 소유, recording `case_id` 결합 스키마, `selection_rev` 저장, 재개 job_id 정책까지 전부 결정됐고, 남은 건 recording 등록 경계 호출 방식 하나뿐이다."
