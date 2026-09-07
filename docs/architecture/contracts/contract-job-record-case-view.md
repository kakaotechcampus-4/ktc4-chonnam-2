# Final Data Contract — JobRecord (Job Intent) + CaseView v1

**Status:** `Final — Accepted`

**Accepted:** 최초 수락일 확인 대기 — 동일 계약 회차라는 이유로 추정한 2026-09-04 표기를 철회한다. CALL-1·5의 2026-09-06 답변 범위는 아래에 별도로 유지한다.

**수락 근거:** §11 Consumer Review 반영 요약 — 신유민(web) 「수정요청 → 반영 완료」 · 김대원(eval) 「승인」 · 김준영 「최종 승인」. 본문에 리뷰 종료 기록이 있다. 정확한 최초 수락일·필드별 서명 범위는 확인 대기다. 과거에는 PM이 헤더를 채웠다(`adr/adr-consistency-2026-09.md` C1-13). 유소연 이견 시 되돌린다

**Architecture Contract:** v4 §5-1 ⑪ `CaseView` · ⑫ `JobRecord`

**Contract Version:** `job-record/v1` · `case-view/v1.2`

**Related ADR:** `adr/adr-job-record-case-view.md` · `adr/adr-consistency-2026-09.md` §6 R-1·R-2 · **`adr/adr-data-contract-call-closure-2026-09-07.md` §4.1·§4.2·§4.3·§4.9 (v1.2 근거)**

> **`CaseView`는 v4에서 부록이 아니라 Core Contract ⑪이다**(v4 §5 머리말 · §4-모듈5 ⑥). 아래 절 제목의 「부록-A / 부록-B」는 ADR 작성 당시 표기이며, 계약의 위상은 Core Contract다.

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

- `kind`: 확인된 값 `COARSE_SEARCH`, `PLATE_READ`, **`OVERLAY_TIME_READ`**(2026-09-07 등재, 유소연). 전체 목록은 모듈 접두어 규칙에 따라 계속 등재 (닫힌 enum 아님)
  - `PLATE_READ`와 `OVERLAY_TIME_READ`는 **항상 별도 `job_id`로 발주**한다. `ReadoutRun.operation`(`contract-readout-run.md` §6)과는 같은 이름의 값끼리 대응한다 — `PLATE_READ↔PLATE_READ`, `OVERLAY_TIME_READ↔OVERLAY_TIME_READ`. 한쪽에만 값을 추가하지 않는다.
  - `PLATE_REREAD`는 `EvidenceNeeds.kind`의 값이며 `JobRecord.kind` 값이 아니다(값 공간이 다르다 — §4 「corrections.kind는 JobRecord.kind와 다른 값 공간」과 같은 이유). **재판독 발주의 `kind`·identity 처리는 case Owner 결정 대기다**(`adr/adr-data-contract-call-closure-2026-09-07.md` §8.1 CALL-12). 확정 전에는 임의로 값을 만들지 않는다.
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
5. **readout 계열 Job 1 execution : `ReadoutRun` 1건 (1:1)** — `case`의 orchestration 불변조건이다(유소연 · 신유민, 2026-09-07). `readout`은 `JobExecution`을 모르므로 readout이 보장하는 것은 「public 함수 호출 1회 = `ReadoutRun` 1건」이고, 1:1은 worker 구현 규칙 「1 execution 안에서 readout public 함수를 정확히 1회 호출한다」(`contract-job-execution.md` §9-9)로 성립한다. `run_id`는 `job_id`처럼 재사용되지 않는 1회성 식별자이나 `execution_id`와 **같은 identity가 아니다**. 근거 `adr/adr-data-contract-call-closure-2026-09-07.md` §4.3

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
- kind 표시용 `label_key`/fallback은 부록-B `CaseView` 계약에서 확정한다. 등재된 `label_key`: `job.plate_read` · `job.overlay_time_read`(2026-09-07 추가). 미등록 kind는 `job.generic_processing` fallback(B절 §12).

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
{  "case_id": "string",  "case_rev": "int",  "stage": "INTAKE | SEARCHING | CANDIDATE_REVIEW | EVIDENCE_REVIEW | READY",  "user_reviewed": "boolean",  "manifest_summary": {    "file_count": "int",    "ok_file_count": "int",    "failed_file_count": "int",    "duration_sec": "number",    "range": "[string, string] | null"  },  "hints": { "time": "string|null", "vehicle": "string|null", "situation": "string|null", "location": "string|null" },  "progress": [ { "step": "string", "state": "PENDING | RUNNING | DONE | FAILED" } ],  "candidates": [    { "candidate_id": "string", "at": "string", "at_provenance": "string", "observed": "string", "thumb_ref": "FrameRef (fr_<opaque-id>) | null", "selected": "boolean" }  ],  "evidence": {    "record_id": "string",    "case_type_display": { "code": "string|null", "label": "string|null", "needs_review": "boolean" },    "report_type_display": { "code": "string|null", "label": "string|null", "needs_review": "boolean" },    "violation_display": { "code": "string|null", "label": "string|null", "needs_review": "boolean" },    "plate_display": { "value": "string|null", "needs_review": "boolean", "info_state": "INFO_AI_ESTIMATED | INFO_SOURCE_VERIFIED | INFO_USER_CONFIRMED | INFO_NEEDS_REVIEW | INFO_UNKNOWN", "source_label_key": "string|null" },    "event_time_display": { "value": "ISO8601|null", "needs_review": "boolean", "info_state": "INFO_AI_ESTIMATED | INFO_SOURCE_VERIFIED | INFO_USER_CONFIRMED | INFO_NEEDS_REVIEW | INFO_UNKNOWN", "source_label_key": "string|null" },    "location_display": { "value": "string|null", "needs_review": "boolean", "info_state": "INFO_AI_ESTIMATED | INFO_SOURCE_VERIFIED | INFO_USER_CONFIRMED | INFO_NEEDS_REVIEW | INFO_UNKNOWN", "source_label_key": "string|null", "coord": "{ lat: number, lon: number } | null", "search_keyword": "string|null" },    "user_edited": "boolean",    "preview_ref": "string|null",    "review_needed": "boolean",    "reason_code": "string|null"  },  "requirements_evidence": { "readiness": "PASS | WARN | BLOCK | UNKNOWN", "checks": [] },  "requirements_package": { "readiness": "PASS | WARN | BLOCK | UNKNOWN", "checks": [] },  "package": {    "package_ref": "string|null",    "report_fields": "object<string, string|null>",    "artifact_ref": "string|null",    "capabilities": "string[]",    "warnings": "string[]"  },  "running_jobs": [ { "job_id": "string", "kind": "string", "label_key": "string", "status": "PENDING | RUNNING" } ],  "notices": [    { "code": "string", "severity": "INFO | WARN | ERROR", "blocking": "boolean", "message_key": "string", "actions": "string[]" }  ]}
```

> `requirements_evidence`·`requirements_package`·`package`·`evidence`는 각각 `null`일 수 있다(조건은 §7·§10). 위 evidence/package는 safe projection 경계를 따른다. case는 Evidence/ReportPackage의 authoritative 값을 재판정하거나 confidence를 자체 threshold로 재해석하지 않고, 확정된 값·검토 필요 여부·사유를 UI 표시 형태로만 변환한다. raw confidence, 내부 provenance, 중간 추론값은 기본 노출하지 않는다. `candidates[].thumb_ref`는 `FrameRef`이며 web은 recording을 직접 호출하지 않는다 — 실제 이미지는 case가 recording lookup을 거쳐 projection한다(전달 형태는 recording 자산 계약 대기, §13).
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
| requirements_evidence | object \| null | Y(키) | 현재 basis의 scope=`EVIDENCE` `RequirementReport` projection `{readiness, checks}`. 선택 규칙 §7. 미실행이면 `null` | **확정** (유소연 2026-09-07, B02 종결) |
| requirements_package | object \| null | Y(키) | 현재 basis의 scope=`FINAL_PACKAGE` `RequirementReport` projection `{readiness, checks}`. 미실행·파생물 미생성이면 `null` | **확정** (유소연 2026-09-07, B02 종결) |
| requirements_*.readiness | enum(4) | Y(객체 안) | 해당 `RequirementReport.overall`의 projection. case가 재계산하지 않는다 | **확정** (유소연 2026-09-06) |
| candidates[].thumb_ref | FrameRef \| null | Y(키) | 후보 대표 frame의 `FrameRef`(`fr_<opaque-id>`). 위치를 ID에 인코딩하지 않는다 | **확정** (정철원·유소연·신유민 2026-09-07) |
| manifest_summary.ok_file_count / failed_file_count / duration_sec | int/int/number | Y | 파일 등록 성공·실패 수, 전체 구간 길이. count/duration은 항상 제공하고 정상 영상이 없으면 range=null | 확정 |
| evidence.* (projection 필드 전반) | object | 선택 | 화면 표시용 evidence 요약 | safe projection 원칙 확정; 세부 필드 합의는 §13 Pending |
| package.* | object | 선택 | 화면 표시용 package 요약 | safe projection 원칙 확정; 세부 필드 합의는 §13 Pending |
| notices[].code/severity/blocking/message_key/actions | string/string/bool/string/array | Y(배열은 빈 배열 허용) | 부분 실패/경고 표시 | 신규, 신유민 요청 반영 |
| progress[].state | string | Y | 단계 상태 | **확정** — `PENDING / RUNNING / DONE / FAILED` |

### 7. Enum / State / Special Value

| 필드 | 확정 값 | 비고 |
| --- | --- | --- |
| stage | `INTAKE`, `SEARCHING`, `CANDIDATE_REVIEW`, `EVIDENCE_REVIEW`, `READY` | 신유민 Q3 답변 기준 최종 확정. **`READY` = 「`PACKAGE_READY` 파생 gate가 성립한 시점」**(`contract-requirement-report-package.md` §5.2). `EVIDENCE_SUFFICIENT`는 `EVIDENCE_REVIEW` 단계 안의 조건이고 `USER_REVIEWED`는 `user_reviewed` 필드가 갖는다 |
| user_reviewed | `true`, `false` | v4 §3-6 `USER_REVIEWED`. `stage`와 별개 축이며 `stage=READY`가 아니어도 `true`일 수 있다 |
| requirements_evidence / requirements_package | 객체 또는 `null` | scope별 report projection. **선택 규칙(3단계)** — ① `basis.evidence_record_ref`가 현재 `EvidenceRecord.record_ref`와 일치하는 report만 후보 ② `supersedes_ref` 체인의 head ③ 그래도 복수면 `evaluated_at` 최신. 이 규칙은 이 계약이 소유하고 `contract-requirement-report-package.md` §5.2-1은 여기를 가리킨다. `requirements_evidence=null`은 현재 basis의 Evidence 검사 미실행, `requirements_package=null`은 package-scope 검사 미실행 또는 필요한 파생물 미생성 |
| requirements_*.readiness | `PASS`, `WARN`, `BLOCK`, `UNKNOWN` | 해당 `RequirementReport.overall`과 **같은 값 공간**. `4/5` 같은 score 표현을 두지 않는다(`contract-requirement-report-package.md` §4 「단순 readiness score를 Contract에 두지 않는다」) |
| 세 gate의 출처 | — | `EVIDENCE_SUFFICIENT` = `requirements_evidence` 판정 · `PACKAGE_READY` = `requirements_package` 판정(+`package` 존재) · `USER_REVIEWED` = `user_reviewed`. **셋을 하나의 readiness로 합치지 않는다.** 별도 gate 표시값을 두려면 이 셋에서 단순 파생되는 표시값이어야 하고 새 authoritative 상태가 되면 안 된다 |
| evidence.*_display.info_state | `INFO_AI_ESTIMATED`, `INFO_SOURCE_VERIFIED`, `INFO_USER_CONFIRMED`, `INFO_NEEDS_REVIEW`, `INFO_UNKNOWN` | `core-user-flow.md` §3-1의 정보 상태 5종과 1:1. **`Observation.status`와 다른 값 공간이므로 `INFO_` 접두어로 분리한다** — 파생 코드가 두 enum을 동시에 다루는 지점에서 `NEEDS_REVIEW`/`UNKNOWN`이 겹치는 것을 막는다(유소연 2026-09-06) |
| progress[].state | `PENDING`, `RUNNING`, `DONE`, `FAILED` | CaseView UI 상태로 확정. JobExecution 상세 상태와 분리 |
| notices[].severity | `INFO`, `WARN`, `ERROR` | 표시 강도만 의미하며 실제 차단 여부는 `blocking`으로 별도 판단 |

**`info_state` 파생 규칙 — 확정 (B01 종결, 2026-09-07)**

입력은 모두 `EvidenceRecord`(`contract-evidence-record-needs.md` §3)에서 온다. `case`는 어느 입력도 재계산·재해석하지 않는다. 근거·기각안은 `adr/adr-data-contract-call-closure-2026-09-07.md` §4.1.

**(1) `EvidenceValue` 기반 display — `plate_display` · `location_display`**

```
1. value == null                        → INFO_UNKNOWN
2. user_corrected == true               → INFO_USER_CONFIRMED
3. needs_review == true                 → INFO_NEEDS_REVIEW
4. source.observability == OBSERVED     → INFO_SOURCE_VERIFIED
5. 그 외 (source.observability=INFERRED) → INFO_AI_ESTIMATED
```

2가 3보다 앞서는 것은 `core-user-flow.md` §9 「한 번 `사용자 확인됨`이 된 값은 다시 묻지 않는다」 때문이다. `needs_review`는 **`evidence`가 값과 함께 내려주는 `EvidenceValue.needs_review`**다. `evidence`가 「`user_corrected=true`와 `needs_review=true` 동시 발생 금지」·「`value=null`과 `needs_review=true` 동시 발생 금지」를 보장하므로(같은 계약 §10) 순서 규칙과 boolean이 어긋나는 조합은 생기지 않는다.

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
- **`thumb_ref` 이미지 전달 형태**(URL/ref/endpoint)는 recording 자산 계약 2건에서 정한다. `FrameRef` 필드 계약도 같은 자리다. 그 전까지 목데이터는 `docs/architecture/mock-pack-v1-refs.md`의 `fr_` 예시를 쓴다.
- **재판독 발주의 `JobRecord.kind`**(A절 §7) — case Owner 결정 대기(CALL-12).
- 최초 수락일 — Owner가 기억하지 못해 **확인 불가**로 유지한다(헤더).
- **별도 종결 항목 —** JobExecution → CaseView 상태 projection: `QUEUED→PENDING`, `RUNNING→RUNNING`, `SUCCEEDED→DONE`, `FAILED/STALE→FAILED`.
