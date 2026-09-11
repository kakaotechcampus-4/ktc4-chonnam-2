# Final Data Contract — JobRecord (Job Intent) + CaseView v1

**Status:** `Final — Accepted`

**Accepted:** 최초 수락일 확인 대기 — 동일 계약 회차라는 이유로 추정한 2026-09-04 표기를 철회한다. CALL-1·5의 2026-09-06 답변 범위는 아래에 별도로 유지한다.

**수락 근거:** §11 Consumer Review 반영 요약 — 신유민(web) 「수정요청 → 반영 완료」 · 김대원(eval) 「승인」 · 김준영 「최종 승인」. 본문에 리뷰 종료 기록이 있다. 정확한 최초 수락일·필드별 서명 범위는 확인 대기다. 과거에는 PM이 헤더를 채웠다(`adr/adr-consistency-2026-09.md` C1-13). 유소연 이견 시 되돌린다

**Architecture Contract:** v4 §5-1 ⑪ `CaseView` · ⑫ `JobRecord`

**Contract Version:** `job-record/v1` · `case-view/v1.3`

**Related ADR:** `adr/adr-job-record-case-view.md` · `adr/adr-consistency-2026-09.md` §6 R-1·R-2 · `adr/adr-data-contract-call-closure-2026-09-07.md` §4.1·§4.2·§4.3·§4.9 (v1.2 근거)

> **`case-view/v1.3` 변경 (2026-09-10, 이슈 #31/#33 반영 · case 통합 초안, 신유민·김준영 PR 리뷰 확인 대상).**
> ① `candidates[].situation_confirmation` 값 공간을 `NOT_ASKED | CONFIRMED | REJECTED | UNKNOWN`에서 **`NOT_ASKED | CONFIRMED | CORRECTED | USER_UNSURE`로 정정**한다 — `EvidenceRecord.situation_response`(`evidence-record/v1.3`) 값 공간과 맞춘다. `REJECTED`/`UNKNOWN`은 실제로 쓰인 적 없는 placeholder였다(§7).
> ② `candidates[].situation_confirmation`의 파생 출처를 확정한다 — `EvidenceRecord.situation_response.value`가 있으면 그대로 projection(`CONFIRMED`/`CORRECTED`/`USER_UNSURE`), 없으면 `NOT_ASKED`. `CorrectionRecord`가 Draft라 이 필드가 대신한다던 기존 문구(A절 참고 각주)는 철회한다 — `CorrectionRecord`는 v1.1로 Final이 됐고 이제 두 계약(`EvidenceRecord.situation_response` + `CorrectionRecord{kind=SITUATION_CHANGE}`)이 각자의 책임으로 함께 존재한다(§7).
> ③ `progress[].state=CANCELLED`는 새 값으로 만들지 않고 **기존 `PARTIAL`로 흡수**한다 — `JobExecution.status=CANCELLED`(`job-execution/v1.1`)는 부분 결과를 남길 수 있어도 완결이 아니므로 이미 있는 `PARTIAL` 의미와 같다(§7, `CONTRACT_CONFLICTS.md` 불명확 항목 9 종결). `JobExecution→CaseView` 상태 projection 표에 `CANCELLED→PARTIAL`을 추가한다(§13).
> ④ `evidence.report_type_display`에 `info_state`/`source_label_key`를 추가한다 — `docs/modules/evidence/decisions/safety-report-policy-v1.md`(SafetyReportType registry, ACCEPTED)가 나와 `CONTRACT_CONFLICTS.md` 불명확 항목 4의 잔여 부분이 해소됐다. 파생은 `case_type_display`/`violation_display`와 같은 (1) 규칙을 따른다(§7).
> ⑤ `package.report_field_states`를 신설한다 — `report_fields`(평면 map)와 나란히 **필드별 `{info_state, source_label_key}`**를 제공한다(신유민 PR #28 요청, `CONTRACT_CONFLICTS.md` 불명확 항목 10 종결). `unconfirmed_fields`는 이제 `report_field_states[field].info_state ∈ {INFO_AI_ESTIMATED, INFO_NEEDS_REVIEW, INFO_UNKNOWN}`인 필드명의 파생 목록으로 **정의를 명확히 한다**. **주의 — 파생 로직 자체는 새로 만드는 게 아니지만(§10 불변조건 6과 같은 원칙), `safety_report_type`/`violation_expression`은 이번 v1.3 이전에는 `report_field_states`(및 그 기반인 `report_type_display.info_state`)가 아예 없어 `unconfirmed_fields` 계산에 들어가지 못했다 — 그래서 기존 fixture 중 이 두 필드가 `INFO_AI_ESTIMATED`인 경우 `unconfirmed_fields`에 새로 추가된다(예: `scenario_happy_001`). 이는 규칙 정의를 명확히 한 자연스러운 결과이며 별도 정책 변경이 아니다.** §6·§7·§10에 반영.
> ⑥ `notices[].actions[]` 값 공간을 5종에서 **7종으로 확장**한다 — `EDIT_HINT`·`RETRY_SEARCH`를 추가한다(이슈 #31 W-1, 신유민). `scenario_empty_001`의 `search.no_candidates` notice가 이 두 값을 이미 쓰고 있었는데 값 공간에 등록돼 있지 않아, "미등록 값은 버튼을 렌더하지 않는다"는 기존 규칙대로면 후보 0건 화면에 탈출 버튼이 하나도 뜨지 않는 상태였다 — 단서 수정·재검색이 그 화면의 유일한 경로라 이 gap은 실사용을 막는 결함이었다. §7에 반영.
> ⑦ `progress[]`의 step 집합 규칙을 확정한다(이슈 #31 W-7, 신유민) — §7에 신설 규칙 추가, `scenario_relative_rebase_001`(8단계 전부 PENDING 표시 → 3단계로 축소) 수정. 같은 이슈의 W-5(`scenario_correction_rerun_001`에 `readout.overlay_not_present` notice 누락)·W-6(`scenario_plate_reread_001` rev4가 다음 행동을 가리키는 필드 없이 막다른 화면이던 것)도 함께 수정한다 — `readout.overlay_not_present` notice를 rev2·rev3에 추가하고, `plate_reread_001` rev3·rev4의 `progress[]`에 `package_assembly: PENDING`을 추가하고 rev4에 `case.report_video_not_generated`(INFO, `actions:["GENERATE_REPORT_VIDEO"]`) notice를 추가했다.

> **`CaseView`는 v4에서 부록이 아니라 Core Contract ⑪이다**(v4 §5 머리말 · §4-모듈5 ⑥). 아래 절 제목의 「부록-A / 부록-B」는 ADR 작성 당시 표기이며, 계약의 위상은 Core Contract다.

> **재판독 발주 규칙 등재 (2026-09-08 반영 · 유소연 2026-09-07 결정).** A절 §7에 「`PLATE_REREAD` Need → `kind=PLATE_READ` + `force_rerun=true`(무조건) · 새 `job_id` · 기존 `ReadoutRun` 갱신 없음」을 등재했다. 값 목록·스키마는 바뀌지 않아 `job-record/v1`을 유지한다. 근거 `adr/adr-data-contract-call-closure-2026-09-08.md` §4.1.

> **Fine 발주·Report Video export `kind` 등재 및 `purge_case` 경계 확정 (2026-09-09 · Decider 유소연, Mock Pack 심층 검토 §12 후속).** A절 §7에 `FINE_VERIFY`(Fine/시각 검증 발주)와 `REPORT_VIDEO_EXPORT`(신고용 파생영상 생성 발주)를 등재한다. `purge_case()`는 `contract-analysis-source-derived.md` §8이 이미 `purge_case(case_id) -> DeletionReport` 직접 호출로 정의했고 `DeletionReport`에 `job_id`가 없으므로, **`JobRecord`/`JobExecution` 경계 밖의 관리 동작으로 유지**하고 별도 `kind`를 만들지 않는다. `label_key`는 §12에 `job.fine_verify`·`job.report_video_export`를 추가한다. 값 목록·스키마는 바뀌지 않아 `job-record/v1`을 유지한다(열린 enum 등재).

> **`case-view/v1.2` 변경 (2026-09-07)** — 유소연(`case` Owner) 결정, 김준영(`evidence`)·신유민(`web`) 확인. 근거와 기각안은 `adr/adr-data-contract-call-closure-2026-09-07.md` §4.1(B01)·§4.2(B02)·§4.9(`thumb_ref`)에 있다. A절 `JobRecord`는 `job-record/v1` 그대로이며 §7의 `kind` 값 등재와 §10 불변조건 5만 늘었다(열린 enum·불변조건 추가라 버전 유지).
> ① `info_state` 파생 입력 세 개 확정(`needs_review` 출처 · `occurred_at` 변환 · 위치 대표값) ② `location_display`에 `coord`·`search_keyword` 별도 필드 ③ `requirements`를 `requirements_evidence` / `requirements_package` 두 객체로 분리, report 선택 3단계 ④ web 소비 규칙(`info_state`만 본다) ⑤ `candidates[].thumb_ref`는 `FrameRef`. **B01·B02 Pending은 종결됐다.**

> **`case-view/v1.1` 변경 (2026-09-06)** — 회신 반영 당시 B절만 바뀌었다. ① `stage=READY` 정의 확정 ② `requirements.readiness`를 `RequirementReport.overall` 값 공간으로 축소 ③ `user_reviewed` 신규 ④ 세 값 display에 `info_state`·`source_label_key` 신규 ⑤ 당시 `requirements.scope`는 PM 제안/Owner 확인 대기로 정정했고 v1.2에서 두 객체 분리로 대체됐다.
> `progress[].state` · `notices[].severity` · `running_jobs[].label_key` · `package.*` 타입 · `evidence`의 `case_type_display`/`report_type_display`/`violation_display`/`preview_ref`는 기존 Closure 판본을 보존한 것이다. **네 evidence 필드는 삭제 의도가 없음을 Owner가 확인했다(2026-09-07, W02 잔여 종결)** — 유지한다.

## A. `JobRecord` (Job Intent)

### 1. 계약 목적

case가 발주한 작업(Job Intent) 1건을 append-only로 기록해, 부분 재실행과 캐시(입력 지문 일치 시 재사용)가 이 위에서 동작하게 하는 계약이다. 실행 중 상태(Job Execution)는 본 계약의 범위 밖이며 runtime이 소유하는 별도 계약으로 이관된다(ADR-부록A §6, §13).

### 2. Producer / Consumer

**Producer**: case (유소연) — Job Intent 부분만

**Consumer**: `common/runtime` — 실행(`JobExecution`)이 이 의도를 받는다 · `eval` — 발주/재실행 집계 · `web`(신유민) — `CaseView` 경유 간접 소비

**관련 Owner**: runtime/common — 주요 Owner 김준영, 구현 담당 정철원 (2026-09-04 백엔드 회의 확정)

### 3. 책임 경계

**Producer(case)가 보장하는 것**

- 작업 1건당 하나의 Intent 기록: job_id, case_id, case_rev, kind, input_fingerprint, force_rerun, 발주 시점
- 새 시도/재실행은 새 기록 추가(append-only), 기존 기록 in-place 수정 없음
- `scope_ref`가 존재하면 유효한 AnalysisScope.scope_id를 가리킴

**Consumer(web)가 기대할 수 있는 것**

- CaseView.running_jobs를 통한 간접 조회(job_id/kind/label_key/status)

**이 Contract가 보장하지 않는 것**

- 실행 상태(status/attempt/cost/produced/failure_kind) — 별도 `JobExecution` 계약 범위
- 재시도 성공 보장
- heartbeat/lease/retry/backoff/DB 구조 등 Runtime 내부 구현 세부

### 4. 조사에서 확인된 제약

| 제약 | 근거 |
| --- | --- |
| Job=추가만(append-only) | v1 R&R 표 |
| failure_kind는 모듈 접두어로 구분 | v1 p.20 |
| corrections.kind는 JobRecord.kind와 다른 값 공간 | v1 p.28 |
| Job Intent/Execution 책임 분리가 v4/Ops 문서와 정합 | ADR-부록A 결정1 |

### 5. 확정 Contract 스키마 (JSON) — Job Intent 부분

json

```json
{  "job_id": "string",  "case_id": "string",  "case_rev": "int",  "kind": "string",  "scope_ref": "string | null",  "input_fingerprint": "string",  "force_rerun": "boolean",  "requested_at": "ISO8601"}
```

> status/attempt/cost/produced/failure_kind는 별도 `JobExecution` 계약으로 이관한다. `JobExecution`은 runtime/common이 소유하며 주요 Owner는 김준영, 구현 담당은 정철원이다. 실행 상태 enum은 `QUEUED / RUNNING / SUCCEEDED / FAILED / STALE`로 고정한다.
> 

### 6. 필드 정의

| 필드 | 타입 | 필수 | 의미 | 근거/상태 |
| --- | --- | --- | --- | --- |
| job_id | string | Y | 고유 식별자, 재사용 없음 | 확인됨 |
| case_id / case_rev | string / int | Y | 소속 Case 및 발주 시점 리비전 | 확인됨 |
| kind | string(모듈 접두어 확장형) | Y | 작업 종류 | ADR 결정3, 절충안 유지 |
| scope_ref | string | null | N (신규) | 참조하는 AnalysisScope.scope_id | ADR 결정4, 신유민 요청 반영 |
| input_fingerprint | string | Y | 캐시 판단 지문 | 확인됨 |
| force_rerun | boolean | Y (신규) | true면 fingerprint 동일해도 재실행 | ADR 결정2, A안 확정 |
| requested_at | ISO8601 | Y | 발주 시점 | 확정 — 발주 시점 필드명을 `requested_at`으로 고정 |

### 7. Enum / State / Special Value

- `kind`: 확인된 값 `COARSE_SEARCH`, `PLATE_READ`, `OVERLAY_TIME_READ`(2026-09-07 등재, 유소연), **`FINE_VERIFY`**·**`REPORT_VIDEO_EXPORT`**(2026-09-09 등재, 유소연). 전체 목록은 모듈 접두어 규칙에 따라 계속 등재 (닫힌 enum 아님)
  - `FINE_VERIFY`는 search의 `AnalysisRun.operation=VISUAL_VERIFY` 실행을 발주한다. `COARSE_SEARCH`(↔`AnalysisRun.operation=CANDIDATE_SEARCH`)와 이미 문자열이 다른 선례를 따라, `case`가 쓰는 Coarse/Fine 업무 명칭을 그대로 쓴다(`operation` 값과 1:1 문자열 일치를 요구하지 않는다 — 그 요구는 §7의 `PLATE_READ`/`OVERLAY_TIME_READ`↔`ReadoutRun.operation`에만 명시돼 있다).
  - `REPORT_VIDEO_EXPORT`는 `DerivedAsset`(`derived_role=REPORT_VIDEO`) 생성을 발주한다(`contract-analysis-source-derived.md` §7.3·§7.5). export 실패는 그 계약 §9의 `REPORT_VIDEO_EXPORT_FAILED`(`JobExecution.failure_kind`, SCREAMING_SNAKE 열거값)를 **그대로 옮기지 않는다** — `case`가 B절 §7 「notices[].code 표기」 규칙에 따라 `recording.report_video_export_failed`로 매핑해 `CaseView.notices[].code`에 싣는다(2026-09-10 정정, 이슈 #26 A-⑤. `failure_kind`는 실행 상태를 나타내는 별도 값공간이라 표시용 `notices[].code`와 casing이 다를 수 있다).
  - **`purge_case()`는 `JobRecord`를 통해 발주하지 않는다.** `contract-analysis-source-derived.md` §8이 `purge_case(case_id) -> DeletionReport`를 직접 호출로 정의하고 `DeletionReport`에 `job_id`가 없으므로, Job Intent/Execution 비동기 흐름 밖의 관리 동작으로 취급한다(2026-09-09, 유소연).
  - `PLATE_READ`와 `OVERLAY_TIME_READ`는 **항상 별도 `job_id`로 발주**한다. `ReadoutRun.operation`(`contract-readout-run.md` §6)과는 같은 이름의 값끼리 대응한다 — `PLATE_READ↔PLATE_READ`, `OVERLAY_TIME_READ↔OVERLAY_TIME_READ`. 한쪽에만 값을 추가하지 않는다.
  - `PLATE_REREAD`는 `EvidenceNeeds.kind`의 값이며 `JobRecord.kind` 값이 아니다(값 공간이 다르다 — §4 「corrections.kind는 JobRecord.kind와 다른 값 공간」과 같은 이유).
  - **재판독 발주 규칙 (2026-09-07 확정 · Decider 유소연 · 확인 신유민·김준영).** `EvidenceNeeds.kind=PLATE_REREAD` Need를 발주로 옮길 때 `case`는 **`kind=PLATE_READ`를 유지하고 `force_rerun=true`를 조건 없이 붙인다.** 별도 kind를 만들지 않는다. `PLATE_REREAD` Need는 사건 interval ref를 그대로 제공하므로 입력이 원판독과 같은 것이 기본값이고, fingerprint 구성에 case/kind가 포함된다고 가정할 수 없으므로 조건부 `force_rerun`은 재판독을 조용히 누락시킨다. 재판독은 **새 `job_id`**(새 `JobRecord`)로 발주하며 새 execution이 새 `ReadoutRun` 1건을 만든다 — **기존 `ReadoutRun`을 갱신하지 않는다.** 인프라 재시도(`STALE`)는 다른 층위다: 같은 `job_id` · 새 `execution_id` · `attempt` 증가(`contract-job-execution.md` §9-2). abstain 결과는 계속 `ReadoutRun.outcome=SUCCEEDED`이며(`contract-readout-run.md` §9-5) cache hit 회피는 `outcome`이 아니라 `force_rerun`으로 한다. 원판독/재판독 중 「현재 값」 선택은 B03 결정대로 `case`/`CaseView` projection 소관이다. §9의 `job_61` 예시가 이 형태다. 근거·기각안 `adr/adr-data-contract-call-closure-2026-09-08.md` §4.1.
- `force_rerun`: 기본값 `false`. **동일 `(case_id, kind, input_fingerprint)`**이고 `force_rerun=false`인 요청에 기존 **SUCCEEDED** 결과가 있으면 재사용한다. `FAILED`/`STALE`은 cache hit가 아니다. `force_rerun=true`이면 새 실행이다. 기존 `adr-job-record-case-view.md` A절 §7의 조건을 복원한 것이며 fingerprint에 case/kind가 포함됐다고 추정하지 않는다.

### 8. 정상 예시

json

```json
{  "job_id": "job_51",  "case_id": "case_3",  "case_rev": 4,  "kind": "COARSE_SEARCH",  "scope_ref": "scope_2026_0912_001",  "input_fingerprint": "sha1:...",  "force_rerun": false,  "requested_at": "2026-09-01T18:00:00Z"}
```

### 9. 실패 / 부분성공 / UNKNOWN 예시

Job Intent 자체는 성공/실패 상태를 갖지 않는다(§실행 결과는 Job Execution 계약 소관). 아래는 강제 재실행 케이스:

json

```json
{  "job_id": "job_61",  "case_id": "case_3",  "case_rev": 5,  "kind": "PLATE_READ",  "scope_ref": null,  "input_fingerprint": "sha1:same-as-before",  "force_rerun": true,  "requested_at": "2026-09-02T09:10:00Z"}
```

### 10. 불변조건

1. 동일 job_id는 재사용되지 않는다
2. 캐시 재사용 조건은 A절 §7을 따른다(동일 case_id·kind·input_fingerprint의 성공 결과에 한정).
3. `scope_ref`가 존재하면 유효한 scope_id를 참조한다
4. 실행 상태 필드(status 등)는 본 계약에 포함되지 않는다 — Job Execution 계약 참고
5. **readout 계열 Job 1 execution : `ReadoutRun` 1건 (1:1)** — `case`의 orchestration 불변조건이다(유소연 · 신유민, 2026-09-07). `readout`은 `JobExecution`을 모르므로 readout이 보장하는 것은 「public 함수 호출 1회 = `ReadoutRun` 1건」이고, 1:1은 worker 구현 규칙 「1 execution 안에서 readout public 함수를 정확히 1회 호출한다」(`contract-job-execution.md` §9-9)로 성립한다. `run_id`는 `job_id`처럼 재사용되지 않는 1회성 식별자이나 `execution_id`와 **같은 identity가 아니다**. 근거 `adr/adr-data-contract-call-closure-2026-09-07.md` §4.3    **예외(2026-09-10, 유소연·신유민, 이슈 #26 B-readout-3):** `status=STALE`인 실행은 run이 없을 수 있다 — worker가 readout 호출을 완료하지 못하고 소멸한 경우. `scenario_infra_failure_001`의 attempt 1(STALE, `produced=[]`)이 이 예외의 fixture 근거다.
6. **execution 대표 상태 — 「대표 execution = `attempt` 최댓값」**(2026-09-10, 유소연·신유민, 이슈 #26 B-web-7). 한 `job_id`에 `attempt`가 여럿이면 `CaseView.progress[]`·`running_jobs[]`는 **가장 큰 `attempt`의 `JobExecution.status`**를 그 job의 대표 상태로 투영한다. 재시도 중 이전 attempt가 `STALE`/`FAILED`였다는 사실 자체는 대표 상태에 노출하지 않는다 — attempt 1이 STALE로 판정된 순간에도 `progress[]`는 곧바로 `FAILED`로 깜빡이지 않고, attempt 2가 `QUEUED`/`RUNNING`인 동안 해당 job은 계속 진행 중으로 보인다. 모든 attempt가 소진된 뒤에야(재시도 없음, 마지막 attempt가 terminal 실패) 대표 상태가 `FAILED`로 전환된다. `scenario_infra_failure_001`의 두 스냅샷(`case_rev:1`=RUNNING, `case_rev:2`=최종 attempt 2 FAILED 이후)이 이미 이 규칙과 일치하며 이번에 fixture를 수정하지 않는다.

### 11. Consumer Review 반영 요약

| Consumer | 상태 | 반영 내용 |
| --- | --- | --- |
| 신유민(web) | 수정요청 → 반영 완료 | scope_ref 신규 추가(Q4), kind 표시 보완 요구는 부록-B에서 label_key/fallback으로 확정(Q3) |
| 김대원(eval) | 승인 | 반영 사항 없음 |
| 김준영(evidence/runtime/PM) | 최종 승인 | Job Intent/Execution 분리, force_rerun, JobExecution Owner/status/cache semantics 최종 확정 |

### 12. 후속 구현 범위

- `JobExecution` Producer/Owner: runtime/common, 주요 Owner 김준영, 구현 담당 정철원 — 2026-09-04 백엔드 회의에서 확정
- `JobExecution.status`: `QUEUED / RUNNING / SUCCEEDED / FAILED / STALE`
- heartbeat/lease/retry/backoff/DB 구조는 Runtime 구현 세부이며 본 Job Intent 계약의 closure를 막지 않는다.
- kind 표시용 `label_key`/fallback은 부록-B `CaseView` 계약에서 확정한다. 등재된 `label_key`: `job.plate_read` · `job.overlay_time_read`(2026-09-07 추가) · `job.fine_verify` · `job.report_video_export`(2026-09-09 추가). `COARSE_SEARCH`는 아직 전용 `label_key`가 없어 `job.generic_processing` fallback을 그대로 쓴다(유소연 확인, 우선순위 낮음 — 필요해지면 `job.coarse_search`로 등재). 미등록 kind는 `job.generic_processing` fallback(B절 §12).

---

## B. `CaseView`

### 1. 계약 목적

web이 화면을 그리기 위해 읽는 유일한 통합 상태다. evidence/package는 이제 safe projection으로 제공되며, web은 요건을 재계산하지 않는다(v1 p.28).

### 2. Producer / Consumer

**Producer**: case (유소연)

**Consumer**: web(신유민), (+김대원, 영상 UI)

**관련 Owner**: evidence(김준영) — safe projection의 의미 경계 및 authoritative 값 소유

### 3. 책임 경계

**Producer(case)가 보장하는 것**

- web이 CaseView 하나만 보면 화면을 그릴 수 있음
- evidence/package는 원본 계약을 그대로 통과시키지 않고 case가 재구성한 값만 제공(ADR-부록B 결정1)
- stage는 5개 값으로 닫힌 enum

**Consumer(web)가 기대할 수 있는 것**

- 요건 충족 여부는 case/evidence가 이미 계산해서 제공
- evidence/package의 내부 구현 변경으로부터 격리된 안정적인 표시용 필드

**이 Contract가 보장하지 않는 것**

- web 또는 case가 Evidence/RequirementReport의 authoritative 판단을 재계산하는 것 — 금지
- raw confidence, 내부 provenance, 중간 추론값 등 Evidence 내부 구현 세부의 직접 노출
- heartbeat/lease/retry/backoff 등 Runtime 내부 실행 세부

### 4. 조사에서 확인된 제약

| 제약 | 근거 |
| --- | --- |
| web은 요건을 재계산하지 않는다 | v1 p.28 원문 |
| evidence/package는 safe projection이어야 함 | ADR-부록B 결정1, 김준영 확정 |
| checks[]는 RequirementReport 그대로 | 이전 회차 확정 |

### 5. Contract 스키마 (JSON)

> **B01·B02 종결 (2026-09-07).** `info_state` 파생 입력과 `requirements_*` 선택 규칙은 §7이 소유한다. 근거 `adr/adr-data-contract-call-closure-2026-09-07.md` §4.1·§4.2. 기존 유형/preview 네 필드는 유지로 확인됐다(같은 문서 §4.10).

json

```json
{  "case_id": "string",  "case_rev": "int",  "stage": "INTAKE | SEARCHING | CANDIDATE_REVIEW | EVIDENCE_REVIEW | READY",  "user_reviewed": "boolean",  "manifest_summary": {    "file_count": "int",    "ok_file_count": "int",    "failed_file_count": "int",    "duration_sec": "number",    "range": "[string, string] | null"  },  "hints": { "time": "string|null", "vehicle": "string|null", "situation": "string|null", "location": "string|null" },  "progress": [ { "step": "string", "state": "PENDING | RUNNING | DONE | FAILED | PARTIAL" } ],  "candidates": [    { "candidate_id": "string", "at": "string", "at_provenance": "string", "observed": "string", "thumb_ref": "FrameRef (fr_<opaque-id>) | null", "selected": "boolean", "timeline_revision": "int", "stale_revision": "boolean", "stale_revision_label_key": "string|null", "situation_confirmation": "NOT_ASKED | CONFIRMED | CORRECTED | USER_UNSURE" }  ],  "evidence": {    "record_id": "string",    "case_type_display": { "code": "string|null", "label": "string|null", "needs_review": "boolean", "info_state": "INFO_AI_ESTIMATED | INFO_SOURCE_VERIFIED | INFO_USER_CONFIRMED | INFO_NEEDS_REVIEW | INFO_UNKNOWN", "source_label_key": "string|null" },    "report_type_display": { "code": "string|null", "label": "string|null", "needs_review": "boolean", "info_state": "INFO_AI_ESTIMATED | INFO_SOURCE_VERIFIED | INFO_USER_CONFIRMED | INFO_NEEDS_REVIEW | INFO_UNKNOWN", "source_label_key": "string|null" },    "violation_display": { "code": "string|null", "label": "string|null", "needs_review": "boolean", "info_state": "INFO_AI_ESTIMATED | INFO_SOURCE_VERIFIED | INFO_USER_CONFIRMED | INFO_NEEDS_REVIEW | INFO_UNKNOWN", "source_label_key": "string|null" },    "plate_display": { "value": "string|null", "needs_review": "boolean", "info_state": "INFO_AI_ESTIMATED | INFO_SOURCE_VERIFIED | INFO_USER_CONFIRMED | INFO_NEEDS_REVIEW | INFO_UNKNOWN", "source_label_key": "string|null" },    "event_time_display": { "value": "ISO8601|null", "needs_review": "boolean", "info_state": "INFO_AI_ESTIMATED | INFO_SOURCE_VERIFIED | INFO_USER_CONFIRMED | INFO_NEEDS_REVIEW | INFO_UNKNOWN", "source_label_key": "string|null" },    "location_display": { "value": "string|null", "needs_review": "boolean", "info_state": "INFO_AI_ESTIMATED | INFO_SOURCE_VERIFIED | INFO_USER_CONFIRMED | INFO_NEEDS_REVIEW | INFO_UNKNOWN", "source_label_key": "string|null", "coord": "{ lat: number, lon: number } | null", "search_keyword": "string|null" },    "user_edited": "boolean",    "preview_ref": "string|null",    "review_needed": "boolean",    "reason_code": "string|null"  },  "requirements_evidence": { "readiness": "PASS | WARN | BLOCK | UNKNOWN", "checks": [] },  "requirements_package": { "readiness": "PASS | WARN | BLOCK | UNKNOWN", "checks": [] },  "package": {    "package_ref": "string|null",    "report_fields": "object<string, string|null>",    "report_field_states": "object<string, { info_state: INFO_AI_ESTIMATED|INFO_SOURCE_VERIFIED|INFO_USER_CONFIRMED|INFO_NEEDS_REVIEW|INFO_UNKNOWN, source_label_key: string|null }>",    "unconfirmed_fields": "string[]",    "artifact_ref": "string|null",    "capabilities": "string[]",    "warnings": "string[]"  },  "running_jobs": [ { "job_id": "string", "kind": "string", "label_key": "string", "status": "PENDING | RUNNING" } ],  "notices": [    { "code": "string", "severity": "INFO | WARN | ERROR", "blocking": "boolean", "message_key": "string", "actions": "string[]" }  ]}
```

> `requirements_evidence`·`requirements_package`·`package`·`evidence`는 각각 `null`일 수 있다(조건은 §7·§10). 위 evidence/package는 safe projection 경계를 따른다. case는 Evidence/ReportPackage의 authoritative 값을 재판정하거나 confidence를 자체 threshold로 재해석하지 않고, 확정된 값·검토 필요 여부·사유를 UI 표시 형태로만 변환한다. raw confidence, 내부 provenance, 중간 추론값은 기본 노출하지 않는다. `candidates[].thumb_ref`는 `FrameRef`이며 web은 recording을 직접 호출하지 않는다 — 실제 이미지는 case가 recording lookup을 거쳐 projection한다(`FrameRef` 필드 계약은 `contract-source-asset-media-stream.md` §5·§7, **이미지 전달 형태는 그 계약 §9-6 Pending**, §13).
> 

### 6. 필드 정의

| 필드 | 타입 | 필수 | 의미 | 상태 |
| --- | --- | --- | --- | --- |
| stage | enum(5) | Y | Case 진행 단계. `READY`는 「`PACKAGE_READY` 파생 gate가 성립한 시점」 | **확정** (신유민 Q3 답변 · READY 정의는 유소연 2026-09-06) |
| user_reviewed | boolean | Y | 사용자가 최종 확인을 마쳤는지. v4 §3-6의 `USER_REVIEWED`를 내려보내는 통로이며 `stage`와 **별개 축**이다 | **확정** (유소연 2026-09-06) |
| evidence.*_display.info_state | enum(5) | Y | 값의 정보 상태. 파생 규칙과 입력은 §7이 소유한다 | **확정** (enum 2026-09-06 · 파생 입력 2026-09-07, B01 종결) |
| evidence.*_display.needs_review | boolean | Y | `evidence`가 값과 함께 내려준 검토 필요 여부(`EvidenceValue.needs_review`)를 그대로 옮긴 값. `event_time_display`는 `occurred_at.resolution_status == NEEDS_REVIEW`를 옮긴다. **web은 이 값으로 분기하지 않는다**(§7) | **확정** (유소연·신유민·김준영 2026-09-07) |
| evidence.*_display.source_label_key | string \| null | Y | `EvidenceValue.source.label_key`(사건시각은 `occurred_at.source.label_key`)를 화면 라벨 키로 노출. `location_display`에서는 대표값 `value`의 출처만 뜻한다. web은 이 키로 문구를 고르고 `kind` 문자열을 직접 해석하지 않는다 | **확정** (유소연·신유민 2026-09-06 · 2026-09-07) |
| evidence.location_display.coord | `{lat, lon}` \| null | Y(키) | `EvidenceRecord.location.coord.value`를 대표값과 **별도로** 내려보낸다. 포맷은 web | **확정** (유소연·신유민·김준영 2026-09-07) |
| evidence.location_display.search_keyword | string \| null | Y(키) | `EvidenceRecord.location.search_keyword.value`. 대표값으로 승격하지 않는다 | **확정** (2026-09-07) |
| evidence.review_needed | boolean | Y | 여섯 개 `*_display.needs_review`의 OR 집계(object-level). 파생 규칙 §7 | **확정** (2026-09-09, 유소연) |
| requirements_evidence | object \| null | Y(키) | 현재 basis의 scope=`EVIDENCE` `RequirementReport` projection `{readiness, checks}`. 선택 규칙 §7. 미실행이면 `null` | **확정** (유소연 2026-09-07, B02 종결) |
| requirements_package | object \| null | Y(키) | 현재 basis의 scope=`FINAL_PACKAGE` `RequirementReport` projection `{readiness, checks}`. 미실행·파생물 미생성이면 `null` | **확정** (유소연 2026-09-07, B02 종결) |
| requirements_*.readiness | enum(4) | Y(객체 안) | 해당 `RequirementReport.overall`의 projection. case가 재계산하지 않는다 | **확정** (유소연 2026-09-06) |
| candidates[].thumb_ref | FrameRef \| null | Y(키) | 후보 대표 frame의 `FrameRef`(`fr_<opaque-id>`). 위치를 ID에 인코딩하지 않는다 | **확정** (정철원·유소연·신유민 2026-09-07) |
| candidates[].timeline_revision | int | Y | 이 candidate 생성 시점에 참조한 `RecordingTimeline.revision`(`CandidateEvent.span.timeline_revision` 투영). rebase 이후에도 mutate하지 않는다(B09) | **확정** (유소연, `docs/modules/case/decisions/candidate-stale-revision-display.md`, 이슈 #18 위임 · 이슈 #26 B-web-8로 정식 등재) |
| candidates[].stale_revision | boolean | Y | `timeline_revision`이 현재 `RecordingTimeline.revision`과 다르면 `true`. case가 매 투영 시점에 비교하는 파생값 | **확정** (같은 문서 · 이슈 #26 B-web-8로 정식 등재) |
| candidates[].stale_revision_label_key | string \| null | Y | `stale_revision=true`일 때 「과거 timeline revision 기준」 문구를 고를 표시 키. `stale_revision=false`면 `null`. `*_display.source_label_key`와 같은 원칙 — web은 이 키로 문구를 고르고 `stale_revision` boolean만으로 문구를 직접 만들지 않는다. v1.1 등록값은 `candidate.stale_timeline_revision` 1개(단일 문구, 향후 세분화 시 값만 추가) | **확정(2026-09-10, 유소연, 이슈 #26 B-web-8 후속)** — A-⑤·B-web-8에서 신유민이 지적한 「label_key 없으면 web이 문구를 임의로 만든다」 gap을 닫는다. `docs/modules/case/decisions/candidate-stale-revision-display.md` 갱신 |
| candidates[].situation_confirmation | enum(4) | Y | "아직 미확인"(`NOT_ASKED`)과 "잘 모르겠어요"(`USER_UNSURE`)를 같은 null로 합치지 않기 위한 projection. `EvidenceRecord.situation_response.value`가 있으면 그대로 옮기고(`CONFIRMED`/`CORRECTED`/`USER_UNSURE`), 없으면 `NOT_ASKED`다 | **확정(v1.3, 2026-09-10)** — 값 공간을 `evidence-record/v1.3`의 `situation_response`와 맞춤(이슈 #33). 원래 유소연 결정(`docs/modules/case/decisions/generic-warn-package-and-situation-response.md`, 이슈 #25)의 후속 |
| package.report_field_states | object<string, {info_state, source_label_key}> | Y(키) | `report_fields`와 나란히 필드별 정보 상태를 제공. 매핑표·값 공간은 §7 | **신규(v1.3)** — 신유민 PR #28 요청, `CONTRACT_CONFLICTS.md` 불명확 항목 10 종결 |
| manifest_summary.ok_file_count / failed_file_count / duration_sec | int/int/number | Y | 파일 등록 성공·실패 수, 전체 구간 길이. count/duration은 항상 제공하고 정상 영상이 없으면 range=null | 확정 |
| evidence.* (projection 필드 전반) | object | 선택 | 화면 표시용 evidence 요약 | safe projection 원칙 확정; 세부 필드 합의는 §13 Pending |
| package.* | object | 선택 | 화면 표시용 package 요약 | safe projection 원칙 확정; 세부 필드 합의는 §13 Pending |
| notices[].code/severity/blocking/message_key/actions | string/string/bool/string/array | Y(배열은 빈 배열 허용) | 부분 실패/경고 표시 | 신규, 신유민 요청 반영 |
| progress[].state | string | Y | 단계 상태 | **확정** — `PENDING / RUNNING / DONE / FAILED / PARTIAL`(2026-09-10 추가) |
| progress[].step 범위(2026-09-10, 유소연, `05` §12 유소연-⑦ 종결) | — | — | `progress[]`는 `product/core-user-flow.md` §3-2가 "AI 분석 진행은 별도로 표현한다"고 정한 **AI job 진행상태 전용**이다. 제품 7단계 표시(§4-1) 중 2단계("사건 설명")·3단계("범위 확인")는 AI job이 아니라 **사용자가 입력·확인하는 동기 단계**라 대응하는 `progress[].step` 값이 원래 없어야 맞다 — web은 이 두 단계를 `hints`/`manifest_summary` 등 다른 필드의 존재 여부로 "완료"를 표시하면 되고, 이는 §3-2가 금지하는 "정보 상태와 작업 상태를 같은 표시 체계로 섞는 것"이 아니다(정보 상태가 아니라 사용자 입력 여부를 보는 것). `progress[].step` 8종(`file_intake~package_assembly`)은 제품 4~7단계(사건 찾기~신고자료)만 커버하면 되고, 이는 이미 그렇다 — **누락이 아니라 원래 이렇게 설계된 것으로 확정, 신규 step 추가 불필요** |

### 7. Enum / State / Special Value

| 필드 | 확정 값 | 비고 |
| --- | --- | --- |
| stage | `INTAKE`, `SEARCHING`, `CANDIDATE_REVIEW`, `EVIDENCE_REVIEW`, `READY` | 신유민 Q3 답변 기준 최종 확정. **`READY` = 「`PACKAGE_READY` 파생 gate가 성립한 시점」**(`contract-requirement-report-package.md` §5.2). `EVIDENCE_SUFFICIENT`는 `EVIDENCE_REVIEW` 단계 안의 조건이고 `USER_REVIEWED`는 `user_reviewed` 필드가 갖는다 |
| user_reviewed | `true`, `false` | v4 §3-6 `USER_REVIEWED`. `stage`와 별개 축이며 `stage=READY`가 아니어도 `true`일 수 있다 |
| requirements_evidence / requirements_package | 객체 또는 `null` | scope별 report projection. **선택 규칙(3단계)** — ① `basis.evidence_record_ref`가 현재 `EvidenceRecord.record_ref`와 일치하는 report만 후보 ② `supersedes_ref` 체인의 head ③ 그래도 복수면 `evaluated_at` 최신. 이 규칙은 이 계약이 소유하고 `contract-requirement-report-package.md` §5.2-1은 여기를 가리킨다. `requirements_evidence=null`은 현재 basis의 Evidence 검사 미실행, `requirements_package=null`은 package-scope 검사 미실행 또는 필요한 파생물 미생성 |
| requirements_*.readiness | `PASS`, `WARN`, `BLOCK`, `UNKNOWN` | 해당 `RequirementReport.overall`과 **같은 값 공간**. `4/5` 같은 score 표현을 두지 않는다(`contract-requirement-report-package.md` §4 「단순 readiness score를 Contract에 두지 않는다」) |
| 세 gate의 출처 | — | `EVIDENCE_SUFFICIENT` = `requirements_evidence` 판정 · `PACKAGE_READY` = `requirements_package` 판정(+`package` 존재) · `USER_REVIEWED` = `user_reviewed`. **셋을 하나의 readiness로 합치지 않는다.** 별도 gate 표시값을 두려면 이 셋에서 단순 파생되는 표시값이어야 하고 새 authoritative 상태가 되면 안 된다 |
| evidence.*_display.info_state | `INFO_AI_ESTIMATED`, `INFO_SOURCE_VERIFIED`, `INFO_USER_CONFIRMED`, `INFO_NEEDS_REVIEW`, `INFO_UNKNOWN` | `core-user-flow.md` §3-1의 정보 상태 5종과 1:1. **`Observation.status`와 다른 값 공간이므로 `INFO_` 접두어로 분리한다** — 파생 코드가 두 enum을 동시에 다루는 지점에서 `NEEDS_REVIEW`/`UNKNOWN`이 겹치는 것을 막는다(유소연 2026-09-06) |
| progress[].state | `PENDING`, `RUNNING`, `DONE`, `FAILED`, `PARTIAL` | CaseView UI 상태로 확정. JobExecution 상세 상태와 분리. **`PARTIAL`(2026-09-10, 유소연, `05` §12 유소연-⑧ 부분 종결)**: 제품 정의 6개 작업상태(`core-user-flow.md` §3-2)의 "부분 완료"·**"중단" 둘 다**에 대응한다(v1.3 개정). 해당 단계의 `AnalysisRun.outcome=PARTIAL`(`contract-analysis-run-candidate-event.md` §5)을 그대로 투영하거나, `JobExecution.status=CANCELLED`(`job-execution/v1.1`, 이슈 #33 A-2로 신설)를 대표 상태로 가질 때도 `PARTIAL`로 투영한다. **새 enum 값을 만들지 않고 기존 `PARTIAL`로 흡수한 이유**: `CANCELLED`도 완결이 아니고(`job-execution/v1.1` §9 예외) 부분 결과가 있을 수 있다는 점에서 UI 표시 목적상 "부분 완료"와 구분할 실익이 이번 라운드엔 없다 — 실제 중단 사유("사용자가 멈춤" vs "일부만 됨")를 구분해야 하면 `notices[]`로 별도 표시한다. `PARTIAL`을 보여주는 demo fixture는 아직 없다(`04_mock_validation_report.md` §1 커버리지 갭에 등재, 이번 라운드도 미포함 — Should-1) |
| notices[].severity | `INFO`, `WARN`, `ERROR` | 표시 강도만 의미하며 실제 차단 여부는 `blocking`으로 별도 판단 |
| notices[].code | dotted-lowercase namespaced string | **확정(2026-09-10, 유소연·신유민, 이슈 #26 A-⑤)**. 형식은 `<producing-module>.<detail>` — `case` / `evidence` / `readout` / `search` / `recording` 중 이 notice의 근거를 실제로 만든 모듈을 접두어로 쓴다. **`time`은 모듈이 아니므로 접두어로 쓰지 않는다** — 기존 `time.*` 4종은 `evidence.time_conflict_needs_notice`·`evidence.time_needs_user_confirmation`·`readout.overlay_not_present`·`evidence.time_post_stamp_required`로 정정했다(근거 모듈 기준: 시각 충돌·재확인·post-stamp는 `TimeResolution`을 만드는 evidence, overlay 부재는 관찰 자체를 만드는 readout). `JobExecution.failure_kind`(SCREAMING_SNAKE 열거값)를 `notices[].code`로 옮길 때는 **문자열을 그대로 복사하지 않고** 이 표기로 변환한다(A절 §7 참고) |
| notices[].actions[] | `EDIT_EVENT_TIME`, `MANUAL_PLATE_INPUT`, `GENERATE_REPORT_VIDEO`, `REVIEW_TIME`, `RETRY_PLATE_READ`, `EDIT_HINT`, `RETRY_SEARCH` | **닫음(2026-09-10, 유소연, 이슈 #26 A-⑥ · 이슈 #31 W-1로 2종 추가)**. SCREAMING_SNAKE 유지(발주 intent를 나타내는 값이라 `JobRecord.kind`류와 같은 표기). 값→발주 매핑은 아래 표. web은 이 값으로만 버튼을 렌더하며 값 자체를 해석하지 않는다(`running_jobs[].label_key`와 같은 원칙). **미등록 값은 fallback으로 버튼을 렌더하지 않는다**(무시) — `label_key` fallback과 달리 실행 경로가 없는 액션을 잘못 노출하는 것이 더 위험하기 때문이다 |

**`notices[].actions[]` → 발주 매핑**

| 값 | 발주/동작 |
| --- | --- |
| `EDIT_EVENT_TIME` | web이 사용자 입력을 받아 `CorrectionRecord`(Draft, N02 해소 후) 경유 시각 정정 — 현재는 case state 경유 |
| `MANUAL_PLATE_INPUT` | web이 사용자 입력을 받아 번호판 값을 직접 정정 (`vehicle_number`, `user_corrected=true`) |
| `GENERATE_REPORT_VIDEO` | `kind=REPORT_VIDEO_EXPORT` 신규 `JobRecord` 발주. 기존 `job_id` 없으면 새로 만든다 |
| `REVIEW_TIME` | web이 시각 후보들을 보여주고 사용자가 하나를 선택/확인하게 한다 — 새 Job 발주 없음, 확인만으로 `TimeResolution.resolved.verification`이 바뀐다(§9-2 미결 항목과 연결) |
| `RETRY_PLATE_READ` | `kind=PLATE_READ` 신규 `job_id` 발주. `FAILED`는 cache hit 대상이 아니므로(A절 §7 캐시 재사용은 성공 결과에 한정) `force_rerun` 불필요 — 새 `job_id`만으로 재시도가 성립한다 |
| `EDIT_HINT` | **신규(v1.3, 이슈 #31 W-1)**. web이 사용자로부터 새 검색 단서(시간대·사건 유형 등)를 입력받는다 — 새 Job 발주 없음, 다음 `RETRY_SEARCH`의 입력을 바꾸는 동작이다 |
| `RETRY_SEARCH` | **신규(v1.3, 이슈 #31 W-1)**. `kind=COARSE_SEARCH` 신규 `job_id` 발주(바뀐 단서 기준). `candidates=[]`는 cache hit 대상이 아니므로 `force_rerun` 불필요 — 새 `job_id`만으로 재검색이 성립한다(`RETRY_PLATE_READ`와 같은 원칙) |

**`info_state` 파생 규칙 — 확정 (B01 종결, 2026-09-07)**

입력은 모두 `EvidenceRecord`(`contract-evidence-record-needs.md` §3)에서 온다. `case`는 어느 입력도 재계산·재해석하지 않는다. 근거·기각안은 `adr/adr-data-contract-call-closure-2026-09-07.md` §4.1.

**(1) `EvidenceValue` 기반 display — `plate_display` · `case_type_display` · `report_type_display` · `violation_display` · (`location_display`의 대표값 선정 후에도 동일 규칙, §7-(3))**

```
1. value == null                        → INFO_UNKNOWN
2. user_corrected == true               → INFO_USER_CONFIRMED
3. needs_review == true                 → INFO_NEEDS_REVIEW
4. source.observability == OBSERVED     → INFO_SOURCE_VERIFIED
5. 그 외 (source.observability=INFERRED) → INFO_AI_ESTIMATED
```

2가 3보다 앞서는 것은 `core-user-flow.md` §9 「한 번 `사용자 확인됨`이 된 값은 다시 묻지 않는다」 때문이다. `needs_review`는 **`evidence`가 값과 함께 내려주는 `EvidenceValue.needs_review`**다. `evidence`가 「`user_corrected=true`와 `needs_review=true` 동시 발생 금지」·「`value=null`과 `needs_review=true` 동시 발생 금지」를 보장하므로(같은 계약 §10) 순서 규칙과 boolean이 어긋나는 조합은 생기지 않는다.

**(1) 적용 범위 확정(v1.3, 이슈 #31 W-3, 유소연).** `case_type_display`(← `event.visual_event_type`)·`report_type_display`(← `event.safety_report_type`)·`violation_display`(← `event.violation_expression`)는 셋 다 `EvidenceRecord.event` 아래의 `EvidenceValue<T>`이므로 `plate_display`와 같은 (1) 규칙을 그대로 쓴다 — 별도 파생 로직이 아니다. 실질적 효과: `visual_event_type`/`violation_expression`은 `evidence.assemble()`이 항상 `source.observability=INFERRED`(AI 추론)로 채우므로(원본 관찰이 아니라 VisualEvidence를 evidence가 해석한 값), `verification=OBSERVED`인 경우도 `case_type_display=INFO_SOURCE_VERIFIED`가 되는 것은 "AI가 VisualEvidence의 OBSERVED 판정을 그대로 옮겼다"는 뜻이고, `violation_display`는 사건 유형 확정 여부와 무관하게 문장 자체가 항상 AI 생성이라 전 시나리오에서 `INFO_AI_ESTIMATED`다 — happy path를 포함해 신고문 화면에 「AI 추정」 표시가 뜬다. 이는 W-3에서 신유민이 제안한 해석을 그대로 채택한 것이다.

**(2) `occurred_at` → `event_time_display`** — `occurred_at`은 `EvidenceValue`가 아니라 `{value, time_resolution_ref, resolution_status, user_corrected, source{kind,label_key}}`다. `case`는 `source`를 들여다보지 않는다.

| 조건 (위에서부터 첫 일치) | `info_state` |
| --- | --- |
| `occurred_at` 부재 | `INFO_UNKNOWN` |
| `occurred_at.user_corrected == true` | `INFO_USER_CONFIRMED` |
| `occurred_at.resolution_status == NEEDS_REVIEW` | `INFO_NEEDS_REVIEW` |
| `occurred_at.resolution_status == OK` | `INFO_SOURCE_VERIFIED` |

이 표가 안전한 것은 `evidence`가 `OK`를 **검증된 영상 화면 시각 또는 사용자 확정에만** 부여하고 파일명·metadata 계산 시각은 `NEEDS_REVIEW`로 내리기 때문이다(`contract-time-resolution.md` §4). `event_time_display.needs_review`는 `resolution_status == NEEDS_REVIEW`를 그대로 옮긴다. `source_label_key`는 `occurred_at.source.label_key`다.

**(3) `location_display` 대표값** — `EvidenceRecord.location`의 `address → place_name → user_hint` 중 **존재하는 첫 값 하나**를 `value`에 싣고 그 `EvidenceValue`를 (1)의 입력으로 쓴다. 대표값이 `user_hint`이면 `info_state = INFO_NEEDS_REVIEW`다. 여러 값을 합쳐 새 위치 문자열을 만들지 않는다. `coord`·`search_keyword`는 대표값 후보가 아니며 `location_display.coord` / `location_display.search_keyword`로 **별도** 내려보낸다(좌표 포맷은 web). `source_label_key`는 대표값 `value`의 출처만 뜻한다. 셋 다 없으면 `value = null`, `INFO_UNKNOWN`.

**(4) `needs_review`와 `info_state`의 관계** — 독립 필드다(동치 불변식이 아니다). `needs_review`는 「값은 있지만 사용자 확인이 필요한 경우」에만 참이다. **web 소비 규칙: web은 `info_state`만 보고 표시하며 `needs_review`를 직접 해석하지 않는다.** 「값이 없어 입력이 필요한 상태」와 「값이 있는데 검토가 필요한 상태」는 `INFO_UNKNOWN` / `INFO_NEEDS_REVIEW`로 이미 갈라진다.

`source.observability`는 `contract-evidence-record-needs.md`의 `EvidenceValue.source`가 소유한다. **`case`가 `source.kind` 문자열을 보고 관찰/추론을 스스로 분류하지 않는다** — 그건 `case`가 정책 판단을 하는 것이라 §3 「authoritative 판단을 재계산하지 않는다」에 걸린다.

`source_label_key`는 `EvidenceValue.source.label_key`(사건시각은 `occurred_at.source.label_key`)를 그대로 통과시킨 값이며 키 네임스페이스는 `evidence`가 소유한다. 대응 키가 없으면 `null`로 두고 web이 fallback 문구를 쓴다.

**`progress[]`의 step 집합 규칙 — 확정 (v1.3, 2026-09-10, 유소연, 이슈 #31 W-7)**

`progress[]`가 담는 step 개수가 시나리오마다 8/7/5/3개로 갈려 있던 것을 정리한다. 규칙: **이 case가 밟을 계획인 step만 담되, "계획"의 기준은 시나리오가 실제로 다루는 모듈 범위다.** 구체적으로:

1. 이 시나리오가 다루는 모든 모듈이 최종적으로 `package_assembly`까지 이어질 수 있는 경우(`happy`·`correction_rerun`·`plate_reread`·`unknown_abstain_partial`), **도달 여부와 무관하게 8단계 전부**를 싣는다 — 아직 도달하지 않은 step은 `PENDING`으로 표시한다.
2. 시나리오 카탈로그가 특정 모듈을 `modules_intentionally_absent`로 명시했다면, 그 모듈에 대응하는 step은 **`PENDING`으로도 넣지 않고 배열에서 아예 뺀다** — 이 CaseView는 애초에 그 단계에 도달할 계획이 없기 때문이다(예: `infra_failure_001`은 evidence 모듈이 없어 `evidence_assembly`부터 이후 3단계를 빼고, `relative_rebase_001`은 readout·evidence 모듈이 모두 없어 `plate_read`부터 이후 5단계를 뺀다).
3. `candidates=[]`로 이 case의 진행이 구조적으로 멈춘 경우(`empty_001`)도 2와 같은 취급이다 — 이후 step은 이 case 생애주기에서 일어날 계획 자체가 없다.

정리 전에는 `relative_rebase_001`이 자신의 카탈로그 선언(readout·evidence 모듈 전체 부재)과 다르게 8단계를 `PENDING`으로 전부 실어 규칙 2를 어기고 있었다 — 3단계(`file_intake`·`coarse_search`·`candidate_review`)로 정정했다. `plate_reread_001`은 evidence/package 모듈이 실제로 존재하는 시나리오인데 `package_assembly`가 빠져 있어 규칙 1 위반이었다 — rev3·rev4 양쪽에 `package_assembly: PENDING`을 추가했다(이 gap이 바로 W-6의 "다음에 뭘 해야 할지 알 수 없는 막다른 화면" 문제의 절반이었다 — 나머지 절반은 `notices[]`에 `case.report_video_not_generated`(INFO, `actions:["GENERATE_REPORT_VIDEO"]`)를 추가해 닫았다).

**`evidence.review_needed` 파생 규칙 — 확정 (2026-09-09, 유소연, Mock Pack 심층 검토 §12 후속)**

`review_needed`(object-level)는 `evidence`(record 단위 `EvidenceRecord`)가 아니라 **`case`가 아래 여섯 개의 `*_display.needs_review`로부터 파생하는 값**이다: `case_type_display` · `report_type_display` · `violation_display` · `plate_display` · `event_time_display` · `location_display`.

```
review_needed = (case_type_display.needs_review OR report_type_display.needs_review OR violation_display.needs_review
                  OR plate_display.needs_review OR event_time_display.needs_review OR location_display.needs_review
                  OR plate_display.info_state==INFO_NEEDS_REVIEW OR event_time_display.info_state==INFO_NEEDS_REVIEW
                  OR location_display.info_state==INFO_NEEDS_REVIEW OR case_type_display.info_state==INFO_NEEDS_REVIEW
                  OR violation_display.info_state==INFO_NEEDS_REVIEW
                  OR report_type_display.info_state==INFO_NEEDS_REVIEW)   # v1.3, report_type_display에 info_state 추가되며 포함
```

즉 **여섯 개 중 하나라도 `needs_review=true`이거나, `info_state`를 가진 필드 중 하나라도 `INFO_NEEDS_REVIEW`이면 `true`**다(v1.3 이전에는 `report_type_display`에 `info_state`가 없어 이 항에서 제외했으나, v1.3에서 `info_state`가 추가돼 이제 `report_type_display.info_state==INFO_NEEDS_REVIEW`도 포함한다 — 이슈 #33 반영). **개정(2026-09-10, 유소연, 이슈 #26 B-web-6)** — 원래는 `needs_review`만 OR했는데, B절 §7-(3) 「대표값이 `user_hint`면 `INFO_NEEDS_REVIEW`」가 `needs_review`를 거치지 않고 바로 `info_state`를 정하는 경로라 원래 식이 이 조합을 놓쳤다(`scenario_happy_001`의 `location_display`가 `needs_review=false`인데 `info_state=INFO_NEEDS_REVIEW`인 사례로 발견). `review_needed`가 "검토 필요한 게 하나라도 있는가"의 요약이라는 원래 의도를 지키기 위해 `info_state` 경로도 포함시켰다 — `needs_review`와 `info_state`가 독립 필드라는 원칙(B절 §7 (4))은 그대로 유지하고, 집계식만 두 경로를 모두 본다. `reason_code`는 `true`가 된 원인이 하나면 그 필드에 대응하는 코드(예: `evidence.event_time_needs_review`, `evidence.location_needs_review`)를, 둘 이상이면 `evidence.multiple_fields_need_review`를 쓴다. `needs_review`·`info_state` 자체를 재계산하지 않으며(§10 불변조건 6과 같은 원칙), object-level `review_needed`와 필드별 값들은 같은 축의 집계일 뿐 서로 다른 정책을 추가하지 않는다.

**`package.report_field_states` — 신설 (v1.3, 2026-09-10, 이슈 #31 A-2 · 신유민 PR #28 요청)**

`report_fields`(평면 `object<string, string|null>`)는 필드 단위 상태(에러/치환/검토 필요 등)를 실을 자리가 없었다(`CONTRACT_CONFLICTS.md` 불명확 항목 10). `report_field_states`를 나란히 추가해 필드별 `{info_state, source_label_key}`를 제공한다. **값 공간은 기존 여섯 `*_display.info_state`와 같다** — 새 상태를 만들지 않는다.

`report_fields`/`report_field_states`의 키와 `evidence.*_display` 출처 대응표:

| `report_fields` 키 | 출처 |
| --- | --- |
| `vehicle_number` | `plate_display` |
| `occurred_at` | `event_time_display` |
| `location` | `location_display` |
| `violation_expression` | `violation_display` |
| `safety_report_type` | `report_type_display` |

`case_type_display`는 `report_fields`에 대응 키가 없다 — 안전신문고 신고 양식에 들어가지 않는 내부 사건 분류 표시이기 때문이다(실제 신고문에 들어가는 것은 `safety_report_type`/`violation_expression`이다). `case`가 `report_fields`/`report_field_states`를 만들 때 이 대응표의 값을 그대로 옮긴다(재계산 없음) — evidence/case 경계의 값 공간을 늘리지 않는다.

**`unconfirmed_fields` 파생 규칙 — 명확화(v1.3)**

```
unconfirmed_fields = [ field for field in report_field_states
                        if report_field_states[field].info_state
                           ∈ {INFO_AI_ESTIMATED, INFO_NEEDS_REVIEW, INFO_UNKNOWN} ]
```

`INFO_SOURCE_VERIFIED`·`INFO_USER_CONFIRMED`인 필드는 `unconfirmed_fields`에 넣지 않는다. `vehicle_number`/`occurred_at`/`location`은 v1.2에서도 이미 `info_state`를 가졌으므로 이 세 필드는 규칙 적용 결과가 바뀌지 않는다. `safety_report_type`/`violation_expression`은 v1.3에서 `report_type_display.info_state`가 처음 생기면서 이번에 `unconfirmed_fields` 계산에 들어간다 — 위 위험 안내 참고.

### 8. 정상 예시

json

```json
{  "case_id": "case_3", "case_rev": 4, "stage": "EVIDENCE_REVIEW", "user_reviewed": false,  "manifest_summary": { "file_count": 42, "ok_file_count": 40, "failed_file_count": 2, "duration_sec": 4680, "range": ["18:03", "19:21"] },  "hints": { "time": "18:30 전후", "vehicle": "흰색 SUV", "situation": "백색 실선 crossing 가능성", "location": "미금역 근처" },  "progress": [ { "step": "SCOPE", "state": "DONE" }, { "step": "COARSE", "state": "DONE" }, { "step": "FINE", "state": "RUNNING" } ],  "candidates": [ { "candidate_id": "c1", "at": "18:31:48", "at_provenance": "TIMELINE_ANCHOR+OFFSET", "observed": "백색 실선 + 흰 SUV가 선을 넘어 인접차로 진입", "thumb_ref": "fr_7c2e91", "selected": true } ],  "evidence": {    "record_id": "ev_88",    "plate_display": { "value": "12가 3476", "needs_review": false, "info_state": "INFO_SOURCE_VERIFIED", "source_label_key": "plate.source.overlay_ocr" },    "event_time_display": { "value": "2026-08-24T18:31:48+09:00", "needs_review": true, "info_state": "INFO_NEEDS_REVIEW", "source_label_key": "time.source.filename_time" },    "location_display": { "value": "미금역 사거리 인근", "needs_review": true, "info_state": "INFO_NEEDS_REVIEW", "source_label_key": "location.source.visual_inference", "coord": null, "search_keyword": "미금역 사거리" },    "review_needed": true,    "reason_code": "LOCATION_LOW_CONFIDENCE"  },  "requirements_evidence": { "readiness": "WARN", "checks": [] },  "requirements_package": null,  "package": null,  "running_jobs": [ { "job_id": "job_52", "kind": "PLATE_READ", "label_key": "job.plate_read", "status": "RUNNING" }, { "job_id": "job_53", "kind": "OVERLAY_TIME_READ", "label_key": "job.overlay_time_read", "status": "PENDING" } ],  "notices": []}
```

> 사건시각이 파일명 계산값이라 `resolution_status=NEEDS_REVIEW` → `INFO_NEEDS_REVIEW`다(`core-user-flow.md` §13의 「파일 기록으로 계산한 시각」 화면과 대응). 위치는 `address`/`place_name`이 있어 대표값이 되었고 `search_keyword`는 별도 필드로 내려갔다. package-scope 검사가 아직 없어 `requirements_package=null`이다.

### 9. 실패 / 부분성공 / UNKNOWN 예시

json

```json
{  "case_id": "case_9", "case_rev": 2, "stage": "CANDIDATE_REVIEW", "user_reviewed": false,  "manifest_summary": { "file_count": 12, "ok_file_count": 10, "failed_file_count": 2, "duration_sec": 2400, "range": ["09:00", "09:40"] },  "hints": { "time": "아침 출근길", "vehicle": null, "situation": "신호위반 목격", "location": null },  "progress": [ { "step": "SCOPE", "state": "DONE" }, { "step": "COARSE", "state": "DONE" } ],  "candidates": [],  "evidence": null,  "requirements_evidence": null,  "requirements_package": null,  "package": null,  "running_jobs": [],  "notices": [    { "code": "PLATE_ABSTAINED", "severity": "WARN", "blocking": false, "message_key": "notice.plate_abstained", "actions": ["MANUAL_PLATE_INPUT"] }  ]}
```

### 10. 불변조건

1. `case_rev`는 반영 시점 리비전이며, 더 최신 case_rev 존재 시 stale
2. `evidence`/`package`가 선택/완료 이전이면 null
3. `package`가 non-null이면 `requirements_package`가 non-null이고 `requirements_package.readiness ∈ {PASS, WARN}`이다 (`contract-requirement-report-package.md` §5.2·§8.1의 Package 생성 조건의 귀결. B02 종결 2026-09-07)
4. `evidence`/`package`는 EvidenceRecord/ReportPackage의 원본 필드를 그대로 포함하지 않는다(safe projection만 포함)
5. `running_jobs`가 비어 있으면 진행 중인 작업 없음
6. `info_state`는 §7의 확정 규칙으로만 파생한다. `case`가 threshold나 source 분류를 독립 정책으로 추가하지 않는다 (B01 종결 2026-09-07)
7. `stage=READY`는 `PACKAGE_READY` 파생 gate가 성립한 시점이며, gate 자체는 `RequirementReport`/`ReportPackage`가 소유한다. `case`는 gate를 재계산하지 않는다
8. **`user_reviewed`(workflow) · `evidence.user_edited`(record 단위) · `info_state=INFO_USER_CONFIRMED`(필드 단위 `user_corrected` 파생)는 서로 다른 세 가지 사실이며 하나로 합치지 않는다.** `contract-time-resolution.md` §10 항목 5 「`user_corrected`는 `USER_REVIEWED` workflow 상태와 동일하지 않다」와 같은 구분이다
9. `stage=READY`이면 `requirements_package`가 non-null이고 `readiness ∈ {PASS, WARN}`이다. `READY`가 `PACKAGE_READY` 파생 gate이고 그 gate는 현재 basis의 `FINAL_PACKAGE` scope report로만 성립한다 (B02 종결 2026-09-07)
10. `requirements_evidence`·`requirements_package`는 §7의 3단계 선택 규칙을 통과한 report만 싣는다. **이전 basis(`EvidenceRecord.record_ref`가 다른) report는 현재 판정으로 대체 사용하지 않는다.** 사용자 수정 직후 재검사 전이면 `null`이 정상이다
11. `EVIDENCE_SUFFICIENT` / `PACKAGE_READY` / `USER_REVIEWED`를 하나의 readiness 값으로 합쳐 내려보내지 않는다
12. web은 `info_state`로만 표시 분기한다. `needs_review`를 직접 해석하지 않는다

### 11. Consumer Review 반영 요약

| Consumer | 상태 | 반영 내용 |
| --- | --- | --- |
| 신유민(web) | 수정요청 → 반영 완료 | evidence/package safe projection 필드 확정, stage/progress enum 확정, manifest_summary/notices/running_jobs 표시 계약 보완 |
| 김대원(eval) | 승인 | 반영 사항 없음 |
| 김준영(evidence/PM) | 최종 승인 | safe projection 원칙, case의 재계산 금지, projection 필드 의미 경계 및 최종 스키마 승인 |
| 유소연(case Owner) · 신유민(web) | **v1.1 확정 (2026-09-06)** | CALL-1 A안 수용 + `INFO_` 접두어(유소연) · A안 채택과 `source_label_key` display별 배치(신유민) · CALL-5 (1)(2)(3) 확정(유소연). 김준영 이견 없음 |

### 12. Closure 완료 사항

- evidence/package: safe projection·재판정 금지 원칙을 유지한다. 세부 필드 합의는 §13의 Pending으로 분리한다.
- `progress.state`: `PENDING / RUNNING / DONE / FAILED`로 확정.
- `running_jobs.label_key`: 필수 제공. web은 `kind` 문자열을 직접 해석하지 않으며, 미등록/알 수 없는 kind는 `job.generic_processing` fallback을 사용한다.
- `notices.severity`: `INFO / WARN / ERROR`로 확정. 실제 차단 여부는 `blocking`이 결정한다.
- `manifest_summary`: file_count/ok_file_count/failed_file_count/duration_sec는 항상 제공하고, 정상 영상이 하나도 없으면 `range=null`을 허용한다.

**v1.1에서 추가로 닫힌 것 (2026-09-06)**

- `stage=READY`: `PACKAGE_READY` 파생 gate 성립 시점으로 확정. `ownership.md` §7-④가 「통합 전 case Owner가 확인한다」로 넘긴 미결이 닫혔다.
- `requirements.readiness`: `RequirementReport.overall`의 projection으로 확정하고 값 공간을 `PASS/WARN/BLOCK/UNKNOWN`으로 축소.
- `user_reviewed`: v4 §3-6 `USER_REVIEWED`를 내려보내는 통로 확정.
- `info_state` · `source_label_key`: 세 값 display의 필드 채택을 유지. 파생 규칙의 완결성은 당시 Pending B01이었고 v1.2(2026-09-07)에서 종결됐다.
- **종결 철회 — `requirements.scope`:** PM의 단독 확정을 제안/Owner 확인 대기로 되돌렸다(B02). 기존 R-7은 과거 결정 기록이며 현재 수락 근거가 아니다.

**v1.2에서 닫힌 것 (2026-09-07 · 유소연 결정 · 김준영·신유민 확인 · `adr/adr-data-contract-call-closure-2026-09-07.md`)**

- **B01 종결:** `needs_review`는 `evidence`가 값과 함께 제공, `occurred_at` 4단계 변환, 위치 대표값 `address→place_name→user_hint`, `coord`·`search_keyword` 별도 필드, `needs_review`↔`info_state` 독립 + web은 `info_state`만 본다.
- **B02 종결:** `requirements`를 `requirements_evidence` / `requirements_package`로 분리. 선택 3단계는 §7이 소유. 세 gate 분리. §10-3·§10-9 확정, §10-10~12 추가.
- **`thumb_ref`:** `FrameRef`(`fr_` 계열)로 확정(정철원·유소연·신유민). web→recording 직접 호출 금지.
- **W02 잔여:** 네 evidence display 필드는 삭제 의도 없음 — 유지 확정.
- `JobRecord.kind`에 `OVERLAY_TIME_READ` 등재, `label_key` `job.overlay_time_read` 추가.

### 13. 남은 미결 및 별도 종결 항목

- evidence/package projection의 세부 필드명 최종 합의 · `CorrectionRecord.target_field`와 display 필드명 정렬 → 같은 자리에서 처리한다.
- **`candidates[]`의 stale-revision 표시 필드.** `CandidateEvent.span.timeline_revision`이 현재 `RecordingTimeline.revision`과 다르면 `case`가 비교해 「과거 timeline revision 기준」임을 표시한다(B09, 2026-09-07 합의). **필드명·모양은 case Owner가 구현 시 정한다** — 여기서 임의로 만들지 않는다. `adr/adr-data-contract-call-closure-2026-09-07.md` §4.8.
- **`FrameRef` 필드 계약 — 종결 (2026-09-08).** `candidates[].thumb_ref`가 `FrameRef`라는 점과 `FrameRef`의 필드·발급·조회 capability는 `contract-source-asset-media-stream.md` §5·§7이 소유한다(`source-asset-media-stream/v1`, Consumer Review 종결). 목데이터의 `fr_` 예시도 그 계약에서 읽는다 — `mock-pack-v1-refs.md`는 폐기됐다. **`thumb_ref` 이미지 전달 형태**(URL/ref/endpoint)는 그 계약 §9-6 Pending으로 남아 있고, 호출 경계(`case → recording → projection → web`, web→recording 직접 호출 금지)는 §7에 확정돼 있다.
- ~~**재판독 발주의 `JobRecord.kind`**(A절 §7) — case Owner 결정 대기(CALL-12).~~ → **종결 (2026-09-07, 유소연).** `kind=PLATE_READ` + `force_rerun=true`(무조건) · 새 `job_id` · 기존 `ReadoutRun` 갱신 없음. A절 §7 등재. `adr/adr-data-contract-call-closure-2026-09-08.md` §4.1.
- ~~**Fine 발주·Report Video export의 `JobRecord.kind` 미등재**(`04_mock_validation_report.md` §3.3-1) — case Owner 결정 대기.~~ → **종결 (2026-09-09, 유소연).** `FINE_VERIFY`·`REPORT_VIDEO_EXPORT` A절 §7 등재, `label_key` `job.fine_verify`·`job.report_video_export` 추가. `purge_case()`는 `JobRecord` 밖의 관리 동작으로 확정(§8 참고).
- ~~**`CaseView.evidence.review_needed` 파생 규칙 미명시**(`04_mock_validation_report.md` §3.2-3) — case Owner 결정 대기.~~ → **종결 (2026-09-09, 유소연).** 규칙과 근거는 B절 §7 「`review_needed` 파생 규칙」에 등재.
- 최초 수락일 — Owner가 기억하지 못해 **확인 불가**로 유지한다(헤더).
- **별도 종결 항목 —** JobExecution → CaseView 상태 projection: `QUEUED→PENDING`, `RUNNING→RUNNING`, `SUCCEEDED→DONE`, `FAILED/STALE→FAILED`, **`CANCELLED→PARTIAL`(v1.3 추가, `job-execution/v1.1`의 `CANCELLED` 신설에 대응)**.

### 14. v1.3에서 닫힌 것 (2026-09-10 · 유소연 통합 초안 · 신유민·김준영 PR 리뷰 확인 대상, 이슈 #31/#33)

- `candidates[].situation_confirmation` 값 공간을 `evidence-record/v1.3`의 `situation_response`와 맞춰 `NOT_ASKED | CONFIRMED | CORRECTED | USER_UNSURE`로 정정. 파생 출처(§7) 명시.
- `progress[].state`의 "중단" 표현: 새 enum 값 없이 `CANCELLED→PARTIAL`로 흡수(`CONTRACT_CONFLICTS.md` 불명확 항목 9 종결).
- `evidence.report_type_display`에 `info_state`/`source_label_key` 추가(`CONTRACT_CONFLICTS.md` 불명확 항목 4 잔여 해소, SafetyReportType registry 근거).
- `package.report_field_states` 신설 + `report_fields` 키 매핑표 + `unconfirmed_fields` 파생 규칙 명확화(`CONTRACT_CONFLICTS.md` 불명확 항목 10 종결).
