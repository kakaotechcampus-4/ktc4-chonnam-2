# Final Data Contract — JobRecord (Job Intent) + CaseView v1

**Status:** `Final — Accepted`

**Accepted:** `2026-09-04`

**수락 근거:** §11 Consumer Review 반영 요약 — 신유민(web) 「수정요청 → 반영 완료」 · 김대원(eval) 「승인」 · 김준영 「최종 승인」. 3인 리뷰 종료. 헤더 표기만 누락돼 있어 PM이 채웠다(`adr/adr-consistency-2026-09.md` C1-13). 유소연 이견 시 되돌린다

**Architecture Contract:** v4 §5-1 ⑪ `CaseView` · ⑫ `JobRecord`

**Contract Version:** `job-record/v1` · `case-view/v1.1`

**Related ADR:** `adr/adr-job-record-case-view.md` · `adr/adr-consistency-2026-09.md` §6 R-1·R-2

> **`CaseView`는 v4에서 부록이 아니라 Core Contract ⑪이다**(v4 §5 머리말 · §4-모듈5 ⑥). 아래 절 제목의 「부록-A / 부록-B」는 ADR 작성 당시 표기이며, 계약의 위상은 Core Contract다.

> **`case-view/v1.1` 변경 (2026-09-06)** — 유소연(`case` Owner) 회신 반영. B절만 바뀌었고 A절 `JobRecord`는 `job-record/v1` 그대로다.
> ① `stage=READY` 정의 확정 ② `requirements.readiness`를 `RequirementReport.overall` 값 공간으로 축소 ③ `user_reviewed` 신규 ④ 세 값 display에 `info_state`·`source_label_key` 신규 ⑤ `requirements.scope` 신규(PM 확정 — ②를 반영하면서 드러난 후속 항목).
> **v1에서 확정된 항목은 하나도 되돌리지 않았다** — `progress[].state` · `notices[].severity` · `running_jobs[].label_key` · `package.*` 타입 · `evidence`의 `case_type_display`/`report_type_display`/`violation_display`/`preview_ref`는 §12 Closure 그대로다(`adr/adr-consistency-2026-09.md` §6 R-1 비고).

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

- `kind`: 확인된 값 `COARSE_SEARCH`, `PLATE_READ`. 전체 목록은 모듈 접두어 규칙에 따라 계속 등재 (닫힌 enum 아님)
- `force_rerun`: 기본값 `false`. `false`이고 동일 fingerprint의 기존 **성공(SUCCEEDED)** 결과가 있으면 재사용한다. `FAILED`/`STALE` 결과는 cache hit로 간주하지 않으며 재실행을 허용한다.

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
2. `force_rerun=false`이고 input_fingerprint가 동일한 **SUCCEEDED 결과**가 존재하면 그 결과를 재사용한다. `FAILED`/`STALE`은 재사용하지 않는다.
3. `scope_ref`가 존재하면 유효한 scope_id를 참조한다
4. 실행 상태 필드(status 등)는 본 계약에 포함되지 않는다 — Job Execution 계약 참고

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
- kind 표시용 `label_key`/fallback은 부록-B `CaseView` 계약에서 확정한다.

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

### 5. 확정 Contract 스키마 (JSON)

json

```json
{  "case_id": "string",  "case_rev": "int",  "stage": "INTAKE | SEARCHING | CANDIDATE_REVIEW | EVIDENCE_REVIEW | READY",  "user_reviewed": "boolean",  "manifest_summary": {    "file_count": "int",    "ok_file_count": "int",    "failed_file_count": "int",    "duration_sec": "number",    "range": "[string, string] | null"  },  "hints": { "time": "string|null", "vehicle": "string|null", "situation": "string|null", "location": "string|null" },  "progress": [ { "step": "string", "state": "PENDING | RUNNING | DONE | FAILED" } ],  "candidates": [    { "candidate_id": "string", "at": "string", "at_provenance": "string", "observed": "string", "thumb_ref": "string", "selected": "boolean" }  ],  "evidence": {    "record_id": "string",    "case_type_display": { "code": "string|null", "label": "string|null", "needs_review": "boolean" },    "report_type_display": { "code": "string|null", "label": "string|null", "needs_review": "boolean" },    "violation_display": { "code": "string|null", "label": "string|null", "needs_review": "boolean" },    "plate_display": { "value": "string|null", "needs_review": "boolean", "info_state": "INFO_AI_ESTIMATED | INFO_SOURCE_VERIFIED | INFO_USER_CONFIRMED | INFO_NEEDS_REVIEW | INFO_UNKNOWN", "source_label_key": "string|null" },    "event_time_display": { "value": "ISO8601|null", "needs_review": "boolean", "info_state": "INFO_AI_ESTIMATED | INFO_SOURCE_VERIFIED | INFO_USER_CONFIRMED | INFO_NEEDS_REVIEW | INFO_UNKNOWN", "source_label_key": "string|null" },    "location_display": { "value": "string|null", "needs_review": "boolean", "info_state": "INFO_AI_ESTIMATED | INFO_SOURCE_VERIFIED | INFO_USER_CONFIRMED | INFO_NEEDS_REVIEW | INFO_UNKNOWN", "source_label_key": "string|null" },    "user_edited": "boolean",    "preview_ref": "string|null",    "review_needed": "boolean",    "reason_code": "string|null"  },  "requirements": { "scope": "EVIDENCE | FINAL_PACKAGE", "readiness": "PASS | WARN | BLOCK | UNKNOWN", "checks": [] },  "package": {    "package_ref": "string|null",    "report_fields": "object<string, string|null>",    "artifact_ref": "string|null",    "capabilities": "string[]",    "warnings": "string[]"  },  "running_jobs": [ { "job_id": "string", "kind": "string", "label_key": "string", "status": "PENDING | RUNNING" } ],  "notices": [    { "code": "string", "severity": "INFO | WARN | ERROR", "blocking": "boolean", "message_key": "string", "actions": "string[]" }  ]}
```

> 위 evidence/package 필드는 CaseView의 **확정 safe projection 스키마**다. case는 Evidence/ReportPackage의 authoritative 값을 재판정하거나 confidence를 자체 threshold로 재해석하지 않고, 확정된 값·검토 필요 여부·사유를 UI 표시 형태로만 변환한다. raw confidence, 내부 provenance, 중간 추론값은 기본 노출하지 않는다.
> 

### 6. 필드 정의

| 필드 | 타입 | 필수 | 의미 | 상태 |
| --- | --- | --- | --- | --- |
| stage | enum(5) | Y | Case 진행 단계. `READY`는 「`PACKAGE_READY` 파생 gate가 성립한 시점」 | **확정** (신유민 Q3 답변 · READY 정의는 유소연 2026-09-06) |
| user_reviewed | boolean | Y | 사용자가 최종 확인을 마쳤는지. v4 §3-6의 `USER_REVIEWED`를 내려보내는 통로이며 `stage`와 **별개 축**이다 | **확정** (유소연 2026-09-06) |
| evidence.*_display.info_state | enum(5) | Y | 값의 정보 상태. `EvidenceValue`에서 결정론적으로 파생한다(§7) | **확정** (유소연·신유민 2026-09-06) |
| evidence.*_display.source_label_key | string \| null | Y | `EvidenceValue.source.kind`를 화면 라벨 키로 노출. web은 이 키로 문구를 고르고 `kind` 문자열을 직접 해석하지 않는다 | **확정** (유소연·신유민 2026-09-06) |
| requirements.scope | enum(2) | Y | 이 `requirements`가 어느 `RequirementReport`의 projection인지 | **확정** (PM 2026-09-06 · §7) |
| requirements.readiness | enum(4) | Y | 위 `scope`에 해당하는 `RequirementReport.overall`의 projection. case가 재계산하지 않는다 | **확정** (유소연 2026-09-06) |
| manifest_summary.ok_file_count / failed_file_count / duration_sec | int/int/number | Y | 파일 등록 성공·실패 수, 전체 구간 길이. count/duration은 항상 제공하고 정상 영상이 없으면 range=null | 확정 |
| evidence.* (projection 필드 전반) | object | 선택 | 화면 표시용 evidence 요약 | **확정** — safe projection 필드 |
| package.* | object | 선택 | 화면 표시용 package 요약 | **확정** — safe projection 필드 |
| notices[].code/severity/blocking/message_key/actions | string/string/bool/string/array | Y(배열은 빈 배열 허용) | 부분 실패/경고 표시 | 신규, 신유민 요청 반영 |
| progress[].state | string | Y | 단계 상태 | **확정** — `PENDING / RUNNING / DONE / FAILED` |

### 7. Enum / State / Special Value

| 필드 | 확정 값 | 비고 |
| --- | --- | --- |
| stage | `INTAKE`, `SEARCHING`, `CANDIDATE_REVIEW`, `EVIDENCE_REVIEW`, `READY` | 신유민 Q3 답변 기준 최종 확정. **`READY` = 「`PACKAGE_READY` 파생 gate가 성립한 시점」**(`contract-requirement-report-package.md` §5.2). `EVIDENCE_SUFFICIENT`는 `EVIDENCE_REVIEW` 단계 안의 조건이고 `USER_REVIEWED`는 `user_reviewed` 필드가 갖는다 |
| user_reviewed | `true`, `false` | v4 §3-6 `USER_REVIEWED`. `stage`와 별개 축이며 `stage=READY`가 아니어도 `true`일 수 있다 |
| requirements.scope | `EVIDENCE`, `FINAL_PACKAGE` | `RequirementReport.scope`와 **같은 값 공간**. 케이스 하나에 report가 둘 존재하므로(`contract-requirement-report-package.md` §5) 어느 쪽의 projection인지 밝힌다. `FINAL_PACKAGE` scope report가 존재하면 그것을, 없으면 `EVIDENCE` scope를 싣는다 |
| requirements.readiness | `PASS`, `WARN`, `BLOCK`, `UNKNOWN` | 위 `scope`에 해당하는 `RequirementReport.overall`과 **같은 값 공간**. `4/5` 같은 score 표현을 두지 않는다(`contract-requirement-report-package.md` §4 「단순 readiness score를 Contract에 두지 않는다」) |
| evidence.*_display.info_state | `INFO_AI_ESTIMATED`, `INFO_SOURCE_VERIFIED`, `INFO_USER_CONFIRMED`, `INFO_NEEDS_REVIEW`, `INFO_UNKNOWN` | `core-user-flow.md` §3-1의 정보 상태 5종과 1:1. **`Observation.status`와 다른 값 공간이므로 `INFO_` 접두어로 분리한다** — 파생 코드가 두 enum을 동시에 다루는 지점에서 `NEEDS_REVIEW`/`UNKNOWN`이 겹치는 것을 막는다(유소연 2026-09-06) |
| progress[].state | `PENDING`, `RUNNING`, `DONE`, `FAILED` | CaseView UI 상태로 확정. JobExecution 상세 상태와 분리 |
| notices[].severity | `INFO`, `WARN`, `ERROR` | 표시 강도만 의미하며 실제 차단 여부는 `blocking`으로 별도 판단 |

**`info_state` 파생 규칙 (결정론적, 위에서부터 먼저 맞는 것 하나)**

`case`는 아래 순서로만 판정하며 자체 threshold나 추가 정책을 넣지 않는다. 입력은 해당 값의 `EvidenceValue<T>`와 projection의 `needs_review`뿐이다.

```
1. value == null                        → INFO_UNKNOWN
2. user_corrected == true               → INFO_USER_CONFIRMED
3. needs_review == true                 → INFO_NEEDS_REVIEW
4. source.observability == OBSERVED     → INFO_SOURCE_VERIFIED
5. 그 외 (source.observability=INFERRED) → INFO_AI_ESTIMATED
```

2가 3보다 앞서는 것은 `core-user-flow.md` §3-1 「한 번 `사용자 확인됨`이 된 값은 다시 묻지 않는다」 때문이다.

`source.observability`는 `contract-evidence-record-needs.md`의 `EvidenceValue.source`가 소유한다. **`case`가 `source.kind` 문자열을 보고 관찰/추론을 스스로 분류하지 않는다** — 그건 `case`가 정책 판단을 하는 것이라 §3 「authoritative 판단을 재계산하지 않는다」에 걸린다.

`source_label_key`는 `source.kind`를 화면 라벨 키로 옮긴 값이며 키 네임스페이스는 `evidence`가 소유한다. 알 수 없는 kind는 `null`로 두고 web이 fallback 문구를 쓴다.

### 8. 정상 예시

json

```json
{  "case_id": "case_3", "case_rev": 4, "stage": "EVIDENCE_REVIEW", "user_reviewed": false,  "manifest_summary": { "file_count": 42, "ok_file_count": 40, "failed_file_count": 2, "duration_sec": 4680, "range": ["18:03", "19:21"] },  "hints": { "time": "18:30 전후", "vehicle": "흰색 SUV", "situation": "백색 실선 crossing 가능성", "location": "미금역 근처" },  "progress": [ { "step": "SCOPE", "state": "DONE" }, { "step": "COARSE", "state": "DONE" }, { "step": "FINE", "state": "RUNNING" } ],  "candidates": [ { "candidate_id": "c1", "at": "18:31:48", "at_provenance": "TIMELINE_ANCHOR+OFFSET", "observed": "백색 실선 + 흰 SUV가 선을 넘어 인접차로 진입", "thumb_ref": "frame:a09@178.6", "selected": true } ],  "evidence": {    "record_id": "ev_88",    "plate_display": { "value": "12가 3476", "needs_review": false, "info_state": "INFO_SOURCE_VERIFIED", "source_label_key": "plate.source.overlay_ocr" },    "event_time_display": { "value": "2026-08-24T18:31:48+09:00", "needs_review": false, "info_state": "INFO_SOURCE_VERIFIED", "source_label_key": "time.source.filename_time" },    "location_display": { "value": "미금역 사거리 인근", "needs_review": true, "info_state": "INFO_NEEDS_REVIEW", "source_label_key": "location.source.visual_inference" },    "review_needed": true,    "reason_code": "LOCATION_LOW_CONFIDENCE"  },  "requirements": { "scope": "EVIDENCE", "readiness": "WARN", "checks": [] },  "package": null,  "running_jobs": [ { "job_id": "job_52", "kind": "PLATE_READ", "label_key": "job.plate_read", "status": "RUNNING" } ],  "notices": []}
```

### 9. 실패 / 부분성공 / UNKNOWN 예시

json

```json
{  "case_id": "case_9", "case_rev": 2, "stage": "CANDIDATE_REVIEW", "user_reviewed": false,  "manifest_summary": { "file_count": 12, "ok_file_count": 10, "failed_file_count": 2, "duration_sec": 2400, "range": ["09:00", "09:40"] },  "hints": { "time": "아침 출근길", "vehicle": null, "situation": "신호위반 목격", "location": null },  "progress": [ { "step": "SCOPE", "state": "DONE" }, { "step": "COARSE", "state": "DONE" } ],  "candidates": [],  "evidence": null,  "requirements": null,  "package": null,  "running_jobs": [],  "notices": [    { "code": "PLATE_ABSTAINED", "severity": "WARN", "blocking": false, "message_key": "notice.plate_abstained", "actions": ["MANUAL_PLATE_INPUT"] }  ]}
```

### 10. 불변조건

1. `case_rev`는 반영 시점 리비전이며, 더 최신 case_rev 존재 시 stale
2. `evidence`/`package`가 선택/완료 이전이면 null
3. `package`가 non-null이면 `requirements.scope=FINAL_PACKAGE`이고 `requirements.readiness ∈ {PASS, WARN}`이다 (`contract-requirement-report-package.md` §5.2·§8.1의 Package 생성 조건과 같은 값)
9. `stage=READY`이면 `requirements.scope=FINAL_PACKAGE`다. `READY`가 `PACKAGE_READY` 파생 gate이고 그 gate는 `FINAL_PACKAGE` scope report로만 성립한다
4. `evidence`/`package`는 EvidenceRecord/ReportPackage의 원본 필드를 그대로 포함하지 않는다(safe projection만 포함)
5. `running_jobs`가 비어 있으면 진행 중인 작업 없음
6. `info_state`는 `case`가 독립적으로 판단하지 않고 항상 §7의 파생 규칙으로 `EvidenceValue`에서 결정론적으로 도출된다
7. `stage=READY`는 `PACKAGE_READY` 파생 gate가 성립한 시점이며, gate 자체는 `RequirementReport`/`ReportPackage`가 소유한다. `case`는 gate를 재계산하지 않는다
8. **`user_reviewed`(workflow) · `evidence.user_edited`(record 단위) · `info_state=INFO_USER_CONFIRMED`(필드 단위 `user_corrected` 파생)는 서로 다른 세 가지 사실이며 하나로 합치지 않는다.** `contract-time-resolution.md` §불변조건 5 「`user_corrected`는 `USER_REVIEWED` workflow 상태와 동일하지 않다」와 같은 구분이다

### 11. Consumer Review 반영 요약

| Consumer | 상태 | 반영 내용 |
| --- | --- | --- |
| 신유민(web) | 수정요청 → 반영 완료 | evidence/package safe projection 필드 확정, stage/progress enum 확정, manifest_summary/notices/running_jobs 표시 계약 보완 |
| 김대원(eval) | 승인 | 반영 사항 없음 |
| 김준영(evidence/PM) | 최종 승인 | safe projection 원칙, case의 재계산 금지, projection 필드 의미 경계 및 최종 스키마 승인 |
| 유소연(case Owner) · 신유민(web) | **v1.1 확정 (2026-09-06)** | CALL-1 A안 수용 + `INFO_` 접두어(유소연) · A안 채택과 `source_label_key` display별 배치(신유민) · CALL-5 (1)(2)(3) 확정(유소연). 김준영 이견 없음 |

### 12. Closure 완료 사항

- evidence/package: 위 스키마를 safe projection 최종안으로 확정. case는 authoritative 판단을 재계산하지 않는다.
- `progress.state`: `PENDING / RUNNING / DONE / FAILED`로 확정.
- `running_jobs.label_key`: 필수 제공. web은 `kind` 문자열을 직접 해석하지 않으며, 미등록/알 수 없는 kind는 `job.generic_processing` fallback을 사용한다.
- `notices.severity`: `INFO / WARN / ERROR`로 확정. 실제 차단 여부는 `blocking`이 결정한다.
- `manifest_summary`: file_count/ok_file_count/failed_file_count/duration_sec는 항상 제공하고, 정상 영상이 하나도 없으면 `range=null`을 허용한다.

**v1.1에서 추가로 닫힌 것 (2026-09-06)**

- `stage=READY`: `PACKAGE_READY` 파생 gate 성립 시점으로 확정. `ownership.md` §7-④가 「통합 전 case Owner가 확인한다」로 넘긴 미결이 닫혔다.
- `requirements.readiness`: `RequirementReport.overall`의 projection으로 확정하고 값 공간을 `PASS/WARN/BLOCK/UNKNOWN`으로 축소.
- `user_reviewed`: v4 §3-6 `USER_REVIEWED`를 내려보내는 통로 확정.
- `info_state` · `source_label_key`: 세 값 display에 추가하고 파생 규칙을 §7에 고정.
- `requirements.scope`: 어느 `RequirementReport`의 projection인지 밝히도록 필드 추가. **PM 확정**이며 소유자 이견 시 되돌린다(`adr/adr-consistency-2026-09.md` §6 R-7).

### 13. 남은 미결

- evidence/package projection의 세부 필드명 최종 합의 · `CorrectionRecord.target_field`와 display 필드명 정렬 → 같은 자리에서 처리한다.
- `candidates[].thumb_ref`의 형식. 예시가 `"frame:a09@178.6"`인데 2026-09-06에 `recording`이 **ref에 위치를 인코딩하지 않는다**로 확정했다(`adr/adr-consistency-2026-09.md` §6 R-5). 어느 자산의 ref인지(`fr_` / `da_`)는 `recording` 계약 2건이 나온 뒤 맞춘다. **목데이터는 `docs/architecture/mock-pack-v1-refs.md`를 쓴다.**

> **닫힌 항목:** `requirements`의 scope 미지정은 §7·§10-3·§10-9로 확정됐다(PM, 2026-09-06 — `adr/adr-consistency-2026-09.md` §6 R-7).
- JobExecution → CaseView 상태 projection: `QUEUED→PENDING`, `RUNNING→RUNNING`, `SUCCEEDED→DONE`, `FAILED/STALE→FAILED`.