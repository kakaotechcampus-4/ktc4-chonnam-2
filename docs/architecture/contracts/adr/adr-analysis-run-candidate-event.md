# ADR: AnalysisRun + CandidateEvent Data Contract 확정

**Status:** Accepted

**Contract:** `AnalysisRun + CandidateEvent`

**Producer:** 서어진 (`search`)

**Consumer:** 유소연 (`case`), 김대원 (`eval`)

**Owner:** 서어진

**결정일:** 9/4

**관련 Contract Version:** `analysis-run-candidate-event/v1`

**관련 Architecture Version:** `module_architecture.md v4`

## 관련 문서

- Product Spec
- `module_architecture.md v4`
- `tech_spec.md v1.1`
- Data Contract Draft — Contract 4 `AnalysisRun + CandidateEvent`
- Consumer Review — 유소연(`case`), 김대원(`eval`)
- [Final Data Contract — Contract 4 AnalysisRun + CandidateEvent v1](https://app.notion.com/p/Final-Data-Contract-Contract-4-AnalysisRun-CandidateEvent-v1-3d17ae78fc6a81bbbad3c56beea9fbd3?pvs=21)

> 본 ADR이 확정한 결정의 **schema/serialization Source of Truth는 `analysis-run-candidate-event/v1` Final Data Contract**다.
> 
> 
> Draft는 검토했던 대안을 확인하기 위해 사용하고, Consumer Review는 Draft 추천안이 유지되거나 변경된 이유를 확인하기 위해 사용한다.
> 

---

# 1. 결정 배경(Context)

`search`는 장시간 블랙박스 영상에서 사건 가능성이 높은 시간 구간을 탐색하고, 그 실행 결과를 `case`와 `eval`에 전달해야 한다.

Architecture v4에서 `search`는 `AnalysisRun`, `CandidateEvent[]`, `VisualEvidence`를 소유하며, `AnalysisRun`은 **불변 실행 기록**, `CandidateEvent`는 실제 파일이 아니라 **사건 후보 span**을 나타낸다. 또한 Search는 법적 판단이나 신고 유형을 확정하지 않는다. fileciteturn0file0

이번 Contract는 이 중:

- Search 실행 하나를 어떻게 식별할지
- Candidate를 어떤 entity와 시간 표현으로 전달할지
- Candidate ordering을 무엇으로 표현할지
- 정상 후보 0개와 실패를 어떻게 구분할지
- partial failure를 어떻게 표현할지
- 실행 implementation과 usage 정보를 어디까지 전달할지

를 확정하기 위해 필요했다.

## Producer가 생성하는 것

`search`는 다음을 생성한다.

- Public Search capability 실행 기록인 `AnalysisRun`
- 해당 실행에서 발견한 0개 이상의 `CandidateEvent`
- Candidate의 Recording Timeline 기준 span
- Candidate rank와 optional diagnostic 정보
- Search 실행 결과 상태
- 부분 실패 정보
- implementation/version 정보
- UsageRecord reference와 Eval용 usage snapshot

## Consumer가 필요로 하는 것

### `case`

`case`는 Candidate를 사용자에게 보여주고 선택된 Candidate를 후속 작업의 안정적인 reference로 사용해야 한다.

이를 위해 다음이 필요하다.

- 안정적인 Candidate ID
- Candidate와 Run 간 관계
- 실제 파일 경계와 독립적인 span
- Candidate ordering
- 후보 0개와 실행 실패의 구분
- partial coverage 정보

### `eval`

`eval`은 동일한 Search 결과를 재사용하면서 다음을 평가해야 한다.

- Recall@1 / @3 / @10
- span/timestamp error
- FP
- implementation별 비교
- cost
- token usage
- latency

Technical Spec에서도 Candidate 평가에는 Recall@1/@3/@10과 timestamp error가, Efficiency 평가에는 cost, latency, token usage가 요구된다. fileciteturn0file1

## 계약을 고정해야 했던 이유

계약이 없으면 다음과 같은 문제가 발생할 수 있었다.

- provider API 호출과 하나의 논리 Search 실행이 같은 개념으로 취급됨
- `COARSE/FINE`과 같은 내부 구현 단계가 Consumer 계약으로 노출됨
- Candidate 위치를 absolute datetime, file offset, timeline offset 중 서로 다르게 해석함
- raw score를 Consumer가 confidence처럼 사용함
- 후보 0개와 Search 실행 실패를 같은 상태로 처리함
- partial failure에서 어느 범위가 처리되지 않았는지 알 수 없음
- 비용·token·latency 평가를 위해 Eval이 별도 runtime 데이터에 의존해야 함
- 재실행 시 기존 결과 수정으로 과거 Eval 결과의 재현성이 깨짐
- Candidate가 Final Evidence 또는 신고 판단처럼 사용될 위험이 생김

---

# 2. 결정 시 적용한 제약조건

| 제약 | 출처 | 이 Contract에 미친 영향 |
| --- | --- | --- |
| `AnalysisRun`은 불변 실행 기록 | Module Architecture v4 | 재실행 시 기존 Run 수정이 아니라 새 `run_id` 생성 |
| Search 결과는 파일이 아니라 사건 span | Module Architecture v4 | Candidate canonical 위치를 Recording Timeline 기준으로 정의 |
| 실제 파일 경계와 Incident Clip 생성은 `recording` 책임 | Module Architecture v4 | Candidate에 실제 file boundary 또는 신고용 영상 정보 미포함 |
| Search는 Recall 우선 후보/visual observation까지만 소유 | Module Architecture v4 | 법적 판단, 신고 유형, 확정 Evidence 제외 |
| Fine/Classification은 Candidate에만 종속되지 않음 | Module Architecture v4 | `COARSE/FINE` 대신 semantic `operation` 사용 |
| Job execution lifecycle은 common/runtime 책임 | Module Architecture v4 | `AnalysisRun`은 terminal domain outcome만 소유 |
| 외부 호출 usage의 원천은 `UsageRecord` | Module Architecture v4 | `usage_refs[]` 유지 |
| AnalysisRun은 과거 실행의 usage/pricing context를 추적 가능해야 함 | Module Architecture v4 | Eval용 immutable usage snapshot 허용 |
| raw provider payload는 sensitive할 수 있음 | Module Architecture v4 | 공용 Contract에서 raw response 제거 |
| Recall@1/3/10 평가 필요 | Technical Spec v1.1 | `rank`를 authoritative ordering으로 확정 |
| span/timestamp error 평가 필요 | Technical Spec v1.1 | timeline-relative span을 canonical 위치로 확정 |
| cost/token/latency 평가 필요 | Technical Spec v1.1 + Eval Review | `usage_summary` snapshot 추가 |
| case는 Search 내부 구현을 몰라야 함 | Architecture + Case Review | provider/chunk/stage 세부를 Contract에서 제외 |

Architecture v4는 Search가 사건 span을 반환하고 실제 clip 생성은 `recording`이 담당하도록 경계를 고정하고 있다. 또한 Job execution lifecycle과 UsageRecord는 common/runtime 영역에 둔다. fileciteturn0file0

---

# 3. 검토했던 주요 선택지

## 결정 1. `AnalysisRun`의 단위

### A안 — Provider 호출 1회 = AnalysisRun 1개

Provider call이나 chunk call 하나마다 별도 Run을 생성한다.

**장점**

- 외부 API 호출과 실행 기록을 1:1로 연결하기 쉽다.
- provider debugging이 단순하다.

**단점**

- `case`가 하나의 Search 결과를 위해 여러 Run을 다시 조립해야 한다.
- `eval`이 logical Search 단위를 재구성해야 한다.
- 내부 chunk/provider 전략이 public Contract에 노출된다.
- provider 전략이 바뀌면 Run 의미도 바뀔 수 있다.

### B안 — Public capability invocation 1회 = AnalysisRun 1개

`search_candidates(scope)` 같은 public capability 호출 하나를 logical Run 하나로 본다.

**장점**

- Consumer가 public capability 기준으로 결과를 이해할 수 있다.
- 내부 chunk/provider 변경과 Contract를 분리할 수 있다.
- 하나의 Run에서 여러 UsageRecord를 연결할 수 있다.
- implementation A/B 비교가 단순하다.

**단점**

- provider call 단위 debugging에는 UsageRecord나 내부 trace가 별도로 필요하다.
- partial failure 표현이 필요하다.

---

## 결정 2. 실행 종류 표현

### A안 — `stage: COARSE | FINE`

**장점**

- 기존 구현 용어와 직접 대응한다.

**단점**

- 현재 Coarse→Fine 구현 방식을 public Contract에 고정한다.
- Fine이 Candidate에 종속된 단계처럼 보일 수 있다.
- candidate-independent verification과 의미가 맞지 않는다.

### B안 — `operation: CANDIDATE_SEARCH | VISUAL_VERIFY`

**장점**

- public capability 의미와 직접 대응한다.
- 내부 실행 단계가 변경되어도 Contract를 유지할 수 있다.
- Eval의 candidate-independent verification과 정합적이다.

**단점**

- 기존 `COARSE/FINE` 용어와 semantic operation 사이의 매핑이 필요하다.

### C안 — `operation`과 `stage` 모두 노출

**장점**

- public 의미와 내부 stage를 동시에 추적할 수 있다.

**단점**

- 중복 개념이 생긴다.
- 두 값이 불일치할 수 있다.
- 내부 구현 상태가 Contract로 노출된다.

---

## 결정 3. Candidate 구조

### A안 — Candidate를 `AnalysisRun` 내부 배열에 embed

**장점**

- 단일 JSON 전달이 단순하다.

**단점**

- Candidate를 개별 entity로 reference하기 어렵다.
- Run과 Candidate를 별도 저장할 경우 중복 serialization이 발생한다.
- Candidate별 후속 결과와 연결하기 어렵다.

### B안 — 별도 `CandidateEvent` + `run_id`

**장점**

- `candidate_id`를 안정적인 reference로 사용할 수 있다.
- `case` selection이 단순해진다.
- `eval` prediction 구조와 잘 맞는다.
- Run과 Candidate를 각각 독립적으로 다룰 수 있다.

**단점**

- 항상 둘을 함께 필요로 하는 Consumer는 추가 lookup이 필요할 수 있다.

---

## 결정 4. Candidate의 canonical 시간 위치

### A안 — Absolute datetime

**장점**

- 사람이 읽기 쉽다.
- UI에 바로 표시할 수 있다.

**단점**

- Timeline anchor 변경의 영향을 받는다.
- 최종 신고 `occurred_at`과 혼동되기 쉽다.
- Eval의 relative span 비교가 불편하다.

### B안 — Timeline reference + relative span

**장점**

- Search가 실제로 본 영상 위치를 안정적으로 보존한다.
- Timeline rebase와 Candidate pixel 위치를 분리한다.
- span error 평가에 직접 사용할 수 있다.
- 파일 경계는 `recording` 책임으로 유지된다.

**단점**

- 사용자 표시용 absolute time은 별도 projection이 필요하다.

### C안 — Canonical relative span + display snapshot

**장점**

- UI와 로그 가독성이 좋아진다.

**단점**

- Timeline rebase 후 snapshot이 최신 시각과 달라질 수 있다.
- Consumer가 snapshot을 authoritative time으로 오해할 수 있다.

---

## 결정 5. Candidate ordering

### A안 — `score`만 필수

**장점**

- 구현이 단순하다.

**단점**

- 서로 다른 implementation의 score를 같은 scale로 오해할 수 있다.
- Eval이 tie/order 규칙을 다시 구현해야 할 수 있다.
- `case`가 raw score threshold를 제품 로직에 사용할 위험이 있다.

### B안 — `rank`만 필수

**장점**

- Recall@K에 필요한 의미가 정확하다.
- implementation 변경에 강하다.

**단점**

- Search 내부 진단을 위한 score 정보가 사라진다.

### C안 — `rank` 필수 + `ranking_score` optional

**장점**

- Consumer ordering과 diagnostic score를 분리할 수 있다.
- Recall@K는 rank 기준으로 안정적으로 계산 가능하다.
- Search/Eval 진단에는 score를 유지할 수 있다.

**단점**

- Consumer가 optional score를 잘못 해석할 가능성은 남는다.

---

## 결정 6. Candidate의 사건 유형 표현

### A안 — `event_type` 필수

**장점**

- routing과 평가가 단순하다.

**단점**

- Recall 우선 Candidate 단계에서 사건 유형을 과도하게 확정한다.

### B안 — `event_type_hint` optional 단일값

**장점**

- routing에는 활용할 수 있다.
- 확정값과 분리된다.
- MVP 구조가 단순하다.

**단점**

- 여러 유형 가능성을 동시에 표현하지 못한다.

### C안 — `event_type_hints[]`

**장점**

- ambiguity를 더 많이 보존할 수 있다.

**단점**

- Consumer가 복잡해진다.
- 상세 classification을 담당하는 `VisualEvidence`와 역할이 겹칠 수 있다.

---

## 결정 7. Candidate 설명 정보

### A안 — span/rank만 제공

**장점**

- Contract가 가장 단순하다.

**단점**

- case Candidate Review UX가 부족하다.
- Eval FP 분석 정보가 적다.

### B안 — `summary` + `uncertainties[]`

**장점**

- Candidate 검토에 필요한 최소 설명을 제공한다.
- Fine/VisualEvidence와 구분된다.
- 실패 분석에도 활용할 수 있다.

**단점**

- 자연어 내용의 deterministic validation이 어렵다.

### C안 — 구조화 Evidence까지 Candidate에 포함

**장점**

- 정보량이 많다.

**단점**

- `VisualEvidence`와 책임이 중복된다.
- Candidate Search가 Fine verification 역할까지 갖게 된다.

---

## 결정 8. Search 결과 상태

### A안 — `SUCCESS | FAILED`

**장점**

- 단순하다.

**단점**

- 일부 구간 실패 + usable result를 표현하지 못한다.

### B안 — `SUCCEEDED | PARTIAL | FAILED`

**장점**

- 부분 결과를 보존할 수 있다.
- 정상 후보 0개와 실패를 구분할 수 있다.
- Job lifecycle과 분리된다.

**단점**

- `PARTIAL` 조건을 별도로 정의해야 한다.

### C안 — Job lifecycle 전체 복제

`QUEUED | RUNNING | SUCCEEDED | FAILED | STALE`

**장점**

- 하나의 객체에서 모든 상태를 볼 수 있다.

**단점**

- `JobRecord`와 책임이 중복된다.
- immutable Run과 mutable execution state가 섞인다.

---

## 결정 9. 부분 실패 정보

### A안 — 단일 `failure_kind`

**장점**

- Schema가 단순하다.

**단점**

- 여러 실패를 표현할 수 없다.
- 어떤 범위가 coverage에서 빠졌는지 표현하기 어렵다.

### B안 — `issues[]`

**장점**

- 복수 failure를 표현할 수 있다.
- 영향을 받은 범위 reference를 함께 전달할 수 있다.
- 내부 stack trace를 노출하지 않아도 된다.

**단점**

- issue schema가 추가된다.

---

## 결정 10. Usage / Cost 전달 방식

### A안 — AnalysisRun이 usage 값을 직접 소유

**장점**

- Eval이 쉽게 읽을 수 있다.

**단점**

- `UsageRecord`와 authoritative ownership이 중복된다.
- provider call 집계 책임이 Search에 생긴다.

### B안 — `usage_refs[]`만 제공

**장점**

- Usage 원천을 한 곳에 유지할 수 있다.
- Architecture ownership이 명확하다.

**단점**

- immutable prediction 파일만으로 재평가하려면 별도 UsageRecord join이 필요하다.

### C안 — `usage_refs[]` + immutable `usage_summary`

**장점**

- Usage의 authoritative 원천은 `UsageRecord`에 유지된다.
- Eval prediction 파일 하나만으로 cost/token/latency를 처리할 수 있다.
- 실행 당시 Efficiency 데이터를 immutable하게 보존할 수 있다.

**단점**

- Usage 일부 정보가 두 위치에 중복된다.
- UsageRecord와 snapshot 간 정합성 관리가 필요하다.

---

## 결정 11. Implementation identity

### A안 — model 이름만

**장점**

- 단순하다.

**단점**

- prompt/config 변경을 구별하지 못한다.

### B안 — opaque `impl_id`

**장점**

- Consumer가 구현 내부를 알 필요가 없다.

**단점**

- debugging 시 세부 version을 즉시 알기 어렵다.

### C안 — `impl_id` + model/prompt/config version

**장점**

- 과거 실행 재현성이 높아진다.
- prompt/config 변경 실험을 구분할 수 있다.
- Eval 비교가 쉬워진다.

**단점**

- implementation metadata가 조금 더 노출된다.

---

## 결정 12. Raw provider response

### A안 — `raw_response_ref` 필수

**장점**

- debugging이 쉽다.

**단점**

- provider-specific format에 Consumer가 결합될 수 있다.
- privacy/retention 부담이 생긴다.

### B안 — 공용 Contract에서 제거

**장점**

- provider 구현과 Consumer를 분리한다.
- sensitive payload 보존 정책을 Search 내부로 한정할 수 있다.

**단점**

- 상세 debugging에는 별도 Search 내부 observability가 필요하다.

### C안 — optional restricted debug ref

**장점**

- 필요한 경우 debugging에 활용할 수 있다.

**단점**

- optional이어도 Consumer dependency가 생길 수 있다.

---

# 4. 최종 결정

## 4-1. 결정 요약

| 결정 항목 | 최종 선택 | Draft 추천 | Consumer 의견 | 최종 변경 여부 |
| --- | --- | --- | --- | --- |
| AnalysisRun 단위 | B안 | B안 | 반대 없음 | 유지 |
| 실행 종류 표현 | B안 | B안 | 반대 없음 | 유지 |
| Candidate 구조 | B안 | B안 | `case` 승인 | 유지 |
| Candidate canonical 위치 | B안 | B안 | `case` Q1/Q2 승인 | 유지 |
| Candidate ordering | C안 | C안 | `case` Q5 승인 | 유지 |
| Event type 표현 | B안 | B안 | 반대 없음 | 유지 |
| Candidate 설명 | B안 | B안 | 반대 없음 | 유지 |
| Search outcome | B안 | B안 | `case` 승인 | 유지 |
| Partial failure | B안 | B안 | `case` Q4 승인 | 유지 |
| Usage / Cost | **C안** | **B안** | `eval` 수정 요청 | **변경** |
| Implementation identity | C안 | C안 | 반대 없음 | 유지 |
| Raw provider response | B안 | B안 | 반대 없음 | 유지 |

---

## 결정 1. Public capability invocation 하나를 `AnalysisRun` 하나로 기록한다

**최종 선택:** B안

### 결정 내용

`AnalysisRun`은 provider API call이나 내부 chunk가 아니라 **public Search capability의 logical invocation 하나**를 나타낸다.

예를 들어 `search_candidates(scope)` 내부에서:

- 여러 chunk를 나누고
- 여러 provider call을 수행하고
- merge/dedup을 수행하더라도

최종적으로 하나의 `AnalysisRun`으로 기록한다.

### 선택 이유

- `AnalysisRun`은 Search domain의 logical 실행 기록이다.
- provider/chunk 전략은 Search 내부 구현이다.
- `case`가 여러 내부 호출을 다시 조립하지 않아도 된다.
- `eval`이 동일 logical Search 실행 단위로 implementation을 비교할 수 있다.
- provider call별 상세 사용량은 `UsageRecord`를 통해 추적 가능하다.

---

## 결정 2. `COARSE/FINE` 대신 semantic `operation`을 사용한다

**최종 선택:** B안

### 결정 내용

공용 Contract의 실행 종류는 내부 구현 stage가 아니라 public capability의 의미를 표현한다.

Final Contract 기준:

- `CANDIDATE_SEARCH`
- `VISUAL_VERIFY`

를 사용한다.

### 선택 이유

Architecture v4는 Fine verification이 Candidate에만 종속되지 않고 독립 input에서도 호출 가능해야 한다고 정의한다. fileciteturn0file0

따라서 `COARSE/FINE`은 현재 Search 구현 전략에 가까우며, public Contract에는 semantic operation을 사용하는 것이 Architecture와 정합적이다.

---

## 결정 3. Candidate를 별도 entity로 유지한다

**최종 선택:** B안

### 결정 내용

`CandidateEvent`는 `AnalysisRun` 내부의 중첩 데이터로만 존재하지 않고 별도 entity로 정의한다.

각 Candidate는:

- `candidate_id`
- `run_id`

를 가진다.

### 선택 이유

- `case`가 Candidate를 안정적인 Selection reference로 사용할 수 있다.
- `eval`에서 Candidate prediction을 개별적으로 다루기 쉽다.
- Candidate와 후속 `VisualEvidence` 등의 관계를 독립적으로 연결할 수 있다.
- Run 본문과 Candidate 본문의 불필요한 중복을 줄인다.

---

## 결정 4. Candidate 위치는 Timeline-relative span을 canonical 값으로 사용한다

**최종 선택:** B안

### 결정 내용

Candidate의 authoritative 위치는:

- `timeline_id`
- `start_ms`
- `end_ms`
- `representative_ms`

로 표현한다.

Candidate Contract에는 absolute display time을 authoritative field로 두지 않는다.

### 선택 이유

- Search가 관찰한 실제 pixel 위치를 Timeline anchor와 독립적으로 보존할 수 있다.
- Timeline rebase 이후에도 Candidate의 영상 위치 자체는 바뀌지 않는다.
- Eval의 span/timestamp error 계산에 직접 사용할 수 있다.
- 실제 SourceAsset/file boundary는 `recording` 책임으로 유지된다.
- Candidate의 표시 시각과 최종 신고 `occurred_at`을 혼동하지 않는다.

### Consumer Review 반영

`case` Owner는 Q1과 Q2 모두 승인했다.

CaseView가 이미 `TIMELINE_ANCHOR+OFFSET` 방식으로 표시 시간을 구성하는 방향이므로 Candidate absolute snapshot을 추가할 필요가 없다고 확인했다.

단, anchor→display 변환의 실제 capability 책임은 별도 접합 단계에서 확인한다.

---

## 결정 5. `rank`를 authoritative ordering으로 사용한다

**최종 선택:** C안

### 결정 내용

Candidate는:

- `rank` — 필수
- `ranking_score` — optional

로 표현한다.

Candidate ordering 및 Recall@K 계산의 기준은 `rank`다.

### 선택 이유

- Recall@1/@3/@10 평가가 Candidate의 명시적인 ordering을 요구한다.
- 모델이나 prompt가 달라지면 score scale이 동일하다는 보장이 없다.
- `case`가 raw score threshold로 Candidate 의미를 판단하는 것을 방지한다.
- Search/Eval debugging에는 optional score를 유지할 수 있다.

### Consumer Review 반영

`case` Owner는 Candidate 표시와 선택 로직을 `rank` 기준으로 사용할 수 있다고 승인했다.

---

## 결정 6. Candidate 사건 유형은 optional hint로만 제공한다

**최종 선택:** B안

### 결정 내용

Candidate에는 확정 `event_type`이 아니라 optional `event_type_hint`를 사용한다.

### 선택 이유

Candidate Search는 Recall 우선 단계이므로 사건 유형까지 확정하도록 강제하지 않는다.

상세 Visual Event verification은 별도 `VisualEvidence` Contract 책임이다.

또한 Search가 신고 유형이나 법적 위반을 확정하지 않는 Architecture 경계를 유지한다. fileciteturn0file0

---

## 결정 7. Candidate에는 lightweight 설명만 제공한다

**최종 선택:** B안

### 결정 내용

Candidate에는 필요할 경우:

- `summary`
- `uncertainties[]`

를 포함한다.

구조화된 visual primitive, temporal order, target association 등은 `VisualEvidence`에 남긴다.

### 선택 이유

- `case`의 Candidate Review에 최소 설명이 필요하다.
- Eval의 FP/failure 분석에 도움이 된다.
- Candidate와 Fine Evidence의 책임을 분리할 수 있다.

---

## 결정 8. Search 결과를 `SUCCEEDED / PARTIAL / FAILED`로 표현한다

**최종 선택:** B안

### 결정 내용

`AnalysisRun.outcome`은 완료된 Search의 terminal domain outcome만 표현한다.

- `SUCCEEDED`
- `PARTIAL`
- `FAILED`

특히:

> `SUCCEEDED + candidates=[]`
> 

은 정상 결과다.

### 선택 이유

- Candidate 0개는 Search 실패가 아니다.
- Long-video Search에서는 일부 구간만 실패하는 경우가 존재할 수 있다.
- `QUEUED`, `RUNNING`, `STALE`은 common/runtime의 `JobRecord` 책임이므로 중복하지 않는다.

Architecture v4는 Job 발주와 execution lifecycle을 분리하고, execution lifecycle을 common/runtime이 소유하도록 정의한다. fileciteturn0file0

---

## 결정 9. 부분 실패는 `issues[]`로 표현한다

**최종 선택:** B안

### 결정 내용

`PARTIAL` 또는 `FAILED`의 상세 정보는 `issues[]`로 전달한다.

각 issue는 최소한:

- failure kind
- stable code
- 영향 범위 reference
- optional masked detail

을 표현할 수 있다.

### 선택 이유

- 하나의 Run에서 복수 실패가 발생할 수 있다.
- partial result의 누락 coverage를 Consumer가 알 수 있어야 한다.
- 내부 stack trace와 raw provider payload는 공개하지 않아도 된다.

### Consumer Review 반영

`case` Owner는 `issues[].scope_ref` 수준의 정보면 partial coverage를 표현하는 데 충분하다고 승인했다.

---

## 결정 10. UsageRecord reference와 immutable usage summary를 함께 제공한다

**최종 선택:** **C안**

**Draft 추천:** B안

### 결정 내용

Final Contract는 다음 두 정보를 함께 제공한다.

```
usage_refs[]
+
usage_summary
```

`usage_refs[]`는 상세 UsageRecord의 authoritative source를 추적한다.

`usage_summary`는 Eval prediction과 함께 보존되는 immutable snapshot으로:

- cost
- token usage
- latency
- 필요한 경우 processed duration

을 제공한다.

### Draft → Review → Final 변화

Draft에서는 Architecture ownership을 가장 단순하게 유지하기 위해:

> `usage_refs[]`만 제공하고 Eval에서 UsageRecord를 join한다.
> 

는 B안을 추천했다.

그러나 Eval Owner는:

> 토큰 사용량과 지연까지 prediction 파일로 넘겨야 Eval에서 한 번에 처리할 수 있다.
> 

고 수정 요청했다.

이에 따라 Final Contract에서는 C안으로 변경했다.

### 선택 이유

Technical Spec의 Efficiency 평가에서는 cost, latency, token usage를 실행 결과와 함께 추적해야 한다. fileciteturn0file1

Eval은 Runner가 생성한 immutable Prediction을 이후 Scorer에서 다시 사용할 수 있어야 하므로, Prediction 파일 단독으로 Efficiency 정보를 사용할 수 있어야 한다.

동시에 Architecture의 `UsageRecord` ownership은 유지해야 한다.

따라서:

- 상세 usage ledger → `UsageRecord`
- Eval용 실행 snapshot → `AnalysisRun.usage_summary`

로 역할을 분리했다.

### 감수하는 비용

Usage 정보 일부가 `UsageRecord`와 `AnalysisRun.usage_summary`에 중복된다.

따라서 Producer는 두 표현의 실행 시점 정합성을 유지해야 한다.

---

## 결정 11. Implementation identity에 version metadata를 포함한다

**최종 선택:** C안

### 결정 내용

Final Contract는 implementation을 다음 수준으로 추적한다.

- `impl_id`
- `model_ref`
- `prompt_version`
- `config_version`

### 선택 이유

- 같은 model을 사용해도 prompt가 다르면 다른 Search implementation일 수 있다.
- config 변경 실험을 구분해야 한다.
- Eval prediction을 과거 실행과 재현 가능하게 연결해야 한다.
- Consumer는 실제 prompt 본문이나 FPS/chunk 설정을 알 필요가 없다.

Technical Spec에서도 평가 결과에 구현 이름표와 contract version을 남겨 재현성을 보장하도록 요구한다. fileciteturn0file1

---

## 결정 12. Raw provider response는 공용 Contract에서 제외한다

**최종 선택:** B안

### 결정 내용

Final Contract에는 `raw_response_ref`를 포함하지 않는다.

### 선택 이유

- raw provider payload가 개인정보 또는 sensitive data를 포함할 수 있다.
- provider-specific response 구조가 Consumer Contract로 노출되는 것을 방지한다.
- `case`와 `eval`은 Search provider 내부 형식을 몰라도 동작해야 한다.
- provider debugging은 Search 내부 observability 책임으로 남긴다.

Architecture v4도 raw provider payload와 공용 Contract/장기 보존 정책을 분리하도록 요구한다. fileciteturn0file0

---

# 5. Consumer Review 반영 내용

| Consumer 피드백 | 반영 여부 | Final Contract 변경 | 이유 |
| --- | --- | --- | --- |
| Candidate는 timeline-relative span만으로 사용 가능 | 반영 | absolute display snapshot 추가하지 않음 | CaseView에서 현재 timeline 기준 projection 가능 |
| Candidate 표시 시각은 CaseView 단계에서 계산 가능 | 반영 | 결정 4 B안 유지 | Search 위치와 display time 책임 분리 |
| Candidate마다 `scope_id` 반복 저장 불필요 | 반영 | `run → input_ref → AnalysisScope`로 추적 | 데이터 중복 방지 |
| PARTIAL 처리에는 issue scope 정도면 충분 | 반영 | `issues[].scope_ref` 유지 | case가 partial coverage를 표현할 수 있음 |
| Candidate ordering은 `rank` 사용 가능 | 반영 | `rank` authoritative | raw score threshold 의존 방지 |
| Case Q1~Q5 전체 승인 | 반영 | 관련 Draft 추천 유지 | 기존 CaseView/ownership 원칙과 정합 |
| anchor 변환 책임 소재 확인 필요 | Contract 변경 없이 별도 확인 | Candidate schema 변경 없음 | 접합 capability 책임 문제 |
| Eval이 prediction 파일에서 cost/token/latency를 바로 사용하고 싶음 | **반영** | 결정 10 B안 → C안 | offline re-score 및 Efficiency 평가 |
| UsageRecord reference도 유지해야 함 | 반영 | `usage_refs[]` 유지 | authoritative Usage ownership 보존 |

---

# 6. 최종 Contract 핵심 요약

**Source of Truth:** [Final Data Contract — Contract 4 AnalysisRun + CandidateEvent v1](https://app.notion.com/p/Final-Data-Contract-Contract-4-AnalysisRun-CandidateEvent-v1-3d17ae78fc6a81bbbad3c56beea9fbd3?pvs=21) (`analysis-run-candidate-event/v1`)

Final `AnalysisRun + CandidateEvent` Contract의 구조적 특징은 다음과 같다.

- `AnalysisRun`은 public capability invocation 단위의 immutable logical run이다.
- 재실행은 기존 Run 수정이 아니라 새 Run 생성이다.
- public 의미에는 semantic `operation`을 사용한다.
- 내부 `COARSE/FINE` stage는 Contract에서 분리한다.
- `CandidateEvent`는 Run과 별도 entity다.
- Candidate는 자신을 생성한 `run_id`를 가진다.
- Candidate의 canonical 위치는 timeline-relative span이다.
- absolute display time은 Candidate의 authoritative 값이 아니다.
- Candidate ordering은 `rank`가 authoritative하다.
- `ranking_score`는 optional diagnostic이다.
- `event_type_hint`는 optional이다.
- Candidate에는 lightweight `summary` / `uncertainties[]`까지만 포함한다.
- 완료 outcome은 `SUCCEEDED | PARTIAL | FAILED`다.
- Candidate 0개는 정상 성공일 수 있다.
- 부분 실패는 `issues[]`로 표현한다.
- 상세 usage는 `UsageRecord`를 reference한다.
- Eval용 cost/token/latency는 immutable `usage_summary`에 함께 보존한다.
- implementation은 model뿐 아니라 prompt/config version까지 추적한다.
- raw provider payload는 공용 Contract에 포함하지 않는다.
- 법적 판단, 신고 유형, 최종 Evidence는 포함하지 않는다.

전체 필드 정의와 serialization은 **Final Data Contract**를 따른다.

---

# 7. Invariants / 보장사항

## `AnalysisRun`

1. 하나의 public capability logical invocation은 하나의 `AnalysisRun`으로 표현한다.
2. `run_id`는 다른 실행에서 재사용하지 않는다.
3. 완료된 `AnalysisRun`은 수정하지 않는다.
4. 동일 입력을 재실행해도 기존 Run을 덮어쓰지 않는다.
5. `completed_at >= started_at`.
6. `CANDIDATE_SEARCH`는 Candidate 0개를 정상 결과로 반환할 수 있다.
7. `SUCCEEDED + candidates=[]`은 오류가 아니다.
8. `FAILED`이면 usable Candidate를 반환하지 않는다.
9. `PARTIAL`이면 하나 이상의 issue가 존재한다.
10. `AnalysisRun`은 `QUEUED`, `RUNNING`, `STALE`을 표현하지 않는다.
11. 모든 Run은 implementation identity를 가져야 한다.
12. 모든 Run은 `contract_version`을 가져야 한다.
13. `usage_refs[]`는 해당 Run의 상세 UsageRecord를 추적할 수 있어야 한다.
14. `usage_summary`는 Run 완료 시점의 immutable snapshot이다.
15. 과거 pricing 변경 때문에 기존 `usage_summary`를 수정하지 않는다.
16. Search는 법적 위반이나 신고 유형을 AnalysisRun에 기록하지 않는다.
17. raw provider response를 공용 AnalysisRun Contract에 저장하지 않는다.

## `CandidateEvent`

1. `candidate_id`는 안정적인 reference여야 한다.
2. Candidate의 `run_id`는 자신을 생성한 Run과 일치해야 한다.
3. `span.start_ms >= 0`.
4. `span.start_ms < span.end_ms`.
5. `representative_ms`는 span 내부에 존재해야 한다.
6. 같은 Run 안에서 `rank`는 중복되지 않는다.
7. `rank`는 1 이상의 정수다.
8. `rank`가 Candidate ordering의 authoritative 값이다.
9. `ranking_score` 없이도 Candidate는 유효하다.
10. 서로 다른 `impl_id`의 `ranking_score`를 calibrated confidence로 비교하지 않는다.
11. Candidate span은 실제 SourceAsset/file boundary를 나타내지 않는다.
12. Candidate span은 최종 신고 `occurred_at`이 아니다.
13. `event_type_hint`는 법적 신고 유형이 아니다.
14. Candidate는 확정 Evidence가 아니다.
15. Candidate ranking을 변경하려면 과거 Candidate를 수정하지 않고 새 Run을 생성한다.
16. Candidate는 Incident Clip 또는 Report Video를 소유하지 않는다.

---

# 8. 이번 결정의 결과(Consequences)

## 긍정적 결과

- Consumer가 Search 내부 chunk/provider 구조를 알 필요가 없다.
- Search 구현 전략이 변경되어도 public Contract 의미가 유지된다.
- Candidate를 안정적인 독립 reference로 사용할 수 있다.
- Timeline rebase와 Search가 관찰한 실제 영상 위치가 분리된다.
- Recall@K 평가를 명시적인 `rank`로 수행할 수 있다.
- score calibration을 제품 로직과 분리할 수 있다.
- 정상 후보 0개와 실패를 구분할 수 있다.
- 일부 구간 실패에서도 usable Candidate를 유지할 수 있다.
- Runtime Job lifecycle과 Search domain result가 분리된다.
- implementation별 실행 재현성이 높아진다.
- provider-specific raw payload가 Consumer에 누출되지 않는다.
- Eval prediction 하나만으로 cost/token/latency를 다시 평가할 수 있다.
- 동시에 상세 Usage source-of-truth는 `UsageRecord`로 유지된다.

## 감수하는 비용 / 단점

- Run과 Candidate를 별도 entity로 관리해야 한다.
- Candidate display time을 사용하려면 Timeline projection이 한 단계 필요하다.
- `PARTIAL` 및 `issues[]` 때문에 단순 SUCCESS/FAILED schema보다 복잡하다.
- Consumer가 optional/null 필드 분기를 처리해야 한다.
- `summary`와 `uncertainties`는 자연어이므로 strict validation이 어렵다.
- implementation version metadata를 관리해야 한다.
- UsageRecord와 `usage_summary`에 일부 값이 중복된다.
- Usage snapshot 정합성을 Producer가 관리해야 한다.
- raw provider response debugging은 별도 내부 tooling이 필요하다.

---

# 9. 채택하지 않은 대안

| 대안 | 채택하지 않은 이유 |
| --- | --- |
| Provider call 하나마다 AnalysisRun 생성 | 내부 구현이 Consumer에 노출되고 logical Search 재구성 부담 발생 |
| `COARSE/FINE`을 public field로 유지 | 현재 구현 단계가 public semantic contract에 고정됨 |
| Candidate를 Run 내부에만 embed | 독립 Candidate reference가 어려움 |
| Candidate 위치를 absolute datetime으로만 저장 | Timeline rebase와 최종 occurred_at 의미가 섞임 |
| absolute display snapshot까지 Candidate에 저장 | 현재 case 요구가 없고 authoritative time으로 오해 가능 |
| score만으로 ordering 표현 | Recall@K와 confidence 의미가 혼재 |
| Candidate event type 필수 | Recall 우선 Candidate에 classification 책임까지 부여 |
| Candidate에 구조화 Evidence 포함 | `VisualEvidence` 책임과 중복 |
| SUCCESS/FAILED만 사용 | partial result 표현 불가 |
| Job lifecycle을 AnalysisRun에 포함 | common/runtime ownership과 충돌 |
| 단일 `failure_kind` | 복수 issue 및 partial coverage 표현 부족 |
| `usage_refs[]`만 제공 | Eval prediction 단독 Efficiency 분석 불가 |
| AnalysisRun이 usage 원천값을 단독 소유 | `UsageRecord`와 authoritative ownership 중복 |
| model 이름만 implementation identity로 사용 | prompt/config 변경을 구분할 수 없음 |
| raw provider response ref를 공용 Contract에 제공 | provider coupling과 privacy/retention 부담 증가 |

---

# 10. 다른 Contract에 미치는 영향

| 영향받는 Contract | 영향 내용 | 추가 수정 필요 여부 |
| --- | --- | --- |
| `AnalysisScope` | `AnalysisRun.input_ref`를 통해 Search 입력 추적 | 현재 추가 변경 없음 |
| `RecordingTimeline` | Candidate canonical span의 기준 | 현재 변경 없음 |
| `AssetSpan` / recording capability | Candidate span을 실제 파일/stream 범위로 해석 | 현재 변경 없음 |
| `FrameRef` | `thumbnail_ref`가 recording FrameRef 사용 | 정식 FrameRef 문법과 정합성 확인 필요 |
| `VisualEvidence` | Candidate보다 상세한 visual verification 책임 | 별도 Contract에서 정의 |
| `UsageRecord` | `usage_refs[]`의 authoritative source | `usage_summary`와 정합성 보장 필요 |
| `CaseView` | Candidate absolute display time projection | anchor→display 책임 확인 필요 |
| Eval Prediction | `usage_summary` 보존 필요 | **반영 필요** |

특히 결정 10의 C안 채택은 `UsageRecord` ownership을 변경하지 않는다.

Architecture v4에서 `UsageRecord`는 provider/model, processed duration, input/output usage, latency, pricing context, calculated cost 등을 추적하는 common/runtime 계약이다. fileciteturn0file0

이번 결정은 이 원천 ledger를 대체하는 것이 아니라, Eval prediction에 해당 Run의 immutable summary를 함께 저장하는 것이다.

---

# 11. Mock / 구현 / Evaluation에 미치는 영향

## Mock Dataset

다음 케이스가 반드시 포함되어야 한다.

### 정상

- Candidate 1개
- Candidate 여러 개
- 연속적인 `rank`
- `ranking_score` 존재
- usage summary 존재

### 후보 없음

```
SUCCEEDED + candidates=[]
```

### 부분 성공

```
PARTIAL
issues.length >= 1
usable Candidate 존재
```

### 전체 실패

```
FAILED
candidates=[]
```

### Optional / Missing

- `event_type_hint = null`
- `ranking_score = null`
- `summary = null`
- `thumbnail_ref = null`
- `uncertainties = []`
- token 값이 없는 usage
- cost를 계산할 수 없는 usage

### Usage

- UsageRecord 1개와 연결된 Run
- 여러 UsageRecord와 연결된 Run
- immutable `usage_summary`
- PARTIAL의 processed duration
- FAILED이지만 latency가 존재하는 예시

---

## 구현

### Producer — `search`

반드시:

- public capability invocation 기준으로 Run을 생성한다.
- 내부 chunk/provider call마다 Run을 생성하지 않는다.
- 재실행 시 새 Run을 생성한다.
- Candidate를 timeline-relative span으로 생성한다.
- Candidate별 안정적인 ID와 rank를 제공한다.
- `ranking_score`를 confidence로 보장하지 않는다.
- `SUCCEEDED`, `PARTIAL`, `FAILED`를 구분한다.
- partial issue에 필요한 scope 정보를 제공한다.
- implementation version metadata를 기록한다.
- 상세 usage를 UsageRecord와 연결한다.
- Eval용 immutable `usage_summary`를 제공한다.
- raw provider response를 공용 Contract에 노출하지 않는다.

### Consumer — `case`

반드시:

- Candidate를 `candidate_id`로 선택한다.
- ordering을 `rank` 기준으로 처리한다.
- `ranking_score` threshold를 Evidence 판단에 사용하지 않는다.
- `SUCCEEDED + []`을 정상 상태로 처리한다.
- `PARTIAL`을 전체 실패와 구분한다.
- Candidate span을 최종 `occurred_at`으로 사용하지 않는다.
- 사용자 표시 시간이 필요하면 Timeline projection을 사용한다.

### Consumer — `eval`

반드시:

- Recall@K를 `rank` 기준으로 계산한다.
- span error에 timeline-relative span을 사용한다.
- `SUCCEEDED`, `PARTIAL`, `FAILED`를 구분한다.
- implementation/version별 prediction을 분리한다.
- immutable prediction의 `usage_summary`에서 cost/token/latency를 읽을 수 있다.
- provider-call 수준 상세 분석이 필요한 경우 `usage_refs[]`를 사용한다.

---

## Evaluation

이 Contract에서 기존 평가를 위해 직접 제공하는 정보는 다음과 같다.

### Candidate Search

- Recall@1
- Recall@3
- Recall@10
- span/timestamp error
- FP

### Implementation 비교

- `impl_id`
- `model_ref`
- `prompt_version`
- `config_version`
- `contract_version`

### Efficiency

- processed duration
- token usage
- latency
- cost

Technical Spec에서는 Prediction과 Scoring을 분리해 기존 prediction을 다시 사용하고, Efficiency에서 cost와 latency 등을 별도로 평가하도록 정의한다. fileciteturn0file1

본 ADR에서는 새로운 평가 요구를 추가하지 않는다.

---

# 12. 변경 규칙

본 ADR이 Accepted된 이후 Contract 의미를 변경하려면 다음 절차를 따른다.

```
문제 발견
→ Producer / Consumer 확인
→ Data Contract 변경안 작성
→ Architecture 영향 확인
→ Contract Version 증가
→ ADR Supersede 또는 변경 ADR 작성
→ Mock Dataset 갱신
→ Consumer 구현 갱신
```

다음 변경은 ADR 변경 대상으로 본다.

- required / optional 의미 변경
- `AnalysisRun` 또는 `CandidateEvent` Ownership 변경
- public Run 단위 변경
- `operation` 의미 변경
- Candidate canonical time 표현 변경
- `rank` authoritative 의미 변경
- `outcome` 의미 변경
- PARTIAL/failure 의미 변경
- Run immutability 변경
- Usage ownership 변경
- `usage_summary` semantic 변경
- Producer/Consumer 책임 변경
- 다른 Contract의 구현을 깨뜨리는 reference 변경

다음과 같은 변경은 새로운 ADR을 요구하지 않는다.

- 오탈자 수정
- 설명 문구 개선
- 의미가 바뀌지 않는 예시 변경
- serialization 의미에 영향을 주지 않는 documentation 수정

---

# 13. 미해결 사항

Final Contract 자체의 주요 Architecture Decision은 확정되었다.

다만 다음 접합 사항은 별도 확인이 필요하다.

| 항목 | 왜 미해결인가 | 담당자 | 언제 결정해야 하는가 |
| --- | --- | --- | --- |
| Candidate absolute display 생성 시 anchor→display 변환 책임 | `case`는 relative span 사용에 동의했으나 실제 변환 capability의 책임 위치는 Review에서 별도 확인 요청 | 유소연(`case`), 정철원(`recording`) | CaseView–Recording 접합 구현 전 |
| `FrameRef` 정식 문법 | `thumbnail_ref`가 recording FrameRef를 사용하지만 exact syntax는 recording Contract 영역 | 정철원(`recording`) | Candidate thumbnail 실제 연동 전 |

위 항목은 현재 `AnalysisRun + CandidateEvent`의 최종 계약 구조를 변경하지 않는다.

---

# 14. 최종 한 줄 결정

> **우리는 `search`가 public capability invocation마다 불변 `AnalysisRun`을 생성하고 Recording Timeline 기준으로 순위화된 `CandidateEvent` span을 보장하며, 상세 usage는 `UsageRecord`로 연결하고 비용·token·latency는 immutable `usage_summary`로 함께 보존하여 `case`가 사용자 후보 선택에, `eval`이 Recall·span·비용 평가에 소비하도록 `AnalysisRun + CandidateEvent` 계약을 확정한다.**
>