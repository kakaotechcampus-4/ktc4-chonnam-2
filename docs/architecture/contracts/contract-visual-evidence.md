# Final Data Contract — VisualEvidence v1.0

**Status:** `Final — Accepted`

**Accepted:** `2026-09-04` (짝 ADR의 결정일 9/4)

**Related ADR:** `adr/adr-visual-evidence.md`

**Architecture Contract:** v4 §5-1 ⑥

**Contract:** `VisualEvidence`

**Contract Version:** `visual-evidence/v1.0`

**Producer / Owner:** 서어진 (`search`)

**Consumers:** `case` — 유소연 (Direct) → `evidence` — 김준영 · `readout` — 신유민 (projection)

**기준 Architecture:** `Module Architecture v4`

**결정 근거:** [ADR: `VisualEvidence` Data Contract 확정](https://app.notion.com/p/ADR-VisualEvidence-Data-Contract-3d17ae78fc6a80b0a111c4ba6b7c45a6?pvs=21)

**검토 이력:** [`VisualEvidence`](https://app.notion.com/p/VisualEvidence-3cf7ae78fc6a80459f85e6fe3985a9ea?pvs=21)

<aside>
✅

이 페이지가 `VisualEvidence`의 **schema / serialization Source of Truth**다. Draft는 대안과 Consumer Review 이력을, ADR은 결정 이유를 보존한다. 구현·Mock·Eval serialization은 이 Final Contract를 따른다.

</aside>

---

# 1. 계약 목적과 책임 경계

`VisualEvidence`는 `search`의 Fine / Classification 분석 결과로 얻은 **시각적 관찰**을 `evidence`와 `readout`에 전달하는 immutable result다.

이 계약이 표현하는 것:

- 어떤 Fine / Classification `AnalysisRun`에서 생성됐는지
- 어떤 실제 분석 입력을 보았는지
- 지원 Visual Event가 관찰되었는지
- 관찰된 대상 association
- 판단에 사용한 visual primitive
- temporal fact 또는 object attribute 관찰
- 불확실성과 영상 근거

이 계약이 **표현하지 않는 것**:

- 법적 위반 확정
- 안전신문고 신고 유형 / Report Type
- violation expression
- Evidence sufficiency
- 신고 가능 여부 / package readiness
- 확정 번호판
- 확정 사건 발생시각
- 확정 위치
- 사용자의 최종 Candidate 선택 여부

> `VisualEvidence`는 **“영상에서 이렇게 관찰되었다”**를 표현한다. **“법적 위반이 확정되었다”**를 표현하지 않는다.
> 

---

# 2. 최종 Serialization

```json
{
  "schema_version": "visual-evidence/v1.0",
  "visual_evidence_id": "ve_lane_001",
  "run_id": "run_fine_101",
  "input_ref": "analysis-input:incident-17",
  "candidate_id": "c17",

  "verification": "OBSERVED",
  "visual_event_type": "SOLID_LINE_LANE_CHANGE",

  "target": {
    "association_status": "MATCHED",
    "described_as": "흰색 SUV",
    "match_with_hint": true,
    "association_confidence": 0.79,
    "track_ref": null,
    "evidence_refs": [
      "frame:incident-17@6400"
    ]
  },

  "primitives": [
    {
      "kind": "WHITE_SOLID_LINE",
      "state": "PRESENT",
      "confidence": 0.88,
      "evidence_refs": [
        "frame:incident-17@6400"
      ]
    }
  ],

  "temporal_facts": [
    {
      "at_offset_ms": 6400,
      "fact": "TARGET_CROSSES_LINE",
      "evidence_refs": [
        "frame:incident-17@6400"
      ]
    }
  ],

  "uncertainties": [],
  "legal_status": null
}
```

---

# 3. Top-level 필드 정의

| 필드 | 타입 | 필수 | 의미 / 규칙 |
| --- | --- | --- | --- |
| `schema_version` | string | 필수 | v1.0에서는 항상 `visual-evidence/v1.0`. |
| `visual_evidence_id` | ID | 필수 | 하나의 immutable VisualEvidence result를 식별한다. 사건 확정 ID가 아니다. |
| `run_id` | ref | 필수 | 결과를 생성한 Fine / Classification `AnalysisRun`. 비용·모델·실행 실패 정보는 Run을 참조한다. |
| `input_ref` | ref | 필수 | 실제 Fine 분석 입력의 opaque reference. Source 파일 경계를 Consumer가 직접 해석하지 않는다. |
| `candidate_id` | ID/null | 선택 | 제품 Candidate 기반 호출이면 연결한다. Candidate-independent Fine에서는 null이 정상이다. |
| `verification` | enum | 필수 | `OBSERVED | NOT_OBSERVED | UNCERTAIN`. 실행 성공/실패 상태가 아니라 Visual Event 관찰 상태다. |
| `visual_event_type` | enum/null | 조건부 | `OBSERVED`일 때만 지원 Visual Event 값을 가진다. Report Type이 아니다. |
| `target` | Target/null | 조건부 | 대상 association 관찰. `track_ref` 존재를 보장하지 않는다. |
| `primitives` | Primitive[] | 필수 | 시각 primitive 관찰 근거. 배열 자체는 항상 존재하며 빈 배열 가능. |
| `temporal_facts` | TemporalFact[] | 필수 | 시간 순서/상태 변화 관찰. object attribute 사건에서는 빈 배열 가능. |
| `uncertainties` | Uncertainty[] | 필수 | 정상 실행에서 남은 판단 불확실성/제약. 배열 자체는 항상 존재하며 빈 배열 가능. |
| `legal_status` | null only | 필수 | 반드시 존재하고 반드시 `null`. non-null은 Contract validation failure. |

---

# 4. Verification / Visual Event

## 4-1. `verification`

| 값 | 의미 | `visual_event_type` |
| --- | --- | --- |
| `OBSERVED` | 지원 Visual Event가 영상 근거로 관찰됨 | 필수, non-null |
| `NOT_OBSERVED` | Fine은 정상 실행됐으나 해당 사건을 지지하는 근거가 없음 | 반드시 null |
| `UNCERTAIN` | Fine은 정상 실행됐으나 관찰 근거가 불충분하거나 모호함 | 반드시 null |
- `NOT_OBSERVED`는 hard-negative / candidate rejection을 표현할 수 있는 **유효한 결과**다.
- `UNCERTAIN`은 시스템 실행 실패가 아니다.
- API timeout, 모델 오류, 파일 처리 실패 등의 실행 실패는 `AnalysisRun` / runtime lifecycle에서 표현한다.
- `NEEDS_REVIEW`, `PARTIAL`, `COMPLETE` 같은 별도 상태 enum을 v1.0에 추가하지 않는다.

## 4-2. `VisualEventType`

v1.0 지원 범위:

- `SIGNAL`
- `CENTER_LINE_CROSSING`
- `SOLID_LINE_LANE_CHANGE`
- `MOTORCYCLE_HELMET_NON_USE`

`visual_event_type`은 **Visual Event 관찰 종류**이며 법적 신고 유형이나 violation expression으로 직접 변환해서는 안 된다.

---

# 5. `Target`

```json
{
  "association_status": "MATCHED",
  "described_as": "흰색 SUV",
  "match_with_hint": true,
  "association_confidence": 0.79,
  "track_ref": null,
  "evidence_refs": ["frame:incident-17@6400"]
}
```

| 필드 | 타입 | 필수 | 규칙 |
| --- | --- | --- | --- |
| `association_status` | enum | 필수 | `MATCHED | AMBIGUOUS | NOT_FOUND`. 법적 행위 주체 확정을 의미하지 않는다. |
| `described_as` | string/null | 선택 | 영상에서 관찰 가능한 대상 설명. 사용자 hint 원문과 동일하다고 가정하지 않는다. |
| `match_with_hint` | bool/null | 선택 | 제공된 target hint와의 시각적 일치 여부. hint가 없으면 null 가능. |
| `association_confidence` | number/null | 선택 | 정의 가능한 경우에만 `[0.0, 1.0]`. Consumer business threshold로 직접 사용하지 않는다. |
| `track_ref` | ref/null | 선택 | tracking reference. `MATCHED`여도 null일 수 있다. |
| `evidence_refs` | ref[] | 필수 | 대상 association 근거. 0개 이상. |

**중요 규칙**

- `track_ref == null`은 정상 상태다.
- `association_status == MATCHED`여도 `track_ref == null`일 수 있다.
- `readout`은 `track_ref` 존재를 실행의 전제조건으로 삼지 않는다.
- `readout`은 `input_ref`와 target hint를 이용해 자체 association할 수 있어야 한다.

---

# 6. `Primitive`

```json
{
  "kind": "WHITE_SOLID_LINE",
  "state": "PRESENT",
  "confidence": 0.88,
  "evidence_refs": ["frame:incident-17@6400"]
}
```

| 필드 | 타입 | 필수 | 규칙 |
| --- | --- | --- | --- |
| `kind` | string/code | 필수 | Search가 관리하는 primitive 식별자. |
| `state` | enum | 필수 | `PRESENT | ABSENT | UNCERTAIN`. |
| `confidence` | number/null | 선택 | 정의 가능한 경우 `[0.0, 1.0]`. |
| `evidence_refs` | ref[] | 필수 | 해당 primitive 관찰의 영상 근거. |

v1.0은 `WHITE_SOLID_LINE`, `HELMET_ON_RIDER` 같은 primitive 사용을 허용하지만 **primitive 전체 registry를 Data Contract의 안정적 정책 API로 고정하지 않는다.**

`evidence`는 `primitives[].kind`에 직접 신고 정책을 결합하지 않는다. 안정적인 정책 입력은 `visual_event_type` 중심이며 primitives는 provenance / 설명 / debugging / evaluation diagnostics 용도다.

---

# 7. `TemporalFact`

```json
{
  "at_offset_ms": 6400,
  "fact": "TARGET_CROSSES_LINE",
  "evidence_refs": ["frame:incident-17@6400"]
}
```

| 필드 | 타입 | 필수 | 규칙 |
| --- | --- | --- | --- |
| `at_offset_ms` | integer/null | 선택 | Fine input 시작점 기준 상대 시간. |
| `fact` | string/code | 필수 | 관찰한 시간적 사실. |
| `evidence_refs` | ref[] | 필수 | 해당 temporal fact의 영상 근거. |
- `temporal_facts`는 항상 배열이다.
- `MOTORCYCLE_HELMET_NON_USE`처럼 object attribute 성격이 강한 사건에서는 `temporal_facts=[]`이 정상이다.
- `at_offset_ms`는 최종 신고 `occurred_at`이 아니다.

---

# 8. `Uncertainty`

```json
{
  "kind": "OCCLUSION",
  "detail": "대상 일부가 앞 차량에 가려짐",
  "evidence_refs": ["frame:incident-17@6400"]
}
```

| 필드 | 타입 | 필수 | 규칙 |
| --- | --- | --- | --- |
| `kind` | string/code | 필수 | 불확실성 유형. vocabulary는 Search가 관리한다. |
| `detail` | string/null | 선택 | 사람이 이해할 수 있는 짧은 진단 설명. |
| `evidence_refs` | ref[] | 선택 | 불확실성을 보여주는 영상 근거. |

`detail`은 진단/검토용이며 Consumer business rule의 안정적 key로 사용하지 않는다.

---

# 9. Confidence 정책

v1.0에는 **top-level global confidence가 존재하지 않는다.**

금지:

```
VisualEvidence.confidence
```

허용되는 것은 의미가 명확한 component confidence뿐이다.

- `target.association_confidence`
- `primitives[].confidence`

규칙:

- 값이 존재하면 `[0.0, 1.0]` 범위다.
- 값이 없다고 `0.0`으로 대체하지 않는다.
- Candidate ranking score를 VisualEvidence confidence로 복사하지 않는다.
- `evidence`, `case`, `readout`은 raw confidence에 임의의 정책 threshold를 만들지 않는다.
- 사용자 표시가 필요하면 `case`가 `CaseView`용 상태로 projection한다.

---

# 10. Partial Observation / Failure 경계

Fine 실행이 정상 완료됐지만 일부 관찰이 불충분한 경우에도 확보된 정보는 버리지 않는다.

```
VisualEvidence 존재
verification = UNCERTAIN
확보된 target / primitives / temporal_facts 유지 가능
uncertainties[]에 부족한 근거 기록
```

별도의 `PARTIAL / COMPLETE` enum은 두지 않는다. `verification`과 각 component의 존재/상태만으로 표현한다.

반대로 실행 자체 실패는 VisualEvidence의 `UNCERTAIN`으로 표현하지 않는다.

```
정상 Fine 실행 후 판단 불충분 → VisualEvidence.verification = UNCERTAIN
API timeout / model error / file failure → AnalysisRun / runtime failure
```

---

# 11. Invariants

## Identity / Lifecycle

1. `visual_evidence_id`는 하나의 result를 고유하게 식별한다.
2. `run_id`는 반드시 존재한다.
3. `input_ref`는 반드시 존재한다.
4. `candidate_id`는 없어도 정상이다.
5. 재실행 시 기존 VisualEvidence를 수정하지 않는다.
6. 재실행은 새로운 `AnalysisRun`과 새로운 VisualEvidence result를 생성한다.

## Verification

1. `verification ∈ {OBSERVED, NOT_OBSERVED, UNCERTAIN}`.
2. `OBSERVED`이면 `visual_event_type != null`.
3. `NOT_OBSERVED`이면 `visual_event_type == null`.
4. `UNCERTAIN`이면 `visual_event_type == null`.
5. 실행 자체 실패를 `UNCERTAIN`으로 표현하지 않는다.

## Ownership / Legal Boundary

1. `legal_status`는 반드시 존재한다.
2. `legal_status`는 반드시 `null`이다.
3. non-null `legal_status`는 validation failure다.
4. `report_type`, `violation_expression`, `requirement_status`, `evidence_sufficient`, `package_ready`를 VisualEvidence에 추가하지 않는다.
5. VisualEvidence는 최종 번호판 / 발생시각 / 위치를 소유하지 않는다.

## Target

1. `track_ref == null`은 정상이다.
2. `association_status == MATCHED`여도 `track_ref == null`일 수 있다.
3. Consumer는 `track_ref` 존재를 readout 실행의 전제조건으로 삼지 않는다.

## Collections

1. `primitives`, `temporal_facts`, `uncertainties`는 null이 아니라 배열이다.
2. 각 배열은 비어 있을 수 있다.
3. `MOTORCYCLE_HELMET_NON_USE`에서 `temporal_facts=[]`은 유효하다.

## Confidence

1. component confidence가 존재하면 `[0.0, 1.0]` 범위다.
2. confidence 부재를 `0.0`으로 변환하지 않는다.
3. top-level global confidence를 추가하지 않는다.
4. Consumer business logic은 raw component confidence threshold에 직접 결합하지 않는다.

---

# 12. Producer / Consumer 구현 규칙

## Producer — `search`

반드시:

- 모든 정상 Fine 결과에 `VisualEvidence`를 생성한다.
- `NOT_OBSERVED`와 `UNCERTAIN`을 구분한다.
- Candidate 없이도 동일 public Fine capability를 사용할 수 있게 한다.
- `input_ref`를 실제 Fine 입력 provenance로 보존한다.
- `candidate_id`를 optional linkage로만 취급한다.
- 가능한 관찰 근거를 `evidence_refs`로 남긴다.
- 법적/신고 의미를 생성하지 않는다.
- 실행 실패를 VisualEvidence 상태로 위장하지 않는다.

## Consumer — `evidence`

반드시:

- `visual_event_type`을 Visual Event 관찰값으로만 해석한다.
- `NOT_OBSERVED`와 `UNCERTAIN`을 별도 입력 상태로 처리한다.
- `primitives[].kind`나 raw confidence에 신고 정책을 직접 결합하지 않는다.
- 법적 판단 / Evidence sufficiency는 Evidence 영역에서 별도로 수행한다.
- 필요하면 최종 Evidence가 근거로 사용한 `VisualEvidence`를 reference한다.

## Consumer — `readout`

반드시:

- `target`을 optional association hint로 사용한다.
- `track_ref`가 없어도 동작한다.
- 실제 판독 대상 association은 `input_ref`와 시각/사용자 단서를 바탕으로 자체 수행할 수 있어야 한다.
- `association_confidence`를 보조 정보 이상으로 확대 해석하지 않는다.

---

# 13. Contract 접합부

```
AnalysisRun.run_id
        ↑
VisualEvidence.run_id

Fine Input
        ↑
VisualEvidence.input_ref

CandidateEvent.candidate_id
        ↑ optional
VisualEvidence.candidate_id

VisualEvidence
   ├─→ evidence
   └─→ readout
```

- `run_id`의 실행 lifecycle / 비용 / 모델 정보는 `AnalysisRun` 계약을 따른다.
- `input_ref`의 실제 reference schema는 Fine Input 계약 또는 해당 capability 접합 규칙을 따른다.
- `candidate_id`는 제품 runtime linkage이며 Fine identity 자체가 아니다.
- final `occurred_at`, 번호판, 위치, 신고요건은 downstream 계약에서 결정한다.

---

# 14. 변경 정책

다음 변경은 `visual-evidence/v1.0`의 호환 변경으로 임의 적용하지 않는다.

- `verification` enum 의미 변경
- `VisualEventType` 의미 변경
- `legal_status`의 non-null 허용
- `candidate_id`를 필수로 변경
- `track_ref`를 필수로 변경
- top-level global confidence 추가 및 Consumer policy 의존 허용
- primitive taxonomy를 Evidence policy의 stable API로 승격
- 실행 실패를 `UNCERTAIN`으로 합치는 변경

변경이 필요하면:

```
Consumer 영향 확인
↓
Data Contract 변경안 작성
↓
Architecture 영향 확인
↓
Contract Version 증가
↓
ADR Supersede 또는 변경 ADR 작성
↓
Mock / Contract Test 갱신
```

---

# 15. 한 문장 정의

> **`VisualEvidence v1.0`은 `search`의 Fine / Classification 실행에서 얻은 Visual Event·대상 association·primitive·temporal fact·불확실성을 Candidate와 독립적으로 보존하는 immutable 관찰 계약이며, 법적·신고 판단은 소유하지 않는다.**
>
