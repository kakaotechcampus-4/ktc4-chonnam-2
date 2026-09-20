# SafetyReportType 매핑과 신고문 Template v1.1

> 결정일: 2026-09-14
> Decider: 김준영 (`evidence` Owner)
> 상태: `ACCEPTED`
> 정책 버전: `safety-report-policy/v1.1`
> 대체 대상: `safety-report-policy/v1`
> 근거: ADR-EVIDENCE-003 §5.4, 이슈 #48

## 개정 범위

v1의 SafetyReportType registry, 초기 4종 매핑, 사용자 `잘 모르겠어요` fallback, 기존 specific/generic template 두 종은 그대로 유지한다. v1.1은 `report_inputs.location=null`인 Package를 위해 장소 슬롯이 없는 template 두 종을 추가하고, renderer의 위치 입력을 선택으로 내린다. 위치값·좌표·대체 문구는 생성하지 않는다.

## Template registry

### 기존 template — 변경 없음

- `tmpl/safety-report-specific-v1`: 위치가 있고 사건 유형과 위반행위 표현이 `CONFIRMED` 또는 `CORRECTED`인 경우
- `tmpl/safety-report-generic-v1`: 위치가 있고 사건 유형 응답이 `USER_UNSURE`인 경우

두 template의 본문과 제목은 [`safety-report-policy-v1.md`](safety-report-policy-v1.md)의 정의를 그대로 사용한다.

### `tmpl/safety-report-specific-no-location-v1`

사용 조건: 표시할 위치가 없고, 사건 유형과 위반행위 표현을 사용자가 확인하거나 수정해 확정했다.

```text
{발생일시}경
차량번호 {차량번호} 차량이
{위반행위}하는 것을 확인하여 신고합니다.
첨부 영상에서 해당 위반 상황을 확인할 수 있습니다.
```

제목은 v1 specific template의 유형별 제목을 그대로 사용한다.

### `tmpl/safety-report-generic-no-location-v1`

사용 조건: 표시할 위치가 없고, 사용자가 사건 유형에 `잘 모르겠어요`라고 답해 `visual_event_type=null`인 WARN Package를 생성한다.

```text
{발생일시}경 촬영된 차량번호 {차량번호} 차량의 주행 상황에 대해 신고합니다.
구체적인 위반 유형은 확인하기 어려워 첨부 영상을 바탕으로 확인을 요청드립니다.
```

제목은 `교통법규 위반 상황 확인 요청`으로 고정한다.

## Renderer 불변조건

1. 신고문은 LLM 자유생성이 아니라 확정 Evidence와 선택된 고정 template로만 생성한다.
2. 공통 입력 슬롯은 `occurred_at`, `vehicle_number`이며, `location.display_text`는 위치가 있는 template에서만 필수다. specific template에는 `violation_expression`도 필요하다.
3. 신고내용은 5~900자 범위를 검사한다.
4. `ReportPackage.report.template_ref`와 `provenance.policy_ref=safety-report-policy/v1.1`을 보존한다.
5. 사용자가 확인하지 않은 위반행위를 문장에 추가하지 않는다.
6. 위치가 없으면 장소 구절 자체를 빼며 `위치 미상`, `확인 필요`, 임의 주소·좌표를 넣지 않는다.
7. Package는 신고자료 준비 결과이며 안전신문고 자동입력·자동제출·처분 성공을 의미하지 않는다.
