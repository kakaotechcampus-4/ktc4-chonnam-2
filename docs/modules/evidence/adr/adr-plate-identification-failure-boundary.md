# ADR-EVIDENCE-008: 번호판 식별 실패와 실행 실패의 Requirement 경계 (#172 D · D-2 · D-3)

> 상태: **ACCEPTED**
>
> 결정일: `2026-09-29`
>
> Decider / Owner: 김준영 (`evidence` Owner · PM) — D · D-3. D-2(Readout 표현 경계)는 신유민(`readout`) 결정을 옮긴 것이다
>
> 동의: 유소연(`case`, D · D-3 필수 동의) · 의견: 정철원(`recording`)
>
> 적용 범위: 번호판 값 표현, `policy/requirement-rules-v4`의 번호판 두 rule(`evidence.vehicle_number.present` · `package.vehicle.plate_visible_in_report_video`)의 outcome 매핑
>
> 근거: 결정 카드 [#172](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/172)의 `[D] 결정` · `[D-2] 결정` · `[D-3] 결정` 댓글 · #146 9/25 Evidence/Product Owner 답변(번호판 식별 실패를 경고 있는 UNKNOWN으로 허용) · [`ADR-EVIDENCE-002`](adr-first-completion-owner-decisions.md) §5.4·§5.6 · [`ADR-EVIDENCE-005`](adr-event-context-rules-removal.md) §5.5·§5.7(I4)

## 1. 목적

「번호판을 읽지 못했다」는 사실이 네 가지 서로 다른 상황에서 같은 모양(값 없음)으로 나타난다. 이 ADR은 그 네 상황을 **값 표현 · Readout 표현 · Requirement outcome** 세 층에서 어떻게 구분할지 확정한다.

지키려는 것은 둘이다.

- #146이 정한 제품 방향 — 번호판 식별 실패 **자체는** 신고자료 blocker가 아니다. 부족한 정보임을 경고하면서 결과까지 준비한다.
- 그러면서도 **실행 실패가 정상적인 경고 결과로 위장되어 `READY`로 흘러가지 않게** 한다.

## 2. 배경

### 2.1 네 상황

| # | 실제 상황 |
| --- | --- |
| 1 | 번호판 영역은 보이나 문자 판독 실패 |
| 2 | 일부 문자만 판독 |
| 3 | 번호판 자체가 보이지 않음 |
| 4 | Readout 실행 실패 / 최종 영상 fact 미생산 |

### 2.2 이 결정 전의 규칙 (v4)

| rule | 조건 | outcome |
| --- | --- | --- |
| `evidence.vehicle_number.present` | 확정 차량번호 있음 / 없음 | `PASS` / `UNKNOWN` |
| `package.vehicle.plate_visible_in_report_video` | 최종 신고영상 관찰 `true` / `false` / 미관찰 | `PASS` / **`BLOCK`** / `UNKNOWN` |

v4는 1·2·3·4를 모두 「값 없음 → `UNKNOWN`」으로 합쳤고, 최종 영상에서 번호판이 안 보이는 것을 `BLOCK`으로 두었다. #146 방향과 맞지 않고, 실행 실패(4)와 판독 실패(1·2·3)를 Requirement 층에서 구분할 수 없었다.

## 3. 결정 상태

| ID | 항목 | 결정자 | 상태 |
| --- | --- | --- | --- |
| D | 번호판 값 표현 원칙 | 김준영 (+Case 동의) | **ACCEPTED** |
| D-2 | 네 상황의 Readout 표현 경계 | 신유민 (+정철원 조건) | **ACCEPTED** — readout 소유. 이 ADR은 옮겨 적기만 한다 |
| D-3 | 상황별 Requirement outcome | 김준영 (+Case 조건 반영) | **ACCEPTED** |

## 4. 결정

### 4.1 D — 값 표현

- 미확보 번호판은 **`null`/부재**로 보존한다. `"UNKNOWN"` 같은 sentinel 문자열을 차량번호로 만들지 않는다. 사용자용 「읽을 수 없음」은 표시 계층이 만든다.
- `IncidentClip` 판독 결과만으로 최종 `REPORT_VIDEO`의 번호판 가시성을 `PASS`/`BLOCK`으로 확정하지 않는다. 최종 영상 가시성은 **I4 관찰이 있을 때만** 확정한다.
- 번호판 식별 실패, I4 미관찰, Readout/I4 실행 실패는 **서로 다른 상태로 유지**한다. 같은 `WARN`으로 합치지 않는다.

### 4.2 D-2 — Readout 표현 (readout 결정, 참고)

| # | 상황 | Readout 표현 |
| --- | --- | --- |
| 1·3 | 글자를 전혀 못 읽음 / 번호판이 안 보임 | `PlateReadout` 존재, `status=UNKNOWN`, value `null`. 현재 판독은 둘을 구분하지 못해 「읽지 못함」 하나로 둔다 |
| 1·2 | 일부라도 읽음 | `PlateReadout` 존재, `NEEDS_REVIEW` + 사유 코드(`PARTIAL_PLATE_READ` 등) |
| 4a | Readout 실행 실패 | `ReadoutRun.outcome=FAILED`(`INFRA`), **`PlateReadout = None`** |
| 4b | I4 미실행 / 최종 영상 fact 없음 | 미관찰 `UNKNOWN`. 실패가 아니다 |
| — | `REPORT_VIDEO` 생성 실패 | Recording 경계(`REPORT_VIDEO_EXPORT_FAILED`). 4a와 따로 둔다 |

### 4.3 D-3 — Requirement outcome

| 상태 | Requirement |
| --- | --- |
| 차량번호 정상 확보 | `PASS` |
| 정상 판독 수행 후 번호판을 읽지 못함(1·3, `PlateReadout` 존재) | `WARN` — 값 `null`, Package blocker로 두지 않음 |
| 일부 판독 / `NEEDS_REVIEW`(1·2) | `WARN` — 검토·재판독 필요를 표시하되 blocker로 두지 않음 |
| I4가 최종 신고영상에서 번호판 식별 불가를 실제 관찰 | `WARN` — v4의 `BLOCK`을 supersede |
| I4 미실행 / 최종 영상 fact 없음(4b) | `UNKNOWN` |
| Readout 실행 실패로 `PlateReadout = None`(4a) | `UNKNOWN` — 식별 실패 `WARN`으로 치환하지 않는다. 실행 실패는 진행 상태·notice로 별도 노출 |
| `REPORT_VIDEO` 생성 실패 | Recording 경계로 유지 |

세 값의 뜻:

- **`WARN`** = 실제 판독·관찰을 수행했고 번호판 정보가 부족함을 **확인한** 경우
- **`UNKNOWN`** = 아직 판정할 수 없거나 판독 결과 자체가 없는 경우
- **실행 실패** = 위 둘과 별도로 진행 상태·notice에서 노출하는 failure 상태

`PlateReadout` 존재 여부로 1·2·3과 4a를 가르는 것은 Case 조건(#172 `[D-3] Case 의견`)이다. 부재까지 `WARN`으로 두면 4a가 1·3과 같은 `WARN` Package로 나가 case가 `READY`로 올린다 — 실행 실패가 정상 결과로 위장된다. 부재를 `UNKNOWN`으로 두면 FINAL이 `PASS`/`WARN`이 되지 않아 Package-ready와 저절로 구분되고, case는 새 gate를 만들지 않는다.

## 5. Requirement policy 반영 — `policy/requirement-rules-v5`

`requirement_rules_v4.json`은 수정하지 않고 새 revision `src/daesingo/evidence/requirement_rules_v5.json`을 발행한다(`supersedes_policy_ref: policy/requirement-rules-v4`). 바뀌는 rule은 둘이고 나머지 rule·rule 수(`EVIDENCE` 4 · `FINAL_PACKAGE` 무조건 12 + 조건부 1)는 v4 그대로다.

### 5.1 `evidence.vehicle_number.present`

| 조건 | 판별 입력 | v4 | v5 | `reason_code` |
| --- | --- | --- | --- | --- |
| `value_present` | `vehicle_number.value`가 비어 있지 않은 문자열 | `PASS` | `PASS` | `evidence.value_confirmed` |
| `readout_performed_value_absent` | 값 없음 + `provenance.input_refs`에 `plate_readout` ref 있음(= `PlateReadout` 존재) | `UNKNOWN` | **`WARN`** | `evidence.plate_unidentified` |
| `readout_absent` | 값 없음 + `plate_readout` ref 없음(= `PlateReadout = None`) | `UNKNOWN` | `UNKNOWN` | `evidence.plate_readout_missing` |

- 판별은 `EvidenceRecord`가 이미 싣는 계약 필드(`vehicle_number`, `provenance.input_refs`)만 쓴다. 새 입력 필드를 만들지 않는다. `assemble_evidence_record()`는 `PlateReadout`이 있으면 그 ref를 `input_refs`에 넣고, 없으면 넣지 않는다.
- 1·3(`status=UNKNOWN`)과 1·2(`NEEDS_REVIEW`)는 같은 `WARN`이다. 둘의 차이는 재판독 Need(`calculate_evidence_needs()` — `NEEDS_REVIEW`·abstain일 때만 `PLATE_REREAD`)와 표시 문구에서 드러나고, 이 rule은 가르지 않는다.
- 사용자가 번호판을 직접 입력하면 정정값이 `vehicle_number`에 들어와 `value_present`가 된다.

### 5.2 `package.vehicle.plate_visible_in_report_video`

| 관찰 fact | v4 | v5 | `reason_code` |
| --- | --- | --- | --- |
| `observed_true` | `PASS` | `PASS` | `readout.plate_visibility.confirmed` |
| `observed_false` | **`BLOCK`** | **`WARN`** | `readout.plate_visibility.not_visible` (v4의 `….failed`를 대체) |
| `not_observed` | `UNKNOWN` | `UNKNOWN` | `readout.plate_visibility.not_observed` |

- `observed_false`의 `reason_code`를 `failed`에서 `not_visible`로 바꾼다. 「관찰했고 안 보였다」는 실행 실패가 아니므로 `failed`라는 이름을 쓰지 않는다. 다른 두 관찰 rule(`package.time.*`)의 `reason_code`는 바꾸지 않는다.
- **Readout 실행 실패를 이 rule의 `observed_false`로 변환하지 않는다.** 실행이 실패했으면 관찰 fact가 없으므로 `not_observed → UNKNOWN`이다. `observed_false`는 I4가 최종 영상을 실제로 관찰한 결과만 가리킨다.
- `IncidentClip` 판독 결과를 이 fact로 승계하지 않는다(§4.1). I4 Producer는 아직 없다(ADR-005 §5.7).

### 5.3 활성 catalog 전환

활성 catalog 선택점은 `policy_catalog.py`의 `_ACTIVE_REQUIREMENT_CATALOG_FILE` 한 곳이며 `requirement_rules_v5.json`으로 바꾼다. 출력 `policy_ref`는 로드한 파일의 값(`policy/requirement-rules-v5`)이다.

## 6. 이 결정이 바꾸지 않는 것 · 후속

**번호판 없는 Package는 이 revision만으로 아직 발행되지 않는다.** 번호판 rule이 더 이상 blocker가 아니게 된 것까지가 이 ADR의 범위이고, Package 입력 쪽 gate 세 곳은 그대로다.

| gate | 현재 | 후속 |
| --- | --- | --- |
| `report_inputs.vehicle_number` | `string` 필수 (`contract-requirement-report-package.md`) | nullable 여부 · wire type — evidence 계약 개정 |
| `build_report_package()` | plate 부재면 `package.input.vehicle_number_missing` | 위 계약 개정과 함께 |
| 신고문 template 4종 · `render_required_inputs_by_template` | 차량번호 문장을 전제, 필수 입력에 `vehicle_number` → 번호판 없으면 `package.report.content_length = UNKNOWN` | 번호판 없는 문장 구성 — 새 template revision |

그래서 1·2·3 상태의 FINAL은 지금도 `package.report.content_length`가 `UNKNOWN`이라 Package가 나가지 않는다. 이 세 곳은 신고문 문구(제품 결정)와 계약 개정이 함께 필요해 이번 ADR에서 임의로 채우지 않는다. 반대로 번호판 값이 있는 상태에서 I4가 「안 보임」을 관찰한 경우는 이 revision만으로 `WARN` Package가 발행된다.

그 밖의 후속(이 ADR 범위 밖):

- `evidence.plate_abstained`(1·2) notice 계약 등재·발행 — case(#172 `[D-3]` Case 의견)
- `readout.plate_read_failed`(4a) 투영 — case가 #193으로 반영했다(`ERROR` · blocking · `RETRY_PLATE_READ`)
- 재판독 Need의 필수성·횟수 — `contract-evidence-record-needs.md`
- 최종 `REPORT_VIDEO` 관찰 Producer(I4) — readout 입력 계약 확장 후 case 배선(ADR-005 §5.7)
- 1과 3의 구분 — readout이 번호판 영역 검출을 갖기 전까지 「읽지 못함」 하나(D-2)

## 7. 영향을 받는 기존 결정

기존 ADR 본문은 고치지 않고, 해당 절에 이 ADR로 대체됐다는 표시만 단다.

| 문서 | 절 | 대체된 내용 |
| --- | --- | --- |
| ADR-002 | §5.4 `evidence.vehicle_number.present` 행 | 「없음 → `UNKNOWN`」 → `PlateReadout` 존재 여부로 `WARN`/`UNKNOWN` 분리 |
| ADR-002 | §5.6 `package.vehicle.plate_visible_in_report_video` 행 | `observed_false → BLOCK` → `WARN` |
| ADR-005 | §5.5 `plate_visible_in_report_video` 행 | 입력 key 유지는 그대로, outcome 매핑만 v5로 대체 |

## 8. 검증

`tests/evidence/test_plate_boundary_d3.py`가 §4.3 표의 각 행을 활성 catalog로 검증한다.

| 행 | 검증 |
| --- | --- |
| 정상 확보 | `PASS` |
| 판독 후 못 읽음(`PlateReadout` 존재, value null) | `WARN`, 값 `null`, 이 rule이 `BLOCK`/`UNKNOWN`을 만들지 않음 |
| `NEEDS_REVIEW` · abstain | `WARN` + `PLATE_REREAD` Need 유지 |
| I4 `observed_false` | `WARN`, 번호판 값이 있으면 `WARN` Package 발행 |
| I4 미관찰 | `UNKNOWN` |
| 실행 실패(`PlateReadout = None`) | `UNKNOWN`, FINAL이 `PASS`/`WARN`이 아니어서 Package 미발행 — case 쪽 notice는 `tests/case/test_plate_read_failure_projection.py` |
| v4 보존 | `requirement_rules_v4.json`이 여전히 `observed_false → BLOCK`을 담고 있음 |
