# GPT-5.6 Sol 전달용 — 김준영 evidence 1차 구현 프롬프트

이 문서 전체를 저장소에 접근 가능한 GPT-5.6 Sol 작업에 전달한다. 기준 문서는 `docs/modules/evidence/`의 [김준영 1차 완료 체크리스트](../first-completion-checklist.md)다. 아래 요청은 계획 작성에 그치지 않고 구현·테스트·Merge 증빙 작성까지 수행하는 작업 지시다.

---

당신은 대신고 모노레포에서 김준영 담당 `evidence`의 1차 Mock 통합 준비를 구현하는 엔지니어다.

**`docs/modules/evidence/first-completion-checklist.md`를 완료 기준으로 삼아, 현재 Final Data Contract와 공용 Mock Scenario에 연결되는 실행 가능한 결과를 만들어라.** 짧은 계획을 먼저 공유한 다음, 이미 결정된 범위는 사용자 확인을 반복해서 요구하지 말고 구현·검증·결과 정리까지 진행하라.

이 작업은 production 완성이나 전체 시스템 구현이 아니다. 내부 클래스·함수·라이브러리 구조는 저장소 규칙과 현재 코드에 맞게 선택하되, 다른 모듈과 주고받는 계약과 Owner 경계는 바꾸지 마라.

## 1. 목표와 담당 범위

구현 대상은 `evidence`다.

- `case`가 전달한 관찰·판독·시각 후보·선택 context·사용자 정정·자산 사실을 소비한다.
- `TimeResolution`, `EvidenceRecord`, `EvidenceNeeds`, `RequirementReport`, `ReportPackage`를 각각의 Final Contract에 맞게 생산한다.
- 불확실·ABSTAIN·부분 재판독·시각 정정에서 확보된 값과 provenance를 보존한다.
- Consumer가 공개 입력/출력 경계에서 결과를 읽을 수 있음을 실제 실행으로 입증한다.
- 체크리스트 항목별로 코드·테스트·Artifact 증빙을 연결한다.

**김준영은 common/runtime의 계약·설계 Owner이며 구현 담당이 아니다. common/runtime 구현은 이 작업에서 제외한다.** Queue, Worker, lease, heartbeat, retry, 취소, 비용 장부, 마스킹 로거, config/storage 기반 계층, CI/CD를 새로 구현하지 마라. evidence 구현을 위해 공통 실행기를 먼저 만들어야 한다는 방향으로 범위를 넓히지 마라.

`Observation<T>`는 김준영 소유 공통 계약이지만 관찰값 Producer는 upstream이다. `CorrectionRecord`, `JobRecord`, `CaseView`는 case의 출력이다. `JobExecution`, `UsageRecord`도 evidence 출력으로 만들지 마라.

## 2. 시작할 때 확인할 것

1. 현재 브랜치·HEAD·작업 트리 변경과 적용되는 `AGENTS.md`, `CLAUDE.md`, `docs/README.md`를 확인한다.
2. 기존 변경과 새로 수행할 변경을 구분한다. 이 프롬프트와 체크리스트가 미커밋 파일이어도 사용자의 작업물로 보존한다.
3. 체크리스트 전체를 읽고, 현재 evidence 코드·테스트·Technical Spec·공개 입력 경계를 확인한다. 구현이 이미 있으면 이어서 작업하며 중복 구현하지 않는다.
4. 현재 실행 환경·의존성·테스트 관례를 확인하고 기존 공용 검증 3종의 시작 상태를 기록한다.
5. 담당 범위, 구현 순서, 예상 변경 경로, 남아 있는 계약 문제를 짧게 공유한 뒤 구현을 시작한다.

프롬프트 작성 시 확인한 상태는 `develop`의 `72e0e05`, evidence는 README 골격, 공용 Pack은 46 JSON·7 Scenario였다. **이는 과거 스냅샷이다. 실행 시 현재 상태를 확인하고 이미 구현되거나 해결된 항목을 다시 만들지 마라.**

## 3. 읽을 자료와 우선순위

모든 경로는 저장소 루트 기준이다. 체크리스트에 링크된 자료를 활용하고, 필요한 부분을 먼저 읽어라.

### 먼저 읽을 문서

- `docs/modules/evidence/first-completion-checklist.md`
- `docs/product/product-spec.md` §5·§7
- `docs/product/core-user-flow.md`의 사용자 보정·번호판·발생시각·신고 상황·신고요건·최종 확인·실패 복구 부분
- `docs/architecture/module-architecture.md`의 원칙, evidence, 관련 Contract·접합부 부분
- `docs/management/ownership.md`의 김준영 및 Producer/Consumer 경계
- `src/daesingo/evidence/README.md`와 현재 evidence 코드/테스트/Technical Spec

### 출력 계약과 사용자 정정

- `docs/architecture/contracts/contract-observation.md`
- `docs/architecture/contracts/contract-time-resolution.md`
- `docs/architecture/contracts/contract-evidence-record-needs.md`
- `docs/architecture/contracts/contract-requirement-report-package.md`
- `docs/architecture/contracts/contract-correction-record.md`

입력 구조가 필요하면 같은 폴더의 source asset, timeline/asset span, analysis source/derived, candidate/visual evidence, plate/overlay/readout run 계약을 읽는다. Consumer 검증에는 `contract-job-record-case-view.md`의 해당 projection 규칙을 확인한다.

### 확정 결정과 Mock

- `docs/modules/evidence/decisions/safety-report-policy-v1.md`
- `docs/modules/evidence/decisions/source-kind-registry.md`
- `docs/modules/evidence/decisions/no-separate-signoff.md`
- 각 Final의 Related ADR 및 2026-09-07·08 계약 종결 ADR의 해당 조항
- `docs/modules/case/decisions/generic-warn-package-and-situation-response.md`의 후속 결정
- `docs/mock/01_mock_dataset_overview.md`
- `docs/mock/02_mock_scenario_catalog.md`
- `docs/mock/03_mock_artifact_templates.md`
- `docs/mock/04_mock_validation_report.md`
- `data/mock/manifest.json`, 해당 Scenario manifest, 모듈별 실제 JSON

Research PDF 3개는 체크리스트가 지정한 관련 절을 보조 근거로만 읽는다. Architecture Input Memo는 확정 근거 추적이 필요할 때만 읽는다. Research의 예전 enum·권장 내부 구조·미확정 수치를 그대로 구현 규칙으로 승격하지 마라.

제품 범위는 Product Spec, 모듈 경계는 Architecture, 구체적 필드·enum·nullable·invariant는 현재 Final과 확정된 후속 결정을 따른다. 체크리스트는 완료 기준이며 Final을 덮어쓰는 새 계약이 아니다. 서로 충돌하면 원문 조항과 실제 JSON 경로를 기록하라. 옛 검수 보고서의 PASS나 Mock Overview의 오래된 미결 문구만으로 현재 상태를 결정하지 마라. `docs/archive/`는 현재 구현 기준으로 사용하지 마라.

## 4. 변경할 수 있는 범위

- evidence 코드, evidence 전용 테스트·실행 도구·검증 Artifact, evidence 문서를 작성·수정한다. 구체적 파일 구성은 현재 저장소 관례에 맞게 선택한다.
- 기존 공용 타입/유틸이 있으면 공개 경계와 계약 안에서 재사용한다. 필요 이상의 전역 패키지 설정·의존성·공통 추상화를 도입하지 마라.
- 다른 Owner의 모듈 구현·문서, canonical Final Contract, 공용 `data/mock/` 원본, 공용 validator를 테스트 통과 목적으로 수정하지 마라.
- 공용 Fixture에 문제가 있으면 원본을 보존한다. evidence 전용 테스트에 파생 입력/expected가 필요할 때는 원본 Scenario와 JSON 경로, 변경점, 확정 근거를 기록한다. 그 파생 결과를 공용 Pack 원본 통과로 보고하지 마라.
- 새로운 공통 Scenario ID를 만들지 마라. Contract 단위 테스트의 이름은 자유롭게 정하되 공통 E2E Scenario인 것처럼 등록하지 마라.
- 타 모듈 직접 구현, 실제 AI/OCR API 호출, ffmpeg 영상 생성, 외부 제출 자동화는 하지 마라. 이에 의존하는 입력은 공용 Mock으로 대체할 수 있다.
- 기존 파일/결과를 덮어쓰는 정리, 다른 작업의 되돌리기, 커밋·push·PR 생성·외부 댓글/메시지는 별도 지시 없이 수행하지 마라.

수정 범위 밖에서 필요한 작업은 구체적인 대상·변경 이유·완료 조건을 후속 목록에 남겨라. 김준영이 PM이라는 이유로 다른 Owner의 미결 결정을 대신 확정하지 마라.

## 5. Q1·Q2·Q3 처리 — 전체 작업을 멈추지 말 것

체크리스트의 확인 항목이 현재도 남아 있는지 먼저 재검증한다. 해결됐다면 근거 파일·조항·revision을 기록하고 해소된 기준으로 진행한다.

| 항목 | 아직 미해결일 때의 행동 |
| --- | --- |
| Q1: U Package의 `report_inputs.location=null`과 Final의 필수 위치 구조 충돌 | `Contract 변경 검토 필요`로 남긴다. null 허용·placeholder·새 location 필드를 임의로 도입하지 않는다. U의 시간/Evidence/Requirement 처리는 구현·검증하고, 정상 Package 접합 완료만 보류한다. 보류 이유는 검증 보고서에서 설명하며 새 Runtime status를 만들지 않는다. |
| Q2: H/U 신고문·Template·정책 provenance 불일치 | 확정된 `safety-report-policy-v1.md`에 따라 구현할 수 있는 renderer/출력은 진행한다. 기존 Fixture 문구를 맞추기 위해 정책을 약화하지 않는다. 근거가 있는 evidence 전용 검증 결과와 공용 Fixture 동기화 대기를 구분한다. 이미 확정된 정책 준수에 별도 승인을 다시 요구하지 않는다. |
| Q3: TimeResolution의 timeline revision 직접 필드 미정 | 현재 Final이 허용한 ref 경로로 사용 revision을 추적한다. 새 필드를 신설하지 않는다. 기존 경로로 추적 가능한 경우 비차단 후속으로 남긴다. |

추가 모호성이 나오면 다음처럼 분류한다.

- **내부 구현 선택:** 관례와 최소 변경 원칙으로 결정하고 계속한다.
- **이미 확정된 계약/정책의 반영:** 근거를 남기고 내 범위에서 구현한다.
- **상대 실제 구현 부재:** 동일 Contract의 Mock으로 연결을 검증하고 실제 접합은 통합 대기로 기록한다.
- **새 필드·enum·nullable·정책 판정·Owner 경계 결정:** `Contract 변경 검토 필요` 또는 `담당 범위 확인 필요`로 분리하고 종속 부분만 보류한다.

입력이 부족한 데도 가시성 PASS, 기한/용량 적합, 위치/번호판/시각 확정을 만들어내지 마라. 공용 Mock에 필요한 policy data나 사용자 응답이 누락됐다면 무엇이 부족한지 드러내고, 계약 밖 입력을 조용히 필수화하지 마라.

## 6. 구현과 검증의 진행 순서

### 단계 A — 추적표와 입력/출력 경계

체크리스트의 항목을 구현 위치·검증 항목·출력 Artifact로 연결할 추적표를 준비한다. 문서 작업만으로 시간을 소진하지 말고 구현 중 함께 갱신한다.

공용 Fixture를 로딩해 필요한 Contract 객체를 전달하는 실행 경로를 준비한다. Mock 관리 필드나 파일 이름을 새로운 도메인 입력 필드로 요구하지 마라. 공개 함수 서명이 이미 확정돼 있으면 이를 따르고, 없으면 기존 Contract 값으로 호출 가능한 최소 경계를 문서화하되 새 wire schema/API를 확정했다고 주장하지 마라.

### 단계 B — H의 정상 연결

`scenario_happy_001`로 시각·Evidence·빈 Needs·두 scope의 Requirement·Package의 ref 연결을 만든다. 확정된 정책으로 처리 가능한 부분은 실행 가능한 baseline으로 작성한다. 외부 관찰·미디어·미준비 Consumer는 Mock으로 대체할 수 있다.

`scenario_id`만 보고 미리 정해진 결과를 반환하는 경로는 명시적인 Fixture 재생으로만 취급하라. 이를 시간 판정·요건 엔진·신고문 생성 구현의 증거로 삼지 마라. 반대로 1차 연결에 충분한 Mock 영역에 실제 AI·OCR·인프라 구현을 강제하지 마라.

### 단계 C — U/P/R의 차이를 보존

| 공통 Scenario | 반드시 확인할 결과 |
| --- | --- |
| `scenario_unknown_abstain_partial_001` | 사건 유형 `UNCERTAIN`, 사용자 `USER_UNSURE`, `visual_event_type.value=null`, 시각 fallback의 `NEEDS_REVIEW`·충돌 provenance, 일반 신고문·WARN 경로. 이 Scenario를 번호판 ABSTAIN 테스트로 해석하지 않는다. Package는 Q1·Q2 상태와 분리해 판정한다. |
| `scenario_plate_reread_001` | 첫 ABSTAIN에서 번호판 부재, 다른 증거 유지, `PLATE_REREAD` Need·EVIDENCE UNKNOWN. 새 판독 입력 이후 새 Evidence에 번호판 `17나2867`, 새 basis의 빈 Needs·EVIDENCE PASS. `selection_rev=1` 유지. 이 Scenario에 Package 완료를 추가 요구하지 않는다. |
| `scenario_correction_rerun_001` | case의 `EVENT_TIME_MANUAL` correction 소비, `USER_OVERRIDE`의 단방향 invariant, 새 time/evidence/report와 supersede 연결. 번호판 `34나7890`·후보 위치·`selection_rev=1` 보존. correction을 evidence가 생산하지 않는다. |

`scenario_empty_001`, `scenario_infra_failure_001`, `scenario_relative_rebase_001`에는 evidence가 직접 참여하지 않는다. 이들을 완료시키기 위해 case/runtime/recording을 구현하지 마라.

### 단계 D — 최소 Contract 경계 검사

체크리스트의 「공용 Scenario 밖에서 필요한 최소 Contract 단위 검증」을 따른다. 특히 다음을 확인한다.

- 시간 근거가 없을 때 UNKNOWN과 `resolved`/`occurred_at` 부재.
- 두 scope의 outcome과 `BLOCK > UNKNOWN > WARN > PASS`, 정상 Report 미생성과 판정 UNKNOWN의 차이.
- 필수 자산 부재·판정/조립 실행 실패·BLOCK/UNKNOWN에서 정상 Package 미생성.
- optional plate image 부재, 정정 후 Package 대체 시 provenance와 과거 결과 보존.
- 사용자 정정의 target별 타입·head·실제 반영 여부, `CORRECTED`와 `USER_UNSURE` 구분.
- 초기 4종 매핑과 Template 조건, 채택한 baseline의 내용 길이·첨부 용량·기한 검사.

실제 판정 규칙이 미정인 항목은 임의 숫자·임계값·상태 매핑으로 채우지 마라. 관련 검사만 미검증/결정 대기로 표시하고 근거가 확정된 다른 검사를 진행하라.

테스트는 실제 public 경계의 결과를 관찰하고 입력·출력 참조와 보존 조건을 확인해야 한다. 테스트가 구현 함수를 그대로 호출해 expected를 만들거나, Fixture 복사만으로 계산 정확성을 증명하지 않도록 하라. 기존 테스트 러너를 우선 사용하고, 없다면 환경에 맞는 최소 실행 방식으로 구성하라.

### 단계 E — Consumer와 연결

실제 case의 공개 Consumer가 준비돼 있으면 범위 안에서 연결 검증한다. 준비되지 않았으면 evidence 전용 테스트에서 Contract JSON을 읽는 Consumer Mock으로 검증한다. 실제 case 구현 파일을 고쳐 가짜 연결 완료를 만들지 마라.

Consumer가 결과를 읽는 것과 실제 CaseView projection·web 동작을 각각 구분한다. evidence가 case 정책을 재구현하거나 테스트용 mock projection을 실제 case 실행으로 보고하지 마라.

## 7. 반드시 지킬 의미 경계

- `EvidenceNeeds`는 선언적 부족분이다. evidence가 readout·recording·runtime을 직접 호출하거나 Job을 발주하지 않는다.
- Need의 `PLATE_REREAD`와 Job의 `PLATE_READ`는 다른 enum이다. 재발주 변환·stale Need 처리의 주체는 case다.
- 관찰값, authoritative Evidence, Requirement 판정, Package, 사용자 검토 상태를 서로 합치지 않는다.
- `TimeResolution.post_stamp`는 정책 결과이며 실제 영상 생성 완료가 아니다.
- 번호판 문자열 확정과 신고영상 가시성, 시각 확정과 영상 시각 표시를 구분한다. 필요한 사실은 실제 입력 또는 표시된 Mock 근거로 입증한다.
- 사용자 정정·재판독 결과로 과거 snapshot을 덮어쓰거나 unrelated 값을 바꾸지 않는다.
- `selection_rev`는 선택 context이며 `case_rev`, 정정 횟수, 재시도 횟수가 아니다.
- ID는 opaque ref로 취급한다. 생성 ID가 Fixture ID와 다르면 테스트 자료에서 대응을 설명하고 실제 Consumer에는 생성한 ref를 전달한다.
- 신고유형 code와 handoff label의 표현을 무조건 문자열 동일성으로 검증하지 않는다. 현재 계약과 확정 mapping을 따른다.
- `EVIDENCE_SUFFICIENT`, `PACKAGE_READY`, `USER_REVIEWED`는 서로 다른 조건이다. `EvidenceNeeds.items=[]`만으로 어느 gate도 성공 처리하지 않는다.

## 8. 실행·검증·리뷰

현재 저장소에 존재하는 공용 검증 명령은 다음과 같다. 실제 상태에 맞게 실행하고 시작/최종 결과를 비교한다.

```powershell
python data/mock/validate_mock_pack.py
python scripts/check_contract_fixtures.py
python scripts/check_boundaries.py
git diff --check
```

evidence의 실행·Contract 단위 검사·Consumer 검증 명령은 **실제로 만든 다음 실행해서** 기록하라. 아직 없는 `python -m ...` 또는 테스트 명령을 실행 가능하다고 적지 마라.

최종 변경 후 필요한 검사를 실행하고 실패 원인을 해결한다. 공용 validator PASS는 전체 스키마·정책 의미·baseline·E2E·Owner 수락의 증거가 아니다. 알려진 불일치를 검사에서 제외해 놓고 전체 PASS로 표현하지 마라. 미해결 항목의 skip/보류 여부와 통과 범위를 명시하라.

코드 리뷰에는 적용 가능한 `code-review-and-quality` 스킬을 읽고 따른다. Contract 위반, 참조 오류, 상태 혼동, 입력/과거 결과 변형, 타 모듈 의존, 테스트가 주장하는 범위를 점검하라. 리뷰에서 발견한 내 범위의 문제를 고치고 영향을 받는 검사를 다시 실행하라.

## 9. 남길 산출물

1. **실행 가능한 evidence 코드와 필요한 Mock 경계.** 각각 실제 처리인지 Fixture 재생인지 식별할 수 있어야 한다.
2. **테스트와 실행 방법.** H/U/P/R 및 체크리스트가 요구한 최소 Contract 검사, 재현 가능한 명령.
3. **Scenario별 JSON/실행 증빙.** 원본 입력 참조, 실제 출력, expected와의 비교, Mock/baseline 범위, 실행한 revision·정책/Template 버전.
4. **체크리스트 대응 결과 문서.** 완료 조건을 축소하거나 체크박스를 일괄 완료하지 말고, 각 항목의 검증 근거를 제공한다.
5. **통합 대기·결정 대기 목록.** Q1/Q2/Q3의 최신 상태, 추가 발견, 담당자, 영향 경로, 완료에 필요한 구체적 조치.
6. **공개 입력/출력 사용 예와 인수인계.** Consumer가 어느 입력으로 무엇을 호출하고 어떤 Contract를 받는지 설명한다. 필요한 evidence README/실행 문서를 갱신한다.

원본 체크리스트의 완료 기준과 작성 시점 기록은 보존하라. 수행 결과는 evidence 문서 영역에 별도로 작성하고 다음 형태로 연결하라. 이 표의 상태는 보고서용이며 Runtime Contract enum이 아니다.

| 체크리스트 위치/항목 | 구현·검증 위치 | 증빙 | 상태 | 남은 일/담당 |
| --- | --- | --- | --- | --- |
| 해당 항목의 원문 또는 식별 가능한 위치 | 실제 파일·테스트 | 실제 출력/로그 링크 | 검증 완료 / Mock 연결 검증 완료 / 미완료 / 통합 대기 / Contract 변경 검토 필요 | 해당 시 기록 |

## 10. 중단과 최종 보고

새 계약 결정이 필요한 경로, Final과 다른 출력, 추적 불가능한 ref, 가짜 값 확정, 잘못된 gate, 과거 결과 훼손은 해당 경로의 완료 판정을 중단한다. 다만 Q1 같은 독립적인 보류 한 건을 이유로 아직 할 수 있는 구현까지 멈추지 마라.

**해결 가능한 범위는 모두 구현·검증한 뒤 보고하라.** 권한 밖 결정이나 실제 Consumer 부재가 남으면 작업 결과를 보존하고 무엇이 필요한지 구체적으로 남겨라. 새 계약 결정이 필요한 경우에만 관련 질문을 모아 제시하고, 코드 구조·테스트 이름 같은 일상적 선택은 스스로 결정하라.

최종 답변은 다음 내용을 포함한다.

1. 달성한 연결 범위와 현재 준비도. 전체를 입증하지 못했으면 `PARTIAL_READY`로 표시하고 이유를 설명한다.
2. 주요 코드/문서/증빙 파일 링크.
3. H/U/P/R별 실제 입력 → 처리 → 출력과 성공·보류 상태.
4. 실행한 검사와 결과, 그 검사로 증명하지 못한 것.
5. 실제 baseline, upstream Mock, Fixture 재생, Consumer Mock, 실제 Consumer 접합의 구분.
6. 미완료·통합 대기·Contract 변경 검토 필요 항목 및 담당자.
7. Merge 회의에서 재현할 정확한 실행 명령과 말할 수 있는 1~2문장 요약.

“코드 작성 완료”, “테스트 통과”만으로 종료하지 마라. **다른 모듈이 어떤 Contract를 실제로 받을 수 있게 됐는지, 어떤 경로는 아직 수락할 수 없는지**를 증거로 설명하라. common/runtime 구현이나 실제 안전신문고 제출을 완료했다는 주장은 이 작업 범위에 없다.
