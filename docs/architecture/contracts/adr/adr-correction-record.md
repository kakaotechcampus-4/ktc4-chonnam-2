# ADR — `CorrectionRecord` Data Contract

**Status:** Draft — Consumer Review 대기
**Decider:** 유소연 (`case` Owner)
**Date:** 2026-09-06
**Contract:** `../contract-correction-record.md`

---

## 1. Context

`CorrectionRecord`는 v4 §4-모듈5 ⑤ 소유 데이터 표에 `case` 소유로 배정돼 있었지만 **§5-1 계약 목록에는 없었고 계약 문서도 없었다.** 그런데 이미 두 계약이 이 데이터를 참조 가능하다고 전제하고 자신의 불변조건을 세워 놓은 상태였다 — `contract-time-resolution.md` §5(`input_ref`가 직접 참조)와 §불변조건 9(추적 가능성), `contract-evidence-record-needs.md`(사용자 수정 provenance).

정합성 검수 Pass 3에서 F-26(BLOCK)으로 잡혔고 CALL-5 (4)로 `case` Owner에게 넘어갔다. 「10:00까지 최소 스키마를 낼 수 있는가」가 질문이었다.

## 2. Decision

**낼 수 있다 — 8필드 최소 스키마로 확정한다.**

`correction_id` · `case_id` · `selection_rev` · `kind`(8값) · `target_field` · `previous_value` · `new_value` · `corrected_at`

**`selection_rev`를 넣은 이유가 이 결정의 핵심이다.** `contract-time-resolution.md` §불변조건 9가 요구하는 「선택 provenance에서 해당 `CorrectionRecord`까지 추적 가능」을 만족시키려면 수정이 **어느 selection 시점에서 일어났는지**가 레코드에 있어야 한다. 없으면 후보를 바꾼 뒤의 수정과 그 전의 수정이 구분되지 않는다.

**`kind` 8값은 새로 정한 것이 아니다** — 계약 회의 v1 원문에 이미 있던 값을 그대로 옮겼다. `JobRecord.kind`와 값 공간이 겹치지 않는 것도 이미 확인된 사항이다.

## 3. 기각한 안

**(a) `EvidenceRecord`의 provenance 안에 nested로 둔다** — 기각. 생산자가 `case`이고 소비자가 `evidence`인데 `evidence` 계약 안에 두면 소유가 뒤집힌다. `ownership.md` §6 「같은 값을 두 Owner가 확정하지 않는다」에 걸린다.

**(b) `target_field`를 지금 닫는다** — 기각. `evidence` 필드명과 `CaseView` display 필드명이 아직 확정 전이라 지금 닫으면 곧 다시 열어야 한다. 열린 string으로 두고 §9에 미결로 남겼다.

## 4. PM 보정 (2026-09-06)

원안을 두 곳 보완했다. 둘 다 표기 수준이며 결정 내용은 바뀌지 않았다.

| 보정 | 근거 |
| --- | --- |
| `ContractRef.kind = correction_record` 명시 (§5) | `contract-time-resolution.md` §5가 이미 그 표기를 쓰고 있었다. 새로 정한 게 아니라 참조되는 쪽에 적어 둔 것 |
| Consumer 각주에 `eval` 경로 명시 | `product-spec.md` §7이 「익명화한 뒤에만 재사용」으로 경로를 갖고 있다. `eval`을 Consumer 본문에 넣지는 않았다 — 직접 읽는 것이 아니라 익명화 copy를 통하기 때문 |

## 5. Consumer Review

**미진행.** `evidence`(김준영) 리뷰 후 v1.1로 올린다. 그때 `target_field` 값 공간을 같이 닫는다.

## 6. 미결

`target_field` 값 공간 · 동일 필드 다건 수정 시 현재 유효값 판정 · 실패한 수정의 레코드 생성 여부. **채우지 않았다.**
