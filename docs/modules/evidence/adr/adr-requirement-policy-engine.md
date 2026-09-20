# ADR-EVIDENCE-004: versioned requirement policy engine 구현 구조

> 상태: **ACCEPTED**
> 결정일: 2026-09-14
> Owner: 김준영 (`evidence`)
> 구현 근거: ADR-EVIDENCE-002 K1~K4, ADR-EVIDENCE-003 D1

## 1. Context

ADR-EVIDENCE-002·003이 확정한 정책을 Runtime 순수 함수에 연결하려면 정책 수치, rule 선택, 조건부 시각 분기, template 선택, 구성 오류와 업무 사실 부족의 경계를 한 구조로 정리해야 했다. 이 ADR은 정책값을 다시 정하지 않고 그 결정을 구현하는 구조만 기록한다. 실행 결과는 `../reviews/13_adr-002-003-implementation_2026-09-14.md`가 소유한다.

## 2. Decision

### 2.1 정책 파일과 loader

- K1은 `attachment_policy_v1.json`, K2는 기존 `deadline_policy_v1.json`, K3·D1은 `requirement_rules_v3.json`, 신고문은 `safety_report_policy_v1_1.json`에서 읽는다.
- `policy_catalog.py`가 JSON 로딩과 정책별 구조 검증을 소유한다. 활성 requirement catalog 파일명은 이 모듈의 한 상수에서만 선택한다.
- loader는 policy ref, 단위, 필수 limit, outcome 값, calendar coverage·source ref, scope·rule 수, 조건부 selector, template registry를 검증한다. 실패하면 `PolicyConfigurationError`를 발생시켜 정상 `RequirementReport`를 만들지 않는다.
- `requirement_rules_v2.json`은 수정하지 않는다. v2는 채택됐으나 첫 Artifact 실행 전에 v3로 대체됐고, v3의 supersedes ref가 이 이력을 보존한다.

이 구조는 정책 변경을 코드 분기와 분리하면서도 깨진 데이터가 일반 업무 결과처럼 보이지 않게 한다.

### 2.2 평가 호출 경계와 rule 선택

`evaluate_requirements()`는 `rule_codes`를 받지 않고 `EvidenceRecord`, scope, `TimeResolution`, AssetFacts, 관찰 fact, 평가 시점을 받는다. catalog가 report type과 scope에 맞는 항상 rule을 선택하고, FINAL_PACKAGE에서는 `TimeResolution.status`와 `post_stamp.reason_code`의 정확한 조합으로 시각 rule 하나를 추가한다.

모든 조건 판정 함수는 catalog outcome key까지만 결정하고, 실제 PASS/WARN/BLOCK/UNKNOWN 값은 rule data에서 읽는다. K1·K2는 하위 policy data의 outcome mapping을 읽으며 catalog가 그 하위 policy ref를 정확히 가리키는지 먼저 확인한다.

호출부인 Mock adapter와 단위 테스트는 새 `time_resolution` 인수를 전달하고 rule 목록을 더 이상 실행 입력으로 쓰지 않는다. adapter의 rule 배열은 활성 catalog 결과를 검증하는 기대값일 뿐이다.

### 2.3 관찰 fact

관찰 fact는 `{value: boolean, subject_refs: ContractRef[]}` 형태의 Python 호출 입력이다. 번호판·사건 장면·전 상황·후 상황·시각 표시처럼 문자열 확정값만으로 알 수 없는 사실에만 사용한다. 누락은 `UNKNOWN`, 명시적 false는 `BLOCK`, malformed 구조는 `PolicyConfigurationError`다.

이 객체는 새 Contract나 Runtime wire schema가 아니다. 생산·전달 경로는 기존 Owner 통합 항목이 소유한다.

### 2.4 D1 template과 필수 입력 분리

위치 snapshot은 address → place name → user hint 순으로 첫 유효 문자열을 고르고, 없으면 `null`을 반환한다. renderer는 사건 유형 확인 상태와 위치 유무를 조합해 네 template 중 하나를 고른다. 장소가 없으면 장소 구절을 제거하며 placeholder를 만들지 않는다.

`package.report.content_length` rule은 catalog의 `render_required_inputs_by_template`에서 위치 있음/없음의 필수 입력을 각각 읽는다. 따라서 위치 부재 WARN과 렌더 입력 완전성이 독립적으로 판정되고, `ReportPackage` builder는 최종 report의 `basis.template_ref`와 실제 renderer 선택이 같은지 확인한다.

### 2.5 오류와 업무 상태 경계

- 알 수 없는 policy ref, 깨진 limit/calendar/rule/outcome/template, selector 0개·복수 선택, malformed observation fact는 `PolicyConfigurationError`다.
- 유효한 구성 아래에서 자산 크기 미측정, 관찰 fact 부재, 미확정 렌더 입력, 시각 부재는 해당 check의 `UNKNOWN`이다.
- 확인된 제한 초과나 관찰 false는 `BLOCK`이다.
- 위치의 확정된 부재는 D1에 따라 `WARN`이다.

## 3. 채택하지 않은 대안

- 호출자가 `rule_codes`나 catalog 파일명을 선택: Consumer가 evidence 정책을 소유하게 되므로 채택하지 않았다.
- rule outcome을 Python 조건문에 직접 기입: v3의 위치 변경이 data와 code 두 곳에 중복되므로 채택하지 않았다.
- `post_stamp`를 EvidenceRecord에 투영: Final Contract 변경이 필요하므로 채택하지 않았다.
- 위치 없음 placeholder 또는 임의 좌표 생성: 확정되지 않은 Evidence를 만들므로 채택하지 않았다.
- 위치 유무를 하나의 template 내부 빈 슬롯으로 처리: template ref만으로 문장을 재현하기 어렵고 빈 구절이 남으므로 별도 ref를 선택했다.
- malformed 정책을 `UNKNOWN` report로 변환: 구성 장애와 업무 사실 부족이 섞이므로 채택하지 않았다.
- 정책 loader 결과를 전역 캐시: 현재 파일은 작고 검증 테스트의 교체 가능성이 더 중요하므로 채택하지 않았다.

## 4. Consequences

- 활성 catalog와 하위 정책의 ref가 맞지 않으면 모든 scope 평가가 fail closed한다.
- FINAL_PACKAGE는 항상 16개 check(15개 항상 rule + 시각 조건부 1개)를 갖는다.
- 기존 v1 ReportPackage validator는 non-null location 의미를 유지하고 v1.1 validator만 null을 허용한다.
- 정책 파일을 바꾸면 Artifact fingerprints가 달라져 실행 기준을 추적할 수 있다.
- 공용 입력에 관찰 fact가 없으면 새로운 rule이 정직하게 `UNKNOWN`을 만들 수 있으며, 이는 policy regression과 구분해 해석해야 한다.

## 5. 이 구현이 확정하지 않은 것

- 실제 사건·전후 상황 관찰 fact의 생산·전달 방식(I4)
- `CaseView`의 위치 field state와 사용자 고지 code
- 공용 H/U Package fixture의 v1.1 재렌더(I2)
- 선택적 위치 질의(④, `DEFERRED`)
- `ReportPackage.assets`를 최대 4개 첨부로 확장하는 Contract 변경
- PLATE_IMAGE 생성·크기 측정 책임과 비시각 correction의 실제 Consumer 검증
- 2028년 이후 공휴일 snapshot

D1의 evidence 정책 결정 자체는 ADR-EVIDENCE-003으로 종결됐다. 위 항목은 D1을 다시 여는 미결이 아니라 다른 Owner 또는 후속 revision의 통합 범위다.

## 6. 발견한 불일치와 근거

구현 발주 W5와 ADR-EVIDENCE-002 §5.15는 공용 H/U/P/R에 사건·전·후 상황 관찰 fact가 없으므로 `UNKNOWN`을 유지하고 사실을 만들지 말라고 한다. W6·W12와 같은 ADR의 D1 정정 블록은 동시에 공용 U의 FINAL_PACKAGE가 WARN이고 Package가 유지돼야 한다고 적는다. `UNKNOWN` precedence가 WARN보다 높아 같은 입력에서는 양쪽을 동시에 만족할 수 없다.

구현은 입력 사실을 만들지 않는 경계를 우선했다. 공용 U의 v3 baseline은 FINAL_PACKAGE `UNKNOWN`이며, D1의 WARN Package는 세 관찰 fact를 명시한 test-derived 입력에서 별도로 검증한다. 정책 원문을 수정하지 않았으며 Owner가 ADR 변경 규칙에 따라 문구를 정리해야 한다.

> **종결 (2026-09-14).** Owner가 [`ADR-EVIDENCE-005`](adr-event-context-rules-removal.md)로 **세 관찰 rule 자체를 제거**해 이 불일치를 해소했다. 원인은 두 지시의 충돌이 아니라 **판정 입력을 생산하는 모듈이 계약 어디에도 없는 rule을 등재해 둔 것**이었다. v4 catalog 반영 후 공용 U는 `WARN`이고 `pkg_u001`이 발행되므로 D1 정정 블록의 기대가 조건 없이 성립한다. 위 구현 판단(입력 사실을 만들지 않음)은 그대로 옳았고 유지된다. 분석 경위는 [`reviews/14_…`](../reviews/14_instruction-conflict-analysis-and-doc-fixes_2026-09-14.md).

발주 W12의 `validate_report_package(pkg_u001) == []`과 공용 fixture 수정 금지도 같은 이유로 동시에 문자 그대로 만족할 수 없다. 디스크의 `pkg_u001`은 v1이므로 v1 의미상 null location이 유효하지 않다. 구현 검사는 payload를 v1.1로 전환한 사본에서 `[]`를 확인하고 원본 fixture 동기화는 I2로 남긴다.
