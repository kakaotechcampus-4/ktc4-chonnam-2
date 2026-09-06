# Final Data Contract — CorrectionRecord v1

**Status:** `Draft — Consumer Review 대기`

**Architecture Contract:** v4 §5-1 ⑬ · §4-모듈5 ⑤ 소유 데이터

**Contract:** `CorrectionRecord`

**Contract Version:** `correction-record/v1`

**Related ADR:** `adr/adr-correction-record.md`

**Contract Lead / Owner:** 유소연 (`case`)

**Runtime Producer:** `case`

**Consumer:** `evidence` — 김준영 (`TimeResolution.considered[].input_ref` · `EvidenceValue.user_corrected` provenance)

> `eval`은 이 계약을 직접 읽지 않는다. 평가·재사용은 `case/decisions/correction-log-reuse.md`의 **익명화 copy**를 통해서만 이뤄지며(`product-spec.md` §7 불변 경계), 그 copy는 본 계약의 범위 밖이다.

> **Status가 `Draft`인 이유** — 작성자가 §11에 「정식 Consumer Review 이전」이라고 명시했다. Mock Pack v1 언블록용 최소 스키마이며 `evidence`(김준영) 리뷰 후 v1.1로 올린다. 나머지 계약과 달리 `Final`로 표기하지 않는다.

---

## 1. 계약 목적

사용자가 화면에서 값을 직접 수정한 이력(보정)을 기록한다. 이 계약이 필요한 이유는 `case`가 새 기능을 만들어서가 아니라, **이미 다른 계약들이 이 데이터의 존재를 전제로 자신의 불변조건을 세워놨기 때문**이다.

- `contract-time-resolution.md` §5 — 「`considered[].input_kind=USER_INPUT`인 경우 `input_ref`는 case가 이미 소유하는 `CorrectionRecord`를 직접 참조한다」
- 같은 문서 §5·§불변조건 9 — 「`user_corrected=true`이면 선택 provenance에서 해당 `CorrectionRecord`까지 추적 가능해야 한다」
- `contract-evidence-record-needs.md` §관련 계약 — 「`CorrectionRecord`: 사용자 수정 provenance」
- v4 §11-4 — 「correction이 어떤 `selection_rev`/candidate context에서 발생했는지는 보존할 수 있어야 한다. 구체 필드는 Data Contract에서 확정한다」

## 2. 책임 경계

**Producer(`case`)가 보장하는 것**

- 사용자가 값을 직접 수정한 시점마다 `CorrectionRecord` 1건 생성
- 수정 시점의 `selection_rev`, `kind`, 대상 필드, 이전/이후 값, 수정 시각 기록
- append-only — 기존 기록을 in-place 수정하지 않는다

**Consumer(`evidence`)가 기대할 수 있는 것**

- `TimeResolution.considered[].input_ref`가 가리키는 대상이 실제로 존재한다
- `user_corrected=true`인 값에 대해 `selection_rev` 기준 역추적이 가능하다

**이 Contract가 보장하지 않는 것**

- `target_field`의 닫힌 enum — `evidence` 필드명과 합의 전이다 (§9)
- 익명화된 재사용 형태 — `case/decisions/correction-log-reuse.md` 소관이며 본 계약(원본 기록)의 범위 밖
- 동일 필드 다건 수정 시 「현재 유효값」 판정 규칙 (§9)

## 3. 확정 Contract 스키마 (JSON)

```json
{
  "correction_id": "string",
  "case_id": "string",
  "selection_rev": "int",
  "kind": "TIME_HINT_EDIT | OTHER_CANDIDATE | PLATE_MANUAL_EDIT | PLATE_REREAD | SPAN_ADJUST | REPORT_TYPE_CHANGE | EVENT_TIME_MANUAL | TIMELINE_REBASE",
  "target_field": "string",
  "previous_value": "any",
  "new_value": "any",
  "corrected_at": "ISO8601"
}
```

## 4. 필드 정의

| 필드 | 타입 | 필수 | 의미 | 상태 |
| --- | --- | --- | --- | --- |
| `correction_id` | string | Y | 고유 식별자. 재사용 없음 | 신규 |
| `case_id` | string | Y | 소속 Case | 확인됨 |
| `selection_rev` | int | Y | 수정 발생 시점의 selection revision | `contract-time-resolution.md` §불변조건 9 요구를 직접 충족 |
| `kind` | enum(8) | Y | 수정 종류 | **확인됨** — 계약 회의 v1 원문 |
| `target_field` | string | Y | 수정 대상 필드(예: `plate`, `event_time`) | **[추가검토 필요]** — §9 |
| `previous_value` / `new_value` | any | Y | 수정 전/후 값 | 신규. 타입 세분화는 이후 |
| `corrected_at` | ISO8601 | Y | 수정 시각 | 신규 |

## 5. ContractRef 표기

다른 계약이 이 레코드를 참조할 때 쓰는 `ContractRef.kind`는 **`correction_record`**로 고정한다.

```
input_kind = USER_INPUT
input_ref = { kind: correction_record, ref: <correction_id> }
```

`contract-time-resolution.md` §5가 이미 같은 표기를 쓰고 있다. 새로 정한 것이 아니라 이 계약 쪽에 명시만 한 것이다.

## 6. Enum

**`kind`** — `TIME_HINT_EDIT` · `OTHER_CANDIDATE` · `PLATE_MANUAL_EDIT` · `PLATE_REREAD` · `SPAN_ADJUST` · `REPORT_TYPE_CHANGE` · `EVENT_TIME_MANUAL` · `TIMELINE_REBASE`

> `JobRecord.kind`와 **다른 값 공간**이다(`adr/adr-job-record-case-view.md` §2·§10에서 확인됨). 두 enum을 한 코드에서 다룰 때 섞지 않는다.

`contract-time-resolution.md` §5가 이 값들에 규칙을 걸어 놨다 — `EVENT_TIME_MANUAL`만 최종 `occurred_at`의 USER_INPUT 근거가 될 수 있고, `TIME_HINT_EDIT`는 Search 범위 조정용이라 최종 시각 근거로 승격하지 않는다.

**`target_field`** — [추가검토 필요]. 닫힌 목록이 아니다. `kind`와의 대응으로 미루어 `plate`, `event_time`, `location`, `situation`, `report_type`, `span`, `timeline` 등이 후보이나 **case의 제안이며 확정이 아니다.**

## 7. 정상 예시

```json
{
  "correction_id": "corr_104",
  "case_id": "case_3",
  "selection_rev": 2,
  "kind": "PLATE_MANUAL_EDIT",
  "target_field": "plate",
  "previous_value": "12가 3476",
  "new_value": "12가 3475",
  "corrected_at": "2026-09-05T09:12:00+09:00"
}
```

```json
{
  "correction_id": "corr_205",
  "case_id": "case_3",
  "selection_rev": 3,
  "kind": "OTHER_CANDIDATE",
  "target_field": "situation",
  "previous_value": "백색 실선 crossing 가능성",
  "new_value": "다른 차량 끼어들기",
  "corrected_at": "2026-09-05T10:02:00+09:00"
}
```

## 8. 불변조건

1. `correction_id`는 재사용되지 않는다 (append-only)
2. `selection_rev`는 수정 발생 시점 값으로 고정되며 이후 변경되지 않는다
3. `kind`는 `JobRecord.kind`와 다른 값 공간이다
4. 익명화 규칙(`case/decisions/correction-log-reuse.md`)은 본 계약(원본)이 아니라 재사용 copy에만 적용된다
5. 이 레코드의 존재가 `EvidenceValue.user_corrected=true`를 **직접 뜻하지는 않는다.** 해당 correction이 최종값에 실제 반영됐는지는 `evidence`가 판정한다 (`contract-time-resolution.md` §불변조건 5)

## 9. 미해결 항목

- **`target_field`의 값 공간** — `evidence` 필드명 및 `CaseView`의 display 필드명(`plate`/`event_time`/`location` · `case_type`/`report_type`/`violation`)과 정렬해야 한다. `CaseView` §13의 projection 필드명 확정과 같은 자리에서 처리한다
- **동일 필드 다건 수정 시 「현재 유효값」 판정 규칙** — [제안] 수준
- **실패한 수정의 처리** — 애초에 레코드를 만들지 않는 것으로 보나 [제안]이며 `evidence` 재확인 필요
- `evidence`(김준영) 정식 Consumer Review — 미진행

> 위 넷은 **채우지 않고 미결로 둔다**(`docs/README.md` · `CLAUDE.md` 「하지 말 것」 4).
