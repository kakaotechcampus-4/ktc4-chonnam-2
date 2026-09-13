# web 값 상태 표시 규칙

**Owner:** 신유민 (`web`) — web 단독 결정이며 CALL 안건이 아니다
**작성:** 2026-09-07 · **레포 반영:** 2026-09-10 (이슈 [#26](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/26) B-5) · **갱신:** 2026-09-10 (Mock Pack v3 3차, 이슈 [#31](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/31)) · **2026-09-11 (Mock Pack v4 · `case-view/v1.3` 기준 전면 갱신, 이슈 [#39](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/39) A-3)** · **2026-09-14 (§5-2 작업 상태 계열 — PR [#46](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/46) 유소연 답변 · Mock Pack v5 반영)**
**근거:** `product/product-spec.md` §7 · `product/core-user-flow.md` §3-1 · `architecture/contracts/contract-job-record-case-view.md` B절 §6·§7·§10-12 · `architecture/contracts/adr/adr-data-contract-call-closure-2026-09-07.md` §4.1(B01)
**대조 기준:** `develop` @ `d9d8e2b` (Mock Pack v4 · `case-view/v1.3`)
**적용 화면:** Evidence Review · 최종 신고자료(handoff)

> **2026-09-11 갱신 요약.** `case-view/v1.3`에서 §5의 미결 2건이 **둘 다 닫혔다** — `report_type_display`에 `info_state`/`source_label_key`가 추가됐고(`CONTRACT_CONFLICTS.md` 항목 4 종결), `package.report_field_states`가 신설되며 대응표·`unconfirmed_fields` 파생 규칙까지 명문화됐다(항목 10 종결). 이 문서의 잠정 2건을 철회하고 §3~§6을 v4 실측값으로 다시 썼다. §5는 아직 닫히지 않은 **작업 상태(CANCELLED) 계열 3건**으로 교체했다.

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

### 2-1. `needs_review`(필드 단위)와 `review_needed`(object 단위)는 다른 값이다

이름이 비슷해 섞어 쓰기 쉬운데 **축이 다르다.** 화면을 만들 때 반드시 구분한다.

| | 어디에 | 무엇을 뜻하나 |
| --- | --- | --- |
| `*_display.needs_review` | 여섯 display 각각 | 그 값 자체를 다시 검토해야 하는가 |
| `evidence.review_needed` | `evidence` object 1개 | 「검토 필요한 게 하나라도 있는가」의 **집계**. 여섯 `needs_review` OR + 여섯 `info_state==INFO_NEEDS_REVIEW` OR (계약 B절 §7) |

**필드 단위로 `needs_review=false`인데 `info_state=INFO_NEEDS_REVIEW`인 조합은 정상이며 v4에도 그대로 있다** — `scenario_happy_001` rev3·rev4의 `location_display`가 그 예다(`needs_review=false` · `info_state=INFO_NEEDS_REVIEW`). §7-(3)의 「대표값이 `user_hint`면 `INFO_NEEDS_REVIEW`」가 `needs_review`를 거치지 않고 바로 `info_state`를 정하는 경로이기 때문이다. 2026-09-10에 바뀐 것은 **object-level 집계식뿐**이고(이제 이 조합도 `review_needed=true`로 잡는다), 필드 단위 조합 자체는 해소된 적이 없다.

`evidence` 쪽 원천도 같은 이야기다 — `EvidenceRecord.location`은 `user_corrected=true` · `needs_review=false`인데 `CaseView`는 대표값이 사용자 hint이므로 `location_display.info_state=INFO_NEEDS_REVIEW`를 쓰고 object-level `review_needed=true`로 집계한다. 「사용자 입력 자체를 다시 검토해야 하는가」와 「이 값을 확정처럼 보여도 되는가」는 서로 다른 축이고 모순이 아니다(이슈 #39 A-3, 김준영).

## 3. 지켜야 하는 것

1. **`INFO_AI_ESTIMATED`·`INFO_NEEDS_REVIEW` 값은 확정값과 시각적으로 구분한다.** 같은 서체·같은 위치에 배지 없이 놓지 않는다.
2. **출처를 값과 같은 화면에 둔다.** `source_label_key`로 문구를 고르고 `source.kind` 문자열을 직접 해석하지 않는다. `source_label_key`가 `null`이면 fallback 문구를 쓴다.
3. **`INFO_UNKNOWN`은 빈 칸이 아니다.** 위치라면 `hints.location` · `coord` · `search_keyword`를 단서로 함께 보여준다. 사용자가 무엇을 근거로 채워야 하는지 알 수 있어야 한다.
   *근거:* `product-spec.md` §7이 「값을 만들어내지 않고 출처와 `확인 필요`/UNKNOWN **상태를 보여준다**」로 `UNKNOWN`을 표시 대상으로 명시한다. 빈 칸은 상태를 보여주는 것도, 단서를 유지하는 것도 아니다.
4. **값을 합치거나 새로 만들지 않는다.** `coord`는 원값으로 내려오고 포맷만 `web`이 한다. 여러 위치 값을 이어 붙여 새 문자열을 만들지 않는다(계약 B절 §7-(3)).
5. **handoff 화면에서 미확정 값을 「준비됨」으로 묶지 않는다.** 신고요건 판정은 `requirements_evidence` / `requirements_package`가 소유하고, 세 gate(`EVIDENCE_SUFFICIENT` · `PACKAGE_READY` · `USER_REVIEWED`)는 각각 구분해 표시한다.
   *근거:* `management/ownership.md` §7-④의 통합 기준 「세 상태가 `CaseView`에 구분되어 표시되는가」 · 계약 B절 §7 「세 gate의 출처」·§10-11(하나의 readiness로 합치지 않는다). 실제 제출은 사용자가 직접 하므로(`product-spec.md` §7) 무엇이 미확정인지가 마지막 화면까지 남아야 한다.
6. **`evidence.review_needed`를 제출 게이트로 쓰지 않는다. 화면 분기의 기준은 언제나 `info_state`다.**
   *2026-09-11 갱신:* v1.3에서 집계식이 `report_type_display.info_state==INFO_NEEDS_REVIEW`까지 포함하도록 개정돼, **「여섯 필드 중 하나라도 검토가 필요한가」의 요약으로는 이제 신뢰할 수 있다.** 요약 배지·정렬 힌트로 쓰는 것은 가능하다.
   그래도 **제출 게이트로는 쓰지 않는다.** ① 게이트는 세 gate(`requirements_evidence`·`requirements_package`·`user_reviewed`)가 소유하며 각각 다른 것을 판정한다 — `review_needed`는 **값 상태의 집계**이지 신고요건·자료완성·사용자검토 어느 것도 아니다(규칙 5). ② `needs_review`와 `info_state`가 독립 필드라는 원칙은 그대로이므로(§2-1), 이 한 불리언으로 화면을 분기하면 어느 필드가 왜 걸렸는지가 사라진다 — 그 정보는 `reason_code`와 필드별 `info_state`에만 있다.
7. **`WARN`이라고 제출 경로를 막지 않는다 — 대신 미확정 표시를 마지막 화면까지 유지한다.**
   계약 §10-3이 `readiness ∈ {PASS, WARN}`에서 `package` non-null을 허용하고, 버튼은 `package.capabilities[]`가 켠다. v4의 `scenario_unknown_abstain_partial_001` rev4가 실제로 `requirements_package.readiness=WARN`인데 `capabilities=["DOWNLOAD_ASSETS","COPY_FIELDS","OPEN_DESTINATION"]` 3종을 그대로 갖는다 — 다운로드·복사·안전신문고 이동을 막지 않는다(이슈 #25 ④).
   **같은 스냅샷의 `package.warnings`는 `[]`다.** 즉 그 화면에서 「무엇이 미확정인가」를 나르는 것은 경고 문구가 아니라 오직 `report_field_states`/`unconfirmed_fields`다(§5-1). 경로를 여는 것과 상태를 숨기는 것은 다른 일이다.

## 4. 적용 대상 — 여섯 display 전부 규칙 적용이 가능하다

| display | 가진 필드 | 이 규칙 적용 |
| --- | --- | --- |
| `plate_display` · `event_time_display` · `location_display` | `value` · `info_state` · `source_label_key` · `needs_review` | **가능.** §2·§3 그대로 |
| `case_type_display` · `violation_display` | `code` · `label` · `needs_review` · `info_state` · `source_label_key` | **가능.** §2·§3 그대로 |
| `report_type_display` | `code` · `label` · `needs_review` · **`info_state` · `source_label_key`**(`case-view/v1.3`에서 추가) | **가능.** §2·§3 그대로 |

> **2026-09-11 갱신 — 여섯 display가 같은 규칙으로 통일됐다.** 마지막까지 남아 있던 `report_type_display`의 `info_state`/`source_label_key` 보류가 풀렸다. 보류 근거였던 `safety_report_type`의 4→2 mapping registry가 `docs/modules/evidence/decisions/safety-report-policy-v1.md`(`safety-report-policy/v1`, PR [#32](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/32))로 확정돼 `CONTRACT_CONFLICTS.md` 항목 4가 종결됐다. **web이 새로 분기할 것은 없다** — 여섯 display 모두 계약 B절 §7 (1)의 같은 파생 규칙을 쓴다.
>
> **필드 부재 처리 — 상시 방어 규칙.** v4에서 `case_type_display`·`violation_display`·`report_type_display`의 백필이 끝나(이슈 #31 W-3), **`evidence`가 있는 모든 스냅샷은 여섯 display를 전부 갖고 `info_state`·`source_label_key`도 모두 채워져 있다.** 따라서 「일부 시나리오에만 필드가 있다」는 한시 상황은 끝났다. 다만 규칙 자체는 유지한다 — display 키가 없거나 `info_state`가 비면 web은 **배지를 붙이지 않고, 없는 상태를 `INFO_SOURCE_VERIFIED`로 간주하지 않으며, `null`이나 임의 기본값을 만들어 넣지 않는다.**
> v4에서 실제로 남는 「없음」은 성격이 다르다 — **`evidence` object 자체가 `null`인 스냅샷**이다(`empty_001` rev2 · `infra_failure` rev1·rev2 · `relative_rebase` rev1·rev2 · `happy` rev1). 개별 display 누락이 아니라 증거 조립 전 단계이므로, 값 상태 표시가 아니라 진행 상태 화면(`progress[]`·`running_jobs[]`)이 담당한다.
>
> **happy path 신고문에 「AI 추정」 배지가 뜨는 것은 의도된 결과다.** v4 `scenario_happy_001` rev3·rev4에서 `violation_display`(AI 생성 위반 문장)와 `report_type_display`(4→2 매핑값)가 둘 다 `INFO_AI_ESTIMATED`다. 예고했던 화면 변화가 이미 일어났고, 이 문서 기준으로 그게 맞는 화면이다.
>
> **주의 — 계약 §7 (1) 적용범위 설명문 1개가 fixture와 어긋난다.** 「`visual_event_type`/`violation_expression`은 `evidence.assemble()`이 **항상** `INFERRED`로 채운다」는 문장인데, 실제 evidence fixture의 `visual_event_type`은 `source.observability=OBSERVED`(`kind=search.visual_inference`)이고 그래서 `case_type_display=INFO_SOURCE_VERIFIED`가 나온다(happy·correction_rerun·plate_reread 공통). **결론과 fixture가 맞고 근거 문장만 틀렸다**(이슈 [#38](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/38) B-3, case 정정 예정). 이 문장을 근거로 fixture를 `INFERRED`로 「고치는」 반대 방향 수정을 하지 않는다.

앞의 셋은 **미확정 상태가 정상 경로**다. 번호판은 `readout`이 `abstained=true`로 보류할 수 있고(`contract-plate-overlay-readout.md` §11-1), 시각은 파일명·metadata 계산값이 `INFO_NEEDS_REVIEW`로 내려오고(계약 B절 §7-(2) · `contract-time-resolution.md` §4), 위치는 `address`가 없는 동안 대표값이 `user_hint`다. 예외 화면이 아니라 기본 화면에서 이 규칙이 작동해야 한다.

## 5. 신고자료(handoff) 화면 규칙 — `report_field_states` 기준

### 5-1. 확정 — `report_field_states`를 직접 읽는다

`case-view/v1.3`에서 `package.report_field_states`가 신설됐다(이슈 #31 A-2 요청분). `report_fields`(복사용 평면 `object<string, string|null>`)와 **나란히** 필드별 `{info_state, source_label_key}`를 제공하며, **값 공간은 여섯 `*_display.info_state`와 같다** — 새 상태 enum이 아니다.

**따라서 이전 잠정(「`report_fields`는 복사용 텍스트로만 쓰고 배지·출처는 `evidence.*_display`에서 가져온다 · 두 면이 다르면 확인 필요로 취급」)은 철회한다.** 신고자료 화면은 `report_field_states`를 직접 읽어 §2·§3 규칙을 그대로 적용한다.

계약 B절 §7이 확정한 대응표(`case`가 재계산 없이 옮긴다):

| `report_fields` 키 | 출처 display |
| --- | --- |
| `vehicle_number` | `plate_display` |
| `occurred_at` | `event_time_display` |
| `location` | `location_display` |
| `violation_expression` | `violation_display` |
| `safety_report_type` | `report_type_display` |
| — | `case_type_display`는 대응 키가 없다 — 안전신문고 신고 양식에 들어가지 않는 내부 사건 분류이기 때문이다. 신고자료 화면에서는 표시 대상이 아니다 |

`unconfirmed_fields`는 이제 독립 원천이 아니라 **파생 목록**으로 정의됐다 — `report_field_states[field].info_state ∈ {INFO_AI_ESTIMATED, INFO_NEEDS_REVIEW, INFO_UNKNOWN}`인 필드명. web은 이 배열을 **요약(「확인 필요 N건」)에만** 쓰고, 필드별 배지·출처는 `report_field_states`에서 가져온다. 두 값이 어긋나면 `report_field_states`가 authoritative다.

> 이전에 기록했던 「두 면이 양방향으로 어긋난다」(u001 rev4에서 `location`·`violation_expression`이 `unconfirmed_fields`에 없고 `safety_report_type`은 배열에만 있던 문제)는 **해소됐다.** v4 u001 rev4의 `unconfirmed_fields`는 `["safety_report_type","occurred_at","location","violation_expression"]`으로 파생 규칙과 정확히 일치한다.

### 5-2. 작업 상태(CANCELLED) 계열 — 확정 2건 · 미결 1건

> **2026-09-14 갱신.** `job-execution/v1.1`에 `CANCELLED`가 신설된 뒤 web이 중단 화면을 그릴 근거가 세 군데 비어 있었다(이슈 [#33](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/33) ②). Mock Pack v5의 `scenario_infra_failure_001`(CANCELLED→PARTIAL 실물)과 유소연 답변(PR [#46](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/46))으로 **①③이 닫혔고 ②만 남는다.**

**확정 ③ — 「중단」과 「부분 완료」는 같은 상태값, 다른 문구** (2026-09-13 유소연, PR #46 Q-2)

`progress[].state=PARTIAL`에는 두 투영 경로가 등재돼 있다(`AnalysisRun.outcome=PARTIAL` · `JobExecution.status=CANCELLED`). **상태값은 `PARTIAL` 하나로 유지하고, 표시 문구만 「취소를 뜻하는 notice code」의 유무로 분기한다** — B절 §7의 2026-09-10 결정(「`PARTIAL`이 부분 완료·중단 둘 다 흡수하고, 구분이 필요하면 `notices[]`로」)을 그대로 따르는 것이라 새 규칙이 아니다.

| 화면 문구 | 조건 |
| --- | --- |
| **「중단됨」** | `progress[].state=PARTIAL` + 같은 단계에 취소 code notice(`case.plate_read_cancelled` · `actions`에 `RETRY_PLATE_READ`) |
| **「부분 완료」** | `progress[].state=PARTIAL`이고 취소 code notice 없음 (무관한 notice는 있을 수 있다) |

- **분기 기준은 「취소를 뜻하는 code」의 존재이지 notice의 존재가 아니다.** v5 `scenario_infra_failure_001` rev3의 `notices[]`는 `case.plate_read_cancelled`와 `readout.overlay_presence_undetermined` **2건**이다 — 중단과 무관한 notice가 같은 스냅샷에 공존하므로, notice가 하나라도 있으면 「중단됨」으로 찍는 규칙은 오작동한다.
- **현재 등재된 취소 code는 `case.plate_read_cancelled` 1종이고, 그 외에는 「부분 완료」로 그린다.** `notices[].code`는 형식(`<producing-module>.<detail>`)만 확정돼 있고 **값 목록은 열려 있으며**, `actions[]`와 달리 「미등록 값 렌더 금지」 규칙도 없다(B절 §7, 이슈 [#26](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/26) A-⑤). 따라서 모르는 code를 만나면 **중단을 단정하지 않는 쪽**이 안전한 기본값이다.
- **계약 공백 — `case`에 요청.** 취소 계열 code가 늘어나면 web이 이 목록을 따라 갱신해야 하고, 놓치면 실제 중단이 「부분 완료」로 표시된다. 새 취소 code를 만들 때 알려주시거나, 취소 계열을 식별할 수단(code 목록 등재 또는 별도 표시)을 주시면 목록 추적을 없앨 수 있다.
**확정 ① — 취소된 job은 `running_jobs[]`에서 빠진다. web은 job 단위 중단 표시를 하지 않는다**

**의도된 설계다.** 근거를 무게 순으로 적는다.

| 근거 | 내용 |
| --- | --- |
| **① 스키마 (핵심 근거)** | `running_jobs[].status`는 `PENDING` / `RUNNING` **2값**이다. `CANCELLED`를 표현할 자리가 애초에 없다 — 취소된 job을 배열에 남기려면 값 공간을 늘려야 하는데 그런 개정이 없었다 |
| **② 계층 구분 (개정문이 직접 말한다)** | `CANCELLED`는 `job-execution/v1.1`(2026-09-10, 이슈 [#33](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/33) A-2)에서 `JobExecution.status`에 추가됐고, 그 개정문이 스스로 **「이 계약은 실행 상태 표현만 연다」**고 적었다. 그 뒤 `case-view/v1.3`은 `running_jobs[].status`를 2값으로 유지했다 — **빠뜨린 게 아니라 계층이 다르다**(실행 상태 ≠ 화면 투영) |
| **③ 불변조건 (보조)** | B절 §10 불변조건 5 — 「`running_jobs`가 비어 있으면 진행 중인 작업 없음」. **단 이 문장은 「진행 중인 것만 담는다」까지 주지는 않는다**(터미널 job이 섞여 있어도 명제는 참이다) — 그건 위 ①에서 나온다. 방향을 지지하는 보조 근거다 |
| **④ fixture 실물** | v5 `scenario_infra_failure_001` rev3·rev4: `job_x001_plate_reread`의 실행이 `CANCELLED`인데 `running_jobs=[]`이고, 중단 사실은 `notices[case.plate_read_cancelled]`가 나른다. Mock Pack 전체의 `running_jobs[]` 엔트리 3건도 전부 `PENDING`/`RUNNING`이다 |

`running_jobs[]`는 「지금 돌고 있는 것」만 보여주는 배열로 쓰고, 중단 사실은 `progress[].state`와 notice가 나른다.

> **case Owner 확인 대기 (비차단).** 위 근거는 전부 계약 문구와 기록된 값이며, 유소연(`case`)이 이 항목을 명시적으로 답한 것은 아니다(PR #46 Q-2 답변은 ③에 대한 것이다). `running_jobs[].status`를 2값으로 유지하는 한 이 절은 확정이고, `CANCELLED`를 이 배열에 넣기로 하면 되돌린다.

**미결 ② — 「이어서 찾기」를 렌더할 `actions[]` 값이 없다**

값 공간이 7종(`EDIT_EVENT_TIME`·`MANUAL_PLATE_INPUT`·`GENERATE_REPORT_VIDEO`·`REVIEW_TIME`·`RETRY_PLATE_READ`·`EDIT_HINT`·`RETRY_SEARCH`)으로 닫혔고 미등록 값은 렌더 금지인데, **재개에 해당하는 값이 없다.** `scenario_empty_001`에서 발견해 이슈 [#31](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/31) W-1로 닫은 것과 정확히 같은 문제다(그때 `EDIT_HINT`·`RETRY_SEARCH` 2종 추가로 해소).

**2026-09-14 갱신 — 이 미결의 무게가 올라갔다.** PR #46에서 「이어서 찾기 = 새 `job_id` 발주」로 확정되면서 재개가 예외가 아니라 **정상 경로**가 됐다. 지금 목록으로는 중단 화면에 버튼이 하나도 뜨지 않는다. 이슈 [#48](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/48) Q3도 같은 `actions[]` 목록에 위치 입력 대응 값을 묻고 있어 **두 건을 한 번에 보는 편이 낫다.**

**검증 상태 — v5에서 절반 해소**

~~두 투영 경로 어느 쪽도 실제 시나리오가 없어 이 화면은 현재 목데이터로 눌러볼 수 없다.~~ → Mock Pack v5가 `scenario_infra_failure_001`에 `CANCELLED`→`PARTIAL` 실물을 넣었다(`job_x001_plate_reread` · rev3·rev4). 위 확정 2건은 이 fixture로 검증 가능하다.

**`AnalysisRun.outcome=PARTIAL` 투영 쪽은 여전히 fixture가 없다** — Mock Pack 어느 run도 `outcome=PARTIAL`이 아니다. 「부분 완료」 문구 자체는 아직 실물로 눌러볼 수 없다.

### 5-3. web이 닫은 것 — `situation_confirmation` 화면 문구

`candidates[].situation_confirmation`은 `NOT_ASKED | CONFIRMED | CORRECTED | USER_UNSURE` **닫힌 4종**으로 확정됐고(`case-view/v1.3`, `EvidenceRecord.situation_response`와 값 공간 일치), `situation_confirmation_label_key`는 내려오지 않는다.

다른 표시 필드는 전부 key로 내려오는데(`source_label_key`·`stale_revision_label_key`·`running_jobs[].label_key`) 이것만 생값이라 문구 소유를 물었고(이슈 #33 ①, #38 A), 값 공간과 파생 출처만 확정된 상태다. **닫힌 enum이고 label key가 제공되지 않으므로 `web`이 4종의 화면 문구를 매핑한다** — 「아직 안 물어봄」(`NOT_ASKED`)과 「모르겠다고 답함」(`USER_UNSURE`)을 다른 칸으로 그리고, 두 상태를 같은 빈칸으로 합치지 않는다(이 필드가 신설된 이유 자체다).

나중에 `case`가 `situation_confirmation_label_key`를 내리기로 하면 그때 이 규칙을 key 참조로 바꾼다. 값 공간이 닫혀 있어 web이 임의 문구를 만드는 위험은 없다.

## 6. 목데이터 대조 (Mock Pack v4 · `develop` @ `d9d8e2b` 기준)

| fixture | v4 실측값 | 이 문서에서 검증되는 것 |
| --- | --- | --- |
| `scenario_happy_001` rev3·rev4 | `location_display`: `value`=사용자 힌트 문장 · `info_state=INFO_NEEDS_REVIEW` · `source_label_key=location.source.user_hint` · `coord`=관측 GPS · **`needs_review=false`** / object-level `review_needed=true` · `reason_code=evidence.location_needs_review` | 규칙 1·4·5 · **§2-1 두 축 구분의 실물** · `stage=READY`·`user_reviewed=true`에서도 미확정 값이 남는다 |
| `scenario_happy_001` rev3·rev4 (package) | `report_field_states` 5필드 = `vehicle_number`/`occurred_at` `INFO_SOURCE_VERIFIED` · `location` `INFO_NEEDS_REVIEW` · `violation_expression`/`safety_report_type` `INFO_AI_ESTIMATED`, `unconfirmed_fields=["safety_report_type","location","violation_expression"]` | **§5-1 전체** — 대응표·파생 규칙이 실제로 맞는 스냅샷 |
| `scenario_correction_rerun_001` rev2 → rev3 | `event_time_display`: `INFO_NEEDS_REVIEW`(`time.source.filename`, `needs_review=true`) → **`INFO_USER_CONFIRMED`**(`time.source.user_correction`), object `review_needed` `true`→`false` | **`INFO_USER_CONFIRMED` 유일한 실화면 검증.** 정정 전/후 쌍이라 「사용자 확인됨」 전환 표시까지 확인 가능 |
| `scenario_plate_reread_001` rev3 → rev4 | `plate_display`: `value=null`·`INFO_UNKNOWN`(재판독 job PENDING) → **`INFO_SOURCE_VERIFIED`**(`plate.source.plate_ocr`) | 규칙 3(빈 칸 금지)과 그 **해소 경로**까지 |
| `scenario_unknown_abstain_partial_001` rev3 | `case_type_display=INFO_UNKNOWN`(`source_label_key=null`) · `violation_display=INFO_AI_ESTIMATED` · `report_type_display=INFO_NEEDS_REVIEW`(`needs_review=true`) · `event_time_display=INFO_NEEDS_REVIEW` · `location_display=INFO_UNKNOWN` | §4의 여섯 display 통일 · `INFO_AI_ESTIMATED`·`INFO_UNKNOWN` 동시 검증 |
| `scenario_unknown_abstain_partial_001` rev4 | `stage=READY` · `requirements_package.readiness=WARN` · `capabilities` 3종 전부 · `warnings=[]` · `unconfirmed_fields=["safety_report_type","occurred_at","location","violation_expression"]` | **규칙 7** — WARN에서도 제출 경로는 열리고, 미확정 정보는 오직 `report_field_states`가 나른다 |
| `evidence=null` 스냅샷 6개 | `empty_001` rev2 · `infra_failure` rev1·rev2 · `relative_rebase` rev1·rev2 · `happy` rev1 | §4 「필드 부재」의 실제 형태 — 값 상태가 아니라 진행 상태 화면이 담당 |

**`info_state` 5종 전부 목데이터로 화면 검증이 가능하다.** `INFO_USER_CONFIRMED`(correction_rerun rev3) · `INFO_SOURCE_VERIFIED`(happy) · `INFO_AI_ESTIMATED`(happy·u001 `violation_display`) · `INFO_NEEDS_REVIEW`(happy `location`·u001 `event_time`) · `INFO_UNKNOWN`(u001 `case_type`·plate_reread rev3 `plate`).

> **문서 stale 1건 (v4에서도 남아 있음).** `docs/mock/04_mock_validation_report.md`의 §1 `CaseView` 행 · §1 갭 요약 · 결론부가 아직 `info_state=INFO_AI_ESTIMATED`를 「미커버」로 적고 있다. 실제로는 v3에서 이미 해소됐고 v4에서는 happy path까지 확대됐다(이슈 #31 W-11로 제기, 이슈 #39 Required-6 범위). fixture가 아니라 문서만 어긋난 상태다.

> **아직 못 그리는 화면.** `requirements_*.readiness=BLOCK` 경로는 fixture가 없어(`scenario_blocked_001` 대기) 규칙 5·7의 BLOCK 분기를 목데이터로 검증할 수 없다. `progress[].state=PARTIAL`도 같다(§5-2 ③).
