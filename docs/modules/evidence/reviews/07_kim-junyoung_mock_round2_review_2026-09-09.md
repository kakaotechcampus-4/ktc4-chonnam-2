# 김준영 담당 Mock Pack v2 2차 검수 보고서

> 검수일: 2026-09-09
> 기준 브랜치: `develop`
> 기준 커밋: `7dcfce5` (`origin/develop`과 동기화 확인)
> 비교 기준: 1차 검수 기준 커밋 `e94f527` → Mock Pack 2차 통합 `7dcfce5`
> 검수 범위: 김준영 담당 `evidence` 및 `common/runtime`, 신규 3개 시나리오와 VISUAL_VERIFY/GPS/예산 변경의 직접 접합부
> 검수 관점: Contract 일치 / 실제 모듈 생산 가능성 / UNKNOWN·ABSTAIN·실패 / Consumer 사용 가능성 / 이전 검수 회귀
> 선행 보고서: `docs/modules/evidence/reviews/06_kim-junyoung_mock_contract_review_2026-09-09.md`

## 1. 최종 판정

**판정: `REQUEST_CHANGES` — `common/runtime` 변경분은 `PASS`, `evidence`는 `UNCERTAIN` 사용자 흐름과 신고유형 정책 때문에 `PARTIAL_READY`.**

- 구조 검증은 모두 통과했다. `validate_mock_pack.py`는 46개 JSON·7개 시나리오를 오류 0건으로 검사했고, 계약 fixture 104개 의미 검사와 boundary 검사도 통과했다.
- 1차 검수에서 지적한 VISUAL_VERIFY provenance, KRW 비용 원장, Windows 출력 인코딩, GPS 있음/없음, 번호판 재판독, runtime STALE→재시도→FAILED는 실제 fixture에 정상 반영됐다.
- 신규 `plate_reread`, `infra_failure`, `relative_rebase` 시나리오의 김준영 담당 범위는 현재 계약으로 생산 가능한 값 조합이다.
- 다만 `scenario_unknown_abstain_partial_001`은 `VisualEvidence.verification=UNCERTAIN` 이후 Evidence·Requirement·Package를 전부 비우고 blocking notice에서 멈춘다. 이는 `잘 모르겠어요`도 진행을 막지 않고 AI 추정으로 최종 확인까지 보낸다는 확정 Product Flow와 충돌한다.
- 이 문제를 새 `EvidenceNeeds.kind`로 해결하지 않는다. 사용자 확인은 추가 OCR/판독 Job이 아니며 `EvidenceNeeds`는 confirmed Evidence 보강용 declarative value다. `case`가 사용자 확인 상태를 관리하고, `evidence`는 그 결과를 받아 결정론적 매핑·신고문·Requirement·Package를 만든다.
- 현재 `safety_report_type`의 `UNSAFE_*` 값과 Package의 `안전운전 불이행`은 여전히 placeholder다. 초기 4종을 실제 안전신문고 선택지 2종으로 매핑하는 versioned evidence 정책 artifact가 필요하다.

| 검수 축 | 판정 | 요약 |
| --- | --- | --- |
| `common/runtime` 신규·변경 fixture | `PASS` | STALE/attempt 증가/FAILED, Fine usage, KRW 원장, 새 Job kind 연결이 계약과 맞는다. |
| `evidence` 번호판 재판독 | `PASS` | abstain을 전체 실패로 만들지 않고 `PLATE_REREAD` + EVIDENCE `UNKNOWN`으로 보강 요청한다. |
| `evidence` GPS 반영 | `PASS_WITH_LIMIT` | GPS 좌표/부재는 맞다. 주소는 reverse-geocode 원본이 없어 의도적으로 만들지 않았다. |
| `evidence` 사건 불확실 흐름 | `REQUEST_CHANGES` | 현재 blocking 종료이며, 확정 Product Flow의 `잘 모르겠어요 → AI 추정 유지 → 진행`을 표현하지 못한다. |
| 신고유형·신고문 정책 | `REQUEST_CHANGES` | 4→2 매핑 방향은 정했지만 canonical enum/label/template artifact와 generic WARN 사례가 없다. |
| 보안·성능 | `NO_NEW_FINDING` | 이번 변경은 fixture·계약 문서·검사기 출력 보강이며 비밀정보, 실행 경로, 의존성 변경이 없다. |

---

## 2. GitHub 이슈 제출용 요약

아래 두 섹션은 공지의 이슈 양식에 맞춘 복사본이다. 담당자 호출이 필요한 항목은 B 아래에 따로 적었다.

이슈 제목: **`[mock] evidence/common-runtime 2차 검수`**

등록 이슈: [#25 `[mock] evidence/common-runtime 2차 검수`](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/25)

## A. 미결 질문 답변 (해당자만)

- [x] **`EvidenceNeeds`에 “사건 유형 자체가 불확실함”을 나타내는 신규 kind를 만들지 않는다.**

  - `EvidenceNeeds`는 확정된 `EvidenceRecord`를 기준으로 추가 OCR/판독을 요청하는 구조다. 사용자에게 신고 상황을 확인시키는 workflow action을 넣으면 Job 요청과 사용자 상호작용이 섞인다.
  - `evidence`는 `search`를 직접 재호출하지 않는다. 후보 변경·재탐색·추가 발주는 `case`가 소유한다.
  - 선택 후보마다 신고 상황 확인은 한 번만 한다. 사용자가 다른 후보를 선택하면 후보 종속 상태가 초기화되므로 새 후보에 대해 한 번 다시 묻는다.
  - `맞아요`/`다른 상황`이면 해당 사용자 응답을 `case`가 구조화해 `evidence`에 전달한다.
  - `잘 모르겠어요`이면 진행을 막지 않는다. 구체 `visual_event_type`은 미확정으로 보존하고, evidence가 기본 신고유형·일반 신고문을 생성하며 Requirement는 `WARN`, 최종 `ReportPackage` 생성은 허용한다.
  - 따라서 필요한 것은 신규 Need가 아니라 **사용자 응답 상태를 case→evidence로 전달하는 계약**과 **EvidenceRecord의 제한적 nullable 규칙**이다.

- [x] **초기 4종 → 안전신문고 신고유형 2종 매핑 정책 방향**

  | Search Visual Event | Evidence의 안전신문고 추천 |
  | --- | --- |
  | `SIGNAL` | 교통위반(고속도로 포함) |
  | `CENTER_LINE_CROSSING` | 교통위반(고속도로 포함) |
  | `SOLID_LINE_LANE_CHANGE` | 교통위반(고속도로 포함) |
  | `MOTORCYCLE_HELMET_NON_USE` | 이륜차 위반 |

  - `잘 모르겠어요`이고 안전모/이륜차 근거도 확정되지 않으면 기본 추천은 교통위반(고속도로 포함)으로 둔다.
  - 안전모 미착용 근거 또는 해당 candidate hint가 남아 있으면 이륜차 위반을 추천할 수 있으나, 이 경우에도 `AI 추정` provenance와 WARN을 유지한다.
  - 위 표는 제품 의미 결정이다. 실제 안전신문고의 canonical 코드·정확한 표시명·버전은 규정 원본을 근거로 evidence 소유 artifact에 별도 등재해야 한다. 현 `UNSAFE_*` 코드를 그대로 승인한 것은 아니다.

- [x] **`visual_event_type=null`인 `EvidenceRecord`를 제한적으로 허용한다.**

  - 허용 조건은 선택 후보에 대한 1회 확인을 거친 뒤 사용자가 명시적으로 `잘 모르겠어요`를 선택한 경우다.
  - “아직 질문하지 않음”, “Fine 실행 실패”, “사용자가 잘 모르겠다고 답함”을 같은 null로 합치면 안 된다. 사용자 응답 상태 또는 동등한 machine-readable provenance가 함께 있어야 한다.
  - 정확한 필드명은 case/evidence 계약 변경에서 정한다. 예를 들어 `event_confirmation=USER_UNSURE` 같은 상태가 필요하지만, 이 보고서에서 새 enum 이름을 확정하지는 않는다.
  - 임의의 `UNSPECIFIED_TRAFFIC_VIOLATION` VisualEventType을 만들지 않는다. 모르는 구체 사건 유형은 null로 보존한다.

- [x] **`잘 모르겠어요` 이후 일반 신고문을 최종 Package까지 허용한다.**

  - `ReportPackage` 계약은 FINAL_PACKAGE `PASS`뿐 아니라 `WARN`도 이미 허용한다.
  - 일반 신고문은 확인되지 않은 구체 위반을 단정하지 않고 관찰 사실, 대상 차량, 시각·장소 등 확인된 정보만 사용한다.
  - case의 AI가 신고유형이나 위반 내용을 임의 확정하지 않는다. case는 사용자 응답·candidate hint를 구조화해 넘기고, 4→2 매핑·specific/generic template 선택·Requirement 판정은 evidence가 소유한다.

### `visual_event_type=null`의 현재 임시 template 원칙

null을 신고문이나 화면에 `null`, `UNKNOWN`, `기타 위반` 같은 사건 유형으로 직접 표시하지 않는다. 최종 확인 화면과 실제 신고문을 다음처럼 분리한다.

- 최종 확인 화면에는 `신고 상황: 구체 유형 미확정`, `상태: AI 추정`을 표시하고 기본 신고유형 추천임을 함께 알린다.
- `ReportPackage.report_inputs.safety_report_type`에는 4→2 fallback 규칙으로 고른 안전신문고 추천값을 넣는다.
- 실제 신고문은 신호위반·중앙선 침범 등 확인되지 않은 구체 위반을 단정하지 않고, 차량·발생 시각·장소와 영상에서 확실히 관찰된 사실만 사용한다.
- generic template은 null을 가짜 VisualEventType으로 치환하지 않으며, 구체 유형 확인이 어렵다는 사실과 첨부 영상 확인 요청을 담을 수 있다.

현재 검토용 문구 예시는 다음과 같다.

> 해당 일시와 장소에서 촬영된 차량의 주행 상황에 대해 신고합니다. 구체적인 위반 유형은 확인하기 어려워 첨부 영상을 바탕으로 확인을 요청드립니다.

이 문구는 **최종 확정 template이 아니다.** 이번 회차에서는 null 처리 방식, 구체 위반 단정 금지, fallback 신고유형, WARN Package 허용까지만 결정한다. 제목·본문 구성과 표현 품질은 실제 신고 규정 원본 및 사용성 검토와 함께 후속 고도화한다.

## B. 신규/변경 fixture 재검수

- [x] 김준영 담당 `evidence`·`common/runtime` 신규·변경분을 검수했다.
- [x] `scenario_plate_reread_001`: 번호판 abstain → EvidenceRecord 유지 → `PLATE_REREAD` → 새 `PLATE_READ` Job + `force_rerun=true` → QUEUED 흐름은 이상 없음.
- [x] `scenario_infra_failure_001`: 같은 `job_id`에서 attempt 1 STALE, 새 `execution_id`의 attempt 2 FAILED, 실패 ReadoutRun과 UsageRecord 연결은 이상 없음.
- [x] `scenario_relative_rebase_001`: common/runtime의 coarse 실행·usage 연결은 이상 없음. 이 시나리오에 evidence fixture가 없는 것은 사건 확정 전 timeline/search 사례라는 범위와 맞는다.
- [x] happy/u001/plate_reread/correction_rerun의 VISUAL_VERIFY 실행: `FINE_VERIFY` JobExecution이 실제 Fine `AnalysisRun`과 usage를 생산하고 `VisualEvidence.run_id`가 Fine run을 가리키는 것을 확인했다.
- [x] GPS: happy의 `Observation<Coordinate>.status=OK`와 EvidenceRecord.coord, u001의 source absent `UNKNOWN`이 구분된다. 주소를 지어내지 않은 것도 맞다.
- [x] 예산: 예산은 1,000 KRW, authoritative `UsageRecord.cost`는 전부 KRW이며 7개 시나리오 원장 합계는 각각 0~938 KRW다. 현재 fixture는 예산 안에 있다.
- [ ] **발견 사항 1 — 수정 필요:** u001은 `UNCERTAIN` 이후 `evidence_records=[]`, `requirement_reports=[]`, `report_packages=[]`와 blocking notice로 종료한다. Product Flow 및 A 답변대로 `잘 모르겠어요` 후 generic/WARN Package 경로를 추가해야 한다.
- [ ] **발견 사항 2 — 수정 필요:** `safety_report_type`이 EvidenceRecord의 `UNSAFE_*`, CaseView/Package의 `안전운전 불이행`, Architecture의 안전신문고 추천 2종으로 갈라져 있다. 4→2 mapping registry와 generic/specific template을 versioned artifact로 만든 뒤 fixture를 교체해야 한다.
- [ ] **발견 사항 3 — 보강 권고:** `REPORT_VIDEO_EXPORT` kind는 계약에 등재됐지만 이를 사용하는 JobRecord/JobExecution fixture는 0건이다. happy의 Report Video는 DerivedAsset만 존재하므로 common/runtime 소비 예시까지 검증하려면 export 실행 chain 1건이 필요하다.

### 이슈에서 함께 호출할 담당자

#### 유소연 — `case` Owner

**호출 이유:** 이번 변경은 evidence 필드 하나를 nullable로 만드는 데서 끝나지 않는다. `case`가 선택 후보, Fine 결과, 사용자의 신고 상황 응답을 어떤 순서로 보존하고 evidence에 넘길지가 정해져야 u001이 blocking 상태에서 정상 진행 상태로 바뀐다. 또한 candidate 변경·재탐색·Evidence 재조립의 orchestration은 case 소유다.

**확인할 부분:**

- 선택 candidate의 `selection_rev`, `VisualEvidence.verification`, `event_type_hint`, 사용자 응답(`맞아요 / 다른 상황 / 잘 모르겠어요`)을 evidence 호출 입력에 어떤 구조로 전달할지 확인한다.
- `잘 모르겠어요`를 단순한 값 부재가 아니라 **사용자 확인을 한 번 완료했으나 구체 사건 유형은 확정하지 않은 상태**로 구분할 machine-readable 필드를 정한다. 현재 Draft인 `CorrectionRecord`를 쓸지, case workflow state를 별도로 둘지도 함께 확인한다.
- 아직 질문하지 않은 상태와 사용자가 `잘 모르겠어요`라고 답한 상태가 같은 null로 내려가지 않도록 한다. 전자는 확인 대기, 후자는 generic 신고자료 생성 가능 상태다.
- 같은 candidate에서는 신고 상황을 반복 질문하지 않고, 다른 candidate를 선택했을 때만 사건 종속 확인 상태를 초기화하는지 확인한다. 번호판처럼 candidate 변경 후에도 유지되는 값과 섞지 않는다.
- `다른 상황`이 단순 사건 유형 정정이면 evidence 재조립만 수행하고, 사용자가 candidate·시간 범위·대상 차량 자체를 부정한 경우에만 case가 search를 재발주하도록 분기한다.
- `잘 모르겠어요` 이후 evidence가 EVIDENCE/FINAL_PACKAGE `WARN`과 ReportPackage를 반환하면 `stage=READY`로 진행할 수 있는지 확인한다. WARN을 blocking 상태로 다시 해석하거나 case가 신고유형을 자체 계산하면 안 된다.
- `scenario_unknown_abstain_partial_001`의 blocking notice를 non-blocking 안내로 바꾸고, `evidence`, `requirements_evidence`, `requirements_package`, `package` projection이 generic/WARN 결과를 담도록 case fixture를 검토한다.

**영향받는 주요 파일/계약:** `contract-job-record-case-view.md`, 필요 시 `contract-correction-record.md`, `data/mock/case/scenario_unknown_abstain_partial_001.json`, 신규 generic/WARN 시나리오를 분리한다면 해당 case fixture와 scenario manifest.

**확인 결과로 남겨야 할 내용:** case→evidence 전달 필드 모양, candidate 변경 시 초기화 규칙, `다른 상황`과 재탐색의 경계, WARN Package를 READY로 투영하는 조건.

#### 신유민 — `web` Owner

**호출 이유:** `잘 모르겠어요`를 허용하면 값은 진행 가능한 상태지만 구체 사건 유형은 확정되지 않은 상태가 된다. web이 이를 실패·차단 또는 사용자 확인 완료로 잘못 표시하면 Product Flow가 달라진다. web은 raw Evidence를 해석하지 않고 CaseView projection만 소비하므로 필요한 표시 정보가 CaseView에 충분한지도 확인해야 한다.

**확인할 부분:**

- 신고 상황 확인 전, `맞아요`, `다른 상황`, `잘 모르겠어요` 이후의 화면 상태가 각각 구분되는지 확인한다.
- `잘 모르겠어요` 이후에는 같은 질문을 반복하지 않고 다음 단계로 진행하되, 구체 사건 유형이 확정되지 않았다는 사실과 `AI 추정` 상태를 최종 확인 화면까지 유지한다.
- 기본 추천인 `교통위반(고속도로 포함)` 또는 `이륜차 위반`을 “AI가 확정한 법적 판정”으로 표시하지 않고, 사용자가 안전신문고에서 직접 선택할 추천 항목으로 보여주는지 확인한다.
- generic 신고문은 확인된 관찰 사실만 보여주고, null인 `visual_event_type`을 임의 label이나 `기타 위반` 같은 새 유형으로 변환하지 않는지 확인한다.
- Requirement `WARN`과 non-blocking notice가 있어도 신고자료 생성·다운로드·복사·안전신문고 이동이 가능해야 한다. 반대로 아직 사용자에게 신고 상황을 묻지 않은 상태는 진행 완료처럼 보여서는 안 된다.
- web이 `source.kind`, candidate hint 또는 confidence를 읽어 `INFO_AI_ESTIMATED`/신고유형을 재계산하지 않고, case가 제공한 `info_state`, label, warning만 사용하는지 확인한다.
- `scenario_unknown_abstain_partial_001`의 최종 CaseView fixture만으로 위 화면을 구현할 정보가 충분한지 검토하고, 부족한 필드가 있다면 case 계약 변경 요청으로 남긴다.

**영향받는 주요 파일/계약:** `contract-job-record-case-view.md`의 evidence/package projection과 notices, `data/mock/case/scenario_unknown_abstain_partial_001.json`, 실제 web의 신고 상황 확인·최종 확인·신고자료 화면.

**확인 결과로 남겨야 할 내용:** 화면별 표시 문구에 필요한 CaseView 필드, WARN의 진행 가능 처리, 반복 질문 방지, 기본 추천과 확정 판정을 구분하는 표시 방식.

#### 김준영 — `evidence` Owner

**호출 이유:** 사건 유형 nullable 조건, 안전신문고 신고유형 추천, 신고문 template, Requirement 판정과 ReportPackage 생성은 evidence의 authoritative 정책이다. case나 web에서 이 값을 임의로 보완하지 않게 하려면 계약과 versioned policy artifact가 함께 바뀌어야 한다.

**확인할 부분:**

- `EvidenceRecord.event.visual_event_type`을 nullable/optional로 허용하는 정확한 조건을 **사용자의 명시적 `잘 모르겠어요` 응답 이후**로 제한한다. Fine 실행 실패나 미확인 상태까지 허용 범위를 넓히지 않는다.
- null 상태의 provenance를 어디에 보존할지 정한다. 사용자 응답 상태를 EvidenceRecord에 snapshot할지, case 상태 ref를 근거로 연결할지 결정하되 `UNKNOWN` 문자열이나 가짜 VisualEventType을 만들지 않는다.
- 4개 VisualEventType을 실제 안전신문고 선택지 2종으로 매핑하는 registry를 versioned artifact로 만든다. exact code/label은 실제 규정 원본을 근거로 하고 현 `UNSAFE_*` placeholder와 `안전운전 불이행`을 canonical 값으로 승인하지 않는다.
- `잘 모르겠어요`일 때 안전모/이륜차 근거가 있으면 이륜차 위반, 그렇지 않으면 교통위반(고속도로 포함)을 기본 추천하는 fallback 우선순위를 명시한다.
- specific template과 generic template을 분리한다. generic `violation_expression`은 신호위반·중앙선 침범처럼 확인되지 않은 구체 위반을 단정하지 않고 차량 행동과 시각·장소 등 확인된 사실만 사용한다.
- 사용자-unsure 상태에 대응하는 Requirement check code/reason을 정하고 EVIDENCE/FINAL_PACKAGE overall을 `WARN`으로 만드는 규칙을 명시한다. `WARN`이므로 ReportPackage 생성은 허용하되 warning/provenance가 Package와 CaseView까지 보존돼야 한다.
- 기존 확정 경로(happy, plate_reread, correction_rerun)가 nullable 확장 때문에 느슨해지지 않는지 회귀 확인한다. `VisualEvidence=OBSERVED`이고 사용자가 동의한 경우에는 기존처럼 구체 event와 specific template을 사용해야 한다.

**영향받는 주요 파일/계약:** `contract-evidence-record-needs.md`, `contract-requirement-report-package.md`, evidence 소유 SafetyReportType/mapping/template artifact, `data/mock/evidence/scenario_unknown_abstain_partial_001.json` 및 관련 happy/plate/correction fixture.

**확인 결과로 남겨야 할 내용:** nullable 불변조건과 계약 버전, 사용자 응답 provenance, 4→2 매핑표와 fallback 우선순위, generic template, WARN check와 Package 생성 예시.

#### 정철원 — `common/runtime`의 `JobExecution` 구현 담당

**호출 이유:** 현재 계약에는 `REPORT_VIDEO_EXPORT` Job kind가 추가됐지만 Mock에는 이를 실행하는 JobExecution이 없다. happy 시나리오는 Report Video DerivedAsset이 이미 존재해도 어떤 execution이 만들었는지 연결되지 않으므로 runtime 구현과 재시도 동작을 검증할 기준이 부족하다.

**확인할 부분:**

- case가 발행한 `REPORT_VIDEO_EXPORT` JobRecord를 runtime이 별도 JobExecution으로 실행할 수 있는지 확인한다.
- 성공 execution의 `produced[]`가 `derived_asset` Report Video ref를 가리키고, 관련 UsageRecord가 execution과 실제 export 작업을 추적할 수 있는지 확인한다.
- export가 실패했을 때 기존 confirmed Evidence는 유지하고 export/package만 재시도한다는 부분 재실행 경계를 확인한다.
- 같은 job의 infra retry라면 새 `execution_id`와 증가한 `attempt`를 사용하고, 사용자가 조건을 바꾸어 새 export를 요청한 경우에는 새 JobRecord가 되는지 구분한다.
- 우선 happy에 성공 chain 1건을 추가할 수 있는지 검토하고, 실패/재시도 fixture는 별도 시나리오가 필요한지 의견을 남긴다.

**영향받는 주요 파일/계약:** `contract-job-execution.md`, `contract-job-record-case-view.md`, `data/mock/common/scenario_happy_001.json`, `data/mock/case/scenario_happy_001.json`, `data/mock/recording/scenario_happy_001.json`.

**확인 결과로 남겨야 할 내용:** REPORT_VIDEO_EXPORT 실행의 produced/usage 연결, 성공 최소 fixture, 실패 시 retry와 부분 재실행 경계.

#### Search Owner 호출 여부

현재 결정만으로는 Search Owner에게 새 분석 동작이나 fixture 변경을 요청할 필요가 없다. Search는 기존처럼 candidate, Fine `VisualEvidence`, candidate hint와 uncertainty를 제공하면 된다. 사용자 확인 상태를 해석하거나 SafetyReportType을 만드는 것은 Search 책임이 아니다.

다만 case 검토 결과 `다른 상황` 또는 candidate 부정의 의미가 기존 재탐색 입력을 바꾸거나, Search가 보존해야 할 hint/provenance가 부족하다고 확인되면 그때 Search Owner를 추가 호출한다. 이 경우에도 evidence가 search를 직접 호출하지 않고 case가 기존 Job orchestration 경계로 발주한다.

---

## 3. A 답변의 근거와 권장 데이터 흐름

### 3.1 현재 확정 Product Flow

`core-user-flow.md`는 후보 선택 뒤 번호판과 신고 상황만 사용자 확인 대상으로 두고, 신고 상황 화면에 `맞아요 / 다른 상황 / 잘 모르겠어요`를 제공한다. 특히 `잘 모르겠어요`도 진행을 막지 않고 `AI 추정` 상태로 최종 확인까지 보낸다고 명시한다.

Architecture의 호출 순서도 다음 경계를 이미 정한다.

```text
search: candidate + Fine VisualEvidence
    ↓
case/web: Top-3 표시 및 사용자 candidate 선택
    ↓
case: 선택 후보 기준 후속 관찰값 수집
    ↓ values only
evidence: EvidenceRecord 조립 + 신고유형/신고문/Requirement/Package
```

즉 Fine 결과는 사용자 후보 선택 전에 존재할 수 있지만, EvidenceRecord는 선택 후보와 사용자 확인 상태를 받은 뒤 조립된다. evidence가 search를 다시 돌릴 정보나 권한을 가져야 할 이유가 없다.

### 3.2 권장 상태 전이

```text
선택 candidate의 Fine 결과
    ├─ OBSERVED ─→ 상황 1회 확인
    │                 ├─ 맞아요 ─────→ 구체 event + 구체 template
    │                 ├─ 다른 상황 ─→ 사용자 선택값 + 재매핑
    │                 └─ 잘 모르겠어요 → event 미확정 + 기본 추천 + 일반 template + WARN
    │
    ├─ UNCERTAIN ─→ 관찰 내용/불확실성 제시 후 같은 1회 확인
    │                 └─ 잘 모르겠어요 → event 미확정 + 기본 추천 + 일반 template + WARN
    │
    └─ 후보/범위 자체를 부정
                      └─ case가 후보 변경 또는 search 재발주
```

여기서 “후보/범위 자체를 부정”과 “선택한 사건의 구체 유형은 모르겠음”은 다르다. 전자는 case/search orchestration 문제이고, 후자는 evidence가 generic 신고자료로 처리할 수 있는 제품 상태다.

### 3.3 계약 변경의 최소 조건

현 `EvidenceRecord.event`의 세 값은 모두 필수 `EvidenceValue<T>`이며 null을 허용하지 않는다. 따라서 다음 중 동등한 형태의 계약 변경이 필요하다.

1. `visual_event_type`만 제한적으로 nullable/optional로 바꾼다.
2. null이 허용되는 정확한 상태를 사용자 응답 provenance로 구분한다.
3. `safety_report_type`과 `violation_expression`은 fallback 정책으로 계속 생성할 수 있게 한다.
4. Requirement에 “구체 사건 유형 미확정이나 일반 신고자료 진행 허용” WARN check를 추가한다.
5. FINAL_PACKAGE overall=WARN과 ReportPackage가 함께 존재하는 fixture를 만든다.
6. CaseView는 `INFO_AI_ESTIMATED`와 non-blocking notice를 투영한다.

`EvidenceRecord`가 confirmed value만 보존한다는 기존 원칙을 지키려면 null 자체를 confirmed 값처럼 포장해서는 안 된다. “사용자가 확인했지만 구체 유형을 확정하지 않음”이라는 workflow 사실과, evidence가 확정한 fallback 신고유형/일반 표현을 분리해 기록해야 한다.

### 3.4 왜 PM/case/web 확인이 필요한가

기본 정책 방향은 이번 답변으로 정할 수 있다. PM이 다시 “신규 Need를 만들지 말지”를 선택할 필요는 없다. 다만 아래는 한 모듈 내부 결정이 아니므로 교차 확인이 필요하다.

- 사용자의 `잘 모르겠어요`를 어느 case 상태/CorrectionRecord로 저장하고 언제 초기화할지
- EvidenceRecord nullable 변경이 기존 Consumer와 버전 호환되는지
- WARN Package를 READY로 보여주면서도 “법적 유형 확정”처럼 오해시키지 않는 UI 문구
- 기본 신고유형이 향후 2종보다 늘어날 때 case 코드가 아니라 evidence의 versioned mapping만 바꿔 확장할 수 있는지

따라서 PM 관점은 정책을 evidence 대신 수행하기 위해서가 아니라, 동일한 사용자 응답이 case·evidence·web에서 서로 다른 의미로 구현되지 않게 release behavior를 맞추기 위해 필요하다.

---

## 4. 신규·변경 fixture 상세 검수

### 4.1 `scenario_plate_reread_001` — `PASS`

- 원 PlateReadout의 abstain은 실행 실패가 아니라 성공한 관찰의 보류 상태로 남는다.
- EvidenceRecord는 사건 유형·시각을 유지하고 차량번호만 만들지 않는다.
- `EvidenceNeeds.items[].kind=PLATE_REREAD`, `would_fill=VEHICLE_NUMBER`, `optional=false`가 계약과 맞는다.
- case는 `kind=PLATE_READ`, 새 `job_id`, `force_rerun=true`로 번역하고 common/runtime은 새 execution을 QUEUED로 둔다.
- EVIDENCE Requirement가 `UNKNOWN`, ReportPackage가 미생성인 것도 재판독 대기 상태와 맞는다.

제한 사항은 이 시나리오 자체가 아니라 `UNSAFE_SIGNAL_VIOLATION` placeholder다. 실제 4→2 신고유형 artifact가 생기면 교체해야 한다.

### 4.2 `scenario_infra_failure_001` — `PASS`

- attempt 1은 STALE, `ended_at=null`, `produced=[]`, `failure_kind=null`이다.
- attempt 2는 같은 `job_id`, 새 `execution_id`, 증가한 attempt=2, 종료 상태 FAILED다.
- 실패한 ReadoutRun은 `outcome=FAILED`, `failure.kind=INFRA`, `READOUT_PROVIDER_TIMEOUT`을 사용하고 결과 PlateReadout을 만들지 않는다.
- 실패 attempt에 발생한 UsageRecord를 원장으로 남기며 비용 0 KRW도 유효한 관찰이다.

이 시나리오는 domain abstain과 worker/provider 실패를 분리하므로 common/runtime 구현 fixture로 사용할 수 있다.

### 4.3 `scenario_relative_rebase_001` — 김준영 범위 `PASS`

이 시나리오의 주 대상은 recording/search/case다. common/runtime에서는 coarse JobExecution SUCCEEDED와 `usage_rb001_coarse` 84 KRW 연결만 담당하며 이상 없다. 사건 선택·Evidence 조립 이전 상태이므로 evidence fixture가 없는 것도 자연스럽다.

### 4.4 VISUAL_VERIFY 추가 4건 — `PASS`

happy/u001/plate_reread/correction_rerun에서 다음을 확인했다.

- Case Job kind는 `FINE_VERIFY`다.
- common/runtime JobExecution은 `VISUAL_VERIFY` AnalysisRun을 produced ref로 연결한다.
- Fine UsageRecord는 해당 execution/run을 가리킨다.
- VisualEvidence.run_id는 Coarse가 아니라 Fine run을 가리킨다.
- u001의 Fine은 실행 성공과 판단 불충분을 구분해 `verification=UNCERTAIN`, `visual_event_type=null`로 반환한다.

### 4.5 GPS 있음/없음 — `PASS_WITH_LIMIT`

- happy는 `recording.gps_stream`의 OK 좌표 `{lat, lon}`을 EvidenceRecord.coord과 CaseView.coord까지 전달한다.
- u001은 GPS source absent를 `UNKNOWN` Observation으로 명시한다.
- reverse-geocode 원본 없이 address/place_name을 만들지 않은 것은 “모르는 값을 지어내지 않는다”는 경계와 맞는다.
- user hint를 location 대표값으로 쓰는 동안 `INFO_NEEDS_REVIEW`인 것은 현재 CaseView의 location 전용 파생 규칙과 맞다. object-level `review_needed=false`와 `info_state`는 계약상 독립 축이므로 오류로 분류하지 않는다.

### 4.6 KRW 예산 정규화 — `PASS_WITH_FOLLOW_UP`

authoritative 원장 합계는 다음과 같다.

| 시나리오 | UsageRecord 합계 | 예산 |
| --- | ---: | ---: |
| correction_rerun | 630 KRW | 1,000 KRW |
| empty | 434 KRW | 1,000 KRW |
| happy | 938 KRW | 1,000 KRW |
| infra_failure | 0 KRW | 별도 AnalysisScope 없음 |
| plate_reread | 728 KRW | 1,000 KRW |
| relative_rebase | 84 KRW | 1,000 KRW |
| unknown_abstain_partial | 756 KRW | 1,000 KRW |

`AnalysisRun.usage_summary`의 provider-native USD snapshot과 예산 판정용 KRW `UsageRecord`는 용도가 다르며, 현재 결정 문서는 예산 판단에서 UsageRecord만 신뢰하도록 한다. 다만 실제 pricing/FX artifact는 아직 opaque `pricing_id`뿐이므로 common/runtime 구현 시 조회 가능한 versioned artifact를 마련해야 한다.

---

## 5. Findings

### Required-1. u001의 blocking 종료는 확정 Product Flow와 충돌한다

**근거**

- Search fixture는 candidate hint를 보존하면서 Fine 결과를 `UNCERTAIN`, `visual_event_type=null`로 낸다.
- Evidence fixture는 `evidence_records`, `evidence_needs`, `requirement_reports`, `report_packages`를 모두 빈 배열로 둔다.
- Case fixture는 `evidence.visual_event_unconfirmed`를 blocking WARN으로 표시하고 진행 action도 제공하지 않는다.
- 반면 Product Flow는 `잘 모르겠어요`도 진행을 막지 않고 AI 추정을 유지한다고 명시한다.

**영향**

- 현재 fixture를 canonical seed로 쓰면 case/web이 사용자를 dead end에 가둔다.
- Evidence 구현은 generic template과 WARN Package 분기를 만들 근거를 잃는다.
- 신규 `EvidenceNeeds.kind`를 추가해도 사용자 응답과 Job 요청이 섞여 올바른 해결이 되지 않는다.

**요구 변경**

- A의 nullable/provenance 규칙을 EvidenceRecord 계약에 반영한다.
- case→evidence 사용자 응답 전달 계약을 정한다.
- u001 또는 별도 시나리오에 `잘 모르겠어요 → generic Requirement WARN → FINAL_PACKAGE WARN → ReportPackage`를 추가한다.
- CaseView에 `INFO_AI_ESTIMATED`와 non-blocking 안내를 포함한다.

### Required-2. 신고유형이 세 표현으로 갈라져 canonical mapping이 아니다

현재 happy 기준으로 다음 값이 동시에 존재한다.

- EvidenceRecord: `UNSAFE_LANE_CHANGE`
- CaseView/ReportPackage: `안전운전 불이행`
- Architecture의 안전신문고 Report Type 예시 및 이번 결정: `교통위반(고속도로 포함)`

Mock 문서도 `UNSAFE_*`가 placeholder라고 명시하므로 구조 검증 PASS는 이 값을 승인하지 않는다.

**요구 변경**

- 4개 VisualEventType → 2개 SafetyReportType → specific/generic violation expression/template을 한 versioned artifact에서 관리한다.
- 정확한 외부 코드·표시명은 실제 안전신문고 규정 원본과 버전을 근거로 한다.
- case AI와 web이 별도의 매핑표를 갖지 않도록 한다.
- happy, plate_reread, correction_rerun, 잘 모르겠어요 WARN 사례를 새 artifact 기준으로 갱신한다.

### Should-1. `REPORT_VIDEO_EXPORT` runtime chain이 아직 미커버다

계약에는 `REPORT_VIDEO_EXPORT`가 등재됐지만, Mock Pack에는 해당 JobRecord/JobExecution이 없다. happy의 Report Video DerivedAsset과 ReportPackage는 존재하나 실행 provenance가 중간에서 생략돼 있다.

이것은 이번 신규 3개 시나리오의 값 오류는 아니지만, common/runtime이 새 kind를 실제로 처리할 수 있음을 검증하려면 최소 성공 1건과 향후 실패/재시도 1건이 필요하다.

### Known gap. 이번 2차 검수에서 새로 결정하지 않는 항목

- `TimeResolution.status=UNKNOWN`
- `RequirementReport.overall=BLOCK`
- `ReadoutRun.outcome=PARTIAL`
- `SpanResolution.status=FAILED`
- DeletionReport 전체
- reverse-geocode 기반 `location.address/place_name`
- notice code 대소문자와 `actions[]` 값 공간
- `CorrectionRecord`에서 신고 상황 사용자 응답을 기록할 exact kind/field

마지막 두 항목 가운데 notice/actions는 공지대로 notices/case 계약 결정이 먼저다. `CorrectionRecord` 표현은 Required-1을 구현할 때 case/evidence Consumer Review에서 함께 확인해야 한다.

---

## 6. 1차 검수 항목 회귀 확인

| 1차 검수 핵심 항목 | 2차 상태 | 판단 |
| --- | --- | --- |
| KRW 예산 vs USD 원장 비교 불가 | authoritative UsageRecord KRW 정규화, 예산 1,000 | `RESOLVED` |
| Fine VisualEvidence가 Coarse run 참조 | VISUAL_VERIFY run 4건 추가 | `RESOLVED` |
| overlay 없음과 실행 실패 혼용 | NOT_APPLICABLE과 신규 INFRA 실패 분리 | `RESOLVED` |
| runtime STALE/retry 부재 | infra_failure에 attempt 1→2 추가 | `RESOLVED` |
| GPS 있음/없음 부재 | happy OK / u001 UNKNOWN 추가 | `RESOLVED` |
| post_stamp 불필요인데 poststamp transform | happy transform이 trim으로 정정 | `RESOLVED` |
| plate-visible check category/provenance | VEHICLE + readout ref로 보강 | `RESOLVED` |
| Windows cp949 validator 종료 실패 | cp949에서도 PASS | `RESOLVED` |
| 실제 SafetyReportType/rule/template 부재 | source.kind registry만 신설, 신고 정책은 미해소 | `OPEN` |
| Requirement BLOCK/INFO_AI_ESTIMATED/WARN Package 미커버 | 여전히 미커버 | `OPEN` |
| Report Video export Job chain 부재 | kind만 등재, fixture 없음 | `OPEN` |
| 역할분담 표의 JobRecord 소유권 오기 | `ownership.md` 공통 기반 행에 여전히 JobRecord 표기 | `OPEN_EXISTING` |

---

## 7. 재검수 통과 조건

- [ ] `EvidenceNeeds` 신규 kind 없이 사용자 확인 workflow와 추가 Job 요청을 분리한다.
- [ ] `잘 모르겠어요`의 case→evidence machine-readable 상태가 정해진다.
- [ ] `visual_event_type=null` 허용 조건과 provenance가 EvidenceRecord 새 버전에 명시된다.
- [ ] 4→2 SafetyReportType mapping과 정확한 외부 label/code가 versioned evidence artifact에 등록된다.
- [ ] 구체 사건을 단정하지 않는 generic violation expression/template이 등록된다.
- [ ] EVIDENCE/FINAL_PACKAGE `WARN`과 ready-only ReportPackage가 함께 있는 사용자-unsure fixture가 생긴다.
- [ ] CaseView가 `INFO_AI_ESTIMATED`와 non-blocking notice를 제공하고 web이 그 의미를 확인한다.
- [ ] `REPORT_VIDEO_EXPORT` 성공 JobRecord→JobExecution→DerivedAsset 연결 fixture가 최소 1건 생긴다.
- [ ] `python data/mock/validate_mock_pack.py` 통과.
- [ ] `python scripts/check_contract_fixtures.py` 통과.
- [ ] `python scripts/check_boundaries.py` 통과.
- [ ] `npm run build` 통과.

---

## 8. 검증 실행 기록

| 명령/검사 | 결과 | 해석 범위 |
| --- | --- | --- |
| `git status --short --branch` | `develop...origin/develop`, 기존 미추적 06 보고서만 존재 | 원격 동기화 및 사용자 파일 보존 확인 |
| `git diff --stat e94f527..HEAD` | 52 files, +5,340 / -808 | 1차 이후 2차 통합 범위 확인 |
| `python data/mock/validate_mock_pack.py` | PASS, 46 JSON / 7 scenarios / 오류 0 | Mock 구조·참조·구현된 의미 불변조건 |
| cp949 환경의 동일 validator | PASS, exit 0 | 이전 Windows 인코딩 회귀 해소 |
| `python scripts/check_contract_fixtures.py` | 문서 60 / JSON 26 / 의미 104 PASS | Contract fixture 정합성 |
| `python scripts/check_boundaries.py` | PASS, 0 violations | 현재 골격의 경계 문자열 검사 |
| `npm run build` | PASS | prototype TypeScript/Vite build; evidence/common 실제 구현 증명은 아님 |
| 7개 시나리오 UsageRecord 합계 확인 | 0~938 KRW, AnalysisScope 1,000 KRW 이내 | authoritative ledger 기준 예산 sanity check |
| `src/daesingo/{evidence,common}` 확인 | README만 존재 | 이번 판정은 fixture/contract 검수이며 구현 E2E 판정이 아님 |

---

## 9. 결론

2차 반영은 1차에서 발견된 구조·provenance·runtime 사례를 상당 부분 제대로 해소했다. 특히 common/runtime의 신규 실패·재시도와 KRW 원장, Fine 실행 연결은 실제 구현 골격으로 사용할 수 있다.

남은 핵심은 “AI가 구체 사건 유형을 확정하지 못했지만 사용자가 `잘 모르겠어요`로 계속 진행하는 정상 제품 상태”다. 이 상태는 새 EvidenceNeeds가 아니라 case의 사용자 workflow 상태와 evidence의 제한적 nullable/fallback 정책으로 풀어야 한다. 최종 Package를 막지 않고 WARN으로 허용하되, 구체 위반을 지어내지 않는 일반 신고문과 AI 추정 provenance를 보존해야 한다.

따라서 현 상태는 다음처럼 기록한다.

```text
MOCK_STRUCTURE_VALIDATED
COMMON_RUNTIME_ROUND2_PASS
EVIDENCE_ROUND2_PARTIAL_READY
USER_UNSURE_GENERIC_WARN_PATH_REQUIRED
SAFETY_REPORT_MAPPING_ARTIFACT_REQUIRED
REQUEST_CHANGES
```

---

## 10. 이슈 #25 담당자 답변 로컬 검토 메모 (2026-09-10)

유소연(case), 신유민(web), 정철원(common/runtime 구현)의 답변을 검토해 아래 방향을 로컬 메모로 정리했다. 이 내용은 이슈 답변으로 게시하지 않는다.

### 수용한 방향

- case가 선택 후보별 신고 상황 응답을 저장하고 evidence 호출 입력으로 전달한다.
- web은 raw source/hint/confidence를 재해석하지 않고 CaseView의 상태·라벨만 표시한다.
- WARN Package도 capabilities를 유지하고 `stage=READY`로 진행할 수 있다.
- happy에 `REPORT_VIDEO_EXPORT` 성공 JobRecord→JobExecution→DerivedAsset→UsageRecord chain을 추가한다.
- user location hint의 `needs_review=false`와 `INFO_NEEDS_REVIEW` 병존은 계약상 독립 축이므로 허용하고, web은 `review_needed`를 제출 gate로 쓰지 않는다.

### 조정해 확정한 방향

- 사용자 응답 enum은 `CONFIRMED | CORRECTED | USER_UNSURE`로 한다. `UNKNOWN`은 관찰 부재 의미와 겹치고 `REJECTED`는 candidate 거절로 오해되므로 쓰지 않는다.
- 사용자가 직접 고른 사건 유형은 `visual_event_type_hint`가 아니라 `selected_visual_event_type`으로 전달한다.
- CaseView candidate 상태는 `NOT_ASKED | CONFIRMED | CORRECTED | USER_UNSURE`로 구분한다.
- `evidence-record/v1.3`에서 `event.situation_confirmation`을 추가하고 `USER_UNSURE`일 때만 `visual_event_type=null`을 허용한다.
- 세 event display에 `info_state`·`source_label_key`, Package projection에 필드별 `report_field_states`를 추가하는 방향으로 한다.
- Report Video export 순서는 Package 이후가 아니라 `EVIDENCE Requirement → export → FINAL_PACKAGE Requirement → Package`다.
- CorrectionRecord에는 `SITUATION_CHANGE`, semantic `target_field` 값 공간, `supersedes_ref`를 추가하고, 유효하지 않은 입력에는 레코드를 만들지 않는다. 유효한 correction 이후 downstream 실행이 실패한 경우 correction은 보존한다.
- STALE/호출 전 실패에는 ReadoutRun 0건을 허용하도록 1 execution:1 run 불변조건 범위를 좁힌다.
- provider timeout에서 처리 영상 길이를 측정하지 못한 경우 `processed_duration_sec=null`로 하고 UsageRecord operation을 `READOUT_*`/`RECORDING_*` namespace로 정규화한다.

### 별도 사용자 결정 없이 후속으로 남긴 것

- SafetyReportType의 실제 code/label은 안전신문고 원본 확보 후 확정한다.
- generic 신고문 최종 문구는 후속 사용성 고도화 대상으로 둔다.
- notices code/actions registry는 이슈 #26의 case 계약 작업과 맞춘다.
- Report Video export 실패 taxonomy/fixture는 성공 chain 반영 뒤 별도 추가한다.

현재 사용자와 다시 선택해야 할 정책 분기는 없다. 위 네 항목은 원본·문안·다른 Owner 계약 반영이 필요한 후속 작업이지 이번 설계 방향을 막는 결정 사항은 아니다.
