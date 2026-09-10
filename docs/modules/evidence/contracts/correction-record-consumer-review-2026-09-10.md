# CorrectionRecord Consumer Review - evidence

> 검토일: 2026-09-10
> Consumer: 김준영 (`evidence`)
> 대상: `docs/architecture/contracts/contract-correction-record.md` (`correction-record/v1`, Draft)
> 판정: `REQUEST_CHANGES` - 아래 수용 조건은 확정, case Owner의 v1.1 반영 후 Final 가능

## 확인한 원본 근거

- Timestamp 연구 PDF §15는 사용자가 시각을 수정해도 최초 자동 관찰값, 최종 사용자 값, 수정 이유를 함께 보존하도록 한다.
- 현재 `contract-time-resolution.md`는 `USER_INPUT`의 authoritative provenance로 `CorrectionRecord`를 직접 참조한다.
- `docs/mock/07_kim-junyoung_mock_round2_review_2026-09-09.md` §10에는 case/common-runtime 답변 검토 후 `SITUATION_CHANGE`, semantic `target_field`, `supersedes_ref`, invalid-input 미생성, downstream 실패 시 보존 방향을 이미 확정한 기록이 있다.
- 기존 Draft의 append-only, `selection_rev`, `ContractRef.kind=correction_record`, case Producer/evidence Consumer 경계는 수용한다.

## v1.1 수용 조건

### 1. semantic `target_field`

자유 문자열 `plate`, `event_time` 대신 의미 경로를 사용한다. evidence가 직접 소비하는 최소 값 공간은 다음과 같다.

- `event.visual_event_type`
- `event.safety_report_type`
- `event.violation_expression`
- `occurred_at`
- `vehicle_number`
- `location.coord`
- `location.address`
- `location.place_name`
- `location.search_keyword`
- `location.user_hint`

case가 후보 선택, span, timeline용 경로를 추가할 수는 있지만 evidence 필드와 같은 이름으로 뭉개지 않고 별도 namespace로 정의해야 한다.

### 2. append-only supersede chain

동일 case·동일 `target_field`를 다시 수정하면 새 `correction_id`를 만들고 `supersedes_ref?: {kind: correction_record, ref}`로 직전 correction을 연결한다. 현재 유효 correction은 단순 최신 `corrected_at`이 아니라 supersede chain의 head다.

### 3. 값 검증

`previous_value`와 `new_value`는 target별 Contract 타입을 따라야 한다. `occurred_at`은 offset-aware RFC3339, `vehicle_number`는 문자열, 좌표는 `{lat, lon}`처럼 검증한다. 무제한 `any`를 저장 스키마로 승인하지 않는다.

### 4. lifecycle

- 입력 형식이 유효하지 않거나 값이 실제로 바뀌지 않았다면 CorrectionRecord를 만들지 않는다.
- 유효한 사용자 수정은 downstream Evidence 재조립/Job보다 먼저 append-only로 기록한다.
- 이후 재조립이나 실행이 실패해도 CorrectionRecord를 삭제하지 않는다.
- `selection_rev`는 수정 횟수가 아니라 수정이 발생한 후보 선택 context다.

### 5. situation correction

사용자가 `다른 상황`을 선택하고 사건 의미를 바꾸면 `kind=SITUATION_CHANGE`를 사용한다. 단순 `잘 모르겠어요`는 값 correction이 아니라 case workflow state이므로 CorrectionRecord를 만들지 않는다.

## case Owner 반영 요청

`contract-correction-record.md`를 `correction-record/v1.1`로 개정하면서 다음을 반영한다.

1. `SITUATION_CHANGE` 추가
2. semantic `target_field` 값 공간 또는 target별 discriminated union
3. `supersedes_ref` 추가와 chain-head 현재값 규칙
4. target별 값 타입 검증
5. 유효하지 않은 입력/무변경 입력에는 미생성
6. 유효 correction 이후 downstream 실패 시 기록 보존

이 여섯 조건이 반영되면 evidence Consumer 관점에서 다시 정책 결정을 할 필요 없이 정합 확인만 수행하면 된다.
