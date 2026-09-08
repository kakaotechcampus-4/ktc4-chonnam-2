# 02. Mock Scenario Catalog

시나리오는 4개로 유지했다(「시나리오를 너무 많이 만들지 않고 시나리오당 Contract coverage를 최대화한다」는 지침에 따름). A~I 9개 유형 전부를 아래 4개 시나리오가 나눠 커버한다.

## 시나리오 목록

| Scenario ID | 커버 타입 | 관련 모듈 fixture | Case ID |
| --- | --- | --- | --- |
| `scenario_happy_001` | A (Happy Path) | recording·search·readout·evidence·case·common | `case_h001` |
| `scenario_empty_001` | B (결과 없음) | search·case·common | `case_e001` |
| `scenario_unknown_abstain_partial_001` | C·D·E·G·H·I | recording·search·readout·evidence·case·common | `case_u001` |
| `scenario_correction_rerun_001` | F·I | recording·search·readout·evidence·case·common | `case_r001` |

---

## `scenario_happy_001` — Happy Path

**목적**: 등록 → COARSE_SEARCH → 후보 선택 → PLATE_READ/OVERLAY_TIME_READ → Evidence 확정 → RequirementReport(EVIDENCE, FINAL_PACKAGE) → ReportPackage까지 전체 파이프라인을 한 번 완주하는 대표 정상 경로를 제공한다. 다른 모든 것이 깨져도 이 시나리오 하나는 각 모듈이 개발 초기에 "정상일 때 내 입력이 이런 모양이구나"를 확인하는 기준이 된다.

**시작 조건**: 전방/후방 2개 영상 파일이 정상 업로드되고(`AVAILABLE`), filename에서 시각을 파싱할 수 있다.

**예상 흐름**: `COARSE_SEARCH` → 후보 1건(`candidate_h001`, ranking_score 0.86) → 사용자가 그 후보 선택 → `PLATE_READ`/`OVERLAY_TIME_READ` 동시 발주 → 둘 다 `SUCCEEDED`, abstain 없음 → `TimeResolution.status=OK`(검증된 Overlay) → `EvidenceRecord`의 모든 필드 confirmed, `needs_review` 전부 false → `RequirementReport` 둘 다 `PASS` → `ReportPackage` 생성 → `CaseView.stage=READY`.

**기대 결과**: 모든 모듈의 fixture가 존재하고, `ReportPackage`가 실제로 생성되며, `CaseView.stage=READY`.

**검증 Contract**: 전체 14개 Final Contract 중 12개(제외: 이 시나리오는 abstain/충돌이 없어 `EvidenceNeeds.items`가 빈 배열, `RequirementReport`의 BLOCK/UNKNOWN outcome은 다른 시나리오가 담당).

---

## `scenario_empty_001` — 결과 없음

**목적**: `AnalysisRun.outcome=SUCCEEDED`이면서 `candidates=[]`인 경우가 실패가 아님을 보여준다. `search`·`case` 양쪽 모두 "빈 배열"과 "에러"를 구분해서 처리해야 함을 데이터로 증명한다.

**시작 조건**: 영상은 정상 업로드됐지만, 사용자가 지목한 시간대에 해당 사건 유형(`ILLEGAL_U_TURN`)의 후보가 실제로 없다.

**예상 흐름**: `COARSE_SEARCH` 실행이 정상 종료(`outcome=SUCCEEDED`)하지만 `candidates=[]` → `CaseView.stage=CANDIDATE_REVIEW`에 머물고 `candidates=[]` → 비차단(`blocking=false`) INFO notice로 힌트 수정/재검색 유도.

**기대 결과**: `AnalysisRun`이 실패로 기록되지 않는다. `readout`/`evidence`/`ReportPackage`는 아예 생성되지 않는다(대상 후보가 없으므로).

**검증 Contract**: `AnalysisScope`·`AnalysisRun`·`JobRecord`·`JobExecution`·`UsageRecord`·`CaseView`.

---

## `scenario_unknown_abstain_partial_001` — ABSTAIN + Partial + 시각 충돌 + UNKNOWN 판정

이 시나리오 하나에 6개 유형을 몰아넣었다(시나리오 수를 늘리지 않고 coverage를 최대화하는 지침에 따름).

**목적**:
- 번호판 판독이 대상 차량 식별 모호(`AMBIGUOUS`)와 프레임 간 불일치로 `abstained=true`가 되는 경우, 이것이 Case 전체 실패가 아님을 보여준다(D).
- 화면 시각 판독의 `ReadoutRun`이 `outcome=FAILED`(`NO_OVERLAY_PRESENT`)로 완전히 실패해 결과 객체(`OverlayTimeReadout`) 자체가 생성되지 않는 규칙을 보여준다(E — Partial: 번호판은 성공, 화면시각은 실패).
- Filename 시각과 File Metadata 시각이 3분 어긋날 때 `TimeResolution`이 임의로 승자를 정하지 않고 `conflict.exists=true`로 보존하는 것을 보여준다(H). `BASE_PLUS_OFFSET` 상대-절대 시간 계산도 함께 검증한다.
- `vehicle_number`가 EvidenceRecord에서 (null이 아니라) **필드 자체 부재**로 표현되고, `RequirementReport(EVIDENCE).overall=UNKNOWN`이 `BLOCK`과 다른 의미(판정 자체가 성립하지 않음)임을 보여준다(C·G).
- `EvidenceNeeds.items`에 `PLATE_REREAD`(optional=false)가 담기고, `case`가 이를 받아 새 `JobRecord`(`force_rerun=true`)를 자동 발주하되 이미 확정된 `occurred_at`·`visual_event_type` 값은 리셋하지 않는 것을 보여준다(I).

**시작 조건**: 영상 1개, filename time과 file metadata time이 서로 다름. 대상 차량 힌트가 약함(신호 상태가 화면에서 불확실).

**예상 흐름**: `COARSE_SEARCH` → 후보 1건(`ranking_score 0.61`, `uncertainties` 포함) → `VisualEvidence.target.association_confidence=0.58`(약함) → `PLATE_READ` 성공하지만 `abstained=true` → `OVERLAY_TIME_READ`은 `ReadoutRun.outcome=FAILED` → `evidence.assemble()`이 `EvidenceRecord`에서 `vehicle_number` 필드를 아예 비움, `occurred_at`은 `NEEDS_REVIEW`로 채움 → `EvidenceNeeds`가 `PLATE_REREAD` 요청 → `case`가 `force_rerun=true`로 새 Job 자동 발주(`QUEUED` 상태로 스냅샷) → `RequirementReport(EVIDENCE).overall=UNKNOWN`.

**기대 결과**: `ReportPackage`가 생성되지 않는다(§8.1 ready-only 규칙). `CaseView.requirements_package=null`.

**검증 Contract**: `AnalysisScope`·`AnalysisRun`·`CandidateEvent`·`VisualEvidence`·`ReadoutRun`·`PlateReadout`·`TimeResolution`·`EvidenceRecord`·`EvidenceNeeds`·`RequirementReport`·`JobRecord`·`JobExecution`·`UsageRecord`·`CaseView`.

---

## `scenario_correction_rerun_001` — 사용자 정정 + Supersede 재실행 + NOT_RUN 구분

**목적**:
- 사용자가 사건 발생시각을 명시적으로 정정했을 때 `TimeResolution`이 `USER_OVERRIDE`/`user_corrected=true`로 새 버전을 만들고 `supersedes_ref`로 이전 버전과 연결되는 것을 보여준다(F).
- 이 정정 과정에서 **이미 확정돼 있던 `vehicle_number`는 완전히 동일한 값·provenance로 유지**됨을 보여준다 — 정정이 무관한 값을 리셋하지 않는다는 원칙의 직접적 증거다(I).
- `EvidenceRecord`·`RequirementReport`가 각각 v1→v2로 supersede되는 chain도 함께 보여준다.
- `OverlayTimeReadout`을 한 번도 시도하지 않아 `readout_runs`에 overlay 항목이 아예 없는 상태 — 이는 "결과 없음(FAILED)"과 다른 **NOT_RUN**을 배열 부재로 표현한 것이다.

**시작 조건**: 번호판은 처음부터 명확하게 확정(`OBSERVED`)됐다. 발생시각은 처음엔 Filename+offset 계산값(`NEEDS_REVIEW`)뿐이었다.

**예상 흐름**: `COARSE_SEARCH` → 후보 선택 → `PLATE_READ` 성공(비-abstain) → `TimeResolution v1`(`NEEDS_REVIEW`, `BASE_PLUS_OFFSET`) → `EvidenceRecord v1`(`occurred_at.resolution_status=NEEDS_REVIEW`) → 사용자가 정정 제출(`CorrectionRecord`, opaque ref만 사용 — Draft 계약이라 필드 스키마 미생성) → `TimeResolution v2`(`status=OK`, `verification=AGREED`, `user_corrected=true`, `supersedes_ref=v1`) → `EvidenceRecord v2`(`occurred_at`만 갱신, `vehicle_number`는 v1과 완전 동일) → `RequirementReport v1(WARN)`→`v2(PASS)`.

**기대 결과**: `EvidenceRecord v2.vehicle_number`가 `EvidenceRecord v1.vehicle_number`와 값·source·support_refs·needs_review 전부 동일. `CaseView.evidence.user_edited=true`이지만 `plate_display`는 그대로.

**검증 Contract**: `TimeResolution`(supersede)·`EvidenceRecord`(supersede)·`RequirementReport`(supersede)·`ReadoutRun`(overlay 부재)·`JobRecord`·`JobExecution`·`UsageRecord`·`CaseView`.

**의도적으로 만들지 않은 것**: `CorrectionRecord`의 실제 필드 fixture. `contract-correction-record.md`가 아직 Draft이기 때문이며, `04_mock_validation_report.md`의 "Fixture 생성 불가"에 기록했다.

---

## Eval Harness 전용 fixture (시나리오 밖, `data/mock/expected/`)

| 파일 | 종류 | 목적 |
| --- | --- | --- |
| `eval_fixture_correct_001.json` | 항상-정답 | actual == expected일 때 metric 계산 코드가 만점(1.0)을 내는지 검증 |
| `eval_fixture_wrong_001.json` | 의도적 오답 | 잘못된 번호판 채택·나쁜 후보 순위·큰 timestamp 편차·false positive abstain을 각각 심어, metric 코드가 실제로 오류를 잡아내는지 검증 |

두 파일 모두 `provisional_non_contract_schema: true`로 표시했다 — eval의 정식 Ground Truth 스키마는 아직 어떤 Final Contract에도 정의돼 있지 않다(`contract-readout-run.md` §2 "정답지... 현재 없으며 eval 소유 후속").
