# ADR-부록: JobRecord / CaseView

## ADR-부록A. `JobRecord` (Job Intent) 확정

### 1. Context

v1/v3의 `JobRecord`는 발주 의도(kind, input_fingerprint)와 실행 중 상태(status, attempt, cost, produced, failure_kind)가 한 row에 섞여 있었다. 반면 김준영의 Runtime/Ops 설계는 status/heartbeat/lease를 실행 중 갱신하는 mutable 모델을 전제해, "Job=추가만(append-only)" 원칙과 구조적으로 충돌했다. v4는 "Job Intent(case) / Job Execution(runtime) 분리" 방향만 제시하고 필드 단위 확정은 없는 상태였다. 이번 Draft에서 3개 설계 결정을 제시했고, 신유민(web)·김대원(eval)·김준영(evidence/runtime/PM) 리뷰를 거쳐 아래와 같이 확정한다.

### 2. Constraints (Draft §4 그대로 인용)

- Job=추가만(append-only) / View=파생 (v1 R&R 표)
- failure_kind는 모듈 접두어로 구분 (v1 p.20)
- input_fingerprint = hash(AnalysisScope 정규화값 + 활성 구현 이름표)
- corrections.kind는 JobRecord.kind와 다른 값 공간 (v1 p.28)
- JobRecord 예시에 scope_id 부재 (v3 §5-부록)

### 3. Alternatives considered

Draft §5의 결정1(A/B안), 결정2(A/B안), 결정3(A/B안+절충안) 그대로.

### 4. Final Decision

| 결정 항목 | Draft 추천 | 최종 결정 | 근거 |
| --- | --- | --- | --- |
| 결정1: Job Intent/Execution 분리 | B안 | **B안 확정** | 신유민 승인(Q5: "역할 분리에 동의함, web은 결합 결과만 받으면 됨"); 김준영 명시적 동의: "Job Intent(case)/Job Execution(common/runtime)은 책임을 분리하는 방향" |
| 결정2: force_rerun 플래그 | A안 | **A안 확정** | 김준영 명시적 동의: "fingerprint에 nonce를 섞기보다 force_rerun 등 명시적 cache bypass 값으로 표현하는 편이 이력 추적에 적합" |
| 결정3: kind 값 공간 | 절충안(모듈 접두어 자유 확장 + 문서 등재) | **절충안 유지 + 표시계층 보완 요구 추가** | 신유민 수정요청(Q3): kind 자체 구조 변경은 요구하지 않았으나, CaseView.running_jobs가 미등록 kind를 안전하게 표시할 방법(label_key 또는 fallback)이 필요 → 부록-B ADR로 이관 |
| 결정4 (Draft에 없던 신규 항목): scope_ref 추가 | — | **optional `scope_ref` 필드 신규 추가** | 신유민 수정요청(Q4): "동일 case_rev에서 범위 변경·재탐색 시 case_id/case_rev만으로는 실행 범위 구분이 어려울 수 있다" |

### 5. Consumer Review 반영 내역

- **신유민(web)**: Q3(kind 표시), Q4(scope 추적), 모두 수정요청 → 결정3 보완 요구는 부록-B로 이관, 결정4는 신규 필드로 직접 반영. Q5(Job Intent/Execution 분리)는 승인.
- **김대원(eval)**: "현재 추천안으로 case 구현 가능" — 승인, 별도 수정 없음.
- **김준영(evidence/runtime/PM)**: 결정1·결정2를 확정하고, 2026-09-04 백엔드 회의에서 `JobExecution`을 runtime/common 공통 영역으로 설계하되 주요 Owner는 김준영, 구현 담당은 정철원으로 확정했다. `JobRecord`의 Job Intent는 계속 case가 소유한다.

### 6. Contract summary

`JobRecord`는 **Job Intent**로 범위를 좁힌다: case가 "무엇을, 왜, 어떤 입력으로 요청했는지"만 append-only로 기록한다. 실행 상태(status/attempt/cost/produced/failure_kind)는 별도 **JobExecution** 레코드로 분리하며 runtime/common이 소유한다. 주요 Owner는 김준영, 구현 담당은 정철원이다. `JobExecution.status`는 `QUEUED / RUNNING / SUCCEEDED / FAILED / STALE`로 고정한다. heartbeat/lease/retry/backoff/DB 구조는 Runtime 구현 세부다. `force_rerun` 기본값은 `false`이며 `scope_ref`(optional)가 AnalysisScope와의 연결을 명시적으로 지원한다.

### 7. Invariants (갱신)

- 동일 (job_id) 재사용 없음(append-only)
- 동일 (case_id, kind, input_fingerprint, force_rerun=false) 조합에서 기존 `SUCCEEDED` 결과가 있으면 재사용한다. `FAILED`/`STALE` 결과는 cache hit로 간주하지 않는다.
- `force_rerun=true`인 요청은 input_fingerprint가 동일해도 새 Job Execution을 발생시킨다
- `scope_ref`가 존재하면 반드시 유효한 `AnalysisScope.scope_id`를 가리킨다

### 8. Consequences

**긍정**: Ops 문서의 mutable 모델과의 구조적 충돌 해소; case가 실행 디테일(재시도 타이밍, lease)을 몰라도 됨; scope_ref로 범위 변경 추적성 확보; force_rerun으로 캐시 우회 이력이 명시적으로 남음.

**비용**: JobExecution이 별도 공통 계약/구현으로 관리되어야 함(추가 작업); runtime/common에 실행 상태 관리 책임이 추가됨; case가 scope_id를 발주 시점에 보존하고 CaseView용 projection을 조립해야 함.

### 9. Rejected alternatives

- 결정1 A안(한 row에 intent+실행상태 유지): Ops 문서의 heartbeat/lease 모델 및 v4 분리 원칙과 정면 충돌 — 기각
- 결정2 B안(fingerprint에 nonce 삽입): "input_fingerprint=입력이 같다는 뜻"이라는 정의가 깨져 캐시 감사 시 혼란 유발 — 기각

### 10. Cross-contract impact

- `AnalysisScope`: scope_ref로 참조됨(신규)
- `CaseView.running_jobs`: `label_key` 필수 + 미등록 kind의 `job.generic_processing` fallback으로 확정(부록-B)
- 신규 `JobExecution` 계약: Producer/Owner는 runtime/common(주요 Owner 김준영), 구현 담당 정철원. status/attempt/cost/produced/failure_kind 이관 대상
- `CorrectionRecord.kind`: JobRecord.kind와 다른 값 공간이라는 점은 재확인만 하고 이번 결정 대상 아님

### 11. Mock/Impl/Eval impact

김대원(eval) 승인. Seed Mock/구현은 `JobExecution.status = QUEUED / RUNNING / SUCCEEDED / FAILED / STALE`를 사용할 수 있다. CaseView의 UI 상태는 부록-B의 별도 projection enum을 사용한다.

### 12. Change rules

- kind 신규값 추가 시 모듈 접두어 규칙을 따르고 계약 문서에 즉시 등재한다(절충안 유지)
- scope_ref, force_rerun은 이번 ADR로 스키마에 고정되며, 향후 삭제 시 별도 ADR 필요

### 13. Closure / 후속 구현 범위

1. `JobExecution` Producer/Owner: runtime/common, 주요 Owner 김준영, 구현 담당 정철원 — 2026-09-04 백엔드 회의 확정.
2. `JobExecution.status`: `QUEUED / RUNNING / SUCCEEDED / FAILED / STALE`로 확정. `CANCELLED`는 현재 제품 요구가 없어 포함하지 않는다.
3. `force_rerun=false`의 cache hit는 기존 `SUCCEEDED` 결과에만 적용한다. `FAILED`/`STALE`은 재실행 가능하다.
4. heartbeat/lease/retry/backoff/DB 구조는 Runtime 구현 세부이며 본 ADR의 추가 의사결정 사항이 아니다.
5. CaseView.running_jobs의 표시 계약은 부록-B에서 `label_key` + 공통 fallback으로 확정한다.

### 14. One-line 최종 결정

JobRecord는 Job Intent(case, append-only)로 범위를 좁히고, JobExecution은 runtime/common(주요 Owner 김준영, 구현 정철원)의 별도 계약으로 분리한다. `force_rerun` 기본값은 false, 성공 결과만 캐시 재사용하며, `scope_ref`를 optional 필드로 유지한다.

---

## ADR-부록B. `CaseView` 확정

### 1. Context

v1 원안은 `CaseView.evidence`를 `EvidenceRecord` "그대로"로 정의했으나, v4는 CaseView를 Core Contract로 승격하며 "safe projection, raw pass-through 금지" 원칙을 신설했다 — 두 문서가 정면으로 배치되는 지점이었다. 이번 Draft의 결정1로 이 문제를 제기했고, evidence 소유자이자 PM인 김준영이 원칙 차원에서 직접 답했다.

### 2. Constraints (Draft §4 그대로 인용)

- web은 요건을 재계산하지 않는다(v1 p.28)
- running_jobs는 이미 최소 필드만 노출
- checks[]는 RequirementReport 그대로(이미 확정, 이번 결정 대상 아님)

### 3. Alternatives considered

Draft §5 결정1의 A안(그대로 통과) / B안(safe projection).

### 4. Final Decision

| 결정 항목 | Draft 추천 | 최종 결정 | 근거 |
| --- | --- | --- | --- |
| evidence 통과 방식 | B안(safe projection) | **B안 확정** | 김준영(Evidence 소유자+PM) 명시적 확정: "raw pass-through 대신 safe projection 사용", "case는 authoritative 판단이나 RequirementReport 판정을 재계산하지 않고 projection만 수행". 신유민이 구체 필드 목록 제시(수정요청) |
| package 통과 방식 | Draft에서는 "재확인 필요"로 미결 | **evidence와 동일 원칙 적용, safe projection 확정** | 신유민 수정요청(Q5): package_ref+신고필드+artifact reference+capability+warning만 포함. 김준영의 일반 원칙과 정합 |
| stage enum | 5개 중 1개만 확인 | **5개 값 확정**: `INTAKE / SEARCHING / CANDIDATE_REVIEW / EVIDENCE_REVIEW / READY` | 신유민 Q3 명시적 답변 |
| progress.state enum | DONE/RUNNING만 확인 | **4개 값 확정**: `PENDING / RUNNING / DONE / FAILED` | CaseView UI 상태로 단순화하고 Runtime의 상세 JobExecution 상태와 분리 |
| manifest_summary 필드 | file_count+range만 | **확장 확정**: file_count/ok_file_count/failed_file_count/duration_sec/range | count/duration은 항상 제공, 정상 영상이 없으면 range=null 허용 |
| notices 필드 | 방향만, 필드명 미정 | **구조화 확정**: code/severity/blocking/message_key/actions | `severity = INFO / WARN / ERROR`; 실제 차단 여부는 별도 `blocking`이 결정 |

### 5. Consumer Review 반영 내역

- **신유민(web)**: Q2(evidence 필드 목록), Q3(stage/progress), Q4(manifest_summary/notices), Q5(package) 전부 수정요청 — 구체적 요구사항을 모두 위 표에 반영.
- **김대원(eval)**: 승인, 별도 의견 없음.
- **김준영(evidence/PM)**: evidence/package safe projection 원칙과 case의 재계산 금지를 확정하고, 최종 closure에서 신유민이 제안한 projection 필드명을 채택했다. case는 authoritative 값·검토 필요 여부·사유를 UI 형태로 변환만 하며 raw confidence/내부 provenance/중간 추론값은 기본 노출하지 않는다.

### 6. Contract summary

`CaseView.evidence`와 `CaseView.package`는 EvidenceRecord/ReportPackage를 그대로 노출하지 않고 case가 구성하는 **safe projection 객체**로 확정한다. `stage = INTAKE / SEARCHING / CANDIDATE_REVIEW / EVIDENCE_REVIEW / READY`, `progress.state = PENDING / RUNNING / DONE / FAILED`로 닫는다. `manifest_summary`와 `notices`는 확장안을 채택하고, `running_jobs`는 `label_key`를 필수 제공하며 미등록 kind에는 `job.generic_processing` fallback을 사용한다.

### 7. Invariants (갱신)

- `case_rev`는 반영 시점의 Case 리비전이며, 더 최신 case_rev 존재 시 stale로 간주
- `evidence`/`package`가 선택/완료 이전 단계면 반드시 null
- `package`가 non-null이면 `requirements.readiness`는 완료 상태여야 함
- **(신규)** `evidence`/`package`는 EvidenceRecord/ReportPackage의 원본 필드를 그대로 포함하지 않는다 — 반드시 case가 재구성한 projection 필드만 포함한다

### 8. Consequences

**긍정**: web/evidence 결합도 감소, evidence 내부 스키마 변경이 CaseView에 즉시 영향을 주지 않음, 화면에 필요한 상태(review_needed 등)가 명시적으로 드러남.

**비용**: case가 projection 로직과 Runtime→UI 상태 매핑을 구현해야 하며, projection 필드가 변경될 때 evidence와 case 간 계약 갱신이 필요하다.

### 9. Rejected alternatives

- evidence/package "그대로 통과"(A안): v4 safe projection 원칙 위반, evidence 스키마 변경 시 web이 직접 영향받는 결합 문제 — 기각(evidence 소유자 본인이 직접 기각에 동의)

### 10. Cross-contract impact

- `EvidenceRecord`/`ReportPackage`(evidence, Contract⑧ 등): projection의 authoritative source. CaseView는 재판정 없이 표시 형태만 변환한다.
- `JobRecord.kind`: CaseView.running_jobs는 `label_key`를 제공하며 web이 kind 문자열을 직접 해석하지 않는다. 미등록 kind는 `job.generic_processing`으로 표시한다.
- `JobExecution.status`: `QUEUED→PENDING`, `RUNNING→RUNNING`, `SUCCEEDED→DONE`, `FAILED/STALE→FAILED`로 CaseView UI 상태에 projection한다.

### 11. Mock/Impl/Eval impact

김대원 승인. Seed Mock/구현은 `progress.state = PENDING / RUNNING / DONE / FAILED`를 사용한다. Runtime 상세 상태는 CaseView에 그대로 노출하지 않고 위 projection 규칙을 따른다.

### 12. Change rules

- evidence/package projection에 필드 추가/변경 시 evidence(김준영)와 case가 합의 후 계약 갱신
- stage enum 5개 값은 이번 ADR로 고정, 변경 시 별도 ADR 필요

### 13. Closure 완료 사항

1. evidence/package safe projection의 필드명을 Final Data Contract의 스키마로 확정한다. case는 authoritative 값을 재계산하지 않는다.
2. `progress.state = PENDING / RUNNING / DONE / FAILED`로 확정한다.
3. `running_jobs.label_key`를 필수로 제공하고, 미등록/알 수 없는 kind는 `job.generic_processing` fallback을 사용한다.
4. `notices.severity = INFO / WARN / ERROR`로 확정하고 차단 여부는 `blocking`으로 분리한다.
5. `manifest_summary`의 count/duration은 항상 제공하고 정상 영상이 없으면 `range=null`을 허용한다.
6. Runtime 상태→CaseView 상태 매핑은 `QUEUED→PENDING`, `RUNNING→RUNNING`, `SUCCEEDED→DONE`, `FAILED/STALE→FAILED`로 고정한다.

### 14. One-line 최종 결정

`CaseView.evidence`/`package`는 safe projection으로 확정하고, case는 authoritative 판단을 재계산하지 않는다. `stage`와 `progress.state`, `running_jobs.label_key` fallback, notices severity, manifest_summary null 규칙까지 닫아 CaseView 계약의 미결사항을 해소한다.