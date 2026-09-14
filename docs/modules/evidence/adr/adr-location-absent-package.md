# ADR-EVIDENCE-003: 위치를 확보하지 못한 사건의 `ReportPackage` 발행 (D1)

> 상태: **ACCEPTED**
>
> 결정일: `2026-09-14`
>
> Decider / Owner: 김준영 (`evidence` Owner · `report-package/v1` Contract Owner · PM)
>
> Consulted: 유소연 (`case`) · 신유민 (`readout`·`web`) — [이슈 #48](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/48)
>
> 적용 범위: `report-package/v1` 위치 필드, 신고문 template registry, 적용 rule catalog, `evidence` 구현
>
> 근거 목록: [`reviews/12_u-package-location-nullability_issue-draft_2026-09-13.md`](../reviews/12_u-package-location-nullability_issue-draft_2026-09-13.md) · [`reviews/10_first-completion_decisions_and_integration_2026-09-13.md`](../reviews/10_first-completion_decisions_and_integration_2026-09-13.md) D1(Q1) · [`ADR-EVIDENCE-002`](adr-first-completion-owner-decisions.md) §5.6·§5.8·§5.11

## 1. 목적

GPS도 없고 사용자도 위치 단서를 준 적이 없는 사건에서 **신고자료를 내줄 것인가 보류할 것인가**를 확정한다. [`ADR-EVIDENCE-002`](adr-first-completion-owner-decisions.md) §5.6이 「K3가 D1을 단독으로 종결하지 않는다」로 열어둔 항목이고, §5.14의 남은 미결 목록에 등재돼 있던 항목이다.

## 2. 배경

### 2.1 네 곳이 서로 다른 답을 전제하고 있었다

| | 위치 없는 U에서 Package는 | 근거 |
| --- | --- | --- |
| Final `report-package/v1` §7 | **불가** — `location{display_text: string}` 필수 | 계약 스키마 |
| `evidence` 구현·baseline | **보류** — `PackageNotReady("package.input.location_missing")` | `requirements.py` |
| 공용 Mock `pkg_u001` | **발행** — `report_inputs.location = null` | `data/mock/evidence/…` |
| 공용 Mock `CaseView` u001 rev4 | **발행** — `stage=READY`, `package_ref=pkg_u001` | `data/mock/case/…` |

`validate_report_package(pkg_u001)`은 `['location']`을 돌려주는데 공용 `validate_mock_pack.py`는 `VALIDATION PASSED`를 낸다. 공용 검사가 `report_inputs` **키의 존재만** 보고 내부 모양을 보지 않기 때문이다.

### 2.2 U는 「못 찾은」 사건이 아니라 「아무도 묻지 않은」 사건이다

- `recording` GPS: `status=UNKNOWN`, `reason.code="recording.gps.source_absent"`
- `case` intake: `hints.location = null` — 사용자가 위치 단서를 준 적이 없다
- `ev_u001`에는 `location` 키 자체가 없다
- `CaseView` u001 rev4: `location_display.info_state=INFO_UNKNOWN`, `coord`·`search_keyword` 모두 `null`, `unconfirmed_fields`에 `location` 포함

이 구분이 아래 결정에 직접 들어간다. 값을 찾다 실패한 것이 아니라 처음부터 입력이 없었다.

## 3. 결정 상태

| ID | 항목 | 상태 |
| --- | --- | --- |
| D1 | 위치 없는 WARN Package를 발행한다 | **ACCEPTED** |
| D1-a | 「위치 없음」의 직렬화 모양 — `location: null` | **ACCEPTED** |
| D1-b | `report-package/v1 → v1.1` 개정 범위 | **ACCEPTED** |
| D1-c | 장소 슬롯 없는 신고문 template | **ACCEPTED** |
| D1-d | rule catalog revision 2건 | **ACCEPTED** |
| D1-e | 사용자 고지의 경계 — `evidence`가 정하지 않는 것 | **ACCEPTED** |
| D1-f | ④(선택적 위치 질의)는 열지 않고 관찰 조건에 건다 | **DEFERRED** |

## 4. 근거

### 4.1 제품·구조 문서 세 곳이 발행 쪽을 가리킨다

- [`core-user-flow.md`](../../../product/core-user-flow.md) §19 — 사용자에게 확인을 요구하는 항목은 차량번호·신고 상황 둘뿐이고 위치는 요구하지 않는다. 같은 절이 「GPS가 없어 제품 안에서 완료할 수 없는 정보를 실패 상태로 표시하지 않는다」를 이미 정했다.
- [`module-architecture.md`](../../../architecture/module-architecture.md) §8-3 — 「GPS 없음 → 나머지 Evidence는 살아 있음 → **위치 미확인, 오류 아님**」.
- [`product-spec.md`](../../../product/product-spec.md) §7 — 값을 만들어내지 않고 상태를 보여준다. 보류는 이 경계를 지키는 유일한 방법이 아니다.

보류를 택하면 「오류 아님」으로 적힌 상황이 사용자 화면에서 막다른 끝이 된다.

### 4.2 두 Consumer Owner의 답변

- **유소연(`case`)** — ①. §19의 「검증할 방법이 없는 정보에 확인을 강요하지 않는다」는 값이 *부재*한 경우에 더 강하게 적용된다. 위치가 영구히 확보되지 않는 사건(고속도로 무명 구간 등)에서 보류는 신고 자체를 막는다. `pkg_u001`·rev4가 이미 발행 모양이라 ②는 동작 중인 것을 되돌리는 비용이 든다.
- **신유민(`readout`·`web`)** — Q1에는 의견을 내지 않고 비용만 보고. `unknown_abstain_partial_001` rev4는 「`WARN`인데 제출 경로는 열려 있고 미확정은 `report_field_states`가 나른다」를 검증하는 유일한 스냅샷이다. `BLOCK` 경로는 이미 fixture가 없어 못 그린다. ②를 고르면 목데이터로 검증할 수 없는 화면이 둘로 는다.

### 4.3 반대 근거는 취소되지 않고 자리를 옮긴다

[`ADR-EVIDENCE-002`](adr-first-completion-owner-decisions.md) §5.11이 발생장소를 두 신고유형 모두 「필요」로 등재하고 있다. 이 사실은 그대로다. 다만 그 무게를 **Package 미발행**이 지지 않고 `report_field_states`·`unconfirmed_fields`·사용자 고지가 진다. 안전신문고 제출 완료 여부는 제품이 보증하는 범위가 아니며([`safety-report-policy-v1.md`](../decisions/safety-report-policy-v1.md) Renderer 불변조건 6), 자료 준비 단계에서 미확정을 숨기지 않는 것으로 책임을 다한다.

### 4.4 제품 Must/Won't는 바뀌지 않는다

이 결정은 `product-spec.md` §5(Won't)·§7(불변 경계) 어느 줄도 바꾸지 않는다. 값을 지어내지 않고, 자체 지도 UI를 두지 않으며, 최종 핀은 안전신문고에서 사용자가 찍는다. 따라서 `cross-cutting-decisions.md` B-1(Product Spec 변경 권한) 경로는 발동하지 않고, 계약·정책·rule catalog 층에서 닫힌다.

## 5. 결정

### 5.1 D1 — 위치 없는 `WARN` Package를 발행한다

위치가 확보되지 않았다는 이유만으로 `ReportPackage` 발행을 보류하지 않는다. 다른 신고요건이 충족되면 위치 없이도 Package를 만들고, 위치는 미확정 상태로 표시한다.

`evidence`는 위치의 진위를 판정하지 않는다. 주입된 `EvidenceRecord.location`으로 rule을 적용하고 발행 여부만 정책으로 정한다.

### 5.2 D1-a — 「위치 없음」은 `location: null`이다

```
location: {
    display_text: string
    search_keyword?: string
} | null
```

- **키를 생략하지 않는다.** `location`은 항상 존재한다.
- `null`은 **「위치 정보가 없다는 확정된 사실」**을 뜻하며 「아직 오지 않은 값」이 아니다.
- `{display_text: null, search_keyword?: null}` 형태는 쓰지 않는다.

세 후보 중 `null`을 고른 이유는 셋이다. `CaseView.package.report_fields`가 이미 `object<string, string|null>`이라 어떤 모양이든 결국 `string|null`로 평평해진다(유소연). 빈 객체는 「객체는 있는데 내부가 비었다」는 **다른 사실**을 뜻하게 되는데 U는 위치 정보 자체가 없는 case다. 키 생략은 `web`의 방어 규칙(「키가 없거나 `info_state`가 비면 배지를 붙이지 않고 `INFO_SOURCE_VERIFIED`로 간주하지 않는다」)과 겹치는데, 그 규칙은 **「아직 안 온 값」**을 위한 것이라 확정된 부재와 화면에서 섞인다(신유민).

세 번째 이유가 「키 생략 금지」를 계약 문구로 박는 근거다. 생산자가 애초에 그 모양을 만들지 못하게 한다.

### 5.3 D1-b — `report-package/v1 → v1.1`

| 절 | 변경 |
| --- | --- |
| §7 | `report_inputs.location`을 nullable로 개정하고 위 §5.2의 세 문장을 규범으로 붙인다 |
| §8.2 | 최소 snapshot의 「location display/search 정보」가 **없으면 없다는 사실까지** 포함함을 명시한다 |

[`contract-requirement-report-package.md`](../../../architecture/contracts/contract-requirement-report-package.md) §14가 「handoff snapshot 필수/선택 의미 변경」을 Contract version 증가 + ADR 대상으로 등재하고 있어 `v1 → v1.1`이다. 같은 절이 **「template 내용 변경」은 version 증가 대상에서 제외**하므로 §5.4는 별도 정책 version으로 관리한다.

### 5.4 D1-c — 장소 슬롯 없는 신고문 template

[`safety-report-policy-v1.md`](../decisions/safety-report-policy-v1.md)의 template 2종은 모두 본문에 `{발생장소}` 슬롯을 쓴다. 장소 없이 렌더할 수 있는 template이 registry에 없다.

- `safety-report-policy/v1 → v1.1`을 발행하고 **장소 구절이 없는 변형을 별도 `template_ref`로 등재**한다. 기존 2종을 덮어쓰지 않는다.
- Renderer 불변조건 2의 입력 슬롯에서 `location.display_text`를 **선택**으로 내린다.
- 불변조건 5(사용자가 확인하지 않은 내용을 문장에 추가하지 않는다)는 그대로다. 장소 구절은 **지어내지 않고 뺀다.**
- 기존 Package의 `template_ref`·`policy_ref`는 유지한다. v1이 「SafetyReportType registry」 절에서 이미 같은 원칙을 쓰고 있다.

**확인된 불일치 1건.** `pkg_u001.report.description`은 현재 `tmpl/safety-report-generic-v1`의 출력이 아니다 — 장소 구절이 없고 문장도 다른데 `template_ref`는 generic-v1을 가리킨다. `template_ref`로 재현되지 않는 상태이며 Renderer 불변조건 1·4 위반이다. 변형 template이 등재되면 fixture의 `template_ref`도 함께 바뀌어야 한다. 이 동기화는 [`10_…`](../reviews/10_first-completion_decisions_and_integration_2026-09-13.md) 통합 항목 **I2**가 이미 덮으므로 새 항목을 만들지 않는다. 순서는 **정책 v1.1 → I2**다.

### 5.5 D1-d — rule catalog revision 2건

`policy/requirement-rules-v2`를 덮어쓰지 않고 새 revision을 발행한다([`ADR-EVIDENCE-002`](adr-first-completion-owner-decisions.md) §7).

| rule | v2 | 새 revision |
| --- | --- | --- |
| `package.location.present` | `display_location_absent: UNKNOWN` | `display_location_absent: WARN` |
| `package.report.content_length` | `render_required_inputs`에 `package_display_location` 포함 → 위치 없으면 `render_inputs_incomplete: UNKNOWN` | 필수 입력을 **선택된 template 기준**으로 읽는다. 장소 슬롯이 없는 template을 고르면 위치는 필수 입력이 아니다 |

**두 번째가 없으면 D1이 무효가 된다.** `content_length`가 `UNKNOWN`이면 overall precedence(`BLOCK > UNKNOWN > WARN > PASS`)에 따라 `FINAL_PACKAGE` overall이 `UNKNOWN`이 되고, 계약 §8.1(「`overall=UNKNOWN`이면 Package가 없다」)로 Package가 다시 사라진다. 두 rule은 한 revision에서 함께 바뀐다.

`evidence.location.present`(EVIDENCE scope)는 v2에서 이미 `no_location_value: WARN`이라 바꾸지 않는다.

### 5.6 D1-e — 사용자 고지의 경계

위치가 비었다는 사실을 사용자에게 말하는 것은 필요하다. 다만 **그 표현은 `case`·`web`이 소유하고 이 ADR이 정하지 않는다.** `evidence`가 사용자에게 직접 묻거나 말하지 않는다.

`evidence` Owner로서 이슈 #48에서 동의한 경계는 다음과 같으며, 확정 권한은 `case`에 있다.

- `notices[].actions[]`는 **확장하지 않는다.** 제품 안에 실행 경로가 있으면 `action`, 없으면 문구다. 최종 위치 핀은 안전신문고 소관이라(`core-user-flow.md` §21) `case` 안에 고칠 방법이 원래 없다.
- 고지가 나를 사실은 「위치를 확보하지 못했다」가 아니다. 그것은 `info_state=INFO_UNKNOWN`이 이미 말한다. 실제로 깨지는 것은 §21의 「검색어를 복사해 지도 검색창에 붙여넣는다」 경로이며, U는 `search_keyword`·`coord`가 모두 `null`이라 붙여넣을 것이 없다.
- 따라서 발동 조건은 `location` 부재가 아니라 **`search_keyword` 부재**다. `pkg_h001`은 `display_text`가 사용자 기억 문장뿐이어도 `search_keyword`가 있어 복사 경로가 성립하므로 대상이 아니다.

### 5.7 D1-f — ④(선택적 위치 질의)는 열지 않는다 (DEFERRED)

D1이 ①로 정해지면서 ④의 성격이 「막다른 끝을 막는 안전장치」에서 「묻는 시점을 앞당기는 편의」로 바뀌었다. 지금 스펙을 정하지 않고 **C-1(Product Validation)의 관찰 항목**에 건다.

> 관찰 항목: `search_keyword`가 없는 case에서 사용자가 안전신문고 지도 앞에서 실제로 무엇을 하는가.

- 사용자가 이미 해야 하는 행위(차량번호 확인·신고 상황 확인·안전신문고 재입력)가 적지 않다. ④는 행위를 하나 더 늘리는 방향이라, 늘릴 만하다는 근거가 관찰로 나오기 전에는 넣지 않는다.
- 나중에 열어도 계약 신설이 아니다. [`contract-correction-record.md`](../../../architecture/contracts/contract-correction-record.md) §6의 닫힌 10개 semantic path에 `location.user_hint`가 이미 있다.
- MVP Won't로 **닫지도 않는다.** ④는 선택적 경로라 §19와 충돌하지 않아 닫을 근거가 없고, 관찰 결과가 반대로 나오면 되돌리는 절차(B-1)가 추가로 붙는다.

### 5.8 `ADR-EVIDENCE-002`에 대한 변경

**K3(§5)가 여러 곳에서 위치 판정을 전제하고 있어 영향 범위가 넓다.** 전수로 확인한 결과는 다음과 같다.

| 위치 | 변경 |
| --- | --- |
| §2 결정 상태 | D1 종결과 영향 범위를 안내한다 |
| §5.4 `EVIDENCE` 기본 rules | 「`FINAL_PACKAGE`에서는 같은 사실을 `UNKNOWN`으로 **다르게** 판정한다」가 무효가 된다. 두 scope가 이제 같은 `WARN`이다. EVIDENCE scope 매핑 자체는 불변 |
| §5.6 무조건 rule 표 | `package.location.present` 행의 `UNKNOWN` → `WARN`. `package.report.content_length` 행에 template 기준 단서 |
| §5.6 「위치 — D1 미결과의 관계」 | 종결 표시. v2 당시 판단은 보존한다 |
| §5.8 렌더 필요 입력 목록 | 「Package 표시용 위치」를 선택된 template 기준으로 읽는다 |
| §5.11 신고유형별 필수성 | 발생장소 「필요」는 사실로 유지하되 그 무게를 Package 미발행이 지지 않음을 명시 |
| §5.12 rule 실행 실패 | **「Package 표시용 위치가 아직 없음」이 `UNKNOWN` 목록에서 빠진다.** 이 절이 원래 두지 않았던 네 번째 갈래(`WARN`)를 명시한다 |
| §5.14 확인 상태 표 | catalog 식별자를 덮어쓰지 않는다는 점, rule 수는 그대로(15)라는 점 |
| §5.15 구현·검증 영향 | `content_length` 항목에 template 기준 단서 |
| §5.15 Artifact 영향 | **정정.** 원문은 U가 `UNKNOWN`으로 떨어져 Package가 사라지는 상태를 전제로 쓰였다. D1 반영 후에는 U가 `WARN`이고 `PACKAGE_READY`가 성립한다. **D1 반영이 Artifact 재실행보다 먼저**여야 한다 |
| §5.15 남은 미결 목록 | 「D1(Q1) 위치 결론」을 이 ADR로 종결 처리 |

**K1·K2·K4는 영향을 받지 않는다.** 확인한 근거는 다음과 같다.

- **K1**(첨부 용량·개수)·**K2**(신고기한)의 입력은 AssetFacts와 `occurred_at`이며 위치를 읽지 않는다.
- **K4**는 §6.9가 `case.user_location_hint`와 `location.user_hint` correction을 명시적으로 다루지만, 그것은 **값이 있을 때의 provenance**이고 D1은 **값이 없을 때의 발행 여부**다. 위치가 부재하면 `EvidenceValue` 자체가 없어 K4의 확장 대상이 아니다. ④를 `DEFERRED`로 둔 결과 새 위치 입력 경로도 생기지 않으므로 §6.9의 경계는 그대로 유지된다.

## 6. 검토한 대안

| 대안 | 기각 이유 |
| --- | --- |
| **② 위치가 생길 때까지 Package 미발행** | §4.1의 문서 세 곳과 정면 충돌한다. 위치 하나 때문에 신고영상·번호판·신고문이 모두 준비된 case를 통째로 보류시킨다. 위치가 영구히 확보되지 않는 사건에서 신고 자체를 막는다. 공용 fixture에서 `WARN` Package 최소 케이스와 `web` 규칙 7 검증 스냅샷이 동시에 사라진다 |
| **③ Package 전에 위치 입력 필수화** | `core-user-flow.md` §19와 정면 충돌한다(위치는 확인을 요구하지 않는 항목) |
| **④ 한 번 묻고 답이 없으면 ① 또는 ②** | 기각이 아니라 보류. §5.7 |
| **placeholder 주소·임의 좌표** | 선택지가 아니다. `product-spec.md` §7 |
| **`{display_text: null}` 빈 객체 / 키 생략** | §5.2 |

## 7. 결과와 trade-off

### 긍정적 결과

- 계약·구현·공용 fixture·`CaseView`가 **하나의 답**을 갖는다. `validate_report_package(pkg_u001)`과 `validate_mock_pack.py`가 같은 방향을 보게 된다.
- 「GPS 없음은 오류가 아니다」가 사용자 화면까지 일관되게 내려간다.
- `unknown_abstain_partial_001` rev4가 유지되어 `contract-requirement-report-package.md` §13의 「`WARN` + 사용자 notice가 있는 Package」 최소 케이스와 `web` 규칙 7 검증 스냅샷이 보존된다.

### 감수하는 비용과 한계

- Contract version이 하나 올라간다(`v1 → v1.1`). 계약 한 줄로 끝나지 않고 template·catalog·구현이 같은 결정에 묶인다.
- 발생장소 없이 준비된 자료로 사용자가 안전신문고 제출을 완료하지 못할 수 있다. 제품은 그 사실을 숨기지 않는 것까지만 한다.
- `WARN` Package 최소 케이스가 여전히 `unknown_abstain_partial_001` **하나**다. 이 결정으로 해소되지 않는 단일점이며 `scenario_blocked_001` 부재와 같은 자리다.

## 8. 이 ADR이 결정하지 않는 것

- `CaseView`의 `report_field_states.location` 필수 존재 문구 — `contract-job-record-case-view.md`(`case`·`web` 공동 소유). 신유민의 조건을 지지하며 등재는 `case`가 한다
- 사용자 고지의 code 이름·`message_key`·문구 — `case` 소유(§5.6)
- 공용 `data/mock` fixture 재렌더 — 통합 항목 I2(`case`)
- 공용 `validate_mock_pack.py` 보강의 시점 — I2 이후
- 자체 지도 UI, 좌표 역지오코딩, 주소 정규화 (`product-spec.md` §5 Won't)
- `report-package/v1`의 `location`에 `coord`를 추가할지 — 이 문제와 별개이며 필요하면 따로 연다
- 위치 이외 필드(`occurred_at`·`safety_report_type`)의 미확정 처리

## 9. 검증

반영 후 다음을 확인한다.

| 확인 | 기대 |
| --- | --- |
| `validate_report_package(pkg_u001)` | `[]` |
| U의 `FINAL_PACKAGE` overall | `WARN` 유지 — `package.location.present=WARN`, `package.report.content_length`는 `UNKNOWN`이 아님 |
| `PACKAGE_READY` | 성립(`overall ∈ {PASS, WARN}` + Package 존재) |
| 장소 없는 신고문 | 장소 구절이 빠질 뿐 값이 지어내지지 않는다 — test로 고정 |
| `template_ref` | 렌더 결과가 `template_ref`로 재현된다(불변조건 1·4) |
| 공용 `validate_mock_pack.py` | `report_inputs` 내부 모양까지 검사한다 (I2 이후) |

## 10. 변경 규칙

- `report-package/v1.1`의 위치 의미를 다시 바꿀 때 v1.1을 덮어쓰지 않고 새 version과 ADR을 남긴다.
- template 변형을 바꿀 때 `safety-report-policy/v1.1`을 덮어쓰지 않고 새 policy version을 발행한다. 기존 Package의 `template_ref`는 보존한다.
- rule catalog는 `policy/requirement-rules-v2`를 덮어쓰지 않고 새 revision을 발행한다.
- ④를 열 때 이 ADR을 수정하지 않고 새 결정으로 기록한다.
- `case`·`web` 소유 항목(§8)은 이 ADR에서 확정하지 않는다.

## 11. 보고

이 결정은 신고요건 규칙 변경(`package.location.present` 매핑과 신고문 template)이다. [`cross-cutting-decisions.md`](../../../management/cross-cutting-decisions.md) §B-3이 별도 서명자를 두지 않는 대신 「신고요건 규칙이 바뀌면 주간 회의에 보고한다」를 조건으로 달아 두었으므로 주간 회의 안건에 올린다. 승인 절차가 아니라 겸임의 이해 상충을 완화하기 위한 보고다.

## 12. 관련 문서와 증빙

- [이슈 #48](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/48) — 질문 본문, 두 Owner 답변, 확정 답변
- [`reviews/12_u-package-location-nullability_issue-draft_2026-09-13.md`](../reviews/12_u-package-location-nullability_issue-draft_2026-09-13.md) — 원본 초안, 재검토, 받은 답변 정리, 사실 확인 표
- [`ADR-EVIDENCE-002`](adr-first-completion-owner-decisions.md) §5.6·§5.8·§5.11·§5.14
- `data/mock/evidence/scenario_unknown_abstain_partial_001.json` · `data/mock/case/…` · `data/mock/recording/…`
- `src/daesingo/evidence/requirements.py`(`_location_snapshot`) · `validation.py` · `mock_integration.py`의 `known_differences`

## 13. 한 줄 결정

> 위치를 확보하지 못한 사건에서도 다른 신고요건이 충족되면 `ReportPackage`를 발행한다. 「위치 없음」은 키를 생략하거나 빈 객체로 쓰지 않고 `location: null`로 직렬화하며 이는 「아직 오지 않은 값」이 아니라 확정된 부재를 뜻한다. `report-package/v1.1`이 이 모양을 규범으로 받고, `safety-report-policy/v1.1`이 장소 슬롯 없는 template을 별도 `template_ref`로 등재하되 값을 지어내지 않으며, 새 rule catalog revision이 `package.location.present`의 부재를 `WARN`으로 바꾸고 `package.report.content_length`의 필수 입력을 선택된 template 기준으로 읽어 Package가 `UNKNOWN`으로 사라지지 않게 한다. 사용자 고지는 `case`가 소유하고 `actions[]`를 확장하지 않으며, 선택적 위치 질의(④)는 C-1 관찰 결과가 나올 때까지 열지 않는다.
