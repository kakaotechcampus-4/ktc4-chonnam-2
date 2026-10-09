# SafetyReportType 매핑과 신고문 Template v1.2

> 결정일: 2026-09-29
> Decider: 김준영 (`evidence` Owner)
> 상태: `ACCEPTED`
> 정책 버전: `safety-report-policy/v1.2`
> 대체 대상: `safety-report-policy/v1.1`
> 근거: #146 9/25 Evidence/Product Owner 답변 · #172 D-3 · [`ADR-EVIDENCE-008`](../adr/adr-plate-identification-failure-boundary.md) §6

## 개정 범위

v1.1의 SafetyReportType registry, 초기 4종 매핑, `잘 모르겠어요` fallback, template 네 종(specific/generic × 위치 있음/없음)의 제목과 본문은 **그대로** 유지한다. v1.2는 `report_inputs.vehicle_number=null`인 Package — 번호판 판독을 수행했지만 차량번호를 식별하지 못한 경우 — 를 위해 **차량번호 슬롯이 없는 template 네 종**을 추가한다. 번호판 값·대체 번호·`UNKNOWN` 같은 표지는 생성하지 않는다.

v1.1 파일(`safety_report_policy_v1_1.json`)은 수정하지 않고 보존한다.

## 번호판 없는 문장 구성

v1.1이 위치가 없을 때 장소 구절을 **뺀** 것과 같은 방식으로, 차량번호가 없으면 `차량번호 {차량번호} 차량` 구절을 `차량`으로 줄인다. 다만 위치와 달리 차량번호는 안전신문고에서 사용자가 따로 고를 수 있는 값이 아니고, #146 답변이 「차량번호 정보가 부족하다는 점을 명확히 안내」하라고 정했으므로 **본문 끝에 식별하지 못했다는 사실을 한 문장으로 밝힌다.** 이 문장은 사실만 적고 신고 처리 가능성을 약속하지 않는다.

- 고정 문장(`no_plate_notice`): `차량번호는 영상에서 식별하지 못했습니다.`

## Template registry — v1.2에서 추가

### `tmpl/safety-report-specific-no-plate-v1`

사용 조건: 위치가 있고, 사건 유형과 위반행위를 사용자가 확인·수정해 확정했으며, 번호판 판독은 수행했지만 차량번호를 식별하지 못했다.

```text
{발생일시}경 {발생장소}에서
차량이
{위반행위}하는 것을 확인하여 신고합니다.
첨부 영상에서 해당 위반 상황을 확인할 수 있습니다.
차량번호는 영상에서 식별하지 못했습니다.
```

### `tmpl/safety-report-specific-no-location-no-plate-v1`

사용 조건: 위 조건에서 표시할 위치도 없다.

```text
{발생일시}경 촬영된
차량이
{위반행위}하는 것을 확인하여 신고합니다.
첨부 영상에서 해당 위반 상황을 확인할 수 있습니다.
차량번호는 영상에서 식별하지 못했습니다.
```

두 specific template의 제목은 v1 유형별 제목을 그대로 쓴다.

### `tmpl/safety-report-generic-no-plate-v1`

사용 조건: 위치가 있고, 사용자가 사건 유형에 `잘 모르겠어요`라고 답했으며(`visual_event_type=null`), 번호판 판독은 수행했지만 차량번호를 식별하지 못했다.

```text
{발생일시}경 {발생장소}에서 촬영된 차량의 주행 상황에 대해 신고합니다.
구체적인 위반 유형은 확인하기 어려워 첨부 영상을 바탕으로 확인을 요청드립니다.
차량번호는 영상에서 식별하지 못했습니다.
```

### `tmpl/safety-report-generic-no-location-no-plate-v1`

사용 조건: 위 조건에서 표시할 위치도 없다.

```text
{발생일시}경 촬영된 차량의 주행 상황에 대해 신고합니다.
구체적인 위반 유형은 확인하기 어려워 첨부 영상을 바탕으로 확인을 요청드립니다.
차량번호는 영상에서 식별하지 못했습니다.
```

두 generic template의 제목은 `교통법규 위반 상황 확인 요청`으로 고정한다.

## Renderer 불변조건 (v1.1에서 바뀐 것만)

1. `vehicle_number`는 필수 슬롯이 아니다. 값이 있으면 기존 네 template, `null`이면 번호판 없는 네 template 중 하나를 고른다. 빈 문자열은 부재로 보지 않고 입력 오류로 거절한다.
2. **번호판 없는 template을 쓸 수 있는지는 renderer가 아니라 호출자(requirement 평가·Package builder)가 정한다.** 번호판 판독을 수행한 기록(`EvidenceRecord.provenance.input_refs`에 `plate_readout` ref)일 때만 허용하며, 판독 실행 실패는 렌더 입력 불완전(`UNKNOWN`)으로 막는다(ADR-EVIDENCE-008 §5.1·§6).
3. `ReportPackage.report.template_ref`와 `provenance.policy_ref=safety-report-policy/v1.2`를 보존한다.
4. 번호판이 없다고 해서 다른 문장을 바꾸거나 위반행위를 더하지 않는다. 번호판 있는 네 template의 출력은 v1.1과 글자 하나까지 같다.
