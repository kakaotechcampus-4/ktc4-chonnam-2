# web 값 상태 표시 규칙

**Owner:** 신유민 (`web`) — web 단독 결정이며 CALL 안건이 아니다
**작성:** 2026-09-07 · **레포 반영:** 2026-09-10 (이슈 [#26](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/26) B-5) · **갱신:** 2026-09-10 (Mock Pack v3 3차 검수, 이슈 [#31](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/31))
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
6. **`evidence.review_needed`를 제출 게이트로 쓰지 않는다. 화면 분기의 기준은 언제나 `info_state`다.**
   *2026-09-10 갱신:* 원래 근거였던 「`info_state=INFO_NEEDS_REVIEW`인데 `review_needed=false`인 조합이 정상적으로 생긴다(happy_001)」는 **해소됐다** — 계약 B절 §7의 OR 공식이 `info_state==INFO_NEEDS_REVIEW` 경로까지 포함하도록 개정됐고(이슈 #26 B-web-6), happy_001의 `review_needed`도 `true`로 정정됐다. 그래서 이 값을 **요약 표시**로 쓰는 것은 이제 가능하다.
   그래도 **제출 게이트로는 쓰지 않는다.** ① 게이트는 세 gate(`requirements_evidence`·`requirements_package`·`user_reviewed`)가 소유한다(규칙 5). ② 개정된 공식도 `report_type_display`는 빼고 집계한다(그 display에 `info_state`가 없다 → §5 ①) — 「검토 필요한 게 하나라도 있는가」의 답이 그 필드에서는 여전히 새어 나간다. ③ `needs_review`와 `info_state`가 독립 필드라는 원칙은 그대로다.

## 4. 적용 대상 — 여섯 display 중 셋만 규칙 적용이 가능하다

| display | 가진 필드 | 이 규칙 적용 |
| --- | --- | --- |
| `plate_display` · `event_time_display` · `location_display` | `value` · `info_state` · `source_label_key` · `needs_review` | **가능.** §2·§3 그대로 |
| `case_type_display` · `violation_display` | `code` · `label` · `needs_review` · **`info_state` · `source_label_key`**(2026-09-10 추가) | **가능.** §2·§3 그대로. 단 아래 「필드 부재」 주의 |
| `report_type_display` | `code` · `label` · `needs_review` | **불가.** `info_state`가 없다 → §5 ① |

> **2026-09-10 갱신.** `case_type_display`·`violation_display`에 `info_state`·`source_label_key`가 추가됐다(계약 B절 §6 스키마 · `docs/modules/case/decisions/generic-warn-package-and-situation-response.md` 2·3). `visual_event_type.value=null`이면 `INFO_UNKNOWN`, generic 신고문처럼 AI가 만든 값이면 `INFO_AI_ESTIMATED`로, 앞의 세 display와 **같은 파생 규칙**을 쓴다 — web이 새로 분기할 것은 없다.
>
> **필드 부재 처리.** Mock Pack v3 기준 두 필드는 `scenario_unknown_abstain_partial_001`에만 실려 있고 나머지 시나리오에는 키 자체가 없다(이슈 [#31](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/31) W-3으로 백필 요청). 백필 전까지 web은 **필드가 없으면 배지를 붙이지 않는다** — 없는 상태를 `INFO_SOURCE_VERIFIED`로 간주하지 않고, `null`이나 임의 기본값을 만들어 넣지도 않는다. 백필이 끝나면 happy path의 `violation_display`(AI 생성 위반 문장)와 `case_type_display`(`VisualEvidence` 추론값)에도 「AI 추정」 배지가 붙게 된다 — 이 문서 기준으로는 그게 맞는 화면이다.

앞의 셋은 **미확정 상태가 정상 경로**다. 번호판은 `readout`이 `abstained=true`로 보류할 수 있고(`contract-plate-overlay-readout.md` §11-1), 시각은 파일명·metadata 계산값이 `INFO_NEEDS_REVIEW`로 내려오고(계약 B절 §7-(2) · `contract-time-resolution.md` §4), 위치는 `address`가 없는 동안 대표값이 `user_hint`다. 예외 화면이 아니라 기본 화면에서 이 규칙이 작동해야 한다.

## 5. 미결 — 계약 요청 (이슈 #26)

- **① ~~사건유형·신고유형·위반표현~~ → `report_type_display` 1건만 남았다.** (2026-09-10 갱신) 세 display에 `info_state`를 추가해 달라는 요청 중 **`case_type_display`·`violation_display` 2건은 반영됐다**(위 §4). 남은 것은 `report_type_display`뿐이고, 보류 근거도 확인했다 — `safety_report_type`의 4→2 mapping registry(evidence 소유)가 없어서 `source_label_key`를 정할 수 없다(`CONTRACT_CONFLICTS.md` 항목 4). **잠정(이 필드에 한해 유지):** 배지를 붙이지 않고 값 옆에 「수정」 경로만 둔다(`product-spec.md` §7의 「추천된 신고 유형도 사용자가 수정할 수 있어야 한다」). registry가 나오면 다른 두 display와 같은 파생 규칙으로 채워진다.
  - 다만 `report_type_display`는 **`package.unconfirmed_fields`에는 `safety_report_type`으로 이미 올라가 있다**(u001 rev4). 즉 같은 필드가 신고자료 화면에서는 「미확정」인데 evidence 화면에서는 아무 표시가 없다 → ②와 같은 건이다.
- **② `package.report_fields`에 필드별 상태가 없다.** `{필드명: 문자열}` 형태라서 신고자료 화면만 보면 무엇이 미확정인지 알 수 없다 — 규칙 5를 지킬 근거가 화면에 없다. **잠정:** `package.report_fields`는 **복사용 텍스트로만** 쓰고, 배지·출처는 같은 `CaseView`(같은 `case_rev`) 안의 `evidence.*_display`를 기준으로 붙인다. 두 값이 다르면 **확정 표시를 하지 않고 확인 필요로 취급한다** — 화면을 막는 쪽이 아니라 불확실을 드러내는 쪽으로 실패한다.
  - **(2026-09-10 갱신) `package.unconfirmed_fields: string[]`가 신설됐지만 이 잠정을 닫지 못한다.** 이름만 나열하는 배열이라 상태 종류(「알 수 없음」/「AI 추정」/「확인 필요」)를 구분하지 못하고, 무엇보다 두 면이 **양방향으로** 어긋난다 — u001 rev4에서 `location`(`INFO_UNKNOWN`)과 `violation_expression`(`INFO_AI_ESTIMATED`)은 배열에 없고, 반대로 `safety_report_type`은 배열에 있는데 evidence 쪽에 상태 필드가 없다. 즉 위 잠정 규칙(두 면 대조)이 **비교할 대상 자체가 없는** 경우가 생긴다.
  - **요청(이슈 [#31](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/31) A-2):** 여섯 `*_display`와 **같은 `info_state` 5종 + `source_label_key`** 를 필드 단위로. 새 상태 enum은 필요 없다. `report_fields`(복사용 평면 map)는 그대로 두고 `report_field_states` 병렬 map을 얹는 형태를 권했다. 함께 요청한 것 2건 — `report_fields` 키와 여섯 display 이름의 **대응표**, `unconfirmed_fields`의 **파생 규칙**(필드별 상태가 들어오면 `info_state ∈ {AI_ESTIMATED, NEEDS_REVIEW, UNKNOWN}`의 파생값으로 정의하고 두 원천을 독립으로 두지 않는다).

## 6. 목데이터 대조 (Mock Pack v3 3차 기준 · 2026-09-10 갱신)

| fixture | 상태 | 이 문서에서 검증되는 것 |
| --- | --- | --- |
| `scenario_happy_001` rev3·rev4 | `location_display`: `value`=사용자 힌트 문장 · `INFO_NEEDS_REVIEW` · `source_label_key=location.source.user_hint` · `coord`=관측 GPS · `review_needed=true`(2026-09-10 정정, 이슈 #26 B-web-6) · `package.report_fields.location`에 같은 문장 | 규칙 1·4·5·6. **`stage=READY`·`user_reviewed=true`에서도 미확정 값이 남는다** |
| `scenario_plate_reread_001` rev3 | `plate_display`: `value=null` · `INFO_UNKNOWN`, 재판독 job PENDING | 규칙 3(빈 칸 금지) · `INFO_UNKNOWN`의 입력 경로 표시 |
| `scenario_unknown_abstain_partial_001` rev3 | ~~`evidence=null` + `blocking=true` notice~~ → **v3에서 재구성**: `evidence` 채워짐, `case_type_display.info_state=INFO_UNKNOWN`, `violation_display.info_state=INFO_AI_ESTIMATED`, notice는 `blocking=false`로 완화 | §4의 두 display 규칙 · **`INFO_AI_ESTIMATED` 실화면 검증** |
| `scenario_unknown_abstain_partial_001` rev4 | `stage=READY` + `package.unconfirmed_fields=["safety_report_type","occurred_at"]`, `report_fields.location=null`·`violation_expression`=generic 문장 | 규칙 5 · §5②의 어긋남 4건이 실제로 관찰되는 스냅샷 |
| — | ~~`INFO_AI_ESTIMATED` fixture 없음~~ → **해소(2026-09-10, v3)**: u001 `violation_display`가 채웠다. `04_mock_validation_report.md` §1 갭 목록에는 아직 「미커버」로 남아 있다(문서만 stale, 이슈 #31 W-11) | **5종 전부 목데이터로 화면 검증 가능.** `scenario_blocked_001`은 `readiness=BLOCK` 경로용으로만 대기 |
