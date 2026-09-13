# ADR-01: ① Observation<T> Data Contract 확정

**Status:** Accepted

**Contract:** `① Observation<T>`

**Producer:** `recording` / `search` / `readout`

**Consumer:** Direct Runtime Consumer `evidence`, `case` projection / Review Consumer 전체 Owner

**Owner:** 김준영 (`evidence` / common / PM)

**결정일:** `2026-09-04`

**관련 Contract Version:** `observation/v1`

**ADR ID:** `ADR-01`

**관련 Architecture Version:** 대신고 모듈 구조 설계 v4

관련 문서:

- Product Spec
- Module Architecture v4
- 역할 분담안 / Ownership
- Data Contract Draft — `Observation<T>`
- Consumer Review — Draft 본문 하단 Review 기록
- Final Data Contract — `Observation<T>` v1
- Final Data Contract — `AnalysisRun + CandidateEvent` v1
- Final Data Contract — `JobRecord / CaseView`

> 이 ADR은 `Observation<T>`를 다시 설계하는 문서가 아니다. Draft의 대안, Consumer Review, 관련 Final Contract와의 정합성 확인을 바탕으로 **최종적으로 채택된 계약 구조와 그 이유를 기록**한다.
> 

---

# 1. 결정 배경(Context)

## Producer가 생성하는 것

`recording`, `search`, `readout`은 각각 Source/영상/좁은 화면 영역에서 **관찰된 사실 또는 관찰 시도 결과**를 생산한다.

- `recording`: 파일·stream 사실, 시각 후보, GPS 등 Source 기반 관찰
- `search`: 사건/primitive/visual event 관련 관찰
- `readout`: 번호판 OCR, Overlay Timestamp 판독 등

## Consumer가 필요로 하는 것

`evidence`는 이 관찰들을 확정 Evidence의 입력으로 사용하고, `case`는 필요한 값을 safe projection으로 전달한다. `eval`은 Producer public output의 결과를 채점·재현해야 한다.

Consumer는 Producer 내부 모델·OCR SDK·raw provider payload를 알지 않고도 다음을 구분할 수 있어야 했다.

- 정상적으로 관찰된 값
- 추가 검토가 필요한 값
- Source 자체가 없거나 값을 알 수 없는 상태
- 처리 실패
- 적용 대상이 아닌 상태
- 값의 출처와 구체 근거
- 어느 Producer/run이 값을 만들었는지

## 계약을 고정해야 했던 이유

공통 Contract가 없으면 Producer마다 `null`, 실패, 미실행, low-confidence의 의미가 달라질 수 있고, `OK`를 최종 확정으로 오해하거나 Consumer가 Producer 내부 구조에 결합될 수 있다.

특히 대신고 Architecture의 핵심 원칙인:

> **관찰(`recording/search/readout`)과 확정(`evidence`)을 분리한다.**
> 

를 데이터 수준에서 강제하기 위해 공통 Observation envelope가 필요했다.

---

# 2. 결정 시 적용한 제약조건

| 제약 | 출처 | 이 Contract에 미친 영향 |
| --- | --- | --- |
| 관찰과 확정 Evidence를 분리 | Module Architecture v4 | `OK`도 최종 확정을 의미하지 않으며 Observation은 confirmed value를 소유하지 않음 |
| Timestamp는 값과 출처를 함께 관리하고 신뢰 가능한 출처가 없으면 임의 생성 금지 | Product Spec | `value`, `source`, `UNKNOWN`, provenance 분리 필요 |
| GPS/metadata가 Source에 없을 수 있음 | Recording 조사 / Architecture | 정상적 부재와 처리 실패를 구분하기 위해 `UNKNOWN`과 `ERROR` 분리 |
| 후보 0개는 Search 실행 실패가 아님 | Search 조사 / Eval 요구 | known-empty를 `OK + []`로 표현 가능해야 함 |
| 번호판 OCR confidence가 높아도 오답 가능 | Readout 조사 | bare numeric confidence를 최종 판단 근거로 사용하지 않음 |
| Readout의 abstain은 정상적인 domain 결과 | Readout 조사 | 공통 status에 `ABSTAIN`을 추가하지 않고 domain contract가 소유 |
| Eval 결과 비교를 위해 실행/계약 provenance 필요 | Eval 조사 | `contract_version`, Producer/run provenance 필요 |
| web은 domain contract를 직접 읽지 않고 CaseView만 소비 | Module Architecture v4 / CaseView Final | Observation의 reason/raw provenance를 UI 계약으로 사용하지 않음 |
| Job Intent / JobExecution / domain logical run은 서로 다른 책임 | Module Architecture v4 + 관련 Final Contracts | `produced_by`가 Job provenance를 중복 소유하지 않도록 logical `run_ref`만 선택적으로 보존 |

---

# 3. 검토했던 주요 선택지

Draft에서 실제로 계약 구조에 영향을 준 선택지만 기록한다.

## 결정 1. `value`와 `status` 관계

### A안 — 단순 Nullable Envelope

`value: T | null`과 `status`를 병렬 필드로 두고 조합 자체는 강하게 제한하지 않는다.

**장점**

- 구현이 가장 단순함

**단점**

- `OK + null`, `ERROR + value` 같은 잘못된 조합 가능
- Consumer별 null 해석이 달라질 수 있음

### B안 — 상태별 Value Invariant를 강제하는 Envelope

JSON 구조는 단순하게 유지하되 각 status가 value의 존재 가능성을 규정한다.

**장점**

- UNKNOWN/ERROR/known-empty 의미를 명확히 분리
- 복잡한 union 타입 없이 Consumer 방어 로직 감소

**단점**

- Producer가 invariant를 반드시 검증해야 함

### C안 — 상태별 구조를 분리하는 강한 Union

상태별 타입을 별도 variant로 구성하는 방식이 검토되었다.

**장점**

- 타입 수준에서 잘못된 조합 방지 가능

**단점**

- 현재 6인·단일 코드베이스 규모에서 serialization/mock/언어별 union 처리 복잡도가 큼

---

## 결정 2. `ABSTAIN`을 공통 Observation 상태로 둘 것인가

### A안 — 공통 상태는 5개로 유지

`ABSTAIN`은 `PlateReadout.abstained` 등 domain contract에서 표현하고 Observation은 `NEEDS_REVIEW`를 사용한다.

**장점**

- 공통 enum이 특정 도메인 세부상태로 확장되는 것을 방지
- Search/Recording Consumer가 Readout 전용 상태를 알 필요 없음

**단점**

- abstain 의미를 확인하려면 domain contract도 함께 봐야 함

### B안 — `ABSTAIN`을 공통 status에 추가

**장점**

- Readout만 보면 표현이 직접적임

**단점**

- `UNKNOWN`, `NEEDS_REVIEW`와 경계가 다시 필요
- 모든 Consumer가 Readout 특화 상태를 이해해야 함

---

## 결정 3. UNKNOWN / known-empty / 미실행 / 실패 구분

### 선택지 핵심

- 단순 null/sentinel로 통합하는 방식
- 실행 결과 상태와 Observation 상태를 섞는 방식
- **known-empty / UNKNOWN / ERROR를 분리하고 미실행은 Observation을 생성하지 않는 방식**

Draft는 세 번째 방향을 추천했고 Consumer가 동의했다.

---

## 결정 4. Provenance 공통 구조

### A안 — 최소 provenance

Source 또는 단일 실행 정보만 두는 단순 구조.

### B안 — `source` / `support_refs` / `produced_by` 분리

- `source`: 무엇을 보고 말했는가
- `support_refs`: 어떤 구체적 근거가 이를 뒷받침하는가
- `produced_by`: 누가/어떤 logical run에서 만들었는가

**장점**

- 입력 근거와 실행 identity를 분리
- frame/span 다중 근거 지원
- raw SDK/provider payload 노출 없이 추적 가능

**단점**

- reference lookup이 한 단계 추가됨

### C안 — raw snapshot / 구현 세부를 공통 Contract에 포함

**장점**

- self-contained diagnostics

**단점**

- 개인정보·payload 노출 및 stale data 위험
- Contract가 구현 세부에 결합됨

---

## 결정 5. `source.kind` 표현 방식

Draft에서는 닫힌 전역 enum과 확장 가능한 namespaced source 체계를 비교했다.

최종적으로 **namespaced semantic source**를 사용하되 provider/model/internal stage를 넣지 않는 방향을 선택했다.

---

## 결정 6. 근거 Reference 개수

### A안 — 단일 reference

**장점**

- 단순함

**단점**

- multi-frame OCR, multi-frame/span visual evidence를 충분히 표현하지 못함

### B안 — `support_refs[]`

**장점**

- 여러 frame/span 근거를 보존 가능
- aggregate object를 억지로 만들 필요 없음

**단점**

- 배열 순서를 의미 있는 시간 순서로 오해할 위험

Consumer Review에서 Search가 이 점을 지적해 Final에 **배열 순서는 semantic/temporal ordering을 보장하지 않는다**는 규칙을 추가했다.

---

## 결정 7. `confidence` 공통 표현

Draft는 bare score, confidence 미포함, `{score, metric}` 형태를 비교했고 **optional `{score, metric}`**을 추천했다.

**선택 이유**

- 동일한 0.9라도 OCR certainty, sequence consistency, model score는 의미가 다름
- Producer가 실제로 정의할 수 있는 경우에만 제공 가능
- Eval/Evidence가 metric 없이 숫자를 과대해석하는 것을 방지

---

## 결정 8. 비정상 상태 Reason

Draft는 free-text 중심 방식과 machine-readable code를 비교했고, **namespaced `reason.code` + optional `reason.note`**를 선택했다.

- 프로그램 분기: `status + reason.code`
- `note`: 사람용 최소 진단 정보

---

## 결정 9. Observation ID / Lifecycle

### 채택안 — 별도 global ID를 강제하지 않는 immutable value object

재실행은 기존 Observation을 수정하지 않고 새 실행 결과에 속한 Observation을 만든다.

**감수점**

- Observation 단독 global identity는 없음
- 부모 결과 / run provenance를 통해 추적해야 함

---

## 결정 10. Observation 적용 범위

Draft는 모든 세부 필드를 Observation으로 감싸는 방식과 semantic boundary value만 감싸는 방식을 비교했다.

최종적으로 **모듈 경계를 넘어 실제 관찰된 사실로 소비되는 값에만 적용**한다.

---

# 4. 최종 결정

| 결정 항목 | 최종 선택 | Draft 추천 | Consumer 의견 | 최종 변경 여부 |
| --- | --- | --- | --- | --- |
| value/status 관계 | B안 — 상태 invariant Envelope | B안 | Search 승인 | 유지 |
| 공통 ABSTAIN | A안 — 추가하지 않음 | A안 | Search/Readout 동의 | 유지 |
| UNKNOWN/known-empty/미실행/ERROR | 분리 | B안 | Search 동의 | 유지 |
| provenance | B안 — source/support_refs/produced_by 분리 | B안 | Search 승인, case 참조 충돌 지적 | **수정** |
| source.kind | namespaced semantic source | B안 | Search 조건부 승인: provider/model/stage 금지 | 조건 반영 |
| 근거 refs | `support_refs[]` | B안 | Search 조건부 승인: 순서 의미 금지 | 조건 반영 |
| confidence | optional `{score, metric}` | C안 | Search 조건부 승인: 모든 score 변환 금지 | 조건 반영 |
| reason | namespaced `code`  • optional `note` | C안 | Search 승인 / case UI 책임 후속 질문 | 유지, UI 경계는 CaseView로 해소 |
| Observation lifecycle | immutable value object, global id 비필수 | B안 | Search 승인 | 유지 |
| 적용 범위 | semantic boundary value만 Observation 사용 | C안 | Search 승인 | 유지 |

## 결정 1. 상태별 Value Invariant를 사용한다

**최종 선택:** B안

**결정 내용:**

- `OK` → value 필수
- `NEEDS_REVIEW` → value 존재 또는 null 가능
- `UNKNOWN`, `ERROR`, `NOT_APPLICABLE` → value null
- known-empty는 `OK + []` 등으로 표현 가능

**선택 이유:**

- Search Consumer는 후보 0개를 실패와 구분해야 함
- Recording은 GPS/metadata의 정상적 부재와 parser 실패를 구분해야 함
- 복잡한 union 없이 공통 의미를 강제할 수 있음

---

## 결정 2. 공통 status는 5개로 유지한다

**최종 선택:** `OK / NEEDS_REVIEW / UNKNOWN / ERROR / NOT_APPLICABLE`

`ABSTAIN`, `PENDING`, `PARTIAL`, `STALE` 등을 추가하지 않는다.

- `ABSTAIN`: Readout domain 상태
- `PENDING/QUEUED/RUNNING/STALE`: JobExecution / CaseView 상태
- `PARTIAL`: AnalysisRun 전체 outcome

각 상태 공간의 책임을 분리한다.

---

## 결정 3. Provenance는 source / support / Producer run을 분리한다

**최종 선택:** Draft B안을 유지하되 Consumer Review와 관련 Final Contract 확정에 따라 수정.

Draft의 `produced_by.execution_ref`는 Final에서 **`produced_by.run_ref`**로 변경한다.

### 결정 내용

- `source`: 관찰 방식/원천
- `support_refs[]`: 구체 근거 refs
- `produced_by.module`: Producer
- `produced_by.run_ref?`: Producer 소유 logical run
- `produced_by.impl_ref?`: optional opaque implementation identity

### 변경 이유

Case Consumer Review에서 기존 `execution_ref`가 `JobRecord.job_id`인지 `AnalysisRun.run_id`인지 모호하다는 충돌이 제기되었다.

이후 관련 Final Contract에서:

- `AnalysisRun.run_id`는 **Job ID와 동일 개념이 아닌 Search public capability logical run**으로 확정
- `JobRecord`는 case의 Job Intent를 소유
- `JobExecution`은 runtime/common이 lifecycle과 produced relation을 소유

하도록 경계가 닫혔다.

따라서 Observation이 Job provenance를 중복 소유하지 않고, Producer logical run만 선택적으로 참조하도록 `execution_ref → run_ref`로 명칭과 의미를 명확화했다.

---

## 결정 4. Source와 근거 Reference는 의미적으로 안정적인 값만 노출한다

- `source.kind`는 namespaced semantic source
- provider/model/internal stage는 `source.kind`에 넣지 않음
- `support_refs[]`는 opaque ref
- 배열 순서는 의미/시간 순서를 보장하지 않음

이는 Search Consumer의 조건부 승인 내용을 Final에 반영한 것이다.

---

## 결정 5. Confidence는 optional `{score, metric}`으로 제한한다

- bare confidence number를 허용하지 않음
- confidence 미제공은 0점이 아님
- 서로 다른 metric은 기본적으로 직접 비교하지 않음
- Search의 모든 `ranking_score`를 Observation confidence로 복사하지 않음
- Evidence는 confidence 숫자 하나만으로 확정하지 않음

---

# 5. Consumer Review 반영 내용

| Consumer 피드백 | 반영 여부 | Final Contract 변경 | 이유 |
| --- | --- | --- | --- |
| eval — 현재 추천안 승인 | 반영 | 구조 유지 | 실행/계약 provenance로 Eval 구분 가능 |
| recording — UNKNOWN/ERROR, namespaced source/reason, optional confidence로 구현 가능 | 반영 | 구조 유지 | Source/Time/GPS 관찰 표현 가능 |
| readout/web — 5개 상태 + `NEEDS_REVIEW + abstained`로 충분 | 반영 | 공통 `ABSTAIN` 미추가 | domain-specific 상태의 공통 enum 침투 방지 |
| search — `source.kind`에 provider/model/internal stage 금지 | 반영 | source 규칙 추가 | 의미적 계약과 구현 identity 분리 |
| search — `support_refs[]` 순서를 시간/semantic 순서로 해석하지 말 것 | 반영 | ordering 보장 없음 명시 | 시간 관계는 참조 대상 timeline 정보가 소유 |
| search — 모든 모델 score를 confidence로 변환할 필요 없음 | 반영 | confidence 규칙 추가 | ranking diagnostic과 cross-module uncertainty 분리 |
| case — `execution_ref`가 Job ID인지 AnalysisRun ID인지 모호 | **반영** | `execution_ref → run_ref`; Job provenance 제외 | AnalysisRun / JobRecord / JobExecution Final 경계와 정합 |
| case — `reason.code`를 UI 문구로 누가 변환하는지 불명확 | Observation 직접 수정은 하지 않음 | CaseView safe projection에서 `notices.code/message_key/severity/actions`로 분리 | UI 표현 책임은 Observation의 domain reason과 별도 계약에서 확정됨 |

---

# 6. 최종 Contract 핵심 요약

- 공통 envelope는 `value + status + source + support_refs + produced_by + optional confidence/reason` 구조다.
- `OK`는 confirmed Evidence가 아니라 **정상 관찰 결과**다.
- known-empty, UNKNOWN, ERROR를 구분한다.
- 미실행/Job lifecycle은 Observation에 넣지 않는다.
- ABSTAIN은 domain contract가 소유한다.
- 근거는 raw payload가 아닌 opaque refs로 연결한다.
- source 의미와 Producer logical run provenance를 분리한다.
- Search logical run은 `run_ref → AnalysisRun.run_id`로 연결 가능하다.
- Job Intent/JobExecution provenance는 Observation이 중복 소유하지 않는다.
- confidence는 metric이 정의된 경우에만 optional로 제공한다.
- Observation은 immutable value object이며 재실행으로 과거 값을 덮어쓰지 않는다.
- 모든 domain 세부 필드를 Observation으로 감싸지 않는다.

전체 Schema와 필드 정의는 **Final Data Contract — `Observation<T>` v1**을 따른다.

---

# 7. Invariants / 보장사항

1. `status=OK`이면 `value != null`이어야 한다.
2. `UNKNOWN / ERROR / NOT_APPLICABLE`이면 `value == null`이어야 한다.
3. 정상적인 empty result를 `UNKNOWN` 또는 `ERROR`로 표현하지 않는다.
4. 미실행 상태를 Observation status로 만들지 않는다.
5. `ABSTAIN`을 공통 status에 추가하지 않는다.
6. `source.kind`는 provider/model/internal stage identity를 포함하지 않는다.
7. `support_refs[]` 배열 순서는 semantic/temporal ordering을 보장하지 않는다.
8. confidence 제공 시 `score`와 `metric`을 함께 제공한다.
9. 서로 다른 metric의 confidence는 별도 정의 없이 직접 비교하지 않는다.
10. `reason.note`는 프로그램 분기 조건으로 사용하지 않는다.
11. `produced_by.run_ref`는 Producer logical run을 의미하고 Job ID / JobExecution을 의미하지 않는다.
12. 재실행은 기존 Observation을 in-place 수정하지 않는다.

---

# 8. 이번 결정의 결과(Consequences)

## 긍정적 결과

- 관찰과 확정 Evidence의 Ownership 경계가 데이터 구조에 반영된다.
- Producer별 null/실패 해석 차이를 줄인다.
- known-empty와 시스템 오류를 Eval에서 분리할 수 있다.
- 다중 frame/span 근거를 보존할 수 있다.
- Consumer가 raw SDK/provider payload에 결합되지 않는다.
- 계약 버전과 logical run provenance로 결과 재현성이 높아진다.
- JobRecord / JobExecution / AnalysisRun과 Observation의 책임 중복을 피한다.
- Mock에서 정상·UNKNOWN·ERROR·NEEDS_REVIEW 상태를 공통 형식으로 만들 수 있다.

## 감수하는 비용 / 단점

- 단순 `value` 하나보다 envelope schema가 복잡하다.
- Consumer는 `status`와 optional `reason.code` 분기를 처리해야 한다.
- opaque reference를 실제 근거로 따라가려면 lookup이 한 단계 필요하다.
- `support_refs[]`에 ordering 의미가 없으므로 시간 관계가 필요한 Consumer는 참조 대상 timeline 정보를 별도로 확인해야 한다.
- global `observation_id`가 없기 때문에 Observation 단독 identity보다 부모 결과/run provenance에 의존한다.
- confidence metric이 서로 다르면 공통 숫자 하나로 간단히 비교할 수 없다.

---

# 9. 채택하지 않은 대안

| 대안 | 채택하지 않은 이유 |
| --- | --- |
| 단순 nullable value + 느슨한 status | 잘못된 value/status 조합과 Consumer별 null 해석 위험 |
| 상태별 강한 Union | 현재 프로젝트 규모 대비 serialization/mock/타입 복잡도가 큼 |
| 공통 `ABSTAIN` 추가 | Readout 전용 상태가 전역 enum에 침투하고 UNKNOWN/NEEDS_REVIEW 경계가 복잡해짐 |
| `PENDING/NOT_COMPUTED` Observation 상태 | 관찰 결과와 Job lifecycle 책임이 섞임 |
| 단일 evidence reference | multi-frame/multi-span 근거 손실 |
| raw snapshot을 Observation에 포함 | payload 중복, privacy, stale data, 구현 결합 위험 |
| bare `confidence: number` | metric 의미를 잃고 Consumer가 숫자를 과대해석할 위험 |
| 모든 세부 필드를 Observation으로 래핑 | domain diagnostics까지 공통 계약에 끌어오는 과설계 |
| `produced_by.execution_ref` 유지 | JobExecution이라는 별도 개념과 명칭 충돌, Job ID와 AnalysisRun ID 의미 혼동 |
| Observation에 `job_ref` 추가 | Job → 산출물 relation을 `JobExecution.produced`와 중복 소유하게 됨 |

---

# 10. 다른 Contract에 미치는 영향

| 영향받는 Contract | 영향 내용 | 추가 수정 필요 여부 |
| --- | --- | --- |
| `AnalysisRun` | Search Observation의 `run_ref`가 `AnalysisRun.run_id`를 참조 가능. `run_id` 의미 변경 없음 | 없음 |
| `JobRecord` | Observation이 `job_id`를 provenance로 소유하지 않음 | 없음 |
| `JobExecution` | Job → produced result relation의 authoritative 책임 유지 | 없음 |
| `PlateReadout` | `ABSTAIN` 등 domain-specific 상태를 계속 소유 | 없음 |
| `OverlayTimeReadout` | semantic observation에 공통 envelope 적용 가능 | 구현 단계 반영 |
| `TimeResolution` / `EvidenceRecord` | Observation provenance와 상태를 입력으로 확정 결과 생성 | 기존 Evidence 계약에서 소비 규칙 확인 |
| `CaseView` | raw Observation/reason/confidence를 직접 노출하지 않고 safe projection 사용 | Final CaseView에서 이미 반영 |
| `ContractRef` | `{kind, ref}` nested structure를 여러 곳에서 사용할 가능성 | 현재 독립 Contract 승격 없음. 실제 중복 문제 확인 시만 재검토 |

---

# 11. Mock / 구현 / Evaluation에 미치는 영향

## Mock Dataset

최소 다음 사례가 필요하다.

- `OK + scalar/object value`
- `OK + []` known-empty
- `NEEDS_REVIEW + tentative value`
- `NEEDS_REVIEW + null`
- `UNKNOWN + null`
- `ERROR + null`
- `NOT_APPLICABLE + null`
- Readout domain의 `NEEDS_REVIEW + abstained=true`
- 다중 `support_refs[]`
- `run_ref`가 있는 Search Observation
- logical run contract가 없어 `run_ref`가 없는 Observation
- confidence가 있는/없는 Observation

## 구현

### Producer

- status/value invariant를 생성 시 검증한다.
- raw provider object나 영상 payload를 Observation에 embed하지 않는다.
- reason code는 namespaced stable code를 사용한다.
- 재실행 시 과거 Observation을 덮어쓰지 않는다.
- Job ID를 `run_ref`에 넣지 않는다.

### Consumer

- `OK`를 confirmed Evidence로 간주하지 않는다.
- null만 보고 UNKNOWN/ERROR를 추론하지 않고 status를 본다.
- `reason.note`로 프로그램 분기하지 않는다.
- `support_refs[]` 배열 순서에 의미를 부여하지 않는다.
- confidence metric이 다르면 직접 비교하지 않는다.

## Evaluation

- known-empty와 ERROR를 구분할 수 있어야 한다.
- `contract_version` 및 제공된 logical run provenance를 통해 결과 버전을 구분할 수 있다.
- confidence가 없는 Observation을 0점으로 처리하지 않는다.

새로운 metric이나 평가 요구는 이 ADR에서 추가하지 않는다.

---

# 12. 변경 규칙

Accepted 이후 의미 변경이 필요하면 다음 절차를 따른다.

```
문제 발견
→ Producer / Consumer 확인
→ Data Contract 변경안 작성
→ Architecture 영향 확인
→ Contract Version 증가
→ ADR Supersede 또는 변경 ADR 작성
→ Mock Dataset 갱신
```

다음 변경은 ADR 변경 대상으로 본다.

- 필수/선택 의미 변경
- 데이터 Ownership 변경
- status/enum 의미 변경
- Producer/Consumer 책임 변경
- UNKNOWN/ERROR 의미 변경
- provenance 구조 의미 변경
- lifecycle/immutability 변경
- 다른 모듈 구현 계약에 영향을 주는 field 변경

설명 문구·예시처럼 계약 의미를 바꾸지 않는 수정은 별도 ADR 없이 문서를 정리할 수 있다.

---

# 13. 미해결 사항

| 항목 | 왜 미해결인가 | 담당자 | 언제 결정해야 하는가 |
| --- | --- | --- | --- |
| ADR 번호 | 팀 ADR numbering 규칙/번호가 이번 입력에서 제공되지 않음 | 김준영 | 공식 ADR 목록에 편입할 때 |
| 결정일 | ADR 작성 입력에서 공식 결정일이 별도로 제공되지 않음 | 김준영 | 문서 확정 시 |

`Observation<T>` 계약 구조 자체에 대해서는 현재 Final Contract 기준 추가로 남은 Architecture Decision을 확인하지 못했다.

`ContractRef`의 독립 공통 Contract 승격은 **현재 결정하지 않는다**. 향후 여러 Final Contract에서 실제 중복/불일치 문제가 확인될 경우 별도 변경안으로 검토한다.

---

# 14. 최종 한 줄 결정

> **우리는 `recording`·`search`·`readout`이 관찰값을 상태·출처·근거·Producer logical run provenance를 가진 immutable `Observation<T>`로 보장하고, `evidence`와 `case`가 이를 확정 Evidence와 safe projection의 입력으로 소비하도록 계약을 확정한다.**
>