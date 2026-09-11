# SafetyReportType 매핑과 신고문 Template v1

> 결정일: 2026-09-10
> Decider: 김준영 (`evidence` Owner)
> 상태: `ACCEPTED`
> 정책 버전: `safety-report-policy/v1`
> 근거: `../research/안전신문고_실제_신고_요건_및_초기_4종_유형_매핑_조사.pdf` §1~§2·§6·§15, `../research/신고문__Package__Handoff__확정된_증거를_실제_신고_가능한_형태로_어떻게_넘길_것인가.pdf` §1~§5·§9~§10·§20~§21, `../../../architecture/module-architecture.md` §3-5

## 결정

`VisualEventType`, 안전신문고 신고유형, 신고문에 들어가는 위반행위 표현은 서로 다른 값으로 관리한다.

```text
VisualEventType
  -> SafetyReportType
  -> violation_expression
  -> deterministic template
```

안전신문고가 공개적으로 사용하는 현재 표시명은 [행정안전부 안전신문고 안내](https://www.mois.go.kr/frt/sub/a06/b10/safetyReport/screen.do)의 자동차·교통위반 신고 목록과 대조했다(2026-09-10 확인). 외부 서비스의 비공개 내부 코드값은 추측하지 않는다. 아래 enum은 대신고 내부의 안정적인 코드다.

## SafetyReportType registry

| 내부 code | 사용자 표시 label | destination | 외부 machine code |
| --- | --- | --- | --- |
| `TRAFFIC_VIOLATION` | `교통위반(고속도로 포함)` | `SAFETY_REPORT` | 확인되지 않았으므로 저장하지 않음 |
| `MOTORCYCLE_VIOLATION` | `이륜차 위반` | `SAFETY_REPORT` | 확인되지 않았으므로 저장하지 않음 |

- 내부 code와 안전신문고 표시 label을 같은 필드에 혼용하지 않는다.
- `UNSAFE_LANE_CHANGE`, `UNSAFE_SIGNAL_VIOLATION`, `안전운전 불이행`은 이 registry의 값이 아니며 기존 Mock placeholder다.
- 외부 표시명이 바뀌면 이 정책의 새 버전을 만들고 기존 Package의 `policy_ref`/`template_ref`는 유지한다.

## 초기 4종 매핑

현재 Final Contract의 `VisualEventType` 이름을 기준으로 한다. 조사 PDF의 예전 이름 `SIGNAL_VIOLATION`, `CENTERLINE_CROSSING`, `MOTORCYCLE_NO_HELMET`은 각각 현재 이름 `SIGNAL`, `CENTER_LINE_CROSSING`, `MOTORCYCLE_HELMET_NON_USE`로 대응한다.

| `VisualEventType` | `SafetyReportType` | 기본 `violation_expression` |
| --- | --- | --- |
| `SIGNAL` | `TRAFFIC_VIOLATION` | `적색신호 상태에서 정지하지 않고 진행` |
| `CENTER_LINE_CROSSING` | `TRAFFIC_VIOLATION` | `황색 중앙선을 넘어 반대 차로로 진입` |
| `SOLID_LINE_LANE_CHANGE` | `TRAFFIC_VIOLATION` | `백색 실선을 넘어 진로를 변경` |
| `MOTORCYCLE_HELMET_NON_USE` | `MOTORCYCLE_VIOLATION` | `이륜차 운전자 또는 탑승자가 안전모를 착용하지 않고 주행` |

위 표현은 사용자가 해당 사건 유형을 확인했거나 수정해 확정한 경우에만 specific template에 넣는다. AI 내부 reasoning, 위험성 과장, 법률상 처분 단정은 넣지 않는다.

## 사용자 `잘 모르겠어요` fallback

- 사용자 응답 provenance가 `USER_UNSURE`이고 이륜차/안전모 근거가 확정되지 않았다면 `TRAFFIC_VIOLATION`을 기본 추천한다.
- 선택 후보에 이륜차이며 안전모 미착용일 가능성이 있다는 근거가 남아 있으면 `MOTORCYCLE_VIOLATION`을 추천할 수 있다.
- 이 경로의 `safety_report_type`은 `needs_review=true`이고 Requirement는 `WARN`이다.
- `visual_event_type=null`을 `기타 위반`, `UNKNOWN` 또는 가짜 VisualEventType으로 치환하지 않는다.
- 신고문에는 확인되지 않은 구체 위반행위를 넣지 않는다.

## Template registry

### `tmpl/safety-report-specific-v1`

사용 조건: 사건 유형과 위반행위 표현을 사용자가 확인했거나 수정해 확정했다.

```text
{발생일시}경 {발생장소}에서
차량번호 {차량번호} 차량이
{위반행위}하는 것을 확인하여 신고합니다.
첨부 영상에서 해당 위반 상황을 확인할 수 있습니다.
```

유형별 제목은 다음처럼 결정론적으로 생성한다.

| `VisualEventType` | PC 제목 |
| --- | --- |
| `SIGNAL` | `신호위반 차량 신고` |
| `CENTER_LINE_CROSSING` | `중앙선 침범 차량 신고` |
| `SOLID_LINE_LANE_CHANGE` | `진로변경 위반 차량 신고` |
| `MOTORCYCLE_HELMET_NON_USE` | `이륜차 안전모 미착용 신고` |

### `tmpl/safety-report-generic-v1`

사용 조건: 사용자가 사건 유형에 `잘 모르겠어요`라고 답해 `visual_event_type=null`인 WARN Package를 생성한다.

```text
{발생일시}경 {발생장소}에서 촬영된 차량번호 {차량번호} 차량의 주행 상황에 대해 신고합니다.
구체적인 위반 유형은 확인하기 어려워 첨부 영상을 바탕으로 확인을 요청드립니다.
```

PC 제목은 `교통법규 위반 상황 확인 요청`으로 고정한다. 모바일에서는 제목을 사용하지 않더라도 동일 Package에 보존한다.

## Renderer 불변조건

1. 신고문은 LLM 자유생성이 아니라 확정 Evidence와 위 고정 template로만 생성한다.
2. 입력 슬롯은 `occurred_at`, `location.display_text`, `vehicle_number`, 그리고 specific template의 `violation_expression`이다.
3. 신고내용은 5~900자 범위를 검사한다.
4. `ReportPackage.report.template_ref`와 `provenance.policy_ref=safety-report-policy/v1`을 보존한다.
5. 사용자가 확인하지 않은 위반행위를 문장에 추가하지 않는다.
6. Package는 신고자료 준비 결과이며 안전신문고 자동입력·자동제출·처분 성공을 의미하지 않는다.

## Mock 반영 요청

- `UNSAFE_*`와 한국어 label을 혼용하는 `EvidenceRecord.event.safety_report_type.value`를 위 내부 code로 정규화한다.
- CaseView의 `report_type_display.code`는 내부 code, `label`은 registry label을 사용한다.
- 기존 `tmpl/safety-report-v1`은 `tmpl/safety-report-specific-v1`로 명시한다.
- 사용자-unsure fixture의 `safety_report_type.needs_review`와 Package `unconfirmed_fields`를 둘 다 검토 필요 상태로 맞춘다.
