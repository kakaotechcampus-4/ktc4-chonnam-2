# 지시 간 불일치 후속 분석과 문서 정정안

> 작성일: 2026-09-14
> 범위: [`13_adr-002-003-implementation_2026-09-14.md`](13_adr-002-003-implementation_2026-09-14.md) §「발견한 지시 간 불일치」의 확장 분석, 구현 판단 평가, Owner 결정 대기 항목과 추천값, 문서 정정안
> 상태: **분석·제안. 이 문서는 결정하지 않는다** — ADR 정정과 우선순위 확정은 `evidence` Owner(김준영)의 몫
>
> **처리 결과 (2026-09-14, 같은 날 추가).** Owner가 §5의 ②③④를 채택하고 **①은 기각**했다. ①이 전제한 「I4-b 관찰 전달 경로를 만든다」는 방향이 틀렸고, 세 rule 자체를 제거하는 것이 맞다는 판단이다. 결정은 [`ADR-EVIDENCE-005`](../adr/adr-event-context-rules-removal.md)에 있다. **§5-①은 폐기됐으며 아래에 폐기 표시를 달고 원문은 보존한다.** §6 문서 정정안 1~3·8은 그 ADR 작업에 흡수돼 반영됐다.

## 이 문서가 따로 있는 이유

리뷰 13은 **구현 시점의 검수 기록**이다. 관찰한 사실을 그 시점 그대로 남기는 문서이므로 나중에 고쳐 쓰지 않는다. 이 문서는 그 뒤에 수행한 **원인 분석과 정정 제안**을 담는다. 둘의 역할이 다르므로 13을 수정하는 대신 14를 새로 둔다.

리뷰 13이 기록한 불일치는 두 건이었다. 그 기록은 정확하다. 다만 **불일치의 실제 범위와 해소 조건**이 13에서는 압축돼 있어, 다음 사람이 우선순위를 잘못 매길 여지가 있다. 아래 §1이 그 부분을 좁힌다.

---

## 1. 재실행 결과 재분석 — 잠금장치는 하나뿐이다

`artifacts/first-completion/`의 baseline 네 건을 outcome 분포까지 열어 확인했다.

| Scenario | FINAL_PACKAGE overall | Package | UNKNOWN check | 나머지 check 분포 |
| --- | --- | --- | --- | --- |
| H `scenario_happy_001` | `UNKNOWN` | 0 | 관찰 rule **3건뿐** | `PASS` 13 |
| U `scenario_unknown_abstain_partial_001` | `UNKNOWN` | 0 | 관찰 rule **3건뿐** | `PASS` 10 · `WARN` 3 |
| P `scenario_plate_reread_001` | — | 0 | — | FINAL_PACKAGE 평가 대상 아님(EVIDENCE scope 전용) |
| R `scenario_correction_rerun_001` | — | 0 | — | 위와 같음 |

여기서 두 가지가 새로 확정된다.

**① `BLOCK`이 어디에도 없다.** H·U 어느 쪽도 실패 판정이 아니다. 막힌 게 아니라 **판정이 유보된 상태**다.

**② 관찰 fact 3종만 공급되면 H는 `PASS`, U는 `WARN`이 되어 둘 다 즉시 Package가 발행된다.** 다른 선행 조건이 없다.

즉 **세 관찰 rule 하나가 공용 Artifact의 Package 0건을 전부 설명하는 유일한 잠금장치다.** 리뷰 13의 후속표는 이 축을 아홉 항목 중 하나(I4)로 평범하게 적었지만, 실제 무게는 그렇지 않다.

> **정정 (2026-09-14).** 이 관측은 그대로 유효하나 **해석이 바뀌었다.** 처음에는 잠금장치를 「I4 관찰 전달 경로의 부재」로 읽고 §5-①에서 그 경로를 만들자고 제안했다. 실제 원인은 **판정 주체가 제품 안에 없는 rule을 등재해 둔 것**이었고, 해소는 경로 신설이 아니라 rule 제거다 — [`ADR-EVIDENCE-005`](../adr/adr-event-context-rules-removal.md). 위 표의 「나머지 분포」가 근거다: 세 rule을 빼면 H는 `PASS` 13으로 `PASS`, U는 `PASS` 10 + `WARN` 3으로 `WARN`이 되어 두 Package가 즉시 발행된다.

동시에 이 분석은 **D1이 완전히 반영됐다는 사실도 재확인한다.** U의 `package.location.present`는 `WARN`, `package.report.content_length`는 `PASS`다. D1이 겨냥한 두 rule은 정확히 D1이 요구한 값으로 바뀌었고, 어느 쪽도 Package를 막고 있지 않다.

---

## 2. 불일치 ① — 같은 U에 반대되는 기대가 걸려 있다

### 양쪽 지시

| 측 | 위치 | 내용 |
| --- | --- | --- |
| A | `prompts/implementation-prompt-adr-002-k1-k4.md:241` (W5 하지 말 것) | "관찰 fact를 **새로 지어내지 마라.** 네 Scenario 모두 이 세 rule은 `UNKNOWN`이 정상이다" |
| A | `adr/adr-first-completion-owner-decisions.md:583` (§5.15 Artifact 영향 본문) | "네 Scenario 모두 사건 장면·전후 상황 rule이 `UNKNOWN`으로 들어온다. (…) 회귀 실패로 보지 않는다" |
| B | `adr/adr-first-completion-owner-decisions.md:593` (§5.15 **D1 정정 블록**) | "D1 반영 후에는 (…) U의 `overall`은 `WARN`이고 `PACKAGE_READY`가 성립한다" |
| B | `prompts/…k1-k4.md:266` (W6 「U는 다르다」) | "U의 Package가 사라졌다면 W12가 덜 반영된 것이니 **원인을 찾아라**" |
| B | `prompts/…k1-k4.md:350` · `:442` (W12 완료 조건·검증) | "U의 `FINAL_PACKAGE` `overall`이 `WARN`이고 `PACKAGE_READY`가 성립한다" |
| B | `adr/adr-location-absent-package.md:230` (ADR-003 §9 검증표) | "U의 `FINAL_PACKAGE` overall — `WARN` 유지" |

**A와 B가 같은 절(ADR-002 §5.15) 안에 함께 있다.** 본문 문단과 그 아래 인용 블록이 서로 반대되는 기대를 적는다.

### 왜 동시에 만족할 수 없나

`contract-requirement-report-package.md:196`의 aggregation이 순수 precedence다.

```
BLOCK > UNKNOWN > WARN > PASS
→ BLOCK이 없고 UNKNOWN이 하나라도 있으면 overall = UNKNOWN
```

같은 계약 §5.2(`:280-289`)는 `PACKAGE_READY`를 `overall ∈ {PASS, WARN}` **그리고** Package 존재로 정의하고, `UNKNOWN`이면 `ReportPackage` 자체가 생성되지 않는다.

`requirement_rules_v3.json`에서 세 관찰 rule은 `not_observed → UNKNOWN`이다. 공용 입력에 세 fact가 없으므로 A를 지키면 `UNKNOWN` 3건이 남고 B는 도달 불가다. B를 만족시키려면 관찰 fact를 위조해야 하는데 그게 A가 금지한 행위다.

### 불일치가 생긴 경위

이번 라운드에 U를 막는 요인이 **두 축**이었다.

- **위치 축** — D1이 해소함
- **관찰 축** — 아무도 해소하지 않음. I4 범위

D1 정정 블록(`:593`)은 위치 축만 계산했다. 블록 자체가 "U의 `package.location.present`와 `package.report.content_length`가 **모두** `UNKNOWN`이 되어"라고 두 rule만 열거한다. 관찰 축은 바로 **윗 문단(`:583`)에 이미 적혀 있었으나** 결론 계산에 들어가지 않았다.

정리하면 이렇다.

| 명제 | 참/거짓 |
| --- | --- |
| "D1이 U의 위치 관련 `UNKNOWN` 2건을 제거한다" | **무조건 참** |
| "D1 반영 후 U의 `overall`은 `WARN`이고 `PACKAGE_READY`가 성립한다" | **조건부** — 관찰 축이 0건일 때만 |

전자를 후자로 넓혀 쓴 것이 불일치의 실체다.

### 실무상 가장 위험한 문장

W6 `:266`의 *"U의 Package가 사라졌다면 W12가 덜 반영된 것이니 원인을 찾아라"* 다. 그대로 따르면 **정상 반영된 W12를 회귀로 의심하며 존재하지 않는 버그를 찾게 된다.** 리뷰 13이 즉시 기록해 둔 덕에 이 경로가 막혔다.

---

## 3. 불일치 ② — 검증 통과 요구와 파일 수정 금지가 같은 절에 있다

### 두 지시

- W12 완료 조건 `:346` — `validate_report_package(pkg_u001)`이 `[]`를 돌려준다
- 같은 W12 하지 말 것 `:362` — "공용 `data/mock` fixture를 고치지 마라. `pkg_u001`의 `template_ref`·신고문 동기화는 통합 항목 I2(`case`)다" (ADR-003 §8도 동일)

### 디스크 실제 상태

`data/mock/evidence/scenario_unknown_abstain_partial_001.json`의 `pkg_u001`:

```json
"contract_version": "report-package/v1",
"report_inputs": { …, "location": null, … },
"report": { …, "template_ref": "tmpl/safety-report-generic-v1" }
```

`report-package/v1`에서 `location`은 non-null 필수다. **디스크 payload를 그대로 검증하면 반드시 `location` 위반이 뜬다.**

### 갈래와 비용

| 방법 | 결과 | 위반 |
| --- | --- | --- |
| fixture의 `contract_version`을 v1.1로 올린다 | `[]` | 같은 절의 fixture 수정 금지. I2(`case`) 영역 침범 |
| 검증기가 v1 payload의 `location: null`도 통과시킨다 | `[]` | v1 계약 의미를 조용히 폐기. ADR-003 §5.3·§10이 v1 의미 보존을 요구 |
| **검증기를 version별로 가르고 테스트에서만 v1.1로 해석** | `[]` | 없음 |

### 구현이 택한 것

`src/daesingo/evidence/validation.py:214`·`:218`이 진입점을 둘로 나눈다. `validate_report_package()`는 v1.1 semantics(키 필수·`null` 허용), `validate_contract()`로 들어온 v1 payload는 v1 semantics(`null` 위반) 그대로다.

`tests/evidence/test_contract_validation.py:37`이 디스크 fixture를 읽어 **메모리에서만** `contract_version`을 v1.1로 바꾼 뒤 네 가지를 고정한다 — ① `[]`, ② 키 삭제는 위반, ③ 빈 객체는 위반, ④ v1로 남긴 payload는 여전히 위반. 파일은 무변경이고 디스크 갱신은 I2에 남겼다.

### 남는 잔여 — `[]`가 곧 D1 정합은 아니다

검증기는 `report_inputs`의 키·모양만 본다(`validation.py:182-210`). `template_ref`와 위치 유무의 정합은 검사하지 않는다.

그런데 `pkg_u001`의 `template_ref`는 아직 `tmpl/safety-report-generic-v1`이고, `decisions/safety-report-policy-v1.1.md:19`는 이 template을 **"위치가 있고" 사건 유형 응답이 `USER_UNSURE`인 경우**로 정의한다. 위치가 `null`인 Package가 위치 있는 template을 가리키는 상태다. 올바른 값은 `tmpl/safety-report-generic-no-location-v1`(`:36`)이다.

**`[]` 통과를 "공용 fixture가 이미 v1.1 정합이다"로 읽으면 안 된다.** 확인된 것은 validator 쪽 semantics뿐이고 fixture는 `contract_version`·`template_ref` 두 곳이 D1 이전 상태다. 리뷰 13이 "디스크 fixture 갱신은 I2에 남겼다"고 적은 이유가 이것이다.

---

## 4. 구현 판단 평가

| 판단 | 평가 | 근거 |
| --- | --- | --- |
| 관찰 fact를 지어내지 않음 | **타당** | Artifact는 증빙이다. 입력을 위조하면 증빙 가치가 0이 된다. W6 「반드시 정직하게 다룰 것」(`:258-263`)이 명시적으로 금지 |
| 세 rule을 `WARN`으로 낮추지 않음 | **타당** | 어떤 ADR도 결정하지 않은 정책 변경이고, §5.15가 관찰 경로를 K3 범위 밖으로 남겨 둠. §5-② 참조 |
| D1을 test-derived 입력으로 별도 증명 | **타당** | `pkg_u001_d1_unit`으로 위치 없는 `WARN` Package·no-location template·재현성 검증. 공용 Scenario 통과로 보고하지 않음 |
| ADR 본문을 고치지 않고 보고에 남김 | **타당** | W7 4번이 정확히 그 절차를 지정 |
| `first-completion-result.md` 갱신 | **타당** | 15·16행에 시나리오별 "관찰 fact 3종 부재로 Package 0건", 63행에 「공용 U Package baseline」 전용 행. 현재 상태를 오해할 여지 없음 |

**두 지시의 성격 차이가 판단의 핵심이다.** W5/§5.15 본문은 **입력의 진실성** 제약이고, W12 완료 조건은 **출력의 기대값**이다. 관찰 fact를 지어내면 출력 기대는 맞출 수 있으나 baseline이 "관찰된 적 없는 사실을 관찰됐다고 기록한 Artifact"가 된다. 상위 경계를 택한 것이 옳다.

### 한 가지 정밀화 대상

리뷰 13의 상태 줄(`:5`)이 `evidence 범위 구현 완료`다. W12 완료 조건 중 *"U의 `overall`이 `WARN`이고 `PACKAGE_READY`가 성립한다"* 한 줄은 **충족되지 않았다.**

결론 2문단(`:11`)이 "H와 U의 FINAL_PACKAGE는 `UNKNOWN`이고 Package는 0건이다"라고 먼저 밝히고 §불일치가 이유를 적으므로 **은폐는 아니다.** 다만 "완료 조건 하나가 미충족이며 그 원인이 evidence 범위 밖"이라는 **라벨이 없어**, 상태 줄만 읽는 사람에게는 보이지 않는다. 처리 방안은 §5-③에 둔다.

---

## 5. Owner 결정이 필요한 항목과 추천값

### ~~① I4의 우선순위와 범위 확장~~ — **기각됨 (2026-09-14)**

> **폐기 사유.** 이 항목은 「세 rule의 관찰 입력을 만들어 공급한다」를 전제로 우선순위를 매겼다. **전제가 틀렸다.**
>
> 제품은 「위반이 영상에 있는가」를 판정하지 않기로 이미 정해 두었다 — `core-user-flow.md` §15 *"AI는 법률적 최종 판정을 요구하지 않는다"*, §11 *"사용자는 AI의 법적 결론을 평가하는 것이 아니라 실제 영상과 AI가 관찰한 사건 내용을 비교한다"*. 확인은 두 단계로 이미 끝나 있다 — **§8 `[이 사건 맞아요]`가 「이 영상이 그 사건이다」를 확정하고**(선택된 후보에서 REPORT_VIDEO가 만들어지므로 evidence 입력의 전제이지 판정 대상이 아니다), **§15 `[맞아요]`가 「그 위반이 어떤 상황인가」를 확정해** `situation_response` → `package.evidence.situation_response`로 판정된다. 세 rule은 이미 확정된 전제를 다시 묻는 것이었다(ADR-005 §2.5).
>
> 그래서 생산자가 계약 어디에도 없었던 것이 누락이 아니라 **판정할 수 있는 모듈이 없다는 증거**였다. 아래 본문의 I4-b 신설 제안은 없는 판정 주체를 만들어내는 방향이라 채택하지 않는다.
>
> **대체 결정: [`ADR-EVIDENCE-005`](../adr/adr-event-context-rules-removal.md)** — 세 rule을 `FINAL_PACKAGE`에서 제거(15 → 12), 요건 확인 책임은 사용자 확인과 `recording` 생성으로 이관, **I4 범위는 번호판·시각 그대로 유지**. 주간 회의 보고 대상은 「I4 우선순위」가 아니라 **신고요건 rule 변경 자체**다(B-3).
>
> 아래 원문은 시점 기록으로 남긴다.

#### (폐기된 원안)

**배경.** §1이 보인 대로 I4 하나가 공용 Artifact의 Package 0건을 전부 만들고 있다. 현재 I4의 정의는 [`10_first-completion_decisions_and_integration_2026-09-13.md:102`](10_first-completion_decisions_and_integration_2026-09-13.md)에서 **"최종 신고영상의 번호판·시각 표시 여부를 실제 관찰로 전달"** 이다. 사건 장면·전 상황·후 상황 세 관찰은 그 정의에 **없다.** §5.15가 "I4의 범위를 사건 장면·전후 상황까지 넓혀야 한다"고 지적한 것이 이 간극이다.

연쇄도 있다. I2(fixture 재렌더)는 I4가 끝나야 의미 있는 결과를 얻고, I5(「U 위치 결론과 H/U Package/CaseView 반영」, 시작 조건 "D1 확정, I2 완료")는 그 뒤다. 즉 **I4 → I2 → I5**가 한 사슬이며 지금 그 맨 앞이 막혀 있다.

**선택지.**

| | 내용 | 비용 |
| --- | --- | --- |
| (a) | I4 정의를 그대로 두고 별도 항목 신설 | 항목 수 증가. 담당·시작 조건이 I4와 동일해 분리 실익 적음 |
| (b) | **I4 정의를 확장하고 하위 분기로 표기** | 기존 담당·시작 조건 재사용. 문서 한 곳 수정 |
| (c) | 현행 유지, 후속표 문구만 보강 | 우선순위가 여전히 드러나지 않음 |

> **추천: (b).** I4를 다음과 같이 확장한다.
>
> - **I4-a** — 번호판·시각 표시 관찰 전달 (기존 정의 그대로)
> - **I4-b** — 사건 장면·전 상황·후 상황 관찰 전달 (신규)
>
> 담당은 기존과 동일하게 **신유민(`readout`)·정철원(`recording`)·유소연(`case`)**, 시작 조건도 동일하게 **REPORT_VIDEO가 실제 ref로 존재**. 세 값 모두 같은 영상에 대한 관찰이므로 전달 경로를 나눌 이유가 없다.
>
> 그리고 후속표의 영향 경로를 **"FINAL_PACKAGE rule inputs"** → **"공용 baseline Package 0건의 단일 원인. 해소되면 H는 `PASS`, U는 `WARN`으로 즉시 발행"** 으로 바꾼다.
>
> **근거.** 잠금장치가 하나라는 사실이 드러나야 우선순위가 제대로 매겨진다. 담당·시작 조건이 이미 같으므로 신설 비용이 없다. `10_…:111`의 "I4처럼 실제 영상이 있어야 의미 있는 항목은 지금 별도 Contract를 서둘러 만들지 않는다"는 경계는 그대로 지킨다 — 확장은 **관찰 전달 범위**이지 Contract 신설이 아니다.

**주간 회의 안건 여부: 올린다.** 세 모듈 담당자의 작업 순서에 영향을 주는 우선순위 변경이다.

---

### ② 세 관찰 rule의 `not_observed → UNKNOWN` 매핑

**배경.** "관찰 경로가 아직 없어서 모른다"와 "관찰 가능하지만 아직 안 했다"가 같은 `UNKNOWN`으로 묶여 있다. 성격이 달라 보이므로 갈래를 나눌지 검토할 여지가 있다.

**확인 결과 — ADR-002 §5.12가 이미 이 질문에 답하고 있다.** 정상 Report의 `UNKNOWN` 목록에 *"번호판·사건 장면·전후 상황·시각 표시를 **아직 관찰하지 않음**"* 이 명시돼 있다. 미관찰은 정책 엔진 오류가 아니라 **업무상 `UNKNOWN`이 맞다**는 것이 이미 내려진 결정이다.

> **추천: 매핑을 바꾸지 않는다. 검토 항목에서 내린다.**
>
> **근거 셋.**
>
> 1. **§5.12가 이미 결정했다.** 바꾸려면 catalog 새 revision + ADR 개정이 필요한데, 바꿔야 할 이유가 없다.
> 2. **D1의 위치와 성격이 정반대다.** 위치는 **부재가 확정된 사실**이라 `WARN`이 맞았다(§5.12의 네 번째 갈래). 사건 장면 가시성은 **부재가 아니라 미지**다. `WARN`으로 낮추면 *"위반 장면이 영상에 실제로 보이는지 한 번도 확인하지 않은 채 신고 준비 완료"* 를 발행하게 된다. 이건 사용자가 실제로 반려당하는 출력이며 `product-spec.md` §7 방향과 어긋난다.
> 3. **구분이 필요하다면 outcome이 아니라 metadata가 나른다.** "관찰 경로 자체가 미구축"이라는 사실은 `run-summary.json`과 `first-completion-result.md`가 이미 적고 있다. 정책 outcome을 흔들 일이 아니다.

---

### ③ 리뷰 13의 「완료 조건 미충족」 라벨 처리

**배경.** §4의 정밀화 대상. 라벨이 어디엔가 있어야 하지만, 리뷰 보고서는 시점 기록이라 나중에 고쳐 쓰지 않는 것이 이 폴더의 원칙이다.

**선택지.**

| | 내용 | 원칙 충돌 |
| --- | --- | --- |
| (a) | 리뷰 13의 상태 줄을 직접 수정 | 시점 기록 원칙과 충돌. 다만 같은 날·같은 회차·같은 저자라 실질 충돌은 작음 |
| (b) | **이 문서(14)가 라벨을 갖고 13을 가리킨다** | 없음 |

> **추천: (b).** 이 문서 §4가 이미 그 라벨을 담고 있고, `reviews/README.md` 항목에 14를 추가해 경로를 만든다. 리뷰 13은 손대지 않는다.
>
> **근거.** living doc(`first-completion-result.md`)이 이미 현재 상태를 정확히 적고 있으므로, "지금 무엇이 참인가"를 읽을 곳은 이미 확보돼 있다. 13에 손대는 실익이 없다.

---

### ④ ADR 정정 방식과 보고 여부

**배경.** ADR-002는 `ACCEPTED`이고 §7 변경 규칙은 **정책 데이터 revision**만 다룬다. ADR 본문 문구 정정 절차는 명시돼 있지 않다.

**선례가 있다.** D1 종결 시 §5.15와 §5.12에 인용 블록(`> **D1 종결에 따른 정정 (2026-09-14).**`)을 덧붙이고 **원문은 지우지 않았다.** 같은 방식이 v2 catalog를 "채택됐으나 첫 실행 전 대체됨"으로 보존한 판단과도 결이 같다.

> **추천: D1 선례를 그대로 따른다.** 원문 보존 + 인용 블록 추가. 구체안은 §6.
>
> **B-3 주간 회의 보고: 이번 정정은 대상이 아니다.** `cross-cutting-decisions.md:80`의 B-3은 *"신고요건 **규칙**이 바뀌면 주간 회의에 보고한다"* 이다. 이번 정정은 catalog·policy 값을 하나도 바꾸지 않는 **문서 문구 정정**이므로 규칙 변경이 아니다.
>
> 다만 **§5-①의 I4 우선순위 상향은 별개로 안건에 올린다.** 그건 타 모듈 일정에 영향을 준다.

---

## 6. 문서 정정안

**근원은 한 군데다.** `adr-first-completion-owner-decisions.md:593`의 D1 정정 블록이 위치 축만 보고 단정한 것. 나머지는 이를 인용하거나 그 전제 위에 쓰였다.

| # | 파일·위치 | 고칠 내용 | 가능 여부 |
| --- | --- | --- | --- |
| 1 | `adr/adr-first-completion-owner-decisions.md:593`<br>§5.15 D1 정정 블록 | 기존 블록 아래에 **정정 블록을 하나 더** 덧붙인다. 요지: "이 블록은 위치 축만 계산했다. 관찰 축(사건 장면·전 상황·후 상황)은 별개이며 I4 대기다. **`PACKAGE_READY` 성립은 I4 관찰 입력이 공급된 뒤 조건부로 성립한다.** 위치 축 2건 제거는 무조건 참" | ✅ Owner 권한 · D1 선례 |
| 2 | `adr/adr-location-absent-package.md:180-181`<br>§5.8 영향 범위 표 | §5.15 관련 두 행이 같은 단정을 복제한다. 1번 정정 블록을 **가리키게** 한다(문구 복제 금지 — `docs/README.md` 「다른 문서의 규칙을 복제하지 않는다」) | ✅ |
| 3 | `adr/adr-location-absent-package.md:230`<br>§9 검증표 | "U의 `FINAL_PACKAGE` overall — `WARN` 유지" → **"test-derived 입력(`pkg_u001_d1_unit`)에서 확인. 공용 U는 I4 대기"**. 실제 검증 방식과 일치시킨다 | ✅ |
| 4 | 리뷰 13 후속표 I4 행 | §5-① 추천대로 I4-a/I4-b 분기와 영향 경로 문구 | ✅ 단, §5-③ 추천에 따르면 **14가 대신 갖는 편이 낫다** |
| 5 | `10_first-completion_decisions_and_integration_2026-09-13.md:102`<br>I4 행 | I4-a/I4-b 분기 반영. 담당·시작 조건 유지 | ⚠️ 리뷰는 시점 기록. **통합 항목 원장을 별도 living doc으로 옮길지 먼저 판단** — §8 참조 |
| 6 | `prompts/…k1-k4.md:266` · `:350` · `:442` | 문구가 틀렸으나 **수정하지 않는다** | ❌ W7 5번 「발주 이력이다. 수정하지 마라」 |
| 7 | `first-completion-result.md` | 이미 정확하다 | — 불필요 |
| 8 | `adr/adr-location-absent-package.md:205`<br>§7 긍정적 결과 (선택) | *"`unknown_abstain_partial_001` rev4가 유지되어 (…) 최소 케이스가 보존된다"* — **디스크 fixture 기준으로는 참이다.** 다만 재실행 baseline에는 Package가 없어 오독 여지가 있다. "fixture 파일 기준. 재실행 Artifact 반영은 I4·I2 이후" 한 마디를 덧붙이면 정확해진다 | ✅ 선택 |

**6번이 구조적으로 중요하다.** 발주 프롬프트는 이력이라 틀린 채로 남는다. 그래서 **정정을 담는 그릇이 리뷰 보고서여야 한다.** 리뷰 13 §불일치와 이 문서가 그 역할을 맡고 있으며, 이는 우연이 아니라 폴더 역할 분담이 의도한 구조다.

**1~3만 반영하면 문서 결함은 사라진다.** 코드 변경은 없다. 4~5·8은 정리 성격이다.

> **반영 결과 (2026-09-14).** [`ADR-EVIDENCE-005`](../adr/adr-event-context-rules-removal.md) 작업에 흡수해 처리했다. 다만 **1·3의 문구는 위 원안과 다르다** — 원안은 「I4 대기」라는 조건을 달자는 것이었는데, 세 rule이 제거되면서 조건 자체가 사라졌으므로 「ADR-005로 해소된다」로 적었다.
>
> | # | 결과 |
> | --- | --- |
> | 1 | ADR-002 §5.15에 두 번째 정정 블록 추가. 원문·D1 블록 모두 보존 |
> | 2 | ADR-003 §5.8 표의 §5.15 Artifact 영향 행에 정정 주기. 1번을 가리킴 |
> | 3 | ADR-003 §9 검증표 U 행 갱신 |
> | 4·5 | **불필요해짐.** I4 범위가 원래대로 유지되므로 고칠 것이 없다(ADR-005 §5.7) |
> | 6 | 손대지 않음 (유지) |
> | 7 | 불필요 (유지) |
> | 8 | ADR-005 §7이 「재실행 Artifact에서도 살아난다」로 처리. ADR-003 §7 원문은 그대로 참이므로 손대지 않았다 |
>
> 추가로 ADR-002 §5.6 rule 표·§5.6 「사건 장면과 전·후 상황」 절·§5.12 두 목록·§5.14 rule 수·§5.15 구현 영향 목록과 미결 목록, 그리고 문서 머리의 후속 안내에 D2 표시를 달았다. 모두 원문 보존 방식이다.

---

## 7. 결함을 언제 기록하나 — 이 레포의 원칙

**표시가 해결보다 먼저다.** 근거 셋.

1. **해결 주체가 내가 아닐 수 있다.** 이번이 그 경우다. I4는 `evidence` 담당이 아니다. "내가 못 고치니 나중에"였다면 기록이 아예 남지 않았다.
2. **"고치고 나서 쓴다"는 결국 안 쓰게 된다.** 해결된 일은 쓸 동기가 사라진다.
3. **이번 사례가 증거다.** W6 `:266`의 오진 유도 문장을 리뷰 13이 즉시 기록해 막았다.

**다만 해결 후 흔적을 지우는 것도 아니다.** 문서 종류마다 다르다.

| 문서 | 처리 |
| --- | --- |
| **ADR** (결정 기록) | **남긴다.** 덮어쓰지 않고 정정 블록을 덧붙인다. v2 catalog 보존 판단과 같은 결 |
| **발주 프롬프트** | **건드리지 않는다.** 이력이다. 정정은 리뷰가 갖는다 |
| **리뷰 보고서** | **시점 기록.** 나중에 고치지 않고 새 리뷰가 갱신한다 |
| **living doc** (`first-completion-result.md` 등) | **현재 상태로 갱신한다.** 왜 바뀌었는지는 링크로 가리킨다 |

지켜야 할 원칙은 하나다. **이력은 여러 곳에 남아도 되지만, "지금 무엇이 참인가"는 한 곳에서만 읽혀야 한다.** `docs/README.md`의 「다른 모듈의 규칙을 자기 문서에 복제하지 않는다」와 같은 얘기다. §6 2번을 "문구 복사"가 아니라 "1번을 가리키게"로 적은 이유가 이것이다.

---

## 8. 이 문서가 결정하지 않는 것

- ~~**ADR-002·003 본문 정정의 실행**~~ → Owner가 채택해 [`ADR-EVIDENCE-005`](../adr/adr-event-context-rules-removal.md) 작업에서 반영했다(§6 반영 결과 표)
- ~~**I4 범위 확장의 확정**~~ → **기각.** I4는 번호판·시각 범위 그대로다(ADR-005 §5.7)
- **통합 항목(I1~I11) 원장의 소유 위치** — 현재 리뷰 10(시점 기록) 안에 있어 갱신할 때마다 원칙 충돌이 생긴다. living doc으로 옮길지는 별도 판단이 필요하며 이 문서에서 정하지 않는다. **미결 유지**
- **`case`·`web` 소유 항목** — `CaseView.report_field_states.location`, 사용자 고지 code, 공용 fixture 재렌더(I2). ADR-003 §8이 이미 evidence 범위 밖으로 못 박았다
- ~~**세 관찰 fact의 실제 생산 방식**~~ → 생산할 대상이 사라졌다. 다만 **녹화 경계로 전후가 물리적으로 없는 경우**는 `recording` 미결로 새로 등재됐다(ADR-005 §5.6 · D2-e). 이 문서도 그 항목을 확정하지 않는다
- **catalog v4 반영 자체** — ADR-005는 결정이고 실행이 아니다. 발주 범위는 같은 ADR §12

---

## 9. 관련 문서

- [`../adr/adr-event-context-rules-removal.md`](../adr/adr-event-context-rules-removal.md) — **이 문서의 분석이 도달한 결정(D2).** §5-①은 여기서 기각됐다
- [`13_adr-002-003-implementation_2026-09-14.md`](13_adr-002-003-implementation_2026-09-14.md) — 구현·검수 기록. 이 문서가 확장하는 원본
- [`../../../product/core-user-flow.md`](../../../product/core-user-flow.md) §8·§11·§15·§18 — 위반 확인의 판정 주체가 사용자라는 근거
- [`10_first-completion_decisions_and_integration_2026-09-13.md`](10_first-completion_decisions_and_integration_2026-09-13.md) §3 — 통합 항목 I1~I11 원장. I4 정의는 `:102`
- [`../adr/adr-first-completion-owner-decisions.md`](../adr/adr-first-completion-owner-decisions.md) §5.12 · §5.15 — 불일치의 근원과 `UNKNOWN` 갈래 분류
- [`../adr/adr-location-absent-package.md`](../adr/adr-location-absent-package.md) §5.8 · §9 — D1 영향 범위 표와 검증표
- [`../first-completion-result.md`](../first-completion-result.md) — 현재 상태 living doc. 15·16·52·63행
- `../../../architecture/contracts/contract-requirement-report-package.md` §4.3 · §5.2 — precedence와 `PACKAGE_READY` 정의
- `../../../management/cross-cutting-decisions.md` §B-3 — 신고요건 규칙 변경 보고 조건
