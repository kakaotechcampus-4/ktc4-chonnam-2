# 입력형 command 구현 — 번호판 직접 입력 · 발생시각 수정 · `[다른 상황]`

> 2026-10-28 · W12 C3 · case-command 계약 §12(입력형 판본) · 근거 [#235](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/235) E-1 · E-2 · E-3 · PR #356(판본 합의) · PR #384(evidence 기록 전 검사)

## 1. 문제

- 입력형 판본(§12)은 합의됐지만(PR #356) 열림 조건 2 · 3(correction v1.2 · evidence 기록 전 검사)을 기다려 구현하지 않았다. PR #384로 두 조건이 갖춰졌다.
- 그동안 `RECORD_SITUATION_RESPONSE`는 `CORRECTED`를 `invalid_payload`로 막았고, `evidence.plate_abstained`는 보낼 command가 없어 `actions`가 비었다.

## 2. 결정

1. **kind 2개를 더하고 `CORRECTED`를 연다.** `MANUAL_PLATE_INPUT{value}` → `PLATE_MANUAL_EDIT` · `vehicle_number`, `EDIT_EVENT_TIME{value}` → `EVENT_TIME_MANUAL` · `occurred_at`, `RECORD_SITUATION_RESPONSE{value: CORRECTED, visual_event_type}` → `SITUATION_CHANGE` · `event.visual_event_type` + 응답. `visual_event_type`은 `CORRECTED`일 때만 있어야 한다(아니면 `invalid_payload`).
2. **기록 전 검사는 `correction.apply_correction()` 안에서 부른다.** evidence `validate_correction_append()`를 append 직전에 부르므로 모든 evidence 경로 정정이 같은 검사를 지난다(case namespace `hints` · `candidate.selected_id`는 evidence가 보지 않고 통과). 거부되면 아무것도 기록하지 않는다.
3. **오류 두 부류(§12-4).** `InvalidCorrectionValue`(값 공간 밖 — 시각 오프셋 없음, 알 수 없는 유형 등)만 `case.command.invalid_value`다. 그 밖의 `ContractInputError`는 case가 만든 레코드의 위반이라 command가 잡지 않고 올린다(HTTP 500). 유형 4종 목록도 case가 복제하지 않고 evidence 값 공간에 맡긴다.
4. **이전 값.** 같은 선택 context에 chain head가 있으면 그 `new_value`, 없으면 사용자가 본 CaseView 값(없으면 `null`). §12-2의 「사용자가 본 값」과 정상 경로에서 같다. head를 우선하는 이유: CaseView 값은 adapter가 조립한 결과라 정규화나 fixture 고정값 때문에 chain 값과 어긋날 수 있고, 어긋나면 evidence chain 연속성 검사가 거부해 내부 오류가 된다.
5. **CorrectionRecord `contract_version`을 `correction-record/v1.2`로 올린다.** v1.2로 기록해야 `vehicle_number` · `occurred_at`의 이전 값 `null`이 유효하다(v1.1 소급 없음).
6. **`[다른 상황]`의 `case_rev`는 한 번만 오른다.** 정정이 올리고 응답은 `record_situation_response(..., bump=False)`로 기록한다. 정정이 거부되면 응답도 남지 않는다. Package가 풀려 `READY`로 오르면 §5대로 +1이 더해진다.
7. **`evidence.plate_abstained`에 `MANUAL_PLATE_INPUT`을 싣는다**(§12-3 「이 판본이 열릴 때 함께 싣는다」). `EDIT_EVENT_TIME`을 싣는 notice는 지금 없다 — 화면 입구는 결과 화면 발생시각 수정(Flow §20)이다.

## 3. 계약에 없던 거부 두 가지

| 거부 | 이유 |
| --- | --- |
| **값 칸이 없는 화면(`evidence=null`)의 정정 → `not_allowed`** | 관찰 전 · 음성 결과(`NOT_ASSEMBLED`) 화면에는 값이 없어 「사용자가 본 이전 값」이 없다. 그대로 `null`로 기록하면 나중에 조립된 값과 chain이 어긋난다. 상황 응답 대기의 부분 투영(`record_id=null`)은 `evidence`가 있으므로 받는다 |
| **`[다른 상황]` 정정이 있는 후보의 `USER_UNSURE` → `not_allowed`** | evidence가 `USER_UNSURE cannot create a SITUATION_CHANGE`로 조립을 거부한다. 정정은 지우지 않으므로(correction-record §8-9) 받으면 그 case는 이후 CaseView를 만들 수 없다. `CONFIRMED`는 받는다(정정한 유형을 확인하는 뜻으로 조립된다) |

## 4. 알려진 한계

- **상황 응답 대기에서 `[다른 상황]`으로 AI가 본 유형과 같은 유형을 고르면 막지 못한다.** 부분 투영에는 유형 값이 없어(`case_type_display.code=null`) case가 비교할 값이 없다. 기록되면 evidence는 그 유형으로 조립한다 — 결과는 `[맞아요]`와 같다. web도 CaseView만 받으므로 지금 유형을 모른다 — 부분 투영에서는 4종을 모두 보여 주고, 지금 값이 있을 때만 뺀다(§12-3, 2026-10-28 PR #433 web 확인). Fine 잠정 유형을 CaseView에 싣는 안은 계약 변경이라 이번에 택하지 않았다(§5).
- **시각 정정 뒤 신고용 영상 재발주는 하지 않는다.** #351 [R-1] 자동 발주(`report-video-export.md`)가 맡고, 그 배선은 recording export handler 뒤로 보류돼 있다.
- web 정정 입력 UI(W4)는 web 소유다 — 이 PR 뒤 연결한다.

## 5. 고르지 않은 안

| 안 | 고르지 않은 이유 |
| --- | --- |
| 기록 전 검사를 command 층에서만 부르기 | `apply_correction()`을 직접 부르는 다른 경로(테스트 · 향후 command)가 검사를 건너뛴다 |
| 이전 값을 항상 CaseView에서 읽기 | adapter 정규화 · fixture 고정값과 chain이 어긋나면 내부 오류가 된다(§2-4) |
| `CORRECTED`를 정정 command와 응답 command 둘로 나누기 | 사이에 실패하면 `CORRECTED` 응답만 남아 evidence가 조립을 거부한다. §12-3이 한 command로 정했다 |
| 부분 투영에 Fine 잠정 유형을 실어 `[다른 상황]`에서 빼기 | CaseView 필드 추가(계약 변경)와 evidence · web 재확인이 필요하다. 같은 유형을 골라도 결과가 `[맞아요]`와 같아 해가 없다 |
| case가 유형 4종 · 시각 형식을 직접 검사 | target별 형식 규칙은 evidence 한 곳에만 둔다(#235 E-3) |

## 6. 테스트

`tests/case/test_input_commands.py` — 번호판 입력 → evidence 반영 · `INFO_USER_CONFIRMED`, 두 번째 입력의 supersede · 이전 값, 무변경 거부, 번호판 없음의 `null` 이전 값, 시각 정정 · 오프셋 없는 값 `invalid_value`, `[다른 상황]`의 정정 + 응답 · `case_rev` 한 번, 두 번째 정정의 chain, `visual_event_type` 유무 `invalid_payload`, 알 수 없는 유형 `invalid_value`, 지금 유형 `not_allowed`, 정정 뒤 `USER_UNSURE` 거부 · `CONFIRMED` 허용, 선택 전 · `evidence=null` 거부, `READY`에서 정정, 내부 계약 위반은 `ContractInputError`, `plate_abstained` action.
