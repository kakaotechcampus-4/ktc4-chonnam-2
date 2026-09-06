# Final Data Contract — EvidenceRecord + EvidenceNeeds v1

**Status:** `Final — Accepted`

**Architecture Contract:** v4 §5-1 ⑨

**Contract:** `EvidenceRecord + EvidenceNeeds`

**Contract Version:** `evidence-record/v1.1` / `evidence-needs/v1`

**Accepted:** `2026-09-04` (v1) · `2026-09-06` (v1.1)

**Related ADR:** `adr/adr-evidence-record-needs.md` · `adr/adr-consistency-2026-09.md` §6 R-1

> **`evidence-record/v1.1` 변경 (2026-09-06)** — `EvidenceValue.source`에 `observability`(`OBSERVED`/`INFERRED`)와 `label_key`를 추가했다. 필드 추가뿐이고 기존 필드의 의미·값 공간은 그대로다. 근거는 §3의 해당 절.

**Contract Lead / Owner:** 김준영 (`evidence`)

**Runtime Producer:** `evidence`

**Direct Runtime Consumer:** `case` — 유소연

**Review / Projection Consumer:** `web` — 신유민 (`CaseView` 경유)

**관련 Architecture:** 대신고 모듈 구조 설계 v4

> 이 페이지가 `EvidenceRecord + EvidenceNeeds`의 **Source of Truth**다. Draft는 선택지와 Consumer Review 이력을 보존하며 구현·Mock·후속 Requirement/Package 계약은 이 Final Contract를 따른다.
> 

---

# 1. 계약 목적

`EvidenceRecord`는 `evidence`가 현재 사건에 대해 **authoritative하게 사용하는 confirmed values의 immutable snapshot**이다.

`EvidenceNeeds`는 해당 `EvidenceRecord`를 기준으로 추가 관찰/판독이 필요할 때 그 필요를 **명령이 아닌 declarative value**로 `case`에 전달한다.

핵심 경계는 다음과 같다.

```
Observation / VisualEvidence / Readout
= "이렇게 관찰됐다"

TimeResolution
= "이 시간 근거들을 비교해 이 시각을 쓴다"

EvidenceRecord
= "현재 제품 정책상 이 값을 authoritative하게 사용한다"

EvidenceNeeds
= "이 confirmed Evidence를 보강하려면 이 추가 관찰/판독이 필요하다"

RequirementReport
= "신고요건을 충족하는가"

ReportPackage / DerivedVideo
= "신고용 파생물을 어떻게 만든다"
```

`evidence`는 다른 모듈을 직접 호출하지 않는다. `EvidenceNeeds`를 반환하고, 실제 Job orchestration은 `case`가 소유한다.

---

# 2. Producer / Consumer

## Producer

- `evidence` — 김준영

## Runtime Consumer

- `case` — 유소연

## Review / Projection Consumer

- `web` — 신유민
- `web`은 `EvidenceRecord`나 `EvidenceNeeds`를 직접 읽지 않고 `CaseView` safe projection만 소비한다.

## 주요 Upstream

- `VisualEvidence`
- `PlateReadout` / `OverlayTimeReadout`
- `TimeResolution`
- `CorrectionRecord`
- `CandidateEvent` / `AssetSpan`

---

# 3. `EvidenceRecord` 최종 구조

```
EvidenceRecord {
    contract_version: string

    record_ref: ContractRef
    supersedes_ref?: ContractRef

    case_ref: ContractRef
    selection_rev: integer

    basis: {
        candidate_ref: ContractRef
        visual_evidence_ref: ContractRef
        evidence_interval_ref: ContractRef
    }

    event: {
        visual_event_type: EvidenceValue<VisualEventType>
        safety_report_type: EvidenceValue<SafetyReportType>
        violation_expression: EvidenceValue<string>
    }

    occurred_at?: {
        value: offset-aware RFC3339 datetime
        time_resolution_ref: ContractRef
        resolution_status:
            OK
            | NEEDS_REVIEW
    }

    vehicle_number?: EvidenceValue<string>

    location?: {
        coord?: EvidenceValue<Coordinate>
        address?: EvidenceValue<string>
        place_name?: EvidenceValue<string>
        search_keyword?: EvidenceValue<string>
        user_hint?: EvidenceValue<string>
    }

    provenance: {
        input_refs: ContractRef[]
        correction_refs: ContractRef[]
        policy_ref: string
    }
}

EvidenceValue<T> {
    value: T

    source: {
        kind: namespaced string
        ref: ContractRef
        observability: OBSERVED | INFERRED
        label_key: string | null
    }

    support_refs: ContractRef[]
    user_corrected: boolean
}

Coordinate {
    lat: number
    lon: number
}
```

`EvidenceValue<T>`는 이번 v1에서 독립 Data Contract로 승격하지 않고 `EvidenceRecord` 내부 nested structure로 둔다.

### `source.observability` · `source.label_key` (v1.1, 2026-09-06)

`CaseView`가 `core-user-flow.md` §3-1의 정보 상태 5종을 내려보내려면 「이 값이 관찰된 것인가 추론된 것인가」를 알아야 한다(`contract-job-record-case-view.md` B절 §7 파생 규칙).

`source.kind`는 `recording.filename_time` · `readout.overlay_ocr` · `search.visual_inference` 같은 **열린 namespaced 문자열**이라 소비자가 문자열을 보고 관찰/추론을 분류해야 했다. 그건 `case`가 정책 판단을 하는 것이고 v4 §3 정책 이관표와 「case는 authoritative 판단을 재계산하지 않는다」에 걸린다. 그래서 **분류를 값에 실어 `evidence`가 준다.**

| 값 | 뜻 |
| --- | --- |
| `OBSERVED` | 영상 화면·파일 메타데이터·GPS 등 **확인 가능한 출처에서 직접 얻은** 값 |
| `INFERRED` | 관찰값·단서로부터 **추론한** 값 |

- 새 `source.kind`를 추가할 때 `observability`를 함께 정한다. 분류 없는 kind는 만들지 않는다.
- 사용자 입력에는 별도 값을 두지 않는다 — `user_corrected=true`가 이미 그 사실을 갖고 있고, 파생 규칙에서 `observability`보다 먼저 판정된다.
- `label_key`는 `kind`에 대응하는 화면 라벨 키다(예: `plate.source.overlay_ocr`). **키 네임스페이스는 `evidence`가 소유**하며 `CaseView.source_label_key`로 그대로 통과한다. 대응 키가 없으면 `null`이고 소비자가 fallback 문구를 쓴다.
- 이 두 필드는 표시를 위한 것이고 **authoritative 값 판정에는 쓰지 않는다.** `confidence`를 노출하는 것이 아니다.

**보정 근거:** `evidence`는 김준영(PM) 소유이고 값 의미를 바꾸지 않는 필드 추가다(`adr/adr-consistency-2026-09.md` §3 트랙 1 조건 3). 소비자 `case`에는 통보한다 — `adr/adr-consistency-2026-09.md` §6 R-1.

---

# 4. `EvidenceRecord` 핵심 의미

## 4.1 Immutable snapshot

- 생성된 `EvidenceRecord`는 의미적으로 mutate하지 않는다.
- correction/reassemble 시 새 `record_ref`를 가진 Record를 만든다.
- 이전 결과를 대체하면 `supersedes_ref`로 연결한다.
- `case`는 새 결과를 받으면 current pointer를 갱신하고, 과거 Record는 audit/history 용도로 보존할 수 있다.

## 4.2 confirmed value만 보존

- Record에 존재하는 값은 `evidence`가 현재 authoritative하게 사용하는 값이다.
- 확정하지 못한 값은 `UNKNOWN` 문자열이나 placeholder를 만들지 않고 **필드 부재/null**로 표현한다.
- upstream `Observation.status=UNKNOWN/ERROR`를 EvidenceRecord에 별도 status로 복제하지 않는다.
- 값이 없는 이유와 추가 작업은 `EvidenceNeeds` / downstream notice에서 표현한다.

## 4.3 Event mapping 분리

다음 세 값은 다른 개념으로 유지한다.

```
visual_event_type
≠ safety_report_type
≠ violation_expression
```

`violation_expression`은 제품의 신고 준비용 표현이며 AI가 법적 최종 판정을 내렸다는 뜻이 아니다.

## 4.4 TimeResolution 연결

`occurred_at`은 TimeResolution 전체를 embed하지 않고 최소 snapshot + reference로 연결한다.

```
occurred_at.value
occurred_at.time_resolution_ref
occurred_at.resolution_status
```

- `TimeResolution.status=UNKNOWN`이면 `occurred_at` 자체가 없어야 한다.
- conflict/considered/timezone provenance 상세는 `TimeResolution`이 authoritative source다.
- `case`는 Timestamp source priority를 재계산하지 않는다.

## 4.5 VisualEvidence 연결

- `VisualEvidence` 상세 primitive/diagnostics를 Record에 복제하지 않는다.
- `basis.visual_evidence_ref`로 실제 사용한 VisualEvidence를 연결한다.
- `EvidenceRecord`는 그 관찰을 바탕으로 채택한 confirmed value만 snapshot한다.

## 4.6 번호판과 신고영상 가시성 분리

```
vehicle_number confirmed
≠ plate_visible_in_evidence
```

번호판 문자열 확정은 EvidenceRecord 책임이고, 신고영상에서 실제 식별 가능한지는 `RequirementReport` 책임이다.

## 4.7 사건시각과 영상 내 표시 분리

```
occurred_at confirmed
≠ evidence_time_visible
```

사건시각 확정은 EvidenceRecord/TimeResolution 책임이고, 신고영상에서 시각이 실제 표시되는지는 `RequirementReport`/Package 흐름에서 판단한다.

---

# 5. 위치 규칙

`location`은 하나의 거대한 위치 상태가 아니라 확보된 confirmed value를 개별 provenance와 함께 보존한다.

- `coord`: 실제 GPS/명시적 근거가 있을 때만 존재
- `address`: 근거가 있는 주소
- `place_name`: 장소명
- `search_keyword`: 위치 검색용 보조 문자열
- `user_hint`: 사용자가 입력한 위치 단서

규칙:

- GPS가 없다고 임의 좌표를 생성하지 않는다.
- `user_hint`를 객관적 GPS/주소와 동일시하지 않는다.
- 사용자 correction이 적용되면 `user_corrected=true`와 correction provenance를 남긴다.
- v1에서 위치 전용 신규 Contract를 만들지 않는다.

---

# 6. Readiness / Workflow 경계

`EvidenceRecord`에는 다음을 넣지 않는다.

```
EVIDENCE_SUFFICIENT
READY
PACKAGE_READY
USER_REVIEWED
Requirement PASS/WARN/BLOCK
```

책임은 다음처럼 분리한다.

- Evidence 값: `EvidenceRecord`
- 추가 관찰/판독 Need: `EvidenceNeeds`
- 신고요건: `RequirementReport`
- 신고용 꾸러미/파생물: `ReportPackage`
- 사용자 workflow/UI: `CaseView`

따라서 `EvidenceNeeds.items=[]`이어도 신고 가능을 의미하지 않는다.

---

# 7. `EvidenceNeeds` 최종 구조

```
EvidenceNeeds {
    contract_version: string

    basis_record_ref: ContractRef

    items: EvidenceNeed[]
}

EvidenceNeed {
    kind:
        OVERLAY_TIME_OCR
        | PLATE_REREAD

    would_fill:
        OCCURRED_AT
        | VEHICLE_NUMBER

    why: {
        code: namespaced string
        summary?: string
    }

    optional: boolean

    context_refs: [
        {
            role: namespaced string
            ref: ContractRef
        }
    ]
}
```

---

# 8. `EvidenceNeeds` 의미

## 8.1 Container + basis Record

`basis_record_ref`는 이 Need가 어느 Evidence snapshot을 기준으로 계산됐는지 나타낸다.

- EvidenceRecord와 EvidenceNeeds는 한 `assemble()` 결과에서 함께 반환할 수 있다.
- 함께 받은 직후에는 별도의 stale 탐색이 필수는 아니다.
- 다만 delayed dispatch/retry 시 `basis_record_ref`가 더 이상 current Record가 아니면 Need를 다시 적용하기 전에 stale 여부를 확인한다.

## 8.2 v1 NeedKind는 2개로 닫는다

허용값:

```
OVERLAY_TIME_OCR
PLATE_REREAD
```

매핑:

- `OVERLAY_TIME_OCR` → `would_fill=OCCURRED_AT`
- `PLATE_REREAD` → `would_fill=VEHICLE_NUMBER`
- `PlateReadout.abstained=true`이고 차량번호가 아직 confirmed되지 않았다면 `PLATE_REREAD` Need로 연결할 수 있다. 이는 기존 Consumer Review에서 합의한 "abstain은 전체 실패가 아니라 번호판 보강이 필요한 상태"라는 의미를 보존한다.
- 사용자 최종 확인·수정 자체는 새로운 `EvidenceNeeds` kind가 아니다. 사용자 action은 `CaseView`/`CorrectionRecord` 흐름에서 처리한다.

새 Need를 추가하려면 EvidenceNeeds Contract version/review를 갱신한다.

## 8.3 `context_refs[]`는 semantic reference만 전달

EvidenceNeeds는 실제 readout command DTO가 아니다.

허용 예:

```
evidence.interval → AssetSpan / Source-derived incident interval ref
evidence.target_hint → VisualEvidence 등 stable target hint ref
```

규칙:

- `PLATE_REREAD`은 사건 interval ref를 제공해야 하며 target hint는 available한 경우 추가할 수 있다.
- `OVERLAY_TIME_OCR`은 source-derived 사건 interval/clip을 구성할 수 있는 ref를 제공한다.
- `context_refs`에 raw path, prompt, OCR threshold, retry, timeout, queue priority를 넣지 않는다.
- case의 `needs_map`이 semantic refs를 현재 readout public input으로 조립한다.

## 8.4 `why`

```
why.code
= stable machine-readable reason

why.summary
= optional human diagnostic summary
```

프로그램 분기는 `why.code`를 사용하고 자연어 parsing을 하지 않는다.

## 8.5 `optional`

`optional`은 **Evidence 보강 작업의 필요성**만 의미한다.

```
optional=false
= 현재 Evidence policy상 가능한 경우 기본적으로 수행해야 하는 보강 작업

optional=true
= Evidence quality/enrichment에 도움이 되지만 생략 가능
```

다음과 같지 않다.

```
optional=false ≠ RequirementReport.BLOCK
```

### 자동 JobIntent 발주 규칙

`optional=false`인 Need가 현재 case/selection revision에서 여전히 유효하면 `case`는 별도 사용자 승인 없이 해당 작업의 `JobIntent`를 자동 발주할 수 있다.

단:

- `EvidenceNeeds` 자체는 명령이 아니다.
- stale Need는 자동 발주하지 않는다.
- 실제 retry/cache/queue 정책은 `JobRecord` / `JobExecution` 책임이다.
- 신고 blocker 여부는 `RequirementReport`만 판단한다.

---

# 9. Post-stamp / Report Video 경계

`EvidenceNeeds` v1은 **confirmed Evidence를 보강하기 위한 추가 관찰/판독 작업**에만 사용한다.

따라서 아래 kind는 v1에 넣지 않는다.

```
POST_STAMP
REPORT_VIDEO
EXPORT
```

`TimeResolution.post_stamp.needed`는 사후 Timestamp 각인이 필요한지와 provenance를 표현하는 정책 결과다.

실제 흐름은:

```
TimeResolution.post_stamp
        ↓
case / package orchestration
        ↓
ReportPackage / DerivedVideo export Job
        ↓
신고용 파생영상 생성
```

즉 post-stamp는 **Evidence를 더 관찰하는 작업이 아니라 이미 확정된 정보를 신고용 파생물에 표현하는 작업**이므로 `EvidenceNeeds`에 포함하지 않는다.

---

# 10. Invariants

## EvidenceRecord

1. 모든 Record는 `record_ref`를 가진다.
2. 동일 Record를 correction/reassemble 결과로 mutate하지 않는다.
3. `supersedes_ref`가 있으면 현재 `record_ref`와 달라야 한다.
4. Record는 하나의 `case_ref`와 `selection_rev`에 결합된다.
5. 존재하는 Evidence value는 evidence의 authoritative confirmed value다.
6. 확정하지 못한 값을 placeholder/sentinel로 채우지 않는다.
7. `occurred_at`이 존재하면 `time_resolution_ref`가 존재한다.
8. `resolution_status=UNKNOWN`인 `occurred_at`을 만들지 않는다.
9. `vehicle_number` 존재와 신고영상 내 번호판 가시성을 동일시하지 않는다.
10. GPS가 없으면 임의 좌표를 만들지 않는다.
11. `PACKAGE_READY`, `USER_REVIEWED`, Requirement severity를 Record에 넣지 않는다.

## EvidenceNeeds

1. 모든 EvidenceNeeds는 `basis_record_ref`를 가진다.
2. `(kind, would_fill)` 조합은 같은 `items[]` 안에서 중복되지 않는다.
3. v1 kind는 `OVERLAY_TIME_OCR | PLATE_REREAD`만 허용한다.
4. `OVERLAY_TIME_OCR → OCCURRED_AT`, `PLATE_REREAD → VEHICLE_NUMBER` 매핑을 지킨다.
5. `why.code`는 stable machine-readable code다.
6. `optional=false`는 Requirement BLOCK을 뜻하지 않는다.
7. 실제 함수명/queue/retry/timeout을 EvidenceNeeds에 넣지 않는다.
8. `items=[]`은 신고 가능/요건 충족을 뜻하지 않는다.
9. superseded basis Record의 Need는 delayed dispatch 전에 stale 여부를 확인한다.
10. `POST_STAMP`/`REPORT_VIDEO`를 EvidenceNeeds kind로 사용하지 않는다.

---

# 11. 예시

## 번호판 재판독 필요

```json
{
  "contract_version": "evidence-needs/v1",
  "basis_record_ref": {"kind":"evidence_record","ref":"ev_89"},
  "items": [
    {
      "kind": "PLATE_REREAD",
      "would_fill": "VEHICLE_NUMBER",
      "why": {
        "code": "evidence.vehicle_number.unconfirmed",
        "summary": "대상 차량 번호판을 확정하지 못했습니다."
      },
      "optional": false,
      "context_refs": [
        {
          "role": "evidence.interval",
          "ref": {"kind":"asset_span","ref":"span_204"}
        },
        {
          "role": "evidence.target_hint",
          "ref": {"kind":"visual_evidence","ref":"ve_204"}
        }
      ]
    }
  ]
}
```

`case`는 이 Need가 current revision 기준으로 유효하면 백그라운드 `PLATE_READ` 계열 JobIntent를 자동 발주할 수 있다.

---

# 12. 다른 Contract와의 경계

- `Observation<T>`: 관찰값과 관찰 상태. confirmed value가 아님.
- `VisualEvidence`: 영상 관찰 근거. EvidenceRecord에는 ref만 연결.
- `PlateReadout / OverlayTimeReadout`: readout 관찰 결과. evidence가 confirmed value로 승격할지 결정.
- `TimeResolution`: occurred_at의 authoritative resolution. EvidenceRecord는 최소 snapshot + ref만 보존.
- `CorrectionRecord`: 사용자 수정 provenance.
- `JobRecord / JobExecution`: Need 이후 실제 발주·실행 lifecycle.
- `RequirementReport`: 신고요건 PASS/WARN/BLOCK 및 가시성 판단.
- `ReportPackage / DerivedVideo`: post-stamp/export 등 신고용 파생물 생성.
- `CaseView`: web을 위한 safe projection.

---

# 13. 후속 변경 규칙

의미 변경이 필요한 경우:

```
문제 발견
→ Producer / Consumer 확인
→ Contract 변경안
→ Architecture 영향 확인
→ Contract Version 증가
→ ADR Supersede/변경 ADR
→ Mock 갱신
```

다음은 의미 변경으로 본다.

- confirmed value ownership 변경
- immutable lifecycle 변경
- Need kind 추가/삭제
- `optional` 의미 변경
- Requirement/Package 책임을 EvidenceRecord/Needs로 이동
- 새로운 command payload를 EvidenceNeeds에 포함

---

# 14. 현재 미해결 사항

현재 Final Contract 기준 **미해결 Architecture Decision 없음**.

구체적인 Evidence policy rule table, SafetyReportType registry, readout adapter 함수 인자, DB schema, retry/queue 세부는 Tech Spec/구현 범위이며 이 Contract 의미를 변경하지 않는다.