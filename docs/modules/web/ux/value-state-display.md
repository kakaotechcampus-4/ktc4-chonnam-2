# web 값 상태 표시 규칙

**Owner:** 신유민 (`web`) — web 단독 결정이며 CALL 안건이 아니다
**작성:** 2026-09-07 · **레포 반영:** 2026-09-10 (이슈 [#26](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/26) B-5)
**근거:** `product/product-spec.md` §7 · `product/core-user-flow.md` §3-1 · `architecture/contracts/contract-job-record-case-view.md` B절 §6·§7·§10-12 · `architecture/contracts/adr/adr-data-contract-call-closure-2026-09-07.md` §4.1(B01)
**적용 화면:** Evidence Review · 최종 신고자료(handoff)

## 1. 왜 이 문서가 필요한가

B01 종결(2026-09-07)에서 `location_display.value`의 대표값 우선순위를 `address → place_name → user_hint`로 정했다(계약 B절 §7-(3) · ADR §4.1). `user_hint`는 **분석 전에 사용자가 말한 미확인 단서**이고, 그것이 값 슬롯에 담긴다.

계약이 제공하는 것은 상태를 알려주는 필드(`info_state` · `source_label_key` · `needs_review`)까지다. **그 값이 확정으로 보이지 않게 만드는 책임은 `web`에 있다.** 이 규칙이 없으면 사용자가 미확정 위치를 확정으로 믿고 신고한다 — 성능 문제가 아니라 잘못된 신고 문제다.

## 2. 표시 규칙 — `info_state` 5종

`web`은 **`info_state`로만 분기한다.** `needs_review`를 직접 해석하지 않는다(계약 B절 §7-(4)·§10-12). 화면 문구는 `core-user-flow.md` §3-1의 이름을 그대로 쓰고 유사 상태 표현을 새로 만들지 않는다.

| `info_state` | 제품 상태 이름 (§3-1) | 표시 |
| --- | --- | --- |
| `INFO_USER_CONFIRMED` | 사용자 확인됨 | 확정 표시. 사용자가 확인했음을 함께 보여준다 |
| `INFO_SOURCE_VERIFIED` | 출처 확인됨 | 확정 표시. 출처 라벨을 함께 보여준다 |
| `INFO_AI_ESTIMATED` | AI 추정 | **값 단독 렌더 금지.** 확인 필요 배지 + 출처 라벨 필수 |
| `INFO_NEEDS_REVIEW` | 확인 필요 | **값 단독 렌더 금지.** 확인 필요 배지 + 출처 라벨 필수 |
| `INFO_UNKNOWN` | 알 수 없음 | 값 없음. 빈 칸으로 두지 않고 「알 수 없음」과 입력 경로를 보여준다 |

## 3. 지켜야 하는 것

1. **`INFO_AI_ESTIMATED`·`INFO_NEEDS_REVIEW` 값은 확정값과 시각적으로 구분한다.** 같은 서체·같은 위치에 배지 없이 놓지 않는다.
2. **출처를 값과 같은 화면에 둔다.** `source_label_key`로 문구를 고르고 `source.kind` 문자열을 직접 해석하지 않는다. `source_label_key`가 `null`이면 fallback 문구를 쓴다.
3. **`INFO_UNKNOWN`은 빈 칸이 아니다.** 위치라면 `hints.location` · `coord` · `search_keyword`를 단서로 함께 보여준다. 사용자가 무엇을 근거로 채워야 하는지 알 수 있어야 한다.
   *근거:* `product-spec.md` §7이 「값을 만들어내지 않고 출처와 `확인 필요`/UNKNOWN **상태를 보여준다**」로 `UNKNOWN`을 표시 대상으로 명시한다. 빈 칸은 상태를 보여주는 것도, 단서를 유지하는 것도 아니다.
4. **값을 합치거나 새로 만들지 않는다.** `coord`는 원값으로 내려오고 포맷만 `web`이 한다. 여러 위치 값을 이어 붙여 새 문자열을 만들지 않는다(계약 B절 §7-(3)).
5. **handoff 화면에서 미확정 값을 「준비됨」으로 묶지 않는다.** 신고요건 판정은 `requirements_evidence` / `requirements_package`가 소유하고, 세 gate(`EVIDENCE_SUFFICIENT` · `PACKAGE_READY` · `USER_REVIEWED`)는 각각 구분해 표시한다.
   *근거:* `management/ownership.md` §7-④의 통합 기준 「세 상태가 `CaseView`에 구분되어 표시되는가」 · 계약 B절 §7 「세 gate의 출처」·§10-11(하나의 readiness로 합치지 않는다). 실제 제출은 사용자가 직접 하므로(`product-spec.md` §7) 무엇이 미확정인지가 마지막 화면까지 남아야 한다.
6. **`evidence.review_needed`를 제출 게이트나 「검토 필요」 요약으로 쓰지 않는다.** 이 값은 여섯 `*_display.needs_review`의 OR이고(계약 B절 §7, 2026-09-09 확정), `needs_review`와 `info_state`는 독립 필드다. 실제로 `info_state=INFO_NEEDS_REVIEW`인데 `review_needed=false`인 조합이 정상적으로 생긴다(§6 happy_001). 화면 분기의 기준은 언제나 `info_state`다.

## 4. 적용 대상 — 여섯 display 중 셋만 규칙 적용이 가능하다

| display | 가진 필드 | 이 규칙 적용 |
| --- | --- | --- |
| `plate_display` · `event_time_display` · `location_display` | `value` · `info_state` · `source_label_key` · `needs_review` | **가능.** §2·§3 그대로 |
| `case_type_display` · `report_type_display` · `violation_display` | `code` · `label` · `needs_review` | **불가.** `info_state`가 없다 → §5 ① |

앞의 셋은 **미확정 상태가 정상 경로**다. 번호판은 `readout`이 `abstained=true`로 보류할 수 있고(`contract-plate-overlay-readout.md` §11-1), 시각은 파일명·metadata 계산값이 `INFO_NEEDS_REVIEW`로 내려오고(계약 B절 §7-(2) · `contract-time-resolution.md` §4), 위치는 `address`가 없는 동안 대표값이 `user_hint`다. 예외 화면이 아니라 기본 화면에서 이 규칙이 작동해야 한다.

## 5. 미결 — 계약 요청 (이슈 #26)

- **① 사건유형·신고유형·위반표현의 「확인 필요」를 표시할 근거가 없다.** 세 display는 `needs_review`만 갖는데 계약 §10-12는 「web은 `info_state`로만 분기하고 `needs_review`를 직접 해석하지 않는다」다. 지금 상태로는 이 셋에 배지를 붙이는 것이 계약 위반이거나, 붙이지 않아 §3-1이 요구하는 상태 표시가 빠진다. **잠정:** 배지를 붙이지 않고 값 옆에 「수정」 경로만 둔다(`product-spec.md` §7의 「추천된 신고 유형도 사용자가 수정할 수 있어야 한다」). 세 display에 `info_state`를 추가하거나 §10-12에 예외를 두는 결정을 case Owner에게 요청했다.
- **② `package.report_fields`에 필드별 상태가 없다.** `{필드명: 문자열}` 형태라서 신고자료 화면만 보면 무엇이 미확정인지 알 수 없다 — 규칙 5를 지킬 근거가 화면에 없다. **잠정:** `package.report_fields`는 **복사용 텍스트로만** 쓰고, 배지·출처는 같은 `CaseView`(같은 `case_rev`) 안의 `evidence.*_display`를 기준으로 붙인다. 두 값이 다르면 **확정 표시를 하지 않고 확인 필요로 취급한다** — 화면을 막는 쪽이 아니라 불확실을 드러내는 쪽으로 실패한다. 계약에 필드별 상태(또는 `unconfirmed_fields[]`)를 싣거나 `package.warnings[]`에 미확정 경고를 넣어달라고 요청했다.

## 6. 목데이터 대조 (Mock Pack v2 2차 기준)

| fixture | 상태 | 이 문서에서 검증되는 것 |
| --- | --- | --- |
| `scenario_happy_001` rev3·rev4 | `location_display`: `value`=사용자 힌트 문장 · `INFO_NEEDS_REVIEW` · `source_label_key=location.source.user_hint` · `coord`=관측 GPS · `review_needed=false` · `package.report_fields.location`에 같은 문장 | 규칙 1·4·5·6. **`stage=READY`·`user_reviewed=true`에서도 미확정 값이 남는다** |
| `scenario_plate_reread_001` rev3 | `plate_display`: `value=null` · `INFO_UNKNOWN`, 재판독 job PENDING | 규칙 3(빈 칸 금지) · `INFO_UNKNOWN`의 입력 경로 표시 |
| `scenario_unknown_abstain_partial_001` rev3 | `evidence=null` + `blocking=true` notice | evidence 화면 자체를 못 그리는 경로 — 이 문서 범위 밖(notice 표시) |
| — | `INFO_AI_ESTIMATED` fixture 없음 (`04_mock_validation_report.md` §1 커버리지 갭) | **5종 중 1종은 목데이터로 화면 검증 불가.** `scenario_blocked_001` 추가 대기 |
