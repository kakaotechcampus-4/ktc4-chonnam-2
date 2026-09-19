# 김준영 1차 완료 체크리스트

> 목적: 공용 Mock Dataset과 Final Data Contract를 기준으로, W4/W5 초기 Mock E2E 통합에 연결할 수 있는 준비 상태를 정의한다.
>
> 기준일: 2026-09-12 · 확인한 체크아웃: `develop`, `72e0e05`.
> 적용 범위: `evidence`의 입력 소비·출력 생산·Consumer 접합. **common/runtime 구현은 제외한다.**
> 이 문서는 완료 조건이다. 내부 설계서나 현재 구현 완료 보고서가 아니며, 체크박스는 증빙을 확보한 뒤 표시한다.

> **체크 표시 근거(2026-09-19):** 체크박스는 [`first-completion-result.md`](first-completion-result.md)의 수행 결과와 그 증빙(`artifacts/first-completion/`의 `run-summary.json`·네 baseline JSON은 `base_revision` `78904bd` 기준 재생성, `tests/evidence` 46 tests, 공용 검증 3종)으로 표시했다. 완료 조건 본문·기준일·작성 시점은 수정하지 않았다. 아래 4개 항목은 증빙이 없어 **미표시로 남긴다.**
>
> | 미표시 항목 | 남은 이유 |
> | --- | --- |
> | 회의 핵심 「신고 준비의 세 조건」 | Consumer Mock은 두 gate만 계산하고 `USER_REVIEWED`를 산출하지 않는다. CaseView Artifact 확인은 `case` 통합 대기 |
> | Integration 「`case`의 safe projection 보존 확인」 | 실제 CaseView projection 호출 경로가 없어 Consumer와 확인하지 못했다 |
> | Test/Evaluation 「eval 제공 값」 | eval에 결과를 제공한 기록이 없다. 김대원 하니스 접합 대기 |
> | RequirementReport 「H PASS·U WARN·P UNKNOWN→PASS·R WARN→PASS」 | baseline의 P v2·R v2는 `PASS`가 아니라 `WARN`이다. D1의 `evidence.location.present` WARN check가 더해진 결과이며, 두 baseline의 `comparison.known_differences`가 비어 있어 이 차이가 증빙에 기록돼 있지 않다 |

## 회의에서 먼저 볼 핵심

- [x] **Happy Path의 입력과 최종 결과를 연결해 보여준다.** `scenario_happy_001`에서 `case`가 전달한 관찰·자산 사실을 받아 `TimeResolution → EvidenceRecord → RequirementReport(EVIDENCE/FINAL_PACKAGE) → ReportPackage`가 이어지고, Consumer가 그 결과를 읽는 실행 증거가 있다.
- [x] **사건 유형 불확실과 번호판 ABSTAIN을 구분해 보여준다.** `scenario_unknown_abstain_partial_001`의 `USER_UNSURE`·일반 신고문·WARN 경로와 `scenario_plate_reread_001`의 번호판 부재·`PLATE_REREAD`·Package 미생성 경로를 각각 설명할 수 있다. WARN Package의 현재 정합 대기 사항은 아래 Q1·Q2로 공개한다.
- [x] **정정·부분 재판독 후 기존 근거가 보존됨을 보여준다.** `scenario_correction_rerun_001`에서는 시각만, `scenario_plate_reread_001`에서는 번호판 관련 결과만 바뀌며, 새 Evidence의 참조와 이전 snapshot을 비교할 수 있다.
- [ ] **신고 준비의 세 조건을 구분해 보여준다.** `EVIDENCE_SUFFICIENT`, `PACKAGE_READY`, `USER_REVIEWED`가 같은 상태가 아님을 실제 Requirement·Package·CaseView Artifact로 확인한다.
- [x] **무엇으로 검증했는지 공개한다.** 각 결과가 공용 Fixture 재생인지 현재 baseline 출력인지 표시하고, 미해결 Contract 접합과 상대 구현 대기를 분리한 셀프 체크 증빙을 제출한다.

## 담당 범위

| 항목 | 김준영 담당 범위 |
| --- | --- |
| **Owner** | 김준영 |
| **주 담당 Module** | `evidence`: 관찰의 확정값 채택, 발생시각 판정, 사용자 정정 반영, 부족분 선언, 신고요건 검사, 신고문·Package·handoff 정보 |
| **보조 담당 Module / 역할** | PM으로서 전반 검토·조율, 공통 Contract 및 common/runtime 계약·설계 Owner. 이 문서에서는 evidence 접합에 필요한 계약 해석·불일치 식별까지만 다룬다. |
| **Producer로 책임지는 Contract** | `TimeResolution`, `EvidenceRecord`, `EvidenceNeeds`, `RequirementReport`, `ReportPackage` |
| **Consumer로 사용하는 Contract** | `Observation<T>`, `TimeSourceCandidate` 및 필요한 `TimeSourceCheck`·`RecordingTimeline`/구간 provenance, `CandidateEvent`, `VisualEvidence`, `PlateReadout`, `OverlayTimeReadout`, `CorrectionRecord`, `IncidentClip`·`FrameRef`·`DerivedAsset`의 참조/근거, `AssetFacts`. 내부 처리 단계에서는 자신의 `TimeResolution`·`EvidenceRecord`·`RequirementReport`를 후속 판단의 근거로 사용한다. |
| **1차 통합에서 내 출력의 주요 Consumer** | 직접 Consumer는 유소연(`case`). 신유민(`web`)은 `CaseView`로 간접 소비한다. eval에는 합의된 평가 경로로 결과를 제공하며 새 직접 Consumer 계약을 만들지 않는다. |
| **1차 통합에서 의존하는 주요 Producer** | 정철원(`recording`): 시각 후보·원본 구간·자산 사실. 서어진(`search`): 후보·시각적 관찰. 신유민(`readout`): 번호판·화면 시각 판독. 유소연(`case`): 선택 context·사용자 정정 및 입력 수집·주입. |

`Observation<T>`의 **계약 Owner**인 것과 관찰값의 **Runtime Producer**인 것은 다르다. 관찰은 `recording`·`search`·`readout`이 생산하고 evidence는 소비한다. `CorrectionRecord`·`JobRecord`·`CaseView`의 Producer는 `case`, `JobExecution`·`UsageRecord`의 Producer는 `common/runtime`이다. 이를 김준영의 evidence 출력 TODO로 옮기지 않는다. [O][A][C0][C4]

R&R의 과거 「공통 기반/운영」 산출물 목록보다 이번 요청의 범위 제한을 우선한다. Queue·lease·heartbeat·retry·비용 장부·마스킹 로거·config·storage adapter·CI/CD 구현은 본 체크리스트에서 제외한다. `JobExecution` 구현 담당은 R&R에 정철원으로 명시돼 있다. 그 밖의 common/runtime 구현 배정이 필요하다면 **`담당 범위 확인 필요`**로 별도 조율하며 김준영에게 자동 배정하지 않는다. [O]

### 적용 자료와 근거 읽는 법

| 근거 | 사용 범위 |
| --- | --- |
| [Product Spec][P], [Core User Flow][F], [Module Architecture v4][A], [R&R][O] | 제품 범위, 관찰/확정 경계, 사용자 보정·신고 준비, Producer/Consumer 역할 |
| [Observation][C0], [TimeResolution][C1], [EvidenceRecord/Needs][C2], [RequirementReport/Package][C3], [CorrectionRecord][C4] | 필드·nullable·enum·provenance·immutable 결과·gate |
| [recording 자산][C5], [timeline/구간][C6], [derived 자산][C7], [후보/Run][C8], [VisualEvidence][C9], [판독 결과][C10], [ReadoutRun][C11], [CaseView/JobRecord][C12] | 입력의 의미와 Consumer 접합 |
| [Timestamp ADR][D1], [Evidence ADR][D2], [Requirement/Package ADR][D3], [9/7 종결 ADR][D4], [9/8 종결 ADR][D5] | 시간·구간·자산 입력과 상태/표시 경계의 확정 근거 |
| [신고유형·Template 정책][D6], [source registry][D7], [별도 sign-off 없음][D8], [USER_UNSURE 후속 결정][D9] | 초기 4종 매핑, 고정 신고문, 출처, 이미 확정된 불확실성 처리 |
| [Mock Overview][M1], [Scenario Catalog][M2], [Artifact Templates][M3], [Validation Report][M4], [manifest][M5] | 공통 Scenario ID, 실제 Artifact, 기존 검사의 범위와 미커버 항목 |
| [신고요건 Research PDF][R1] §1~6·15 | 유형 매핑·값 확정과 영상 가시성 분리의 연구 근거 |
| [Timestamp Research PDF][R2] §10~15 | 출처·사후 각인·원본 보존·사용자 수정 provenance의 연구 근거 |
| [Package/Handoff Research PDF][R3] §2~7·14~15·20~21 | 결정론적 신고문, 준비 상태 분리, 사용자 제출 경계의 연구 근거 |

Research의 권장 스키마·과거 enum·내부 구조 제안은 완료 조건으로 승격하지 않는다. 예를 들어 PDF의 `CONFLICT` 표현보다 [TimeResolution][C1]의 `conflict` 객체와 현재 enum을 따른다. 외부 신고 규정의 최신성을 재조사한 문서가 아니며, 검사 수치의 근거는 채택된 버전의 정책으로 추적한다. Architecture Input Memo는 이번 조건을 정하는 데 추가 사용하지 않았다. 현재 evidence Technical Spec·공개 실행 코드는 확인되지 않았다. [구현 자리][CODE]는 README만 있는 골격이다.

Mock Overview·Catalog·Validation Report에는 옛 미해소 설명과 후속 종결 기록이 공존한다. 이 문서는 현재 Final 본문·확정 후속 기록·실제 JSON을 함께 대조했다. 특히 `CorrectionRecord`는 Final v1.1이고, U 시나리오에서 Evidence가 전부 미생성된다는 과거 설명은 현재 기준이 아니다. 자료가 실제로 어긋나는 부분은 아래 Q1·Q2에 남겼다.

## 1차 완료 정의

`scenario_happy_001`, `scenario_unknown_abstain_partial_001`, `scenario_plate_reread_001`, `scenario_correction_rerun_001`을 기준으로 `case`가 전달한 후보·관찰·판독·시각 후보·사용자 정정·자산 사실을 받아, 공용 Mock 또는 현재 baseline으로 시각/증거 확정·부족분 선언·신고요건 판정을 수행하고 Final Contract에 맞는 `TimeResolution`, `EvidenceRecord`, `EvidenceNeeds`, `RequirementReport` 및 생성 조건을 충족한 `ReportPackage`를 제공할 수 있으며, 불확실·부분 성공·정정에서도 확보된 값과 provenance를 보존하고, Consumer가 같은 계약으로 연결해 읽은 Artifact와 검증 결과를 제시하면 1차 완료로 본다. **해당 경로의 Contract 불일치가 남아 있으면 그 경로의 완료는 보류한다.** common/runtime의 실제 구현 완료는 김준영의 1차 완료 조건에 포함하지 않는다.

공용 Fixture를 호출 가능한 Mock으로 연결한 단계도 1차 통합에 사용할 수 있다. 다만 JSON 파일의 존재만으로 연결 완료라고 하지 않으며, Fixture 재생 결과를 실제 시간 판정·요건 엔진·영상 생성의 구현 검증이라고 보고하지 않는다.

## 구현 체크리스트

아래의 **H/U/P/R**은 문서 내 약칭일 뿐 새 Scenario ID가 아니다.

| 약칭 | 공통 Scenario ID |
| --- | --- |
| H | `scenario_happy_001` |
| U | `scenario_unknown_abstain_partial_001` |
| P | `scenario_plate_reread_001` |
| R | `scenario_correction_rerun_001` |

### Input

- [x] H/U/P/R에 필요한 공용 모듈 Fixture를 로딩하거나 동일한 Contract payload를 입력으로 전달받을 수 있다. Mock 관리용 `scenario_id`·배열 묶음·`contract` 식별 태그를 새로운 필수 Runtime 필드로 요구하지 않는다. [M1][M3]
- [x] 선택된 `CandidateEvent`와 `VisualEvidence`가 동일 사건 context를 가리키는지 입력·참조 목록으로 확인할 수 있다. 관찰 근거의 Fine run 참조를 유지한다. [C8][C9]
- [x] 시각 후보와 `OverlayTimeReadout`의 실제 상태를 받아들이며, 후보 부재·`NOT_APPLICABLE`·`UNKNOWN`을 정상 시각 값으로 채우지 않는다. [C0][C1][C6][C10]
- [x] `PlateReadout.abstained`와 값/근거를 함께 소비한다. `ReadoutRun.outcome` 하나로 번호판 확정 여부를 판단하지 않는다. [C10][C11]
- [x] `case`가 생산한 `CorrectionRecord`를 원래 `case_id`, `selection_rev`, `kind`, `target_field`, 값 타입 및 correction ref와 함께 소비할 수 있다. [C4]
- [x] `case`가 주입한 `AssetFacts`의 자산 종류·role·크기·가용성·lineage를 판정 근거로 사용할 수 있다. opaque ID 접두어로 자산 성질을 추측하지 않는다. [C3] §4.6[C5] §6
- [x] H의 GPS와 사용자 위치 단서를 구분해 보존하고, U처럼 위치 근거가 없으면 임의 좌표·주소를 만들지 않는다. [C2] §5

### Core Flow

- [x] H에서 검증된 화면 시각을 사용한 시간 결과부터 두 scope의 Requirement와 Package까지 Consumer가 따라갈 수 있는 결과가 나온다. 실제 처리 또는 Mock인 부분을 실행 결과에 표시한다. [C1][C2][C3]
- [x] U에서 `VisualEvidence.verification=UNCERTAIN`과 사용자 `USER_UNSURE`를 일반 신고문·WARN 경로로 보존한다. 정해지지 않은 구체적 위반행위를 추가하지 않는다. [C2] §3·4.6-1[D6]
- [x] P의 첫 결과에서 이미 확보한 사건·시각을 유지한 채 번호판 보강 필요를 반환한다. [C2] §8[M2]
- [x] P의 재판독 결과가 입력되면 번호판을 반영한 새 Evidence와 새 basis의 Needs/Requirement를 제공할 수 있다. [C2] §4.1[C3] §6
- [x] R의 `EVENT_TIME_MANUAL`이 입력되면 새 시각과 Evidence를 반환하고, 기존 번호판의 값·출처·근거·검토 상태는 유지한다. [C1] §5·10[C4]

### Output Contract

- [x] 생산하는 다섯 Contract의 버전·필수 필드·enum·nullable 규칙을 아래 Contract별 기준으로 검증할 수 있다. [C1][C2][C3]
- [x] 출력의 ref가 같은 Scenario의 실제 입력/산출물 또는 문서화된 외부 opaque 참조로 이어진다. 존재하지 않는 ID를 새 객체가 있는 것처럼 전달하지 않는다. [C1][C2][C3][M1]
- [x] `EvidenceRecord`의 값에 출처·support refs·사용자 정정 여부·`needs_review`가 계약대로 전달된다. 원시 confidence를 최종 확신 점수로 새로 만들지 않는다. [C1] §9[C2] §3
- [x] 사건 구간 ref에서 사용한 timeline revision과 범위를 복원할 수 있다. `incident_clip`/`candidate_event` 규칙과 각 계약의 초·밀리초 단위를 보존한다. [C2] §8.3[C6][D5] §4.9

### Failure / Partial

- [x] P의 ABSTAIN에서 확정되지 않은 `vehicle_number`를 만들지 않는다. `UNKNOWN`·빈 문자열 같은 가짜 번호판도 만들지 않는다. [C2] §4.2
- [x] `EvidenceNeeds.optional=false`를 `RequirementReport.BLOCK`과 동일하게 취급하지 않는다. [C2] §8.5
- [x] `EvidenceNeeds.items=[]`를 신고요건 충족이나 Package 준비 완료로 취급하지 않는다. [C2] §6
- [x] `RequirementReport`의 `UNKNOWN`과 `BLOCK`을 구분하고, 판정 엔진 실행 실패를 `overall=ERROR` 같은 새 enum으로 출력하지 않는다. [C3] §4.2·6
- [x] Package 생성 조건이 충족되지 않으면 정상 Package를 반환하지 않는다. 준비 중·실패를 표현하려고 `ReportPackage.status`를 추가하지 않는다. [C3] §8.1
- [x] 값 확정과 신고영상의 번호판/시각 가시성을 별도 조건으로 검증한다. `AssetFacts`에 없는 가시성 필드를 요구하거나 번호판 문자열만으로 가시성 PASS를 만들지 않는다. [C2] §4.6·4.7[C3] §4.6
- [x] 실행 실패 후에도 이전에 발행된 정상 Evidence·시간 결과·사용자 correction을 훼손하지 않는지 결과 비교로 확인한다. 실행 lifecycle 자체의 구현은 case/runtime 접합 확인으로 남긴다. [C1] §10[C2] §4.1[C4] §8

### State / Lifecycle

- [x] 대체 결과는 새 identity와 필요한 `supersedes_ref`로 연결하고, 과거 snapshot을 덮어쓰지 않는다. [C1] §10[C2] §4.1[C3] §6·8
- [x] R의 순수 시각 정정과 P의 번호판 재판독에서 `selection_rev=1`을 유지한다. 정정 횟수나 `case_rev`를 selection revision으로 사용하지 않는다. [C4] §4[M2]
- [x] R에서 사건 발생시각을 바꿔도 후보의 timeline 위치·원래 `CandidateEvent.span`은 바꾸지 않는다. [C8][M2]
- [x] 후속 결과의 `basis_record_ref`·`basis.evidence_record_ref`가 해당 새 Evidence를 가리킨다. Consumer가 옛 Need와 새 결과를 구분할 수 있다. [C2] §8.1[C3] §5.2-1
- [x] `USER_REVIEWED`·`READY`·작업 진행 상태를 evidence 출력에 독자적인 authoritative 필드로 추가하지 않는다. [C2] §6[C3] §5

### Integration

- [x] 유소연이 evidence 출력 JSON을 `case`의 입력 경계에서 읽은 결과를 제시할 수 있다. 실제 case가 준비되지 않았다면 같은 Contract를 읽는 Consumer Mock으로 검증하고 실제 접합은 통합 대기로 기록한다. [C1][C2][C3]
- [x] 입력 수집·readout 재발주·export 호출을 evidence가 수행하지 않는다. 필요한 후속 작업은 `EvidenceNeeds` 또는 `post_stamp` 결과로 전달된다. [A] §2 원칙6[C2] §9[C3] §9
- [x] 공용 Mock과 baseline을 교체해도 Consumer가 읽는 Contract 필드와 상태 의미가 같다. 다른 모듈 내부 클래스·DB row·provider 응답 형식을 외부 입출력으로 노출하지 않는다. [A][C1][C2][C3]
- [ ] `case`가 만든 safe projection에서 시각 출처·검토 필요·두 Requirement scope·Package 유무가 보존되는지 Consumer와 확인한다. web의 raw evidence 직접 소비를 전제로 하지 않는다. [C12]

### Test / Evaluation

- [x] H/U/P/R 각각의 입력, 출력, 예상 상태, 검증 결과를 재현 가능한 실행 기록으로 제시한다. U의 Q1·Q2가 미해결이면 해당 결과를 PASS로 표시하지 않는다. [M2][C1][C2][C3]
- [x] 공용 Scenario에서 실제로 다루지 않는 필수 불변조건은 **Contract 단위 검사**로 확인하고, 공통 E2E를 실행했다고 표시하지 않는다. 아래 최소 보완 표를 따른다. [C1] §13[C3] §13
- [x] 기존 공용 검증 명령의 결과와 evidence 자신의 동작/Consumer 검증 결과를 별도로 제시한다. [검증 명령](#검증-명령)
- [ ] eval에서 사용하는 값은 원래 결과 ref와 기준 Scenario를 유지한 채 제공한다. 정답지·채점기·최종 성능 기준은 김대원 소유로 두고, Fixture PASS를 AI/OCR 정확도로 보고하지 않는다. [A] §9[M1]

### Operational — 1차 연결에 필요한 최소 범위

- [x] 실행 기록에서 사용한 Scenario·입력/출력 Artifact 위치·코드 revision·정책/Template 버전·Mock 대체 범위를 확인할 수 있다. 이는 제출 증빙 정보이며 새 Runtime Contract 필드를 뜻하지 않는다. [M1][C1][C2][C3]

별도 비용 장부·progress·retry·latency 수집기를 김준영이 구현할 필요는 없다. 본 단계에서는 결과 재현과 접합 실패의 위치를 확인할 실행 기록이면 충분하며, 고정된 성능 수치를 합격 조건으로 신설하지 않는다.

## Contract별 완료 조건

### `TimeResolution` — `time-resolution/v1`

- [x] H/P는 `OK + VERIFIED + DIRECT`, U와 R 정정 전은 `NEEDS_REVIEW + UNVERIFIED + BASE_PLUS_OFFSET`이라는 현재 Fixture 의미를 보존한다. [C1] §4[M2]
- [x] U에서 파일명 fallback 값과 `conflict.exists=true`·충돌 refs·사용자 안내 필요를 함께 반환한다. [C1] §3·11
- [x] `BASE_PLUS_OFFSET` 결과에 `base_input_ref`, `source_offset_ms`, timezone provenance가 있고, 최종 시각은 offset-aware RFC3339다. [C1] §7·8
- [x] R의 `USER_OVERRIDE`는 §13 invariant 12의 단방향 체인 전체를 만족한다: `OK`, 선택 결과/considered의 `AGREED`, `user_corrected=true`, 실제 `EVENT_TIME_MANUAL` correction 참조. 역방향 규칙은 만들지 않는다. [C1]
- [x] `post_stamp`는 각인 필요와 provenance만 표현한다. 사용자 입력 기반 사후 각인의 안내 필요를 유지하고 영상 생성 완료로 해석하지 않는다. [C1] §12

### `EvidenceRecord` — `evidence-record/v1.3`

- [x] `record_ref`, `case_ref`, `selection_rev`, `basis`, 필수 `event` 구조와 provenance가 있다. [C2] §3
- [x] 시각이 존재할 때 `occurred_at`의 값·상태·사용자 정정 여부·출처가 참조한 TimeResolution의 snapshot과 일치한다. `occurred_at.source`에 `observability`를 넣지 않는다. [C2] §4.4
- [x] `user_corrected=true` 또는 `value=null`인 EvidenceValue에는 `needs_review=false`를 사용한다. [C2] §10
- [x] U에서 `event.visual_event_type.value=null`이어도 `event`와 필수 키는 존재하며, `safety_report_type`·`violation_expression`까지 null 허용으로 확장하지 않는다. [C2] §3
- [x] U의 `situation_response=USER_UNSURE`와 `responded_at`·대상 후보 ref를 보존하고, 단순 응답을 새 CorrectionRecord로 만들지 않는다. [C2] §4.6-1
- [x] 초기 4종의 `VisualEventType → SafetyReportType → violation_expression`을 [확정 매핑][D6]과 대조할 수 있다. 네 유형 모두 실영상 AI 처리를 구현해야 한다는 뜻은 아니다.

### `EvidenceNeeds` — `evidence-needs/v1`

- [x] P 첫 결과는 `basis_record_ref=ev_p001`, `kind=PLATE_REREAD`, `would_fill=VEHICLE_NUMBER`, `optional=false` 및 machine-readable `why.code`를 제공한다. [C2] §7·8[M2]
- [x] P의 `evidence.interval`은 생성된 `clip_p001`을 가리키며, 같은 items 안의 `(kind, would_fill)`이 중복되지 않는다. [C2] §8.3·10
- [x] P 재판독 후에는 `ev_p001_v2`를 basis로 한 `items=[]` 결과를 제공할 수 있다. H의 빈 items와 U의 Needs 객체 미발행을 같은 배열 계층으로 혼동하지 않는다. [M3]
- [x] v1의 두 kind 외에 `EVENT_TYPE_CONFIRM`, `POST_STAMP`, `REPORT_VIDEO`, `EXPORT`를 만들지 않는다. 추가 kind가 필요하면 **`Contract 변경 검토 필요`**로 분리한다. [C2] §8·9

### `RequirementReport` — `requirement-report/v1`

- [x] H/U에서 `EVIDENCE`와 `FINAL_PACKAGE`를 서로 다른 평가 결과로 발행한다. P/R은 Catalog가 다루는 `EVIDENCE` 범위까지 검증한다. [C3] §4.1[M2]
- [x] `overall`은 `BLOCK > UNKNOWN > WARN > PASS` 우선순위를 만족한다. 정상 Report에는 적용 rule의 check가 있고 `checks[].code`가 중복되지 않는다. [C3] §4.3·6
- [x] 각 check의 `code`, `category`, `outcome`, `reason_code`, `subject_refs`를 Consumer에게 전달한다. 수치 설명을 제공할 때 `measurement`의 단위를 보존한다. [C3] §3
- [x] `policy_ref`, `evaluated_at`, Evidence basis와 실제 사용 자산 refs로 판정 근거를 추적할 수 있다. Fixture의 임의 수치를 새 보편 한도로 채택하지 않는다. [C3] §4.5·6
- [x] 첨부 용량 조건은 전달된 `AssetFacts.byte_size`와 채택한 baseline 정책으로 검증한 결과를 제시한다. 측정되지 않은 값을 0이나 용량 적합으로 처리하지 않는다. [C3] §4.5·4.6 [C5] §6
- [x] 신고기한 조건은 발생시각·`evaluated_at`·채택한 정책 버전으로 추적 가능한 검사 결과를 제시한다. Mock 날짜를 오늘 날짜로 다시 평가해 Scenario 의미를 바꾸지 않는다. [C3] §6 [A] §3-6
- [ ] H의 두 scope는 PASS, U의 두 scope는 WARN, P는 UNKNOWN→PASS, R은 WARN→PASS라는 서로 다른 이유를 설명할 수 있다. U의 Package까지 계약 적합하다는 판정은 Q1·Q2 해소 후에 한다. [M2]

### `ReportPackage` — `report-package/v1`

- [x] `FINAL_PACKAGE`의 PASS/WARN, 필수 신고용 자산 존재, 조립 성공을 모두 만족할 때만 Package를 제공한다. [C3] §8.1
- [x] `evidence_record_ref`와 `requirement_report_ref`가 같은 Evidence를 기준으로 한 최종 평가를 가리킨다. [C3] §7
- [x] 필수 `report_inputs`, 제목·본문·`template_ref`, 신고용 영상 ref, source/derived provenance, `created_at` 및 handoff 정보가 Contract 형식에 맞는다. 위치의 현재 nullable 충돌은 Q1로 처리한다. [C3] §7
- [x] 신고문이 확정된 Template와 입력으로 재현되며, 같은 `template_ref`로 서로 다른 임의 문구를 정답 처리하지 않는다. 현재 예시 차이는 Q2로 처리한다. [C3] §8.3[D6]
- [x] `plate_image_ref`는 있을 때만 포함한다. 원본 파일을 신고용 파생영상으로 바꾸어 참조하지 않는다. [C3] §8.4
- [x] `SAFETY_REPORT`와 `DOWNLOAD_ASSETS`, `COPY_FIELDS`, `OPEN_DESTINATION` capability를 Consumer가 읽을 수 있다. 사용자 인증정보·실제 제출 성공·`USER_REVIEWED`를 Package에 넣지 않는다. [C3] §10

## Scenario별 완료 조건

아래 네 행만 evidence의 직접 참여 Scenario다. 기대 출력은 현재 공용 Fixture의 의미를 설명하며, 공용 Fixture 자체의 계약 불일치까지 승인한다는 뜻은 아니다.

| Scenario | 내 입력 | 내가 해야 할 처리 | 기대 출력 | 완료 기준 |
| --- | --- | --- | --- | --- |
| `scenario_happy_001` | `case_h001`/`candidate_h001`, `ve_h001`, 번호판·검증된 overlay, 시각 후보, `clip_h001`, 최종 derived 자산 사실 | 시각·Evidence 확정, EVIDENCE 검사, 자산 준비 후 FINAL_PACKAGE 검사·신고문/Package 조립 | `tres_h001`, `ev_h001`, 빈 items의 Needs, `req_h001_evidence=PASS`, `req_h001_final=PASS`, `pkg_h001` | 시각 `2026-08-24T18:05:12+09:00`, 번호판 `12가3456`과 근거 refs 유지. Consumer가 두 scope와 Package를 읽음. 신고문 예시 적합성은 Q2 해소 필요. |
| `scenario_unknown_abstain_partial_001` | `ve_u001.verification=UNCERTAIN`, 정상 번호판 `88부1234`, overlay `NOT_APPLICABLE`, 충돌하는 파일명/metadata 시각, `USER_UNSURE`, derived 자산 사실 | 시각 fallback과 충돌 보존, 사건 유형 null·사용자 응답 snapshot, 일반 신고문·WARN 판정 | `tres_u001=NEEDS_REVIEW`, `ev_u001`, `req_u001_evidence/final=WARN`, 일반 신고문의 `pkg_u001`이 Catalog의 목표 | 가짜 사건 유형·시각·위치 없음. `safety_report_type.needs_review=true`. **Q1·Q2 해결 전에는 WARN Package 전체 접합 완료를 보류**하고 Evidence/Requirement 결과까지만 별도로 증빙. |
| `scenario_plate_reread_001` | 관찰된 `SIGNAL`, 검증된 시각, 첫 번호판 `abstained=true`, 이후 `readout_p001_plate_reread` | 확보된 사건·시각 보존, 번호판 보강 Need 반환, 재판독 입력을 받아 새 Evidence/Requirement 산출 | `ev_p001`에 번호판 부재, `PLATE_REREAD`, `req_p001_evidence=UNKNOWN` → `ev_p001_v2.vehicle_number=17나2867`, 새 Needs의 `items=[]`, `req_p001_evidence_v2=PASS` | `selection_rev=1` 유지, 기존 Evidence 보존, 새 plate ref 사용. `case_rev=4`도 `EVIDENCE_REVIEW`; 이 Scenario에는 FINAL_PACKAGE/Package가 없으므로 READY까지 요구하지 않음. |
| `scenario_correction_rerun_001` | 파일명 기반 `tres_r001_v1`/`ev_r001_v1`, case의 `cr_r001_time`(`EVENT_TIME_MANUAL`, `target_field=occurred_at`, `selection_rev=1`) | 사용자 시각을 적용한 새 시간/Evidence 생성, 새 basis로 요건 재평가 | `tres_r001_v1: NEEDS_REVIEW` → `tres_r001_v2: OK/AGREED/USER_OVERRIDE`, `ev_r001_v2`, `req_r001_evidence_v1: WARN` → v2 `PASS` | `13:15:30+09:00` → `13:13:00+09:00`, 번호판 `34나7890`과 나머지 근거 불변, time/evidence/report supersede 연결. 후보 시각·`selection_rev` 불변. Package 생성은 이 Scenario 범위 밖. |

각 Scenario 입력·출력 원문은 [공용 manifest][M5]와 [`data/mock/evidence/`][MF]에서 같은 ID로 찾는다. 재생 테스트에서는 공용 ID를 유지한다. baseline이 새 ID를 발급한다면 테스트 증빙에서 공용 ID와 생성 ID의 대응을 제공하고, 같은 실행의 Consumer에는 실제 생성된 ref를 전달한다. ID 대응표는 테스트 자료이며 Runtime Contract 확장이 아니다.

**직접 참여하지 않는 Scenario:** `scenario_empty_001`은 후보가 없어 evidence가 발행되지 않는 경로이고, `scenario_infra_failure_001`은 판독 실행 실패/취소로 evidence assembly가 시작되지 않는 경로다. `scenario_relative_rebase_001`은 timeline 메커니즘 검증으로 evidence가 의도적으로 없다. 이 세 건에 김준영의 가짜 Evidence 출력이나 runtime 구현을 요구하지 않는다. 관련 비호출·상태 유지 확인은 case/recording/runtime 담당과의 접합 증거로만 사용한다. [M2]

### 공용 Scenario 밖에서 필요한 최소 Contract 단위 검증

새 공통 Scenario ID를 만들지 않는다. 다음은 이미 Final Contract가 요구하는 최소 경계 검사이며, 현재 7개 공통 Scenario의 E2E 커버리지와 구분한다.

| Contract 근거 | 검증할 결과 | 공용 Mock 커버리지 |
| --- | --- | --- |
| C1 §13·C2 §4.4 | 신뢰 가능한 사건시각이 없으면 `TimeResolution.status=UNKNOWN`, `resolved` 부재, Evidence의 `occurred_at` 부재 | 현재 evidence Scenario에는 없음. U의 NEEDS_REVIEW와 구분 |
| C3 §4.3·13 | 두 scope의 PASS/WARN/BLOCK/UNKNOWN과 overall 우선순위, BLOCK/UNKNOWN일 때 Package 미생성 | 공용 Pack의 BLOCK은 미커버. FINAL_PACKAGE UNKNOWN도 직접 참여 4개에 없음 |
| C3 §6·8.1 | 요건 엔진 실패 시 정상 Report 미생성, 필수 자산 부재/조립 실패 시 Package 미생성 | 현재 evidence 실행 실패 Fixture 없음 |
| C3 §13 | optional plate image가 없는 정상 Package, Evidence 정정 후 새 Package와 대체 ref | 현재 H/U는 모두 plate image 존재. R은 Package 단계 없음 |
| C4 §6·8, C2 §10 | 소비하는 correction의 target별 타입과 head, `CORRECTED`의 SITUATION_CHANGE 참조, `USER_UNSURE`와 구분 | 공용 Pack은 EVENT_TIME_MANUAL·USER_UNSURE 중심. 전체 값 공간 검증을 했다고 보고하지 않음 |
| D6 초기 4종 매핑·Renderer 불변조건 | 네 VisualEventType의 매핑과 채택된 Template의 결과·5~900자 범위 | 모든 유형의 공통 Package/실영상 처리를 요구하는 것은 아님 |
| C3 §4.5·4.6·6, Product Spec §5 | 채택한 baseline의 첨부 용량·신고기한 검사와 근거. 규칙 수치는 policy로 추적하며 이 문서에서 정하지 않음 | 현재 H/U의 FINAL_PACKAGE checks는 자산 존재·가시성·시각 등을 예시화하며 용량·기한 검사를 모두 증명하지 않음 |

## Merge 전 셀프 체크 증빙

증빙 위치는 구현자가 정한다. 각 체크 완료 시 파일 또는 실행 결과 링크를 남긴다. 예시 JSON을 복사했다는 사실만으로 실제 baseline 처리 완료라고 표시하지 않는다.

- [x] H의 실제 전달 입력과 5종 Contract 출력 JSON, case가 이를 읽은 결과를 준비했다.
- [x] U의 `USER_UNSURE`, null 사건 유형, 충돌 시각, WARN 결과 JSON을 준비했고 Q1·Q2의 해소/보류 상태를 함께 적었다.
- [x] P의 재판독 전후 Evidence·Needs·Requirement JSON과 변경되지 않은 사건/시각 비교 결과를 준비했다.
- [x] R의 case 소유 CorrectionRecord와 전후 시간/Evidence/Requirement JSON, `selection_rev` 및 번호판 보존 비교 결과를 준비했다.
- [x] Package가 있어야 하는 경우와 없어야 하는 경우를 각각 입증했다. P/R의 Package 부재는 Catalog의 범위이며 실행 실패가 아님을 적었다.
- [x] 공용 검증 3종과 필요한 Contract 단위 검사의 실행 명령·결과·검사 대상 revision을 준비했다.
- [x] 신고문 예시, 적용 `template_ref`·`policy_ref`, 자산 refs 및 source/derived lineage를 제시할 수 있다.
- [x] Consumer의 JSON 소비 또는 API 응답/실행 로그 중 실제로 수행한 접합 증거를 준비했다. UI 캡처는 projection을 확인한 경우에만 첨부하며 evidence 완료의 필수 형식으로 요구하지 않는다.
- [x] 실제 구현·Mock 대체·통합 대기·Contract 불일치 목록을 각각 표시했다. 비용/latency/Eval 수치는 측정한 경우에만 첨부한다.

## Merge 전 확인 질문

1. H의 입력이 들어오면 어떤 다섯 Contract가 어떤 ref로 연결되는지 설명할 수 있는가?
2. U의 사건 유형 불확실과 P의 번호판 ABSTAIN이 서로 어떤 출력·후속 행동으로 이어지는가?
3. 번호판을 읽었다는 사실과 신고영상에서 번호판이 보인다는 판단의 근거를 구분할 수 있는가?
4. R에서 바뀌는 시각과 바뀌지 않는 번호판·후보 위치·`selection_rev`를 전후 JSON으로 보여줄 수 있는가?
5. case가 내 결과 중 어떤 필드를 사용하며, `EVIDENCE_SUFFICIENT`·`PACKAGE_READY`·`USER_REVIEWED`를 어떻게 분리하는지 알고 있는가?
6. 아직 실제 구현되지 않은 처리가 무엇이며, 현재 검증은 Fixture 재생·baseline·실제 Consumer 중 어디까지인가?
7. Q1·Q2 같은 Contract/Fixture 불일치가 해결됐는가? 해결되지 않았다면 어떤 경로의 완료를 보류하고 있는가?

## 접합부 확인

| 접합 상대 | 확인 Contract | 내 역할 | 상대 역할 | Merge에서 확인할 것 |
| --- | --- | --- | --- | --- |
| 정철원 `recording` → 유소연 `case` → evidence | 시각 후보, IncidentClip/FrameRef, AssetFacts, DerivedAsset | 전달받은 사실로 시간·요건 판정 | recording이 사실 생산, case가 수집·주입 | 같은 원본/구간/revision, 가용성·크기·lineage의 의미. opaque ref만 보고 판정하지 않음. 실제 파일 생성은 Mock 대체 가능 |
| 서어진 `search` → case → evidence | CandidateEvent, VisualEvidence | 관찰을 확인해 확정값 또는 불확실 상태로 출력 | 후보와 Fine 관찰 생산 | candidate/visual/run 연결, UNCERTAIN·null 의미, 초기 4종 이름 일치. 신고유형은 evidence가 매핑 |
| 신유민 `readout` → case → evidence | PlateReadout, OverlayTimeReadout, ReadoutRun 참조 | 판독 값·abstain·검증 근거 소비 | 관찰·실행 결과 생산 | ABSTAIN과 FAILED 분리, overlay 부재와 OCR 실패 분리, 재판독 후 새 plate ref 사용 |
| 유소연 `case` → evidence | CorrectionRecord, 선택 context | correction 적용 여부와 새 Evidence 판정 | 유효 correction을 먼저 기록, 입력·선택 context 전달 | R의 실제 correction ref, append-only 보존, selection_rev 유지, 재조립 실패 시 correction 보존 |
| evidence → 유소연 `case` | EvidenceNeeds | 부족분과 basis/semantic refs 반환 | 유효한 Need를 JobIntent로 번역·발주 | P의 `PLATE_REREAD`를 `JobRecord.kind=PLATE_READ`, `force_rerun=true`로 연결. 옛 basis의 Need를 재발주하지 않음 |
| evidence → 유소연 `case` → 신유민 `web` | TimeResolution, EvidenceRecord, RequirementReport, ReportPackage / CaseView | authoritative 결과·provenance·검토 필요 전달 | 현재 결과 선택, gate·표시·notice 투영 | 두 scope 보존, USER_UNSURE를 사용자 확정으로 승격하지 않음, Package 유무와 최종 사용자 검토 분리. H/U의 Q1·Q2 확인 |
| 김대원 `eval` | 합의된 시간·판독/결과 refs와 공용 Scenario | 제공 결과의 근거·버전 설명 | 정답지·scorer·측정 책임 | timestamp 등 평가 입력을 추적 가능하게 제공. 임시 `expected/` 예시를 정식 성능 채점 완료로 간주하지 않음 |
| 정철원 등 common/runtime 구현 담당, 유소연 case | JobRecord/JobExecution, UsageRecord의 기존 계약 | evidence 성공 결과 유무와 불확실성 의미 설명; 계약·설계 관점 확인 | 실제 실행·취소·재시도·비용 기록 구현 | 도메인 UNKNOWN/ABSTAIN과 실행 FAILED를 혼동하지 않음. runtime 구현·인프라 Scenario 통과를 김준영 구현 TODO로 전가하지 않음 |

## 부분 완료 / 통합 대기

**현재 확인 상태:** 공용 JSON과 계약 검증 도구가 존재하고 검증 3종은 통과했다. evidence 실행 코드와 실제 Consumer 연결은 확인되지 않았으므로 **현재 김준영 모듈이 1차 완료됐다는 판정은 하지 않는다.** 아래 상태는 이 체크아웃에서 확인한 범위이며 다른 담당자의 별도 브랜치 구현 진척을 추정하지 않는다.

| 항목 | 현재 어디까지 됨 | 무엇을 기다리는가 | 상대 담당 | Mock 대체 가능 여부 |
| --- | --- | --- | --- | --- |
| **미완료: evidence의 호출 가능한 처리/Mock 경계와 자체 증빙** | Contract·공용 Fixture 존재, `src/daesingo/evidence`는 README만 존재 | 김준영의 Mock 또는 baseline 연결, 결과 검증 기록 | 김준영 | 가능. 단 Fixture 파일만 존재하는 상태는 실행 가능한 대체가 아님 |
| **통합 대기: 실제 case 소비·projection** | case Fixture 존재, 실제 연결 실행 증거 없음 | case 공개 입력 경계와 Consumer 실행 결과 | 유소연, 표시 확인은 신유민 | Consumer Mock 가능. 실제 case 접합 완료와 구분 |
| **통합 대기: recording/readout 실제 자산·관찰** | Contract형 입력과 자산 사실 Fixture 존재 | 실제 Producer 출력 교체·참조 해석 확인 | 정철원·신유민·서어진, 주입은 유소연 | 가능. 승인된 Mock 사실을 사용했다는 표시 필요 |
| **Owner 확인 대기: U의 신고영상·번호판 이미지** | [case 결정][D9]은 `da_u001_report_video`·`da_u001_plate_image`를 provisional로 기록하고 있음 | 해당 자산 사실에 대한 recording Owner 확인 근거 | 정철원, Mock 관리 유소연 | 잠정 Mock 소비 가능. 실제 자산 검증·Owner 수락 완료로 표기하지 않음 |
| **평가 접합 대기** | `data/mock/expected/`에 임시 정답/오답 예시 2개 존재 | eval Owner의 실제 하니스·합의된 expected 형식 | 김대원 | 자체 Contract 검사는 계속 가능. 최종 성능 점수는 불필요 |
| **범위 밖: common/runtime 구현** | 공용 실행 Fixture·계약 존재 | 실제 실행 계층 연결은 해당 구현 담당 일정 | JobExecution은 정철원, 기타 구현 배정은 담당 범위 확인 필요 | 기존 runtime Mock으로 통합 준비 가능 |

### Merge 전에 별도 정합 확인이 필요한 항목

아래는 상대 코드 지연과 다른 **자료/계약 접합 문제**다. 체크리스트에서 새 필드나 새 정책으로 해결하지 않는다. 이 문서의 Q 번호는 확인 항목 번호이며 공통 Scenario ID가 아니다.

| 항목 | 현재 확인된 사실 | 분류 / 해소 조건 | 담당과 영향 |
| --- | --- | --- | --- |
| **Q1. U Package의 위치 nullable** | [U JSON][MU]의 `report_packages[0].report_inputs.location=null`. [Final Package][C3] §7은 `location: {display_text, search_keyword?}`를 필수 구조로 정의하며 null 허용이 없음. U의 위치 부재 WARN 방향은 이미 [case 결정][D9]에 존재 | **`Contract 변경 검토 필요`**. 기존 WARN 정책을 유지하면서 location 부재를 직렬화하는 방법이 Final에 반영될지, 공용 Fixture를 바꿀지 Producer/Consumer가 결정·동기화해야 함. 임의 위치 문자열을 채우거나 null을 몰래 허용하지 않음 | 김준영(evidence)·유소연(case), 신유민(projection). U의 최종 Package 접합 완료를 보류. 사건 유형 null 허용 결정 자체를 다시 미결로 돌리지는 않음 |
| **Q2. H/U의 신고문·정책 provenance** | H/U JSON은 현재 `tmpl/safety-report-specific-v1`/`tmpl/safety-report-generic-v1`를 사용하지만 제목·본문은 [확정 Template][D6]와 다름. U 제목은 `차량 주행 상황 신고 (위반 유형 확인 요청)`이나 확정값은 `교통법규 위반 상황 확인 요청`. Package `provenance.policy_ref`도 정책이 요구한 `safety-report-policy/v1` 대신 `policy/package-assembly-v1`임 | **기존 확정 결정 반영·정합 확인 필요**. 해당 Template 버전의 정확한 예시로 맞추고 정책 참조를 정렬하거나, 별도 정책을 의도했다면 버전과 근거를 명시해 합의. Fixture 문장을 무조건 정답으로 삼지 않음 | 김준영(evidence 정책)·유소연(Mock/Consumer). H/U 신고문·Package 의미 검증 완료에 영향 |
| **Q3. TimeResolution의 timeline revision 직접 필드** | [C1] §16[C1]은 반영 방향만 합의했고 필드 위치·이름은 미정. 그 전에는 `base_input_ref`의 대상 계약 revision을 추적하도록 명시 | **`Contract 변경 검토 필요` — 후속, 현재는 비차단**. 기존 ref 경로로 provenance가 복원되면 통합 가능. 새 `timeline_revision` 필드를 체크리스트에서 신설하지 않음 | 김준영, 정철원·유소연과 접합. 기존 ref로 추적 불가한 실제 입력이 나오면 해당 경로를 재검토 |

`report_inputs.safety_report_type`은 현재 H/U에서 표시 label, EvidenceRecord에서는 내부 code로 쓰이고 Catalog가 그 수정 이력을 설명한다. 따라서 두 필드의 단순 문자열 동일성을 새 불변조건으로 만들지 않는다. Consumer가 어느 표현을 사용하는지 확인하고, 표현을 변경하려면 정책/계약 소유자와 동기화한다. [M2][D6][C3] §7

자체 구현이 없어 실패한 항목을 통합 대기로 옮기지 않는다. 반대로 상대의 실제 인프라가 없어도 같은 Contract의 Mock으로 접합을 입증했다면 그 Mock 검증은 완료로 기록할 수 있다. **스키마 충돌은 Mock 사용으로 면제되지 않는다.**

## 1차 완료 제외 범위

- common/runtime의 Queue·Worker·lease·heartbeat·retry·취소·비용 장부·마스킹 로거·CI/CD 등 구현 전부.
- search의 실제 AI 모델·프롬프트·challenger, readout의 OCR·임계값·프레임 선택 알고리즘, recording의 ffmpeg·압축·각인·저장소 구현.
- 실제 장시간 영상 전체·모든 edge case·최종 정확도·production 성능/비용 최적화. 초기 4종의 **계약상 매핑**과 공통 Scenario 접합은 제외하지 않는다.
- 최종 UI polish·로그인·신고자 인증·안전신문고 자동입력/자동제출·외부 제출/처분 성공 보장.
- 위치 주소/장소명의 완전자동 생성, GPS 없는 좌표 추측, 실제 지도 핀 확정.
- 공용 Catalog에 없는 신규 전체 E2E Scenario의 독자 설계. 다만 위 최소 Contract 경계 검사는 유지한다.
- DB 세부 구조·내부 클래스/함수 분리·라이브러리·SDK wrapper·파일 내부 구조의 지정.
- PDF에만 있는 미확정 첨부 개수 조합·세부 수치나 구현 권장을 새 Merge 필수 조건으로 채택하는 일.

## Merge 중단 기준

다음 문제가 있는 **해당 접합의 Merge/완료 판정**을 중단한다. 독립적으로 검증 가능한 다른 경로의 준비 작업까지 멈출 필요는 없다.

- 필수 필드·버전·enum·nullable이 Final과 다르거나 Q1을 해결하지 않은 U Package를 정상 Contract 출력으로 수락한다.
- Q2가 해결되지 않았는데 해당 `template_ref`의 결정론적 신고문 검증을 통과했다고 한다.
- H의 입력에서 Contract 결과 연결이 성립하지 않거나 Consumer가 출력 JSON을 읽지 못한다.
- ref 누락/오연결·다른 사건 혼입·초/밀리초 혼용·timeline revision 소실로 원본 구간/판정 근거를 추적할 수 없다.
- ABSTAIN에서 번호판을 확정하거나, 근거 없는 시각/위치를 생성하거나, `USER_UNSURE`를 사용자 확정으로 바꾼다.
- domain UNKNOWN/ABSTAIN을 실행 실패와 섞거나, 실행 실패를 정상 Requirement/Package로 숨긴다.
- `FINAL_PACKAGE`가 BLOCK/UNKNOWN인데 Package를 생성하거나, EVIDENCE PASS만으로 Package/사용자 검토까지 완료 처리한다.
- 정정·재판독이 이전 Evidence/correction을 덮어쓰거나, 관련 없는 번호판·선택 revision·후보 위치를 바꾼다.
- evidence가 다른 모듈 내부 객체에 의존하거나 직접 Job을 발주하며, Consumer가 evidence의 시각/신고요건 판정을 재계산한다.
- 공용 검증 스크립트 실패를 해소하지 않았거나, 검증 범위 밖 항목을 PASS로 보고한다. 코드 없는 경로의 NOTE는 구현 검증 PASS가 아니다.

## 검증 명령

저장소 루트에서 실행한다. 아래는 현재 존재하는 명령이며 이 문서 작성 시 실제 실행했다.

```powershell
python data/mock/validate_mock_pack.py
python scripts/check_contract_fixtures.py
python scripts/check_boundaries.py
```

| 명령 | 2026-09-12 확인 결과 | 증명하지 않는 것 |
| --- | --- | --- |
| `validate_mock_pack.py` | 46 JSON / 7 Scenario, 오류·경고 없이 PASS | 전체 Final 스키마의 완전한 검증, 정책/Template 의미 일치, 실제 실행/영상 가시성 |
| `check_contract_fixtures.py` | 문서 구조 60 / JSON 파싱 26 / 의미 Fixture 104 검사, 모두 PASS | evidence baseline 동작·Consumer E2E·Owner 수락 |
| `check_boundaries.py` | 경계·계약 검사 PASS, 코드 없는 모듈 7곳 NOTE | 코드가 없는 evidence의 실제 의존 경계나 실행 품질 |

**evidence 자체 실행, 최소 Contract 단위 검사, Consumer 통합 실행 명령:** `[구현 후 작성]`

공개 함수 서명·CLI·테스트 러너가 아직 없으므로 `pytest`나 `python -m ...` 명령을 임의로 제시하지 않는다. 실제 명령을 추가할 때 H/U/P/R 입력 위치, 결과 위치, 실행 모드(Mock/baseline), 검사 범위를 함께 적는다. 기존 스크립트 3종이 PASS여도 Q1·Q2는 별도로 해소해야 한다.

## 회의에서 말할 한 줄 요약

**증빙을 모두 확보한 뒤 사용할 문장:**

> “제 evidence 모듈은 case가 전달한 관찰·판독·사용자 정정·자산 사실을 받아 시각과 증거, 부족분, 신고요건 및 조건을 충족한 신고 Package를 Contract 형태로 반환합니다. Happy·사용자 불확실·번호판 재판독·시각 정정의 공통 Mock 경로를 Consumer 연결로 검증했으며, 실제 구현 대체 범위와 통합 대기는 별도 표시했고 common/runtime 구현은 제 완료 범위에서 제외했습니다.”

**현재 체크아웃으로 말할 수 있는 문장:**

> “계약과 공용 Mock을 대조해 evidence의 1차 완료 기준을 정리했고 공용 검증 3종은 통과했습니다. 아직 evidence 실행·Consumer 접합 완료는 입증되지 않았으며, H/U Package의 Template 정합과 U의 위치 nullable 문제를 해소한 뒤 해당 경로의 완료를 판정하겠습니다.”

[P]: ../../product/product-spec.md
[F]: ../../product/core-user-flow.md
[A]: ../../architecture/module-architecture.md
[O]: ../../management/ownership.md
[C0]: ../../architecture/contracts/contract-observation.md
[C1]: ../../architecture/contracts/contract-time-resolution.md
[C2]: ../../architecture/contracts/contract-evidence-record-needs.md
[C3]: ../../architecture/contracts/contract-requirement-report-package.md
[C4]: ../../architecture/contracts/contract-correction-record.md
[C5]: ../../architecture/contracts/contract-source-asset-media-stream.md
[C6]: ../../architecture/contracts/contract-recording-timeline-asset-span.md
[C7]: ../../architecture/contracts/contract-analysis-source-derived.md
[C8]: ../../architecture/contracts/contract-analysis-run-candidate-event.md
[C9]: ../../architecture/contracts/contract-visual-evidence.md
[C10]: ../../architecture/contracts/contract-plate-overlay-readout.md
[C11]: ../../architecture/contracts/contract-readout-run.md
[C12]: ../../architecture/contracts/contract-job-record-case-view.md
[D1]: ../../architecture/contracts/adr/adr-time-resolution.md
[D2]: ../../architecture/contracts/adr/adr-evidence-record-needs.md
[D3]: ../../architecture/contracts/adr/adr-requirement-report-package.md
[D4]: ../../architecture/contracts/adr/adr-data-contract-call-closure-2026-09-07.md
[D5]: ../../architecture/contracts/adr/adr-data-contract-call-closure-2026-09-08.md
[D6]: decisions/safety-report-policy-v1.md
[D7]: decisions/source-kind-registry.md
[D8]: decisions/no-separate-signoff.md
[D9]: ../case/decisions/generic-warn-package-and-situation-response.md
[M1]: ../../mock/01_mock_dataset_overview.md
[M2]: ../../mock/02_mock_scenario_catalog.md
[M3]: ../../mock/03_mock_artifact_templates.md
[M4]: ../../mock/04_mock_validation_report.md
[M5]: ../../../data/mock/manifest.json
[MF]: ../../../data/mock/evidence/
[MU]: ../../../data/mock/evidence/scenario_unknown_abstain_partial_001.json
[CODE]: ../../../src/daesingo/evidence/README.md
[R1]: research/안전신문고_실제_신고_요건_및_초기_4종_유형_매핑_조사.pdf
[R2]: research/Timestamp__Evidence_Policy__사건_발생시각을_어떻게_확보하고_신고영상에_표시할_것인가.pdf
[R3]: research/신고문__Package__Handoff__확정된_증거를_실제_신고_가능한_형태로_어떻게_넘길_것인가.pdf
