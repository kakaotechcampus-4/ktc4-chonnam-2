# ADR-EVIDENCE-001: Final Contract 기반 1차 Mock 통합 구현 구조

> 상태: **ACCEPTED**
>
> 결정일: `2026-09-13`
>
> Decider / Owner: 김준영 (`evidence`)
>
> 적용 범위: 1차 Mock 통합 baseline의 내부 구현 구조
>
> 준비도: **PARTIAL_READY** — 실제 `case` Consumer 접합과 Q1은 완료되지 않음

## 1. 배경

`evidence`는 공용 Mock에서 `case`가 전달하는 관찰·판독·선택 context·사용자 정정·자산 사실을 소비해 다음 Final Contract를 생산해야 한다.

- `TimeResolution`
- `EvidenceRecord`
- `EvidenceNeeds`
- `RequirementReport`
- `ReportPackage`

구현 전에는 `src/daesingo/evidence/README.md` 골격만 존재했다. 1차 통합에서는 production runtime이나 실제 AI/OCR/영상 처리를 만드는 대신, 현재 Final Contract와 공용 H/U/P/R Scenario를 실제로 실행할 수 있는 최소 경계가 필요했다.

동시에 다음 제약을 지켜야 했다.

- `evidence`는 Queue, Worker, Job 발주, retry, storage를 구현하거나 호출하지 않는다.
- 공용 `data/mock/` 원본과 다른 Owner의 모듈을 구현 편의상 수정하지 않는다.
- Observation, authoritative Evidence, Requirement, Package, 사용자 검토 상태를 합치지 않는다.
- 사용자 정정과 재판독은 과거 결과를 덮어쓰지 않는다.
- 확정되지 않은 위치·시각·번호판·가시성·정책 수치를 만들어내지 않는다.
- 공용 Fixture 재생, 실제 계약 처리, Consumer Mock, 실제 Consumer 접합을 서로 구분한다.

이 ADR은 위 제약 안에서 채택한 **구현 구조**를 기록한다. 필드·enum·nullable·Owner 경계를 새로 확정하는 Contract ADR이 아니다.

## 2. 근거와 우선순위

구현 판단은 다음 순서를 따른다.

1. Product 범위: [`product-spec.md`](../../../product/product-spec.md)
2. 모듈 경계: [`module-architecture.md`](../../../architecture/module-architecture.md)
3. 필드와 invariant: `docs/architecture/contracts/`의 현재 Final Contract와 후속 종결 ADR
4. evidence 확정 정책: [`safety-report-policy-v1.md`](../decisions/safety-report-policy-v1.md), [`source-kind-registry.md`](../decisions/source-kind-registry.md)
5. 실행 완료 기준: [`first-completion-checklist.md`](../first-completion-checklist.md)
6. 공용 입력: `data/mock/`의 실제 JSON

옛 Mock 설명이나 validator PASS만으로 계약 의미 또는 E2E 완료를 판정하지 않는다.

## 3. 결정

### 3.1 공개 경계는 Final Contract 값을 받는 순수 함수로 둔다

`daesingo.evidence`는 JSON 역직렬화 값인 `dict`를 받고 Final Contract 형태의 `dict`를 반환한다.

| 공개 함수 | 역할 | 주요 출력 |
| --- | --- | --- |
| `resolve_time` | 시간 후보·정정·선택 context를 판정 | `TimeResolution` |
| `assemble_evidence` | 확정값과 provenance를 조립 | `EvidenceRecord` |
| `calculate_evidence_needs` | 현재 Evidence의 선언적 부족분 계산 | `EvidenceNeeds` 또는 부재 |
| `evaluate_requirements` | scope별 rule outcome 집계 | `RequirementReport` |
| `build_report_package` | ready 조건을 만족할 때만 조립 | `ReportPackage` |
| `render_report` | 확정 정책의 결정론적 신고문 생성 | Package report 입력 |
| `correction_heads` | 정정 target별 타입·chain head 검증 | 내부 조립 입력 |
| `validate_contract` | 다섯 출력의 최소 공개 경계 검사 | 오류 목록 |

새 wire schema나 공용 runtime DTO를 만들지 않는다. `scenario_id`, Fixture 경로, 테스트용 출력 ID, 평가 시각, rule 목록은 공개 입력에 포함하지 않는다.

### 3.2 내부 책임을 계약 처리 단계별로 분리한다

| 파일 | 책임 |
| --- | --- |
| `_contract.py` | 공통 ContractRef·RFC3339·필수값 경계 검사 |
| `corrections.py` | CorrectionRecord 타입과 supersedes chain 검증 |
| `time_resolution.py` | 시간 source 우선순위·충돌·사용자 override 판정 |
| `assembly.py` | EvidenceRecord와 EvidenceNeeds 조립 |
| `policy.py` / `policy_data.json` | 확정된 유형 매핑과 신고문 renderer |
| `requirements.py` | 두 scope 판정, 우선순위, ready-only Package 조립 |
| `validation.py` | 출력 Contract 최소 invariant 검사 |

이 분리는 내부 선택이다. 각 파일이나 함수 이름을 다른 모듈이 의존해야 하는 새 계약으로 취급하지 않는다.

### 3.3 공용 Mock adapter는 공개 처리 경계와 분리한다

`mock_integration.py`는 공용 H/U/P/R JSON을 로딩하고 공개 함수를 호출하는 evidence 전용 실행 도구다. `daesingo.evidence.__init__`에서 export하지 않으며 production API로 간주하지 않는다.

adapter가 담당하는 것은 다음뿐이다.

- 공용 Contract JSON 로딩
- 테스트에 필요한 명시적 upstream fact와 생성 ID 주입
- 공개 함수 호출 순서 구성
- Scenario 출력과 원본 경로 기록
- 공개 Contract만 읽는 Consumer Mock 실행
- 재현 Artifact 생성

`scenario_id`를 보고 미리 정한 Contract 출력을 반환하지 않는다. Fixture별 차이는 adapter 입력에 명시하고, 시간 판정·Evidence 조립·Requirement 평가·Package 생성은 실제 공개 함수가 수행한다.

### 3.4 불충분하거나 미확정인 입력은 fail-closed로 처리한다

정상 Package는 다음을 모두 만족할 때만 생성한다.

- `FINAL_PACKAGE` Requirement가 `PASS` 또는 `WARN`
- 필수 자산이 존재하고 사용할 수 있음
- 시간·번호판·위치 등 Package 필수 입력이 존재함
- 신고문에 쓰는 사건 유형에 사용자 응답 provenance가 있음
- 결정론적 조립이 성공함

specific 신고문은 `CONFIRMED` 또는 `CORRECTED`, generic 신고문은 `USER_UNSURE` 응답을 요구한다. 조건을 만족하지 않으면 renderer 또는 Package 조립이 오류로 중단되며 정상 Package나 새로운 Runtime status를 만들지 않는다.

공용 H `CaseView`의 `NOT_ASKED` 경로는 미발행 결과로 보존한다. H의 정상 Package baseline은 evidence 전용 `TEST_DERIVED_CONFIRMATION`을 명시적으로 주입한 Mock 연결이며, 공용 case 원본과 동일하다고 주장하지 않는다.

### 3.5 재판독과 정정 결과는 immutable snapshot으로 추가한다

- 새 판독이나 정정은 새 `TimeResolution`, `EvidenceRecord`, `RequirementReport`, `ReportPackage`를 만든다.
- 대체 관계는 `supersedes_ref`로 연결한다.
- 기존 snapshot과 unrelated 값은 변경하지 않는다.
- `selection_rev`는 선택 context로 유지하고 정정 횟수나 retry 횟수로 사용하지 않는다.
- 생성 ID는 opaque ref로 취급하고 Consumer에는 실제 생성한 ref를 전달한다.

P에서는 첫 번호판 ABSTAIN snapshot과 재판독 성공 snapshot을 모두 보존한다. R에서는 `EVENT_TIME_MANUAL` correction이 시간 lineage만 바꾸고 기존 번호판·후보 위치·`selection_rev=1`을 유지한다.

### 3.6 EvidenceNeeds는 선언 값으로만 생산한다

`EvidenceNeeds`는 현재 Evidence에서 부족한 값을 설명한다. evidence는 이를 바탕으로 readout이나 runtime을 호출하지 않는다.

- `PLATE_REREAD` Need와 `PLATE_READ` Job을 같은 enum으로 취급하지 않는다.
- Need의 실제 Job 변환과 stale basis 재검증은 `case` 책임이다.
- `items=[]`은 `EVIDENCE_SUFFICIENT`, `PACKAGE_READY`, `USER_REVIEWED` 중 어느 것도 단독으로 보장하지 않는다.

### 3.7 Requirement와 Package gate를 분리한다

- 두 scope는 `EVIDENCE`와 `FINAL_PACKAGE`로 별도 평가한다.
- outcome 우선순위는 `BLOCK > UNKNOWN > WARN > PASS`다.
- 판정 결과가 `UNKNOWN`인 것과 판정/조립 자체를 실행하지 못한 것을 구분한다.
- `EvidenceNeeds`, Requirement outcome, Package 생성 여부, 사용자 검토 상태를 서로 파생 동의어로 사용하지 않는다.
- 번호판 문자열 확정과 신고영상 안의 번호판 가시성, 시각 확정과 영상의 시각 표시를 별도 fact로 받는다.

기한과 첨부 용량은 채택된 수치·계산 규칙이 없으므로 임의 baseline을 만들지 않는다. 해당 rule이 요청되면 policy configuration 오류로 드러낸다.

### 3.8 실행 Artifact는 코드와 별도 검토 단위로 남긴다

`python -m daesingo.evidence.mock_integration`은 다음을 `artifacts/first-completion/`에 기록한다.

- 원본 입력 JSON 경로와 입력 추적 정보
- 실제 생성한 Contract 배열
- 공용 expected와의 비교 및 알려진 차이
- Consumer Mock 판독
- 실행 코드 revision과 구현·테스트 파일 fingerprint
- baseline, upstream Mock, 파생 Mock, Consumer Mock의 구분

Artifact의 `base_revision`은 Artifact를 포함하는 문서 커밋이 아니라 **실제로 실행한 코드 커밋**을 가리킨다. 현재 0번 수정 증빙은 `16c078f`를 기준으로 생성됐다.

### 3.9 Consumer Mock은 실제 case 접합 완료로 간주하지 않는다

Consumer Mock은 공개 Contract에서 current head와 `EVIDENCE_SUFFICIENT`, `PACKAGE_READY`에 필요한 참조를 읽을 수 있는지만 확인한다.

다음은 수행하지 않는다.

- 실제 `CaseView` 생성
- case의 Need → Job 변환
- `USER_REVIEWED` 판정
- web projection
- 저장·재시도·취소 lifecycle

따라서 현재 준비도는 `PARTIAL_READY`다.

## 4. 검토한 대안

| 대안 | 판단 | 이유 |
| --- | --- | --- |
| Scenario별 완성 JSON을 그대로 반환 | 기각 | Fixture 재생만 증명하며 판정·조립 구현을 검증하지 못함 |
| evidence 안에 Queue/Worker/Job 발주 구현 | 기각 | common/runtime와 case Owner 경계를 침범함 |
| 공용 Mock 원본을 구현에 맞게 수정 | 기각 | 다른 Owner의 입력과 알려진 불일치를 은폐함 |
| U 위치에 placeholder 또는 새 nullable 규칙 추가 | 기각 | Q1 Contract 결정을 evidence 구현이 대신하게 됨 |
| 기존 Evidence snapshot을 in-place 수정 | 기각 | correction·재판독 provenance와 과거 결과를 훼손함 |
| `EvidenceNeeds.items=[]`이면 Package 생성 | 기각 | Evidence, Requirement, Package gate를 혼동함 |
| 미확정 위반유형으로 specific 신고문 생성 | 기각 | 사용자가 확인하지 않은 위반 사실을 확정하게 됨 |
| 새 모델 계층이나 외부 validation 라이브러리 도입 | 보류 | 1차 Mock 범위에서 새 공용 추상화·의존성을 정당화하지 못함 |

## 5. 결과와 trade-off

### 긍정적 결과

- 다른 모듈이나 runtime 없이 Final Contract 경계를 실행할 수 있다.
- H/U/P/R의 불확실성, 재판독, 정정, supersede 차이가 보존된다.
- Package가 준비되지 않은 경로를 정상 출력으로 위장하지 않는다.
- 공용 Mock 원본을 변경하지 않고 계약 충돌과 파생 입력을 추적할 수 있다.
- Consumer가 어떤 Contract ref를 실제로 받을 수 있는지 JSON Artifact로 확인할 수 있다.

### 감수하는 비용과 한계

- `dict` 기반 경계는 정적 타입 모델보다 IDE 지원이 약하다.
- `validate_contract`는 최소 invariant 검사이며 전체 JSON Schema 검증이나 Owner 수락을 대신하지 않는다.
- adapter가 Scenario 입력을 조립하므로 production orchestration과 동일하지 않다.
- 실행 Artifact가 커서 코드 diff와 함께 보면 리뷰 비용이 크므로 별도 커밋으로 관리한다.
- 실제 case 구현이 준비되면 Consumer Mock으로는 발견할 수 없는 projection·head 선택 문제가 나올 수 있다.

## 6. Scenario별 적용 결과

| Scenario | 구현 결과 | 현재 판정 |
| --- | --- | --- |
| H | 공용 `NOT_ASKED`는 차단, test-derived `CONFIRMED`에서 PASS/PASS와 Package 생성 | 정책 guard 검증 및 Mock 연결 완료 |
| U | `NEEDS_REVIEW`, 충돌 provenance, `USER_UNSURE`, WARN/WARN 보존 | Q1 때문에 정상 Package 보류 |
| P | ABSTAIN snapshot의 `PLATE_REREAD`와 재판독 성공 snapshot을 모두 보존 | Mock 연결 완료, Package는 Scenario 범위 밖 |
| R | 수동 시각 정정 후 새 time/evidence/report와 supersede lineage 생성 | Mock 연결 완료, Package는 Scenario 범위 밖 |

## 7. 검증

구현과 Artifact는 다음 명령으로 재현한다.

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests/evidence -p 'test_*.py' -v
python -m daesingo.evidence.mock_integration
python -m ruff check src/daesingo/evidence tests/evidence
python data/mock/validate_mock_pack.py
python scripts/check_contract_fixtures.py
python scripts/check_boundaries.py
git diff --check
```

현재 증빙:

- evidence 테스트: 21건 통과
- 공용 Mock: 46 JSON / 7 Scenario 통과
- Contract fixture: 문서 60 / JSON 26 / 의미 104 통과
- boundary violation: 0건
- Ruff, compileall, `git diff --check`: 통과

이 결과는 실제 AI/OCR 정확도, production runtime, 실제 `case`/web E2E, 외부 제출, Consumer Owner 수락을 증명하지 않는다.

## 8. 이 ADR이 결정하지 않는 것

| 항목 | 상태 | 다음 책임 |
| --- | --- | --- |
| U Package의 `location=null`과 Final 필수 위치 구조 충돌(Q1) | Contract 변경 검토 필요 | Contract Owner 및 관련 Producer/Consumer 협의 |
| 공용 H/U Package의 옛 문구·Template·policy provenance(Q2) | evidence 구현과 공용 Fixture 동기화 분리 | Mock Pack 담당 및 관련 Owner |
| TimeResolution timeline revision 직접 필드(Q3) | 기존 ref로 추적, 비차단 | 향후 Contract 변경 시 반영 |
| 첨부 용량·신고기한 수치 policy | 결정 대기 | evidence Owner가 근거와 함께 채택 |
| 실제 CaseView projection과 Need → Job 변환 | 통합 대기 | `case` Owner |

## 9. 변경 규칙

다음 변경은 이 구현 ADR만 고쳐서 진행하지 않는다.

- Final Contract의 필드·enum·nullable 변경
- Producer/Consumer 또는 orchestration Owner 변경
- Requirement severity나 Package ready 조건의 정책 변경
- 신고유형·Template registry 변경
- 새로운 EvidenceNeed kind 추가

이 경우 원 Contract/정책의 Owner 결정과 version 변경을 먼저 반영한 뒤 구현과 이 ADR을 갱신한다.

내부 파일 분리, helper 이름, 테스트 구성처럼 계약 의미를 바꾸지 않는 선택은 evidence 범위에서 변경할 수 있다.

## 10. 관련 구현과 증빙

- 공개 사용법: [`src/daesingo/evidence/README.md`](../../../../src/daesingo/evidence/README.md)
- 수행 결과: [`first-completion-result.md`](../first-completion-result.md)
- 실행 요약: [`artifacts/first-completion/run-summary.json`](../artifacts/first-completion/run-summary.json)
- 후속 결정·통합 목록: [`reviews/10_first-completion_decisions_and_integration_2026-09-13.md`](../reviews/10_first-completion_decisions_and_integration_2026-09-13.md)
- 구현 커밋: `7732230`, `91c1ce9`, `1295f57`
- 사용자 확인 gate: `16c078f`
- 실행 증빙 갱신: `08eb78c`

## 11. 한 줄 결정

> `evidence` 1차 Mock 통합은 Final Contract 값을 받는 순수 함수 경계로 구현하고, 공용 Scenario adapter와 Consumer Mock은 명시적인 테스트 도구로 격리하며, 미확정 입력에서는 fail-closed하고 immutable provenance를 보존한다.
