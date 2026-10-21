# ADR-EVIDENCE-011: CorrectionRecord 기록 전 검사 경계 (#235 E-3)

> 상태: **ACCEPTED**
>
> 결정일: `2026-10-06`(E-3 결정) · 구현 `2026-10-21`
>
> Decider / Owner: 김준영 (`evidence` Owner) — E-3. E-1 · E-2(`previous_value=null`)는 유소연(`case`, `contract-correction-record.md` Decider) 결정을 옮긴 것이다
>
> 동의: 유소연(`case`, E-3 필수 동의 — #235 `[E-3] Case 의견`)
>
> 적용 범위: `daesingo.evidence` 공개 API `validate_correction_append()` · `InvalidCorrectionValue`, `correction_heads()`의 이전 값 검사(`correction-record/v1.2`)
>
> 근거: 결정 카드 [#235](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/235)의 `[E-1]` · `[E-2]` · `[E-3]` 댓글 · [PR #356 evidence 리뷰](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/356)(사용자 수정 가능 오류와 내부 계약 위반 구분) · PR #234 「남은 크래시」 측정

## 1. 문제

`correction_heads()`는 evidence가 CorrectionRecord를 **읽을 때** 형식 · chain을 검사한다. 기록은 되돌리지 않으므로(`contract-correction-record.md` §8-9) 형식이 틀린 정정이 한 번 기록되면 그 case는 이후 Evidence 조립 · CaseView 생성이 계속 실패한다(#235 §1 — #234 재측정 13,188 세션 중 909건). §8-6은 「형식이 틀린 입력은 기록하지 않는다」를 Producer(case) 몫으로 두지만, 그 형식 표는 evidence 비공개(`_valid_value`)였다.

## 2. 결정

### 2.1 검사 권위는 evidence 한 곳

case는 CorrectionRecord를 append하기 **직전에** `validate_correction_append(correction, *, existing_records)`를 부른다. 통과하면 기록하고, 예외가 나면 아무것도 기록하지 않는다. target별 값 형식 표와 chain 규칙은 `evidence/corrections.py`에만 있고 case는 복제하지 않는다.

이 함수는 새 규칙을 만들지 않는다. `existing_records + [correction]`에 대해 `correction_heads()`를 그대로 돌린다. 그래서 통과한 기록은 나중에 evidence가 읽을 때 같은 이유로 실패하지 않는다. 검사 범위는 E-3 결정 그대로 **값 형식 + supersede chain 연속성**이고, 그 결과로 head 유일성 · `kind` 값 공간 · `SITUATION_CHANGE`/`occurred_at`의 `kind` 조합 · 무변경 정정 · `correction_id` 재사용도 함께 걸린다.

다른 입력이 있어야 아는 조립 검사 — 상황 응답과 `SITUATION_CHANGE` head 개수, TimeResolution이 고른 correction — 는 이 함수가 보지 않고 조립에 남는다. case 네임스페이스(`hints` · `candidate.selected_id`)는 evidence가 소비하지 않으므로 검사하지 않는다.

### 2.2 거부 두 부류

| 예외 | 뜻 | 원인 | case 쪽 대응(참고 — 결정은 case) |
| --- | --- | --- | --- |
| `InvalidCorrectionValue` | `new_value`가 target 값 공간 밖 | 사용자가 넣은 값 — 다시 입력하면 해결된다 | `case.command.invalid_value` |
| `ContractInputError`(그 밖) | case가 채운 기록이 계약 위반이거나, 이미 기록된 정정이 위반 | chain 단절 · head 중복 · `supersedes_ref` 미해결/타 target · `kind`/target 조합 · 이전 값 형식 · 무변경 · 구조 — 정상 사용자 입력에서는 생기지 않는 배선 오류 | 사용자 입력 오류로 보이지 않는 내부 오류 |

- `InvalidCorrectionValue`는 `ContractInputError`의 하위 타입이다. 기존처럼 `ContractInputError`만 잡는 호출자는 그대로 동작하고, 구분이 필요한 호출자는 `InvalidCorrectionValue`를 먼저 잡는다. 「위반이면 모두 `ContractInputError`」라는 evidence 경계 규칙도 유지된다.
- `target_field` 속성을 싣는다. 어느 값을 다시 받아야 하는지 호출자가 알 수 있게 하려는 것이고, 문구 키는 정하지 않는다.
- 판정 순서는 `new_value` 형식이 먼저다. 값과 배선이 동시에 틀리면 사용자는 먼저 값 오류를 보고, 다시 입력하면 내부 오류가 드러난다 — 그 반대보다 손실이 작다.
- 세부 오류 코드 taxonomy는 만들지 않았다. #356 리뷰가 요구한 것은 두 부류의 구분이고, 기존 예외 패턴(`VisualEventNotAssembled` · `PackageNotReady`처럼 타입으로 결말을 가른다)에 맞춰 타입 하나를 더했다.

### 2.3 이미 기록된 위반

읽는 경로(`correction_heads()`)는 지금처럼 전체를 `ContractInputError`로 거부한다. 건너뛰거나 고쳐 읽지 않는다. 기록 전 검사도 기존 기록이 위반이면 같은 `ContractInputError`를 낸다 — 그 case는 이미 깨져 있고 새 값으로 해결되지 않는다. 운영 데이터 복구가 필요해지면 별도 repair · migration으로 다룬다(#235 E-3).

### 2.4 함께 바뀐 것

- **`previous_value=null`(v1.2, E-1 · E-2).** evidence 의미 경로 모두 이전 값 `null`을 받는다. `new_value`는 값 공간 그대로라 `occurred_at` · `vehicle_number` · `location.coord`는 non-null이다.
- **시각 형식 오류를 값 오류로 판정.** `_valid_value("occurred_at", …)`는 형식이 틀리면 예외 대신 `False`를 돌려준다. 읽는 경로의 메시지는 `datetime must be a string` 등에서 `invalid new_value for occurred_at`/`invalid previous_value for occurred_at`으로 바뀌고, 예외 타입은 그대로다.
- **`occurred_at` head의 `kind` 검사 위치.** `EVENT_TIME_MANUAL`만 최종 시각 근거가 된다는 검사(`contract-time-resolution.md` §5)를 `resolve_time()` 내부에서 `correction_heads()`의 head 선택으로 옮겼다. 기록 전 검사가 이 조합을 잡게 하려는 것이고, 조립 결과는 바뀌지 않는다(그 head는 원래도 `resolve_time()`에서 거부됐다).

## 3. 넣지 않은 것

- **번호판 `new_value` 빈 문자열.** `vehicle_number`의 값 공간은 §6 「문자열」이라 `""`도 통과한다. E-1은 「번호판을 지우는 정정은 받지 않는다」고 했지만 빈 문자열을 그 정정으로 볼지는 값 공간을 좁히는 계약 변경이라 여기서 정하지 않았다 — case-command 입력형 판본(#356)에서 함께 정할 일로 남긴다.
- **selection context를 넘는 chain(§8-12) 거부.** 지금 읽는 경로도 거부하지 않는다. 이미 저장된 기록을 새로 거부하게 되므로 이 ADR에서 소비 규칙을 넓히지 않았다.
- **case 배선.** `apply_correction()`에서 이 함수를 부르는 것, `CONTRACT_VERSION`을 `correction-record/v1.2`로 올리는 것, `invalid_value` 응답은 case Owner 몫이다(#356).

## 4. 검증

- `tests/evidence/test_correction_precheck.py` — v1.2 이전 값 `null` 수용 · `new_value` non-null 유지, 값 오류 8종 → `InvalidCorrectionValue`, 배선 오류 12종 → `ContractInputError`(값 오류 아님), 기존 위반 기록 비무시, 새 selection context · 다른 case · case 네임스페이스, 입력 불변, 응답 대기 중 번호판 · 시각 첫 입력의 부분 투영(#234 경로)
- `tests/evidence/test_plate_boundary_d3.py::test_6c` — Readout 실행 실패(4a) 뒤 직접 입력이 Package · `READY`까지 간다(ADR-EVIDENCE-008 D-3 추가 행)
