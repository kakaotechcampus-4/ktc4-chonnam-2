# 김준영 담당 Mock Pack v3 3차 검수 보고서

> 검수일: 2026-09-10
> 기준 브랜치: `develop`
> 기준 커밋: `e056d64` (`origin/develop`과 동기화 확인)
> 비교 기준: Mock Pack v2 통합 `7dcfce5` → Mock Pack v3 통합 `e056d64`
> 검수 범위: 김준영 담당 `evidence` 및 `common/runtime`, 변경된 7개 소유 fixture와 Report Video·사용자-unsure·재판독·실패/STALE 직접 접합부
> 검수 관점: Contract 일치 / 실제 모듈 생산 가능성 / UNKNOWN·ABSTAIN·실패 / Consumer 사용 가능성 / 2차 검수 회귀 / correctness·architecture·security·performance
> 선행 보고서: `docs/modules/evidence/reviews/07_kim-junyoung_mock_round2_review_2026-09-09.md`

## 0. 이번 검수에서 누가 무엇을 확인하나

이번 검수는 단순한 fixture 오탈자 수정만은 아니다. 객관적으로 바로 고칠 수 있는 항목과 Owner 간 계약 결정이 필요한 항목이 섞여 있다. 다만 김준영이 원시 JSON과 시각값을 다시 직접 대조할 필요는 없고, 아래 evidence/common-runtime 원칙과 eval 3차 검수 이슈 #30 B-1의 계약 방향을 확인하면 된다. 현재 이 Owner 판단은 모두 완료됐다.

### 김준영 확인 결과

1. **[김준영 확인 완료] UsageRecord 생성 기준**: 실패·STALE attempt도 실제 provider/local capability 호출이 시작됐다면 남기고, 호출 전에 끝났다면 만들지 않는다.
2. **[김준영 확인 완료] 사용자 중단 표현**: `JobExecution.status`에 `CANCELLED`를 추가하고, 이미 생성된 부분 결과는 보존한다. 즉 사용자가 분석 도중 중단하면 오류(`FAILED`)가 아니라 사용자 중단(`CANCELLED`)으로 기록하고, 그전에 찾은 후보는 삭제하지 않되 전체 분석 완료 결과로 취급하지 않는다. `이어서 찾기`의 Job identity는 case/runtime가 별도 확정한다.
3. **[김준영 확인 완료] 사건 유형을 “잘 모르겠어요”로 답한 근거**: CaseView에만 응답을 두지 않고, 새 immutable EvidenceRecord revision에도 해당 사용자 응답의 snapshot/ref를 넣어 `visual_event_type.value=null`의 근거를 독립적으로 재현할 수 있게 한다.
4. **[김준영 확인 완료 · 이슈 #30 B-1] UsageRecord 집계와 Run 연결**: 사건 전체 비용은 `case_id`, 특정 Analysis/Readout Run의 사용량 감사는 `run_ref`를 정본 키로 사용한다. STALE 때문에 실패한 logical Run을 인위적으로 만들지 않고, 실제 호출은 시작됐지만 Run artifact가 생기지 않은 row는 `run_ref=null`과 별도의 사유값으로 직접 호출과 구분한다.

추가된 evidence 원본 조사 PDF 3개를 재검토한 결과, 축약 메모에서 빠진 근거가 확인됐다. `CorrectionRecord`의 evidence Consumer 수용 조건은 `docs/modules/evidence/contracts/correction-record-consumer-review-2026-09-10.md`에 확정했고, SafetyReportType 4→2 매핑과 specific/generic template은 `docs/modules/evidence/decisions/safety-report-policy-v1.md`에 등재했다. 따라서 두 항목은 더 이상 김준영의 추가 정책 선택을 기다리지 않는다. case Owner의 계약 반영과 mock Owner의 fixture 정규화만 남는다.

### case 통합 주도와 원 담당자 확인 범위

- **case/mock Owner**: Mock Pack 전체 통합 담당으로서 fixture·validator·문서뿐 아니라 아래 결정이 완료된 계약 개정 초안까지 한 PR에서 직접 반영한다. 대상은 `CorrectionRecord v1.1`, `EvidenceRecord v1.3`, `UsageRecord v1.2`, `JobExecution v1.1`, CaseView 대응 버전과 AnalysisRun Consumer 문구다.
- **evidence/common Owner**: 새 설계를 다시 제안하는 구현 주체가 아니라, case PR이 이 보고서의 확정 조건과 같은지 확인한다.
- **readout/web Consumer**: `USER_UNSURE`, `CANCELLED`, 필드별 상태를 소비할 수 있는지만 확인한다. `crop_ref`는 이슈 #31 A-3 결정을 case가 그대로 적용하므로 다시 질문하지 않는다.
- **eval Consumer**: 사건/source-video 비용=`case_id`, 특정 Run audit=`run_ref`, CANCELLED 집계 처리만 확인한다. 이슈 #30 B-1 답변을 다시 작성할 필요는 없다.
- **search Owner**: AnalysisRun Consumer 문구 정렬만 확인하며 별도 search fixture 작업은 없다.
- **recording Owner**: 이번 post-stamp/export chain은 이미 확정된 계약을 case가 조립할 수 있으므로 새 결정을 요청하지 않는다. 실제 worker 구현 제약이 발견될 때만 별도 확인한다.

### 별도 판단 없이 바로 수정 가능한 항목

- happy Report Video의 `EVIDENCE 판정 → export → FINAL_PACKAGE 판정 → package → READY` 시간·revision 순서 정리
- u001 post-stamp/export provenance 누락 보완
- 확정된 CaseView 필수 필드의 누락 snapshot 백필과 validator 보강
- 실제 provider 호출 여부에 맞춘 `usage_x001_plate_a1` 유지 또는 제거
- `CONTRACT_CONFLICTS.md`의 현재 계약과 어긋난 설명 및 기존 trailing whitespace 정리

따라서 이 문서는 **수정 요청서이면서 Owner 질문 답변서**다. 김준영 Owner 판단은 모두 확정됐고 공지 양식의 A/B 본문을 GitHub 이슈 #33으로 등록했다.

## 1. 최종 판정

**판정: `REQUEST_CHANGES` — v3의 방향은 맞지만, `common/runtime`과 `evidence` 모두 canonical seed로 승인하기 전에 의미 정합 보완이 필요하다.**

- 자동 검증은 전부 통과했다. `validate_mock_pack.py`는 46개 JSON·7개 시나리오를 오류 0건으로 검사했고, 계약 fixture 104개 의미 검사, boundary 검사, npm build, Windows cp949 출력도 통과했다.
- 2차 Required였던 `잘 모르겠어요 → generic EVIDENCE WARN → FINAL_PACKAGE WARN → ReportPackage → stage=READY` 경로가 u001에 실제로 생겼다. blocking dead-end를 없애고 `INFO_UNKNOWN`/`INFO_AI_ESTIMATED`, `unconfirmed_fields`, non-blocking notice를 제공한 방향은 수용한다.
- `plate_reread_001`은 최초 abstain을 보존하면서 새 ReadoutRun·UsageRecord·EvidenceRecord revision·Requirement PASS를 추가했다. `ev_p001 → ev_p001_v2` 자체는 immutable supersede 원칙과 맞는다.
- happy에 `REPORT_VIDEO_EXPORT` JobRecord→JobExecution→DerivedAsset→UsageRecord 체인이 처음 추가됐지만, 발주 revision과 시간 순서가 FINAL_PACKAGE보다 뒤섞였다. 현재 fixture대로면 아직 생성되지 않은 Report Video를 `PASS`로 판정한 뒤 export를 발주하는 순환이 생긴다.
- u001은 `TimeResolution.post_stamp.needed=true`인데 Report Video는 trim transform만 가리키고, post-stamp 적용·사용자 고지·export 실행 chain 없이 FINAL_PACKAGE WARN과 Package를 생성한다.
- CaseView 계약이 `situation_confirmation`, `case_type_display`/`violation_display`의 `info_state`·`source_label_key`를 필수처럼 등재했지만 기존 candidate/evidence snapshot에는 백필되지 않았다. 자동 validator가 이 계약 위반을 잡지 못한다.
- u001의 `visual_event_type.value=null`은 CaseView에만 사용자 `UNKNOWN` 응답이 있고 EvidenceRecord 자체의 stable provenance에는 그 응답이 없다. `evidence-record/v1.2`로는 “사용자 응답 후 제한 허용”과 “Fine 불확실성 때문에 null”을 독립적으로 판별할 수 없다.
- 2차에서 열어 둔 SafetyReportType 4→2 mapping과 generic/specific template은 복원된 원본 PDF를 근거로 evidence versioned artifact에 등재했다. 다만 v3 fixture에는 아직 `UNSAFE_*`와 한국어 표시값이 같은 authoritative 필드에서 혼용되므로 mock 정규화는 필요하다.

| 검수 축 | 판정 | 요약 |
| --- | --- | --- |
| `common/runtime` 변경 fixture | `REQUEST_CHANGES` | Usage operation namespace와 재판독 성공 usage는 양호하나, happy Report Video 발주/판정 순서, STALE UsageRecord 발행 조건, 사건/Run 집계 키의 역할 분리를 계약에 반영해야 한다. |
| `evidence` 사용자-unsure 경로 | `PARTIAL_READY` | dead-end 해소와 WARN Package 및 SafetyReportType 정책은 확보. null 허용 계약·사용자 응답 provenance와 fixture 정규화가 남았다. |
| `evidence` 번호판 재판독 | `PASS_WITH_CHANGE_REQUEST` | immutable EvidenceRecord chain은 맞고 RequirementReport supersede 생략도 허용된다. 후보 재선택 없는 `selection_rev` 증가만 수정이 필요하다. |
| Report Video / post-stamp | `REQUEST_CHANGES` | happy는 시간 순서가 역전되고, u001은 필요한 post-stamp와 export chain이 없다. |
| CaseView Consumer 계약 | `REQUEST_CHANGES` | 신규 필수 필드가 10개 candidate snapshot 및 6개 evidence snapshot에 백필되지 않았다. |
| 보안 | `NO_NEW_FINDING` | 비밀정보·인증·외부 전송·의존성 변경이 없다. 안전신문고의 비공개 machine code는 추측하지 않고 대신고 내부 code와 공개 label을 분리했다. |
| 성능 | `NOT_APPLICABLE` | fixture·계약 문서 변경이며 새 실행 코드가 없다. build 성능 수치는 구현 성능 증거가 아니다. |

---

## 2. GitHub 이슈 제출용 요약

아래 A/B는 공지의 3차 검수 양식에 맞춘 복사본이며 GitHub 이슈 #33에 등록했다.

이슈 제목: **`[mock] evidence/common-runtime 3차 검수`**

## A. 미결 질문 답변

### A-1. STALE/실패 attempt의 `UsageRecord` 발행 규칙

**답: 실행 상태가 아니라 실제 capability/provider 호출 발생 여부를 기준으로 발행한다. 실패·STALE이라고 UsageRecord를 버리지는 않지만, 모든 attempt에 인위적인 0원 row를 강제하지도 않는다.**

- 실제 외부 provider 또는 측정 대상 로컬 capability 호출이 시작됐다면 성공 여부와 무관하게 `UsageRecord`를 남긴다.
- 실패로 token·처리시간·latency를 끝까지 측정하지 못한 필드는 `null`로 보존한다. 관측된 비용이 0원이면 `amount="0.00"` row도 유효하다.
- worker가 capability 호출 전에 STALE/FAILED가 됐다면 `JobExecution`이 attempt 존재를 이미 기록하므로 `usage_refs=[]`가 맞다. “attempt가 있었다”를 증명하려고 UsageRecord를 만들어서는 안 된다.
- 따라서 `usage_x001_plate_a1`은 `ocr-local` 호출이 실제 시작된 뒤 worker가 소멸했다는 시나리오 근거를 명시할 때만 유지할 수 있다. 그렇지 않으면 삭제하고 `exec_x001_plate_a1.usage_refs=[]`로 되돌려야 한다.
- 이 규칙을 `contract-usage-record.md`의 생성 조건과 실패/STALE 예시에 정식 등재하고 validator는 `FAILED/STALE → 반드시 1건`이 아니라 `usage_ref가 있으면 실제 invocation row와 정합`을 검사해야 한다.

### A-2. `progress[].state="중단"`을 위한 `JobExecution.status`

**답: `CANCELLED`류 status 추가에 동의한다. 현재 “제품 요구가 없다”는 기존 기각 근거는 `core-user-flow.md` §3-2·§7의 명시적 분석 중단 UX와 충돌한다.**

다만 닫힌 enum을 늘리는 것만으로는 부족하고 다음 계약을 함께 정해야 한다.

- 의미: 사용자 요청으로 실행을 의도적으로 종료한 terminal state. `FAILED`·`STALE`과 구분한다.
- 최소 전이: `QUEUED → CANCELLED`, `RUNNING → CANCELLED`.
- `ended_at`: 취소 확인 시각을 기록한다. `failure_kind`는 `null`이다.
- 부분 결과: 제품은 중단 시 이미 찾은 후보를 보존하므로, `status!=SUCCEEDED이면 produced를 유효 결과로 취급하지 않는다`는 현 불변조건의 예외 또는 별도 partial-result 연결 규칙이 필요하다.
- 재개: `이어서 찾기`가 같은 JobRecord의 새 attempt인지 새 JobRecord인지 `case`와 함께 확정해야 한다. 사용자가 조건을 바꿨다면 새 JobRecord라는 기존 원칙은 유지한다.
- Consumer: CaseView `progress[].state`에도 대응값을 추가하고 web/eval Consumer Review와 계약 버전 변경을 함께 진행한다.

### A-3. `CorrectionRecord` Consumer Review

**답: evidence Consumer Review를 완료했다. append-only·`selection_rev` context·`correction_record` ContractRef 방향은 수용하지만 현재 Draft는 `REQUEST_CHANGES`이며, v1.1 수용 조건을 `docs/modules/evidence/contracts/correction-record-consumer-review-2026-09-10.md`에 확정했다.**

필수 보완:

1. `target_field`를 CaseView 표시명이나 자유 문자열이 아니라 evidence semantic path로 제한한다. 최소 `event.visual_event_type`, `event.safety_report_type`, `event.violation_expression`, `occurred_at`, `vehicle_number`, `location.*`, candidate/span 계열을 서로 구분해야 한다.
2. 동일 case·동일 target의 다중 correction은 append-only `supersedes_ref` chain으로 연결하고 chain head를 현재 correction으로 본다. 단순 최신 timestamp만으로 판정하지 않는다.
3. target별 `previous_value`/`new_value` 검증 규칙을 둔다. 현재의 무제한 `any`만으로는 잘못된 유형이 Evidence provenance로 들어오는 것을 막지 못한다.
4. 입력 검증에 실패한 correction은 생성하지 않는다. 유효한 correction이 기록된 뒤 downstream evidence 재조립/Job이 실패한 경우에는 correction을 삭제하지 않는다.
5. `selection_rev`는 “수정 횟수”가 아니다. 같은 candidate context에서 값만 고쳤다면 유지될 수 있으며, 후보 선택이 바뀌었을 때 증가하는 case 규칙과 맞춘다.
6. `다른 상황`은 `SITUATION_CHANGE`로 기록한다. 단순 사용자-unsure 응답은 correction이 아니라 workflow state로 유지한다.

case Owner가 위 여섯 조건을 반영하면 evidence가 정책 선택을 다시 여는 Consumer Review는 필요 없고, 문서·schema 정합만 확인하면 된다.

### A-4. SafetyReportType mapping registry와 신고문 template

**답: 복원된 evidence 원본 조사 PDF를 다시 확인해 `docs/modules/evidence/decisions/safety-report-policy-v1.md`로 완료했다. 현 fixture의 `UNSAFE_*`만 canonical 값이 아니며 새 registry로 교체해야 한다.**

- 내부 값 공간은 `TRAFFIC_VIOLATION` / `MOTORCYCLE_VIOLATION`, 사용자 label은 `교통위반(고속도로 포함)` / `이륜차 위반`으로 분리한다.
- `SIGNAL`·`CENTER_LINE_CROSSING`·`SOLID_LINE_LANE_CHANGE`는 전자, `MOTORCYCLE_HELMET_NON_USE`는 후자로 매핑한다.
- specific template은 PDF의 공통 신고내용 템플릿과 유형별 위반행위 표현 4개를 사용한다.
- generic template은 확인된 차량·시각·장소만 사용하고 구체 유형 확인이 어렵다는 사실과 영상 확인 요청을 담는다.
- 안전신문고의 공개되지 않은 machine code는 추측하지 않는다. 위 영문 code는 대신고 내부 code다.
- v3의 `UNSAFE_*`, `안전운전 불이행`, `tmpl/safety-report-v1`을 새 registry와 `tmpl/safety-report-specific-v1` / `tmpl/safety-report-generic-v1` 기준으로 정규화한다.

### A-5. `plate_reread_001` immutable supersede 패턴

**답: `ev_p001 → ev_p001_v2`의 새 record 생성과 `supersedes_ref` 연결 자체는 `correction_rerun_001` 패턴과 일치한다. 다만 전체 revision 패턴은 아직 완전히 일치하지 않는다.**

- PASS: 기존 `ev_p001`을 mutate하지 않고 새 `ev_p001_v2`를 만들었다.
- PASS: 사건 유형·시각은 유지하고 새 PlateReadout만 `vehicle_number`와 provenance에 반영했다.
- 확인 필요: 후보 재선택이 없는데 `selection_rev`가 1→2로 증가했다. evidence revision과 selection revision을 같은 값처럼 올리면 안 된다.
- 수용: `RequirementReport.supersedes_ref`는 optional이고 새 report의 basis가 새 EvidenceRecord를 가리키므로 생략할 수 있다. 이 부분은 별도 결정이나 수정 요구가 아니다.

### A-6. eval 3차 검수 이슈 #30 B-1 — 비용 집계 키와 STALE `run_ref`

**답: `case_id`와 `run_ref`는 하나를 폐기할 경쟁 키가 아니라 집계 범위가 다르다. 사건/source-video 단위 비용은 `case_id`, 특정 logical Run 귀속은 `run_ref`를 정본으로 사용한다.**

- `cost_per_source_video_hour`, 사건 총비용, 사건 예산 소진처럼 여러 Run·재시도·Run 없는 직접 작업을 합쳐야 하는 지표는 `UsageRecord.case_id=<case_id>`를 스캔한다.
- `AnalysisRun.usage_summary`, `ReadoutRun.usage_refs`, 특정 Run 상세 audit처럼 한 logical Run에 속한 호출만 볼 때는 `UsageRecord.run_ref={kind, ref}`를 스캔한다.
- 따라서 `contract-analysis-run-candidate-event.md`의 “상세 usage audit·비용 분모 집계를 `run_ref`로 계산” 문구는 **특정 Run audit**과 **사건/source-video 비용 지표**를 분리해 수정해야 한다.
- STALE attempt를 비용에서 보존하려고 실패한 `ReadoutRun`을 인위적으로 생성하지 않는다. `JobExecution`이 실행 attempt를 이미 소유하고, 실제 호출이 시작됐지만 worker 소멸로 Run artifact가 나오지 않은 경우가 존재하기 때문이다.
- `run_ref=null`은 현재 “Run 개념이 없는 직접 호출”과 “Run을 만들려 했으나 artifact가 생성되지 않음”을 동시에 뜻해 계약 위반이다. `UsageRecord` 다음 버전에 `run_ref_reason: DIRECT_NO_RUN | RUN_NOT_PRODUCED | null` 같은 구분값을 추가하고 다음 불변조건을 둔다.
  - `run_ref != null`이면 `run_ref_reason=null`
  - `run_ref == null`이면 `run_ref_reason`은 반드시 `DIRECT_NO_RUN` 또는 `RUN_NOT_PRODUCED`
  - 실제 capability 호출이 시작되지 않았다면 A-1에 따라 UsageRecord 자체를 만들지 않는다.
- 현재 fixture의 금액·`case_id`·execution 연결은 유지할 수 있지만, 새 구분 필드를 계약에 채택하면 `usage_x001_plate_a1=RUN_NOT_PRODUCED`, `usage_h001_report_video=DIRECT_NO_RUN` 백필은 필요하다. 따라서 “어느 방향이든 fixture 수정 불필요”는 스키마 변경을 전제로 하면 성립하지 않는다.

## B. 신규/변경 fixture 재검수

- [x] `scenario_happy_001`: REPORT_VIDEO_EXPORT JobExecution·UsageRecord·operation namespace가 추가된 것을 확인했다.
- [ ] **수정 필요:** happy의 FINAL_PACKAGE Requirement가 `18:25:00`에 Report Video 존재를 PASS로 판정하지만 export execution은 `18:25:35`에 끝난다. JobRecord도 이미 Package가 보이는 `case_rev:4`에 발주되고 fingerprint가 미래 `pkg_h001`을 포함한다.
- [x] `scenario_unknown_abstain_partial_001`: blocking dead-end가 EVIDENCE/FINAL_PACKAGE WARN + ReportPackage + READY로 바뀐 방향을 확인했다.
- [ ] **수정 필요:** u001은 `post_stamp.needed=true`인데 `tr_u001_trim_v1`만 가리키며 post-stamp 적용·notice·export execution 없이 Package를 만든다.
- [ ] **수정 필요:** u001의 사용자-unsure 응답은 CaseView에만 있고 `ev_u001` provenance에는 없다. 제한적 null 허용 조건을 EvidenceRecord 단독으로 감사할 수 없다.
- [x] `scenario_plate_reread_001`: 재판독 성공값 `17나2867`, 새 ReadoutRun/UsageRecord, immutable EvidenceRecord, EVIDENCE PASS를 확인했다.
- [ ] **수정 필요:** 후보 재선택이 없으므로 `selection_rev`은 기존 값을 유지한다. RequirementReport supersede 생략은 계약상 허용된다.
- [x] `scenario_infra_failure_001`: attempt 1 STALE·attempt 2 FAILED, overlay UNKNOWN과 새 INFO notice, operation namespace 변경을 확인했다.
- [ ] **수정 필요:** STALE attempt마다 0원 UsageRecord를 의무화한 case decision 문구를 A-1의 actual-invocation 규칙으로 좁혀야 한다.
- [ ] **수정 필요 · 이슈 #30 B-1:** 사건/source-video 비용은 `case_id`, 특정 Run audit은 `run_ref`를 사용하도록 두 계약의 문구를 정렬하고, `run_ref=null`인 두 종류의 row를 구분하는 사유값을 추가해야 한다.
- [x] search `usage_summary.total_cost` 6개 시나리오가 KRW 원장 값과 정합하는 것을 확인했다.
- [x] timeline stale 3필드가 candidate가 존재하는 12개 CaseView snapshot에 모두 들어간 것을 확인했다.
- [ ] **수정 필요:** `situation_confirmation`을 `NOT_ASKED | CONFIRMED | CORRECTED | USER_UNSURE`로 정규화하고 required/conditional 규칙을 정한 뒤 기존 snapshot을 백필한다.
- [ ] **수정 필요:** `case_type_display`/`violation_display.info_state`·`source_label_key`는 evidence가 있는 8개 snapshot 중 u001의 2개에만 있고 6개에는 없다.
- [ ] **문서 수정:** `CONTRACT_CONFLICTS.md` 항목 5와 `generic-warn-package-and-situation-response.md`는 신규 CaseView 필드가 계약 미등재라고 하지만 현재 계약 schema/필드표에는 이미 등재돼 있다.

### 담당자 후속 — case 통합 주도

case/mock Owner는 다음을 같은 통합 PR에서 직접 반영한다.

- happy Report Video 순서·fingerprint, u001 post-stamp/export provenance, CaseView 필드 backfill, SafetyReportType/template 정규화, plate reread `selection_rev`, 이슈 #31의 새 crop id, conflict/decision/validator/template 문서 정합
- `CorrectionRecord v1.1`: A-3의 6조건
- `EvidenceRecord v1.3`: `CONFIRMED | CORRECTED | USER_UNSURE`, null은 `USER_UNSURE`에만 허용, 응답값·시각·candidate ref snapshot
- `UsageRecord v1.2`: actual invocation 발행, 사건 비용=`case_id`, Run audit=`run_ref`, `run_ref_reason`
- `JobExecution v1.1`과 CaseView: `CANCELLED`, 부분 결과 보존, 재개 identity 규칙
- AnalysisRun Consumer 문구: Run 상세 audit과 사건/source-video 비용 분모 분리

원 계약 Owner와 Consumer는 구현을 나눠 맡기보다 case PR reviewer로 참여한다. recording에는 새 결정을 요청하지 않는다.

---

## 3. 상세 검수

### 3.1 happy REPORT_VIDEO_EXPORT — 구조는 추가됐지만 시간 순서가 역전됨

현재 값:

```text
18:25:00  req_h001_final evaluated_at, Report Video exists = PASS
18:25:00  job_h001_report_video requested_at (case_rev=4)
18:25:05  exec_h001_report_video started_at
18:25:35  exec_h001_report_video ended_at=SUCCEEDED
18:26:00  pkg_h001 created_at
```

계약의 정상 흐름은 다음이어야 한다.

```text
EVIDENCE Requirement PASS/WARN
  → REPORT_VIDEO_EXPORT JobRecord
  → JobExecution SUCCEEDED + DerivedAsset AVAILABLE
  → FINAL_PACKAGE Requirement PASS/WARN
  → ReportPackage
  → CaseView stage=READY
```

현재 `req_h001_final`은 asset 생성 35초 전에 `package.asset.report_video.exists=PASS`를 낸다. 또한 JobRecord의 `input_fingerprint="...pkg_h001"`는 아직 생성되지 않은 Package를 export 입력처럼 사용하고, `case_rev=4`는 이미 `case_rev=3` READY 이후다. 이는 실행 provenance를 추가했지만 기존 Package를 앞에 둔 채 chain을 끼워 넣은 상태다.

### 3.2 u001 generic WARN — dead-end 해소는 맞지만 post-stamp/정책 provenance가 빠짐

수용하는 부분:

- 사용자 응답 상태를 CaseView에 표현하려는 방향은 맞다. 다만 `UNKNOWN` 하나로 미질문과 사용자-unsure를 겸하지 않고 `NOT_ASKED`와 `USER_UNSURE`로 분리해야 한다.
- `case_type_display=INFO_UNKNOWN`, `violation_display=INFO_AI_ESTIMATED`를 분리했다.
- EVIDENCE/FINAL_PACKAGE `WARN`, non-blocking notice, Package capabilities 유지가 제품 흐름과 맞는다.
- generic 문구는 신호위반·중앙선 침범 등 구체 위반을 단정하지 않는다.

남은 문제:

- `TimeResolution.post_stamp.needed=true`, `requires_user_notice=true`인데 Report Video의 `transform_ref`는 `tr_u001_trim_v1`뿐이다.
- `evidence.time_post_stamp_required` notice나 동등한 사용자 고지가 없다.
- u001 Report Video와 Plate Image는 새로 생겼지만 대응 JobRecord/JobExecution/UsageRecord가 없다.
- `ev_u001.event.visual_event_type.value=null`의 source는 `evidence.category_mapping → ve_u001`일 뿐 사용자 `UNKNOWN` 응답을 가리키지 않는다.
- `safety_report_type.needs_review=false`인데 CaseView package는 같은 필드를 `unconfirmed_fields`에 넣는다. 추천값과 확정값의 상태가 레이어별로 다르다.

따라서 u001은 제품 흐름 데모로는 개선됐지만 evidence authoritative record와 export provenance까지 완결된 canonical seed는 아니다.

### 3.3 CaseView 신규 필드 — schema와 fixture가 서로 다름

`contract-job-record-case-view.md` 현재 schema/필드표 기준:

- `candidates[].situation_confirmation`: 필수 `Y`
- `case_type_display.info_state/source_label_key`: schema에 존재
- `violation_display.info_state/source_label_key`: schema에 존재
- `evidence.*_display.info_state/source_label_key`: 필드표는 포괄형 `Y`

실제 7개 scenario 전체를 파싱한 결과:

| 항목 | 전체 대상 | 필드 존재 | 누락 |
| --- | ---: | ---: | ---: |
| candidate `situation_confirmation` | 12 snapshot | 2 | 10 |
| evidence `case_type_display.info_state` | 8 snapshot | 2 | 6 |
| evidence `violation_display.info_state` | 8 snapshot | 2 | 6 |
| candidate timeline/stale 3필드 | 12 snapshot | 12 | 0 |
| package `unconfirmed_fields` | 3 snapshot | 3 | 0 |

선택지는 둘 중 하나다.

1. 이 필드들을 모든 관련 projection의 필수 필드로 유지하고 기존 fixture와 계약 예시까지 백필한다.
2. 실제 의도가 u001 같은 상태에서만 제공하는 조건부 필드라면 schema/필드표에 optional 조건을 명시한다.

필수 필드로 유지한다면 기존 `case-view/v1.2` payload가 새 요구를 충족하지 못하므로 계약 버전도 함께 올려야 한다. 현재처럼 계약은 필수이고 fixture는 조건부인 상태를 validator PASS로 승인하면 Consumer 구현이 서로 달라진다.

### 3.4 plate reread — EvidenceRecord immutable chain은 양호

`ev_p001`과 `ev_p001_v2` 비교 결과:

- 기존 record 보존: PASS
- `supersedes_ref=ev_p001`: PASS
- 새 vehicle value `17나2867`: PASS
- 새 source/support/provenance `readout_p001_plate_reread`: PASS
- visual event/time 유지: PASS
- 새 basis EVIDENCE Requirement `UNKNOWN→PASS`: PASS
- Package 부재로 `stage=EVIDENCE_REVIEW` 유지: PASS

단, 후보 재선택이 없는데 `selection_rev`가 증가한 것은 수정해야 한다. `selection_rev`는 record revision counter가 아니다. RequirementReport는 basis가 새 EvidenceRecord를 가리키므로 optional `supersedes_ref`를 생략해도 된다.

### 3.5 common/runtime UsageRecord — namespace 정리는 PASS, 생성·집계 조건은 보완 필요

- `PLATE_OCR → READOUT_PLATE`, `OVERLAY_OCR → READOUT_OVERLAY_TIME`: PASS
- report export `RECORDING_REPORT_VIDEO_EXPORT`: 모듈 접두어 규칙과 일치
- authoritative KRW 합계: correction 630, empty 434, happy 938, infra 0, plate reread 728, relative rebase 84, u001 756
- 모든 AnalysisScope 예산 1,000 KRW 이하: PASS
- failed provider call의 `processed_duration_sec=null`: 확인하지 못한 값을 만들지 않는 원칙과 일치

다만 `UsageRecord`는 호출 원장이지 attempt 존재 원장이 아니다. 실패/STALE 비용 누락을 막는 목적은 맞지만, capability 호출 전 실패에도 0원 row를 강제하면 측정하지 않은 호출을 생성하게 된다. A-1처럼 “실제 invocation이 시작됐다면 상태와 무관하게 기록”으로 좁혀야 한다.

이슈 #30 B-1은 별도의 실질 충돌도 드러냈다. `usage_x001_plate_a1`은 `case_id=case_x001`이지만 `run_ref=null`이므로 사건 비용을 `run_ref`로만 세면 STALE 호출이 빠진다. 반대로 모든 비용을 `case_id`로만 보면 특정 Run의 immutable usage snapshot을 검증할 수 없다. 따라서 집계 범위를 사건/Run으로 나누고, null의 이유는 `DIRECT_NO_RUN`과 `RUN_NOT_PRODUCED`로 분리해야 한다.

---

## 4. Findings

### Required-1. happy의 FINAL_PACKAGE 판정이 Report Video 생성보다 35초 빠르다

**근거**

- `req_h001_final.evaluated_at=18:25:00`
- `exec_h001_report_video.ended_at=18:25:35`
- Requirement check는 이미 `package.asset.report_video.exists=PASS`
- JobRecord는 `case_rev=4`, fingerprint에는 미래 `pkg_h001`이 들어간다.

**영향**

- runtime 구현이 fixture를 따르면 존재하지 않는 asset을 PASS로 판정한다.
- Package가 export 입력인지 export 결과 소비자인지 순환 의존이 생긴다.
- `case_rev`가 발주 시점 revision이라는 계약 의미가 깨진다.

**요구 변경**

- export JobRecord를 EVIDENCE Requirement 이후·FINAL_PACKAGE 검사 이전 revision에 둔다.
- fingerprint는 Evidence/TimeResolution/IncidentClip/export policy 등 실제 선행 입력으로 구성하고 Package ref를 제거한다.
- export 성공 뒤 FINAL_PACKAGE Requirement를 평가하고 그 다음 Package/READY CaseView를 만든다.

### Required-2. u001은 필수 post-stamp 없이 FINAL_PACKAGE WARN을 통과한다

**근거**

- `tres_u001.post_stamp.needed=true`, `requires_user_notice=true`
- `da_u001_report_video.transform_ref=tr_u001_trim_v1`
- FINAL_PACKAGE checks에 post-stamp 적용 검사가 없다.
- post-stamp notice와 REPORT_VIDEO_EXPORT 실행 provenance가 없다.

**영향**

- 신고용 영상이 TimeResolution 정책을 적용하지 않은 채 Package에 들어간다.
- 사용자는 원본 화면 시각이 없고 사후 각인이 필요하다는 사실을 충분히 추적할 수 없다.

**요구 변경**

- post-stamp transform/policy provenance와 사용자 notice를 추가한다.
- export 완료 뒤 post-stamp 적용 여부를 FINAL_PACKAGE Requirement에서 검사한다.
- u001에도 Report Video JobRecord→JobExecution→UsageRecord chain을 추가하거나, 최소한 Job 없는 DerivedAsset이 허용되는 이유와 생성 provenance를 별도 계약으로 제공한다.

### Required-3. 신규 CaseView 필드가 기존 fixture에 백필되지 않았다

**근거**

- `situation_confirmation`은 12개 candidate snapshot 중 10개 누락
- `case_type_display`/`violation_display` 신규 상태 필드는 8개 evidence snapshot 중 각각 6개 누락
- 계약 정상/실패 예시도 신규 필드와 dotted-lowercase notice 규칙을 반영하지 않았다.
- `CONTRACT_CONFLICTS.md`는 반대로 이 필드들이 계약 미등재라고 적어 현재 본문과 충돌한다.

**영향**

- web Consumer가 필드를 required로 구현할지 optional로 구현할지 결정할 수 없다.
- validator PASS가 실제 계약 충족을 보장하지 않는다.

**요구 변경**

- required/conditional 중 하나를 계약에서 명확히 선택하고 fixture·예시·conflict index를 같은 결정으로 정렬한다.
- required 필드 추가라면 `case-view/v1.2`를 그대로 재사용하지 말고 새 계약 버전과 Consumer 전환 규칙을 제공한다.
- validator에 required field coverage를 추가한다.

### Required-4. u001 EvidenceRecord가 제한적 null 허용의 원인을 증명하지 못한다

**근거**

- `ev_u001`은 `evidence-record/v1.2`를 사용하면서 `visual_event_type.value=null`이다.
- EvidenceRecord schema는 `EvidenceValue<VisualEventType>`을 요구하고, null 허용의 정확한 사용자 상태를 명문화하지 않았다.
- 사용자 응답 `UNKNOWN`은 CaseView candidate projection에만 있고 `ev_u001.basis/provenance`에는 stable ref 또는 snapshot이 없다.
- source ref는 `ve_u001`이라 Fine `UNCERTAIN`만 증명한다.

**영향**

- evidence Consumer/audit가 “사용자가 잘 모르겠다고 답함”과 “아직 묻지 않음/Fine 실패”을 Record만으로 구분할 수 없다.
- null 허용 범위가 다른 시나리오로 조용히 확장될 수 있다.

**요구 변경**

- EvidenceRecord 새 버전에 제한 조건과 machine-readable user response provenance를 추가한다.
- case→evidence 호출 입력에서 끝내지 말고 immutable EvidenceRecord가 허용 근거를 snapshot 또는 stable ref로 보존하게 한다.

### Required-5. UsageRecord를 attempt marker로 사용한 규칙을 좁혀야 한다

**근거**

- case decision은 “row 자체로 attempt 존재와 원장 부재를 구분”한다고 설명한다.
- 그러나 attempt identity/lifecycle의 authoritative record는 이미 JobExecution이다.
- UsageRecord 계약은 실제 호출·처리량·latency·pricing/cost 원장이다.

**영향**

- 호출 전 실패에도 가짜 0원 provider row가 생길 수 있다.
- 비용 0과 호출 없음이 다시 구분되지 않는다.

**요구 변경**

- A-1의 actual-invocation 조건으로 계약과 mock decision 문구를 갱신한다.
- `usage_x001_plate_a1` 유지 시 provider invocation이 시작됐다는 시나리오 사실을 명시한다.

### Required-6. SafetyReportType과 template artifact는 확보됐고 fixture 정규화가 남았다

**근거**

- v3 확정 경로는 `UNSAFE_LANE_CHANGE`/`UNSAFE_SIGNAL_VIOLATION`, u001은 한국어 `교통위반(고속도로 포함)`을 같은 `safety_report_type` 필드에 쓴다.
- 원본 PDF 재검토로 versioned mapping/template artifact는 `safety-report-policy-v1.md`에 확보됐다.
- u001 `safety_report_type.needs_review=false`와 Package `unconfirmed_fields=["safety_report_type", ...]`가 서로 다른 상태를 말한다.

**영향**

- 새 artifact와 fixture가 다르므로 구현 seed가 여전히 옛 placeholder를 학습할 수 있다.
- case/web이 내부 code와 사용자 label을 혼용할 위험이 있다.

**요구 변경**

- 전 evidence/package/CaseView fixture를 `safety-report-policy/v1`과 두 template ref 기준으로 교체한다.
- 사용자-unsure의 `needs_review`와 `unconfirmed_fields`를 모두 검토 필요 상태로 맞춘다.

### Required-7. 비용 집계 범위와 `run_ref=null` 의미를 분리해야 한다

**근거**

- `contract-usage-record.md` §9-2는 사건 단위 원가를 `case_id`로 직접 집계하도록 한다.
- `contract-analysis-run-candidate-event.md` Consumer — eval은 비용 분모까지 `run_ref`로 스캔하도록 적었다.
- `usage_x001_plate_a1`은 실제 STALE 호출 row이지만 `run_ref=null`, `case_id=case_x001`이다.
- 같은 null을 쓰는 `usage_h001_report_video`는 실제로 Run 개념이 없는 직접 export 호출이다.

**영향**

- `run_ref`만 쓰면 STALE 호출이 사건 비용에서 빠지고, `case_id`만 쓰면 특정 Run 귀속 검증 범위가 흐려진다.
- 현재 null 하나가 “Run 없음”과 “Run 미생성”을 동시에 뜻해 소비자가 row 의미를 안정적으로 분기할 수 없다.

**요구 변경**

- 사건/source-video 비용 지표의 정본 집계 키를 `case_id`, 특정 Run 상세 audit의 정본을 `run_ref`로 명시한다.
- STALE 때문에 synthetic failed Run을 만들지 말고 `run_ref_reason` 또는 동등한 discriminant를 UsageRecord 새 버전에 추가한다.
- 두 계약, schema/example, validator, null row fixture를 같은 변경으로 정렬한다.

### Should-1. `progress[].state=PARTIAL`과 CANCELLED 경로 fixture가 필요함

PARTIAL은 계약에 추가됐지만 이를 보여주는 fixture가 0건이다. CANCELLED를 채택하면 `RUNNING → CANCELLED`, 부분 candidate 보존, `이어서 찾기`까지 한 시나리오로 검증해야 한다.

### Nit-1. `03_mock_artifact_templates.md`에 trailing whitespace 1건

`git diff --check 7dcfce5..HEAD`가 `03_mock_artifact_templates.md:2613`의 trailing whitespace를 보고한다. 의미 오류는 아니지만 커밋 위생상 정리할 수 있다.

---

## 5. 2차 검수 항목 회귀 확인

| 2차 검수 핵심 항목 | 3차 상태 | 판단 |
| --- | --- | --- |
| u001 blocking dead-end | generic EVIDENCE/FINAL_PACKAGE WARN + Package + READY 추가 | `RESOLVED_WITH_CONTRACT_GAP` |
| `INFO_AI_ESTIMATED` fixture 부재 | u001 violation display에 추가 | `RESOLVED` |
| CaseView 사용자 응답 상태 부재 | u001에 임시 `situation_confirmation=UNKNOWN` 추가 | `PARTIAL` — `NOT_ASKED`/`USER_UNSURE` 분리와 다른 snapshot 백필/optional 규칙 필요 |
| WARN Package capabilities | 다운로드·복사·이동 유지 | `RESOLVED` |
| REPORT_VIDEO_EXPORT chain 부재 | happy 성공 chain 추가 | `REQUEST_CHANGES` — 시간/revision 순서 역전 |
| 실제 SafetyReportType/rule/template 부재 | 원본 PDF 복원 후 `safety-report-policy/v1`로 결정 완료 | `RESOLVED_POLICY` — fixture 교체 필요 |
| EvidenceRecord nullable 계약 | fixture에서 null 사용 | `OPEN` — v1.2 계약/provenance 미완료 |
| STALE/FAILED usage 비용 누락 | attempt 1에 0원 row 추가 | `PARTIAL` — 실제 호출 조건 명문화 필요 |
| eval 3차 B-1 비용 집계 키 | `case_id`와 `run_ref` 문구 충돌 확인 | `DECIDED_WITH_CONTRACT_CHANGE` — 사건 비용=`case_id`, Run audit=`run_ref`, null 사유 구분 필요 |
| plate reread 완료 상태 부재 | 성공 Readout/Evidence/Requirement/CaseView 추가 | `RESOLVED_WITH_REVIEW_NOTE` |
| Report Video export 실패 경로 | 추가 없음 | `OPEN` |
| Requirement BLOCK / Readout PARTIAL / Span FAILED | 추가 없음 | `OPEN_EXISTING` |
| reverse-geocode 기반 address | artifact 없음 | `OPEN_EXTERNAL_ARTIFACT` |

---

## 6. 재검수 통과 조건

- [ ] happy Report Video export 발주·실행·FINAL_PACKAGE 검사·Package 생성 시간을 정상 순서로 재배치한다.
- [ ] happy export JobRecord의 `case_rev`와 fingerprint에서 미래 Package 의존을 제거한다.
- [ ] u001 `post_stamp.needed=true`를 실제 Report Video transform/provenance/notice/Requirement check에 반영한다.
- [ ] `situation_confirmation`과 event display 신규 상태 필드의 required/conditional 규칙을 정하고 fixture를 정렬한다.
- [ ] `CONTRACT_CONFLICTS.md`와 case decision 문서의 “계약 미등재” 문구를 현재 계약 본문과 맞춘다.
- [ ] `visual_event_type=null`의 사용자 응답 provenance와 제한 불변조건을 EvidenceRecord 새 버전에 명시한다.
- [ ] STALE/FAILED UsageRecord 발행 규칙을 actual invocation 기준으로 계약화한다.
- [ ] 사건/source-video 비용=`case_id`, 특정 Run audit=`run_ref`로 두 계약의 집계 문구를 정렬한다.
- [ ] `run_ref=null`을 `DIRECT_NO_RUN`과 `RUN_NOT_PRODUCED`로 구분하는 필드·불변조건·fixture를 추가한다.
- [x] `CANCELLED` 추가와 기존 부분 결과 보존·재개 identity 원칙을 김준영 Owner 결정으로 확정했다. case가 계약 개정 초안을 만들고 web/eval은 PR에서 확인한다.
- [x] `CorrectionRecord` evidence Consumer Review와 v1.1 수용 조건을 별도 문서로 확정했다. case가 계약 본문에 반영해야 한다.
- [x] SafetyReportType mapping registry와 generic/specific template artifact를 원본 조사 PDF 근거로 작성했다. mock fixture 교체는 남았다.
- [ ] plate reread는 후보 재선택이 없으므로 `selection_rev`을 유지한다. RequirementReport supersede 생략은 허용한다.
- [ ] `python data/mock/validate_mock_pack.py` 통과.
- [ ] cp949 환경의 동일 validator 통과.
- [ ] `python scripts/check_contract_fixtures.py` 통과.
- [ ] `python scripts/check_boundaries.py` 통과.
- [ ] `npm run build` 통과.
- [ ] `git diff --check` 통과.

---

## 7. 검증 실행 기록

| 명령/검사 | 결과 | 해석 범위 |
| --- | --- | --- |
| `git status --short --branch` | `develop...origin/develop`, 기존 untracked 06·07 보고서만 존재 | 원격 동기화 및 사용자 파일 보존 확인 |
| `git diff --stat 7dcfce5..HEAD` | 38 files, +2,205 / -198 | Mock Pack v3 통합 범위 확인 |
| `python data/mock/validate_mock_pack.py` | PASS, 46 JSON / 7 scenarios / 오류 0 | Mock 구조·참조·구현된 validator 불변조건 |
| cp949 환경의 동일 validator | PASS, exit 0 | Windows 출력 인코딩 회귀 없음 |
| `python scripts/check_contract_fixtures.py` | 문서 60 / JSON 26 / 의미 104 PASS | 별도 Contract fixture 정합성; Mock Pack 전체 필수 필드 검사는 아님 |
| `python scripts/check_boundaries.py` | PASS, 0 violations | 현재 tracked 골격의 경계 문자열 검사 |
| `npm run build` | PASS, Vite 1,603 modules transformed | prototype build; evidence/common 구현 E2E 증거 아님 |
| `git diff --check 7dcfce5..HEAD` | FAIL, trailing whitespace 1건 | 문서 whitespace hygiene |
| candidate 신규 필드 전수 파싱 | timeline/stale 12/12, situation 2/12 | CaseView 신규 필드 coverage |
| evidence display 신규 필드 전수 파싱 | case/violation info state 각 2/8 | event display backfill gap |
| Report Video asset↔Job 전수 파싱 | happy 1/1, u001 0/1 | export provenance coverage |
| 7개 시나리오 UsageRecord 합계 | 0~938 KRW, 예산 있는 시나리오 모두 1,000 KRW 이하 | authoritative ledger 기준 예산 sanity check |
| `src/daesingo/{evidence,common}` tracked file 확인 | README만 존재 | 이번 판정은 fixture/contract 검수이며 구현 통합/E2E 판정이 아님 |
| evidence 원본 조사 PDF 3개 | 19 + 19 + 24 = 62쪽 전체 텍스트 확인, 핵심 표·예시 17쪽 렌더링 대조 | 축약 memo에서 빠진 4→2 매핑, 유형별 표현, 고정 template, 사후각인 조건, correction provenance 복원 |
| GitHub 이슈 #30 본문 및 현재 댓글 | OPEN, 댓글 0, B-1 common/runtime·B-2 readout/web | B-1 계약 충돌 추가 검수; B-2는 신유민 담당으로 범위 분리 |
| GitHub 이슈 #33 | `[mock] evidence/common-runtime 3차 검수` 등록 | 공지 양식 A/B와 #30 B-1 답변 공유 |

자동 검증 PASS는 위 Required finding을 반박하지 않는다. 현재 validator는 교차 파일 참조와 일부 enum/invariant를 검사하지만, timestamp ordering, post-stamp 적용, CaseView 신규 필드의 전 snapshot coverage, 사용자 응답 provenance, fixture가 versioned policy artifact와 일치하는지는 검사하지 않는다.

---

## 8. 결론

Mock Pack v3는 2차의 핵심 dead-end를 실제 진행 가능한 WARN Package로 바꾸고, 재판독이 대기에서 성공까지 가는 상태를 완결했다. 이 두 변화는 명확한 개선이다. 또한 operation namespace, KRW snapshot, stale revision label, overlay UNKNOWN notice도 방향이 맞다.

하지만 canonical seed로 쓰려면 “보이는 최종 상태”뿐 아니라 그 상태가 만들어지는 선행 chain이 시간·revision·policy provenance까지 성립해야 한다. 현재 happy는 FINAL_PACKAGE 검사가 export보다 먼저이고, u001은 필요한 post-stamp와 user-response provenance 없이 Package를 만든다. 새 CaseView 필드도 계약과 fixture의 required/conditional 해석이 갈려 있다. SafetyReportType 정책과 CorrectionRecord Consumer 조건은 이번 원본 PDF 재검토로 더 이상 미결이 아니다. 추가 공지 #30 B-1은 사건 비용과 Run audit의 집계 키를 분리하고 `run_ref=null`의 두 원인을 구분하는 계약 변경으로 답을 확정했다.

따라서 3차 판정은 다음처럼 기록한다.

```text
MOCK_STRUCTURE_VALIDATED
COMMON_RUNTIME_ROUND3_CHANGES_REQUIRED
EVIDENCE_ROUND3_PARTIAL_READY
USER_UNSURE_WARN_PATH_PRESENT
REPORT_VIDEO_ORDERING_INVALID
POST_STAMP_CHAIN_REQUIRED
CASEVIEW_BACKFILL_OR_OPTIONAL_RULE_REQUIRED
SAFETY_REPORT_FIXTURE_NORMALIZATION_REQUIRED
USAGE_AGGREGATION_SCOPE_SPLIT_REQUIRED
RUN_REF_NULL_REASON_REQUIRED
CANCELLED_ACCEPTED_CONTRACT_UPDATE_REQUIRED
REQUEST_CHANGES
```
