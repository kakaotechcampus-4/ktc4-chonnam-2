# 김준영 담당 Mock / Contract 검수 보고서

> 검수일: 2026-09-09
> 기준 브랜치: `develop`
> 기준 커밋: `e94f527` (`origin/develop`과 동기화 확인)
> 검수 범위: 김준영 담당 `evidence` 및 `common/runtime`, 그리고 해당 Mock의 직접 Producer/Consumer 접합부
> 검수 관점: Contract 일치 / 현실적인 값 조합 / 실패·UNKNOWN·ABSTAIN / Consumer 사용 가능 / Scenario 참조 일관성
> 추가 근거: [Mock Pack PR #14](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/14), 팀 검수 이슈 [#15 search](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/15) / [#16 readout](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/16) / [#17 eval](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/17) / [#18 recording](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/18)
> Mock 생성자 문서 전수 확인: `docs/mock/01`~`05` 및 `CONTRACT_CONFLICTS.md` 6종 전문

## 1. 최종 판정

**판정: `REQUEST_CHANGES` — 단, 구조 검증과 제한된 개발 착수에는 `PARTIAL_READY`.**

- `data/mock/validate_mock_pack.py`와 계약 fixture 검사는 모두 통과했다. JSON 파싱, 주요 필수 필드, ID/참조, 일부 상태 불변조건은 양호하다.
- `evidence` Mock은 `OK`, `NEEDS_REVIEW`, 번호판 부재, `PLATE_REREAD`, correction/supersede, `RequirementReport`의 `PASS/WARN/UNKNOWN`, ready-only `ReportPackage`를 계약 모양대로 표현한다.
- `common/runtime` Mock은 `JobExecution`과 `UsageRecord`의 실행·Run 참조를 정상적으로 연결한다.
- 그러나 현재 Pack을 **김준영 담당 구현의 완료 기준 또는 Consumer가 그대로 믿을 canonical seed**로 쓰기에는 아래 Required 항목이 남아 있다. 특히 비용 통화, 정책/유형 registry, Requirement/Package 최소 사례, overlay 없음의 실패 오분류는 실제 분기 결과를 바꾼다.
- PR #14는 이 Pack을 `develop`에 병합하면서도 Owner 독립 수정만 반영하고 15개 후속 항목을 남겼다. 열린 이슈 #15~#18에서 여러 의미 결정이 추가로 내려졌지만 현재 기준 커밋의 fixture에는 아직 반영되지 않았다.
- Mock 생성자 주요 문서 6종은 유용한 근거를 상당수 이미 담고 있지만, 문서 간 readiness 판정과 미해결 상태가 동기화되지 않았다. 특히 `01`·`04`의 준비 가능 표현보다 `05`의 미해소 목록과 현재 Owner 이슈를 우선해야 한다.
- `src/daesingo/evidence`와 `src/daesingo/common`에는 실행 구현이 없고 README 골격만 있다. 따라서 이번 판정은 **Mock/Contract 정합성 판정**이며 구현 통합 또는 E2E 통과 판정이 아니다.

| 검수 축 | 판정 | 요약 |
| --- | --- | --- |
| Contract 일치 | `PARTIAL_PASS` | 구조·enum·nullable·ref는 대체로 일치하나 정책 값 공간과 일부 접합 결정이 미완이다. |
| 현실적인 값 조합 | `REQUEST_CHANGES` | KRW 예산과 USD 비용을 비교할 수 없고, 실제 번호판 형식이 아닌 값과 인과관계가 어색한 readout 조합이 있다. 정책 원본 없이 PASS/신고문 값도 검증할 수 없다. |
| 실패·UNKNOWN·ABSTAIN | `PARTIAL_PASS` | 번호판 ABSTAIN/UNKNOWN은 좋지만 TimeResolution UNKNOWN, Requirement BLOCK, runtime STALE/retry가 없다. overlay 없음은 실패로 잘못 접혀 있다. |
| Consumer 사용 가능 | `PARTIAL_READY` | parser/UI 골격 개발에는 사용 가능하나 예산·정책·failure 분기와 전체 E2E에는 부족하다. |
| Scenario 참조 일관성 | `FAIL` | correction 시나리오 설명과 실제 fixture가 다르고, search/eval의 의미 참조도 팀 Owner 결정과 어긋난다. |

## 2. 기준 문서 대조 결과

### 2.1 Product Spec

다음 제품 경계는 Mock에 대체로 반영됐다.

- 초기 지원 4종만 사용한다: `SIGNAL`, `CENTER_LINE_CROSSING`, `SOLID_LINE_LANE_CHANGE`, `MOTORCYCLE_HELMET_NON_USE`.
- 불확실한 번호판·시각·위치를 지어내지 않는다.
- AI 관찰과 신고 유형/신고문을 분리하고, 실제 제출은 사용자가 수행한다.
- 원본 Source와 신고용 파생 자산을 분리한다.

단, `safety_report_type` 값 공간과 실제 신고 규칙 원본이 없으므로 “초기 4종 → 안전신문고 신고유형 → 신고문” 연결은 아직 제품 수준에서 검증할 수 없다.

### 2.2 Module Architecture

`evidence` Mock은 다음 경계를 지킨다.

- 관찰값을 직접 생산하지 않고, upstream 결과를 받아 confirmed Evidence로 조립한다.
- `EvidenceNeeds`만 반환하고 다른 모듈을 직접 호출하지 않는다.
- `occurred_at` 확정과 영상 내 시각 표시, 번호판 문자열 확정과 영상 내 번호판 가시성을 분리한다.
- `EVIDENCE_SUFFICIENT`, `PACKAGE_READY`, `USER_REVIEWED`를 한 상태로 합치지 않는다.
- `ReportPackage`는 최종 `PASS/WARN`일 때만 존재하는 ready-only 객체다.

`common/runtime`은 `JobExecution`과 `UsageRecord`를 소유하고 Job 발주 의미를 판단하지 않는 경계를 지킨다. 다만 역할분담안의 역방향 표는 이 경계와 모순된다(Required-1).

### 2.3 역할분담안

김준영의 실제 범위는 다음으로 정리된다.

- `evidence`: `TimeResolution`, `EvidenceRecord`, `EvidenceNeeds`, `RequirementReport`, `ReportPackage`, 규정/유형 매핑, 결정론적 신고문/Package.
- `common/runtime`: `JobExecution` 계약, `UsageRecord`, 마스킹 로거/config/운영 기반. `JobExecution` 구현 담당은 정철원.
- 김준영이 소유하지 않는 것: `JobRecord` 발주 의도, OCR/AI 모델, 영상 처리, 화면 workflow, 외부 작업 직접 발주.

### 2.4 Mock 생성자 주요 문서 6종 전수 검토

| 문서 | 확인 결과 | 이 보고서에 반영한 판단 |
| --- | --- | --- |
| `01_mock_dataset_overview.md` | 목적·계약 inventory·사용 원칙은 명확하다. 다만 첫머리에서는 P0 2건 미해소를 경고하면서 §8은 준비 완료 체크를 전부 통과로 표시하고, “데이터 계약 전부 종결”이라고 쓴 뒤 `CorrectionRecord`는 Draft라고 적는다. ADR 경로도 실제 `docs/architecture/contracts/adr/`가 아니라 `docs/architecture/adr/`로 잘못 안내한다. | overview의 완료 표시는 상태 근거로 사용하지 않고, `PARTIAL_READY/REQUEST_CHANGES`로 낮춘다. |
| `02_mock_scenario_catalog.md` | 시나리오 의도와 nominal A~I 배치는 이해하기 쉽다. 그러나 happy의 전체 완주, unknown의 overlay 실패/시각 승자 없음, correction의 NOT_RUN 설명이 실제 계약·fixture·Owner 결정과 어긋난다. | Scenario 설명을 expected assertion으로 직접 사용하지 않는다. Required-5·7·8·10에 반영했다. |
| `03_mock_artifact_templates.md` | 2,486줄 전체가 generator가 선택한 실제 fixture 발췌다. 형태 확인에는 유용하지만 전체 Contract/variant를 포괄하는 문서가 아니며, 원본 fixture의 의미 오류도 그대로 복제한다. | parser 예시는 쓸 수 있으나 semantic canonical 문서로 취급하지 않는다. |
| `04_mock_validation_report.md` | 검증 범위와 미커버 목록을 비교적 정직하게 공개한다. 하지만 P0-3/P0-4 미해소를 적고도 마지막 판정을 “1차 Mock E2E 조건부 가능”으로 두며, `05`가 발견한 일부 conflict/ambiguity가 `CONTRACT_CONFLICTS.md`로 동기화되지 않았다. | validator PASS는 schema/reference 부분 통과로만 해석한다. |
| `05_mock_deep_review_report.md` | 여섯 문서 중 가장 상세하고 유용하다. 기존 보고서에서 빠졌던 AssetFacts/category, post-stamp, considered time, source kind 등 김준영 관련 항목도 확인했다. | 아래 Required-12·13 및 Owner 목록에 추가했다. 다만 2026-09-08 당시의 “Owner 답변 대기” 표시는 #15~#18 결정 이후 상태로 갱신해 해석한다. |
| `CONTRACT_CONFLICTS.md` | `04`의 초기 7개 항목만 색인하며 “Contract 충돌 없음”으로 남아 있다. 현재도 존재하는 GPS 좌표 `lat/lng` 대 `lat/lon` 충돌과 후속 미등재 값/정책 항목이 빠졌다. | 최신 conflict/ambiguity의 완전한 목록으로 사용하지 않는다. Required-13으로 분류한다. |

## 3. Contract별 Mock 커버리지

| 담당 Contract | 현재 존재하는 사례 | 빠진 핵심 사례 | 판정 |
| --- | --- | --- | --- |
| `TimeResolution` | `OK`, `NEEDS_REVIEW+conflict`, `USER_OVERRIDE+supersedes` | `status=UNKNOWN`; USER_OVERRIDE와 `verification`의 확정 대응 | `PARTIAL` |
| `EvidenceRecord` | happy confirmed 값, 차량번호 필드 부재, correction 전/후 immutable chain | `VisualEvidence=UNCERTAIN`일 때 Record/event 처리 | `PARTIAL` |
| `EvidenceNeeds` | `items=[]`, `PLATE_REREAD` | `OVERLAY_TIME_OCR` | `PARTIAL` |
| `RequirementReport` | EVIDENCE `PASS/WARN/UNKNOWN`, FINAL_PACKAGE `PASS`, measurement, supersedes | EVIDENCE `BLOCK`; FINAL_PACKAGE `WARN/BLOCK/UNKNOWN` | `INSUFFICIENT` |
| `ReportPackage` | 정상 PASS Package 1건 | WARN Package, optional plate image 없음, post-stamp, correction 후 새 Package+supersedes | `INSUFFICIENT` |
| `JobExecution` | `QUEUED`, `SUCCEEDED`, `FAILED` | `RUNNING`, `STALE`, `attempt>=2` 재시도 | `PARTIAL` |
| `UsageRecord` | analysis/readout run 연결, token object/null, latency/duration/cost | 단일 통화 또는 환율 snapshot을 포함한 예산 비교 가능 사례 | `BLOCKED_FOR_BUDGET_CONSUMER` |

Contract가 명시한 `RequirementReport`/`ReportPackage` 최소 Mock 사례는 `docs/architecture/contracts/contract-requirement-report-package.md` §13에 있다. 현재 Pack은 그 목록 중 일부만 충족한다.

## 4. Findings

### Required-1. 역할분담안 역방향 표가 `JobRecord`와 `JobExecution` 소유권을 뒤집어 적었다

**근거**

- `docs/management/ownership.md:316`은 `common/runtime` 계약 생산자를 `JobRecord`·`UsageRecord`로 적고 `JobExecution`을 빠뜨린다.
- 같은 문서 `:357`과 `module-architecture.md:1054`는 `JobRecord=case`, `JobExecution/UsageRecord=common/runtime`으로 정의한다.

**영향**

- 김준영 담당 범위를 읽는 사람이 Job 발주 스키마까지 김준영 소유로 오해한다.
- `case`와 `common/runtime`이 서로 다른 Mock을 만들 가능성이 있다.

**조치 기준**

- 역방향 표를 `JobExecution`·`UsageRecord`·마스킹 로거로 바로잡고, `JobRecord`는 `case` 행에만 남긴다.

### Required-2. KRW 예산과 USD 비용으로는 Consumer가 예산 소진을 판정할 수 없다

**근거**

- 모든 `AnalysisScope.budget.max_cost_krw`는 `300` KRW다. 예: `data/mock/search/scenario_happy_001.json:12`.
- 같은 happy Search/Usage 비용은 `0.42 USD`다: `data/mock/search/scenario_happy_001.json:37`, `data/mock/common/scenario_happy_001.json:63`.
- 같은 case의 local OCR 비용은 KRW이므로 한 사건 안에 USD/KRW가 섞인다.
- `contract-usage-record.md` §10도 KRW 고정/다중 통화 환산을 미결로 남긴다.

**영향**

- `case` Consumer는 `max_cost_krw`와 사용 비용을 비교할 수 없다.
- `scenario_happy_001`이 실제로 예산 내 성공인지 초과인지 판정할 수 없어 “현실적인 Happy”가 성립하지 않는다.

**조치 기준 — 담당 범위 확인 필요**

- 김준영(`UsageRecord`) + 유소연(`AnalysisScope/case`) + 김대원(eval)이 KRW 단일화 또는 실행 시점 환율 snapshot 규칙을 결정한다.
- 결정 후 Mock과 validator가 `budget` 대비 authoritative usage 합계를 검증해야 한다.

### Required-3. 신고 규칙·유형·template 원본이 없어 PASS와 Package 내용을 독립 검증할 수 없다

**근거**

- Mock은 `policy/requirement-rules-v1`, `policy/evidence-assembly-v1`, `policy/package-assembly-v1`, `tmpl/safety-report-v1`을 참조한다.
- 저장소에는 해당 policy/registry/template을 해석할 수 있는 정식 산출물이 없다. 현재는 research memo와 opaque 문자열만 있다.
- `safety_report_type`의 값 공간도 Final Contract에 등재되지 않아 Mock 문서 스스로 placeholder라고 명시한다.

**영향**

- `RequirementReport.overall=PASS`가 어떤 규정 데이터로 나온 결과인지 재현할 수 없다.
- `ReportPackage.report`가 deterministic template 결과인지 확인할 수 없다.
- Consumer는 placeholder enum을 production 분기나 저장 스키마에 고정하면 안 된다.

**조치 기준 — 구현/정책 산출물 필요**

- 김준영 Owner 범위에서 최소한 4종 유형 매핑 registry, requirement rule data, template 원본과 버전 lookup 규칙을 제공한다.
- 기존 Contract의 `policy_ref`/`template_ref`로 충분히 연결할 수 없다면 그때 `Contract 변경 검토 필요`로 올린다.

### Required-4. evidence/Package Contract가 요구한 실패·UNKNOWN 조합이 부족하다

**근거**

- 현재 evidence fixture의 Requirement 결과는 `EVIDENCE: PASS/WARN/UNKNOWN`, `FINAL_PACKAGE: PASS`뿐이다.
- Contract 최소 사례는 EVIDENCE와 FINAL_PACKAGE 각각 `PASS/WARN/BLOCK/UNKNOWN`, 그리고 WARN Package·plate image 없음·post-stamp·correction Package를 요구한다.
- `TimeResolution.status=UNKNOWN`도 0건이다.

**영향**

- `BLOCK > UNKNOWN > WARN > PASS` precedence의 BLOCK 최상위 분기를 Mock E2E에서 확인하지 못한다.
- `BLOCK/UNKNOWN`에서 Package가 없고 `WARN`에서는 Package가 존재하는 경계를 Consumer가 비교할 수 없다.
- 사후 timestamp가 필요한 경우의 Package/notice 연결을 검증하지 못한다.

**조치 기준**

- 최소 추가 순서는 `RequirementReport BLOCK`, `TimeResolution UNKNOWN`, `FINAL_PACKAGE WARN + Package`, `FINAL_PACKAGE BLOCK/UNKNOWN + Package 부재`, `post_stamp=true` Package다.
- 시나리오 수를 줄이려면 한 시나리오 안에 unrelated 상태를 섞기보다 전이 snapshot을 사용한다.

### Required-5. “overlay 없음”을 실행 실패로 모델링해 없음과 UNKNOWN/ERROR가 합쳐졌다

**근거**

- `data/mock/readout/scenario_unknown_abstain_partial_001.json:21-22`는 `NO_OVERLAY_PRESENT`를 `ReadoutRun.outcome=FAILED`로 둔다.
- `data/mock/common/scenario_unknown_abstain_partial_001.json:38-44`도 이를 `JobExecution.status=FAILED`, `failure_kind=READOUT_OVERLAY_DETECTION`으로 투영한다.
- readout 결정 문서는 “overlay 없음”과 “탐지 실패/확인하지 못함”을 합치지 말라고 명시한다.
- `OVERLAY_DETECTION`과 `READOUT_OVERLAY_DETECTION`은 현재 readout failure taxonomy에 등재된 값이 아니다.

**영향**

- Consumer가 “화면 시각이 실제로 없음”과 “판독 인프라/검증 실패”를 구분할 수 없다.
- 정상 fallback 시나리오가 retry 대상 실패처럼 보이고, runtime 실패 통계도 오염된다.

**조치 기준 — Owner 결정 완료, Mock 미반영**

- 이슈 #16에서 신유민은 overlay가 실제로 없으면 `ReadoutRun=SUCCEEDED` + `Observation.status=NOT_APPLICABLE` + `reason=readout.overlay.not_present`로 표현하기로 정리했다.
- 존재 여부가 불명확하거나 OCR이 실패한 경우만 `UNKNOWN`과 해당 reason을 사용한다. 실제 실행 실패는 `ReadoutRun.failure.kind=INFRA`, `JobExecution.failure_kind=READOUT_INFRA` 계열로 분리한다.
- 현재 unknown 시나리오와 common/runtime projection을 이 결정에 맞춰 수정하고, 별도의 UNKNOWN/INFRA 사례를 추가한다.

### Required-6. `VisualEvidence`가 Fine 실행과 불확실성 의미를 잘못 표현한다

**근거**

- `contract-visual-evidence.md`는 `run_id`가 결과를 생산한 Fine/Classification `AnalysisRun`이어야 한다고 정한다.
- 현재 3개 `VisualEvidence`는 모두 `operation=CANDIDATE_SEARCH`인 동일 Run을 가리키며 `VISUAL_VERIFY` Run은 0건이다.
- unknown 시나리오의 `ve_u001`은 RED_SIGNAL primitive가 `UNCERTAIN`, confidence `0.47`인데도 `verification=OBSERVED`, `visual_event_type=SIGNAL`이다(`data/mock/search/scenario_unknown_abstain_partial_001.json:64-80`).
- 같은 객체 안에서도 uncertainties 문자열이 후보 단계의 `SIGNAL_STATE_NOT_CLEARLY_VISIBLE`과 VisualEvidence의 `SIGNAL_STATE_OCCLUDED`로 갈린다.

**영향**

- `evidence`는 실제 판단 근거를 어느 검증 실행이 만들었는지 추적할 수 없다.
- 비용·모델·실패 provenance가 Coarse Search로 잘못 연결된다.

**조치 기준 — search 결정 완료, evidence 결정 필요**

- 이슈 #15에서 서어진은 `VISUAL_VERIFY.input_ref=analysis_source(as_h001_fine)`, evidence ref는 `FrameRef`, `ve_u001.verification=UNCERTAIN`, `visual_event_type=null`로 정리했다.
- search Mock은 이 결정을 반영해야 한다.
- 김준영은 UNCERTAIN `VisualEvidence`에서 `EvidenceRecord` 생성 여부와 필수 event 필드 처리 규칙을 확정해야 한다. 이 결정 전 unknown scenario의 downstream evidence를 canonical expected로 고정하면 안 된다.

### Required-7. Happy Path의 Report Video 생성 실행이 Mock에서 생략됐다

**근거**

- happy `JobRecord`는 `COARSE_SEARCH`, `PLATE_READ`, `OVERLAY_TIME_READ` 3건뿐이다(`data/mock/case/scenario_happy_001.json:4-40`).
- 하지만 같은 시나리오에는 `DerivedAsset(REPORT_VIDEO)`와 `ReportPackage`가 이미 존재한다.
- Mock 문서도 Report Video export용 `JobRecord.kind`가 미등재라서 자산을 미리 만들어 우회했다고 기록한다.

**영향**

- “입력부터 ReportPackage까지 전체 파이프라인 완주”라는 시나리오 설명과 달리 export 발주/실행/실패/retry 경계는 검증되지 않는다.
- `JobExecution` Consumer와 Package Consumer를 잇는 실제 접합을 개발할 수 없다.

**조치 기준 — 담당 범위 확인 필요**

- 유소연(case)의 export Job kind 결정과 정철원(recording)의 export 실행/fixture 연결을 기다린다.
- 결정 전에는 현재 happy를 `prebuilt derived asset 기반 제한 경로`로 명시한다.

### Required-8. Scenario 설명이 다르고 실제 번호판 값도 현실적이지 않다

**근거**

- `data/mock/scenarios/scenario_correction_rerun_001.json:6`은 확정 번호판을 `45다6789`라고 적는다.
- 실제 readout/evidence/case fixture는 모두 `광주서구 가1234`다. 예: `data/mock/evidence/scenario_correction_rerun_001.json:155-156`.
- `광주서구 가1234` 자체도 실제 국내 번호판 형식으로 보기 어렵다. 광역 지명 뒤에 구 단위 `서구`를 이어 붙였고 선행 숫자 자리도 빠졌다. 이슈 #16과 #17의 독립 검수도 같은 문제를 지적했다.
- `scenario_unknown_abstain_partial_001` 설명은 시각 충돌에서 “임의로 승자를 정하지 않는다”고 적지만, 실제 `TimeResolution`은 Filename 후보를 fallback resolved 값으로 선택하고 `selected_input_ref`에도 기록한다. 계약상 맞는 설명은 “fallback을 선택하되 conflict를 보존한다”다.

**영향**

- 시나리오를 테스트 이름/expected 설명으로 사용하는 Consumer가 실제 payload와 다른 assertion을 작성한다.

**조치 기준**

- correction 번호판은 실제 형식의 테스트 값 하나로 readout/evidence/case/scenario 설명을 함께 맞춘다.
- 시각 conflict metadata는 실제 fixture에 맞춰 고친다.
- validator에 시나리오 설명의 구조화 expected 값까지 넣지 않는다면, 최소한 review checklist에서 문구-값 대조를 수행한다.

### Required-9. eval expected fixture가 실제 검색 정확도와 ABSTAIN 품질을 채점하지 못한다

**근거**

- `eval_fixture_correct_001.json:18-22`는 예측과 정답의 `candidate_id` 문자열 동일성으로 Top-1 정답 여부를 판정한다. 실제 구현은 Ground Truth의 candidate ID를 재사용하지 않으므로 현실적인 채점 기준이 아니다.
- 이슈 #17은 사건 유형과 시간구간 IoU(`>=0.5`)로 match한 뒤 `recall_at(K=1,3,10)`을 계산하도록 정리했다.
- 현재 metric은 `candidate_top1_accuracy`, `time_within_tolerance_rate`, `abstention_correctness_rate` 한 값이다. 이슈 #17의 결정은 각각 `recall_at`, `timestamp_error_sec`, `abstention_recall` + `wrong_accept_rate`로 바꾸고 번호판 정답에 `legibility`를 추가하는 것이다.
- validator의 eval 구간(`validate_mock_pack.py:765-793`)은 ref 존재와 `expect_match` boolean만 확인한다. `actual_value`가 실제 참조 객체의 값과 같은지는 역참조해 확인하지 않는다.

**영향**

- Consumer가 provisional expected fixture를 그대로 구현하면 실제 후보 탐색을 틀리게 채점할 수 있다.
- UNKNOWN/ABSTAIN에서 “잘 포기함”과 “읽을 수 있는데 포기함”, “읽을 수 없는데 잘못 채택함”이 분리되지 않는다.
- fixture 안의 복제 `actual_value`가 runtime mock과 달라져도 validator가 PASS할 수 있다.

**조치 기준 — eval 결정 완료, fixture/harness 미반영**

- 김대원 결정에 맞춰 Ground Truth match와 metric 구조를 교체하고, `UsageRecord`를 비용의 authoritative source로 사용한다.
- validator는 `actual_ref`가 있는 target의 실제 값과 inline `actual_*`를 동기화 검증하거나 inline 복제를 제거해야 한다.

### Required-10. readout 값 조합이 실제 실패 원인과 시간 검증을 충분히 표현하지 못한다

**근거**

- unknown 번호판은 `target_association.status=AMBIGUOUS`인데 `abstain_reason=FRAME_DISAGREEMENT`다(`data/mock/readout/scenario_unknown_abstain_partial_001.json:42,71`). 어떤 원인이 우선하여 ABSTAIN을 일으켰는지 불명확하다.
- 낮은 품질(`plate_px_height=24`, `sharpness=0.44`)인데 두 frame OCR 문자열은 한 글자만 달라 지나치게 깨끗한 조합이다.
- happy overlay 표본은 `12.48`, `13.1`, `13.6`초에 몰려 있어 긴 clip에서 monotonic/duration 정합성을 실질적으로 검증하기 어렵다.
- correction 시나리오는 사건 후보가 선택되어 있는데 `OVERLAY_TIME_READ` 실행과 `OverlayTimeReadout`이 모두 없다. 이는 선택 사건마다 Overlay OCR을 실행한다는 `contract-plate-overlay-readout.md:259-265`의 초기 v1 정책과 충돌한다.
- Contract는 여러 sample 중 어떤 값을 `observation.value`로 고르는지 규칙을 정의하지 않는다. 이슈 #16은 incident offset과 가장 가까운 sample이라는 후보 규칙을 김준영/유소연 결정사항으로 올렸다.

**영향**

- readout/evidence Consumer가 동일 입력에 서로 다른 주원인, 대표 시각, 재시도 동작을 선택할 수 있다.
- correction 경로가 Overlay OCR 미실행을 완료 상태처럼 숨긴다.

**조치 기준**

- ABSTAIN 주원인을 `TARGET_AMBIGUOUS`로 맞추거나 association을 `ASSOCIATED`로 바꿔 frame disagreement가 실제 주원인이 되게 한다.
- 품질 수치와 frame OCR 변이를 함께 현실화하고 overlay sample을 clip 전반에 분산한다.
- correction을 pre-dispatch snapshot으로 명시하지 않는다면 `SUCCEEDED+NOT_APPLICABLE`을 포함한 Overlay 실행 결과를 추가한다.
- 대표 `observation.value` 선택 규칙은 Contract에 확정한 뒤 validator에 넣는다.

### Required-11. Windows 기본 출력 인코딩에서 validator가 성공 후 실패한다

**근거**

- 현재 호스트에서 UTF-8 실행은 PASS하지만 `PYTHONIOENCODING=cp949`로 실행하면 마지막 성공 문구의 em dash(`—`) 출력에서 `UnicodeEncodeError`가 발생해 exit code 1이 된다.
- 이슈 #16과 #17의 보고를 현재 checkout에서 재현했다.

**영향**

- 구조 검증은 모두 끝났는데 Windows 실행자와 CI wrapper에는 실패로 보인다. 팀원이 실제 schema 오류로 오인하거나 검증을 우회할 수 있다.

**조치 기준**

- stdout을 UTF-8로 재설정하거나 출력 문자열을 cp949-safe 문자로 바꾸고, cp949 회귀 실행을 추가한다.

### Required-12. Happy Evidence/Package 안에 서로 양립하기 어려운 판정이 남아 있다

**근거**

- `tres_h001.post_stamp.needed=false`인데 Report Video의 `transform_ref`는 `tr_h001_poststamp_v1`이다(`data/mock/evidence/scenario_happy_001.json:49-52`, `data/mock/recording/scenario_happy_001.json:205`). 사후각인이 불필요하다는 판정과 실제 적용 transform 이름이 충돌한다.
- FINAL_PACKAGE의 `package.asset.plate_visible`은 `category=ASSET`으로 PASS하지만, Contract는 번호판 가시성을 AssetFacts가 아닌 readout observation 기반 판정으로 분리한다. recording의 `asset_facts`에는 `clip_h001`과 Report Video만 있고 `da_h001_plate_image` 사실도 없다.
- happy `TimeResolution.considered[]`에는 사건시각이 아니라 파일 시작 anchor `18:00:00`이 그대로 들어가, resolved event time `18:05:12`와 허위 5분 차이처럼 보인다.
- happy 위치는 user hint뿐이라 `CaseView.location_display.info_state=INFO_NEEDS_REVIEW`인데 object-level `review_needed=false`이고 Requirement는 `PASS`다. 각 값은 개별 규칙으로 설명할 수 있어도 “모든 값 confirmed/all-green”이라는 happy 설명과는 맞지 않는다.

**영향**

- evidence와 recording Consumer가 같은 happy fixture에서 “각인됨/각인 불필요”, “자산 사실/판독 관찰”, “사건시각/파일 시작시각”을 서로 다르게 해석할 수 있다.
- 정상 기준선 하나로 Consumer 테스트를 작성하면 잘못된 판정이 canonical behavior로 굳는다.

**조치 기준**

- happy transform은 실제 적용한 trim 등으로 바꾸고, post-stamp 사례는 `post_stamp.needed=true`인 correction/별도 시나리오로 옮긴다.
- plate visibility check를 `VEHICLE` 등 적합한 category와 readout 근거로 연결하고, 정말 필요한 derived plate image AssetFacts는 recording 입력으로 보강한다.
- `considered[]`에는 같은 사건시각 축으로 비교 가능한 anchor+offset 값을 넣거나 base anchor는 `computation.base_input_ref`에만 둔다.
- happy를 all-green으로 유지하려면 GPS/address 관찰을 추가해 위치 상태까지 맞추고, 그렇지 않으면 “location review가 남은 partial happy”로 이름과 설명을 낮춘다.

### Required-13. Mock 문서의 상태·충돌 인덱스가 서로 동기화되지 않았다

**근거**

- `01_mock_dataset_overview.md:3`은 P0 2건 미해소를 경고하지만 §8은 1차 통합 준비 조건 12개를 전부 완료로 표시한다.
- `04_mock_validation_report.md:5`도 같은 P0를 미해소로 기록하면서 `:109`에서는 1차 E2E 통합이 조건부 가능하다고 결론낸다. `05_mock_deep_review_report.md:34`의 “현재 상태로 merge 불가”와 readiness 표현이 일치하지 않는다.
- `01`은 “데이터 계약이 전부 종결”됐다고 쓰지만 같은 문서와 실제 `contract-correction-record.md`는 `CorrectionRecord`를 Draft로 둔다. Source of Truth의 ADR 경로도 실제 위치와 다르다.
- `CONTRACT_CONFLICTS.md`는 충돌 없음으로 남아 있지만 `contract-observation.md`의 GPS `{lat,lng}`와 evidence/CaseView의 `{lat,lon}`은 현재도 충돌한다. `05`에서 발견한 미등재 `source.kind`, VisualEvidence ref 형식, 예산 통화 등도 index에 반영되지 않았다.
- `05`의 Owner 대기 목록은 #15~#18에서 결정이 난 뒤에도 갱신되지 않아, “결정 대기”와 “결정 완료·Mock 미반영”을 구분하지 못한다.

**영향**

- 처음 `01` 또는 `04`만 읽은 개발자는 Pack을 canonical/E2E-ready로 오해할 수 있다.
- 이슈에서 끝난 논의를 다시 열거나, 반대로 미반영 fixture를 합의된 최종값으로 오해할 수 있다.

**조치 기준**

- `01`·`04`·`05` 상단에 동일한 현재 상태(`REQUEST_CHANGES`, schema-only `PARTIAL_READY`)와 기준 commit/date를 둔다.
- 완료 체크리스트는 nominal 파일 존재와 semantic E2E readiness를 분리한다.
- `CONTRACT_CONFLICTS.md`를 `04`·`05`·#15~#18과 동기화하고 각 항목을 `결정 대기 / 결정 완료·미반영 / 해소`로 표시한다.
- `03`은 generated snapshot임을 유지하되 “선택된 예시이며 semantic 검증을 보장하지 않는다”는 경계를 앞부분에 명시한다.

## 5. 잘 된 부분

- 번호판 ABSTAIN은 `ReadoutRun=SUCCEEDED`와 `PlateReadout.abstained=true`로 분리되어 전체 Case 실패로 번지지 않는다.
- 차량번호를 확정하지 못한 경우 `UNKNOWN` 문자열이나 placeholder 대신 `EvidenceRecord.vehicle_number` 필드 자체를 생략한다.
- `EvidenceNeeds.PLATE_REREAD`가 사건 interval과 target hint를 semantic ref로 전달하며 queue/timeout 같은 실행 세부를 담지 않는다.
- correction은 `TimeResolution`, `EvidenceRecord`, `RequirementReport`를 overwrite하지 않고 새 ref와 `supersedes_ref`로 연결한다.
- 기존 번호판 값과 provenance는 시각 correction 뒤에도 유지된다.
- `RequirementReport` aggregation과 ready-only `ReportPackage` 기본 규칙은 현재 fixture에서 맞는다.
- `UsageRecord.run_ref`와 Search/Readout의 usage reference, token 합계, processed duration, latency가 현재 데이터에서는 일치한다.
- `CaseView`가 raw evidence를 복제하지 않고 safe projection을 제공하며 web이 원 계약을 직접 읽지 않는 경계를 지킨다.

## 6. Consumer별 사용 가능 범위

| Consumer | 지금 가능한 것 | 아직 막힌 것 |
| --- | --- | --- |
| `case` | Evidence/Needs 파싱, PLATE_REREAD 발주, PASS/WARN/UNKNOWN projection, correction head 선택 | 비용 예산 판정, BLOCK 및 Time UNKNOWN 분기, Report Video export orchestration |
| `web` (`CaseView` 경유) | happy/empty/ABSTAIN/처리중/사용자 최종확인 기본 화면 | overlay 없음 vs 실패 문구, 수동 번호판 입력 action, BLOCK UI, post-stamp warning, progress의 미실행/대기 구분, 완전한 report type registry |
| `eval` | usage ledger 기본 집계 shape와 metric harness 연동용 provisional 자료 | 현실적인 candidate matching, recall@K, legibility 기반 ABSTAIN 지표, timestamp error, KRW 기준 비용 비교, runtime STALE/retry 집계 |
| `search`/`readout` | `UsageRecord` 연결 모양 | 예산 통화 규칙, Fine/Visual Verify provenance, 등록된 overlay failure taxonomy |

## 7. 김준영 Owner 결정 목록

1. `SafetyReportType` registry와 4종→신고유형/표현 매핑의 canonical 위치를 확정한다.
2. requirement rule data와 deterministic report template의 실제 versioned artifact를 만든다.
3. 유소연·김대원과 KRW/USD 예산 비교 규칙을 확정한다.
4. `VisualEvidence.verification=UNCERTAIN`일 때 `EvidenceRecord`를 만들지, 만든다면 필수 event 값을 어떻게 다룰지 확정한다. 이 결정은 이슈 #15의 search Mock 반영을 막는 현재 직접 blocker다.
5. 미등재 `source.kind`와 `source.label_key`를 승인/교체하고 registry 위치를 정한다.
6. `plate_visible` Requirement check의 category와 입력 관찰 provenance를 확정한다.
7. GPS `Observation<Coordinate>`를 주소/신고 위치로 변환할 때 reverse-geocode provenance와 user hint 우선순위를 정한다. recording은 이슈 #18에서 좌표 관찰 생산 경계까지만 확정했다.
8. 여러 overlay sample 중 `OverlayTimeReadout.observation.value`를 선택하는 규칙을 유소연과 확정한다.
9. 업로드 직후 overlay 존재 여부를 제품이 보여줘야 한다면, 현 Contract에 intake presence 결과가 없다는 이슈 #16의 gap을 `Contract 변경 검토 필요`로 처리한다.
10. `package.asset.plate_visible`의 category와 readout observation/AssetFacts 경계를 확정한다.
11. `TimeResolution.post_stamp`와 `DerivedAsset.transform_ref`가 서로 모순되지 않도록 Package 조립 검증 규칙을 정한다.
12. `TimeResolution.considered[]`에는 서로 비교 가능한 사건시각만 넣을지, base anchor를 어떤 형태로 표시할지 확정한다.

## 8. PR #14 및 팀 이슈 교차검토

PR #14는 2026-09-08 `develop`에 병합되었고 merge commit이 이 보고서의 기준 커밋 `e94f527`이다. PR 본문은 심층 검토에서 찾은 항목 중 Owner 독립 수정만 반영했으며, `VISUAL_VERIFY`, overlay 없음, GPS/location, source kind, eval metric 등은 후속 이슈로 넘겼다고 명시한다. PR 자체에는 별도 review/comment가 없으므로, 아래 Owner 이슈를 최신 의미 결정 근거로 사용했다.

| 이슈 | 확인된 Owner 결정 | develop 반영 상태 | 김준영 관점 |
| --- | --- | --- | --- |
| [#15 search](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/15) | Fine 입력은 `analysis_source`, 근거는 `FrameRef`; `ve_u001=UNCERTAIN`, event type `null`; uncertainty kind 통일 | **미반영** | UNCERTAIN EvidenceRecord/event 규칙 결정 필요 |
| [#16 readout](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/16) | overlay 없음=`SUCCEEDED+NOT_APPLICABLE`; 불명=`UNKNOWN`; 인프라 실패 taxonomy 분리 | **미반영** | TimeResolution/CaseView가 없음·불명·실패를 다르게 소비해야 함 |
| [#17 eval](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/17) | 후보 IoU matching, recall@K, legibility, ABSTAIN recall/wrong accept, timestamp error, UsageRecord authoritative | **미반영** | 현 expected fixture는 비canonical이며 비용/ABSTAIN 검증 근거로 사용 금지 |
| [#18 recording](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/18) | 요청 시각당 GPS Observation 1개; source absent=`UNKNOWN`; rebase/gap 시나리오 승인 | **미반영** (`data/mock` GPS 0건) | 좌표 이후 주소 provenance만 evidence 결정으로 남음 |

네 이슈는 2026-09-09 확인 시점에 모두 `OPEN`이고 comment는 없다. 따라서 “결정 완료”는 이슈 본문에 기록된 각 Owner의 검수 결론을 뜻하며, 구현·fixture 반영 완료를 뜻하지 않는다.

### 아직 외부 Owner 반영이 필요한 항목

- 신유민: 이슈 #16 결정을 readout fixture/failure taxonomy/CaseView notice 입력에 반영.
- 서어진·유소연: 이슈 #15의 `VISUAL_VERIFY` Run과 Fine 발주 연결을 fixture에 반영.
- 김대원: 이슈 #17의 Ground Truth/metric 구조와 harness를 반영.
- 정철원: 이슈 #18의 GPS/rebase/gap 및 Report Video export 결과 fixture를 반영.
- 유소연: Report Video export/purge Job kind, `CaseView.evidence.review_needed`와 progress 미실행 표현 확정.
- 유소연 + 김준영: `CorrectionRecord` Draft Consumer Review(case → evidence).

Owner 결정이 난 항목은 더 이상 “의미 결정 대기”로 보지 않는다. 대신 **결정 완료·Mock 미반영** 상태로 추적한다. upstream 반영 전 현재 Mock을 canonical input으로 고정하면 안 된다.

## 9. 재검수 통과 조건

- [ ] 역할분담안에서 `JobRecord`/`JobExecution` Owner 표가 일치한다.
- [ ] 예산과 비용이 직접 비교 가능하고 validator가 이를 검사한다.
- [ ] SafetyReportType/rule/template registry가 실제 파일로 존재하고 Mock ref가 resolve된다.
- [ ] EVIDENCE 및 FINAL_PACKAGE의 PASS/WARN/BLOCK/UNKNOWN 최소 사례가 있다.
- [ ] `TimeResolution.status=UNKNOWN`, `EvidenceNeeds.OVERLAY_TIME_OCR`, post-stamp Package 사례가 있다.
- [ ] overlay 없음과 실행 실패가 서로 다른 payload와 UI projection으로 표현된다.
- [ ] VisualEvidence가 실제 `VISUAL_VERIFY` Run을 가리키고, unknown 사례가 `UNCERTAIN` + event type `null`로 연결된다.
- [ ] Report Video export 발주→실행→DerivedAsset→FINAL_PACKAGE→ReportPackage 연결이 있다.
- [ ] GPS OK/UNKNOWN 및 rebase/gap 시나리오가 이슈 #18 결정대로 존재한다.
- [ ] eval expected가 event type + interval IoU matching, recall@K, legibility/ABSTAIN, timestamp error를 표현한다.
- [ ] correction에도 선택 사건 Overlay OCR 실행 또는 명시적인 pre-dispatch snapshot 설명이 있다.
- [ ] happy의 post-stamp/transform, plate-visible 입력/category, considered 시각, location review 상태가 서로 일치한다.
- [ ] 번호판 값이 실제 형식이고, Scenario 설명의 기대값이 실제 JSON과 일치한다.
- [ ] validator가 `actual_ref`와 inline actual 값을 동기화 검사하고 cp949 출력에서도 종료코드 0이다.
- [ ] `01`·`04`·`05`의 readiness와 Owner 상태가 같고 `CONTRACT_CONFLICTS.md`가 알려진 충돌/불명확성을 빠짐없이 색인한다.
- [ ] `python data/mock/validate_mock_pack.py` 통과.
- [ ] `python scripts/check_contract_fixtures.py` 통과.
- [ ] `python scripts/check_boundaries.py` 통과.
- [ ] 구현이 생긴 뒤 module test와 제한 Mock E2E 결과를 별도로 기록한다.

## 10. 이번 검증 실행 기록

| 명령 | 결과 | 해석 범위 |
| --- | --- | --- |
| `git status --short --branch` | `develop...origin/develop`, clean (보고서 작성 전) | 원격 동기화 확인 |
| `gh pr view 14 ...` | MERGED, merge commit `e94f527` | 현재 기준 commit이 마지막 Mock 생성 PR 결과임을 확인 |
| `gh issue list/view ...` | #15~#18 OPEN, 각 Owner 검수 본문 확인 | 이슈 결정과 현재 fixture를 교차대조 |
| `docs/mock/01`~`05`, `CONTRACT_CONFLICTS.md` 전문 확인 | 6개 문서 / 총 4,009행 | 문서 주장·상태·fixture/Contract 근거 교차검토 |
| `python data/mock/validate_mock_pack.py` | PASS, JSON 29개 / 시나리오 4개 | Mock 구조·참조·구현된 불변조건 |
| `PYTHONIOENCODING=cp949` 상당 환경에서 동일 validator 실행 | **FAIL**, 최종 em dash 출력의 `UnicodeEncodeError`, exit 1 | 이슈 #16/#17의 Windows 인코딩 결함 재현 |
| `python scripts/check_contract_fixtures.py` | 문서 60 / JSON 26 / 의미 104 검사 PASS | 계약 문서 fixture 정합성; E2E/Owner 수락 아님 |
| `python scripts/check_boundaries.py` | PASS, domain 실행 코드 없음 NOTE | 경계 문자열 검사; 구현 동작 검증 아님 |
| `npm run build` | PASS | prototype TypeScript/Vite build; 김준영 domain 구현 검증 아님 |
| `git diff --check` | PASS (보고서 작성 전) | 기존 working tree whitespace 오류 없음 |

## 11. 결론

현재 Mock Pack과 생성자 문서는 **계약 모양을 읽고 parser/projection 골격을 만드는 자료로는 쓸 수 있다.** 그러나 김준영 담당 기준으로는 “실제 정책이 적용된 현실적인 데이터”, “예산 Consumer가 계산 가능한 ledger”, “BLOCK/UNKNOWN/ABSTAIN 전체 분기”, “Owner 결정이 반영된 Fine·readout·GPS·eval 접합”, “Report Video까지 이어지는 E2E”를 아직 증명하지 못한다. 또한 `01`·`04`의 준비 가능 문구는 `05`의 미해소 목록 및 현재 이슈 상태와 함께 읽어야 하며, 단독 readiness 근거로 사용하면 안 된다.

따라서 현재 상태를 `완료`나 `E2E_READY`로 부르지 않고 다음처럼 유지한다.

```
MOCK_SCHEMA_VALIDATED
EVIDENCE_COMMON_PARTIAL_READY
OWNER_DECISIONS_RECORDED_BUT_NOT_APPLIED
MOCK_DOCUMENTATION_STATUS_NOT_SYNCHRONIZED
POLICY_AND_RUNTIME_INTEGRATION_NOT_VERIFIED
REQUEST_CHANGES
```
