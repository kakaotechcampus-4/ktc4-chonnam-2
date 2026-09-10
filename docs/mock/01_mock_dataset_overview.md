# 01. Mock Dataset Overview — 대신고 공용 Mock Fixture Pack

> **⚠️ 먼저 읽을 것 — `05_mock_deep_review_report.md`.** 이 Pack은 심층 검토를 한 번 거쳤고, 그 결과 P0 2건(`VisualEvidence`가 Coarse run에 연결됨 · 「화면 시각 없음」 모델링)이 **아직 미해소 상태**다. 각 모듈 Owner의 답변을 기다리는 항목이며 05 §12에 정리돼 있다. fixture를 그대로 믿고 구현을 시작하기 전에 05 §0과 §12를 먼저 보라.

## 1. 목적

이 Mock Pack은 **새 Product/Architecture/Data Contract를 설계하지 않는다.** `origin/develop`에서 데이터 계약이 전부 종결된 상태(커밋 `8fc0ced`, 2026-09-08, 로드맵 「③ 데이터 계약 확정 ✓ → ④ 목데이터 1차 통합」)를 그대로 확장해 실제 실행 가능한 JSON 예시 데이터로 만든 것이다.

목적은 다음이며, 실제 AI/OCR/Search 성능을 증명하는 용도가 **아니다**:

- Data Contract 검증 (필드 모양이 실제로 파싱·직렬화되는가)
- Producer/Consumer 연결 검증 (모듈 간 ID·참조가 실제로 이어지는가)
- Parser/Serializer 개발
- 상태 전이(state transition) 검증
- 부분 실패 / UNKNOWN / ABSTAIN 처리 검증
- Web/UI 병렬 개발 (CaseView safe projection)
- Case orchestration 개발
- Eval Harness의 초기 metric 코드 검증
- 1차 Mock End-to-End 통합

## 2. Source of Truth

- `docs/architecture/module-architecture.md` v4
- `docs/management/ownership.md` (R&R)
- `docs/architecture/contracts/*.md` — Final Data Contract 14건 + Draft 1건(`contract-correction-record.md`)
- 관련 ADR (`docs/architecture/adr/*.md`), 특히 `adr-data-contract-call-closure-2026-09-07.md` · `-08.md`

계약이 서로 충돌하거나 불명확한 지점을 발견해도 **이 Mock 생성 작업 중에는 그 설계 문제를 직접 고치지 않는다.** 발견한 것은 전부 `04_mock_validation_report.md`의 「발견한 문제」 절에 보고했다.

## 3. Contract Inventory

| # | Contract | Producer | Consumer | 역할 | 참조하는 다른 Contract |
| --- | --- | --- | --- | --- | --- |
| 1 | `SourceAsset` / `MediaStream` / `FrameRef` / `AssetFacts` | recording | search·readout·evidence·case(projection) | 원본 파일 자산·스트림·프레임 opaque 참조 | — (최하위) |
| 2 | `RecordingTimeline` / `AssetSpan` / `SpanResolution` / `TimeSourceCandidate` | recording | search·evidence·case | 다중 파일을 하나의 사건 timeline으로 정렬 | #1 |
| 3 | `AnalysisSource` / `IncidentClip` / `DerivedAsset` / `RemoteCopy` / `DeletionReport` | recording | search·readout·evidence | 분석/판독/신고용 파생 자산과 그 정리(삭제) | #1·#2 |
| 4 | `AnalysisScope` / `AnalysisRun` / `CandidateEvent` | search | case(direct)·evidence·eval | 사건 후보 탐색 실행과 후보 목록 | #2 |
| 5 | `VisualEvidence` | search | evidence·eval | 후보에 대한 시각적 관찰 근거 | #3·#4 |
| 6 | `PlateReadout` / `OverlayTimeReadout` | readout | case(direct)→evidence(projection)·eval | 번호판·화면 시각 관찰값, abstain 근거 | #3·#4 |
| 7 | `ReadoutRun` | readout | case·eval | 판독 실행 1회의 성공/부분/실패 기록 | #6 |
| 8 | `TimeResolution` | evidence | case(direct)·web(projection) | 사건 발생시각 최종 확정과 충돌 provenance | #2·#6·(Draft)`CorrectionRecord` |
| 9 | `EvidenceRecord` / `EvidenceNeeds` | evidence | case(direct)·web(projection) | confirmed value snapshot + 보강 필요 declarative value | #4·#5·#6·#8 |
| 10 | `RequirementReport` / `ReportPackage` | evidence | case(direct)·web(projection) | 신고요건 판정, 신고용 handoff bundle | #1·#9 |
| 11 | `JobRecord` (Job Intent) | case | common/runtime·eval·web(간접) | 발주된 작업 1건, append-only | #4·#6·#9 |
| 12 | `CaseView` | case | web·eval(간접) | web이 읽는 유일한 통합 상태, safe projection | #1~#11 전체 |
| 13 | `JobExecution` | common/runtime | case·web(projection)·eval | Job 1건의 실행 상태 1회분 | #11 |
| 14 | `UsageRecord` | common/runtime | case·eval·search·readout | 외부 유료 호출 1건의 사용량/비용 원장 | #4·#7·#13 |
| (Draft) | `CorrectionRecord` | case | evidence(TimeResolution 근거) | 사용자 정정 기록 — **아직 Draft**, 이 Mock Pack은 opaque ref로만 참조 | — |

데이터 흐름은 대략 `recording → search → readout → evidence → case → web` 순서로 쌓이며, `common/runtime`(`JobExecution`·`UsageRecord`)이 `case`가 발주한 작업의 실행 계층을 옆에서 채운다.

```
recording  ──▶  search  ──▶  readout  ──▶  evidence  ──▶  case  ──▶  web
    │              │             │             │            │
    └──────────────┴─────────────┴─────────────┴────────────┘
                         common/runtime (JobExecution, UsageRecord)
```

## 4. Contract Consistency Check 결과

전체 14 Final Contract + 1 Draft를 다시 읽고 이름·enum·unit·nullable·ID 참조·UNKNOWN/FAILURE/ABSTAIN 의미 축을 교차 검사했다. 발견한 항목은 전부 `04_mock_validation_report.md`에 있다. 요약:

**Mock 생성 진행 가능** — 치명적 충돌(다른 계약이 서로 값을 부정하는 경우)은 없었다. 다만 진행 가능 판단과 별개로 아래 7건은 이 문서와 검증 리포트에 명시적으로 보고한다(고치지 않았다). 이후 심층 검토에서 추가로 발견한 항목은 `05_mock_deep_review_report.md` §8에 있다:

1. `contract-visual-evidence.md`의 JSON 예시가 `frame:incident-17@6400` 같은 위치 인코딩 문자열을 그대로 쓰고 있어 이후 확정된 opaque `FrameRef`(`fr_<opaque-id>`) 관례와 형식이 다르다.
2. `JobRecord.kind`에 Report Video export / `purge_case()` 발주용 값이 아직 등재되지 않았다.
3. `TimeResolution.resolved.verification`(`AGREED/VERIFIED/UNVERIFIED`) 중 어떤 값이 `computation.mode=USER_OVERRIDE`(사용자 정정)와 짝을 이루는지 계약이 명시하지 않는다.
4. `EvidenceRecord`의 「사용자 원본 입력(한 번도 AI 추정을 거치지 않은 값)」에 대해 `source.observability`(OBSERVED/INFERRED)와 `user_corrected`를 어떻게 매기는지 계약이 명시하지 않는다.
5. `CaseView.evidence.review_needed`(object-level)가 개별 `*_display.needs_review`/`info_state`와 어떤 파생 규칙으로 연결되는지 계약이 명시하지 않는다.
6. `EvidenceRecord.event.safety_report_type`의 실제 값 공간(안전신문고 신고유형 enum/코드 목록)이 어느 Final Contract에도 등재돼 있지 않다.
7. `contract-correction-record.md`가 아직 Draft라서, `TimeResolution`/`EvidenceRecord`가 구조적으로 참조하는 `CorrectionRecord`의 필드 스키마를 이 Mock Pack이 생성할 수 없다.

## 5. 전체 구성

```
data/mock/
  manifest.json                                 # Mock 전체 색인 (Mock 관리 전용, Contract 아님)
  scenarios/
    scenario_happy_001.json                     # 시나리오별 manifest (Mock 관리 전용)
    scenario_empty_001.json
    scenario_unknown_abstain_partial_001.json
    scenario_plate_reread_001.json
    scenario_correction_rerun_001.json
    scenario_infra_failure_001.json
    scenario_relative_rebase_001.json           # 시나리오 4개→7개로 확장(2026-09-09~10, `02_mock_scenario_catalog.md` 참고)
  recording/  scenario_*.json                   # SourceAsset~DeletionReport
  search/     scenario_*.json                   # AnalysisScope~VisualEvidence
  readout/    scenario_*.json                   # ReadoutRun~OverlayTimeReadout
  evidence/   scenario_*.json                   # TimeResolution~ReportPackage
  case/       scenario_*.json                   # JobRecord~CaseView
  common/     scenario_*.json                   # JobExecution~UsageRecord
  expected/
    eval_fixture_correct_001.json                # Eval 전용, Mock Runtime Output과 분리
    eval_fixture_wrong_001.json
  validate_mock_pack.py                          # 경량 자동 검증 스크립트
docs/mock/
  01_mock_dataset_overview.md   (이 문서)
  02_mock_scenario_catalog.md
  03_mock_artifact_templates.md   # fixture에서 자동 추출 — 직접 편집하지 말 것
  04_mock_validation_report.md
  05_mock_deep_review_report.md   # 심층 검토 결과 + 남은 작업 + Owner 확인 항목
  CONTRACT_CONFLICTS.md           # 계약 문제 인덱스
scripts/
  build_artifact_templates_doc.py # 03 재생성 스크립트
```

각 `<module>/scenario_*.json` 파일은 `{"scenario_id": ..., "module": ..., <계약별 배열...>}` 형태의 **얇은 wrapper**다. `scenario_id`/`module` 키는 이 wrapper에만 있고, 그 안의 실제 Contract 객체(예: `SourceAsset`, `PlateReadout`)에는 없다 — 즉 런타임 Contract 스키마에 `scenario_id`를 추가한 것이 아니다. 시나리오 간 관계는 오직 `data/mock/scenarios/*.json`과 `data/mock/manifest.json`(둘 다 Mock 관리 전용 파일)에서만 표현한다.

## 6. 공통 기준 시나리오

| Scenario ID | 커버 타입 | 한 줄 요약 |
| --- | --- | --- |
| `scenario_happy_001` | A | 정상 경로 — 등록부터 ReportPackage 생성까지 전체 파이프라인 1회 통과 |
| `scenario_empty_001` | B | Candidate Search 결과 0건(빈 배열 ≠ 실패) |
| `scenario_unknown_abstain_partial_001` | E·H | 화면시각 NOT_APPLICABLE, 시각 소스 충돌, 사건유형 확정 불가 → WARN 경로로 `stage=READY`까지 진행 |
| `scenario_plate_reread_001` | C·D·G·I | 사건유형은 확정, 번호판만 abstain → `EvidenceNeeds` 자동 재판독 발주 |
| `scenario_correction_rerun_001` | F·I | 사용자 시각 정정 → TimeResolution/EvidenceRecord/RequirementReport supersede 체인, Overlay NOT_APPLICABLE 구분 |
| `scenario_infra_failure_001` | J | readout 인프라 실패 — STALE 재시도 후 FAILED, blocking notice |
| `scenario_relative_rebase_001` | K | Timeline 상대전용(`USABLE_RELATIVE_ONLY`) + rebase + `SpanResolution PARTIAL` |

> **2026-09-09~10 갱신.** 이 표는 최초 4개 시나리오(A~I 9개 유형) 버전을 서술하던 것을 7개 시나리오·11개 유형(A~K) 현재 상태로 정정했다. 분리·확장 경위는 `02_mock_scenario_catalog.md` 상단 버전 노트, 상세 매핑도 그 문서 참고.

## 7. 사용 원칙

- 모든 Mock 객체는 **공식 cross-module Contract 객체**만 표현한다. 어떤 모듈의 내부 SDK/ORM/AI-모델 객체도 흉내내지 않는다.
- 같은 Scenario에 속한 모든 모듈의 artifact는 **같은 opaque ID**로 서로를 참조한다(`validate_mock_pack.py`가 기계적으로 검사한다).
- ID는 사람이 읽을 수 있는 접두어(`sa_`·`ms_`·`fr_`·`tl_`·`tsc_`·`candidate_`·`ve_`·`readout_`·`rr_`·`tres_`·`ev_`·`req_`·`pkg_`·`job_`·`exec_`·`usage_`·`case_`)를 쓰되 **위치를 ID에 인코딩하지 않는다**(팀 기존 원칙).
- Mock은 **완전히 결정론적**이다 — 난수·현재 시각·외부 API 호출이 전혀 없다.
- **정의 객체가 없는 opaque ref가 몇 개 있다** — `crop_ref`(`crop_h001_001` 등)·`track_ref`(`track_h001`)는 `readout` 내부 식별자이고, `profile_ref`·`transform_ref`·`template_ref`·`policy_ref`·`pricing_id`는 각 계약이 opaque로 규정한 값이다. 이들을 가리키는 별도 fixture 객체는 없으며 찾을 필요도 없다(검증 스크립트도 참조 해석 대상에서 제외한다). `external_source`(`ext_*`)와 `correction_record`(`cr_*`)도 같은 이유로 제외 — 전자는 계약 집합 밖의 업로드 원본이고, 후자는 아직 Draft다.
- `null` / `[]`(빈 배열) / `UNKNOWN` / `ABSTAIN` / `FAILED` / `NOT_RUN`(레코드 자체 부재)은 서로 다른 의미이며 절대 하나로 합치지 않았다. 예: `scenario_correction_rerun_001`은 `OverlayTimeReadout`을 아예 시도하지 않아 `readout_runs`에 overlay 항목이 없다(`FAILED`가 아니라 `NOT_RUN`).
- Mock Runtime Output(각 모듈 fixture)과 Eval Ground Truth(`expected/`)는 완전히 분리했다. Search 후보 A/B/C 자체가 정답이 아니다.

## 8. 1차 Mock E2E 통합 준비 완료 기준

아래는 이 Mock Pack이 만족하는지를 스스로 점검한 완료 체크리스트다(상세 근거는 `04_mock_validation_report.md` §4·§5).

| # | 조건 | 상태 |
| --- | --- | --- |
| 1 | 핵심 Final Data Contract마다 fixture ≥1건 | ✅ |
| 2 | 대표 Happy Path가 전체 시스템을 관통 | ✅ (`scenario_happy_001`) |
| 3 | 부분 실패/불확실성 시나리오 ≥1건 | ✅ (`scenario_unknown_abstain_partial_001`) |
| 4 | ABSTAIN/UNKNOWN 시나리오(Contract 관련 있는 곳) | ✅ |
| 5 | 한 Scenario 내 ID/참조/시간값 상호 일관 | ✅ (`validate_mock_pack.py` 통과) |
| 6 | Mock Runtime Output ≠ Eval Ground Truth | ✅ (`expected/` 분리, provisional 명시) |
| 7 | Web이 쓸 수 있는 공유 View/Projection fixture | ✅ (`case/*.json`의 `case_views[]` = `CaseView`) |
| 8 | Eval이 fixture로 자신의 기본 Metric 코드를 검증 가능 | ✅ (`expected/eval_fixture_*`, provisional 명시) |
| 9 | 실제 JSON 파일이 디스크에 존재 | ✅ |
| 10 | 문서 4종 모두 존재 | ✅ |
| 11 | 발견한 Contract 문제를 숨기지 않음 | ✅ (§4, `04_mock_validation_report.md`) |
| 12 | Owner별 검수 책임 문서화 | ✅ (`04_mock_validation_report.md` §6) |

## 9. 금지 사항 (이 작업 중 지킨 것)

Final Contract를 Mock 편의로 수정하지 않았다 / Contract에 없는 필드를 추가하지 않았다 / 모듈 내부 구현 세부를 Mock-Contract로 승격하지 않았다 / 존재하지 않는 제품 기능·법률/비즈니스 규칙을 만들지 않았다 / 서로 다른 실패 유형을 `null` 하나로 뭉치지 않았다 / 임의의 confidence·metric 숫자를 실제 성능인 것처럼 쓰지 않았다 / Mock Dataset을 실제 Evaluation Dataset처럼 다루지 않았다 / 서로 무관한 JSON을 만들지 않았다 / 한 Scenario 안에서 ID/참조가 모순되게 두지 않았다 / 문서만 만들고 끝내지 않았다(실제 JSON 파일 29개 — 모듈 fixture 22 + scenario manifest 4 + 상위 manifest 1 + eval fixture 2 — 및 검증 스크립트 생성) / 한 모듈의 Mock이 다른 모듈의 판단 책임을 대신하지 않았다 / 발견한 Contract 충돌을 임의 해석으로 숨기지 않았다.
