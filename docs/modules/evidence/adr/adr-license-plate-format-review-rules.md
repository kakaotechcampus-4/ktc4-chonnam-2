# ADR-EVIDENCE-006: 번호판 형식 규칙은 hard reject가 아니라 사용자 검토 신호로 사용한다

> 상태: **ACCEPTED — IMPLEMENTED (문자열 규칙)** · readout partial/layout 신호 연계는 후속(§7)
>
> 결정일: `2026-09-19` · 구현: `2026-11-01` (#487)
>
> Decider / Owner: 김준영 (`evidence`)
>
> 적용 범위: `PlateReadout` 관찰값을 `EvidenceRecord.vehicle_number`로 승격할 때의 형식 consistency check, `needs_review`, 사용자 수정 경로
>
> 근거: PR #80 · PR #88 · [대한민국 자동차 등록번호판 형식 및 분류기호 조사](../research/%EB%8C%80%ED%95%9C%EB%AF%BC%EA%B5%AD%20%EC%9E%90%EB%8F%99%EC%B0%A8%20%EB%93%B1%EB%A1%9D%EB%B2%88%ED%98%B8%ED%8C%90%20%ED%98%95%EC%8B%9D%20%EB%B0%8F%20%EB%B6%84%EB%A5%98%EA%B8%B0%ED%98%B8%20%EC%A1%B0%EC%82%AC.md) · [core-user-flow.md](../../../product/core-user-flow.md) §3-1·§12·§19·§22 · [EvidenceRecord 계약](../../../architecture/contracts/contract-evidence-record-needs.md)

## 1. 배경

PR #80의 OCR baseline에서 황색 2줄 번호판의 아랫줄 `바5215`만 5/5 프레임에서 고신뢰로 일치하는 사례가 확인됐다. 현재 readout 합의 규칙만 보면 이 값은 정상 관찰값처럼 통과할 수 있지만, 전체 등록번호를 모두 읽었다고 보기는 어렵다.

PR #88의 공식 근거 조사에서는 대한민국 번호판이 단일 정규식 하나로 닫히지 않는다는 점도 확인됐다. 차종·용도·관할기호·번호체계 세대·이륜차 등 여러 profile이 존재하고, `바` 자체는 자동차운수사업용으로 허용되는 정상 기호다.

따라서 `바5215` 같은 문자열을 단순히 “INVALID”로 버리면 부분 관찰과 합법적 예외를 함께 잃는다.

또한 `core-user-flow.md` §12는 **형식이 어긋나도 저장을 막지 않고 경고만 하며 최종 확인은 사용자에게 맡긴다**고 이미 확정했다.

## 2. 결정

### 2.1 Readout은 관찰값을 보존한다

`readout`은 OCR이 실제로 관찰한 문자열을 가능한 한 그대로 `PlateReadout`에 남긴다.

readout이 제공할 수 있는 것은 OCR/vision 관찰 신호다.

- 문자열과 confidence
- multi-frame agreement
- bbox / text-region / layout 정보
- 일부 영역만 검출됐을 가능성
- 해상도·프레임 불일치 등 abstain 근거

readout은 대한민국 번호판의 법적·제품적 유효성을 최종 판정하지 않는다.

### 2.2 Evidence가 형식 consistency check를 수행한다

`evidence`는 PR #88의 공식 근거를 바탕으로 **관찰 문자열이 알려진 번호판 형식과 얼마나 일관적인지** deterministic rule로 검사한다.

이 검사는 다음 목적으로만 사용한다.

- 명백한 용도문자 집합 위반 탐지
- 알려진 차종 분류기호 범위와의 불일치 탐지
- 완전한 번호판 profile로 설명하기 어려운 부분 문자열 탐지
- readout의 partial/layout 신호와 문자열 규칙을 함께 사용한 사용자 검토 필요 판정

이 검사를 “법적으로 유효한 번호판인가”라는 최종 `VALID/INVALID` 판정으로 사용하지 않는다.

### 2.3 값이 있으면 우선 보존하고, 의심스러우면 `needs_review=true`

readout에 usable한 문자열이 존재하지만 형식 consistency를 충분히 확인할 수 없거나 partial 가능성이 있으면:

- `EvidenceRecord.vehicle_number.value`에는 관찰값을 보존한다.
- `EvidenceValue.needs_review=true`로 사용자 확인 필요 상태를 남긴다.
- `case`는 이를 `CaseView`의 `INFO_NEEDS_REVIEW`로 projection한다.
- `web`은 값을 숨기거나 자체 판정하지 않고, 번호판 이미지·경고·수정 UI를 제공한다.

예:

```text
readout: "바5215"
        ↓
evidence:
  vehicle_number.value = "바5215"
  needs_review = true
        ↓
case/web:
  "번호판 일부만 인식되었을 수 있습니다. 영상과 비교해 확인해주세요."
```

### 2.4 값이 없는 경우와 의심스러운 값이 있는 경우를 구분한다

- **값이 있음 + 의심스러움**: 값 보존 + `needs_review=true`
- **실질적인 문자열이 없음 / readout abstain**: `vehicle_number` 부재 + 필요 시 `EvidenceNeeds.PLATE_REREAD`

`needs_review`와 `PLATE_REREAD`는 같은 상태가 아니다.

- `needs_review`: 현재 값의 신뢰/사용자 확인 상태
- `PLATE_REREAD`: 시스템이 추가 판독을 시도할 가치가 있을 때의 보강 행동

재판독 중이거나 재판독이 가능하더라도 현재 관찰값을 사용자에게 숨길 이유는 없다.

### 2.5 사용자 수정은 다시 형식 때문에 막지 않는다

사용자가 실제 영상을 보고 번호판을 수정하면 기존 계약대로:

- `user_corrected=true`
- `needs_review=false`

로 새 `EvidenceRecord`를 만든다.

형식 rule은 사용자 확인값을 다시 hard reject하거나 동일 항목을 재확인시키는 근거로 사용하지 않는다. 필요하면 UI에 non-blocking 참고 경고를 둘 수 있으나 workflow 상태는 사용자 확인을 우선한다.

## 3. PR #80과의 연결

PR #80이 제기한 질문은 “윗줄을 못 읽었는데 `status=OK`가 되는 것을 readout에서 막을지 evidence에서 막을지”였다.

이 ADR은 그 질문을 다음처럼 분해한다.

1. **Readout**: `바5215`라는 관찰을 버리지 않는다. 대신 partial/layout 등 관찰 신호를 제공한다.
2. **Evidence**: 관찰값 + 공식 번호판 rule을 바탕으로 “전체 번호판으로 확정해도 되는지”를 판단한다.
3. **Case**: evidence가 준 `needs_review`를 사용자 상태로 projection한다.
4. **Web**: 값을 보여주고 사용자가 확인·수정하게 한다.

따라서 PR #80의 사례는 **readout hard-abstain만으로 해결하지 않고 Evidence review rule의 회귀 테스트 케이스로 보존**한다.

## 4. 후속 코드 구현 — 이 PR에서는 하지 않는다

> **구현됨 (2026-11-01, #487).** 아래 요구사항의 구현 결과와 남은 범위는 §7에 있다.

이 ADR은 정책 방향만 확정한다. **실제 rule 값과 validator 구현은 후속 구현 PR에서 진행한다.**

후속 구현은 최소 다음을 포함해야 한다.

1. PR #88에서 확인한 차종 분류기호 범위, 용도별 한글 기호, 관할기호, 번호체계 세대 정보를 **versioned rule 데이터**로 코드화한다.
2. 규칙을 여러 함수/정규식에 하드코딩하지 않고 단일 rule source에서 읽도록 한다.
3. Evidence의 번호판 승격 경로에 deterministic consistency check를 추가한다.
4. 결과는 hard reject가 아니라 `needs_review` 판정에 연결한다.
5. PR #80의 `바5215` 사례를 회귀 테스트에 넣어 **값이 보존되고 `needs_review=true`가 되는지** 확인한다.
6. 허용 문자 밖 OCR 오인식, 정상 7자리/8자리, 사업용·대여용, 지역표시 계열, 사용자 직접 수정 사례를 테스트한다.
7. 지원하지 않거나 아직 rule profile이 확정되지 않은 구형·외교·임시·이륜차 형식은 임의로 `INVALID` 처리하지 않고 `undetermined/review` 경로로 둔다.
8. 고시가 바뀌면 기존 rule revision을 덮어쓰지 않고 새 revision으로 갱신할 수 있게 한다. 제2025-676호가 2026-11-28 시행되면 영향 범위를 다시 대조한다.

구체 enum 이름, 파일 경로, regex 구조는 구현 PR에서 현재 Evidence 코드 구조를 보고 정한다. 이 ADR은 **공식 근거를 코드의 rule 값으로 옮겨야 한다는 요구와 판정 semantics**를 고정한다.

## 5. 하지 않는 것

이 결정은 다음을 의미하지 않는다.

- 하나의 regex로 대한민국의 모든 번호판을 완전 판정한다.
- 형식 불일치만으로 OCR 관찰값을 삭제한다.
- Evidence가 이미지 픽셀을 다시 분석한다.
- Readout이 법적 번호판 유효성을 판정한다.
- `needs_review=true`이면 무조건 `PLATE_REREAD`를 발주한다.
- 사용자 확인값을 rule 위반 때문에 제출 흐름에서 차단한다.

## 6. 한 줄 결정

> Readout은 관찰한 번호판 문자열과 vision 신호를 보존하고, Evidence는 PR #88의 공식 번호판 근거를 향후 versioned rule 값으로 구현해 형식 일관성을 검사하되 이를 hard `VALID/INVALID` gate로 사용하지 않는다. 값이 있으나 완전성이나 형식이 의심되면 값을 유지한 채 `needs_review=true`로 CaseView까지 전달하고 사용자가 영상과 비교해 수정하도록 하며, 값 자체가 없을 때의 `PLATE_REREAD`와는 별도 상태로 다룬다. PR #80의 `바5215` 부분 판독 사례는 이 정책의 대표 회귀 테스트로 사용한다.

## 7. 구현 상태 (2026-11-01, #487)

PR #91 실험의 `classify()`·`notes()`를 제품 코드로 옮겼다. 실험 파일은 import하지 않는다.

| 위치 | 내용 |
| --- | --- |
| `src/daesingo/evidence/plate_format_rules_kr_v1.json` | rule 값. revision `plate-format/kr-v1`, 기준 고시 제2025-121호. 기호 집합·분류기호 대역·profile 8종마다 `provenance`(`OFFICIAL` / `OBSERVED_OUTSIDE_NOTICE_SCOPE`)와 근거를 단다 |
| `src/daesingo/evidence/plate_format.py` | 위 파일만 해석하는 evaluator. `assess_plate_format(value)` → `matched_profile` · `reason_codes` · `review_required` · `rule_ref`. `VALID/INVALID`는 없다 |
| `assembly.py` `_independent_facts()` | `PlateReadout`이 `status=OK`·`abstained=false`로 준 값만 검사한다. 값은 그대로 두고 `needs_review`에만 반영한다 |
| `policy.py` | `provenance.policy_ref`를 `policy/evidence-assembly-v2`로 올렸다. v2가 적용하는 rule revision은 `PLATE_FORMAT_RULE_REF`(`plate-format/kr-v1`)이고 테스트로 묶었다. 계약 변경은 없다 |

§4 요구사항별 결과:

1. **versioned rule 데이터** — 위 JSON. 고시가 바뀌면 `plate_format_rules_kr_v2.json`을 새로 두고 `supersedes_rule_ref`를 채운다. v1은 고치지 않는다.
2. **단일 rule source** — 기호·대역·profile 값은 JSON 한 곳에만 있다. 판정 순서(관할 → 용도 → 분류기호 → 일련번호)와 부분 문자열 진단만 코드에 있다.
3. **deterministic check** — 순수 함수다. 검사는 NFC 정규화 후 공백만 지운 사본으로 하고, 저장값은 바꾸지 않는다(`core-user-flow.md` §12 · web #513 · readout과 같다). PR #91 E-0은 사람 라벨 표기를 흡수하려고 `-`·`.`·`·`도 지웠지만 제품은 지우지 않는다. 그런 값은 review로 간다.
4. **`needs_review` 연결** — `plate.format.*`(구조가 설명되지 않음, 첫 실패 하나)나 `plate.consistency.*`(설명되지만 고시 밖 조합·관측 기반 profile·검사 불완전)가 하나라도 있으면 `needs_review=true`다. reason code는 wire에 싣지 않는다. CaseView는 기존대로 `INFO_NEEDS_REVIEW`만 받는다.
5. **`바5215` 회귀** — readout이 `OK`로 준 `바5215`는 값이 보존되고 `needs_review=true`, `plate.format.incomplete`다(`tests/evidence/test_plate_format_review.py`).
6. **대표 사례** — 정상 7·8자리, 사업용·대여용(`허/하/호`), 관할기호형, 허용 문자 밖 오인식, 사용자 수정을 테스트한다. PR #91 엔진과의 parity는 고정 fixture 45건으로 확인한다(`tests/evidence/fixtures/plate_format_parity_kr_v1.json`).
7. **미확정 profile** — 구형 1자리·군용·건설기계(관측 기반)는 인식하되 `legacy_scheme`·`outside_notice_scope`로, 이륜차(시·군·구 목록 없음)·외교(관측 0건)는 `plate.consistency.partial_coverage`로 review다. 거부하지 않는다. `partial_coverage`는 PR #91에 없던 제품 추가 코드다.
8. **revision 갱신** — 제2025-676호(2026-11-28 시행)는 rule 파일의 `basis.pending_notice`에 적어 두었다. 시행 후 대조는 하지 않았다.

사용자 수정값(`user_corrected=true`)은 형식 검사를 하지 않는다. 형식이 어긋나도 `validate_correction_append()`가 거부하지 않고 `needs_review=false`로 남는다(§2.5).

### 7.1 남은 것

- **readout의 부분 판독 보류와 §2.3·§2.4의 충돌은 그대로다.** readout은 `바5215` 같은 값에 이미 `PARTIAL_PLATE_READ`로 abstain한다(`readout/api.py` `is_full_plate()`). 그러면 §2.4와 ADR-EVIDENCE-008 §4.3에 따라 `vehicle_number`가 없고 `PLATE_REREAD`가 나간다. 이번 구현은 이 경로를 바꾸지 않았다. 따라서 실제 파이프라인에서 Evidence 규칙이 작동하는 곳은 readout이 `OK`로 넘긴 값이다. provider가 바뀌거나 readout guard를 통과한 값에 대한 2차 방어선이다. abstain된 관찰값도 보존할지는 PR #91 README §6-4의 선택지와 함께 `readout`·`evidence`·`case`가 정할 일이다.
- **partial/layout 신호 연계(PR #91 E-9)는 하지 않았다.** `best_frame.plate_bbox_xywh`가 2줄판에서 텍스트 한 줄만 감싸는 문제(PR #80 ⓑ)가 전제조건이다. 문자열 규칙만으로는 「관할기호만 누락」(`경기37바…` → `37바…`)을 잡지 못한다(PR #91 §4, 0.24%).
- **형식 통과는 정확성을 보장하지 않는다.** 자릿수·문자종이 보존된 오독은 원리상 검출할 수 없다(PR #91 §2-②).
- **reason code별 안내 문구는 없다.** 코드는 evaluator 결과에만 있고 계약 필드가 없다. 「일부만 인식되었을 수 있습니다」처럼 사유별로 안내하려면 wire 필드가 따로 필요하다.
- Web은 #513에서 저장을 막지 않는 경고로 바꿨다. web 정규식은 경고용이며 이 rule source와 같지 않다.
