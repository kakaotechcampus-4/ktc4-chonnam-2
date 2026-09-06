# ADR: VisualEvidence Data Contract 확정

**Status:** Accepted

> **⚠ 2026-09-05 정합성 보정 (PM · 김준영).** 본문의 `LANE_CHANGE`를 **`SOLID_LINE_LANE_CHANGE`**로 고쳤다(3곳). v4 §3-5가 baseline 4종을 `SIGNAL / CENTER_LINE_CROSSING / SOLID_LINE_LANE_CHANGE / MOTORCYCLE_HELMET_NON_USE`로 고정하고 Final 계약도 그 이름을 쓰는데 이 ADR만 옛 이름을 갖고 있었다.
>
> **결정 내용은 바뀌지 않았다 — 같은 값의 표기만 v4에 맞췄다.** 지원 범위 4종, 그 안에서 세 번째 항목이 「진로변경(백색 실선 침범)」인 것은 그대로다. 경위는 `adr-consistency-2026-09.md` C1-1.

**Contract:** `VisualEvidence`

**Producer:** `search`

**Consumer:** `evidence` — 김준영, `readout` — 신유민

**Owner:** 서어진 (`search` / Contract Lead)

**결정일:** 9/4

**관련 Contract Version:** `visual-evidence/v1.0`

**관련 Architecture Version:** `Module Architecture v4`

## 관련 문서

- Product Spec — `[직접 제공된 문서 버전 작성 필요]`
- Module Architecture v4
- Technical Spec v1.1
- `VisualEvidence` Data Contract Draft
- Consumer Review — 김준영 (`evidence`), 신유민 (`readout`)
- [Final Data Contract — Contract 5 VisualEvidence v1.0](https://app.notion.com/p/Final-Data-Contract-Contract-5-VisualEvidence-v1-0-3d17ae78fc6a81838841df7302a83929?pvs=21)

> 본 ADR이 확정한 결정의 **schema / serialization Source of Truth는 `visual-evidence/v1.0` Final Data Contract**다. Draft는 검토 대안과 Consumer Review 이력을 보존한다.
> 

---

# 1. 결정 배경(Context)

`VisualEvidence`는 `search`의 Fine / Classification 단계에서 영상으로부터 관찰한 **Visual Event, 대상 association, primitive, 시간적 사실 및 불확실성**을 다른 모듈로 전달하는 계약이다.

이 계약을 고정해야 했던 핵심 이유는 `search`가 생성하는 **시각적 관찰**과 `evidence`가 담당하는 **확정 Evidence 및 신고 정책 판단**을 데이터 수준에서도 분리하면서, 동시에 `readout`이 대상 차량 association을 위한 충분한 hint를 받을 수 있게 해야 했기 때문이다.

## Producer가 생성하는 것

`search`는 Fine / Classification 분석 결과로 다음 의미의 데이터를 생성한다.

- 지원 Visual Event가 관찰되었는지 여부
- 관찰된 Visual Event 종류
- 대상 차량 또는 객체에 대한 association observation
- 판단에 사용된 visual primitive
- temporal fact 또는 object attribute observation
- 영상 품질이나 대상 모호성 등에 따른 uncertainty
- 어떤 Fine 실행과 어떤 분석 입력에서 생성됐는지를 추적하기 위한 provenance

이 값들은 모두 **관찰 결과**이며 최종 신고 Evidence가 아니다.

## Consumer가 필요로 하는 것

### `evidence`

`evidence`는 `VisualEvidence`를 다음 단계의 입력으로 사용한다.

- Visual Event 관찰 결과 확인
- 사건이 관찰되지 않은 경우와 판단하지 못한 경우의 구분
- Visual Event를 이후 신고 정책과 연결하기 위한 안정적인 입력
- 확정 Evidence가 어떤 Search 관찰에 근거했는지 provenance 보존

단, `evidence`는 Search 내부 primitive taxonomy나 numeric confidence에 직접 정책적으로 결합하지 않는다.

### `readout`

`readout`은 대상 차량 또는 객체를 다시 association할 때 `VisualEvidence.target`을 optional hint로 사용할 수 있어야 한다.

그러나 Search가 항상 tracking 정보를 제공할 수 있는 것은 아니므로 `track_ref`가 없어도 동작해야 한다.

## 계약을 고정해야 했던 이유

계약을 고정하지 않으면 다음 문제가 발생할 수 있었다.

- Fine 결과가 `CandidateEvent`에 강하게 결합되어 candidate가 없는 Eval 입력을 처리하지 못함
- 사건이 실제로 없었던 경우와 영상이 불충분해 판단하지 못한 경우가 같은 `null`로 표현됨
- Search가 Visual Event를 넘어 법적 위반 또는 신고 유형을 표현하게 됨
- `evidence`가 Search 내부 primitive 구조에 직접 결합됨
- 하나의 global confidence가 서로 다른 불확실성을 섞어 표현함
- 부분적으로 확보된 관찰이 전체 실패와 함께 폐기됨
- `readout`이 `track_ref` 존재를 전제로 구현될 위험이 생김
- 실행 자체 실패와 정상 실행 후 불확실한 결과가 동일한 상태로 취급될 수 있음

따라서 Draft 단계에서 위 문제들에 대해 복수의 대안을 검토했고, Consumer Review 후 Final Contract v1.0으로 구조를 확정했다.

---

# 2. 결정 시 적용한 제약조건

| 제약 | 출처 | 이 Contract에 미친 영향 |
| --- | --- | --- |
| `search`와 `readout`은 관찰하고 `evidence`가 확정한다 | Module Architecture v4 | `VisualEvidence`가 법적 위반, Report Type, Evidence sufficiency 등을 표현하지 않도록 경계를 설정 |
| Search는 Visual Event까지만 다룬다 | Module Architecture v4 | `visual_event_type`과 SafetyReport Report Type / violation expression을 분리 |
| Fine / Classification은 Candidate 없이도 public capability로 실행 가능해야 한다 | Module Architecture v4 | `candidate_id`를 필수 identity로 사용하지 않고 `input_ref`를 필수로 채택 |
| 제품과 Eval은 같은 public capability를 사용하며 `eval_mode` branch를 만들지 않는다 | Module Architecture v4 | Candidate-independent `VisualEvidence` 구조 채택 |
| `target_hint`와 `track_ref`는 optional이다 | Module Architecture v4 | `track_ref = null`을 정상 상태로 인정하고 readout의 필수 입력으로 만들지 않음 |
| 초기 지원 범위는 4종 Visual Event다 | Product/Technical Spec | `SIGNAL`, `CENTER_LINE_CROSSING`, `SOLID_LINE_LANE_CHANGE`, `MOTORCYCLE_HELMET_NON_USE`를 `VisualEventType`으로 고정 |
| 안전모 사건은 temporal event보다 object attribute 성격이 강하다 | Technical Spec | event별 전용 schema 대신 공통 primitive 구조를 사용하고 `temporal_facts=[]`을 허용 |
| Fine 평가에서 Hard-negative FPR과 target correctness가 중요하다 | Technical Spec / Eval 요구 | `NOT_OBSERVED`와 `UNCERTAIN`을 분리 |
| Search 실행 결과는 immutable run에 종속된다 | Module Architecture v4 | 재실행 시 기존 결과 수정 대신 새 `AnalysisRun` / `VisualEvidence` 생성 |
| Candidate score와 Fine 관찰은 서로 다른 단계의 의미다 | Architecture 구조 및 Draft | Candidate score를 `VisualEvidence` confidence로 복제하지 않음 |
| AI가 법적 판단을 최종 확정해서는 안 된다 | Product/Technical Spec, Module Architecture | `legal_status`를 항상 `null`로 강제하고 non-null을 validation failure로 처리 |
| 불확실한 값을 억지로 확정하지 않는다 | Product/Technical Spec | 부분 관찰을 `UNCERTAIN`으로 보존하고 실행 실패와 분리 |

---

# 3. 검토했던 주요 선택지

## 결정 1. `VisualEvidence`를 Candidate에 강하게 종속시킬 것인가

### A안 — Candidate-bound Result

`candidate_id`를 Fine 결과의 필수 identity로 사용한다.

**장점**

- 제품 runtime에서 Candidate → Fine 결과 관계가 단순하다.
- Candidate FK를 중심으로 저장 구조를 구성하기 쉽다.

**단점**

- Candidate가 없는 Eval fixture를 직접 처리할 수 없다.
- Eval을 위해 가짜 Candidate를 만들거나 별도 분기를 둘 가능성이 생긴다.
- candidate-independent Fine이라는 Architecture v4 요구와 충돌한다.

### B안 — Generic Input 중심 + Candidate Optional

`input_ref`를 실제 Fine 입력의 필수 identity로 사용하고 `candidate_id`는 존재하는 경우에만 연결한다.

**장점**

- 제품과 Eval에서 같은 Fine capability와 Contract를 사용할 수 있다.
- Candidate 없이 clip / frame sequence를 직접 검증할 수 있다.
- 실제 분석한 입력 provenance와 Candidate linkage를 분리할 수 있다.

**단점**

- `candidate_id`가 항상 존재한다고 가정할 수 없다.
- `input_ref` 자체의 reference 의미를 별도로 정의해야 한다.

---

## 결정 2. 법적 판단 금지를 Contract에서 어떻게 강제할 것인가

### A안 — `legal_status: null` Sentinel 유지

`legal_status` 필드를 존재시키되 값은 반드시 `null`로 제한한다.

**장점**

- JSON과 schema에서 Search가 법적 판단을 하지 않는다는 경계가 명시적으로 드러난다.
- 기존 Architecture의 `legal_status = null` 원칙과 직접 일치한다.
- validation으로 non-null 값을 거부할 수 있다.

**단점**

- 실제 정보가 없는 sentinel field를 항상 직렬화해야 한다.
- 필드가 존재하기 때문에 잘못된 확장을 시도할 가능성 자체는 남는다.

### B안 — 필드 제거 + 법적 판단 관련 Extra Field 금지

`legal_status` 자체를 제거하고 schema가 관찰 정보만 허용하도록 한다.

**장점**

- 법적 판단 값을 표현하는 통로 자체를 제거할 수 있다.
- Consumer가 해당 필드에 잘못 의존할 가능성이 없다.

**단점**

- 기존 Architecture가 명시한 `legal_status = null` 표현과 달라진다.
- 계약 데이터만 보았을 때 법적 판단 금지 경계가 덜 명시적으로 보일 수 있다.

---

## 결정 3. Fine 결과의 사건 상태를 어떻게 표현할 것인가

### A안 — `visual_event_type`만 사용

관찰된 사건이 있으면 event type을 기록하고, 사건이 없거나 판단하지 못하면 모두 `null`로 처리한다.

**장점**

- 구조가 가장 단순하다.

**단점**

- 정상적인 hard-negative와 판단 불가를 구분할 수 없다.
- Fine HN-FPR 및 failure diagnostics에 불리하다.
- Consumer가 `null`의 의미를 추가 context로 추론해야 한다.

### B안 — Event Type + Verification State 분리

다음 세 상태를 별도로 사용한다.

```
OBSERVED
NOT_OBSERVED
UNCERTAIN
```

**장점**

- 사건 없음과 판단 불가를 명시적으로 구분한다.
- Fine Hard-negative 평가에 적합하다.
- 실행 실패와 정상적인 불확실성도 분리할 수 있다.

**단점**

- `verification`과 `visual_event_type` 사이 invariant가 추가된다.
- Consumer가 세 상태를 처리해야 한다.

---

## 결정 4. Visual Evidence를 Event별 전용 Schema로 만들 것인가

### A안 — Event별 전용 Evidence Schema

각 Visual Event마다 서로 다른 구조를 정의한다.

예를 들어 lane change와 helmet non-use가 서로 다른 필드 집합을 갖는다.

**장점**

- 각 사건의 의미가 구체적이고 명확하다.
- 특정 유형을 구현할 때 필요한 필드를 직접 사용할 수 있다.

**단점**

- 사건 유형이 늘수록 Contract가 계속 확장된다.
- Search 내부 perception 설계가 외부 Consumer 계약으로 노출된다.
- Consumer가 각 사건별 내부 구조에 결합될 수 있다.

### B안 — 공통 Primitive + Temporal Fact

공통 구조인:

```
primitives[]
temporal_facts[]
```

를 사용하고, 안전모와 같이 temporal fact가 필요하지 않은 사건은 빈 배열을 허용한다.

**장점**

- temporal event와 object attribute event를 하나의 상위 구조로 표현할 수 있다.
- Search 내부 routing과 Consumer Contract의 결합을 줄인다.
- Fine diagnostics와 Eval에도 동일 구조를 사용할 수 있다.

**단점**

- primitive / fact vocabulary를 별도로 관리해야 한다.
- 지나치게 generic하게 사용하면 문자열 convention에 의존할 위험이 있다.

---

## 결정 5. Confidence를 하나의 점수로 제공할 것인가

### A안 — Global Confidence

`VisualEvidence` 전체에 단일 confidence를 제공한다.

**장점**

- 정렬이나 threshold 적용이 단순하다.
- Consumer와 UI가 하나의 숫자만 다루면 된다.

**단점**

- target association, primitive detection, event verification 중 무엇에 대한 confidence인지 불명확하다.
- Consumer가 이를 최종 사건 확률처럼 사용할 위험이 있다.
- 모델 또는 provider 변경 시 calibration 의미가 달라질 수 있다.

### B안 — Component Confidence만 제공

전체 confidence는 두지 않고 필요한 component에서만 optional confidence를 제공한다.

예:

```
target.association_confidence
primitives[].confidence
```

**장점**

- 숫자의 의미가 특정 관찰 component에 한정된다.
- 서로 다른 종류의 불확실성을 섞지 않는다.
- Consumer가 global score를 Evidence confidence로 오용하기 어렵다.

**단점**

- 하나의 숫자로 정렬하거나 표시하려면 별도 projection이 필요하다.
- Consumer가 여러 optional confidence를 처리해야 한다.

### C안 — Global + Component Confidence

전체 confidence와 component confidence를 모두 제공한다.

**장점**

- 단순 정렬과 세부 diagnostics를 동시에 지원할 수 있다.

**단점**

- 두 종류의 confidence 사이 관계를 추가로 정의해야 한다.
- 실제 Consumer가 global confidence에만 의존하게 될 가능성이 있다.

---

## 결정 6. 일부 관찰만 성공한 Fine 결과를 보존할 것인가

### A안 — All-or-Nothing

필요한 판단이 모두 끝난 경우에만 `VisualEvidence`를 생성하고, 그렇지 않으면 실행 실패로 처리한다.

**장점**

- 성공한 `VisualEvidence`의 상태가 단순하다.
- Consumer가 partial component를 적게 처리해도 된다.

**단점**

- 이미 확보한 target / primitive observation을 잃는다.
- 정상적인 불확실성과 시스템 실행 실패를 구분하기 어렵다.
- Eval failure analysis에 필요한 정보가 사라진다.

### B안 — Partial Evidence 보존

Fine 실행이 정상적으로 완료됐다면 확보한 관찰을 보존하고:

```
verification = UNCERTAIN
```

으로 표현한다.

**장점**

- 정상적인 불확실성과 실행 실패를 분리한다.
- 확보한 observation을 diagnostics와 재검토에 사용할 수 있다.
- Fine failure taxonomy 분석에 유리하다.

**단점**

- Consumer가 `UNCERTAIN`과 부분 component를 처리해야 한다.
- 상태 invariant가 All-or-Nothing보다 많아진다.

---

# 4. 최종 결정

## 4-1. 결정 요약

| 결정 항목 | 최종 선택 | Draft 추천 | Consumer 의견 | 최종 변경 여부 |
| --- | --- | --- | --- | --- |
| Fine identity / Candidate linkage | **B안 — `input_ref` 필수 + `candidate_id` optional** | B안 | `evidence`, `readout` 모두 승인 | 유지 |
| 법적 판단 금지 | **A안 — `legal_status: null` 유지 및 validation 강제** | A안 | `evidence` 승인 | 유지 |
| Fine 관찰 상태 | **B안 — `OBSERVED / NOT_OBSERVED / UNCERTAIN`** | B안 | `evidence` 승인 | 유지 |
| Event evidence 구조 | **B안 — 공통 primitive + temporal fact** | B안 | `evidence` 승인 | 유지 |
| Confidence | **B안 — global 제거, component optional** | B안 | `evidence`, `readout` 승인 | 유지 |
| Partial Fine result | **B안 — `UNCERTAIN`으로 보존** | B안 | `evidence` 승인 | 유지 |

Consumer Review에서 Draft의 핵심 추천안을 뒤집는 요청은 없었다.

대신 Review를 통해 몇 가지 의미가 더 명확해졌다.

- `evidence`는 Candidate 객체 자체에 의존하지 않는다.
- `input_ref`를 Consumer가 직접 파싱해 Source 구조를 해석하지 않는다.
- `UNCERTAIN`과 `NEEDS_REVIEW`를 같은 모듈의 상태로 합치지 않는다.
- 실행 오류는 `AnalysisRun`에서 표현한다.
- primitive는 Evidence policy의 안정적인 입력이 아니다.
- `PARTIAL / COMPLETE` 같은 별도 completeness enum을 만들지 않는다.
- UI에 raw confidence를 직접 노출하지 않는다.
- `readout`은 `track_ref` 없이도 자체 association을 수행할 수 있다.

---

## 결정 1. Fine identity를 `input_ref` 중심으로 정의한다

**최종 선택:** B안

**결정 내용**

`VisualEvidence`는 다음 identity 구조를 갖는다.

```
visual_evidence_id   필수
run_id               필수
input_ref             필수
candidate_id          optional
```

제품 runtime의 Candidate 기반 Fine과 Eval의 candidate-less Fine 모두 동일한 Contract를 사용한다.

**선택 이유**

### Architecture 측면

Module Architecture v4가 Fine / Classification public capability를 Candidate 객체에만 묶지 않도록 요구한다.

제품은 Candidate span에서 Fine input을 만들고 Eval은 clip 또는 frame sequence fixture에서 직접 Fine input을 만들기 때문에 Candidate를 필수 identity로 삼을 수 없다.

### Consumer 측면

`evidence`는 Candidate 객체 자체에 의존할 필요가 없으며, 필요한 경우 어떤 `VisualEvidence`를 근거로 사용했는지를 참조하면 충분하다고 확인했다.

`readout` 역시 `candidate_id`가 없어도 선택된 분석 입력과 target hint를 이용해 association을 수행할 수 있다고 확인했다.

### Evaluation 측면

Candidate가 없는 AI-Hub frame sequence 등의 Fine classification input을 별도 `eval_mode` 없이 동일 public capability로 실행할 수 있다.

**감수하는 점**

`input_ref`의 실제 reference schema는 별도의 Fine Input 계약에서 정의되어야 한다.

---

## 결정 2. `legal_status: null` sentinel을 유지한다

**최종 선택:** A안

**결정 내용**

Final Contract는 다음을 필수 invariant로 둔다.

```
legal_status MUST exist
legal_status MUST equal null
```

non-null 값은 validation failure다.

**선택 이유**

### Architecture / Ownership 측면

Module Architecture v4에서 Search는 Visual Event까지만 관찰하고 법적/신고 의미는 `evidence`가 담당한다고 명시되어 있다.

`legal_status = null`은 이 경계를 serialization에서도 명시적으로 표현한다.

### Consumer 측면

`evidence`는 `legal_status` 값을 실제 policy input으로 사용하지 않는다.

Consumer Review에서는 null sentinel이 관찰과 확정의 경계를 스키마에서도 보여주므로 현재 Contract에 적합하다고 판단했다.

또한 단순 optional이 아니라 **null 외의 값 자체를 validation에서 거부해야 한다**는 점을 확인했다.

**감수하는 점**

실제 정보를 전달하지 않는 sentinel field 하나가 항상 존재한다.

필드를 완전히 제거하는 B안보다 표현 가능한 표면적은 넓지만, validation으로 non-null을 금지한다.

---

## 결정 3. Fine 관찰 상태를 3-state verification으로 표현한다

**최종 선택:** B안

**결정 내용**

```
OBSERVED
NOT_OBSERVED
UNCERTAIN
```

만 사용한다.

관계는 다음과 같이 고정한다.

```
OBSERVED
→ visual_event_type != null

NOT_OBSERVED
→ visual_event_type == null

UNCERTAIN
→ visual_event_type == null
```

**선택 이유**

### Evaluation 측면

Fine의 Hard-negative FPR을 측정하려면:

```
사건이 없다고 정상적으로 판단한 결과
```

와:

```
판단하지 못한 결과
```

를 구분해야 한다.

### Consumer 측면

`evidence`는 `NOT_OBSERVED`를 정상적으로 실행된 유효한 관찰 결과로 보존할 필요가 있다고 확인했다.

동시에 `UNCERTAIN`과 `NEEDS_REVIEW`를 합치지 않기로 했다.

`UNCERTAIN`은 Search의 observation state이고, 실제 사람 검토 필요 여부는 `case` 또는 `evidence` workflow가 결정한다.

### Failure Boundary 측면

Fine 실행 자체의 API timeout, model error, parsing failure 등은 `AnalysisRun`의 failure로 표현한다.

따라서:

```
UNCERTAIN ≠ FAILED
```

경계가 유지된다.

**감수하는 점**

Consumer와 테스트가 세 상태 및 event type invariant를 모두 처리해야 한다.

---

## 결정 4. Event별 전용 schema 대신 공통 primitive 구조를 사용한다

**최종 선택:** B안

**결정 내용**

Visual Event 근거는 공통적으로 다음으로 표현한다.

```
primitives[]
temporal_facts[]
uncertainties[]
```

안전모 미착용과 같은 object attribute 사건에서는:

```
temporal_facts = []
```

도 유효하다.

**선택 이유**

### Product / Technical Spec 측면

초기 4종 가운데:

```
SIGNAL
CENTER_LINE_CROSSING
SOLID_LINE_LANE_CHANGE
```

는 시간적 관계의 비중이 큰 반면:

```
MOTORCYCLE_HELMET_NON_USE
```

는 객체 속성 관찰의 성격이 강하다.

하나의 temporal-only schema로는 네 유형을 자연스럽게 표현하기 어렵다.

### Architecture 측면

Event별 Search 내부 routing과 perception 설계를 Consumer Contract에 그대로 노출하지 않는다.

### Consumer 측면

`evidence`는 primitive `kind`에 직접 의존해 신고 정책을 판단하지 않는다고 확인했다.

안정적인 cross-module semantic input은:

```
visual_event_type
```

이고 primitives는 provenance, 설명, debugging, evaluation diagnostics 용도로 유지한다.

**감수하는 점**

primitive, temporal fact, uncertainty의 vocabulary를 Search 영역에서 별도로 관리해야 한다.

---

## 결정 5. Global Confidence를 두지 않는다

**최종 선택:** B안

**결정 내용**

다음 top-level field는 만들지 않는다.

```
VisualEvidence.confidence
```

대신 필요한 경우 다음과 같이 component confidence만 제공한다.

```
target.association_confidence
primitives[].confidence
```

confidence 자체도 Producer가 의미 있는 값을 제공할 수 있을 때만 사용한다.

**선택 이유**

### 의미 측면

target association confidence와 primitive detection confidence는 서로 다른 의미를 갖는다.

이를 하나의 숫자로 합치면 무엇에 대한 confidence인지 불명확해진다.

### Consumer 측면

`evidence`는 numeric confidence를 직접 policy input으로 사용할 계획이 없다고 확인했다.

구조화된:

```
OBSERVED / NOT_OBSERVED / UNCERTAIN
```

상태를 우선 사용한다.

`readout` 역시 association confidence를 보조 hint로만 사용 가능하다고 확인했다.

### UI 측면

raw confidence를 Web에 직접 노출할 필요가 없으며, 사용자 표시가 필요하면 `case`가 `CaseView`용 상태로 projection한다.

**감수하는 점**

하나의 숫자로 결과를 정렬하거나 사용자에게 표시하려는 Consumer는 별도 projection을 거쳐야 한다.

---

## 결정 6. 정상 실행에서 확보한 Partial Evidence를 보존한다

**최종 선택:** B안

**결정 내용**

Fine 실행은 성공했지만 전체 사건 판단이 불충분하면:

```
VisualEvidence 존재
verification = UNCERTAIN
```

으로 처리하고 이미 확보한 target / primitive / temporal observation을 보존한다.

반대로 실행 자체가 실패하면:

```
VisualEvidence 없음
AnalysisRun.status = FAILED
```

로 처리한다.

별도의:

```
PARTIAL
COMPLETE
```

enum은 만들지 않는다.

**선택 이유**

### Consumer 측면

`evidence`는 `UNCERTAIN`도 정상 실행을 통해 얻어진 유효한 관찰 결과이므로 보존할 가치가 있다고 확인했다.

단, 실제 사용자 review에 노출할지 여부는 `case` workflow의 책임이다.

### Evaluation / Diagnostics 측면

일부 primitive와 target까지 확보했는데 temporal relation만 불명확했던 경우와 provider 자체가 실패한 경우를 구분할 수 있다.

### Contract 단순성 측면

Consumer Review에서 별도 completeness enum은 `verification` 및 각 component의 상태와 중복되고 불필요한 상태 조합을 늘릴 수 있다고 판단했다.

**감수하는 점**

Consumer가 `UNCERTAIN` result에도 일부 component가 존재할 수 있음을 처리해야 한다.

---

# 5. Consumer Review 반영 내용

| Consumer 피드백 | 반영 여부 | Final Contract 반영 | 이유 |
| --- | --- | --- | --- |
| `evidence`는 Candidate 객체 자체에 의존할 필요가 없음 | 반영 | `input_ref` 필수 / `candidate_id` optional 유지 | Candidate-independent Fine과 동일 Contract 사용 가능 |
| `input_ref`를 Consumer가 직접 해석해 Source 구조를 알아내지 않음 | 반영 | `input_ref`를 opaque reference로 취급 | recording/case 책임과 Search Consumer의 결합 방지 |
| `legal_status`는 실제 Evidence 입력으로 사용하지 않음 | 반영 | `legal_status=null` sentinel 유지 | 관찰/확정 경계를 schema에서도 명시 |
| `legal_status`는 null 이외 값을 validation에서 거부해야 함 | 반영 | non-null validation failure를 invariant로 확정 | 법적 판단 침범을 구현 수준에서 차단 |
| `NOT_OBSERVED`는 유효한 Fine 결과로 보존해야 함 | 반영 | verification 3-state 유지 | 실행 실패 및 미실행과 구분 |
| `UNCERTAIN`과 `NEEDS_REVIEW`를 분리해야 함 | 반영 | `NEEDS_REVIEW`를 verification enum에 추가하지 않음 | Search observation과 workflow policy의 책임 분리 |
| Fine 실행 자체 오류는 `AnalysisRun`에서 표현하면 충분 | 반영 | 실행 실패 시 `VisualEvidence`를 생성하지 않음 | observation uncertainty와 execution failure 분리 |
| `evidence`는 primitive kind를 policy input으로 직접 사용하지 않음 | 반영 | primitive taxonomy를 Search-owned diagnostic/provenance로 정의 | Search 내부 perception 구조와 Evidence 정책의 결합 방지 |
| `track_ref` 없이도 readout association 가능 | 반영 | `track_ref` optional 유지 | Search tracking 구현 유무와 readout 실행 분리 |
| Global confidence 없어도 구현 가능 | 반영 | top-level confidence 제거 | 숫자의 의미 혼동 방지 |
| Web에는 raw confidence 대신 CaseView projection이면 충분 | 반영 | raw confidence의 UI 안정 contract 사용 금지 | web이 raw score를 직접 해석하지 않는 Architecture 원칙 유지 |
| `UNCERTAIN` 결과도 보존할 가치가 있음 | 반영 | partial observation 보존 | 정상 불확실성과 실행 실패 구분 |
| 별도 `PARTIAL / COMPLETE` enum 불필요 | 반영 | completeness enum 추가하지 않음 | 상태 조합 증가 방지 |

Consumer Review 과정에서 Draft 추천안 자체를 다른 선택지로 변경한 항목은 없다.

대신 Consumer의 구현 관점 피드백을 통해 각 선택의 **사용 범위와 금지 의존성**이 Final Contract에서 더 명확해졌다.

---

# 6. 최종 Contract 핵심 요약

Final `VisualEvidence v1.0`의 구조적 특징은 다음과 같다.

- 하나의 `VisualEvidence`는 immutable Fine / Classification result다.
- `run_id`와 `input_ref`는 필수다.
- `candidate_id`는 optional이다.
- Candidate가 없는 Eval에서도 동일 Contract를 사용한다.
- 관찰 상태는 `OBSERVED / NOT_OBSERVED / UNCERTAIN`으로 구분한다.
- `OBSERVED`일 때만 `visual_event_type`을 가진다.
- 지원 `VisualEventType`은 초기 4종이다.
- event 근거는 공통 `primitives[] + temporal_facts[]` 구조를 사용한다.
- object attribute 사건에서 `temporal_facts=[]`은 정상이다.
- `target.track_ref`는 optional이다.
- global confidence는 존재하지 않는다.
- component confidence만 선택적으로 제공한다.
- 정상 실행에서 확보한 부분 관찰은 `UNCERTAIN`으로 보존한다.
- 실행 자체 실패는 `AnalysisRun`에서 표현한다.
- `legal_status`는 반드시 존재하며 항상 `null`이다.
- Search는 Report Type, violation expression, occurred_at, 확정 번호판, 확정 위치, 신고 가능 여부를 소유하지 않는다.

전체 field 및 serialization 정의는 [Final Data Contract — Contract 5 VisualEvidence v1.0](https://app.notion.com/p/Final-Data-Contract-Contract-5-VisualEvidence-v1-0-3d17ae78fc6a81838841df7302a83929?pvs=21) (`visual-evidence/v1.0`)을 따른다.

---

# 7. Invariants / 보장사항

다음 규칙은 구현 및 자동 Contract Test에서 확인할 수 있어야 한다.

## Identity / Lifecycle

1. `visual_evidence_id`는 하나의 VisualEvidence result를 고유하게 식별한다.
2. `run_id`는 반드시 존재한다.
3. `input_ref`는 반드시 존재한다.
4. `candidate_id`는 없어도 정상이다.
5. 재실행 시 기존 VisualEvidence를 수정하지 않는다.
6. 재실행은 새로운 `AnalysisRun`과 새로운 VisualEvidence result를 생성한다.

## Verification

1. `verification`은 `OBSERVED / NOT_OBSERVED / UNCERTAIN` 중 하나다.
2. `OBSERVED`이면 `visual_event_type != null`이다.
3. `NOT_OBSERVED`이면 `visual_event_type == null`이다.
4. `UNCERTAIN`이면 `visual_event_type == null`이다.
5. 실행 자체 실패를 `UNCERTAIN`으로 표현하지 않는다.

## Ownership

1. `legal_status`는 반드시 존재한다.
2. `legal_status`의 값은 반드시 `null`이다.
3. non-null `legal_status`는 validation failure다.
4. `report_type`, `violation_expression`, `requirement_status`, `evidence_sufficient`, `package_ready`를 `VisualEvidence`에 추가하지 않는다.

## Target

1. `track_ref = null`은 정상 상태다.
2. `association_status = MATCHED`여도 `track_ref = null`일 수 있다.
3. `readout`은 `track_ref` 존재를 실행 전제조건으로 삼지 않는다.
4. `MATCHED`는 최종 법적 행위 주체 확정을 의미하지 않는다.

## Collection / Partial Result

1. `primitives`, `temporal_facts`, `uncertainties`는 항상 배열이다.
2. 빈 배열은 정상이다.
3. `MOTORCYCLE_HELMET_NON_USE`에서 `temporal_facts=[]`은 유효하다.
4. `UNCERTAIN` result에도 target 또는 primitive observation이 존재할 수 있다.

## Confidence

1. top-level global confidence는 존재하지 않는다.
2. component confidence가 존재하면 `[0.0, 1.0]` 범위다.
3. confidence가 없음을 `0.0`으로 변환하지 않는다.
4. `CandidateEvent.score`를 VisualEvidence confidence로 복사하지 않는다.
5. Consumer business policy가 raw confidence에 직접 의존하지 않는다.

## Time / Provenance

1. `TemporalFact.at_offset_ms`는 Fine input 내부 relative offset이다.
2. 이를 신고용 `occurred_at`으로 해석하지 않는다.
3. visual evidence provenance는 Source 또는 Source-derived Incident Clip pixel을 가리켜야 한다.
4. Evidence 확정 뒤 사후 Timestamp가 삽입된 Report Video frame을 VisualEvidence의 관찰 근거로 사용하지 않는다.

---

# 8. 이번 결정의 결과(Consequences)

## 긍정적 결과

### 1. 제품과 Eval이 동일한 Fine Contract를 사용할 수 있다

Candidate를 필수 identity에서 제거했기 때문에 제품 Candidate와 독립 Eval fixture가 같은 `verify_visual` capability를 사용할 수 있다.

별도 `eval_mode`가 필요하지 않다.

### 2. 관찰과 확정의 책임 경계가 데이터에서도 유지된다

`legal_status=null` 및 Visual Event / Report Type 분리를 통해 Search 결과가 신고 또는 법적 확정값으로 확대되는 것을 제한한다.

### 3. Hard Negative와 불확실성을 구분할 수 있다

`NOT_OBSERVED`와 `UNCERTAIN`을 구분하므로 Fine evaluation과 runtime diagnostics에서 의미가 명확하다.

### 4. 서로 다른 4종 Visual Event를 하나의 상위 Contract로 표현할 수 있다

temporal event와 object attribute event를 공통 primitive 구조로 표현한다.

### 5. Consumer가 Search 내부 perception 구조에 덜 결합된다

`visual_event_type`을 안정적 semantic contract로 두고 primitive는 근거/진단용으로 제한했다.

### 6. Confidence 의미의 혼동을 줄인다

전체 사건에 대한 단일 확률처럼 보이는 global confidence가 없다.

### 7. 정상적으로 얻은 부분 관찰을 보존할 수 있다

Fine이 완전한 결론을 내리지 못해도 target, primitive 등의 observation을 잃지 않는다.

### 8. Search tracking 구현과 readout을 분리할 수 있다

`track_ref`를 optional로 유지하므로 tracking 구현이 없어도 readout pipeline이 동작할 수 있다.

---

## 감수하는 비용 / 단점

### 1. Contract 상태 조합이 단순 event type 하나보다 많다

Consumer는:

```
OBSERVED
NOT_OBSERVED
UNCERTAIN
```

과 component의 존재 여부를 함께 처리해야 한다.

### 2. `input_ref` 관련 별도 계약이 필요하다

Candidate-independent 구조를 선택한 대가로 Fine input reference의 정확한 의미가 다른 계약에서 정의되어야 한다.

### 3. Primitive vocabulary 관리가 필요하다

공통 generic 구조를 사용하므로 `kind`, `fact`, `uncertainty kind`의 vocabulary를 Search에서 관리해야 한다.

### 4. 단일 정렬 점수를 바로 사용할 수 없다

global confidence가 없으므로 하나의 숫자가 필요한 화면 또는 ranking에서는 별도 projection이 필요하다.

### 5. Partial result를 Consumer가 처리해야 한다

`UNCERTAIN`이라고 해서 모든 component가 비어 있는 것이 아니므로 Consumer가 partial observation을 허용해야 한다.

### 6. `legal_status` sentinel serialization 비용이 남는다

항상 `null`인 필드를 유지한다는 소규모 schema 복잡성을 감수한다.

---

# 9. 채택하지 않은 대안

| 대안 | 채택하지 않은 이유 |
| --- | --- |
| Candidate-bound Fine | Candidate 없는 Eval input을 동일 public capability로 처리할 수 없고 Architecture v4의 candidate-independent Fine과 충돌 |
| `legal_status` 필드 제거 | 더 강한 boundary일 수 있으나 현재 Architecture의 명시적 `legal_status=null` 원칙과 Consumer Review가 null sentinel 유지를 지지 |
| `visual_event_type` 단독 표현 | `NOT_OBSERVED`와 `UNCERTAIN`을 구분할 수 없어 Hard-negative 평가 및 Consumer 의미 해석이 약해짐 |
| Event별 전용 Evidence Schema | Search 내부 event routing / perception 구조가 Consumer Contract로 노출되고 유형 추가 시 coupling 증가 |
| Global Confidence | 무엇에 대한 confidence인지 불분명하고 Evidence 또는 UI에서 최종 확률처럼 오용될 위험 |
| Global + Component Confidence | 두 점수의 관계를 추가로 정의해야 하고 global 값에 Consumer가 의존할 위험 |
| All-or-Nothing Fine | 정상 실행에서 확보한 observation을 잃고 실행 실패와 불확실성을 구분하기 어려움 |
| 별도 `PARTIAL / COMPLETE` 상태 | `verification` 및 component 존재 여부와 중복되어 상태 조합만 증가 |
| `NEEDS_REVIEW`를 Search verification에 포함 | review 여부는 Search observation이 아니라 `case` / `evidence` workflow 책임 |

---

# 10. 다른 Contract에 미치는 영향

| 영향받는 Contract / 영역 | 영향 내용 | 추가 수정 필요 여부 |
| --- | --- | --- |
| `AnalysisRun` | Fine 실행 실패는 `VisualEvidence.UNCERTAIN`이 아니라 `AnalysisRun.status/failure_kind`에서 표현해야 함 | 기존 의미와 정합. 구현 시 확인 필요 |
| `CandidateEvent` | Candidate는 optional linkage이며 `CandidateEvent.score`를 VisualEvidence confidence로 복제하지 않음 | 추가 필드 변경 필요 없음 |
| Fine / Classification Input Contract | `input_ref`가 `VisualEvidence`의 필수 identity가 되었으므로 clip/frame sequence를 공통 참조하는 exact schema 필요 | **추가 정의 필요** |
| `EvidenceRecord` | Evidence는 `VisualEvidence`를 관찰 근거로 참조하되 primitive를 직접 정책 taxonomy로 사용하지 않음 | Consumer 구현에서 준수 |
| `PlateReadout` / readout input | `track_ref`는 optional hint이며 없는 경우에도 자체 association 가능해야 함 | Consumer 구현에서 준수 |
| `CaseView` | raw confidence를 직접 안정적 UI contract로 사용하지 않고 필요한 경우 case가 상태로 projection | CaseView 설계에서 준수 |
| Eval prediction/scoring | `NOT_OBSERVED + visual_event_type=null`을 Fine의 NONE / hard-negative 결과로 평가 가능 | Scorer 구현에서 반영 |
| Recording / frame provenance | `evidence_refs`는 Source-derived pixel을 참조해야 하며 Report Video 사후각인 frame을 근거로 사용하지 않음 | 기존 Architecture와 정합 |

특히 **Fine `input_ref`의 exact schema는 현재 `VisualEvidence` ADR에서 새로 정의하지 않는다.**

이는 본 Contract가 결정한 identity 의미를 지원하는 인접 계약의 후속 작업이다.

---

# 11. Mock / 구현 / Evaluation에 미치는 영향

## Mock Dataset

Mock에는 최소한 다음 상태가 포함되어야 한다.

### 1. 정상 `OBSERVED`

예:

```
SOLID_LINE_LANE_CHANGE
target = MATCHED
primitives 존재
temporal_facts 존재
```

### 2. Object Attribute Event

예:

```
MOTORCYCLE_HELMET_NON_USE
temporal_facts = []
```

### 3. Hard Negative

```
verification = NOT_OBSERVED
visual_event_type = null
```

target 또는 primitive가 관찰됐더라도 event 자체는 관찰되지 않은 예시가 필요하다.

### 4. Partial / Uncertain

```
verification = UNCERTAIN
```

이면서 일부 target / primitive observation은 존재하는 예시가 필요하다.

### 5. Target Association Ambiguous

```
association_status = AMBIGUOUS
track_ref = null
```

예시가 필요하다.

### 6. Candidate-independent Fine

```
candidate_id = null
input_ref != null
```

인 Eval fixture 예시가 필요하다.

### 7. Execution Failure

`VisualEvidence`가 생성되지 않고 `AnalysisRun = FAILED`인 예시가 필요하다.

### 8. Validation Failure

```
legal_status != null
```

인 객체가 Contract validation을 통과하지 못하는 테스트가 필요하다.

---

## 구현

### Producer — `search`

반드시 다음을 지켜야 한다.

- `input_ref`가 있는 Fine result만 `VisualEvidence`로 생성한다.
- Candidate 없는 입력을 정상적으로 지원한다.
- `verification`과 `visual_event_type` invariant를 지킨다.
- Fine 실행 실패 시 빈 VisualEvidence를 만들지 않는다.
- `legal_status`는 항상 null로 생성한다.
- primitive / temporal / uncertainty를 Search-owned observation으로 유지한다.
- Candidate score를 confidence로 복사하지 않는다.
- 재실행 시 기존 result를 수정하지 않는다.
- Source-derived pixel만 evidence provenance로 사용한다.

### Consumer — `evidence`

반드시 다음을 지켜야 한다.

- `visual_event_type`을 Visual Event observation으로만 해석한다.
- `legal_status`에 실제 값을 기대하지 않는다.
- `NOT_OBSERVED`와 `UNCERTAIN`을 구분한다.
- primitive taxonomy를 신고 정책의 안정적 API로 사용하지 않는다.
- raw confidence를 직접 policy threshold로 사용하지 않는다.
- `candidate_id` 존재를 전제로 하지 않는다.

### Consumer — `readout`

반드시 다음을 지켜야 한다.

- `VisualEvidence.target`은 optional hint로 취급한다.
- `track_ref = null`을 정상 상태로 처리한다.
- 필요한 경우 input/span과 사용자·시각 단서로 자체 association을 수행한다.
- Search를 직접 호출하지 않는다.

---

## Evaluation

기존 Evaluation 요구에서 다음을 직접 지원한다.

### Fine classification

- Macro Recall
- Macro Precision
- Hard-negative FPR
- target correctness / target association diagnostics

Hard-negative는:

```
verification = NOT_OBSERVED
visual_event_type = null
```

로 명확하게 표현할 수 있다.

### Failure diagnostics

다음 구분이 가능해야 한다.

```
NOT_OBSERVED
UNCERTAIN
AnalysisRun FAILED
```

이를 하나의 failure state로 합치지 않는다.

### Candidate-independent A-tier

Eval fixture가:

```
input_ref
candidate_id = null
```

형태로 동일 Fine capability를 호출할 수 있어야 한다.

---

# 12. 변경 규칙

본 ADR이 `Accepted`된 이후 `VisualEvidence` Contract의 의미 변경이 필요하면 다음 순서로 처리한다.

```
문제 발견
    ↓
Producer / Consumer 확인
    ↓
Data Contract 변경안 작성
    ↓
Architecture 영향 확인
    ↓
Contract Version 증가
    ↓
ADR Supersede 또는 변경 ADR 작성
    ↓
Mock Dataset / Contract Test 갱신
```

다음과 같은 변경은 ADR 변경 대상으로 본다.

- `candidate_id`의 optional 의미 변경
- `input_ref`의 identity 역할 변경
- `verification` enum 또는 각 상태의 의미 변경
- `visual_event_type`의 ownership 변경
- `legal_status=null` invariant 변경
- primitive가 Evidence policy의 안정적 input으로 승격되는 변경
- global confidence 도입
- `track_ref`를 필수값으로 변경
- `UNCERTAIN`과 execution failure 경계 변경
- partial result 보존 정책 변경
- VisualEvidence immutability 변경
- Producer / Consumer responsibility 변경

반대로 다음은 기존 의미를 유지하는 한 반드시 새로운 ADR을 요구하지 않는다.

- 설명 문구 수정
- 예시 JSON의 ID 변경
- 새로운 Search-owned primitive kind 추가
- 새로운 temporal fact / uncertainty diagnostic code 추가
- 내부 모델 또는 prompt 변경

단, diagnostic vocabulary 변경이 실제 Consumer business rule에 영향을 주게 된다면 Architecture 영향 여부를 다시 검토해야 한다.

---

# 13. 미해결 사항

현재 Final `VisualEvidence v1.0`을 뒤집어야 할 **미해결 Architecture Decision은 확인되지 않았다.**

다만 Final Contract가 의존하는 다음 세부사항은 후속 계약 또는 구현 명세에서 정의해야 한다.

| 항목 | 왜 미해결인가 | 담당자 | 언제 결정해야 하는가 |
| --- | --- | --- | --- |
| Fine `input_ref` exact schema | Final Contract에서는 opaque reference의 의미만 확정했고 clip/frame sequence의 실제 reference 구조는 정의하지 않음 | `[Fine Input Contract Owner 작성 필요]` | Fine public capability 구현/통합 전 |
| Primitive vocabulary registry | Final Contract는 `kind + state` 구조만 고정하고 전체 vocabulary를 고정하지 않음 | `search` / 서어진 | Search 구현 및 Eval fixture 구체화 과정 |
| Temporal fact / uncertainty vocabulary | Contract는 구조와 semantic boundary만 고정하고 전체 code 목록은 확정하지 않음 | `search` / 서어진 | 구현 및 diagnostics 정리 과정 |

이 항목들은 현재 `VisualEvidence`의 ownership, lifecycle 또는 Consumer 책임을 변경하는 Architecture Decision이 아니다.

후속 정의 과정에서 본 ADR의 의미 경계를 변경해야 하는 요구가 발견되면 별도의 Contract 변경 절차를 따른다.

---

# 14. 최종 한 줄 결정

> **우리는 `search`가 Candidate 존재 여부와 무관하게 `input_ref`를 기준으로 Visual Event의 관찰 상태·대상·근거·불확실성을 immutable `VisualEvidence`로 보장하고, `evidence`와 `readout`이 이를 각각 확정 Evidence의 입력과 optional target association hint로 소비하되 법적 판단·global confidence·Search 내부 primitive 정책에는 결합하지 않도록 `VisualEvidence v1.0` 계약을 확정한다.**
>