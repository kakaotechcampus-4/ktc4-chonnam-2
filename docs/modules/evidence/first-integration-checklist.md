# 김준영 — 1차 Mock 통합 완료 체크리스트 (`evidence` + `common/runtime`)

> **이 문서가 하는 일:** 공용 Mock Pack(`data/mock/`, Seed v0)과 Final Data Contract를 기준으로, **1차 Mock E2E 통합(ownership.md §7-④) 전에 김준영 담당 영역이 어디까지 되어 있으면 "통합 가능한 상태"인가**만 정의한다.
> **이 문서가 하지 않는 일:** 내부 설계(클래스·함수 분리·DB·정책표 구현 방식·템플릿 문장)를 정하지 않는다. 그건 Tech Spec/구현 범위다.
> **기준일:** 2026-09-07 · **기준 브랜치:** `codex/fix-mock-pack-seed-consistency` (Mock 수정 PR 미머지 상태에서 착수)
> **기준 문서:** `architecture/contracts/contract-{observation,time-resolution,evidence-record-needs,requirement-report-package,job-execution,usage-record}.md` · `docs/mock/01`~`05` · `docs/mock/CONTRACT_CONFLICTS.md` · `management/ownership.md` · `architecture/module-architecture.md` §3-2·3-5·3-6·3-7 · §4-모듈4 · §6-2
> **주의:** Mock 수정(`c4fcbf0`, R1~R4)이 아직 `develop`에 머지되지 않았다. 이 체크리스트는 **수정 후 fixture**를 기준으로 쓴다. Mock이 다시 바뀌면 영향 범위는 §Contract별 완료 조건과 §Scenario별 완료 조건 두 절이며, 그때 해당 행만 고친다.
> **현재 이행 판정:** 체크박스는 acceptance baseline으로 보존한다. 2026-09-07
> 코드리뷰 항목별 수용·수정·Pending 및 실행 증빙은
> `first-integration-code-review-response-2026-09-07.md`를 따른다.

---

## 회의에서 먼저 볼 핵심 (5개)

이 5개를 먼저 보여준다. "구현 완료"라는 말은 하지 않는다.

1. **`scenario_happy_001`의 upstream fixture만 입력으로 넣어 evidence 산출물 5건을 실제 코드로 만든다.**
   `VisualEvidence`·`PlateReadout`·`OverlayTimeReadout`·`TimeSourceCandidate`·GPS `Observation` → `TimeResolution` → `EvidenceRecord` → `EvidenceNeeds` → `RequirementReport(FINAL_PACKAGE, WARN)` → `ReportPackage`. 출력이 `data/mock/evidence/*.happy_001.json`과 **구조가 동일**함을 나란히 보여준다.
2. **`scenario_partial_001`에서 "부분 성공"이 실패가 아니라는 것을 출력으로 보여준다.**
   `PlateReadout.abstained=true` + GPS `Observation.status=UNKNOWN`이 들어와도 → `occurred_at`은 확정되고, `EvidenceRecord`에 `vehicle_number`/`location` **키 자체가 없고**, `EvidenceNeeds.items=[PLATE_REREAD]`가 나오고, `RequirementReport.overall=BLOCK`이며 `ReportPackage`는 **의도적으로 만들지 않는다**.
3. **`BLOCK`과 `UNKNOWN`을 다르게 낸다.**
   같은 partial 리포트 안에서 번호판은 `BLOCK`(판정 성립, 진행 불가), 위치는 `UNKNOWN`(판정 자체 불성립)이고 `overall`은 precedence `BLOCK > UNKNOWN > WARN > PASS`로 `BLOCK`이 된다는 것을 checks 배열로 보여준다.
4. **`case`가 그대로 쓸 수 있는 `EvidenceNeeds`를 보여준다.**
   `PLATE_REREAD` / `would_fill=VEHICLE_NUMBER` / `optional=false` / `context_refs`에 `evidence.interval`+`evidence.target_hint`만 들어 있고 함수명·queue·threshold·retry가 **없다**는 것을 유소연 앞에서 확인한다.
5. **`UsageRecord` 원장과 `AnalysisRun.usage_summary`가 다시 어긋나지 않는다.**
   R1 회귀 방지 — 모듈 전용 `validate_evidence_impl.py`의 usage 연결 검증과 테스트의 aggregate assertion을 돌려 보인다. (`common/runtime` 계약 Owner 몫)

---

## 담당 범위

**Owner:** 김준영 (PM)

**주 담당 Module:** `evidence` — 증거 확정 / 신고 정책 / Package (`module-architecture.md` §4-모듈4)

**보조 담당 Module:** `common/runtime` (§6-2) — **계약 Owner**. `JobExecution` 구현 담당은 정철원(2026-09-04 백엔드 회의). 운영(경계 스크립트·CI·마스킹 로거)도 여기에 붙는다.

**Producer로 책임지는 Contract**

| Contract | 지위 | 실제 산출 주체 |
| --- | --- | --- |
| `TimeResolution` | Final · Producer=`evidence` | 나 |
| `EvidenceRecord` (`evidence-record/v1.1`) | Final · Producer=`evidence` | 나 |
| `EvidenceNeeds` (`evidence-needs/v1`) | Final · Producer=`evidence` | 나 |
| `RequirementReport` | Final · Producer=`evidence` | 나 |
| `ReportPackage` | Final · Producer=`evidence` | 나 |
| `UsageRecord` | Final · Producer=`common/runtime` | 나 (계약+구현) |
| `JobExecution` | Final · Producer=`common/runtime` | **계약만 나**, 구현 정철원 |
| `Observation<T>` | Final · **Contract Lead만 나** | Runtime Producer는 `recording`/`search`/`readout` |

> `Observation<T>`는 내가 **생산하지 않는다.** 계약 소유자로서 "값 공간·invariant가 지켜지는가"를 검수하고, 소비자로서 읽는다. 1차 통합에서 나는 이 계약의 **Consumer**로 행동한다.

**Consumer로 사용하는 Contract**

`Observation<T>`(GPS 등) · `VisualEvidence` · `CandidateEvent` · `PlateReadout` · `OverlayTimeReadout` · `TimeSourceCandidate` · `AssetSpan`/`SpanResolution`(구간 ref 수준) · `CorrectionRecord`(**Draft — 1차 통합에서 소비하지 않음**) · `case`가 주는 `case_ref`/`selection_rev`

**1차 통합에서 내 출력의 주요 Consumer**

- `case` (유소연) — `TimeResolution`·`EvidenceRecord`·`EvidenceNeeds`·`RequirementReport`·`ReportPackage` 전부의 **직접 Runtime Consumer**. `JobExecution.status`/`produced`도 읽는다.
- `web` (신유민) — 직접 읽지 않는다. `CaseView` safe projection 경유만.
- `eval` (김대원) — `UsageRecord`(비용 분모)·`JobExecution`(실행 성공률·latency). `evidence`를 import하지 않는다.
- `search` (서어진) — `AnalysisRun.usage_refs[]`에 내 `usage_id`를 넣는다.

**1차 통합에서 내가 의존하는 주요 Producer**

| Producer | Owner | 내가 받는 것 |
| --- | --- | --- |
| `readout` | 신유민 | `PlateReadout`(abstain 포함) · `OverlayTimeReadout`(검증 4항목) |
| `search` | 서어진 | `VisualEvidence`(visual_event_type·target association) · `CandidateEvent` |
| `recording` | 정철원 | `TimeSourceCandidate` · GPS `Observation` · 사건 구간 `AssetSpan` ref · (Package용) derived asset ref |
| `case` | 유소연 | `case_ref` · `selection_rev` · (v1 이후) `CorrectionRecord` |

### 담당 범위 확인 필요

임의로 결정하지 않고 표시만 한다.

- **`담당 범위 확인 필요`** — `JobRecord.kind`에 `OVERLAY_TIME_READ`가 필요한가. 현재 Mock은 "하나의 `PLATE_READ` Job이 `PlateReadout`+`OverlayTimeReadout` 두 `ReadoutRun`을 만든다"는 **임시 가정**으로 돌아간다(`CONTRACT_CONFLICTS.md` §4-3). `JobRecord`는 `case` 소유, `ReadoutRun.operation`은 `readout` 소유, 나는 `JobExecution` 계약 소유 — 세 명이 정해야 한다.
- **`담당 범위 확인 필요`** — `EvidenceValue.source.label_key` 네임스페이스는 계약상 `evidence`가 소유하지만, 그 키가 `CaseView.*_display.source_label_key`로 어떻게 흐르는지(B01)는 case/web 합의 대기다. 현재 Mock은 overlay 계열 키를 `null`로 두었다(R3).
- **`담당 범위 확인 필요`** — `JobExecution`의 계약(나)과 구현(정철원) 사이에서 **1차 통합의 목 queue 응답을 누가 내놓는가**가 문서에 없다. 정철원의 `resolve_span` 목 이후 순서라는 PM 제안은 확인 전이다(`ownership.md` §정철원 절).

---

## 1차 완료 정의

> 공용 Scenario `scenario_happy_001`·`scenario_partial_001`의 **upstream fixture(`VisualEvidence`/`PlateReadout`/`OverlayTimeReadout`/`TimeSourceCandidate`/GPS `Observation`/구간 ref)를 Contract 형식 그대로 입력으로 받아**, 시각 최종 판정·확정값 승격·부족분 계산·신고요건 판정·Package 조립을 수행하고, Final Data Contract에 맞는 **`TimeResolution`·`EvidenceRecord`·`EvidenceNeeds`·`RequirementReport`·`ReportPackage`** 를 생성할 수 있으며, ABSTAIN/UNKNOWN/BLOCK Scenario에서도 **없는 값을 만들지 않고 필드 부재·`UNKNOWN`·`BLOCK`·Package 미생성으로 구분해 보존**하고, `common/runtime` 쪽으로는 `JobExecution`·`UsageRecord`가 계약 스키마와 aggregate 정합을 만족하는 형태로 존재하며, Merge 회의에서 `case`(유소연)가 **그 출력 JSON을 그대로 파싱해 `CaseView`를 만들 수 있음**을 실행 결과와 fixture 대조로 제시할 수 있으면 1차 완료로 본다.

---

## 구현 체크리스트

### A. Input

- [ ] `PlateReadout`을 Contract 형식(`data/mock/readout/plate_readout.*.json`)으로 로드해 `abstained` 값을 읽을 수 있다.
- [ ] `OverlayTimeReadout`을 Contract 형식으로 로드해 검증 결과와 판독 시각을 읽을 수 있다.
- [ ] `VisualEvidence`를 Contract 형식으로 로드해 `visual_event_type`과 `target.association_status`를 읽을 수 있다.
- [ ] `TimeSourceCandidate`(recording)를 시간 후보로 로드할 수 있다.
- [ ] GPS `Observation<T>`를 로드하고 `status=UNKNOWN` + `value=null`을 값 부재로 해석한다(오류로 해석하지 않는다).
- [ ] 사건 구간을 `AssetSpan` opaque ref(`sa_h001_01:690.0-708.0` 형태)로만 받아 통과시킬 수 있다 — 자산 metadata를 lookup하지 않는다.
- [ ] `case`가 주는 `case_ref`와 `selection_rev`를 필수 입력으로 받는다.
- [ ] Optional 입력(GPS 부재·`location` 단서 없음·`plate_image` 없음)이 빠져도 처리가 중단되지 않는다.
- [ ] `CorrectionRecord`는 **입력으로 요구하지 않는다** (Draft — 1차 범위 밖).
- [ ] 입력을 `data/mock/`의 파일에서 읽든 함수 인자로 받든, **다른 모듈의 내부 객체를 import하지 않는다**.

### B. Core Flow

- [ ] Happy 입력에서 `TimeResolution` → `EvidenceRecord` → `EvidenceNeeds` → `RequirementReport` → `ReportPackage` 순서로 한 번에 산출물 5건을 만들 수 있다.
- [ ] Partial 입력에서 같은 흐름이 `RequirementReport(BLOCK)`까지 가고 `ReportPackage`에서 멈춘다.
- [ ] Timestamp 선택이 **검증된 Overlay 우선 → filename/metadata 비교 → USER_INPUT → UNKNOWN** 순서(§3-2, `contract-time-resolution.md` §4)를 따르며, 이 우선순위가 내 모듈 안에만 있다.
- [ ] `visual_event_type` → `safety_report_type` → `violation_expression` 세 값을 각각 별도로 만든다(§3-5).
- [ ] `EVIDENCE_SUFFICIENT`/`PACKAGE_READY`를 저장 필드로 만들지 않고 `RequirementReport.scope + overall`에서 파생 gate로만 계산한다.
- [ ] 신고문(`report.title`/`report.description`)을 고정 template + 확정 Evidence로 결정론적으로 만든다 — LLM 호출 없음, `template_ref` 보존.

### C. Output Contract

- [ ] 모든 산출물에 올바른 `contract_version` 문자열이 들어간다 (`time-resolution/v1`, `evidence-record/v1.1`, `evidence-needs/v1`, `requirement-report/v1`, `report-package/v1`).
- [ ] 모든 산출물이 자기 식별자를 `ContractRef` 형태로 갖는다 (`resolution_ref`/`record_ref`/`requirement_report_ref`/`package_ref`) — evidence 계열은 자기 ID도 `*_ref`라는 관례를 지킨다.
- [ ] `EvidenceNeeds.basis_record_ref`가 같은 실행에서 만든 `EvidenceRecord.record_ref`를 가리킨다.
- [ ] `RequirementReport.basis.evidence_record_ref`가 존재하고, `scope=FINAL_PACKAGE`이면 `basis.asset_refs`가 비어 있지 않다.
- [ ] `ReportPackage`가 `evidence_record_ref`와 `requirement_report_ref`를 둘 다 가진다.
- [ ] 모든 시각 필드가 **offset-aware RFC3339**다 (`+09:00`).
- [ ] `TimeResolution.resolved.computation.timezone.source`가 `SOURCE_EXPLICIT`/`PRODUCT_CONTEXT` 중 실제 근거에 맞는 값이다.
- [ ] `EvidenceValue.source`에 `kind`·`observability`(`OBSERVED`/`INFERRED`)·`label_key`(없으면 `null`)·`user_corrected`가 모두 들어간다.
- [ ] enum 값을 계약 문자열 그대로 쓴다 — `OK/NEEDS_REVIEW/UNKNOWN`(TimeResolution), `PASS/WARN/BLOCK/UNKNOWN`(Requirement), `EVIDENCE/FINAL_PACKAGE`(scope), `OVERLAY_TIME_OCR/PLATE_REREAD`(Need kind), `DOWNLOAD_ASSETS/COPY_FIELDS/OPEN_DESTINATION`(handoff).
- [ ] `RequirementCheck`는 `code`·`category`·`outcome`·`reason_code`를 모두 갖고 같은 Report 안에서 `code`가 중복되지 않는다.
- [ ] `provenance.policy_ref`(그리고 Package는 `report.template_ref`)를 항상 채운다.

### D. Failure / Uncertainty

- [ ] `PlateReadout.abstained=true`일 때 **확정 번호판 값을 만들지 않는다** — `EvidenceRecord.vehicle_number` 키가 아예 없다.
- [ ] GPS `Observation.status=UNKNOWN`일 때 좌표를 생성하지 않는다 — `location.coord`를 만들지 않는다.
- [ ] 위치 근거가 사용자 기억 단서뿐이면 `location.user_hint`로만 보존하고 `address`/`place_name`으로 승격하지 않는다 (R2).
- [ ] `TimeResolution.status=UNKNOWN`일 때 `resolved`를 만들지 않고, `EvidenceRecord.occurred_at`도 만들지 않는다.
- [ ] `RequirementReport`에서 `BLOCK`(판정 성립·진행 불가)과 `UNKNOWN`(판정 불성립)을 다른 check outcome으로 낸다.
- [ ] `overall`을 precedence `BLOCK > UNKNOWN > WARN > PASS`로 계산한다.
- [ ] `overall ∈ {BLOCK, UNKNOWN}`이면 `ReportPackage`를 만들지 않는다. 빈 Package·status 필드 붙은 Package를 만들지 않는다.
- [ ] `overall=WARN`이어도 `ReportPackage`를 만든다 (Happy 시나리오의 핵심 불변조건).
- [ ] `EvidenceNeeds.items=[]`을 "신고 가능"으로 해석하지 않는다 — Happy 시나리오가 `items=[]`이면서 `readiness=WARN`이다.
- [ ] Requirement engine 실행 자체가 실패하면 `overall=ERROR`를 만들지 않고 **Report를 생성하지 않는다**.
- [ ] `Observation.status=OK + 빈 값`(known-empty)을 `UNKNOWN`과 같게 처리하지 않는다.

### E. State / Lifecycle

- [ ] 모든 산출물을 immutable value로 취급한다 — 재계산 시 in-place 수정하지 않는다.
- [ ] 재평가·재조립 시 새 `*_ref`를 만들고 `supersedes_ref`로 이전 결과를 가리킬 수 있다(1차에서는 **경로만 존재하면 됨**, 실제 rerun 시나리오는 범위 밖).
- [ ] `EvidenceRecord`가 하나의 `case_ref` + `selection_rev`에 묶인다.
- [ ] `EvidenceNeeds`를 지연 발주할 때 `basis_record_ref`가 current Record가 아니면 stale로 판정할 수 있는 근거를 출력에 남긴다.
- [ ] `USER_REVIEWED`·`SUBMITTED`·`stage`·`running_jobs` 같은 workflow 상태를 내 산출물에 넣지 않는다.

### F. Integration

- [ ] 내 5개 산출물이 **`case`가 파일/함수 반환값으로 그대로 읽을 수 있는 JSON**이다 (내부 dataclass 강제 없음).
- [ ] `case`가 `CaseView.requirements.{scope,readiness}`와 `package`를 내 출력만으로 채울 수 있다.
- [ ] `case`가 `notices`(`PLATE_ABSTAINED`/`LOCATION_UNKNOWN`)를 만들 근거가 내 출력 안에 있다 — `EvidenceNeeds.why.code`, `RequirementCheck.reason_code`.
- [ ] Mock 입력 ↔ 실제 upstream 구현 입력을 **같은 Contract 형식**으로 받아 교체할 수 있다(입력 경로만 바뀌고 처리 코드가 안 바뀐다).
- [ ] `evidence/`에서 `ffmpeg`·프롬프트·`import search`/`import readout` 검색 결과가 0건이다 (`ownership.md` §6 grep 목록).
- [ ] `evidence`가 다른 모듈 함수를 호출하지 않는다 — 필요한 추가 작업은 `EvidenceNeeds` 값으로만 반환한다.

### G. Test / Evaluation

- [ ] `scenario_happy_001` 입력 → 출력 5건을 검증하는 테스트가 있다.
- [ ] `scenario_partial_001` 입력 → 출력 4건(+Package 미생성)을 검증하는 테스트가 있다.
- [ ] "ABSTAIN이면 `vehicle_number` 키 부재"를 단독으로 검증하는 테스트가 있다.
- [ ] "`overall=WARN`이면 Package 생성 / `BLOCK`이면 미생성"을 검증하는 테스트가 있다.
- [ ] `overall` precedence 4가지 조합(PASS/WARN/UNKNOWN/BLOCK)을 검증하는 테스트가 있다.
- [ ] 계약 enum 문자열 오타를 잡는 검증이 있다(직접 assertion이든 schema든).
- [ ] `python scripts/validate_evidence_impl.py`가 내 산출물(실제 코드 출력)에 대해서 0 error로 통과한다.
- [ ] `eval`이 쓰는 `UsageRecord` 필드(`processed_duration_sec`·`latency_ms`·`cost`·`case_id`)가 실제로 채워진 예시가 있다.

### H. Operational

1차 통합에 실제로 필요한 것만.

- [ ] `UsageRecord`가 호출 1건당 1 row로 append-only이며 `total_tokens == input + output`을 만족한다.
- [ ] `token_usage`를 제공하지 않는 provider는 객체 전체를 `null`로 둔다 (0으로 채우지 않는다).
- [ ] `JobExecution.status`↔`started_at`/`ended_at` 관계 불변조건이 지켜진다 (`QUEUED`→`started_at=null`, `{QUEUED,RUNNING}`→`ended_at=null`).
- [ ] `JobExecution.usage_refs[]` ↔ `UsageRecord.execution_ref`가 양방향으로 맞는다.
- [ ] 마스킹 로거가 번호판 문자열·정확한 GPS·원본 frame·외부 API payload 전문을 남기지 않는다 (§8-5).
- [ ] `UsageRecord`에 사용자 이름·연락처·번호판·GPS 좌표가 들어가지 않는다.
- [ ] `scripts/check_boundaries.py`가 FAIL 0건이다.

---

## Contract별 완료 조건

### `TimeResolution`

- [ ] Happy/Partial 두 입력 모두에서 `status=OK` + `resolved` + `provenance.selected_input_ref`를 갖는 Artifact를 만든다.
- [ ] `considered[]`에 채택된 overlay와 기각된 filename 후보가 둘 다 있고, 기각 쪽에 `used=false` + `reason_code`가 있다.
- [ ] `considered[]`가 원본 Observation의 diagnostics/raw confidence/frame payload를 복제하지 않는다.
- [ ] `conflict.exists=false`일 때 `between_refs=[]`이다. 충돌 케이스를 만든다면 `resolved`가 있으면서 `conflict.exists=true`도 허용된다는 것을 알고 있다.
- [ ] numeric confidence 필드를 만들지 않는다.
- [ ] `post_stamp`를 `needed`/`reason_code`/`requires_user_notice`만으로 표현하고 Report Video 생성 상태와 섞지 않는다.
- [ ] `USER_INPUT` 경로는 **구조만 열어두고 1차에서는 사용하지 않는다** (`CorrectionRecord` Draft).

### `EvidenceRecord` (`v1.1`)

- [ ] Happy: `event` 3값 + `occurred_at` + `vehicle_number` + `location.user_hint`가 있는 Record를 만든다.
- [ ] Partial: 같은 코드가 `vehicle_number`와 `location` **키 없이** Record를 만든다 — placeholder·`null`·`"UNKNOWN"` 문자열을 만들지 않는다.
- [ ] `occurred_at`이 있으면 `time_resolution_ref`가 있고 `resolution_status ∈ {OK, NEEDS_REVIEW}`다 (`UNKNOWN` 금지).
- [ ] 모든 `EvidenceValue.source.observability`가 실제 출처에 맞다 — 화면/메타데이터/GPS 유래는 `OBSERVED`, 정책 매핑·사용자 단서 유래는 `INFERRED`.
- [ ] `basis`의 3개 ref(`candidate_ref`·`visual_evidence_ref`·`evidence_interval_ref`)가 모두 채워진다.
- [ ] `provenance.input_refs`에 실제로 사용한 upstream ref만 들어간다.
- [ ] Requirement severity·`PACKAGE_READY`·`USER_REVIEWED`를 Record에 넣지 않는다.

### `EvidenceNeeds`

- [ ] Happy에서 `items=[]`인 Artifact를, Partial에서 `items=[PLATE_REREAD]`인 Artifact를 만든다.
- [ ] `kind`가 `OVERLAY_TIME_OCR`/`PLATE_REREAD` 2개로 닫혀 있고 `would_fill` 매핑을 어기지 않는다.
- [ ] `PLATE_REREAD`의 `context_refs`에 `evidence.interval`이 반드시 있고, 가능하면 `evidence.target_hint`가 있다.
- [ ] `context_refs`에 path·prompt·threshold·retry·timeout·queue priority가 **없다**.
- [ ] `why.code`가 machine-readable stable code다 (`evidence.vehicle_number.unconfirmed` 등).
- [ ] `optional=false`를 Requirement `BLOCK`과 같은 뜻으로 쓰지 않는다.
- [ ] `POST_STAMP`/`REPORT_VIDEO`/`EXPORT`를 kind로 만들지 않는다.

### `RequirementReport`

- [ ] Happy에서 `scope=FINAL_PACKAGE` + `overall=WARN` Artifact를, Partial에서 `scope=EVIDENCE` + `overall=BLOCK` Artifact를 만든다.
- [ ] 두 scope가 같은 check 구조를 쓰되 **서로 다른 gate**로 동작한다.
- [ ] "번호판 문자열 확정"과 "신고영상에서 번호판 식별 가능"을 **다른 check**로 둔다(§4-모듈4 ④). 1차에서 후자를 판정할 근거가 없으면 `UNKNOWN`으로 낸다.
- [ ] "사건시각 확정"과 "영상 내 시각 표시"도 다른 check다.
- [ ] `evaluated_at`이 필수이고, 기한 계열 rule은 이 시점을 기준으로 계산한다.
- [ ] `measurement`가 필요한 check(용량·글자수·기한)를 낼 경우 `actual`/`unit`을 갖추고, 한도 숫자는 `policy_ref`가 소유한다.
- [ ] check가 하나도 없는 Report를 정상으로 취급하지 않는다.

### `ReportPackage`

- [ ] Happy에서만 Artifact가 존재하고 Partial에서는 **파일 자체가 없다**.
- [ ] `report_inputs` 5개 값(`safety_report_type`·`occurred_at`·`location`·`vehicle_number`·`violation_expression`)이 확정 Evidence의 snapshot이다.
- [ ] `report.title`/`description`이 고정 template 결과이고 `template_ref`가 보존된다.
- [ ] `assets.report_video_ref`가 derived asset ref이고 원본 `source_asset`과 구분된다. `plate_image_ref`는 확보된 경우에만 넣는다.
- [ ] `provenance.source_refs`와 `derived_asset_refs`가 분리되어 있다.
- [ ] `handoff.supported_actions`가 3값 안에서만 나오고, 신고자 개인정보·인증·제출 상태가 없다.
- [ ] `BUILDING`/`READY`/`ERROR` 같은 status 필드를 만들지 않는다.
- [ ] **`Contract 변경 검토 필요`** — Happy Package의 신고문에 있는 `흰색 SUV`는 confirmed `EvidenceRecord`에 대응 필드가 없어 재생성이 불가능하다(`05_kim_junyoung_mock_review` §6). 1차에서는 **차량 묘사를 template에서 생략**하거나 사용자 hint임을 명시하는 쪽으로 낸다.

### `Observation<T>` (계약 Owner — Producer 아님)

- [ ] 세 Producer가 낸 Observation이 status↔value invariant를 지키는지 검수한 결과를 말할 수 있다 (`OK`→값 존재, `UNKNOWN/ERROR/NOT_APPLICABLE`→`null`).
- [ ] `source.kind`에 provider/model 이름이 들어간 사례가 0건임을 확인했다.
- [ ] `ABSTAIN`이 Observation status로 올라오지 않았음을 확인했다 (`NEEDS_REVIEW` + `PlateReadout.abstained=true`).
- [ ] **`Contract 변경 검토 필요` / Pending B03** — `Observation.produced_by.run_ref`를 `ReadoutRun`에 연결하는 규칙은 1차에서 만들지 않는다.

### `JobExecution` (계약 Owner · 구현 정철원)

- [ ] 계약 스키마 9필드가 Mock fixture에서 그대로 재현되고, 구현 담당(정철원)이 같은 스키마로 목 queue 응답을 낼 수 있음을 확인했다.
- [ ] `status` 5값과 허용 전이가 문서로 닫혀 있고, `case`가 `SUCCEEDED`가 아닌 `produced`를 반영하지 않는다는 규칙을 유소연이 알고 있다.
- [ ] **통합 대기** — domain `PARTIAL` ↔ runtime `status` 접합(W04)은 이번에 정하지 않는다.

### `UsageRecord`

- [ ] Happy/Partial 두 시나리오의 usage row가 `execution_ref`·`case_id`·`pricing_context`를 갖는다.
- [ ] `AnalysisRun.usage_summary`의 duration/token/cost가 참조된 row들의 aggregate와 일치한다 (R1).
- [ ] token 미제공 provider row에서 `token_usage=null`이다.
- [ ] **통합 대기 / Pending B05** — `ReadoutRun`을 `run_ref`로 연결하는 정책은 만들지 않고 `run_ref=null`을 유지한다.

---

## Scenario별 완료 조건

공용 Scenario ID만 쓴다. 새 Scenario를 만들지 않는다.

| Scenario | 내 입력 | 내가 해야 할 처리 | 기대 출력 | 완료 기준 |
| --- | --- | --- | --- | --- |
| `scenario_happy_001` | `OverlayTimeReadout`(OK, 검증 4항목 true) · `TimeSourceCandidate`(filename) | 검증된 Overlay 우선 채택, filename 후보 기각 사유 보존 | `TimeResolution(tres_h001)` | `status=OK` · `verification=VERIFIED` · `considered[]` 2건 중 filename에 `used=false`+`reason_code` |
| `scenario_happy_001` | `VisualEvidence(ve_h001)` · `PlateReadout`(비abstain) · GPS `Observation(UNKNOWN)` · 사용자 hint "미금역 근처" | 확정값 승격 + 정책 매핑 | `EvidenceRecord(ev_h001)` | 번호판·시각 확정, 위치는 `user_hint`만(주소 생성 금지), `observability` 전 필드 채움 |
| `scenario_happy_001` | 위 Record | 부족분 계산 | `EvidenceNeeds` | `items=[]` — 그러나 이것을 "신고 가능"으로 표현하지 않는다 |
| `scenario_happy_001` | Record + derived asset ref | 신고요건 판정 | `RequirementReport(req_h001)` | `scope=FINAL_PACKAGE` · `overall=WARN` · 위치 check가 `WARN`(`location.user_hint_needs_review`) |
| `scenario_happy_001` | WARN Report | Package 조립 | `ReportPackage(pkg_h001)` | **WARN인데도 Package 생성** · `report_inputs` 5값 · `template_ref` 보존 |
| `scenario_happy_001` | 2건의 `JobExecution`, 3건의 `UsageRecord` | 원장 정합 | usage aggregate | `AnalysisRun.usage_summary`와 duration/token/cost 일치 |
| `scenario_partial_001` | `OverlayTimeReadout`(OK) | 시간은 성공 처리 | `TimeResolution(tres_p001)` | `status=OK` — **번호판 실패가 시간 판정을 오염시키지 않는다** |
| `scenario_partial_001` | `PlateReadout(abstained=true, FRAME_DISAGREEMENT)` · GPS `Observation(UNKNOWN)` · 위치 힌트 없음 | 미확정 값을 만들지 않음 | `EvidenceRecord(ev_p001)` | `vehicle_number`·`location` **키 부재** · `occurred_at`은 존재 |
| `scenario_partial_001` | 위 Record | 부족분 계산 | `EvidenceNeeds` | `items=[PLATE_REREAD]` · `would_fill=VEHICLE_NUMBER` · `optional=false` · `context_refs` 2건 |
| `scenario_partial_001` | 위 Record (asset 없음) | 신고요건 판정 | `RequirementReport(req_p001)` | `scope=EVIDENCE` · 번호판 `BLOCK` + 위치 `UNKNOWN` + 시각 `PASS` · `overall=BLOCK` |
| `scenario_partial_001` | BLOCK Report | Package 미생성 | (출력 없음) | `ReportPackage` 파일이 **존재하지 않음**. 빈 객체·에러 객체를 만들지 않는다 |
| `scenario_partial_001` | — | Case 전체 생존 | `case`가 만드는 `CaseView` | `stage=EVIDENCE_REVIEW`(에러 화면 아님) · `readiness=BLOCK` · `package=null` · `notices=[PLATE_ABSTAINED, LOCATION_UNKNOWN]`이 내 출력만으로 도출 가능 |

**이번 1차에서 참여하지 않는 공용 Scenario 유형**: B(결과 없음)·F(사용자 확인·수정)·I(재실행). Seed Pack에 대표 Scenario가 없다(`02_mock_scenario_catalog.md`). 내가 임의로 만들지 않는다.

---

## Merge 전 셀프 체크 증빙

"구현했습니다"로는 통과하지 않는다. 아래 파일/출력을 실제로 들고 간다.

- [ ] **정상 입력 예시** — Happy 실행에 넣은 upstream fixture 경로 목록 (`data/mock/{readout,search,recording}/*.happy_001.json`)
- [ ] **정상 출력 JSON 5건** — 내 코드가 만든 `TimeResolution`/`EvidenceRecord`/`EvidenceNeeds`/`RequirementReport`/`ReportPackage`
- [ ] **기존 fixture와의 diff** — 위 5건 vs `data/mock/evidence/*.happy_001.json` (구조 차이 0, 값 차이는 설명 가능해야 함)
- [ ] **ABSTAIN/UNKNOWN 출력 JSON 4건** — Partial 실행 결과 + `ReportPackage`가 **없다는 사실**을 보여주는 실행 로그 한 줄
- [ ] **BLOCK vs UNKNOWN 대조** — `requirement_report.partial_001`의 checks 배열을 화면에 띄워 두 outcome의 의미 차이 설명
- [ ] **테스트 실행 결과** — Happy/Partial 시나리오 테스트 + precedence 테스트 pass 출력
- [ ] **`python scripts/validate_mock_pack.py` 출력** — `오류(ERROR): 0 / 경고(WARN): 0`
- [ ] **`python scripts/validate_evidence_impl.py` 출력** — 실제 Evidence 구현 `오류(ERROR): 0`
- [ ] **`python scripts/check_boundaries.py` 출력** — `FAIL 0건`
- [ ] **경계 grep 결과** — `evidence/`에서 `ffmpeg`·프롬프트·`import search`/`import readout` 0건
- [ ] **마스킹 로거 로그 예시** — 번호판·GPS가 남지 않는 것을 보여주는 실제 로그 라인
- [ ] **usage 원장 정합 출력** — `AnalysisRun.usage_summary` ↔ `UsageRecord` aggregate 비교 결과

불필요해서 넣지 않는 것: 화면 캡처(web은 신유민), Eval 지표 결과(김대원), latency/비용 실측(1차 범위 밖 — 형식만 보증).

---

## Merge 전 확인 질문

회의 전에 스스로 답할 수 있어야 한다.

1. `scenario_happy_001`의 upstream fixture가 들어오면 내 5개 출력의 어떤 필드가 어떤 값이 되는지, 문서를 안 보고 흐름으로 설명할 수 있는가?
2. `case`(유소연)가 내 출력 중 **정확히 어떤 필드**를 읽어 `CaseView.requirements`·`package`·`notices`를 만드는지 말할 수 있는가?
3. `PlateReadout.abstained=true`가 들어와도 `occurred_at`·`visual_event_type`·선택된 후보가 살아 있는가? 그 근거가 코드의 어느 분기인가?
4. `BLOCK`과 `UNKNOWN`을 내가 실제로 다르게 쓰고 있는가? 같은 상황에서 둘 중 무엇을 낼지 판단 기준을 한 문장으로 말할 수 있는가?
5. `overall=WARN`인데 `ReportPackage`를 만드는 것이 왜 정상인지, 그리고 이것이 Happy 시나리오의 핵심 검증 지점인 이유를 설명할 수 있는가?
6. 실제 구현이 아직 없는 부분(`CorrectionRecord` 경로, `plate_visible_in_evidence` 판정 근거, derived asset metadata)이 각각 어떤 Mock/`UNKNOWN`으로 대체되고 있는지 목록으로 말할 수 있는가?
7. 내 코드가 `search`/`readout`/`recording`의 내부 클래스를 직접 import하지 않고 Contract 형식 JSON만 받는가? grep으로 증명할 수 있는가?

---

## 접합부 확인 (Merge 회의에서 상대와 같이 볼 것)

| 접합 상대 | 확인 Contract | 내 역할 | 상대 역할 | Merge에서 확인할 것 |
| --- | --- | --- | --- | --- |
| `readout` (신유민) → 나 | `PlateReadout` · `OverlayTimeReadout` | Consumer | Producer | `abstained=true`인데 `ReadoutRun.outcome=SUCCEEDED`라는 의미를 양쪽이 같게 읽는가 · 나는 abstain을 실행 실패로 처리하지 않는가 · overlay 검증 4항목을 내가 `verification=VERIFIED` 근거로 쓰는 방식에 합의하는가 |
| `search` (서어진) → 나 | `VisualEvidence` · `CandidateEvent` | Consumer | Producer | `visual_event_type` 값 공간이 `SIGNAL`/`CENTER_LINE_CROSSING`/`SOLID_LINE_LANE_CHANGE`/`MOTORCYCLE_HELMET_NON_USE`로 같은가 · `target.association_status=AMBIGUOUS`를 내가 어떤 check로 반영하는가 · `usage_refs[]`에 내 `usage_id`가 들어가는가 |
| `recording` (정철원) → 나 | `TimeSourceCandidate` · `AssetSpan`/`SpanResolution` · GPS `Observation` | Consumer | Producer | 시간 후보가 verification까지 주는가 raw만 주는가 · 사건 구간 ref 문자열 형식이 같은가 · `SpanResolution.status=PARTIAL`이 내 Requirement에 어떻게 들어오는가 (**1차에서는 opaque ref까지만**) |
| 나 → `case` (유소연) | `TimeResolution`·`EvidenceRecord`·`EvidenceNeeds`·`RequirementReport`·`ReportPackage` | Producer | Consumer | 같은 `case_ref`/`selection_rev` 사용 · `EvidenceNeeds`를 `JobIntent`로 번역하는 규칙 · `optional=false`가 자동 발주 조건이라는 해석 일치 · `readiness`/`package`가 내 출력에서만 파생되는가 |
| 나 ↔ `case` | `EvidenceValue.source.label_key` → `CaseView.*_display.source_label_key` | 키 네임스페이스 소유 | projection | **B01 Pending** — 미합의 키는 `null`로 두고 web이 fallback 문구를 쓴다는 것에 합의 |
| 나 ↔ `case`·`readout` | `JobRecord.kind` ↔ `ReadoutRun.operation` | `JobExecution` 계약 소유 | 각각 발주/실행 | `OVERLAY_TIME_READ`용 `JobRecord.kind`가 필요한가 — **이번 회의 안건** |
| 나 ↔ `common/runtime` 구현 (정철원) | `JobExecution` | 계약 소유 | 구현 | 목 queue 응답이 계약 9필드와 status 전이를 지키는가 · 누가 1차 목 응답을 내놓는가 |
| 나 → `eval` (김대원) | `UsageRecord` · `JobExecution` | Producer | Consumer | `cost_per_source_video_hour` 분모에 필요한 필드가 다 있는가 · eval이 `case`/`evidence`를 import하지 않는가 |
| 나 → `web` (신유민) | (직접 없음) | — | `CaseView`만 소비 | web이 내 계약을 직접 읽지 않는지 · 미합의 label key에 fallback이 있는지 |

---

## 부분 완료 / 통합 대기

내 구현만으로 닫을 수 없는 것. **미완료가 아니라 대기다.**

| 항목 | 현재 어디까지 됨 | 무엇을 기다리는가 | 상대 담당 | Mock 대체 가능 여부 |
| --- | --- | --- | --- | --- |
| `CorrectionRecord` 기반 `USER_INPUT` 시각 판정 | `TimeResolution`에 `input_kind=USER_INPUT` 구조만 존재 | `CorrectionRecord` Final 승격 + 내 Consumer Review (N02) | 유소연 (Producer) / 나 (Review) | ✕ — Draft 기준 Mock을 만들지 않는다 |
| Rerun / 사용자 수정 Scenario (Type F·I) | 대표 Scenario 없음 | 위와 동일 | 유소연 | ✕ |
| `plate_visible_in_evidence` check | Requirement check 자리는 있으나 판정 근거 없음 | 어느 Observation이 이 사실을 전달할지 합의 (memo §6-B2) | 신유민 (`readout`) | △ — 1차에서는 `UNKNOWN` outcome으로 낸다 |
| 파일 용량·첨부 규칙 check (130MB 등) | 규정 수치는 조사됨, 판정 입력 없음 | derived asset metadata 계약 (`contract-analysis-source-derived.md` 미작성, B06~B09) | 정철원 | △ — `UNKNOWN` outcome + `measurement` 생략 |
| `report_video_ref` / `plate_image_ref` 실체 | opaque id(`da_*`)만 참조 | 위와 동일 | 정철원 | ○ — opaque ref로 Package 조립 가능 |
| `CaseView` projection 파생 규칙 (needs_review·source_label_key·representative location) | 계약 §8/§9 예시 형태만 재사용 | **B01** case/evidence/web 합의 | 유소연 · 신유민 · 나 | ○ — 미합의 키는 `null` |
| `requirements.scope`/`readiness` projection 선택 규칙 | 시나리오별 basis 1개만 표현 | **B02** | 유소연 | ○ — 단일 basis로 진행 |
| `Observation.run_ref` ↔ `ReadoutRun` 연결 | 미연결 | **B03** | 신유민 · 나 | ○ — 생략 |
| `UsageRecord.run_ref` ↔ `ReadoutRun` 연결 | readout 관련 row는 `run_ref=null` | **B05** | 신유민 · 김대원 · 나 | ○ — `null` 유지 |
| domain `PARTIAL` ↔ `JobExecution.status` 번역 | 미정의 | **W04** | 유소연 · 김대원 | ○ — `status`만 채움 |
| `JobExecution` 실제 queue 구현 | 계약·fixture만 | 정철원 구현 착수 | 정철원 | ○ — fixture로 대체 |
| 신고문의 차량 묘사(`흰색 SUV`) | Package fixture에는 있으나 Evidence에서 재생성 불가 | 계약 입력 범위 결정 3안 중 택1 (`05_...review` §6) | 나 (PM 결정) | ○ — 1차에서는 묘사 생략 |
| 신고기한 계산(초일 불산입·공휴일) | 규칙만 조사됨 | 공휴일 데이터 소스 결정 (Tech Spec) | 나 | ○ — 1차에서는 deadline check 미포함 또는 `UNKNOWN` |

---

## 1차 완료 제외 범위

명시적으로 뺀다. 이걸 요구하면 1차가 안 끝난다.

- `RequirementReport` 8개 outcome 조합 전부 (`contract-requirement-report-package.md` §13). 1차는 **WARN(FINAL_PACKAGE)·BLOCK(EVIDENCE) 2개**만.
- `TimeResolution`의 conflict/fallback/`NEEDS_REVIEW`/`UNKNOWN` 전 케이스. 1차는 **`OK` 2건**만.
- `supersedes_ref` 재평가 체인의 실제 동작. 1차는 **필드 경로 존재**까지.
- 신고 규정 데이터 표의 완성 (4종 유형 × 기한·용량·필수항목 전부). 1차는 **두 시나리오가 쓰는 rule**만.
- 신고문 template의 최종 문장·PC/Mobile 필드 분기.
- 실제 안전신문고 handoff 동작·다운로드·복사 UX.
- DB 스키마·MySQL queue 구현·retry backoff·lease/heartbeat 수치.
- 비용·latency 실측치와 최적화. 1차는 **원장 형식과 aggregate 정합**만.
- production 로깅·모니터링·알람.
- 성능(대용량 영상, 다수 case 동시 처리).

---

## Merge 중단 기준

아래가 하나라도 나오면 Merge를 진행하지 않는다.

1. **Contract와 다른 필드명/enum 문자열을 쓴다** — 예: `overall`을 `status`로, `PASS/WARN/BLOCK`을 `OK/WARNING/FAIL`로.
2. **필수 ID/Reference 누락** — `record_ref`·`basis_record_ref`·`basis.evidence_record_ref`·`provenance.selected_input_ref` 중 하나라도 빠짐.
3. **`UNKNOWN`을 정상 성공으로 처리한다** — GPS `UNKNOWN`을 좌표 `null`로 통과시키지 않고 임의 좌표를 만들거나, Requirement `UNKNOWN`을 `PASS`로 집계.
4. **확정하지 못한 값을 placeholder로 채운다** — `vehicle_number: "UNKNOWN"` / `"미상"` / 빈 문자열.
5. **`BLOCK`/`UNKNOWN`인데 `ReportPackage`가 생성된다.** 반대로 **`WARN`인데 Package가 생성되지 않는다.**
6. **ABSTAIN이 Case 전체를 실패로 만든다** — Partial 시나리오에서 `occurred_at`이나 선택 후보가 사라짐.
7. **Producer/Consumer가 같은 enum을 다르게 해석한다** — 특히 `abstained=true` + `ReadoutRun.outcome=SUCCEEDED`, `optional=false` ≠ `BLOCK`, `items=[]` ≠ 신고 가능.
8. **Happy Path 자체가 안 돈다** — 5개 산출물 중 하나라도 생성 실패.
9. **Contract 밖 내부 객체에 의존한다** — `evidence`가 `search`/`readout`을 import하거나, `case`가 내 내부 dataclass를 import.
10. **공통 Scenario에서 서로 다른 ID를 쓴다** — `case_happy_001`/`ev_h001`/`tres_h001`/`req_h001`/`pkg_h001` 체인이 모듈 간에 어긋남.
11. **Pending 항목을 몰래 확정한다** — B01/B02/B03/B05를 합의 없이 코드에 고정.
12. **마스킹 로거를 통과한 로그에 번호판·GPS 원문이 남는다.**

---

## 검증 명령

현재 실제로 있는 것:

```bash
python scripts/validate_mock_pack.py     # fixture 참조 무결성 + 선택 invariant (0 error / 0 warn 기대)
python scripts/validate_evidence_impl.py # Evidence 실제 출력 + 공용 fixture 회귀 (0 error 기대)
python scripts/check_boundaries.py       # 모듈 경계 · 계약 헤더 정합 (FAIL 0건 기대)
```

경계 grep (수동, `ownership.md` §6):

```bash
grep -rn "ffmpeg\|프롬프트" src/daesingo/evidence/            # 0건이어야 한다
grep -rn "import.*daesingo\.\(search\|readout\)" src/daesingo/evidence/   # 0건이어야 한다
```

evidence 구현 테스트:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/run_evidence_fixture.py happy_001 --output <output-dir>
python scripts/run_evidence_fixture.py partial_001 --output <output-dir>
```

테스트는 Python 표준 라이브러리 `unittest`만 사용하므로 별도 `pyproject.toml`이나
pytest 설치를 요구하지 않는다. 실제 완료 범위와 Pending은
`docs/modules/evidence/tech-spec.md` §2·§9를 함께 본다.

---

## 회의에서 말할 한 줄 요약

> "제 모듈은 `readout`·`search`·`recording`의 **관찰값(Observation·PlateReadout·OverlayTimeReadout·VisualEvidence·TimeSourceCandidate)** 을 입력으로 받아 **사건시각 최종 판정·확정값 승격·부족분 계산·신고요건 판정·신고 꾸러미 조립**을 수행하고, `TimeResolution`·`EvidenceRecord`·`EvidenceNeeds`·`RequirementReport`·`ReportPackage` 5개 Contract로 `case`에 넘깁니다. `scenario_happy_001`(WARN인데도 Package 생성)과 `scenario_partial_001`(번호판 ABSTAIN·위치 UNKNOWN → 필드 부재 + BLOCK + Package 미생성)까지 Mock 기준으로 검증했고, `common/runtime` 쪽은 `JobExecution`·`UsageRecord` 계약과 원장 정합까지입니다. `CorrectionRecord` 기반 재실행과 자산 metadata 기반 요건 검사는 상대 계약 대기입니다."
