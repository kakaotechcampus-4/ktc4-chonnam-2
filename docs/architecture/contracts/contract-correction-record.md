# Data Contract — CorrectionRecord v1.1

**Status:** `Final — Accepted`

**Accepted:** 2026-09-10 · evidence Consumer Review 수용 조건(`docs/modules/evidence/contracts/correction-record-consumer-review-2026-09-10.md`, 김준영) 6건을 전부 반영해 `v1`(Draft)에서 `v1.1`(Final)로 승격

**Architecture Contract:** v4 §5-1 ⑬ · §4-모듈5 ⑤ 소유 데이터

**Contract:** `CorrectionRecord`

**Contract Version:** `correction-record/v1.1`

**Related ADR:** `adr/adr-correction-record.md` · Consumer Review: `docs/modules/evidence/contracts/correction-record-consumer-review-2026-09-10.md`

**Contract Lead / Owner:** 유소연 (`case`)

**Runtime Producer:** `case`

**Consumer:** `evidence` — 김준영 (`TimeResolution.considered[].input_ref` · `EvidenceValue.user_corrected` provenance)

> `eval`은 이 계약을 직접 읽지 않는다. 평가·재사용은 `case/decisions/correction-log-reuse.md`의 **익명화 copy**를 통해서만 이뤄지며(`product-spec.md` §7 불변 경계), 그 copy는 본 계약의 범위 밖이다.

> **`v1.1` 변경 (2026-09-10) — v1(Draft)의 §9 미해결 항목 4건을 evidence Consumer Review 수용 조건으로 확정하고 Final로 승격했다.** ① `target_field`를 자유 문자열에서 **evidence가 실제 소비하는 의미 경로(semantic path)** 값 공간으로 좁힘 ② append-only supersede chain(`supersedes_ref`) 신설 — 동일 `target_field` 재수정은 새 `correction_id` + `supersedes_ref`로 이전 correction을 가리키고, "현재 유효값"은 최신 `corrected_at`이 아니라 **chain의 head**다 ③ `previous_value`/`new_value`에 target별 타입 검증 추가(무제한 `any` 저장 금지) ④ lifecycle 3원칙 확정(무효/무변경 입력 미생성, 유효 수정은 downstream보다 먼저 append-only 기록, downstream 실패해도 삭제하지 않음) ⑤ `kind`에 `SITUATION_CHANGE` 추가(9종) ⑥ 「잘 모르겠어요」 단순 응답은 값 수정이 아니라 case workflow state이므로 CorrectionRecord를 만들지 않는다 — 그 provenance는 `contract-evidence-record-needs.md` v1.3의 `EvidenceRecord.event.situation_response`가 대신 보존한다. Decider 유소연(`case`) · Consumer Review 김준영(`evidence`).

---

## 1. 계약 목적

사용자가 화면에서 값을 직접 수정한 이력(보정)을 기록한다. 이 계약이 필요한 이유는 `case`가 새 기능을 만들어서가 아니라, **이미 다른 계약들이 이 데이터의 존재를 전제로 자신의 불변조건을 세워놨기 때문**이다.

- `contract-time-resolution.md` §5 — 「`considered[].input_kind=USER_INPUT`인 경우 `input_ref`는 case가 이미 소유하는 `CorrectionRecord`를 직접 참조한다」
- 같은 문서 §5·§13 Invariants 9 — 「`user_corrected=true`이면 선택 provenance에서 해당 `CorrectionRecord`까지 추적 가능해야 한다」
- `contract-evidence-record-needs.md` §관련 계약 — 「`CorrectionRecord`: 사용자 수정 provenance」
- v4 §11-4 — 「correction이 어떤 `selection_rev`/candidate context에서 발생했는지는 보존할 수 있어야 한다. 구체 필드는 Data Contract에서 확정한다」

## 2. 책임 경계

**Producer(`case`)가 보장하는 것**

- 사용자가 값을 직접 수정한 시점마다 `CorrectionRecord` 1건 생성 — 단, 입력이 유효하지 않거나 값이 실제로 바뀌지 않았다면 생성하지 않는다(§8 불변조건 6·7)
- 수정 시점의 `selection_rev`, `kind`, 대상 필드(semantic path), 이전/이후 값, 수정 시각 기록
- append-only — 기존 기록을 in-place 수정하지 않는다. 동일 `target_field` 재수정은 새 레코드 + `supersedes_ref`로 연결한다(§3·§8)
- 유효한 사용자 수정은 downstream Evidence 재조립/Job 발주보다 **먼저** 기록한다. 이후 재조립·실행이 실패해도 이미 기록된 CorrectionRecord는 삭제하지 않는다(§8 불변조건 8·9)

**Consumer(`evidence`)가 기대할 수 있는 것**

- `TimeResolution.considered[].input_ref`가 가리키는 대상이 실제로 존재한다
- `user_corrected=true`인 값에 대해 `selection_rev` 기준 역추적이 가능하다
- `target_field`가 evidence 자신의 필드 경로와 같은 이름 공간을 공유한다 — 자유 문자열을 다시 해석할 필요가 없다(§3)
- 동일 대상이 여러 번 수정됐을 때 supersede chain의 head를 따라가면 현재 유효값을 판정할 수 있다(§3·§8)

**이 Contract가 보장하지 않는 것**

- 익명화된 재사용 형태 — `case/decisions/correction-log-reuse.md` 소관이며 본 계약(원본 기록)의 범위 밖
- 「잘 모르겠어요」류 workflow 응답의 보존 — `contract-evidence-record-needs.md` v1.3의 `event.situation_response` 소관(§8 불변조건 10)

## 3. Contract 스키마 (JSON)

```json
{
  "correction_id": "string",
  "case_id": "string",
  "selection_rev": "int",
  "kind": "TIME_HINT_EDIT | OTHER_CANDIDATE | PLATE_MANUAL_EDIT | PLATE_REREAD | SPAN_ADJUST | REPORT_TYPE_CHANGE | EVENT_TIME_MANUAL | TIMELINE_REBASE | SITUATION_CHANGE",
  "target_field": "string (semantic path — §6)",
  "previous_value": "target별 타입 — §6",
  "new_value": "target별 타입 — §6",
  "supersedes_ref": "{ kind: correction_record, ref: string } | null",
  "corrected_at": "ISO8601"
}
```

## 4. 필드 정의

| 필드 | 타입 | 필수 | 의미 | 상태 |
| --- | --- | --- | --- | --- |
| `correction_id` | string | Y | 고유 식별자. 재사용 없음 | 확인됨 |
| `case_id` | string | Y | 소속 Case | 확인됨 |
| `selection_rev` | int | Y | 수정 **발생 시점**의 selection revision — 수정 횟수 카운터가 아니라 그 수정이 일어난 candidate 선택 context다 | 확인됨 |
| `kind` | enum(9) | Y | 수정 종류 | **확인됨(v1.1, `SITUATION_CHANGE` 추가)** |
| `target_field` | string(semantic path) | Y | 수정 대상 필드 — §6 값 공간 | **확인됨(v1.1)** |
| `previous_value` / `new_value` | target별 타입 | Y | 수정 전/후 값. 무제한 `any` 아님 — §6 검증 규칙 | **확인됨(v1.1)** |
| `supersedes_ref` | `ContractRef{kind:correction_record}` \| null | Y(키) | 동일 `target_field`를 다시 수정했을 때 직전 correction을 가리킨다. 최초 수정이면 `null` | **신규(v1.1)** |
| `corrected_at` | ISO8601 | Y | 수정 시각 | 확인됨 |

## 5. ContractRef 표기

다른 계약이 이 레코드를 참조할 때 쓰는 `ContractRef.kind`는 **`correction_record`**로 고정한다.

```
input_kind = USER_INPUT
input_ref = { kind: correction_record, ref: <correction_id> }
```

`contract-time-resolution.md` §5가 이미 같은 표기를 쓰고 있다.

## 6. `target_field` 값 공간과 값 검증 (v1.1 확정)

evidence Consumer Review가 실제로 소비하는 최소 값 공간이다. `case`는 후보 선택·span·timeline용 경로를 추가할 수 있지만 evidence 필드와 같은 이름으로 뭉개지 않고 별도 namespace로 정의한다(예: `candidate.selected_id`, `span.start_ms` 등 — 닫힌 목록 아님, evidence 아래 10개 semantic path는 닫힘 — `correction-record-consumer-review-2026-09-10.md` v1.1 수용 조건 ①의 목록 그대로).

| `target_field` | 값 타입 | 검증 |
| --- | --- | --- |
| `event.visual_event_type` | string \| null | `VisualEventType` 값 공간(`contract-analysis-run-candidate-event.md`) |
| `event.safety_report_type` | string \| null | `SafetyReportType` 값 공간(`docs/modules/evidence/decisions/safety-report-policy-v1.md`) |
| `event.violation_expression` | string \| null | 자유 문자열, 5~900자(안전신문고 신고문 제약과 동일 하한/상한 재사용) |
| `occurred_at` | ISO8601 | offset-aware RFC3339 |
| `vehicle_number` | string | 문자열 |
| `location.coord` | `{lat:number, lon:number}` | 좌표 쌍 |
| `location.address` \| `location.place_name` \| `location.search_keyword` \| `location.user_hint` | string \| null | 자유 문자열 |

**`kind`** — `TIME_HINT_EDIT` · `OTHER_CANDIDATE` · `PLATE_MANUAL_EDIT` · `PLATE_REREAD` · `SPAN_ADJUST` · `REPORT_TYPE_CHANGE` · `EVENT_TIME_MANUAL` · `TIMELINE_REBASE` · `SITUATION_CHANGE`(v1.1 신규 — 사용자가 「다른 상황」을 선택해 사건 의미 자체를 바꾼 경우. 단순 「잘 모르겠어요」는 이 kind를 쓰지 않는다 — §8 불변조건 10)

> `JobRecord.kind`와 **다른 값 공간**이다(`adr/adr-job-record-case-view.md` §2·§10에서 확인됨). 두 enum을 한 코드에서 다룰 때 섞지 않는다.

`contract-time-resolution.md` §5가 이 값들에 규칙을 걸어 놨다 — `EVENT_TIME_MANUAL`만 최종 `occurred_at`의 USER_INPUT 근거가 될 수 있고, `TIME_HINT_EDIT`는 Search 범위 조정용이라 최종 시각 근거로 승격하지 않는다.

## 7. 정상 예시

```json
{
  "correction_id": "corr_104",
  "case_id": "case_3",
  "selection_rev": 2,
  "kind": "PLATE_MANUAL_EDIT",
  "target_field": "vehicle_number",
  "previous_value": "12가 3476",
  "new_value": "12가 3475",
  "supersedes_ref": null,
  "corrected_at": "2026-09-05T09:12:00+09:00"
}
```

동일 `target_field`를 다시 수정한 경우 — supersede chain:

```json
{
  "correction_id": "corr_205",
  "case_id": "case_3",
  "selection_rev": 3,
  "kind": "PLATE_MANUAL_EDIT",
  "target_field": "vehicle_number",
  "previous_value": "12가 3475",
  "new_value": "12가 3479",
  "supersedes_ref": { "kind": "correction_record", "ref": "corr_104" },
  "corrected_at": "2026-09-05T10:02:00+09:00"
}
```

「다른 상황」 선택(`SITUATION_CHANGE`):

```json
{
  "correction_id": "corr_301",
  "case_id": "case_3",
  "selection_rev": 3,
  "kind": "SITUATION_CHANGE",
  "target_field": "event.visual_event_type",
  "previous_value": "SOLID_LINE_LANE_CHANGE",
  "new_value": "CENTER_LINE_CROSSING",
  "supersedes_ref": null,
  "corrected_at": "2026-09-05T10:05:00+09:00"
}
```

## 8. 불변조건

1. `correction_id`는 재사용되지 않는다 (append-only)
2. `selection_rev`는 수정 발생 시점 값으로 고정되며 이후 변경되지 않는다
3. `kind`는 `JobRecord.kind`와 다른 값 공간이다
4. 익명화 규칙(`case/decisions/correction-log-reuse.md`)은 본 계약(원본)이 아니라 재사용 copy에만 적용된다
5. 이 레코드의 존재가 `EvidenceValue.user_corrected=true`를 **직접 뜻하지는 않는다.** 해당 correction이 최종값에 실제 반영됐는지는 `evidence`가 판정한다 (`contract-time-resolution.md` §10 항목 5)
6. **(v1.1)** 입력 형식이 유효하지 않으면 CorrectionRecord를 만들지 않는다
7. **(v1.1)** `new_value`가 `previous_value`와 같다면(실질적으로 값이 바뀌지 않았다면) CorrectionRecord를 만들지 않는다
8. **(v1.1)** 유효한 사용자 수정은 downstream Evidence 재조립·Job 발주보다 먼저 append-only로 기록한다
9. **(v1.1)** 기록 이후 downstream 재조립·실행이 실패해도 이미 기록된 CorrectionRecord를 삭제하거나 되돌리지 않는다
10. **(v1.1)** 단순 「잘 모르겠어요」(사건 유형을 특정하지 않고 불확실하다고만 답한 경우)는 값 correction이 아니라 case workflow state이므로 이 계약으로 기록하지 않는다 — `SITUATION_CHANGE`는 사용자가 **다른 구체적 상황을 실제로 선택**했을 때만 쓴다
11. **(v1.1)** 동일 `case_id`·동일 `target_field`의 현재 유효값은 최신 `corrected_at`이 아니라 `supersedes_ref` chain의 **head**(어느 correction도 자신을 `supersedes_ref`로 가리키지 않는 레코드)다

## 9. 남은 것

- 익명화 재사용 copy(`case/decisions/correction-log-reuse.md`)의 구체 스키마는 본 계약 범위 밖으로 별도 유지
- `case`가 추가하는 non-evidence `target_field` 네임스페이스(후보 선택·span·timeline 등)의 전체 목록은 해당 필드가 실제로 correction 대상이 되는 시점에 이 문서에 추가한다(닫힌 목록 아님)
