# 이슈 초안 — 위치를 확보하지 못한 사건에서 `ReportPackage`를 발행할 것인가

> 상태: **게시 완료 — [이슈 #48](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/48)** (2026-09-13). 이 문서는 이슈의 원본 초안과 재검토 기록으로 남는다. 이후 논의는 이슈에서 진행한다.
>
> 작성일: `2026-09-13`
>
> 관련 결정: [`10_first-completion_decisions_and_integration`](./10_first-completion_decisions_and_integration_2026-09-13.md) **D1(Q1)** · [`ADR-EVIDENCE-002` §5.6](../adr/adr-first-completion-owner-decisions.md)
>
> 제안 논의자: 김준영(`evidence`, `report-package/v1` Contract Owner) · 유소연(`case`) · 신유민(`web`)

## 제안 제목

`[evidence/case/web] 위치를 확보하지 못한 사건에서 ReportPackage를 발행하는가 — report-package/v1 location 필수 규정 확인`

## 한 줄 요약

공용 `scenario_unknown_abstain_partial_001`의 `pkg_u001`은 `report_inputs.location = null`인데, `report-package/v1` §7은 `location{display_text: string}`을 **필수**로 요구한다. 지금 이 둘을 동시에 만족하는 구현은 없다. 그래서 「GPS도 없고 사용자도 위치 단서를 주지 않은 사건」에서 신고자료를 **내줄 것인지 보류할 것인지**를 한 번 정해야 한다.

## 배경

### 무엇을 하려는 것인가

대신고는 마지막에 `ReportPackage`를 만들어 사용자에게 넘긴다. 여기에는 안전신문고 입력칸에 대응하는 확정값 snapshot(`report_inputs`)과 결정론적으로 생성한 신고문(`report`)이 들어간다.

`report_inputs.location`은 그중 하나다. 최종 지도 핀은 제품이 찍지 않는다 — 사용자가 안전신문고 지도에서 직접 놓고, 대신고는 **검색어와 표시 문구까지만** 넘긴다(`core-user-flow.md` §14 · §21).

### 지금 세 곳이 서로 다른 답을 전제한다

| | 위치 없는 U에서 Package는? | 근거 |
| --- | --- | --- |
| Final Contract `report-package/v1` §7 | **불가.** `location{display_text: string}`이 필수 | 계약 §7 스키마 |
| evidence 구현·baseline | **보류.** `PackageNotReady("package.input.location_missing")` | `src/daesingo/evidence/requirements.py` `_location_snapshot` |
| 공용 Mock fixture `pkg_u001` | **발행.** `report_inputs.location = null`로 존재 | `data/mock/evidence/scenario_unknown_abstain_partial_001.json` |
| 공용 Mock `CaseView` u001 rev4 | **발행.** `stage=READY`, `package.package_ref=pkg_u001` | `data/mock/case/scenario_unknown_abstain_partial_001.json` |

실행해서 확인한 값이다.

```text
validate_report_package(pkg_h001)  → []
validate_report_package(pkg_u001)  → ['location']     ← report-package/v1 위반
python data/mock/validate_mock_pack.py → VALIDATION PASSED (46 files, 7 scenarios)
```

**공용 validator가 이것을 잡지 못하는 이유**는 `validate_mock_pack.py`의 `REQUIRED_OBJECT_KEYS`가 `report_packages`에 대해 `report_inputs` **키의 존재만** 검사하고 그 안의 모양은 보지 않기 때문이다. 계약 위반이 맞는데 공용 검사를 통과해서, 지금까지 fixture 쪽에서는 문제로 드러나지 않았다.

### U가 실제로 어떤 상태인가

- `recording`의 GPS: `Observation{value: null, status: UNKNOWN, reason.code: "recording.gps.source_absent"}`
- `case`의 intake hint: `hints.location = null` — **사용자가 위치 단서를 준 적이 없다**
- 그래서 `ev_u001`에는 `location` 키 자체가 없다(`address`·`place_name`·`user_hint`·`search_keyword`·`coord` 전부 부재)
- `CaseView` u001 rev4: `location_display = {value: null, info_state: INFO_UNKNOWN, ...}`, `unconfirmed_fields`에 `location` 포함, **위치에 관한 `notices[]`는 하나도 없음**

즉 U는 「제품이 위치를 찾으려다 실패한 상태」가 아니라 **「아무도 위치를 물어본 적이 없는 상태」**다. 이 구분이 아래 선택지 판단에 직접 들어간다.

### 이미 닫혀 있어서 다시 논의하지 않는 것

- **placeholder 주소·임의 좌표는 선택지가 아니다.** `product-spec.md` §7 — 「번호판·시각·위치가 불확실하면 값을 만들어내지 않고 출처와 `확인 필요`/UNKNOWN 상태를 보여준다」.
- **자체 지도 UI는 MVP 밖이고 최종 핀은 안전신문고에서 사용자가 찍는다**(`product-spec.md` §7 · `core-user-flow.md` §14 · §21).
- **GPS 없는 위치 완전자동 확정은 버린 항목이다**(`product-spec.md` §5 Won't · 재논의 구분표 「버림(MVP)」).
- **`CaseView`의 위치 표시 규칙은 닫혔다.** 대표값은 `address → place_name → user_hint` 중 첫 값, 셋 다 없으면 `INFO_UNKNOWN`(`contract-job-record-case-view.md` B절 §7-(3)). 필드별 상태는 `report_field_states`로 내려간다(`case-view/v1.3`, 이슈 `#31` A-2 종결).
- **K3의 `package.location.present`(`PASS`/`UNKNOWN`) 기본값은 이 결정을 선점하지 않는다.** ADR-EVIDENCE-002 §5.6이 「D1이 ①로 결정되면 outcome 매핑을 바꾸는 새 revision을 발행한다」고 명시해 뒀다.

### 아직 닫히지 않은 것 — 이 이슈의 전부

**위치를 확보하지 못한 사건에서 `ReportPackage`를 발행하는가, 보류하는가.** 그리고 그 답에 따라 따라오는 신고문·CaseView·fixture 처리.

## 문제

`10_first-completion_decisions_and_integration` D1은 선택지를 세 개로 적었다. 이번 재검토에서 **①과 ② 양쪽 모두 D1이 적은 것보다 비용이 크다**는 것이 드러났다. 그래서 「무엇이 가장 작은 변경인가」로는 이 결정이 닫히지 않는다.

### ①(위치 없는 WARN Package 허용)은 계약 한 줄로 끝나지 않는다

신고문 template이 `{발생장소}`를 **두 template 모두** 본문 슬롯으로 쓴다(`safety-report-policy-v1.md`).

```text
tmpl/safety-report-specific-v1
  {발생일시}경 {발생장소}에서 차량번호 {차량번호} 차량이 {위반행위}하는 것을 …

tmpl/safety-report-generic-v1
  {발생일시}경 {발생장소}에서 촬영된 차량번호 {차량번호} 차량의 주행 상황에 대해 …
```

같은 문서 Renderer 불변조건 2가 입력 슬롯을 `occurred_at` · **`location.display_text`** · `vehicle_number`(+ specific은 `violation_expression`)로 고정한다. **장소 없이 렌더할 수 있는 template이 registry에 없다.** ①을 고르면 template 변형이나 슬롯 생략 규칙을 같은 결정에 넣어야 한다.

`report-package/v1` §14도 「handoff snapshot 필수/선택 의미 변경」을 **contract version 증가 + ADR 대상**으로 등재하고 있다. ①은 `v1 → v1.1`이다.

### ②(Package 보류)는 사용자를 READY 화면에 도달시키지 않는다

제품 문서 세 곳이 반대 방향을 가리킨다.

- `core-user-flow.md` §19 — 사용자에게 확인을 요구하는 항목은 차량번호·신고 상황 **둘뿐**이고, 「발생시각 · 위치 · 신고유형」은 **요구하지 않음**이다.
- 같은 문서 §19 — 「GPS가 없어 제품 안에서 완료할 수 없는 정보를 `4/5` 같은 실패 상태로 표시하지 않는다.」
- `module-architecture.md` §8-3 실패 시나리오 표 — 「GPS 없음 → 나머지 Evidence는 살아 있음 → **위치 미확인, 오류 아님**」.

②는 위치 하나로 신고영상·번호판·신고문이 전부 준비된 case를 통째로 보류시킨다. 「오류 아님」으로 적힌 상황이 사용자 화면에서는 막다른 끝이 된다.

반대 근거도 분명히 있다. ADR-EVIDENCE-002 §5.11이 Research를 근거로 **발생장소를 `TRAFFIC_VIOLATION`·`MOTORCYCLE_VIOLATION` 양쪽에서 「필요」**로 등재했다. 위치 없는 자료를 내주면 사용자가 안전신문고에서 제출을 완료하지 못할 수 있다.

### 「위치 있음」의 현재 하한이 기억 문장이다

`pkg_h001`의 `location.display_text`는 `"상무중앙로에서 시청 방향으로 가다가 사거리에서 발생"`이다. `ev_h001`에 `address`·`place_name`이 없어 `user_hint`가 대표값으로 올라온 것이고, 이 문장은 안전신문고 발생장소 칸에 그대로 넣을 값이 아니다(이슈 `#26` A-5에서 신유민이 같은 지적을 했고, 그때는 **표시 상태** 문제로 닫혔다 — `INFO_NEEDS_REVIEW`로 표시한다).

H는 GPS 좌표(`coord`)를 갖고 있는데도 `report-package/v1`의 `location`에는 `display_text`·`search_keyword`만 있어 좌표가 Package에 실리지 않는다.

정리하면 지금 기준은 **「기억 문장 한 줄이라도 있으면 발행, 아무것도 없으면 전면 보류」**다. 이 선을 그대로 둘 것인지가 ①/② 판단에 들어간다.

### 지금 정하지 않으면 K3 v2에서 어긋남이 커진다

K3(`policy/requirement-rules-v2`)를 적용해 U를 재실행하면 `FINAL_PACKAGE`에 `package.location.present`(→ `UNKNOWN`)와 `package.report.content_length`(위치가 없어 렌더 불가 → `UNKNOWN`)가 들어온다. overall precedence가 `BLOCK > UNKNOWN > WARN > PASS`이므로 **U의 `overall`은 현재 fixture의 `WARN`에서 `UNKNOWN`으로 바뀌고, `PACKAGE_READY`는 성립하지 않는다.** 공용 fixture의 `pkg_u001`·`stage=READY`와의 거리가 지금보다 더 벌어진다.

## 확인할 질문

질문마다 답해야 할 Owner가 다르다. **각자 자기 이름이 붙은 항목만 답하면 된다.**

### Q1. 위치 없는 신고자료를 사용자에게 내주는가 — 김준영(PM·`evidence`) · 유소연(`case`)

이 이슈의 본문이다. `report-package/v1`의 Contract Owner는 김준영이므로 「계약을 고쳐도 되는가」는 질문이 아니다. 물어야 할 것은 **제품이 어느 쪽을 약속하는가**다.

| 선택지 | 내용 | 따라오는 것 |
| --- | --- | --- |
| ① | 위치 없는 WARN Package를 명시적으로 허용 | `report-package/v1` 개정(§14 → version 증가 + ADR) · 장소 슬롯 없는 신고문 규칙 · `package.location.present` 매핑 revision |
| ② | 위치가 생길 때까지 Package 미발행 | 공용 `pkg_u001` 삭제, `CaseView` u001 rev4의 `stage`·`package` 수정 · 사용자에게 무엇이 남았는지 말하는 경로 필요 |
| ③ | Package 전에 위치 입력을 **필수화** | `core-user-flow.md` §19와 정면 충돌(위치는 확인을 요구하지 않는 항목) |
| ④ | **한 번 묻고, 답이 없으면 ① 또는 ②** | 아래 Q3. 이번 재검토에서 추가로 보인 선택지다 |

placeholder 주소·임의 좌표는 선택지에 없다(`product-spec.md` §7).

### Q2. ①이면 「위치 없음」을 계약에서 어떤 모양으로 쓰는가 — 김준영(`evidence`) · 유소연(`case`) · 신유민(`web`)

`location: null`인가, `{display_text: null, search_keyword?: null}`인가, 키 생략인가?

**`location: null`이면 공용 fixture와 `CaseView`(`report_fields`는 `object<string, string|null>`)가 이미 그 모양이라 fixture 변경이 없다.** 다만 Consumer 세 쪽이 같은 모양을 읽는지 한 번 확인하고 닫아야 한다.

### Q3. 위치가 없다는 사실을 사용자에게 언제 어떻게 말하는가 — 유소연(`case`) · 신유민(`web`)

지금 U의 `CaseView`에는 **위치 관련 notice가 하나도 없다.** 사용자는 위치가 비어 있다는 사실을 신고자료 화면의 빈칸으로만 마주친다.

`notices[].actions[]`는 **7종으로 닫힌 목록**(`EDIT_EVENT_TIME`·`MANUAL_PLATE_INPUT`·`GENERATE_REPORT_VIDEO`·`REVIEW_TIME`·`RETRY_PLATE_READ`·`EDIT_HINT`·`RETRY_SEARCH`)이고 **위치 입력에 대응하는 값이 없다.** `EDIT_HINT`는 계약상 「다음 `RETRY_SEARCH`의 입력을 바꾸는 동작」이라 신고자료의 발생장소와 다른 것이다. 미등록 값은 버튼을 렌더하지 않는 규칙이므로, Q1이 ①·④ 어느 쪽이든 이 목록을 함께 봐야 한다.

### Q4. ②로 정하면 공용 fixture를 어떻게 고치는가 — 유소연(`case`)

`pkg_u001` 삭제, `req_u001_final`의 `overall`, `CaseView` u001 rev4의 `stage`·`package`·`requirements_package`가 한 묶음으로 움직인다. U 시나리오가 「부분 성공 + WARN Package」를 보여주는 자리였으므로, 그 역할을 어느 시나리오가 대신할지도 같이 정해야 한다(`report-package/v1` §13 최소 케이스 「WARN + 사용자 notice가 있는 Package」).

## 권장 경계

**아래는 이 초안의 제안이며 아직 cross-module 결정이 아니다.** `10_first-completion_decisions_and_integration` D1의 권장안은 ②(「현재 Final을 보존하려면 가장 작은 변경」)였는데, 이번 재검토에서 제품 문서 세 곳이 ① 방향을 가리키는 것이 확인돼 방향을 바꿔 제안한다.

**①을 기본안으로 검토한다.** 단, 계약 한 줄이 아니라 아래 네 가지를 **하나의 결정으로** 묶는다.

1. `report-package/v1` §7의 `location`을 nullable로 개정한다(`report-package/v1.1` + ADR). 모양은 공용 fixture·`CaseView`가 이미 쓰는 `location: null`.
2. 장소 슬롯이 없는 신고문 규칙을 `safety-report-policy`에 추가한다. 값을 지어내 슬롯을 채우지 않고, 문장에서 장소 구절을 빼되 「발생장소는 안전신문고 지도에서 직접 지정」 안내를 handoff 화면이 그대로 이어받는다(`core-user-flow.md` §21이 이미 모든 case에 대해 그렇게 말한다).
3. `package.location.present`의 위치 부재 outcome을 `UNKNOWN` → `WARN`으로 바꾸는 catalog revision을 발행한다(ADR-EVIDENCE-002 §5.6이 예고한 revision).
4. 위치가 비었다는 사실을 사용자에게 말하는 notice를 둔다. 필요한 action 값이 없으면 `notices[].actions[]` 확장을 같은 결정에 포함한다(Q3).

**④(한 번 묻고 나서 정한다)를 함께 검토한다.** U는 애초에 위치를 물어본 적이 없는 case다. 「묻지 않고 보류」와 「묻지 않고 발행」 사이에 한 칸이 비어 있다. 다만 이것을 ③(필수화)으로 만들면 §19와 충돌하므로, **답하지 않아도 진행되는 선택적 경로**여야 한다.

- evidence는 위치의 진위를 판정하지 않는다. 주입된 `EvidenceRecord.location`으로 rule을 적용하고 Package 발행 여부만 정책으로 정한다.
- case는 위치 수집·재질의 orchestration을 소유한다. evidence가 사용자에게 직접 묻지 않는다.
- web은 `info_state`만 보고 표시한다(`contract-job-record-case-view.md` B절 §7-(4)). 위치 빈칸을 web이 자체 판단으로 채우거나 감추지 않는다.
- 어느 쪽으로 정하든 placeholder 주소·임의 좌표·좌표의 임의 역지오코딩은 넣지 않는다.

## 완료 조건

- [ ] 「위치 없는 `ReportPackage`를 발행하는가」에 대해 ①~④ 중 하나가 선택되고 근거가 기록되어 있다.
- [ ] ①이면 `report-package/v1` 개정(version + ADR)과 「위치 없음」의 직렬화 모양이 특정되어 있다.
- [ ] ①이면 장소 슬롯 없는 신고문 규칙이 `safety-report-policy`에 있고, 값을 지어내지 않는다는 점이 test로 남는다.
- [ ] ②면 `pkg_u001`·`req_u001_final`·`CaseView` u001 rev4가 한 묶음으로 수정되고, 「WARN Package」 최소 케이스를 어느 시나리오가 맡는지 정해져 있다.
- [ ] 위치가 비었다는 사실이 `CaseView`에서 관찰 가능하고, 필요한 `notices[].actions[]` 값이 등록되어 있다(또는 필요 없다는 결론이 기록되어 있다).
- [ ] 같은 U 입력에 대해 evidence의 Package 발행 여부와 `case`/`web` 표시가 **하나의 결정으로 일치**한다.
- [ ] `validate_report_package(pkg_u001)`이 빈 목록을 돌려주거나, `pkg_u001`이 더 이상 존재하지 않는다.
- [ ] 공용 `validate_mock_pack.py`가 `report_inputs`의 내부 모양까지 검사하도록 보강되었다(같은 종류의 위반이 다시 조용히 통과하지 않게).
- [ ] K3 v2 재실행 결과(U의 `package.location.present`·`package.report.content_length`)가 선택된 결정과 일치한다.

## 범위 밖

- 자체 지도 UI, 좌표 역지오코딩, 주소 정규화
- GPS 없는 위치의 자동 추정(`product-spec.md` §5에서 「버림(MVP)」)
- 안전신문고 자동입력·자동제출
- `report-package/v1`의 `location`에 `coord`를 추가할지 여부 — 지금 문제와 별개이고, 필요하면 별도 항목으로 연다
- 위치 이외 필드(`occurred_at`·`safety_report_type`)의 미확정 처리

## 레포 내 중복·기존 근거 재검토 (2026-09-13)

게시 전에 같은 질문이 이미 닫혀 있는지 레포와 GitHub 이슈를 확인했다. **닫혀 있지 않다.**

### 확인한 대상

| 대상 | 확인한 것 | 결과 |
| --- | --- | --- |
| GitHub 이슈 `#15`–`#47`(open·closed, 본문과 코멘트 전수) | `location` · `위치` · `display_text` 언급 | **위치 표시·상태 표현**을 다룬 이슈는 여럿 있으나, **Package 발행 여부**를 물은 이슈는 없다(아래) |
| `contract-requirement-report-package.md` | §7 스키마 · §8.2 snapshot 최소 항목 · §13 최소 케이스 · §14 변경 규칙 | `location{display_text}`는 필수이고 nullable 여지가 없다. §14가 이 변경을 version 증가 대상으로 등재 |
| `contract-job-record-case-view.md` | B절 §5 스키마 · §6 필드 정의 · §7-(3) 대표값 · §7-(4) `needs_review`/`info_state` · §7 `notices[].actions[]` · §10 불변조건 · §13 남은 미결 | 표시 규칙은 닫혔고 `report_fields`는 `string|null`을 허용한다. **action 7종에 위치 입력 값이 없고, §13 미결 목록에도 이 항목이 없다** |
| `safety-report-policy-v1.md` | template registry 2종 · Renderer 불변조건 2 | 두 template 모두 `{발생장소}` 슬롯을 쓰고, 장소 없는 변형이 없다 |
| `adr-first-completion-owner-decisions.md` | §5.6 위치 rule · §5.11 신고유형별 필수성 · §5.13 「K3가 단독으로 확정하지 않는 것」 | **D1을 열어둔 채 이 항목을 가리키고 있다.** 발생장소는 두 신고유형 모두 「필요」 |
| `product-spec.md` · `core-user-flow.md` · `module-architecture.md` | §5 Won't·§7 불변 경계 / §14·§19·§21 / §8-3 | 제품·구조 문서가 ① 방향의 근거를 준다(위 「문제」) |
| `data/mock/**` · `data/mock/validate_mock_pack.py` | U 4개 모듈 fixture와 공용 검사 | 아래 「재검토에서 드러난 빈 자리」 |
| `src/daesingo/evidence/**` | `requirements.py` · `validation.py` · `mock_integration.py` | 구현은 이미 보류 쪽이고 그 사실을 `known_differences`로 기록해 두고 있다 |

### 이 이슈와 **다른** 것으로 확인한 기존 논의

- **이슈 `#31` A-2(신유민, closed)** — `u001 rev4`의 `report_fields.location = null`을 **직접 인용했다.** 그러나 물은 것은 「화면에서 `알 수 없음`과 확정 빈칸을 구분할 수 없다」였고, `case-view/v1.3`의 `report_field_states` 신설로 닫혔다. **`location: null`인 Package가 존재해도 되는가는 그때 묻지 않았다** — 오히려 그 모양을 전제로 표시 규칙을 정했다.
- **이슈 `#26` A-5·A-6(신유민, closed)** — happy의 미확정 위치가 그대로 신고자료에 실리는 문제. 값이 **있는데** 미확정인 경우이고, `INFO_NEEDS_REVIEW` 표시와 `review_needed` 집계식 개정으로 닫혔다.
- **이슈 `#19`(evidence 1차)** — happy 위치가 user hint뿐인데 Requirement `PASS`라는 지적. `EVIDENCE` scope의 판정 문제이고, `FINAL_PACKAGE`/Package 발행과 다른 gate다.
- **이슈 `#18`(recording 1차)** — 「`EvidenceRecord.location`의 `address` 및 reverse geocoding provenance는 evidence 측 결정에 따른다. recording은 좌표와 provenance까지만 생산한다」로 Producer 경계가 닫혔다. U의 GPS 부재(`recording.gps.source_absent`)도 그때 승인됐다. **부재 이후를 어떻게 할지는 그 답변의 범위가 아니었다.**
- **`CONTRACT_CONFLICTS.md` 불명확 항목 2·10** — 둘 다 종결. 2번은 사용자 입력값의 `user_corrected` 판정, 10번은 `report_field_states` 신설이다.

### 재검토에서 드러난 빈 자리

1. **공용 validator가 계약 위반을 통과시킨다.** `validate_mock_pack.py`의 `REQUIRED_OBJECT_KEYS[("evidence","report_packages")]`는 `report_inputs` 키 존재만 본다. `pkg_u001`은 `report-package/v1` 위반인데 `VALIDATION PASSED`가 나온다. evidence 쪽 `validate_report_package`만 `['location']`을 돌려준다.
2. **`CaseView`가 위치 부재를 사용자에게 말하지 않는다.** u001 rev4의 `notices[]` 4건은 시각 충돌·overlay 부재·사건 유형 미확정·post-stamp다. 위치는 `unconfirmed_fields`에만 들어가고, 눌러서 해결할 action이 없다.
3. **U는 위치를 물어본 적이 없는 case다.** `hints.location = null`이고 `ev_u001`에는 `location` 키 자체가 없다. 「못 찾음」과 「안 물어봄」이 지금 같은 상태로 표현된다.
4. **장소 없는 신고문 경로가 없다.** template 2종 모두 `{발생장소}`가 본문 슬롯이다. ①을 고르면 이 자리가 반드시 열린다 — `mock_integration.py`의 `known_differences`도 이미 「this scenario cannot fill the required location slot」으로 같은 사실을 적어 두고 있다.

### 결론

**게시할 가치가 있다.** `location: null`이라는 **표기**는 이슈 `#31`에서 이미 화면에 등장했지만, 그 Package가 **존재해도 되는가**는 어느 이슈·계약·결정 문서에서도 답하지 않았다. 반대로 ADR-EVIDENCE-002 §5.6과 §5.13이 이 항목을 열어둔 채 `10_first-completion_decisions_and_integration` D1을 가리키고 있다. **이미 등록된 후속 항목**이지 새로 만든 논점이 아니다.

## 관련 근거

아래는 위 재검토에서 실제로 열어 확인한 것이다.

### 계약

- [`contract-requirement-report-package.md`](../../../architecture/contracts/contract-requirement-report-package.md) — Contract Owner 김준영(`evidence`) · §4.2 outcome 의미(`UNKNOWN` ≠ `BLOCK`) · §4.3 precedence `BLOCK > UNKNOWN > WARN > PASS` · §5.2 `PACKAGE_READY` · §7 `report_inputs.location{display_text, search_keyword?}` 필수 · §8.1 Package 부재 조건 · §8.2 snapshot 최소 항목에 「location display/search 정보」 · §13 최소 케이스 「WARN + 사용자 notice가 있는 Package」 · §14 「handoff snapshot 필수/선택 의미 변경」은 version 증가 + ADR 대상
- [`contract-job-record-case-view.md`](../../../architecture/contracts/contract-job-record-case-view.md) — B절 §5 스키마(`report_fields`는 `object<string, string|null>`) · §6 필드 정의(`location_display.coord`·`search_keyword`는 대표값과 별도) · §7-(3) `location_display` 대표값과 `INFO_UNKNOWN` · §7-(4) `needs_review`/`info_state` 독립과 web 소비 규칙 · §7 `notices[].actions[]` **닫힌 7종** · §7 `unconfirmed_fields` 파생 규칙 · §13 남은 미결(이 항목 없음) · v1.3 개정 ⑤⑥
- [`contract-evidence-record-needs.md`](../../../architecture/contracts/contract-evidence-record-needs.md) — `EvidenceRecord.location`의 값 구조와 `EvidenceValue` 규칙
- [`contract-correction-record.md`](../../../architecture/contracts/contract-correction-record.md) — §6 semantic path 10종 중 위치 4종(`location.coord`·`address`·`place_name`·`search_keyword`·`user_hint`)

### 구조·제품

- [`product-spec.md`](../../../product/product-spec.md) — §5 Won't 「GPS 없는 위치 완전자동 확정」과 재논의 구분표 「버림(MVP)」 · §7 불변 경계 3줄(값을 만들어내지 않음 · 자체 지도 UI 없음 · 최종 핀은 안전신문고)
- [`core-user-flow.md`](../../../product/core-user-flow.md) — §14 위치(GPS 있음/없음 두 화면, 「정확한 위치를 임의로 확정하지 않는다」) · §19 확인 요구 항목 표(**위치는 요구하지 않음**)와 「완료할 수 없는 정보를 실패 상태로 표시하지 않는다」 · §20 최종 확인 화면의 위치 문구 · §21 「직접 고를 것」과 검색어 복사 예외 · §22 대응표 「위치 근거 없음 → 사용자 기억 유지 또는 UNKNOWN」
- [`module-architecture.md`](../../../architecture/module-architecture.md) — §5-9 `EvidenceRecord`의 `location observations` · §8-3 실패 시나리오 「GPS 없음 → 위치 미확인 — 오류 아님」
- [`cross-cutting-decisions.md`](../../../management/cross-cutting-decisions.md) — B-1(Product Spec/Must-Won't 변경 권한: 김준영 PM) · B-3(신고요건 규칙 변경은 별도 서명자 없이 evidence Owner가 겸하되 **주간 회의에 보고**)

### evidence 쪽 기록

- [`adr-first-completion-owner-decisions.md`](../adr/adr-first-completion-owner-decisions.md) — §5.4 `evidence.location.present`(`PASS`/`WARN`)와 EVIDENCE scope에서 WARN인 이유 · §5.6 `package.location.present`(`PASS`/`UNKNOWN`)와 **「K3가 D1을 단독으로 종결하지 않는다」** · §5.11 발생장소 「필요」 · §5.12 업무상 `UNKNOWN`과 정책 엔진 오류의 구분 · §5.13 「D1(Q1) 위치 결론 — 결정되면 새 revision 필요」
- [`safety-report-policy-v1.md`](../decisions/safety-report-policy-v1.md) — template registry 2종의 `{발생장소}` 슬롯 · Renderer 불변조건 2(입력 슬롯에 `location.display_text` 포함) · 불변조건 5(확인하지 않은 내용을 문장에 추가하지 않음)
- [`10_first-completion_decisions_and_integration_2026-09-13.md`](./10_first-completion_decisions_and_integration_2026-09-13.md) — D1(Q1) 원안, 통합 항목 I2·I5
- [`first-completion-result.md`](../first-completion-result.md) — Q1 행: 「U Evidence/Requirement는 처리했지만 정상 Package baseline은 `package.input.location_missing`으로 보류」

### 구현·fixture

- `src/daesingo/evidence/requirements.py` — `_location_snapshot`이 `address → place_name → user_hint` 순으로 대표값을 고르고, 없으면 `PackageNotReady("package.input.location_missing")`
- `src/daesingo/evidence/validation.py` — `report_inputs`에 `location` 필수, `location.display_text`가 비어 있지 않은 문자열일 것
- `src/daesingo/evidence/mock_integration.py` — `known_differences`에 「Baseline withholds ReportPackage because location is absent; the shared package serializes `location=null` outside `report-package/v1`」과 「this scenario cannot fill the required location slot」
- `data/mock/evidence/scenario_unknown_abstain_partial_001.json` — `ev_u001`에 `location` 키 없음 · `req_u001_evidence`의 `evidence.location.present = WARN` · `pkg_u001.report_inputs.location = null`
- `data/mock/case/scenario_unknown_abstain_partial_001.json` — `hints.location = null` · rev4 `stage=READY` · `location_display.info_state=INFO_UNKNOWN` · `unconfirmed_fields`에 `location` 포함 · 위치 notice 없음
- `data/mock/recording/scenario_unknown_abstain_partial_001.json` — `gps_observations`의 `status=UNKNOWN`, `reason.code=recording.gps.source_absent`
- `data/mock/evidence/scenario_happy_001.json` — `ev_h001.location`은 `user_hint`·`search_keyword`·`coord`뿐(`address`·`place_name` 없음), `pkg_h001.location.display_text`는 사용자 기억 문장
- `data/mock/validate_mock_pack.py` — `REQUIRED_OBJECT_KEYS`가 `report_packages`의 최상위 키만 검사

### GitHub 이슈

- [`#31`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/31) A-2 — `u001 rev4`의 `report_fields.location = null`을 인용했으나 **표시 상태 schema** 문제로 닫힘(`report_field_states` 신설)
- [`#26`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/26) A-5·A-6 — happy의 미확정 위치 표시와 `review_needed` 집계식 개정
- [`#19`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/19) — happy 위치가 user hint뿐인데 `EVIDENCE` Requirement `PASS`라는 지적
- [`#18`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/18) — `EvidenceRecord.location`의 address·역지오코딩 provenance는 evidence 결정, recording은 좌표까지만 생산
- [`#39`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/39) A-3 — happy location의 `user_corrected=true`/`needs_review=false`와 `INFO_NEEDS_REVIEW`가 서로 다른 축임을 확인

## 게시 결과 (2026-09-13)

[이슈 #48](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/48) · label `question` · assignee 유소연(`yuusoyeon`)·신유민(`uminshin`).

게시 전 확인 항목 처리:

- [x] 기존 관련 이슈와 중복 여부 확인 — `#15`–`#47` 본문·코멘트 전수 확인, 중복 없음(위 「레포 내 중복·기존 근거 재검토」). 게시 직전 `#47` 이후 신규 이슈가 없음을 다시 확인
- [x] 제목과 label — Contract 변경 **제안**이 아니라 **제품 결정 요청**이므로 `question`. ①로 정해지면 그때 별도 계약 개정 PR로 분리한다
- [x] 「권장 경계」가 합의 완료로 오해되지 않게 문구 확인 — 이슈 §6 도입부에 「제 제안이고 아직 cross-module 결정이 아니다」 명시
- [x] assignee 유소연·신유민 지정 — 지정됨. 본문에서도 질문별 담당 Owner를 @멘션으로 표시했다(Q1 유소연·김준영 / Q2 유소연·신유민 / Q3 유소연·신유민 / Q4 유소연). 정철원은 GPS Producer 경계가 `#18`에서 이미 닫혀 이번 질문에 해당 항목이 없어 제외했다
- [x] 참고 문서 열람 안내 — ADR·`src/daesingo/evidence/**`·이 초안은 아직 `develop`에 없어 링크가 열리지 않는다. 계약 §7 스키마, template 2종의 `{발생장소}` 슬롯과 Renderer 불변조건 2, 제품 문서 세 줄, `notices[].actions[]` 7종을 **본문에 그대로 인용**해 외부 문서를 열지 않아도 답할 수 있게 했다
- [x] 인용한 원문이 `develop` 기준과 일치하는지 확인 — 계약 §7 · policy template 슬롯 · action 7종 · U/H fixture 값을 `origin/develop`에서 대조. 공용 fixture의 `location: null`과 `CaseView` u001 rev4의 `stage=READY`·`pkg_u001`도 `develop`에 그대로 있다
- [ ] **B-3에 따라 주간 회의 보고** — ①·④로 결정되면 신고요건 규칙(`package.location.present` 매핑)과 신고문 template이 함께 바뀌므로 보고 안건에 올린다. 결정 전이라 아직 미수행

게시 시 이슈 본문에 추가한 것(이 문서에는 없는 부분):

- 참고 문서 열람 안내와 「지금 열람 가능(`develop` blob URL) / PR 병합 이후」 분리
- 계약 §7 스키마 블록, template 슬롯, `notices[].actions[]` 7종의 직접 인용
- 질문별 담당 Owner @멘션

이후 논의는 이슈에서 진행한다. 이 문서는 원본 초안과 재검토 기록으로 남긴다.

---

# 받은 답변 정리 (2026-09-14)

이슈 #48에 두 Owner가 답변했다. 아래는 요약이고, 원문은 이슈에 있다.

## 유소연(`case`) — Q1·Q2·Q3·Q4 전부 답변

| 질문 | 답 | 근거로 든 것 |
| --- | --- | --- |
| Q1 | **①** (위치 없이 WARN 발행) | `core-user-flow.md` §19 「사용자가 검증할 방법이 없는 정보에 확인을 강요하지 않는다」는 값이 **부재**한 경우에 더 강하게 적용된다 · `pkg_u001`/rev4가 이미 이 모양이라 ②는 되돌리는 비용 · ②는 고속도로 무명 구간처럼 위치가 영구히 안 채워지는 사건에서 신고 자체를 막는다 |
| Q2 | **`location: null`** | `report_fields`가 이미 `object<string, string\|null>`이라 어떤 모양이든 결국 `string\|null`로 평평해진다 · 빈 객체는 「객체는 있는데 내부가 빈」 다른 사실을 뜻한다 · fixture 변경 비용 0 |
| Q3 | `readout.overlay_not_present`와 같은 모양(**INFO · non-blocking · `actions: []`**), code `case.location_not_secured` 제안. 등재는 본인이 처리 | §19가 이미 「제품 안에서 완료 못 하는 정보를 실패 상태로 안 보여준다」로 정했고, 최종 핀은 안전신문고 소관이라 case 안에 고칠 방법이 없다. 억지 액션은 잘못된 기대를 준다 |
| Q4 | ②면 신규 시나리오가 **필수** | 전수 확인 결과 `FINAL_PACKAGE WARN` + Package 존재 + `notices` 비어있지 않음을 모두 만족하는 시나리오는 u001 하나뿐 |

**추가로 보고한 것 — `case` 구현 두 곳이 실제로 죽는다.** `report_inputs.location`이 `None`이면 `_build_package_view()`가 `location["display_text"]`에서 `TypeError`, `EvidenceRecord`에 `location` 키 자체가 없으면(U가 그렇다) `_field_states()`가 `KeyError`. 둘 다 본인 쪽 방어 부재이고 `location: null`로 확정되면 본인이 고치겠다고 했다.

## 신유민(`readout`·`web`) — Q2·Q3만 답변, Q1은 비용만 보고

- **A절 — 내 전제 정정.** 「사용자는 빈칸으로만 마주친다」(이슈 §5 Q3)는 사실이 아니다. rev4에 위치 상태를 나르는 경로가 이미 둘 있다 — `evidence.location_display.info_state = INFO_UNKNOWN`(빈 칸 금지 규칙 발동)과 `package.report_field_states.location` + `unconfirmed_fields`. 완료 조건 5번째(「CaseView에서 관찰 가능」)는 **이미 충족**이다. 진짜 공백은 다른 곳 — `INFO_UNKNOWN`일 때 함께 보여줄 단서(`hints.location`·`coord`·`search_keyword`)가 U는 셋 다 `null`이다.
- **Q2 — `location: null` 지지. 조건 1건.** `report_fields.location`이 `null`이어도 `report_field_states.location`은 `{info_state: INFO_UNKNOWN, …}`으로 **항상 존재**해야 한다는 문구가 계약에 같이 박혀야 한다. 없으면 web의 §4 방어 규칙(「키가 없거나 state가 비면 배지를 붙이지 않는다」)이 발동해 진짜 빈칸이 생긴다. 키 생략이 가장 위험한 이유도 같다 — 그 규칙은 **「아직 안 온 값」**용인데 위치 부재는 **확정된 사실**이라 두 상황이 화면에서 섞인다. fixture 변경은 없고 현 상태를 계약 문구로 고정해 달라는 요청이다.
- **Q3 — 모양 동의, 문구 재조정 요청(C-2).** `actions[]`는 7종으로 닫혀 있어 늘리지 않으면 버튼은 **못 뜬다**. 늘릴 이유도 없다. 다만 #31 W-6에서 `case.report_video_not_generated`(INFO·`actions:["GENERATE_REPORT_VIDEO"]`)를 추가한 선례와 구분해야 한다 — **제품 안에 실행 경로가 있으면 action, 없으면 문구**. 문구는 「위치를 확보하지 못했다」면 `info_state`와 중복이다. U에서 실제로 깨지는 것은 §21의 「검색어를 복사해 지도에 붙여넣는다」 경로 — `search_keyword`·`coord`가 `null`이라 붙여넣을 것이 없다. notice가 나를 것은 그 사실이다. 복사 버튼 비렌더는 본인이 처리하고 별도 결정이 필요 없다.
- **D절 — ② 비용 보고(의견 아님).** rev4는 web 표시 규칙 문서의 규칙 7(「WARN인데 제출 경로는 열려 있고, 미확정은 `report_field_states`가 나른다」)을 검증하는 **유일한 스냅샷**이다. 전수 재확인 결과 `requirements_package`가 붙는 스냅샷은 `happy_001` rev3·rev4(둘 다 PASS)와 이 rev4뿐이고 WARN은 하나다. `BLOCK`은 이미 fixture가 없어(`scenario_blocked_001` 대기) ②를 고르면 web이 목데이터로 검증 못 하는 화면이 둘로 는다. 유소연 Q4와 같은 결론.

## 두 답변의 관계

| | 유소연 | 신유민 | 상태 |
| --- | --- | --- | --- |
| Q1 | ① | 의견 없음(비용만) | 갈리지 않음 |
| Q2 모양 | `location: null` | `location: null` | **일치** |
| Q2 조건 | 언급 없음 | `report_field_states.location` 필수 존재 | 신유민이 추가한 조건 — 수용 |
| Q3 모양 | INFO·non-blocking·`actions: []` | 동의 + 근거 보강 | **일치** |
| Q3 문구 | `notice.location_not_secured` | 그 문구는 중복 · 「검색어 없음」이어야 | 신유민 수정 요청 — 수용 |
| Q4 | ②면 신규 시나리오 필수 | 같은 결론 | **일치**. ①이면 미발동 |

## 답변 전 사실 확인 (2026-09-14)

게시 전에 두 답변의 사실 주장을 `develop`·작업 트리에서 직접 확인했다.

| 확인한 주장 | 결과 |
| --- | --- |
| 신유민 A절 — rev4가 위치 상태를 이미 나른다 | **맞다.** `location_display = {value: null, needs_review: false, info_state: "INFO_UNKNOWN", source_label_key: null, coord: null, search_keyword: null}`, `report_field_states.location = {info_state: "INFO_UNKNOWN", source_label_key: null}`, `unconfirmed_fields`에 `location` 포함, `warnings: []` |
| 유소연 Q3 — `readout.overlay_not_present`가 INFO·`actions: []` 선례 | **맞다.** u001 rev4의 `notices[]` 안에 그 모양 그대로 있다 |
| 신유민 C-2 — U는 붙여넣을 검색어가 없다 | **맞다.** `search_keyword`·`coord` 모두 `null` |
| `package.location.present` 현재 매핑 | `requirement_rules_v2.json`에 `display_location_absent: "UNKNOWN"` + `open_decision: D1(Q1)` |
| `package.report.content_length` | `render_required_inputs`에 `package_display_location` 포함 · `render_inputs_incomplete: "UNKNOWN"` — **①만 정하고 이걸 그대로 두면 U가 `UNKNOWN`이 되어 §8.1로 Package가 다시 사라진다** |
| 계약 §14 | 「template 내용 변경」은 contract version 증가 대상이 **아니다**(`policy_ref`/`template_ref` 버전으로 관리). 계약 개정과 정책 개정은 PR을 분리할 수 있다 |
| `pkg_u001.report.description` | `tmpl/safety-report-generic-v1`의 출력이 **아니다.** 장소 구절이 없고 문장도 다른데 `template_ref`는 generic-v1을 가리킨다 → Renderer 불변조건 1·4 위반. 장소 없는 변형을 별도 `template_ref`로 등재하면서 함께 고쳐야 한다 |

---

# 답변 — Q1 ① 확정 (게시 완료)

> **게시 완료 (2026-09-14)** — [이슈 #48 코멘트](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/48#issuecomment-5658225684). 작성자 김준영(PM · `evidence` Owner · `report-package/v1` Contract Owner). 아래는 게시한 본문 그대로다.

---

두 분 답변 확인했습니다. **Q1을 ①로 확정**합니다. Q2·Q3에서 나온 결론과 조건도 그대로 받습니다.

## 0. 확정

| | 결정 | 후속 소유 |
| --- | --- | --- |
| Q1 | **①** — 위치 없는 WARN Package를 명시적으로 허용 | 김준영 |
| Q2 | **`location: null`** — 키 생략·빈 객체 둘 다 금지 | 김준영(`report-package/v1.1`) |
| Q2 조건 | `report_field_states.location` 필수 존재 | 유소연(`contract-job-record-case-view.md`) |
| Q3 | INFO · non-blocking · `actions: []`. 문구는 「붙여넣을 검색어가 없다」. `actions[]` **확장 없음** | 유소연(등재)·신유민(문구 매핑) |
| Q4 | **발동하지 않음** — `pkg_u001` 유지 | — |
| ④ | 이번 결정에 넣지 않고 별도 항목으로 남김 | 미정 |

## 1. Q1 — ①

두 분이 든 근거와 제 재검토가 같은 방향입니다. 특히 ②가 「`module-architecture.md` §8-3에서 **오류 아님**으로 적힌 상황」을 사용자 화면에서 막다른 끝으로 만든다는 점, 그리고 고속도로 무명 구간처럼 위치가 **영구히** 안 채워지는 사건에서 신고 자체를 막는다는 점이 결정적입니다.

**발생장소가 신고요건상 「필요」라는 반대 근거는 취소되지 않습니다.** 다만 그 무게를 **Package 미발행**이 지는 것이 아니라 `report_field_states`·`unconfirmed_fields`·notice가 지도록 옮깁니다 — 신유민 님이 C-1에서 정리한 구조와 같습니다. 신고요건 규칙이 바뀌므로 주간 회의에 보고합니다(§8).

**제품 Must/Won't는 건드리지 않습니다.** ①은 `product-spec.md` §5(Won't)·§7(불변 경계) 어느 줄도 바꾸지 않습니다 — 값을 지어내지 않고, 자체 지도 UI를 두지 않고, 최종 핀은 안전신문고에서 사용자가 찍는다는 세 줄이 그대로입니다. 오히려 ②가 「GPS 없음은 오류가 아니다」와 멀어집니다. 따라서 B-1(Product Spec 변경 권한) 경로는 발동하지 않고, 이 결정은 계약·정책·rule catalog 층에서 닫힙니다.

**④(한 번 묻고 나서 정한다)는 여기서 닫지 않습니다.** ①이 서면 U가 막다른 끝이 아니게 되어 시급하지 않고, 선택적 위치 질의는 `case` orchestration 소유라 이 이슈에서 함께 정하면 결정 단위가 섞입니다. **통합(I2·I5)이 자동으로 덮지 않는 항목**이라 — I5는 「D1 결론 반영」만 합니다 — `10_first-completion_decisions_and_integration_2026-09-13.md`의 후속 결정표에 **새 항목으로 등록**하고, 열리는 조건은 별도로 정합니다.

## 2. Q2 — `location: null`, 그리고 「부재는 확정 사실」을 계약에 같이 박습니다

`report-package/v1.1` §7 개정안입니다.

```
location: {
    display_text: string
    search_keyword?: string
} | null
```

여기에 문구를 붙입니다.

> `location` 키는 생략하지 않는다. `null`은 **「위치 정보가 없다는 확정된 사실」**을 뜻하며 「아직 오지 않은 값」이 아니다. `{display_text: null, …}` 형태는 쓰지 않는다.

신유민 님이 §4 방어 규칙을 들어 「키 생략이 가장 위험하다」고 하신 지적을 생산 쪽 계약에서 막는 문장입니다. 두 상태가 화면에서 섞이지 않게 하려면 **생산자가 애초에 그 모양을 못 만들게** 하는 쪽이 맞다고 봅니다.

**조건 수용 — `report_field_states.location` 필수 존재.** 다만 그 줄이 들어갈 곳은 `contract-job-record-case-view.md`(case·web 공동 소유)라 제가 쓰지 않습니다. 유소연 님께 요청드립니다. 제 쪽에서는 그 조건의 근거가 되는 위 한 줄을 `report-package/v1.1`에 넣습니다. v5 fixture가 이미 그 모양인 것은 저도 직접 확인했습니다(`{info_state: INFO_UNKNOWN, source_label_key: null}` · `unconfirmed_fields`에 `location` · `warnings: []`).

### 정정 — 제 이슈 §5 Q3의 전제

「사용자는 위치가 비어 있다는 사실을 빈칸으로만 마주친다」는 틀렸습니다. rev4를 다시 열어 확인했고 신유민 님 A절 표가 맞습니다. 완료 조건 다섯 번째(「CaseView에서 관찰 가능」)는 **이미 충족**이고, 남은 빈 자리는 C-2가 가리킨 쪽입니다.

## 3. Q3 — 모양 동의. 문구는 C-2로, 발동 조건은 「검색어 없음」으로 좁힙니다

`actions: []`에 동의합니다. `readout.overlay_not_present`가 rev4 `notices[]`에 이미 그 모양으로 들어 있는 것도 확인했습니다.

**기준을 채택합니다 — 제품 안에 실행 경로가 있으면 `action`, 없으면 문구.** #31 W-6(`case.report_video_not_generated`)과의 차이를 이렇게 적어두자는 제안 그대로 받습니다. 따라서 **`notices[].actions[]`는 확장하지 않습니다.** 제 이슈 §6 제안 4번의 「필요하면 확장을 같은 결정에 포함」은 철회합니다.

**문구는 C-2를 받습니다.** notice가 나를 것은 「위치를 확보하지 못했다」가 아니라 「지도에 붙여넣을 검색어를 제공하지 못한다 — 기억나는 장소를 직접 검색해야 한다」입니다.

**그래서 발동 조건도 `location`이 아니라 `search_keyword`로 잡는 것이 맞습니다.** `location_display.search_keyword == null`입니다. h001은 `display_text`가 사용자 기억 문장뿐이어도 `search_keyword`가 있어 §21 복사 경로가 성립하므로 이 notice 대상이 아닙니다. 반대로 「위치 부재」를 조건으로 잡으면 §21이 실제로 깨지는 지점과 어긋납니다.

같은 이유로 code 이름 `case.location_not_secured`는 의미와 어긋납니다 — 「확보하지 못했다」는 `INFO_UNKNOWN`이 이미 말하는 사실입니다. 이름과 `message_key` 모두 **검색어 부재** 쪽으로 잡아주시길 제안합니다. 확정은 `case` 소유라 제가 정하지 않습니다.

§21 복사 버튼 비렌더는 신유민 님 판단대로 별도 결정이 필요 없습니다.

## 4. Q4 — 발동하지 않습니다

①이므로 `pkg_u001`·`req_u001_final`·rev4는 그대로 둡니다. §13의 「WARN + 사용자 notice가 있는 Package」 최소 케이스도 u001이 계속 맡고, Q3 notice가 붙으면 오히려 그 항목에 더 정확히 맞습니다.

두 분이 전수로 확인해 주신 「이 조합은 u001 하나뿐」은 이번 결정으로 해소되지만 **단일점으로 남습니다.** `scenario_blocked_001`이 없어 BLOCK 경로를 못 그리는 것과 같은 자리입니다. 이 이슈에서 닫지 않고 별도 항목으로 옮깁니다.

## 5. 제가 하는 것 (`evidence`)

1. **계약 `report-package/v1 → v1.1`** — §7 nullable + 위 「부재는 확정 사실」 문구, §8.2의 「location display/search 정보」가 **없으면 없다는 사실까지** 포함하도록 문구 보강. §14의 「handoff snapshot 필수/선택 의미 변경」에 해당하므로 version 증가 + ADR.
2. **신고문 정책 `safety-report-policy/v1 → v1.1`** — 장소 슬롯 없는 template 변형을 **별도 `template_ref`로 등록**하고, Renderer 불변조건 2의 입력 슬롯에서 `location.display_text`를 선택으로 내립니다. 불변조건 5(확인하지 않은 내용 추가 금지)는 그대로라 장소 구절은 **지어내지 않고 뺍니다.** §14가 template 내용 변경을 contract version 증가 대상에서 빼두었으므로 1번과 PR을 분리합니다.
   - 확인된 사실 하나 보탭니다. **`pkg_u001.report.description`은 지금 `tmpl/safety-report-generic-v1`의 출력이 아닙니다** — 장소 구절이 빠져 있고 문장도 다른데 `template_ref`는 generic-v1을 가리킵니다. `template_ref`로 재현되지 않는 상태라 불변조건 1·4 위반이고, 변형 template이 등록되면 fixture의 `template_ref`도 함께 바뀌어야 합니다. ①이 아니었어도 손봐야 했던 자리입니다. 이 동기화는 이미 **통합 항목 I2**(「H/U 제목·본문·`template_ref`·`policy_ref`를 `safety-report-policy/v1`과 동기화」)가 덮고 있으므로 새 항목을 만들지 않고 I2에서 처리합니다 — 다만 I2의 기준이 되는 template이 이번 정책 개정으로 바뀌므로 **순서는 정책 v1.1 → I2**입니다.
3. **rule catalog revision** — `package.location.present`의 `display_location_absent`를 `UNKNOWN → WARN`. **여기에 하나가 더 필요합니다.** `package.report.content_length`의 `render_required_inputs`에 `package_display_location`이 들어 있어, 이대로 두면 U가 `render_inputs_incomplete → UNKNOWN`이 되고 §8.1(「`overall=UNKNOWN`이면 Package 없음」)로 **①을 정해도 Package가 다시 사라집니다.** 필수 입력을 **선택된 template 기준**으로 읽도록 같은 revision에서 고칩니다. v2는 아직 미발행이라 발행 전에 반영합니다.
4. **구현** — `requirements.py`의 `PackageNotReady("package.input.location_missing")` 제거, `validation.py`의 「`location` 필수 + 비어 있지 않은 문자열」을 「키 필수 + `null` 허용」으로. `validate_report_package(pkg_u001) → []`를 확인해서 올립니다.
5. **공용 `validate_mock_pack.py` 보강** — `report_inputs` 내부 모양까지 검사해 같은 종류의 위반이 다시 조용히 통과하지 않게. 공용 파일이라 PR로 올리고 두 분께 리뷰 요청드립니다.
6. **test** — 위치 없는 U가 장소 값을 지어내지 않고 렌더되는지(불변조건 5).

**PR 구성.** 1~4·6은 **PR 하나로 올립니다.** 계약만 먼저 병합되면 `develop`이 자기모순 상태가 됩니다 — 계약은 `location: null`을 허용하는데 구현은 여전히 거부하고 catalog는 `UNKNOWN`을 내서 Package가 안 나오는 구간이 생깁니다. 그 사이에 `develop` 기준으로 작업하시면 틀린 기준에 맞추게 됩니다. §14 등급 구분(계약 개정 / template 변경)은 커밋 스코프로 남깁니다.

**5번(공용 `validate_mock_pack.py` 보강)만 따로, 그리고 나중에 냅니다.** 검사를 넣는 순간 `pkg_u001`이 걸리는데 그 fixture 동기화는 I2(유소연 님)이라, 같은 PR에 넣으면 제 PR이 그 작업을 기다리게 됩니다. **I2 이후에 별도 PR로 올립니다** — I2 타이밍을 잡으실 때 참고해 주세요.

그리고 이 답변 직후에 **현재 `evidence` 브랜치를 먼저 올립니다.** 이슈 본문에서 「PR 병합 이후 열람 가능」이라고 안내한 ADR·`src/daesingo/evidence/**`가 거기 있습니다. 신유민 님이 「ADR 원문은 아직 `develop`에 없어 대조하지 못했다」고 하신 §5.6·§5.11도 그 PR이 들어가면 열립니다.

## 6. 두 분 몫

- **유소연 님** — (a) `report_field_states.location` 필수 존재 한 줄을 `contract-job-record-case-view.md`에(신유민 님 B절 조건), (b) notice code 등재 — 이름·`message_key`는 C-2 의미로, 발동 조건은 `search_keyword == null`, (c) `_build_package_view()`·`_field_states()` 방어(`location` 값이 `null`인 경우와 `EvidenceRecord`에 키 자체가 없는 경우 **둘 다**).
- **신유민 님** — 등재된 code에 문구 매핑, §21 복사 버튼 비렌더. 추가로 요청드릴 것은 없습니다.

## 7. 완료 조건 갱신

- [x] ①~④ 중 하나가 선택되고 근거가 기록됨 → **①**
- [ ] 계약 개정(version + ADR)과 「위치 없음」의 직렬화 모양 → 모양은 `location: null`로 **확정**, 개정 PR 남음
- [ ] 장소 슬롯 없는 신고문 규칙 + 지어내지 않는다는 test
- [x] ②면 fixture 재구성 → **해당 없음**
- [x] 위치 부재가 `CaseView`에서 관찰 가능 / 필요한 `actions[]` 값 → **이미 충족**, `actions[]` 확장은 **불필요**로 결론(C-1)
- [ ] evidence 발행 여부와 `case`/`web` 표시가 하나의 결정으로 일치 → 결정은 일치, 각 모듈 반영 남음
- [ ] `validate_report_package(pkg_u001)` → `[]`
- [ ] `validate_mock_pack.py` 보강
- [ ] K3 v2 재실행 결과가 결정과 일치 → §5-3의 `content_length` 수정 포함

## 8. 주간 회의 보고 — 왜 하는가

이 결정은 **신고요건 규칙 변경**입니다(`package.location.present`의 outcome 매핑, 그리고 신고문 template). 그래서 이번 주 회의 안건에 올립니다.

**승인을 받으러 가는 절차가 아닙니다.** 기획 1.3에는 「Evidence Rule / 신고요건 변경은 만든 사람이 아닌 평가·QA 담당자가 서명한다」는 규칙이 있었는데, `evidence` Owner가 저(PM)라 구현과 승인이 한 사람에게 겹칩니다. 팀은 **별도 서명자를 두지 않는 대신** 조건 하나를 붙여 이 항목을 닫았습니다(`cross-cutting-decisions.md` §B-3).

> 1.3의 서명자 분리를 두지 않는다. 이유: `evidence`는 아무도 호출하지 않는 순수 함수 모듈이라 규칙 변경이 테스트로 즉시 검증되고, 6인 팀에 별도 검토자를 뺄 여유가 없다. **대신 신고요건 규칙이 바뀌면 주간 회의에 보고한다.**

규칙 변경 권한은 evidence Owner가 겸하는 것으로 이미 닫혀 있으므로, 이 보고는 결정을 되돌리거나 재승인받는 자리가 아니라 **겸임의 이해 상충을 완화하려고 붙여둔 의무의 이행**입니다. 안건에서 다룰 것은 위 §0 확정표와 §5의 revision 범위입니다.

## 9. 이 이슈 밖으로 옮기는 것 — 어디에 등록하는가

「별도 항목」이라고만 적으면 열리지 않으므로 등록처를 같이 적습니다.

| 남기는 것 | 통합(I2·I5)이 덮는가 | 등록처 |
| --- | --- | --- |
| **④ 선택적 위치 질의 경로** | **아니오.** I5는 D1 결론 반영만 하고, ④는 `case`의 새 사용자 흐름이라 별도 제품 결정이 필요합니다 | `10_first-completion_decisions_and_integration` 후속 결정표에 새 항목. **여는 조건은 C-1 사용자 검증 관찰 결과**(아래) |
| **`WARN` Package 최소 케이스가 u001 단일점** | **아니오.** fixture 커버리지 문제라 ① 반영과 무관합니다 | `scenario_blocked_001` 부재(= `BLOCK` 경로를 목데이터로 못 그림)와 같은 묶음으로 Mock 커버리지 항목에 등록 |
| **`pkg_u001`의 신고문이 `template_ref`와 불일치** (`report.description` · `report_inputs.violation_expression`) | **예 — 이미 I2가 덮습니다.** 새 항목을 만들지 않습니다 | 통합 항목 **I2**. 단 기준 template이 이번 정책 개정으로 바뀌므로 순서는 **정책 v1.1 → I2** |

### ④를 여는 조건 — 지금 열지 않습니다

①이 확정되면서 ④의 성격이 바뀌었습니다. 원래는 「막다른 끝을 막는 안전장치」였는데, 이제 U도 Package를 받고 Q3 notice로 「붙여넣을 검색어가 없으니 직접 검색해야 한다」를 듣습니다. 남는 것은 **묻는 시점을 앞당기는 편의**뿐입니다.

그래서 지금 스펙을 정하지 않고, **C-1(Product Validation) 관찰 항목에 걸어둡니다.**

> 관찰 항목: `search_keyword`가 없는 case에서 사용자가 안전신문고 지도 앞에서 실제로 무엇을 하는가.

관찰에서 사용자가 막히면 ④를 열고, 넘어가면 열지 않습니다. 근거 셋입니다.

1. **핵심 UX 판단 — 사용자가 해야 할 행위가 이미 적지 않습니다.** 차량번호 확인·신고 상황 확인·안전신문고 재입력이 이미 있고, 줄일 수 있으면 줄이는 쪽이 맞습니다. ④는 **행위를 하나 더 늘리는 방향**이라, 늘릴 만하다는 근거가 관찰로 나오기 전에는 넣지 않습니다.
2. **추측으로만 판단되는 항목입니다.** 미리 물었을 때 사용자가 실제로 답하는지, 아니면 안전신문고 지도에서 찍는 편이 쉬운지는 관찰 없이 알 수 없습니다.
3. **나중에 열어도 계약 신설이 아닙니다.** `contract-correction-record.md` §6의 닫힌 10개 semantic path에 `location.user_hint`가 이미 있습니다. ④는 계약 개정이 아니라 `case` 흐름 추가라 미루는 비용이 낮습니다.

MVP Won't로 **닫지는 않습니다.** ④는 선택적 경로라 §19와 충돌하지 않아 닫을 근거가 없고, 관찰 결과가 반대로 나오면 되돌리는 절차(B-1)가 추가로 붙습니다.

이슈는 위 PR들이 병합될 때까지 열어둡니다.
