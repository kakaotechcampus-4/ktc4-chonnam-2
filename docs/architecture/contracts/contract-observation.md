# Final Data Contract — Observation<T> v1

**Status:** `Final — Accepted`

**Architecture Contract:** v4 §5-1 ①

**Contract:** `Observation<T>`

**Contract Version:** `observation/v1`

**Accepted:** `2026-09-04`

**Related ADR:** `adr/adr-observation.md` (노션 표기 `ADR-01`)

**Contract Lead / Owner:** 김준영 (`evidence` / common / PM)

**Runtime Producer:** `recording` / `search` / `readout`

**Direct Runtime Consumer:** `evidence`, `case` projection

**Review Consumer:** 전체 Owner

**관련 Architecture:** 대신고 모듈 구조 설계 v4

> 이 페이지가 `Observation<T>`의 **Source of Truth**다. Draft는 선택지와 Consumer Review 이력을 보존하고, 구현·Mock·후속 계약은 이 Final Contract를 따른다.
> 

---

# 1. 계약 목적

`Observation<T>`는 `recording`, `search`, `readout`이 만든 **관찰된 사실 또는 관찰 시도 결과**를 공통 의미로 전달하는 cross-module envelope다.

이 계약은 다음 경계를 고정한다.

> **Producer가 “이렇게 관찰됐다”고 말하는 것과 `evidence`가 “이 값을 확정값으로 사용한다”고 말하는 것을 분리한다.**
> 

`Observation<T>` 자체는 최종 Evidence, 법적 판단, 신고 가능 여부, 최종 Timestamp, 최종 번호판 문자열을 확정하지 않는다.

---

# 2. Producer / Consumer

## Runtime Producer

- `recording`
    - 파일·stream에서 얻은 사실
    - 파일명·metadata 기반 시각 후보
    - GPS 등 Source 기반 관찰
- `search`
    - 영상 범위에서 관찰한 사건·primitive·visual inference 결과
- `readout`
    - 번호판 OCR 결과
    - 영상 Overlay Timestamp 판독 결과

## Direct Runtime Consumer

- `evidence`
- `case`가 필요한 projection

## 간접 Consumer

- `eval`: Producer public output의 채점·재현 추적
- `web`: `Observation<T>`를 직접 읽지 않고 `CaseView`만 소비

---

# 3. 최종 Contract 구조

```
Observation<T> {
    contract_version: string

    value: T | null

    status:
        OK
        | NEEDS_REVIEW
        | UNKNOWN
        | ERROR
        | NOT_APPLICABLE

    source: {
        kind: namespaced string
        ref?: ContractRef
    }

    support_refs: ContractRef[]

    produced_by: {
        module:
            recording
            | search
            | readout

        run_ref?: ContractRef
        impl_ref?: string
    }

    confidence?: {
        score: float [0.0, 1.0]
        metric: namespaced string
    }

    reason?: {
        code: namespaced string
        note?: string
    }
}

ContractRef {
    kind: string
    ref: string
}
```

`ContractRef`는 이번 계약에서 독립 Data Contract로 승격하지 않는다. 현재는 Observation 내부에서 사용하는 opaque reference 구조로 둔다.

---

# 4. 필드 의미

| 필드 | 필수 | 의미 | 핵심 규칙 |
| --- | --- | --- | --- |
| `contract_version` | 필수 | 직렬화된 Observation 계약 버전 | v1은 `observation/v1` |
| `value` | 필수 키 | 실제 관찰값 | 상태 invariant를 따른다 |
| `status` | 필수 | 관찰 결과의 사용 가능 상태 | 확정 Evidence 상태가 아님 |
| `source.kind` | 필수 | 어떤 방식/원천을 보고 관찰했는가 | namespaced 의미값. provider/model/internal stage 금지 |
| `source.ref` | 선택 | 주된 Source reference | 존재 시 유효한 `ContractRef` |
| `support_refs` | 필수 | 관찰을 뒷받침하는 구체 근거 refs | raw payload를 포함하지 않음. 빈 배열 가능 |
| `produced_by.module` | 필수 | Observation을 생성한 모듈 | `recording/search/readout` 중 하나 |
| `produced_by.run_ref` | 선택 | Producer 소유 logical run reference | Job ID / JobExecution reference가 아님 |
| `produced_by.impl_ref` | 선택 | 사용 구현의 opaque 식별자 | 상세 구현 metadata를 중복 복제하지 않음 |
| `confidence` | 선택 | Producer가 정의 가능한 보조 불확실성 정보 | `score`만 단독 사용 금지, `metric` 필수 |
| `reason.code` | 조건부/선택 | machine-readable domain reason | 프로그램 분기는 `status + reason.code` 사용 |
| `reason.note` | 선택 | 사람용 최소 진단 설명 | 분기 조건으로 사용하지 않음 |

---

# 5. 상태 의미와 값 Invariant

| status | `value` 규칙 | 의미 |
| --- | --- | --- |
| `OK` | **필수** | Producer가 정상적으로 관찰을 수행해 사용할 수 있는 값을 냄. 최종 확정 의미 아님 |
| `NEEDS_REVIEW` | 값 존재 또는 `null` 가능 | tentative 값이 있거나 추가 확인이 필요한 관찰 |
| `UNKNOWN` | `null` | 정상적으로 시도했으나 신뢰 가능한 값을 결정할 수 없음 / Source 자체가 없을 수 있음 |
| `ERROR` | `null` | 관찰 작업 자체의 처리 실패 |
| `NOT_APPLICABLE` | `null` | 해당 입력/상황에서 이 관찰이 적용 대상이 아님 |

추가 규칙:

- 정상적으로 탐색했지만 결과가 비어 있는 경우 `OK + []`처럼 **known-empty**를 표현할 수 있다.
- 아직 실행하지 않은 상태는 Observation으로 만들지 않는다. `PENDING`, `QUEUED`, `RUNNING`은 `case` / `JobExecution` 책임이다.
- Readout의 `ABSTAIN`은 공통 status로 추가하지 않는다. 예: `NEEDS_REVIEW + PlateReadout.abstained=true`.

---

# 6. Provenance 규칙

## `source`

**무엇을 보고 이 말을 했는가**를 표현한다.

예:

```
recording.filename_time
readout.overlay_ocr
search.visual_inference
```

`source.kind`에는 provider/model/internal stage 이름을 넣지 않는다.

```
search.visual_inference      ✅
search.gemini_3_7_coarse     ❌
```

## `support_refs[]`

관찰을 뒷받침하는 구체적인 `FrameRef`, `AssetSpan` 등의 opaque reference 목록이다.

- 근거 payload 자체를 embed하지 않는다.
- **배열 순서는 semantic 또는 temporal ordering을 보장하지 않는다.**
- 시간 관계는 각 참조 대상 Contract의 timeline/timestamp 정보가 담당한다.

## `produced_by`

**누가 / 어떤 Producer logical run에서 만들었는가**를 표현한다.

### `run_ref`

- Producer가 별도 logical run identity를 가진 경우 사용한다.
- Search Observation이면 `AnalysisRun.run_id`를 참조할 수 있다 — `{ "kind": "analysis_run", "ref": <run_id> }`.
- Readout Observation이면 `ReadoutRun.run_id`를 참조한다 — `{ "kind": "readout_run", "ref": <run_id> }` (2026-09-07 등재, B03). `readout` 결과는 항상 `ReadoutRun`에서 나오므로 `readout`은 이 필드를 항상 채운다(Producer-side 강화, `contract-plate-overlay-readout.md` §3). 공용 계약의 optional 의미는 바뀌지 않는다.
- run identity를 뜻하는 `kind`는 현재 `analysis_run` · `readout_run` 둘이다. 새 run 종류는 계약 개정으로 추가한다(`contract-usage-record.md` §5의 필드 수준 제약과 같은 어휘).
- `JobRecord.job_id` 또는 common/runtime의 `JobExecution`을 의미하지 않는다.
- Job 발주·실행과 산출물의 관계는 `JobRecord` / `JobExecution.produced`가 소유한다.
- recording 등 별도 run Contract가 없는 Producer는 생략할 수 있다.

### `impl_ref`

- Producer 구현 identity가 필요할 때 사용하는 opaque label이다.
- `run_ref`가 가리키는 Run Contract에 상세 implementation metadata가 존재하면 그것이 authoritative source다.
- 모델·prompt·config 전체를 Observation에 중복 복사하지 않는다.

---

# 7. Confidence 규칙

`confidence`는 optional 보조 정보다.

```
confidence {
    score: 0.94
    metric: readout.overlay.sequence_consistency
}
```

불변 규칙:

1. `confidence`가 없다는 것은 `score=0.0`을 의미하지 않는다.
2. 서로 다른 `confidence.metric`의 score는 별도 정의가 없는 한 직접 비교하지 않는다.
3. `evidence`는 bare confidence 숫자 하나만으로 최종 확정을 내리지 않는다.
4. Search 내부의 모든 `ranking_score` / 모델 score를 Observation confidence로 변환할 필요는 없다.

---

# 8. Reason 규칙

```
reason {
    code: namespaced string
    note?: string
}
```

- `reason.code`는 Producer/domain이 소유하는 stable machine-readable reason이다.
- `reason.note`는 사람용 진단 설명일 뿐 프로그램 분기에 사용하지 않는다.
- 민감한 번호판·GPS·영상 payload나 raw provider response를 note에 반복 기록하지 않는다.
- 사용자-facing 문구는 Observation reason 자체가 아니라 downstream의 Evidence/CaseView safe projection을 통해 제공한다.

---

# 9. Immutability / Lifecycle

1. 한번 발행된 Observation의 의미를 후속 재실행 결과로 덮어쓰지 않는다.
2. 동일 입력을 다시 실행하더라도 새 execution/result에 속한 Observation으로 취급한다.
3. Observation 자체에 global `observation_id`를 필수로 요구하지 않는다.
4. `contract_version`, `produced_by.module`, 가능한 경우 `run_ref`로 provenance를 추적한다.
5. Observation은 별도 DB entity를 강제하지 않는 immutable value object로 취급한다.

---

# 10. 적용 범위

`Observation<T>`는 **모듈 경계를 넘어 실제로 관찰된 사실로 소비되는 semantic value**에 적용하는 공통 envelope다.

모든 세부 필드를 Observation으로 감싸지 않는다.

예를 들어 `PlateReadout.best_frame`, diagnostics, 내부 threshold 등 도메인 구조 전체를 중첩 Observation으로 만드는 것은 요구하지 않는다.

---

# 11. Job / Run / UI 상태와의 경계

아래 상태는 서로 다른 책임이므로 합치지 않는다.

```
Observation.status
= OK / NEEDS_REVIEW / UNKNOWN / ERROR / NOT_APPLICABLE

AnalysisRun.outcome
= SUCCEEDED / PARTIAL / FAILED

JobExecution.status
= QUEUED / RUNNING / SUCCEEDED / FAILED / STALE

CaseView.progress.state
= PENDING / RUNNING / DONE / FAILED
```

- Observation은 개별 관찰값 상태를 표현한다.
- AnalysisRun은 Search logical run 전체의 terminal domain outcome을 표현한다.
- JobExecution은 runtime lifecycle을 표현한다.
- CaseView는 web을 위한 UI projection을 표현한다.

---

# 12. 예시

## Recording — GPS 정상 관찰

```json
{
  "contract_version": "observation/v1",
  "value": { "lat": 35.0, "lng": 126.0 },
  "status": "OK",
  "source": {
    "kind": "recording.gps_stream",
    "ref": { "kind": "media_stream", "ref": "stream_03" }
  },
  "support_refs": [
    { "kind": "source_asset", "ref": "source_01" }
  ],
  "produced_by": {
    "module": "recording",
    "impl_ref": "gps-parser/default"
  }
}
```

## Search — logical run에서 생성된 관찰

```json
{
  "contract_version": "observation/v1",
  "value": { "visual_event_type": "SOLID_LINE_LANE_CHANGE" },
  "status": "NEEDS_REVIEW",
  "source": {
    "kind": "search.visual_inference",
    "ref": { "kind": "asset_span", "ref": "span_204" }
  },
  "support_refs": [
    { "kind": "frame", "ref": "frame_441" },
    { "kind": "frame", "ref": "frame_449" }
  ],
  "produced_by": {
    "module": "search",
    "run_ref": { "kind": "analysis_run", "ref": "run_01J..." }
  },
  "reason": {
    "code": "search.visual.temporal_relation_uncertain"
  }
}
```

## GPS source 없음

```json
{
  "contract_version": "observation/v1",
  "value": null,
  "status": "UNKNOWN",
  "source": { "kind": "recording.gps_stream" },
  "support_refs": [],
  "produced_by": { "module": "recording" },
  "reason": {
    "code": "recording.gps.source_absent"
  }
}
```

---

# 13. 불변조건

- `OK`이면 `value != null`이어야 한다.
- `UNKNOWN`, `ERROR`, `NOT_APPLICABLE`이면 `value == null`이어야 한다.
- known-empty는 `OK + empty value`로 표현할 수 있으며 `UNKNOWN/ERROR`와 동일시하지 않는다.
- 미실행 상태를 Observation status로 표현하지 않는다.
- `ABSTAIN`을 공통 Observation status에 추가하지 않는다.
- `source.kind`에 provider/model/internal stage를 넣지 않는다.
- `support_refs[]` 배열 순서에 semantic/temporal 의미를 부여하지 않는다.
- `confidence` 제공 시 `score`와 `metric`을 함께 제공한다.
- 서로 다른 metric의 confidence를 기본적으로 직접 비교하지 않는다.
- `reason.note`를 프로그램 분기 조건으로 사용하지 않는다.
- `produced_by.run_ref`는 Producer logical run을 의미하며 Job ID/JobExecution을 의미하지 않는다.
- 재실행 결과로 과거 Observation을 in-place 수정하지 않는다.

---

# 14. 다른 Contract와의 접합

| Contract | 접합 규칙 |
| --- | --- |
| `AnalysisRun` | Search Observation의 `produced_by.run_ref`가 `AnalysisRun.run_id`를 가리킬 수 있음 (`kind=analysis_run`) |
| `ReadoutRun` | Readout Observation의 `produced_by.run_ref`가 `ReadoutRun.run_id`를 가리킴 (`kind=readout_run`). 결과 문서 최상위 `run_ref`와 같은 실행 |
| `JobRecord` / `JobExecution` | Observation이 Job provenance를 중복 소유하지 않음. Job → 산출물 연결은 runtime/common 책임 |
| `PlateReadout` | `ABSTAIN` 등 domain-specific 상태는 PlateReadout이 소유 |
| `OverlayTimeReadout` | 판독/검증 결과 중 semantic observation에 Observation envelope 적용 가능 |
| `EvidenceRecord` / `TimeResolution` | Observation을 입력으로 받아 확정값과 provenance를 생성 |
| `CaseView` | raw Observation을 web에 직접 전달하지 않고 safe projection으로 변환 |

---

# 15. 변경 규칙

다음과 같이 계약 의미가 바뀌는 변경은 Producer/Consumer 확인 후 Contract Version 증가와 ADR 변경 또는 Supersede 대상이다.

- 필수/선택 의미 변경
- status 의미 또는 값 invariant 변경
- `source` / provenance 의미 변경
- Producer / Consumer 책임 변경
- UNKNOWN / ERROR / NOT_APPLICABLE 의미 변경
- immutability / lifecycle 의미 변경
- 다른 모듈 구현 계약에 영향을 주는 field 변경

사소한 설명 문구나 예시 정리는 같은 의미를 유지하는 범위에서 문서 수정으로 처리할 수 있다.

---

# 16. 최종 한 줄 계약

> **`recording`·`search`·`readout`은 관찰값을 값·상태·출처·근거·Producer run provenance를 가진 immutable `Observation<T>`로 보장하고, `evidence`와 `case`는 이를 확정값과 safe projection의 입력으로 소비한다.**
>